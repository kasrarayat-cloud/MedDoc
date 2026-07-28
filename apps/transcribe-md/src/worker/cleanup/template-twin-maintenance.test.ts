import { beforeEach, describe, expect, it, vi } from 'vitest';

import { JOB_TEMPLATE_TWIN_MAINTENANCE } from '@/lib/queue';
import { reconcileTemplateTwinObjectLedgers } from '@/lib/template-twin/storage/object-ledger';
import {
  TemplateTwinMaintenanceConfigurationError,
  TemplateTwinMaintenanceExecutionError,
  createTemplateTwinMinioObjectAdmin,
  resolveTemplateTwinMaintenanceConfig,
  runTemplateTwinMaintenance,
  scheduleTemplateTwinMaintenance,
} from './template-twin-maintenance';

const DAY_MS = 24 * 60 * 60 * 1000;
const OBJECT_KEY =
  'practices/practice-1/template-twin/outputs/visit-1/' +
  `${'a'.repeat(64)}/artifact-1/${'b'.repeat(64)}.docx`;

const enabledEnv = {
  TEMPLATE_TWIN_MAINTENANCE_ENABLED: 'true',
  TEMPLATE_TWIN_ORPHAN_RETENTION_DAYS: '14',
  TRANSCRIBE_MD_TEMPLATE_BUCKET: 'transcribe-md-template-artifacts-qa',
};

const drainAudit = vi.fn();
const reconcileObjects = vi.fn();
const upsertJobScheduler = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  drainAudit.mockResolvedValue({ delivered: 2, failed: 0, contended: 1 });
  reconcileObjects.mockResolvedValue({
    recovered: 1,
    scheduled: 1,
    purged: 0,
    failed: 0,
  });
  upsertJobScheduler.mockResolvedValue(undefined);
});

describe('Template Twin maintenance configuration', () => {
  it('is disabled and non-destructive by default', () => {
    expect(resolveTemplateTwinMaintenanceConfig({})).toEqual({
      enabled: false,
      cron: '*/5 * * * *',
      orphanRetentionMs: null,
      purgeApproved: false,
      auditLimit: 100,
      objectLimit: 100,
    });
  });

  it('does not let dormant maintenance configuration disrupt the visit worker', () => {
    expect(
      resolveTemplateTwinMaintenanceConfig({
        TEMPLATE_TWIN_MAINTENANCE_ENABLED: 'false',
        TEMPLATE_TWIN_ORPHAN_RETENTION_DAYS: 'invalid',
        TEMPLATE_TWIN_MAINTENANCE_AUDIT_LIMIT: '99999',
      }),
    ).toMatchObject({ enabled: false, purgeApproved: false });
  });

  it('requires an explicit bounded orphan-retention window when enabled', () => {
    for (const value of [undefined, '', '0', '-1', '1.5', '366', 'not-days']) {
      expect(() =>
        resolveTemplateTwinMaintenanceConfig({
          TEMPLATE_TWIN_MAINTENANCE_ENABLED: 'true',
          TEMPLATE_TWIN_ORPHAN_RETENTION_DAYS: value,
        }),
      ).toThrow(TemplateTwinMaintenanceConfigurationError);
    }
  });

  it('keeps purging off unless the independent approval flag is exactly true', () => {
    for (const value of [undefined, '', 'false', 'yes', '1']) {
      expect(
        resolveTemplateTwinMaintenanceConfig({
          ...enabledEnv,
          TEMPLATE_TWIN_ORPHAN_PURGE_APPROVED: value,
        }).purgeApproved,
      ).toBe(false);
    }
    expect(
      resolveTemplateTwinMaintenanceConfig({
        ...enabledEnv,
        TEMPLATE_TWIN_ORPHAN_PURGE_APPROVED: ' true ',
      }),
    ).toMatchObject({
      enabled: true,
      orphanRetentionMs: 14 * DAY_MS,
      purgeApproved: true,
    });
  });

  it('rejects unbounded batch sizes before starting work', () => {
    expect(() =>
      resolveTemplateTwinMaintenanceConfig({
        ...enabledEnv,
        TEMPLATE_TWIN_MAINTENANCE_AUDIT_LIMIT: '101',
      }),
    ).toThrow(TemplateTwinMaintenanceConfigurationError);
    expect(() =>
      resolveTemplateTwinMaintenanceConfig({
        ...enabledEnv,
        TEMPLATE_TWIN_MAINTENANCE_OBJECT_LIMIT: '501',
      }),
    ).toThrow(TemplateTwinMaintenanceConfigurationError);
  });
});

