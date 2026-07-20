import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { deflateSync } from "node:zlib";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { canonicalSha256 } from "../canonical";
import {
  buildTemplateTwinProviderOwnershipReceipt,
  runTemplateTwinOwnedModelComplete,
} from "../provider-ownership";

const aiMocks = vi.hoisted(() => ({ complete: vi.fn() }));
const delimiterMocks = vi.hoisted(() => ({
  injectionAttemptDetected: false,
}));

vi.mock("@meddoc/ai", () => ({
  delimiterSystemSuffix: () => "",
  wrapAsData: (value: string) => ({
    wrapped: value,
    suffix: "0123456789abcdef",
    injectionAttemptDetected: delimiterMocks.injectionAttemptDetected,
  }),
  modelClient: { complete: aiMocks.complete },
}));
vi.mock("../provider-ownership", () => ({
  runWithTemplateTwinProviderOwnershipContext: vi.fn(
    async (_context: unknown, callback: () => Promise<unknown>) => callback(),
  ),
  runTemplateTwinOwnedModelComplete: vi.fn(
    async (input: {
      args: unknown;
      client: { complete(args: unknown): Promise<unknown> };
    }) => input.client.complete(input.args),
  ),
  buildTemplateTwinProviderOwnershipReceipt: vi.fn(
    (input: {
      projection: {
        subjectId: string;
        subjectSha256: string;
        visitId: string | null;
        sourceArtifactId: string | null;
        compiledVersionId: string | null;
        noteTemplateId: string | null;
      };
    }) => {
      const evidence = {
        contractVersion: "template-twin-provider-ownership-receipt-v2",
        practiceId: "practice_synthetic",
        actorUserId: "admin_synthetic",
        providerMode: "LIVE",
        syntheticAdmissionId: null,
        ...input.projection,
        executions: [
          {
            executionId: "static-provider-execution-synthetic",
            operation: "STATIC_ASSET_PRIVACY_SCAN",
            resultSha256: "b".repeat(64),
          },
        ],
      };
      return { evidence, sha256: canonicalSha256(evidence) };
    },
  ),
}));
vi.mock("../runtime-attestation", () => ({
  registerTemplateTwinRuntimeAttestation: vi.fn().mockResolvedValue({
    instanceId: "app-1",
  }),
  TemplateTwinRuntimeAttestationError: class extends Error {},
}));

import {
  TemplateTwinStaticAssetError,
  approveTemplateTwinStaticAsset,
  assertTemplateTwinStaticAssetBindingsCurrent,
  inspectTemplateTwinStaticAsset,
  inspectTemplateTwinStaticAssetForReview,
  listTemplateTwinStaticAssetsForPractice,
  lockAndAssertTemplateTwinStaticAssetBindingsCurrent,
  rejectTemplateTwinStaticAsset,
  resolveApprovedTemplateTwinStaticAssets,
  revokeTemplateTwinStaticAsset,
  type LocalStaticAssetOcr,
  type TemplateTwinStaticAssetActor,
  type TemplateTwinStaticAssetClaimDb,
} from "../static-assets";

const POSTGRES_ECMASCRIPT_TRIM_WHITESPACE_CLASS =
  "U&'[\\0009-\\000D\\0020\\00A0\\1680\\2000-\\200A\\2028\\2029\\202F\\205F\\3000\\FEFF]'";

const RELEASE_ID = "0eb13c1b-0893-4cb0-bbd6-68b3e544baac";
const RELEASE_IDENTITY_SHA256 = "1".repeat(64);
const RUNTIME_MANIFEST_SHA256 = "2".repeat(64);
const RUNTIME_INSTANCE_ID = "app-1";

const ACTOR: TemplateTwinStaticAssetActor = {
  userId: "admin_synthetic",
  userEmail: "admin@synthetic.test",
  practiceId: "practice_synthetic",
  role: "ADMIN",
  rolloutToken: {
    practiceId: "practice_synthetic",
    globalGeneration: BigInt(1),
    practiceGeneration: BigInt(1),
    releaseId: RELEASE_ID,
    releaseIdentitySha256: RELEASE_IDENTITY_SHA256,
    runtimeManifestSha256: RUNTIME_MANIFEST_SHA256,
    runtimeInstanceId: RUNTIME_INSTANCE_ID,
  },
};

function localOcr(text = ""): LocalStaticAssetOcr {
  return {
    scan: vi.fn().mockResolvedValue({
      local: true,
      complete: true,
      engineVersion: "synthetic-local-ocr/1.0",
      text,
    }),
  };
}

function syntheticPng(
  options: {
    width?: number;
    height?: number;
    metadata?: string;
    trailing?: Uint8Array;
    animation?: boolean;
  } = {},
): Uint8Array {
  const width = options.width ?? 2;
  const height = options.height ?? 2;
  const ihdr = new Uint8Array(13);
  writeU32(ihdr, 0, width);
  writeU32(ihdr, 4, height);
  ihdr.set([8, 6, 0, 0, 0], 8);
  const scanlines = new Uint8Array((width * 4 + 1) * height);
  for (let row = 0; row < height; row += 1) {
    scanlines[row * (width * 4 + 1)] = 0;
    scanlines.fill(
      0x7f,
      row * (width * 4 + 1) + 1,
      (row + 1) * (width * 4 + 1),
    );
  }
  const chunks = [chunk("IHDR", ihdr)];
  if (options.metadata !== undefined) {
    chunks.push(
      chunk(
        "tEXt",
        new TextEncoder().encode(`Description\0${options.metadata}`),
      ),
    );
  }
  if (options.animation)
    chunks.push(chunk("acTL", Uint8Array.from([0, 0, 0, 1])));
  chunks.push(
    chunk("IDAT", deflateSync(scanlines)),
    chunk("IEND", new Uint8Array()),
  );
  if (options.trailing) chunks.push(options.trailing);
  return concat(
    Uint8Array.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    ...chunks,
  );
}

interface MemoryAsset {
  id: string;
  practiceId: string;
  createdById: string;
  sha256: string;
  mimeType: string;
  width: number;
  height: number;
  sizeBytes: number;
  scannerVersion: string;
  ocrEngineVersion: string;
  ocrTextSha256: string;
  metadataEvidenceSha256: string;
  privacyEvidenceSha256: string;
  privacyScanProvider: string;
  privacyScanModel: string;
  inspectionEvidenceSha256: string;
  inspectionEvidence: unknown;
  providerOwnershipEvidence: unknown;
  providerOwnershipSha256: string | null;
  currentStatus: string;
  currentDecisionVersion: number;
  createdAt: Date;
  updatedAt: Date;
}

