// ============================================================================
// L6 — polish. FIND-P1-016 + FIND-P1-018 (final partial) closure.
// ----------------------------------------------------------------------------
// Sibling test for the polish layer. Mirrors the L4 test template,
// adapted for L6's actual shape:
//
//   - Uses `modelClient.completeText` (markdown shape, no useToolUse)
//   - Sonnet (not Opus like L4/L5) — temperature 0.1 (tighter than L4)
//   - TWO BRANCHES:
//     (a) Passthrough: `fixable.length === 0` → soapFinal = soapDraft
//         (no model call, no validation needed — L4 already validated)
//     (b) Model-call: fixable.length > 0 → call completeText with
//         apply-the-fixes prompt → validate output → write soapFinal
//         + soapL6Original; raw write + needsReview on validator fail
//   - Output shape includes `needsReview` + `reviewReason` derived from
//     unfixable critiques AND (FIND-P1-016) the validator-fail reason.
//   - soapL6Original is written ALONGSIDE soapFinal as the immutable
//     T-M14.1 snapshot for sign-time DoctorEditPattern capture.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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
import type {
  CritiqueReport,
  CritiqueIssue,
} from '../05-self-critique';

const FAKE_VISIT = 'vis-6';
const FAKE_USER = 'u1';
const FAKE_PRACTICE = 'p1';

const DRAFT_SOAP = `## Subjective
Patient reports headache for 3 days.

## Objective
Vitals stable. HEENT normal.

## Assessment
Tension-type headache.

## Plan
1. Trial ibuprofen 400 mg PRN.
2. RTC if worsens.`;

const POLISHED_SOAP = `## Subjective
Patient reports throbbing headache for 3 days, no red flags.

## Objective
Vitals stable. HEENT normal. No focal neurologic deficits.

## Assessment
Tension-type headache, primary care manageable.

## Plan
1. Trial ibuprofen 400 mg PRN.
2. Hydration and stress-reduction counseling.
3. RTC if worsens or new neuro symptoms emerge.`;

function issue(
  severity: CritiqueIssue['severity'],
  description: string,
  location = 'Subjective'
): CritiqueIssue {
  return {
    severity,
    location,
    description,
    suggested_fix: 'apply the fix described above',
  };
}

function makeCleanReport(): CritiqueReport {
  return {
    issues: [],
    overall_quality: 'high',
    safe_to_sign_without_review: true,
  };
}

