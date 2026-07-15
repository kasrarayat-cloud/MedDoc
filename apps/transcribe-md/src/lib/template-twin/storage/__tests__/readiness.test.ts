import { describe, expect, it, vi } from 'vitest';

import {
  TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION,
  TemplateTwinStorageReadinessError,
  verifyTemplateTwinStorageReadiness,
} from '../readiness';

const QA_ATTESTATIONS = {
  TEMPLATE_TWIN_QA_STORAGE_ENCRYPTION_AT_REST_ATTESTATION:
    TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION,
  TEMPLATE_TWIN_QA_STORAGE_TLS_EXPECTATION_ATTESTATION:
    TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION,
  TEMPLATE_TWIN_QA_STORAGE_LEAST_PRIVILEGE_ATTESTATION:
    TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION,
  TEMPLATE_TWIN_QA_STORAGE_LIFECYCLE_RETENTION_ATTESTATION:
    TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION,
  TEMPLATE_TWIN_QA_STORAGE_BACKUP_RESTORE_ATTESTATION:
    TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION,
} as const;

function safeQaEnv(
  overrides: Record<string, string | undefined> = {},
): Record<string, string | undefined> {
  return {
    TEMPLATE_TWIN_STORAGE_PROFILE: 'qa',
    MOCK_AI_CALLS: 'true',
    DATABASE_URL: 'postgresql://synthetic@postgres/meddoc_qa_test',
    MINIO_USE_SSL: 'false',
    ...QA_ATTESTATIONS,
    ...overrides,
  };
}

function verifiedQaClient() {
  return {
    bucketExists: vi.fn().mockResolvedValue(true),
    getBucketPolicy: vi.fn().mockRejectedValue({ code: 'NoSuchBucketPolicy' }),
    getBucketVersioning: vi.fn().mockResolvedValue({ Status: 'Enabled' }),
    getObjectLockConfig: vi
      .fn()
      .mockResolvedValue({ objectLockEnabled: 'Enabled' }),
  };
}

function safeProductionEnv(
  overrides: Record<string, string | undefined> = {},
): Record<string, string | undefined> {
  return {
    TEMPLATE_TWIN_STORAGE_PROFILE: 'production',
    MINIO_USE_SSL: 'true',
    TEMPLATE_TWIN_STORAGE_LEAST_PRIVILEGE_ATTESTED: 'true',
    TEMPLATE_TWIN_STORAGE_BACKUP_RESTORE_ATTESTED: 'true',
    ...overrides,
  };
}

function verifiedClient() {
  return {
    bucketExists: vi.fn().mockResolvedValue(true),
    getBucketPolicy: vi.fn().mockRejectedValue({ code: 'NoSuchBucketPolicy' }),
    getBucketEncryption: vi.fn().mockResolvedValue({ Rule: [{ ApplyServerSideEncryptionByDefault: { SSEAlgorithm: 'AES256' } }] }),
    getBucketVersioning: vi.fn().mockResolvedValue({ Status: 'Enabled' }),
    getObjectLockConfig: vi.fn().mockResolvedValue({ ObjectLockEnabled: 'Enabled' }),
    getBucketLifecycle: vi.fn().mockResolvedValue({ Rule: [{ ID: 'retain-template-twin', Status: 'Enabled' }] }),
  };
}

