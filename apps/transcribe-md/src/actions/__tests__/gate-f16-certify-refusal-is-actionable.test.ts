// ============================================================================
// F16 GATE, ACTION LEVEL — the arm the first version of this guard did not have.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS FILE EXISTS, STATED AS A MEASUREMENT RATHER THAN A WORRY.
//
// F16's first gate lived entirely in `src/lib/template-twin/__tests__/` and
// imported ONLY the two new leaf modules. It never loaded `synthetic-test.ts`
// and never loaded `template-twin-certify.ts`. The independent adversarial pass
// enumerated the PARTIAL landings of the fix — the one-file versions a tired
// session actually ships — applied each one, asserted the mutation applied, and
// ran the suite:
//
//   | the half that landed                          | what the physician gets        | gate |
//   |-----------------------------------------------|--------------------------------|------|
//   | counts land, certify ladder branch does NOT   | the 2026-08-17 sentence, verbatim | 7 passed |
//   | ladder lands, throw carries no detail         | "some fields still need confirming" — NO NUMBER | 7 passed |
//   | message helper lands, action returns the old literal | the 2026-08-17 sentence, verbatim | 7 passed |
//
// Three of four, green. A guard proven only against the COMPLETE inverse has
// proved the tidy case; the failure that ships is the half-landed fix.
//
// ⚠️ AND THE OLD ARM NAMED "never tells the doctor the refusal is somebody
// else's to fix" ASSERTED ON A PURE FUNCTION. It could not observe whether the
// action ever CALLED that function — a title that is WIDER than what it
// measures. Every arm below goes through `certifyNativeTemplateAction` itself,
// so the claim and the measurement are the same claim.
//
// WHAT THIS DOES NOT GUARD, said plainly:
//   · Not RENDERING. It asserts what the action returns; the single consumer
//     (`native-template-manager.tsx:127`) does `setError(res.error)` and renders
//     it at `:283`, which is checked structurally in the lib-level gate, not
//     here.
//   · The audit assertion is a SPY, not a row in `audit_logs`. A fire-and-forget
//     writer is only fully proved by reading the row back; that needs an E2E.
//     This proves the call is made with the right shape, which is strictly more
//     than the previous zero.
// ============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';

import { ENCOUNTER_NOT_DERIVABLE_REASONS } from '@/lib/template-twin/verification-encounter';

const h = vi.hoisted(() => {
  // Faithful stubs for the classes the action only ever `instanceof`-checks.
  // Spreading the real modules would drag prisma and the twin runtime into a
  // test about ONE action's control flow — the sibling
  // `template-twin-mappings-action.test.ts` records that this is what made its
  // first version fail to load at all.
  class LifecycleError extends Error {
    readonly code: string;
    constructor(code: string, message: string) {
      super(message);
      this.name = 'TemplateTwinLifecycleError';
      this.code = code;
    }
  }
  class DraftError extends Error {
    readonly code: string;
    constructor(code: string, message: string) {
      super(message);
      this.name = 'TemplateTwinDraftError';
      this.code = code;
    }
  }
  class DocxError extends Error {}
  class PhiError extends Error {}
  return {
    requireSession: vi.fn(),
    enabled: vi.fn(() => true),
    readWorkspace: vi.fn(),
    runSynthetic: vi.fn(),
    certify: vi.fn(),
    logTwinAudit: vi.fn(),
    extract: vi.fn(),
    makeGenerator: vi.fn(() => vi.fn()),
    sendEmail: vi.fn(),
    emailEnabled: vi.fn(() => false),
    createDraft: vi.fn(),
    LifecycleError,
    DraftError,
    DocxError,
    PhiError,
  };
});

