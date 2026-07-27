// ============================================================================
// Real-document preview. Build-time, fail-closed, OFF.
// ----------------------------------------------------------------------------
// Flag ON, the settings surfaces stop showing a markdown mock of the doctor's
// note and start showing the DOCUMENT:
//
//   confirm card   their uploaded form — a flat PDF rendered FILLED, sample
//                  answers in their own blanks; a .docx rendered as the page it
//                  is, labelled as unfilled rather than dressed up as a fill.
//   settings row   "See your form" opens, inline, the artifact certification
//                  itself verified. Not a re-typeset approximation of it.
//                  ⚠ THIS HALF ALSO REQUIRES NEXT_PUBLIC_SETTINGS_SIMPLE_ROW.
//                  The simple row is the only row that has it; the legacy row
//                  is deliberately frozen and gains nothing. Turning this flag
//                  on ALONE therefore changes the confirm card and leaves the
//                  settings list exactly as it was — intended, but silent, so
//                  it is written here rather than discovered.
//
// The mock it replaces answered "did we read your sections". That is our
// question. The doctor's question is "will this come back looking like my
// document", and only the document can answer it.
//
// Flag OFF, both surfaces keep the markdown sample byte-for-byte, and the
// converter sidecar is never called.
//
// Rollback: unset NEXT_PUBLIC_DOC_PREVIEW and rebuild.
// ============================================================================

export function isDocPreview(): boolean {
  return process.env.NEXT_PUBLIC_DOC_PREVIEW === 'true';
}

export const DOC_PREVIEW_FLAG = 'NEXT_PUBLIC_DOC_PREVIEW';
