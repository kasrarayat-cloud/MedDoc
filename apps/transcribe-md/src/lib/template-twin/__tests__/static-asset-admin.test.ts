import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  auth: vi.fn(),
  findUser: vi.fn(),
  evaluateRollout: vi.fn(),
  pinRollout: vi.fn(),
  sessionStale: vi.fn(),
}));

vi.mock('@/lib/auth', () => ({
  AuthError: class AuthError extends Error {
    constructor(
      public readonly code: 'UNAUTHENTICATED' | 'FORBIDDEN',
      message: string,
    ) {
      super(message);
    }
  },
}));
vi.mock('@/lib/nextauth', () => ({ auth: mocks.auth }));
vi.mock('@/lib/admin-session-freshness', () => ({
  isAdminSessionStale: mocks.sessionStale,
}));
vi.mock('@meddoc/db', () => ({
  default: { user: { findUnique: mocks.findUser } },
}));
vi.mock('../rollout', () => ({
  TemplateTwinRolloutError: class TemplateTwinRolloutError extends Error {},
  evaluateTemplateTwinRollout: mocks.evaluateRollout,
  pinTemplateTwinRollout: mocks.pinRollout,
}));

import { requireTemplateTwinStaticAssetAdmin } from '../static-asset-admin';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.mockResolvedValue({
    user: { id: 'admin_synthetic', sessionId: 'session_synthetic' },
  });
  mocks.sessionStale.mockResolvedValue(false);
  mocks.findUser.mockResolvedValue({
    email: 'admin@synthetic.test',
    role: 'ADMIN',
    isActive: true,
    practiceId: 'practice_synthetic',
    practice: { templateTwinEnabled: true },
  });
  mocks.evaluateRollout.mockReturnValue({ allowed: true });
  mocks.pinRollout.mockResolvedValue({
    practiceId: 'practice_synthetic',
    globalGeneration: 1,
    practiceGeneration: 1,
  });
});

describe('fresh Template Twin static-asset administrator authorization', () => {
  it('returns only the current database-confirmed practice and admin role', async () => {
    await expect(requireTemplateTwinStaticAssetAdmin()).resolves.toEqual({
      userId: 'admin_synthetic',
      userEmail: 'admin@synthetic.test',
      practiceId: 'practice_synthetic',
      role: 'ADMIN',
      rolloutToken: {
        practiceId: 'practice_synthetic',
        globalGeneration: 1,
        practiceGeneration: 1,
      },
    });
    expect(mocks.pinRollout).toHaveBeenCalledWith({
      practiceId: 'practice_synthetic',
    });
  });

  it.each(['DOCTOR', 'STAFF'])(
    'rejects a fresh %s database role',
    async (role) => {
      mocks.findUser.mockResolvedValue({
        email: 'user@synthetic.test',
        role,
        isActive: true,
        practiceId: 'practice_synthetic',
        practice: { templateTwinEnabled: true },
      });
      await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
        code: 'FORBIDDEN',
      });
      expect(mocks.pinRollout).not.toHaveBeenCalled();
    },
  );

  it('rejects inactive accounts, disabled rollout, and database outages without JWT fallback', async () => {
    mocks.findUser.mockResolvedValueOnce({
      email: 'admin@synthetic.test',
      role: 'ADMIN',
      isActive: false,
      practiceId: 'practice_synthetic',
      practice: { templateTwinEnabled: true },
    });
    await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
      code: 'FORBIDDEN',
    });

    mocks.findUser.mockResolvedValueOnce({
      email: 'admin@synthetic.test',
      role: 'ADMIN',
      isActive: true,
      practiceId: 'practice_synthetic',
      practice: { templateTwinEnabled: false },
    });
    mocks.evaluateRollout.mockReturnValueOnce({
      allowed: false,
      reason: 'Synthetic rollout is disabled.',
    });
    await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
      code: 'FORBIDDEN',
    });

    mocks.findUser.mockRejectedValueOnce(new Error('synthetic database outage'));
    await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
      code: 'FORBIDDEN',
    });
  });

  it('rejects a missing or stale administrator session before database authorization', async () => {
    mocks.sessionStale.mockResolvedValueOnce(true);
    await expect(requireTemplateTwinStaticAssetAdmin()).rejects.toMatchObject({
      code: 'FORBIDDEN',
    });
    expect(mocks.findUser).not.toHaveBeenCalled();
  });
});
