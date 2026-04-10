import { useEffect, useRef } from 'react'

export default function Workspace({
  step,
  origHtml, fmtHtml,
  origTag, fmtTag,
  origLoading, fmtLoading, fmtLoadingMsg, fmtLoadingSub,
  actionInfo,
  mainBtnDisabled, showReset,
  onMainAction, onReset,
  origBodyRef, fmtBodyRef, splitRef,
}) {
  const dividerRef = useRef(null)

  // Divider drag
  useEffect(() => {
    const divider = dividerRef.current
    const split = splitRef?.current
    if (!divider || !split) return

    let dragging = false, startX, startLeft

    const onDown = e => {
      dragging = true
      startX = e.clientX
      startLeft = parseFloat(getComputedStyle(split).gridTemplateColumns.split(' ')[0])
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
    }
    const onMove = e => {
      if (!dragging) return
      const total = split.offsetWidth - 5
      const ratio = Math.min(.85, Math.max(.15, (startLeft + e.clientX - startX) / total))
      split.style.gridTemplateColumns = `${ratio * 100}% 5px ${(1 - ratio) * 100}%`
    }
    const onUp = () => {
      if (dragging) { dragging = false; document.body.style.cursor = ''; document.body.style.userSelect = '' }
    }

    divider.addEventListener('mousedown', onDown)
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    return () => {
      divider.removeEventListener('mousedown', onDown)
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
  }, [splitRef])

  // Main button label/style by step
  let mainBtnCls = 'btn btn-primary btn-lg'
  let mainBtnTxt = '選擇格式'
  if (step === 2) mainBtnTxt = '匯入論文'
  else if (step >= 5) { mainBtnTxt = '匯出修正後論文'; mainBtnCls = 'btn btn-ok btn-lg' }

  return (
    <div className="split-wrap">
      <div className="split" ref={splitRef}>

        {/* LEFT: original */}
        <div className="pane">
          <div className="pane-hdr">
            <span>原始論文</span>
            <span className="pane-tag">{origTag}</span>
          </div>
          <div className="pane-body" ref={origBodyRef}>
            {!origHtml && (
              <div className="ph">
                <span className="ph-icon">📄</span>
                <p>請先選擇格式並匯入論文</p>
              </div>
            )}
            {origHtml && (
              <div dangerouslySetInnerHTML={{ __html: `<div class="doc-paper">${origHtml}</div>` }} />
            )}
            {origLoading && (
              <div className="pane-overlay">
                <div className="spin-lg" />
                <div className="ov-title">讀取論文中…</div>
              </div>
            )}
          </div>
        </div>

        <div className="divider" ref={dividerRef} />

        {/* RIGHT: formatted */}
        <div className="pane">
          <div className="pane-hdr">
            <span>修正後論文</span>
            <span className="pane-tag">{fmtTag}</span>
          </div>
          <div className="pane-body" ref={fmtBodyRef}>
            {!fmtHtml && (
              <div className="ph">
                <span className="ph-icon">✨</span>
                <p>修正後的論文將顯示於此</p>
              </div>
            )}
            {fmtHtml && (
              <div dangerouslySetInnerHTML={{ __html: `<div class="doc-paper">${fmtHtml}</div>` }} />
            )}
            {fmtLoading && (
              <div className="pane-overlay">
                <div className="spin-lg" />
                <div className="ov-title">{fmtLoadingMsg}</div>
                {fmtLoadingSub && <div className="ov-sub">{fmtLoadingSub}</div>}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Action bar */}
      <div id="action-bar">
        <div
          className="action-info"
          dangerouslySetInnerHTML={{ __html: actionInfo }}
        />
        {showReset && (
          <button className="btn btn-ghost" onClick={onReset}>重新開始</button>
        )}
        <button
          className={mainBtnCls}
          disabled={mainBtnDisabled}
          onClick={onMainAction}
        >
          {mainBtnTxt}
        </button>
      </div>
    </div>
  )
}