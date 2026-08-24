// ============================================================================
// F24-S5 ITEM B — THE OTHER 28. THE CONTENT-CONTROL HALF OF THE CENSUS.
// ----------------------------------------------------------------------------
// The acceptance walk's arm 1 read 52/80 and was reported as a REFUSAL rather
// than a pass, because the number was true about a system that no longer
// exists: `gate-f24-s3-editor-addressable-census.test.ts:356` classifies every
// non-table-cell as `no_editor_intent` UNCONDITIONALLY, and that file carries
// zero references to `edit_form_control`, `listEditableFormControls` or
// `applyClinicianOverrides`. It measures the pre-S5 world correctly.
//
// This file measures the other 28 — and ITEM B's three clauses are the design,
// not a summary of it:
//
//   (a) REPLAY, NEVER RECLASSIFY.  Every bucket below is earned by RUNNING the
//       shipped addressing and the shipped fill. A bucket rename would satisfy
//       the ledger row and change nothing about the product, which is the exact
//       failure the clause forbids.
//   (b) RED IN BOTH DIRECTIONS.  Disabling the intent must take the number back
//       down, and a control that genuinely cannot be reached must land in a GAP
//       bucket rather than in `addressable`.
//   (c) THE RATCHET FLIPS ONLY IF THE REPLAY EARNS IT.  It does not. See the
//       closing block: 5 of the 28 are refused by design and the residual is a
//       PRODUCT question, not an editor gap.
//
// ⚠️ THE CLAIM I HAVE NOT TESTED IS: that the door's own value->ordinal MATCH
// behaves the same way this file's ordinal-first replay assumes. This file
// never runs `setTemplateControlAction` — it is a `'use server'` module with
// three prisma reads — so it addresses by the ORDINAL the server issued and
// hands `applyClinicianOverrides` the ordinal directly. The door's matching of
// a doctor's typed words onto that ordinal is asserted by
// `gate-f24-s5-write-path.test.ts` and is NOT re-asserted here. Written down
// before the refutation pass, per canon, so the gap is named by its author
// rather than found in it.
//
// ⚠️ AND THE LAYER THIS FILE EXISTS TO COVER IS THE ONE EVERY OTHER S5 PROOF
// RUNS BELOW. `gate-f24-s5-write-path.test.ts` calls the action with a
// `fieldId` already in hand; `gate-f24-s5-fill-wiring.test.ts` calls the fill
// with an override already in hand. Neither touches the ORDINAL — the only
// address the model is permitted to name, and the layer F24-S4 shipped a
// promise it could not keep on.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { compileTemplateDocx } from '@/lib/note-template-docx';
import {
  isWordPlaceholderOption,
  withoutPlaceholderOptions,
} from '@/lib/note-template-docx/placeholder-option';

const noteTemplateFindFirst = vi.fn();
const overrideFindMany = vi.fn();

// The same two stubs `gate-f24-s5-fill-wiring.test.ts` carries, for the same
// stated reason: they make the SUBJECT reachable and change no route the fill
// takes. The compiled IR, the resolver, the bridges, the overlay and the merge
// are all shipped code.
vi.mock('@meddoc/db', () => ({
  default: {
    noteTemplate: { findFirst: (...a: unknown[]) => noteTemplateFindFirst(...a) },
    templateTwinFieldOverride: { findMany: (...a: unknown[]) => overrideFindMany(...a) },
  },
}));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
vi.mock('../mapping-hash', () => ({ templateTwinMappingsSha256: () => 'MAPPINGS_SHA' }));

import { readAndPrepareTemplateTwinFill } from '../fill-engine';
import { listEditableFormControls } from '../editable-controls';
import { fallbackSemanticMappings } from '../semantic-mapping';
import type { SemanticMapping, TemplateField } from '../ir';

const WM_IOV_PATH = path.resolve(process.cwd(), '../../WM IOV Template.docx');
const wmIovBytes = new Uint8Array(readFileSync(WM_IOV_PATH));
const ir = compileTemplateDocx(wmIovBytes);

