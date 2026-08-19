// ============================================================================
// F12-d GATE — A RETIRED TEMPLATE DOES NOT OVERRULE THE DOCUMENT BEING SIGNED
// (refining the PROVISIONAL ruling #126 — this decision is F12-d, on branch
//  feat/f12d-note-shape-precedence. It is NOT cited by a RULINGS number here:
//  per the number-claim protocol a number is claimed by LANDING, and an
//  unlanded decision referred to by number strands every citation if a
//  collision forces a renumber.)
// ----------------------------------------------------------------------------
// F12-a/F12-c suppress an office E/M level on operative notes at the EXPORT,
// STORE and COMPUTE layers. All three ask ONE question — `emAppliesToVisit` —
// so the reach of that predicate is the reach of the whole feature.
//
// F12-d makes exactly ONE change: an operative-shaped TEMPLATE no longer
// suppresses a note body that reads AFFIRMATIVELY as an office visit.
//
// ⚠️ IT ORIGINALLY MADE TWO, AND THE ADVERSARIAL PASS DELETED THE OTHER ONE.
// The first draft also ungated the note-body arm from `templateIsSilent` into
// an OR. Measured, that changes ZERO production verdicts — and a refuter then
// showed it INTRODUCES a defect: production template `cmpz63jsw000501tayag818lq`
// is ACTIVE and spells its sections `CHIEF COMPLAINT · INTERVAL HISTORY · EXAM ·
// IMPRESSION & PLAN · PATIENT INSTRUCTIONS`, so an ordinary office visit with an
// in-room excision scores 0 on the exact-match office counterweight while the
// excision supplies two operative markers -> `true -> false`, a billable level
// silently stripped from the "derm office w/ excision" family that #126(b)'s
// counterweight exists to protect. **The OR waits for F12-f.**
//
// THE MEASUREMENT THAT CHOSE THE SHAPE, run over all 48 production visits
// through the REAL module in production's flag universe:
//
//     scheme                                       vs deployed
//     B  the plain OR (the filing's candidate 3)   +0 suppressed,  0 applied
//     D  widen `templateIsSilent` (candidate 1)    +0 suppressed,  0 applied
//     C  body-first, any non-operative body wins   +0 suppressed,  1 applied
//     SHIPPED (measured through emAppliesToVisit)  +0 suppressed,  1 applied
//
// Both candidates F12-d was FILED with move nothing.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import {
  emAppliesToVisit,
  isProcedureNoteShape,
  isProcedureNoteShapeFromText,
  noteReadsAsOfficeVisitFromText,
  officeConceptCountFromText,
  officeSkeletonCountFromText,
  procedureNoteMarkerCount,
  procedureNoteMarkerCountFromText,
  templateIsSilent,
  OFFICE_ESCAPE_FLOOR,
} from '../note-shape';

const sec = (labels: string[]) => labels.map((label, i) => ({ key: `k${i}`, label, order: i }));
const body = (labels: string[]) => labels.map((l) => `## ${l}\n…text…`).join('\n\n');

// ── the real production shapes, measured 2026-08-18 ─────────────────────────

/** The template bound to the row this item exists for.
 *  ⚠️ `cmsu1jsls000901ns6y1aeoy6`, "Operative Note", **status = INACTIVE**.
 *  The visit's FK is frozen to it and every read path joins WITHOUT a status
 *  filter, so a RETIRED template still classifies signed visits. That doctor's
 *  one ACTIVE template is an imaging one. */
const RETIRED_OPERATIVE_TEMPLATE = sec([
  'PROCEDURE',
  'PREOPERATIVE DIAGNOSIS',
  'POSTOPERATIVE FINDINGS',
  'CONSENT',
  'DESCRIPTION OF PROCEDURE',
  'RECOMMENDATIONS',
]);

/** ⚠️ THE ROW THIS ITEM EXISTS FOR — `cmsu1mhrp000h01nsxpvxxshk`.
 *  SIGNED · `gastroenterology` · `cptCodes.em.code` 99215 · FROZEN
 *  `signedCode` 99214. 4 of 4 SOAP concepts, 0 operative markers. */
const SIGNED_OFFICE_BODY = body(['CHIEF COMPLAINT', 'SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT', 'PLAN']);

