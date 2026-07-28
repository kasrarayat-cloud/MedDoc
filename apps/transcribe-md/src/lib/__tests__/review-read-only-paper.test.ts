// ============================================================================
// The review page is READ-ONLY PAPER.
// ----------------------------------------------------------------------------
// The pre-sign review screen renders the document being signed. Everything a
// doctor can DO sits in three places and nowhere else: the chat editor, the
// gate stack (Rx cards, the E/M level card), and Sign & Download.
//
// This file pins that shape. Two kinds of assertion:
//
//   • NO-REMNANTS — the deleted furniture is gone from the source, not merely
//     hidden behind a flag. A flag-gated remnant comes back the moment someone
//     flips the flag to debug something else.
//   • BEHAVIOURAL — the E/M suppression on imaging visits, executed against the
//     real specialty resolver rather than grepped for.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import {
  findSpecialty,
  isImagingReportSpecialty,
} from '@meddoc/shared/specialties';

const read = (p: string) => readFileSync(p, 'utf8');

const REVIEW_DOC = 'src/app/visits/[id]/review-document-view.tsx';
const READY_VIEW = 'src/app/visits/[id]/visit-ready-view.tsx';
const SOAP_EDITOR = 'src/app/visits/[id]/soap-editor.tsx';
const VISIT_PAGE = 'src/app/visits/[id]/page.tsx';
const INTENT = 'src/lib/chat-edit/intent.ts';
const PROMPT = 'src/lib/chat-edit/prompt.ts';

describe('the per-section edit machinery is gone', () => {
  it('SectionEditCard no longer exists and nothing imports it', () => {
    expect(() => read('src/app/visits/[id]/section-edit-card.tsx')).toThrow();
    expect(read(READY_VIEW)).not.toContain('SectionEditCard');
  });

  it('no "Edit <SECTION>" pill testids survive anywhere in the app', () => {
    // Grepped by SELECTOR, not by the word "edit". The lesson from the
    // suggestion-lane cut: assertions hide in files whose names give no hint,
    // and the selector is the thing a test actually drives.
    for (const f of [REVIEW_DOC, READY_VIEW, SOAP_EDITOR]) {
      const src = read(f);
      expect(src).not.toContain('section-edit-');
      expect(src).not.toContain('section-textarea-');
      expect(src).not.toContain('section-save-');
      expect(src).not.toContain('section-uneditable-');
    }
  });

  it('the review page no longer holds a per-section save callback', () => {
    const src = read(READY_VIEW);
    expect(src).not.toContain('saveSection');
    expect(src).not.toContain('saveNoteSectionAction');
  });

  it('but the ACTION survives — the chat editor writes through it', () => {
    // The pill and the chat always shared one splice-and-save. Deleting the
    // pill must not delete the write path, or every section edit dies with it.
    expect(() => read('src/actions/save-note-section.ts')).not.toThrow();
    expect(read('src/actions/chat-edit-visit.ts')).toContain('saveNoteSectionAction');
  });

  it('the note rendered AS the document is read-only', () => {
    // `chromeless` is exactly "this editor is being rendered as the document".
    // On those surfaces the click-to-edit textarea must not mount, or the paper
    // has a second write path on top of it.
    const src = read(SOAP_EDITOR);
    expect(src).toContain('readonly={isReadonly || chromeless}');
  });

  it('the LEGACY tabbed editor keeps inline editing', () => {
    // It is a workspace, not paper — and it is what the default CI project
    // exercises. Deleting its editor would red the required gate for no gain.
    const src = read(READY_VIEW);
    const legacy = src.slice(src.lastIndexOf('<SoapEditor'));
    expect(legacy).not.toContain('chromeless');
  });
});

