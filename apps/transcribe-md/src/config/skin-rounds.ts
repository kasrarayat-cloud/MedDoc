// ============================================================================
// ROUNDS — the full app re-skin flag.
// ----------------------------------------------------------------------------
// Rounds is the merge of two design directions: Ward Board (the dark stage, the
// patient-lane × stage-column matrix, position-awareness, blocker language) and
// Focus Flow (the spotlit sheet, the sequential gates, the deep paper shadow).
// docs/design-tokens.md is the authority for what it looks like.
//
// Build-time, fail-closed, DEFAULT OFF. When OFF, every surface renders exactly
// what it renders today.
//
// SKIN-ONLY CONTRACT — the same one NEXT_PUBLIC_SKIN_BETA carries, and it is
// worth restating because Rounds touches far more surfaces:
//
//   This flag gates PRESENTATION ONLY. Nothing behind it modifies the worker or
//   pipeline, the anchored-generation verifier, the E/M confirm-before-sign
//   gate, the critical-Rx typed-override gate, the attestation gate, audit
//   logging, or auth. The new UI calls the SAME server actions and API routes.
//
//   The gates in particular are UI OVER SERVER REFUSALS. `POST /sign` refuses
//   independently of anything drawn on screen, and it stays the sole source of
//   truth. A Rounds gate that looked cleared while the server still refused
//   would be the pretend-success failure class — the E2Es that assert the
//   server-side block must pass unchanged.
//
// TWO INVARIANTS THAT ARE EASY TO BREAK WHILE RE-SKINNING:
//
//   1. `emApplies` decides whether the E/M gate EXISTS, not how it looks. On an
//      imaging report there is no E/M gate at all — not a hidden one, not a
//      disabled one. Rounds must not introduce a styled-empty variant.
//   2. Custom templates render UNTOUCHED. Rounds styles the DEFAULT QuillMD
//      paper layout only. A practice that uploaded its own letterhead did not
//      ask for our typography.
//
// Rollback: unset NEXT_PUBLIC_SKIN_ROUNDS (or set it to anything but 'true')
// and rebuild. Because it is a NEXT_PUBLIC_* build-time constant it is INLINED
// at build; a surviving runtime read in the shipped bundle means it was not
// inlined and the flag is not doing what you think. Grep the built chunk, not
// `.env` — see the prod-smoke step in AGENTS.md.
// ============================================================================

export function isSkinRounds(): boolean {
  return process.env.NEXT_PUBLIC_SKIN_ROUNDS === 'true';
}

export const SKIN_ROUNDS_FLAG = 'NEXT_PUBLIC_SKIN_ROUNDS';

/** The attribute the token layer scopes to. Applied on <html> so the stage
 *  background and every token cascade from the root, and so a screenshot of any
 *  page shows which skin produced it. */
export const SKIN_ROUNDS_ATTR = 'data-skin';
export const SKIN_ROUNDS_VALUE = 'rounds';
