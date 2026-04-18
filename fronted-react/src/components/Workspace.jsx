import { useEffect, useRef } from 'react'
import { renderAsync } from 'docx-preview'

const RENDER_OPTS = {
  inWrapper: true,
  ignoreWidth: false,
  ignoreHeight: false,
  breakPages: true,
  useBase64URL: true,
  renderHeaders: true,
  renderFooters: true,
}

export default function Workspace({
  step,
  origFile, fmtFile,
  origTag, fmtTag,
  origLoading, fmtLoading, fmtLoadingMsg, fmtLoadingSub,
  actionInfo,
  mainBtnDisabled, showReset,
  onMainAction, onReset,
  origBodyRef, fmtBodyRef, splitRef,
  onOrigRendered, onFmtRendered,
  showTexBtn, onExportTex,
}) {
  const dividerRef = useRef(null)
  const origDocRef = useRef(null)
  const fmtDocRef = useRef(null)
  const origTexts = useRef(null)   // Set<string> of orig paragraph texts for diff

  // ── Render original ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!origFile || !origDocRef.current) return
    const el = origDocRef.current
    el.innerHTML = ''
    origFile.arrayBuffer().then(buf =>
      renderAsync(buf, el, null, RENDER_OPTS)
        .then(() => {
          origTexts.current = new Set(
            Array.from(el.querySelectorAll('p'))
              .map(p => p.textContent.trim())
              .filter(Boolean)
          )
          onOrigRendered?.()
        })
        .catch(console.error)
    )
  }, [origFile])   // eslint-disable-line react-hooks/exhaustive-deps

  // ── Render formatted + apply diff ────────────────────────────────────────
  useEffect(() => {
    if (!fmtFile || !fmtDocRef.current) return
    const el = fmtDocRef.current
    el.innerHTML = ''
    fmtFile.arrayBuffer().then(buf =>
      renderAsync(buf, el, null, RENDER_OPTS)
        .then(() => {
          // Highlight paragraphs that moved or don't exist in orig
          if (origTexts.current) {
            el.querySelectorAll('p').forEach(p => {
              const t = p.textContent.trim()
              if (t && !origTexts.current.has(t)) p.classList.add('diff-chg')
            })
          }
          onFmtRendered?.()
        })
        .catch(console.error)
    )
  }, [fmtFile])   // eslint-disable-line react-hooks/exhaustive-deps

  // ── Divider drag ─────────────────────────────────────────────────────────
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
            {!origFile && (
              <div className="ph">
                <span className="ph-icon">📄</span>
                <p>請先選擇格式並匯入論文</p>
              </div>
            )}
            <div ref={origDocRef} className="docx-container" style={{ display: origFile ? 'block' : 'none' }} />
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
            {!fmtFile && (
              <div className="ph">
                <span className="ph-icon">✨</span>
                <p>修正後的論文將顯示於此</p>
              </div>
            )}
            <div ref={fmtDocRef} className="docx-container" style={{ display: fmtFile ? 'block' : 'none' }} />
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
        <div className="action-info" dangerouslySetInnerHTML={{ __html: actionInfo }} />
        {showReset && (
          <button className="btn btn-ghost" onClick={onReset}>重新開始</button>
        )}
        {showTexBtn && step >= 5 && (
          <button className="btn btn-ghost" onClick={onExportTex}>下載 .tex</button>
        )}
        <button className={mainBtnCls} disabled={mainBtnDisabled} onClick={onMainAction}>
          {mainBtnTxt}
        </button>
      </div>
    </div>
  )
}
