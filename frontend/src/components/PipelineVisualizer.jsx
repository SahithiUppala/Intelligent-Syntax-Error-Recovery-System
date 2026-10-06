/**
 * Interactive pipeline stage visualizer.
 *
 * Shows Source → … → Result with status badges. Clicking a stage reveals
 * what that stage produced (tokens, AST, errors, candidates, recovery, …).
 */

const DEFAULT_STAGES = [
  'Source Code',
  'Lexical Analysis',
  'Parsing',
  'Error Detection',
  'Classification',
  'Candidate Generation',
  'Correction Scoring',
  'Recovery',
  'Result',
]

const STATUS_LABELS = {
  pending: 'PENDING',
  processing: 'RUNNING',
  running: 'RUNNING',
  completed: 'COMPLETED',
  error: 'ERROR DETECTED',
  'error-detected': 'ERROR DETECTED',
  recovered: 'RECOVERED',
}

function normalizeStatus(status) {
  if (!status) return 'pending'
  if (status === 'error') return 'error-detected'
  if (status === 'running') return 'processing'
  return status
}

function statusLabel(status) {
  const key = normalizeStatus(status)
  return STATUS_LABELS[key] || key
}

export default function PipelineVisualizer({
  stages = [],
  activeStageName,
  onStageClick,
  processing = false,
  compact = false,
}) {
  const items = stages.length
    ? stages
    : DEFAULT_STAGES.map((name) => ({
        name,
        status: processing ? 'processing' : 'pending',
        detail: processing ? 'Waiting for analysis…' : 'Run analysis to populate this stage.',
      }))

  const active =
    items.find((stage) => stage.name === activeStageName) || items[0] || null

  return (
    <div className={`panel pipeline-panel ${compact ? 'pipeline-compact' : ''}`}>
      <div className="pipeline-header">
        <h3>Analysis Pipeline</h3>
        <p className="muted pipeline-hint">
          {compact
            ? 'Click a stage to open it in the Inspector'
            : 'Click a stage to inspect its output'}
        </p>
      </div>

      <ol className="pipeline-flow">
        {items.map((stage, index) => {
          const status = normalizeStatus(stage.status)
          const isActive = active?.name === stage.name
          return (
            <li key={stage.name || index} className="pipeline-flow-item">
              <button
                type="button"
                className={`pipeline-stage status-${status} ${isActive ? 'active' : ''}`}
                onClick={() => onStageClick?.(stage)}
                title={stage.detail || stage.name}
              >
                <span className="stage-index">{index + 1}</span>
                <span className="stage-body">
                  <span className="stage-name">{stage.name}</span>
                  <span className="stage-status">{statusLabel(status)}</span>
                </span>
              </button>
              {index < items.length - 1 ? (
                <span className="pipeline-arrow" aria-hidden="true">
                  →
                </span>
              ) : null}
            </li>
          )
        })}
      </ol>

      {!compact ? <StageDetail stage={active} /> : null}
    </div>
  )
}

function StageDetail({ stage }) {
  if (!stage) {
    return (
      <div className="pipeline-detail">
        <p className="muted">No stage selected.</p>
      </div>
    )
  }

  const status = normalizeStatus(stage.status)
  const data = stage.data || {}

  return (
    <div className="pipeline-detail">
      <div className="pipeline-detail-header">
        <h4>{stage.name}</h4>
        <span className={`detail-badge status-${status}`}>{statusLabel(status)}</span>
      </div>
      {stage.detail ? <p className="pipeline-detail-summary">{stage.detail}</p> : null}
      <div className="pipeline-detail-body">{renderStageBody(stage.name, data, status)}</div>
    </div>
  )
}

function renderStageBody(name, data, status) {
  if (status === 'pending') {
    return <p className="muted">This stage has not run yet.</p>
  }
  if (status === 'processing') {
    return <p className="muted processing-pulse">Processing…</p>
  }

  switch (name) {
    case 'Source Code':
      return (
        <pre className="stage-pre">{data.code || '(empty source)'}</pre>
      )

    case 'Lexical Analysis':
      return <TokenPreview tokens={data.tokens || []} errors={data.lexical_errors || []} />

    case 'Parsing':
      return (
        <div className="stage-split">
          {data.errors?.length ? (
            <ErrorListPreview title="Parse errors" errors={data.errors} />
          ) : (
            <p className="muted">No parse errors.</p>
          )}
          <pre className="stage-pre ast-pre">
            {data.ast ? JSON.stringify(data.ast, null, 2) : 'No AST'}
          </pre>
        </div>
      )

    case 'Error Detection':
      return data.errors?.length ? (
        <ErrorListPreview title="Detected errors" errors={data.errors} />
      ) : (
        <p className="muted">No syntax errors detected.</p>
      )

    case 'Classification':
      return data.errors?.length ? (
        <ClassificationPreview errors={data.errors} />
      ) : (
        <p className="muted">Nothing to classify.</p>
      )

    case 'Candidate Generation':
      return <CandidatesPreview byError={data.by_error || []} mode="generate" />

    case 'Correction Scoring':
      return <CandidatesPreview byError={data.by_error || []} mode="score" />

    case 'Recovery':
      return <RecoveryPreview data={data} />

    case 'Result':
      return <ResultPreview report={data.report} />

    default:
      return (
        <pre className="stage-pre">{JSON.stringify(data, null, 2)}</pre>
      )
  }
}

