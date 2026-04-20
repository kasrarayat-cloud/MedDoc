// ============================================================================
// Unit tests for T-M14.1 captureEditPattern
// ----------------------------------------------------------------------------
// Both @meddoc/db and @meddoc/ai are mocked so the test runs against
// in-memory fakes — no real postgres, no real OpenAI. The assertions
// focus on the contract the sign-path callers rely on: the function
// NEVER throws, writes a row exactly once on the happy path, and
// gracefully degrades when dependencies fail.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

// vi.mock() is hoisted above const declarations; the mocks have to
// live in vi.hoisted() or they'd be undefined at factory-call time.
const {
  mockVisitFind,
  mockUserFind,
  mockEditCreate,
  mockExecuteRaw,
  mockEmbedText,
} = vi.hoisted(() => ({
  mockVisitFind: vi.fn(),
  mockUserFind: vi.fn(),
  mockEditCreate: vi.fn(),
  mockExecuteRaw: vi.fn(),
  mockEmbedText: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: { findUnique: mockVisitFind },
    user: { findUnique: mockUserFind },
    doctorEditPattern: { create: mockEditCreate },
    $executeRaw: mockExecuteRaw,
  },
}));

vi.mock('@meddoc/ai', () => ({
  embedText: mockEmbedText,
}));

// Import AFTER the mocks so the module picks them up.
import { captureEditPattern } from '@/lib/edit-tracking';

const ORIGINAL = '## Subjective\n[AI] Patient reports headache.\n';
const EDITED = '## Subjective\nPt reports headache, resolving.\n';

