// ============================================================================
// F5-i PART 1a — A SECOND SHAPE WALKS THE REAL PIPELINE AND IS REFUSED, BY NAME.
// ----------------------------------------------------------------------------
// THE OWNER'S QUESTION was "is the fix for ALL categories/templates, not just
// mine?". F5-i's census answered it honestly and uncomfortably: production
// holds 10 note templates and exactly ONE compiled twin — the venous duplex —
// so every end-to-end claim about the engine rested on one shape.
//
// ⚠️ WHAT WAS ACTUALLY UNPROVEN WAS THE FRONT HALF, NOT THE REFUSAL.
// `gate-derived-encounter-exercises-the-form.test.ts` already pins every
// refusal reason — but it hands `deriveVerificationEncounter` a HAND-BUILT
// `EncounterSourceField[]`. So the stages BEFORE it had never once run on a
// second shape:
//
//     .docx bytes -> ingestDocxTemplateSource -> compileTemplateDocx
//                 -> fallbackSemanticMappings -> deriveVerificationEncounter
//
// A classifier that mislabelled an operative note's narrative field as a
// measurement would produce a WRONG refusal reason, or — the case that would
// have mattered — an `ok: true` venous dictation about a colonoscopy. Nothing
// in the suite could have seen it, because nothing fed it real bytes.
//
// THIS GATE IS THAT WALK. It ends where the engine now ends for an unfamiliar
// shape: a NAMED refusal the doctor can read.
//
// ⚠️ WHAT IT DOES NOT CLAIM, said here so the title is not read wider than the
// measurement:
//   · it does NOT claim an operative note can certify. It cannot, by design,
//     and that refusal IS F5-i part 2. This gate asserts the refusal is
//     correct, named, and reached from real document bytes.
//   · it does NOT exercise the MODEL mapping path (`proposeSemanticMappings`).
//     It walks the deterministic FALLBACK, which is the path with no network
//     and therefore the one a gate can pin. See the honest-limit arm below,
//     which states that boundary as an assertion rather than as a comment.
//   · it does NOT walk an upload through the UI or the worker. Those are the
//     QA-stack half of part 1a and are named as owed, not claimed here.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { ingestDocxTemplateSource } from '../ingest-docx-source';
import { fallbackSemanticMappings } from '../semantic-mapping';
import {
  deriveVerificationEncounter,
  type EncounterSourceField,
} from '../verification-encounter';
import { compilerDecidableConcepts } from '../concept-registry';
import type { TemplateDocIR } from '../ir';

import { buildOperativeNoteDocx } from './fixtures/operative-note-source';

const APP_ROOT = process.cwd();
const REPO_ROOT = path.resolve(APP_ROOT, '../..');

/** The venous duplex — the ONE shape everything has been proven on so far. */
const VENOUS_FORM = path.join(REPO_ROOT, 'WM IOV Template.docx');
/** The second shape, committed so an upload walk has a real file to upload. */
const OPERATIVE_NOTE = path.join(
  APP_ROOT,
  'tests',
  'e2e',
  'fixtures',
  'sample-operative-note.docx',
);

async function irFromBytes(bytes: Uint8Array): Promise<TemplateDocIR> {
  return (await ingestDocxTemplateSource(bytes)).ir;
}

async function irFromFile(file: string): Promise<TemplateDocIR> {
  return irFromBytes(new Uint8Array(readFileSync(file)));
}

/**
 * THE WALK, as one function, so both shapes go through byte-for-byte the same
 * code. Two harnesses would let the second shape be "proven" by a path the
 * first never took.
 */
function encounterSourceFields(ir: TemplateDocIR): EncounterSourceField[] {
  const byId = new Map(ir.fields.map((f) => [f.fieldId, f]));
  return fallbackSemanticMappings(ir).map((m) => ({
    originalLabel: byId.get(m.fieldId)?.originalLabel ?? null,
    clinicalConcept: m.clinicalConcept,
  }));
}