vi.mock('@/lib/auth', () => ({ requireSession: h.requireSession }));
vi.mock('@/config/template-native-docx', () => ({ templateNativeDocxEnabled: h.enabled }));
vi.mock('@/lib/template-twin/workspace-read', () => ({
  readTemplateTwinWorkspace: h.readWorkspace,
}));
vi.mock('@/lib/template-twin/create-draft', () => ({
  createTemplateTwinDraft: h.createDraft,
  TemplateTwinDraftError: h.DraftError,
}));
vi.mock('@/lib/template-twin/certification-lifecycle', () => ({
  certifyAndActivateTemplateTwin: h.certify,
  TemplateTwinLifecycleError: h.LifecycleError,
}));
// ⚠️ THE ERROR CLASS HERE IS THE **REAL** ONE, AND THAT IS ONLY POSSIBLE
// BECAUSE F16 SPLIT IT INTO A LEAF MODULE. Importing the real
// `synthetic-test.ts` would pull prisma, storage, the fill engine and the docx
// parser into this file; importing `./synthetic-test-error` pulls nothing. So
// the `instanceof` on the action's ladder is exercised against the class
// production actually throws, and `blocking.length` / `totalFields` flow through
// the genuine constructor defaults rather than a stub's.
vi.mock('@/lib/template-twin/synthetic-test', async () => {
  const leaf = await vi.importActual<
    typeof import('@/lib/template-twin/synthetic-test-error')
  >('@/lib/template-twin/synthetic-test-error');
  return {
    runTemplateTwinSyntheticTest: h.runSynthetic,
    TemplateTwinSyntheticTestError: leaf.TemplateTwinSyntheticTestError,
  };
});
vi.mock('@/lib/note-template-docx', () => ({ TemplateDocxError: h.DocxError }));
vi.mock('@/lib/template-twin/source-phi', () => ({ TemplateTwinPhiRejectedError: h.PhiError }));
vi.mock('@/lib/email', () => ({ sendTemplateCertifiedEmail: h.sendEmail }));
vi.mock('@/lib/email-enabled', () => ({ isEmailDeliveryEnabled: h.emailEnabled }));
vi.mock('@/lib/template-twin/twin-audit', () => ({ logTwinAudit: h.logTwinAudit }));
vi.mock('@/worker/layers/03-extract-entities', () => ({
  extractTemplateTwinEntities: h.extract,
}));
vi.mock('@/worker/template-twin-note-generator', () => ({
  createEphemeralVisitNoteGenerator: h.makeGenerator,
}));

import { certifyNativeTemplateAction } from '@/actions/template-twin-certify';
import { TemplateTwinSyntheticTestError } from '@/lib/template-twin/synthetic-test-error';

const SHA = 'a'.repeat(64);

/** The production shape, verbatim. Measured 2026-08-17/18: the single compiled
 *  twin on production has 80 fields, 74 `CERTIFIED` and 6 `NEEDS_CONFIRMATION`,
 *  and the physician stopped after two refusals. */
const SIX_OF_EIGHTY = () =>
  new TemplateTwinSyntheticTestError(
    'MAPPINGS_NOT_READY',
    'Every field needs a physician-confirmed mapping before testing.',
    {
      blocking: [
        'ttf_346a0ce8e5a68a910de138a6:unconfirmed',
        'ttf_5d84f80e2fec3d0085ad6b33:unconfirmed',
        'ttf_0000000000000000000000c3:unconfirmed',
        'ttf_0000000000000000000000c4:unconfirmed',
        'ttf_0000000000000000000000c5:unconfirmed',
        'ttf_0000000000000000000000c6:no_concept',
      ],
      totalFields: 80,
    },
  );

/** The sentence the physician actually saw, twice, on 2026-08-17. */
const OLD_SCARY = 'will not succeed on a retry until it is fixed';

beforeEach(() => {
  vi.clearAllMocks();
  h.enabled.mockReturnValue(true);
  h.emailEnabled.mockReturnValue(false);
  h.requireSession.mockResolvedValue({
    user: {
      id: 'doc_1',
      email: 'd@example.invalid',
      fullName: 'Dr Example',
      practiceId: 'prac_1',
    },
  });
  // null => no fresh proof => the action runs the synthetic test, which is the
  // call that throws MAPPINGS_NOT_READY.
  h.readWorkspace.mockResolvedValue(null);
});

