// ============================================================================
// Feature flag — native-PDF template fill (feat/pdf-native-fill, 2026-07-23)
// ----------------------------------------------------------------------------
// Default OFF. When OFF, the custom-template PDF export path is BYTE-IDENTICAL to
// the styled generator (loadVisitExportData → generateVisitPdf). When ON, and the
// visit's active template is a flat PDF that has been CERTIFIED (its blank page
// bytes + label anchors stored at certify time), the export instead returns the
// doctor's OWN page with generated answers drawn into its blank regions
// (fill-engine + anchors) — never a styled re-creation, his bytes never altered.
//
// Separate from NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX (the DOCX twin path) — that flag
// is untouched. NEXT_PUBLIC_ so the value is legible at build time in the frontend
// and at runtime in the worker. Read via this named helper only (house style:
// co-located helper, `=== 'true'`, default OFF).
// ============================================================================

export const TEMPLATE_NATIVE_PDF_FLAG = 'NEXT_PUBLIC_TEMPLATE_NATIVE_PDF';

export function templateNativePdfEnabled(): boolean {
  return process.env.NEXT_PUBLIC_TEMPLATE_NATIVE_PDF === 'true';
}
