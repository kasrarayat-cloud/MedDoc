import { describe, expect, it, vi, beforeEach } from 'vitest';

/**
 * F5-f RULING 2(b) — A SIGNED RECORD RESOLVES BY POINTER, NEVER BY LOOKUP.
 *
 * "Impossible, then inert." Layer (a) makes a post-signature manifest write
 * impossible (the persist re-checks the visit's status and the DB enforces it).
 * This layer makes a write that slipped through UNREACHABLE: the signature
 * stamped `frozenFillManifestId` in the same write that set SIGNED, and the
 * serve path reads only that id.
 *
 * ⚠️ NULL IS A RECORDED OUTCOME, NOT A MISSING VALUE. A signed visit with no
 * pointer froze no native document; the answer is styled, forever. Treating
 * null as "look it up instead" is exactly the defect this closes.
 */
const visitFindFirst = vi.fn();
const manifestFindFirst = vi.fn();
const readOutput = vi.fn();
/** F24-S5 — the override half of the bound identity. */
const overrideFindMany = vi.fn();

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: { findFirst: (...a: unknown[]) => visitFindFirst(...a) },
    templateTwinFillManifest: { findFirst: (...a: unknown[]) => manifestFindFirst(...a) },
    // F24-S5 — both the serve path and `resolveFrozenPointer` now read the
    // override half of the bound identity.
    templateTwinFieldOverride: { findMany: (...a: unknown[]) => overrideFindMany(...a) },
  },
}));
vi.mock('../storage', () => ({
  createTemplateTwinArtifactStore: () => ({ readOutputArtifact: readOutput }),
}));
// ⚠️ `native-export` imports the fill engine for its COMPUTE path, and the
// engine's graph reaches next-auth. This test exercises only the SERVE path, so
// the engine is stubbed rather than loaded — the alternative is dragging a web
// framework into a unit test of a database predicate.
vi.mock('../fill-engine', () => ({ processTemplateTwinVisit: vi.fn() }));
vi.mock('@/lib/practice-scope', () => ({
  visitByIdScope: (id: string, practiceId: string) => ({ id, practiceId }),
  asPracticeId: (v: string) => v,
}));

const NOTE = 'IMPRESSION: right GSV incompetent.';
const sha = async (s: string) =>
  (await import('node:crypto')).createHash('sha256').update(s, 'utf8').digest('hex');

const manifestRow = async (id: string) => ({
  id,
  practiceId: 'p1',
  outputObjectKey: `k/${id}`,
  outputSha256: 'a'.repeat(64),
  outputSizeBytes: 10,
  noteSha256: await sha(NOTE),
  visit: { soapFinal: NOTE },
});

beforeEach(() => {
  visitFindFirst.mockReset();
  manifestFindFirst.mockReset();
  readOutput.mockReset();
  overrideFindMany.mockReset();
  // No corrections on this visit — the pre-F24-S5 world, which must stay
  // behaviourally identical.
  overrideFindMany.mockResolvedValue([]);
  readOutput.mockResolvedValue(Buffer.from('DOCX'));
});

