/**
 * One-line analysis summary — replaces the large 4-card dashboard.
 */
export default function AnalysisSummary({ summary }) {
  if (!summary) return null

  const status =
    summary.recovered || summary.success ? 'Recovered' : 'Needs review'

  return (
    <div className="compact-summary" aria-live="polite">
      <span>
        <strong>{summary.errors}</strong> Errors
      </span>
      <span className="summary-sep">|</span>
      <span>
        <strong>{summary.candidates}</strong> Candidates
      </span>
      <span className="summary-sep">|</span>
      <span>
        <strong>{summary.applied}</strong> Applied
      </span>
      <span className="summary-sep">|</span>
      <span className={summary.recovered || summary.success ? 'ok-text' : 'bad-text'}>
        {status}
      </span>
    </div>
  )
}
