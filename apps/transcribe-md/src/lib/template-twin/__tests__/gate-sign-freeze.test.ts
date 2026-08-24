import { describe, expect, it, vi, beforeEach } from 'vitest';

/**
 * F5-f RULING 1, SIGN HALF — REGENERATE-THEN-SIGN, BOUNDED, FAIL-OPEN.
 *
 * `native-export` declines a stale manifest, so a stale document is never
 * SERVED. But a visit signed while stale is frozen stale: afterwards the compute
 * path refuses to recompute (`visit_not_eligible`), so the doctor's own
 * letterhead is unavailable on their own signed record, permanently.
 *
 * The refresh therefore happens BEFORE the signature is written. Ruled shape:
 *   fresh      -> sign unchanged, ZERO added work
 *   stale      -> re-fill under a bounded budget, pair frozen by construction
 *   can't      -> SIGN STILL PROCEEDS, styled, reason in the audit row AND in
 *                 the response. A formatting subsystem never blocks a signature;
 *                 silence about the downgrade is the only forbidden outcome.
 */
const findFirst = vi.fn();
const processFill = vi.fn();
/**
 * F24-S5 — the override half of the bound identity.
 *
 * ⚠️ THIS SPY IS THE ARM THE REFUTATION ASKED FOR. The adversarial pass killed
 * the first build by driving this very function and observing
 * `templateTwinFieldOverride.findMany` called ZERO times: the freeze answered
 * `already_fresh` on a note-only comparison and the correction never reached the
 * document. Mocking it as a spy makes that observable here rather than only
 * under a hand-built harness.
 */
const overrideFindMany = vi.fn();

vi.mock('@meddoc/db', () => ({
  default: {
    templateTwinFillManifest: { findFirst: (...a: unknown[]) => findFirst(...a) },
    templateTwinFieldOverride: { findMany: (...a: unknown[]) => overrideFindMany(...a) },
  },
}));
vi.mock('../fill-engine', () => ({
  processTemplateTwinVisit: (...a: unknown[]) => processFill(...a),
}));
vi.mock('../native-export', () => ({ mapInputMode: () => 'dictation' }));

const NOTE = 'IMPRESSION: right GSV incompetent, 6.2 mm.';
const VISIT = {
  soapFinal: NOTE,
  userId: 'doc-1',
  noteTemplateId: 'tpl-1',
  noteTemplateVersion: 1,
  inputMode: 'dictation',
  transcriptText: 't',
  entities: {},
};
const sha = async (s: string) =>
  (await import('node:crypto')).createHash('sha256').update(s, 'utf8').digest('hex');

beforeEach(() => {
  findFirst.mockReset();
  processFill.mockReset();
  overrideFindMany.mockReset();
  // Default: no corrections on this visit, which is the pre-F24-S5 world and
  // must stay byte-identical in behaviour.
  overrideFindMany.mockResolvedValue([]);
});

