// ============================================================================
// GATE — F12-c: THE COMPUTE LAYER OF THE E/M INVARIANT (ruling #123, #127)
// ----------------------------------------------------------------------------
// `packages/shared/src/specialties.ts:139-143` states the invariant is enforced
// at THREE layers — COMPUTE · STORE · EXPORT. F12-a closed STORE and EXPORT for
// the NOTE-SHAPE axis and left COMPUTE keyed on specialty alone, so an
// operative note still had an office E/M level computed and PERSISTED into
// `transcribe_visits.cptCodes.em`. This gate watches the third layer.
//
// ⚠️ WHAT THIS GATE IS FOR, STATED AS THE THING THAT WOULD MAKE IT FAIL:
//
//   1. the E/M half survives on a note where E/M does not apply
//   2. the PROCEDURE half is lost on one where it does not     ← the #109 trap
//   3. the suppression is filed as an allowlist REJECTION      ← a wrong reason
//   4. a deliberately-absent E/M is reported to the doctor as a FAILED LAYER
//
// ⚠️ (4) IS THE HALF A TIRED LANDING LEAVES OUT, AND IT IS WHY THIS FILE
// COVERS TWO MODULES. `07b-cpt-coding.ts` and `automation-incomplete.ts` are
// separate files with separate tests, and the first edit the change invites is
// the L7b one alone — at which point every operative note gets a permanent
// "Auto-coding incomplete — cpt-coding: no E&M code emitted. Click Retry to
// reprocess" banner that Retry can never clear. Splitting these arms across two
// files by module would let that partial landing stay green in both.
// That is AGENTS.md's "MUTATE TO THE PARTIAL FIX, NOT THE COMPLETE INVERSE".
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelComplete: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
  // Typed to take the code, because two arms below drive it per-code to prove
  // the allowlist floor still discriminates. `vi.fn(() => true)` compiles here
  // and then refuses `mockImplementation((code: string) => …)`.
  isValidCpt: vi.fn((_code: string) => true),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    modelClient: { complete: mocks.modelComplete },
    isValidCpt: mocks.isValidCpt,
  };
});

vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { update: mocks.prismaUpdate } },
}));

vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import { runLayer7bCptCoding } from '../07b-cpt-coding';
import {
  detectIncompleteAutomation,
  type AutomationConfidenceScores,
} from '@/worker/automation-incomplete';
import {
  emAppliesToVisit,
  PROCEDURE_NOTE_SECTION_MARKERS,
} from '@/lib/note-shape';
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from '@/worker/note-templates/system-default-template';

/** What the coding model returns for a colonoscopy: a real procedure code, a
 *  modifier, AND an E/M level it had no business proposing. The E/M is present
 *  on purpose — a fixture where the model returned nothing would let a broken
 *  suppression pass. */
const MODEL_RETURNED_BOTH = {
  em: {
    code: '99214',
    description: 'Established patient, moderate complexity',
    reasoning: { problems: [], data: 'reviewed prior colonoscopy', risk: 'moderate' as const },
    evidence_quote: 'polyp removed',
  },
  procedures: [
    {
      code: '45385',
      description: 'Colonoscopy with lesion removal by snare technique',
      evidence_quote: 'snare polypectomy performed',
      confidenceLevel: 'high' as const,
      provenance: 'coach_suggested' as const,
    },
  ],
  modifiers: [{ code: '33', rationale: 'preventive service' }],
};

const OPERATIVE_NOTE = [
  '## Preoperative Diagnosis',
  'Screening colonoscopy.',
  '## Description of Procedure',
  'The scope was advanced to the cecum.',
  '## Postoperative Findings',
  'One sessile polyp removed by snare.',
].join('\n');

const OFFICE_NOTE = [
  '## Subjective',
  'Routine follow-up for hypertension.',
  '## Objective',
  'BP 148/92.',
  '## Assessment',
  'Hypertension not at goal.',
  '## Plan',
  'Increase lisinopril.',
].join('\n');

const baseInput = {
  visitId: 'vis-f12c',
  practiceId: 'p1',
  userId: 'u1',
  specialty: 'gastroenterology',
  soapFinal: OPERATIVE_NOTE,
  entitiesJson: '{}',
};

