// ============================================================================
// ADMIN-6 — REAL-POSTGRES PROOF: archive → restore leaves `users` BYTE-IDENTICAL
// ----------------------------------------------------------------------------
//   DATABASE_URL=postgresql://…/<name carrying a qa/test/e2e/ci marker> \
//     npx tsx scripts/proofs/admin6-archive-restore-proof.ts
//
// NEVER PRODUCTION: `assertNonProdDatabase()` is the first statement and refuses
// any database whose name lacks a qa/test/e2e/ci marker. It needs every
// migration applied. It seeds its own rows under a unique run tag and never
// touches rows it did not create.
//
// Why a real database: the unit arms prove the verb CALLS no users writer. Only
// Postgres can prove that no users ROW changed — that no trigger, cascade or
// default moved a byte — and that the `FOR UPDATE` serializes two concurrent
// archives into one. A mock can only agree with its author.
//
// Exit 0 + "🟢 all arms ran and passed" = every arm held. Exit 1 = a claim was
// refuted. Exit 2 = CANNOT TELL (the concurrency arm's racers never overlapped),
// which is neither.
// ============================================================================
import { assertNonProdDatabase } from '@meddoc/db/guard';
import prisma from '@meddoc/db';

import { updatePractice } from '../../src/lib/practice-write';
import { validateSession } from '../../../../packages/auth/src/user-session';

assertNonProdDatabase();

const RUN = `a6p${Date.now().toString(36)}`;
let failed = 0;
let cannotTell = false;

