/**
 * ADMIN-3a — THE ONLY WRITE PATH TO A `Practice` ROW.
 *
 * ⚠️ THERE WAS NONE. `practice.update` had **zero call sites** across `apps/`
 * and `packages/`, against a positive control of 15+ `user.update` sites — and
 * FOUR FILED ROWS PLUS A STANDING RULING all waited on that one missing verb,
 * each filed as though it owned the problem:
 *
 *   · ADMIN-3  — set a practice's specialty
 *   · ADMIN-6  — archive a practice
 *   · ADMIN-2a — change a slug (195 of 199 are machine-generated `solo-…`)
 *   · ruling #226 — blocked since 2026-09-07, and it names this exact cause:
 *     *"NO ADMIN PATH WRITES A PRACTICE ROW."*
 *
 *   ⚠️ CORRECTION, 2026-09-10 (ADMIN-6) — the #226 line above was STALE when it
 *   was written. #226 had ALREADY been executed on 2026-09-07 as a raw-SQL
 *   one-shot under ruling #230 (declaration `071b80ab`, judgement `fca86bb0`,
 *   9 of 9), recorded on `main` by PR #1041 as `ef21f059`. The recon looked in
 *   `docs/foundation/mutations/` and the declaration lives in
 *   `docs/deploy-declarations/`. What #226 still lacks is its six
 *   `PRACTICE_ARCHIVED` audit rows (#230's deferral) — a separate ruled
 *   mutation, not this file.
 *
 * ⚠️ SO THIS FILE IS DELIBERATELY ONE FUNCTION, NOT FOUR. Four surfaces each
 * growing their own `practice.update` is four readers of one rule — the shape
 * this codebase keeps paying for. One verb, one allowlist, one audit row.
 *
 * ⚠️ ADMIN-6 / ADMIN-6a — `isActive` IS NOW A SWITCH, NOT A MARKER. Three doors
 * read it through `@meddoc/db/practice-admits` (login, every request, invite
 * redemption), so an archive logs a whole practice out. That makes this verb a
 * lockout lever, and it therefore refuses BY NAME, inside the same transaction
 * as the write:
 *
 *   · `own_practice`              — the actor would lock themselves out;
 *   · `practice_has_super_admin`  — a platform administrator would be locked
 *                                    out, and they are who restores practices;
 *   · `visits_in_flight`          — a visit is still being processed. The
 *                                    worker is DELIBERATELY not a door (it is on
 *                                    the clinical generation path), so the act
 *                                    refuses instead of stranding a visit.
 *
 * ⚠️ AND IT WRITES **ONLY THE PRACTICE ROW** (design A, ruling #310(b) — never
 * strand). No `users` row changes, so neither `users_last_owner_guard` nor
 * `users_no_orphan_member` fires, and a restore (`isActive: true`) returns every
 * member EXACTLY to the state they were in, including any suspension or
 * deactivation they already carried.
 */
import { Prisma, TranscribeVisitStatus } from '@prisma/client';

import prisma from '@meddoc/db';
import type { TransactionClient } from '@meddoc/db';

/**
 * ⚠️ AN ALLOWLIST, AND IT FAILS CLOSED ON ANYTHING ABSENT.
 *
 * A patch naming a field that is not here is REFUSED — not ignored. Ignoring is
 * how a caller silently fails to change what it asked to change, and the caller
 * that most often does this is a future one nobody is watching.
 *
 * ⚠️ AND THE RETENTION COLUMNS ARE DELIBERATELY NOT HERE. `audioRetentionDays`
 * and `transcriptRetentionDays` decide how long clinical material is kept;
 * shortening one destroys records on a schedule. That is not a field an
 * ordinary practice-update verb should be able to touch on the way past, and
 * adding it is its own decision with its own declaration.
 */
export const PRACTICE_WRITABLE_FIELDS = ['name', 'slug', 'isActive'] as const;
export type PracticeWritableField = (typeof PRACTICE_WRITABLE_FIELDS)[number];

export type PracticePatch = Partial<{
  name: string;
  slug: string;
  isActive: boolean;
}>;

export type PracticeWriteResult =
  | { ok: true; changed: Record<string, { from: unknown; to: unknown }> }
  | { ok: false; reason: PracticeWriteRefusal; detail: string };