/** The `cptCodes` payload L7b actually wrote, read back off the mock rather
 *  than off the return value. THE COLUMN IS WHAT A LATER READER SEES — a
 *  function that returns a suppressed blob and persists an unsuppressed one
 *  would satisfy a return-value assertion and be the whole bug. */
function writtenCptCodes(): {
  em: unknown;
  procedures: Array<{ code: string }>;
  modifiers: Array<{ code: string }>;
} {
  expect(mocks.prismaUpdate, 'L7b must have written exactly once').toHaveBeenCalledTimes(1);
  return mocks.prismaUpdate.mock.calls[0][0].data.cptCodes;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.isValidCpt.mockReturnValue(true);
  mocks.prismaUpdate.mockResolvedValue({});
  mocks.modelComplete.mockResolvedValue(MODEL_RETURNED_BOTH);
});

// ---------------------------------------------------------------------------
describe('F12-c — the E/M half is dropped where E/M does not apply', () => {
  it('an OPERATIVE note persists NO em, even though the model proposed one', async () => {
    const result = await runLayer7bCptCoding({ ...baseInput, emApplies: false });

    expect(result.em, 'the returned blob must carry no E/M').toBeNull();
    expect(writtenCptCodes().em, 'and neither must the COLUMN').toBeNull();
  });

  it('NON-VACUITY — the same fixture WITH emApplies keeps the level', async () => {
    // Without this arm every assertion above is satisfiable by a layer that
    // never emits an E/M at all, and the gate would be measuring nothing.
    const result = await runLayer7bCptCoding({ ...baseInput, emApplies: true });

    expect(result.em?.code).toBe('99214');
    expect((writtenCptCodes().em as { code: string }).code).toBe('99214');
  });

  it('THE MARKER IS WRITTEN — the record says WHY the field is absent', async () => {
    // `em: null` alone is ambiguous between "the model produced nothing" and
    // "nobody asked". Every reader that needs to tell those apart was
    // recomputing the verdict at read time, against a note the doctor may have
    // edited since. The stored marker is what makes that unnecessary.
    await runLayer7bCptCoding({ ...baseInput, emApplies: false });
    expect((writtenCptCodes() as { emSuppressed?: boolean }).emSuppressed).toBe(true);
  });

  it('and it is ABSENT on a visit where E/M applies — not written as false', async () => {
    // A marker present-and-false and a marker absent are two states; only one
    // is produced, so a reader cannot be caught out by the other.
    await runLayer7bCptCoding({ ...baseInput, emApplies: true });
    expect(writtenCptCodes()).not.toHaveProperty('emSuppressed');
  });

  it('THE #109 ARM — the PROCEDURE code and the MODIFIERS survive suppression', async () => {
    // A colonoscopy's procedure code is the one code that encounter genuinely
    // bills. Gating the whole layer on note shape would delete it, which is the
    // recorded failure of scoping a deletion by what the ruling CALLS the thing
    // rather than by what the thing DOES.
    await runLayer7bCptCoding({ ...baseInput, emApplies: false });
    const written = writtenCptCodes();

    expect(written.procedures.map((p) => p.code)).toEqual(['45385']);
    expect(written.modifiers.map((m) => m.code)).toEqual(['33']);
  });

  it('BYTE-PARITY ON THE UNTOUCHED HALVES — suppressed and unsuppressed agree', async () => {
    // Stronger than "procedures are still there": asserts the change is
    // confined to ONE field. Anything else that moves fails here by name.
    await runLayer7bCptCoding({ ...baseInput, emApplies: false });
    const suppressed = writtenCptCodes();
    vi.clearAllMocks();
    mocks.isValidCpt.mockReturnValue(true);
    mocks.prismaUpdate.mockResolvedValue({});
    mocks.modelComplete.mockResolvedValue(MODEL_RETURNED_BOTH);
    await runLayer7bCptCoding({ ...baseInput, emApplies: true });
    const kept = writtenCptCodes();

    expect(suppressed.procedures).toEqual(kept.procedures);
    expect(suppressed.modifiers).toEqual(kept.modifiers);
    // The ONLY permitted structural difference is the suppression marker. Any
    // other key appearing or vanishing is a change this diff does not claim.
    expect(Object.keys(kept).sort()).toEqual(['em', 'modifiers', 'procedures']);
    expect(Object.keys(suppressed).sort()).toEqual([
      'em',
      'emSuppressed',
      'modifiers',
      'procedures',
    ]);
  });

  it('A SUPPRESSED E/M IS NOT AN ALLOWLIST REJECTION — no audit row is filed', async () => {
    // The reason matters. `CODING_COACH_REJECTED_INVALID_CPT` says the code was
    // not billable; here it was not APPLICABLE. A wrong reason in an audit row
    // outlives the session that wrote it.
    mocks.isValidCpt.mockImplementation((code: string) => code !== '99214');

    await runLayer7bCptCoding({ ...baseInput, emApplies: false });

    const rejections = mocks.logAudit.mock.calls.filter(
      (c) => c[0]?.action === 'CODING_COACH_REJECTED_INVALID_CPT',
    );
    expect(rejections, 'suppression must not be filed as a rejection').toHaveLength(0);
  });

  it('and the allowlist floor STILL rejects an invalid E/M where E/M applies', async () => {
    // The negative control for the arm above. Moving the suppression ahead of
    // the allowlist check must not weaken the floor for office visits.
    mocks.isValidCpt.mockImplementation((code: string) => code !== '99214');

    const result = await runLayer7bCptCoding({ ...baseInput, emApplies: true });

    expect(result.em, 'an invalid E/M is still dropped').toBeNull();
    const rejections = mocks.logAudit.mock.calls.filter(
      (c) => c[0]?.action === 'CODING_COACH_REJECTED_INVALID_CPT',
    );
    expect(rejections, 'and it IS still audited as a rejection').toHaveLength(1);
    expect(rejections[0][0].metadata.rejectedCodes).toContain('99214');
  });
});

