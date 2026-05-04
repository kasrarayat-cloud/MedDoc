// ============================================================================
// POST /api/auth/check-entitlement
// ----------------------------------------------------------------------------
// Pre-flight gate for the credentials-login flow. Verifies email +
// password, then reports whether the user has MEDDOC_PRO access.
//
// Why a separate endpoint: the login page uses client-side
// next-auth/react `signIn`, which surfaces every failure as the same
// generic "CredentialsSignin" string. This endpoint runs BEFORE
// signIn so we can branch the form's error UX on entitlement —
// specifically to redirect a TRANSCRIBE_MD-only user to app.quillmd.com
// instead of leaving them stuck on a generic "Invalid credentials".
//
// Auth posture:
//   - 5/15min per IP. Same bucket as the live login on this app, so a
//     brute-forcer can't burn extra attempts via the pre-check.
//   - Wrong email / wrong password / inactive / unparseable body all
//     collapse to `INVALID_CREDENTIALS` — anti-enumeration.
//   - Account locked is surfaced specifically so users know to wait.
//   - The cross-app `NO_MEDDOC_PRO_HAS_TRANSCRIBE` reply requires
//     correct credentials AND a product mismatch. The entitlement
//     gate in nextauth.ts authorize() is still the security boundary;
//     this endpoint is purely UX.
//   - Non-existent / wrong-password paths run a dummy bcrypt.compare
//     so wall-clock latency matches the verified path.
// ============================================================================

import { NextResponse } from 'next/server';
import bcrypt from 'bcryptjs';
import { headers } from 'next/headers';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { Product } from '@prisma/client';

import { checkRateLimit, RATE_LIMITS } from '@/lib/rate-limit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const TRANSCRIBE_MD_URL =
  process.env.NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL ?? 'https://app.quillmd.com';

// Module-load constant; used to keep timing parity with the verified
// path on no-account / inactive / wrong-password branches.
const DUMMY_PASSWORD_HASH = bcrypt.hashSync(
  'timing-equalizer-never-matches',
  12
);

const BodySchema = z.object({
  email: z
    .string()
    .email()
    .transform((s) => s.trim().toLowerCase()),
  password: z.string().min(1).max(200),
});

type EntitlementResponse =
  | { ok: true }
  | { ok: false; code: 'INVALID_CREDENTIALS' }
  | {
      ok: false;
      code: 'ACCOUNT_LOCKED';
      retryAfterSeconds: number;
    }
  | {
      ok: false;
      code: 'NO_MEDDOC_PRO_HAS_TRANSCRIBE';
      redirectTo: string;
    }
  | {
      ok: false;
      code: 'RATE_LIMITED';
      retryAfterSeconds: number;
    };

export async function POST(req: Request): Promise<NextResponse> {
  const hdrs = await headers();
  const xff = hdrs.get('x-forwarded-for') ?? '';
  const realIp = hdrs.get('x-real-ip') ?? '';
  const callerIp = xff.split(',')[0]?.trim() || realIp || 'unknown';
  // Mirror of the loopback skip in nextauth.ts's authorize() (Phase 13
  // h9-meddoc-e2e-residual). The pre-check fires once per signIn
  // attempt; CI's e2e suite logs in 5+ times per run from loopback,
  // which would re-trip the IP gate without this skip and surface as
  // a "Too many attempts" error on the login page. The per-account
  // brute-force protection in authorize itself (failedLoginCount +
  // lockedUntil) still fires regardless of origin.
  const isLoopback =
    callerIp === '127.0.0.1' ||
    callerIp === '::1' ||
    callerIp === 'unknown';
  const skipResult = { ok: true, count: 0, limit: 0, retryAfterSeconds: 0 };
  const ipGate = isLoopback
    ? skipResult
    : checkRateLimit(callerIp, RATE_LIMITS.loginIp);
  if (!ipGate.ok) {
    const body: EntitlementResponse = {
      ok: false,
      code: 'RATE_LIMITED',
      retryAfterSeconds: ipGate.retryAfterSeconds,
    };
    return NextResponse.json(body, { status: 429 });
  }

  let raw: unknown;
  try {
    raw = await req.json();
  } catch {
    await bcrypt.compare('x', DUMMY_PASSWORD_HASH).catch(() => false);
    const body: EntitlementResponse = {
      ok: false,
      code: 'INVALID_CREDENTIALS',
    };
    return NextResponse.json(body);
  }
  const parsed = BodySchema.safeParse(raw);
  if (!parsed.success) {
    await bcrypt.compare('x', DUMMY_PASSWORD_HASH).catch(() => false);
    const body: EntitlementResponse = {
      ok: false,
      code: 'INVALID_CREDENTIALS',
    };
    return NextResponse.json(body);
  }

  const user = await prisma.user.findUnique({
    where: { email: parsed.data.email },
    select: {
      id: true,
      passwordHash: true,
      products: true,
      isActive: true,
      lockedUntil: true,
    },
  });

  if (!user || !user.isActive) {
    await bcrypt
      .compare(parsed.data.password, DUMMY_PASSWORD_HASH)
      .catch(() => false);
    const body: EntitlementResponse = {
      ok: false,
      code: 'INVALID_CREDENTIALS',
    };
    return NextResponse.json(body);
  }

  if (user.lockedUntil && user.lockedUntil > new Date()) {
    await bcrypt
      .compare(parsed.data.password, DUMMY_PASSWORD_HASH)
      .catch(() => false);
    const retryAfterSeconds = Math.ceil(
      (user.lockedUntil.getTime() - Date.now()) / 1000
    );
    const body: EntitlementResponse = {
      ok: false,
      code: 'ACCOUNT_LOCKED',
      retryAfterSeconds,
    };
    return NextResponse.json(body);
  }

  const valid = await bcrypt.compare(parsed.data.password, user.passwordHash);
  if (!valid) {
    const body: EntitlementResponse = {
      ok: false,
      code: 'INVALID_CREDENTIALS',
    };
    return NextResponse.json(body);
  }

  // SUPER_ADMIN bypasses both the entitlement gate AND the
  // cross-app-redirect UX — they'd see the platform-admin dashboard
  // next, not the TranscribeMD login.
  const hasSuperAdmin = user.products.includes(Product.SUPER_ADMIN);
  if (!user.products.includes(Product.MEDDOC_PRO) && !hasSuperAdmin) {
    if (user.products.includes(Product.TRANSCRIBE_MD)) {
      const body: EntitlementResponse = {
        ok: false,
        code: 'NO_MEDDOC_PRO_HAS_TRANSCRIBE',
        redirectTo: `${TRANSCRIBE_MD_URL}/login`,
      };
      return NextResponse.json(body);
    }
    // No products at all — match generic so we don't reveal the empty
    // product array as a distinct signal.
    const body: EntitlementResponse = {
      ok: false,
      code: 'INVALID_CREDENTIALS',
    };
    return NextResponse.json(body);
  }

  const body: EntitlementResponse = { ok: true };
  return NextResponse.json(body);
}
