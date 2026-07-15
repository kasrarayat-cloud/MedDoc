export type TemplateTwinStorageControl =
  | 'private_access'
  | 'encryption_at_rest'
  | 'tls_expectation'
  | 'least_privilege'
  | 'versioning_object_lock'
  | 'lifecycle_retention'
  | 'backup_restore';

export interface TemplateTwinStorageControlEvidence {
  control: TemplateTwinStorageControl;
  source: 'verified' | 'attested' | 'qa_exception' | 'missing';
  detail: string;
}

export interface TemplateTwinStorageReadiness {
  ready: true;
  productionReady: boolean;
  profile: 'qa' | 'production';
  controls: TemplateTwinStorageControlEvidence[];
}

export interface TemplateTwinReadinessClient {
  bucketExists(bucket: string): Promise<boolean>;
  getBucketPolicy?(bucket: string): Promise<string>;
  getBucketEncryption?(bucket: string): Promise<unknown>;
  getBucketVersioning?(bucket: string): Promise<unknown>;
  getObjectLockConfig?(bucket: string): Promise<unknown>;
  getBucketLifecycle?(bucket: string): Promise<unknown>;
}

export class TemplateTwinStorageReadinessError extends Error {
  readonly code = 'TEMPLATE_TWIN_STORAGE_READINESS_FAILED';

  constructor(readonly failedControls: string[]) {
    super('Template Twin storage controls are not ready.');
    this.name = 'TemplateTwinStorageReadinessError';
  }
}

export const TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION =
  'accepted-isolated-synthetic-qa-gap' as const;

const QA_EXCEPTION_ENV: Readonly<
  Record<
    Exclude<
      TemplateTwinStorageControl,
      'private_access' | 'versioning_object_lock'
    >,
    string
  >
> = {
  encryption_at_rest:
    'TEMPLATE_TWIN_QA_STORAGE_ENCRYPTION_AT_REST_ATTESTATION',
  tls_expectation: 'TEMPLATE_TWIN_QA_STORAGE_TLS_EXPECTATION_ATTESTATION',
  least_privilege:
    'TEMPLATE_TWIN_QA_STORAGE_LEAST_PRIVILEGE_ATTESTATION',
  lifecycle_retention:
    'TEMPLATE_TWIN_QA_STORAGE_LIFECYCLE_RETENTION_ATTESTATION',
  backup_restore: 'TEMPLATE_TWIN_QA_STORAGE_BACKUP_RESTORE_ATTESTATION',
};

function explicitlyTrue(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === 'true';
}

