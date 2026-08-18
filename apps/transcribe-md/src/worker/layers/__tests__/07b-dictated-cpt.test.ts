// ============================================================================
// A PROCEDURE CODE THE DOCTOR SAID ALOUD MUST REACH THE NOTE.
// ----------------------------------------------------------------------------
// Found on a production smoke (docs/backlog/q1-fixpack-carryover.md): a bilateral
// venous duplex was dictated with the CPT spoken — "bill this as 93970" — and
// PROCEDURES came back with ZERO entries. The code was in the transcript and did
// not reach the structured list.
//
// Why it vanished, precisely: L7b's input is `{specialty, soapFinal,
// entitiesJson}`. It never sees the raw dictation. And "bill this as 93970" is a
// billing instruction, not clinical prose, so L4 correctly leaves it out of the
// SOAP note — which means by the time coding runs, the sentence is gone. The
// allowlist was never the problem (93970 has been allowlisted throughout, and
// cpt-allowlist-coverage.test.ts pins that).
//
// So the capture belongs in L3, which DOES see the dictation, and the merge in
// L7b, which owns the fail-closed allowlist floor.
//
// THE PROVENANCE DISTINCTION IS THE POINT. A code the doctor dictated and a code
// the coding model proposed are different claims about the world. One is an
// instruction; the other is a suggestion to review. Billing cannot tell them
// apart if the note flattens them together, so `provenance` is carried through.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelComplete: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return { ...actual, modelClient: { complete: mocks.modelComplete } };
});
vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { update: mocks.prismaUpdate } },
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import { runLayer7bCptCoding } from '../07b-cpt-coding';

/** The coding model finds nothing — exactly what happened on the smoke, because
 *  the SOAP note it reads contains no billing instruction. */
const MODEL_FOUND_NOTHING = { em: null, procedures: [], modifiers: [] };

const VENOUS_DUPLEX_SOAP = [
  '## EXAM TYPE',
  'Bilateral lower extremity venous duplex ultrasound.',
  '## IMPRESSION',
  'No evidence of deep venous thrombosis.',
].join('\n');

/** What L3 extracts from a dictation in which the clinician spoke the code. */
const entitiesWithSpokenCode = (code: string) =>
  JSON.stringify({
    spoken_procedure_codes: [
      {
        code,
        description: 'Duplex scan of extremity veins, complete bilateral',
        evidence_quote: `bill this as ${code}`,
      },
    ],
  });

const baseInput = {
  visitId: 'vis-dictated-cpt',
  practiceId: 'p1',
  userId: 'u1',
  specialty: 'ultrasound',
  soapFinal: VENOUS_DUPLEX_SOAP,
  entitiesJson: '{}',
  // F12-c — every arm in this file is about the PROCEDURE half, which
  // `emApplies` does not touch. Set true so these arms keep testing exactly
  // what they tested before the parameter existed.
  //
  // ⚠️ AND THE COMBINATION IS UNREACHABLE IN PRODUCTION, WHICH IS SAID HERE
  // RATHER THAN LEFT TO BE REDISCOVERED: an `ultrasound` visit never reaches
  // L7b at all (`worker.ts` sets `flags.cpt = … && !isImagingReport`), so a
  // real ultrasound run would carry `emApplies: false` or would not run. That
  // does not weaken these arms — the dictated-code merge is specialty-agnostic
  // and none of them reads `result.em` — but a reader must not take this
  // fixture as evidence about how imaging visits are coded.
  emApplies: true,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.prismaUpdate.mockResolvedValue({});
  mocks.modelComplete.mockResolvedValue(MODEL_FOUND_NOTHING);
});

