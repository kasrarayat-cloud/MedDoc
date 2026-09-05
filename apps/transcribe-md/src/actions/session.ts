'use server';

import { revalidatePath } from 'next/cache';

import { revokeSession, revokeAllUserSessions } from '@meddoc/auth';
import { getCurrentSessionId } from '@/lib/auth';
import { auth, signOut as nextAuthSignOut } from '@/lib/nextauth';
import { logAudit } from '@/lib/audit';

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
 * ⚠️ RULING #182(2) — THE AUDIT ROW IS WRITTEN ON EVERY ATTEMPT, WITH ITS
 * OUTCOME. Before, the only LOGOUT row lived in `events.signOut`, which is
 * reached only on the SUCCESS path — so a sign-out that failed left no artefact
 * at all, and "the doctor never clicked it" and "it failed silently" were
 * indistinguishable in the record forever.
 *
 * ⚠️ AND IT NEVER CHANGES THE RESULT. The audit write goes to the same database
 * that may have just failed; if it throws too, that is logged and swallowed
 * DELIBERATELY. A sign-out must not start failing because its receipt could not
 * be filed — and equally, a filed receipt must never be mistaken for a
 * successful revocation.
 */
async function recordLogoutAttempt(
  outcome: 'SUCCESS' | 'FAILED',
  detail: string,
  userId?: string | null,
  practiceId?: string | null,
): Promise<void> {
  try {
    await logAudit({
      action: 'LOGOUT',
      ...(userId ? { userId } : {}),
      ...(practiceId ? { practiceId } : {}),
      // ⚠️ #186(b) — `success` IS PASSED EXPLICITLY, AND THE ROW USED TO
      // CONTRADICT ITSELF. `logAudit` applies `success: input.success ?? true`,
      // so a FAILED sign-out was filed with `success = true` while its own
      // `metadata.outcome` said FAILED. An auditor reading the column — which
      // is the indexed, greppable half — would have counted it as a success.
      //
      // Strictly better than the state before #182, where a failed sign-out
      // left NO row at all. But a row that disagrees with itself is a poor
      // artefact, and the disagreement was silent.
      success: outcome === 'SUCCESS',
      metadata: { outcome, detail },
    } as Parameters<typeof logAudit>[0]);
  } catch (err) {
    console.error(
      '[auth] LOGOUT_AUDIT_WRITE_FAILED: the sign-out receipt could not be ' +
        'filed. The sign-out result itself is unchanged.',
      { outcome, error: err instanceof Error ? err.message : String(err) },
    );
  }
}

/** Who is signing out, tolerating a session layer that cannot answer. */
async function currentActor(): Promise<{ userId: string | null; practiceId: string | null }> {
  try {
    const session = await auth();
    return {
      userId: session?.user?.id ?? null,
      practiceId: (session?.user as { practiceId?: string } | undefined)?.practiceId ?? null,
    };
  } catch {
    // `auth()` can now throw SessionUnverifiableError (#182(1)). That is a
    // reason to refuse, handled by the caller — not a reason to crash here.
    return { userId: null, practiceId: null };
  }
}

/**
 * Sign out the current user.
 *
 * ⚠️ #182(2) — SUCCESS IS REPORTED ONLY WHEN REVOCATION IS CONFIRMED, AND THE
 * COOKIE IS NOT CLEARED OTHERWISE. Clearing the cookie over a live server
 * session is the specific lie this forbids: the doctor's browser forgets a
 * session that the server still honours, so the UI says "signed out" while any
 * copy of that token keeps working for the rest of its 7-day life.
 *
 * ⚠️ AND AN UNRESOLVABLE SESSION ID IS A FAILURE, NOT A NO-OP. The previous
 * version guarded the revoke with `if (sessionId)` and fell through to success
 * when it was null — which is exactly what happens when the database is
 * blipping, because `auth()` cannot answer then either. The adversarial pass
 * found that path: {ok:true}, "Signed out" toasted, row alive.
 */
export async function signOutAction(): Promise<SignOutResult> {
  const { userId, practiceId } = await currentActor();

  let sessionId: string | null = null;
  try {
    sessionId = await getCurrentSessionId();
  } catch (err) {
    console.error('[auth] SIGNOUT_SESSION_ID_UNRESOLVABLE', {
      error: err instanceof Error ? err.message : String(err),
    });
  }

  if (!sessionId) {
    await recordLogoutAttempt('FAILED', 'session id unresolvable', userId, practiceId);
    return {
      ok: false,
      reason:
        'We could not confirm your sign-out — your session could not be ' +
        'identified. You may still be signed in. Please try again.',
    };
  }

  try {
    await revokeSession(sessionId);
  } catch (err) {
    console.error(
      '[auth] SIGNOUT_REVOKE_FAILED: the UserSession row could not be ' +
        'revoked; refusing to report a successful sign-out and KEEPING the ' +
        'cookie, because a cleared cookie over a live session is the lie.',
      { error: err instanceof Error ? err.message : String(err) },
    );
    await recordLogoutAttempt('FAILED', 'revokeSession threw', userId, practiceId);
    return {
      ok: false,
      reason:
        'We could not confirm your sign-out — the server could not end your ' +
        'session. You are still signed in. Please try again.',
    };
  }

  await recordLogoutAttempt('SUCCESS', 'session revoked', userId, practiceId);
  await nextAuthSignOut({ redirect: false });
  revalidatePath('/', 'layout');
  return { ok: true };
}

/**
 * Revoke every session for this user (settings → "Sign out all devices").
 *
 * ⚠️ #182(2) — IT NEVER SAYS "You are not signed in." That was the old reply
 * when `auth()` returned null, which is precisely what a DB blip produces — so
 * the one control a doctor has for a suspected compromise answered a transient
 * fault by telling them there was nothing to revoke, and revoked nothing.
 */
export async function signOutAllDevicesAction(): Promise<SignOutResult> {
  const { userId, practiceId } = await currentActor();

  if (!userId) {
    await recordLogoutAttempt('FAILED', 'actor unresolvable (all devices)', null, null);
    return {
      ok: false,
      reason:
        'We could not confirm your sign-out — your account could not be ' +
        'identified. Your sessions may still be active. Please try again.',
    };
  }

  try {
    await revokeAllUserSessions(userId);
  } catch (err) {
    console.error(
      '[auth] SIGNOUT_ALL_REVOKE_FAILED: sessions could not be revoked; ' +
        'refusing to report success and KEEPING the cookie.',
      { error: err instanceof Error ? err.message : String(err) },
    );
    await recordLogoutAttempt('FAILED', 'revokeAllUserSessions threw', userId, practiceId);
    return {
      ok: false,
      reason:
        'We could not confirm your sign-out — the server could not end your ' +
        'sessions. They may still be active. Please try again.',
    };
  }

  await recordLogoutAttempt('SUCCESS', 'all sessions revoked', userId, practiceId);
  await nextAuthSignOut({ redirect: false });
  revalidatePath('/', 'layout');
  return { ok: true };
}
