// ============================================================================
// Unit tests for T-M16.2 auth-tokens library
// ----------------------------------------------------------------------------
// Pure helpers (generate / hash) get tested directly. DB-touching helpers
// (createAuthToken / consumeAuthToken / invalidateAuthTokens) mock the
// @meddoc/db module so we can verify the exact Prisma call shapes + the
// atomicity/expiry/purpose guards without a real database.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockCreate, mockFindUnique, mockUpdateMany } = vi.hoisted(() => ({
  mockCreate: vi.fn(),
  mockFindUnique: vi.fn(),
  mockUpdateMany: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    authToken: {
      create: mockCreate,
      findUnique: mockFindUnique,
      updateMany: mockUpdateMany,
    },
  },
}));

import {
  consumeAuthToken,
  createAuthToken,
  generateRawToken,
  hashToken,
  invalidateAuthTokens,
} from '@/lib/auth-tokens';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('generateRawToken + hashToken', () => {
  it('produces a long base64url token', () => {
    const t = generateRawToken();
    expect(t.length).toBeGreaterThanOrEqual(40);
    expect(t).toMatch(/^[A-Za-z0-9_-]+$/);
  });

  it('every generate call produces a distinct token', () => {
    const a = generateRawToken();
    const b = generateRawToken();
    expect(a).not.toBe(b);
  });

  it('hashToken is deterministic + 64 hex chars', () => {
    const raw = 'abc123';
    const a = hashToken(raw);
    const b = hashToken(raw);
    expect(a).toBe(b);
    expect(a).toHaveLength(64);
    expect(a).toMatch(/^[0-9a-f]+$/);
  });

  it('hashToken differs for different inputs', () => {
    expect(hashToken('a')).not.toBe(hashToken('b'));
  });
});

describe('createAuthToken', () => {
  it('invalidates prior unused tokens by default', async () => {
    mockUpdateMany.mockResolvedValueOnce({ count: 2 });
    mockCreate.mockResolvedValueOnce({ id: 'tk1' });

    await createAuthToken({
      userId: 'u1',
      purpose: 'PASSWORD_RESET',
      expiresInMs: 60_000,
    });

    expect(mockUpdateMany).toHaveBeenCalledTimes(1);
    expect(mockUpdateMany.mock.calls[0][0].where).toMatchObject({
      userId: 'u1',
      purpose: 'PASSWORD_RESET',
      usedAt: null,
    });
  });

  it('skips invalidation when invalidatePrior=false', async () => {
    mockCreate.mockResolvedValueOnce({ id: 'tk1' });

    await createAuthToken({
      userId: 'u1',
      purpose: 'EMAIL_VERIFICATION',
      expiresInMs: 60_000,
      invalidatePrior: false,
    });

    expect(mockUpdateMany).not.toHaveBeenCalled();
    expect(mockCreate).toHaveBeenCalledTimes(1);
  });

  it('hashes the token before persisting it', async () => {
    mockUpdateMany.mockResolvedValueOnce({ count: 0 });
    mockCreate.mockResolvedValueOnce({ id: 'tk1' });

    const { token } = await createAuthToken({
      userId: 'u1',
      purpose: 'PASSWORD_RESET',
      expiresInMs: 60_000,
    });

    const createArgs = mockCreate.mock.calls[0][0];
    // The plaintext token never enters the DB payload.
    expect(createArgs.data.tokenHash).toBe(hashToken(token));
    expect(createArgs.data.tokenHash).not.toBe(token);
  });

  it('stores metadata when provided', async () => {
    mockUpdateMany.mockResolvedValueOnce({ count: 0 });
    mockCreate.mockResolvedValueOnce({ id: 'tk1' });

    await createAuthToken({
      userId: 'u1',
      purpose: 'EMAIL_CHANGE',
      expiresInMs: 60_000,
      metadata: { newEmail: 'new@example.com' },
    });

    const createArgs = mockCreate.mock.calls[0][0];
    expect(createArgs.data.metadata).toEqual({ newEmail: 'new@example.com' });
  });

  it('leaves metadata undefined when omitted', async () => {
    mockUpdateMany.mockResolvedValueOnce({ count: 0 });
    mockCreate.mockResolvedValueOnce({ id: 'tk1' });

    await createAuthToken({
      userId: 'u1',
      purpose: 'PASSWORD_RESET',
      expiresInMs: 60_000,
    });

    const createArgs = mockCreate.mock.calls[0][0];
    expect(createArgs.data.metadata).toBeUndefined();
  });
});

