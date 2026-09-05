// ============================================================================
// A SIGNED NOTE MUST EXIST IN THE ACCESSIBILITY TREE, NOT ONLY ON A CANVAS
// ----------------------------------------------------------------------------
// The signed visit renders the DELIVERED DOCUMENT — `document-pages.tsx` paints
// each page to a `<canvas>` and sets `role="img"`. To a screen reader that is
// one unlabelled raster per page and nothing else: the clinical note, on the
// permanent record, is absent.
//
// ⚠️ THE UNSIGNED PATH ALREADY SOLVED THIS AND SAID WHY, IN ITS OWN WORDS
// (`review-document-view.tsx:243-249`):
//
//     "Without this the entire clinical note a doctor is about to sign would
//      exist nowhere in the DOM, which is not a degraded experience but an
//      absent one."
//
// That reasoning does not weaken once the note is signed — the signed note is
// the permanent record. Measured before this change: `qm-sr-only` occurred in
// exactly ONE source file in the whole application, and it was the unsigned one.
//
// ⚠️ AND THE TEXT MUST BE THE FROZEN RECORD. `page.tsx:588-591` computes
// `soapText` as `signedSoap ?? soapFinal` for a SIGNED visit; every other call
// site in the signed branch passes `adoption?.text ?? props.soapText`. Reading
// an adopted DRAFT aloud from a signed document would be a screen reader hearing
// something the signed record does not say — the failure this file's last arm
// exists to prevent.
// ============================================================================

import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';

// SignedDocumentView mounts SignAndSendModal for the pinned "Export again" bar,
// and that reaches for the app router. Same mock idiom the Rounds board tests
// use — this file is about the accessibility tree, not about navigation.
vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

import { SignedDocumentView } from '../signed-document-view';

const SIGNED_NOTE = [
  'Subjective:',
  'Patient reports two weeks of dry cough. Not taking warfarin.',
  '',
  'Assessment:',
  'Acute bronchitis, resolving.',
].join('\n');

const DRAFT_NOTE = [
  'Subjective:',
  'A DRAFT THAT WAS NEVER SIGNED.',
].join('\n');

function renderSigned(over: Partial<React.ComponentProps<typeof SignedDocumentView>> = {}) {
  return render(
    <SignedDocumentView
      visitId="v1"
      doctorEmail="dr@example.com"
      emailEnabled={false}
      lockBanner={null}
      noteNode={<div data-testid="the-note-node">the editable note</div>}
      documentNode={<div data-testid="the-document-node">the drawn document</div>}
      signedNoteText={SIGNED_NOTE}
      dictationNode={<div>transcript</div>}
      dictationLabel="original dictation"
      summary={{ icd: [], emCode: null, emNotApplicable: true }}
      {...over}
    />
  );
}

import { parseNoteSections } from '@/lib/parse-note-sections';
import { spokenBody } from '@/lib/spoken-body';

/** What this block would say for a given note — the real shipped pipeline. */
const spokenFor = (note: string) =>
  parseNoteSections(note)
    .map((sec) => `[${sec.label}] ${spokenBody(sec.body, note)}`)
    .join(' ');

// ============================================================================
// THE LIMITS, AS EXECUTABLE FACTS RATHER THAN PROSE
// ----------------------------------------------------------------------------
// The adversarial pass proved the claim "the signed note's TEXT is in the
// accessibility tree" false in three ways. All three are INHERITED from the
// shared parse/spoken pipeline — the unsigned review surface has carried them
// since before this change — and none is introduced here: before this block the
// signed note had NO accessible copy at all.
//
// ⚠️ THEY ARE PINNED RATHER THAN DESCRIBED BECAUSE A COMMENT DECAYS AND AN ARM
// DOES NOT. Each of these will RED when somebody fixes the underlying defect,
// which is the point: the arm names the follow-up, and whoever closes it is told
// by a failing test that this file's promise just got bigger.
// ============================================================================
describe('KNOWN LIMITS of the accessible copy — inherited, pinned, not accepted', () => {
  it('LIMIT: content above the first SOAP heading is dropped', () => {
    // `parse-soap-sections.ts` states this in its own docstring. The clinical
    // shape of it: an addendum carrying an allergy, above the first heading,
    // reaches the drawn document and not the listener.
    const note = [
      'ADDENDUM 2026-09-04: patient is ALLERGIC TO PENICILLIN — anaphylaxis.',
      '',
      '## Subjective',
      'Two weeks of dry cough.',
    ].join('\n');
    expect(note).toContain('ALLERGIC TO PENICILLIN');
    expect(
      spokenFor(note),
      'FIXED? Good — content above the first SOAP heading now survives. Update ' +
        'this arm and the comment in signed-document-view.tsx, which documents it as a limit.'
    ).not.toContain('ALLERGIC TO PENICILLIN');

    // CONTROL — the trigger is classic-SOAP mode specifically, not "any
    // preamble". One non-SOAP heading first flips the parser to generic mode and
    // the same line survives. Without this the arm above would misname the bug.
    expect(spokenFor('# Visit Note\n' + note)).toContain('ALLERGIC TO PENICILLIN');
  });

  it('LIMIT: SOAP headings the record does not contain are announced as "Not documented."', () => {
    const note = '## Subjective\nPatient declined further workup today.';
    expect(note.toLowerCase()).not.toContain('assessment');
    expect(
      spokenFor(note),
      'FIXED? Then absent-vs-empty is now discriminated — update this arm.'
    ).toContain('Not documented');

    // CONTROL — where the heading is PRESENT but empty, the export says the same
    // thing, so the two agree and nothing is being asserted that the record does
    // not. That parity is what makes this a bounded defect rather than a general
    // one, and an arm that skipped empties would BREAK it.
    expect(spokenFor('## Subjective\nx\n\n## Assessment\n')).toContain('Not documented');
  });

  // ⚠️ THIS LIMIT NARROWED, AND THE ARM IS REWRITTEN RATHER THAN DELETED.
  //
  // It used to read *"a table header is deleted, and restored only when its
  // rows are unique"*, and it asserted BOTH halves of that defect:
  // `not.toContain('Diameter')` and `toContain('|')`. The spoken-pipeline slice
  // fixed the FIRST half — the header now survives on BOTH of two identical
  // tables, which is the case that used to lose it — so the old arm became a
  // FALSE REJECTION: green code, red gate, and the "fix" would have been to
  // re-break the pipeline.
  //
  // The second half is still true and is still a limit, so it stays pinned.
  // What the listener gets now is the column names followed by a raw pipe row:
  //
  //     Columns: Vein, Diameter (mm), Reflux Time (seconds).
  //     | GSV at the Knee | 6.2 | 1.8 |
  //
  // The numbers are recoverable BY POSITION against the header, which is the
  // clinical harm that mattered — a listener hearing "6.2" with no column
  // identity cannot tell a diameter in mm from a reflux time in seconds.
  it('LIMIT NARROWED: the header now survives colliding tables; the ROW is still raw pipes', () => {
    const table = [
      '| Vein | Diameter (mm) | Reflux Time (seconds) |',
      '| --- | --- | --- |',
      '| GSV at the Knee | 6.2 | 1.8 |',
    ].join('\n');
    const collide = ['## Findings', 'Right Leg', '', table, '', 'Left Leg', '', table].join('\n');
    const spoken = spokenFor(collide);

    // FIXED: the column names reach the listener, on BOTH tables. Counted, not
    // merely `toContain` — the defect was losing the SECOND one to a collision,
    // and a presence check cannot see that.
    expect(spoken.split('Columns: Vein, Diameter (mm), Reflux Time (seconds).').length - 1).toBe(2);

    // STILL A LIMIT: the data rows are passed through as markdown.
    expect(spoken).toContain('| GSV at the Knee | 6.2 | 1.8 |');
    // FIXED? Then the row is being spoken as prose — update this arm, and check
    // the numbers still carry their columns.
  });
});