interface MemoryDecision {
  id: string;
  assetId: string;
  version: number;
  decision: string;
  inspectionEvidenceSha256: string;
  auditEventKey: string;
  decidedById: string;
  decidedAt: Date;
}

interface MemoryReceipt {
  id: string;
  practiceId: string;
  reviewedById: string;
  tokenSha256: string;
  assetSha256: string;
  inspectionEvidenceSha256: string;
  scannerVersion: string;
  ocrEngineVersion: string;
  privacyEvidenceSha256: string;
  globalRolloutGeneration: bigint;
  practiceRolloutGeneration: bigint;
  createdAt: Date;
  expiresAt: Date;
  consumedAt: Date | null;
}

function memoryDb() {
  const assets: MemoryAsset[] = [];
  const decisions: MemoryDecision[] = [];
  const outbox: Array<Record<string, unknown>> = [];
  const receipts: MemoryReceipt[] = [];
  const queryRawCalls: unknown[] = [];
  const rollout = {
    globalEnabled: true,
    globalGeneration: BigInt(1),
    practiceEnabled: true,
    practiceGeneration: BigInt(1),
  };
  const authority = {
    id: ACTOR.userId,
    email: ACTOR.userEmail,
    practiceId: ACTOR.practiceId,
    role: "ADMIN",
    isActive: true,
    deactivatedAt: null as Date | null,
    suspendedAt: null as Date | null,
    softDeletedAt: null as Date | null,
    products: ["TRANSCRIBE_MD"],
    mfaEnabled: false,
    mfaSecret: null as string | null,
    mfaVerifiedAt: null as Date | null,
    practiceActive: true,
  };
  const faults = { auditOutbox: false };
  const db: TemplateTwinStaticAssetClaimDb = {
    templateTwinStaticAsset: {
      async findUnique(args) {
        const where = args.where as {
          practiceId_sha256: { practiceId: string; sha256: string };
        };
        const key = where.practiceId_sha256;
        const row = assets.find(
          (item) =>
            item.practiceId === key.practiceId && item.sha256 === key.sha256,
        );
        if (!row) return null;
        return {
          ...row,
          decisions: (args as { include?: { decisions?: unknown } }).include
            ?.decisions
            ? decisions
                .filter((item) => item.assetId === row.id)
                .sort((left, right) => right.version - left.version)
                .slice(0, 1)
            : undefined,
        } as never;
      },
      async findMany(args) {
        const where = args.where as {
          practiceId: string;
          currentStatus?: string;
          sha256?: { in: string[] };
        };
        return assets
          .filter(
            (item) =>
              item.practiceId === where.practiceId &&
              (where.currentStatus === undefined ||
                item.currentStatus === where.currentStatus) &&
              (where.sha256 === undefined ||
                where.sha256.in.includes(item.sha256)),
          )
          .map((item) => ({
            ...item,
            decisions: decisions
              .filter((decision) => decision.assetId === item.id)
              .sort((left, right) => right.version - left.version)
              .slice(0, 1),
          })) as never;
      },
      async create(args) {
        const row = {
          ...(args as { data: Omit<MemoryAsset, "createdAt" | "updatedAt"> })
            .data,
          createdAt: new Date(),
          updatedAt: new Date(),
        };
        assets.push(row);
        return row as never;
      },
    },
    templateTwinStaticAssetDecision: {
      async create(args) {
        const row = {
          ...(args as { data: Omit<MemoryDecision, "decidedAt"> }).data,
          decidedAt: new Date(),
        };
        const asset = assets.find((item) => item.id === row.assetId)!;
        if (row.version !== asset.currentDecisionVersion + 1) {
          throw new Error("TT_STATIC_ASSET_DECISION_CONFLICT");
        }
        const expectedAction = `TEMPLATE_TWIN_STATIC_ASSET_${row.decision}`;
        const audit = outbox.find(
          (item) => item.eventKey === row.auditEventKey,
        );
        if (
          !audit ||
          audit.action !== expectedAction ||
          audit.practiceId !== asset.practiceId ||
          audit.actorId !== row.decidedById ||
          audit.targetType !== "TemplateTwinStaticAsset" ||
          audit.targetId !== asset.id ||
          (audit.metadata as { decisionId?: string } | undefined)
            ?.decisionId !== row.id ||
          audit.status !== "PENDING"
        ) {
          throw new Error("TT_STATIC_ASSET_AUDIT_OUTBOX_INVALID");
        }
        decisions.push(row);
        asset.currentStatus = row.decision;
        asset.currentDecisionVersion = row.version;
        return row as never;
      },
    },
    templateTwinStaticAssetReviewReceipt: {
      async create(args) {
        const row = {
          ...(args as { data: Omit<MemoryReceipt, "consumedAt"> }).data,
          consumedAt: null,
        };
        receipts.push(row);
        return row;
      },
    },
    templateTwinAuditOutbox: {
      async create(args) {
        if (faults.auditOutbox) throw new Error("synthetic audit outage");
        outbox.push(args.data);
        return args.data;
      },
    },
    async $transaction(callback) {
      const assetSnapshot = assets.map((item) => ({ ...item }));
      const decisionSnapshot = decisions.map((item) => ({ ...item }));
      const receiptSnapshot = receipts.map((item) => ({ ...item }));
      const outboxSnapshot = outbox.map((item) => ({ ...item }));
      try {
        return await callback(db);
      } catch (error) {
        assets.splice(0, assets.length, ...assetSnapshot);
        decisions.splice(0, decisions.length, ...decisionSnapshot);
        receipts.splice(0, receipts.length, ...receiptSnapshot);
        outbox.splice(0, outbox.length, ...outboxSnapshot);
        throw error;
      }
    },
    async $queryRaw<T = unknown>(query: unknown): Promise<T> {
      queryRawCalls.push(query);
      const sql =
        (query as { strings?: readonly string[] }).strings?.join("?") ?? "";
      const values = (query as { values?: unknown[] }).values ?? [];
      if (sql.includes('SELECT CURRENT_TIMESTAMP AS "createdAt"')) {
        return [{ createdAt: new Date() }] as T;
      }
      if (sql.includes('FROM "template_twin_rollout_controls"')) {
        return [
          {
            enabled: rollout.globalEnabled,
            generation: rollout.globalGeneration,
            rollbackFenceState: "OPEN",
            rollbackOperationId: null,
          },
        ] as T;
      }
      if (sql.includes('FROM "practices"')) {
        return [
          {
            templateTwinEnabled: rollout.practiceEnabled,
            templateTwinRolloutGeneration: rollout.practiceGeneration,
            isActive: true,
          },
        ] as T;
      }
      if (sql.includes("template_twin_current_runtime_release")) {
        return [
          {
            id: RELEASE_ID,
            releaseIdentitySha256: RELEASE_IDENTITY_SHA256,
            runtimeManifestSha256: RUNTIME_MANIFEST_SHA256,
            runtimeReady: true,
          },
        ] as T;
      }
      if (sql.includes('FROM "template_twin_lineage_migration_progress"')) {
        return [{ phase: "CONTRACTED" }] as T;
      }
      const currentAuthority =
        authority.id === values[0] &&
        authority.practiceId === values[1] &&
        (authority.role === "ADMIN" || authority.role === "SUPER_ADMIN") &&
        authority.isActive &&
        authority.deactivatedAt === null &&
        authority.suspendedAt === null &&
        authority.softDeletedAt === null &&
        authority.products.includes("TRANSCRIBE_MD") &&
        (!authority.products.includes("SUPER_ADMIN") ||
          (authority.mfaEnabled &&
            typeof authority.mfaSecret === "string" &&
            authority.mfaSecret.trim().length > 0 &&
            authority.mfaVerifiedAt instanceof Date &&
            authority.mfaVerifiedAt.getTime() <= Date.now())) &&
        authority.practiceActive &&
        rollout.practiceEnabled;
      if (sql.includes("WITH current_admin AS")) {
        if (!currentAuthority) return [] as T;
        const scoped = assets
          .filter((asset) => asset.practiceId === authority.practiceId)
          .sort(
            (left, right) =>
              right.updatedAt.getTime() - left.updatedAt.getTime() ||
              left.sha256.localeCompare(right.sha256),
          )
          .slice(0, 100);
        if (scoped.length === 0) {
          return [
            {
              authorizedAdminId: authority.id,
              assetId: null,
              assetPracticeId: null,
              sha256: null,
              currentStatus: null,
              mimeType: null,
              width: null,
              height: null,
              sizeBytes: null,
              scannerVersion: null,
              ocrEngineVersion: null,
              currentDecisionVersion: null,
              createdAt: null,
              updatedAt: null,
            },
          ] as T;
        }
        return scoped.map((asset) => ({
          authorizedAdminId: authority.id,
          assetId: asset.id,
          assetPracticeId: asset.practiceId,
          sha256: asset.sha256,
          currentStatus: asset.currentStatus,
          mimeType: asset.mimeType,
          width: asset.width,
          height: asset.height,
          sizeBytes: asset.sizeBytes,
          scannerVersion: asset.scannerVersion,
          ocrEngineVersion: asset.ocrEngineVersion,
          currentDecisionVersion: asset.currentDecisionVersion,
          createdAt: asset.createdAt,
          updatedAt: asset.updatedAt,
        })) as T;
      }
      if (
        sql.includes('FROM "users" actor') &&
        sql.includes("FOR UPDATE OF actor")
      ) {
        return (
          currentAuthority
            ? [
                {
                  id: authority.id,
                  email: authority.email,
                  practiceId: authority.practiceId,
                  role: authority.role,
                },
              ]
            : []
        ) as T;
      }
      if (sql.includes('FROM "template_twin_static_asset_review_receipts"')) {
        const receipt = receipts.find((item) => item.id === values[0]);
        return (
          receipt
            ? [{ ...receipt, notExpired: receipt.expiresAt > new Date() }]
            : []
        ) as T;
      }
      if (sql.includes('UPDATE "template_twin_static_asset_review_receipts"')) {
        const receipt = receipts.find((item) => item.id === values[0]);
        if (!receipt || receipt.consumedAt || receipt.expiresAt <= new Date()) {
          return [] as T;
        }
        receipt.consumedAt = new Date();
        return [{ id: receipt.id }] as T;
      }
      if (
        sql.includes('FROM "template_twin_static_assets" asset') &&
        !sql.includes(" IN (")
      ) {
        return assets
          .filter(
            (asset) =>
              asset.practiceId === values[0] && asset.sha256 === values[1],
          )
          .map(({ id }) => ({ id })) as T;
      }
      const practiceId = values[0];
      const assetIds = new Set(values.slice(1));
      return assets
        .filter(
          (asset) => asset.practiceId === practiceId && assetIds.has(asset.id),
        )
        .sort((left, right) => left.id.localeCompare(right.id))
        .map(({ id }) => ({ id })) as T;
    },
  };
  return {
    db,
    assets,
    decisions,
    receipts,
    outbox,
    queryRawCalls,
    rollout,
    authority,
    faults,
  };
}