export type PracticeWriteRefusal =
  | 'not_found'
  | 'unknown_field'
  | 'invalid_slug'
  | 'reserved_slug'
  | 'slug_taken'
  | 'no_change'
  // ADMIN-6 — the archive's own refusals. Each is a STATE of the world, not a
  // malformed request, which is why the route answers them 409.
  | 'actor_unknown'
  | 'own_practice'
  | 'practice_has_super_admin'
  | 'visits_in_flight';

/** The archive refusals, for the route's status mapping. */
export const ARCHIVE_REFUSALS: readonly PracticeWriteRefusal[] = [
  'actor_unknown',
  'own_practice',
  'practice_has_super_admin',
  'visits_in_flight',
];

/**
 * ⚠️ THE STATUSES A VISIT CAN **REST** IN — everything else is "still being
 * processed". Stated as the SETTLED set and derived by subtraction, so a status
 * added to the enum tomorrow counts as IN FLIGHT until somebody says otherwise.
 * Listing the in-flight statuses instead would fail OPEN on the new one: the
 * archive would log a practice out under a visit the worker is still writing.
 *
 * `FAILED` rests: the schema calls it "terminal until the user retries", and a
 * retry needs a session, which the archive ends.
 */
const SETTLED_VISIT_STATUSES: ReadonlySet<string> = new Set<TranscribeVisitStatus>([
  'READY',
  'FAILED',
  'SIGNED',
]);
export const IN_FLIGHT_VISIT_STATUSES: readonly TranscribeVisitStatus[] = (
  Object.values(TranscribeVisitStatus) as TranscribeVisitStatus[]
).filter((s) => !SETTLED_VISIT_STATUSES.has(s));

/**
 * ⚠️ THE RESERVED NAMES — ADMIN-2 KEYS HOSTNAMES ON THIS COLUMN.
 *
 * A slug becomes a subdomain, so a practice called `admin` or `api` would take
 * a name the platform already answers on. Refused here rather than discovered
 * at ingress, because by then the row exists and something is already routing.
 */
const RESERVED_SLUGS = new Set([
  'www', 'app', 'admin', 'api', 'pro', 'mail', 'smtp', 'ftp', 'ns', 'mx',
  'static', 'assets', 'cdn', 'status', 'health', 'auth', 'login', 'signup',
  'billing', 'support', 'help', 'docs', 'blog', 'test', 'staging', 'qa', 'dev',
  'preview', 'internal', 'system', 'root', 'localhost',
]);

/**
 * A DNS label: lowercase alphanumerics and hyphens, 3–63 characters, not
 * starting or ending with a hyphen. ⚠️ RFC 1035's shape, because this value
 * becomes a hostname — not a display name, and not a slug in the blog sense.
 */
const SLUG_RE = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$/;

export function slugRefusal(slug: string): PracticeWriteRefusal | null {
  if (!SLUG_RE.test(slug)) return 'invalid_slug';
  if (RESERVED_SLUGS.has(slug)) return 'reserved_slug';
  return null;
}

/**
 * Is this member a platform administrator?
 *
 * ⚠️ BOTH SPELLINGS, FAIL-CLOSED. The `/admin` gate's authority is the
 * `products` array (`admin-api-gate.ts` refuses without `Product.SUPER_ADMIN`),
 * while `role = SUPER_ADMIN` is the older axis the schema still carries.
 * Checking only one would let an archive lock out somebody the other calls an
 * administrator.
 */
function isPlatformAdmin(m: { role: string | null; products: readonly string[] | null }): boolean {
  return m.role === 'SUPER_ADMIN' || (m.products ?? []).includes('SUPER_ADMIN');
}

type LockedPractice = { id: string; name: string; slug: string; isActive: boolean };

class Refusal extends Error {
  constructor(
    public readonly reason: PracticeWriteRefusal,
    public readonly detail: string,
  ) {
    super(`${reason}: ${detail}`);
  }
}

