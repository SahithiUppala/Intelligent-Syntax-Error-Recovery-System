/**
 * Detected syntax error cards with expected/found details.
 * Clicking a card highlights the location in Monaco.
 */
export default function ErrorPanel({
  errors = [],
  activeErrorIndex = null,
  onErrorClick,
  embedded = false,
  emphasizeClassification = false,
}) {
  const body =
    errors.length === 0 ? (
      <p className="muted">No errors detected. Source looks clean.</p>
    ) : (
      <ul className="error-list">
        {errors.map((error, index) => {
          const active = activeErrorIndex === index
          const expected = Array.isArray(error.expected)
            ? error.expected.join(', ')
            : error.expected || '—'
          return (
            <li key={`${error.type}-${error.line}-${error.column}-${index}`}>
              <button
                type="button"
                className={`error-card ${active ? 'active' : ''} ${emphasizeClassification ? 'class-focus' : ''}`}
                onClick={() => onErrorClick?.(error, index)}
              >
                <div className="error-card-top">
                  <strong>ERROR {(index + 1).toString().padStart(2, '0')}</strong>
                  {error.classification ? (
                    <span className="class-chip">{error.classification}</span>
                  ) : null}
                </div>
                <span className="error-locus">
                  Line {error.line} : Column {error.column}
                </span>
                <span className="error-type">{humanize(error.type)}</span>
                {emphasizeClassification && error.classification_reason ? (
                  <p className="error-explain class-reason">
                    {error.classification_reason}
                  </p>
                ) : null}
                <div className="error-meta">
                  <div>
                    <span className="meta-label">Expected</span>
                    <code>{expected}</code>
                  </div>
                  <div>
                    <span className="meta-label">Found</span>
                    <code>{error.found ?? '—'}</code>
                  </div>
                </div>
                {!emphasizeClassification && (error.explanation || error.message) ? (
                  <p className="error-explain">
                    {error.explanation || error.message}
                  </p>
                ) : null}
                {error.fragment ? (
                  <pre className="error-fragment">{error.fragment}</pre>
                ) : null}
              </button>
            </li>
          )
        })}
      </ul>
    )

  if (embedded) {
    return <div className="error-panel embedded-panel">{body}</div>
  }

  return (
    <div className="panel error-panel">
      <div className="panel-heading">
        <h3>Error Panel</h3>
        <span className="count-chip">{errors.length}</span>
      </div>
      {body}
    </div>
  )
}

function humanize(type) {
  if (!type) return 'Syntax Error'
  return type.replace(/([a-z])([A-Z])/g, '$1 $2')
}
