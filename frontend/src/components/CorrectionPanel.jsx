import { useMemo, useState, useEffect } from 'react'
import { SCORE_MAX, enrichCandidate } from '../utils/codeEdit.js'

/**
 * Interactive correction selection — main Phase 3 interaction surface.
 * Uses backend scores/breakdown only (never invents frontend scores).
 */
export default function CorrectionPanel({
  corrections = [],
  reportEntries = [],
  selectedKey = null,
  previewKey = null,
  appliedMap = {},
  activeErrorIndex = 0,
  onSelectCandidate,
  onPreviewCandidate,
  onApplyCandidate,
  onApplyAllBest,
  onResetCorrections,
  onApplyToEditor,
  embedded = false,
  focusMode = 'all',
}) {
  const groups = useMemo(
    () => buildGroups(corrections, reportEntries),
    [corrections, reportEntries],
  )

  const [openError, setOpenError] = useState(0)

  useEffect(() => {
    if (typeof activeErrorIndex === 'number' && activeErrorIndex >= 0) {
      setOpenError(Math.min(activeErrorIndex, Math.max(groups.length - 1, 0)))
    } else {
      setOpenError(0)
    }
  }, [groups.length, corrections, activeErrorIndex])

  if (!groups.length) {
    const empty = (
      <p className="muted">Candidate corrections will appear after analysis.</p>
    )
    if (embedded) {
      return <div className="correction-panel embedded-panel">{empty}</div>
    }
    return (
      <div className="panel correction-panel">
        <div className="panel-heading">
          <h3>Correction Panel</h3>
        </div>
        {empty}
      </div>
    )
  }

  const errorIndex = Math.min(openError, groups.length - 1)
  const active = groups[errorIndex]
  const appliedEntry = appliedMap[errorIndex]
  const appliedKey = appliedEntry?.key || null

  const body = (
    <>
      <div className="correction-toolbar">
        <button
          type="button"
          className="btn"
          disabled={!groups.length}
          onClick={() => onApplyAllBest?.(groups)}
        >
          Apply All Best Corrections
        </button>
        <button type="button" className="btn" onClick={() => onResetCorrections?.()}>
          Reset Corrections
        </button>
        <button
          type="button"
          className="btn primary"
          onClick={() => onApplyToEditor?.()}
        >
          Apply Corrected Code to Editor
        </button>
      </div>

      {groups.length > 1 ? (
        <div className="error-tabs">
          {groups.map((group, index) => (
            <button
              key={group.key}
              type="button"
              className={`error-tab ${index === errorIndex ? 'active' : ''}`}
              onClick={() => {
                setOpenError(index)
                onSelectCandidate?.(null, null, index)
              }}
            >
              Err {(index + 1).toString().padStart(2, '0')}
              {appliedMap[index] ? ' ✓' : ''}
            </button>
          ))}
        </div>
      ) : null}

      <header className="correction-error-header">
        <h4 className="correction-error-title">{active.title}</h4>
        <p className="correction-error-locus">
          Line {active.line} : Column {active.column}
        </p>
        {active.original ? (
          <p className="correction-original">
            <span className="meta-label">Original</span>
            <code>{active.original}</code>
          </p>
        ) : null}
      </header>

      <p className="section-label">Possible Corrections</p>
      <ul className="correction-list">
        {active.candidates.map((item, index) => {
          const score = Number(item.score ?? 0)
          const isBest = Boolean(item.is_best || index === 0)
          const key = candidateKey(item, active.key, index)
          const selected = selectedKey === key
          const previewing = previewKey === key
          const applied = appliedKey === key
          return (
            <li key={key}>
              <div
                className={`correction-card ${isBest ? 'best' : ''} ${selected ? 'selected' : ''} ${applied ? 'applied' : ''} ${previewing ? 'previewing' : ''}`}
              >
                <button
                  type="button"
                  className="correction-card-main"
                  onClick={() => onSelectCandidate?.(item, key, errorIndex)}
                >
                  <div className="correction-card-top">
                    <strong>
                      Candidate {index + 1}
                      {isBest ? (
                        <span className="best-badge"> BEST CORRECTION</span>
                      ) : null}
                      {applied ? (
                        <span className="applied-badge"> ✓ APPLIED</span>
                      ) : null}
                    </strong>
                    <span className="score-text">{score}%</span>
                  </div>
                  <code className="correction-code">{item.correction}</code>
                  <div className="confidence-bar" aria-hidden="true">
                    <div
                      className="confidence-fill"
                      style={{ width: `${clamp(score, 0, 100)}%` }}
                    />
                  </div>
                </button>

                {item.breakdown ? (
                  <ScoreBreakdownBars breakdown={item.breakdown} />
                ) : focusMode === 'scoring' ? (
                  <p className="muted score-missing">No breakdown from backend for this candidate.</p>
                ) : null}

                {(item.reason || item.description) && (
                  <p className="correction-reason">
                    {item.reason || item.description}
                  </p>
                )}

                <div className="correction-card-actions">
                  <button
                    type="button"
                    className={`btn ${previewing ? 'primary' : ''}`}
                    onClick={() => onPreviewCandidate?.(item, key, errorIndex)}
                  >
                    {previewing ? 'Previewing…' : 'Preview'}
                  </button>
                  <button
                    type="button"
                    className={`btn ${applied ? 'applied-btn' : 'primary'}`}
                    onClick={() => onApplyCandidate?.(item, key, errorIndex)}
                  >
                    {applied ? '✓ APPLIED' : 'Apply'}
                  </button>
                </div>
              </div>
            </li>
          )
        })}
      </ul>
    </>
  )

  if (embedded) {
    return <div className="correction-panel embedded-panel">{body}</div>
  }

  return (
    <div className="panel correction-panel">
      <div className="panel-heading">
        <h3>Correction Panel</h3>
        <span className="count-chip">{corrections.length}</span>
      </div>
      {body}
    </div>
  )
}