// ---------------------------------------------------------------------------
describe('F12-c — a deliberately absent E/M is not a failed layer', () => {
  const okScores: AutomationConfidenceScores = {
    icd_coding: { status: 'ok' },
    cpt_coding: { status: 'ok' },
    rx_drafting: { status: 'ok' },
  };
  const healthyIcd = { codes: [{ code: 'Z12.11' }] };
  /** Exactly what L7b now writes for an operative note. */
  const suppressedCpt = { em: null, procedures: [{ code: '45385' }], emSuppressed: true };

  it('THE PARTIAL-LANDING ARM — suppressed em + status:ok does NOT flip review', () => {
    // ⚠️ THIS IS THE ARM THAT GOES RED IF ONLY THE L7b HALF LANDS. Without the
    // `emApplies` leg in automation-incomplete.ts, `isCptEmpty` reads the
    // deliberate null as "the layer returned nothing" and the doctor gets
    // "Auto-coding incomplete … Click Retry" on every colonoscopy, forever.
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: healthyIcd,
      cptCodes: suppressedCpt,
    });

    expect(r.needsReview).toBe(false);
    expect(r.failedLayers).toEqual([]);
    expect(r.reviewReason).toBeNull();
  });

  it('⚠️ THE RESUME PATH — the verdict FLIPS after the blob is written, and the banner must NOT return', () => {
    // THE DEFECT TWO INDEPENDENT REFUTERS CONVERGED ON, and it is the failure
    // this whole mechanism exists to prevent, reappearing through a door the
    // first draft did not cover:
    //
    //   1. operative note -> L7b writes { em: null, procedures: [...] }
    //   2. the doctor EDITS the note; its shape flips to office
    //   3. the doctor hits Retry -> L7b is SKIPPED (`hasContent` is true for
    //      ANY object) and records status:'ok'
    //   4. a reader that RECOMPUTES applicability now says "E/M applies",
    //      reads em:null, and reports "no E&M code emitted (status:ok)"
    //   5. "Auto-coding incomplete ... Click Retry" that Retry can NEVER clear,
    //      because L7b is skipped every time, until the 5-retry budget is spent
    //      and the route answers 429 "contact support".
    //
    // This arm is step 4 with the fix in place: the helper is given NO verdict
    // at all, so there is nothing to recompute. It reads the marker L7b stored
    // in the same run that produced the blob.
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: healthyIcd,
      cptCodes: suppressedCpt,
    });

    expect(r.needsReview, 'the unclearable banner must not return').toBe(false);
    expect(r.reviewReason).toBeNull();
  });

  it('NON-VACUITY — the SAME payload with emApplies DOES flip review', () => {
    // Proves the leg discriminates rather than having been switched off. If
    // this passed too, the fix would have deleted the empty-codes guard for
    // every office visit and nothing would say so.
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: healthyIcd,
      // the SAME payload without the marker — i.e. an office visit whose
      // model genuinely returned no E/M. This must still trip.
      cptCodes: { em: null, procedures: [{ code: '45385' }] },
    });

    expect(r.needsReview).toBe(true);
    expect(r.failedLayers).toContain('cpt_coding');
    expect(r.causeByLayer.cpt_coding).toBe('empty');
  });

  it('and an office visit that DID get its level is still clean', () => {
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: healthyIcd,
      cptCodes: { em: { code: '99214' }, procedures: [] },
    });

    expect(r.needsReview).toBe(false);
  });

  it('⚠️ A WHOLLY EMPTY LAYER ON AN OPERATIVE NOTE STILL TRIPS — the true positive the first draft LOST', () => {
    // Found by the mandatory adversarial pass. Draft 1 skipped the empty leg
    // entirely when `emApplies` was false, which removed the false banner AND
    // the only doctor-facing signal for a real failure on the same notes: the
    // model returning nothing, or the allowlist rejecting every procedure code.
    // The doctor got an empty Codes tab, no banner, no retry CTA.
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: healthyIcd,
      cptCodes: { em: null, procedures: [], emSuppressed: true },
    });

    expect(r.needsReview).toBe(true);
    expect(r.failedLayers).toContain('cpt_coding');
    expect(r.causeByLayer.cpt_coding).toBe('empty');
  });

  it('and it says the RIGHT thing — "no E&M code emitted" is false about an operative note', () => {
    // A wrong field in a doctor-facing banner is worse than an absent one.
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: healthyIcd,
      cptCodes: { em: null, procedures: [], emSuppressed: true },
    });

    expect(r.reviewReason).not.toContain('E&M');
    expect(r.reasonsByLayer.cpt_coding).toBe('no codes emitted at all (status:ok)');
  });

  it('THE DB-BLIP DEFENCE SURVIVES — a null column on an operative note still trips', () => {
    // `worker.ts`'s post-fan-out re-read is `.catch(() => null)`, and the
    // comment above it states the fresh-run blip lands in review "via the
    // cpt-null leg only". Gating that leg off would have made that sentence
    // false in the same commit that edited the code it describes.
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: healthyIcd,
      cptCodes: null,
    });

    expect(r.needsReview).toBe(true);
    expect(r.failedLayers).toContain('cpt_coding');
  });

  it('a GENUINELY failed cpt layer still trips even where E/M does not apply', () => {
    // `emApplies:false` narrows the EMPTY leg only. A layer that actually threw
    // must still reach the doctor — narrowing a false positive must not become
    // a blanket exemption for operative notes.
    const r = detectIncompleteAutomation(
      { ...okScores, cpt_coding: { status: 'failed', reason: 'anthropic 529' } },
      { icdCodes: healthyIcd, cptCodes: null },
    );

    expect(r.needsReview).toBe(true);
    expect(r.failedLayers).toContain('cpt_coding');
    expect(r.causeByLayer.cpt_coding).toBe('failed');
  });
});

