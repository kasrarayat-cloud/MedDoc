import { Readable } from "node:stream";

import { describe, expect, it, vi } from "vitest";

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
} from "..";

interface MemoryObject {
  bytes: Buffer;
  metadata: Record<string, string>;
  versionId: string;
  etag: string;
}

class MemoryObjectClient implements TemplateTwinObjectClient {
  readonly buckets = new Set<string>();
  readonly objects = new Map<string, MemoryObject>();
  readonly streamOverrides = new Map<string, Buffer>();
  missNextStat = false;
  private version = 0;
  readonly putObject = vi.fn(
    async (
      bucket: string,
      objectKey: string,
      bytes: Buffer,
      _sizeBytes: number,
      metadata: Record<string, string>,
    ) => {
      const storageKey = `${bucket}/${objectKey}`;
      if (metadata["If-None-Match"] === "*" && this.objects.has(storageKey)) {
        throw Object.assign(new Error("conditional write rejected"), {
          code: "PreconditionFailed",
          statusCode: 412,
        });
      }
      const persistedMetadata = { ...metadata };
      delete persistedMetadata["If-None-Match"];
      this.version += 1;
      const versionId = `version-${this.version}`;
      const etag = `etag-${this.version}`;
      this.objects.set(storageKey, {
        bytes: Buffer.from(bytes),
        metadata: persistedMetadata,
        versionId,
        etag,
      });
      return { versionId, etag };
    },
  );

  async bucketExists(bucket: string): Promise<boolean> {
    return this.buckets.has(bucket);
  }

  async statObject(
    bucket: string,
    objectKey: string,
    options?: { versionId?: string },
  ) {
    if (this.missNextStat) {
      this.missNextStat = false;
      throw Object.assign(new Error("synthetic stale read"), {
        code: "NotFound",
      });
    }
    const item = this.objects.get(`${bucket}/${objectKey}`);
    if (!item) throw Object.assign(new Error("missing"), { code: "NotFound" });
    if (options?.versionId && options.versionId !== item.versionId) {
      throw Object.assign(new Error("missing version"), { code: "NoSuchVersion" });
    }
    return {
      size: item.bytes.byteLength,
      metaData: item.metadata,
      versionId: item.versionId,
      etag: item.etag,
    };
  }

  async getObject(
    bucket: string,
    objectKey: string,
    options?: { versionId?: string },
  ): Promise<AsyncIterable<unknown>> {
    const storageKey = `${bucket}/${objectKey}`;
    const item = this.objects.get(storageKey);
    if (!item) throw Object.assign(new Error("missing"), { code: "NoSuchKey" });
    if (options?.versionId && options.versionId !== item.versionId) {
      throw Object.assign(new Error("missing version"), { code: "NoSuchVersion" });
    }
    return Readable.from([this.streamOverrides.get(storageKey) ?? item.bytes]);
  }

  overrideStream(bucket: string, objectKey: string, bytes: Buffer): void {
    const storageKey = `${bucket}/${objectKey}`;
    if (!this.objects.has(storageKey)) throw new Error("test object missing");
    this.streamOverrides.set(storageKey, Buffer.from(bytes));
  }

  tamperBytes(bucket: string, objectKey: string, bytes: Buffer): void {
    const item = this.objects.get(`${bucket}/${objectKey}`);
    if (!item) throw new Error("test object missing");
    item.bytes = Buffer.from(bytes);
  }

  tamperMetadata(
    bucket: string,
    objectKey: string,
    key: string,
    value: string,
  ): void {
    const item = this.objects.get(`${bucket}/${objectKey}`);
    if (!item) throw new Error("test object missing");
    item.metadata[key] = value;
  }
}

