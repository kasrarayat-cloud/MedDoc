// ============================================================================
// Deep-audit G9 — test the partial-L7-failure detection helper.
// ----------------------------------------------------------------------------
// Verifies that when any of icd_coding / cpt_coding / rx_drafting fails
// in the L7 fan-out, the visit gets flagged for review with a specific
// reason. Non-load-bearing layers (referrals, patient_summary) failing
// must NOT flip needsReview — they're page-augmentation, not signing-
// critical.
//
// Reproduces the deep-audit V3 scenario verbatim (credit-exhaustion
// 400 from Anthropic mid-L7) as one of the cases.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  detectIncompleteAutomation,
  LOAD_BEARING_L7_TASKS,
  type AutomationConfidenceScores,
} from '@/worker/automation-incomplete';

describe('detectIncompleteAutomation — happy path', () => {
  it('returns no-review when every load-bearing task is ok', () => {
    const scores: AutomationConfidenceScores = {
      icd_coding: { status: 'ok' },
      cpt_coding: { status: 'ok' },
      rx_drafting: { status: 'ok' },
      referrals: { status: 'ok' },
      patient_summary: {
        status: 'ok',
        metadata: { flesch_kincaid: 7.2, flagged: false },
      },
    };
    const r = detectIncompleteAutomation(scores);
    expect(r.needsReview).toBe(false);
    expect(r.reviewReason).toBeNull();
    expect(r.failedLayers).toEqual([]);
  });

  it('returns no-review when a load-bearing layer is intentionally skipped (env flag off)', () => {
    // TM_ENABLE_RX=false → rx_drafting rolls up as skipped, not failed.
    // Skipping is operator intent, not a failure — must NOT flip review.
    const scores: AutomationConfidenceScores = {
      icd_coding: { status: 'ok' },
      cpt_coding: { status: 'ok' },
      rx_drafting: { status: 'skipped' },
      referrals: { status: 'skipped' },
      patient_summary: { status: 'skipped' },
    };
    const r = detectIncompleteAutomation(scores);
    expect(r.needsReview).toBe(false);
    expect(r.failedLayers).toEqual([]);
  });
});

describe('detectIncompleteAutomation — partial failure (the G9 scenario)', () => {
  it('flags review when ONLY icd_coding fails', () => {
    const scores: AutomationConfidenceScores = {
      icd_coding: { status: 'failed', reason: 'allowlist filter dropped all codes' },
      cpt_coding: { status: 'ok' },
      rx_drafting: { status: 'ok' },
    };
    const r = detectIncompleteAutomation(scores);
    expect(r.needsReview).toBe(true);
    expect(r.failedLayers).toEqual(['icd_coding']);
    expect(r.reviewReason).toMatch(/Auto-coding incomplete/);
    expect(r.reviewReason).toMatch(/icd-coding: allowlist filter dropped all codes/);
    expect(r.reviewReason).toMatch(/Click Retry to reprocess\.$/);
    expect(r.reasonsByLayer.icd_coding).toBe('allowlist filter dropped all codes');
    expect(r.reasonsByLayer.cpt_coding).toBeNull();
    expect(r.reasonsByLayer.rx_drafting).toBeNull();
  });

  it('flags review when only rx_drafting fails (the deep-audit V3 shape)', () => {
    const scores: AutomationConfidenceScores = {
      icd_coding: { status: 'ok' },
      cpt_coding: { status: 'ok' },
      rx_drafting: {
        status: 'failed',
        reason: '400 invalid_request_error: Your credit balance is too low to access the Anthropic API.',
      },
    };
    const r = detectIncompleteAutomation(scores);
    expect(r.needsReview).toBe(true);
    expect(r.failedLayers).toEqual(['rx_drafting']);
    expect(r.reviewReason).toMatch(/rx-drafting: 400 invalid_request_error/);
    expect(r.reviewReason).toMatch(/credit balance/);
  });

  it('flags review when MULTIPLE load-bearing layers fail (the multi-layer V3 shape)', () => {
    const scores: AutomationConfidenceScores = {
      icd_coding: { status: 'failed', reason: 'credit balance too low' },
      cpt_coding: { status: 'failed', reason: 'credit balance too low' },
      rx_drafting: { status: 'failed', reason: 'credit balance too low' },
      referrals: { status: 'failed', reason: 'credit balance too low' },
      patient_summary: { status: 'failed', reason: 'credit balance too low' },
    };
    const r = detectIncompleteAutomation(scores);
    expect(r.needsReview).toBe(true);
    expect(r.failedLayers).toEqual(['icd_coding', 'cpt_coding', 'rx_drafting']);
    expect(r.reviewReason).toMatch(/icd-coding[\s\S]*cpt-coding[\s\S]*rx-drafting/);
  });

  it('caps reviewReason at 500 chars to protect Postgres row width', () => {
    const longReason = 'x'.repeat(2000);
    const scores: AutomationConfidenceScores = {
      icd_coding: { status: 'failed', reason: longReason },
      cpt_coding: { status: 'failed', reason: longReason },
      rx_drafting: { status: 'failed', reason: longReason },
    };
    const r = detectIncompleteAutomation(scores);
    expect(r.reviewReason!.length).toBeLessThan(
      // Allowed body of "Auto-coding incomplete — …. Click Retry to reprocess." overhead is ~55 chars.
      // Helper caps joined reasons at 500 → total ≤ ~570 chars conservative ceiling.
      600,
    );
  });

  it('caps reasonsByLayer values at 300 chars (audit-log metadata sanity)', () => {
    const longReason = 'y'.repeat(2000);
    const scores: AutomationConfidenceScores = {
      icd_coding: { status: 'failed', reason: longReason },
      cpt_coding: { status: 'ok' },
      rx_drafting: { status: 'ok' },
    };
    const r = detectIncompleteAutomation(scores);
    expect(r.reasonsByLayer.icd_coding!.length).toBe(300);
  });
});