describe('the inline panels are gone from the review page', () => {
  const src = read(REVIEW_DOC);

  it('renders no billing panel, codes table or input transcript', () => {
    for (const remnant of [
      'billingNode',
      'codesNode',
      'dictationNode',
      'dictationLabel',
      'review-doc-billing-panel',
      'review-doc-codes-panel',
      'review-doc-dictation-panel',
      'qm-rdoc-meta',
      'hasSummary',
    ]) {
      expect(src).not.toContain(remnant);
    }
  });

  it('and the parent stopped constructing them for it', () => {
    const ready = read(READY_VIEW);
    const branch = ready.slice(
      ready.indexOf('if (isReviewDocView() && !isSigned) {'),
      ready.indexOf('if (isUxSimplify() && isSigned) {'),
    );
    expect(branch).toContain('<ReviewDocumentView');
    for (const remnant of ['billingNode', 'codesNode', 'dictationNode', 'summary={']) {
      expect(branch).not.toContain(remnant);
    }
  });

  it('the gate stack and Sign survive — they were never part of the panels', () => {
    expect(src).toContain('review-doc-rx-gate');
    expect(src).toContain('review-doc-em-stale-gate');
    expect(src).toContain('review-doc-em-gate');
    expect(src).toContain('review-doc-em-rescore');
    expect(src).toContain('<SignAndSendModal');
  });

  it('the SIGNED view is untouched — it keeps its own transcript disclosure', () => {
    // Different surface, different job: the panels came off the pre-sign page.
    expect(read('src/app/visits/[id]/signed-document-view.tsx')).toContain(
      'signed-doc-dictation-toggle',
    );
  });
});

describe('no dangling chat intents', () => {
  it('scroll_to lost `codes` with the panel it pointed at', () => {
    const src = read(INTENT);
    const decl = src.slice(src.indexOf('ScrollIntentSchema'), src.indexOf('RefuseIntentSchema'));
    expect(decl).toContain("'rx_gate'");
    expect(decl).toContain("'em_gate'");
    expect(decl).toContain("'document'");
    expect(decl).not.toContain("'codes'");
  });

  it('every scroll target still resolves to a real anchor', () => {
    // The union is only honest if each member has something to scroll to. Two
    // resolve by testid in the handler; the third by data-chat-target.
    const ready = read(READY_VIEW);
    const review = read(REVIEW_DOC);
    expect(ready).toContain('review-doc-rx-gate');
    expect(ready).toContain('visit-document');
    expect(review).toContain('data-chat-target="em_gate"');
    expect(review).not.toContain('data-chat-target="codes"');
  });

  it('the PROMPT stops advertising targets and tools that no longer exist', () => {
    // The prompt is not schema-checked, so drift here is silent: the model is
    // told about a tool, emits it, and the reply fails validation as a whole.
    // `suggestions` had been left behind by the suggestion-lane cut.
    const src = read(PROMPT);
    expect(src).not.toContain('adopt_suggestion');
    expect(src).not.toContain('listed_suggestions');
    expect(src).not.toContain('suggestions the outstanding');
    expect(src).not.toContain('target `codes`');
  });

  it('"show billing" is a CANNOT, not a refusal', () => {
    // Refusing tells the doctor their own coding is out of bounds. It is not —
    // it just is not on this page any more.
    const src = read(PROMPT);
    expect(src).toContain('`cannot`, not `refuse`');
  });
});

