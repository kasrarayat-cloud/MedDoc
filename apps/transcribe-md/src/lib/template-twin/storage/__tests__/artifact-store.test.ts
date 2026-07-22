import { Readable } from 'node:stream';

import { describe, expect, it, vi } from 'vitest';

import {
  createTemplateTwinArtifactStore,
  DEFAULT_TEMPLATE_TWIN_BUCKET,
  DOCX_MIME_TYPE,
  hasTemplateTwinStorageProvider,
  TemplateTwinArtifactCollisionError,
  TemplateTwinArtifactIntegrityError,
  TemplateTwinArtifactNotFoundError,
  TemplateTwinStorageUnavailableError,
  type TemplateTwinObjectClient,
} from '..';

interface MemoryObject {
  bytes: Buffer;
  metadata: Record<string, string>;
}

class MemoryObjectClient implements TemplateTwinObjectClient {
  readonly buckets = new Set<string>();
  readonly objects = new Map<string, MemoryObject>();
  missNextStat = false;
  readonly putObject = vi.fn(
    async (
      bucket: string,
      objectKey: string,
      bytes: Buffer,
      _sizeBytes: number,
      metadata: Record<string, string>
    ) => {
      const storageKey = `${bucket}/${objectKey}`;
      if (metadata['If-None-Match'] === '*' && this.objects.has(storageKey)) {
        throw Object.assign(new Error('conditional write rejected'), {
          code: 'PreconditionFailed',
          statusCode: 412,
        });
      }
      const persistedMetadata = { ...metadata };
      delete persistedMetadata['If-None-Match'];
      this.objects.set(storageKey, {
        bytes: Buffer.from(bytes),
        metadata: persistedMetadata,
      });
    }
  );

  async bucketExists(bucket: string): Promise<boolean> {
    return this.buckets.has(bucket);
  }

  async statObject(bucket: string, objectKey: string) {
    if (this.missNextStat) {
      this.missNextStat = false;
      throw Object.assign(new Error('synthetic stale read'), { code: 'NotFound' });
    }
    const item = this.objects.get(`${bucket}/${objectKey}`);
    if (!item) throw Object.assign(new Error('missing'), { code: 'NotFound' });
    return { size: item.bytes.byteLength, metaData: item.metadata };
  }

  async getObject(bucket: string, objectKey: string): Promise<AsyncIterable<unknown>> {
    const item = this.objects.get(`${bucket}/${objectKey}`);
    if (!item) throw Object.assign(new Error('missing'), { code: 'NoSuchKey' });
    return Readable.from([item.bytes]);
  }

  tamperBytes(bucket: string, objectKey: string, bytes: Buffer): void {
    const item = this.objects.get(`${bucket}/${objectKey}`);
    if (!item) throw new Error('test object missing');
    item.bytes = Buffer.from(bytes);
  }

  tamperMetadata(bucket: string, objectKey: string, key: string, value: string): void {
    const item = this.objects.get(`${bucket}/${objectKey}`);
    if (!item) throw new Error('test object missing');
    item.metadata[key] = value;
  }
}

const DOCX_BYTES = Buffer.from('PK\u0003\u0004synthetic-docx-package');
const MANIFEST_SHA = 'c'.repeat(64);

function setup() {
  const client = new MemoryObjectClient();
  client.buckets.add(DEFAULT_TEMPLATE_TWIN_BUCKET);
  const factory = vi.fn(() => client);
  const store = createTemplateTwinArtifactStore({
    clientFactory: factory,
    idFactory: () => 'opaque_artifact_1',
  });
  return { client, factory, store };
}