/**
 * Update a practice, audited.
 *
 * ⚠️ THE AUDIT ROW CARRIES `from` AND `to`, NOT JUST THE NEW VALUE. "Somebody
 * set the slug to `northside`" does not tell an incident what it used to be,
 * and the previous value is exactly what a recovery needs. Same reasoning the
 * platform-rate table uses one arc over.
 *
 * ⚠️ AND `isActive` GETS ITS OWN ACTION. An archive is not a field edit — it is
 * the act ruling #226 was waiting on, and it must be greppable as itself rather
 * than hidden inside a generic update.
 *
 * ⚠️ ADMIN-6 — ONE READ COMMITTED TRANSACTION, FOR EVERY PATCH:
 *
 *   1. `SELECT … FOR UPDATE` the practice, so two concurrent writes serialize
 *      and each computes `from` on the value the other COMMITTED. Without the
 *      lock both read `true`, both write `false`, and two PRACTICE_ARCHIVED rows
 *      each claim a `true → false` only one of them performed.
 *   2. refuse by name (above);
 *   3. write the practice row — and nothing else;
 *   4. write the audit row with `tx.auditLog.create`, INSIDE the transaction.
 *      `logAudit` swallows its own failures by design, which is right for an
 *      access log and wrong for a lifecycle act: an archive whose audit row
 *      failed would have landed with no record that anyone did it. Here a
 *      failed audit insert rolls the archive back.
 */