describe('the sign-time freeze', () => {
  it('⚠️ NOT APPLICABLE when there is no native manifest — and NO fill runs', async () => {
    findFirst.mockResolvedValueOnce(null);
    const { freezeNativeManifestForSigning } = await import('../sign-freeze');
    const out = await freezeNativeManifestForSigning({ visitId: 'v1', practiceId: 'p1' });
    expect(out).toEqual({ state: 'not_applicable' });
    expect(processFill).not.toHaveBeenCalled();
  });

  it('⚠️ THE COMMON PATH PAYS NOTHING — a fresh manifest costs ONE read, no fill', async () => {
    findFirst.mockResolvedValueOnce({ noteSha256: await sha(NOTE), visit: VISIT });
    const { freezeNativeManifestForSigning } = await import('../sign-freeze');
    const out = await freezeNativeManifestForSigning({ visitId: 'v1', practiceId: 'p1' });

    expect(out).toEqual({ state: 'already_fresh' });
    expect(processFill, 'a fresh manifest must not trigger a fill').not.toHaveBeenCalled();
    // Exactly one lookup: no re-read, no verification round trip.
    expect(findFirst).toHaveBeenCalledTimes(1);
  });

  it('⚠️ REGENERATES when the note has changed, and PROVES the pair afterwards', async () => {
    const edited = NOTE.replace('right', 'left');
    findFirst
      .mockResolvedValueOnce({ noteSha256: await sha(NOTE), visit: { ...VISIT, soapFinal: edited } })
      .mockResolvedValueOnce({ noteSha256: await sha(edited), visit: { soapFinal: edited } });
    processFill.mockResolvedValueOnce(undefined);

    const { freezeNativeManifestForSigning } = await import('../sign-freeze');
    const out = await freezeNativeManifestForSigning({ visitId: 'v1', practiceId: 'p1' });

    expect(out).toEqual({ state: 'regenerated' });
    expect(processFill).toHaveBeenCalledTimes(1);
    // ⚠️ The fill is attributed to the VISIT'S doctor, never the signer.
    expect(processFill.mock.calls[0][0]).toMatchObject({ doctorId: 'doc-1' });
    // ⚠️ And the claim is VERIFIED by a re-read, not assumed from a non-throw.
    expect(findFirst).toHaveBeenCalledTimes(2);
  });

  it('⚠️ F24-S5 SIGN-AFTER-OVERRIDE — a correction makes the freeze RE-FILL, not "already_fresh"', async () => {
    // ⚠️ THIS IS THE LINE THE REFUTED SLICE DIED ON, and the arm is written to
    // reproduce the pass's own harness. Driven under a mocked prisma, the old
    // freeze returned `already_fresh` with `processTemplateTwinVisit` called
    // ZERO times and `templateTwinFieldOverride.findMany` called ZERO times: the
    // note matched, so the correction was never re-applied and the signature
    // pinned the PRE-OVERRIDE manifest as the signed document, permanently.
    const { overridesIdentity } = await import('../note-identity');
    const ov = [{ fieldId: 'ttf_' + 'a'.repeat(24), selectedOptionOrdinal: 2 }];

    findFirst
      // The stored manifest matches the NOTE and ran against NO corrections…
      .mockResolvedValueOnce({
        noteSha256: await sha(NOTE),
        overridesSha256: null,
        visit: VISIT,
      })
      // …and after the re-fill it carries them.
      .mockResolvedValueOnce({
        noteSha256: await sha(NOTE),
        overridesSha256: overridesIdentity(ov),
        visit: { soapFinal: NOTE },
      });
    // A correction exists on both reads.
    overrideFindMany.mockResolvedValue(ov);
    processFill.mockResolvedValueOnce(undefined);

    const { freezeNativeManifestForSigning } = await import('../sign-freeze');
    const out = await freezeNativeManifestForSigning({ visitId: 'v1', practiceId: 'p1' });

    // NOT `already_fresh`. The freeze CAPTURES the correction.
    expect(out).toEqual({ state: 'regenerated' });
    expect(processFill).toHaveBeenCalledTimes(1);
    // The exact observation that condemned the previous build, inverted.
    expect(overrideFindMany).toHaveBeenCalled();
    expect(overrideFindMany.mock.calls[0][0].where).toEqual({
      visitId: 'v1',
      practiceId: 'p1',
    });
  });

  it('⚠️ and a manifest that ALREADY ran against those corrections still costs NOTHING', async () => {
    // The other direction. A widened identity that declined everything would
    // make every signature pay for a re-fill — "fixing" the bug by breaking the
    // common path.
    const { overridesIdentity } = await import('../note-identity');
    const ov = [{ fieldId: 'ttf_' + 'a'.repeat(24), selectedOptionOrdinal: 2 }];
    findFirst.mockResolvedValueOnce({
      noteSha256: await sha(NOTE),
      overridesSha256: overridesIdentity(ov),
      visit: VISIT,
    });
    overrideFindMany.mockResolvedValue(ov);

    const { freezeNativeManifestForSigning } = await import('../sign-freeze');
    const out = await freezeNativeManifestForSigning({ visitId: 'v1', practiceId: 'p1' });

    expect(out).toEqual({ state: 'already_fresh', manifestId: undefined });
    expect(processFill).not.toHaveBeenCalled();
  });

  it('⚠️ a fill that returns WITHOUT matching is a FAILURE, not a success', async () => {
    const edited = NOTE.replace('right', 'left');
    findFirst
      .mockResolvedValueOnce({ noteSha256: await sha(NOTE), visit: { ...VISIT, soapFinal: edited } })
      // still stale after the fill — the engine declined for its own reasons
      .mockResolvedValueOnce({ noteSha256: await sha(NOTE), visit: { soapFinal: edited } });
    processFill.mockResolvedValueOnce(undefined);

    const { freezeNativeManifestForSigning } = await import('../sign-freeze');
    const out = await freezeNativeManifestForSigning({ visitId: 'v1', practiceId: 'p1' });
    expect(out).toEqual({ state: 'failed', reason: 'refill_did_not_match' });
  });

  it('⚠️ a THROWING fill FAILS OPEN with the named cause — never rethrows', async () => {
    const edited = NOTE.replace('right', 'left');
    findFirst.mockResolvedValueOnce({
      noteSha256: await sha(NOTE),
      visit: { ...VISIT, soapFinal: edited },
    });
    processFill.mockRejectedValueOnce(new Error('minio_unreachable'));

    const { freezeNativeManifestForSigning } = await import('../sign-freeze');
    const out = await freezeNativeManifestForSigning({ visitId: 'v1', practiceId: 'p1' });

    // The signature must not be blocked by a formatting subsystem.
    expect(out).toEqual({ state: 'failed', reason: 'minio_unreachable' });
  });

  it('the budget is FILL-sized, not sweep-sized — a doctor is waiting', async () => {
    const { SIGN_FREEZE_BUDGET_MS } = await import('../sign-freeze');
    expect(SIGN_FREEZE_BUDGET_MS).toBeGreaterThan(0);
    expect(SIGN_FREEZE_BUDGET_MS).toBeLessThanOrEqual(30_000);
  });
});

