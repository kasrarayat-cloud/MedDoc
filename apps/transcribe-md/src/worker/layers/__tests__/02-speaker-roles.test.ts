// ============================================================================
// L2 — speaker roles. FIND-P1-017 closure tests.
// ----------------------------------------------------------------------------
// Two related changes from FIND-P1-017 (comprehensive-audit 2026-05-14):
//
//   1. Main AI-success branch now passes `useToolUse: { name, description }`
//      to `modelClient.complete`, forcing Anthropic to return the speaker
//      map via tool_use rather than free-form JSON. Eliminates the
//      JSON_PARSE_FAIL class for L2.
//
//   2. Fallback branch (no-samples) now runs the hardcoded
//      `{ '0': { role: 'doctor', confidence: 0.5, reasoning: ... } }`
//      shape through `SpeakerMap.parse(...)` before persistence —
//      catches drift between the constant and the Zod schema at
//      dev/test time rather than in production.
//
// These are also the first sibling tests for any L2-L6 layer
// (FIND-P1-018 noted the pipeline transformer chain had no unit
// tests). Mocked at the @meddoc/ai + @meddoc/db boundary; no real
// Anthropic calls and no real Postgres connection.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelComplete: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    modelClient: { complete: mocks.modelComplete },
  };
});

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: { update: mocks.prismaUpdate },
  },
}));

vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import {
  runLayer2SpeakerRoles,
  SpeakerMap,
  type Layer2Input,
} from '../02-speaker-roles';

const FAKE_VISIT = 'vis-1';
const FAKE_USER = 'u1';
const FAKE_PRACTICE = 'p1';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.prismaUpdate.mockResolvedValue({ id: FAKE_VISIT });
  mocks.logAudit.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

function makeInput(overrides: Partial<Layer2Input> = {}): Layer2Input {
  return {
    visitId: FAKE_VISIT,
    practiceId: FAKE_PRACTICE,
    userId: FAKE_USER,
    utterances: [
      { speaker: 0, transcript: 'How can I help you today?', start: 0, end: 2 },
      { speaker: 1, transcript: 'I have a headache.', start: 2, end: 4 },
      { speaker: 0, transcript: 'How long has it been going on?', start: 4, end: 6 },
      { speaker: 1, transcript: 'Three days now.', start: 6, end: 8 },
    ] as Layer2Input['utterances'],
    interpreterMode: false,
    ...overrides,
  };
}

describe('runLayer2SpeakerRoles — happy path (useToolUse main branch)', () => {
  it('passes useToolUse with submit_speaker_roles to modelClient.complete', async () => {
    const wellFormed = {
      '0': { role: 'doctor', confidence: 0.95, reasoning: 'asks diagnostic questions' },
      '1': { role: 'patient', confidence: 0.92, reasoning: 'describes symptoms in lay terms' },
    };
    mocks.modelComplete.mockResolvedValueOnce(wellFormed);

    const result = await runLayer2SpeakerRoles(makeInput());

    expect(mocks.modelComplete).toHaveBeenCalledTimes(1);
    const callArgs = mocks.modelComplete.mock.calls[0][0];

    // Cluster 3 / FIND-P1-017 contract: useToolUse must be set with
    // the canonical tool name. The downstream Anthropic call uses
    // this to force tool_use, eliminating JSON_PARSE_FAIL.
    expect(callArgs.useToolUse).toEqual({
      name: 'submit_speaker_roles',
      description: expect.stringContaining('speaker role classification'),
    });

    // The Zod schema is still passed (defense-in-depth: tool_use is
    // best-effort, Zod is the strict gate).
    expect(callArgs.schema).toBe(SpeakerMap);

    // Speaker map is written verbatim from the validated response.
    expect(result.speakerMap).toEqual(wellFormed);
    expect(result.lowestConfidence).toBeCloseTo(0.92, 5);
    expect(result.needsReview).toBe(false);
  });

  it('flips needsReview when lowest confidence falls below the threshold', async () => {
    const lowConf = {
      '0': { role: 'doctor', confidence: 0.95, reasoning: 'ok' },
      '1': { role: 'patient', confidence: 0.55, reasoning: 'noisy audio' },
    };
    mocks.modelComplete.mockResolvedValueOnce(lowConf);

    const result = await runLayer2SpeakerRoles(makeInput());

    expect(result.lowestConfidence).toBeCloseTo(0.55, 5);
    expect(result.needsReview).toBe(true);
    const updateArg = mocks.prismaUpdate.mock.calls[0][0];
    expect(updateArg.data.needsReview).toBe(true);
    expect(updateArg.data.reviewReason).toMatch(/confidence below/);
  });

  it('passes deterministic temperature=0 and the Zod schema (no regression)', async () => {
    mocks.modelComplete.mockResolvedValueOnce({
      '0': { role: 'doctor', confidence: 0.9, reasoning: '' },
    });

    await runLayer2SpeakerRoles(makeInput());

    const callArgs = mocks.modelComplete.mock.calls[0][0];
    expect(callArgs.temperature).toBe(0);
    expect(callArgs.schema).toBe(SpeakerMap);
    expect(callArgs.provider).toBe('anthropic');
    expect(callArgs.purpose).toBe('tm_speaker_roles');
  });
});

