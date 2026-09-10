// ============================================================================
// GET /api/admin/users — list users with summary stats
// ----------------------------------------------------------------------------
// Query params:
//   search   — substring match on email or name (case-insensitive)
//   status   — "active" | "inactive" | "locked"
//   limit    — 1..200 (default 50)
//   cursor   — opaque, "createdAt|id" of last row from previous page
//
// Response:
//   { users: [{ id, email, name, role, products, isActive, lockedUntil,
//               createdAt, lastLogin, practiceId }],
//     nextCursor, hasMore }
// ============================================================================

import { randomBytes } from 'node:crypto';

import bcrypt from 'bcryptjs';
import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { AuthTokenPurpose, PracticeRole, Product, UserRole } from '@prisma/client';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';
import { createAuthToken } from '@/lib/auth-tokens';
import { sendPasswordResetEmail } from '@/lib/email';
import { isAutoConfirmDomain } from '@/lib/email-auto-confirm';
import { isEmailDeliveryEnabled } from '@/lib/email-enabled';
import { withPracticeLock, wouldOrphanMember } from '@/lib/last-owner-invariant';

const QuerySchema = z.object({
  search: z.string().trim().min(1).max(200).optional(),
  status: z.enum(['active', 'inactive', 'locked']).optional(),
  limit: z
    .string()
    .optional()
    .transform((s) => {
      const n = s ? Number.parseInt(s, 10) : 50;
      if (!Number.isFinite(n) || n < 1) return 50;
      return Math.min(n, 200);
    }),
  cursor: z.string().optional(),
});

interface UserListRow {
  id: string;
  email: string;
  name: string | null;
  role: string;
  products: string[];
  isActive: boolean;
  lockedUntil: string | null;
  createdAt: string;
  lastLogin: string | null;
  practiceId: string;
}

function parseCursor(s: string | undefined):
  | { createdAt: Date; id: string }
  | null {
  if (!s) return null;
  const idx = s.lastIndexOf('|');
  if (idx < 1) return null;
  const ts = s.slice(0, idx);
  const id = s.slice(idx + 1);
  const d = new Date(ts);
  if (Number.isNaN(d.getTime()) || !id) return null;
  return { createdAt: d, id };
}

export const dynamic = 'force-dynamic';

export const GET = adminApi('users:list', async (req) => {
  const url = new URL(req.url);
  const parsed = QuerySchema.safeParse({
    search: url.searchParams.get('search') ?? undefined,
    status: url.searchParams.get('status') ?? undefined,
    limit: url.searchParams.get('limit') ?? undefined,
    cursor: url.searchParams.get('cursor') ?? undefined,
  });
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Invalid query parameters' },
      { status: 400 }
    );
  }
  const q = parsed.data;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const where: any = {};
  if (q.search) {
    where.OR = [
      { email: { contains: q.search, mode: 'insensitive' } },
      { name: { contains: q.search, mode: 'insensitive' } },
    ];
  }
  // Phase 6Z fix: previously this set `where.OR = where.OR ?? []` which
  // produced an empty-OR-array predicate when no search was supplied —
  // Prisma treats `OR: []` as "match no rows", so `?status=active`
  // (no search, no cursor) silently returned an empty page even though
  // the DB had matching active users. The lock-state condition needs
  // to be combined as AND only.
  if (q.status === 'active') {
    where.isActive = true;
    where.AND = [
      { OR: [{ lockedUntil: null }, { lockedUntil: { lt: new Date() } }] },
    ];
  } else if (q.status === 'inactive') {
    where.isActive = false;
  } else if (q.status === 'locked') {
    where.lockedUntil = { gt: new Date() };
  }

  // Cursor predicate is added as a separate AND clause rather than
  // overwriting `where.OR`. The previous version stomped on the search
  // OR-predicate from above, causing pagination to lose the search
  // filter on the second page.
  const cur = parseCursor(q.cursor);
  if (cur) {
    const cursorOr = {
      OR: [
        { createdAt: { lt: cur.createdAt } },
        { createdAt: cur.createdAt, id: { lt: cur.id } },
      ],
    };
    where.AND = where.AND ? [...where.AND, cursorOr] : [cursorOr];
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rows: any[] = await prisma.user.findMany({
    where,
    orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
    take: q.limit + 1,
    select: {
      id: true,
      email: true,
      name: true,
      role: true,
      products: true,
      isActive: true,
      lockedUntil: true,
      createdAt: true,
      lastLogin: true,
      practiceId: true,
    },
  });

  const hasMore = rows.length > q.limit;
  const page = hasMore ? rows.slice(0, q.limit) : rows;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const users: UserListRow[] = page.map((r: any) => ({
    id: r.id,
    email: r.email,
    name: r.name ?? null,
    role: String(r.role),
    products: (r.products ?? []).map(String),
    isActive: r.isActive,
    lockedUntil: r.lockedUntil?.toISOString() ?? null,
    createdAt: r.createdAt.toISOString(),
    lastLogin: r.lastLogin?.toISOString() ?? null,
    practiceId: r.practiceId,
  }));

  const last = page[page.length - 1];
  const nextCursor =
    hasMore && last
      ? `${last.createdAt.toISOString()}|${last.id}`
      : null;

  return NextResponse.json({ users, nextCursor, hasMore });
});

