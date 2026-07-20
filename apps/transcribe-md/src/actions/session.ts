'use server';

import { signOut as nextAuthSignOut } from '@/lib/nextauth';
import {
  revokeAllUserSessionsFromCurrentSession,
  revokeSession,
} from '@meddoc/auth';
import { readSignedSessionAuthority } from '@/lib/signed-session-authority';
import { revalidatePath } from 'next/cache';
import { headers } from 'next/headers';

export type SessionRevocationActionResult =
  | { ok: true }
  | {
      ok: false;
      code: 'SESSION_REVOCATION_FAILED';
      retryable: true;
      message: string;
    }
  | {
      ok: false;
      code: 'AUTHENTICATION_REQUIRED';
      retryable: false;
      message: string;
    };

const REVOCATION_FAILED_RESULT = {
  ok: false,
  code: 'SESSION_REVOCATION_FAILED',
  retryable: true,
  message: 'We could not securely end your session. Please try again.',
} as const satisfies SessionRevocationActionResult;

const AUTHENTICATION_REQUIRED_RESULT = {
  ok: false,
  code: 'AUTHENTICATION_REQUIRED',
  retryable: false,
  message: 'Your session is no longer active. Reload this page to continue.',
} as const satisfies SessionRevocationActionResult;

/** Sign out the current user. Revokes the UserSession row (so the JWT's
 *  sessionId claim stops validating) AND clears the NextAuth cookie. */
export async function signOutAction(): Promise<SessionRevocationActionResult> {
  const authority = await readSignedSessionAuthority(await headers());
  if (!authority.cookiePresent) return AUTHENTICATION_REQUIRED_RESULT;
  if (!authority.sessionId) return REVOCATION_FAILED_RESULT;
  try {
    await revokeSession(authority.sessionId);
  } catch {
    // Do not include the driver error: it may contain a credential-bearing
    // connection URL. A failed durable revocation must leave the cookie in
    // place so the user can retry rather than receiving false assurance.
    console.error('[session] current session revocation failed');
    return REVOCATION_FAILED_RESULT;
  }
  await nextAuthSignOut({ redirect: false });
  revalidatePath('/', 'layout');
  return { ok: true };
}

/** Revoke every session for this user (settings → "Sign out all devices").
 *  With single-session enforcement there's only ever one row to delete,
 *  but the button exists so users have an obvious panic-stop. */
export async function signOutAllDevicesAction(): Promise<SessionRevocationActionResult> {
  const authority = await readSignedSessionAuthority(await headers());
  if (!authority.cookiePresent) return AUTHENTICATION_REQUIRED_RESULT;
  if (!authority.sessionId || !authority.userId) {
    return REVOCATION_FAILED_RESULT;
  }
  try {
    const revoked = await revokeAllUserSessionsFromCurrentSession({
      sessionToken: authority.sessionId,
      userId: authority.userId,
    });
    if (!revoked) return AUTHENTICATION_REQUIRED_RESULT;
  } catch {
    // Keep the local cookie until the database confirms every session was
    // revoked. This avoids reporting a successful panic-stop when it failed.
    console.error('[session] all-session revocation failed');
    return REVOCATION_FAILED_RESULT;
  }
  await nextAuthSignOut({ redirect: false });
  revalidatePath('/', 'layout');
  return { ok: true };
}
