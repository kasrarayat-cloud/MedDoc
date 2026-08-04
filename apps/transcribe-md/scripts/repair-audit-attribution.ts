// ============================================================================
// Repair the attribution of audit rows written under the `?? 'clinic_main'`
// fail-open.  READ-ONLY BY DEFAULT.  `--apply` to write.
// ----------------------------------------------------------------------------
//   npx tsx scripts/repair-audit-attribution.ts            # report only
//   npx tsx scripts/repair-audit-attribution.ts --apply    # append corrections
//
// ⚠️ THIS SCRIPT NEVER UPDATES AND NEVER DELETES A SINGLE ROW.
//
// `audit_logs` is append-only by design. An audit trail you can rewrite is not
// an audit trail — the row that says a thing happened is worth exactly as much
// as the guarantee that nobody edited it afterwards. So a wrongly-attributed
// row STAYS wrong, and the truth is recorded by APPENDING an
// `AUDIT_ATTRIBUTION_CORRECTED` row that points back at it via `targetId`.
// A reader who wants the corrected view joins; a reader who wants the original
// gets the original. Both are honest.
//
// WHAT WENT WRONG (so the next reader does not have to reconstruct it):
// until 2026-08-04 `lib/audit.ts` resolved the tenant as
// `input.practiceId ?? sessionPracticeId ?? 'clinic_main'`. `clinic_main` is
// the largest SHARED practice in production (11 users). Any write with no
// practice in scope was therefore filed under it. The one caller that hit this
// in anger is the NextAuth `signOut` event, which runs OUTSIDE request scope,
// so `auth()` returns nothing and the fallback took over — 64 `LOGOUT` rows
// belonging to 64 different solo doctors, all filed under Main Clinic.
//
// SCOPE, stated precisely, because "65" was the first number and it was wrong:
//   • IN scope — rows whose practiceId is 'clinic_main' while the row's own
//     userId resolves to a DIFFERENT practice. 64 of them, all LOGOUT.
//   • NOT in scope — the single USER_GRANTED_SUPER_ADMIN row that also matches
//     a naive `a.practiceId <> actor.practiceId` query. That row is CORRECT:
//     `grant-admin/route.ts` deliberately passes the TARGET user's practice,
//     not the actor's, because the event belongs to the tenant being changed.
//     A repair driven by the naive query would have corrupted a correct row.
//   • NOT in scope — the 6 pre-S4c `EM_LEVEL_CHANGED` rows with NULL in BOTH
//     practiceId and practiceIdSnapshot AND a NULL userId. Their tenant is
//     genuinely unrecoverable. They are reported with determinable=false
//     rather than guessed at, and their emitter no longer exists in the tree.
// ============================================================================

import prisma from '@meddoc/db';

const APPLY = process.argv.includes('--apply');
const WRONG_PRACTICE = 'clinic_main';

type Undeterminable = { id: string; action: string };

type Row = {
  id: string;
  action: string;
  userId: string | null;
  practiceId: string | null;
  practiceIdSnapshot: string | null;
  actorPracticeId: string | null;
};

