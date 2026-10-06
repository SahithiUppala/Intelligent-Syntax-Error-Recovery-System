import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import Editor, { loader } from '@monaco-editor/react'

const LANGUAGE_ID = 'minic'

let languageRegistered = false

function registerMiniC(monaco) {
  if (languageRegistered) return
  languageRegistered = true

  monaco.languages.register({ id: LANGUAGE_ID })
  monaco.languages.setMonarchTokensProvider(LANGUAGE_ID, {
    keywords: ['int', 'float', 'if', 'else', 'while'],
    operators: ['=', '==', '!=', '<', '>', '<=', '>=', '+', '-', '*', '/'],
    symbols: /[=><!~?:&|+\-*/^%]+/,
    tokenizer: {
      root: [
        [/[a-zA-Z_]\w*/, {
          cases: {
            '@keywords': 'keyword',
            '@default': 'identifier',
          },
        }],
        [/\d+\.\d+/, 'number.float'],
        [/\d+/, 'number'],
        [/\/\/.*$/, 'comment'],
        [/\/\*/, 'comment', '@comment'],
        [/[{}()\[\]]/, 'delimiter.bracket'],
        [/;/, 'delimiter'],
        [/@symbols/, {
          cases: {
            '@operators': 'operator',
            '@default': '',
          },
        }],
        [/\s+/, 'white'],
      ],
      comment: [
        [/[^/*]+/, 'comment'],
        [/\*\//, 'comment', '@pop'],
        [/[/*]/, 'comment'],
      ],
    },
  })

  monaco.languages.setLanguageConfiguration(LANGUAGE_ID, {
    comments: {
      lineComment: '//',
      blockComment: ['/*', '*/'],
    },
    brackets: [
      ['{', '}'],
      ['(', ')'],
    ],
    autoClosingPairs: [
      { open: '{', close: '}' },
      { open: '(', close: ')' },
    ],
  })
}

/**
 * Monaco-based source editor for the mini C-like language.
 *
 * Props:
 * - code / onChange
 * - markers: [{ line, column, message, severity? }]
 * - readOnly
 */
const CodeEditor = forwardRef(function CodeEditor(
  {
    code = '',
    onChange,
    markers = [],
    readOnly = false,
    height = '320px',
    activeErrorIndex = null,
  },
  ref,
) {
  const editorRef = useRef(null)
  const monacoRef = useRef(null)
  const decorationRef = useRef([])

  useImperativeHandle(ref, () => ({
    focus() {
      editorRef.current?.focus()
    },
    revealError(error) {
      const editor = editorRef.current
      if (!editor || !error) return
      const line = Math.max(1, error.line || 1)
      const column = Math.max(1, error.column || 1)
      editor.revealPositionInCenter({ lineNumber: line, column })
      editor.setPosition({ lineNumber: line, column })
      editor.focus()
    },
    getEditor() {
      return editorRef.current
    },
  }))

  function handleMount(editor, monaco) {
    editorRef.current = editor
    monacoRef.current = monaco
    registerMiniC(monaco)
    const model = editor.getModel()
    if (model) {
      monaco.editor.setModelLanguage(model, LANGUAGE_ID)
    }
    applyMarkers(monaco, editor, markers)
    applyActiveDecoration(monaco, editor, markers, activeErrorIndex, decorationRef)
  }

  useEffect(() => {
    if (monacoRef.current && editorRef.current) {
      applyMarkers(monacoRef.current, editorRef.current, markers)
      applyActiveDecoration(
        monacoRef.current,
        editorRef.current,
        markers,
        activeErrorIndex,
        decorationRef,
      )
    }
  }, [markers, code, activeErrorIndex])

  return (
    <div className="panel editor-panel">
      <div className="editor-header">
        <h3>Code Editor</h3>
        <span className="editor-badge">mini-C · Monaco</span>
      </div>
      <div className="monaco-shell">
        <Editor
          height={height}
          language={LANGUAGE_ID}
          theme="vs-dark"
          value={code}
          onChange={(value) => onChange?.(value ?? '')}
          onMount={handleMount}
          beforeMount={(monaco) => {
            registerMiniC(monaco)
          }}
          options={{
            readOnly,
            fontSize: 14,
            fontFamily: 'Cascadia Code, Consolas, Courier New, monospace',
            lineNumbers: 'on',
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 4,
            renderLineHighlight: 'line',
            cursorBlinking: 'smooth',
            wordWrap: 'off',
            padding: { top: 12, bottom: 12 },
            glyphMargin: true,
            folding: true,
            roundedSelection: true,
            overviewRulerLanes: 0,
          }}
          loading={<div className="monaco-loading">Loading editor…</div>}
        />
      </div>
    </div>
  )
})

function applyMarkers(monaco, editor, markers) {
  const model = editor.getModel()
  if (!model) return

  const Severity = monaco.MarkerSeverity
  const monacoMarkers = (markers || []).map((marker) => {
    const line = Math.max(1, marker.line || 1)
    const column = Math.max(1, marker.column || 1)
    const severity =
      marker.severity === 'warning' ? Severity.Warning : Severity.Error
    return {
      startLineNumber: line,
      startColumn: column,
      endLineNumber: line,
      endColumn: column + Math.max(1, marker.length || 1),
      message: marker.message || marker.type || 'Syntax error',
      severity,
    }
  })

  monaco.editor.setModelMarkers(model, 'isers', monacoMarkers)
}

function applyActiveDecoration(monaco, editor, markers, activeErrorIndex, decorationRef) {
  const model = editor.getModel()
  if (!model) return

  const active =
    typeof activeErrorIndex === 'number' ? markers[activeErrorIndex] : null

  const next = []
  if (active) {
    const line = Math.max(1, active.line || 1)
    const column = Math.max(1, active.column || 1)
    const endCol = column + Math.max(1, active.length || 1)
    next.push({
      range: new monaco.Range(line, column, line, endCol),
      options: {
        className: 'monaco-error-highlight',
        isWholeLine: false,
        overviewRuler: {
          color: '#f07178',
          position: monaco.editor.OverviewRulerLane.Center,
        },
      },
    })
    next.push({
      range: new monaco.Range(line, 1, line, 1),
      options: {
        isWholeLine: true,
        className: 'monaco-error-line',
      },
    })
  }

  decorationRef.current = editor.deltaDecorations(decorationRef.current, next)
}

// Prefer local Vite bundling; avoid unexpected CDN stalls in offline demos
loader.config({
  paths: {
    // default CDN still works; Vite plugin path kept implicit via package
  },
})

export default CodeEditor
