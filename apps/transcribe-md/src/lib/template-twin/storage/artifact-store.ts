import { createHash } from 'node:crypto';

import {
  createOutputArtifactKey,
  createSourceArtifactKey,
  DOCX_MIME_TYPE,
  resolveTemplateTwinBucket,
  type TemplateTwinArtifactKind,
} from './keys';
import {
  assertTenantOwnedArtifactKey,
  TemplateTwinArtifactNotFoundError,
} from './ownership';
import {
  verifyTemplateTwinStorageReadiness,
  type TemplateTwinReadinessClient,
} from './readiness';
import {
  beginTemplateTwinObjectWrite,
  markTemplateTwinObjectWritten,
  type TemplateTwinObjectLedgerClient,
} from './object-ledger';

const DEFAULT_MAX_ARTIFACT_BYTES = 25 * 1024 * 1024;

interface TemplateTwinObjectStat {
  size: number;
  etag?: string | null;
  versionId?: string | null;
  metaData?: Record<string, string | number | undefined>;
}

interface TemplateTwinObjectWriteResult {
  etag?: string | null;
  versionId?: string | null;
}

export interface TemplateTwinObjectClient extends TemplateTwinReadinessClient {
  bucketExists(bucket: string): Promise<boolean>;
  statObject(
    bucket: string,
    objectKey: string,
    options?: { versionId?: string },
  ): Promise<TemplateTwinObjectStat>;
  putObject(
    bucket: string,
    objectKey: string,
    bytes: Buffer,
    sizeBytes: number,
    metadata: Record<string, string>
  ): Promise<TemplateTwinObjectWriteResult>;
  getObject(
    bucket: string,
    objectKey: string,
    options?: { versionId?: string },
  ): Promise<AsyncIterable<unknown>>;
}

export type TemplateTwinObjectClientFactory = () =>
  | TemplateTwinObjectClient
  | Promise<TemplateTwinObjectClient>;

export class TemplateTwinStorageUnavailableError extends Error {
  readonly code = 'TEMPLATE_TWIN_STORAGE_UNAVAILABLE';

  constructor(cause?: unknown) {
    super('Template Twin artifact storage is unavailable.', { cause });
    this.name = 'TemplateTwinStorageUnavailableError';
  }
}

export class TemplateTwinArtifactIntegrityError extends Error {
  readonly code = 'TEMPLATE_TWIN_ARTIFACT_INTEGRITY_FAILED';

  constructor(message = 'Template Twin artifact integrity verification failed.') {
    super(message);
    this.name = 'TemplateTwinArtifactIntegrityError';
  }
}

export class TemplateTwinArtifactCollisionError extends Error {
  readonly code = 'TEMPLATE_TWIN_ARTIFACT_COLLISION';

  constructor() {
    super('An object already exists at the generated artifact key with different metadata.');
    this.name = 'TemplateTwinArtifactCollisionError';
  }
}

export class TemplateTwinArtifactTooLargeError extends Error {
  readonly code = 'TEMPLATE_TWIN_ARTIFACT_TOO_LARGE';

  constructor(maxBytes: number) {
    super(`Template Twin artifact exceeds the ${maxBytes}-byte safety limit.`);
    this.name = 'TemplateTwinArtifactTooLargeError';
  }
}

export interface StoredTemplateTwinArtifact {
  bucket: string;
  objectKey: string;
  objectVersionId: string;
  objectEtag: string;
  sha256: string;
  mimeType: typeof DOCX_MIME_TYPE;
  sizeBytes: number;
  created: boolean;
}

export interface StoreSourceArtifactInput {
  practiceId: string;
  lineageId: string;
  templateVersion: number;
  bytes: Buffer | Uint8Array;
}

export interface StoreOutputArtifactInput {
  practiceId: string;
  visitId: string;
  manifestSha256: string;
  bytes: Buffer | Uint8Array;
}

export interface ReadArtifactInput {
  practiceId: string;
  objectKey: string;
  expectedObjectVersionId: string;
  expectedObjectEtag: string;
  expectedSha256: string;
  expectedSizeBytes?: number;
}

export interface TemplateTwinArtifactStore {
  readonly bucket: string;
  storeSourceArtifact(input: StoreSourceArtifactInput): Promise<StoredTemplateTwinArtifact>;
  storeOutputArtifact(input: StoreOutputArtifactInput): Promise<StoredTemplateTwinArtifact>;
  readSourceArtifact(input: ReadArtifactInput): Promise<Buffer>;
  readOutputArtifact(input: ReadArtifactInput): Promise<Buffer>;
}