describe('detectIncompleteAutomation — non-load-bearing layers do NOT trigger review', () => {
  it('referrals failure alone does NOT flip needsReview', () => {
    const scores: AutomationConfidenceScores = {
      icd_coding: { status: 'ok' },
      cpt_coding: { status: 'ok' },
      rx_drafting: { status: 'ok' },
      referrals: { status: 'failed', reason: 'transient API error' },
    };
    const r = detectIncompleteAutomation(scores);
    expect(r.needsReview).toBe(false);
    expect(r.failedLayers).toEqual([]);
  });

  it('patient_summary failure alone does NOT flip needsReview', () => {
    const scores: AutomationConfidenceScores = {
      icd_coding: { status: 'ok' },
      cpt_coding: { status: 'ok' },
      rx_drafting: { status: 'ok' },
      patient_summary: { status: 'failed', reason: 'flesch-kincaid validator timeout' },
    };
    const r = detectIncompleteAutomation(scores);
    expect(r.needsReview).toBe(false);
  });

  it('does NOT consider referrals/patient_summary in failedLayers even when all five fail', () => {
    const all_failed: AutomationConfidenceScores = {
      icd_coding: { status: 'failed', reason: 'err' },
      cpt_coding: { status: 'failed', reason: 'err' },
      rx_drafting: { status: 'failed', reason: 'err' },
      referrals: { status: 'failed', reason: 'err' },
      patient_summary: { status: 'failed', reason: 'err' },
    };
    const r = detectIncompleteAutomation(all_failed);
    expect(r.failedLayers).toEqual(['icd_coding', 'cpt_coding', 'rx_drafting']);
    // referrals + patient_summary failures ARE captured in confidenceScores
    // (the source-of-truth column on the visit) but the helper deliberately
    // doesn't surface them in failedLayers because they don't block signing.
  });
});

describe('detectIncompleteAutomation — defensive shapes', () => {
  it('returns no-review for null input', () => {
    const r = detectIncompleteAutomation(null);
    expect(r.needsReview).toBe(false);
    expect(r.failedLayers).toEqual([]);
  });

  it('returns no-review for undefined input', () => {
    const r = detectIncompleteAutomation(undefined);
    expect(r.needsReview).toBe(false);
  });

  it('returns no-review for an empty scores object', () => {
    const r = detectIncompleteAutomation({});
    expect(r.needsReview).toBe(false);
    expect(r.failedLayers).toEqual([]);
  });

  it('treats a load-bearing layer with status=failed but missing reason as "unknown"', () => {
    const scores: AutomationConfidenceScores = {
      // @ts-expect-error — defensive: production code should always
      // supply a reason on failure, but the helper handles the missing
      // case so a partial schema can't crash the worker.
      icd_coding: { status: 'failed' },
    };
    const r = detectIncompleteAutomation(scores);
    expect(r.needsReview).toBe(true);
    expect(r.failedLayers).toEqual(['icd_coding']);
  });
});