describe('the sign route surfaces the downgrade', () => {
  const src = () =>
    readFileSync(
      join(__dirname, '..', '..', '..', 'app', 'api', 'visits', '[id]', 'sign', 'route.ts'),
      'utf8',
    )
      .split('\n')
      .filter((l) => !l.trim().startsWith('//'))
      .join('\n');

  it('⚠️ the freeze runs BEFORE the signature is written', () => {
    const c = src();
    const freeze = c.indexOf('freezeNativeManifestForSigning');
    const write = c.indexOf('status: TranscribeVisitStatus.SIGNED');
    expect(freeze).toBeGreaterThan(-1);
    expect(write).toBeGreaterThan(-1);
    expect(freeze, 'the refresh must precede the signature').toBeLessThan(write);
  });

  it('⚠️ ONE VISIT_SIGNED audit row — the downgrade rides it, never a second row', () => {
    // An earlier draft emitted a second row and corrupted the trail.
    expect((src().match(/action: 'VISIT_SIGNED'/g) ?? []).length).toBe(1);
    expect(src()).toMatch(/signNativeRefreshFailed/);
  });

  it('⚠️ the doctor is TOLD, in the response — silence is the forbidden outcome', () => {
    expect(src()).toMatch(/formatNotice/);
  });

  it('⚠️ the signature is never blocked — and the guard COVERS THE IMPORT', () => {
    // ⚠️ THIS ARM WAS GREEN WITH THE DEFECT PRESENT.
    //
    // It asserted a `.catch(` existed near the call and never asked WHAT IT
    // COVERED. The `await import()` sat OUTSIDE it, so a module-load rejection
    // escaped the handler, returned 500, and the signature was never written —
    // falsifying the very invariant this arm is named for.
    //
    // Presence of a guard is not coverage by it. The arm now checks the
    // STRUCTURE: the dynamic import must be lexically inside a try whose catch
    // yields a `failed` state rather than propagating.
    const c = src();
    // ⚠️ ANCHOR ON THE CALL, NOT THE FIRST MENTION. A first draft of this arm
    // used `indexOf('freezeNativeManifestForSigning')`, which in the DEFECTIVE
    // version matches the import destructuring itself — so the arm measured a
    // window that already contained the import and passed. Caught by mutating
    // toward the shipped defect and watching this arm stay green.
    const callIdx = c.indexOf('await freezeNativeManifestForSigning(');
    expect(callIdx, 'the freeze call must exist').toBeGreaterThan(-1);

    const tryIdx = c.lastIndexOf('try {', callIdx);
    expect(tryIdx, 'the freeze must sit inside a try').toBeGreaterThan(-1);

    const importIdx = c.lastIndexOf("import(", callIdx);
    expect(
      importIdx > tryIdx,
      'the dynamic import must be INSIDE the try that guards the call — a ' +
        'module-load failure must not escape and 500 the signature',
    ).toBe(true);

    // and the catch must degrade, not rethrow or refuse
    const after = c.slice(callIdx, callIdx + 700);
    expect(after).not.toMatch(/return apiError/);
    expect(after).toMatch(/state: 'failed'/);
  });

  it('⚠️ the freeze is FLAG-GATED — a rollback must not run a fill inside /sign', () => {
    // It was the only twin entry point not behind the flag, so the documented
    // rollback would still have run a full fill on the signature path.
    const c = src();
    const i = c.indexOf('freezeNativeManifestForSigning');
    const before = c.slice(Math.max(0, i - 400), i);
    expect(before).toMatch(/templateNativeDocxEnabled\(\)/);
  });
});

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
