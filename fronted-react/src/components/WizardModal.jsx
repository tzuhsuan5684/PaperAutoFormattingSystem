import { useRef, useState } from 'react'

const API = 'http://localhost:8000'

export default function WizardModal({ panel, schools, schoolsLoading, onClose, onConfirmSchool, onConfirmCustom, onStartScan }) {
  const [selectedSchool, setSelectedSchool] = useState(null)
  const [cfPdfFile, setCfPdfFile] = useState(null)
  const [cfText, setCfText] = useState('')
  const [cfHint, setCfHint] = useState('支援 PDF')
  const [parsing, setParsing] = useState(false)
  const [parsedRules, setParsedRules] = useState(null)
  const [customConfig, setCustomConfig] = useState(null)

  // Upload paper state
  const [paperFile, setPaperFile] = useState(null)
  const [dzOver, setDzOver] = useState(false)

  const cfFileRef = useRef(null)
  const paperFileRef = useRef(null)

  // ── Panel routing ──
  const show = id => id === panel

  // ── Helpers ──
  function formatSize(n) {
    return n < 1024 ? n + 'B' : n < 1048576 ? (n / 1024).toFixed(1) + 'KB' : (n / 1048576).toFixed(1) + 'MB'
  }

  // ── Custom format ──
  function handleCfFile(f) {
    if (!f.name.toLowerCase().endsWith('.pdf')) { alert('請上傳 .pdf 格式'); return }
    setCfPdfFile(f)
    setCfHint(f.name)
    setCfText('')
  }

  async function parseCustomFormat() {
    setParsing(true)
    try {
      let res
      if (cfPdfFile) {
        const form = new FormData()
        form.append('file', cfPdfFile)
        res = await fetch(`${API}/parse-format-pdf`, { method: 'POST', body: form })
      } else {
        const text = cfText.trim()
        if (!text) { alert('請輸入格式規定文字，或上傳 PDF'); return }
        res = await fetch(`${API}/parse-format`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        })
      }
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '解析失敗')
      const data = await res.json()
      setCustomConfig(data.config)
      setParsedRules(data.rules_display || data.config)
      onClose('p1c')
    } catch (err) {
      alert(`AI 解析不可用：${err.message}`)
    } finally {
      setParsing(false)
    }
  }

  function confirmCustom() {
    onConfirmCustom({ config: customConfig, schoolId: '_custom', schoolName: '自訂格式' })
  }

  // ── Paper upload ──
  function acceptPaper(f) {
    if (!f.name.toLowerCase().endsWith('.docx')) { alert('僅支援 .docx 格式'); return }
    setPaperFile(f)
  }

  function removePaper() {
    setPaperFile(null)
    if (paperFileRef.current) paperFileRef.current.value = ''
  }

  return (
    <div id="overlay" onClick={e => e.target === e.currentTarget && onClose(null)}>
      <div className="card">

        {/* P1: Select school */}
        {show('p1') && (
          <>
            <div className="card-hdr">
              <div className="card-title">選擇學校格式</div>
              <div className="card-sub">請選擇您的學校，系統將依該校格式規範進行檢查與修正</div>
            </div>
            <div className="card-body">
              <div className="school-list">
                {schoolsLoading ? (
                  <div className="ph" style={{ height: 80 }}>
                    <div className="spin-lg" />
                    <p>載入學校清單中…</p>
                  </div>
                ) : schools.length === 0 ? (
                  <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>無法連線到後端（port 8000），請確認伺服器已啟動</p>
                ) : (
                  schools.map(s => (
                    <label
                      key={s.school_id}
                      className={`school-opt${selectedSchool?.school_id === s.school_id ? ' sel' : ''}`}
                      onClick={() => setSelectedSchool(s)}
                    >
                      <input type="radio" name="school" value={s.school_id} readOnly checked={selectedSchool?.school_id === s.school_id} />
                      <span className="school-nm">{s.school_name}</span>
                      <span className="school-id">{s.school_id.toUpperCase()}</span>
                    </label>
                  ))
                )}
              </div>
              <div className="sep">或</div>
              <button className="custom-btn" onClick={() => onClose('p1b')}>
                <span>📂</span><span>自行匯入格式規定文件</span>
              </button>
            </div>
            <div className="card-foot">
              <button className="btn btn-ghost" onClick={() => onClose(null)}>取消</button>
              <button
                className="btn btn-primary"
                disabled={!selectedSchool}
                onClick={() => onConfirmSchool(selectedSchool)}
              >下一步</button>
            </div>
          </>
        )}

        {/* P1B: Custom format */}
        {show('p1b') && (
          <>
            <div className="card-hdr">
              <div className="card-title">匯入自訂格式規定</div>
              <div className="card-sub">請上傳格式規定文件，或貼上文字，系統將自動解析格式規則</div>
            </div>
            <div className="card-body">
              <label className="lbl">上傳格式規定文件（.pdf）</label>
              <div
                className="cf-drop"
                onClick={() => cfFileRef.current?.click()}
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); if (e.dataTransfer.files[0]) handleCfFile(e.dataTransfer.files[0]) }}
              >
                📎 點擊上傳，或將文件拖曳至此
                <div style={{ fontSize: 11, marginTop: 4, opacity: .6 }}>{cfHint}</div>
              </div>
              <input type="file" ref={cfFileRef} className="hidden-inp" accept=".pdf" onChange={e => e.target.files[0] && handleCfFile(e.target.files[0])} />
              <div className="sep">或直接貼上文字</div>
              <label className="lbl">格式規定內容</label>
              <textarea
                className="cf-textarea"
                value={cfText}
                onChange={e => setCfText(e.target.value)}
                placeholder={'例如：\n字體：標楷體 12pt\n行距：1.5 倍\n邊界：上下 2.5cm、左 3cm、右 2cm'}
              />
              {parsing && (
                <div className="parsing-msg">
                  <div className="spinner" style={{ borderColor: 'rgba(59,130,246,.3)', borderTopColor: 'var(--accent)' }} />
                  <span>AI 解析格式規定中，請稍候…</span>
                </div>
              )}
            </div>
            <div className="card-foot">
              <button className="btn btn-ghost" onClick={() => onClose('p1')}>← 返回</button>
              <button className="btn btn-primary" onClick={parseCustomFormat} disabled={parsing}>解析格式規則</button>
            </div>
          </>
        )}

        {/* P1C: Confirm rules */}
        {show('p1c') && (
          <>
            <div className="card-hdr">
              <div className="card-title">確認格式規則</div>
              <div className="card-sub">請確認以下由 AI 解析出的格式規則</div>
            </div>
            <div className="card-body">
              <div className="rules-list">
                <RulesDisplay src={parsedRules} />
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 12 }}>※ 如有錯誤，請返回修改後重新解析</p>
            </div>
            <div className="card-foot">
              <button className="btn btn-ghost" onClick={() => onClose('p1b')}>← 返回</button>
              <button className="btn btn-primary" onClick={confirmCustom}>確認並繼續</button>
            </div>
          </>
        )}

        {/* P2: Upload paper */}
        {show('p2') && (
          <>
            <div className="card-hdr">
              <div className="card-title">匯入論文</div>
              <div className="card-sub">請上傳您的論文（.docx 格式）</div>
            </div>
            <div className="card-body">
              <div
                className={`drop-zone${dzOver ? ' over' : ''}${paperFile ? ' has-file' : ''}`}
                onClick={() => !paperFile && paperFileRef.current?.click()}
                onDragOver={e => { e.preventDefault(); setDzOver(true) }}
                onDragLeave={() => setDzOver(false)}
                onDrop={e => { e.preventDefault(); setDzOver(false); if (e.dataTransfer.files[0]) acceptPaper(e.dataTransfer.files[0]) }}
              >
                <span className="dz-icon">{paperFile ? '✅' : '📂'}</span>
                <div className="dz-title">{paperFile ? '已選擇論文' : '點擊選擇，或拖曳論文至此'}</div>
                <div className="dz-hint">{paperFile ? '' : '支援 .docx 格式'}</div>
              </div>
              <input type="file" ref={paperFileRef} className="hidden-inp" accept=".docx" onChange={e => e.target.files[0] && acceptPaper(e.target.files[0])} />

              {paperFile && (
                <div className="file-info-row">
                  <span>📄</span>
                  <span className="file-nm">{paperFile.name}</span>
                  <span className="file-sz">{formatSize(paperFile.size)}</span>
                  <button className="rm-btn" onClick={removePaper}>✕</button>
                </div>
              )}

              <div style={{ marginTop: 14, padding: '10px 12px', background: 'var(--warn-bg)', border: '1px solid var(--warn-bd)', borderRadius: 'var(--r)', fontSize: 12, color: 'var(--warn)' }}>
                ⚠ 建議先備份原始論文，修正為不可逆操作
              </div>
            </div>
            <div className="card-foot">
              <button className="btn btn-ghost" onClick={() => onClose('p1')}>← 返回</button>
              <button className="btn btn-primary" disabled={!paperFile} onClick={() => onStartScan(paperFile)}>開始掃描</button>
            </div>
          </>
        )}

      </div>
    </div>
  )
}

