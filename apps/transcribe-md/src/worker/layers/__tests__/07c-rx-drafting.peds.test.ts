// ============================================================================
// L7c Rx drafting — pediatric framing tests (Fix-Pack 1, audit Finding 01.1)
// ----------------------------------------------------------------------------
// Asserts that the user message sent to modelClient.complete carries the
// correct PEDIATRIC PATIENT / weight-required / ADULT PATIENT header per the
// (ageYears, weightKg) pair the worker passes in.
//
// Mocks @meddoc/ai (so no real Anthropic call) AND @meddoc/db (so no Postgres
// is required). Captures the {system, user} args at call time so each test
// can assert on the exact prompt the model would have seen.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// We capture the modelClient.complete args here so each test can inspect
// what the layer actually built. Reset between tests via beforeEach below.
const captured: { system?: string; user?: string }[] = [];

vi.mock('@meddoc/ai', async (importOriginal) => ({
  // F-8: the layer now also calls the real (pure) drug-pair checker +
  // validateRxDose — pass the actual implementations through.
  ...(await importOriginal<Record<string, unknown>>()),
  modelClient: {
    complete: vi.fn(async (args: { system: string; user: string }) => {
      captured.push({ system: args.system, user: args.user });
      // Schema-valid empty-result. The layer doesn't branch on contents,
      // so an empty draft is the lightest fixture that satisfies the
      // RxResult zod shape.
      return { prescriptions: [], warnings: [] };
    }),
    completeText: vi.fn(),
  },
}));

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: {
      // The layer writes its draft to TranscribeVisit.rxDrafts after
      // the model call returns. Tests don't assert on this — make it
      // a no-op resolver so the layer's await chain completes.
      update: vi.fn(async () => ({})),
    },
  },
}));

// Fix-Pack 1 Q0-1 — L7c now imports `logAudit` from @/lib/audit so the
// validator integration can emit audit rows. That module pulls in
// next-auth → next/server which jsdom can't resolve in this unit test.
// Stub it out — the peds-framing tests don't assert on audit emits.
vi.mock('@/lib/audit', () => ({
  logAudit: vi.fn(async () => undefined),
}));

import { runLayer7cRxDrafting } from '../07c-rx-drafting';

const baseInput = {
  visitId: 'visit-test',
  practiceId: 'practice-test',
  userId: 'user-test',
  soapFinal: '## Subjective\nFever × 2 days.\n## Plan\nibuprofen 200 mg q6h.',
  entitiesJson: '{"medications":[],"allergies":[]}',
};

/** Build a DOB string for "ageYears years ago, today's date". The validator
 *  uses today's calendar to compute age, so anchoring relative to "now"
 *  keeps the test deterministic across runs without freezing time. */
function dobForAgeYears(ageYears: number): string {
  const now = new Date();
  const y = now.getFullYear() - ageYears;
  const m = String(now.getMonth() + 1).padStart(2, '0');
  // Shift the day back by 1 so a same-month boundary case never flips
  // the computed age between the test setup and the validator's read.
  const d = String(Math.max(1, now.getDate() - 1)).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

describe('runLayer7cRxDrafting — pediatric framing (Finding 01.1)', () => {
  beforeEach(() => {
    captured.length = 0;
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('emits "PEDIATRIC PATIENT" header when age < 18 and weight is non-null', async () => {
    await runLayer7cRxDrafting({
      ...baseInput,
      patient: {
        dateOfBirth: dobForAgeYears(6),
        weightKg: 22,
        allergies: [],
      },
    });

    expect(captured).toHaveLength(1);
    const userMsg = captured[0].user!;
    // Header substring is the contract — keep stable across copy edits.
    expect(userMsg).toMatch(/PEDIATRIC PATIENT, age 6 years, weight 22 kg\./);
    // The mg/kg/day instruction is the load-bearing part of the block.
    expect(userMsg).toContain('mg/kg/day');
    // Adult-only header MUST NOT appear in this branch.
    expect(userMsg).not.toMatch(/^ADULT PATIENT/m);
    // System prompt should include the few-shot examples for peds.
    const systemMsg = captured[0].system!;
    expect(systemMsg).toContain('PEDIATRIC FEW-SHOT EXAMPLES');
  });

  it('emits "weight required" critical-warning header when peds with null weight', async () => {
    await runLayer7cRxDrafting({
      ...baseInput,
      patient: {
        dateOfBirth: dobForAgeYears(4),
        weightKg: null,
        allergies: [],
      },
    });

    expect(captured).toHaveLength(1);
    const userMsg = captured[0].user!;
    expect(userMsg).toContain('PEDIATRIC PATIENT WITH UNKNOWN WEIGHT');
    expect(userMsg).toMatch(/weight required for pediatric dosing/i);
    // The refuse-numeric-dose instruction is the safety contract.
    expect(userMsg).toMatch(/action="unclear"/);
    // Few-shot examples still load (still pediatric) — anchor on the
    // refuse-mode behavior is intentional, not a regression.
    const systemMsg = captured[0].system!;
    expect(systemMsg).toContain('PEDIATRIC FEW-SHOT EXAMPLES');
  });

  it('emits "ADULT PATIENT" header when age >= 18 OR DOB is null', async () => {
    // Case 1: explicit adult.
    await runLayer7cRxDrafting({
      ...baseInput,
      patient: {
        dateOfBirth: dobForAgeYears(45),
        weightKg: 80,
        allergies: [],
      },
    });

    expect(captured).toHaveLength(1);
    expect(captured[0].user).toContain('ADULT PATIENT. Use adult dose ceilings.');
    expect(captured[0].user).not.toContain('PEDIATRIC PATIENT');
    // No few-shot examples for adults — token saving + avoids anchoring
    // the model on weight-based dosing inappropriately.
    expect(captured[0].system).not.toContain('PEDIATRIC FEW-SHOT EXAMPLES');

    captured.length = 0;

    // Case 2: null DOB falls back to adult ceilings.
    await runLayer7cRxDrafting({
      ...baseInput,
      patient: {
        dateOfBirth: null,
        weightKg: null,
        allergies: [],
      },
    });
    expect(captured).toHaveLength(1);
    expect(captured[0].user).toContain('ADULT PATIENT. Use adult dose ceilings.');
    expect(captured[0].user).not.toContain('PEDIATRIC PATIENT');
    expect(captured[0].system).not.toContain('PEDIATRIC FEW-SHOT EXAMPLES');
  });
});
