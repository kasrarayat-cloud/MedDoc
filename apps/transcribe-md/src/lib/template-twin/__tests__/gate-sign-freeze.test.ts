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

vi.mock('@meddoc/db', () => ({
  default: { templateTwinFillManifest: { findFirst: (...a: unknown[]) => findFirst(...a) } },
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

  it('the signature is never blocked by the freeze', () => {
    // No throw, no early return, no apiError on the freeze path.
    const c = src();
    const i = c.indexOf('freezeNativeManifestForSigning');
    const window = c.slice(i, i + 900);
    expect(window).not.toMatch(/return apiError/);
    expect(window).toMatch(/\.catch\(/);
  });
});

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