const isContentControl = (f: TemplateField) =>
  f.rendererBinding.bindingType === 'content_control';

/**
 * The mappings the DOCUMENT ITSELF decides, from the shipped derivation.
 *
 * ⚠️ DRIVEN, NOT APPROXIMATED. `fallbackSemanticMappings` is the function F5-a
 * shipped; re-deriving "which fields have a concept" by hand here would be the
 * census-fidelity failure this arc has already paid for twice (670 for 441;
 * 25 for 9).
 */
const DERIVED: SemanticMapping[] = fallbackSemanticMappings(ir);
const DERIVED_BY_ID = new Map(DERIVED.map((m) => [m.fieldId, m]));

/**
 * THE TWO MAPPING UNIVERSES, AND WHY ONE IS NOT ENOUGH.
 *
 * Addressability of a content control depends on whether its mapping carries a
 * `clinicalConcept` — `applyClinicianOverrides` declines `no_approved_concept`
 * without one, and the door refuses in the same direction. That value is
 * DATABASE state on a certified twin, so a census run over one universe would
 * be reporting a property of its fixture as a property of the system: canon's
 * "A WELL-CHOSEN FIXTURE DISGUISES A WRONG UNIVERSE", aimed at a census.
 *
 * · `document-decided`  — exactly what the shipped derivation produces. This is
 *   what a freshly compiled, not-yet-confirmed template carries.
 * · `certified-shaped`  — every NON-manual field additionally carries a
 *   concept, which is what certification MEANS: `MAPPINGS_NOT_READY` demands a
 *   concept for every non-manual field and deliberately certifies a `manual`
 *   one without.
 *
 * ⚠️ THE SUBSTITUTE CONCEPT IS A PRESENCE, NEVER A CLAIM ABOUT CORRECTNESS.
 * `certified-shaped` stands in one registered concept for the physician's
 * confirmation. This file asserts only that a concept EXISTS — it never asserts
 * the value is the right one for that control, and the arm below pins exactly
 * which fields the substitution touched so it cannot silently widen.
 */
type Universe = 'document-decided' | 'certified-shaped';
const SUBSTITUTE_CONCEPT = 'exam.side';

function conceptFor(m: SemanticMapping, universe: Universe): string | null {
  if (universe === 'document-decided') return m.clinicalConcept;
  return m.clinicalConcept ?? (m.sourceType === 'manual' ? null : SUBSTITUTE_CONCEPT);
}

function persistedFieldRows(universe: Universe) {
  return ir.fields.map((f) => {
    const m = DERIVED_BY_ID.get(f.fieldId)!;
    return {
      fieldId: f.fieldId,
      detectionStatus: 'CERTIFIED',
      mapping: {
        sourceType: m.sourceType,
        clinicalConcept: conceptFor(m, universe),
        expectedDataType: m.expectedDataType,
        polarityBehavior: m.polarityBehavior,
        temporality: m.temporality ?? 'current',
        laterality: m.laterality ?? 'optional',
        unitPolicy: m.unitPolicy,
        approvedSynonyms: m.approvedSynonyms,
        required: m.required,
        blankPolicy: m.blankPolicy,
        unknownPolicy: m.unknownPolicy,
        practiceDefault: null,
        mappingStatus: 'CERTIFIED',
      },
    };
  });
}

const storage = {
  readSourceArtifact: async () => wmIovBytes,
  storeOutputArtifact: async () => ({
    objectKey: 'k',
    sha256: 's',
    mimeType: 'm',
    sizeBytes: 1,
  }),
  readOutputArtifact: async () => wmIovBytes,
};

function armTemplate(universe: Universe) {
  noteTemplateFindFirst.mockResolvedValue({
    id: 'tpl-1',
    version: 1,
    templateTwinCompiledVersion: {
      id: 'cv-1',
      compilerVersion: ir.compilerVersion,
      compiledDocumentIr: ir,
      certificationStatus: 'CERTIFIED',
      certification: { id: 'cert-1', approvedMappingsSha256: 'MAPPINGS_SHA' },
      sourceArtifact: {
        practiceId: 'prac-1',
        objectKey: 'obj',
        sha256: 'sha',
        sizeBytes: 1,
        validationStatus: 'accepted',
      },
      fields: persistedFieldRows(universe),
    },
  });
}

