// ============================================================================
// Feature gate — ONE-PIPELINE form detect→fill (ruling #326). PER-PRACTICE.
// ----------------------------------------------------------------------------
// ⚠️ THERE IS NO GLOBAL "ON". A practice is enabled ONLY by being in the
// `FORM_DETECT_FILL_PRACTICES` allowlist (a comma-separated list of practiceIds).
// Empty / unset ⇒ OFF for EVERY practice. This replaces the Slice A global
// `NEXT_PUBLIC_FORM_DETECT_FILL` boolean: prod has ~200 practices, so a global
// boolean would route every practice's PDF uploads through the pipeline at once —
// the Slice D acceptance must reach the OWNER's practice ONLY (owner directive
// 2026-09-16), and a per-practice allowlist is the only way to scope it.
//
// SERVER-SIDE (deliberately NOT `NEXT_PUBLIC_`): the gate is read only in server
// code — the export route, the create-draft intercept, the certify action — never
// in a client bundle. So it is NOT inlined at build time, it is read from
// `process.env` at request time, and enabling/disabling a practice is an `.env`
// edit + container recreate — NO rebuild. Both `transcribe-md` and the worker load
// `.env` via `env_file`, so the same value reaches both.
//
// FAIL-CLOSED: a null / absent practiceId is OFF. A caller with no practice cannot
// route onto the pipeline by omission.
// ============================================================================

export const FORM_DETECT_FILL_PRACTICES_ENV = 'FORM_DETECT_FILL_PRACTICES';

/** The set of practiceIds the ONE-PIPELINE detect→fill is enabled for, parsed from
 *  `FORM_DETECT_FILL_PRACTICES` (comma-separated). Read fresh each call so an
 *  `.env` change takes effect on recreate without any code path caching a stale set. */
function allowedPractices(): ReadonlySet<string> {
  return new Set(
    (process.env.FORM_DETECT_FILL_PRACTICES ?? '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
  );
}

/**
 * True iff the ONE-PIPELINE detect→fill is enabled FOR THIS PRACTICE. Per-practice
 * by construction — there is no global enable. Fail-closed on a null/absent practice.
 */
export function formDetectFillEnabled(practiceId: string | null | undefined): boolean {
  if (!practiceId) return false;
  return allowedPractices().has(practiceId);
}

/** URL of the `form-detect` sidecar (FFDNet field detection + fidelity verify),
 *  reached on the internal network like Gotenberg. Default matches the compose
 *  service name. */
export function formDetectUrl(): string {
  return process.env.FORM_DETECT_URL ?? 'http://form-detect:8000';
}