// ── Rules display ──
function RulesDisplay({ src }) {
  if (!src) return null

  if (src && typeof src === 'object' && !Array.isArray(src) && (src.global_rules || src.thesis_sections)) {
    return (
      <>
        {src.global_rules && (
          <RuleSection title="全域規則" rows={flattenObj(src.global_rules)} />
        )}
        {Array.isArray(src.thesis_sections) && src.thesis_sections.map((sec, i) => {
          const rows = []
          if (sec.content_requirements?.length)
            rows.push(['必須包含', <ul>{sec.content_requirements.map((r, j) => <li key={j}>{r}</li>)}</ul>])
          if (sec.specific_constraints)
            rows.push(['排版限制', sec.specific_constraints])
          return <RuleSection key={i} title={sec.section_name || '未命名章節'} attachment={sec.attachment} rows={rows} />
        })}
      </>
    )
  }

  const entries = Array.isArray(src) ? src : Object.entries(src)
  return (
    <RuleSection title="格式規則" rows={entries.map(([k, v]) => [k, typeof v === 'object' ? JSON.stringify(v) : v])} />
  )
}

function RuleSection({ title, attachment, rows = [] }) {
  return (
    <div className="rule-section">
      <div className="rule-section-hdr">
        {title}
        {attachment && <span className="rs-attach">{attachment}</span>}
      </div>
      <div className="rule-section-body">
        {rows.length === 0 ? (
          <div className="rule"><div className="rule-v" style={{ color: 'var(--text-muted)' }}>無詳細規定</div></div>
        ) : rows.map(([k, v], i) => (
          <div className="rule" key={i}>
            <div className="rule-k">{k}</div>
            <div className="rule-v">{v ?? <span style={{ color: 'var(--text-muted)' }}>—</span>}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function flattenObj(obj, prefix) {
  const rows = []
  for (const [k, v] of Object.entries(obj)) {
    const label = prefix ? `${prefix} › ${k}` : k
    if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
      rows.push(...flattenObj(v, label))
    } else {
      rows.push([label, v ?? null])
    }
  }
  return rows
}