describe('F16 action gate — a DESIGNED refusal reaches the doctor as work they can do', () => {
  it('returns the typed reason, the counts, and a sentence carrying "6 of 80"', async () => {
    h.runSynthetic.mockRejectedValue(SIX_OF_EIGHTY());

    const res = await certifyNativeTemplateAction('tmpl_1', SHA);

    expect(res.ok).toBe(false);
    if (res.ok) throw new Error('unreachable');
    // ⚠️ THE TYPED REASON. Nothing asserted this before, so the whole ladder
    // branch could vanish and the old gate stayed green.
    expect(res.reason).toBe('mappings_not_ready');
    expect(res.remaining).toBe(6);
    expect(res.totalFields).toBe(80);
    // ⚠️ AND THE SENTENCE ITSELF, FROM THE ACTION — not from the helper called
    // directly. This is the arm that reddens when the action returns the old
    // literal while the helper sits orphaned.
    expect(res.error).toContain('6 of 80 fields still need confirming');
  });

  it('never returns the 2026-08-17 sentence for this refusal', async () => {
    h.runSynthetic.mockRejectedValue(SIX_OF_EIGHTY());

    const res = await certifyNativeTemplateAction('tmpl_1', SHA);

    expect(res.ok).toBe(false);
    if (res.ok) throw new Error('unreachable');
    expect(res.error).not.toContain(OLD_SCARY);
    expect(res.error).not.toContain('could not be completed');
    // the raw code is an engineer's token and never the doctor's word
    expect(res.error).not.toContain('MAPPINGS_NOT_READY');
    expect(res.error?.toLowerCase()).toContain('confirm');
  });

  // ⚠️ THE PARTIAL-LANDING ARM. If `synthetic-test.ts` regresses to throwing
  // without `{blocking, totalFields}` — the first edit someone reverting the
  // "collect, do not throw on the first" rewrite would make — then
  // `err.blocking.length` is 0 and the doctor loses the NUMBER, which is F16's
  // entire product. The old gate was green on exactly this.
  it('a detail-less throw is a FINDING, not a silently vaguer sentence', async () => {
    h.runSynthetic.mockRejectedValue(
      new TemplateTwinSyntheticTestError(
        'MAPPINGS_NOT_READY',
        'Every field needs a physician-confirmed mapping before testing.',
      ),
    );

    const res = await certifyNativeTemplateAction('tmpl_1', SHA);

    expect(res.ok).toBe(false);
    if (res.ok) throw new Error('unreachable');
    // It still takes the designed-refusal branch — the classification is right…
    expect(res.reason).toBe('mappings_not_ready');
    // …and THIS is the assertion that fails if the counts stop arriving.
    // `toBe`, not `toContain`: the expected value is knowable.
    expect(res.remaining).toBe(0);
    expect(res.error).toBe(
      'Not yet — some fields still need confirming. In the field list below, ' +
        'confirm the ones still marked as needing review, then certify again.',
    );
  });

  it('audits the refusal with ids and reason codes — never the message as the doctor sees it', async () => {
    h.runSynthetic.mockRejectedValue(SIX_OF_EIGHTY());

    await certifyNativeTemplateAction('tmpl_1', SHA);

    expect(h.logTwinAudit).toHaveBeenCalledTimes(1);
    const entry = h.logTwinAudit.mock.calls[0][0];
    expect(entry.action).toBe('TEMPLATE_TWIN_CERTIFY_FAILED');
    expect(entry.success).toBe(false);
    expect(entry.errorCode).toBe('MAPPINGS_NOT_READY');
    expect(entry.targetId).toBe('tmpl_1');
    expect(entry.metadata.totalFields).toBe(80);
    expect(entry.metadata.blocking).toHaveLength(6);
    // ⚠️ EVERY ENTRY IS `<opaque id>:<closed reason code>`. This is the arm that
    // reddens if anyone widens `blocking` to carry a label or free text onto
    // the cross-tenant admin activity stream.
    for (const b of entry.metadata.blocking as string[]) {
      expect(b).toMatch(/^ttf_[a-z0-9]+:(no_mapping|unconfirmed|no_concept)$/);
    }
  });

  // ⚠️ NON-VACUITY / DISCRIMINATION. Every arm above asserts on a REFUSAL, so a
  // mock that rejected everything would satisfy all of them. This proves the
  // harness can also produce a SUCCESS — i.e. the arms above are reporting the
  // refusal path, not the only path the mocks allow.
  it('POSITIVE CONTROL — the same harness certifies when nothing refuses', async () => {
    h.runSynthetic.mockResolvedValue(undefined);
    h.certify.mockResolvedValue({
      template: { id: 'tmpl_1', name: 'WM IOV', certificationStatus: 'certified' },
    });

    const res = await certifyNativeTemplateAction('tmpl_1', SHA);

    expect(res.ok).toBe(true);
    expect(h.logTwinAudit).not.toHaveBeenCalled();
  });

  // ⚠️ AND THE OTHER DIRECTION: a DIFFERENT synthetic-test code must NOT be
  // dressed up as an actionable mapping refusal. Widening the branch to catch
  // every `TemplateTwinSyntheticTestError` would tell a doctor to go and
  // confirm fields when the real failure was, say, rejected synthetic evidence.
  it('only MAPPINGS_NOT_READY takes the actionable branch', async () => {
    h.runSynthetic.mockRejectedValue(
      new TemplateTwinSyntheticTestError(
        'SYNTHETIC_EVIDENCE_REJECTED',
        'The synthetic proof did not round-trip.',
      ),
    );

    const res = await certifyNativeTemplateAction('tmpl_1', SHA);

    expect(res.ok).toBe(false);
    if (res.ok) throw new Error('unreachable');
    expect(res.reason).not.toBe('mappings_not_ready');
    expect(res.error).not.toContain('still need confirming');
  });
});