describe('Template Twin storage readiness', () => {
  it('fails closed when a storage profile and evidence are absent', async () => {
    await expect(
      verifyTemplateTwinStorageReadiness({
        bucket: 'transcribe-md-template-artifacts',
        client: verifiedClient(),
        env: {},
      }),
    ).rejects.toMatchObject({
      code: 'TEMPLATE_TWIN_STORAGE_READINESS_FAILED',
    });
  });

  it('verifies provider-visible QA controls and reports named local gaps without claiming production readiness', async () => {
    const result = await verifyTemplateTwinStorageReadiness({
      bucket: 'transcribe-md-template-artifacts-qa',
      client: verifiedQaClient(),
      env: safeQaEnv(),
    });

    expect(result.ready).toBe(true);
    expect(result.productionReady).toBe(false);
    expect(result.controls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          control: 'private_access',
          source: 'verified',
        }),
        expect.objectContaining({
          control: 'versioning_object_lock',
          source: 'verified',
        }),
        expect.objectContaining({
          control: 'encryption_at_rest',
          source: 'qa_exception',
        }),
        expect.objectContaining({
          control: 'tls_expectation',
          source: 'qa_exception',
        }),
        expect.objectContaining({
          control: 'least_privilege',
          source: 'qa_exception',
        }),
        expect.objectContaining({
          control: 'lifecycle_retention',
          source: 'qa_exception',
        }),
        expect.objectContaining({
          control: 'backup_restore',
          source: 'qa_exception',
        }),
      ]),
    );
  });

  it('does not let the QA profile authorize a non-QA database', async () => {
    await expect(
      verifyTemplateTwinStorageReadiness({
        bucket: 'transcribe-md-template-artifacts-qa',
        client: verifiedQaClient(),
        env: safeQaEnv({
          DATABASE_URL: 'postgresql://synthetic@postgres/meddoc',
        }),
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStorageReadinessError);
  });

  it('rejects the former blanket QA exemption without provider proof and named per-control attestations', async () => {
    await expect(
      verifyTemplateTwinStorageReadiness({
        bucket: 'transcribe-md-template-artifacts-qa',
        client: { bucketExists: vi.fn().mockResolvedValue(true) },
        env: {
          TEMPLATE_TWIN_STORAGE_PROFILE: 'qa',
          TEMPLATE_TWIN_QA_STORAGE_ATTESTATION: 'isolated-synthetic-only',
          MOCK_AI_CALLS: 'true',
          DATABASE_URL: 'postgresql://synthetic@postgres/meddoc_qa_test',
        },
      }),
    ).rejects.toMatchObject({
      failedControls: expect.arrayContaining([
        'private_access',
        'versioning_object_lock',
        'encryption_at_rest',
        'tls_expectation',
        'least_privilege',
        'lifecycle_retention',
        'backup_restore',
      ]),
    });
  });

  it.each([
    [
      'encryption_at_rest',
      'TEMPLATE_TWIN_QA_STORAGE_ENCRYPTION_AT_REST_ATTESTATION',
    ],
    ['tls_expectation', 'TEMPLATE_TWIN_QA_STORAGE_TLS_EXPECTATION_ATTESTATION'],
    [
      'least_privilege',
      'TEMPLATE_TWIN_QA_STORAGE_LEAST_PRIVILEGE_ATTESTATION',
    ],
    [
      'lifecycle_retention',
      'TEMPLATE_TWIN_QA_STORAGE_LIFECYCLE_RETENTION_ATTESTATION',
    ],
    ['backup_restore', 'TEMPLATE_TWIN_QA_STORAGE_BACKUP_RESTORE_ATTESTATION'],
  ] as const)(
    'fails QA readiness when the named %s exception is missing or generic',
    async (control, envName) => {
      for (const value of [undefined, 'true', 'isolated-synthetic-only']) {
        await expect(
          verifyTemplateTwinStorageReadiness({
            bucket: 'transcribe-md-template-artifacts-qa',
            client: verifiedQaClient(),
            env: safeQaEnv({ [envName]: value }),
          }),
        ).rejects.toMatchObject({ failedControls: [control] });
      }
    },
  );

  it.each([
    ['anonymous access', (client: ReturnType<typeof verifiedQaClient>) => {
      client.getBucketPolicy.mockResolvedValue(
        JSON.stringify({ Statement: [{ Effect: 'Allow', Principal: '*' }] }),
      );
    }, 'private_access'],
    ['disabled versioning', (client: ReturnType<typeof verifiedQaClient>) => {
      client.getBucketVersioning.mockResolvedValue({ Status: 'Suspended' });
    }, 'versioning_object_lock'],
    ['missing object lock', (client: ReturnType<typeof verifiedQaClient>) => {
      client.getObjectLockConfig.mockResolvedValue({});
    }, 'versioning_object_lock'],
  ] as const)(
    'does not let named QA exceptions override provider-detected %s',
    async (_caseName, mutate, failedControl) => {
      const client = verifiedQaClient();
      mutate(client);
      await expect(
        verifyTemplateTwinStorageReadiness({
          bucket: 'transcribe-md-template-artifacts-qa',
          client,
          env: safeQaEnv(),
        }),
      ).rejects.toMatchObject({ failedControls: [failedControl] });
    },
  );

  it('accepts a production profile only when provider checks and required attestations pass', async () => {
    const result = await verifyTemplateTwinStorageReadiness({
      bucket: 'transcribe-md-template-artifacts',
      client: verifiedClient(),
      env: safeProductionEnv(),
    });

    expect(result).toMatchObject({ ready: true, productionReady: true });
    expect(result.controls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ control: 'private_access', source: 'verified' }),
        expect.objectContaining({ control: 'encryption_at_rest', source: 'verified' }),
        expect.objectContaining({ control: 'least_privilege', source: 'attested' }),
        expect.objectContaining({ control: 'backup_restore', source: 'attested' }),
      ]),
    );
  });

  it('rejects an anonymous/public bucket even if other controls are present', async () => {
    const client = verifiedClient();
    client.getBucketPolicy.mockResolvedValue(
      JSON.stringify({
        Statement: [{ Effect: 'Allow', Principal: '*', Action: 's3:GetObject' }],
      }),
    );

    await expect(
      verifyTemplateTwinStorageReadiness({
        bucket: 'transcribe-md-template-artifacts',
        client,
        env: safeProductionEnv(),
      }),
    ).rejects.toMatchObject({
      failedControls: expect.arrayContaining(['private_access']),
    });
  });

  it('fails production readiness when TLS, lifecycle, or backup evidence is missing', async () => {
    const client = verifiedClient();
    client.getBucketLifecycle.mockResolvedValue(null);

    await expect(
      verifyTemplateTwinStorageReadiness({
        bucket: 'transcribe-md-template-artifacts',
        client,
        env: safeProductionEnv({
          MINIO_USE_SSL: 'false',
          TEMPLATE_TWIN_STORAGE_BACKUP_RESTORE_ATTESTED: undefined,
        }),
      }),
    ).rejects.toMatchObject({
      failedControls: expect.arrayContaining([
        'tls_expectation',
        'lifecycle_retention',
        'backup_restore',
      ]),
    });
  });
});