describe('a SIGNED record resolves by pointer', () => {
  it('⚠️ SIGNED + NO POINTER serves styled FOREVER — even if a manifest exists', async () => {
    visitFindFirst.mockResolvedValueOnce({ status: 'SIGNED', frozenFillManifestId: null });
    // A manifest DOES exist — the orphan that landed after the signature.
    manifestFindFirst.mockResolvedValueOnce(await manifestRow('m-late'));

    const { loadNativeTemplateDocxForVisit } = await import('../native-export');
    const out = await loadNativeTemplateDocxForVisit('v1', 'p1');

    expect(out, 'a late manifest must be unreachable on a styled-signed record').toBeNull();
    // and it must not even have looked
    expect(manifestFindFirst).not.toHaveBeenCalled();
  });

  it('⚠️ SIGNED + POINTER resolves EXACTLY that id — even if a NEWER manifest exists', async () => {
    visitFindFirst.mockResolvedValueOnce({ status: 'SIGNED', frozenFillManifestId: 'm-frozen' });
    manifestFindFirst.mockResolvedValueOnce(await manifestRow('m-frozen'));

    const { loadNativeTemplateDocxForVisit } = await import('../native-export');
    await loadNativeTemplateDocxForVisit('v1', 'p1');

    const where = manifestFindFirst.mock.calls[0][0].where;
    expect(where.id, 'the pointer must be the predicate').toBe('m-frozen');
  });

  it('an UNSIGNED visit still resolves by lookup — the pointer governs signed only', async () => {
    visitFindFirst.mockResolvedValueOnce({ status: 'READY', frozenFillManifestId: null });
    manifestFindFirst.mockResolvedValueOnce(await manifestRow('m-current'));

    const { loadNativeTemplateDocxForVisit } = await import('../native-export');
    await loadNativeTemplateDocxForVisit('v1', 'p1');

    const where = manifestFindFirst.mock.calls[0][0].where;
    expect(where.id, 'an unsigned visit has no frozen pointer to obey').toBeUndefined();
    expect(where.visitId).toBe('v1');
  });

  it('⚠️ F24-S5 EXPORT-AFTER-OVERRIDE — a note-matching manifest is DECLINED once a correction exists', async () => {
    // THE ACCEPTANCE ARM FOR THE ROOT FIX, at the surface that failed.
    //
    // Before the bound identity widened, this exact state served the stored
    // bytes: the manifest's `noteSha256` matches (an override never touches
    // `soapFinal`), so freshness answered `match` and the doctor's download
    // showed the value they had just corrected. The pre-sign preview showed the
    // correction and the export did not.
    visitFindFirst.mockResolvedValueOnce({ status: 'READY', frozenFillManifestId: null });
    manifestFindFirst.mockResolvedValueOnce({
      ...(await manifestRow('m-current')),
      // Filled when there were no corrections…
      overridesSha256: null,
    });
    // …and a correction now exists.
    overrideFindMany.mockResolvedValueOnce([
      { fieldId: 'ttf_' + 'a'.repeat(24), selectedOptionOrdinal: 2 },
    ]);

    const { loadNativeTemplateDocxForVisit } = await import('../native-export');
    const out = await loadNativeTemplateDocxForVisit('v1', 'p1');

    // DECLINED — so the caller recomputes and the correction reaches the
    // document, rather than the stale artifact being handed over.
    expect(out).toBeNull();
    expect(readOutput, 'the stale artifact must not even be READ').not.toHaveBeenCalled();
    // And the override half really was consulted, scoped to this visit.
    expect(overrideFindMany).toHaveBeenCalledTimes(1);
    expect(overrideFindMany.mock.calls[0][0].where).toEqual({
      visitId: 'v1',
      practiceId: 'p1',
    });
  });

  it('⚠️ and it still SERVES when the manifest ran against those same corrections', async () => {
    // The other direction, and it is the one that keeps the gate honest: a
    // widened identity that declined everything would "fix" the bug by breaking
    // native export for every visit.
    const { overridesIdentity } = await import('../note-identity');
    const ov = [{ fieldId: 'ttf_' + 'a'.repeat(24), selectedOptionOrdinal: 2 }];
    visitFindFirst.mockResolvedValueOnce({ status: 'READY', frozenFillManifestId: null });
    manifestFindFirst.mockResolvedValueOnce({
      ...(await manifestRow('m-current')),
      overridesSha256: overridesIdentity(ov),
    });
    overrideFindMany.mockResolvedValueOnce(ov);
    readOutput.mockResolvedValueOnce(new Uint8Array([1, 2, 3]));

    const { loadNativeTemplateDocxForVisit } = await import('../native-export');
    const out = await loadNativeTemplateDocxForVisit('v1', 'p1');
    expect(out).not.toBeNull();
    expect(readOutput).toHaveBeenCalledTimes(1);
  });

  it('⚠️ a signed record still serves after a post-sign edit to soapFinal', async () => {
    // Freshness governs the UNSIGNED record. Re-deriving it for a signed one
    // would let an edit to `soapFinal` decline the document the signature froze
    // — the record would lose the ability to produce itself.
    visitFindFirst.mockResolvedValueOnce({ status: 'SIGNED', frozenFillManifestId: 'm-frozen' });
    manifestFindFirst.mockResolvedValueOnce({
      ...(await manifestRow('m-frozen')),
      visit: { soapFinal: 'EDITED AFTER SIGNING' },
    });

    const { loadNativeTemplateDocxForVisit } = await import('../native-export');
    const out = await loadNativeTemplateDocxForVisit('v1', 'p1');
    expect(out, 'the frozen document must still be servable').not.toBeNull();
  });
});

