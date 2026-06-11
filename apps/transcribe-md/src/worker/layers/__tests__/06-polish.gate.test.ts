// ============================================================================
// L6b fabrication gate — deterministic unit coverage (2026-06-11 RED fix).
// ----------------------------------------------------------------------------
// Pins the gate's load-bearing FAIL-CLOSED contract end-to-end through the
// REAL runLayer6Polish:
//   1. injected fabrication in a mocked L6 output → gate rejects →
//      soapFinal falls back to the pre-L6 draft + L6_FABRICATION_REJECTED
//      audit row + needsReview;
//   2. clean polish passes through untouched;
//   3. ANY gate/verifier failure (API error, prose output, malformed
//      verdict) → same fallback — gate error must NEVER ship ungated L6
//      output;
//   4. the passthrough branch never invokes the gate (no model call to
//      verify);
//   5. audit metadata carries counts + class strings only (PHI guard).
// Plus pure-function coverage of findNovelContentTerms, including the
// negation-flip case that documents why the term scan is telemetry, not
// an acceptor.
// All model calls mocked — runs in the CI unit gate.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelCompleteText: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    modelClient: {
      complete: vi.fn(),
      completeText: mocks.modelCompleteText,
    },
  };
});

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: { update: mocks.prismaUpdate },
  },
}));

vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import { runLayer6Polish, type Layer6Input } from '../06-polish';
import { findNovelContentTerms } from '../06b-polish-fidelity-gate';
import type { CritiqueReport } from '../05-self-critique';

const DRAFT = `## Subjective
Patient reports headache for 3 days. No visual changes.

## Objective
Vitals stable.

## Assessment
Tension-type headache.

## Plan
1. Trial ibuprofen 400 mg PRN.
2. RTC if worsens.`;

// A polished note with an INJECTED FABRICATION (a referral + risk
// reasoning that exist nowhere in the draft) — the day1_c03 class.
const FABRICATED_POLISH = `## Subjective
Patient reports headache for 3 days. No visual changes.

## Objective
Vitals stable.

## Assessment
Tension-type headache. Combined oral contraceptives are contraindicated in
migraine with aura due to elevated ischaemic stroke risk.

## Plan
1. Trial ibuprofen 400 mg PRN.
2. Urgent neurology referral.
3. RTC if worsens.`;

const CLEAN_POLISH = `## Subjective
Patient reports a 3-day headache. No visual changes.

## Objective
Vitals stable.

## Assessment
Tension-type headache.

## Plan
1. Trial ibuprofen 400 mg PRN.
2. Return to clinic if symptoms worsen.`;

const FIXABLE_CRITIQUE: CritiqueReport = {
  issues: [
    {
      severity: 'minor',
      location: 'Plan',
      description: 'tighten wording',
      suggested_fix: 'reword for clarity',
    },
  ],
  overall_quality: 'high',
  safe_to_sign_without_review: true,
};

function makeInput(overrides: Partial<Layer6Input> = {}): Layer6Input {
  return {
    visitId: 'vis-gate',
    practiceId: 'p1',
    userId: 'u1',
    soapDraft: DRAFT,
    critique: FIXABLE_CRITIQUE,
    ...overrides,
  };
}

/** Mock: polish call returns `polishText`; gate call returns `gateText`
 *  (or rejects when gateText is an Error). */
function mockPolishAndGate(polishText: string, gateText: string | Error) {
  mocks.modelCompleteText.mockImplementation(
    async (args: { purpose?: string }) => {
      if (args?.purpose === 'tm_polish_gate') {
        if (gateText instanceof Error) throw gateText;
        return { text: gateText };
      }
      return { text: polishText };
    }
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.prismaUpdate.mockResolvedValue({ id: 'vis-gate' });
  mocks.logAudit.mockResolvedValue(undefined);
});

