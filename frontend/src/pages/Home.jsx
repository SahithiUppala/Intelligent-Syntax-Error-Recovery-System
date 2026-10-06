import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import AnalysisSummary from '../components/AnalysisSummary.jsx'
import CodeEditor from '../components/CodeEditor.jsx'
import PipelineVisualizer from '../components/PipelineVisualizer.jsx'
import Inspector from '../components/Inspector.jsx'
import ResultTabs from '../components/ResultTabs.jsx'
import ErrorNavigator from '../components/ErrorNavigator.jsx'
import {
  analyze,
  checkHealth,
  fetchExamples,
  getApiErrorMessage,
} from '../services/api.js'
import {
  applyFragmentCorrection,
  rebuildCorrectedCode,
  summarizeAnalysis,
} from '../utils/codeEdit.js'
import { buildFeaturedExamples } from '../utils/examples.js'

const FALLBACK_SAMPLE = `int x = 10
int y = 20;

if (x < y {
    x = x + 1;
}`

const PIPELINE_NAMES = [
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

export default function Home() {
  const editorRef = useRef(null)
  const [code, setCode] = useState(FALLBACK_SAMPLE)
  const [examples, setExamples] = useState([])
  const [exampleId, setExampleId] = useState('demo')
  const [backendStatus, setBackendStatus] = useState('checking')
  const [backendMessage, setBackendMessage] = useState('')
  const [stages, setStages] = useState([])
  const [activeStageName, setActiveStageName] = useState('Source Code')
  const [analyzeMessage, setAnalyzeMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [analysis, setAnalysis] = useState(null)
  const [activeErrorIndex, setActiveErrorIndex] = useState(null)
  const [selectedCandidateKey, setSelectedCandidateKey] = useState(null)
  const [previewCandidateKey, setPreviewCandidateKey] = useState(null)
  const [appliedMap, setAppliedMap] = useState({})
  const [workingCorrected, setWorkingCorrected] = useState('')
  const [previewCorrected, setPreviewCorrected] = useState('')
  const [accepted, setAccepted] = useState(false)
  const [baselineCorrected, setBaselineCorrected] = useState('')
  const [inspectorTab, setInspectorTab] = useState('tokens')
  const [resultTab, setResultTab] = useState('diff')

  const refreshHealth = useCallback(async () => {
    try {
      const data = await checkHealth()
      setBackendStatus('online')
      setBackendMessage(`${data.service} v${data.version}`)
      return true
    } catch (error) {
      setBackendStatus('offline')
      setBackendMessage(getApiErrorMessage(error, 'Backend unreachable'))
      return false
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function boot() {
      const online = await refreshHealth()
      if (cancelled) return

      try {
        const data = await fetchExamples()
        if (cancelled) return
        const featured = buildFeaturedExamples(data.examples || [])
        setExamples(featured)
        const initial =
          featured.find((item) => item.id === 'missing_semicolon') ||
          featured.find((item) => item.id === 'demo') ||
          featured[0]
        if (initial?.code) {
          setExampleId(initial.id)
          setCode(initial.code)
        }
      } catch {
        if (cancelled) return
        const featured = buildFeaturedExamples([])
        setExamples(featured)
        if (!online) {
          setAnalyzeMessage('Backend offline — using local demo samples.')
        }
      }
    }

    boot()
    const timer = setInterval(() => {
      refreshHealth()
    }, 15000)

    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [refreshHealth])

  const markers = useMemo(() => {
    const errors = analysis?.errors || []
    return errors.map((error, index) => ({
      line: error.line,
      column: error.column,
      message: error.message || error.type,
      length: (error.found && String(error.found).length) || 1,
      active: activeErrorIndex === index,
    }))
  }, [analysis, activeErrorIndex])

  const summary = useMemo(() => {
    const base = summarizeAnalysis(analysis)
    const userApplied = Object.keys(appliedMap).length
    return {
      ...base,
      applied: userApplied || base.applied,
    }
  }, [analysis, appliedMap])

  const activeStage = useMemo(
    () => stages.find((stage) => stage.name === activeStageName) || null,
    [stages, activeStageName],
  )

  const originalSource = analysis?.original_code ?? code

  const selectError = useCallback(
    (index) => {
      const errs = analysis?.errors || []
      if (!errs.length || index < 0 || index >= errs.length) return
      const error = errs[index]
      setActiveErrorIndex(index)
      setActiveStageName('Error Detection')
      setInspectorTab('errors')
      editorRef.current?.revealError(error)
    },
    [analysis],
  )

  const handleAnalyzeRef = useRef(null)

  // Keyboard shortcuts: Ctrl/Cmd+Enter analyze · Alt+↑/↓ error nav
  useEffect(() => {
    function onKeyDown(event) {
      const target = event.target
      const tag = target?.tagName
      const inEditable =
        target?.isContentEditable ||
        tag === 'INPUT' ||
        tag === 'SELECT' ||
        tag === 'TEXTAREA'

      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault()
        handleAnalyzeRef.current?.()
        return
      }

      if (event.altKey && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
        // Allow even when Monaco has focus
        event.preventDefault()
        const errs = analysis?.errors || []
        if (!errs.length) return
        const cur = activeErrorIndex ?? 0
        const next =
          event.key === 'ArrowDown'
            ? Math.min(cur + 1, errs.length - 1)
            : Math.max(cur - 1, 0)
        if (next !== cur) selectError(next)
        return
      }

      // Avoid stealing plain keys from form controls
      if (inEditable && !(event.ctrlKey || event.metaKey || event.altKey)) return
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [analysis, activeErrorIndex, selectError])

  function resetCorrectionState() {
    setSelectedCandidateKey(null)
    setPreviewCandidateKey(null)
    setAppliedMap({})
    setWorkingCorrected('')
    setPreviewCorrected('')
    setBaselineCorrected('')
    setAccepted(false)
  }

  async function handleAnalyze() {
    if (!code.trim()) {
      setAnalyzeMessage('Editor is empty — load an example or type some mini-C code first.')
      return
    }

    if (backendStatus === 'offline') {
      const online = await refreshHealth()
      if (!online) {
        setAnalyzeMessage('Backend is offline. Start uvicorn on port 8000, then retry.')
        return
      }
    }

    setBusy(true)
    setAnalyzeMessage('')
    setAnalysis(null)
    setAccepted(false)
    resetCorrectionState()

    setStages(
      PIPELINE_NAMES.map((name, index) => ({
        name,
        status: index === 0 ? 'processing' : 'pending',
        detail: index === 0 ? 'Preparing source…' : 'Queued',
      })),
    )
    setActiveStageName('Lexical Analysis')
    setInspectorTab('tokens')

    let sweepIndex = 0
    const sweep = setInterval(() => {
      sweepIndex = Math.min(sweepIndex + 1, PIPELINE_NAMES.length - 1)
      setStages(
        PIPELINE_NAMES.map((name, index) => ({
          name,
          status:
            index < sweepIndex
              ? 'completed'
              : index === sweepIndex
                ? 'processing'
                : 'pending',
          detail:
            index < sweepIndex
              ? 'Waiting for server response…'
              : index === sweepIndex
                ? 'Processing…'
                : 'Queued',
        })),
      )
      setActiveStageName(PIPELINE_NAMES[sweepIndex])
    }, 160)

    try {
      const result = await analyze(code)
      setAnalysis(result)
      const nextStages = result.stages || []
      setStages(nextStages)
      const recovered = result.corrected_code || result.original_code || code
      setBaselineCorrected(recovered)
      setWorkingCorrected(recovered)
      setPreviewCorrected(recovered)
      setSelectedCandidateKey(null)
      setPreviewCandidateKey(null)
      setAppliedMap({})
      setActiveErrorIndex(result.errors?.length ? 0 : null)
      setResultTab('diff')

      const firstInteresting =
        nextStages.find((stage) => stage.status === 'error' || stage.status === 'recovered') ||
        nextStages.find((stage) => stage.name === 'Error Detection') ||
        nextStages.find((stage) => stage.name === 'Lexical Analysis') ||
        nextStages[0]
      setActiveStageName(firstInteresting?.name || 'Result')

      if (result.errors?.length) {
        setInspectorTab('corrections')
      } else {
        setInspectorTab('ast')
      }

      setAnalyzeMessage(result.message || 'Analysis complete.')

      if (result.errors?.[0]) {
        setTimeout(() => editorRef.current?.revealError(result.errors[0]), 50)
      }
    } catch (error) {
      setAnalysis(null)
      resetCorrectionState()
      setActiveErrorIndex(null)
      setStages(
        PIPELINE_NAMES.map((name) => ({
          name,
          status: 'error',
          detail: getApiErrorMessage(error),
        })),
      )
      setAnalyzeMessage(getApiErrorMessage(error, 'Analysis request failed.'))
      await refreshHealth()
    } finally {
      clearInterval(sweep)
      setBusy(false)
    }
  }
  handleAnalyzeRef.current = handleAnalyze

  function handleClear() {
    setCode('')
    setStages([])
    setAnalyzeMessage('')
    setAnalysis(null)
    setActiveStageName('Source Code')
    setActiveErrorIndex(null)
    resetCorrectionState()
    setInspectorTab('tokens')
    setResultTab('diff')
  }

  function handleLoadExample() {
    const selected =
      examples.find((item) => item.id === exampleId) ||
      examples.find((item) => item.id === 'demo') ||
      examples[0]
    setCode(selected?.code || FALLBACK_SAMPLE)
    setAnalyzeMessage(`Loaded example: ${selected?.name || 'local demo'}`)
    setAnalysis(null)
    setStages([])
    resetCorrectionState()
    setActiveErrorIndex(null)
    setInspectorTab('tokens')
    setResultTab('diff')
  }

  function handleErrorClick(_error, index) {
    selectError(index)
  }

  function handleStageClick(stage) {
    setActiveStageName(stage.name)
    const tab = stageToInspectorTab(stage.name)
    if (tab) setInspectorTab(tab)

    if (
      (stage.name === 'Error Detection' || stage.name === 'Classification') &&
      analysis?.errors?.length
    ) {
      const idx = activeErrorIndex ?? 0
      const error = analysis.errors[idx]
      if (error) {
        setTimeout(() => editorRef.current?.revealError(error), 30)
      }
    }
  }

  function handleSelectCandidate(candidate, key, errorIndex) {
    if (typeof errorIndex === 'number') {
      setActiveErrorIndex(errorIndex)
    }
    if (!candidate || !key) {
      setInspectorTab('corrections')
      return
    }
    setSelectedCandidateKey(key)
    setActiveStageName('Correction Scoring')
    setInspectorTab('corrections')
  }

  function handlePreviewCandidate(candidate, key, errorIndex) {
    if (typeof errorIndex === 'number') {
      setActiveErrorIndex(errorIndex)
    }
    setSelectedCandidateKey(key)
    setPreviewCandidateKey(key)
    setAccepted(false)
    // Preview only — leave workingCorrected / Monaco untouched
    const next = applyFragmentCorrection(originalSource, candidate)
    setPreviewCorrected(next)
    setActiveStageName('Correction Scoring')
    setInspectorTab('corrections')
    setResultTab('diff')
    setAnalyzeMessage(`Preview: ${candidate.correction}`)
  }

  function handleApplyCandidate(candidate, key, errorIndex) {
    const idx = typeof errorIndex === 'number' ? errorIndex : activeErrorIndex ?? 0
    setActiveErrorIndex(idx)
    setSelectedCandidateKey(key)
    setPreviewCandidateKey(null)
    setAccepted(false)

    const nextMap = {
      ...appliedMap,
      [idx]: { key, candidate },
    }
    setAppliedMap(nextMap)

    const rebuilt = rebuildCorrectedCode(originalSource, nextMap)
    setWorkingCorrected(rebuilt)
    setPreviewCorrected(rebuilt)
    setActiveStageName('Recovery')
    setInspectorTab('corrections')
    setResultTab('diff')
    setAnalyzeMessage(`Applied candidate to corrected code: ${candidate.correction}`)
  }

  function handleApplyAllBest(groups = []) {
    if (!groups.length) {
      // Fall back to backend recovery suggestion
      const recovered = baselineCorrected || analysis?.corrected_code || originalSource
      setWorkingCorrected(recovered)
      setPreviewCorrected(recovered)
      setPreviewCandidateKey(null)
      setAnalyzeMessage('Applied backend best corrections to corrected-code state.')
      setResultTab('diff')
      return
    }

    const nextMap = {}
    groups.forEach((group, index) => {
      const best =
        group.candidates.find((c) => c.is_best) || group.candidates[0] || null
      if (!best) return
      const bestIndex = group.candidates.indexOf(best)
      const key = `${group.key}:${best.correction}:${bestIndex}`
      nextMap[index] = { key, candidate: best }
    })

    setAppliedMap(nextMap)
    setSelectedCandidateKey(null)
    setPreviewCandidateKey(null)

    // Prefer backend full corrected code when applying all bests
    const recovered = analysis?.corrected_code
    const rebuilt =
      recovered && Object.keys(nextMap).length
        ? recovered
        : rebuildCorrectedCode(originalSource, nextMap)

    setWorkingCorrected(rebuilt)
    setPreviewCorrected(rebuilt)
    setActiveStageName('Recovery')
    setInspectorTab('corrections')
    setResultTab('diff')
    setAnalyzeMessage('Applied all best corrections to corrected-code state (editor unchanged).')
  }

  function handleResetCorrections() {
    setAppliedMap({})
    setSelectedCandidateKey(null)
    setPreviewCandidateKey(null)
    setAccepted(false)
    const recovered = baselineCorrected || analysis?.corrected_code || originalSource
    setWorkingCorrected(recovered)
    setPreviewCorrected(recovered)
    setAnalyzeMessage('Corrections reset to analysis baseline (editor unchanged).')
  }

  function handleApplyToEditor() {
    const next = workingCorrected || previewCorrected || analysis?.corrected_code || ''
    if (!next) {
      setAnalyzeMessage('Nothing to apply — run analysis and apply a candidate first.')
      return
    }
    setCode(next)
    setAccepted(true)
    setPreviewCandidateKey(null)
    setAnalyzeMessage('Corrected code applied to the editor. Re-run analysis to verify.')
  }

  function handleAcceptCorrection(nextCode) {
    // Result tab Accept → same as Apply Corrected Code to Editor
    setCode(nextCode)
    setWorkingCorrected(nextCode)
    setPreviewCorrected(nextCode)
    setAccepted(true)
    setAnalyzeMessage('Correction accepted into the editor. Re-run analysis to verify.')
  }

  function handleRejectCorrection() {
    setPreviewCandidateKey(null)
    setPreviewCorrected(workingCorrected || baselineCorrected || analysis?.corrected_code || '')
    setSelectedCandidateKey(null)
    setAccepted(false)
    setAnalyzeMessage('Preview rejected — restored working corrected code.')
  }

  const correctedDisplay =
    previewCorrected || workingCorrected || analysis?.corrected_code || ''
  const offline = backendStatus === 'offline'
  const errors = analysis?.errors || []

  return (
    <div className={`app-shell workspace-shell ${busy ? 'is-busy' : ''}`}>
      <header className="app-header">
        <div>
          <h1>Intelligent Syntax Error Recovery System</h1>
          <p className="subtitle">Detect • Explain • Correct • Continue</p>
        </div>
        <button
          type="button"
          className={`status-badge status-${backendStatus} status-button`}
          onClick={refreshHealth}
          title="Click to refresh backend status"
        >
          Backend: {backendStatus}
        </button>
      </header>

      <section className="toolbar">
        <button
          type="button"
          className="btn primary"
          onClick={handleAnalyze}
          disabled={busy}
          title="Ctrl/Cmd + Enter"
        >
          {busy ? 'Analyzing…' : 'Run Analysis'}
        </button>
        <button type="button" className="btn" onClick={handleClear} disabled={busy}>
          Clear
        </button>
        {examples.length > 0 ? (
          <select
            className="example-select"
            value={exampleId}
            disabled={busy}
            onChange={(e) => setExampleId(e.target.value)}
            aria-label="Example program"
          >
            {examples.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        ) : null}
        <button type="button" className="btn" onClick={handleLoadExample} disabled={busy}>
          Load Example
        </button>
        {analysis ? <AnalysisSummary summary={summary} /> : null}
        <span className="toolbar-note muted">{backendMessage}</span>
      </section>

      {offline ? (
        <p className="banner banner-danger">
          Backend offline. Start it with: <code>uvicorn main:app --reload --port 8000</code> from{' '}
          <code>backend/</code>
        </p>
      ) : null}

      {analyzeMessage ? (
        <p className={`banner ${analysis ? 'banner-info' : 'muted'}`}>{analyzeMessage}</p>
      ) : null}

      <PipelineVisualizer
        stages={stages}
        activeStageName={activeStageName}
        onStageClick={handleStageClick}
        processing={busy}
        compact
      />

      <main className="workspace-main">
        <div className="workspace-editor">
          <ErrorNavigator
            errors={errors}
            activeIndex={activeErrorIndex ?? 0}
            onSelect={selectError}
          />
          <CodeEditor
            ref={editorRef}
            code={code}
            onChange={setCode}
            markers={markers}
            activeErrorIndex={activeErrorIndex}
          />
        </div>
        <Inspector
          activeTab={inspectorTab}
          onTabChange={setInspectorTab}
          analysis={analysis}
          activeErrorIndex={activeErrorIndex}
          selectedCandidateKey={selectedCandidateKey}
          previewCandidateKey={previewCandidateKey}
          appliedMap={appliedMap}
          onErrorClick={handleErrorClick}
          onSelectCandidate={handleSelectCandidate}
          onPreviewCandidate={handlePreviewCandidate}
          onApplyCandidate={handleApplyCandidate}
          onApplyAllBest={handleApplyAllBest}
          onResetCorrections={handleResetCorrections}
          onApplyToEditor={handleApplyToEditor}
          activeStageName={activeStageName}
          activeStage={activeStage}
        />
      </main>

      <ResultTabs
        activeTab={resultTab}
        onTabChange={setResultTab}
        original={analysis?.original_code || code}
        corrected={correctedDisplay}
        onAccept={handleAcceptCorrection}
        onReject={handleRejectCorrection}
        accepted={accepted}
        analysis={analysis}
        activeErrorIndex={activeErrorIndex ?? 0}
      />

      <footer className="app-footer">
        <p>
          Intelligent Syntax Error Recovery System · Detect • Explain • Correct • Continue
        </p>
        <p className="muted">
          Shortcuts: Ctrl/Cmd+Enter Run Analysis · Alt+↓ Next Error · Alt+↑ Previous Error
        </p>
      </footer>
    </div>
  )
}

function stageToInspectorTab(stageName) {
  switch (stageName) {
    case 'Source Code':
    case 'Lexical Analysis':
      return 'tokens'
    case 'Parsing':
    case 'Result':
      return 'ast'
    case 'Error Detection':
    case 'Classification':
      return 'errors'
    case 'Candidate Generation':
    case 'Correction Scoring':
    case 'Recovery':
      return 'corrections'
    default:
      return null
  }
}
