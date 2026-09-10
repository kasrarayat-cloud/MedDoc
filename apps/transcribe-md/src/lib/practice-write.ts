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
 * ⚠️ SO THIS FILE IS DELIBERATELY ONE FUNCTION, NOT FOUR. Four surfaces each
 * growing their own `practice.update` is four readers of one rule — the shape
 * this codebase keeps paying for. One verb, one allowlist, one audit row.
 */
import type { Prisma } from '@prisma/client';

import prisma from '@meddoc/db';

import { logAudit } from './audit';

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
  // ADMIN-2a — the caller's `ifSlugIs` precondition no longer held.
  | 'changed_under_you';

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
  // ⚠️ ADMIN-2a, 2026-09-10 — names that ALREADY EXIST in the quillmd.com zone
  // or are mail/infra labels. A wildcard record does not cover a name the zone
  // already has, so a practice given one would never resolve to us.
  // MEASURED with dig: `send` carries MX `feedback-smtp.us-east-1.amazonses.com`
  // and an SPF TXT (live mail). `www`/`app`/`admin`/`staging` resolve and were
  // already above. The rest do not resolve today; they are the labels mail
  // clients and MTAs probe by convention, so a practice holding one would
  // receive somebody's autodiscovery traffic.
  'send', 'www2', 'mta-sts', 'autodiscover', 'autoconfig', 'quillmd',
  'imap', 'pop', 'pop3', 'webmail',
]);

/**
 * ⚠️ THE MACHINE-SLUG NAMESPACE. Signup mints `solo-<rand>-<base36 ts>`
 * (`actions/auth.ts`), and 195 of 199 production practices still carry one.
 * ONE constant, two readers: the label guard refuses it (a human must not claim
 * a name that looks machine-made), and the owner's one-time claim is allowed
 * ONLY while the current slug is still in it. ADMIN-2 treats these hosts as
 * unroutable, so it must import this rather than retype the prefix.
 */
const MACHINE_SLUG_PREFIX = 'solo-';

export function isMachineSlug(slug: string): boolean {
  return slug.startsWith(MACHINE_SLUG_PREFIX);
}

/**
 * A DNS label: lowercase alphanumerics and hyphens, 3–63 characters, not
 * starting or ending with a hyphen. ⚠️ RFC 1035's shape, because this value
 * becomes a hostname — not a display name, and not a slug in the blog sense.
 */
const SLUG_RE = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$/;

/**
 * ⚠️ `--` IN POSITIONS 3–4 IS RESERVED BY RFC 5891 §4.2.3.1 ("R-LDH" labels).
 * `xn--` is the one in use — punycode, i.e. a lookalike of some other script's
 * name rendered in the address bar — and the others are reserved for future
 * encodings. Refused as a class, not only as `xn--`.
 */
const RESERVED_LDH_RE = /^..--/;

/**
 * ⚠️ THE ONE PREDICATE FOR "MAY THIS BE A PRACTICE'S HOST LABEL". ADMIN-2's
 * host classifier imports this; it must not grow a second copy. Pure — no
 * database — so it can run before any read.
 */
export function practiceLabelRefusal(slug: string): PracticeWriteRefusal | null {
  if (!SLUG_RE.test(slug)) return 'invalid_slug';
  if (slug.startsWith('xn--') || RESERVED_LDH_RE.test(slug)) return 'invalid_slug';
  if (RESERVED_SLUGS.has(slug)) return 'reserved_slug';
  if (isMachineSlug(slug)) return 'reserved_slug';
  return null;
}

/** P2002 read STRUCTURALLY, not via `instanceof` — the sign route records why
 *  (a Prisma error crossing a bundle or mock boundary keeps its shape, not its
 *  prototype). MEASURED: `@prisma/adapter-pg` maps SQLSTATE 23505 to
 *  `UniqueConstraintViolation`, which the client reports as `P2002`. */