function arm(name: string, ok: boolean, detail = '') {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `  — ${detail}` : ''}`);
  if (!ok) failed += 1;
}

async function usersHash(): Promise<{ hash: string; count: number }> {
  const [r] = await prisma.$queryRaw<{ hash: string; count: bigint }[]>`
    SELECT md5(coalesce(string_agg(u::text, '|' ORDER BY u.id), '')) AS hash, count(*) AS count
    FROM users u`;
  return { hash: r!.hash, count: Number(r!.count) };
}

async function practiceActive(id: string): Promise<boolean> {
  const p = await prisma.practice.findUniqueOrThrow({ where: { id }, select: { isActive: true } });
  return p.isActive;
}

async function auditRows(practiceId: string) {
  return prisma.auditLog.findMany({
    where: { targetType: 'Practice', targetId: practiceId },
    select: { action: true, metadata: true, userId: true },
    orderBy: { timestamp: 'asc' },
  });
}

async function mkPractice(tag: string) {
  return prisma.practice.create({ data: { name: `${RUN} ${tag}`, slug: `${RUN}-${tag}` } });
}

async function mkUser(practiceId: string, tag: string, extra: Record<string, unknown> = {}) {
  return prisma.user.create({
    data: {
      email: `${RUN}-${tag}@admin6.invalid`,
      passwordHash: 'not-a-real-hash',
      practiceId,
      practiceRole: 'OWNER',
      role: 'DOCTOR',
      products: ['TRANSCRIBE_MD'],
      ...extra,
    } as never,
  });
}

async function main() {
  // ── Seed ──────────────────────────────────────────────────────────────────
  const S = await mkPractice('actor'); // the actor's own practice
  const A = await mkUser(S.id, 'actor', { products: ['TRANSCRIBE_MD', 'SUPER_ADMIN'] });

  const P = await mkPractice('target'); // three members in three different states
  const O = await mkUser(P.id, 'owner');
  await mkUser(P.id, 'susp', { practiceRole: 'CLINICIAN', suspendedAt: new Date('2026-09-01T00:00:00Z') });
  await mkUser(P.id, 'deact', {
    practiceRole: 'TECH',
    isActive: false,
    deactivatedAt: new Date('2026-08-01T00:00:00Z'),
  });
  const sess = await prisma.userSession.create({
    data: { userId: O.id, sessionToken: `${RUN}-sess`, expiresAt: new Date(Date.now() + 3_600_000) },
  });

  const Q = await mkPractice('hasadmin'); // holds a platform administrator
  await mkUser(Q.id, 'qowner', { products: ['TRANSCRIBE_MD', 'SUPER_ADMIN'] });

  const V = await mkPractice('inflight'); // holds a visit still being processed
  const W = await mkUser(V.id, 'vowner');
  const patient = await prisma.transcribeMdPatient.create({
    data: { practiceId: V.id, name: `${RUN} synthetic patient` } as never,
  });
  await prisma.transcribeVisit.create({
    data: {
      userId: W.id,
      createdBy: W.id,
      patientId: patient.id,
      practiceId: V.id,
      specialty: 'Vascular Surgery',
      inputMode: 'text_notes',
      status: 'DRAFTING',
    } as never,
  });

  const R = await mkPractice('race');
  await mkUser(R.id, 'rowner');

  // ── Arm 1 · control: the session is live before anything happens ─────────
  arm('control: the member\'s session validates before the archive', (await validateSession(sess.sessionToken)) !== null);

  const before = await usersHash();
  arm('control: the users hash is computed over a non-empty table', before.count > 0, `${before.count} rows`);

  // ── Arm 2 · archive ───────────────────────────────────────────────────────
  const archived = await updatePractice({ practiceId: P.id, patch: { isActive: false }, actorUserId: A.id, reason: `${RUN} proof` });
  arm('archive succeeds', archived.ok, JSON.stringify(archived));
  arm('the practice row is now isActive=false', (await practiceActive(P.id)) === false);

  const afterArchive = await usersHash();
  arm('⚠️ DESIGN A — the users table is BYTE-IDENTICAL after the archive', afterArchive.hash === before.hash, `${before.hash} → ${afterArchive.hash}`);
  arm('⚠️ D2 — the member\'s session is refused while archived', (await validateSession(sess.sessionToken)) === null);

  // ── Arm 3 · restore ───────────────────────────────────────────────────────
  const restored = await updatePractice({ practiceId: P.id, patch: { isActive: true }, actorUserId: A.id });
  arm('restore succeeds', restored.ok, JSON.stringify(restored));
  const afterRestore = await usersHash();
  arm('⚠️ archive → restore leaves the users table BYTE-IDENTICAL to before', afterRestore.hash === before.hash, `${before.hash} → ${afterRestore.hash}`);
  arm('⚠️ D2 — the SAME session is admitted again after the restore', (await validateSession(sess.sessionToken)) !== null);

  const rowsP = await auditRows(P.id);
  arm(
    'the audit trail is exactly ARCHIVED then RESTORED, each naming the actor',
    rowsP.map((r) => r.action).join(',') === 'PRACTICE_ARCHIVED,PRACTICE_RESTORED' && rowsP.every((r) => r.userId === A.id),
    rowsP.map((r) => r.action).join(','),
  );
  const archMeta = rowsP[0]?.metadata as { changed?: { isActive?: { from: unknown } }; members?: unknown[] } | undefined;
  arm('the ARCHIVED row carries from=true and a 3-member snapshot', archMeta?.changed?.isActive?.from === true && archMeta?.members?.length === 3);

  // ── Arm 4 · refusals on real SQL — nothing written ────────────────────────
  for (const [label, practiceId, reason] of [
    ['own practice', S.id, 'own_practice'],
    ['a platform administrator inside', Q.id, 'practice_has_super_admin'],
    ['a visit in flight', V.id, 'visits_in_flight'],
  ] as const) {
    const r = await updatePractice({ practiceId, patch: { isActive: false }, actorUserId: A.id });
    const still = await practiceActive(practiceId);
    const rows = await auditRows(practiceId);
    arm(`refuses ${label} BY NAME and writes nothing`, !r.ok && r.reason === reason && still && rows.length === 0, JSON.stringify(r));
  }

  // ── Arm 5 · a failed audit insert rolls the write back ────────────────────
  // A rename by an actor id that does not exist: the verb does not refuse a
  // non-archive write for an unknown actor, so it reaches the audit insert,
  // whose FK on `userId` fails — and the rename must go with it.
  const nameBefore = (await prisma.practice.findUniqueOrThrow({ where: { id: R.id } })).name;
  let threw = false;
  try {
    await updatePractice({ practiceId: R.id, patch: { name: `${RUN} renamed` }, actorUserId: `${RUN}-ghost` });
  } catch {
    threw = true;
  }
  const nameAfter = (await prisma.practice.findUniqueOrThrow({ where: { id: R.id } })).name;
  arm('⚠️ a failed audit insert FAILS the act and ROLLS BACK the write', threw && nameAfter === nameBefore, `threw=${threw} name ${nameBefore} → ${nameAfter}`);

  // ── Arm 6 · FOR UPDATE serializes two concurrent archives ─────────────────
  const t0 = Date.now();
  const [x, y] = await Promise.all([
    updatePractice({ practiceId: R.id, patch: { isActive: false }, actorUserId: A.id, reason: 'racer-1' }),
    updatePractice({ practiceId: R.id, patch: { isActive: false }, actorUserId: A.id, reason: 'racer-2' }),
  ]);
  const elapsed = Date.now() - t0;
  const okCount = [x, y].filter((r) => r.ok).length;
  const noChange = [x, y].filter((r) => !r.ok && r.reason === 'no_change').length;
  const rowsR = (await auditRows(R.id)).filter((r) => r.action === 'PRACTICE_ARCHIVED');
  arm(
    '⚠️ two concurrent archives → exactly ONE act and ONE audit row; the other sees no_change',
    okCount === 1 && noChange === 1 && rowsR.length === 1,
    `ok=${okCount} no_change=${noChange} archivedRows=${rowsR.length} (${elapsed}ms)`,
  );
  if (okCount === 2 && rowsR.length === 1) cannotTell = true;

  const end = await usersHash();
  arm('⚠️ after EVERY arm, the users table is still byte-identical to the seed', end.hash === before.hash);
}

main()
  .then(async () => {
    await prisma.$disconnect();
    if (failed > 0) {
      console.log(`🔴 ${failed} arm(s) FAILED`);
      process.exit(1);
    }
    if (cannotTell) {
      console.log('🟡 CANNOT TELL — the racers did not overlap');
      process.exit(2);
    }
    console.log('🟢 all arms ran and passed');
  })
  .catch(async (err) => {
    console.error('🔴 proof crashed:', err);
    await prisma.$disconnect();
    process.exit(1);
  });
