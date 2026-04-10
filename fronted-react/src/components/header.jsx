const STEPS = ['選擇格式', '匯入論文', '掃描問題', '自動修正', '匯出']

export default function Header({ step, onStepClick }) {
  return (
    <header>
      <div className="brand">論文格式<em>自動修正</em>系統</div>
      <nav className="stepper">
        {STEPS.map((label, i) => {
          const n = i + 1
          const isActive = step === n
          const isDone = step > n
          return (
            <span key={n} style={{ display: 'contents' }}>
              <div
                className={`step${isActive ? ' active' : ''}${isDone ? ' done' : ''}`}
                onClick={() => isDone && onStepClick(n)}
              >
                <div className="step-n">{isDone ? '✓' : n}</div>
                <span className="step-lbl">{label}</span>
              </div>
              {i < STEPS.length - 1 && <div className="conn" />}
            </span>
          )
        })}
      </nav>
    </header>
  )
}