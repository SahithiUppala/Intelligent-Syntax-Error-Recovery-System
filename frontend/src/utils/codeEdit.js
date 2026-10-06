/**
 * Shared helpers for applying fragment-level corrections onto full source.
 */

export const SCORE_MAX = {
  grammar_validity: 40,
  local_context: 25,
  token_compatibility: 15,
  parse_progress: 20,
  edit_penalty: 10,
}

export function applyFragmentCorrection(source, candidate) {
  if (!candidate) return source || ''

  // Prefer a full-program corrected source when the scorer/recovery provided one
  if (
    typeof candidate.corrected_source === 'string' &&
    candidate.corrected_source.length > 0 &&
    (candidate.corrected_source.includes('\n') ||
      candidate.corrected_source === source)
  ) {
    return candidate.corrected_source
  }

  const original = source || ''
  const fragment = candidate.original_fragment || candidate.fragment || ''
  const correction = candidate.correction || ''
  const line = Number(candidate.line) || 0

  if (!correction) return original

  const lines = original.split('\n')
  if (line >= 1 && line <= lines.length) {
    const idx = line - 1
    const current = lines[idx]
    if (fragment && current.includes(fragment)) {
      lines[idx] = current.replace(fragment, correction)
      return lines.join('\n')
    }
    const leading = current.slice(0, current.length - current.trimStart().length)
    lines[idx] = `${leading}${correction}`
    return lines.join('\n')
  }

  if (fragment && original.includes(fragment)) {
    return original.replace(fragment, correction)
  }

  return correction
}

/**
 * Rebuild corrected source from the original by applying selected candidates
 * bottom-up (later lines first) so earlier edits do not shift later loci.
 */
export function rebuildCorrectedCode(original, appliedMap) {
  const source = original || ''
  const entries = Object.entries(appliedMap || {})
    .map(([errorIndex, value]) => ({
      errorIndex: Number(errorIndex),
      candidate: value?.candidate,
    }))
    .filter((item) => item.candidate)

  if (!entries.length) return source

  entries.sort((a, b) => {
    const lineA = Number(a.candidate.line) || 0
    const lineB = Number(b.candidate.line) || 0
    if (lineA !== lineB) return lineB - lineA
    const colA = Number(a.candidate.column) || 0
    const colB = Number(b.candidate.column) || 0
    return colB - colA
  })

  // Prefer single full corrected_source only when one candidate is applied
  if (entries.length === 1) {
    return applyFragmentCorrection(source, entries[0].candidate)
  }

  let result = source
  for (const item of entries) {
    // Force fragment-level apply for multi-error rebuild
    const { corrected_source: _drop, ...fragmentCand } = item.candidate
    result = applyFragmentCorrection(result, fragmentCand)
  }
  return result
}

/** Merge score breakdown / corrected_source from flat corrections into report candidates. */
export function enrichCandidate(candidate, flatCorrections = []) {
  if (!candidate) return candidate
  if (candidate.breakdown && candidate.corrected_source) return candidate

  const match = (flatCorrections || []).find(
    (item) =>
      item.correction === candidate.correction &&
      (candidate.line == null || item.line === candidate.line) &&
      (candidate.column == null || item.column === candidate.column),
  )

  if (!match) return candidate
  return {
    ...candidate,
    breakdown: candidate.breakdown || match.breakdown,
    corrected_source:
      candidate.corrected_source && candidate.corrected_source.includes('\n')
        ? candidate.corrected_source
        : match.corrected_source || candidate.corrected_source,
    reason: candidate.reason || match.reason,
    description: candidate.description || match.description,
    score: candidate.score ?? match.score,
    is_best: candidate.is_best || match.is_best,
  }
}

export function summarizeAnalysis(result) {
  if (!result) {
    return {
      errors: 0,
      candidates: 0,
      applied: 0,
      success: false,
      recovered: false,
    }
  }
  return {
    errors: result.errors?.length || result.report?.total_errors || 0,
    candidates: result.corrections?.length || result.pipeline?.candidate_count || 0,
    applied: result.pipeline?.applied_count || result.report?.applied_count || 0,
    success: Boolean(result.success),
    recovered: Boolean(result.pipeline?.recovery_success ?? result.success),
  }
}