const DOCX_BYTES = Buffer.from("PK\u0003\u0004synthetic-docx-package");
const MANIFEST_SHA = "c".repeat(64);
const READINESS_ENV = {
  TEMPLATE_TWIN_STORAGE_PROFILE: "production",
  MINIO_USE_SSL: "true",
  TEMPLATE_TWIN_STORAGE_PRIVATE_ACCESS_ATTESTED: "true",
  TEMPLATE_TWIN_STORAGE_ENCRYPTION_AT_REST_ATTESTED: "true",
  TEMPLATE_TWIN_STORAGE_LEAST_PRIVILEGE_ATTESTED: "true",
  TEMPLATE_TWIN_STORAGE_VERSIONING_OBJECT_LOCK_ATTESTED: "true",
  TEMPLATE_TWIN_STORAGE_LIFECYCLE_RETENTION_ATTESTED: "true",
  TEMPLATE_TWIN_STORAGE_BACKUP_RESTORE_ATTESTED: "true",
} as const;

function setup() {
  const client = new MemoryObjectClient();
  client.buckets.add(DEFAULT_TEMPLATE_TWIN_BUCKET);
  const factory = vi.fn(() => client);
  const store = createTemplateTwinArtifactStore({
    clientFactory: factory,
    idFactory: () => "opaque_artifact_1",
    readinessEnv: READINESS_ENV,
    objectLedgerClient: null,
  });
  return { client, factory, store };
}