describe('runLayer2SpeakerRoles — fallback branch (no samples, FIND-P1-017)', () => {
  it('writes the hardcoded fallback when utterances yield zero samples', async () => {
    // utterances=[] → samples.size === 0 → fallback path
    const result = await runLayer2SpeakerRoles(makeInput({ utterances: [] }));

    // Model was NEVER called — fallback skips the AI step entirely.
    expect(mocks.modelComplete).not.toHaveBeenCalled();
    expect(mocks.prismaUpdate).toHaveBeenCalledTimes(1);

    // Result shape matches the canonical single-speaker-doctor fallback.
    expect(result).toEqual({
      speakerMap: {
        '0': {
          role: 'doctor',
          confidence: 0.5,
          reasoning: 'Diarization returned no speaker tags; defaulting to single-speaker doctor.',
        },
      },
      lowestConfidence: 0.5,
      needsReview: true,
    });

    const updateArg = mocks.prismaUpdate.mock.calls[0][0];
    expect(updateArg.data.needsReview).toBe(true);
  });

  it('fallback shape parses cleanly through SpeakerMap Zod schema (drift guard)', async () => {
    // This is the FIND-P1-017 invariant: if a future schema bump adds a
    // required field but the hardcoded fallback isn't updated, the
    // `SpeakerMap.parse(...)` call inside the fallback branch will
    // throw — surfacing the drift during a dev rebuild rather than
    // letting the runtime write a malformed row that breaks L3+.
    //
    // The test asserts this by exercising the fallback and confirming
    // the runtime did NOT throw + the returned shape passes a fresh
    // parse (i.e., the constant in source is in sync with the schema
    // at the time this test runs).
    const result = await runLayer2SpeakerRoles(makeInput({ utterances: [] }));

    // Re-parse: would throw if the runtime emitted a drifted shape.
    expect(() => SpeakerMap.parse(result.speakerMap)).not.toThrow();

    // And explicit shape: confidence is a number in [0, 1], role is
    // one of the SpeakerRole enum values.
    const entry = result.speakerMap['0'];
    expect(typeof entry.confidence).toBe('number');
    expect(entry.confidence).toBeGreaterThanOrEqual(0);
    expect(entry.confidence).toBeLessThanOrEqual(1);
    expect(['doctor', 'patient', 'family', 'other', 'unknown']).toContain(entry.role);
  });

  it('fallback ignores interpreterMode (single-speaker fallback is mode-agnostic)', async () => {
    const result = await runLayer2SpeakerRoles(
      makeInput({ utterances: [], interpreterMode: true })
    );

    // The fallback short-circuits before the system-prompt construction
    // that branches on interpreterMode — so the result shape is identical
    // for both modes. (If a future change adds an interpreter-mode
    // fallback, this test should fail and prompt a deliberate rewrite.)
    expect(result.speakerMap['0'].role).toBe('doctor');
    expect(result.speakerMap['0'].confidence).toBe(0.5);
    expect(mocks.modelComplete).not.toHaveBeenCalled();
  });
});

describe('runLayer2SpeakerRoles — propagation of model errors', () => {
  it('SCHEMA_FAIL from modelClient propagates up to the caller', async () => {
    // modelClient.complete internally retries on SCHEMA_FAIL up to
    // MAX_RETRIES=2 and then throws `Error('SCHEMA_FAIL')`. L2 itself
    // does NOT swallow — it propagates so the worker's outer catch
    // can categorize (transient → BullMQ retry) and surface a
    // user-facing reviewReason.
    mocks.modelComplete.mockRejectedValueOnce(new Error('SCHEMA_FAIL'));

    await expect(runLayer2SpeakerRoles(makeInput())).rejects.toThrow('SCHEMA_FAIL');
    // No DB write on the failure path.
    expect(mocks.prismaUpdate).not.toHaveBeenCalled();
  });
});
