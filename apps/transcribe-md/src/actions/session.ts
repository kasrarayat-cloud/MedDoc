'use server';

import { signOut as nextAuthSignOut } from '@/lib/nextauth';
import { revokeSession, revokeAllUserSessions } from '@meddoc/auth';
import { getCurrentSessionId } from '@/lib/auth';
import { auth } from '@/lib/nextauth';
import { revalidatePath } from 'next/cache';

/** Sign out the current user. Revokes the UserSession row (so the JWT's
 *  sessionId claim stops validating) AND clears the NextAuth cookie. */
export async function signOutAction(): Promise<void> {
  const sessionId = await getCurrentSessionId();
  if (sessionId) {
    await revokeSession(sessionId).catch(() => {
      // Non-fatal — cookie clearing below still signs them out locally.
    });
  }
  await nextAuthSignOut({ redirect: false });
  revalidatePath('/', 'layout');
}

/** Revoke every session for this user (settings → "Sign out all devices").
 *  With single-session enforcement there's only ever one row to delete,
 *  but the button exists so users have an obvious panic-stop. */
export async function signOutAllDevicesAction(): Promise<void> {
  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) return;
  await revokeAllUserSessions(userId).catch(() => {});
  await nextAuthSignOut({ redirect: false });
  revalidatePath('/', 'layout');
}