describe('Template Twin dedicated-bucket object administrator', () => {
  it('reads provider metadata from the dedicated bucket without opening bytes', async () => {
    const statObject = vi.fn().mockResolvedValue({
      size: 128,
      versionId: 'provider-version-synthetic',
      etag: 'provider-etag-synthetic',
      metaData: { 'X-Amz-Meta-Sha256': 'b'.repeat(64) },
    });
    const removeObject = vi.fn();
    const admin = createTemplateTwinMinioObjectAdmin({
      client: { statObject, removeObject },
      env: enabledEnv,
    });

    await expect(admin.statObject(OBJECT_KEY)).resolves.toEqual({
      exists: true,
      objectVersionId: 'provider-version-synthetic',
      objectEtag: 'provider-etag-synthetic',
      sha256: 'b'.repeat(64),
      sizeBytes: 128,
    });
    expect(statObject).toHaveBeenCalledWith(
      'transcribe-md-template-artifacts-qa',
      OBJECT_KEY,
    );
  });

  it('returns an existence result for a missing object without leaking provider text', async () => {
    const statObject = vi.fn().mockRejectedValue({
      code: 'NoSuchKey',
      message: 'synthetic private endpoint and object key',
    });
    const admin = createTemplateTwinMinioObjectAdmin({
      client: { statObject, removeObject: vi.fn() },
      env: enabledEnv,
    });

    await expect(admin.statObject(OBJECT_KEY)).resolves.toEqual({
      exists: false,
    });
  });

  it('purges only the exact provider version recorded by the orphan ledger', async () => {
    const removeObject = vi.fn().mockResolvedValue(undefined);
    const admin = createTemplateTwinMinioObjectAdmin({
      client: { statObject: vi.fn(), removeObject },
      env: enabledEnv,
    });

    await admin.deleteObject(OBJECT_KEY, 'provider-version-synthetic');

    expect(removeObject).toHaveBeenCalledWith(
      'transcribe-md-template-artifacts-qa',
      OBJECT_KEY,
      { versionId: 'provider-version-synthetic' },
    );
  });

  it('refuses malformed or non-Twin keys before any provider operation', async () => {
    const statObject = vi.fn();
    const removeObject = vi.fn();
    const admin = createTemplateTwinMinioObjectAdmin({
      client: { statObject, removeObject },
      env: enabledEnv,
    });

    await expect(
      admin.statObject('../other-bucket/object'),
    ).rejects.toBeInstanceOf(TemplateTwinMaintenanceExecutionError);
    await expect(
      admin.deleteObject('unowned/object', 'provider-version-synthetic'),
    ).rejects.toBeInstanceOf(TemplateTwinMaintenanceExecutionError);
    expect(statObject).not.toHaveBeenCalled();
    expect(removeObject).not.toHaveBeenCalled();
  });
});