function TokenPreview({ tokens, errors }) {
  const rows = tokens.filter((t) => t.type !== 'EOF').slice(0, 40)
  if (!rows.length && !errors.length) {
    return <p className="muted">No tokens.</p>
  }
  return (
    <div className="stage-scroll">
      {errors.length ? (
        <p className="stage-note danger-text">
          {errors.length} lexical error(s)
        </p>
      ) : null}
      <table className="token-table compact">
        <thead>
          <tr>
            <th>TOKEN</th>
            <th>VALUE</th>
            <th>LINE</th>
            <th>COLUMN</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((token, index) => (
            <tr key={`${token.type}-${token.line}-${token.column}-${index}`}>
              <td>{token.type}</td>
              <td>{token.value}</td>
              <td>{token.line}</td>
              <td>{token.column}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {tokens.length > 41 ? (
        <p className="muted stage-note">Showing first 40 tokens…</p>
      ) : null}
    </div>
  )
}

function ErrorListPreview({ title, errors }) {
  return (
    <div className="stage-scroll">
      <p className="stage-note">{title}</p>
      <ul className="stage-error-list">
        {errors.map((error, index) => (
          <li key={`${error.type}-${error.line}-${index}`}>
            <strong>{error.type}</strong>
            <span>
              L{error.line}:C{error.column}
            </span>
            <span className="muted">{error.message || error.explanation}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ClassificationPreview({ errors }) {
  return (
    <div className="stage-scroll">
      <ul className="stage-error-list">
        {errors.map((error, index) => (
          <li key={`${error.classification}-${error.line}-${index}`}>
            <strong>{error.classification || 'UNCLASSIFIED'}</strong>
            <span>{error.type}</span>
            <span className="muted">
              {error.classification_reason || error.suggested_fix || error.message}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function CandidatesPreview({ byError, mode }) {
  if (!byError.length) {
    return <p className="muted">No candidates for this run.</p>
  }
  return (
    <div className="stage-scroll">
      {byError.map((group) => {
        const error = group.error || {}
        const candidates = group.candidates || []
        return (
          <div key={`${error.type}-${group.error_index}`} className="candidate-group">
            <p className="stage-note">
              {error.type} @ L{error.line}:{error.column}
            </p>
            <ul className="stage-candidate-list">
              {candidates.slice(0, 5).map((cand, index) => (
                <li key={`${cand.correction}-${index}`}>
                  <code>{cand.correction}</code>
                  {mode === 'score' ? (
                    <span className={cand.is_best ? 'best-score' : ''}>
                      {cand.score != null ? `${cand.score}%` : '—'}
                      {cand.is_best ? ' · BEST' : ''}
                    </span>
                  ) : (
                    <span className="muted">{cand.operation?.kind || cand.description}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )
      })}
    </div>
  )
}

function RecoveryPreview({ data }) {
  const actions = data.actions || []
  return (
    <div className="stage-scroll">
      <p className="stage-note">
        Applied {data.applied_count ?? 0} correction(s)
      </p>
      {actions.length ? (
        <ul className="stage-error-list">
          {actions.map((action) => (
            <li key={action.error_number}>
              <strong>
                #{action.error_number} {action.error_type}
              </strong>
              <span className="badge-inline">{action.action}</span>
              <span className="muted">
                {action.selected_correction || action.explanation}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No recovery actions.</p>
      )}
      {data.corrected_code ? (
        <pre className="stage-pre">{data.corrected_code}</pre>
      ) : null}
    </div>
  )
}

function ResultPreview({ report }) {
  if (!report) {
    return <p className="muted">No report available.</p>
  }
  return (
    <div className="stage-scroll">
      <p className="stage-note">
        Total errors: {report.total_errors} · Applied: {report.applied_count}
      </p>
      <pre className="stage-pre report-pre">{report.text || JSON.stringify(report, null, 2)}</pre>
    </div>
  )
}
