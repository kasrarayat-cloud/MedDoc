// ============================================================================
// Feature flag — native-DOCX template ingestion + export (Template Twin salvage)
// ----------------------------------------------------------------------------
// Default OFF. When OFF, the custom-template .docx path is BYTE-IDENTICAL to the
// live pipeline (docxToTextWithControls → parse → reconcile → fill → styled
// export). When ON, an uploaded .docx template additionally:
//   1. passes the fail-closed OOXML security boundary (macros/OLE/zip attacks
//      rejected — never a half-state), and
//   2. is compiled to a deterministic IR so the doctor's OWN document can be
//      natively re-rendered (formatting preserved, roundtrip-verified) on export.
//
// NEXT_PUBLIC_ so the same value is legible at build time in the frontend and at
// runtime in the worker — the exact rationale as ultrasoundSpecialtyEnabled()
// (packages/shared/src/specialties.ts). Read via this named helper only (house
// style: co-located helper, `=== 'true'`, default OFF).
// ============================================================================

export const TEMPLATE_NATIVE_DOCX_FLAG = 'NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX';

export function templateNativeDocxEnabled(): boolean {
  return process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX === 'true';
}