describe('the signed note reaches the accessibility tree', () => {
  it('renders the note as text when the DOCUMENT is what is displayed', () => {
    renderSigned();
    // The document is displayed…
    expect(screen.getByTestId('the-document-node')).toBeTruthy();
    // …so the note node is NOT mounted (`??` falls through only on nullish),
    // which is precisely why the text has to come from somewhere else.
    expect(screen.queryByTestId('the-note-node')).toBeNull();

    const spoken = screen.getByTestId('signed-document-text');
    expect(spoken.textContent).toContain('Patient reports two weeks of dry cough');
    expect(spoken.textContent).toContain('Acute bronchitis, resolving');
  });

  it('speaks the SIGNED text, never an adopted draft', () => {
    // The defect this guards is not "no text" but "the WRONG text": a screen
    // reader hearing something the signed record does not say.
    renderSigned({ signedNoteText: SIGNED_NOTE });
    const spoken = screen.getByTestId('signed-document-text');
    expect(spoken.textContent).not.toContain('A DRAFT THAT WAS NEVER SIGNED');
    expect(spoken.textContent).toContain('Not taking warfarin.');
  });

  it('does NOT duplicate the note when the fallback NOTE NODE is displayed', () => {
    // On the note fallback the SoapEditor mounts and its text is already in the
    // DOM. A second copy makes a screen reader read the whole note twice.
    //
    // ⚠️ THIS ARM DOES NOT COVER THE WORD PATH, AND THE COMMIT ORIGINALLY
    // CLAIMED IT DID. `usingDocument` tests whether a documentNode ELEMENT was
    // passed, never how it draws. On `docx_fallback` the document renders as
    // REAL DOM TEXT inside that element, so the note IS in the tree twice — and
    // this test cannot see it, because the element it is handed here is a stub.
    // Reaching the real render mode means threading it out of
    // VisitDocumentSurface, which touches the renderer seam; that is a
    // follow-up, not an accessibility change.
    renderSigned({ documentNode: undefined });
    expect(screen.getByTestId('the-note-node')).toBeTruthy();
    expect(screen.queryByTestId('signed-document-text')).toBeNull();
  });

  it('renders nothing rather than an empty shell when there is no text', () => {
    renderSigned({ signedNoteText: '' });
    expect(screen.queryByTestId('signed-document-text')).toBeNull();
  });

  it('adds READING MATTER to the tree and no controls', () => {
    // ⚠️ The obvious wrong fix is to render `noteNode` visually hidden, which
    // would put a whole editor — buttons, textareas — into the accessibility
    // tree as invisible interactive junk. This arm pins that it did not happen.
    renderSigned();
    const spoken = screen.getByTestId('signed-document-text');
    expect(within(spoken).queryAllByRole('button')).toHaveLength(0);
    expect(spoken.querySelectorAll('button, input, textarea, select, a[href]')).toHaveLength(0);
    // It is hidden VISUALLY, not from assistive technology: the class is the
    // clip-rect one, and `hidden`/`aria-hidden` would defeat the entire point.
    expect(spoken.className).toContain('qm-sr-only');
    expect(spoken.getAttribute('aria-hidden')).toBeNull();
    expect(spoken.hasAttribute('hidden')).toBe(false);
  });
});
