/**
 * ADMIN-3a — `PATCH /api/admin/practices/[id]`.
 *
 * ⚠️ THE FIRST PRACTICE-MUTATING SURFACE IN THE PRODUCT. Until this route there
 * was no way to change a `Practice` row at all — `practice.update` had zero
 * call sites — and four filed rows plus standing ruling #226 were all blocked
 * on that one absence.
 *
 * Guard is the existing `/admin` stack, inherited rather than re-implemented:
 * `adminApi` re-reads the `SUPER_ADMIN` entitlement per request, answers
 * unauthenticated callers with a 404 so the route's existence is not disclosed,
 * enforces ≤12h admin-session freshness, and writes an access audit row.
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';

import { adminApi } from '@/lib/admin-api-gate';
import { ARCHIVE_REFUSALS, updatePractice } from '@/lib/practice-write';

const Body = z
  .object({
    name: z.string().min(1).max(200).optional(),
    slug: z.string().min(3).max(63).optional(),
    isActive: z.boolean().optional(),
    reason: z.string().max(500).optional(),
  })
  .strict(); // ⚠️ `.strict()` — an unknown key is a 400, never a silent drop.

/** Refusals that are the CALLER's fault (400) vs the target's absence (404). */
const NOT_FOUND = new Set(['not_found']);
/**
 * ADMIN-6 — the archive's refusals are the STATE of the world (your own
 * practice, a platform administrator inside it, a visit still processing), not
 * a malformed request. 409 says "valid, and not now", which is what a caller
 * needs to decide whether to retry.
 */
const CONFLICT = new Set<string>(ARCHIVE_REFUSALS);

export const PATCH = adminApi('practices:update', async (req, ctx) => {
  // ⚠️ THE ID COMES FROM THE PATH, THE SAME WAY EVERY OTHER `/api/admin/[id]`
  // route reads it. `AdminContext` deliberately carries only the session and
  // the route key; adding params to it for one route would make the gate's
  // shape depend on its callers.
  const segs = new URL(req.url).pathname.split('/');
  const id = segs[segs.indexOf('practices') + 1];
  if (typeof id !== 'string' || id.length === 0) {
    return NextResponse.json({ error: 'missing practice id' }, { status: 400 });
  }
  const parsed = Body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: 'invalid body' }, { status: 400 });
  }
  const { reason, ...patch } = parsed.data;

  const result = await updatePractice({
    practiceId: id,
    patch,
    actorUserId: ctx.session.user.id,
    reason,
  });

  if (!result.ok) {
    return NextResponse.json(
      { error: result.reason, detail: result.detail },
      {
        status: NOT_FOUND.has(result.reason) ? 404 : CONFLICT.has(result.reason) ? 409 : 400,
      },
    );
  }
  return NextResponse.json({ ok: true, changed: result.changed });
});
