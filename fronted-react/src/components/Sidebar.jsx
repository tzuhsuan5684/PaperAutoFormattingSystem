import { useState } from 'react'

export default function Sidebar({ issues, issuesAfter, activeIssueIdx, onIssueClick }) {
  const [collapsed, setCollapsed] = useState(false)

  const counts = {}
  issues.forEach(i => { counts[i.severity] = (counts[i.severity] || 0) + 1 })

  return (
    <div id="sidebar" className={collapsed ? 'collapsed' : ''}>
      <div className="sb-hdr" onClick={() => setCollapsed(c => !c)}>
        {!collapsed && <span className="sb-title">問題清單</span>}
        <span className="sb-toggle">{collapsed ? '▶' : '◀'}</span>
      </div>

      {!collapsed && issues.length > 0 && (
        <div className="sb-badges">
          {counts.error   && <span className="badge b-err">{counts.error} 錯誤</span>}
          {counts.warning && <span className="badge b-warn">{counts.warning} 警告</span>}
          {counts.info    && <span className="badge b-info">{counts.info} 提示</span>}
          {issuesAfter.length === 0 && <span className="badge b-ok">全部已修正</span>}
        </div>
      )}

      {!collapsed && (
        <div className="sb-body">
          {issues.length === 0 ? (
            <div className="sb-empty">
              <span className="sb-empty-icon">📋</span>
              <span>掃描後將顯示<br />格式問題清單</span>
            </div>
          ) : (
            issues.map((issue, idx) => {
              const cls = issue.severity === 'error' ? 'err' : issue.severity === 'warning' ? 'warn' : 'info'
              return (
                <div
                  key={idx}
                  className={`issue-card ${cls}${activeIssueIdx === idx ? ' active' : ''}`}
                  onClick={() => onIssueClick(idx)}
                >
                  <div className="ic-top">
                    <div className="ic-dot" />
                    <span className="ic-sec">{issue.section}</span>
                    {issue.auto_fixed && <span className="ic-fixed">已修正</span>}
                  </div>
                  <div className="ic-msg">{issue.message}</div>
                  <span className="ic-jump">點擊跳至修正位置 ›</span>
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}