beforeEach(() => {
  vi.clearAllMocks();
  // Silence expected console output during tests; re-enable in the one
  // test that asserts on logs if we ever need it.
  vi.spyOn(console, 'info').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

describe('captureEditPattern — happy path', () => {
  it('creates a row with expected columns and writes the embedding', async () => {
    mockVisitFind.mockResolvedValueOnce({
      soapL6Original: ORIGINAL,
      signedSoap: EDITED,
      userId: 'u1',
    });
    mockUserFind.mockResolvedValueOnce({ practiceId: 'p1' });
    mockEditCreate.mockResolvedValueOnce({ id: 'dep1' });
    const fixtureVec = Array.from({ length: 1536 }, (_, i) => i / 1536);
    mockEmbedText.mockResolvedValueOnce({
      embedding: fixtureVec,
      inputTokens: 50,
      costCents: 0,
    });
    mockExecuteRaw.mockResolvedValueOnce(1);

    await expect(
      captureEditPattern({ visitId: 'v1', doctorId: 'u1' })
    ).resolves.toBeUndefined();

    expect(mockEditCreate).toHaveBeenCalledTimes(1);
    const createArgs = mockEditCreate.mock.calls[0][0];
    expect(createArgs.data).toMatchObject({
      visitId: 'v1',
      doctorId: 'u1',
      originalSoap: ORIGINAL,
      editedSoap: EDITED,
    });
    // editDistance is computed by the char-Levenshtein helper — non-zero
    // for these two distinct inputs, but we don't pin an exact value.
    expect(createArgs.data.editDistance).toBeGreaterThan(0);

    expect(mockEmbedText).toHaveBeenCalledWith({
      text: ORIGINAL,
      practiceId: 'p1',
      visitId: 'v1',
      purpose: 'tm_embed',
    });
    expect(mockExecuteRaw).toHaveBeenCalledTimes(1);
  });

  it('editDistance is 0 when the doctor did not edit', async () => {
    mockVisitFind.mockResolvedValueOnce({
      soapL6Original: ORIGINAL,
      signedSoap: ORIGINAL,
      userId: 'u1',
    });
    mockUserFind.mockResolvedValueOnce({ practiceId: 'p1' });
    mockEditCreate.mockResolvedValueOnce({ id: 'dep1' });
    mockEmbedText.mockResolvedValueOnce({
      embedding: Array(1536).fill(0.01),
      inputTokens: 10,
      costCents: 0,
    });
    mockExecuteRaw.mockResolvedValueOnce(1);

    await captureEditPattern({ visitId: 'v1', doctorId: 'u1' });

    expect(mockEditCreate.mock.calls[0][0].data.editDistance).toBe(0);
  });
});

describe('captureEditPattern — skip conditions', () => {
  it('skips silently when soapL6Original is null (legacy visit)', async () => {
    mockVisitFind.mockResolvedValueOnce({
      soapL6Original: null,
      signedSoap: EDITED,
      userId: 'u1',
    });
    mockUserFind.mockResolvedValueOnce({ practiceId: 'p1' });

    await captureEditPattern({ visitId: 'v_legacy', doctorId: 'u1' });

    expect(mockEditCreate).not.toHaveBeenCalled();
    expect(mockEmbedText).not.toHaveBeenCalled();
    expect(mockExecuteRaw).not.toHaveBeenCalled();
  });

  it('skips when signedSoap is null (unexpected post-sign state)', async () => {
    mockVisitFind.mockResolvedValueOnce({
      soapL6Original: ORIGINAL,
      signedSoap: null,
      userId: 'u1',
    });
    mockUserFind.mockResolvedValueOnce({ practiceId: 'p1' });

    await captureEditPattern({ visitId: 'v1', doctorId: 'u1' });

    expect(mockEditCreate).not.toHaveBeenCalled();
    expect(mockEmbedText).not.toHaveBeenCalled();
  });

  it('skips when visit is gone', async () => {
    mockVisitFind.mockResolvedValueOnce(null);
    mockUserFind.mockResolvedValueOnce({ practiceId: 'p1' });

    await captureEditPattern({ visitId: 'v_deleted', doctorId: 'u1' });

    expect(mockEditCreate).not.toHaveBeenCalled();
    expect(mockEmbedText).not.toHaveBeenCalled();
  });

  it('skips when doctor is gone', async () => {
    mockVisitFind.mockResolvedValueOnce({
      soapL6Original: ORIGINAL,
      signedSoap: EDITED,
      userId: 'u1',
    });
    mockUserFind.mockResolvedValueOnce(null);

    await captureEditPattern({ visitId: 'v1', doctorId: 'u_deleted' });

    expect(mockEditCreate).not.toHaveBeenCalled();
  });
});

describe('captureEditPattern — partial failures degrade gracefully', () => {
  it('embed failure leaves the row in place with no embedding write', async () => {
    mockVisitFind.mockResolvedValueOnce({
      soapL6Original: ORIGINAL,
      signedSoap: EDITED,
      userId: 'u1',
    });
    mockUserFind.mockResolvedValueOnce({ practiceId: 'p1' });
    mockEditCreate.mockResolvedValueOnce({ id: 'dep1' });
    mockEmbedText.mockRejectedValueOnce(new Error('openai 503 timeout'));

    await expect(
      captureEditPattern({ visitId: 'v1', doctorId: 'u1' })
    ).resolves.toBeUndefined();

    expect(mockEditCreate).toHaveBeenCalledTimes(1);
    expect(mockExecuteRaw).not.toHaveBeenCalled();
  });

  it('vector UPDATE failure does not throw (row still present)', async () => {
    mockVisitFind.mockResolvedValueOnce({
      soapL6Original: ORIGINAL,
      signedSoap: EDITED,
      userId: 'u1',
    });
    mockUserFind.mockResolvedValueOnce({ practiceId: 'p1' });
    mockEditCreate.mockResolvedValueOnce({ id: 'dep1' });
    mockEmbedText.mockResolvedValueOnce({
      embedding: Array(1536).fill(0.01),
      inputTokens: 1,
      costCents: 0,
    });
    mockExecuteRaw.mockRejectedValueOnce(new Error('pgvector down'));

    await expect(
      captureEditPattern({ visitId: 'v1', doctorId: 'u1' })
    ).resolves.toBeUndefined();

    expect(mockEditCreate).toHaveBeenCalledTimes(1);
  });

  it('create() failure is swallowed (never throws)', async () => {
    mockVisitFind.mockResolvedValueOnce({
      soapL6Original: ORIGINAL,
      signedSoap: EDITED,
      userId: 'u1',
    });
    mockUserFind.mockResolvedValueOnce({ practiceId: 'p1' });
    mockEditCreate.mockRejectedValueOnce(
      new Error('Unique constraint failed on visitId')
    );

    // Must not throw — the sign response path depends on this.
    await expect(
      captureEditPattern({ visitId: 'v1', doctorId: 'u1' })
    ).resolves.toBeUndefined();

    expect(mockEmbedText).not.toHaveBeenCalled();
    expect(mockExecuteRaw).not.toHaveBeenCalled();
  });

  it('DB findUnique failure is swallowed', async () => {
    mockVisitFind.mockRejectedValueOnce(new Error('prisma pool exhausted'));
    mockUserFind.mockResolvedValueOnce({ practiceId: 'p1' });

    await expect(
      captureEditPattern({ visitId: 'v1', doctorId: 'u1' })
    ).resolves.toBeUndefined();

    expect(mockEditCreate).not.toHaveBeenCalled();
  });
});
