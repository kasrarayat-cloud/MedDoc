// ============================================================================
// L6 POLISH CAN SEE WHAT THE VISIT ACTUALLY CONTAINED (Q1 audit §07.1).
// ----------------------------------------------------------------------------
// Layer 6's input was `{soapDraft, critique, noteTemplate}` — it never saw the
// entities, the role-labeled transcript, or even the specialty, although the
// worker already had all three loaded for L4 and L5.
//
// WHAT THAT CONTEXT IS FOR, AND WHAT IT IS NOT FOR.
//
// It is a DISAMBIGUATION source, never a content source. The L6b fidelity gate
// measures the polished note against the DRAFT ONLY and rejects anything novel
// — that is deliberate, it is the fabrication backstop from 2026-06-11, and it
// is NOT weakened by this change. Anything L6 tried to import from the
// transcript would be rejected and the whole polish thrown away with it.
//
// So the value is in the fixes L6 previously had to GUESS at. A critique that
// says "the Assessment contradicts the HPI about chest pain" can be applied in
// either direction; both readings use vocabulary already in the draft, so both
// pass the gate, and until now L6 picked one blind. With the entities it can
// apply the fix in the direction the evidence actually supports.
//
// THE NON-VACUITY PROOF is the mirrored fixture. The same draft and the same
// critique are polished twice with OPPOSITE entities, and the resolution must
// flip. If the output were identical either way, the context would be
// decoration and these tests would be measuring nothing.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  completeText: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
  fidelityGate: vi.fn(),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return { ...actual, modelClient: { completeText: mocks.completeText } };
});
vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { update: mocks.prismaUpdate } },
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@/worker/finalize-review-state', () => ({
  applyAdditiveReviewState: vi.fn(async () => ({})),
}));
vi.mock('../06b-polish-fidelity-gate', async () => {
  const actual = await vi.importActual<
    typeof import('../06b-polish-fidelity-gate')
  >('../06b-polish-fidelity-gate');
  return { ...actual, runPolishFidelityGate: mocks.fidelityGate };
});

import { runLayer6Polish, type Layer6Input } from '../06-polish';
import type { CritiqueReport } from '../05-self-critique';

/** A draft that genuinely contradicts itself, so the fix below is ambiguous by
 *  construction and BOTH readings stay inside the draft's own vocabulary. */
const CONTRADICTORY_DRAFT = [
  '## Subjective',
  'Patient reports chest pain since Tuesday.',
  '',
  '## Objective',
  'Vitals stable.',
  '',
  '## Assessment',
  'No chest pain reported.',
  '',
  '## Plan',
  'Follow up in two weeks.',
].join('\n');

const AMBIGUOUS_CRITIQUE: CritiqueReport = {
  issues: [
    {
      severity: 'major',
      location: 'Assessment',
      description: 'The Assessment contradicts the Subjective regarding chest pain.',
      suggested_fix: 'Reconcile the two statements so the note is internally consistent.',
    },
  ],
  overall_quality: 'medium',
  safe_to_sign_without_review: false,
};

/** L3 output in which the symptom was AFFIRMED. */
const ENTITIES_AFFIRMED = JSON.stringify({
  ros: [
    {
      system: 'cardiovascular',
      finding: 'chest pain present',
      evidence_quote: "I've had chest pain since Tuesday",
    },
  ],
});

/** The mirror: the same slot, denied. */
const ENTITIES_DENIED = JSON.stringify({
  ros: [
    {
      system: 'cardiovascular',
      finding: 'denies chest pain',
      evidence_quote: 'no, no chest pain at all',
    },
  ],
});

const TRANSCRIPT_AFFIRMED = [
  'Patient #1: I’ve had chest pain since Tuesday.',
  'Doctor #0: Understood.',
].join('\n');

const baseInput: Layer6Input = {
  visitId: 'vis-l6-context',
  practiceId: 'p1',
  userId: 'u1',
  soapDraft: CONTRADICTORY_DRAFT,
  critique: AMBIGUOUS_CRITIQUE,
};