describe('a dictated CPT code reaches procedures', () => {
  it('THE SMOKE CASE — 93970 spoken aloud lands, with a description', async () => {
    const result = await runLayer7bCptCoding({
      ...baseInput,
      entitiesJson: entitiesWithSpokenCode('93970'),
    });

    const codes = result.procedures.map((p) => p.code);
    expect(codes, 'the dictated code must reach PROCEDURES').toContain('93970');

    const proc = result.procedures.find((p) => p.code === '93970')!;
    expect(proc.description, 'a bare code with no description is not billable').toBeTruthy();
    expect(proc.evidence_quote, 'must carry what the doctor actually said').toContain('93970');
  });

  it('marks it DICTATED, not coach-suggested', async () => {
    // Billing cannot tell an instruction from a suggestion if the note flattens
    // them together.
    const result = await runLayer7bCptCoding({
      ...baseInput,
      entitiesJson: entitiesWithSpokenCode('93970'),
    });
    expect(result.procedures.find((p) => p.code === '93970')?.provenance).toBe('dictated');
  });

  it('and a model-proposed code stays COACH-SUGGESTED', async () => {
    // The negative half: if everything came back "dictated", the field would be
    // decoration rather than a distinction.
    mocks.modelComplete.mockResolvedValue({
      em: null,
      procedures: [
        {
          code: '93971',
          description: 'Duplex scan of extremity veins, unilateral or limited',
          evidence_quote: 'unilateral study performed',
          confidenceLevel: 'high',
        },
      ],
      modifiers: [],
    });
    const result = await runLayer7bCptCoding(baseInput);
    expect(result.procedures.find((p) => p.code === '93971')?.provenance).toBe('coach_suggested');
  });

  it('NOTHING IS INVENTED when no code was spoken', async () => {
    // The failure mode on the other side: a capture path that hallucinates a
    // procedure onto every imaging visit would be far worse than the gap it fixes.
    const result = await runLayer7bCptCoding({ ...baseInput, entitiesJson: '{}' });
    expect(result.procedures).toEqual([]);
  });

  it('a NON-ALLOWLISTED spoken code is rejected — the floor still holds', async () => {
    // Fail-closed is not negotiable: a code the doctor said aloud is still a
    // claim, and an invented or mistyped one is a False Claims Act vector. The
    // dictated path goes through the SAME allowlist as the model's.
    const result = await runLayer7bCptCoding({
      ...baseInput,
      entitiesJson: entitiesWithSpokenCode('99999'),
    });
    expect(result.procedures.map((p) => p.code)).not.toContain('99999');
    expect(
      mocks.logAudit.mock.calls.some(
        (c) => c[0]?.action === 'CODING_COACH_REJECTED_INVALID_CPT',
      ),
      'rejection must use the EXISTING audit action, not a new silent path',
    ).toBe(true);
  });

  it('does not duplicate a code the model already proposed', async () => {
    // The doctor says it and the coder finds it: one procedure, not two. The
    // dictated provenance wins, because an instruction outranks a suggestion.
    mocks.modelComplete.mockResolvedValue({
      em: null,
      procedures: [
        {
          code: '93970',
          description: 'Duplex scan of extremity veins, complete bilateral',
          evidence_quote: 'bilateral venous duplex performed',
          confidenceLevel: 'high',
        },
      ],
      modifiers: [],
    });
    const result = await runLayer7bCptCoding({
      ...baseInput,
      entitiesJson: entitiesWithSpokenCode('93970'),
    });
    const hits = result.procedures.filter((p) => p.code === '93970');
    expect(hits).toHaveLength(1);
    expect(hits[0].provenance).toBe('dictated');
  });
});

// ============================================================================
// THE L3 HALF — the capture slot, where the raw dictation still exists.
// ----------------------------------------------------------------------------
// L7b can only merge what L3 hands it. These pin the contract between them, and
// in particular the one rule that keeps this a TRANSCRIPTION slot rather than a
// second coding engine: L3 records codes that were SPOKEN, and never infers one
// from a described procedure.
// ============================================================================

import { ExtractedEntities } from '../03-extract-entities';

/** chief_complaint and hpi are nullable-but-required, so a bare {} does not
 *  parse. This is the smallest thing that does. */
const MINIMAL = { chief_complaint: null, hpi: null };

describe('L3 capture slot for spoken procedure codes', () => {
  it('defaults to empty — the normal case for almost every visit', () => {
    const parsed = ExtractedEntities.parse({ ...MINIMAL });
    expect(parsed.spoken_procedure_codes).toEqual([]);
  });

  it('accepts a spoken code with its verbatim quote', () => {
    const parsed = ExtractedEntities.parse({
      ...MINIMAL,
      spoken_procedure_codes: [
        {
          code: '93970',
          description: 'Duplex scan of extremity veins, complete bilateral',
          evidence_quote: 'bill this as 93970',
        },
      ],
    });
    expect(parsed.spoken_procedure_codes[0].code).toBe('93970');
    expect(parsed.spoken_procedure_codes[0].evidence_quote).toBe('bill this as 93970');
  });

  it('rejects anything that is not five digits', () => {
    // A partial or garbled transcription must fail the slot rather than travel
    // downstream as a plausible-looking code. Rejection here is visible as a
    // SCHEMA_FAIL; a malformed code that survived would be a silent claim.
    for (const bad of ['9397', '939700', '9397A', 'E11.9', '']) {
      const r = ExtractedEntities.safeParse({
        ...MINIMAL,
        spoken_procedure_codes: [{ code: bad, evidence_quote: 'said something' }],
      });
      expect(r.success, `${bad || '(empty)'} should not parse as a CPT code`).toBe(false);
    }
  });

  it('requires an evidence quote — no code without the words behind it', () => {
    const r = ExtractedEntities.safeParse({
      ...MINIMAL,
      spoken_procedure_codes: [{ code: '93970' }],
    });
    expect(r.success).toBe(false);
  });

  it('the prompt forbids INFERRING a code from a described procedure', () => {
    // The whole failure mode this slot could introduce: an extractor that helpfully
    // supplies 93970 whenever it reads "bilateral venous duplex" would be inventing
    // a billing claim on every imaging visit. The rule lives in the prompt because
    // that is the only place it can be enforced.
    const { readFileSync } = require('node:fs') as typeof import('node:fs');
    const { join } = require('node:path') as typeof import('node:path');
    const src = readFileSync(join(__dirname, '../03-extract-entities.ts'), 'utf8');
    expect(src).toContain('NEVER infer a code from a described procedure');
    // Non-vacuity: the rule must be inside the field list the model is shown,
    // not stranded in a comment somewhere.
    expect(src).toContain("'- spoken_procedure_codes: list of {code, description?, evidence_quote,',");
  });
});

