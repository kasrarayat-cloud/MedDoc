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

/**
 * The source text of ONE self-closing JSX element, from `<Tag` to its matching
 * `/>`, found by brace balance rather than by indentation.
 *
 * ⚠️ THIS REPLACED A GUARD THAT COULD PASS WHILE READING THE WRONG ELEMENT.
 * Both call sites used to slice to a literal newline-plus-N-spaces-plus-`/>`
 * marker — `'\n          />'` for `<ReviewDocumentView`, `'\n    />'` for
 * `<VisitReadyView`. That boundary is not the element's boundary, it is a
 * guess about how the file happens to be formatted, and it fails in the two
 * worst ways:
 *
 *   - **Re-indent the element by one level** (wrapping it in anything — which
 *     is exactly what putting the Rounds stage around it does) and the marker
 *     is no longer there. `indexOf` returns -1, `slice(0, -1)` drops one
 *     character instead of erroring, and the assertion runs against the whole
 *     rest of the file. It passes, and it is checking nothing.
 *   - **Or the marker matches some LATER element's close** at the new depth —
 *     measured on this file: the 12-space marker resolves 6654 characters past
 *     the real one — and the assertion then runs against a different
 *     component's props entirely. It still passes.
 *
 * A guard whose scope is set by whitespace silently stops guarding the first
 * time someone reformats. Brace balance is the property that actually holds.
 */
function jsxElement(src: string, tag: string): string {
  const start = src.indexOf(`<${tag}`);
  if (start === -1) throw new Error(`<${tag} not found`);
  let depth = 0;
  for (let i = start; i < src.length; i++) {
    const c = src[i];
    if (c === '{') depth++;
    else if (c === '}') depth--;
    else if (c === '/' && src[i + 1] === '>' && depth === 0) {
      return src.slice(start, i + 2);
    }
    // A nested child element means this tag is not self-closing; the callers
    // below all target self-closing elements, so that is a real error rather
    // than something to tolerate quietly.
    else if (c === '>' && depth === 0 && src[i - 1] !== '/') {
      throw new Error(`<${tag} is not self-closing — this helper assumes it is`);
    }
  }
  throw new Error(`<${tag} has no matching />`);
}

/** The user-visible text of a TSX source: JSX text nodes plus the attributes
 *  that render as words (placeholder, title, aria-label).
 *
 *  WHY NOT JUST GREP THE FILE. Two ways that lies in opposite directions. The
 *  prose explaining a rule trips the rule — this file's own "no next-level-up
 *  coaching" comment contains the words it bans, and the tempting fix is to
 *  weaken the list. And identifiers collide: `toLowerCase` contains "lower", so
 *  a direction check over raw source can never ban the word "lower".
 *  Comments and code are stripped; what a doctor reads is what is checked. */
function renderedText(src: string): string {
  const jsxish = stripComments(src).replace(/=>/g, ' ');
  const parts: string[] = [];
  // A JSX text node starts after a tag close `>` or an expression close `}`,
  // and ends at the next tag open `<` or expression open `{`. Both terminators
  // matter: `This visit is documented at{' '}` ends at a brace, and the
  // `, changed from` after it begins at one.
  for (const m of jsxish.matchAll(/[>}]([^<>{}]+)[<{]/g)) {
    const t = m[1].trim();
    if (!/[A-Za-z]/.test(t)) continue;
    if (/[;=:()[\]]/.test(t)) continue; // code, not copy
    if (!/\s/.test(t) && !/^[A-Z]/.test(t)) continue; // a lone identifier
    parts.push(t);
  }
  // Attribute-borne words a doctor still reads.
  for (const m of jsxish.matchAll(
    /(?:placeholder|title|aria-label|aria-description)=(?:"([^"]*)"|'([^']*)')/g,
  )) {
    parts.push(m[1] ?? m[2] ?? '');
  }
  return parts.join(' ').replace(/\s+/g, ' ').trim();
}