describe('consumeAuthToken', () => {
  const HASH_OF_VALID = hashToken('valid-token-value-must-be-20-plus-chars');

  function okRow(overrides: Record<string, unknown> = {}) {
    return {
      id: 'tk1',
      userId: 'u1',
      purpose: 'PASSWORD_RESET',
      expiresAt: new Date(Date.now() + 10_000),
      usedAt: null,
      metadata: null,
      ...overrides,
    };
  }

  it('returns ConsumedAuthToken on happy path', async () => {
    mockFindUnique.mockResolvedValueOnce(okRow());
    mockUpdateMany.mockResolvedValueOnce({ count: 1 });

    const result = await consumeAuthToken({
      token: 'valid-token-value-must-be-20-plus-chars',
      purpose: 'PASSWORD_RESET',
    });

    expect(result).toEqual({ id: 'tk1', userId: 'u1', metadata: null });
    expect(mockFindUnique.mock.calls[0][0].where).toEqual({
      tokenHash: HASH_OF_VALID,
    });
  });

  it('returns null for too-short token without hitting DB', async () => {
    const result = await consumeAuthToken({
      token: 'short',
      purpose: 'PASSWORD_RESET',
    });
    expect(result).toBeNull();
    expect(mockFindUnique).not.toHaveBeenCalled();
  });

  it('returns null when row missing', async () => {
    mockFindUnique.mockResolvedValueOnce(null);
    const result = await consumeAuthToken({
      token: 'valid-token-value-must-be-20-plus-chars',
      purpose: 'PASSWORD_RESET',
    });
    expect(result).toBeNull();
    expect(mockUpdateMany).not.toHaveBeenCalled();
  });

  it('returns null on purpose mismatch', async () => {
    mockFindUnique.mockResolvedValueOnce(okRow({ purpose: 'EMAIL_CHANGE' }));
    const result = await consumeAuthToken({
      token: 'valid-token-value-must-be-20-plus-chars',
      purpose: 'PASSWORD_RESET',
    });
    expect(result).toBeNull();
    expect(mockUpdateMany).not.toHaveBeenCalled();
  });

  it('returns null when token already used', async () => {
    mockFindUnique.mockResolvedValueOnce(okRow({ usedAt: new Date() }));
    const result = await consumeAuthToken({
      token: 'valid-token-value-must-be-20-plus-chars',
      purpose: 'PASSWORD_RESET',
    });
    expect(result).toBeNull();
    expect(mockUpdateMany).not.toHaveBeenCalled();
  });

  it('returns null when expired', async () => {
    mockFindUnique.mockResolvedValueOnce(
      okRow({ expiresAt: new Date(Date.now() - 1) })
    );
    const result = await consumeAuthToken({
      token: 'valid-token-value-must-be-20-plus-chars',
      purpose: 'PASSWORD_RESET',
    });
    expect(result).toBeNull();
    expect(mockUpdateMany).not.toHaveBeenCalled();
  });

  it('returns null when the atomic mark-used race is lost', async () => {
    mockFindUnique.mockResolvedValueOnce(okRow());
    mockUpdateMany.mockResolvedValueOnce({ count: 0 });
    const result = await consumeAuthToken({
      token: 'valid-token-value-must-be-20-plus-chars',
      purpose: 'PASSWORD_RESET',
    });
    expect(result).toBeNull();
  });

  it('forwards metadata on happy path', async () => {
    mockFindUnique.mockResolvedValueOnce(
      okRow({
        purpose: 'EMAIL_CHANGE',
        metadata: { newEmail: 'new@example.com' },
      })
    );
    mockUpdateMany.mockResolvedValueOnce({ count: 1 });

    const result = await consumeAuthToken({
      token: 'valid-token-value-must-be-20-plus-chars',
      purpose: 'EMAIL_CHANGE',
    });

    expect(result).toEqual({
      id: 'tk1',
      userId: 'u1',
      metadata: { newEmail: 'new@example.com' },
    });
  });
});

describe('invalidateAuthTokens', () => {
  it('updates all unused tokens for a (user, purpose) pair', async () => {
    mockUpdateMany.mockResolvedValueOnce({ count: 3 });
    await invalidateAuthTokens('u1', 'PASSWORD_RESET');
    expect(mockUpdateMany).toHaveBeenCalledWith({
      where: { userId: 'u1', purpose: 'PASSWORD_RESET', usedAt: null },
      data: expect.objectContaining({ usedAt: expect.any(Date) }),
    });
  });
});