/** Its sibling on the SAME template — a genuine colonoscopy. 3 markers. */
const OPERATIVE_BODY = body([
  'PROCEDURE',
  'PREOPERATIVE DIAGNOSIS',
  'POSTOPERATIVE FINDINGS',
  'CONSENT',
  'DESCRIPTION OF PROCEDURE',
  'RECOMMENDATIONS',
]);

/** The same office visit after an ordinary edit merges two headings. */
const SIGNED_OFFICE_BODY_COMBINED = body(['CHIEF COMPLAINT', 'SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT & PLAN']);

/** An office note that avoids the SOAP words entirely. The KNOWN RESIDUAL. */
const NON_SOAP_OFFICE_BODY = body(['CHIEF COMPLAINT', 'EXAM', 'IMPRESSION & PLAN']);

describe('F12-d — NON-VACUITY: the fixtures are the shapes they claim to be', () => {
  // ⚠️ Every verdict below is meaningless if the inputs do not carry the
  // properties the reasoning attributes to them. A fixture that was merely
  // office-SHAPED already stood in for a production row it did not resemble
  // once inside this very feature — that is what F12-d found in F12-a's suite.
  it('the office bodies sit where the reasoning says they do', () => {
    expect(officeConceptCountFromText(SIGNED_OFFICE_BODY)).toBe(OFFICE_ESCAPE_FLOOR);
    expect(procedureNoteMarkerCountFromText(SIGNED_OFFICE_BODY)).toBe(0);
    // The combined-heading edit: FEWER literal SOAP headings, SAME concepts.
    expect(officeSkeletonCountFromText(SIGNED_OFFICE_BODY_COMBINED)).toBe(2);
    expect(officeConceptCountFromText(SIGNED_OFFICE_BODY_COMBINED)).toBe(OFFICE_ESCAPE_FLOOR);
    // The residual reaches neither count.
    expect(officeConceptCountFromText(NON_SOAP_OFFICE_BODY)).toBeLessThan(OFFICE_ESCAPE_FLOOR);
  });

  it('the operative fixtures carry a real MARGIN, not a bare pass', () => {
    // ⚠️ THE TEMPLATE'S MARGIN IS ASSERTED TOO. A refuter deleted one marker
    // from this template, dropping it to exactly the floor of 2 with zero
    // margin, and all arms stayed green — the docstring's "3 markers" was
    // unpinned. The COUNT is evidence; the VERDICT is the function.
    expect(procedureNoteMarkerCount(RETIRED_OPERATIVE_TEMPLATE)).toBe(3);
    expect(procedureNoteMarkerCountFromText(OPERATIVE_BODY)).toBe(3);
    expect(isProcedureNoteShape(RETIRED_OPERATIVE_TEMPLATE)).toBe(true);
    expect(isProcedureNoteShapeFromText(OPERATIVE_BODY)).toBe(true);
    expect(isProcedureNoteShapeFromText(SIGNED_OFFICE_BODY)).toBe(false);
  });
});