const stripComments = (src: string) =>
  src.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ');

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

  it('EVERY GATE SIGNAL THE VIEW READS IS ACTUALLY PASSED TO IT', () => {
    // The class of bug this catches: `emStale` was declared on VisitReadyView,
    // consumed as `useState(props.emStale ?? false)`, and never passed by
    // page.tsx. An optional prop with a falsy default is silent when it goes
    // missing — the stale gate simply never rendered on a fresh load, so a visit
    // whose level needed re-checking looked "Reviewed" until the doctor pressed
    // Sign and met the server's refusal instead.
    //
    // Optional-with-a-default is the trap, so assert the wiring, which types
    // cannot: the prop must appear in the JSX page.tsx renders.
    const jsx = jsxElement(read(VISIT_PAGE), 'VisitReadyView');
    for (const prop of [
      'emStale={',
      'emPendingChange={',
      'emNotApplicable={',
      'initialEmScore={',
      'cptCodes={',
    ]) {
      expect(jsx, `VisitReadyView is never passed ${prop}`).toContain(prop);
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
    // showing an office code on an imaging report. (The card's own null-guard is
    // asserted by rendering it in em-level-card.test.tsx; here we only pin that
    // the parent still derives the level from the not-applicable flag.)
    expect(card).toContain('if (!level) return null;');
    const ready = read(READY_VIEW);
    const decl = ready.slice(
      ready.indexOf('const emLevelFromProps'),
      ready.indexOf('const [emLevel, setEmLevel]'),
    );
    expect(decl).toContain('props.emNotApplicable');
    expect(decl).toContain('? null');
  });

  it('the row is fed the SAME projection the gate and the signature use', () => {
    // Two different numbers live on a visit: `cptCodes.em.code` is Layer-7b's
    // raw LLM suggestion as persisted, and `initialEmScore` is the rubric-engine
    // projection the page computes — the one the confirm card, the export and
    // the signed record all use. Seeding the row from the blob let it state one
    // level while the card underneath it and the file being signed said another.
    const ready = read(READY_VIEW);
    const decl = ready.slice(
      ready.indexOf('const emLevelFromProps'),
      ready.indexOf('const [emLevel, setEmLevel]'),
    );
    expect(decl).toContain('props.initialEmScore');
    expect(decl).toContain('override?.code ?? props.initialEmScore.suggestedCode');
  });

  it('A RE-CHECK THAT FINDS NO MOVEMENT MUST NOT BLANK THE ROW', () => {
    // The bug this pins, and it took the whole affordance with it: the client
    // read the level out of `pending?.to`, so the ordinary no-movement outcome —
    // and the guaranteed outcome of a FIRST re-check, where there is no baseline
    // to move from — set the level to null and unmounted the row. The level
    // text and the Adjust button, i.e. the only place a doctor can disagree
    // with the scored level, gone until a full page reload. It also fired from
    // the sign bar, which re-scores on click whenever the visit is stale.
    const ready = read(READY_VIEW);
    // Comments stripped: the paragraph above this assertion, and the one in the
    // source, both quote the broken expression in order to name it.
    const cb = stripComments(
      ready.slice(
        ready.indexOf('const rescoreEm = useCallback'),
        ready.indexOf('// V2 review (skin-only, flag-gated)'),
      ),
    );
    expect(cb).not.toContain('r.pending?.to ?? null');
    // Falls back to what is already displayed; never to null.
    expect(cb).toContain('setEmLevel((prev) => r.code ?? prev)');
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

  it('the extractor actually extracts — negative control for the two guards below', () => {
    // A word-list guard over an empty string passes every word list there is.
    // If `renderedText` ever stops matching this file's JSX, the two tests after
    // this one become decoration, and they are the enforcement for requirement
    // C. So pin that the real copy is in what they scan, and that the extractor
    // does the stripping it claims: no identifiers, no comment prose.
    const prose = renderedText(card + review);
    expect(prose).toContain('This visit is documented at');
    expect(prose).toContain('Confirm the level before signing');
    expect(prose).toContain('Documentation level');
    expect(prose).toContain('Save level');
    // Comment prose is stripped — this phrase exists ONLY in a comment.
    expect(prose).not.toContain('document for the number');
    // Identifiers are stripped — `toLowerCase` would otherwise smuggle "lower"
    // past the direction check.
    expect(prose).not.toContain('toLowerCase');
  });

  it('NO REVENUE FRAMING — not one word of it', () => {
    // A level describes work already done. A surface that dresses one
    // direction up as better is asking the doctor to document for the number.
    //
    // ONLY THE RENDERED STRINGS. This read the whole file, which meant the
    // paragraph of prose EXPLAINING the rule tripped the rule — the honest fix
    // for which is to weaken the list, so the guard was pushing the wrong way.
    // The JSX-visible text is what a doctor sees.
    const prose = renderedText(card + review).toLowerCase();
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
      'rvu',
      'collect',
      'pays',
    ]) {
      expect(prose, `revenue framing leaked: ${word}`).not.toContain(word);
    }
    // Currency of any denomination, and spelled-out money.
    expect(prose, 'a monetary figure on a clinical surface').not.toMatch(
      /[$£€]\s?\d|\bdollars?\b/,
    );
  });

  it('AND NO DIRECTION — up and down must read identically', () => {
    // The word list above cannot express this, which is the whole lesson: it
    // passed `up from` while `up from` was shipping in the very file it reads.
    // A level moving down is not a loss and a level moving up is not a win, so
    // the copy may not name a direction or argue for the level at all.
    //
    // "supports" is on the list because it argues: the visit does not "support"
    // a code, it IS documented at one.
    const prose = renderedText(card + review).toLowerCase();
    for (const framing of [
      'up from',
      'down from',
      'increased',
      'decreased',
      'higher',
      'lower',
      'supports',
      'upgrade',
      'downgrade',
    ]) {
      expect(prose, `directional framing on the level surface: ${framing}`).not.toContain(
        framing,
      );
    }
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
        // ONE named switch, not a re-typed conjunction. The original bug in this
        // area was a call site spelling the predicate's argument differently
        // (a label where an id was wanted); a single helper removes the chance.
        'applies: emAppliesToSpecialty(visit.specialty),',
      );
    }

    // THE OVERRIDE ROUTE IS A WRITER TOO, since it moves the baseline when it
    // clears a pending record. It is unreachable for an imaging visit because
    // the imaging gate 409s before the write — but the enumeration is the point:
    // a new emScoredCode writer that is not on this list is not being checked.
    const override = read('src/app/api/visits/[id]/em-score/override/route.ts');
    expect(override).toContain('emScoredCode: parsed.data.overrideToCode');
    const imagingGate = override.indexOf('emAppliesToSpecialty(visit.specialty)');
    expect(imagingGate).toBeGreaterThan(-1);
    expect(
      override.indexOf('emScoredCode:'),
      'the imaging 409 must come BEFORE any emScoredCode write',
    ).toBeGreaterThan(imagingGate);

    // The re-score never scores an imaging visit — it clears the flag instead.
    const rescore = read('src/actions/rescore-em.ts');
    const imagingBranch = rescore.slice(
      rescore.indexOf('if (!emAppliesToSpecialty(visit.specialty)) {'),
      rescore.indexOf('let scored: string;'),
    );
    expect(imagingBranch).toContain('emStale: false');
    expect(imagingBranch).not.toContain('emScoredCode');
  });

  it('AND STALENESS IS SUPPRESSED TOO — no "re-check the level" on a report with no level', () => {
    // Every note edit sets emStale regardless of specialty, and the stale gate
    // renders on `emStale && !emPendingChange` with no applicability check of its
    // own. So the moment the flag actually reached the view (it never did before
    // 2026-07-28 — the prop was not passed), an edited ultrasound report drew
    // "Documentation level needs re-checking" and the bottom bar told the doctor
    // to "Re-check the documentation level above", pointing at a card that does
    // not exist for a level the same page correctly refuses to show.
    //
    // Sign stayed enabled — the route exempts imaging — so this blocked nothing.
    // It asked for something impossible, which is its own kind of broken.
    const jsx = jsxElement(read(READY_VIEW), 'ReviewDocumentView');
    expect(jsx).toContain('emStale={props.emNotApplicable ? false : emStale}');
  });

  it('NEGATIVE CONTROL — the extractor bounds the element, and the assertion can fail', () => {
    // Two things a passing guard does not prove on its own.
    //
    // 1. That the slice STOPS at this element. The old indentation marker did
    //    not: re-indent by one level and it ran to the end of the file, or
    //    matched a later component's close. Both still passed.
    const ready = read(READY_VIEW);
    const jsx = jsxElement(ready, 'ReviewDocumentView');
    expect(jsx.startsWith('<ReviewDocumentView')).toBe(true);
    expect(jsx.endsWith('/>')).toBe(true);
    // It must be a fraction of the file, not most of it.
    expect(jsx.length).toBeLessThan(ready.length / 2);
    // And it must not have swallowed the next sibling element.
    expect(jsx).not.toContain('<SignedDocumentView');

    // 2. That the assertion is capable of failing. Strip the prop from a COPY
    //    and the same check must go red — otherwise it is satisfied by
    //    something other than the thing it names.
    const withoutProp = jsx.replace(
      'emStale={props.emNotApplicable ? false : emStale}',
      'emStale={emStale}',
    );
    expect(withoutProp).not.toContain(
      'emStale={props.emNotApplicable ? false : emStale}',
    );

    // 3. And it survives re-indentation, which the indentation marker did not.
    const reindented = ready.replace(
      /^(\s*)(<ReviewDocumentView)/m,
      '$1  $2',
    );
    expect(jsxElement(reindented, 'ReviewDocumentView')).toContain(
      'emStale={props.emNotApplicable ? false : emStale}',
    );
  });

  it('NOBODY RE-TYPES THE CONJUNCTION — emAppliesToSpecialty is the only copy', () => {
    // The failure this prevents: seven call sites each spelling
    // `!(ultrasoundSpecialtyEnabled() && isImagingReportSpecialty(x))` by hand.
    // One of them spelled its argument differently — a display LABEL where the
    // predicate wanted an id — and the comparison was silently, permanently
    // false, so every ultrasound visit computed and stored an office E/M level.
    // Seven copies is seven chances to make that mistake again.
    const { execSync } = require('node:child_process') as typeof import('node:child_process');
    const hits = execSync(
      'grep -rln "ultrasoundSpecialtyEnabled() && isImagingReportSpecialty" src ../../packages/shared/src || true',
      { encoding: 'utf8' },
    )
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
      // The definition itself is allowed to contain it — it IS the copy.
      .filter((f) => !f.endsWith('specialties.ts'))
      // Tests may quote it while explaining the history.
      .filter((f) => !/__tests__|\.test\./.test(f));
    expect(hits, `open-coded copies of the E/M applicability switch: ${hits.join(', ')}`).toEqual([]);
  });

  it('these guards all read the raw column through the ONE switch', () => {
    // The page needed a new prop because it had already turned the column into
    // a label. Everywhere else reads `visit.specialty` straight off Prisma, so
    // the predicate gets an id and the same bug cannot be there.
    for (const f of [
      'src/actions/soap.ts',
      'src/actions/rescore-em.ts',
      'src/app/api/visits/[id]/sign/route.ts',
    ]) {
      expect(read(f)).toContain('emAppliesToSpecialty(visit.specialty)');
    }
  });
});
