import { createHash } from 'node:crypto';

import {
  createOutputArtifactKey,
  createSourceArtifactKey,
  createUploadArtifactKey,
  DOCX_MIME_TYPE,
  resolveTemplateTwinBucket,
  type TemplateTwinArtifactKind,
} from './keys';
import {
  assertTenantOwnedArtifactKey,
  TemplateTwinArtifactNotFoundError,
} from './ownership';

const DEFAULT_MAX_ARTIFACT_BYTES = 25 * 1024 * 1024;

interface TemplateTwinObjectStat {
  size: number;
  metaData?: Record<string, string | number | undefined>;
}

export interface TemplateTwinObjectClient {
  bucketExists(bucket: string): Promise<boolean>;
  statObject(bucket: string, objectKey: string): Promise<TemplateTwinObjectStat>;
  putObject(
    bucket: string,
    objectKey: string,
    bytes: Buffer,
    sizeBytes: number,
    metadata: Record<string, string>
  ): Promise<unknown>;
  getObject(bucket: string, objectKey: string): Promise<AsyncIterable<unknown>>;
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

export interface StoreUploadArtifactInput {
  practiceId: string;
  /** Opaque id minted per upload attempt — NOT a template id. */
  uploadId: string;
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
  expectedSha256: string;
  expectedSizeBytes?: number;
}

export interface TemplateTwinArtifactStore {
  readonly bucket: string;
  storeSourceArtifact(input: StoreSourceArtifactInput): Promise<StoredTemplateTwinArtifact>;
  storeOutputArtifact(input: StoreOutputArtifactInput): Promise<StoredTemplateTwinArtifact>;
  /** RC-2 (#106(b)): keep the doctor's original bytes BEFORE extraction, when
   *  no template — and therefore no lineage or version — exists yet. */
  storeUploadArtifact(input: StoreUploadArtifactInput): Promise<StoredTemplateTwinArtifact>;
  readUploadArtifact(input: ReadArtifactInput): Promise<Buffer>;
  readSourceArtifact(input: ReadArtifactInput): Promise<Buffer>;
  readOutputArtifact(input: ReadArtifactInput): Promise<Buffer>;
}

export interface CreateTemplateTwinArtifactStoreOptions {
  bucket?: string;
  clientFactory?: TemplateTwinObjectClientFactory;
  maxArtifactBytes?: number;
  /** Test seam. Production uses cryptographically random UUIDs. */
  idFactory?: () => string;
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
  return code === 'NotFound' || code === 'NoSuchKey' || code === 'NoSuchObject';
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

export function createTemplateTwinArtifactStore(
  options: CreateTemplateTwinArtifactStoreOptions = {}
): TemplateTwinArtifactStore {
  const bucket = options.bucket ?? resolveTemplateTwinBucket();
  const clientFactory = options.clientFactory ?? defaultClientFactory;
  const maxBytes = options.maxArtifactBytes ?? DEFAULT_MAX_ARTIFACT_BYTES;
  const idFactory = options.idFactory;
  if (!Number.isSafeInteger(maxBytes) || maxBytes < 1) {
    throw new TemplateTwinArtifactTooLargeError(DEFAULT_MAX_ARTIFACT_BYTES);
  }

  let clientPromise: Promise<TemplateTwinObjectClient> | null = null;
  let bucketReadyPromise: Promise<TemplateTwinObjectClient> | null = null;

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
          const exists = await client.bucketExists(bucket);
          // Provisioning and lifecycle policy are operations decisions. The
          // application deliberately never creates or reconfigures a bucket
          // from a clinical request path.
          if (!exists) {
            throw new TemplateTwinStorageUnavailableError(
              new Error('The private Template Twin bucket is not provisioned.'),
            );
          }
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
    objectKey: string;
    bytes: Buffer;
    digest: string;
    kind: TemplateTwinArtifactKind;
  }): Promise<StoredTemplateTwinArtifact> {
    assertBoundedSize(input.bytes.byteLength, maxBytes);
    const client = await readyClient();

    try {
      const existing = await client.statObject(bucket, input.objectKey);
      try {
        assertStoredMetadata(
          existing,
          input.digest,
          input.bytes.byteLength,
          input.kind
        );
      } catch {
        throw new TemplateTwinArtifactCollisionError();
      }
      return {
        bucket,
        objectKey: input.objectKey,
        sha256: input.digest,
        mimeType: DOCX_MIME_TYPE,
        sizeBytes: input.bytes.byteLength,
        created: false,
      };
    } catch (error) {
      if (error instanceof TemplateTwinArtifactCollisionError) throw error;
      if (!isObjectNotFound(error)) {
        throw new TemplateTwinStorageUnavailableError(error);
      }
    }

    try {
      await client.putObject(
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
      } catch (verificationError) {
        if (verificationError instanceof TemplateTwinArtifactIntegrityError) {
          throw new TemplateTwinArtifactCollisionError();
        }
        throw new TemplateTwinStorageUnavailableError(verificationError);
      }
      return {
        bucket,
        objectKey: input.objectKey,
        sha256: input.digest,
        mimeType: DOCX_MIME_TYPE,
        sizeBytes: input.bytes.byteLength,
        created: false,
      };
    }

    // A successful PUT is not enough: verify the provider persisted the exact
    // immutable metadata contract before returning a key to the DB layer.
    let stored: TemplateTwinObjectStat;
    try {
      stored = await client.statObject(bucket, input.objectKey);
    } catch (error) {
      throw new TemplateTwinStorageUnavailableError(error);
    }
    assertStoredMetadata(
      stored,
      input.digest,
      input.bytes.byteLength,
      input.kind
    );

    return {
      bucket,
      objectKey: input.objectKey,
      sha256: input.digest,
      mimeType: DOCX_MIME_TYPE,
      sizeBytes: input.bytes.byteLength,
      created: true,
    };
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

    const client = await readyClient();
    let stat: TemplateTwinObjectStat;
    try {
      stat = await client.statObject(bucket, input.objectKey);
    } catch (error) {
      if (isObjectNotFound(error)) throw new TemplateTwinArtifactNotFoundError();
      throw new TemplateTwinStorageUnavailableError(error);
    }
    assertBoundedSize(stat.size, maxBytes);
    const expectedSize = input.expectedSizeBytes ?? stat.size;
    if (!Number.isSafeInteger(expectedSize) || expectedSize < 1) {
      throw new TemplateTwinArtifactIntegrityError();
    }
    assertStoredMetadata(stat, input.expectedSha256, expectedSize, kind);

    let stream: AsyncIterable<unknown>;
    try {
      stream = await client.getObject(bucket, input.objectKey);
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
      return putOnce({ objectKey, bytes, digest, kind: 'source' });
    },
    async storeUploadArtifact(
      input: StoreUploadArtifactInput
    ): Promise<StoredTemplateTwinArtifact> {
      const bytes = asBuffer(input.bytes);
      const digest = sha256(bytes);
      const objectKey = createUploadArtifactKey({
        practiceId: input.practiceId,
        uploadId: input.uploadId,
        sha256: digest,
      });
      return putOnce({ objectKey, bytes, digest, kind: 'upload' });
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
      return putOnce({ objectKey, bytes, digest, kind: 'output' });
    },
    readSourceArtifact(input: ReadArtifactInput): Promise<Buffer> {
      return readVerified(input, 'source');
    },
    readOutputArtifact(input: ReadArtifactInput): Promise<Buffer> {
      return readVerified(input, 'output');
    },
    readUploadArtifact(input: ReadArtifactInput): Promise<Buffer> {
      return readVerified(input, 'upload');
    },
  });
}