export interface CreateTemplateTwinArtifactStoreOptions {
  bucket?: string;
  clientFactory?: TemplateTwinObjectClientFactory;
  maxArtifactBytes?: number;
  /** Test seam. Production uses cryptographically random UUIDs. */
  idFactory?: () => string;
  /** Test/QA seam for non-secret storage-control evidence. Runtime callers
   * use process.env and therefore cannot bypass the readiness gate. */
  readinessEnv?: Readonly<Record<string, string | undefined>>;
  /** Injected only by synthetic unit/integration tests. Runtime callers omit
   * this and receive the real Prisma-backed durable ledger. */
  objectLedgerClient?: TemplateTwinObjectLedgerClient | null;
  /** Test seam. Runtime requires TEMPLATE_TWIN_ORPHAN_RETENTION_DAYS. */
  orphanRetentionMs?: number;
}

function sha256(bytes: Buffer): string {
  return createHash('sha256').update(bytes).digest('hex');
}

function metadataValue(
  stat: TemplateTwinObjectStat,
  name: string
): string | undefined {
  const target = name.toLowerCase();
  for (const [key, value] of Object.entries(stat.metaData ?? {})) {
    const normalized = key.toLowerCase().replace(/^x-amz-meta-/, '');
    if (normalized === target && value !== undefined) return String(value);
  }
  return undefined;
}

function isObjectNotFound(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  const code = String((error as { code?: unknown }).code ?? '');
  return (
    code === 'NotFound' ||
    code === 'NoSuchKey' ||
    code === 'NoSuchObject' ||
    code === 'NoSuchVersion'
  );
}

function isPreconditionFailed(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false;
  const candidate = error as { code?: unknown; statusCode?: unknown };
  const code = String(candidate.code ?? '');
  return (
    candidate.statusCode === 412 ||
    code === 'PreconditionFailed' ||
    code === 'ConditionNotMet'
  );
}

function asBuffer(bytes: Buffer | Uint8Array): Buffer {
  return Buffer.isBuffer(bytes) ? bytes : Buffer.from(bytes);
}

function assertBoundedSize(size: number, maxBytes: number): void {
  if (!Number.isSafeInteger(size) || size <= 0) {
    throw new TemplateTwinArtifactIntegrityError('Template Twin artifact is empty.');
  }
  if (size > maxBytes) throw new TemplateTwinArtifactTooLargeError(maxBytes);
}

function assertStoredMetadata(
  stat: TemplateTwinObjectStat,
  expectedSha256: string,
  expectedSizeBytes: number,
  expectedKind: TemplateTwinArtifactKind
): void {
  if (
    stat.size !== expectedSizeBytes ||
    metadataValue(stat, 'sha256') !== expectedSha256 ||
    metadataValue(stat, 'artifact-kind') !== expectedKind ||
    metadataValue(stat, 'content-type') !== DOCX_MIME_TYPE
  ) {
    throw new TemplateTwinArtifactIntegrityError();
  }
}

interface ProviderObjectIdentity {
  objectVersionId: string;
  objectEtag: string;
}

function requiredProviderIdentity(input: {
  versionId?: string | null;
  etag?: string | null;
}): ProviderObjectIdentity {
  const objectVersionId = input.versionId?.trim() ?? '';
  const objectEtag = input.etag?.trim() ?? '';
  if (!objectVersionId || !objectEtag) {
    throw new TemplateTwinArtifactIntegrityError(
      'Template Twin storage did not return an immutable object version and ETag.',
    );
  }
  return { objectVersionId, objectEtag };
}

function assertProviderIdentity(
  stat: TemplateTwinObjectStat,
  expected: ProviderObjectIdentity,
): void {
  const actual = requiredProviderIdentity(stat);
  if (
    actual.objectVersionId !== expected.objectVersionId ||
    actual.objectEtag !== expected.objectEtag
  ) {
    throw new TemplateTwinArtifactIntegrityError(
      'Template Twin provider object identity does not match the immutable record.',
    );
  }
}

