// ============================================================================
// Authentication & RBAC Helpers (now backed by real NextAuth)
// ----------------------------------------------------------------------------
// This file is the only auth surface used by the rest of the app — server
// components, server actions, and the audit logger all import from here.
// All call sites stay the same; the only thing that changed is what powers
// `getSession()` under the hood.
//
// HISTORY:
//   v1: Mock session hard-coded for development.
//   v2: NextAuth v5 + PrismaAdapter + Credentials provider (this version).
// ============================================================================

import { headers } from 'next/headers';
import { auth } from '@/lib/nextauth';
import prisma from '@/lib/db';

export type UserRole = 'DOCTOR' | 'ADMIN' | 'STAFF' | 'SUPER_ADMIN';

export interface Session {
  user: {
    id: string;
    email: string;
    /** Display name (mapped from NextAuth's `name` field) */
    fullName: string;
    role: UserRole;
    /** Multi-tenancy: the practice this user belongs to. Used to scope
     *  every query/action to a single tenant. */
    practiceId: string;
  };
}

/**
 * Toggle for development environments without a real database.
 * When `true`, getSession() returns a mock DOCTOR so the CRM UI is usable
 * without a real Postgres + user table. ONLY controlled by AUTH_USE_MOCK —
 * NEVER auto-enables based on NODE_ENV, because a silent fallback to a
 * DOCTOR session hides real auth failures (e.g., middleware approves an
 * ADMIN but the layout's getSession returns DOCTOR → wrong redirect).
 */
const USE_MOCK_SESSION = process.env.AUTH_USE_MOCK === 'true';

function getMockSession(): Session {
  return {
    user: {
      id: 'mock_user_doctor_01',
      email: 'doctor@meddoc.local',
      fullName: 'Dr. Bakhtiar Moussazadeh',
      role: 'DOCTOR',
      // Mock sessions land in the default practice so filtered queries
      // still return the seeded mock data.
      practiceId: 'clinic_main',
    },
  };
}

/**
 * Get the current authenticated user session.
 * Returns null if not logged in.
 *
 * Production: returns a real NextAuth session, populated with id + role
 * via JWT callbacks in `src/lib/nextauth.ts`.
 *
 * Dev (no DB / no signed-in user): falls back to a mock DOCTOR session
 * so server components can still render — toggle off via `AUTH_USE_MOCK=false`.
 */
export async function getSession(): Promise<Session | null> {
  // 1. Try the real NextAuth session first
  try {
    const nextAuthSession = await auth();
    if (nextAuthSession?.user?.id) {
      let role = nextAuthSession.user.role as UserRole | undefined;
      let practiceId = nextAuthSession.user.practiceId as string | undefined;

      // Always hit the DB once per getSession to re-verify (a) the user
      // still exists and (b) they're still active. This makes Deactivate
      // User in the admin panel take effect on the user's next request
      // instead of waiting for their 8h JWT to expire — critical for
      // emergency access revocation. Side benefit: fills in role and
      // practiceId for freshly-issued JWTs where those claims haven't
      // settled yet.
      //
      // Perf: one indexed PK lookup, ~1ms on the same box. Cached by
      // Next's per-request memoization (each render tree calls getSession
      // once).
      try {
        const dbUser = await prisma.user.findUnique({
          where: { id: nextAuthSession.user.id },
          select: { role: true, isActive: true, practiceId: true },
        });
        if (!dbUser || !dbUser.isActive) {
          // User deactivated or deleted while logged in — treat as no
          // session so protected layouts bounce to /login.
          return null;
        }
        if (!role && dbUser.role) role = dbUser.role as UserRole;
        // practiceId is the tenant boundary — always prefer the DB's
        // current value over a stale JWT claim, in case the user was
        // migrated between practices (unusual but possible for platform
        // operations).
        if (dbUser.practiceId) practiceId = dbUser.practiceId;
      } catch {
        // DB unreachable — fail open (don't log everyone out during a
        // transient DB blip). The user sees their cached session until
        // the DB recovers.
      }

      if (role && practiceId) {
        return {
          user: {
            id: nextAuthSession.user.id,
            email: nextAuthSession.user.email ?? '',
            fullName: nextAuthSession.user.name ?? 'Unknown',
            role,
            practiceId,
          },
        };
      }
    }
  } catch {
    // auth() can throw if NextAuth is misconfigured or if the request
    // context isn't available — fall through to mock in dev.
  }

  // 2. Dev fallback so the CRM UI keeps working without a real DB
  if (USE_MOCK_SESSION) {
    return getMockSession();
  }

  // 3. Production — no session means not logged in
  return null;
}

/**
 * Authorization guard. Throws an `AuthError` if the user is not logged in
 * or does not have one of the allowed roles. Use at the top of every
 * server action / API route that touches PHI.
 *
 * @example
 *   await requireRole(['DOCTOR', 'ADMIN']);
 */
export async function requireRole(allowed: UserRole[]): Promise<Session> {
  const session = await getSession();
  if (!session) {
    throw new AuthError('UNAUTHENTICATED', 'You must be logged in.');
  }
  if (!allowed.includes(session.user.role)) {
    throw new AuthError(
      'FORBIDDEN',
      `Role ${session.user.role} cannot perform this action.`
    );
  }
  return session;
}

/**
 * Get the request IP and user-agent from Next.js headers (server-side only).
 * Used by the audit logger.
 */
export async function getRequestContext(): Promise<{
  ipAddress: string | null;
  userAgent: string | null;
}> {
  try {
    const h = await headers();
    const ipAddress =
      h.get('x-forwarded-for')?.split(',')[0]?.trim() ||
      h.get('x-real-ip') ||
      null;
    const userAgent = h.get('user-agent') || null;
    return { ipAddress, userAgent };
  } catch {
    return { ipAddress: null, userAgent: null };
  }
}

/**
 * Custom error for auth failures — lets API routes / actions return
 * 401/403 instead of a generic 500.
 */
export class AuthError extends Error {
  code: 'UNAUTHENTICATED' | 'FORBIDDEN';

  constructor(code: 'UNAUTHENTICATED' | 'FORBIDDEN', message: string) {
    super(message);
    this.name = 'AuthError';
    this.code = code;
  }
}