describe('F12-d — the escape: an affirmatively office-shaped record beats a retired template', () => {
  it('🔴 THE LIVE DEFECT: a SIGNED office visit keeps its level under a colonoscopy template', () => {
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: RETIRED_OPERATIVE_TEMPLATE,
        noteText: SIGNED_OFFICE_BODY,
      }),
    ).toBe(true);
  });

  it('its SIBLING on the same template is still suppressed — the escape is not a hole', () => {
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: RETIRED_OPERATIVE_TEMPLATE,
        noteText: OPERATIVE_BODY,
      }),
    ).toBe(false);
  });

  it('🔴 A BODY WITH THE FULL SOAP SKELETON **AND** OPERATIVE MARKERS DOES NOT ESCAPE', () => {
    // Found by a refuter. `noteReadsAsOfficeVisitFromText` is a bare concept
    // count with no marker check, and `isProcedureNoteShapeFromText` returns
    // FALSE for such a body because the office counterweight is tested first —
    // so nothing else objected either. Verified: it flipped `false -> true`,
    // which would freeze an office E/M onto a SIGNED operative record at
    // `sign/route.ts:538`, the exact state that conjunction exists to prevent.
    const opBodyWithFullSoap = body([
      'SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT', 'PLAN',
      'PROCEDURE', 'PREOPERATIVE DIAGNOSIS', 'POSTOPERATIVE FINDINGS', 'DESCRIPTION OF PROCEDURE',
    ]);
    expect(officeConceptCountFromText(opBodyWithFullSoap)).toBe(OFFICE_ESCAPE_FLOOR);
    expect(procedureNoteMarkerCountFromText(opBodyWithFullSoap)).toBe(3);
    expect(noteReadsAsOfficeVisitFromText(opBodyWithFullSoap)).toBe(true);
    expect(
      emAppliesToVisit({
        specialtyId: 'bariatric-surgery',
        templateSections: RETIRED_OPERATIVE_TEMPLATE,
        noteText: opBodyWithFullSoap,
      }),
      'a body carrying operative markers must never reach the escape',
    ).toBe(false);
  });

  it('🔴 THE VERDICT IS STABLE UNDER AN ORDINARY HEADING EDIT — no mid-visit flip', () => {
    // Found by a refuter. With a bare `countOfficeSkeleton`, merging
    // `## Assessment` and `## Plan` into `## Assessment & Plan` drops the count
    // 4 -> 2 and FLIPS the verdict, stranding `emPendingChange` and (under
    // Rounds) leaving a visit with NO sign control and a banner whose text is
    // false, with no way to clear it. The concepts are what the doctor
    // documented; the number of headings used to spell them is not a clinical
    // fact.
    for (const noteText of [SIGNED_OFFICE_BODY, SIGNED_OFFICE_BODY_COMBINED]) {
      expect(
        emAppliesToVisit({
          specialtyId: 'gastroenterology',
          templateSections: RETIRED_OPERATIVE_TEMPLATE,
          noteText,
        }),
        'both spellings of the same note must agree',
      ).toBe(true);
    }
    // …and every combined form the module names, one at a time.
    for (const combined of [
      'ASSESSMENT AND PLAN', 'ASSESSMENT/PLAN',
      'IMPRESSION & PLAN', 'IMPRESSION AND PLAN', 'IMPRESSION/PLAN',
    ]) {
      const b = body(['SUBJECTIVE', 'OBJECTIVE', combined]);
      expect(officeConceptCountFromText(b), `${combined} must satisfy A and P`).toBe(OFFICE_ESCAPE_FLOOR);
    }
  });

  it('⚠️ A SILENT BODY DOES NOT ESCAPE — the exception is AFFIRMATIVE, not a default', () => {
    for (const noteText of ['', null, undefined, '   ', 'prose with no headings at all']) {
      expect(
        emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections: RETIRED_OPERATIVE_TEMPLATE, noteText }),
        `noteText=${JSON.stringify(noteText)} must NOT escape suppression`,
      ).toBe(false);
    }
  });

  it('the escape needs ALL FOUR concepts — three is not enough', () => {
    // #126(b) measured this against a real SIGNED operative row carrying
    // SUBJECTIVE · OBJECTIVE · ASSESSMENT beside five operative markers.
    const threeOfFour = body(['SUBJECTIVE', 'OBJECTIVE', 'ASSESSMENT']);
    expect(officeConceptCountFromText(threeOfFour)).toBe(3);
    expect(noteReadsAsOfficeVisitFromText(threeOfFour)).toBe(false);
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: RETIRED_OPERATIVE_TEMPLATE,
        noteText: threeOfFour,
      }),
    ).toBe(false);
  });

  it('⚠️ KNOWN RESIDUAL — F12-f — a non-SOAP-worded office note is STILL over-suppressed', () => {
    // The escape needs the four SOAP CONCEPTS. `CHIEF COMPLAINT · EXAM ·
    // IMPRESSION & PLAN` supplies only two, so an office note in that
    // vocabulary — the `cmpz63jsw` template's own — does not reach it.
    // NOT fixed here: the cure widens the SHARED counterweight, which also
    // decides operative-ness. Filed as F12-f.
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: RETIRED_OPERATIVE_TEMPLATE,
        noteText: NON_SOAP_OFFICE_BODY,
      }),
      'F12-f is OPEN — if this goes true, close F12-f in RELAY rather than deleting this arm',
    ).toBe(false);
  });
});