describe('LOAD_BEARING_L7_TASKS — registry stability guard', () => {
  it('contains exactly icd_coding, cpt_coding, rx_drafting (in that order)', () => {
    // Order matters for reviewReason readability. If a future change
    // adds or reorders load-bearing tasks, this test flags it so the
    // companion comment in worker/automation-incomplete.ts can be
    // updated.
    expect(LOAD_BEARING_L7_TASKS).toEqual(['icd_coding', 'cpt_coding', 'rx_drafting']);
  });
});

// ── 2026-05-13 extension: empty-codes detection ──────────────────────
// Closes cross-input-mode-audit Finding 2 (UC2 audio_upload). The
// helper now accepts an `outputs` parameter carrying L7a + L7b
// results; when the output is empty despite status:ok the helper
// flags it with cause='empty' so audit-log forensics can separate
// "the layer crashed" from "the model returned nothing."

describe('detectIncompleteAutomation — empty L7a output detection (Finding 2)', () => {
  const okScores: AutomationConfidenceScores = {
    icd_coding: { status: 'ok' },
    cpt_coding: { status: 'ok' },
    rx_drafting: { status: 'ok' },
  };

  // "Healthy" CPT output used as the control field in L7a-focused
  // tests so we can isolate the icd_coding trip from the cpt_coding
  // trip. The helper checks both whenever the caller passes the
  // `outputs` parameter; providing a known-good CPT keeps the
  // assertion focused.
  const healthyCpt = { em: { code: '99213' }, procedures: [] };
  const healthyIcd = { codes: [{ code: 'Z39.2' }] };

  it('SKIPPED cpt_coding + null cptCodes does NOT flip review — imaging/E-M-suppressed visits (F-6)', () => {
    const imagingScores: AutomationConfidenceScores = {
      icd_coding: { status: 'ok' },
      cpt_coding: { status: 'skipped' },
      rx_drafting: { status: 'ok' },
    };
    const r = detectIncompleteAutomation(imagingScores, {
      icdCodes: healthyIcd,
      cptCodes: null, // L7b never ran — column legitimately null
    });
    expect(r.needsReview).toBe(false);
    expect(r.reviewReason).toBeNull();
    expect(r.failedLayers).toEqual([]);
  });

  it('SKIPPED icd_coding + null icdCodes does NOT flip review — TM_ENABLE_ICD_CPT=false (F-6)', () => {
    const disabledScores: AutomationConfidenceScores = {
      icd_coding: { status: 'skipped' },
      cpt_coding: { status: 'skipped' },
      rx_drafting: { status: 'ok' },
    };
    const r = detectIncompleteAutomation(disabledScores, {
      icdCodes: null,
      cptCodes: null,
    });
    expect(r.needsReview).toBe(false);
    expect(r.failedLayers).toEqual([]);
  });

  it('flags review when icdCodes is null', () => {
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: null,
      cptCodes: healthyCpt,
    });
    expect(r.needsReview).toBe(true);
    expect(r.failedLayers).toEqual(['icd_coding']);
    expect(r.causeByLayer.icd_coding).toBe('empty');
    expect(r.reviewReason).toMatch(/icd-coding: returned empty codes array/);
  });

  it('flags review when icdCodes.codes is []', () => {
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: { codes: [] },
      cptCodes: healthyCpt,
    });
    expect(r.needsReview).toBe(true);
    expect(r.causeByLayer.icd_coding).toBe('empty');
  });

  it('flags review when icdCodes.codes is missing entirely', () => {
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: {},
      cptCodes: healthyCpt,
    });
    expect(r.needsReview).toBe(true);
    expect(r.causeByLayer.icd_coding).toBe('empty');
  });

  it('does NOT flag review when icdCodes has ≥1 code', () => {
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: healthyIcd,
      cptCodes: healthyCpt,
    });
    expect(r.needsReview).toBe(false);
  });

  it('icd_coding=failed wins over empty when both apply (preserves "failed" semantics)', () => {
    // If L7a threw AND wrote nothing, the cause should be reported as
    // 'failed' (the actionable signal) not 'empty' (the consequence).
    const scores: AutomationConfidenceScores = {
      icd_coding: { status: 'failed', reason: 'Anthropic 529 overload' },
      cpt_coding: { status: 'ok' },
      rx_drafting: { status: 'ok' },
    };
    const r = detectIncompleteAutomation(scores, {
      icdCodes: { codes: [] },
      cptCodes: healthyCpt,
    });
    expect(r.needsReview).toBe(true);
    expect(r.causeByLayer.icd_coding).toBe('failed');
    expect(r.reasonsByLayer.icd_coding).toBe('Anthropic 529 overload');
  });
});

