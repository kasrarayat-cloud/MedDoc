// ============================================================================
// ADMIN-5 — THE SUPER_ADMIN DOORS' LAST-OWNER REFUSAL, AUDITED, IN ONE SHAPE.
// ----------------------------------------------------------------------------
// ⚠️ TWO SOURCES, ONE ANSWER. The admin `suspend` and `soft-delete` routes can
// learn that a write would strand a practice in two ways:
//
//   · `precheck` — `wouldStrandPractice` said so BEFORE the write (the friendly
//     refusal, ruling #210). Until ADMIN-5 this 409 wrote NO audit row, so the
//     one administrative act this invariant exists to stop left no trace when
//     it was stopped.
//   · `trigger`  — the pre-check passed (it runs outside the lock, so two
//     admins can both pass it) and `users_last_owner_guard` refused the write.
//     Until ADMIN-5 this was a raw 500 carrying a Postgres error, which the
//     routes' own comments admitted.
//
// Both now produce the same 409 body and the same audit row, differing only in
// `source`. One shape, because four hand-written copies (two routes × two
// sources) are four readers of one refusal, and the copy that drifts is the one
// nobody reads.
//
// ⚠️ THIS ENFORCES NOTHING. The trigger has already decided (or will); this
// only records and speaks. Metadata is ids and counts — never a name or email.
// ============================================================================

import { NextResponse } from 'next/server';

import { logAudit } from '@/lib/audit';

export type LastOwnerRefusalSource = 'precheck' | 'trigger';

export async function refuseLastOwner(args: {
  targetId: string;
  practiceId: string;
  attempted: 'SUSPEND' | 'SOFT_DELETE';
  source: LastOwnerRefusalSource;
  reason: string;
  membersLeft: number;
}): Promise<NextResponse> {
  await logAudit({
    action: 'PRACTICE_ADMIN_REFUSED',
    targetType: 'User',
    targetId: args.targetId,
    practiceId: args.practiceId,
    metadata: {
      refusal: 'LAST_OWNER',
      attempted: args.attempted,
      source: args.source,
      membersLeft: args.membersLeft,
      practiceId: args.practiceId,
    },
  });
  return NextResponse.json(
    { error: args.reason, reason: 'LAST_OWNER', membersLeft: args.membersLeft },
    { status: 409 },
  );
}
