import { useState } from 'react'

/**
 * Readable AST tree with optional collapsible raw JSON.
 */
export default function ParseResult({
  ast = null,
  message = '',
  success = null,
  embedded = false,
  treeMode = false,
  showParseStatus = false,
}) {
  const [showRaw, setShowRaw] = useState(false)
  const statements = ast?.body || []

  const content = !ast ? (
    <p className="muted">{message || 'Run analysis to see the AST.'}</p>
  ) : (
    <>
      <div className="parse-status-row">
        {success != null || showParseStatus ? (
          <span className={`status-pill ${success ? 'ok' : 'bad'}`}>
            {success ? '✓ Parsed' : 'Parsed with errors'}
          </span>
        ) : null}
        <span className="muted parse-summary">
          {statements.length} top-level statement{statements.length === 1 ? '' : 's'}
        </span>
      </div>

      {treeMode ? (
        <ul className="ast-tree">
          <li>
            <span className="ast-node-type">Program</span>
            <ul>
              {statements.map((stmt, index) => (
                <AstNode key={`${stmt.type}-${index}`} node={stmt} />
              ))}
            </ul>
          </li>
        </ul>
      ) : (
        <ul className="stmt-chips">
          {statements.map((stmt, index) => (
            <li key={`${stmt.type}-${index}`}>
              <span className="stmt-chip">{stmt.type}</span>
            </li>
          ))}
        </ul>
      )}

      <details
        className="raw-json-details"
        open={showRaw}
        onToggle={(e) => setShowRaw(e.target.open)}
      >
        <summary>Raw JSON</summary>
        <pre className="ast-preview">{JSON.stringify(ast, null, 2)}</pre>
      </details>
    </>
  )

  if (embedded) {
    return <div className="parse-panel embedded-panel">{content}</div>
  }

  return (
    <div className="panel parse-panel">
      <div className="panel-heading">
        <h3>Parse Result</h3>
      </div>
      {content}
    </div>
  )
}

function AstNode({ node }) {
  if (!node || typeof node !== 'object') {
    return <li className="ast-leaf">{String(node)}</li>
  }

  const type = node.type || 'Node'
  const label = describeNode(node)
  const children = childNodes(node)

  return (
    <li>
      <span className="ast-node-type">{type}</span>
      {label ? <span className="ast-node-label"> {label}</span> : null}
      {children.length > 0 ? (
        <ul>
          {children.map((child, index) => (
            <AstNode key={`${child.type}-${index}`} node={child} />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

function describeNode(node) {
  if (node.type === 'Declaration') {
    return `${node.var_type || ''} ${node.name || ''}`.trim()
  }
  if (node.type === 'Assignment') return node.name || ''
  if (node.type === 'Identifier') return node.name || ''
  if (node.type === 'Literal') return String(node.value ?? '')
  if (node.type === 'BinaryExpression') return node.operator || ''
  if (node.type === 'UnaryExpression') return node.operator || ''
  return ''
}

function childNodes(node) {
  const kids = []
  if (node.initializer) kids.push(node.initializer)
  if (node.value) kids.push(node.value)
  if (node.left) kids.push(node.left)
  if (node.right) kids.push(node.right)
  if (node.argument) kids.push(node.argument)
  if (node.expression) kids.push(node.expression)
  if (node.condition) kids.push(node.condition)
  if (node.then_branch) kids.push(node.then_branch)
  if (node.else_branch) kids.push(node.else_branch)
  if (node.body) {
    if (Array.isArray(node.body)) kids.push(...node.body)
    else kids.push(node.body)
  }
  return kids.filter(Boolean)
}
