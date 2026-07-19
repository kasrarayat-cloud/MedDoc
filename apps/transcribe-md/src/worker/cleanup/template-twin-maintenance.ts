import prisma from '@meddoc/db';

import { drainTemplateTwinAuditOutbox } from '@/lib/template-twin/audit-outbox';
import {
  parseTemplateTwinArtifactKey,
  resolveTemplateTwinBucket,
} from '@/lib/template-twin/storage';
import {
  reconcileTemplateTwinObjectLedgers,
  type TemplateTwinObjectAdmin,
  type TemplateTwinObjectLedgerClient,
} from '@/lib/template-twin/storage/object-ledger';
import { getMinio } from '@/lib/minio';
import { JOB_TEMPLATE_TWIN_MAINTENANCE } from '@/lib/queue';
import {
  reconcileStaleTemplateTwinQuarantines,
  type TemplateTwinQuarantineReconciliationClient,
} from './template-twin-quarantine-reconciliation';

const DAY_MS = 24 * 60 * 60 * 1000;
const DEFAULT_CRON = '*/5 * * * *';
const DEFAULT_AUDIT_LIMIT = 100;
const DEFAULT_OBJECT_LIMIT = 100;
const AUDIT_DISPATCHER_SERVICE_ROLE = 'template-twin-audit-dispatcher';

type AuditOutboxClient = Parameters<
  typeof drainTemplateTwinAuditOutbox
>[0]['prisma'];

export type TemplateTwinMaintenancePrisma = AuditOutboxClient &
  TemplateTwinObjectLedgerClient &
  TemplateTwinQuarantineReconciliationClient;

export interface TemplateTwinMaintenanceConfig {
  enabled: boolean;
  cron: string;
  orphanRetentionMs: number | null;
  purgeApproved: boolean;
  auditLimit: number;
  objectLimit: number;
  quarantineLimit: number;
  quarantineStaleMs: number | null;
}

export interface TemplateTwinMaintenanceResult {
  enabled: boolean;
  purgeApproved: boolean;
  audit: {
    delivered: number;
    failed: number;
    contended: number;
  };
  objects: {
    recovered: number;
    scheduled: number;
    purged: number;
    failed: number;
  };
  quarantines: {
    quarantinedRejected: number;
    malwareCleanRejected: number;
    contended: number;
  };
}

export class TemplateTwinMaintenanceConfigurationError extends Error {
  readonly code = 'TEMPLATE_TWIN_MAINTENANCE_CONFIGURATION_INVALID';

  constructor() {
    super('Template Twin maintenance configuration is invalid.');
    this.name = 'TemplateTwinMaintenanceConfigurationError';
  }
}

export class TemplateTwinMaintenanceExecutionError extends Error {
  readonly code = 'TEMPLATE_TWIN_MAINTENANCE_FAILED';

  constructor() {
    // Provider and database errors can contain object keys, endpoints, or SQL.
    // Keep the worker-facing error stable and non-sensitive.
    super('Template Twin maintenance failed.');
    this.name = 'TemplateTwinMaintenanceExecutionError';
  }
}

function exactTrue(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === 'true';
}

function positiveBoundedInteger(
  value: string | undefined,
  fallback: number,
  maximum: number,
): number {
  if (value === undefined || value.trim() === '') return fallback;
  if (!/^[1-9][0-9]*$/.test(value.trim())) {
    throw new TemplateTwinMaintenanceConfigurationError();
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed > maximum) {
    throw new TemplateTwinMaintenanceConfigurationError();
  }
  return parsed;
}

/**
 * Maintenance is opt-in. Purging is a second, independent opt-in so merely
 * enabling delivery/reconciliation can never delete an artifact.
 */