async function reviewedReceipt(
  state: ReturnType<typeof memoryDb>,
  bytes: Uint8Array,
  ocrText = "",
): Promise<string> {
  const review = await inspectTemplateTwinStaticAssetForReview({
    bytes,
    claimedMimeType: "image/png",
    actor: ACTOR,
    ocr: localOcr(ocrText),
    db: state.db,
  });
  return review.previewReviewReceipt;
}

beforeEach(() => {
  vi.stubEnv("TEMPLATE_TWIN_KILL_SWITCH", "false");
  aiMocks.complete.mockReset();
  aiMocks.complete.mockResolvedValue({ phiFields: [], anyUncertain: false });
  delimiterMocks.injectionAttemptDetected = false;
  vi.mocked(buildTemplateTwinProviderOwnershipReceipt).mockClear();
  vi.mocked(runTemplateTwinOwnedModelComplete).mockClear();
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("practice-scoped static image approval", () => {
  it("rejects a physician or cross-practice caller before image review", async () => {
    await expect(
      inspectTemplateTwinStaticAsset({
        bytes: syntheticPng(),
        claimedMimeType: "image/png",
        actor: { ...ACTOR, role: "DOCTOR" },
        ocr: localOcr(),
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_ADMIN_REQUIRED" });
    const state = memoryDb();
    await expect(
      revokeTemplateTwinStaticAsset({
        practiceId: "practice_other",
        sha256: "a".repeat(64),
        actor: ACTOR,
        reason: "Synthetic cross-practice revocation attempt.",
        db: state.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_NOT_FOUND" });
  });

  it("lists only PHI-safe metadata for the authorized practice", async () => {
    const state = memoryDb();
    const bytes = syntheticPng({ metadata: "Synthetic reusable mark" });
    const approved = await approveTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr("Synthetic Clinic"),
      previewReviewReceipt: await reviewedReceipt(
        state,
        bytes,
        "Synthetic Clinic",
      ),
      attestedReusableBlankAsset: true,
      reason: "Reusable synthetic practice mark.",
      db: state.db,
    });
    state.assets.push({
      ...state.assets[0]!,
      id: "asset_other_practice",
      practiceId: "practice_other_synthetic",
      sha256: "f".repeat(64),
    });

    await expect(
      listTemplateTwinStaticAssetsForPractice({ actor: ACTOR, db: state.db }),
    ).resolves.toEqual([
      expect.objectContaining({
        sha256: approved.sha256,
        status: "APPROVED",
        mimeType: "image/png",
        decisionVersion: 1,
      }),
    ]);
    const [listed] = await listTemplateTwinStaticAssetsForPractice({
      actor: ACTOR,
      db: state.db,
    });
    expect(listed).not.toHaveProperty("inspectionEvidence");
    expect(listed).not.toHaveProperty("ocrTextSha256");
    expect(listed).not.toHaveProperty("privacyScanModel");
    expect(listed).not.toHaveProperty("reason");
    const listSql = state.queryRawCalls
      .map(
        (query) =>
          (query as { strings?: readonly string[] }).strings?.join(" ") ?? "",
      )
      .find((sql) => sql.includes("WITH current_admin AS"));
    expect(listSql).toContain('actor."practiceId"');
    expect(listSql).toContain('actor."role" IN');
    expect(listSql).toContain('actor."deactivatedAt" IS NULL');
    expect(listSql).toContain('actor."suspendedAt" IS NULL');
    expect(listSql).toContain('actor."softDeletedAt" IS NULL');
    expect(listSql).toContain('ANY(actor."products")');
    expect(listSql).toContain("NOT ('SUPER_ADMIN'::\"Product\"");
    expect(listSql).toContain('actor."mfaEnabled" = true');
    expect(listSql).toContain("regexp_replace(");
    expect(listSql).toContain('actor."mfaSecret",');
    expect(listSql).toContain(POSTGRES_ECMASCRIPT_TRIM_WHITESPACE_CLASS);
    expect(listSql).toMatch(/\)\s*<> ''/u);
    expect(listSql).not.toContain('btrim(actor."mfaSecret")');
    expect(listSql).not.toContain("[[:space:]]");
    expect(listSql).toContain('actor."mfaVerifiedAt" <= CURRENT_TIMESTAMP');
    expect(listSql).toContain('practice."isActive" = true');
  });

  it("returns an authorized empty index instead of confusing it with denied authority", async () => {
    const state = memoryDb();

    await expect(
      listTemplateTwinStaticAssetsForPractice({ actor: ACTOR, db: state.db }),
    ).resolves.toEqual([]);
    expect(
      state.queryRawCalls.some((query) =>
        (
          (query as { strings?: readonly string[] }).strings?.join(" ") ?? ""
        ).includes("WITH current_admin AS"),
      ),
    ).toBe(true);
  });

  it("returns an authorized empty index when only another practice has assets", async () => {
    const state = memoryDb();
    state.assets.push({
      id: "asset_other_practice_only",
      practiceId: "practice_other_synthetic",
      createdById: "admin_other_synthetic",
      sha256: "e".repeat(64),
      mimeType: "image/png",
      width: 320,
      height: 80,
      sizeBytes: 2048,
      scannerVersion: "template-twin-static-png/1.0.0",
      ocrEngineVersion: "synthetic-local-ocr/1.0",
      ocrTextSha256: "1".repeat(64),
      metadataEvidenceSha256: "2".repeat(64),
      privacyEvidenceSha256: "3".repeat(64),
      privacyScanProvider: "anthropic",
      privacyScanModel: "synthetic-model",
      inspectionEvidenceSha256: "4".repeat(64),
      inspectionEvidence: {},
      providerOwnershipEvidence: {},
      providerOwnershipSha256: "5".repeat(64),
      currentStatus: "APPROVED",
      currentDecisionVersion: 1,
      createdAt: new Date("2026-07-20T00:00:00.000Z"),
      updatedAt: new Date("2026-07-20T00:00:00.000Z"),
    });

    await expect(
      listTemplateTwinStaticAssetsForPractice({ actor: ACTOR, db: state.db }),
    ).resolves.toEqual([]);
  });

  it.each([
    ["deactivation", { isActive: false }],
    ["lifecycle deactivation", { deactivatedAt: new Date() }],
    ["suspension", { suspendedAt: new Date() }],
    ["soft deletion", { softDeletedAt: new Date() }],
    ["demotion", { role: "STAFF" }],
    ["product loss", { products: [] }],
    ["platform MFA absence", { products: ["TRANSCRIBE_MD", "SUPER_ADMIN"] }],
    ["practice transfer", { practiceId: "practice_other_synthetic" }],
    ["practice deactivation", { practiceActive: false }],
  ])(
    "denies the asset list after current-admin %s",
    async (_label, mutation) => {
      const state = memoryDb();
      Object.assign(state.authority, mutation);

      await expect(
        listTemplateTwinStaticAssetsForPractice({ actor: ACTOR, db: state.db }),
      ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_ADMIN_REQUIRED" });
    },
  );

  it("admits a dual-entitled current admin list only with complete MFA", async () => {
    const state = memoryDb();
    state.authority.products = ["TRANSCRIBE_MD", "SUPER_ADMIN"];
    state.authority.mfaEnabled = true;
    state.authority.mfaSecret = "SYNTHETIC-SECRET";
    state.authority.mfaVerifiedAt = new Date("2020-01-01T00:00:00.000Z");

    await expect(
      listTemplateTwinStaticAssetsForPractice({ actor: ACTOR, db: state.db }),
    ).resolves.toEqual([]);
  });

  it.each(["\t", "\n", "\r\n\t", "\u00a0", "\u2007", "\u202f", "\ufeff"])(
    "rejects a dual-entitled asset list with a whitespace-only MFA secret %j",
    async (mfaSecret) => {
      const state = memoryDb();
      state.authority.products = ["TRANSCRIBE_MD", "SUPER_ADMIN"];
      state.authority.mfaEnabled = true;
      state.authority.mfaSecret = mfaSecret;
      state.authority.mfaVerifiedAt = new Date("2020-01-01T00:00:00.000Z");

      await expect(
        listTemplateTwinStaticAssetsForPractice({ actor: ACTOR, db: state.db }),
      ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_ADMIN_REQUIRED" });
    },
  );

  it("uses the same true non-whitespace SQL predicate in list and write fences", () => {
    const source = readFileSync(
      path.resolve(__dirname, "../static-assets.ts"),
      "utf8",
    );
    expect(
      source.match(/regexp_replace\(\s*actor\."mfaSecret"/gu),
    ).toHaveLength(2);
    expect(source).not.toContain('btrim(actor."mfaSecret")');
    expect(source).not.toContain("[[:space:]]");
  });

  it("validates bytes, bounded pixels, local OCR, metadata, and returns an ephemeral preview", async () => {
    const bytes = syntheticPng({ metadata: "Reusable synthetic mark" });
    const result = await inspectTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr("Synthetic clinic"),
    });
    expect(result.previewBytes).toEqual(bytes);
    expect(result.evidence).toMatchObject({
      mimeType: "image/png",
      width: 2,
      height: 2,
      sizeBytes: bytes.byteLength,
      metadataKinds: ["tEXt"],
    });
    expect(result.evidence.sha256).toMatch(/^[a-f0-9]{64}$/);
  });

  it("issues a durable single-use preview proof without persisting its bearer secret", async () => {
    const state = memoryDb();
    const bytes = syntheticPng();
    const review = await inspectTemplateTwinStaticAssetForReview({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      db: state.db,
    });
    const reviewProviderInput = vi
      .mocked(runTemplateTwinOwnedModelComplete)
      .mock.calls.at(-1)?.[0];
    expect(reviewProviderInput).toMatchObject({
      operation: "STATIC_ASSET_PRIVACY_SCAN",
      operationInstance: "primary",
    });
    expect(reviewProviderInput?.args.user).toMatch(
      /^Locally extracted static-image evidence:\n<transcript_[a-f0-9]{64}>/u,
    );
    expect(review.previewReviewReceipt).toMatch(
      /^[0-9a-f-]{36}\.[A-Za-z0-9_-]{43}$/,
    );
    expect(state.receipts).toHaveLength(1);
    expect(state.receipts[0]).toMatchObject({
      practiceId: ACTOR.practiceId,
      reviewedById: ACTOR.userId,
      assetSha256: review.evidence.sha256,
      inspectionEvidenceSha256: canonicalSha256(review.evidence),
      scannerVersion: review.evidence.scannerVersion,
      ocrEngineVersion: review.evidence.ocrEngineVersion,
      privacyEvidenceSha256: review.evidence.privacyEvidenceSha256,
      globalRolloutGeneration: BigInt(1),
      practiceRolloutGeneration: BigInt(1),
      consumedAt: null,
    });
    expect(
      state.receipts[0]!.expiresAt.getTime() -
        state.receipts[0]!.createdAt.getTime(),
    ).toBe(15 * 60 * 1_000);
    expect(
      state.queryRawCalls.some((query) =>
        (
          (query as { strings?: readonly string[] }).strings?.join(" ") ?? ""
        ).includes('SELECT CURRENT_TIMESTAMP AS "createdAt"'),
      ),
    ).toBe(true);
    expect(state.receipts[0]?.tokenSha256).toBe(
      createHash("sha256")
        .update(review.previewReviewReceipt, "utf8")
        .digest("hex"),
    );
    expect(
      Object.values(state.receipts[0]!).map(String).join("|"),
    ).not.toContain(review.previewReviewReceipt);
  });

  it("binds review and decision receipts to the database-enforced primary operation instance", async () => {
    const state = memoryDb();
    const bytes = syntheticPng();
    const review = await inspectTemplateTwinStaticAssetForReview({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      db: state.db,
    });
    const reviewProviderInput = vi
      .mocked(runTemplateTwinOwnedModelComplete)
      .mock.calls.at(-1)?.[0];
    expect(buildTemplateTwinProviderOwnershipReceipt).toHaveBeenLastCalledWith(
      expect.objectContaining({
        expectedExecutionPlan: [
          {
            operation: "STATIC_ASSET_PRIVACY_SCAN",
            operationInstance: "primary",
            disposition: "EXECUTED",
          },
        ],
      }),
    );

    await approveTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      previewReviewReceipt: review.previewReviewReceipt,
      attestedReusableBlankAsset: true,
      reason: "Reusable synthetic practice mark.",
      db: state.db,
    });
    const decisionProviderInput = vi
      .mocked(runTemplateTwinOwnedModelComplete)
      .mock.calls.at(-1)?.[0];
    expect(decisionProviderInput?.args.user).toBe(
      reviewProviderInput?.args.user,
    );
    expect(buildTemplateTwinProviderOwnershipReceipt).toHaveBeenLastCalledWith(
      expect.objectContaining({
        expectedExecutionPlan: [
          {
            operation: "STATIC_ASSET_PRIVACY_SCAN",
            operationInstance: "primary",
            disposition: "EXECUTED",
          },
        ],
      }),
    );
  });

  it("retains delimiter-attempt rejection before static-asset provider egress", async () => {
    delimiterMocks.injectionAttemptDetected = true;

    await expect(
      inspectTemplateTwinStaticAsset({
        bytes: syntheticPng(),
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_PRIVACY_REJECTED" });
    expect(runTemplateTwinOwnedModelComplete).not.toHaveBeenCalled();
    expect(aiMocks.complete).not.toHaveBeenCalled();
  });

  it("fails preview and decision writes closed after current admin authority changes", async () => {
    const bytes = syntheticPng();

    const whitespaceMfaPreview = memoryDb();
    whitespaceMfaPreview.authority.products = ["TRANSCRIBE_MD", "SUPER_ADMIN"];
    whitespaceMfaPreview.authority.mfaEnabled = true;
    whitespaceMfaPreview.authority.mfaSecret = "\ufeff";
    whitespaceMfaPreview.authority.mfaVerifiedAt = new Date(
      "2020-01-01T00:00:00.000Z",
    );
    await expect(
      inspectTemplateTwinStaticAssetForReview({
        bytes,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
        db: whitespaceMfaPreview.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_ADMIN_REQUIRED" });
    expect(whitespaceMfaPreview.receipts).toHaveLength(0);
    expect(whitespaceMfaPreview.outbox).toHaveLength(0);

    const suspendedPreview = memoryDb();
    suspendedPreview.authority.suspendedAt = new Date();
    await expect(
      inspectTemplateTwinStaticAssetForReview({
        bytes,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
        db: suspendedPreview.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_ADMIN_REQUIRED" });
    expect(suspendedPreview.receipts).toHaveLength(0);
    expect(suspendedPreview.outbox).toHaveLength(0);

    const demotedApproval = memoryDb();
    const approvalReceipt = await reviewedReceipt(demotedApproval, bytes);
    demotedApproval.authority.role = "STAFF";
    await expect(
      approveTemplateTwinStaticAsset({
        bytes,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
        previewReviewReceipt: approvalReceipt,
        attestedReusableBlankAsset: true,
        reason: "Reusable synthetic practice mark.",
        db: demotedApproval.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_ADMIN_REQUIRED" });
    expect(demotedApproval.receipts[0]?.consumedAt).toBeNull();
    expect(demotedApproval.assets).toHaveLength(0);
    expect(demotedApproval.decisions).toHaveLength(0);
    expect(demotedApproval.outbox).toHaveLength(0);

    const productRevokedRejection = memoryDb();
    productRevokedRejection.authority.products = [];
    await expect(
      rejectTemplateTwinStaticAsset({
        bytes,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
        reason: "Reject this synthetic reusable practice mark.",
        db: productRevokedRejection.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_ADMIN_REQUIRED" });
    expect(productRevokedRejection.assets).toHaveLength(0);
    expect(productRevokedRejection.decisions).toHaveLength(0);
    expect(productRevokedRejection.outbox).toHaveLength(0);

    const transferredRevocation = memoryDb();
    const approved = await approveTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      previewReviewReceipt: await reviewedReceipt(transferredRevocation, bytes),
      attestedReusableBlankAsset: true,
      reason: "Reusable synthetic practice mark.",
      db: transferredRevocation.db,
    });
    transferredRevocation.authority.practiceId = "practice_other_synthetic";
    await expect(
      revokeTemplateTwinStaticAsset({
        practiceId: ACTOR.practiceId,
        sha256: approved.sha256,
        actor: ACTOR,
        reason: "Revoke the transferred synthetic practice mark.",
        db: transferredRevocation.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_ADMIN_REQUIRED" });
    expect(transferredRevocation.assets[0]?.currentStatus).toBe("APPROVED");
    expect(transferredRevocation.decisions).toHaveLength(1);
    expect(transferredRevocation.outbox).toHaveLength(1);
  });

  it("rejects forged, cross-user, changed-byte, and replayed preview proofs", async () => {
    const bytes = syntheticPng();

    const forgedState = memoryDb();
    await expect(
      approveTemplateTwinStaticAsset({
        bytes,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
        previewReviewReceipt: "forged",
        attestedReusableBlankAsset: true,
        reason: "Reusable synthetic practice mark.",
        db: forgedState.db,
      }),
    ).rejects.toMatchObject({
      code: "TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID",
    });
    expect(forgedState.decisions).toHaveLength(0);

    const crossUserState = memoryDb();
    const crossUserReceipt = await reviewedReceipt(crossUserState, bytes);
    await expect(
      approveTemplateTwinStaticAsset({
        bytes,
        claimedMimeType: "image/png",
        actor: { ...ACTOR, userId: "admin_other_synthetic" },
        ocr: localOcr(),
        previewReviewReceipt: crossUserReceipt,
        attestedReusableBlankAsset: true,
        reason: "Reusable synthetic practice mark.",
        db: crossUserState.db,
      }),
    ).rejects.toMatchObject({
      code: "TT_STATIC_ASSET_ADMIN_REQUIRED",
    });

    const changedState = memoryDb();
    const changedReceipt = await reviewedReceipt(changedState, bytes);
    const changedBytes = syntheticPng({ metadata: "Changed synthetic mark" });
    await expect(
      approveTemplateTwinStaticAsset({
        bytes: changedBytes,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
        previewReviewReceipt: changedReceipt,
        expectedSha256: createHash("sha256").update(changedBytes).digest("hex"),
        attestedReusableBlankAsset: true,
        reason: "Reusable synthetic practice mark.",
        db: changedState.db,
      }),
    ).rejects.toMatchObject({
      code: "TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID",
    });

    const replayState = memoryDb();
    const receipt = await reviewedReceipt(replayState, bytes);
    await approveTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      previewReviewReceipt: receipt,
      attestedReusableBlankAsset: true,
      reason: "Reusable synthetic practice mark.",
      db: replayState.db,
    });
    await expect(
      approveTemplateTwinStaticAsset({
        bytes,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
        previewReviewReceipt: receipt,
        attestedReusableBlankAsset: true,
        reason: "Reusable synthetic practice mark.",
        db: replayState.db,
      }),
    ).rejects.toMatchObject({
      code: "TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID",
    });
    expect(replayState.decisions).toHaveLength(1);
  });

  it("records and audits a repeated approval instead of consuming proof silently", async () => {
    const state = memoryDb();
    const bytes = syntheticPng();
    const firstReceipt = await reviewedReceipt(state, bytes);
    const first = await approveTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      previewReviewReceipt: firstReceipt,
      attestedReusableBlankAsset: true,
      reason: "Initial synthetic practice approval.",
      db: state.db,
    });
    const secondReceipt = await reviewedReceipt(state, bytes);
    const second = await approveTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      previewReviewReceipt: secondReceipt,
      attestedReusableBlankAsset: true,
      reason: "Repeated synthetic approval after a fresh review.",
      db: state.db,
    });
    expect(first.decisionVersion).toBe(1);
    expect(second).toMatchObject({
      assetId: first.assetId,
      decisionVersion: 2,
    });
    expect(state.decisions.map((item) => item.decision)).toEqual([
      "APPROVED",
      "APPROVED",
    ]);
    expect(state.receipts.every((item) => item.consumedAt !== null)).toBe(true);
    expect(state.outbox.map((item) => item.action)).toEqual([
      "TEMPLATE_TWIN_STATIC_ASSET_APPROVED",
      "TEMPLATE_TWIN_STATIC_ASSET_APPROVED",
    ]);
  });

  it.each([
    ["global disable", { globalEnabled: false }],
    ["global generation change", { globalGeneration: BigInt(2) }],
    ["practice disable", { practiceEnabled: false }],
    ["practice generation change", { practiceGeneration: BigInt(2) }],
  ])(
    "rejects approval after %s and leaves the receipt unconsumed",
    async (_label, mutation) => {
      const state = memoryDb();
      const bytes = syntheticPng();
      const receipt = await reviewedReceipt(state, bytes);
      Object.assign(state.rollout, mutation);
      await expect(
        approveTemplateTwinStaticAsset({
          bytes,
          claimedMimeType: "image/png",
          actor: ACTOR,
          ocr: localOcr(),
          previewReviewReceipt: receipt,
          attestedReusableBlankAsset: true,
          reason: "Reusable synthetic practice mark.",
          db: state.db,
        }),
      ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_ROLLOUT_STALE" });
      expect(state.receipts[0]?.consumedAt).toBeNull();
      expect(state.assets).toHaveLength(0);
      expect(state.decisions).toHaveLength(0);
      expect(state.outbox).toHaveLength(0);
    },
  );

  it("rolls back receipt consumption and clinical state when durable audit enqueue fails", async () => {
    const state = memoryDb();
    const bytes = syntheticPng();
    const receipt = await reviewedReceipt(state, bytes);
    state.faults.auditOutbox = true;
    await expect(
      approveTemplateTwinStaticAsset({
        bytes,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
        previewReviewReceipt: receipt,
        attestedReusableBlankAsset: true,
        reason: "Reusable synthetic practice mark.",
        db: state.db,
      }),
    ).rejects.toThrow("synthetic audit outage");
    expect(state.receipts[0]?.consumedAt).toBeNull();
    expect(state.assets).toHaveLength(0);
    expect(state.decisions).toHaveLength(0);
    state.faults.auditOutbox = false;
    await expect(
      approveTemplateTwinStaticAsset({
        bytes,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
        previewReviewReceipt: receipt,
        attestedReusableBlankAsset: true,
        reason: "Reusable synthetic practice mark.",
        db: state.db,
      }),
    ).resolves.toMatchObject({ decisionVersion: 1 });
  });

  it("uses the global-practice-admin-receipt-asset lock order and revalidates reject and revoke", async () => {
    const state = memoryDb();
    const bytes = syntheticPng();
    const receipt = await reviewedReceipt(state, bytes);
    state.queryRawCalls.length = 0;
    await approveTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      previewReviewReceipt: receipt,
      attestedReusableBlankAsset: true,
      reason: "Reusable synthetic practice mark.",
      db: state.db,
    });
    const lockSql = state.queryRawCalls.map(
      (query) =>
        (query as { strings?: readonly string[] }).strings?.join(" ") ?? "",
    );
    expect(lockSql.slice(0, 8)).toEqual([
      expect.stringContaining("template_twin_rollout_controls"),
      expect.stringContaining('FROM "practices"'),
      expect.stringContaining("template_twin_current_runtime_release"),
      expect.stringContaining("template_twin_lineage_migration_progress"),
      expect.stringContaining('FROM "users" actor'),
      expect.stringContaining("template_twin_static_asset_review_receipts"),
      expect.stringContaining(
        'UPDATE "template_twin_static_asset_review_receipts"',
      ),
      expect.stringContaining('FROM "template_twin_static_assets" asset'),
    ]);

    state.rollout.practiceGeneration = BigInt(2);
    await expect(
      revokeTemplateTwinStaticAsset({
        practiceId: ACTOR.practiceId,
        sha256: state.assets[0]!.sha256,
        actor: ACTOR,
        reason: "The synthetic asset was retired after rollout changed.",
        db: state.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_ROLLOUT_STALE" });
    expect(state.assets[0]?.currentStatus).toBe("APPROVED");
    expect(state.decisions).toHaveLength(1);

    const rejectedState = memoryDb();
    rejectedState.rollout.globalEnabled = false;
    await expect(
      rejectTemplateTwinStaticAsset({
        bytes,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
        reason: "Synthetic rejection after global disable.",
        db: rejectedState.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_ROLLOUT_STALE" });
    expect(rejectedState.assets).toHaveLength(0);
    expect(rejectedState.decisions).toHaveLength(0);
    expect(rejectedState.outbox).toHaveLength(0);
  });

  it.each([
    ["SVG renamed as PNG", new TextEncoder().encode("<svg><script/></svg>")],
    [
      "PNG with executable tail",
      syntheticPng({ trailing: Uint8Array.from([0x4d, 0x5a]) }),
    ],
    ["animated PNG", syntheticPng({ animation: true })],
    ["oversized dimensions", syntheticPng({ width: 4097, height: 1 })],
  ])("rejects %s before approval", async (_name, bytes) => {
    await expect(
      inspectTemplateTwinStaticAsset({
        bytes,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
      }),
    ).rejects.toBeInstanceOf(TemplateTwinStaticAssetError);
  });

  it("rejects PHI in either OCR or metadata and durably audits a failed review", async () => {
    const state = memoryDb();
    await expect(
      inspectTemplateTwinStaticAssetForReview({
        bytes: syntheticPng(),
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr("patient.person@example.test"),
        db: state.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_PRIVACY_REJECTED" });
    await expect(
      inspectTemplateTwinStaticAsset({
        bytes: syntheticPng({ metadata: "patient.person@example.test" }),
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_PRIVACY_REJECTED" });
    expect(state.outbox).toHaveLength(1);
    expect(state.outbox[0]?.action).toBe("TEMPLATE_TWIN_STATIC_ASSET_REJECTED");
  });

  it("uses the shared independent privacy model for names that deterministic patterns cannot detect", async () => {
    aiMocks.complete.mockResolvedValueOnce({
      phiFields: ["ocrText"],
      anyUncertain: false,
    });
    await expect(
      inspectTemplateTwinStaticAsset({
        bytes: syntheticPng(),
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr("Synthetic Person Name"),
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_PRIVACY_REJECTED" });
    expect(aiMocks.complete).toHaveBeenCalledWith(
      expect.objectContaining({
        purpose: "tm_template_phi_scan",
        provider: "anthropic",
        temperature: 0,
      }),
    );
  });

  it("fails closed when the independent privacy scan is unavailable or uncertain", async () => {
    aiMocks.complete.mockRejectedValueOnce(new Error("synthetic outage"));
    await expect(
      inspectTemplateTwinStaticAsset({
        bytes: syntheticPng(),
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
      }),
    ).rejects.toMatchObject({
      code: "TT_STATIC_ASSET_PRIVACY_SCAN_UNAVAILABLE",
    });
    aiMocks.complete.mockResolvedValueOnce({
      phiFields: [],
      anyUncertain: true,
    });
    await expect(
      inspectTemplateTwinStaticAsset({
        bytes: syntheticPng(),
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_PRIVACY_REJECTED" });
  });

  it("requires a complete local OCR result and never accepts an external fallback", async () => {
    await expect(
      inspectTemplateTwinStaticAsset({
        bytes: syntheticPng(),
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: {
          scan: vi.fn().mockResolvedValue({
            local: false,
            complete: true,
            engineVersion: "external/1",
            text: "",
          }),
        } as never,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_OCR_UNAVAILABLE" });
  });

  it("records an immutable approval, scopes it to one practice, and audits use-ready evidence", async () => {
    const state = memoryDb();
    state.authority.email = "current-admin@synthetic.test";
    const bytes = syntheticPng();
    const binding = await approveTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      previewReviewReceipt: await reviewedReceipt(state, bytes),
      attestedReusableBlankAsset: true,
      reason: "Reusable synthetic practice mark.",
      expectedSha256: createHash("sha256").update(bytes).digest("hex"),
      db: state.db,
    });
    await expect(
      resolveApprovedTemplateTwinStaticAssets({
        practiceId: ACTOR.practiceId,
        sha256: [binding.sha256],
        db: state.db,
      }),
    ).resolves.toEqual([binding]);
    await expect(
      resolveApprovedTemplateTwinStaticAssets({
        practiceId: "practice_other",
        sha256: [binding.sha256],
        db: state.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_NOT_APPROVED" });
    expect(state.decisions).toHaveLength(1);
    expect(state.outbox.map((row) => row.action)).toEqual([
      "TEMPLATE_TWIN_STATIC_ASSET_APPROVED",
    ]);
    expect(state.outbox[0]?.actorEmailSnapshot).toBe(
      "current-admin@synthetic.test",
    );
  });

  it("records an explicit administrator rejection as an append-only decision", async () => {
    const state = memoryDb();
    const bytes = syntheticPng();
    await rejectTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      reason: "This synthetic mark is no longer approved branding.",
      db: state.db,
    });
    expect(state.decisions.map((row) => row.decision)).toEqual(["REJECTED"]);
    expect(state.outbox.map((row) => row.action)).toEqual([
      "TEMPLATE_TWIN_STATIC_ASSET_REJECTED",
    ]);
  });

  it("requires explicit revocation instead of relabeling an approved asset as rejected", async () => {
    const state = memoryDb();
    const bytes = syntheticPng();
    await approveTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      previewReviewReceipt: await reviewedReceipt(state, bytes),
      attestedReusableBlankAsset: true,
      reason: "Reusable synthetic practice mark.",
      db: state.db,
    });
    await expect(
      rejectTemplateTwinStaticAsset({
        bytes,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
        reason: "Use the explicit synthetic revocation workflow.",
        db: state.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_DECISION_CONFLICT" });
    expect(state.decisions.map((row) => row.decision)).toEqual(["APPROVED"]);
  });

  it("revocation prevents new source/certification bindings while preserving append-only history", async () => {
    const state = memoryDb();
    const bytes = syntheticPng();
    const approved = await approveTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      previewReviewReceipt: await reviewedReceipt(state, bytes),
      attestedReusableBlankAsset: true,
      reason: "Reusable synthetic practice mark.",
      db: state.db,
    });
    await revokeTemplateTwinStaticAsset({
      practiceId: ACTOR.practiceId,
      sha256: approved.sha256,
      actor: ACTOR,
      reason: "The practice retired this synthetic mark.",
      db: state.db,
    });
    await expect(
      assertTemplateTwinStaticAssetBindingsCurrent({
        practiceId: ACTOR.practiceId,
        bindings: [approved],
        db: state.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_NOT_APPROVED" });
    expect(state.decisions.map((row) => row.decision)).toEqual([
      "APPROVED",
      "REVOKED",
    ]);
    expect(state.outbox.map((row) => row.action)).toEqual([
      "TEMPLATE_TWIN_STATIC_ASSET_APPROVED",
      "TEMPLATE_TWIN_STATIC_ASSET_REVOKED",
    ]);
  });

  it("locks every certified asset in canonical identity order before revalidating approval", async () => {
    const state = memoryDb();
    const firstBytes = syntheticPng();
    const first = await approveTemplateTwinStaticAsset({
      bytes: firstBytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      previewReviewReceipt: await reviewedReceipt(state, firstBytes),
      attestedReusableBlankAsset: true,
      reason: "Reusable first synthetic practice mark.",
      db: state.db,
    });
    const secondBytes = syntheticPng({
      metadata: "Second synthetic practice mark",
    });
    const second = await approveTemplateTwinStaticAsset({
      bytes: secondBytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      previewReviewReceipt: await reviewedReceipt(state, secondBytes),
      attestedReusableBlankAsset: true,
      reason: "Reusable second synthetic practice mark.",
      db: state.db,
    });

    state.queryRawCalls.length = 0;
    await expect(
      lockAndAssertTemplateTwinStaticAssetBindingsCurrent({
        practiceId: ACTOR.practiceId,
        bindings: [second, first],
        db: state.db,
      }),
    ).resolves.toBeUndefined();

    expect(state.queryRawCalls).toHaveLength(1);
    const values = (state.queryRawCalls[0] as { values: unknown[] }).values;
    expect(values[0]).toBe(ACTOR.practiceId);
    expect(values.slice(1)).toEqual(
      [first.assetId, second.assetId].sort((left, right) =>
        left.localeCompare(right),
      ),
    );
  });

  it("rejects duplicate certified asset bindings before taking a database lock", async () => {
    const state = memoryDb();
    const bytes = syntheticPng();
    const binding = await approveTemplateTwinStaticAsset({
      bytes,
      claimedMimeType: "image/png",
      actor: ACTOR,
      ocr: localOcr(),
      previewReviewReceipt: await reviewedReceipt(state, bytes),
      attestedReusableBlankAsset: true,
      reason: "Reusable synthetic practice mark.",
      db: state.db,
    });

    state.queryRawCalls.length = 0;
    await expect(
      lockAndAssertTemplateTwinStaticAssetBindingsCurrent({
        practiceId: ACTOR.practiceId,
        bindings: [binding, binding],
        db: state.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_STALE_DIGEST" });
    expect(state.queryRawCalls).toHaveLength(0);
  });

  it("requires a new approval when reviewed bytes change", async () => {
    const state = memoryDb();
    const reviewed = syntheticPng();
    const changed = syntheticPng({ metadata: "Changed synthetic mark" });
    await expect(
      approveTemplateTwinStaticAsset({
        bytes: changed,
        claimedMimeType: "image/png",
        actor: ACTOR,
        ocr: localOcr(),
        previewReviewReceipt: await reviewedReceipt(state, changed),
        attestedReusableBlankAsset: true,
        reason: "Reusable synthetic practice mark.",
        expectedSha256: createHash("sha256").update(reviewed).digest("hex"),
        db: state.db,
      }),
    ).rejects.toMatchObject({ code: "TT_STATIC_ASSET_STALE_DIGEST" });
    expect(state.decisions).toHaveLength(0);
  });
});

function chunk(type: string, data: Uint8Array): Uint8Array {
  const typeBytes = new TextEncoder().encode(type);
  const output = new Uint8Array(12 + data.byteLength);
  writeU32(output, 0, data.byteLength);
  output.set(typeBytes, 4);
  output.set(data, 8);
  writeU32(output, 8 + data.byteLength, crc32(concat(typeBytes, data)));
  return output;
}

function concat(...values: Uint8Array[]): Uint8Array {
  const output = new Uint8Array(
    values.reduce((total, value) => total + value.byteLength, 0),
  );
  let offset = 0;
  for (const value of values) {
    output.set(value, offset);
    offset += value.byteLength;
  }
  return output;
}

function writeU32(bytes: Uint8Array, offset: number, value: number): void {
  bytes[offset] = (value >>> 24) & 0xff;
  bytes[offset + 1] = (value >>> 16) & 0xff;
  bytes[offset + 2] = (value >>> 8) & 0xff;
  bytes[offset + 3] = value & 0xff;
}

function crc32(bytes: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}