async function defaultClientFactory(): Promise<TemplateTwinObjectClient> {
  // Dynamic import is intentional: importing or constructing this storage
  // abstraction must be safe in builds/tests where no MinIO provider is
  // configured. Existing getMinio() reads credentials only when invoked.
  try {
    const { getMinio } = await import('@/lib/minio');
    return getMinio() as unknown as TemplateTwinObjectClient;
  } catch (error) {
    throw new TemplateTwinStorageUnavailableError(error);
  }
}

export function hasTemplateTwinStorageProvider(
  env: Readonly<Record<string, string | undefined>> = process.env
): boolean {
  return Boolean(env.MINIO_ACCESS_KEY?.trim() && env.MINIO_SECRET_KEY?.trim());
}

function configuredOrphanRetentionMs(
  explicit: number | undefined,
  env: Readonly<Record<string, string | undefined>>,
): number {
  if (explicit !== undefined) {
    if (Number.isSafeInteger(explicit) && explicit > 0) return explicit;
    throw new TemplateTwinStorageUnavailableError(
      new Error('Invalid synthetic orphan retention window.'),
    );
  }
  const days = Number(env.TEMPLATE_TWIN_ORPHAN_RETENTION_DAYS ?? '');
  if (!Number.isSafeInteger(days) || days < 1 || days > 365) {
    throw new TemplateTwinStorageUnavailableError(
      new Error('An approved Template Twin orphan retention window is required.'),
    );
  }
  return days * 24 * 60 * 60 * 1000;
}