interface ManifestField {
  fieldId: string;
  value: unknown;
  reasonCode?: string | null;
}

/** The REAL caller-level fill — the function the worker, the preview, the
 *  export and the sign freeze all go through. */
async function fill(
  universe: Universe,
  overrides: { fieldId: string; selectedOptionOrdinal: number }[],
): Promise<{ fields: ManifestField[]; declines: Record<string, number> }> {
  armTemplate(universe);
  overrideFindMany.mockResolvedValue(overrides);
  const out = await readAndPrepareTemplateTwinFill({
    visitId: 'v1',
    practiceId: 'prac-1',
    doctorId: 'doc-1',
    noteTemplateId: 'tpl-1',
    noteTemplateVersion: 1,
    inputMode: 'dictation',
    contextText: 'right GSV incompetent',
    entities: {},
    generatedNote: 'IMPRESSION: right GSV incompetent.',
    visitDate: new Date('2026-08-24T00:00:00.000Z'),
    validationNow: new Date('2026-08-24T00:00:00.000Z'),
    resolverModelVersion: null,
    storage: storage as never,
  } as never);
  const manifest = out.prepared.manifest as {
    fields: ManifestField[];
    validation?: { issues?: { code: string; message: string }[] };
  };
  const declines: Record<string, number> = {};
  for (const issue of manifest.validation?.issues ?? []) {
    if (issue.code !== 'CLINICIAN_OVERRIDE_DECLINED') continue;
    // ⚠️ THE REASON IS READ OFF THE ISSUE, NOT GUESSED. `declinedOverrideIssues`
    // writes "(<reason>)" into the message and the reason set is a closed union;
    // an unparseable message becomes its own loud bucket rather than being
    // folded into a plausible one.
    const m = /was not applied \(([a-z_]+)\)/.exec(issue.message);
    const reason = m ? m[1] : 'UNPARSEABLE_DECLINE_MESSAGE';
    declines[reason] = (declines[reason] ?? 0) + 1;
  }
  return { fields: manifest.fields, declines };
}

/**
 * ⚠️ THE PROBE THAT READ THE WRONG KEY, KEPT AS AN ASSERTION RATHER THAN A
 * MEMORY. The first draft read `manifest.issues`; the issues live at
 * `manifest.validation.issues`. It reported `declines 0` against 27 declines
 * logged by the overlay in the same run — the incoherent value is the only
 * reason it was caught, and this arm makes the key itself non-vacuous.
 */

