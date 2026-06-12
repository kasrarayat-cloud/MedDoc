// ============================================================================
// Hybrid anchored-generation flag (2026-06-11). Mirrors the Whisper
// kill-switch pattern: default OFF; prod behavior is byte-identical until
// the pre-registered n=30 protocol passes ON THE NEW PATH and the flag is
// deliberately enabled. Rollback = flag off + container recreate (one step).
// ============================================================================

export function evidenceAnchorsEnabled(): boolean {
  return (process.env.TRANSCRIBE_MD_EVIDENCE_ANCHORS ?? '').toLowerCase() === 'true';
}