describe('an imaging visit has NO E/M level — not displayed, not computed, not stored', () => {
  it('the specialty resolver round-trips a label to the id the predicate takes', () => {
    // THE BUG THIS PINS. `page.tsx` passed `specialtyLabel(visit.specialty)` —
    // 'Ultrasound' — into `isImagingReportSpecialty`, which compares against
    // the ID 'ultrasound'. The comparison was always false, so emNotApplicable
    // was always false, and every ultrasound visit computed an office E/M level
    // and persisted it to emScoredCode.
    expect(isImagingReportSpecialty('ultrasound')).toBe(true);
    expect(isImagingReportSpecialty('Ultrasound')).toBe(false);

    // The fix passes the RAW COLUMN through the resolver, and the raw column is
    // already an id — so this is the path that has to hold, and it does.
    expect(isImagingReportSpecialty(findSpecialty('ultrasound').id)).toBe(true);

    // A legacy row must answer a predicate the same way a canonical one does.
    expect(findSpecialty('Cardiology').id).toBe('cardiology');
    expect(findSpecialty('pain').id).toBe('pain-management');
    expect(isImagingReportSpecialty(findSpecialty('Cardiology').id)).toBe(false);

    // AND THE LABEL DOES NOT ROUND-TRIP — deliberately pinned, because it is
    // what made the original bug silent rather than loud. 'Ultrasound' is not a
    // key in the legacy map (ultrasound post-dates the display-name era, so no
    // row ever stored it that way), so feeding a label to the resolver yields
    // `unspecified` — a real specialty, quietly the wrong one. Nothing throws.
    // The only safe input is the id.
    expect(findSpecialty('Ultrasound').id).toBe('unspecified');
  });

  it('the page derives emNotApplicable from the ID prop, never the label', () => {
    const src = read(VISIT_PAGE);
    const decl = src.slice(src.indexOf('const emNotApplicable'), src.indexOf('const emNotApplicable') + 300);
    expect(decl).toContain('props.specialtyId');
    expect(decl).not.toContain('props.specialty)');
    // And the id prop is fed the canonicalised value, not the raw column.
    expect(src).toContain('specialtyId={specialtyId(visit.specialty)}');
  });

  it('COMPUTE is skipped: the scorer sits behind the flag', () => {
    const src = read(VISIT_PAGE);
    const guard = src.indexOf('if (!emNotApplicable) {');
    expect(guard).toBeGreaterThan(-1);
    expect(src.indexOf('computeEmScore(')).toBeGreaterThan(guard);
  });

  it('STORE is skipped at every emScoredCode writer', () => {
    // Three writers. Each one must be unreachable for an imaging visit, or the
    // column carries a clinic code on an imaging report — wrong as DATA, which
    // outlives any UI decision because export and the signed record read it.
    const page = read(VISIT_PAGE);
    const pageSeed = page.slice(page.indexOf('if (!emNotApplicable) {'));
    expect(pageSeed).toContain('emScoredCode: code');

    // seedEmBaselineIfUnset takes the guard as a REQUIRED parameter, so a new
    // caller cannot forget it — it will not typecheck.
    const seed = read('src/lib/em-coding/seed-baseline.ts');
    expect(seed).toContain('applies: boolean;');
    expect(seed).toContain('if (!input.applies) return;');

    for (const caller of [
      'src/actions/soap.ts',
      'src/app/api/visits/[id]/em-score/apply-additions/route.ts',
    ]) {
      const src = read(caller);
      expect(src).toContain('seedEmBaselineIfUnset(');
      expect(src).toContain(
        'applies: !(ultrasoundSpecialtyEnabled() && isImagingReportSpecialty(visit.specialty)),',
      );
    }

    // The re-score never scores an imaging visit — it clears the flag instead.
    const rescore = read('src/actions/rescore-em.ts');
    const imagingBranch = rescore.slice(
      rescore.indexOf('if (ultrasoundSpecialtyEnabled() && isImagingReportSpecialty(visit.specialty)) {'),
      rescore.indexOf('let scored: string;'),
    );
    expect(imagingBranch).toContain('emStale: false');
    expect(imagingBranch).not.toContain('emScoredCode');
  });

  it('these guards all read the raw column, which IS an id', () => {
    // The page needed a new prop because it had already turned the column into
    // a label. Everywhere else reads `visit.specialty` straight off Prisma, so
    // the predicate gets an id and the same bug cannot be there.
    for (const f of [
      'src/actions/soap.ts',
      'src/actions/rescore-em.ts',
      'src/app/api/visits/[id]/sign/route.ts',
    ]) {
      expect(read(f)).toContain('isImagingReportSpecialty(visit.specialty)');
    }
  });
});