function isQaDatabase(value: string | undefined): boolean {
  if (!value) return false;
  try {
    const url = new URL(value);
    return /(?:^|[_-])(qa|test)(?:$|[_-])/i.test(url.pathname.replace(/^\//, ''));
  } catch {
    return false;
  }
}

function noBucketPolicy(error: unknown): boolean {
  return (
    Boolean(error) &&
    typeof error === 'object' &&
    ['NoSuchBucketPolicy', 'NoSuchPolicy'].includes(
      String((error as { code?: unknown }).code ?? ''),
    )
  );
}

function containsPublicAllow(policyText: string): boolean {
  try {
    const policy = JSON.parse(policyText) as { Statement?: unknown };
    const statements = Array.isArray(policy.Statement) ? policy.Statement : [];
    return statements.some((candidate) => {
      if (!candidate || typeof candidate !== 'object') return false;
      const statement = candidate as { Effect?: unknown; Principal?: unknown };
      if (String(statement.Effect).toLowerCase() !== 'allow') return false;
      return (
        statement.Principal === '*' ||
        JSON.stringify(statement.Principal).includes('"*"')
      );
    });
  } catch {
    // A policy that cannot be interpreted cannot prove private access.
    return true;
  }
}

function nonEmptyProviderConfiguration(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  return Object.keys(value as Record<string, unknown>).length > 0;
}

function versioningEnabled(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  const status = (value as { Status?: unknown; status?: unknown }).Status ??
    (value as { status?: unknown }).status;
  return String(status).toLowerCase() === 'enabled';
}

function objectLockEnabled(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  const status =
    (value as { ObjectLockEnabled?: unknown; objectLockEnabled?: unknown })
      .ObjectLockEnabled ??
    (value as { objectLockEnabled?: unknown }).objectLockEnabled;
  return String(status).toLowerCase() === 'enabled';
}

function lifecycleConfigured(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  const record = value as { Rule?: unknown; Rules?: unknown; rules?: unknown };
  const rules = record.Rule ?? record.Rules ?? record.rules;
  return (
    Array.isArray(rules) &&
    rules.some((rule) => {
      if (!rule || typeof rule !== 'object') return false;
      const status = (rule as { Status?: unknown; status?: unknown }).Status ??
        (rule as { status?: unknown }).status;
      return String(status).toLowerCase() === 'enabled';
    })
  );
}

function evidence(
  control: TemplateTwinStorageControl,
  ok: boolean,
  source: TemplateTwinStorageControlEvidence['source'],
  detail: string,
): TemplateTwinStorageControlEvidence {
  return {
    control,
    source: ok ? source : 'missing',
    detail,
  };
}

async function privateAccessEvidence(input: {
  client: TemplateTwinReadinessClient;
  bucket: string;
  attested: boolean;
}): Promise<TemplateTwinStorageControlEvidence> {
  if (!input.client.getBucketPolicy) {
    return evidence(
      'private_access',
      input.attested,
      'attested',
      input.attested ? 'operator_attestation' : 'provider_check_unavailable',
    );
  }
  try {
    const policy = await input.client.getBucketPolicy(input.bucket);
    if (containsPublicAllow(policy)) {
      return evidence('private_access', false, 'verified', 'public_allow_detected');
    }
    return evidence('private_access', true, 'verified', 'no_public_allow');
  } catch (error) {
    if (noBucketPolicy(error)) {
      return evidence('private_access', true, 'verified', 'no_anonymous_policy');
    }
    return evidence(
      'private_access',
      input.attested,
      'attested',
      input.attested ? 'operator_attestation' : 'provider_check_failed',
    );
  }
}

async function providerOrAttested(input: {
  control: TemplateTwinStorageControl;
  check: (() => Promise<boolean>) | undefined;
  attested: boolean;
  verifiedDetail: string;
}): Promise<TemplateTwinStorageControlEvidence> {
  if (input.check) {
    try {
      if (await input.check()) {
        return evidence(input.control, true, 'verified', input.verifiedDetail);
      }
    } catch {
      // An explicit operator attestation may close a provider API evidence gap.
    }
  }
  return evidence(
    input.control,
    input.attested,
    'attested',
    input.attested ? 'operator_attestation' : 'evidence_missing',
  );
}

function qaExceptionEvidence(input: {
  control: keyof typeof QA_EXCEPTION_ENV;
  env: Readonly<Record<string, string | undefined>>;
}): TemplateTwinStorageControlEvidence {
  const envName = QA_EXCEPTION_ENV[input.control];
  const accepted =
    input.env[envName]?.trim() ===
    TEMPLATE_TWIN_QA_STORAGE_EXCEPTION_ATTESTATION;
  return {
    control: input.control,
    source: accepted ? 'qa_exception' : 'missing',
    detail: accepted
      ? `explicit_isolated_synthetic_qa_exception:${input.control}`
      : `named_qa_attestation_missing:${envName}`,
  };
}

async function qaProviderOrException(input: {
  control: keyof typeof QA_EXCEPTION_ENV;
  check: (() => Promise<boolean>) | undefined;
  verifiedDetail: string;
  env: Readonly<Record<string, string | undefined>>;
}): Promise<TemplateTwinStorageControlEvidence> {
  if (input.check) {
    try {
      if (await input.check()) {
        return evidence(input.control, true, 'verified', input.verifiedDetail);
      }
    } catch {
      // The named, local-only QA exception below must be explicit. Provider
      // errors never become implicit evidence.
    }
  }
  return qaExceptionEvidence({ control: input.control, env: input.env });
}

export async function verifyTemplateTwinStorageReadiness(input: {
  bucket: string;
  client: TemplateTwinReadinessClient;
  env?: Readonly<Record<string, string | undefined>>;
}): Promise<TemplateTwinStorageReadiness> {
  const env = input.env ?? process.env;
  const profile = env.TEMPLATE_TWIN_STORAGE_PROFILE?.trim().toLowerCase();
  if (profile !== 'qa' && profile !== 'production') {
    throw new TemplateTwinStorageReadinessError(['storage_profile']);
  }

  let bucketExists = false;
  try {
    bucketExists = await input.client.bucketExists(input.bucket);
  } catch {
    // Report only a stable control code; provider errors may contain endpoints.
  }
  if (!bucketExists) {
    throw new TemplateTwinStorageReadinessError(['bucket_exists']);
  }

  if (profile === 'qa') {
    const isolated =
      env.MOCK_AI_CALLS === 'true' &&
      isQaDatabase(env.DATABASE_URL) &&
      /(?:^|-)qa(?:-|$)/.test(input.bucket);
    if (!isolated) {
      throw new TemplateTwinStorageReadinessError(['qa_isolation']);
    }

    // QA is not allowed to turn one generic "synthetic" switch into blanket
    // storage evidence. Verify provider-observable controls and require a
    // separate, named acknowledgement for every remaining local-only gap.
    const controls: TemplateTwinStorageControlEvidence[] = [];
    controls.push(
      await privateAccessEvidence({
        client: input.client,
        bucket: input.bucket,
        attested: false,
      }),
    );
    controls.push(
      await qaProviderOrException({
        control: 'encryption_at_rest',
        check: input.client.getBucketEncryption
          ? async () =>
              nonEmptyProviderConfiguration(
                await input.client.getBucketEncryption!(input.bucket),
              )
          : undefined,
        verifiedDetail: 'provider_encryption_configured',
        env,
      }),
    );
    controls.push(
      explicitlyTrue(env.MINIO_USE_SSL)
        ? evidence(
            'tls_expectation',
            true,
            'verified',
            'provider_connection_tls_enabled',
          )
        : qaExceptionEvidence({ control: 'tls_expectation', env }),
    );
    controls.push(qaExceptionEvidence({ control: 'least_privilege', env }));
    controls.push(
      await providerOrAttested({
        control: 'versioning_object_lock',
        check:
          input.client.getBucketVersioning && input.client.getObjectLockConfig
            ? async () =>
                versioningEnabled(
                  await input.client.getBucketVersioning!(input.bucket),
                ) &&
                objectLockEnabled(
                  await input.client.getObjectLockConfig!(input.bucket),
                )
            : undefined,
        attested: false,
        verifiedDetail: 'versioning_and_object_lock_enabled',
      }),
    );
    controls.push(
      await qaProviderOrException({
        control: 'lifecycle_retention',
        check: input.client.getBucketLifecycle
          ? async () =>
              lifecycleConfigured(
                await input.client.getBucketLifecycle!(input.bucket),
              )
          : undefined,
        verifiedDetail: 'provider_lifecycle_configured',
        env,
      }),
    );
    controls.push(qaExceptionEvidence({ control: 'backup_restore', env }));

    const failedControls = controls
      .filter((control) => control.source === 'missing')
      .map((control) => control.control);
    if (failedControls.length > 0) {
      throw new TemplateTwinStorageReadinessError(failedControls);
    }
    return {
      ready: true,
      productionReady: false,
      profile,
      controls,
    };
  }

  const controls: TemplateTwinStorageControlEvidence[] = [];
  controls.push(
    await privateAccessEvidence({
      client: input.client,
      bucket: input.bucket,
      attested: explicitlyTrue(env.TEMPLATE_TWIN_STORAGE_PRIVATE_ACCESS_ATTESTED),
    }),
  );
  controls.push(
    await providerOrAttested({
      control: 'encryption_at_rest',
      check: input.client.getBucketEncryption
        ? async () =>
            nonEmptyProviderConfiguration(
              await input.client.getBucketEncryption!(input.bucket),
            )
        : undefined,
      attested: explicitlyTrue(
        env.TEMPLATE_TWIN_STORAGE_ENCRYPTION_AT_REST_ATTESTED,
      ),
      verifiedDetail: 'provider_encryption_configured',
    }),
  );
  controls.push(
    evidence(
      'tls_expectation',
      explicitlyTrue(env.MINIO_USE_SSL) ||
        explicitlyTrue(env.TEMPLATE_TWIN_STORAGE_TLS_EXPECTATION_ATTESTED),
      explicitlyTrue(env.MINIO_USE_SSL) ? 'verified' : 'attested',
      explicitlyTrue(env.MINIO_USE_SSL)
        ? 'provider_connection_tls_enabled'
        : 'operator_attestation',
    ),
  );
  controls.push(
    evidence(
      'least_privilege',
      explicitlyTrue(env.TEMPLATE_TWIN_STORAGE_LEAST_PRIVILEGE_ATTESTED),
      'attested',
      'operator_attestation',
    ),
  );
  controls.push(
    await providerOrAttested({
      control: 'versioning_object_lock',
      check:
        input.client.getBucketVersioning && input.client.getObjectLockConfig
          ? async () =>
              versioningEnabled(
                await input.client.getBucketVersioning!(input.bucket),
              ) &&
              objectLockEnabled(
                await input.client.getObjectLockConfig!(input.bucket),
              )
          : undefined,
      attested: explicitlyTrue(
        env.TEMPLATE_TWIN_STORAGE_VERSIONING_OBJECT_LOCK_ATTESTED,
      ),
      verifiedDetail: 'versioning_and_object_lock_enabled',
    }),
  );
  controls.push(
    await providerOrAttested({
      control: 'lifecycle_retention',
      check: input.client.getBucketLifecycle
        ? async () =>
            lifecycleConfigured(
              await input.client.getBucketLifecycle!(input.bucket),
            )
        : undefined,
      attested: explicitlyTrue(
        env.TEMPLATE_TWIN_STORAGE_LIFECYCLE_RETENTION_ATTESTED,
      ),
      verifiedDetail: 'provider_lifecycle_configured',
    }),
  );
  controls.push(
    evidence(
      'backup_restore',
      explicitlyTrue(env.TEMPLATE_TWIN_STORAGE_BACKUP_RESTORE_ATTESTED),
      'attested',
      'operator_attestation',
    ),
  );

  const failedControls = controls
    .filter((control) => control.source === 'missing')
    .map((control) => control.control);
  if (failedControls.length > 0) {
    throw new TemplateTwinStorageReadinessError(failedControls);
  }

  return { ready: true, productionReady: true, profile, controls };
}