describe('F5-i part 1a — a second SHAPE reaches a named refusal from real .docx bytes', () => {
  it('POSITIVE CONTROL — the harness DISCRIMINATES before any refusal is believed', async () => {
    // ⚠️ THIS ARM IS THE WHOLE REASON THE REST MEANS ANYTHING.
    // `no_measurement_rows` is what an EMPTY field set answers. A harness that
    // silently compiled nothing — a bad path, a throwing ingest swallowed
    // somewhere, an IR whose fields never populated — would produce exactly the
    // verdict this gate is looking for, for exactly the wrong reason. So the
    // venous form is run through the SAME walk first, and it must come back
    // derivable. Two zeroes with opposite meanings is one broken instrument.
    const venous = await irFromFile(VENOUS_FORM);
    expect(venous.fields.length).toBe(80);

    const derived = deriveVerificationEncounter(encounterSourceFields(venous));
    expect(derived.ok).toBe(true);
  });

  it('the operative note COMPILES — a non-vacuous field set with real labels', async () => {
    const ir = await irFromFile(OPERATIVE_NOTE);

    // A form that compiled to zero fields would satisfy every assertion below
    // while measuring nothing at all. The count is PINNED rather than
    // `> 0` — the expected value is knowable, so asserting the weaker thing
    // would let the fixture lose fields silently.
    expect(ir.fields.length).toBe(17);

    // ⚠️ 17 AND NOT 16, AND THE SEVENTEENTH IS NOT IN THE FIXTURE'S OWN BODY.
    // `operative-note-source.ts` declares SIXTEEN controls. The extra one is
    // "Practice display name", a letterhead control in the HEADER part that
    // `buildSyntheticDocx` supplies. Asserted rather than left as arithmetic a
    // reader has to redo — counting the controls in that file and getting 16
    // against this 17 is exactly the kind of unexplained gap that gets
    // "corrected" by someone loosening the assertion.
    expect(ir.fields.map((f) => f.originalLabel)).toContain('Practice display name');

    // Labels came from the document, not from the compiler's `Field N`
    // fallback. A fixture whose controls carried no alias would compile to
    // ordinals, and a refusal computed over ordinals says nothing about labels.
    const generated = ir.fields.filter((f) => f.labelSource === 'generated');
    expect(generated).toEqual([]);
    expect(ir.fields.map((f) => f.originalLabel)).toEqual(
      expect.arrayContaining([
        'Indication',
        'Findings',
        'Sedation',
        'Extent of examination',
        'Largest polyp diameter (mm)',
      ]),
    );
  });

  it('REFUSES with `no_measurement_rows` — named, not thrown, not fabricated', async () => {
    const ir = await irFromFile(OPERATIVE_NOTE);
    expect(deriveVerificationEncounter(encounterSourceFields(ir))).toEqual({
      ok: false,
      reason: 'no_measurement_rows',
    });
  });

  it('⚠️ the bucket is decided by the CONCEPT, never by the compiler KIND', async () => {
    // The sharpest arm in this file. The fixture deliberately carries
    // "Largest polyp diameter (mm)", and `inferTextKind` (compiler.ts:1187)
    // reads the word "diameter" and compiles it as `kind: 'measurement'`.
    //
    // So this document contains a field the COMPILER calls a measurement, and
    // the derivation must still answer `no_measurement_rows` — because that
    // bucket is decided by `clinicalConcept.startsWith('measurement.')`, and a
    // kind is not a concept. F5-i's own comment warns that "the buckets are
    // defined by the FIELD SET, never by what the document is called"; this is
    // the same trap one field lower down, and it is the one a future reader is
    // most likely to conflate.
    const ir = await irFromFile(OPERATIVE_NOTE);
    const measurementKind = ir.fields.filter((f) => f.kind === 'measurement');
    expect(measurementKind.length).toBeGreaterThan(0);

    const fields = encounterSourceFields(ir);
    expect(fields.filter((f) => f.clinicalConcept?.startsWith('measurement.'))).toEqual([]);
    expect(deriveVerificationEncounter(fields)).toEqual({
      ok: false,
      reason: 'no_measurement_rows',
    });
  });

  it('NOT ONE WORD OF VENOUS NARRATIVE ESCAPES — the fabrication class, asserted', async () => {
    // The defect F5-i existed to kill was a leg-vein dictation being attested
    // against a form that never mentions a vein. A refusal that still leaked
    // the reference encounter would be the same defect wearing a `false`.
    const ir = await irFromFile(OPERATIVE_NOTE);
    const out = JSON.stringify(deriveVerificationEncounter(encounterSourceFields(ir)));
    for (const word of [
      'saphenous',
      'reflux',
      'incompetent',
      'deep vein thrombosis',
      'varicos',
      'Bilateral lower extremity',
    ]) {
      expect(out.toLowerCase()).not.toContain(word.toLowerCase());
    }
  });

  it('a NEW SHAPE does not weaken the wall — every mapping is still needs_confirmation', async () => {
    // MAPPINGS_NOT_READY is the gate that makes a certificate mean something.
    // A second shape arriving must not come with a relaxation attached, and the
    // cheapest way for one to arrive is for a new path to emit a mapping that
    // is already `confirmed`.
    const ir = await irFromFile(OPERATIVE_NOTE);
    const mappings = fallbackSemanticMappings(ir);
    expect(mappings.length).toBe(ir.fields.length);
    expect(mappings.every((m) => m.status === 'needs_confirmation')).toBe(true);
    expect(mappings.every((m) => m.practiceDefault === null)).toBe(true);
  });

  it('the COMMITTED .docx is pinned to its tracked source — a hand-edit reddens here', async () => {
    // The binary is the artifact an upload walk needs; the source module is
    // what a reviewer can actually read. Compiling both and comparing the field
    // sets keeps them from drifting without depending on zip determinism,
    // which is not a property this repo has.
    const fromDisk = await irFromFile(OPERATIVE_NOTE);
    const fromSource = await irFromBytes(new Uint8Array(await buildOperativeNoteDocx()));

    const shape = (ir: TemplateDocIR) =>
      ir.fields.map((f) => `${f.originalLabel}|${f.kind}|${f.labelSource}`);
    expect(shape(fromDisk)).toEqual(shape(fromSource));
    expect(shape(fromDisk).length).toBe(fromDisk.fields.length);
  });

  it('HONEST LIMIT, as an assertion — the fallback path can decide only THREE concepts', async () => {
    // ⚠️ STATED AS AN ARM RATHER THAN A COMMENT, because it bounds every claim
    // above. On the deterministic fallback path a concept can only come from
    // `compilerDecidedConcept`, whose entire range is the vein-grid pair plus
    // the exam-type override. So "no measurement rows" on THIS path is a
    // weaker statement than "no measurement rows on this form" — the MODEL
    // path can propose concepts this one cannot, and a form's classification
    // may differ there.
    //
    // If that range ever widens, this arm reddens and whoever widens it has to
    // come back and re-read what this gate is entitled to conclude.
    expect([...compilerDecidableConcepts()].sort()).toEqual([
      'measurement.diameter',
      'measurement.reflux_time',
      'test.name',
    ]);
  });
});
