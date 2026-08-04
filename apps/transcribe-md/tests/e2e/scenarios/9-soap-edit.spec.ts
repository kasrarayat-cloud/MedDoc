// ============================================================================
// Scenario 9 — RETIRED 2026-08-04, F-ret.1 #19. Kept as a tombstone, on purpose.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE INTENTIONALLY CONTAINS NO TESTS. It is a `describe.skip` holding
// the record of what was removed and what the required pack lost with it.
// Deleting the file outright would have erased that, and the next person to
// notice the coverage hole would have had to rediscover why it exists.
//
// WHAT IT PINNED. Click-to-edit on a SOAP section opens a textarea over the
// full markdown blob; Esc/blur persists via `saveSoapDraftAction`; the edit
// survives a reload — i.e. it went to the server, not just to local state. The
// reload half was the point of the test.
//
// WHY IT IS NO LONGER LOAD-BEARING. The inline editor cannot render on any
// shipped surface:
//
//   soap-editor.tsx:359      readonly={isReadonly || chromeless}
//   SoapInlineEdit.tsx:92    if (readonly) return <div>{children}</div>
//                            — no textarea, no button, no affordance at all
//
// and BOTH live mounts pass `chromeless`: `review-document-view.tsx:48` (the
// unsigned read-only paper) and `signed-document-view.tsx:56` (the signed one).
// So `getByRole('button', { name: 'Edit SOAP note' })` cannot resolve, and the
// aria-label at `SoapInlineEdit.tsx:107,132` is on the branch `readonly`
// already returned before.
//
// It died with the read-only-paper work on 2026-07-28, not with the Rounds
// flip. The flag-ON run is simply the first run that ever looked.
//
// ⚠️ WHAT THE REQUIRED PACK LOSES, STATED PLAINLY RATHER THAN ABSORBED.
// The default `chromium` project no longer covers NOTE-EDIT PERSISTENCE — that
// an edit to a note reaches the server and survives a reload. That capability
// still exists in the product; it moved to the chat editor
// (`saveNoteSectionAction`, driven from the Rounds chat drawer), and it is
// covered by `rounds-stage` and by the production clinical walks.
//
// But those are FLAG-ON packs. Until F-ret migrates the default project to the
// Rounds contract, the required check has **no** note-edit-persistence
// coverage. That is a real hole, it is deliberate, and it is recorded in
// `docs/rounds/RELAY.md` rather than left for a future audit to find.
//
// UN-RETIRE CONDITION: if an inline editing affordance ever returns to a
// shipped surface, this file is where its test belongs — the persistence
// assertion (edit → reload → still there) is the shape worth restoring, not the
// selectors.
// ============================================================================

import { test } from '@playwright/test';

test.describe.skip('Scenario 9 — inline SOAP edit (RETIRED — see the header)', () => {
  test('inline-editing a section persists + survives reload', () => {
    // Intentionally empty. The surface this drove does not exist on any
    // shipped build; see the header for the flag arithmetic and for what the
    // required pack lost.
  });
});
