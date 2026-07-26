// ============================================================================
// The visit page IS the document. Build-time, fail-closed, OFF.
// ----------------------------------------------------------------------------
// For a visit whose template is CERTIFIED, the pre-sign page stops being a
// rendering of the note and becomes the doctor's own form — filled with what
// has been captured so far, blank where nothing has. Suggestions and the Rx /
// E/M gates interleave between the pages they belong to, and the pinned
// Sign & Download bar is untouched.
//
// The point is that "review" and "what I am signing" stop being two different
// artifacts. A doctor who reads a styled note and then downloads a filled Word
// form has reviewed the wrong document.
//
// WHAT THIS DOES NOT CHANGE — and a test asserts each one:
//   • the verifier, the gates, and adopt semantics
//   • the sign route and everything it validates
//   • what is audited
// The preview is computed with readAndPrepareTemplateTwinFill, which WRITES
// NOTHING. No fill manifest is created by looking at a document, because the
// sign gate validates a stored manifest and a mid-review one could be stale.
//
// NON-TEMPLATE VISITS ARE UNTOUCHED: no certified twin, no native page — the
// styled note-as-page is the correct surface and stays exactly as it is.
//
// PREVIEW NEVER GATES. Sidecar down, fill failed, template not certified: the
// styled review renders with a named reason and the doctor signs as before.
//
// Rollback: unset NEXT_PUBLIC_VISIT_DOC_PAGE and rebuild.
// ============================================================================

export function isVisitDocPage(): boolean {
  return process.env.NEXT_PUBLIC_VISIT_DOC_PAGE === 'true';
}

export const VISIT_DOC_PAGE_FLAG = 'NEXT_PUBLIC_VISIT_DOC_PAGE';