// ---------------------------------------------------------------------------
// 0. THE UNIVERSE — pinned by CONTENT, before anything is counted
// ---------------------------------------------------------------------------
describe('F24-S5 control census — the universe is pinned by content', () => {
  it('the compiled form is the 80-field shape, split 52 table / 28 control', () => {
    expect(ir.fields.length, 'not the 80-field form').toBe(80);
    const controls = ir.fields.filter(isContentControl);
    expect(controls.length).toBe(28);
    // The partition against the file that owns the other half. 52 + 28 = 80, so
    // the two censuses provably cover the form between them with no residue and
    // no overlap — asserted here rather than assumed across two files.
    expect(ir.fields.length - controls.length, 'table-bound half moved').toBe(52);
  });

  it('⚠️ ALL 28 ARE OFFERED BY THE SHIPPED LIST — a control it filters out is unreachable', () => {
    // `listEditableFormControls` drops any control with an empty option set. If
    // that ever eats one, the census's denominator changes and the ratchet must
    // be re-earned rather than silently reinterpreted.
    expect(listEditableFormControls(ir).length).toBe(28);
  });

  it('⚠️ THE SHIPPED CLASSIFIER REPRODUCES PRODUCTION’S OWN MAPPING PARTITION', () => {
    // A SECOND, INDEPENDENT ROUTE to the figure this census is built on.
    // `set-template-control.ts` records a read-only production measurement of
    // the one certified twin (2026-08-24):
    //
    //     80 mappings = 52 extraction + 23 verified_note_selection + 5 manual
    //
    // That was measured against the DATABASE. This is `classifyFieldSource`
    // running over the compiled FIXTURE. They are different routes to the same
    // quantity, and they RECONCILE exactly — which is what makes the fixture
    // usable as a stand-in for the certified twin at all. If this ever diverges,
    // the fixture and the certified twin are no longer the same form and every
    // number below is about something else.
    const tally: Record<string, number> = {};
    for (const m of DERIVED) tally[m.sourceType] = (tally[m.sourceType] ?? 0) + 1;
    expect(tally).toEqual({ extraction: 52, verified_note_selection: 23, manual: 5 });
    // And all five manual fields are content controls — which is why the
    // residual this census reports is entirely inside the 28.
    const controlIds = new Set(ir.fields.filter(isContentControl).map((f) => f.fieldId));
    expect(DERIVED.filter((m) => m.sourceType === 'manual').every((m) => controlIds.has(m.fieldId)))
      .toBe(true);
  });

  it('⚠️ THE SUBSTITUTION IS BOUNDED, AND ITS EXTENT IS PINNED', () => {
    // `certified-shaped` may only ever ADD a concept where the derivation left
    // none AND the field is non-manual. A substitution that widened — to manual
    // fields, or over an existing concept — would manufacture addressability the
    // product does not have, which is the one way this universe could lie.
    const touched = DERIVED.filter(
      (m) => conceptFor(m, 'certified-shaped') !== conceptFor(m, 'document-decided'),
    );
    expect(touched.every((m) => m.clinicalConcept === null)).toBe(true);
    expect(touched.every((m) => m.sourceType !== 'manual')).toBe(true);
    // 28 = 1 already-decided + 22 substituted + 5 manual. The arithmetic is the
    // check: a partition that does not add up has an unnamed bucket in it.
    const controls = ir.fields.filter(isContentControl).map((f) => DERIVED_BY_ID.get(f.fieldId)!);
    const decided = controls.filter((m) => m.clinicalConcept !== null).length;
    const substituted = controls.filter(
      (m) => m.clinicalConcept === null && m.sourceType !== 'manual',
    ).length;
    const manual = controls.filter((m) => m.sourceType === 'manual').length;
    expect({ decided, substituted, manual }).toEqual({ decided: 1, substituted: 22, manual: 5 });
    expect(decided + substituted + manual).toBe(28);
  });
});

