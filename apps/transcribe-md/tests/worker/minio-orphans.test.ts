// ============================================================================
// Unit tests for T-M12 MinIO orphan cleanup
// ----------------------------------------------------------------------------
// vi.mock() replaces @meddoc/db + @/lib/minio so the function under test
// runs against in-memory fixtures instead of a live DB/bucket.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

// vi.mock() is hoisted above all `const` declarations, so the mocks
// themselves have to live in vi.hoisted() or they'd be undefined at
// factory-call time.
const { mockListAll, mockDelete, mockFindMany } = vi.hoisted(() => ({
  mockListAll: vi.fn(),
  mockDelete: vi.fn(),
  mockFindMany: vi.fn(),
}));

vi.mock('@/lib/minio', () => ({
  listAllAudioObjects: mockListAll,
  deleteAudioObject: mockDelete,
}));

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: {
      findMany: mockFindMany,
    },
  },
}));

// --- system under test ----------------------------------------------
// Imported AFTER the mocks so the cleanup module picks them up.
import { runMinioOrphanCleanup } from '@/worker/cleanup/minio-orphans';

const NOW = Date.UTC(2026, 3, 19, 12, 0, 0); // 2026-04-19 12:00Z
const DAY = 24 * 60 * 60 * 1000;

function dateDaysAgo(n: number): Date {
  return new Date(NOW - n * DAY);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('runMinioOrphanCleanup', () => {
  it('keeps objects referenced by a TranscribeVisit', async () => {
    mockFindMany.mockResolvedValueOnce([
      { audioKey: 'u1/v1/audio.mp3', dictationAudioKey: null },
      { audioKey: null, dictationAudioKey: 'u2/v2/dictation.webm' },
    ]);
    mockListAll.mockResolvedValueOnce([
      { name: 'u1/v1/audio.mp3', size: 1000, lastModified: dateDaysAgo(60) },
      { name: 'u2/v2/dictation.webm', size: 500, lastModified: dateDaysAgo(60) },
    ]);

    const result = await runMinioOrphanCleanup({
      retentionDays: 30,
      dryRun: false,
      nowMs: NOW,
    });

    expect(result.kept).toBe(2);
    expect(result.deleted).toBe(0);
    expect(result.skippedYoung).toBe(0);
    expect(mockDelete).not.toHaveBeenCalled();
  });

  it('deletes orphan objects older than retentionDays', async () => {
    mockFindMany.mockResolvedValueOnce([
      { audioKey: 'u1/v1/referenced.mp3', dictationAudioKey: null },
    ]);
    mockListAll.mockResolvedValueOnce([
      { name: 'u1/v1/referenced.mp3', size: 1000, lastModified: dateDaysAgo(60) },
      { name: 'u1/v9/orphan-old.mp3', size: 2000, lastModified: dateDaysAgo(45) },
      { name: 'u2/v9/orphan-old-2.mp3', size: 3000, lastModified: dateDaysAgo(31) },
    ]);

    const result = await runMinioOrphanCleanup({
      retentionDays: 30,
      dryRun: false,
      nowMs: NOW,
    });

    expect(result.kept).toBe(1);
    expect(result.deleted).toBe(2);
    expect(result.skippedYoung).toBe(0);
    expect(result.totalReclaimedBytes).toBe(5000);
    expect(mockDelete).toHaveBeenCalledTimes(2);
    expect(mockDelete).toHaveBeenCalledWith('u1/v9/orphan-old.mp3');
    expect(mockDelete).toHaveBeenCalledWith('u2/v9/orphan-old-2.mp3');
  });

  it('skips orphans younger than retentionDays (race guard)', async () => {
    mockFindMany.mockResolvedValueOnce([]);
    mockListAll.mockResolvedValueOnce([
      { name: 'u1/v9/orphan-young.mp3', size: 1000, lastModified: dateDaysAgo(5) },
      { name: 'u2/v9/orphan-old.mp3', size: 2000, lastModified: dateDaysAgo(40) },
    ]);

    const result = await runMinioOrphanCleanup({
      retentionDays: 30,
      dryRun: false,
      nowMs: NOW,
    });

    expect(result.kept).toBe(0);
    expect(result.deleted).toBe(1);
    expect(result.skippedYoung).toBe(1);
    expect(result.totalReclaimedBytes).toBe(2000);
    expect(mockDelete).toHaveBeenCalledTimes(1);
    expect(mockDelete).toHaveBeenCalledWith('u2/v9/orphan-old.mp3');
  });

  it('dry-run logs but does NOT delete', async () => {
    mockFindMany.mockResolvedValueOnce([]);
    mockListAll.mockResolvedValueOnce([
      { name: 'u1/v9/orphan.mp3', size: 1000, lastModified: dateDaysAgo(90) },
    ]);

    const result = await runMinioOrphanCleanup({
      retentionDays: 30,
      dryRun: true,
      nowMs: NOW,
    });

    expect(result.deleted).toBe(1);
    expect(result.totalReclaimedBytes).toBe(1000);
    // Crucially: the real delete was NOT called.
    expect(mockDelete).not.toHaveBeenCalled();
  });

  it('skips objects with unknown lastModified', async () => {
    mockFindMany.mockResolvedValueOnce([]);
    mockListAll.mockResolvedValueOnce([
      { name: 'u1/v9/unknown-age.mp3', size: 500, lastModified: undefined },
    ]);

    const result = await runMinioOrphanCleanup({
      retentionDays: 30,
      dryRun: false,
      nowMs: NOW,
    });

    expect(result.skippedYoung).toBe(1);
    expect(result.deleted).toBe(0);
    expect(mockDelete).not.toHaveBeenCalled();
  });

  it('records per-object delete failures and keeps going', async () => {
    mockFindMany.mockResolvedValueOnce([]);
    mockListAll.mockResolvedValueOnce([
      { name: 'u1/a.mp3', size: 100, lastModified: dateDaysAgo(60) },
      { name: 'u1/b.mp3', size: 200, lastModified: dateDaysAgo(60) },
      { name: 'u1/c.mp3', size: 300, lastModified: dateDaysAgo(60) },
    ]);
    mockDelete
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error('minio 503 blah'))
      .mockResolvedValueOnce(undefined);

    const result = await runMinioOrphanCleanup({
      retentionDays: 30,
      dryRun: false,
      nowMs: NOW,
    });

    expect(result.deleted).toBe(2);
    expect(result.failures).toEqual([
      { key: 'u1/b.mp3', error: 'minio 503 blah' },
    ]);
    expect(result.totalReclaimedBytes).toBe(400); // 100 + 300
    expect(mockDelete).toHaveBeenCalledTimes(3);
  });

  it('aborts cleanly when the DB query throws (never deletes anything)', async () => {
    mockFindMany.mockRejectedValueOnce(new Error('prisma down'));

    await expect(
      runMinioOrphanCleanup({
        retentionDays: 30,
        dryRun: false,
        nowMs: NOW,
      })
    ).rejects.toThrow(/prisma down/);
    expect(mockListAll).not.toHaveBeenCalled();
    expect(mockDelete).not.toHaveBeenCalled();
  });
});
