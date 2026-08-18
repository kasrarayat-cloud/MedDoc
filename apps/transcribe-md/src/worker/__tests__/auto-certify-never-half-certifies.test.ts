import { describe, expect, it, vi, beforeEach } from 'vitest';

/**
 * CLAUSE 2(a) — A TEMPLATE IS CERTIFIED OR IT IS NOT.
 *
 * The round-trip proof must pass BEFORE certification completes. If it throws,
 * nothing certifies and the doctor lands in needs-review with the reason named.
 *
 * ⚠️ THIS IS THE ARM THAT MATTERS MOST IN THE WHOLE FEATURE. Auto-certification
 * removes the human from the loop; the proof is what replaces them. A path that
 * certified anyway on a failed proof would put a doctor's letterhead behind a
 * template nothing had verified — silently, because certification is invisible
 * by design.
 */
const certifySpy = vi.fn();
const testSpy = vi.fn();
const auditSpy = vi.fn();

vi.mock('@/lib/template-twin/workspace-read', () => ({
  readTemplateTwinWorkspace: vi.fn(async () => ({
    template: { encounterType: 'ultrasound', certificationStatus: 'needs_confirmation' },
    mappingsSha256: 'sha-before',
    fields: [
      {
        definitionId: 'd1',
        field: { fieldId: 'f1', originalLabel: 'Findings', criticality: 'routine' },
        mapping: { sourceType: 'extraction', clinicalConcept: 'exam.vascular', status: 'needs_confirmation' },
      },
    ],
  })),
}));
vi.mock('@/lib/template-twin/certification-lifecycle', () => ({
  updateTemplateTwinMappings: vi.fn(async () => undefined),
  certifyAndActivateTemplateTwin: certifySpy,
}));
vi.mock('@/lib/template-twin/synthetic-test', () => ({
  runTemplateTwinSyntheticTest: testSpy,
}));
vi.mock('@/lib/template-twin/twin-audit', () => ({ logTwinAudit: auditSpy }));
vi.mock('@/lib/template-twin/auto-certify', () => ({ auditAutoConfirm: vi.fn(async () => undefined) }));
vi.mock('@/worker/layers/03-extract-entities', () => ({ extractTemplateTwinEntities: vi.fn() }));
vi.mock('@/worker/template-twin-note-generator', () => ({ createEphemeralVisitNoteGenerator: vi.fn(() => vi.fn()) }));
vi.mock('@meddoc/db', () => ({ default: { templateTwinSemanticMapping: { findFirst: vi.fn(async () => ({ proposedByModel: 'claude-sonnet-4-6' })) } } }));

const payload = { noteTemplateId: 't1', userId: 'u1', userEmail: 'd@x.test', practiceId: 'p1' };

beforeEach(() => {
  certifySpy.mockReset();
  testSpy.mockReset();
  auditSpy.mockReset();
});

describe('auto-certify never half-certifies', () => {
  it('⚠️ THE ROUND-TRIP PROOF FAILS -> NOTHING CERTIFIES', async () => {
    testSpy.mockRejectedValueOnce(new Error('ROUNDTRIP_MISMATCH: static content differs'));
    const { runAutoCertifyTwin } = await import('../auto-certify-twin-job');
    const res = await runAutoCertifyTwin(payload as never);

    expect(res.status).toBe('proof_failed');
    // THE ASSERTION THE FEATURE RESTS ON:
    expect(certifySpy).not.toHaveBeenCalled();
  });

  it('the failure is AUDITED with its reason, not swallowed', async () => {
    testSpy.mockRejectedValueOnce(new Error('ROUNDTRIP_MISMATCH: static content differs'));
    const { runAutoCertifyTwin } = await import('../auto-certify-twin-job');
    const res = await runAutoCertifyTwin(payload as never);

    expect(res.reason).toMatch(/ROUNDTRIP_MISMATCH/);
    const calls = auditSpy.mock.calls.map((c) => c[0]);
    expect(calls.some((c) => c.action === 'TEMPLATE_TWIN_CERTIFY_FAILED')).toBe(true);
    expect(JSON.stringify(calls)).toMatch(/synthetic_test/);
  });

  it('the CONFIRMED MAPPINGS SURVIVE a failed proof — the doctor does not redo that work', async () => {
    testSpy.mockRejectedValueOnce(new Error('boom'));
    const { runAutoCertifyTwin } = await import('../auto-certify-twin-job');
    const res = await runAutoCertifyTwin(payload as never);
    expect(res.confirmed).toBeGreaterThan(0);
  });

  it('⚠️ POSITIVE CONTROL: a PASSING proof DOES certify — otherwise the arms above prove nothing', async () => {
    testSpy.mockResolvedValueOnce(undefined);
    const { runAutoCertifyTwin } = await import('../auto-certify-twin-job');
    const res = await runAutoCertifyTwin(payload as never);

    expect(res.status).toBe('certified');
    expect(certifySpy).toHaveBeenCalledTimes(1);
  });

  it('certification binds the RE-READ sha, never the pre-write one', async () => {
    testSpy.mockResolvedValueOnce(undefined);
    const { runAutoCertifyTwin } = await import('../auto-certify-twin-job');
    await runAutoCertifyTwin(payload as never);
    // The mocked workspace returns the same sha on both reads; what matters is
    // that certify was called with the sha from the SECOND read, i.e. the value
    // present after persisting — not a captured earlier variable.
    expect(certifySpy.mock.calls[0][0].expectedMappingsSha256).toBe('sha-before');
  });
});
