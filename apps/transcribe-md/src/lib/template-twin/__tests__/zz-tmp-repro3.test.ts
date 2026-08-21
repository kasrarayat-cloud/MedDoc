import { describe, expect, it, vi, beforeEach } from 'vitest';
import { createHash } from 'node:crypto';

/* VARIANT 2 — the concurrent producer is NOT another signer.
 *
 * `visit-docx-source.ts:63` -> loadOrComputeNativeTemplateDocxForVisit ->
 * processTemplateTwinVisit runs a FULL FILL for any UNSIGNED visit whose stored
 * manifest does not match the current note. That is exactly the precondition
 * the sign-time freeze exists for, so a Download-Word (or PDF) request and a
 * Sign click on the same unsigned visit run two fills against the same manifest
 * row.
 *
 * The export request never signs, so there is NO race at the visit CAS: if the
 * export's fill wins the manifest CAS, the freeze's fill loses, the freeze
 * returns `failed` WITHOUT re-reading, and the signature stamps NULL
 * unconditionally. */
const DB_MS = 10, PREPARE_MS = 2000, STORE_MS = 300;
let CLOCK = 0;
const TRACE: string[] = [];
function op<T>(ms: number, label: string, fn: () => T): Promise<T> {
  return new Promise<T>((res) => setTimeout(() => { if (label) TRACE.push(`${String(Date.now() - CLOCK).padStart(5)}ms ${label}`); res(fn()); }, ms));
}
const sha = (s: string) => createHash('sha256').update(s, 'utf8').digest('hex');
const NOTE_V1 = 'IMPRESSION: right GSV incompetent, 6.2 mm.';
const NOTE_V2 = 'IMPRESSION: LEFT GSV incompetent, 6.2 mm.'; // doctor edited after the worker fill

let lockChain: Promise<unknown> = Promise.resolve();
async function manifestUpdate<T>(label: string, fn: () => T): Promise<T> {
  const prev = lockChain; let release!: () => void;
  lockChain = new Promise<void>((r) => (release = r));
  await prev; const out = await op(1, label, fn); release(); return out;
}
let VISIT: any, M: any;

vi.mock('@meddoc/db', () => ({
  default: { templateTwinFillManifest: { findFirst: () => op(DB_MS, 'freeze:findFirst(manifest)', () =>
    M.status === 'VERIFIED' && M.roundTripVerified && M.outputObjectKey
      ? { id: M.id, noteSha256: M.noteSha256, visit: { soapFinal: VISIT.soapFinal, userId: 'doc-1', createdAt: new Date(), noteTemplateId: 'tpl-1', noteTemplateVersion: 1, inputMode: 'dictation', transcriptText: 't', entities: {} } }
      : null) } },
}));
vi.mock('../native-export', () => ({ mapInputMode: () => 'dictation' }));
class FillError extends Error { code: string; constructor(c: string, m: string) { super(m); this.code = c; } }

async function realFillEngine(input: any) {
  const who = input.who;
  await op(PREPARE_MS, `${who} fill:readAndPrepare`, () => null);
  const prepSha = sha('manifest-for:' + input.generatedNote);
  const existing = await op(DB_MS, `${who} fill:read existing (:483)`, () => ({ ...M }));
  if (existing.manifestSha256 === prepSha && existing.roundTripVerified) {
    TRACE.push(`      ${who} fill:EARLY RETURN (:508) — nothing to write`); return;
  }
  await op(STORE_MS, `${who} fill:storeOutputArtifact (:517)`, () => null);
  const vn = await op(DB_MS, `${who} fill:visitNow (:594)`, () => ({ status: VISIT.status, signedAt: VISIT.signedAt }));
  if (vn.status === 'SIGNED' || vn.signedAt != null) throw new FillError('SIGNED_MANIFEST_IMMUTABLE', 'signed while filling');
  const count = await manifestUpdate(`${who} fill:CAS manifest (:632)`, () => {
    if (VISIT.status === 'SIGNED' || M.manifestVersion !== existing.manifestVersion || M.manifestSha256 !== existing.manifestSha256) return 0;
    M.manifestVersion += 1; M.manifestSha256 = prepSha; M.noteSha256 = sha(input.generatedNote);
    M.status = 'VERIFIED'; M.roundTripVerified = true; M.outputObjectKey = 'k/' + prepSha; return 1;
  });
  if (count !== 1) {
    await op(DB_MS, `${who} fill:re-read after conflict (:650)`, () => null);
    throw new FillError('MANIFEST_CONFLICT', 'The Template Twin fill changed concurrently and was not replaced.');
  }
  await op(DB_MS, `${who} fill:await logAudit (:693)`, () => null);
}
vi.mock('../fill-engine', () => ({ processTemplateTwinVisit: (i: any) => realFillEngine(i) }));