function makeInput(
  overrides: Partial<Layer6Input> = {}
): Layer6Input {
  return {
    visitId: FAKE_VISIT,
    practiceId: FAKE_PRACTICE,
    userId: FAKE_USER,
    soapDraft: DRAFT_SOAP,
    critique: makeCleanReport(),
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.prismaUpdate.mockResolvedValue({ id: FAKE_VISIT });
  mocks.logAudit.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('runLayer6Polish — passthrough branch (no fixable issues)', () => {
  it('skips the model call entirely when critique has zero issues', async () => {
    const result = await runLayer6Polish(makeInput());

    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();

    // Passthrough → soapFinal = soapDraft verbatim.
    expect(result.soapFinal).toBe(DRAFT_SOAP);
    expect(result.needsReview).toBe(false);
    expect(result.reviewReason).toBe(null);
    expect(result.unfixable).toEqual([]);
  });

  it('passthrough still writes both soapFinal + soapL6Original (T-M14.1 invariant)', async () => {
    await runLayer6Polish(makeInput());

    expect(mocks.prismaUpdate).toHaveBeenCalledTimes(1);
    const updateArgs = mocks.prismaUpdate.mock.calls[0][0];
    expect(updateArgs.where).toEqual({ id: FAKE_VISIT });
    expect(updateArgs.data.soapFinal).toBe(DRAFT_SOAP);
    expect(updateArgs.data.soapL6Original).toBe(DRAFT_SOAP);
  });

  it('passthrough with only unfixable critical issues flips needsReview', async () => {
    // No fixable issues but one unfixable critical (red-flag missing).
    // Model call still skipped; review banner still triggered.
    const report: CritiqueReport = {
      issues: [
        issue(
          'critical',
          'No red-flag screening for headache documented'
        ),
      ],
      overall_quality: 'low',
      safe_to_sign_without_review: false,
    };

    const result = await runLayer6Polish(makeInput({ critique: report }));

    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
    expect(result.needsReview).toBe(true);
    expect(result.reviewReason).toMatch(/Auto-polish could not fix 1 critical issue/);
    expect(result.unfixable).toHaveLength(1);
  });

  it('passthrough with safe_to_sign=false but no issues at all → needsReview=true', async () => {
    const report: CritiqueReport = {
      issues: [],
      overall_quality: 'medium',
      safe_to_sign_without_review: false,
    };

    const result = await runLayer6Polish(makeInput({ critique: report }));

    expect(result.needsReview).toBe(true);
    expect(result.reviewReason).toMatch(/Auditor flagged issues worth a quick review/);
  });
});

describe('runLayer6Polish — model-call branch contract', () => {
  function reportWithFixable(): CritiqueReport {
    return {
      issues: [issue('major', 'Plan does not address assessment')],
      overall_quality: 'medium',
      safe_to_sign_without_review: false,
    };
  }

  it('calls completeText with sonnet model, temperature 0.1, purpose tm_polish', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({ text: POLISHED_SOAP });

    await runLayer6Polish(makeInput({ critique: reportWithFixable() }));

    expect(mocks.modelCompleteText).toHaveBeenCalledTimes(1);
    const callArgs = mocks.modelCompleteText.mock.calls[0][0];

    expect(callArgs.provider).toBe('anthropic');
    expect(callArgs.purpose).toBe('tm_polish');
    expect(callArgs.model).toBe('claude-sonnet-4-6');
    expect(callArgs.temperature).toBe(0.1);
    expect(callArgs.maxTokens).toBe(8192);
    expect(callArgs.useToolUse).toBeUndefined();
    expect(callArgs.schema).toBeUndefined();
  });

  it('system prompt instructs "apply ONLY those fixes" + preserve unfixable content', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({ text: POLISHED_SOAP });

    await runLayer6Polish(makeInput({ critique: reportWithFixable() }));

    const { system } = mocks.modelCompleteText.mock.calls[0][0];
    expect(system).toMatch(/apply ONLY those fixes/i);
    expect(system).toMatch(/Preserve all clinical content/i);
    expect(system).toMatch(/Do NOT introduce new clinical facts/i);
    expect(system).toMatch(/Output ONLY the revised SOAP markdown/i);
  });

  it('user message carries the draft + fixable issues numbered', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({ text: POLISHED_SOAP });

    const report: CritiqueReport = {
      issues: [
        issue('major', 'plan missing'),
        issue('minor', 'unclear phrasing in HPI'),
      ],
      overall_quality: 'medium',
      safe_to_sign_without_review: false,
    };

    await runLayer6Polish(makeInput({ critique: report }));

    const { user } = mocks.modelCompleteText.mock.calls[0][0];
    expect(user).toMatch(/Draft:/);
    expect(user).toMatch(/Issues to apply/);
    expect(user).toMatch(/1\. \[major\]/);
    expect(user).toMatch(/2\. \[minor\]/);
  });

  it('happy path writes soapFinal + soapL6Original, no needsReview, no audit', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({ text: POLISHED_SOAP });

    const result = await runLayer6Polish(
      makeInput({
        critique: {
          issues: [issue('minor', 'redundant wording')],
          overall_quality: 'high',
          safe_to_sign_without_review: true,
        },
      })
    );

    expect(mocks.logAudit).not.toHaveBeenCalled();

    expect(result.soapFinal).toBe(POLISHED_SOAP);
    expect(result.needsReview).toBe(false);
    expect(result.reviewReason).toBe(null);

    const updateArgs = mocks.prismaUpdate.mock.calls[0][0];
    expect(updateArgs.data.soapFinal).toBe(POLISHED_SOAP);
    expect(updateArgs.data.soapL6Original).toBe(POLISHED_SOAP);
    expect(updateArgs.data.needsReview).toBeUndefined();
  });
});