// ============================================================================
// THE DISPLAY HALF — provenance a doctor and a biller can actually see.
// ----------------------------------------------------------------------------
// Provenance recorded in a JSON column and shown to nobody is decoration. The
// note is marked in ONE direction on purpose; the reasoning is on the helper.
// ============================================================================

import { procedureProvenanceNote } from '@/lib/visit-export';

describe('provenance as it reaches the page and the export', () => {
  const base = { code: '93970', description: 'Duplex scan', evidence_quote: 'q' };

  it('a dictated code is named as dictated', () => {
    expect(procedureProvenanceNote({ ...base, provenance: 'dictated' })).toBe('dictated');
  });

  it('a coach-suggested code says nothing', () => {
    // The common case. A per-row "suggested" tag on every ordinary procedure is
    // noise, and noise on a billing line trains people to stop reading it.
    expect(procedureProvenanceNote({ ...base, provenance: 'coach_suggested' })).toBe('');
  });

  it('a legacy row with NO provenance also says nothing', () => {
    // The important one. Every procedure coded before this field existed has no
    // provenance, and there is no way to recover it. Silence is the only honest
    // rendering — the alternative asserts a distinction we cannot make.
    expect(procedureProvenanceNote(base)).toBe('');
  });
});

// ============================================================================
// THE DESCRIPTION, when the doctor said only the number.
// ----------------------------------------------------------------------------
// A live check against the real model showed L3 returns the code with NO
// description — correctly, because its prompt forbids supplying one from its own
// knowledge. That left a dictated code rendering as "93970 — Dictated procedure
// code" on a billing line: honest, and close to useless.
//
// When the coding model independently proposed the same code it already carried
// the real nomenclature. Borrowing it is not an invention — it is the same
// source every other procedure description on the note comes from.
// ============================================================================

describe('a dictated code borrows a description rather than inventing one', () => {
  const spokenBare = JSON.stringify({
    spoken_procedure_codes: [{ code: '93970', evidence_quote: 'bill this as 93970' }],
  });

  it('takes the coding model’s nomenclature when it proposed the same code', async () => {
    mocks.modelComplete.mockResolvedValue({
      em: null,
      procedures: [
        {
          code: '93970',
          description: 'Duplex scan of extremity veins, complete bilateral',
          evidence_quote: 'bilateral venous duplex performed',
          confidenceLevel: 'high',
        },
      ],
      modifiers: [],
    });
    const result = await codeWith(spokenBare);
    const proc = result.procedures.find((p) => p.code === '93970')!;
    expect(proc.description).toBe('Duplex scan of extremity veins, complete bilateral');
    // Provenance is unchanged: where the CODE came from is the claim being made,
    // and a borrowed label does not change who said the number.
    expect(proc.provenance).toBe('dictated');
    // And the doctor's own words stay the evidence.
    expect(proc.evidence_quote).toBe('bill this as 93970');
  });

  it('falls back to a neutral label when NOBODY named it', async () => {
    // The model found nothing, so there is no nomenclature to borrow. Guessing
    // one from the code number would be inventing clinical text on a claim.
    const result = await codeWith(spokenBare);
    const proc = result.procedures.find((p) => p.code === '93970')!;
    expect(proc.description).toBe('Dictated procedure code');
  });

  it('does not overwrite a description the CLINICIAN dictated', async () => {
    mocks.modelComplete.mockResolvedValue({
      em: null,
      procedures: [
        {
          code: '93970',
          description: 'Duplex scan of extremity veins, complete bilateral',
          evidence_quote: 'bilateral venous duplex performed',
          confidenceLevel: 'high',
        },
      ],
      modifiers: [],
    });
    const result = await codeWith(
      JSON.stringify({
        spoken_procedure_codes: [
          {
            code: '93970',
            description: 'bilateral leg vein scan',
            evidence_quote: 'bill this as 93970, bilateral leg vein scan',
          },
        ],
      }),
    );
    expect(result.procedures.find((p) => p.code === '93970')?.description).toBe(
      'bilateral leg vein scan',
    );
  });
});

/** Runs L7b with a given entitiesJson against the shared base input. */
async function codeWith(entitiesJson: string) {
  return runLayer7bCptCoding({ ...baseInput, entitiesJson });
}