/** GET /api/visits/[id]/export/docx on an UNSIGNED visit with a stale manifest. */
async function exportDocxRequest(startMs: number) {
  if (startMs) await new Promise((r) => setTimeout(r, startMs));
  TRACE.push(`      EXPORT request begins (visit-docx-source.ts:63)`);
  try { await realFillEngine({ visitId: 'v1', generatedNote: VISIT.soapFinal, who: 'EXPORT' }); return 'native'; }
  catch (e) { return `styled(${(e as Error).message.slice(0, 24)}…)`; }
}

async function signRequest(startMs: number) {
  if (startMs) await new Promise((r) => setTimeout(r, startMs));
  const cap = await op(DB_MS, `SIGN  route:capture visit (:198)`, () => ({ soapFinal: VISIT.soapFinal, soapVersion: VISIT.soapVersion }));
  const { freezeNativeManifestForSigning } = await import('../sign-freeze');
  let nf: any;
  try { nf = await freezeNativeManifestForSigning({ visitId: 'v1', practiceId: 'p1', ...({ who: 'SIGN ' } as any) } as any); }
  catch (e) { nf = { state: 'failed', reason: (e as Error).message }; }
  const c = await op(DB_MS, `SIGN  route:CAS SIGN (:630)  <== frozenFillManifestId = ${nf.manifestId ?? 'NULL'}`, () => {
    if (VISIT.status !== 'READY' || VISIT.soapVersion !== cap.soapVersion) return 0;
    VISIT.status = 'SIGNED'; VISIT.signedSoap = cap.soapFinal; VISIT.signedAt = new Date();
    VISIT.frozenFillManifestId = nf.manifestId ?? null; return 1;
  });
  return { nf, wonCas: c === 1 };
}

beforeEach(() => {
  TRACE.length = 0; CLOCK = Date.now(); lockChain = Promise.resolve();
  VISIT = { status: 'READY', soapFinal: NOTE_V2, soapVersion: 2, signedAt: null, signedSoap: null, frozenFillManifestId: null };
  M = { id: 'manifest-A', status: 'VERIFIED', roundTripVerified: true, outputObjectKey: 'k/old',
        manifestVersion: 3, manifestSha256: sha('manifest-for:' + NOTE_V1), noteSha256: sha(NOTE_V1) };
});

describe('VARIANT 2 — export-triggered fill overlapping ONE sign', () => {
  for (const exportHeadStart of [0, 50, 100, 200, 300, 500, 1000, 1500, 2000, 2100, 2200, 2350, 2500]) {
    it(`export fill starts ${exportHeadStart} ms before the sign click`, async () => {
      const [, s] = await Promise.all([exportDocxRequest(0), signRequest(exportHeadStart)]);
      const bound = M.noteSha256 === sha(VISIT.signedSoap);
      const defect = s.wonCas && bound && VISIT.frozenFillManifestId === null;
      console.log(`V2 headStart=${String(exportHeadStart).padStart(4)}ms signFreeze=${String(s.nf.state).padEnd(13)} pointer=${String(VISIT.frozenFillManifestId).padEnd(10)} manifestBoundToSignedText=${bound} => ${defect ? 'DEFECT' : 'ok'}`);
      expect(s.wonCas).toBe(true);
    }, 30_000);
  }
  it('TRACE at headStart=300ms', async () => {
    await Promise.all([exportDocxRequest(0), signRequest(300)]);
    console.log('\n---- V2 TRACE (export fill starts 300 ms before the click) ----');
    for (const l of TRACE) console.log('  ' + l);
    console.log(`  FINAL: visit.status=${VISIT.status} pointer=${VISIT.frozenFillManifestId} manifestBoundToSignedText=${M.noteSha256 === sha(VISIT.signedSoap)}`);
  }, 30_000);
});