describe('F12-d — everything else is UNCHANGED', () => {
  it('the note-body fallback still fires ONLY into silence — the OR was rejected', () => {
    const combinedOfficeTemplate = sec([
      'CHIEF COMPLAINT', 'INTERVAL HISTORY', 'EXAM', 'IMPRESSION & PLAN', 'PATIENT INSTRUCTIONS',
    ]);
    const officeWithExcision = body([
      'CHIEF COMPLAINT', 'INTERVAL HISTORY', 'EXAM',
      'DESCRIPTION OF PROCEDURE', 'SPECIMENS REMOVED', 'IMPRESSION & PLAN',
    ]);
    // Non-vacuity: this really is the shape that would have been stripped.
    expect(templateIsSilent(combinedOfficeTemplate)).toBe(false);
    expect(isProcedureNoteShape(combinedOfficeTemplate)).toBe(false);
    expect(procedureNoteMarkerCountFromText(officeWithExcision)).toBe(2);
    expect(isProcedureNoteShapeFromText(officeWithExcision)).toBe(true);
    expect(
      emAppliesToVisit({
        specialtyId: 'primary-care',
        templateSections: combinedOfficeTemplate,
        noteText: officeWithExcision,
      }),
      'an ordinary office visit with an in-room excision keeps its billable level',
    ).toBe(true);
  });

  it('an untemplated operative note is still suppressed — #126(a) is not weakened', () => {
    for (const templateSections of [null, undefined, [], 'nonsense']) {
      expect(
        emAppliesToVisit({ specialtyId: 'gastroenterology', templateSections, noteText: OPERATIVE_BODY }),
        `templateSections=${JSON.stringify(templateSections)} must still suppress`,
      ).toBe(false);
    }
  });

  it('the specialty axis still short-circuits before either shape source', () => {
    const prev = process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
    process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = 'true';
    try {
      expect(
        emAppliesToVisit({ specialtyId: 'ultrasound', templateSections: null, noteText: SIGNED_OFFICE_BODY }),
        'the flag did not take effect — every arm in this block would pass for the wrong reason',
      ).toBe(false);
      expect(
        emAppliesToVisit({
          specialtyId: 'ultrasound',
          templateSections: RETIRED_OPERATIVE_TEMPLATE,
          noteText: SIGNED_OFFICE_BODY,
        }),
        'the escape must NOT re-admit an E/M onto an imaging report',
      ).toBe(false);
    } finally {
      if (prev === undefined) delete process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY;
      else process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY = prev;
    }
  });
});

