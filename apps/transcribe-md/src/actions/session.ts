'use server';

import { revalidatePath } from 'next/cache';

import { revokeSession, revokeAllUserSessions } from '@meddoc/auth';
import { getCurrentSessionId } from '@/lib/auth';
import { auth, signOut as nextAuthSignOut } from '@/lib/nextauth';

// ============================================================================
// SIGN-OUT IS A SERVER ACTION, AND THAT IS THE FIX — RULING #181(a)/(b).
// ----------------------------------------------------------------------------
// ⚠️ THE DEFECT THIS REPLACES, TRACED END TO END. Every client surface called
// `signOut()` from `next-auth/react`, which POSTs to `/api/auth/signout` over
// HTTP. In `@auth/core/lib/index.js` the signout case reads:
//
//     case "signout":
//         validateCSRF(action, csrfTokenVerified);
//         return await actions.signOut(cookies, sessionStore, options);
//
// `events.signOut` — which holds BOTH the `revokeSession` call and the LOGOUT
// audit row — is reachable ONLY from `actions.signOut`, i.e. strictly AFTER the
// CSRF gate. So a failed CSRF check meant:
//
//   · the UserSession row was never deleted — THE SERVER KEPT HONOURING THE
//     COOKIE for the remaining 7 days of the JWT's maxAge;
//   · no LOGOUT audit row was written, so the incident was invisible;
//   · the response was HTTP 200 with NO Set-Cookie, because the client always
//     sends `X-Auth-Return-Redirect: 1` and the framework's error path answers
//     `Response.json({ url })` — 200, no cookies;
//   · the client navigated to `/login?error=MissingCSRF`, and `/login` bounced
//     the still-authenticated user straight back to `/board`.
//
// And the trigger needed no race: `getCsrfToken()` in `next-auth/react` is
// `return response?.csrfToken ?? ""` — one transient blip on the preceding GET
// silently produces an unverifiable POST.
//
// ⚠️ A SERVER ACTION DOES NOT TAKE THAT PATH AT ALL. `nextAuthSignOut()` here
// invokes the action directly, in-process, with no HTTP request and no NextAuth
// CSRF token — so `events.signOut` always fires, the row is always revoked and
// the audit row is always written. Next.js applies its own server-action
// protection to the call itself.
//
// ⚠️ AND IT IS ONE DOOR ON PURPOSE. Hardening only the account menu would have
// left the admin overview and the delete-account dialog on the broken path —
// fix by ground, not by the site the bug was reported from.
// ============================================================================

/** What every sign-out surface receives. A FAILURE IS A VALUE, not an exception
 *  and never a silent redirect: the caller must render it. */
export type SignOutResult =
  | { ok: true }
  | { ok: false; reason: string };

/**
 * Sign out the current user.
 *
 * ⚠️ FAILS CLOSED ON REVOCATION. The previous version wrapped `revokeSession`
 * in `.catch(() => {})` under the note "non-fatal — cookie clearing below still
 * signs them out locally". That reasoning holds only for the browser in front
 * of you: clearing a cookie here does nothing to a COPY of that token, and the
 * surviving row means the copy keeps validating. If we cannot revoke, we say
 * so and we do NOT report success.
 */
export async function signOutAction(): Promise<SignOutResult> {
  const sessionId = await getCurrentSessionId();

  if (sessionId) {
    try {
      await revokeSession(sessionId);
    } catch (err) {
      console.error(
        '[auth] SIGNOUT_REVOKE_FAILED: the UserSession row could not be ' +
          'revoked; refusing to report a successful sign-out.',
        { error: err instanceof Error ? err.message : String(err) },
      );
      return {
        ok: false,
        reason:
          'We could not end your session on the server. You are still signed ' +
          'in. Please try again.',
      };
    }
  }

  await nextAuthSignOut({ redirect: false });
  revalidatePath('/', 'layout');
  return { ok: true };
}

/** Revoke every session for this user (settings → "Sign out all devices").
 *  Same fail-closed contract as `signOutAction`. */
export async function signOutAllDevicesAction(): Promise<SignOutResult> {
  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) {
    return { ok: false, reason: 'You are not signed in.' };
  }

  try {
    await revokeAllUserSessions(userId);
  } catch (err) {
    console.error(
      '[auth] SIGNOUT_ALL_REVOKE_FAILED: sessions could not be revoked; ' +
        'refusing to report a successful sign-out.',
      { error: err instanceof Error ? err.message : String(err) },
    );
    return {
      ok: false,
      reason:
        'We could not end your sessions on the server. You are still signed ' +
        'in. Please try again.',
    };
  }

  await nextAuthSignOut({ redirect: false });
  revalidatePath('/', 'layout');
  return { ok: true };
}