export function resolveTemplateTwinMaintenanceConfig(
  env: Readonly<Record<string, string | undefined>> = process.env,
): TemplateTwinMaintenanceConfig {
  const enabled = exactTrue(env.TEMPLATE_TWIN_MAINTENANCE_ENABLED);
  const cron = env.TEMPLATE_TWIN_MAINTENANCE_CRON?.trim() || DEFAULT_CRON;

  if (!enabled) {
    return {
      enabled: false,
      cron,
      orphanRetentionMs: null,
      purgeApproved: false,
      auditLimit: DEFAULT_AUDIT_LIMIT,
      objectLimit: DEFAULT_OBJECT_LIMIT,
      quarantineLimit: DEFAULT_OBJECT_LIMIT,
      quarantineStaleMs: null,
    };
  }

  const auditLimit = positiveBoundedInteger(
    env.TEMPLATE_TWIN_MAINTENANCE_AUDIT_LIMIT,
    DEFAULT_AUDIT_LIMIT,
    100,
  );
  const objectLimit = positiveBoundedInteger(
    env.TEMPLATE_TWIN_MAINTENANCE_OBJECT_LIMIT,
    DEFAULT_OBJECT_LIMIT,
    500,
  );
  const quarantineLimit = positiveBoundedInteger(
    env.TEMPLATE_TWIN_MAINTENANCE_QUARANTINE_LIMIT,
    DEFAULT_OBJECT_LIMIT,
    500,
  );
  const quarantineStaleHours = positiveBoundedInteger(
    env.TEMPLATE_TWIN_QUARANTINE_STALE_HOURS,
    24,
    24 * 30,
  );

  const retentionDays = positiveBoundedInteger(
    env.TEMPLATE_TWIN_ORPHAN_RETENTION_DAYS,
    0,
    365,
  );
  if (retentionDays < 1) {
    throw new TemplateTwinMaintenanceConfigurationError();
  }

  return {
    enabled: true,
    cron,
    orphanRetentionMs: retentionDays * DAY_MS,
    purgeApproved: exactTrue(env.TEMPLATE_TWIN_ORPHAN_PURGE_APPROVED),
    auditLimit,
    objectLimit,
    quarantineLimit,
    quarantineStaleMs: quarantineStaleHours * 60 * 60 * 1000,
  };
}

interface TemplateTwinMinioStat {
  size: number;
  versionId?: string | null;
  etag?: string | null;
  metaData?: Record<string, string | number | undefined>;
}

export interface TemplateTwinMinioAdminClient {
  statObject(bucket: string, objectKey: string): Promise<TemplateTwinMinioStat>;
  removeObject(
    bucket: string,
    objectKey: string,
    options?: { versionId?: string },
  ): Promise<void>;
}

function metadataValue(
  stat: TemplateTwinMinioStat,
  expectedName: string,
): string | undefined {
  const expected = expectedName.toLowerCase();
  for (const [name, value] of Object.entries(stat.metaData ?? {})) {
    const normalized = name.toLowerCase().replace(/^x-amz-meta-/, '');
    if (normalized === expected && value !== undefined) return String(value);
  }
  return undefined;
}

function isMissingObject(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  const code = String((error as { code?: unknown }).code ?? '');
  return ['NotFound', 'NoSuchKey', 'NoSuchObject', 'NoSuchVersion'].includes(
    code,
  );
}

function assertManagedObjectKey(objectKey: string): void {
  if (!parseTemplateTwinArtifactKey(objectKey)) {
    throw new TemplateTwinMaintenanceExecutionError();
  }
}

/** A deliberately narrow administrator for the dedicated Twin bucket. */
export function createTemplateTwinMinioObjectAdmin(
  input: {
    client?: TemplateTwinMinioAdminClient;
    env?: Readonly<Record<string, string | undefined>>;
  } = {},
): TemplateTwinObjectAdmin {
  const env = input.env ?? process.env;
  const bucket = resolveTemplateTwinBucket(env);
  const client =
    input.client ?? (getMinio() as unknown as TemplateTwinMinioAdminClient);

  return {
    async statObject(objectKey) {
      assertManagedObjectKey(objectKey);
      try {
        const stat = await client.statObject(bucket, objectKey);
        return {
          exists: true,
          objectVersionId: stat.versionId?.trim() || undefined,
          objectEtag: stat.etag?.trim() || undefined,
          sha256: metadataValue(stat, 'sha256'),
          sizeBytes: stat.size,
        };
      } catch (error) {
        if (isMissingObject(error)) return { exists: false };
        throw new TemplateTwinMaintenanceExecutionError();
      }
    },
    async deleteObject(objectKey, objectVersionId) {
      assertManagedObjectKey(objectKey);
      if (!objectVersionId.trim()) {
        throw new TemplateTwinMaintenanceExecutionError();
      }
      try {
        await client.removeObject(bucket, objectKey, {
          versionId: objectVersionId,
        });
      } catch {
        throw new TemplateTwinMaintenanceExecutionError();
      }
    },
  };
}