export async function updatePractice(args: {
  practiceId: string;
  patch: PracticePatch;
  actorUserId: string;
  reason?: string;
}): Promise<PracticeWriteResult> {
  const keys = Object.keys(args.patch);
  // FAIL CLOSED on an unknown field, before reading anything.
  const unknown = keys.filter(
    (k) => !(PRACTICE_WRITABLE_FIELDS as readonly string[]).includes(k),
  );
  if (unknown.length > 0) {
    return { ok: false, reason: 'unknown_field', detail: unknown.join(', ') };
  }
  if (keys.length === 0) return { ok: false, reason: 'no_change', detail: 'empty patch' };

  // The slug's SHAPE needs no database, so it is refused before the transaction.
  if (typeof args.patch.slug === 'string') {
    const refusal = slugRefusal(args.patch.slug);
    if (refusal) return { ok: false, reason: refusal, detail: args.patch.slug };
  }

  try {
    return await prisma.$transaction(
      async (tx: TransactionClient) => {
        // 1 · THE LOCK. Raw because Prisma has no `FOR UPDATE`; the table name
        // is the `@@map` of `Practice`.
        const locked = await tx.$queryRaw<LockedPractice[]>`
          SELECT id, name, slug, "isActive" FROM practices WHERE id = ${args.practiceId} FOR UPDATE`;
        const before = locked[0];
        if (!before) throw new Refusal('not_found', args.practiceId);

        if (typeof args.patch.slug === 'string' && args.patch.slug !== before.slug) {
          const taken = await tx.practice.findUnique({
            where: { slug: args.patch.slug },
            select: { id: true },
          });
          // ⚠️ CHECKED HERE **AND** UNIQUE IN THE DATABASE. This read is for the
          // MESSAGE — `slug_taken` rather than a raw constraint violation — and
          // the column's own `@unique` is what actually holds under a race.
          if (taken && taken.id !== before.id) {
            throw new Refusal('slug_taken', args.patch.slug);
          }
        }

        const changed: Record<string, { from: unknown; to: unknown }> = {};
        for (const k of keys as PracticeWritableField[]) {
          const from = (before as Record<string, unknown>)[k];
          const to = (args.patch as Record<string, unknown>)[k];
          if (from !== to) changed[k] = { from, to };
        }
        if (Object.keys(changed).length === 0) {
          throw new Refusal('no_change', 'patch matches current values');
        }

        const archiving = 'isActive' in changed && changed.isActive!.to === false;
        const restoring = 'isActive' in changed && changed.isActive!.to === true;

        const actor = await tx.user.findUnique({
          where: { id: args.actorUserId },
          select: { practiceId: true, email: true },
        });

        // ⚠️ THE MEMBER SNAPSHOT — IDS, ROLES AND LIFECYCLE COLUMNS, NEVER A
        // NAME OR AN EMAIL. It is what makes a restore checkable: the row says
        // who was in the practice and in what state at the moment it closed, so
        // "everyone came back exactly as they were" is a comparison, not a hope.
        const members =
          archiving || restoring
            ? await tx.user.findMany({
                where: { practiceId: args.practiceId },
                select: {
                  id: true,
                  role: true,
                  practiceRole: true,
                  products: true,
                  isActive: true,
                  deactivatedAt: true,
                  suspendedAt: true,
                  softDeletedAt: true,
                  forceLogoutAt: true,
                },
                orderBy: { id: 'asc' },
              })
            : [];

        if (archiving) {
          // ⚠️ FAIL-CLOSED ON AN ACTOR WE CANNOT FIND. `adminApi` has just
          // verified them, so this is unreachable in practice — and if it is
          // reached, "is this the actor's own practice?" has no answer, which
          // is not the same as "no".
          if (!actor) throw new Refusal('actor_unknown', args.actorUserId);
          if (actor.practiceId === args.practiceId) {
            throw new Refusal(
              'own_practice',
              'archiving your own practice would end your own session; another platform administrator must do it',
            );
          }
          const admins = members.filter(isPlatformAdmin);
          if (admins.length > 0) {
            throw new Refusal(
              'practice_has_super_admin',
              `${admins.length} platform administrator(s) in this practice would be locked out: ${admins
                .map((a) => a.id)
                .join(', ')}`,
            );
          }
          // ⚠️ BOTH TENANCIES. A visit belongs to the practice that owns the
          // CHART (`practiceId`, #287) and is processed with its AUTHOR's
          // practice (`user.practiceId`). A locum visit differs on the two, and
          // archiving either practice ends a session the visit depends on.
          //
          // ⚠️ SOFT-DELETED VISITS ARE COUNTED TOO. A deleted visit in a
          // processing status may still have a job on the queue, and "the row
          // is hidden" is not "the worker has stopped".
          const inFlight = await tx.transcribeVisit.findMany({
            where: {
              status: { in: [...IN_FLIGHT_VISIT_STATUSES] },
              OR: [{ practiceId: args.practiceId }, { user: { practiceId: args.practiceId } }],
            },
            select: { id: true, status: true },
            orderBy: { id: 'asc' },
            take: 20,
          });
          if (inFlight.length > 0) {
            throw new Refusal(
              'visits_in_flight',
              `${inFlight.length}${inFlight.length === 20 ? '+' : ''} visit(s) still being processed: ${inFlight
                .map((v) => `${v.id}(${v.status})`)
                .join(', ')}`,
            );
          }
        }

        // 3 · THE WRITE — the practice row and NOTHING else (design A).
        await tx.practice.update({
          where: { id: args.practiceId },
          data: args.patch as Prisma.PracticeUpdateInput,
        });

        // 4 · THE AUDIT ROW, IN THE TRANSACTION.
        await tx.auditLog.create({
          data: {
            userId: args.actorUserId,
            userEmailSnapshot: actor?.email ?? null,
            action: archiving
              ? 'PRACTICE_ARCHIVED'
              : restoring
                ? 'PRACTICE_RESTORED'
                : 'PRACTICE_UPDATED',
            targetType: 'Practice',
            targetId: args.practiceId,
            metadata: {
              changed,
              reason: args.reason ?? null,
              ...(archiving || restoring
                ? {
                    members: members.map((m) => ({
                      id: m.id,
                      role: m.role,
                      practiceRole: m.practiceRole,
                      products: m.products,
                      isActive: m.isActive,
                      deactivatedAt: m.deactivatedAt?.toISOString() ?? null,
                      suspendedAt: m.suspendedAt?.toISOString() ?? null,
                      softDeletedAt: m.softDeletedAt?.toISOString() ?? null,
                      forceLogoutAt: m.forceLogoutAt?.toISOString() ?? null,
                    })),
                  }
                : {}),
            } as Prisma.InputJsonValue,
            success: true,
            practiceId: args.practiceId,
            practiceIdSnapshot: args.practiceId,
          },
        });

        return { ok: true as const, changed };
      },
      { isolationLevel: Prisma.TransactionIsolationLevel.ReadCommitted },
    );
  } catch (err) {
    if (err instanceof Refusal) return { ok: false, reason: err.reason, detail: err.detail };
    throw err;
  }
}
