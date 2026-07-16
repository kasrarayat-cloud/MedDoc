import prisma from '@meddoc/db';

import { AuthError } from '@/lib/auth';
import { isAdminSessionStale } from '@/lib/admin-session-freshness';
import { auth } from '@/lib/nextauth';

import {
  evaluateTemplateTwinRollout,
  pinTemplateTwinRollout,
  TemplateTwinRolloutError,
} from './rollout';
import type { TemplateTwinStaticAssetActor } from './static-assets';

/** Fresh, fail-closed practice-admin authorization for reusable image review. */
export async function requireTemplateTwinStaticAssetAdmin(): Promise<TemplateTwinStaticAssetActor> {
  const session = await auth().catch(() => null);
  if (!session?.user?.id) {
    throw new AuthError('UNAUTHENTICATED', 'You must be logged in.');
  }
  const sessionId = (session.user as { sessionId?: string }).sessionId;
  if (await isAdminSessionStale(sessionId)) {
    throw new AuthError(
      'FORBIDDEN',
      'Sign in again before reviewing a reusable template image.',
    );
  }
  try {
    const user = await prisma.user.findUnique({
      where: { id: session.user.id },
      select: {
        email: true,
        role: true,
        isActive: true,
        practiceId: true,
        practice: { select: { templateTwinEnabled: true } },
      },
    });
    if (
      !user ||
      !user.isActive ||
      (user.role !== 'ADMIN' && user.role !== 'SUPER_ADMIN') ||
      !user.practiceId
    ) {
      throw new AuthError(
        'FORBIDDEN',
        'An active practice administrator is required to review reusable template images.',
      );
    }
    const rollout = evaluateTemplateTwinRollout({
      practiceEnabled: user.practice.templateTwinEnabled,
    });
    if (!rollout.allowed) {
      throw new AuthError('FORBIDDEN', rollout.reason);
    }
    let rolloutToken;
    try {
      rolloutToken = await pinTemplateTwinRollout({
        practiceId: user.practiceId,
      });
    } catch (error) {
      if (error instanceof TemplateTwinRolloutError) {
        throw new AuthError('FORBIDDEN', error.message);
      }
      throw error;
    }
    return {
      userId: session.user.id,
      userEmail: user.email,
      practiceId: user.practiceId,
      role: user.role,
      rolloutToken,
    };
  } catch (error) {
    if (error instanceof AuthError) throw error;
    throw new AuthError(
      'FORBIDDEN',
      'Current practice-administrator authorization could not be verified.',
    );
  }
}