/** The last prompt L6 sent to the model, as one searchable string. */
function lastPrompt(): string {
  const call = mocks.completeText.mock.calls.at(-1)?.[0];
  return `${call?.system ?? ''}\n${call?.user ?? ''}`;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.prismaUpdate.mockResolvedValue({});
  mocks.fidelityGate.mockResolvedValue({ ok: true });
  // The model echoes the draft; these tests are about what it is SHOWN.
  mocks.completeText.mockResolvedValue({ text: CONTRADICTORY_DRAFT });
});

describe('L6 receives the context the worker already had', () => {
  it('carries the SPECIALTY into the prompt', async () => {
    // Polish has been editing ultrasound reports and paediatric visits with no
    // idea which it was looking at.
    await runLayer6Polish({ ...baseInput, specialty: 'ultrasound' });
    expect(lastPrompt().toLowerCase()).toContain('ultrasound');
  });

  it('carries the ENTITIES into the prompt', async () => {
    await runLayer6Polish({ ...baseInput, entitiesJson: ENTITIES_AFFIRMED });
    // A phrase that exists ONLY in the entities. "chest pain since Tuesday" is
    // in the draft too, so asserting that would pass with no wiring at all.
    expect(lastPrompt()).toContain('chest pain present');
  });

  it('carries the ROLE-LABELED TRANSCRIPT into the prompt', async () => {
    await runLayer6Polish({
      ...baseInput,
      roleLabeledTranscript: TRANSCRIPT_AFFIRMED,
    });
    expect(lastPrompt()).toContain('Doctor #0');
  });

  it('and changes NOTHING when none of it is supplied', async () => {
    // Every existing caller and test must be byte-identical. An optional field
    // with a falsy default is silent when never passed — that is the failure
    // class this repo has already been bitten by, so it is asserted, not assumed.
    await runLayer6Polish(baseInput);
    const p = lastPrompt();
    expect(p).not.toContain('WHAT WAS ACTUALLY SAID');
    expect(p).not.toContain('Specialty:');
  });
});

describe('the context is used to RESOLVE, not to add — the mirrored proof', () => {
  it('an AFFIRMED symptom points the fix one way', async () => {
    await runLayer6Polish({
      ...baseInput,
      entitiesJson: ENTITIES_AFFIRMED,
      roleLabeledTranscript: TRANSCRIPT_AFFIRMED,
    });
    const p = lastPrompt();
    expect(p).toContain("I’ve had chest pain since Tuesday");
    expect(p).not.toContain('no chest pain at all');
  });

  it('a DENIED symptom points it the other way — same draft, same critique', async () => {
    // THE NON-VACUITY CHECK. If this prompt were identical to the one above,
    // the context would be decoration and every assertion in this file would be
    // measuring the fixture rather than the code.
    await runLayer6Polish({ ...baseInput, entitiesJson: ENTITIES_DENIED });
    const p = lastPrompt();
    expect(p).toContain('no chest pain at all');
    expect(p).not.toContain("I’ve had chest pain since Tuesday");
  });

  it('the prompt forbids IMPORTING from the context', async () => {
    // The fabrication risk this change could introduce, stated where it can be
    // enforced. Handing polish the transcript without this line invites exactly
    // the expansion the 2026-06-11 gate exists to catch.
    await runLayer6Polish({
      ...baseInput,
      entitiesJson: ENTITIES_AFFIRMED,
      roleLabeledTranscript: TRANSCRIPT_AFFIRMED,
    });
    expect(lastPrompt()).toContain('never as content to add');
  });

  it('does NOT weaken the fidelity gate — the draft stays its only source', async () => {
    // The gate measures the polished note against the DRAFT. If the transcript
    // were ever passed to it as permitted context, anything polish copied in
    // would start passing, and the backstop would be gone.
    await runLayer6Polish({
      ...baseInput,
      entitiesJson: ENTITIES_AFFIRMED,
      roleLabeledTranscript: TRANSCRIPT_AFFIRMED,
    });
    const gateArg = mocks.fidelityGate.mock.calls.at(-1)?.[0] ?? {};
    expect(gateArg.draft).toBe(CONTRADICTORY_DRAFT);
    // Phrases unique to the transcript and the entities. Asserting on anything
    // the DRAFT also contains would pass no matter what the gate was handed.
    expect(JSON.stringify(gateArg)).not.toContain('Doctor #0');
    expect(JSON.stringify(gateArg)).not.toContain('chest pain present');
  });
});
