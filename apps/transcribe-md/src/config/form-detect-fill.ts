// ============================================================================
// Feature flag — ONE-PIPELINE form detect→fill (ruling #326, Slice A).
// ----------------------------------------------------------------------------
// Default OFF. Slice A ships the `lib/form-fill` pipeline and the `form-detect`
// sidecar ADDITIVELY — nothing is routed onto them while this is OFF, so the
// upload/certify/export paths are byte-identical to today. Later slices route
// PDF (B) then prose-Word (C) uploads onto it behind this same flag.
//
// NEXT_PUBLIC_ so the value is legible at build time in the frontend and at
// runtime in the worker. Read via these named helpers only (house style:
// co-located helper, `=== 'true'`, default OFF).
// ============================================================================

export const FORM_DETECT_FILL_FLAG = 'NEXT_PUBLIC_FORM_DETECT_FILL';

export function formDetectFillEnabled(): boolean {
  return process.env.NEXT_PUBLIC_FORM_DETECT_FILL === 'true';
}

/** URL of the `form-detect` sidecar (FFDNet field detection + fidelity verify),
 *  reached on the internal network like Gotenberg. Default matches the compose
 *  service name. */
export function formDetectUrl(): string {
  return process.env.FORM_DETECT_URL ?? 'http://form-detect:8000';
}
