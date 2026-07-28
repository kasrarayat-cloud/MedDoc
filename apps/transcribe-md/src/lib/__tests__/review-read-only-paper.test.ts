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

describe('the level is shown, and the doctor may disagree with it', () => {
  const card = read('src/app/visits/[id]/em-level-card.tsx');
  const review = read(REVIEW_DOC);

  it('the gate stack carries a level row with an adjust affordance', () => {
    expect(review).toContain('<EmLevelCard');
    expect(card).toContain('review-doc-em-level');
    expect(card).toContain('em-level-current');
    expect(card).toContain('em-level-adjust');
    expect(card).toContain('em-level-select');
    expect(card).toContain('em-level-reason');
    expect(card).toContain('em-level-save');
  });

  it('it renders NOTHING when there is no level — imaging has none', () => {
    // `emLevel` is null when emNotApplicable, so the row is absent rather than
    // showing an office code on an imaging report.
    expect(card).toContain('if (!level) return null;');
    expect(read(READY_VIEW)).toContain('props.emNotApplicable\n      ? null');
  });

  it('the reason is REQUIRED, in the UI and at the route', () => {
    // Armed only when the change is real AND the reason is there — a disabled
    // control rather than a told-off-after-the-fact validation message.
    expect(card).toContain('disabled={saving || !reasonOk || !changed}');
    expect(card).toContain('reason.trim().length >= 3');
    const route = read('src/app/api/visits/[id]/em-score/override/route.ts');
    expect(route).toContain('reason: z.string().trim().min(MIN_REASON_LENGTH)');
    expect(route).not.toContain('reason: z.string().max(MAX_REASON_LENGTH).optional()');
  });

  it('NO REVENUE FRAMING — not one word of it', () => {
    // A level describes work already done. A surface that dresses one
    // direction up as better is asking the doctor to document for the number.
    const prose = (card + review).toLowerCase();
    for (const word of [
      'revenue',
      'reimbursement',
      'higher-paying',
      'optimi', // optimise / optimize / optimization
      'maximi', // maximise / maximize
      'capture more',
      'upcode',
      'worth more',
      'billable',
    ]) {
      expect(prose, `revenue framing leaked: ${word}`).not.toContain(word);
    }
    // Currency specifically — `$` alone is every template literal in the file,
    // so match a figure: "$120", "$1,200.00".
    expect(card + review, 'a monetary figure on a clinical surface').not.toMatch(
      /\$\s?\d/,
    );
  });

  it('SETTING a level is not ATTESTING to one — the gate is not weakened', () => {
    const route = read('src/app/api/visits/[id]/em-score/override/route.ts');
    // The override arms the same pending-change record a re-score raises…
    expect(route).toContain("cause: 'doctor_override'");
    // …which the sign route enforces, unchanged.
    const sign = read('src/app/api/visits/[id]/sign/route.ts');
    expect(sign).toContain('unacknowledgedEmChange(visit.emPendingChange)');
    expect(sign).toContain('acknowledgedEmChange');
    // …and the cause is one the parser accepts, or it coerces to the
    // unknown→unknown sentinel and confronts the doctor with "unknown, up from
    // unknown" for a code they just chose.
    expect(read('src/lib/em-pending-change.ts')).toContain("'doctor_override'");
  });

  it('an override does NOT touch the note, so it cannot arm the STALE gate', () => {
    // Staleness keys on content change. An override is not a note edit; if it
    // bumped soapVersion it would gate the doctor behind their own choice.
    const route = read('src/app/api/visits/[id]/em-score/override/route.ts');
    expect(route).not.toContain('soapVersion: { increment');
    expect(route).not.toContain('emStale: true');
  });
});

describe('speaker reassignment is gone — no route with zero callers', () => {
  it('the action no longer exists', () => {
    const soap = read('src/actions/soap.ts');
    expect(soap).not.toContain('export async function reassignSpeakerAction');
    expect(soap).not.toContain('ReassignSpeakerSchema');
  });

  it('nothing imports or calls it', () => {
    for (const f of ['src/app/visits/[id]/transcript-tab.tsx']) {
      const src = read(f);
      expect(src).not.toContain('reassignSpeakerAction');
      expect(src).not.toContain('SpeakerRoleReassign');
    }
  });

  it('but the AUDIT ACTION survives — old rows still reference it', () => {
    // An audit enum that forgets its own history makes its own records
    // unreadable. The value stays; nothing writes it.
    expect(read('src/lib/audit.ts')).toContain("| 'SPEAKER_ROLE_REASSIGNED'");
  });

  it('and transcript-tab itself survives — it feeds the SOAP sources rail', () => {
    // Deleting the file would break `utterancesToSources` on every path,
    // including the signed view. Only the reassign surface came out.
    const src = read('src/app/visits/[id]/transcript-tab.tsx');
    expect(src).toContain('export function utterancesToSources');
    expect(read(READY_VIEW)).toContain('utterancesToSources');
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
