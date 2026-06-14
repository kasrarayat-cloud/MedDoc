// ============================================================================
// Stage 1 core-flow redesign flag — the C3 "calm, one-clear-action" skin.
// ----------------------------------------------------------------------------
// Build-time, fail-closed, DEFAULT OFF. When OFF (production today), every
// surface renders the existing Phase-5 "Linear V1" UI byte-for-byte. When ON,
// the chrome + dashboard render the new calm IA.
//
// SKIN-ONLY CONTRACT: this flag gates ONLY presentation. It does NOT gate, and
// no code behind it modifies, the worker/pipeline, the anchored-generation
// verifier, the E/M confirm-before-sign gate, the Rx critical-override
// correlation gate, audit logging, or auth. The new UI calls the SAME server
// actions / API routes as the old UI.
//
// Rollback: unset NEXT_PUBLIC_SKIN_BETA (or set it to anything but 'true') and
// rebuild — the old UI returns. Because it is a NEXT_PUBLIC_* build-time
// constant, both branches are present in the bundle and tree-shaking keeps the
// inactive one out of the hot path.
// ============================================================================

export function isSkinBeta(): boolean {
  return process.env.NEXT_PUBLIC_SKIN_BETA === 'true';
}

export const SKIN_BETA_FLAG = 'NEXT_PUBLIC_SKIN_BETA';