describe('L6b gate — injected fabrication is rejected (the RED-finding case)', () => {
  it('verifier violation → soapFinal falls back to the pre-L6 draft', async () => {
    mockPolishAndGate(
      FABRICATED_POLISH,
      JSON.stringify({
        violations: [
          { kind: 'addition', summary: 'new contraindication/risk reasoning' },
          { kind: 'addition', summary: 'new neurology referral' },
        ],
      })
    );

    const result = await runLayer6Polish(makeInput());

    expect(result.polishRejected).toBe(true);
    expect(result.soapFinal).toBe(DRAFT); // the measured-clean artifact
    // DB write also carries the draft, not the fabricated polish.
    const updateArgs = mocks.prismaUpdate.mock.calls[0][0];
    expect(updateArgs.data.soapFinal).toBe(DRAFT);
    expect(updateArgs.data.soapL6Original).toBe(DRAFT);
  });

  it('rejection emits ONE L6_FABRICATION_REJECTED audit row with countable metadata', async () => {
    mockPolishAndGate(
      FABRICATED_POLISH,
      JSON.stringify({
        violations: [{ kind: 'addition', summary: 'new referral' }],
      })
    );

    await runLayer6Polish(makeInput());

    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    const audit = mocks.logAudit.mock.calls[0][0];
    expect(audit.action).toBe('L6_FABRICATION_REJECTED');
    expect(audit.success).toBe(false);
    expect(audit.metadata.layer).toBe('L6');
    expect(audit.metadata.violationCount).toBe(1);
    expect(audit.metadata.kinds).toEqual(['addition']);
    expect(audit.metadata.fellBackToDraft).toBe(true);
    expect(audit.metadata.gateError).toBe(null);
    expect(typeof audit.metadata.novelTermCount).toBe('number');
  });

  it('rejection flips needsReview with the fixes-not-applied reason', async () => {
    mockPolishAndGate(
      FABRICATED_POLISH,
      JSON.stringify({ violations: [{ kind: 'addition', summary: 'x' }] })
    );

    const result = await runLayer6Polish(makeInput());

    expect(result.needsReview).toBe(true);
    expect(result.reviewReason).toMatch(/rejected by the fabrication gate/);
    expect(result.reviewReason).toMatch(/fixes remain unapplied/);
  });

  it('meaning_change (negation flip) violations also reject', async () => {
    mockPolishAndGate(
      CLEAN_POLISH, // text looks clean — the verifier verdict is what counts
      JSON.stringify({
        violations: [{ kind: 'meaning_change', summary: 'negation flipped' }],
      })
    );

    const result = await runLayer6Polish(makeInput());

    expect(result.polishRejected).toBe(true);
    expect(result.soapFinal).toBe(DRAFT);
    expect(mocks.logAudit.mock.calls[0][0].metadata.kinds).toEqual([
      'meaning_change',
    ]);
  });
});