describe('detectIncompleteAutomation — empty L7b output detection (Finding 2)', () => {
  const okScores: AutomationConfidenceScores = {
    icd_coding: { status: 'ok' },
    cpt_coding: { status: 'ok' },
    rx_drafting: { status: 'ok' },
  };

  it('flags review when cptCodes is null', () => {
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: { codes: [{ code: 'Z39.2' }] },
      cptCodes: null,
    });
    expect(r.needsReview).toBe(true);
    expect(r.causeByLayer.cpt_coding).toBe('empty');
    expect(r.reviewReason).toMatch(/cpt-coding: no E&M code emitted/);
  });

  it('flags review when cptCodes.em is missing', () => {
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: { codes: [{ code: 'Z39.2' }] },
      cptCodes: { procedures: [{ code: '99213' }] },
    });
    expect(r.needsReview).toBe(true);
    expect(r.causeByLayer.cpt_coding).toBe('empty');
  });

  it('flags review when cptCodes.em.code is empty string', () => {
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: { codes: [{ code: 'Z39.2' }] },
      cptCodes: { em: { code: '   ' } },
    });
    expect(r.needsReview).toBe(true);
    expect(r.causeByLayer.cpt_coding).toBe('empty');
  });

  it('does NOT flag review when em.code is a non-empty string + procedures empty', () => {
    // Many established-patient visits legitimately bill only the E&M
    // tier with no procedures — that must NOT trip the empty-codes guard.
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: { codes: [{ code: 'Z39.2' }] },
      cptCodes: { em: { code: '99213' }, procedures: [] },
    });
    expect(r.needsReview).toBe(false);
  });
});

describe('detectIncompleteAutomation — both L7a + L7b empty (UC2-style)', () => {
  it('flags review with BOTH layers in failedLayers + both causes=empty', () => {
    const okScores: AutomationConfidenceScores = {
      icd_coding: { status: 'ok' },
      cpt_coding: { status: 'ok' },
      rx_drafting: { status: 'ok' },
    };
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: { codes: [] },
      cptCodes: null,
    });
    expect(r.needsReview).toBe(true);
    expect(r.failedLayers).toContain('icd_coding');
    expect(r.failedLayers).toContain('cpt_coding');
    expect(r.causeByLayer.icd_coding).toBe('empty');
    expect(r.causeByLayer.cpt_coding).toBe('empty');
    expect(r.reviewReason).toMatch(/icd-coding[\s\S]*cpt-coding/);
  });
});

describe('detectIncompleteAutomation — Rx is intentionally NOT subject to empty-check', () => {
  it('empty rxDrafts does NOT flag review (many visits have no Rx legitimately)', () => {
    const okScores: AutomationConfidenceScores = {
      icd_coding: { status: 'ok' },
      cpt_coding: { status: 'ok' },
      rx_drafting: { status: 'ok' },
    };
    // Derm-biopsy follow-up, screening encounter, etc. — empty Rx is normal.
    // We pass valid icd + cpt so only the (intentionally-missing) rx
    // empty-check would be the only way this could trip — confirming
    // the helper does NOT trip on rx emptiness.
    const r = detectIncompleteAutomation(okScores, {
      icdCodes: { codes: [{ code: 'Z12.83' }] },
      cptCodes: { em: { code: '99213' }, procedures: [] },
    });
    expect(r.needsReview).toBe(false);
  });
});

describe('detectIncompleteAutomation — backwards-compatible single-arg call', () => {
  it('callers that pass only scores get the historic failed-only behavior', () => {
    const scores: AutomationConfidenceScores = {
      icd_coding: { status: 'ok' },
      cpt_coding: { status: 'ok' },
      rx_drafting: { status: 'ok' },
    };
    // No outputs passed → empty-codes detection is silent. This is the
    // T-M14 behavior every existing test in this file relies on.
    const r = detectIncompleteAutomation(scores);
    expect(r.needsReview).toBe(false);
  });
});
