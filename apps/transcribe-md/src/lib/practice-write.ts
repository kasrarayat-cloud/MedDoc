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
// ⚠️ `defaultNoteTemplateId` ADDED 2026-09-12 (#318, TEMPLATE-CHOICE-1) — its own
// declared decision, like the note above about retention columns. Unlike those it
// is benign (a pointer to the practice's default note template, or NULL to clear;
// it destroys nothing on write), and it must go through THIS verb so it is audited
// and so the practice-write population stays pinned at three files (ADMIN-3a). The
// caller validates the id is a CERTIFIED template in the practice before setting it.
export const PRACTICE_WRITABLE_FIELDS = [
  'name',
  'slug',
  'isActive',
  'defaultNoteTemplateId',
] as const;
export type PracticeWritableField = (typeof PRACTICE_WRITABLE_FIELDS)[number];

export type PracticePatch = Partial<{
  name: string;
  slug: string;
  isActive: boolean;
  defaultNoteTemplateId: string | null;
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
  | 'no_change';

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
    select: { id: true, name: true, slug: true, isActive: true, defaultNoteTemplateId: true },
  });
  if (!before) return { ok: false, reason: 'not_found', detail: args.practiceId };

  if (typeof args.patch.slug === 'string') {
    const refusal = slugRefusal(args.patch.slug);
    if (refusal) return { ok: false, reason: refusal, detail: args.patch.slug };
    if (args.patch.slug !== before.slug) {
      const taken = await prisma.practice.findUnique({
        where: { slug: args.patch.slug },
        select: { id: true },
      });
      // ⚠️ CHECKED HERE **AND** UNIQUE IN THE DATABASE. This read is for the
      // MESSAGE — `slug_taken` rather than a raw constraint violation — and the
      // column's own `@unique` is what actually holds under a race.
      if (taken && taken.id !== before.id) {
        return { ok: false, reason: 'slug_taken', detail: args.patch.slug };
      }
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

  await prisma.practice.update({
    where: { id: args.practiceId },
    data: args.patch as Prisma.PracticeUpdateInput,
  });

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