describe('Template Twin artifact storage initialization', () => {
  it('uses a pre-provisioned dedicated bucket and does not initialize the provider eagerly', async () => {
    const { client, factory, store } = setup();
    expect(store.bucket).toBe(DEFAULT_TEMPLATE_TWIN_BUCKET);
    expect(factory).not.toHaveBeenCalled();
    expect(client.buckets).toContain(DEFAULT_TEMPLATE_TWIN_BUCKET);

    await store.storeSourceArtifact({
      practiceId: 'practice_1',
      lineageId: 'lineage_1',
      templateVersion: 1,
      bytes: DOCX_BYTES,
    });

    expect(factory).toHaveBeenCalledTimes(1);
    expect(client.buckets).toContain(DEFAULT_TEMPLATE_TWIN_BUCKET);
  });

  it('never creates production infrastructure from an application request', async () => {
    const client = new MemoryObjectClient();
    const store = createTemplateTwinArtifactStore({ clientFactory: () => client });

    await expect(
      store.storeSourceArtifact({
        practiceId: 'practice_1',
        lineageId: 'lineage_1',
        templateVersion: 1,
        bytes: DOCX_BYTES,
      })
    ).rejects.toBeInstanceOf(TemplateTwinStorageUnavailableError);
    expect(client.buckets.size).toBe(0);
  });

  it('allows provider-presence checks without reading or exposing credential values', () => {
    expect(hasTemplateTwinStorageProvider({})).toBe(false);
    expect(
      hasTemplateTwinStorageProvider({
        MINIO_ACCESS_KEY: 'present',
        MINIO_SECRET_KEY: 'present',
      })
    ).toBe(true);
  });

  it('does not fail until I/O when the provider is absent', async () => {
    const factory = vi.fn(() => {
      throw new Error('credentials absent');
    });
    const store = createTemplateTwinArtifactStore({ clientFactory: factory });
    expect(factory).not.toHaveBeenCalled();

    await expect(
      store.storeSourceArtifact({
        practiceId: 'practice_1',
        lineageId: 'lineage_1',
        templateVersion: 1,
        bytes: DOCX_BYTES,
      })
    ).rejects.toBeInstanceOf(TemplateTwinStorageUnavailableError);
  });
});

describe('Template Twin put-once behavior', () => {
  it('writes content-addressed metadata once and treats an identical retry as idempotent', async () => {
    const { client, store } = setup();
    const input = {
      practiceId: 'practice_1',
      lineageId: 'lineage_1',
      templateVersion: 1,
      bytes: DOCX_BYTES,
    };

    const first = await store.storeSourceArtifact(input);
    const second = await store.storeSourceArtifact(input);

    expect(first.created).toBe(true);
    expect(second).toEqual({ ...first, created: false });
    expect(client.putObject).toHaveBeenCalledTimes(1);
    expect(first.objectKey).toMatch(
      /^practices\/practice_1\/template-twin\/sources\/lineage_1\/v1\/opaque_artifact_1\/[a-f0-9]{64}\.docx$/
    );
    expect(client.putObject.mock.calls[0]?.[4]).toEqual({
      'Content-Type': DOCX_MIME_TYPE,
      'If-None-Match': '*',
      'X-Amz-Meta-Sha256': first.sha256,
      'X-Amz-Meta-Artifact-Kind': 'source',
    });
    expect(store).not.toHaveProperty('delete');
    expect(store).not.toHaveProperty('overwrite');
  });

  it('uses a conditional PUT so a stale existence check cannot overwrite an object', async () => {
    const { client, store } = setup();
    const input = {
      practiceId: 'practice_1',
      lineageId: 'lineage_1',
      templateVersion: 1,
      bytes: DOCX_BYTES,
    };
    const first = await store.storeSourceArtifact(input);
    client.missNextStat = true;

    await expect(store.storeSourceArtifact(input)).resolves.toEqual({
      ...first,
      created: false,
    });
    expect(client.putObject).toHaveBeenCalledTimes(2);
    expect(
      client.objects.get(`${first.bucket}/${first.objectKey}`)?.bytes
    ).toEqual(DOCX_BYTES);
  });

  it('fails closed instead of overwriting an existing object with mismatched metadata', async () => {
    const { client, store } = setup();
    const first = await store.storeSourceArtifact({
      practiceId: 'practice_1',
      lineageId: 'lineage_1',
      templateVersion: 1,
      bytes: DOCX_BYTES,
    });
    client.tamperMetadata(
      first.bucket,
      first.objectKey,
      'X-Amz-Meta-Sha256',
      '0'.repeat(64)
    );

    await expect(
      store.storeSourceArtifact({
        practiceId: 'practice_1',
        lineageId: 'lineage_1',
        templateVersion: 1,
        bytes: DOCX_BYTES,
      })
    ).rejects.toBeInstanceOf(TemplateTwinArtifactCollisionError);
    expect(client.putObject).toHaveBeenCalledTimes(1);
  });

  it('creates a tenant-scoped output key without document or patient names', async () => {
    const { store } = setup();
    const output = await store.storeOutputArtifact({
      practiceId: 'practice_1',
      visitId: 'visit_1',
      manifestSha256: MANIFEST_SHA,
      bytes: DOCX_BYTES,
    });
    expect(output.objectKey).toContain(
      `/outputs/visit_1/${MANIFEST_SHA}/opaque_artifact_1/`
    );
    expect(output.objectKey).not.toContain('patient');
    expect(output.mimeType).toBe(DOCX_MIME_TYPE);
  });
});