// ---------------------------------------------------------------------------
// 1. THE ADDRESSING — a server-issued ordinal, round-tripped
// ---------------------------------------------------------------------------
describe('F24-S5 control census — the ordinal is the address, and it round-trips', () => {
  const controls = listEditableFormControls(ir);

  it('⚠️ ordinals are 1..28, CONTIGUOUS and UNIQUE', () => {
    // A duplicate ordinal makes `find` order-dependent; a gap makes a number the
    // doctor reads off the list resolve to nothing. Both are wrong-control
    // writes waiting for a form that provokes them.
    expect(controls.map((c) => c.ordinal)).toEqual(
      Array.from({ length: 28 }, (_, i) => i + 1),
    );
    expect(new Set(controls.map((c) => c.fieldId)).size).toBe(28);
  });

  it('⚠️ THE ORDINAL FOLLOWS DOCUMENT ORDER — the order the doctor reads', () => {
    // FOUND BY REFUTING THIS FILE'S OWN CENSUS RATHER THAN BY THE CENSUS.
    //
    // Every other arm here addresses fieldId -> ordinal -> fieldId, so it
    // round-trips no matter what order the list is in. Sort `eligible` by
    // `fieldId` instead of `displayOrder` and the census still reads 23: the
    // ordinals are still unique, still contiguous, still resolve to their own
    // control — and ordinal 2 is no longer the second control on the page.
    //
    // That matters because the ordinal is the ONLY address, and the prompt tells
    // the doctor to count occurrences down their own form ("the FIRST of the two
    // identically-worded sentences, or the SECOND?"). A list in the wrong order
    // makes that question resolve to a real neighbouring control and report
    // success — the wrong-cell write this whole arc exists to stop, arriving one
    // layer above every proof that watches the write.
    //
    // `listEditableFormControls` sorts explicitly and its own comment says why.
    // This is the assertion that comment was missing.
    const byOrdinal = controls.map((c) => c.fieldId);
    const byDisplayOrder = ir.fields
      .filter((f) => isContentControl(f) && f.allowedOptions.length > 0)
      .slice()
      .sort((a, b) => a.displayOrder - b.displayOrder)
      .map((f) => f.fieldId);
    expect(byOrdinal).toEqual(byDisplayOrder);
    // NON-VACUITY: the two orders must be capable of differing, or the
    // assertion is satisfied by a form whose document order happens to equal
    // its compiled order and proves nothing about the sort.
    const byFieldId = [...byDisplayOrder].sort();
    expect(byFieldId, 'document order == fieldId order — this arm cannot discriminate')
      .not.toEqual(byDisplayOrder);
  });

  it('⚠️ EVERY ordinal resolves to its OWN control — the resolution the action makes', () => {
    // `chat-edit-visit.ts:348` resolves with `formControls.find(c => c.ordinal
    // === intent.controlOrdinal)` against THIS list. Driving the list is
    // driving the resolution; re-implementing a matcher here would be the F12-g
    // failure.
    for (const c of controls) {
      const resolved = controls.find((x) => x.ordinal === c.ordinal);
      expect(resolved?.fieldId, `ordinal ${c.ordinal} resolved elsewhere`).toBe(c.fieldId);
    }
  });

  it('⚠️ AN ORDINAL THE SERVER NEVER ISSUED RESOLVES TO NOTHING — refused, never clamped', () => {
    // The refusal BRANCH is asserted by the write-path gate. What is asserted
    // here is the property that branch depends on: the list does not silently
    // wrap, clamp or extend. A clamping resolution writes a real value into a
    // real neighbouring control and reports success.
    expect(controls.find((c) => c.ordinal === 0)).toBeUndefined();
    expect(controls.find((c) => c.ordinal === 29)).toBeUndefined();
    expect(controls.find((c) => c.ordinal === -1)).toBeUndefined();
  });

  it('⚠️ NO OPTION OFFERED IS WORD FURNITURE', () => {
    // The model may only name a value from this list, so a placeholder reaching
    // it is a placeholder the doctor can select. Driven through the shipped
    // predicate, with a positive control that it can still recognise one.
    for (const c of controls) {
      expect(c.options.length, `${c.fieldId} offers nothing`).toBeGreaterThan(0);
      for (const o of c.options) expect(isWordPlaceholderOption(o)).toBe(false);
    }
    expect(isWordPlaceholderOption('Choose an item.')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 2. THE CENSUS — replayed through the real fill, over both universes
// ---------------------------------------------------------------------------
describe('F24-S5 control census — replay, over both mapping universes', () => {
  beforeEach(() => {
    noteTemplateFindFirst.mockReset();
    overrideFindMany.mockReset();
    overrideFindMany.mockResolvedValue([]);
  });

  /** Choose, for each control, an option whose value DIFFERS from what the
   *  baseline fill produced — otherwise "it changed" is unobservable and a
   *  no-op would count as `addressable`. */
  function planFor(baseline: ManifestField[]) {
    const byId = new Map(baseline.map((f) => [f.fieldId, f]));
    const plan: { fieldId: string; selectedOptionOrdinal: number; want: string }[] = [];
    const indistinguishable: string[] = [];
    for (const c of listEditableFormControls(ir)) {
      const field = ir.fields.find((f) => f.fieldId === c.fieldId)!;
      const before = byId.get(c.fieldId);
      // ⚠️ THE SELECTABLE SET, NOT THE STORED ONE. The IR carries Word's
      // "Choose an item." at ordinal 0 (F24-S5 ITEM A — stripping it at compile
      // time orphaned every already-compiled twin), and a doctor can never pick
      // furniture. Planning over the stored array would make every arm below
      // measure the placeholder refusal instead of addressability.
      const opt = withoutPlaceholderOptions(field.allowedOptions)
        .sort((a, b) => a.ordinal - b.ordinal)
        .find((o) => o.value !== before?.value);
      if (!opt) {
        indistinguishable.push(c.fieldId);
        continue;
      }
      plan.push({ fieldId: c.fieldId, selectedOptionOrdinal: opt.ordinal, want: opt.value });
    }
    return { plan, indistinguishable };
  }

  async function census(universe: Universe) {
    const base = await fill(universe, []);
    const { plan, indistinguishable } = planFor(base.fields);
    const after = await fill(
      universe,
      plan.map((p) => ({ fieldId: p.fieldId, selectedOptionOrdinal: p.selectedOptionOrdinal })),
    );
    const afterById = new Map(after.fields.map((f) => [f.fieldId, f]));
    const baseById = new Map(base.fields.map((f) => [f.fieldId, f]));

    const buckets: Record<string, number> = {};
    const bump = (k: string) => {
      buckets[k] = (buckets[k] ?? 0) + 1;
    };
    for (const id of indistinguishable) bump('option_indistinguishable');

    // Declines are attributed to the plan as a whole; the manifest issue names
    // the reason and the field, so a per-field bucket is honest.
    const declinedIds = new Set<string>();
    for (const f of after.fields) {
      if (!plan.some((p) => p.fieldId === f.fieldId)) continue;
      const want = plan.find((p) => p.fieldId === f.fieldId)!;
      if (f.value === want.want && f.reasonCode === 'clinician_override') {
        bump('addressable');
      } else if (f.value === want.want && f.reasonCode !== 'clinician_override') {
        // The value is right and the provenance is not — a citation nobody can
        // trace back to the doctor's act. Never a census result.
        bump('wrote_without_provenance');
      } else if (f.value === baseById.get(f.fieldId)?.value) {
        declinedIds.add(f.fieldId);
      } else {
        // It moved, and not to what was asked for. The worst outcome there is.
        bump('wrote_wrong_value');
      }
    }
    // Every unchanged field must be explained by a decline the fill reported.
    const declineTotal = Object.values(after.declines).reduce((a, b) => a + b, 0);
    for (const [reason, n] of Object.entries(after.declines)) {
      buckets[`declined_${reason}`] = (buckets[`declined_${reason}`] ?? 0) + n;
    }
    const unexplained = declinedIds.size - declineTotal;
    if (unexplained > 0) buckets.silently_not_applied = unexplained;

    // Collateral: anything OUTSIDE the plan that moved between the two fills.
    let collateral = 0;
    for (const f of after.fields) {
      if (plan.some((p) => p.fieldId === f.fieldId)) continue;
      if (baseById.get(f.fieldId)?.value !== f.value) collateral += 1;
    }
    if (collateral > 0) buckets.collateral_write = collateral;

    return { buckets, planned: plan.length };
  }

  const BAD = [
    'wrote_wrong_value',
    'wrote_without_provenance',
    'collateral_write',
    'silently_not_applied',
  ] as const;

  it('CENSUS: both universes, every control in exactly one named bucket', async () => {
    const results: Record<string, Record<string, number>> = {};
    for (const universe of ['document-decided', 'certified-shaped'] as const) {
      const { buckets } = await census(universe);
      results[universe] = buckets;

      // The partition reconciles against a total computed a different way.
      expect(
        Object.values(buckets).reduce((a, b) => a + b, 0),
        `${universe}: partition does not reconcile to 28`,
      ).toBe(28);

      // ⚠️ A WRONG WRITE IS NEVER A CENSUS RESULT. Unlike a decline, none of
      // these is ever an acceptable steady state, in either universe.
      for (const bad of BAD) {
        expect(buckets[bad] ?? 0, `${universe}: ${bad}`).toBe(0);
      }
    }

    // eslint-disable-next-line no-console
    console.info(
      [
        '',
        'F24-S5 CONTROL CENSUS — the other 28, by replay',
        `  document-decided : ${JSON.stringify(results['document-decided'])}`,
        `  certified-shaped : ${JSON.stringify(results['certified-shaped'])}`,
        '',
      ].join('\n'),
    );

    // ⚠️ THE TWO UNIVERSES DISAGREE, AND THE DISAGREEMENT IS THE MEASUREMENT.
    // A census that produced the same number either way would be reporting a
    // property of its own harness.
    expect(results['document-decided'].addressable).toBe(1);
    expect(results['document-decided'].declined_no_approved_concept).toBe(27);
    expect(results['certified-shaped'].addressable).toBe(23);
    expect(results['certified-shaped'].declined_no_approved_concept).toBe(5);
  }, 180_000);

  // -------------------------------------------------------------------------
  // (b) RED IN BOTH DIRECTIONS
  // -------------------------------------------------------------------------
  it('⚠️ (b) DISABLING THE INTENT TAKES IT BACK DOWN — 23 becomes 0', async () => {
    // The mutation is run rather than written: an empty override set is exactly
    // what the pre-S5 world produced for every visit, and it is also what a
    // regression that stops reading the override rows would produce. If this
    // ever stays at 23, the census is reporting something other than the
    // correction — a ratchet that does not move when the fix is removed is a
    // decoration.
    const base = await fill('certified-shaped', []);
    const { plan } = planFor(base.fields);
    expect(plan.length, 'nothing to plan — the census is vacuous').toBe(28);

    const none = await fill('certified-shaped', []);
    const byId = new Map(none.fields.map((f) => [f.fieldId, f]));
    let addressable = 0;
    for (const p of plan) {
      const f = byId.get(p.fieldId);
      if (f?.value === p.want && f?.reasonCode === 'clinician_override') addressable += 1;
    }
    expect(addressable, 'the intent was disabled and the census did not notice').toBe(0);
  }, 180_000);

  it('⚠️ (b) AN UNREACHABLE CONTROL CLASSIFIES AS A GAP, NEVER AS ADDRESSABLE', async () => {
    // Not a synthetic mutation: `document-decided` IS the unreachable state for
    // 27 of the 28, because the derivation leaves them without a concept and
    // `applyClinicianOverrides` declines. Every one of those 27 must land in a
    // decline bucket and NONE may be counted addressable — the direction a
    // census written to agree with its author would get wrong.
    const { buckets } = await census('document-decided');
    expect(buckets.declined_no_approved_concept).toBe(27);
    expect(buckets.addressable).toBe(1);
    expect(buckets.wrote_wrong_value ?? 0).toBe(0);
  }, 180_000);

  it('⚠️ (b) AND THE DECLINE IS VISIBLE TO THE DOCTOR, not only to a log line', async () => {
    // A correction that is silently dropped is worse than one that is refused:
    // the chat already told the doctor it landed. The reason must reach the
    // manifest's own issue list, which is where the surfaces read it from.
    //
    // ⚠️ THIS ARM IS ALSO THE KEY CHECK. The first draft of this file read
    // `manifest.issues` and got 0 against 27 declines logged in the same run.
    // Reading the reason off the parsed message means a rename of the issue
    // shape reddens here instead of quietly zeroing the bucket.
    const base = await fill('document-decided', []);
    const { plan } = planFor(base.fields);
    const after = await fill(
      'document-decided',
      plan.map((p) => ({ fieldId: p.fieldId, selectedOptionOrdinal: p.selectedOptionOrdinal })),
    );
    expect(after.declines).toEqual({ no_approved_concept: 27 });
    expect(after.declines.UNPARSEABLE_DECLINE_MESSAGE ?? 0).toBe(0);
  }, 180_000);
});

// ---------------------------------------------------------------------------
// 3. (c) THE RATCHET — and it is NOT flipped to zero, because the replay did
//        not earn it
// ---------------------------------------------------------------------------
describe('F24-S5 control census — the ratchet, and what it does NOT claim', () => {
  beforeEach(() => {
    noteTemplateFindFirst.mockReset();
    overrideFindMany.mockReset();
    overrideFindMany.mockResolvedValue([]);
  });

  it('⚠️ (c) THE RESIDUAL IS 5, AND IT IS A PRODUCT QUESTION RATHER THAN AN EDITOR GAP', async () => {
    // ITEM B(c) says the deliberate `toBeGreaterThan(0)` becomes the zero
    // assertion ONLY IF the replay earns it. IT DOES NOT, and saying so is the
    // point of the clause.
    //
    // On the universe production is actually in, 23 of 28 controls are
    // addressable end to end. The other 5 are the `manual` fields — Address,
    // REFERRING PHYSICIAN, ULTRASOUND TECHNOLOGIST, LOCATION and one more —
    // which `mappings-readiness.ts` CERTIFIES with a null concept on purpose
    // ("nothing dictates who the technologist on shift was"), and which both
    // the door and the overlay refuse in the TIGHTEN-ONLY direction.
    //
    // ⚠️ SO F24'S "ZERO GAPS" ACCEPTANCE CANNOT BE MET BY BUILDING MORE EDITOR.
    // It is met by a decision about whether a concept-less control should be
    // settable at all — and letting one through would mint a fact the validator
    // has nothing to check a citation against. That is a loosening of a clinical
    // validation path and is not this layer's call.
    //
    // ⚠️ AND PRODUCTION READS 4, NOT 5 — A DIFFERENCE THIS FILE CANNOT SEE.
    // `set-template-control.ts` records 4 of the 5 manual mappings carrying a
    // null concept on the live certified twin, so a physician has confirmed a
    // concept for one of them. That is DATABASE state; the fixture-derived
    // universe leaves all 5 null. The census is therefore CONSERVATIVE by
    // exactly one control, and the direction is the safe one: it under-reports
    // addressability rather than claiming a control works that does not.
    const { buckets } = await census2();
    expect(buckets.addressable).toBe(23);
    expect(28 - (buckets.addressable ?? 0), 'the control half reached ZERO gaps — re-read (c) and update RELAY')
      .toBeGreaterThan(0);
  }, 180_000);

  async function census2() {
    const base = await fill('certified-shaped', []);
    const byId = new Map(base.fields.map((f) => [f.fieldId, f]));
    const plan: { fieldId: string; selectedOptionOrdinal: number; want: string }[] = [];
    for (const c of listEditableFormControls(ir)) {
      const field = ir.fields.find((f) => f.fieldId === c.fieldId)!;
      // ⚠️ THE SELECTABLE SET, NOT THE STORED ONE. The IR carries Word's
      // "Choose an item." at ordinal 0 (F24-S5 ITEM A — stripping it at compile
      // time orphaned every already-compiled twin), and a doctor can never pick
      // furniture. Planning over the stored array would make every arm below
      // measure the placeholder refusal instead of addressability.
      const opt = withoutPlaceholderOptions(field.allowedOptions)
        .sort((a, b) => a.ordinal - b.ordinal)
        .find((o) => o.value !== byId.get(c.fieldId)?.value);
      if (opt) plan.push({ fieldId: c.fieldId, selectedOptionOrdinal: opt.ordinal, want: opt.value });
    }
    const after = await fill(
      'certified-shaped',
      plan.map((p) => ({ fieldId: p.fieldId, selectedOptionOrdinal: p.selectedOptionOrdinal })),
    );
    const afterById = new Map(after.fields.map((f) => [f.fieldId, f]));
    let addressable = 0;
    for (const p of plan) {
      const f = afterById.get(p.fieldId);
      if (f?.value === p.want && f?.reasonCode === 'clinician_override') addressable += 1;
    }
    return { buckets: { addressable } };
  }
});
