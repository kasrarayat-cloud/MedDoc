// ============================================================================
// L6 survival tuning canaries (2026-07-02) — additive-vs-rewording partition.
// Under anchored generation L5 asks polish to ADD lane-demoted content; the
// L6b gate rejects any addition by construction, which rejected the ENTIRE
// polish on ~every visit (17/17 QA matrix). These pin the partition: additive
// fixes are deferred to the review banner; only rewording fixes reach
// tm_polish; the gate is untouched.
// ============================================================================

import { describe, expect, it, beforeEach, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelCompleteText: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
  applyAdditiveReviewState: vi.fn(),
  runPolishFidelityGate: vi.fn(),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('@meddoc/ai');
  return {
    ...actual,
    modelClient: { completeText: mocks.modelCompleteText, complete: vi.fn() },
  };
});
vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { update: mocks.prismaUpdate } },
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('@/worker/finalize-review-state', () => ({
  applyAdditiveReviewState: mocks.applyAdditiveReviewState,
}));
vi.mock('../06b-polish-fidelity-gate', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../06b-polish-fidelity-gate');
  return { ...actual, runPolishFidelityGate: mocks.runPolishFidelityGate };
});

import { runLayer6Polish, isAdditiveFix } from '../06-polish';
import type { CritiqueIssue, CritiqueReport } from '../05-self-critique';

const DRAFT = `## Subjective
Headache for two days. Denies fever. Denies vision changes.

## Objective
BP 120/80. Neuro exam intact. No papilledema.

## Assessment
Tension-type headache.

## Plan
1. Ibuprofen 400 mg PRN.
2. Return if symptoms worsen.`;

function issue(overrides: Partial<CritiqueIssue>): CritiqueIssue {
  return {
    severity: 'major',
    location: 'Plan',
    description: 'issue',
    suggested_fix: 'apply the fix described above',
    ...overrides,
  };
}

function report(issues: CritiqueIssue[]): CritiqueReport {
  return { issues, overall_quality: 'medium', safe_to_sign_without_review: true };
}

function input(critique: CritiqueReport) {
  return {
    visitId: 'v_partition_test',
    practiceId: 'p1',
    userId: 'u1',
    soapDraft: DRAFT,
    critique,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.modelCompleteText.mockResolvedValue({ text: DRAFT });
  mocks.runPolishFidelityGate.mockResolvedValue({
    ok: true, violationCount: 0, kinds: [], novelTermCount: 0, gateError: null,
  });
  mocks.prismaUpdate.mockResolvedValue({});
  mocks.applyAdditiveReviewState.mockResolvedValue(undefined);
});

describe('isAdditiveFix', () => {
  it('classifies "Add …" fixes as additive (the lane-demotion class)', () => {
    expect(isAdditiveFix(DRAFT, issue({
      suggested_fix: "Add Plan item: 'Start lisinopril 10 mg orally daily in addition to amlodipine.'",
    }))).toBe(true);
    expect(isAdditiveFix(DRAFT, issue({
      suggested_fix: 'Populate the Vital Signs section with the dictated blood pressure readings.',
    }))).toBe(true);
  });

  it('classifies novel-content fixes without an add-verb as additive (caution-first)', () => {
    expect(isAdditiveFix(DRAFT, issue({
      suggested_fix: 'The plan should mention metformin titration, creatinine recheck, and ophthalmology referral.',
    }))).toBe(true);
  });

  it('classifies rewording/consolidation fixes as NOT additive', () => {
    expect(isAdditiveFix(DRAFT, issue({
      suggested_fix: 'Consolidate the overlapping negatives into a single sentence.',
    }))).toBe(false);
    expect(isAdditiveFix(DRAFT, issue({
      suggested_fix: 'apply the fix described above',
    }))).toBe(false);
  });

  it('NEVER defers removal fixes — deletions are gate-passable and safety-relevant', () => {
    expect(isAdditiveFix(DRAFT, issue({
      suggested_fix: 'Remove the unsupported contraindication reasoning and add a shorter neutral phrasing.',
    }))).toBe(false);
  });
});

describe('runLayer6Polish — partition behavior', () => {
  it('ALL-additive fixable set → passthrough (no tm_polish call), deferred reason + needsReview', async () => {
    const r = await runLayer6Polish(input(report([
      issue({ suggested_fix: 'Add the omitted medication start to the Plan.' }),
      issue({ suggested_fix: 'Include the dictated potassium and creatinine values in Objective.' }),
    ])));
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
    expect(mocks.runPolishFidelityGate).not.toHaveBeenCalled();
    expect(r.soapFinal).toBe(DRAFT);
    expect(r.polishRejected).toBe(false);
    expect(r.needsReview).toBe(true);
    expect(r.reviewReason).toMatch(/deferred 2 auditor fixes/i);
    expect(r.reviewReason).toMatch(/content not in the draft/i);
  });

  it('mixed set → tm_polish called with ONLY the rewording fix; deferred reason composes', async () => {
    const r = await runLayer6Polish(input(report([
      issue({ suggested_fix: 'Add the omitted lisinopril start to the Plan.', description: 'Plan omits the new medication' }),
      issue({ suggested_fix: 'Consolidate the duplicated negation statements.', description: 'Duplicate negations' }),
    ])));
    expect(mocks.modelCompleteText).toHaveBeenCalledTimes(1);
    const user = mocks.modelCompleteText.mock.calls[0][0].user as string;
    expect(user).toContain('Consolidate the duplicated negation statements.');
    expect(user).not.toContain('lisinopril');
    expect(r.needsReview).toBe(true);
    expect(r.reviewReason).toMatch(/deferred 1 auditor fix\b/i);
  });

  it('all-rewording set → behavior unchanged (no deferred reason)', async () => {
    const r = await runLayer6Polish(input(report([
      issue({ suggested_fix: 'Consolidate the duplicated negation statements.' }),
    ])));
    expect(mocks.modelCompleteText).toHaveBeenCalledTimes(1);
    expect(r.reviewReason ?? '').not.toMatch(/deferred/i);
  });

  it('gate still backstops applied fixes (rejection path byte-compatible)', async () => {
    mocks.runPolishFidelityGate.mockResolvedValue({
      ok: false, violationCount: 2, kinds: ['addition'], novelTermCount: 9, gateError: null,
    });
    const r = await runLayer6Polish(input(report([
      issue({ suggested_fix: 'Consolidate the duplicated negation statements.' }),
    ])));
    expect(r.polishRejected).toBe(true);
    expect(r.soapFinal).toBe(DRAFT);
    expect(r.reviewReason).toMatch(/rejected by the fabrication gate/i);
    expect(mocks.logAudit).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'L6_FABRICATION_REJECTED' })
    );
  });
});
