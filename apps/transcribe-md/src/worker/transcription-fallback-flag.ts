// ============================================================================
// Cross-provider transcription fallback kill-switch (2026-06-10)
// ----------------------------------------------------------------------------
// The Deepgram → OpenAI Whisper fallback ships raw patient AUDIO to OpenAI.
// OpenAI has no countersigned BAA on file (see docs/BAA_CHECKLIST.md), so the
// hop is FAIL-CLOSED: disabled unless an operator explicitly opts in AFTER a
// BAA is signed.
//
// Enable ONLY by setting, exactly:
//     TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED=true
//
// Absent / empty / any other value = DISABLED. When disabled, a transient
// Deepgram failure fails the visit into the BullMQ DLQ (retryable, surfaced
// on /admin/queues) instead of silently calling OpenAI. Closes audit item
// 4.2 of docs/qa-reports/pre-pilot-baa-status-20260610T152350Z.md.
// ============================================================================

/** True only when `TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED` is exactly the
 *  string `'true'`. Fail-closed by default — see the file header. */
export function isWhisperFallbackEnabled(): boolean {
  return process.env.TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED === 'true';
}

/** Env-var name, exported so audit metadata + logs can name the flag
 *  without hard-coding the string at every call site. */
export const WHISPER_FALLBACK_FLAG = 'TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED';
