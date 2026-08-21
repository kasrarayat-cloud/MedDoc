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

/**
 * ⚠️ THIS FIXTURE CARRIES A DERIVABLE VENOUS MEASUREMENT ROW ON PURPOSE — F5-i,
 * AND ITS ABSENCE SILENTLY HOLLOWED OUT THIS FILE.
 *
 * It used to hold ONE field: `originalLabel: 'Findings'`,
 * `clinicalConcept: 'exam.vascular'`. F5-i made `deriveVerificationEncounter`
 * REFUSE a form with no `measurement.*` rows, so `runAutoCertifyTwin` began
 * returning `proof_failed` **before ever reaching `runTemplateTwinSyntheticTest`**.
 *
 * Four arms went red and said so. TWO PASSED — and they are the dangerous half:
 *
 *   · "⚠️ THE ROUND-TRIP PROOF FAILS -> NOTHING CERTIFIES" — asserts
 *     `proof_failed` and `certify not called`, and an early refusal satisfies
 *     BOTH. This file's own header calls it "THE ARM THAT MATTERS MOST IN THE
 *     WHOLE FEATURE"; it would have gone on passing while never once exercising
 *     the round-trip proof.
 *   · "the CONFIRMED MAPPINGS SURVIVE a failed proof" — same shape.
 *
 * A guard that passes because it never reached the code it guards is
 * indistinguishable from one that works. So the fixture is now DERIVABLE, and
 * the refusal has its own arm below with its own fixture.
 */
const DERIVABLE_WORKSPACE = () => ({
  template: { encounterType: 'ultrasound', certificationStatus: 'needs_confirmation' },
  mappingsSha256: 'sha-before',
  fields: [
    {
      definitionId: 'd1',
      field: { fieldId: 'f1', originalLabel: 'Findings', criticality: 'routine' },
      mapping: { sourceType: 'extraction', clinicalConcept: 'exam.vascular', status: 'needs_confirmation' },
    },
    {
      definitionId: 'd2',
      field: { fieldId: 'f2', originalLabel: 'GSV at the SFJ', criticality: 'routine' },
      mapping: {
        sourceType: 'extraction',
        clinicalConcept: 'measurement.diameter',
        status: 'needs_confirmation',
      },
    },
  ],
});

const readSpy = vi.fn(async () => DERIVABLE_WORKSPACE());

vi.mock('@/lib/template-twin/workspace-read', () => ({
  readTemplateTwinWorkspace: readSpy,
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
  readSpy.mockReset();
  readSpy.mockImplementation(async () => DERIVABLE_WORKSPACE());
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

  /**
   * ⚠️ THE LIFECYCLE GATE IS A SECOND REFUSER, AND IT USED TO ESCAPE.
   * `certifyAndActivateTemplateTwin` runs its own final checks (fill coverage,
   * measurement-cell coverage). That call was unwrapped, so its refusal left as
   * an unhandled throw: a FAILED worker job with no audit row and no reason.
   * Found by the QA walk, not by this file — which is why the arm exists now.
   */
  it('a LIFECYCLE refusal lands as needs-review, not as a crashed job', async () => {
    testSpy.mockResolvedValueOnce(undefined);
    certifySpy.mockRejectedValueOnce(
      new Error('Confirm every field, clear blocking structure, and verify a synthetic DOCX.'),
    );
    const { runAutoCertifyTwin } = await import('../auto-certify-twin-job');

    const res = await runAutoCertifyTwin(payload as never);

    expect(res.status).toBe('proof_failed');
    expect(res.reason).toMatch(/synthetic DOCX/);
    const calls = auditSpy.mock.calls.map((c) => c[0]);
    expect(calls.some((c) => c.metadata?.stage === 'certify')).toBe(true);
  });

  /**
   * F5-i — A FORM WE CANNOT SELF-TEST IS REFUSED BEFORE ANY PROOF RUNS.
   *
   * ⚠️ THE LOAD-BEARING ASSERTION IS `testSpy` NOT BEING CALLED, not the status.
   * `proof_failed` is what four other arms already assert, and an early refusal
   * satisfies it for a completely different reason — which is exactly how this
   * change hollowed out the arms above. Asserting that the round-trip proof was
   * never REACHED is the only claim that distinguishes this path from those.
   */
  it('⚠️ a form with no measurement rows REFUSES WITHOUT RUNNING THE PROOF', async () => {
    readSpy.mockImplementation(async () => ({
      ...DERIVABLE_WORKSPACE(),
      // A table-less form: an operative note, a SOAP template. Nothing here can
      // be dictated, and the old code answered with a VENOUS reflux study.
      fields: [
        {
          definitionId: 'd1',
          field: { fieldId: 'f1', originalLabel: 'Findings', criticality: 'routine' },
          mapping: {
            sourceType: 'extraction',
            clinicalConcept: 'exam.vascular',
            status: 'needs_confirmation',
          },
        },
      ],
    }));
    const { runAutoCertifyTwin } = await import('../auto-certify-twin-job');
    const res = await runAutoCertifyTwin(payload as never);

    expect(testSpy).not.toHaveBeenCalled();
    expect(certifySpy).not.toHaveBeenCalled();
    expect(res.status).toBe('proof_failed');
    expect(res.reason).toBe('ENCOUNTER_NOT_DERIVABLE:no_measurement_rows');

    // The refusal is AUDITED with a stage that distinguishes it from a proof
    // that ran and failed — "we never tested your form" must not read as
    // "your form was tested".
    const calls = auditSpy.mock.calls.map((c) => c[0]);
    expect(calls.some((c) => c.metadata?.stage === 'derive_encounter')).toBe(true);
    expect(JSON.stringify(calls)).not.toMatch(/synthetic_test/);
  });

  /**
   * ⚠️ THE CONTROL FOR THE ARM ABOVE. Without it, a change that refused EVERY
   * template would satisfy every refusal arm in this file. This asserts the
   * derivable fixture really does reach the proof — so "not called" above is a
   * measurement rather than a constant.
   */
  it('⚠️ POSITIVE CONTROL: a DERIVABLE form DOES reach the round-trip proof', async () => {
    testSpy.mockResolvedValueOnce(undefined);
    const { runAutoCertifyTwin } = await import('../auto-certify-twin-job');
    await runAutoCertifyTwin(payload as never);

    expect(testSpy).toHaveBeenCalledTimes(1);
    // and it was handed a dictation derived from THIS form's own row, not a
    // constant — the property F5-c established and F5-i must not regress.
    expect(testSpy.mock.calls[0][0].encounterText).toContain('Right GSV at the SFJ');
  });
});