describe('F12-d — THE SEAM: what each caller PASSES, not merely that it passes something', () => {
  // ⚠️ THIS BLOCK EXISTS BECAUSE A REFUTER BROKE THE FIRST VERSION OF IT.
  // That version asserted a `noteText:` key was present and not a literal `''`.
  // A caller passing `visit.noteTemplate?.sections` — the line directly above,
  // i.e. the copy-paste a tired human actually makes — left all arms GREEN,
  // because `normalizedNoteHeadings` returns `[]` for any non-string and the
  // parameter is typed `unknown`, so `tsc` cannot object either. The gate was
  // strict about SYNTAX and blind about SEMANTICS in the same assertion.
  //
  // So the value is now pinned to an ALLOWLIST of expressions, per call site.

  /** The note-body expression each caller is entitled to pass. Anything else
   *  is a finding, including a same-typed neighbour like `soapDraft`. */
  const EXPECTED: Record<string, readonly string[]> = {
    'app/api/visits/[id]/sign/route.ts': ['visit.soapFinal'],
    'app/api/visits/[id]/em-score/override/route.ts': ["visit.soapFinal ?? visit.soapDraft ?? ''"],
    'app/api/visits/[id]/em-score/apply-additions/route.ts': ["visit.soapFinal ?? visit.soapDraft ?? ''"],
    'app/visits/[id]/page.tsx': ['soapText'],
    // `rawSoap` = `signedSoap ?? soapFinal` when SIGNED, else `soapFinal` —
    // deliberately the STORED record, before the export-only cleanups, so the
    // verdict cannot depend on which surface asked.
    'lib/visit-export-server.ts': ['rawSoap'],
    'lib/sign-gates.ts': ['input.noteText'],
    'actions/soap.ts': ['visit.soapFinal'],
    'actions/rescore-em.ts': ['visit.soapFinal'],
    'worker.ts': ['soapFinalForFanout'],
    // F12-g's READ-ONLY production watcher. Not a runtime caller — nothing in
    // the app imports it; it is driven by
    // `scripts/check-em-note-shape-artifacts.sh` against the production
    // database, and it exists so a stale office E/M level stops being
    // invisible.
    //
    // ⚠️ `row.noteHeadingLines` IS NOT A SAME-TYPED NEIGHBOUR SLIPPING THROUGH,
    // AND THE DISTINCTION IS THE POINT OF THIS ROW. The projection carries only
    // the note's markdown HEADING LINES, filtered in SQL by a strict PREFIX of
    // `NOTE_SECTION_HEADING_RE` — so no clinical prose leaves the database, and
    // the heading list `normalizedNoteHeadings` derives is IDENTICAL to the one
    // it would derive from the whole note. `assertNoBodyText` asserts the other
    // direction (that the filter did not over-select) on every run.
    //
    // The SOURCE is still this table's rule: the SQL reads
    // `coalesce("signedSoap", "soapFinal")`, i.e. the stored record, signed
    // text first.
    'lib/em-artifact-scan.ts': ['row.noteHeadingLines'],
  };

  /** ⚠️ LINE COMMENTS ARE STRIPPED **BEFORE** BLOCK COMMENTS, AND THE ORDER IS
   *  THE FIX. A refuter showed the reverse order corrupts a file: an ordinary
   *  `//` comment that merely MENTIONS a block-comment opener starts a phantom
   *  block that runs to the next close, swallowing ~60 lines including the
   *  call, and reddened two arms on a comment-only edit. */
  const stripComments = (src: string) =>
    src.replace(/^[ \t]*\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '');

  /** Matches the call however it is spelled — `({`, `(\n{`, or `(args)`. The
   *  first version required `({` adjacently, so a pure reformat produced an
   *  unwatched caller. */
  const CALL_RE = /emAppliesToVisit\s*\(/;

  const root = join(__dirname, '../..');

  it('the caller census is the WHOLE census — reconciled against the tree, not hand-kept', () => {
    const found = new Set<string>();
    const walk = (dir: string) => {
      for (const e of readdirSync(dir, { withFileTypes: true })) {
        const p = join(dir, e.name);
        if (e.isDirectory()) {
          if (e.name === '__tests__' || e.name === 'node_modules') continue;
          walk(p);
        } else if (/\.(tsx?|jsx?|mjs|cjs)$/.test(e.name) && e.name !== 'note-shape.ts') {
          if (CALL_RE.test(stripComments(readFileSync(p, 'utf8')))) found.add(p.slice(root.length + 1));
        }
      }
    };
    walk(root);
    expect(found.size, 'the traversal found no callers at all — the instrument is broken').toBeGreaterThan(0);
    expect([...found].sort()).toEqual(Object.keys(EXPECTED).sort());
  });

  it('every caller passes the EXACT note-body expression it is entitled to', () => {
    for (const [rel, allowed] of Object.entries(EXPECTED)) {
      const src = stripComments(readFileSync(join(root, rel), 'utf8'));
      const at = src.search(CALL_RE);
      expect(at, `${rel} must call emAppliesToVisit`).toBeGreaterThanOrEqual(0);
      const window = src.slice(at, at + 800);
      const m = /noteText\s*:\s*([^,\n}]+)/.exec(window);
      expect(m, `${rel} must pass an explicit noteText: (object shorthand is not accepted here)`).not.toBeNull();
      const actual = m![1].trim().replace(/,$/, '');
      expect(
        allowed,
        `${rel} passes noteText: ${actual} — not an approved note-body expression. ` +
          `A same-typed neighbour (soapDraft, signedSoap, transcript) or a template ` +
          `object typechecks and silently disables the whole note-shape axis.`,
      ).toContain(actual);
    }
  });
});