interface MaintenanceDependencies {
  drainAudit: typeof drainTemplateTwinAuditOutbox;
  reconcileObjects: typeof reconcileTemplateTwinObjectLedgers;
  reconcileQuarantines: typeof reconcileStaleTemplateTwinQuarantines;
}

const defaultDependencies: MaintenanceDependencies = {
  drainAudit: drainTemplateTwinAuditOutbox,
  reconcileObjects: reconcileTemplateTwinObjectLedgers,
  reconcileQuarantines: reconcileStaleTemplateTwinQuarantines,
};

function purgeGuardedObjectAdmin(
  objectAdmin: TemplateTwinObjectAdmin,
  purgeApproved: boolean,
): TemplateTwinObjectAdmin {
  return {
    statObject: (objectKey) => objectAdmin.statObject(objectKey),
    async deleteObject(objectKey, objectVersionId) {
      // Re-check approval at the actual destructive boundary. This also
      // protects a PURGE_PENDING row created by an older approved run after
      // operations have withdrawn approval.
      if (!purgeApproved) {
        throw new TemplateTwinMaintenanceExecutionError();
      }
      await objectAdmin.deleteObject(objectKey, objectVersionId);
    },
  };
}

export async function runTemplateTwinMaintenance(
  input: {
    prisma?: TemplateTwinMaintenancePrisma;
    objectAdmin?: TemplateTwinObjectAdmin;
    env?: Readonly<Record<string, string | undefined>>;
    now?: Date;
    dependencies?: MaintenanceDependencies;
  } = {},
): Promise<TemplateTwinMaintenanceResult> {
  const env = input.env ?? process.env;
  const config = resolveTemplateTwinMaintenanceConfig(env);
  if (!config.enabled) {
    return {
      enabled: false,
      purgeApproved: false,
      audit: { delivered: 0, failed: 0, contended: 0 },
      objects: { recovered: 0, scheduled: 0, purged: 0, failed: 0 },
      quarantines: {
        quarantinedRejected: 0,
        malwareCleanRejected: 0,
        contended: 0,
      },
    };
  }

  const db =
    input.prisma ?? (prisma as unknown as TemplateTwinMaintenancePrisma);
  const dependencies = input.dependencies ?? defaultDependencies;

  try {
    const quarantines = await dependencies.reconcileQuarantines({
      prisma: db,
      now: input.now,
      staleAfterMs: config.quarantineStaleMs!,
      limit: config.quarantineLimit,
    });
    const audit =
      env.NODE_ENV !== 'production' ||
      env.QUILLMD_SERVICE_ROLE === AUDIT_DISPATCHER_SERVICE_ROLE
        ? await dependencies.drainAudit({
            prisma: db,
            now: input.now,
            limit: config.auditLimit,
          })
        : { delivered: 0, failed: 0, contended: 0 };
    const objectAdmin =
      input.objectAdmin ?? createTemplateTwinMinioObjectAdmin({ env });
    const objects = await dependencies.reconcileObjects({
      prisma: db,
      objectAdmin: purgeGuardedObjectAdmin(objectAdmin, config.purgeApproved),
      now: input.now,
      orphanRetentionMs: config.orphanRetentionMs!,
      purgeApproved: config.purgeApproved,
      limit: config.objectLimit,
    });
    return {
      enabled: true,
      purgeApproved: config.purgeApproved,
      audit,
      objects,
      quarantines,
    };
  } catch {
    throw new TemplateTwinMaintenanceExecutionError();
  }
}

interface CleanupQueueScheduler {
  upsertJobScheduler(
    schedulerId: string,
    repeat: { pattern: string; tz: string },
    template: {
      name: string;
      data: Record<string, never>;
      opts: { attempts: number };
    },
  ): Promise<unknown>;
}

export async function scheduleTemplateTwinMaintenance(input: {
  queue: CleanupQueueScheduler;
  env?: Readonly<Record<string, string | undefined>>;
}): Promise<TemplateTwinMaintenanceConfig> {
  const config = resolveTemplateTwinMaintenanceConfig(input.env);
  if (!config.enabled) return config;

  await input.queue.upsertJobScheduler(
    'template-twin-maintenance',
    { pattern: config.cron, tz: 'UTC' },
    {
      name: JOB_TEMPLATE_TWIN_MAINTENANCE,
      data: {},
      opts: { attempts: 1 },
    },
  );
  return config;
}
