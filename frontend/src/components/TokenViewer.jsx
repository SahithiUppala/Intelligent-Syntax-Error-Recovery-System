import { useMemo, useState } from 'react'

/**
 * Interactive token table with type filtering.
 */
export default function TokenViewer({ tokens = [], embedded = false }) {
  const [filter, setFilter] = useState('ALL')
  const [hideEof, setHideEof] = useState(true)

  const types = useMemo(() => {
    const set = new Set(tokens.map((token) => token.type))
    return ['ALL', ...Array.from(set).sort()]
  }, [tokens])

  const visible = useMemo(() => {
    return tokens.filter((token) => {
      if (hideEof && token.type === 'EOF') return false
      if (filter === 'ALL') return true
      return token.type === filter
    })
  }, [tokens, filter, hideEof])

  const body =
    tokens.length === 0 ? (
      <p className="muted">No tokens yet. Run analysis to lex the source.</p>
    ) : (
      <>
        <div className="token-controls">
          <label className="field-label" htmlFor="token-filter">
            Filter by type
          </label>
          <select
            id="token-filter"
            className="token-filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            {types.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={hideEof}
              onChange={(e) => setHideEof(e.target.checked)}
            />
            Hide EOF
          </label>
          <span className="count-chip">{visible.length}</span>
        </div>

        <div className="table-scroll">
          <table className="token-table">
            <thead>
              <tr>
                <th>TOKEN</th>
                <th>VALUE</th>
                <th>LINE</th>
                <th>COLUMN</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((token, index) => (
                <tr key={`${token.type}-${token.line}-${token.column}-${index}`}>
                  <td>
                    <span className="token-type-pill">{token.type}</span>
                  </td>
                  <td className="token-value">{token.value === '' ? 'ε' : token.value}</td>
                  <td>{token.line}</td>
                  <td>{token.column}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </>
    )

  if (embedded) {
    return <div className="token-panel embedded-panel">{body}</div>
  }

  return (
    <div className="panel token-panel">
      <div className="panel-heading">
        <h3>Token Viewer</h3>
        <span className="count-chip">{visible.length}</span>
      </div>
      {body}
    </div>
  )
}
