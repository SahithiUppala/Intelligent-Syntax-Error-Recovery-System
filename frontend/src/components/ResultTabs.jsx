import { useState } from 'react'
import CorrectedCode from './CorrectedCode.jsx'

/**
 * Bottom result area: DIFF | HOW WAS THIS FIXED? | PARSE RESULT
 */

const TABS = [
  { id: 'diff', label: 'DIFF' },
  { id: 'how', label: 'HOW WAS THIS FIXED?' },
  { id: 'parse', label: 'PARSE RESULT' },
]

export default function ResultTabs({
  activeTab = 'diff',
  onTabChange,
  original,
  corrected,
  onAccept,
  onReject,
  accepted,
  analysis,
  activeErrorIndex = 0,
}) {
  const entries = analysis?.report?.entries || []
  const errors = analysis?.errors || []
  const entry = entries[activeErrorIndex] || entries[0] || null
  const errorFallback = errors[activeErrorIndex] || errors[0] || null

  return (
    <section className="result-tabs panel">
      <div className="result-tablist" role="tablist" aria-label="Results">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`result-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => onTabChange?.(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="result-tabpanel" role="tabpanel">
        {activeTab === 'diff' ? (
          <CorrectedCode
            original={original}
            corrected={corrected}
            onAccept={onAccept}
            onReject={onReject}
            accepted={accepted}
            embedded
          />
        ) : null}

        {activeTab === 'how' ? (
          <HowFixedFlow
            entry={entry}
            error={errorFallback}
            errorIndex={activeErrorIndex}
            total={Math.max(entries.length, errors.length)}
            hasAnalysis={Boolean(analysis)}
          />
        ) : null}

        {activeTab === 'parse' ? (
          <ParseResultView analysis={analysis} />
        ) : null}
      </div>
    </section>
  )
}

function HowFixedFlow({ entry, error, errorIndex, total, hasAnalysis }) {
  if (!hasAnalysis) {
    return <p className="muted">Run analysis to see how errors were fixed.</p>
  }
  if (!entry && !error) {
    return (
      <div className="how-fixed-empty">
        <p className="ok-text">✓ No errors — nothing to fix.</p>
        <p className="muted">Source parsed cleanly.</p>
      </div>
    )
  }

  const type = entry?.type || error?.type || 'SyntaxError'
  const classification =
    entry?.classification || error?.classification || 'UNCLASSIFIED'
  const how = entry?.how_fixed || {}
  const candidateCount =
    how.candidates_generated ?? entry?.candidates?.length ?? 0
  const selected =
    how.selected_operation || how.selected || entry?.best_correction || '—'
  const recovered =
    how.reason ||
    entry?.explanation ||
    (entry?.recovery_action
      ? `Recovery: ${entry.recovery_action}`
      : 'Parsing continued successfully')

  const steps = [
    { label: 'Detected', value: humanize(type) },
    { label: 'Classified', value: classification },
    {
      label: 'Generated',
      value: `${candidateCount} Candidate${candidateCount === 1 ? '' : 's'}`,
    },
    { label: 'Selected', value: selected },
    { label: 'Recovered', value: recovered },
  ]

  return (
    <div className="how-fixed-flow" key={`how-${errorIndex}-${type}`}>
      <p className="how-fixed-heading">
        Error {(errorIndex ?? 0) + 1}
        {total > 0 ? ` of ${total}` : ''}: {humanize(type)}
      </p>
      <ol className="how-flow-steps">
        {steps.map((step, index) => (
          <li key={step.label} className="how-flow-step">
            <div className="how-flow-card">
              <strong>{step.label}</strong>
              <span>{step.value}</span>
            </div>
            {index < steps.length - 1 ? (
              <span className="how-flow-arrow" aria-hidden="true">
                ↓
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  )
}

function ParseResultView({ analysis }) {
  const [open, setOpen] = useState(false)

  if (!analysis) {
    return <p className="muted">Run analysis to see the parse result.</p>
  }

  const ast = analysis.ast
  const success = Boolean(analysis.success)
  const statements = ast?.body || []

  return (
    <div className="parse-result-view">
      <p className={`parse-hero ${success ? 'ok' : 'bad'}`}>
        {success
          ? '✓ Program successfully parsed'
          : '✗ Program parsed with remaining issues'}
      </p>
      <p className="muted parse-count">
        {statements.length} top-level statement
        {statements.length === 1 ? '' : 's'}
      </p>

      {statements.length ? (
        <ul className="parse-stmt-list">
          {statements.map((stmt, index) => (
            <li key={`${stmt.type}-${index}`}>
              <span className="stmt-chip">{stmt.type || 'Statement'}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No top-level statements in the AST.</p>
      )}

      <details
        className="advanced-details"
        open={open}
        onToggle={(e) => setOpen(e.target.open)}
      >
        <summary>Advanced Details</summary>
        <pre className="ast-preview">
          {ast ? JSON.stringify(ast, null, 2) : analysis.message || 'No AST'}
        </pre>
      </details>
    </div>
  )
}

function humanize(type) {
  if (!type) return 'Syntax Error'
  return String(type).replace(/([a-z])([A-Z])/g, '$1 $2')
}