describe('L6b gate — clean polish passes through', () => {
  it('empty violations → polished text kept, no audit, no review flag', async () => {
    mockPolishAndGate(CLEAN_POLISH, '{"violations":[]}');

    const result = await runLayer6Polish(makeInput());

    expect(result.polishRejected).toBe(false);
    expect(result.soapFinal).toBe(CLEAN_POLISH);
    expect(result.needsReview).toBe(false);
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('tolerates verifier prose AROUND a valid JSON verdict (judge-parse lesson)', async () => {
    mockPolishAndGate(
      CLEAN_POLISH,
      'Here is my analysis:\n```json\n{"violations":[]}\n```\nThe edit is faithful.'
    );

    const result = await runLayer6Polish(makeInput());

    expect(result.polishRejected).toBe(false);
    expect(result.soapFinal).toBe(CLEAN_POLISH);
  });
});

describe('L6b gate — FAIL-CLOSED on every gate failure', () => {
  it('verifier API error → fallback to draft + audit with gateError class', async () => {
    mockPolishAndGate(CLEAN_POLISH, new Error('Anthropic 529 overloaded'));

    const result = await runLayer6Polish(makeInput());

    expect(result.polishRejected).toBe(true);
    expect(result.soapFinal).toBe(DRAFT);
    const audit = mocks.logAudit.mock.calls[0][0];
    expect(audit.action).toBe('L6_FABRICATION_REJECTED');
    expect(audit.metadata.gateError).toBe('verifier_call_failed');
    expect(audit.metadata.violationCount).toBe(0);
  });

  it('verifier output with NO JSON at all → fallback (verifier_output_not_json)', async () => {
    mockPolishAndGate(CLEAN_POLISH, 'I could not analyze this note.');

    const result = await runLayer6Polish(makeInput());

    expect(result.polishRejected).toBe(true);
    expect(result.soapFinal).toBe(DRAFT);
    expect(mocks.logAudit.mock.calls[0][0].metadata.gateError).toBe(
      'verifier_output_not_json'
    );
  });

  it('verifier JSON with the wrong shape → fallback (verifier_verdict_malformed)', async () => {
    mockPolishAndGate(CLEAN_POLISH, '{"violations": "none found"}');

    const result = await runLayer6Polish(makeInput());

    expect(result.polishRejected).toBe(true);
    expect(result.soapFinal).toBe(DRAFT);
    expect(mocks.logAudit.mock.calls[0][0].metadata.gateError).toBe(
      'verifier_verdict_malformed'
    );
  });

  it('gate fallback SKIPS structure validation (draft already L4-validated) — single audit row', async () => {
    mockPolishAndGate(CLEAN_POLISH, new Error('boom'));

    await runLayer6Polish(makeInput());

    // Exactly one audit row: the rejection. No MODEL_OUTPUT_VALIDATION_FAIL
    // for the fallback draft.
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit.mock.calls[0][0].action).toBe(
      'L6_FABRICATION_REJECTED'
    );
  });
});

describe('L6b gate — scope', () => {
  it('passthrough branch (no fixable issues) never invokes the gate', async () => {
    const result = await runLayer6Polish(
      makeInput({
        critique: {
          issues: [],
          overall_quality: 'high',
          safe_to_sign_without_review: true,
        },
      })
    );

    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
    expect(result.polishRejected).toBe(false);
    expect(result.soapFinal).toBe(DRAFT);
  });

  it('audit metadata never carries note content (PHI guard, key-set pinned)', async () => {
    mockPolishAndGate(
      FABRICATED_POLISH,
      JSON.stringify({
        violations: [{ kind: 'addition', summary: 'invented referral to Dr Jane Doe' }],
      })
    );

    await runLayer6Polish(makeInput());

    const meta = mocks.logAudit.mock.calls[0][0].metadata;
    const metaString = JSON.stringify(meta);
    // Neither the draft, the polish, nor the verifier's free-text summary
    // may reach the audit row.
    expect(metaString).not.toContain('headache');
    expect(metaString).not.toContain('ibuprofen');
    expect(metaString).not.toContain('Jane Doe');
    expect(Object.keys(meta).sort()).toEqual([
      'fellBackToDraft',
      'gateError',
      'kinds',
      'layer',
      'novelTermCount',
      'violationCount',
    ]);
  });
});

describe('findNovelContentTerms (pure telemetry helper)', () => {
  it('detects novel clinical terms absent from the base texts', () => {
    const novel = findNovelContentTerms(
      [DRAFT, 'reword for clarity'],
      FABRICATED_POLISH
    );
    // The fabrication's distinctive vocabulary shows up as novel terms.
    expect(novel).toEqual(
      expect.arrayContaining(['contraindicated', 'ischaemic', 'stroke', 'neurology'])
    );
  });

  it('a faithful reword has few/no novel terms', () => {
    const novel = findNovelContentTerms([DRAFT, 'reword for clarity'], DRAFT);
    expect(novel).toEqual([]);
  });

  it('a NEGATION FLIP adds zero novel terms — documents why the scan is not an acceptor', () => {
    const base = '## Subjective\nNo chest pain. Patient denies fever.';
    const flipped = '## Subjective\nChest pain. Patient denies fever.';
    expect(findNovelContentTerms([base], flipped)).toEqual([]);
  });
});