describe('Template Twin verified reads', () => {
  it('re-hashes source and output bytes before returning them', async () => {
    const { store } = setup();
    const source = await store.storeSourceArtifact({
      practiceId: 'practice_1',
      lineageId: 'lineage_1',
      templateVersion: 1,
      bytes: DOCX_BYTES,
    });
    const output = await store.storeOutputArtifact({
      practiceId: 'practice_1',
      visitId: 'visit_1',
      manifestSha256: MANIFEST_SHA,
      bytes: DOCX_BYTES,
    });

    await expect(
      store.readSourceArtifact({
        practiceId: 'practice_1',
        objectKey: source.objectKey,
        expectedSha256: source.sha256,
        expectedSizeBytes: source.sizeBytes,
      })
    ).resolves.toEqual(DOCX_BYTES);
    await expect(
      store.readOutputArtifact({
        practiceId: 'practice_1',
        objectKey: output.objectKey,
        expectedSha256: output.sha256,
        expectedSizeBytes: output.sizeBytes,
      })
    ).resolves.toEqual(DOCX_BYTES);
  });

  it('rejects corrupt bytes even when provider metadata still claims the expected digest', async () => {
    const { client, store } = setup();
    const source = await store.storeSourceArtifact({
      practiceId: 'practice_1',
      lineageId: 'lineage_1',
      templateVersion: 1,
      bytes: DOCX_BYTES,
    });
    client.tamperBytes(
      source.bucket,
      source.objectKey,
      Buffer.alloc(DOCX_BYTES.byteLength, 0x78)
    );

    await expect(
      store.readSourceArtifact({
        practiceId: 'practice_1',
        objectKey: source.objectKey,
        expectedSha256: source.sha256,
      })
    ).rejects.toBeInstanceOf(TemplateTwinArtifactIntegrityError);
  });

  it('rejects cross-tenant reads before initializing or contacting the provider', async () => {
    const { store: sourceStore } = setup();
    const source = await sourceStore.storeSourceArtifact({
      practiceId: 'practice_1',
      lineageId: 'lineage_1',
      templateVersion: 1,
      bytes: DOCX_BYTES,
    });

    const factory = vi.fn(() => new MemoryObjectClient());
    const isolatedStore = createTemplateTwinArtifactStore({ clientFactory: factory });
    await expect(
      isolatedStore.readSourceArtifact({
        practiceId: 'practice_2',
        objectKey: source.objectKey,
        expectedSha256: source.sha256,
      })
    ).rejects.toBeInstanceOf(TemplateTwinArtifactNotFoundError);
    expect(factory).not.toHaveBeenCalled();
  });
});