async function main() {
  console.log(
    `\n=== audit attribution repair — ${APPLY ? 'APPLY' : 'REPORT ONLY'} ===\n`,
  );

  // ---- 1. Establish the boundary BEFORE selecting anything. A repair that
  // does not state the size of the set it is repairing cannot be checked.
  const total = await prisma.auditLog.count();
  const alreadyCorrected = await prisma.auditLog.count({
    where: { action: 'AUDIT_ATTRIBUTION_CORRECTED' as never },
  });
  console.log(`audit_logs total rows        : ${total}`);
  console.log(`existing correction rows     : ${alreadyCorrected}`);

  // ---- 2. The misattributed set. Raw SQL because the predicate joins the row
  // to its own user, which Prisma's relation filters cannot express directly.
  const misattributed = await prisma.$queryRaw<Row[]>`
    SELECT a.id,
           a.action::text          AS action,
           a."userId",
           a."practiceId",
           a."practiceIdSnapshot",
           u."practiceId"          AS "actorPracticeId"
    FROM audit_logs a
    JOIN users u ON u.id = a."userId"
    WHERE a."practiceId" = ${WRONG_PRACTICE}
      AND u."practiceId" IS DISTINCT FROM ${WRONG_PRACTICE}
    ORDER BY a."timestamp"
  `;

  // ---- 3. The undeterminable set — reported, never guessed.
  const undeterminable = await prisma.$queryRaw<Undeterminable[]>`
    SELECT a.id, a.action::text AS action
    FROM audit_logs a
    WHERE a."practiceId" IS NULL
      AND a."practiceIdSnapshot" IS NULL
      AND a."userId" IS NULL
    ORDER BY a."timestamp"
  `;

  console.log(`misattributed (determinable) : ${misattributed.length}`);
  console.log(`unattributable (no user)     : ${undeterminable.length}`);

  const byAction = new Map<string, number>();
  for (const r of misattributed as Row[])
    byAction.set(r.action, (byAction.get(r.action) ?? 0) + 1);
  console.log(
    `  by action                  : ${[...byAction]
      .map(([a, n]) => `${a}=${n}`)
      .join(', ') || '(none)'}`,
  );

  // ---- 4. ABORT-ON-MISMATCH. Every determinable row must resolve to a real,
  // non-null practice; if one does not, the classifier is wrong and nothing is
  // written. Remediation is a deliberate act with a guard, never a side effect.
  const unresolved = (misattributed as Row[]).filter((r: Row) => !r.actorPracticeId);
  if (unresolved.length > 0) {
    console.error(
      `\nABORT: ${unresolved.length} row(s) are in the "determinable" set but ` +
        'resolve to no practice. The classifier disagrees with itself — ' +
        'nothing was written.',
    );
    process.exit(2);
  }

  if (!APPLY) {
    console.log('\nREPORT ONLY — nothing written. Re-run with --apply.\n');
    for (const r of misattributed.slice(0, 5))
      console.log(`  sample ${r.id} ${r.action} ${r.practiceId} -> ${r.actorPracticeId}`);
    if (misattributed.length > 5)
      console.log(`  … and ${misattributed.length - 5} more`);
    return;
  }

  // ---- 5. Append. One correction row per original row, in one transaction,
  // written DIRECTLY rather than through `logAudit` — logAudit is
  // fire-and-forget and resolves its own context, and a repair must be neither.
  const now = new Date();
  const corrections = [
    ...(misattributed as Row[]).map((r: Row) => ({
      userId: r.userId,
      userEmailSnapshot: null,
      action: 'AUDIT_ATTRIBUTION_CORRECTED' as never,
      targetId: r.id,
      targetType: 'AuditLog',
      ipAddress: null,
      userAgent: null,
      metadata: {
        wrongPracticeId: r.practiceId,
        correctPracticeId: r.actorPracticeId,
        determinable: true,
        basis: "users.practiceId of the row's own userId",
        correctedAction: r.action,
      } as unknown as object,
      success: true,
      errorCode: null,
      timestamp: now,
      practiceId: r.actorPracticeId,
      practiceIdSnapshot: r.actorPracticeId,
    })),
    ...(undeterminable as Undeterminable[]).map((r: Undeterminable) => ({
      userId: null,
      userEmailSnapshot: null,
      action: 'AUDIT_ATTRIBUTION_CORRECTED' as never,
      targetId: r.id,
      targetType: 'AuditLog',
      ipAddress: null,
      userAgent: null,
      metadata: {
        wrongPracticeId: null,
        correctPracticeId: null,
        determinable: false,
        basis:
          'pre-S4c row: practiceId, practiceIdSnapshot and userId are all ' +
          'NULL, so the tenant is unrecoverable. Stated, not guessed.',
        correctedAction: r.action,
      } as unknown as object,
      success: true,
      errorCode: null,
      timestamp: now,
      practiceId: null,
      practiceIdSnapshot: 'UNATTRIBUTED',
    })),
  ];

  const written = await prisma.$transaction(async (tx: unknown) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const res = await (tx as any).auditLog.createMany({ data: corrections });
    return res.count as number;
  });

  const totalAfter = await prisma.auditLog.count();
  console.log(`\ncorrection rows written      : ${written}`);
  console.log(`audit_logs total AFTER       : ${totalAfter} (was ${total})`);

  // ---- 6. Prove the invariant that matters: nothing was destroyed. The table
  // may only ever have GROWN, and by exactly the number of rows appended.
  if (totalAfter !== total + written) {
    console.error(
      `\nINVARIANT VIOLATED: expected ${total + written} rows, found ${totalAfter}. ` +
        'Something other than this script wrote or deleted concurrently.',
    );
    process.exit(3);
  }
  console.log('append-only invariant holds  : OK (grew by exactly the writes)\n');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
