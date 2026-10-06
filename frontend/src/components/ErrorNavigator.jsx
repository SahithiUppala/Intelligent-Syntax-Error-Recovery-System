/**
 * Error navigation bar above the editor.
 * Error N of M · ← Previous | Next →
 */
export default function ErrorNavigator({
  errors = [],
  activeIndex = 0,
  onSelect,
}) {
  const total = errors.length
  if (total === 0) return null

  const index = Math.min(Math.max(activeIndex ?? 0, 0), total - 1)
  const canPrev = index > 0
  const canNext = index < total - 1

  return (
    <div className="error-nav" role="navigation" aria-label="Error navigation">
      <span className="error-nav-count">
        Error <strong>{index + 1}</strong> of <strong>{total}</strong>
      </span>
      <div className="error-nav-actions">
        <button
          type="button"
          className="btn error-nav-btn"
          disabled={!canPrev}
          onClick={() => onSelect?.(index - 1)}
          aria-label="Previous error"
        >
          ← Previous
        </button>
        <button
          type="button"
          className="btn error-nav-btn"
          disabled={!canNext}
          onClick={() => onSelect?.(index + 1)}
          aria-label="Next error"
        >
          Next →
        </button>
      </div>
      <span className="error-nav-locus muted">
        Line {errors[index]?.line ?? '—'} : Column {errors[index]?.column ?? '—'}
      </span>
    </div>
  )
}