describe("Template Twin artifact storage initialization", () => {
  it("uses a pre-provisioned dedicated bucket and does not initialize the provider eagerly", async () => {
    const { client, factory, store } = setup();
    expect(store.bucket).toBe(DEFAULT_TEMPLATE_TWIN_BUCKET);
    expect(factory).not.toHaveBeenCalled();
    expect(client.buckets).toContain(DEFAULT_TEMPLATE_TWIN_BUCKET);

    await store.storeSourceArtifact({
      practiceId: "practice_1",
      lineageId: "lineage_1",
      templateVersion: 1,
      bytes: DOCX_BYTES,
    });

    expect(factory).toHaveBeenCalledTimes(1);
    expect(client.buckets).toContain(DEFAULT_TEMPLATE_TWIN_BUCKET);
  });

  it("never creates production infrastructure from an application request", async () => {
    const client = new MemoryObjectClient();
    const store = createTemplateTwinArtifactStore({
      clientFactory: () => client,
      readinessEnv: READINESS_ENV,
      objectLedgerClient: null,
    });

    await expect(
      store.storeSourceArtifact({
        practiceId: "practice_1",
        lineageId: "lineage_1",
        templateVersion: 1,
        bytes: DOCX_BYTES,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStorageUnavailableError);
    expect(client.buckets.size).toBe(0);
  });

  it("allows provider-presence checks without reading or exposing credential values", () => {
    expect(hasTemplateTwinStorageProvider({})).toBe(false);
    expect(
      hasTemplateTwinStorageProvider({
        MINIO_ACCESS_KEY: "present",
        MINIO_SECRET_KEY: "present",
      }),
    ).toBe(true);
  });

  it("does not fail until I/O when the provider is absent", async () => {
    const factory = vi.fn(() => {
      throw new Error("credentials absent");
    });
    const store = createTemplateTwinArtifactStore({
      clientFactory: factory,
      readinessEnv: READINESS_ENV,
      objectLedgerClient: null,
    });
    expect(factory).not.toHaveBeenCalled();

    await expect(
      store.storeSourceArtifact({
        practiceId: "practice_1",
        lineageId: "lineage_1",
        templateVersion: 1,
        bytes: DOCX_BYTES,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStorageUnavailableError);
  });
});

describe("Template Twin put-once behavior", () => {
  it("keeps generated candidates in a distinct immutable namespace", async () => {
    const { store } = setup();
    const stored = await store.storeCandidateArtifact({
      practiceId: "practice_1",
      candidateId: "candidate_1",
      candidateVersion: 1,
      bytes: DOCX_BYTES,
    });

    expect(stored.objectKey).toContain(
      "/template-twin/candidates/candidate_1/v1/",
    );
    await expect(
      store.readCandidateArtifact({
        practiceId: "practice_1",
        objectKey: stored.objectKey,
        expectedObjectVersionId: stored.objectVersionId,
        expectedObjectEtag: stored.objectEtag,
        expectedSha256: stored.sha256,
        expectedSizeBytes: stored.sizeBytes,
      }),
    ).resolves.toEqual(DOCX_BYTES);
    await expect(
      store.readSourceArtifact({
        practiceId: "practice_1",
        objectKey: stored.objectKey,
        expectedObjectVersionId: stored.objectVersionId,
        expectedObjectEtag: stored.objectEtag,
        expectedSha256: stored.sha256,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinArtifactNotFoundError);
  });

  it("writes and verifies raw uploads in the isolated quarantine namespace", async () => {
    const { store } = setup();
    const stored = await store.storeQuarantineArtifact({
      practiceId: "practice_1",
      lineageId: "lineage_1",
      lineageVersion: 1,
      bytes: DOCX_BYTES,
    });

    expect(stored.objectKey).toContain("/template-twin/quarantine/");
    await expect(
      store.readQuarantineArtifact({
        practiceId: "practice_1",
        objectKey: stored.objectKey,
        expectedObjectVersionId: stored.objectVersionId,
        expectedObjectEtag: stored.objectEtag,
        expectedSha256: stored.sha256,
        expectedSizeBytes: stored.sizeBytes,
      }),
    ).resolves.toEqual(DOCX_BYTES);
    await expect(
      store.readSourceArtifact({
        practiceId: "practice_1",
        objectKey: stored.objectKey,
        expectedObjectVersionId: stored.objectVersionId,
        expectedObjectEtag: stored.objectEtag,
        expectedSha256: stored.sha256,
        expectedSizeBytes: stored.sizeBytes,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinArtifactNotFoundError);
  });

  it("fails closed when the provider omits an immutable version or ETag", async () => {
    const { client, store } = setup();
    const write = client.putObject.getMockImplementation();
    if (!write) throw new Error("Synthetic object writer is missing");
    client.putObject.mockImplementationOnce(async (...args) => {
      await write(...args);
      return { versionId: "", etag: "" };
    });

    await expect(
      store.storeSourceArtifact({
        practiceId: "practice_1",
        lineageId: "lineage_1",
        templateVersion: 1,
        bytes: DOCX_BYTES,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinArtifactIntegrityError);
  });

  it("durably records an object intent before PUT and marks the verified write afterward", async () => {
    const client = new MemoryObjectClient();
    client.buckets.add(DEFAULT_TEMPLATE_TWIN_BUCKET);
    const findUnique = vi.fn().mockResolvedValue(null);
    const create = vi.fn().mockResolvedValue({
      id: "ledger-synthetic-1",
      practiceId: "practice_1",
      objectKey: "pending",
      sha256: "a".repeat(64),
      sizeBytes: DOCX_BYTES.byteLength,
      kind: "source",
      state: "INTENT",
      claimType: null,
      claimId: null,
      attemptCount: 0,
      nextAttemptAt: null,
      retentionUntil: null,
      lastErrorCode: null,
    });
    const updateMany = vi.fn().mockResolvedValue({ count: 1 });
    const ledger = {
      templateTwinObjectLedger: {
        findUnique,
        findMany: vi.fn(),
        create,
        update: vi.fn(),
        updateMany,
      },
    };
    const store = createTemplateTwinArtifactStore({
      clientFactory: () => client,
      idFactory: () => "opaque_artifact_ledger",
      readinessEnv: READINESS_ENV,
      objectLedgerClient:
        ledger as unknown as import("../object-ledger").TemplateTwinObjectLedgerClient,
      orphanRetentionMs: 60_000,
    });

    const stored = await store.storeSourceArtifact({
      practiceId: "practice_1",
      lineageId: "lineage_1",
      templateVersion: 1,
      bytes: DOCX_BYTES,
    });

    expect(create).toHaveBeenCalledWith({
      data: expect.objectContaining({
        objectKey: stored.objectKey,
        state: "INTENT",
      }),
    });
    expect(create.mock.invocationCallOrder[0]).toBeLessThan(
      client.putObject.mock.invocationCallOrder[0]!,
    );
    expect(updateMany.mock.invocationCallOrder[0]).toBeGreaterThan(
      client.putObject.mock.invocationCallOrder[0]!,
    );
    expect(updateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ objectKey: stored.objectKey }),
        data: expect.objectContaining({ state: "WRITTEN_UNCLAIMED" }),
      }),
    );
  });

  it("writes content-addressed metadata once and treats an identical retry as idempotent", async () => {
    const { client, store } = setup();
    const input = {
      practiceId: "practice_1",
      lineageId: "lineage_1",
      templateVersion: 1,
      bytes: DOCX_BYTES,
    };

    const first = await store.storeSourceArtifact(input);
    const second = await store.storeSourceArtifact(input);

    expect(first.created).toBe(true);
    expect(second).toEqual({ ...first, created: false });
    expect(first.objectVersionId).toBe("version-1");
    expect(first.objectEtag).toBe("etag-1");
    expect(client.putObject).toHaveBeenCalledTimes(1);
    expect(first.objectKey).toMatch(
      /^practices\/practice_1\/template-twin\/sources\/lineage_1\/v1\/opaque_artifact_1\/[a-f0-9]{64}\.docx$/,
    );
    expect(client.putObject.mock.calls[0]?.[4]).toEqual({
      "Content-Type": DOCX_MIME_TYPE,
      "If-None-Match": "*",
      "X-Amz-Meta-Sha256": first.sha256,
      "X-Amz-Meta-Artifact-Kind": "source",
    });
    expect(store).not.toHaveProperty("delete");
    expect(store).not.toHaveProperty("overwrite");
  });

  it("uses a conditional PUT so a stale existence check cannot overwrite an object", async () => {
    const { client, store } = setup();
    const input = {
      practiceId: "practice_1",
      lineageId: "lineage_1",
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
      client.objects.get(`${first.bucket}/${first.objectKey}`)?.bytes,
    ).toEqual(DOCX_BYTES);
  });

  it("fails closed instead of overwriting an existing object with mismatched metadata", async () => {
    const { client, store } = setup();
    const first = await store.storeSourceArtifact({
      practiceId: "practice_1",
      lineageId: "lineage_1",
      templateVersion: 1,
      bytes: DOCX_BYTES,
    });
    client.tamperMetadata(
      first.bucket,
      first.objectKey,
      "X-Amz-Meta-Sha256",
      "0".repeat(64),
    );

    await expect(
      store.storeSourceArtifact({
        practiceId: "practice_1",
        lineageId: "lineage_1",
        templateVersion: 1,
        bytes: DOCX_BYTES,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinArtifactCollisionError);
    expect(client.putObject).toHaveBeenCalledTimes(1);
  });

  it("creates a tenant-scoped output key without document or patient names", async () => {
    const { store } = setup();
    const output = await store.storeOutputArtifact({
      practiceId: "practice_1",
      visitId: "visit_1",
      manifestSha256: MANIFEST_SHA,
      bytes: DOCX_BYTES,
    });
    expect(output.objectKey).toContain(
      `/outputs/visit_1/${MANIFEST_SHA}/opaque_artifact_1/`,
    );
    expect(output.objectKey).not.toContain("patient");
    expect(output.mimeType).toBe(DOCX_MIME_TYPE);
  });
});

describe("Template Twin verified reads", () => {
  it("rejects an ETag that is not bound to the exact stored provider version", async () => {
    const { store } = setup();
    const source = await store.storeSourceArtifact({
      practiceId: "practice_1",
      lineageId: "lineage_1",
      templateVersion: 1,
      bytes: DOCX_BYTES,
    });

    await expect(
      store.readSourceArtifact({
        practiceId: "practice_1",
        objectKey: source.objectKey,
        expectedObjectVersionId: source.objectVersionId,
        expectedObjectEtag: "provider-etag-replaced",
        expectedSha256: source.sha256,
        expectedSizeBytes: source.sizeBytes,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinArtifactIntegrityError);
  });

  it("re-hashes source and output bytes before returning them", async () => {
    const { store } = setup();
    const source = await store.storeSourceArtifact({
      practiceId: "practice_1",
      lineageId: "lineage_1",
      templateVersion: 1,
      bytes: DOCX_BYTES,
    });
    const output = await store.storeOutputArtifact({
      practiceId: "practice_1",
      visitId: "visit_1",
      manifestSha256: MANIFEST_SHA,
      bytes: DOCX_BYTES,
    });

    await expect(
      store.readSourceArtifact({
        practiceId: "practice_1",
        objectKey: source.objectKey,
        expectedObjectVersionId: source.objectVersionId,
        expectedObjectEtag: source.objectEtag,
        expectedSha256: source.sha256,
        expectedSizeBytes: source.sizeBytes,
      }),
    ).resolves.toEqual(DOCX_BYTES);
    await expect(
      store.readOutputArtifact({
        practiceId: "practice_1",
        objectKey: output.objectKey,
        expectedObjectVersionId: output.objectVersionId,
        expectedObjectEtag: output.objectEtag,
        expectedSha256: output.sha256,
        expectedSizeBytes: output.sizeBytes,
      }),
    ).resolves.toEqual(DOCX_BYTES);
  });

  it("rejects corrupt bytes even when provider metadata still claims the expected digest", async () => {
    const { client, store } = setup();
    const source = await store.storeSourceArtifact({
      practiceId: "practice_1",
      lineageId: "lineage_1",
      templateVersion: 1,
      bytes: DOCX_BYTES,
    });
    client.tamperBytes(
      source.bucket,
      source.objectKey,
      Buffer.alloc(DOCX_BYTES.byteLength, 0x78),
    );

    await expect(
      store.readSourceArtifact({
        practiceId: "practice_1",
        objectKey: source.objectKey,
        expectedObjectVersionId: source.objectVersionId,
        expectedObjectEtag: source.objectEtag,
        expectedSha256: source.sha256,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinArtifactIntegrityError);
  });

  it("rejects a missing output object", async () => {
    const { client, store } = setup();
    const output = await store.storeOutputArtifact({
      practiceId: "practice_1",
      visitId: "visit_1",
      manifestSha256: MANIFEST_SHA,
      bytes: DOCX_BYTES,
    });
    client.objects.delete(`${output.bucket}/${output.objectKey}`);

    await expect(
      store.readOutputArtifact({
        practiceId: "practice_1",
        objectKey: output.objectKey,
        expectedObjectVersionId: output.objectVersionId,
        expectedObjectEtag: output.objectEtag,
        expectedSha256: output.sha256,
        expectedSizeBytes: output.sizeBytes,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinArtifactNotFoundError);
  });

  it.each([
    ["truncated", DOCX_BYTES.subarray(0, DOCX_BYTES.byteLength - 3)],
    ["modified", Buffer.concat([Buffer.from("Q"), DOCX_BYTES.subarray(1)])],
    ["replaced", Buffer.alloc(DOCX_BYTES.byteLength, 0x72)],
  ])(
    "rejects %s output bytes even when stat metadata is unchanged",
    async (_case, streamed) => {
      const { client, store } = setup();
      const output = await store.storeOutputArtifact({
        practiceId: "practice_1",
        visitId: "visit_1",
        manifestSha256: MANIFEST_SHA,
        bytes: DOCX_BYTES,
      });
      client.overrideStream(output.bucket, output.objectKey, streamed);

      await expect(
        store.readOutputArtifact({
          practiceId: "practice_1",
          objectKey: output.objectKey,
          expectedObjectVersionId: output.objectVersionId,
          expectedObjectEtag: output.objectEtag,
          expectedSha256: output.sha256,
          expectedSizeBytes: output.sizeBytes,
        }),
      ).rejects.toBeInstanceOf(TemplateTwinArtifactIntegrityError);
    },
  );

  it("rejects cross-tenant reads before initializing or contacting the provider", async () => {
    const { store: sourceStore } = setup();
    const source = await sourceStore.storeSourceArtifact({
      practiceId: "practice_1",
      lineageId: "lineage_1",
      templateVersion: 1,
      bytes: DOCX_BYTES,
    });

    const factory = vi.fn(() => new MemoryObjectClient());
    const isolatedStore = createTemplateTwinArtifactStore({
      clientFactory: factory,
      readinessEnv: READINESS_ENV,
      objectLedgerClient: null,
    });
    await expect(
      isolatedStore.readSourceArtifact({
        practiceId: "practice_2",
        objectKey: source.objectKey,
        expectedObjectVersionId: source.objectVersionId,
        expectedObjectEtag: source.objectEtag,
        expectedSha256: source.sha256,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinArtifactNotFoundError);
    expect(factory).not.toHaveBeenCalled();
  });
});
