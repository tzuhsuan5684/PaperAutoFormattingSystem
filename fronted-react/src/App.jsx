import { useState, useRef, useEffect, useCallback } from 'react'
import Header from './components/header'
import Workspace from './components/Workspace'
import Sidebar from './components/Sidebar'
import WizardModal from './components/WizardModal'
import './index.css'

const API = 'http://localhost:8000'

const SECTION_KW = {
  '封面': ['封面'], '書名頁': ['書名頁'], '授權書': ['授權書'],
  '口試委員審定書': ['口試委員', '審定書'], '中文摘要': ['中文摘要', '摘要'],
  '英文摘要': ['abstract', 'Abstract', '英文摘要'], '誌謝': ['誌謝', '致謝'],
  '目錄': ['目錄'], '圖目錄': ['圖目錄', '圖次'], '表目錄': ['表目錄', '表次'],
  '論文正文': ['第一章', '緒論', 'Chapter 1', 'Introduction'],
  '參考文獻': ['參考文獻', 'References'], '圖說': ['圖', 'Figure'],
}


export default function App() {
  const [step, setStep] = useState(1)
  const [school, setSchool] = useState(null)
  const [schools, setSchools] = useState([])
  const [schoolsLoading, setSchoolsLoading] = useState(true)
  const [modalPanel, setModalPanel] = useState('p1')

  // File objects (replacing HTML strings)
  const [origFile, setOrigFile] = useState(null)
  const [fmtFile,  setFmtFile]  = useState(null)

  const [origTag, setOrigTag] = useState('尚未匯入')
  const [fmtTag,  setFmtTag]  = useState('尚未修正')
  const [origLoading, setOrigLoading] = useState(false)
  const [fmtLoading,  setFmtLoading]  = useState(false)
  const [fmtLoadingMsg, setFmtLoadingMsg] = useState('')
  const [fmtLoadingSub, setFmtLoadingSub] = useState('')

  const [issues,        setIssues]        = useState([])
  const [issuesAfter,   setIssuesAfter]   = useState([])
  const [activeIssueIdx, setActiveIssueIdx] = useState(null)
  const [downloadToken, setDownloadToken] = useState(null)
  const [texToken,      setTexToken]      = useState(null)
  const [mode,          setMode]          = useState('rule')  // 'rule' | 'ai'

  const [actionInfo,      setActionInfo]      = useState('請先選擇學校格式，再匯入論文。')
  const [mainBtnDisabled, setMainBtnDisabled] = useState(false)
  const [showReset,       setShowReset]       = useState(false)
  const [toast,           setToast]           = useState(null)

  // Pending state that waits for docx render callbacks
  const pendingState = useRef(null)

  const toastTimer  = useRef(null)
  const splitRef    = useRef(null)
  const origBodyRef = useRef(null)
  const fmtBodyRef  = useRef(null)

  const showToast = useCallback(msg => {
    setToast(msg)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 3200)
  }, [])

  useEffect(() => {
    fetch(`${API}/schools`)
      .then(r => r.json())
      .then(d => setSchools(d.schools || []))
      .catch(() => setSchools([]))
      .finally(() => setSchoolsLoading(false))
    setModalPanel('p1')
  }, [])

  // ── Issue navigation ────────────────────────────────────────────────────
  function findHeading(container, kws) {
    for (const el of container.querySelectorAll('p, h1, h2, h3, h4')) {
      const t = el.textContent.trim().toLowerCase()
      if (kws.some(k => t.includes(k.toLowerCase()))) return el
    }
    return null
  }

  function handleIssueClick(idx) {
    setActiveIssueIdx(idx)
    const issue = issues[idx]
    if (!issue || !fmtBodyRef.current) return
    const fmtDoc = fmtBodyRef.current   // docx-preview renders p elements directly here

    const kws    = SECTION_KW[issue.section] || [issue.section]
    const chgEls = Array.from(fmtDoc.querySelectorAll('.diff-chg'))
    let targets  = []

    if (issue.section === '圖說') {
      targets = chgEls.filter(el => /^(圖|Figure)\s*\d+/i.test(el.textContent.trim()))
    } else {
      const heading = findHeading(fmtDoc, kws)
      if (heading) {
        const sibs = []
        let node = heading.nextElementSibling
        while (node && sibs.length < 5) {
          if (node.classList.contains('diff-chg')) sibs.push(node)
          node = node.nextElementSibling
        }
        targets = sibs.length ? sibs : [heading]
      } else {
        targets = chgEls.filter(el => kws.some(k => el.textContent.toLowerCase().includes(k.toLowerCase()))).slice(0, 3)
      }
    }

    if (targets.length) {
      targets[0].scrollIntoView({ behavior: 'smooth', block: 'center' })
      targets.forEach(el => {
        el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash')
        el.addEventListener('animationend', () => el.classList.remove('flash'), { once: true })
      })
    } else {
      const heading = findHeading(fmtDoc, kws)
      if (heading) {
        heading.scrollIntoView({ behavior: 'smooth', block: 'center' })
        heading.classList.add('section-flash')
        heading.addEventListener('animationend', () => heading.classList.remove('section-flash'), { once: true })
      }
    }
  }

  // ── Render callbacks from Workspace ────────────────────────────────────
  function handleOrigRendered() {
    setOrigLoading(false)
  }

  function handleFmtRendered() {
    const p = pendingState.current
    if (!p) return
    pendingState.current = null
    setFmtLoading(false)
    setStep(5)
    setOrigTag(p.origName)
    if (p.isAI) {
      setFmtTag('AI 智慧排版完成')
      setActionInfo('AI 已辨識論文結構並套用 Word 模板，可下載排版後 .docx')
    } else {
      setFmtTag(`已修正・${p.issueCount} 個問題`)
      setActionInfo(`發現 <strong>${p.issueCount}</strong> 個問題，已自動修正 <strong>${p.fixedCount}</strong> 個`)
    }
    setMainBtnDisabled(false)
    setShowReset(true)
  }

  // ── School / wizard handlers ────────────────────────────────────────────
  function handleConfirmSchool(s) {
    setSchool(s)
    setStep(2)
    setModalPanel('p2')
    setActionInfo(`已選擇：<strong>${s.school_name}</strong>，請匯入論文`)
  }

  function handleConfirmCustom({ config, schoolId, schoolName }) {
    setSchool({ school_id: schoolId, school_name: schoolName, config })
    setStep(2)
    setModalPanel('p2')
    setActionInfo(`已選擇：<strong>${schoolName}</strong>，請匯入論文`)
  }

  // ── Main scan flow ──────────────────────────────────────────────────────
  async function handleStartScan(paperFile, scanMode = 'rule') {
    if (!paperFile || !school) return
    setMode(scanMode)
    setModalPanel(null)
    setStep(3)
    setActionInfo('掃描中，請稍候…')
    setMainBtnDisabled(true)

    // Start rendering original immediately (non-blocking)
    setOrigLoading(true)
    setOrigFile(paperFile)

    setFmtLoading(true)
    const schoolId = school.school_id === '_custom' ? 'ncu' : school.school_id

    try {
      await new Promise(r => setTimeout(r, 600))
      setStep(4)

      const form = new FormData()
      form.append('file', paperFile)
      form.append('school_id', schoolId)

      if (scanMode === 'ai') {
        // ── AI Schema → Word 模板流程 ──────────────────────────────────
        setFmtLoadingMsg('AI 分析論文結構中…')
        setFmtLoadingSub('辨識摘要、章節、參考文獻等區塊…')

        const res = await fetch(`${API}/smart-format`, { method: 'POST', body: form })
        if (!res.ok) throw new Error(((await res.json().catch(() => ({}))).detail) || 'AI 排版失敗')
        const data = await res.json()

        setDownloadToken(data.download_token)
        setTexToken(null)

        const fmtBlob = await fetch(`${API}/download/${data.download_token}`).then(r => r.blob())
        const fmtFileObj = new File([fmtBlob], `smart_${paperFile.name}`, { type: fmtBlob.type })

        setFmtLoadingMsg('套用 Word 模板中…')
        setFmtLoadingSub('')
        pendingState.current = { origName: paperFile.name, isAI: true }
        setFmtFile(fmtFileObj)

      } else {
        // ── 規則修正流程 ────────────────────────────────────────────────
        setFmtLoadingMsg('掃描問題中…')
        setFmtLoadingSub('正在分析格式規範…')
        await new Promise(r => setTimeout(r, 0))
        setFmtLoadingMsg('自動修正中…')
        setFmtLoadingSub('修正頁邊距、字型、行距…')

        const res = await fetch(`${API}/format`, { method: 'POST', body: form })
        if (!res.ok) throw new Error(((await res.json().catch(() => ({}))).detail) || '格式化失敗')
        const data = await res.json()

        setIssues(data.issues_before || [])
        setIssuesAfter(data.issues_after || [])
        setDownloadToken(data.download_token)

        const fmtBlob = await fetch(`${API}/download/${data.download_token}`).then(r => r.blob())
        const fmtFileObj = new File([fmtBlob], `formatted_${paperFile.name}`, { type: fmtBlob.type })

        setFmtLoadingMsg('產生預覽中…')
        setFmtLoadingSub('')
        const issueCount = (data.issues_before || []).length
        pendingState.current = {
          origName:   paperFile.name,
          issueCount,
          fixedCount: (data.issues_before || []).filter(i => i.auto_fixed).length,
        }
        setFmtFile(fmtFileObj)
      }

    } catch (err) {
      pendingState.current = null
      setFmtLoading(false)
      setOrigLoading(false)
      showToast(`錯誤：${err.message}`)
      setActionInfo(`發生錯誤：${err.message}`)
      setMainBtnDisabled(false)
      setStep(2)
    }
  }

  // ── Export ──────────────────────────────────────────────────────────────
  async function exportDoc() {
    if (!downloadToken) return
    const a = document.createElement('a')
    a.href = `${API}/download/${downloadToken}`
    a.download = mode === 'ai' ? 'smart_formatted_thesis.docx' : 'formatted_thesis.docx'
    a.click()
    showToast('已開始下載修正後論文')
  }

  async function exportTex() {
    if (!texToken) return
    const a = document.createElement('a')
    a.href = `${API}/download/${texToken}`
    a.download = 'thesis_source.tex'
    a.click()
    showToast('已開始下載 LaTeX 原始檔')
  }

  function handleMainAction() {
    if (step <= 1)  setModalPanel('p1')
    else if (step === 2) setModalPanel('p2')
    else if (step >= 5)  exportDoc()
  }

  function handleStepClick(n) {
    if (n === 1) setModalPanel('p1')
    else if (n === 2 && school) setModalPanel('p2')
  }

  function handleReset() {
    setStep(1); setSchool(null); setMode('rule')
    setOrigFile(null); setFmtFile(null)
    pendingState.current = null
    setOrigTag('尚未匯入'); setFmtTag('尚未修正')
    setIssues([]); setIssuesAfter([]); setActiveIssueIdx(null)
    setDownloadToken(null); setTexToken(null)
    setActionInfo('請先選擇學校格式，再匯入論文。')
    setMainBtnDisabled(false); setShowReset(false)
    setModalPanel('p1')
  }

  return (
    <>
      <Header step={step} onStepClick={handleStepClick} />
      <main>
        <div className="workspace">
          <Workspace
            step={step}
            origFile={origFile} fmtFile={fmtFile}
            origTag={origTag} fmtTag={fmtTag}
            origLoading={origLoading}
            fmtLoading={fmtLoading} fmtLoadingMsg={fmtLoadingMsg} fmtLoadingSub={fmtLoadingSub}
            actionInfo={actionInfo}
            mainBtnDisabled={mainBtnDisabled}
            showReset={showReset}
            onMainAction={handleMainAction}
            onReset={handleReset}
            origBodyRef={origBodyRef}
            fmtBodyRef={fmtBodyRef}
            splitRef={splitRef}
            onOrigRendered={handleOrigRendered}
            onFmtRendered={handleFmtRendered}
            showTexBtn={mode === 'ai' && !!texToken}
            onExportTex={exportTex}
          />
          <Sidebar
            issues={issues}
            issuesAfter={issuesAfter}
            activeIssueIdx={activeIssueIdx}
            onIssueClick={handleIssueClick}
          />
        </div>
      </main>

      {modalPanel && (
        <WizardModal
          panel={modalPanel}
          schools={schools}
          schoolsLoading={schoolsLoading}
          onClose={setModalPanel}
          onConfirmSchool={handleConfirmSchool}
          onConfirmCustom={handleConfirmCustom}
          onStartScan={handleStartScan}
        />
      )}

      {toast && <div id="toast">{toast}</div>}
    </>
  )
}