describe('the pointer is written with the signature, in one statement', () => {
  const src = () =>
    readFileSync(
      join(__dirname, '..', '..', '..', 'app', 'api', 'visits', '[id]', 'sign', 'route.ts'),
      'utf8',
    ).split('\n').filter((l) => !l.trim().startsWith('//')).join('\n');

  it('⚠️ frozenFillManifestId is in the SAME updateMany as status: SIGNED', () => {
    const c = src();
    const i = c.indexOf('status: TranscribeVisitStatus.SIGNED');
    expect(i).toBeGreaterThan(-1);
    const block = c.slice(i, i + 900);
    expect(
      block,
      'the pointer and the signature must be one write — two writes can interleave',
    ).toMatch(/frozenFillManifestId:/);
  });

  it('⚠️ and that write is CAS-guarded on the note identity', () => {
    const c = src();
    const i = c.indexOf('status: TranscribeVisitStatus.SIGNED');
    const before = c.slice(Math.max(0, i - 1200), i);
    expect(before).toMatch(/soapVersion: visit\.soapVersion/);
  });
});

/**
 * ⚠️ THE POINTER IS DERIVED AT WRITE TIME, NOT TRUSTED FROM THE FREEZE.
 *
 * The aimed TOCTOU pass found two interleaves where the freeze's in-memory
 * manifestId is wrong at the moment the signature lands:
 *   · two concurrent signs — the loser's fill throws MANIFEST_CONFLICT, its
 *     outcome is `failed` (a variant that structurally cannot carry an id), and
 *     it stamps NULL even though the winner produced exactly the right document;
 *   · one sign whose 20s race expired — the orphaned fill lands the correct
 *     manifest moments later, and NULL is stamped anyway.
 *
 * Both strand the record on styled FOREVER, with an audit row asserting a
 * downgrade that did not happen.
 */
describe('resolveFrozenPointer — asked of the database, at the last moment', () => {
  it('⚠️ finds the manifest matching the CAPTURED note, whoever produced it', async () => {
    const wanted = await sha(NOTE);
    manifestFindFirst.mockResolvedValueOnce({ id: 'm-by-other-actor' });
    const { resolveFrozenPointer } = await import('../sign-freeze');
    const id = await resolveFrozenPointer('v1', 'p1', NOTE);

    expect(id).toBe('m-by-other-actor');
    // it is bound to the CAPTURE, not to the visit's current note
    expect(manifestFindFirst.mock.calls[0][0].where.noteSha256).toBe(wanted);
  });

  it('⚠️ returns null when NOTHING matches — styled becomes a fact, not a guess', async () => {
    manifestFindFirst.mockResolvedValueOnce(null);
    const { resolveFrozenPointer } = await import('../sign-freeze');
    expect(await resolveFrozenPointer('v1', 'p1', NOTE)).toBeNull();
  });

  it('a visit with no captured note has no pointer to resolve', async () => {
    const { resolveFrozenPointer } = await import('../sign-freeze');
    expect(await resolveFrozenPointer('v1', 'p1', null)).toBeNull();
    expect(manifestFindFirst).not.toHaveBeenCalled();
  });

  it('⚠️ it demands the SERVE predicate — a half-ready manifest is not a pointer', async () => {
    manifestFindFirst.mockResolvedValueOnce({ id: 'm' });
    const { resolveFrozenPointer } = await import('../sign-freeze');
    await resolveFrozenPointer('v1', 'p1', NOTE);
    const w = manifestFindFirst.mock.calls[0][0].where;
    expect(w.status).toBe('VERIFIED');
    expect(w.roundTripVerified).toBe(true);
    expect(w.outputObjectKey).toEqual({ not: null });
  });

  it('⚠️ the sign route stamps the DERIVED pointer, not the freeze\'s id', () => {
    const c = readFileSync(
      join(__dirname, '..', '..', '..', 'app', 'api', 'visits', '[id]', 'sign', 'route.ts'),
      'utf8',
    ).split('\n').filter((l) => !l.trim().startsWith('//')).join('\n');
    expect(c).toMatch(/resolveFrozenPointer\(/);
    expect(c).toMatch(/signWrite\(pointer\)/);
    // the in-memory value must NOT be what reaches the write
    expect(c).not.toMatch(/signWrite\(nativeFreeze\.manifestId/);
  });
});

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