// ============================================================================
// POST /api/admin/users — create an account INSIDE AN EXISTING PRACTICE
// ----------------------------------------------------------------------------
// PORTED from the retired meddoc-pro console (`createUserAction`), under ruling
// #310 step 3 — "PORT, not BUILD, never REVIVE" — with the four things the
// original got wrong for THIS app corrected rather than copied:
//
//   1. ⚠️ NO PRACTICE IS EVER MINTED HERE. The body names an EXISTING practice
//      and the route refuses an unknown one. Minting a practice would make this
//      a FOURTH promo-grant door ("a practice with an active member has a
//      grant"), and rulings #99/#100 authorized exactly three.
//   2. ⚠️ THE ROLE IS EXPLICIT. The original wrote every new account as an
//      OWNER of the creating admin's own practice — i.e. of the platform
//      operator's practice. `practiceRole` is required in the body.
//   3. ⚠️ `products` IS `[TRANSCRIBE_MD]`. The schema default is `[MEDDOC_PRO]`,
//      and `nextauth.ts` refuses to sign in a user without TRANSCRIBE_MD — the
//      original's shape would have produced accounts that cannot log in here.
//   4. ⚠️ NO ADMIN-TYPED PASSWORD. The account is created with a random secret
//      nobody ever sees, and the person sets their own password through the
//      SAME reset-token email the admin "Reset password" door sends (1-hour,
//      single-use, prior tokens invalidated). An admin never knows a
//      clinician's password, and nothing here stores or returns one.
//
// `emailVerified` follows signup's own rule — stamped only when email delivery
// is off (or the QA auto-confirm domain), so the login gate treats an
// admin-created account exactly as it treats a self-signup.
//
// The INSERT runs inside the practice lock: it adds a member to an existing
// practice, which is the write `users_no_orphan_member` locks on (#289).
// ============================================================================

const CreateBody = z
  .object({
    email: z.string().email().max(254),
    name: z.string().trim().min(1).max(200),
    practiceId: z.string().trim().min(1).max(64),
    practiceRole: z.enum(['OWNER', 'CLINICIAN', 'TECH']),
    role: z.enum(['DOCTOR', 'STAFF', 'ADMIN']).optional(),
  })
  .strict();

function isUniqueViolation(err: unknown): boolean {
  return !!err && typeof err === 'object' && (err as { code?: unknown }).code === 'P2002';
}

