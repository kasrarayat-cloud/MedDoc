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

  it('does NOT duplicate the note when the fallback note node is displayed', () => {
    // On the fallback path the SoapEditor mounts and its text is already in the
    // DOM. A second copy makes a screen reader read the whole note twice.
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
