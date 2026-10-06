/**
 * Original vs corrected split view with change highlighting
 * and Accept / Reject actions.
 */

function diffLines(original, corrected) {
  const a = (original || '').split('\n')
  const b = (corrected || '').split('\n')
  const n = a.length
  const m = b.length

  // LCS lengths
  const dp = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      if (a[i] === b[j]) dp[i][j] = dp[i + 1][j + 1] + 1
      else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  const pairs = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      pairs.push({ type: 'same', left: a[i], right: b[j], line: i + 1 })
      i += 1
      j += 1
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      pairs.push({ type: 'delete', left: a[i], right: null, line: i + 1 })
      i += 1
    } else {
      pairs.push({ type: 'insert', left: null, right: b[j], line: j + 1 })
      j += 1
    }
  }
  while (i < n) {
    pairs.push({ type: 'delete', left: a[i], right: null, line: i + 1 })
    i += 1
  }
  while (j < m) {
    pairs.push({ type: 'insert', left: null, right: b[j], line: j + 1 })
    j += 1
  }

  // Detect same-index replacements that LCS split oddly: merge adjacent delete+insert
  const merged = []
  for (let k = 0; k < pairs.length; k += 1) {
    const cur = pairs[k]
    const next = pairs[k + 1]
    if (cur.type === 'delete' && next && next.type === 'insert') {
      merged.push({
        type: 'change',
        left: cur.left,
        right: next.right,
        line: cur.line,
      })
      k += 1
    } else {
      merged.push(cur)
    }
  }
  return merged
}

function diffChars(left, right) {
  const a = left || ''
  const b = right || ''
  const n = a.length
  const m = b.length
  const dp = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      if (a[i] === b[j]) dp[i][j] = dp[i + 1][j + 1] + 1
      else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  const leftParts = []
  const rightParts = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      leftParts.push({ text: a[i], kind: 'same' })
      rightParts.push({ text: b[j], kind: 'same' })
      i += 1
      j += 1
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      leftParts.push({ text: a[i], kind: 'delete' })
      i += 1
    } else {
      rightParts.push({ text: b[j], kind: 'insert' })
      j += 1
    }
  }
  while (i < n) {
    leftParts.push({ text: a[i], kind: 'delete' })
    i += 1
  }
  while (j < m) {
    rightParts.push({ text: b[j], kind: 'insert' })
    j += 1
  }
  return { leftParts, rightParts }
}

function renderParts(parts) {
  return parts.map((part, index) => {
    if (part.kind === 'same') {
      return <span key={index}>{part.text}</span>
    }
    return (
      <span key={index} className={`diff-${part.kind}`}>
        {part.text}
      </span>
    )
  })
}

function DiffPane({ title, rows, side }) {
  return (
    <div className="diff-pane">
      <h4>{title}</h4>
      <div className="diff-code" role="region" aria-label={title}>
        {rows.length === 0 ? (
          <div className="diff-line muted">
            <span className="diff-gutter"> </span>
            <span className="diff-content">// empty</span>
          </div>
        ) : (
          rows.map((row, index) => (
            <div
              key={`${side}-${index}`}
              className={`diff-line diff-line-${row.rowKind}`}
            >
              <span className="diff-gutter">{row.gutter}</span>
              <span className="diff-content">{row.content}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function buildPaneRows(pairs, side) {
  return pairs
    .map((pair) => {
      if (side === 'left') {
        if (pair.type === 'insert') return null
        if (pair.type === 'same') {
          return {
            rowKind: 'same',
            gutter: pair.line,
            content: pair.left || ' ',
          }
        }
        if (pair.type === 'delete') {
          return {
            rowKind: 'delete',
            gutter: pair.line,
            content: <span className="diff-delete">{pair.left || ' '}</span>,
          }
        }
        // change
        const { leftParts } = diffChars(pair.left, pair.right)
        return {
          rowKind: 'change',
          gutter: pair.line,
          content: renderParts(leftParts),
        }
      }

      // right pane
      if (pair.type === 'delete') return null
      if (pair.type === 'same') {
        return {
          rowKind: 'same',
          gutter: pair.line,
          content: pair.right || ' ',
        }
      }
      if (pair.type === 'insert') {
        return {
          rowKind: 'insert',
          gutter: pair.line,
          content: <span className="diff-insert">{pair.right || ' '}</span>,
        }
      }
      const { rightParts } = diffChars(pair.left, pair.right)
      return {
        rowKind: 'change',
        gutter: pair.line,
        content: renderParts(rightParts),
      }
    })
    .filter(Boolean)
}

export default function CorrectedCode({
  original = '',
  corrected = '',
  onAccept,
  onReject,
  accepted = false,
  embedded = false,
}) {
  const hasCorrected = Boolean(corrected)
  const unchanged = hasCorrected && original === corrected
  const pairs = hasCorrected ? diffLines(original, corrected) : []
  const leftRows = buildPaneRows(pairs, 'left')
  const rightRows = buildPaneRows(pairs, 'right')

  const changeCount = pairs.filter((p) => p.type !== 'same').length

  const body = (
    <>
      <div className="compare-header">
        <div>
          {!embedded ? <h3>Original vs Corrected</h3> : null}
          <p className="muted compare-subtitle">
            {!hasCorrected
              ? 'Run analysis to generate a corrected preview.'
              : unchanged
                ? 'No textual changes — source already valid.'
                : `${changeCount} changed line region(s). Insertions highlighted in green.`}
          </p>
        </div>
        <div className="compare-actions">
          <button
            type="button"
            className="btn primary"
            disabled={!hasCorrected || unchanged}
            onClick={() => onAccept?.(corrected)}
          >
            Apply Corrected Code to Editor
          </button>
          <button
            type="button"
            className="btn"
            disabled={!hasCorrected}
            onClick={() => onReject?.()}
          >
            Reset Preview
          </button>
        </div>
      </div>

      {accepted ? (
        <p className="banner-success">Correction accepted into the editor.</p>
      ) : null}

      <div className="code-compare">
        <DiffPane title="Original Code" rows={leftRows} side="left" />
        <DiffPane
          title="Corrected Code"
          rows={
            hasCorrected
              ? rightRows
              : [
                  {
                    rowKind: 'same',
                    gutter: ' ',
                    content: '// corrected source',
                  },
                ]
          }
          side="right"
        />
      </div>

      <div className="diff-legend">
        <span>
          <i className="swatch insert" /> Inserted
        </span>
        <span>
          <i className="swatch delete" /> Removed
        </span>
        <span>
          <i className="swatch change" /> Changed line
        </span>
      </div>
    </>
  )

  if (embedded) {
    return <div className="corrected-panel embedded-panel">{body}</div>
  }

  return <div className="panel corrected-panel">{body}</div>
}
