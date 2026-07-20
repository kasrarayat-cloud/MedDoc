import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  headers: vi.fn(),
  nextAuthSignOut: vi.fn(),
  readSignedSessionAuthority: vi.fn(),
  revalidatePath: vi.fn(),
  revokeAllUserSessionsFromCurrentSession: vi.fn(),
  revokeSession: vi.fn(),
}));

vi.mock('@/lib/nextauth', () => ({
  signOut: mocks.nextAuthSignOut,
}));

vi.mock('@/lib/signed-session-authority', () => ({
  readSignedSessionAuthority: mocks.readSignedSessionAuthority,
}));

vi.mock('next/headers', () => ({ headers: mocks.headers }));

vi.mock('@meddoc/auth', () => ({
  revokeAllUserSessionsFromCurrentSession:
    mocks.revokeAllUserSessionsFromCurrentSession,
  revokeSession: mocks.revokeSession,
}));

vi.mock('next/cache', () => ({
  revalidatePath: mocks.revalidatePath,
}));

import { signOutAction, signOutAllDevicesAction } from '../session';

function expectCalledBefore(
  first: ReturnType<typeof vi.fn>,
  second: ReturnType<typeof vi.fn>,
) {
  expect(first.mock.invocationCallOrder[0]).toBeLessThan(
    second.mock.invocationCallOrder[0] ?? Number.POSITIVE_INFINITY,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.headers.mockResolvedValue(new Headers({ cookie: 'synthetic' }));
  mocks.readSignedSessionAuthority.mockResolvedValue({
    cookiePresent: true,
    sessionId: 'session-synthetic-current',
    userId: 'user-synthetic-current',
  });
  mocks.revokeSession.mockResolvedValue(undefined);
  mocks.revokeAllUserSessionsFromCurrentSession.mockResolvedValue(true);
  mocks.nextAuthSignOut.mockResolvedValue(undefined);
});

describe('session revocation server actions', () => {
  it('does not clear the cookie or claim success when current-session revocation fails', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    mocks.revokeSession.mockRejectedValue(
      new Error('synthetic credential-bearing database diagnostic'),
    );

    await expect(signOutAction()).resolves.toEqual({
      ok: false,
      code: 'SESSION_REVOCATION_FAILED',
      retryable: true,
      message: 'We could not securely end your session. Please try again.',
    });

    expect(mocks.revokeSession).toHaveBeenCalledWith(
      'session-synthetic-current',
    );
    expect(mocks.nextAuthSignOut).not.toHaveBeenCalled();
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
    expect(log).toHaveBeenCalledWith(
      '[session] current session revocation failed',
    );
    expect(JSON.stringify(log.mock.calls)).not.toContain(
      'credential-bearing database diagnostic',
    );
    log.mockRestore();
  });

  it('revokes the current session before clearing the cookie and revalidating', async () => {
    await expect(signOutAction()).resolves.toEqual({ ok: true });

    expect(mocks.nextAuthSignOut).toHaveBeenCalledWith({ redirect: false });
    expect(mocks.revalidatePath).toHaveBeenCalledWith('/', 'layout');
    expectCalledBefore(mocks.readSignedSessionAuthority, mocks.revokeSession);
    expectCalledBefore(mocks.revokeSession, mocks.nextAuthSignOut);
    expectCalledBefore(mocks.nextAuthSignOut, mocks.revalidatePath);
  });

  it('does not clear the cookie or claim success when all-session revocation fails', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    mocks.revokeAllUserSessionsFromCurrentSession.mockRejectedValue(
      new Error('synthetic credential-bearing database diagnostic'),
    );

    await expect(signOutAllDevicesAction()).resolves.toEqual({
      ok: false,
      code: 'SESSION_REVOCATION_FAILED',
      retryable: true,
      message: 'We could not securely end your session. Please try again.',
    });

    expect(mocks.revokeAllUserSessionsFromCurrentSession).toHaveBeenCalledWith({
      sessionToken: 'session-synthetic-current',
      userId: 'user-synthetic-current',
    });
    expect(mocks.nextAuthSignOut).not.toHaveBeenCalled();
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
    expect(log).toHaveBeenCalledWith(
      '[session] all-session revocation failed',
    );
    expect(JSON.stringify(log.mock.calls)).not.toContain(
      'credential-bearing database diagnostic',
    );
    log.mockRestore();
  });

  it('revokes every user session before clearing the cookie and revalidating', async () => {
    await expect(signOutAllDevicesAction()).resolves.toEqual({ ok: true });

    expect(mocks.nextAuthSignOut).toHaveBeenCalledWith({ redirect: false });
    expect(mocks.revalidatePath).toHaveBeenCalledWith('/', 'layout');
    expectCalledBefore(
      mocks.readSignedSessionAuthority,
      mocks.revokeAllUserSessionsFromCurrentSession,
    );
    expectCalledBefore(
      mocks.revokeAllUserSessionsFromCurrentSession,
      mocks.nextAuthSignOut,
    );
    expectCalledBefore(mocks.nextAuthSignOut, mocks.revalidatePath);
  });

  it('denies a stale signed cookie without revoking a newer session or clearing the cookie', async () => {
    mocks.revokeAllUserSessionsFromCurrentSession.mockResolvedValue(false);

    await expect(signOutAllDevicesAction()).resolves.toEqual({
      ok: false,
      code: 'AUTHENTICATION_REQUIRED',
      retryable: false,
      message: 'Your session is no longer active. Reload this page to continue.',
    });
    expect(mocks.revokeAllUserSessionsFromCurrentSession).toHaveBeenCalledWith({
      sessionToken: 'session-synthetic-current',
      userId: 'user-synthetic-current',
    });
    expect(mocks.nextAuthSignOut).not.toHaveBeenCalled();
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
  });

  it('does not claim all-device revocation without an authenticated user', async () => {
    mocks.readSignedSessionAuthority.mockResolvedValue({
      cookiePresent: false,
      sessionId: null,
      userId: null,
    });

    await expect(signOutAllDevicesAction()).resolves.toEqual({
      ok: false,
      code: 'AUTHENTICATION_REQUIRED',
      retryable: false,
      message: 'Your session is no longer active. Reload this page to continue.',
    });
    expect(
      mocks.revokeAllUserSessionsFromCurrentSession,
    ).not.toHaveBeenCalled();
    expect(mocks.nextAuthSignOut).not.toHaveBeenCalled();
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
  });

  it('does not clear a signed cookie when its durable session binding cannot be decoded', async () => {
    mocks.readSignedSessionAuthority.mockResolvedValue({
      cookiePresent: true,
      sessionId: null,
      userId: null,
    });

    await expect(signOutAction()).resolves.toEqual({
      ok: false,
      code: 'SESSION_REVOCATION_FAILED',
      retryable: true,
      message: 'We could not securely end your session. Please try again.',
    });
    expect(mocks.revokeSession).not.toHaveBeenCalled();
    expect(mocks.nextAuthSignOut).not.toHaveBeenCalled();
  });
});