function ScoreBreakdownBars({ breakdown }) {
  const rows = [
    {
      label: 'Grammar Validity',
      value: breakdown.grammar_validity,
      max: SCORE_MAX.grammar_validity,
    },
    {
      label: 'Context',
      value: breakdown.local_context,
      max: SCORE_MAX.local_context,
    },
    {
      label: 'Token Compatibility',
      value: breakdown.token_compatibility,
      max: SCORE_MAX.token_compatibility,
    },
    {
      label: 'Parse Progress',
      value: breakdown.parse_progress,
      max: SCORE_MAX.parse_progress,
    },
    {
      label: 'Edit Penalty',
      value: breakdown.edit_penalty,
      max: SCORE_MAX.edit_penalty,
      penalty: true,
    },
  ]

  return (
    <div className="score-bars">
      {rows.map((row) => {
        const raw = Number(row.value ?? 0)
        const pct = row.max ? clamp((raw / row.max) * 100, 0, 100) : 0
        return (
          <div key={row.label} className={`score-bar-row ${row.penalty ? 'penalty' : ''}`}>
            <div className="score-bar-label">
              <span>{row.label}</span>
              <span className="score-bar-value">
                {row.penalty ? `−${raw}` : `${raw}/${row.max}`}
              </span>
            </div>
            <div className="score-bar-track" aria-hidden="true">
              <div
                className="score-bar-fill"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function buildGroups(corrections, reportEntries) {
  if (reportEntries?.length) {
    return reportEntries.map((entry, index) => {
      const candidates = (entry.candidates || [])
        .map((cand) =>
          enrichCandidate(
            {
              ...cand,
              error_type: entry.type,
              line: entry.line,
              column: entry.column,
              original_fragment: entry.original_fragment,
            },
            corrections,
          ),
        )
        .sort((a, b) => (b.score || 0) - (a.score || 0))
      return {
        key: `report-${index}`,
        title: humanize(entry.type),
        label: `${humanize(entry.type)} @ L${entry.line}:C${entry.column}`,
        line: entry.line,
        column: entry.column,
        original: entry.original_fragment,
        howFixed: entry.how_fixed,
        candidates,
      }
    })
  }

  const map = new Map()
  corrections.forEach((item, index) => {
    const key = `${item.error_type || 'error'}-${item.line}-${item.column}`
    if (!map.has(key)) {
      map.set(key, {
        key,
        title: humanize(item.error_type) || 'Error',
        label: `${humanize(item.error_type) || 'Error'} @ L${item.line || '?'}:C${item.column || '?'}`,
        line: item.line,
        column: item.column,
        original: item.original_fragment,
        howFixed: null,
        candidates: [],
      })
    }
    map.get(key).candidates.push(enrichCandidate({ ...item, _index: index }, corrections))
  })

  return Array.from(map.values()).map((group) => ({
    ...group,
    candidates: group.candidates.sort((a, b) => (b.score || 0) - (a.score || 0)),
  }))
}

function candidateKey(item, groupKey, index) {
  return `${groupKey}:${item.correction}:${index}`
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function humanize(type) {
  if (!type) return 'Correction'
  return String(type).replace(/([a-z])([A-Z])/g, '$1 $2')
}
