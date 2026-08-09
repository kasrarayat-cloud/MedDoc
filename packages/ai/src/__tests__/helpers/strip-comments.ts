// ============================================================================
// Shared source-scanning helper for the B1 gates.
// ----------------------------------------------------------------------------
// Extracted from `gate-b1b-request-id-capture.test.ts` when the step 2 gate
// needed it too. It lives in its OWN module rather than being imported from a
// `.test.ts` file for a concrete reason: importing a spec file EXECUTES its
// `describe` blocks in the importer, so the step 1 gate's 12 tests ran a second
// time inside the step 2 gate's file. Harmless, but it makes a suite's test
// count a function of who imports whom — and a count nobody can predict is a
// count nobody notices moving.
// ============================================================================

/**
 * Strip `//` and block comments, quote-aware.
 *
 * Quote awareness is the whole point: `deepgram-batch.ts` builds an https URL,
 * and a stripper that cut at the first `//` would truncate real code and then
 * silently under-count call sites — a false all-clear.
 *
 * ⚠️ Comment-stripping is not a nicety in this repo, it is the fix for a
 * recurring defect: prose is where the words you are grepping for are
 * GUARANTEED to appear, so a source scan that reads comments finds its own
 * documentation and reports it as code. Both B1 gates depend on this, and both
 * positive-control it against a REAL file rather than only a fixture.
 */
export function stripComments(src: string): string {
  let out = '';
  let i = 0;
  type State = 'code' | 'line' | 'block' | 'sq' | 'dq' | 'tpl';
  let state: State = 'code';

  while (i < src.length) {
    const c = src[i];
    const next = src[i + 1];

    if (state === 'code') {
      if (c === '/' && next === '/') { state = 'line'; i += 2; continue; }
      if (c === '/' && next === '*') { state = 'block'; i += 2; continue; }
      if (c === "'") state = 'sq';
      else if (c === '"') state = 'dq';
      else if (c === '`') state = 'tpl';
      out += c; i++; continue;
    }

    if (state === 'line') {
      if (c === '\n') { state = 'code'; out += c; }
      i++; continue;
    }

    if (state === 'block') {
      if (c === '*' && next === '/') { state = 'code'; i += 2; continue; }
      // Keep newlines so line numbers survive for error messages.
      if (c === '\n') out += c;
      i++; continue;
    }

    // Inside a string literal: copy verbatim, honour escapes.
    out += c;
    if (c === '\\') { out += src[i + 1] ?? ''; i += 2; continue; }
    if (state === 'sq' && c === "'") state = 'code';
    else if (state === 'dq' && c === '"') state = 'code';
    else if (state === 'tpl' && c === '`') state = 'code';
    i++;
  }
  return out;
}