function isUniqueViolation(err: unknown): boolean {
  return (err as { code?: unknown } | null)?.code === 'P2002';
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
 * the act ruling #226 has been waiting to perform, and it must be greppable as
 * itself rather than hidden inside a generic update.
 */
export async function updatePractice(args: {
  practiceId: string;
  patch: PracticePatch;
  actorUserId: string;
  reason?: string;
  /**
   * ADMIN-2a — a COMPARE-AND-SET precondition: write only if the row's slug is
   * still exactly this. The owner's one-time claim passes the machine slug it
   * read, so two owners claiming at once cannot both succeed — the second's
   * UPDATE matches zero rows and is refused, not applied over the first.
   */
  ifSlugIs?: string;
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

  const before = await prisma.practice.findUnique({
    where: { id: args.practiceId },
    select: { id: true, name: true, slug: true, isActive: true },
  });
  if (!before) return { ok: false, reason: 'not_found', detail: args.practiceId };

  if (args.ifSlugIs !== undefined && before.slug !== args.ifSlugIs) {
    return { ok: false, reason: 'changed_under_you', detail: before.slug };
  }

  // ⚠️ VALIDATED ONLY WHEN IT CHANGES. The guard is stricter than the rows it
  // now governs: 195 practices hold a `solo-` slug the guard refuses. A patch
  // that carries the CURRENT slug unchanged (a form sending every field) must
  // not be refused for a value nobody is asking to write.
  if (typeof args.patch.slug === 'string' && args.patch.slug !== before.slug) {
    const refusal = practiceLabelRefusal(args.patch.slug);
    if (refusal) return { ok: false, reason: refusal, detail: args.patch.slug };
    const taken = await prisma.practice.findUnique({
      where: { slug: args.patch.slug },
      select: { id: true },
    });
    // ⚠️ CHECKED HERE **AND** UNIQUE IN THE DATABASE. This read is for the
    // MESSAGE — `slug_taken` rather than a raw constraint violation — and the
    // column's own `@unique` is what actually holds under a race (the P2002
    // arm around the write below names that case too).
    if (taken && taken.id !== before.id) {
      return { ok: false, reason: 'slug_taken', detail: args.patch.slug };
    }
  }

  const changed: Record<string, { from: unknown; to: unknown }> = {};
  for (const k of keys as PracticeWritableField[]) {
    const from = (before as Record<string, unknown>)[k];
    const to = (args.patch as Record<string, unknown>)[k];
    if (from !== to) changed[k] = { from, to };
  }
  if (Object.keys(changed).length === 0) {
    return { ok: false, reason: 'no_change', detail: 'patch matches current values' };
  }

  try {
    if (args.ifSlugIs === undefined) {
      await prisma.practice.update({
        where: { id: args.practiceId },
        data: args.patch as Prisma.PracticeUpdateInput,
      });
    } else {
      // ⚠️ `updateMany`, NOT `update`, FOR THE COMPARE-AND-SET: it compiles to
      // ONE `UPDATE … WHERE id AND slug` and reports a count, the shape
      // `changeMemberRoleAction` already relies on. Count 0 = the slug moved
      // between our read and this write, so we refuse and audit nothing.
      const { count } = await prisma.practice.updateMany({
        where: { id: args.practiceId, slug: args.ifSlugIs },
        data: args.patch as Prisma.PracticeUpdateManyMutationInput,
      });
      if (count === 0) {
        return { ok: false, reason: 'changed_under_you', detail: args.ifSlugIs };
      }
    }
  } catch (err) {
    // ⚠️ THE RACE THE `taken` READ ABOVE CANNOT CLOSE. Two writers can both see
    // a slug free; the column's `@unique` then refuses the second, and that
    // arrives here as P2002. Named as `slug_taken` instead of a raw 500 — but
    // ONLY when this patch changes the slug, the one unique column it can
    // write. Any other failure is rethrown, never relabelled.
    if (isUniqueViolation(err) && 'slug' in changed) {
      return { ok: false, reason: 'slug_taken', detail: String(args.patch.slug) };
    }
    throw err;
  }

  const archiving = 'isActive' in changed && changed.isActive!.to === false;
  const restoring = 'isActive' in changed && changed.isActive!.to === true;
  await logAudit({
    action: archiving ? 'PRACTICE_ARCHIVED' : restoring ? 'PRACTICE_RESTORED' : 'PRACTICE_UPDATED',
    practiceId: args.practiceId,
    userId: args.actorUserId,
    metadata: { changed, reason: args.reason ?? null },
  });

  return { ok: true, changed };
}