describe('Template Twin maintenance execution and scheduling', () => {
  it('does no database or storage work while disabled', async () => {
    await expect(
      runTemplateTwinMaintenance({
        env: {},
        prisma: {} as never,
        dependencies: { drainAudit, reconcileObjects },
      }),
    ).resolves.toEqual({
      enabled: false,
      purgeApproved: false,
      audit: { delivered: 0, failed: 0, contended: 0 },
      objects: { recovered: 0, scheduled: 0, purged: 0, failed: 0 },
    });
    expect(drainAudit).not.toHaveBeenCalled();
    expect(reconcileObjects).not.toHaveBeenCalled();
  });

  it('drains the outbox and reconciles orphans with purge disabled by default', async () => {
    const objectAdmin = {
      statObject: vi.fn(),
      deleteObject: vi.fn(),
    };
    const db = {} as never;
    const now = new Date('2026-07-15T21:00:00.000Z');

    await expect(
      runTemplateTwinMaintenance({
        env: enabledEnv,
        prisma: db,
        objectAdmin,
        now,
        dependencies: { drainAudit, reconcileObjects },
      }),
    ).resolves.toEqual({
      enabled: true,
      purgeApproved: false,
      audit: { delivered: 2, failed: 0, contended: 1 },
      objects: { recovered: 1, scheduled: 1, purged: 0, failed: 0 },
    });
    expect(drainAudit).toHaveBeenCalledWith({
      prisma: db,
      now,
      limit: 100,
    });
    expect(reconcileObjects).toHaveBeenCalledWith({
      prisma: db,
      objectAdmin: expect.objectContaining({
        statObject: expect.any(Function),
        deleteObject: expect.any(Function),
      }),
      now,
      orphanRetentionMs: 14 * DAY_MS,
      purgeApproved: false,
      limit: 100,
    });
  });

  it('passes explicit purge approval to reconciliation and never infers it', async () => {
    await runTemplateTwinMaintenance({
      env: {
        ...enabledEnv,
        TEMPLATE_TWIN_ORPHAN_PURGE_APPROVED: 'true',
      },
      prisma: {} as never,
      objectAdmin: { statObject: vi.fn(), deleteObject: vi.fn() },
      dependencies: { drainAudit, reconcileObjects },
    });
    expect(reconcileObjects).toHaveBeenCalledWith(
      expect.objectContaining({ purgeApproved: true }),
    );
  });

  it('re-checks purge approval at delete time for an older PURGE_PENDING row', async () => {
    const deleteObject = vi.fn();
    const update = vi.fn().mockResolvedValue({});
    const db = {
      templateTwinObjectLedger: {
        findMany: vi.fn().mockResolvedValue([
          {
            id: 'ledger-1',
            practiceId: 'practice-1',
            objectKey: OBJECT_KEY,
            sha256: 'b'.repeat(64),
            sizeBytes: 128,
            kind: 'output',
            state: 'PURGE_PENDING',
            claimType: null,
            claimId: null,
            attemptCount: 1,
            nextAttemptAt: null,
            retentionUntil: new Date('2026-07-14T21:00:00.000Z'),
            lastErrorCode: null,
          },
        ]),
        update,
      },
    } as never;

    await expect(
      runTemplateTwinMaintenance({
        env: enabledEnv,
        prisma: db,
        objectAdmin: { statObject: vi.fn(), deleteObject },
        now: new Date('2026-07-15T21:00:00.000Z'),
        dependencies: {
          drainAudit,
          reconcileObjects: reconcileTemplateTwinObjectLedgers,
        },
      }),
    ).resolves.toMatchObject({
      purgeApproved: false,
      objects: { purged: 0, failed: 1 },
    });
    expect(deleteObject).not.toHaveBeenCalled();
    expect(update).toHaveBeenCalledWith({
      where: { id: 'ledger-1' },
      data: expect.objectContaining({
        lastErrorCode: 'OBJECT_PURGE_FAILED',
      }),
    });
  });

  it('turns dependency failures into a stable non-sensitive worker error', async () => {
    drainAudit.mockRejectedValueOnce(
      new Error('Synthetic database dependency failure at db.synthetic.test'),
    );
    const promise = runTemplateTwinMaintenance({
      env: enabledEnv,
      prisma: {} as never,
      objectAdmin: { statObject: vi.fn(), deleteObject: vi.fn() },
      dependencies: { drainAudit, reconcileObjects },
    });

    await expect(promise).rejects.toEqual(
      expect.objectContaining({
        code: 'TEMPLATE_TWIN_MAINTENANCE_FAILED',
        message: 'Template Twin maintenance failed.',
      }),
    );
  });

  it('registers exactly one bounded BullMQ cleanup job when enabled', async () => {
    await expect(
      scheduleTemplateTwinMaintenance({
        queue: { upsertJobScheduler },
        env: {
          ...enabledEnv,
          TEMPLATE_TWIN_MAINTENANCE_CRON: '7 * * * *',
        },
      }),
    ).resolves.toMatchObject({ enabled: true, cron: '7 * * * *' });
    expect(upsertJobScheduler).toHaveBeenCalledWith(
      'template-twin-maintenance',
      { pattern: '7 * * * *', tz: 'UTC' },
      {
        name: JOB_TEMPLATE_TWIN_MAINTENANCE,
        data: {},
        opts: { attempts: 1 },
      },
    );
  });

  it('does not register a scheduler while maintenance is disabled', async () => {
    await expect(
      scheduleTemplateTwinMaintenance({
        queue: { upsertJobScheduler },
        env: {},
      }),
    ).resolves.toMatchObject({ enabled: false });
    expect(upsertJobScheduler).not.toHaveBeenCalled();
  });
});
