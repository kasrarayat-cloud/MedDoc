// ============================================================================
// L7c Rx drafting — deterministic validator integration tests
// (Fix-Pack 1 Q0-1, audit Finding 06.1)
// ----------------------------------------------------------------------------
// Asserts that after the model call returns, validateRxDose runs against
// every prescription and surfaces its warnings into result.warnings with
// the correct severity. Uses the REAL validateRxDose from @meddoc/ai so
// the data tables (dose-ranges.ts, contraindications) are exercised
// end-to-end; only modelClient.complete + Prisma + audit are stubbed.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Captured logAudit calls — tests assert on action codes + targetIds so
// we know an audit row was emitted (or skipped, for the complex-dosing
// case which is intentionally not in the AuditAction enum yet).
const auditCalls: Array<{
  action: string;
  targetId?: string | null;
  metadata?: unknown;
}> = [];

vi.mock('@/lib/audit', () => ({
  logAudit: vi.fn(async (input: { action: string; targetId?: string | null; metadata?: unknown }) => {
    auditCalls.push({
      action: input.action,
      targetId: input.targetId,
      metadata: input.metadata,
    });
  }),
}));

// Per-test mock of modelClient.complete. Each test pushes a result via
// `setNextRxResult` before invoking runLayer7cRxDrafting; the mock
// resolves with that fixture.
let nextRxResult: { prescriptions: unknown[]; warnings: unknown[] } = {
  prescriptions: [],
  warnings: [],
};
function setNextRxResult(r: { prescriptions: unknown[]; warnings: unknown[] }) {
  nextRxResult = r;
}

// Keep validateRxDose REAL — the test exercises the full
// dose-ranges.ts + contraindications + peds-cap codepath.
vi.mock('@meddoc/ai', async () => {
  const actual =
    await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    modelClient: {
      complete: vi.fn(async () => nextRxResult),
      completeText: vi.fn(),
    },
  };
});

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: {
      update: vi.fn(async () => ({})),
    },
  },
}));

import { runLayer7cRxDrafting } from '../07c-rx-drafting';
import type { RxResult } from '../07c-rx-drafting';

/** Build a DOB string for "ageYears years ago, today's date". Mirrors
 *  the helper in 07c-rx-drafting.peds.test.ts so age math is consistent
 *  across the suite. */
function dobForAgeYears(ageYears: number): string {
  const now = new Date();
  const y = now.getFullYear() - ageYears;
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(Math.max(1, now.getDate() - 1)).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

const baseInput = {
  visitId: 'visit-validator-test',
  practiceId: 'practice-test',
  userId: 'user-test',
  soapFinal: '## Plan\nSee Rx draft.',
  entitiesJson: '{"medications":[],"allergies":[]}',
};

describe('runLayer7cRxDrafting — validateRxDose integration (Finding 06.1)', () => {
  beforeEach(() => {
    auditCalls.length = 0;
    nextRxResult = { prescriptions: [], warnings: [] };
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('A — pediatric overdose: amoxicillin 500 mg TID at 10 kg → fires RX_DOSE_EXCEEDS_VERIFIED_RANGE (critical)', async () => {
    // 500 mg/dose × 3 doses/day = 1500 mg/day at 10 kg = 150 mg/kg/day.
    // Verified peds max for amoxicillin is 90 mg/kg/day.
    setNextRxResult({
      prescriptions: [
        {
          drug: 'amoxicillin',
          strength: '500 mg',
          form: 'capsule',
          sig: 'Take 1 capsule TID',
          quantity: '30',
          refills: '0',
          action: 'new',
          evidence_quote: 'Start amoxicillin 500 mg TID for AOM',
        },
      ],
      warnings: [],
    });

    const out: RxResult = await runLayer7cRxDrafting({
      ...baseInput,
      patient: {
        dateOfBirth: dobForAgeYears(1), // 15-month-old (age 1 completed years)
        weightKg: 10,
        allergies: [],
      },
    });

    // Validator fired and the warning was appended to result.warnings.
    const doseWarnings = out.warnings.filter((w) =>
      w.message.includes('Exceeds verified peds max')
    );
    expect(doseWarnings.length).toBeGreaterThanOrEqual(1);
    expect(doseWarnings[0].severity).toBe('critical');
    expect(doseWarnings[0].rx_drug).toBe('amoxicillin');
    expect(doseWarnings[0].message).toMatch(/^\[deterministic\]/);

    // Audit row was emitted with the PR-D enum value.
    expect(
      auditCalls.some((c) => c.action === 'RX_DOSE_EXCEEDS_VERIFIED_RANGE')
    ).toBe(true);
  });

  it('B — penicillin-allergic patient + amoxicillin → fires RX_CONTRAINDICATION_MATCH (critical)', async () => {
    setNextRxResult({
      prescriptions: [
        {
          drug: 'amoxicillin',
          strength: '500 mg',
          form: 'capsule',
          sig: 'Take 1 capsule TID',
          quantity: '21',
          refills: '0',
          action: 'new',
          evidence_quote: 'Start amoxicillin for sinusitis',
        },
      ],
      warnings: [],
    });

    const out: RxResult = await runLayer7cRxDrafting({
      ...baseInput,
      patient: {
        dateOfBirth: '1980-01-01', // adult, no peds-cap collision
        weightKg: 75,
        allergies: ['Penicillin allergy — hives'],
      },
    });

    const contraWarnings = out.warnings.filter((w) =>
      w.message.toLowerCase().includes('allergy/contraindication match')
    );
    expect(contraWarnings.length).toBeGreaterThanOrEqual(1);
    expect(contraWarnings[0].severity).toBe('critical');
    expect(contraWarnings[0].rx_drug).toBe('amoxicillin');

    expect(
      auditCalls.some((c) => c.action === 'RX_CONTRAINDICATION_MATCH')
    ).toBe(true);
  });

  it('C — drug not in dose-ranges DB (pregabalin) → fires RX_DRUG_NOT_IN_VERIFIED_DATABASE (major)', async () => {
    // pregabalin is intentionally NOT in the 29-drug PR-D dose-ranges
    // table; this is the fail-closed "we cannot verify" path.
    setNextRxResult({
      prescriptions: [
        {
          drug: 'pregabalin',
          strength: '75 mg',
          form: 'capsule',
          sig: 'Take 1 capsule BID',
          quantity: '60',
          refills: '2',
          action: 'new',
          evidence_quote: 'Start pregabalin for neuropathic pain',
        },
      ],
      warnings: [],
    });

    const out: RxResult = await runLayer7cRxDrafting({
      ...baseInput,
      patient: {
        dateOfBirth: '1980-01-01',
        weightKg: 75,
        allergies: [],
      },
    });

    const unknownWarnings = out.warnings.filter((w) =>
      w.message.includes('not in our verified safety database')
    );
    expect(unknownWarnings.length).toBe(1);
    expect(unknownWarnings[0].severity).toBe('major');
    expect(unknownWarnings[0].rx_drug).toBe('pregabalin');
    expect(unknownWarnings[0].message).toMatch(/^\[deterministic\]/);

    expect(
      auditCalls.some(
        (c) => c.action === 'RX_DRUG_NOT_IN_VERIFIED_DATABASE'
      )
    ).toBe(true);
  });
});
