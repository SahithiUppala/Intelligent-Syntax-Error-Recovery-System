/**
 * Featured example programs for the toolbar (friendly labels).
 * Maps onto backend /api/examples ids — does not change API contracts.
 */

export const FEATURED_EXAMPLE_ORDER = [
  'missing_semicolon',
  'while_missing_paren',
  'missing_opening_brace',
  'missing_operand',
  'continue_after_errors',
  'valid',
]

export const FEATURED_EXAMPLE_LABELS = {
  missing_semicolon: 'Missing Semicolon',
  while_missing_paren: 'Missing Parenthesis',
  missing_opening_brace: 'Missing Brace',
  missing_operand: 'Expression Error',
  continue_after_errors: 'Multiple Errors',
  valid: 'Valid Program',
  demo: 'Demo (Multiple Errors)',
}

/** Offline fallbacks when the backend examples endpoint is unavailable. */
export const LOCAL_FEATURED_EXAMPLES = [
  {
    id: 'missing_semicolon',
    name: 'Missing Semicolon',
    code: 'int x = 10\nint y = 20;\n',
  },
  {
    id: 'while_missing_paren',
    name: 'Missing Parenthesis',
    code: 'while x > 0) {\n    x = x - 1;\n}\n',
  },
  {
    id: 'missing_opening_brace',
    name: 'Missing Brace',
    code: 'if (x < y)\n    x = x + 1;\n',
  },
  {
    id: 'missing_operand',
    name: 'Expression Error',
    code: 'int y = ;\nint z = 30;\n',
  },
  {
    id: 'continue_after_errors',
    name: 'Multiple Errors',
    code: 'int x = 10\nint y = ;\nint z = 30;\n',
  },
  {
    id: 'valid',
    name: 'Valid Program',
    code:
      'int x = 10;\nint y = 20;\n\nif (x < y) {\n    x = x + 1;\n}\n',
  },
]

export function buildFeaturedExamples(apiExamples = []) {
  const byId = new Map((apiExamples || []).map((item) => [item.id, item]))
  const featured = []

  for (const id of FEATURED_EXAMPLE_ORDER) {
    const fromApi = byId.get(id)
    const local = LOCAL_FEATURED_EXAMPLES.find((item) => item.id === id)
    if (fromApi) {
      featured.push({
        ...fromApi,
        name: FEATURED_EXAMPLE_LABELS[id] || fromApi.name,
      })
    } else if (local) {
      featured.push(local)
    }
  }

  // Keep demo available if present but not in the short list
  if (byId.has('demo') && !featured.some((item) => item.id === 'demo')) {
    featured.unshift({
      ...byId.get('demo'),
      name: FEATURED_EXAMPLE_LABELS.demo,
    })
  }

  return featured.length ? featured : LOCAL_FEATURED_EXAMPLES
}
