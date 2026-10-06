/**
 * Right-hand inspector with exclusive tabs — only one view at a time.
 * Pipeline stage clicks route here with a stage-specific insight panel.
 */
import TokenViewer from './TokenViewer.jsx'
import ErrorPanel from './ErrorPanel.jsx'
import CorrectionPanel from './CorrectionPanel.jsx'
import ParseResult from './ParseResult.jsx'

const TABS = [
  { id: 'tokens', label: 'TOKENS' },
  { id: 'errors', label: 'ERRORS' },
  { id: 'corrections', label: 'CORRECTIONS' },
  { id: 'ast', label: 'AST' },
]

export default function Inspector({
  activeTab = 'tokens',
  onTabChange,
  analysis,
  activeErrorIndex,
  selectedCandidateKey,
  previewCandidateKey,
  appliedMap,
  onErrorClick,
  onSelectCandidate,
  onPreviewCandidate,
  onApplyCandidate,
  onApplyAllBest,
  onResetCorrections,
  onApplyToEditor,
  activeStageName = null,
  activeStage = null,
}) {
  return (
    <aside className="inspector panel">
      <div className="inspector-tabs" role="tablist" aria-label="Inspector">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`inspector-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => onTabChange?.(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="inspector-body" role="tabpanel">
        <StageInsight
          stageName={activeStageName}
          stage={activeStage}
          analysis={analysis}
          activeErrorIndex={activeErrorIndex}
        />

        {activeTab === 'tokens' ? (
          <TokenViewer tokens={analysis?.tokens || []} embedded />
        ) : null}
        {activeTab === 'errors' ? (
          <ErrorPanel
            errors={analysis?.errors || []}
            activeErrorIndex={activeErrorIndex}
            onErrorClick={onErrorClick}
            embedded
            emphasizeClassification={activeStageName === 'Classification'}
          />
        ) : null}
        {activeTab === 'corrections' ? (
          <CorrectionPanel
            corrections={analysis?.corrections || []}
            reportEntries={analysis?.report?.entries || []}
            selectedKey={selectedCandidateKey}
            previewKey={previewCandidateKey}
            appliedMap={appliedMap}
            activeErrorIndex={activeErrorIndex}
            onSelectCandidate={onSelectCandidate}
            onPreviewCandidate={onPreviewCandidate}
            onApplyCandidate={onApplyCandidate}
            onApplyAllBest={onApplyAllBest}
            onResetCorrections={onResetCorrections}
            onApplyToEditor={onApplyToEditor}
            embedded
            focusMode={
              activeStageName === 'Recovery'
                ? 'recovery'
                : activeStageName === 'Correction Scoring'
                  ? 'scoring'
                  : activeStageName === 'Candidate Generation'
                    ? 'candidates'
                    : 'all'
            }
          />
        ) : null}
        {activeTab === 'ast' ? (
          <ParseResult
            ast={analysis?.ast || null}
            success={analysis ? analysis.success : null}
            message={analysis ? analysis.message : 'Run analysis to see the AST.'}
            embedded
            treeMode
            showParseStatus={
              activeStageName === 'Parsing' || activeStageName === 'Result'
            }
          />
        ) : null}
      </div>
    </aside>
  )
}

function StageInsight({ stageName, stage, analysis, activeErrorIndex }) {
  if (!stageName || !analysis) return null

  const errors = analysis.errors || []
  const error =
    typeof activeErrorIndex === 'number' ? errors[activeErrorIndex] : errors[0]
  const data = stage?.data || {}
  const detail = stage?.detail

  let title = stageName
  let body = detail || null

  switch (stageName) {
    case 'Source Code':
      body = `${(data.code || analysis.original_code || '').split('\n').length} line(s) of source`
      break
    case 'Lexical Analysis':
      body = `${(analysis.tokens || []).filter((t) => t.type !== 'EOF').length} tokens`
      break
    case 'Parsing':
      body = analysis.success
        ? 'Parse succeeded'
        : `${errors.length} parse issue(s) — see AST / errors`
      break
    case 'Error Detection':
      body = errors.length
        ? `${errors.length} error(s) detected`
        : 'No syntax errors detected'
      break
    case 'Classification':
      body = error
        ? `${humanize(error.type)} → ${error.classification || 'UNCLASSIFIED'}`
        : 'Nothing to classify'
      break
    case 'Candidate Generation': {
      const count = analysis.corrections?.length || 0
      body = `${count} candidate(s) generated`
      break
    }
    case 'Correction Scoring': {
      const best = analysis.corrections?.[0]
      body = best
        ? `Top score ${best.score ?? '—'}% · ${best.correction || ''}`
        : 'No scored candidates'
      break
    }
    case 'Recovery': {
      const applied = analysis.pipeline?.applied_count ?? analysis.report?.applied_count ?? 0
      body =
        applied > 0
          ? `${applied} correction(s) applied`
          : 'No corrections auto-applied'
      break
    }
    case 'Result':
      body = analysis.message || (analysis.success ? 'Program parsed' : 'Parse incomplete')
      break
    default:
      break
  }

  if (!body) return null

  return (
    <div className="stage-insight">
      <span className="stage-insight-label">{title}</span>
      <p className="stage-insight-body">{body}</p>
    </div>
  )
}

function humanize(type) {
  if (!type) return 'Error'
  return String(type).replace(/([a-z])([A-Z])/g, '$1 $2')
}