// ---------------------------------------------------------------------------
describe('F12-c — the orchestrator can actually reach the suppressed verdict', () => {
  // ⚠️ THE ARMS ABOVE ALL PASS `emApplies` BY HAND. That proves the seam and
  // says NOTHING about whether the worker computes `false` for a real operative
  // visit. A gate that only exercises the parameter it was handed is the
  // "fixture from the right domain, wrong universe" failure — so these arms
  // drive `emAppliesToVisit` with the inputs `worker.ts` actually passes it.

  it('an UNTEMPLATED operative note resolves to emApplies=false', () => {
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: null,
        noteText: OPERATIVE_NOTE,
      }),
    ).toBe(false);
  });

  it('THE PRODUCTION-MAJORITY PATH — the SYSTEM DEFAULT template is SILENT, so the body decides', () => {
    // ⚠️ WITHOUT RULING #126c THIS PARAMETER IS PERMANENTLY TRUE AND THE WHOLE
    // ITEM IS INERT. `04-generate-soap.ts` binds `noteTemplateId`
    // UNCONDITIONALLY on both paths, falling back to the system default — so
    // in the worker `noteTemplate.sections` is almost never empty. If the
    // system default ever stops being silent, this arm is what says so.
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: SYSTEM_DEFAULT_NOTE_TEMPLATE.sections,
        noteText: OPERATIVE_NOTE,
      }),
    ).toBe(false);
  });

  it('THE SHAPE CONTRACT — ResolvedNoteTemplate.sections is what the classifier reads', () => {
    // `worker.ts` passes the RESOLVED template object where every other caller
    // passes the database row's JSONB. They agree only while the in-memory
    // sections carry a `label` field. Asserted rather than assumed, because a
    // shape drift here reads as "no labels" → silent, and fails OPEN.
    const labels = SYSTEM_DEFAULT_NOTE_TEMPLATE.sections.map((s) => s.label);
    expect(labels.length).toBeGreaterThan(0);
    expect(labels.every((l) => typeof l === 'string' && l.length > 0)).toBe(true);
  });

  it('AND THE OFFICE DIRECTION — a full SOAP note keeps its level', () => {
    // Ruling #123 names over-suppression as WORSE than the defect being fixed,
    // so the positive arm is not optional. A change that suppressed everything
    // would satisfy every assertion above this one.
    expect(
      emAppliesToVisit({
        specialtyId: 'gastroenterology',
        templateSections: SYSTEM_DEFAULT_NOTE_TEMPLATE.sections,
        noteText: OFFICE_NOTE,
      }),
    ).toBe(true);
  });

  it('THE HALF-LANDED-FIX ARM — worker.ts really wires both consumers', () => {
    // ⚠️ EVERY ARM ABOVE IS SATISFIED BY A `worker.ts` THAT NEVER CALLS ANY OF
    // THIS. The seam is proved, the classifier is proved, and the one line that
    // joins them is proved by nothing — which is exactly the defect F12-a's own
    // independent pass found in ITS guard (`noteText:` threaded everywhere and
    // asserted nowhere, so `noteText: ''` stayed green while disabling the
    // axis). `tsc` cannot help: `emApplies` is a REQUIRED boolean, so the
    // cheapest way to satisfy the compiler is to write `true`, and this file's
    // fixtures write `emApplies: true` fourteen times — the permissive value is
    // house style here too.
    //
    // Read as SOURCE, comment-stripped, because prose in this repository names
    // every token a scan looks for (`'practice-scope'` matched
    // "practice-scoped" once already).
    const fs = require('node:fs') as typeof import('node:fs');
    const path = require('node:path') as typeof import('node:path');
    const raw = fs.readFileSync(
      // __dirname is src/worker/layers/__tests__ → up THREE to src/.
      path.join(__dirname, '..', '..', '..', 'worker.ts'),
      'utf8',
    );
    // Comment-stripped, because prose in this repository names every token a
    // scan looks for. BOTH forms: whole-line comments AND a trailing `//` on a
    // code line — a reviewer pointed out that `enabled: flags.cpt, // emApplies
    // is handled in the layer` survives a leading-only strip and would then be
    // accused of deleting a procedure code.
    const src = raw
      .split('\n')
      .filter((l) => !/^\s*(\/\/|\*|\/\*)/.test(l))
      .map((l) => l.replace(/\s*\/\/.*$/, ''))
      .join('\n');

    // POSITIVE CONTROL ON THE MATCHER ITSELF — a scan that read the wrong file,
    // or stripped the whole thing, returns zero for every needle and looks
    // exactly like a clean pass.
    expect(src, 'the worker source must have been read').toContain(
      'runLayer7bCptCoding(',
    );
    expect(src.length).toBeGreaterThan(10_000);

    // 1 · the classifier is called, with all three axes, from real values.
    const call = /emAppliesToVisit\(\{([\s\S]{0,400}?)\}\)/.exec(src);
    expect(call, 'worker.ts must call emAppliesToVisit').not.toBeNull();
    const args = call![1];
    expect(args).toContain('specialtyId: visit.specialty');
    expect(args).toContain('templateSections: noteTemplate.sections');
    expect(args).toContain('noteText: soapFinalForFanout');

    // 2 · the four placeholder spellings that satisfy the compiler and disable
    //     the axis. Any of them here is the half-landed fix.
    for (const dead of [
      'templateSections: null',
      'templateSections: []',
      "noteText: ''",
      'noteText: null',
    ]) {
      expect(args, `worker.ts must not neutralise the axis with \`${dead}\``)
        .not.toContain(dead);
    }

    // 3 · BOTH consumers get the computed value, not a literal. One consumer
    //     wired and the other hardcoded is the partial landing this file exists
    //     for, and it is invisible to `tsc`.
    expect(src, 'L7b must receive the computed value').toMatch(
      /runLayer7bCptCoding\(\{[\s\S]{0,400}?\n\s*emApplies,\n/,
    );
    // ⚠️ AND THE DETECTOR MUST **NOT** RECEIVE IT. It reads the STORED
    // `cptCodes.emSuppressed` instead; handing it a verdict recomputed here
    // re-opens the resume-path banner two refuters found.
    expect(src, 'the detector must not be handed a recomputed verdict').not.toMatch(
      /detectIncompleteAutomation\([\s\S]{0,1200}?\n\s*emApplies,\n/,
    );
    expect(src, 'neither consumer may be handed a literal').not.toMatch(
      /emApplies:\s*(true|false)/,
    );

    // 4 · ⚠️ THE NOTE-SHAPE AXIS MUST NEVER BECOME A LAYER GATE — ASSERTED AS A
    //     BUCKET TOTAL, NOT AS A LIST OF SPELLINGS.
    //
    // THIS ARM WAS WRONG TWICE AND BOTH FAILURES WERE MEASURED, NOT IMAGINED.
    //
    //   1st: no arm at all. `flags.cpt = … && !isImagingReport && emApplies`
    //        left this gate 16 of 16 GREEN. The "#109 ARM" above calls
    //        `runLayer7bCptCoding` directly, so it cannot see a layer that
    //        never runs — its title was wider than what it measured.
    //   2nd: an arm that scanned the `cpt:` LINE. An adversarial reviewer then
    //        gated the SAME layer one line lower — `enabled: flags.cpt &&
    //        emApplies`, on the task object — and the gate read 16 of 16 GREEN
    //        AGAIN. One form enumerated, two forms available; the recorded
    //        lesson is that a sweep is defeated by an incomplete TOKEN LIST at
    //        least as often as by a missing form.
    //
    // What either mutation ships: the cpt task never runs on an operative note,
    // it records status:'skipped', `cptCodes` stays NULL, and a colonoscopy
    // loses its PROCEDURE code — the one code that encounter genuinely bills.
    // The E/M is indeed gone, so every other arm in this file still passes.
    //
    // So this asserts the PROPERTY instead of the spellings: `emApplies` may
    // appear in exactly FOUR places in the comment-stripped source, and the two
    // consumer sites must be the bare shorthand. Any third spelling of a layer
    // gate — one nobody has thought of yet — makes the total 5 and reddens
    // here, naming the offending line. That is the "enumerate every bucket and
    // assert the total" shape; anything that does not fit a named bucket IS the
    // finding.
    const uses = src
      .split('\n')
      .map((line, i) => ({ line: line.trim(), n: i + 1 }))
      .filter((l) => l.line.includes('emApplies'));

    // ⚠️ THE BUCKET PREDICATES ACCEPT EVERY BEHAVIOUR-IDENTICAL SPELLING THEY
    // CAN, BECAUSE AN OVER-STRICT PROBE IS ALSO A DEFECT. A reviewer applied
    // `const emApplies: boolean = emAppliesToVisit({` — a cosmetic type
    // annotation — and earned a failure message accusing them of deleting a
    // colonoscopy's procedure code. A guard that cries clinical harm at a
    // formatting change is a guard people learn to route around.
    const BUCKETS = {
      import: (l: string) => /^import\s.*emAppliesToVisit.*from/.test(l),
      // The `= true` / `= false` shape must NOT match: calling the classifier
      // and discarding its result is a real bypass a reviewer demonstrated.
      compute: (l: string) =>
        /^const emApplies(\s*:\s*boolean)?\s*=\s*emAppliesToVisit\(\{?$/.test(l),
      consumer: (l: string) => l === 'emApplies,' || l === 'emApplies: emApplies,',
    };
    const classify = (l: string) =>
      (Object.keys(BUCKETS) as Array<keyof typeof BUCKETS>).find((k) => BUCKETS[k](l));

    const unclassified = uses.filter((u) => !classify(u.line));
    expect(
      unclassified.map((u) => `worker.ts:${u.n}  ${u.line}`),
      'every `emApplies` in worker.ts must be the import, the ONE computation, or a bare ' +
        'consumer argument. Anything else — `flags.cpt && emApplies`, `enabled: flags.cpt && ' +
        'emApplies`, or any other layer gate — deletes the PROCEDURE code from every ' +
        'colonoscopy while leaving every other arm in this file green.',
    ).toEqual([]);

    // The bucket census must also RECONCILE, or "0 unclassified" is satisfiable
    // by a file that lost the wiring altogether. It also catches the shape
    // `const emApplies = true;` followed by a bare `emAppliesToVisit({...});`
    // whose result is discarded — the call is present, the value is not used,
    // and every arg check above still passes.
    const census = { import: 0, compute: 0, consumer: 0 };
    for (const u of uses) census[classify(u.line)!]++;
    expect(census).toEqual({ import: 1, compute: 1, consumer: 1 });

    // 5 · ⚠️ AND THE TWO LAYER GATES ARE PINNED BY THEIR EXACT FORM, BECAUSE A
    //     TOKEN CENSUS IS A DENYLIST AND THIS IS KNOWABLE.
    //
    // The census above watches the token `emApplies`. A reviewer probing this
    // gate defeated it in one line by introducing a DIFFERENT identifier —
    // `const isOperativeNote = isProcedureNoteShapeFromText(soapFinalForFanout)`
    // — and gating the layer on that instead. Same deletion of the same
    // colonoscopy's procedure code, no `emApplies` anywhere near it.
    //
    // A denylist of identifiers is unbounded. What is BOUNDED is the correct
    // answer: the cpt layer runs when the env flag allows it and the visit is
    // not an imaging report, and on NOTHING else. So both lines are asserted by
    // equality rather than by absence — canon's own "prefer `toBe` over
    // `toContain` whenever the expected value is knowable".
    //
    // ⚠️ YES, THIS REDDENS ON A REFORMAT. That is intended: these two lines
    // decide whether a colonoscopy keeps the one code it bills, and a change to
    // either should cost somebody a deliberate read of ruling #127 rather than
    // sliding through as whitespace.
    const flagLine = /\n\s*(cpt:[^\n]*)/.exec(src);
    expect(flagLine, 'worker.ts must still declare a cpt flag').not.toBeNull();
    expect(
      flagLine![1],
      'the LAYER gate may depend only on the env flag and the imaging specialty',
    ).toBe("cpt: process.env.TM_ENABLE_ICD_CPT !== 'false' && !isImagingReport,");

    const taskEnabled = /key:\s*'cpt_coding',\s*\n\s*(enabled:[^\n]*)/.exec(src);
    expect(taskEnabled, "the cpt_coding task must still declare `enabled`").not.toBeNull();
    expect(
      taskEnabled![1],
      'the cpt_coding TASK gate may depend only on flags.cpt — anything else ' +
        'stops the layer running on operative notes and deletes their procedure code',
    ).toBe('enabled: flags.cpt,');
  });

  it('the fixture is built from the REAL marker list, not from remembered strings', () => {
    // A fixture whose headings drifted out of `PROCEDURE_NOTE_SECTION_MARKERS`
    // would make every suppression arm above vacuous while staying green.
    const headings = OPERATIVE_NOTE.split('\n')
      .filter((l) => l.startsWith('## '))
      .map((l) => l.slice(3).trim().toUpperCase());
    const hits = headings.filter((h) => PROCEDURE_NOTE_SECTION_MARKERS.includes(h));
    expect(hits.length, `fixture headings ${headings.join(' | ')} must be real markers`)
      .toBeGreaterThanOrEqual(2);
  });
});