export function createTemplateTwinArtifactStore(
  options: CreateTemplateTwinArtifactStoreOptions = {}
): TemplateTwinArtifactStore {
  const bucket = options.bucket ?? resolveTemplateTwinBucket();
  const clientFactory = options.clientFactory ?? defaultClientFactory;
  const maxBytes = options.maxArtifactBytes ?? DEFAULT_MAX_ARTIFACT_BYTES;
  const idFactory = options.idFactory;
  const readinessEnv = options.readinessEnv;
  const configuredLedgerClient = options.objectLedgerClient;
  if (!Number.isSafeInteger(maxBytes) || maxBytes < 1) {
    throw new TemplateTwinArtifactTooLargeError(DEFAULT_MAX_ARTIFACT_BYTES);
  }

  let clientPromise: Promise<TemplateTwinObjectClient> | null = null;
  let bucketReadyPromise: Promise<TemplateTwinObjectClient> | null = null;
  let ledgerClientPromise: Promise<TemplateTwinObjectLedgerClient | null> | null =
    null;

  async function getLedgerClient(): Promise<TemplateTwinObjectLedgerClient | null> {
    if (configuredLedgerClient !== undefined) return configuredLedgerClient;
    if (!ledgerClientPromise) {
      ledgerClientPromise = import('@meddoc/db')
        .then((module) =>
          module.default as unknown as TemplateTwinObjectLedgerClient,
        )
        .catch((error) => {
          ledgerClientPromise = null;
          throw new TemplateTwinStorageUnavailableError(error);
        });
    }
    return ledgerClientPromise;
  }

  async function getClient(): Promise<TemplateTwinObjectClient> {
    if (!clientPromise) {
      clientPromise = Promise.resolve()
        .then(clientFactory)
        .catch((error) => {
          clientPromise = null;
          if (error instanceof TemplateTwinStorageUnavailableError) throw error;
          throw new TemplateTwinStorageUnavailableError(error);
        });
    }
    return clientPromise;
  }

  async function readyClient(): Promise<TemplateTwinObjectClient> {
    if (!bucketReadyPromise) {
      bucketReadyPromise = getClient()
        .then(async (client) => {
          // Provisioning and lifecycle policy are operations decisions. The
          // application never creates or reconfigures a bucket from a clinical
          // request path; it verifies provider controls or explicit operational
          // attestations and otherwise fails closed.
          await verifyTemplateTwinStorageReadiness({
            bucket,
            client,
            env: readinessEnv,
          });
          return client;
        })
        .catch((error) => {
          bucketReadyPromise = null;
          if (error instanceof TemplateTwinStorageUnavailableError) throw error;
          throw new TemplateTwinStorageUnavailableError(error);
        });
    }
    return bucketReadyPromise;
  }

  async function putOnce(input: {
    practiceId: string;
    objectKey: string;
    bytes: Buffer;
    digest: string;
    kind: TemplateTwinArtifactKind;
  }): Promise<StoredTemplateTwinArtifact> {
    assertBoundedSize(input.bytes.byteLength, maxBytes);
    const client = await readyClient();
    const ledger = await getLedgerClient();
    const orphanRetentionMs = ledger
      ? configuredOrphanRetentionMs(
          options.orphanRetentionMs,
          readinessEnv ?? process.env,
        )
      : null;
    const ledgerWrite = ledger
      ? await beginTemplateTwinObjectWrite(ledger, {
        practiceId: input.practiceId,
        objectKey: input.objectKey,
        sha256: input.digest,
        sizeBytes: input.bytes.byteLength,
        kind: input.kind,
      })
      : null;

    async function recorded(
      created: boolean,
      identity: ProviderObjectIdentity,
    ): Promise<StoredTemplateTwinArtifact> {
      if (ledger && orphanRetentionMs !== null) {
        await markTemplateTwinObjectWritten(ledger, {
          objectKey: input.objectKey,
          practiceId: input.practiceId,
          objectVersionId: identity.objectVersionId,
          objectEtag: identity.objectEtag,
          retentionUntil: new Date(Date.now() + orphanRetentionMs),
        });
      }
      return {
        bucket,
        objectKey: input.objectKey,
        objectVersionId: identity.objectVersionId,
        objectEtag: identity.objectEtag,
        sha256: input.digest,
        mimeType: DOCX_MIME_TYPE,
        sizeBytes: input.bytes.byteLength,
        created,
      };
    }

    if (ledgerWrite?.objectVersionId && ledgerWrite.objectEtag) {
      const identity = requiredProviderIdentity({
        versionId: ledgerWrite.objectVersionId,
        etag: ledgerWrite.objectEtag,
      });
      try {
        const existing = await client.statObject(bucket, input.objectKey, {
          versionId: identity.objectVersionId,
        });
        assertStoredMetadata(
          existing,
          input.digest,
          input.bytes.byteLength,
          input.kind,
        );
        assertProviderIdentity(existing, identity);
        return recorded(false, identity);
      } catch (error) {
        if (error instanceof TemplateTwinArtifactIntegrityError) throw error;
        if (isObjectNotFound(error)) {
          throw new TemplateTwinArtifactIntegrityError(
            'The provider version recorded by the Template Twin ledger is missing.',
          );
        }
        throw new TemplateTwinStorageUnavailableError(error);
      }
    }

    try {
      const existing = await client.statObject(bucket, input.objectKey);
      try {
        assertStoredMetadata(
          existing,
          input.digest,
          input.bytes.byteLength,
          input.kind
        );
        const identity = requiredProviderIdentity(existing);
        return recorded(false, identity);
      } catch {
        throw new TemplateTwinArtifactCollisionError();
      }
    } catch (error) {
      if (error instanceof TemplateTwinArtifactCollisionError) throw error;
      if (!isObjectNotFound(error)) {
        throw new TemplateTwinStorageUnavailableError(error);
      }
    }

    let written: TemplateTwinObjectWriteResult;
    try {
      written = await client.putObject(
        bucket,
        input.objectKey,
        input.bytes,
        input.bytes.byteLength,
        {
          'Content-Type': DOCX_MIME_TYPE,
          'If-None-Match': '*',
          'X-Amz-Meta-Sha256': input.digest,
          'X-Amz-Meta-Artifact-Kind': input.kind,
        }
      );
    } catch (error) {
      if (!isPreconditionFailed(error)) {
        throw new TemplateTwinStorageUnavailableError(error);
      }

      // A concurrent identical retry may win between STAT and PUT. The
      // conditional request prevents replacement; accept only an object whose
      // immutable metadata is byte-for-byte compatible with this write.
      try {
        const existing = await client.statObject(bucket, input.objectKey);
        assertStoredMetadata(
          existing,
          input.digest,
          input.bytes.byteLength,
          input.kind
        );
        const identity = requiredProviderIdentity(existing);
        return recorded(false, identity);
      } catch (verificationError) {
        if (verificationError instanceof TemplateTwinArtifactIntegrityError) {
          throw new TemplateTwinArtifactCollisionError();
        }
        throw new TemplateTwinStorageUnavailableError(verificationError);
      }
    }

    const identity = requiredProviderIdentity(written);
    // A successful PUT is not enough: verify the exact returned provider
    // version before exposing it to the relational claim layer.
    let stored: TemplateTwinObjectStat;
    try {
      stored = await client.statObject(bucket, input.objectKey, {
        versionId: identity.objectVersionId,
      });
    } catch (error) {
      throw new TemplateTwinStorageUnavailableError(error);
    }
    assertStoredMetadata(
      stored,
      input.digest,
      input.bytes.byteLength,
      input.kind,
    );
    assertProviderIdentity(stored, identity);
    return recorded(true, identity);
  }

  async function readVerified(
    input: ReadArtifactInput,
    kind: TemplateTwinArtifactKind
  ): Promise<Buffer> {
    const parsed = assertTenantOwnedArtifactKey({
      objectKey: input.objectKey,
      practiceId: input.practiceId,
      kind,
    });
    if (parsed.sha256 !== input.expectedSha256) {
      throw new TemplateTwinArtifactIntegrityError();
    }
    const expectedIdentity = requiredProviderIdentity({
      versionId: input.expectedObjectVersionId,
      etag: input.expectedObjectEtag,
    });

    const client = await readyClient();
    let stat: TemplateTwinObjectStat;
    try {
      stat = await client.statObject(bucket, input.objectKey, {
        versionId: expectedIdentity.objectVersionId,
      });
    } catch (error) {
      if (isObjectNotFound(error)) throw new TemplateTwinArtifactNotFoundError();
      throw new TemplateTwinStorageUnavailableError(error);
    }
    assertProviderIdentity(stat, expectedIdentity);
    assertBoundedSize(stat.size, maxBytes);
    const expectedSize = input.expectedSizeBytes ?? stat.size;
    if (!Number.isSafeInteger(expectedSize) || expectedSize < 1) {
      throw new TemplateTwinArtifactIntegrityError();
    }
    assertStoredMetadata(stat, input.expectedSha256, expectedSize, kind);

    let stream: AsyncIterable<unknown>;
    try {
      stream = await client.getObject(bucket, input.objectKey, {
        versionId: expectedIdentity.objectVersionId,
      });
    } catch (error) {
      if (isObjectNotFound(error)) throw new TemplateTwinArtifactNotFoundError();
      throw new TemplateTwinStorageUnavailableError(error);
    }

    const chunks: Buffer[] = [];
    const digest = createHash('sha256');
    let bytesRead = 0;
    for await (const value of stream) {
      let chunk: Buffer;
      if (Buffer.isBuffer(value)) chunk = value;
      else if (value instanceof Uint8Array) chunk = Buffer.from(value);
      else if (typeof value === 'string') chunk = Buffer.from(value);
      else throw new TemplateTwinArtifactIntegrityError();
      bytesRead += chunk.byteLength;
      if (bytesRead > maxBytes) throw new TemplateTwinArtifactTooLargeError(maxBytes);
      digest.update(chunk);
      chunks.push(chunk);
    }

    if (
      bytesRead !== expectedSize ||
      digest.digest('hex') !== input.expectedSha256
    ) {
      throw new TemplateTwinArtifactIntegrityError();
    }
    return Buffer.concat(chunks, bytesRead);
  }

  return Object.freeze({
    bucket,
    async storeSourceArtifact(
      input: StoreSourceArtifactInput
    ): Promise<StoredTemplateTwinArtifact> {
      const bytes = asBuffer(input.bytes);
      const digest = sha256(bytes);
      const objectKey = createSourceArtifactKey({
        practiceId: input.practiceId,
        lineageId: input.lineageId,
        templateVersion: input.templateVersion,
        sha256: digest,
        ...(idFactory ? { idFactory } : {}),
      });
      return putOnce({
        practiceId: input.practiceId,
        objectKey,
        bytes,
        digest,
        kind: 'source',
      });
    },
    async storeOutputArtifact(
      input: StoreOutputArtifactInput
    ): Promise<StoredTemplateTwinArtifact> {
      const bytes = asBuffer(input.bytes);
      const digest = sha256(bytes);
      const objectKey = createOutputArtifactKey({
        practiceId: input.practiceId,
        visitId: input.visitId,
        manifestSha256: input.manifestSha256,
        outputSha256: digest,
        ...(idFactory ? { idFactory } : {}),
      });
      return putOnce({
        practiceId: input.practiceId,
        objectKey,
        bytes,
        digest,
        kind: 'output',
      });
    },
    readSourceArtifact(input: ReadArtifactInput): Promise<Buffer> {
      return readVerified(input, 'source');
    },
    readOutputArtifact(input: ReadArtifactInput): Promise<Buffer> {
      return readVerified(input, 'output');
    },
  });
}
