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
// EVERY VISIT GETS A DOCUMENT — superseded 2026-07-27.
//
// This block used to read: "NON-TEMPLATE VISITS ARE UNTOUCHED: no certified
// twin, no native page — the styled note-as-page is the correct surface and
// stays exactly as it is." That was wrong about its own consequences. In
// production the set of visits with a CERTIFIED twin was EMPTY — 0 compiled
// versions, 20 visits, every one of them missing — so "untouched" meant every
// doctor saw the old wall of cards and this flag changed nothing for anyone.
//
// A visit with a note now renders as a paginated document whatever its template
// state: the certified twin fills the doctor's OWN form; everything else is
// built from the styled export — the same file they would download — and says
// plainly that the layout is QuillMD's, with the one step that changes it.
// One review surface, one interaction model.
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