export const POST = adminApi('users:create', async (req, ctx) => {
  const raw = await req.json().catch(() => null);
  const parsed = CreateBody.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Body must carry email, name, practiceId and practiceRole (OWNER, CLINICIAN, TECH)' },
      { status: 400 }
    );
  }
  const email = parsed.data.email.trim().toLowerCase();
  const { name, practiceId } = parsed.data;
  const practiceRole = parsed.data.practiceRole as PracticeRole;
  const role = (parsed.data.role ?? 'DOCTOR') as UserRole;

  const practice = await prisma.practice.findUnique({
    where: { id: practiceId },
    select: { id: true, name: true },
  });
  if (!practice) {
    return NextResponse.json(
      { error: 'No practice with that id. Accounts are created inside an existing practice.', reason: 'PRACTICE_NOT_FOUND' },
      { status: 404 }
    );
  }

  const existing = await prisma.user.findUnique({ where: { email }, select: { id: true } });
  if (existing) {
    return NextResponse.json(
      { error: 'An account with that email already exists.', reason: 'EMAIL_TAKEN' },
      { status: 409 }
    );
  }

  // The row exactly as it will be inserted, predicate columns included — the
  // orphan refusal is asked about THIS object, and the create writes it.
  const row = {
    practiceRole,
    isActive: true,
    deactivatedAt: null,
    suspendedAt: null,
    softDeletedAt: null,
  };
  const orphan = await wouldOrphanMember({ kind: 'insert', practiceId, row });
  if (orphan.wouldOrphan) {
    return NextResponse.json(
      { error: orphan.reason, reason: 'NO_ACTIVE_OWNER', restorableOwners: orphan.restorableOwners },
      { status: 409 }
    );
  }

  // A secret nobody sees: the account cannot be signed into until its owner
  // sets a password through the emailed link.
  const passwordHash = await bcrypt.hash(randomBytes(32).toString('base64url'), 12);
  const verifyEnabled = isEmailDeliveryEnabled() && !isAutoConfirmDomain(email);

  let created: { id: string };
  try {
    created = await prisma.$transaction((tx) =>
      withPracticeLock(tx, practiceId, async () =>
        tx.user.create({
          data: {
            ...row,
            email,
            name,
            passwordHash,
            role,
            practiceId,
            products: [Product.TRANSCRIBE_MD],
            emailVerified: verifyEnabled ? null : new Date(),
          },
          select: { id: true },
        }),
      ),
    );
  } catch (err) {
    // The pre-check above lost a race with a concurrent create of the same
    // address; the unique index is the authority.
    if (isUniqueViolation(err)) {
      return NextResponse.json(
        { error: 'An account with that email already exists.', reason: 'EMAIL_TAKEN' },
        { status: 409 }
      );
    }
    throw err;
  }

  await logAudit({
    action: 'USER_CREATED',
    targetType: 'User',
    targetId: created.id,
    metadata: {
      createdVia: 'admin_console',
      practiceRole,
      role,
      targetEmail: email,
      actorEmail: ctx.session.user.email,
    },
    practiceId,
  });

  // ── THE CREDENTIAL — the reset door's primitives, verbatim. ────────────────
  // A send failure does NOT undo the account: it exists, it simply has no
  // password yet, and the drawer's "Reset password" re-sends the same link.
  const baseUrl = process.env.AUTH_URL?.replace(/\/$/, '') ?? 'https://app.quillmd.com';
  let emailSent = false;
  let errorCode: string | null = null;
  try {
    const { token } = await createAuthToken({
      userId: created.id,
      purpose: AuthTokenPurpose.PASSWORD_RESET,
      expiresInMs: 60 * 60 * 1000,
    });
    await sendPasswordResetEmail({
      toEmail: email,
      resetUrl: `${baseUrl}/reset-password?token=${encodeURIComponent(token)}`,
      userName: name,
    });
    emailSent = true;
  } catch (err) {
    errorCode = err instanceof Error ? err.name : 'UNKNOWN';
    console.error('[admin:create-user] credential email failed:', err);
  }

  await logAudit({
    action: 'USER_PASSWORD_RESET_TRIGGERED',
    targetType: 'User',
    targetId: created.id,
    success: emailSent,
    errorCode,
    metadata: { via: 'admin_create', targetEmail: email, actorEmail: ctx.session.user.email },
    practiceId,
  });

  return NextResponse.json({
    ok: true,
    user: { id: created.id, email, practiceId, practiceName: practice.name, practiceRole },
    credentialEmail: { sent: emailSent, errorCode },
  });
});