/**
 * F5-i, ACTION LEVEL — "we cannot self-test this KIND of form" is its own
 * refusal, and it must never displace one the doctor can act on.
 *
 * ⚠️ THIS BLOCK EXISTS BECAUSE THE FIRST DRAFT OF F5-i SHIPPED THE DISPLACEMENT
 * AND NOTHING IN THE REPOSITORY COULD SEE IT. The adversarial pass enumerated
 * the partial landings and found the manual caller's refusal, its error code
 * and its ladder branch had **no coverage in any direction** — a mutation
 * re-pointing this caller at the retired venous fallback left `tsc` at exit 0
 * and every suite green.
 *
 * The defect it shipped was F16's own, inverted. The draft derived the
 * encounter EAGERLY, before `runTemplateTwinSyntheticTest`, so a physician with
 * six unconfirmed fields was told their FORM could not be self-tested — while
 * their mappings were emphatically not fine, and the sentence told them to stop
 * doing the one thing that would unblock them.
 */
describe('F5-i action gate — an undeclarable self-test never displaces actionable work', () => {
  /**
   * ⚠️ THE REGRESSION GUARD, AND THE MOST IMPORTANT ARM HERE.
   *
   * `readWorkspace` resolves null, so the action's field list is `[]` — the
   * exact input that makes `deriveVerificationEncounter` answer
   * `no_measurement_rows`. If anyone moves the derivation back above the
   * readiness gates, this arm goes red immediately, because the doctor stops
   * being told about their six fields.
   */
  it('⚠️ MAPPINGS_NOT_READY still wins over an underivable encounter', async () => {
    h.runSynthetic.mockRejectedValue(SIX_OF_EIGHTY());

    const res = await certifyNativeTemplateAction('tmpl_1', SHA);

    expect(res.ok).toBe(false);
    if (res.ok) throw new Error('unreachable');
    expect(res.reason).toBe('mappings_not_ready');
    expect(res.error).toContain('6 of 80');
    expect(res.error).not.toContain('not one we can self-test');
  });

  /**
   * ⚠️ AND THE ORDER IS ENFORCED BY LAZINESS, NOT BY CONVENTION. The action
   * hands a THUNK down; the proof evaluates it below its own readiness gates.
   * A caller that resolved it eagerly would re-introduce the arm above's
   * defect, so this asserts the value crossing the boundary is a function AND
   * that the action never called it itself.
   */
  it('⚠️ the action passes a THUNK and does not evaluate it', async () => {
    h.runSynthetic.mockResolvedValue(undefined);
    h.certify.mockResolvedValue({
      template: { id: 'tmpl_1', name: 'WM IOV', certificationStatus: 'certified' },
    });

    await certifyNativeTemplateAction('tmpl_1', SHA);

    const arg = h.runSynthetic.mock.calls[0][0];
    expect(typeof arg.deriveEncounter).toBe('function');
    // and there is no eagerly-computed string anywhere on the payload — the
    // property whose absence is the whole fix.
    expect(arg.encounterText).toBeUndefined();
  });

  it('an ENCOUNTER_NOT_DERIVABLE refusal reaches the doctor as its own reason', async () => {
    h.runSynthetic.mockRejectedValue(
      new TemplateTwinSyntheticTestError(
        'ENCOUNTER_NOT_DERIVABLE',
        'We could not generate a self-test that matches this form, so nothing was certified.',
        { blocking: ['no_addressable_fields'], totalFields: 12 },
      ),
    );

    const res = await certifyNativeTemplateAction('tmpl_1', SHA);

    expect(res.ok).toBe(false);
    if (res.ok) throw new Error('unreachable');
    expect(res.reason).toBe('encounter_not_derivable');
    // ⚠️ NOT the 2026-08-17 sentence. This is a known limit of the generator,
    // not a fault under repair, and it asks nothing of the doctor.
    expect(res.error).not.toContain(OLD_SCARY);
    expect(res.error).not.toContain('still need confirming');
  });

  it('audits it with its own code and its closed-union reason — never free text', async () => {
    h.runSynthetic.mockRejectedValue(
      new TemplateTwinSyntheticTestError(
        'ENCOUNTER_NOT_DERIVABLE',
        'We could not generate a self-test that matches this form, so nothing was certified.',
        { blocking: ['unsupported_study_type'], totalFields: 3 },
      ),
    );

    await certifyNativeTemplateAction('tmpl_1', SHA);

    expect(h.logTwinAudit).toHaveBeenCalled();
    const entry = h.logTwinAudit.mock.calls[0][0];
    expect(entry.action).toBe('TEMPLATE_TWIN_CERTIFY_FAILED');
    expect(entry.success).toBe(false);
    expect(entry.errorCode).toBe('ENCOUNTER_NOT_DERIVABLE');
    expect(entry.metadata.blocking).toEqual(['unsupported_study_type']);
    // ⚠️ THE CROSS-TENANT CONSTRAINT, ASSERTED RATHER THAN NOTED. `logAudit`
    // fans this row out to every subscribed SUPER_ADMIN, so `blocking` may
    // carry opaque ids and closed reason codes and NOTHING else. A field label
    // arriving here would be a customer's form leaking across tenants.
    // ⚠️ THE SET IS IMPORTED, NOT RETYPED — F5-i-2. This array used to be three
    // string literals copied from the union by hand, so it could drift from the
    // vocabulary in BOTH directions without anything failing: a new reason would
    // be rejected as though it were a leak, and a RETIRED one would go on being
    // admitted. It drifted the moment `no_measurement_rows` was replaced.
    // `ENCOUNTER_NOT_DERIVABLE_REASONS` is now the single source and the union
    // is derived from it.
    expect(ENCOUNTER_NOT_DERIVABLE_REASONS.length).toBeGreaterThan(0);
    for (const b of entry.metadata.blocking) {
      expect([...ENCOUNTER_NOT_DERIVABLE_REASONS]).toContain(b);
    }
  });
});