describe('runLayer6Polish — FIND-P1-016 validator-fail path', () => {
  function reportWithFixable(): CritiqueReport {
    return {
      issues: [issue('major', 'plan missing')],
      overall_quality: 'medium',
      safe_to_sign_without_review: false,
    };
  }

  it('validator empty-output → raw write + needsReview + audit row', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({ text: '' });

    const result = await runLayer6Polish(
      makeInput({ critique: reportWithFixable() })
    );

    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.action).toBe('MODEL_OUTPUT_VALIDATION_FAIL');
    expect(auditArgs.success).toBe(false);
    expect(auditArgs.metadata.layer).toBe('L6');
    expect(auditArgs.metadata.reason).toBe('empty output');

    // Raw output still persisted.
    const updateArgs = mocks.prismaUpdate.mock.calls[0][0];
    expect(updateArgs.data.soapFinal).toBe('');
    expect(updateArgs.data.soapL6Original).toBe('');
    expect(updateArgs.data.needsReview).toBe(true);
    expect(updateArgs.data.reviewReason).toMatch(
      /Polish output didn't match expected markdown structure/
    );

    expect(result.needsReview).toBe(true);
    expect(result.reviewReason).toMatch(/Polish output didn't match/);
  });

  it('validator + unfixable critical → BOTH reasons compose in reviewReason', async () => {
    const report: CritiqueReport = {
      issues: [
        issue('major', 'plan missing'),
        issue('critical', 'No red-flag screening documented'), // unfixable
      ],
      overall_quality: 'low',
      safe_to_sign_without_review: false,
    };
    // Model returns garbage (JSON-shape rejection).
    mocks.modelCompleteText.mockResolvedValueOnce({ text: '{"oops": "wrong"}' });

    const result = await runLayer6Polish(makeInput({ critique: report }));

    // Validator-fail reason prepends; unfixable reason follows.
    expect(result.reviewReason).toMatch(
      /Polish output didn't match expected markdown structure[\s\S]*Auto-polish could not fix 1 critical issue/
    );
    expect(result.needsReview).toBe(true);
  });

  it('validator missing-sections → metadata includes the section list', async () => {
    const truncated = `## Subjective\nLong narrative here to clear the min-length gate.\n\n## Objective\nExam findings.`;
    mocks.modelCompleteText.mockResolvedValueOnce({ text: truncated });

    await runLayer6Polish(makeInput({ critique: reportWithFixable() }));

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    expect(auditArgs.metadata.missingSections).toEqual([
      'Assessment',
      'Plan',
    ]);
    expect(auditArgs.metadata.reason).toMatch(
      /missing SOAP sections: Assessment, Plan/
    );
  });

  it('audit metadata never carries raw output content (PHI guard)', async () => {
    const phiOutput =
      `## Subjective\nPatient Jane Doe MRN 88888 reports chest pain. ` +
      'A'.repeat(200); // missing other sections → validator fails
    mocks.modelCompleteText.mockResolvedValueOnce({ text: phiOutput });

    await runLayer6Polish(makeInput({ critique: reportWithFixable() }));

    const auditArgs = mocks.logAudit.mock.calls[0][0];
    const metaString = JSON.stringify(auditArgs.metadata);
    expect(metaString).not.toContain('Jane Doe');
    expect(metaString).not.toContain('88888');
    expect(metaString).not.toContain('chest pain');
    // Pin the exact metadata key set so a future refactor can't
    // accidentally add a `rawOutput` field.
    expect(Object.keys(auditArgs.metadata).sort()).toEqual([
      'layer',
      'missingSections',
      'outputLength',
      'reason',
    ]);
  });

  it('passthrough branch does NOT re-validate (soapDraft already validated by L4)', async () => {
    // Passthrough fires when fixable.length === 0. Even if soapDraft
    // would FAIL the validator, the passthrough branch must not run
    // L6's validator — that's L4's responsibility upstream. Pin
    // this so a future refactor doesn't accidentally add a redundant
    // validation step.
    const malformedDraft = '{"oh no": "wrong"}';
    const result = await runLayer6Polish(
      makeInput({ soapDraft: malformedDraft })
    );

    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
    expect(result.soapFinal).toBe(malformedDraft);
    // needsReview stays false on the passthrough branch with a clean
    // critique even if the draft is technically malformed.
    expect(result.needsReview).toBe(false);
  });
});

describe('runLayer6Polish — error propagation', () => {
  function reportWithFixable(): CritiqueReport {
    return {
      issues: [issue('major', 'plan missing')],
      overall_quality: 'medium',
      safe_to_sign_without_review: false,
    };
  }

  it('SCHEMA_FAIL from completeText propagates; NO DB write on failure', async () => {
    mocks.modelCompleteText.mockRejectedValueOnce(new Error('SCHEMA_FAIL'));

    await expect(
      runLayer6Polish(makeInput({ critique: reportWithFixable() }))
    ).rejects.toThrow('SCHEMA_FAIL');
    expect(mocks.prismaUpdate).not.toHaveBeenCalled();
  });

  it('ModelOutputMalformedError (FIND-P1-010) propagates without DB write', async () => {
    class FakeMalformed extends Error {
      constructor() {
        super('Anthropic response was not valid JSON: garbage');
        this.name = 'ModelOutputMalformedError';
      }
    }
    mocks.modelCompleteText.mockRejectedValueOnce(new FakeMalformed());

    await expect(
      runLayer6Polish(makeInput({ critique: reportWithFixable() }))
    ).rejects.toThrow(/Anthropic response was not valid JSON/);
    expect(mocks.prismaUpdate).not.toHaveBeenCalled();
  });
});
