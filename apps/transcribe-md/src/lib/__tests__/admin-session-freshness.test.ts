import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  findSession: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    userSession: {
      findFirst: mocks.findSession,
      findUnique: vi.fn(),
    },
  },
}));

import { verifyFreshPlatformAdminSession } from '../admin-session-freshness';

const NOW = new Date('2026-07-19T12:00:00.000Z');

function validRow() {
  return {
    id: 'session_row_synthetic',
    userId: 'admin_synthetic',
    createdAt: new Date('2026-07-19T08:00:00.000Z'),
    expiresAt: new Date('2026-07-20T08:00:00.000Z'),
    user: {
      id: 'admin_synthetic',
      email: 'admin@synthetic.invalid',
      role: 'SUPER_ADMIN',
      practiceId: 'practice_synthetic',
      products: ['SUPER_ADMIN'],
      isActive: true,
      deactivatedAt: null,
      suspendedAt: null,
      softDeletedAt: null,
      forceLogoutAt: null as Date | null,
      mfaEnabled: true,
      mfaSecret: 'synthetic-encrypted-secret',
      mfaVerifiedAt: new Date('2026-07-19T07:59:00.000Z') as Date | null,
    },
  };
}

async function verify(requireMfa = true) {
  return verifyFreshPlatformAdminSession({
    claimedUserId: 'admin_synthetic',
    sessionId: 'session_synthetic',
    requireMfa,
    now: NOW,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.findSession.mockResolvedValue(validRow());
});

describe('fresh platform-admin session verification', () => {
  it('returns only current database-confirmed identity fields', async () => {
    await expect(verify()).resolves.toEqual({
      userId: 'admin_synthetic',
      email: 'admin@synthetic.invalid',
      role: 'SUPER_ADMIN',
      practiceId: 'practice_synthetic',
      sessionId: 'session_synthetic',
      sessionCreatedAt: new Date('2026-07-19T08:00:00.000Z'),
      sessionExpiresAt: new Date('2026-07-20T08:00:00.000Z'),
      mfaEnabled: true,
      mfaVerifiedAt: new Date('2026-07-19T07:59:00.000Z'),
    });
    expect(mocks.findSession).toHaveBeenCalledWith(
      expect.objectContaining({
        where: {
          sessionToken: 'session_synthetic',
          userId: 'admin_synthetic',
        },
      }),
    );
  });

  it('rejects missing and mismatched current-session ownership', async () => {
    await expect(
      verifyFreshPlatformAdminSession({
        claimedUserId: 'admin_synthetic',
        sessionId: null,
        now: NOW,
      }),
    ).resolves.toBeNull();
    expect(mocks.findSession).not.toHaveBeenCalled();

    const row = validRow();
    row.userId = 'different_user';
    mocks.findSession.mockResolvedValue(row);
    await expect(verify()).resolves.toBeNull();
  });

  it.each([
    ['inactive', { isActive: false }],
    ['deactivated', { deactivatedAt: NOW }],
    ['suspended', { suspendedAt: NOW }],
    ['soft-deleted', { softDeletedAt: NOW }],
    ['not entitled', { products: ['TRANSCRIBE_MD'] }],
  ])('rejects a %s account', async (_label, patch) => {
    const row = validRow();
    Object.assign(row.user, patch);
    mocks.findSession.mockResolvedValue(row);
    await expect(verify()).resolves.toBeNull();
  });

  it.each([
    ['12-hour-old', { createdAt: new Date('2026-07-19T00:00:00.000Z') }],
    ['expired', { expiresAt: NOW }],
    [
      'issued in the future',
      { createdAt: new Date('2026-07-19T12:00:00.001Z') },
    ],
  ])('rejects a %s session', async (_label, patch) => {
    mocks.findSession.mockResolvedValue({ ...validRow(), ...patch });
    await expect(verify()).resolves.toBeNull();
  });

  it('rejects force-logout at or after session issuance', async () => {
    const row = validRow();
    row.user.forceLogoutAt = new Date(row.createdAt);
    mocks.findSession.mockResolvedValue(row);
    await expect(verify()).resolves.toBeNull();
  });

  it('requires verified MFA for APIs but lets the page route a valid operator to enrollment', async () => {
    const row = validRow();
    row.user.mfaEnabled = false;
    row.user.mfaVerifiedAt = null;
    mocks.findSession.mockResolvedValue(row);
    await expect(verify()).resolves.toBeNull();
    await expect(verify(false)).resolves.toMatchObject({
      userId: 'admin_synthetic',
      mfaEnabled: false,
      mfaVerifiedAt: null,
    });
  });

  it('rejects an inconsistent MFA-enabled account with no enrolled secret', async () => {
    const row = validRow();
    row.user.mfaSecret = '';
    mocks.findSession.mockResolvedValue(row);
    await expect(verify()).resolves.toBeNull();
    await expect(verify(false)).resolves.toMatchObject({
      userId: 'admin_synthetic',
      mfaEnabled: true,
    });
  });

  it('fails closed without exposing database error details', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    mocks.findSession.mockRejectedValue(
      new Error('synthetic credential-bearing connection failure'),
    );
    await expect(verify()).resolves.toBeNull();
    expect(errorSpy).toHaveBeenCalledWith(
      '[admin-session-freshness] database verification failed; access denied',
    );
    expect(errorSpy.mock.calls.flat().join(' ')).not.toContain('credential');
    errorSpy.mockRestore();
  });
});
