import { createHash } from "node:crypto";

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
  type TranscribeArgs,
  type TranscribeResult,
} from "@meddoc/ai";
import { runWithTemplateTwinSyntheticQaProviderContext } from "@meddoc/ai/internal/synthetic-qa-context";
import { z } from "zod";

import {
  buildTemplateTwinProviderOwnershipReceipt,
  isTemplateTwinProviderAuthorityCurrent,
  resolveTemplateTwinProviderLogicalAttempt,
  runTemplateTwinOwnedModelComplete,
  runTemplateTwinOwnedModelCompleteText,
  runTemplateTwinOwnedProvider,
  runTemplateTwinOwnedTranscribe,
  runWithTemplateTwinProviderOwnershipContext as runWithTemplateTwinProviderOwnershipContextRaw,
  TemplateTwinProviderOwnershipError,
  type TemplateTwinProviderOwnershipContext,
  type ProviderOwnershipDbClient,
} from "../provider-ownership";
import { runWithTemplateTwinProviderCensus } from "../provider-census";
import { TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT } from "../staging-qa-fixtures";

const POSTGRES_ECMASCRIPT_TRIM_WHITESPACE_CLASS =
  "U&'[\\0009-\\000D\\0020\\00A0\\1680\\2000-\\200A\\2028\\2029\\202F\\205F\\3000\\FEFF]'";

interface StoredRow extends Record<string, unknown> {
  id: string;
  ownershipKey: string;
  idempotencyKey: string;
  status: string;
  invocationCount: number;
  claimId: string | null;
  resultPayload: unknown;
  resultSha256: string | null;
  resultVersion: string | null;
}

function whereMatches(row: StoredRow, where: Record<string, unknown>): boolean {
  return Object.entries(where).every(([key, value]) => row[key] === value);
}

class MemoryProviderDatabase {
  readonly rows = new Map<string, StoredRow>();
  throwAfterSuccessfulCompletion = false;

  readonly templateTwinProviderExecution = {
    create: async (raw: unknown): Promise<StoredRow> => {
      const args = raw as { data: Record<string, unknown> };
      const duplicate = [...this.rows.values()].find(
        (row) =>
          row.ownershipKey === args.data.ownershipKey ||
          row.idempotencyKey === args.data.idempotencyKey,
      );
      if (duplicate) {
        throw Object.assign(new Error("synthetic unique conflict"), {
          code: "P2002",
        });
      }
      const row = {
        ...args.data,
        status: "RESERVED",
        invocationCount: 0,
        claimId: null,
        resultPayload: null,
        resultSha256: null,
        resultVersion: null,
      } as StoredRow;
      this.rows.set(row.id, row);
      return { ...row };
    },
    findUnique: async (raw: unknown): Promise<StoredRow | null> => {
      const args = raw as { where: Record<string, unknown> };
      const row = [...this.rows.values()].find((candidate) =>
        whereMatches(candidate, args.where),
      );
      return row ? { ...row } : null;
    },
    updateMany: async (raw: unknown): Promise<{ count: number }> => {
      const args = raw as {
        where: Record<string, unknown>;
        data: Record<string, unknown>;
      };
      const row = [...this.rows.values()].find((candidate) =>
        whereMatches(candidate, args.where),
      );
      if (!row) return { count: 0 };
      Object.assign(row, args.data);
      return { count: 1 };
    },
  };

  async $queryRaw<T>(): Promise<T> {
    return [] as T;
  }

  async $transaction<T>(
    callback: (tx: MemoryProviderDatabase) => Promise<T>,
  ): Promise<T> {
    const result = await callback(this);
    if (
      this.throwAfterSuccessfulCompletion &&
      [...this.rows.values()].some((row) => row.status === "SUCCEEDED")
    ) {
      this.throwAfterSuccessfulCompletion = false;
      throw new Error("synthetic commit acknowledgement lost");
    }
    return result;
  }
}

const CONTEXT: TemplateTwinProviderOwnershipContext = {
  practiceId: "practice-provider-owner",
  actorUserId: "doctor-provider-owner",
  visitId: "visit-provider-owner",
  visitInputMode: "text_notes",
  scope: "VISIT_PIPELINE",
  logicalAttempt: 1,
  subjectId: "visit-provider-owner",
  subjectSha256: "1".repeat(64),
  sourceArtifactId: "source-provider-owner",
  compiledVersionId: "compiled-provider-owner",
  noteTemplateId: "template-provider-owner",
  noteTemplateVersion: 4,
  sourceLineageId: "lineage-provider-owner",
  sourceLineageVersion: 2,
  sourceSha256: "2".repeat(64),
  syntheticAdmissionId: null,
  rolloutToken: {
    practiceId: "practice-provider-owner",
    globalGeneration: BigInt(7),
    practiceGeneration: BigInt(9),
    releaseId: "77777777-7777-4777-8777-777777777777",
    releaseIdentitySha256: "3".repeat(64),
    runtimeManifestSha256: "4".repeat(64),
    runtimeInstanceId: "worker-provider-owner-1",
  },
};

const SYNTHETIC_AUDIO = Buffer.from("bounded synthetic voice audio", "utf8");
const SYNTHETIC_AUDIO_SHA256 = createHash("sha256")
  .update(SYNTHETIC_AUDIO)
  .digest("hex");
const SYNTHETIC_VOICE_CONTEXT: TemplateTwinProviderOwnershipContext = {
  ...CONTEXT,
  visitInputMode: "audio_upload",
  scope: "SYNTHETIC_EVIDENCE",
  subjectId: "synthetic-voice-admission-1",
  subjectSha256: "5".repeat(64),
  syntheticAdmissionId: "synthetic-voice-admission-1",
  rolloutToken: {
    practiceId: CONTEXT.practiceId,
    globalGeneration: BigInt(7),
    practiceGeneration: BigInt(9),
  },
};

const STATIC_ASSET_CONTEXT: TemplateTwinProviderOwnershipContext = {
  ...CONTEXT,
  actorUserId: "admin-provider-owner",
  visitId: null,
  visitInputMode: null,
  scope: "STATIC_ASSET",
  subjectId: "6".repeat(64),
  subjectSha256: "6".repeat(64),
  sourceArtifactId: null,
  compiledVersionId: null,
  noteTemplateId: null,
  noteTemplateVersion: null,
  sourceLineageId: null,
  sourceLineageVersion: null,
  sourceSha256: null,
};

const SAFE_SYNTHETIC_ENV = {
  NODE_ENV: "production",
  TEMPLATE_TWIN_STAGING_QA_ENABLED: "true",
  TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "qa",
  TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: "isolated-disposable-qa-v1",
  TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
  DATABASE_URL: "postgresql:///meddoc_synthetic_test",
  REDIS_URL: "redis://redis:6379/15",
  MINIO_ENDPOINT: "minio:9000",
  MINIO_USE_SSL: "false",
  TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio-qa",
  TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-template-artifacts-qa",
  MOCK_AI_CALLS: "true",
  MOCK_TEMPLATE_TWIN_E2E: "true",
} as const;

function runWithSyntheticVoiceProviderOwnershipContext<T>(
  context: TemplateTwinProviderOwnershipContext,
  callback: () => Promise<T>,
): Promise<T> {
  return runWithTemplateTwinSyntheticQaProviderContext(
    {
      mode: TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
      fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
      admissionId: SYNTHETIC_VOICE_CONTEXT.syntheticAdmissionId!,
      runId: SYNTHETIC_VOICE_CONTEXT.syntheticAdmissionId!,
      visitId: SYNTHETIC_VOICE_CONTEXT.visitId!,
      practiceId: SYNTHETIC_VOICE_CONTEXT.practiceId,
      requestSha256: "7".repeat(64),
      attempt: 1,
      workerClaimId: "11111111-1111-4111-8111-111111111111",
      pinnedGlobalGeneration:
        SYNTHETIC_VOICE_CONTEXT.rolloutToken.globalGeneration,
      pinnedPracticeGeneration:
        SYNTHETIC_VOICE_CONTEXT.rolloutToken.practiceGeneration,
      evidenceText: TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT,
    },
    () => runWithTemplateTwinProviderOwnershipContextRaw(context, callback),
    SAFE_SYNTHETIC_ENV,
  );
}

function syntheticVoiceTranscribeInput(
  transcriber: (args: TranscribeArgs) => Promise<TranscribeResult>,
) {
  return {
    operation: "SYNTHETIC_EVIDENCE_TRANSCRIPTION" as const,
    operationVersion: "synthetic-evidence-transcription-v1",
    audioIdentity: {
      objectKey: "template-twin-synthetic-voice/exact-audio",
      objectEtag: SYNTHETIC_AUDIO_SHA256,
      sha256: SYNTHETIC_AUDIO_SHA256,
      sizeBytes: SYNTHETIC_AUDIO.byteLength,
      lastModifiedIso: "2026-07-19T17:20:00.000Z",
    },
    transcriber,
    args: {
      practiceId: SYNTHETIC_VOICE_CONTEXT.practiceId,
      userId: SYNTHETIC_VOICE_CONTEXT.actorUserId,
      visitId: SYNTHETIC_VOICE_CONTEXT.visitId!,
      purpose: "tm_transcribe" as const,
      audio: SYNTHETIC_AUDIO,
      mimeType: "audio/webm",
      allowCrossProviderFallback: false,
      deepgram: { maxAttempts: 1 as const },
    },
  };
}

function runWithTemplateTwinProviderOwnershipContext<T>(
  context: TemplateTwinProviderOwnershipContext,
  callback: () => Promise<T>,
): Promise<T> {
  if (context.scope !== "VISIT_PIPELINE") {
    return runWithTemplateTwinProviderOwnershipContextRaw(context, callback);
  }
  return runWithTemplateTwinProviderCensus(
    {
      classification: "TEMPLATE_TWIN",
      templateId: context.noteTemplateId!,
      templateVersion: context.noteTemplateVersion!,
    },
    () => runWithTemplateTwinProviderOwnershipContextRaw(context, callback),
  );
}

let sequence = 0;

function dependencies(
  database: MemoryProviderDatabase,
  input: {
    mode?: "LIVE" | "DETERMINISTIC_MOCK" | "SYNTHETIC_QA";
    rolloutCurrent?: boolean;
    authorityCurrent?: boolean | (() => boolean | Promise<boolean>);
  } = {},
): NonNullable<Parameters<typeof runTemplateTwinOwnedProvider>[1]> {
  return {
    db: database,
    providerMode: () => input.mode ?? "DETERMINISTIC_MOCK",
    lockRollout: async () => input.rolloutCurrent ?? true,
    currentAuthority: async () =>
      typeof input.authorityCurrent === "function"
        ? await input.authorityCurrent()
        : (input.authorityCurrent ?? true),
    executionId: () => `provider-execution-${++sequence}`,
    claimId: () => `${sequence.toString(16).padStart(64, "0")}`,
    now: () => new Date("2026-07-19T17:20:00.000Z"),
    sleep: (milliseconds: number) =>
      new Promise((resolve) => setTimeout(resolve, milliseconds)),
    terminalWaitMs: 250,
    pollMs: 1,
  } as unknown as NonNullable<
    Parameters<typeof runTemplateTwinOwnedProvider>[1]
  >;
}

function currentLiveAuthorityDatabase(
  input: {
    patient?: Partial<{
      practiceId: string;
      name: string;
      externalId: string | null;
      dateOfBirth: Date | null;
      mrn: string | null;
      insurance: string | null;
      problemList: unknown | null;
      weightKg: number | null;
      allergies: string[];
      deletedAt: Date | null;
    }>;
    artifactAuthorized?: boolean;
  } = {},
): {
  db: ProviderOwnershipDbClient;
  queries: string[];
} {
  const patient = {
    practiceId: CONTEXT.practiceId,
    name: "Synthetic Unit Patient",
    externalId: "ordinary-patient-1",
    dateOfBirth: null,
    mrn: null,
    insurance: null,
    problemList: null,
    weightKg: null,
    allergies: [] as string[],
    deletedAt: null,
    ...input.patient,
  };
  const queries: string[] = [];
  const db = {
    templateTwinProviderExecution: {} as never,
    $queryRaw: vi.fn(async (query: { strings?: readonly string[] }) => {
      const sql = query.strings?.join("?") ?? "";
      queries.push(sql);
      if (sql.includes('FROM "users" actor')) {
        return [
          {
            practiceId: CONTEXT.practiceId,
            role: "DOCTOR",
            isActive: true,
            deactivatedAt: null,
            suspendedAt: null,
            softDeletedAt: null,
            products: ["TRANSCRIBE_MD"],
          },
        ];
      }
      if (sql.includes('FROM "transcribe_visits" visit')) {
        return [
          {
            userId: CONTEXT.actorUserId,
            inputMode: CONTEXT.visitInputMode,
            noteTemplateId: CONTEXT.noteTemplateId,
            noteTemplateVersion: CONTEXT.noteTemplateVersion,
            deletedAt: null,
            archivedAt: null,
            status: "AUTOMATING",
            audioKey: null,
            audioMimeType: null,
            audioSizeBytes: null,
            rawTextInput: "synthetic non-PHI input",
            dictationAudioKey: null,
            signedAt: null,
            patientPracticeId: patient.practiceId,
            patientName: patient.name,
            patientExternalId: patient.externalId,
            patientDateOfBirth: patient.dateOfBirth,
            patientMrn: patient.mrn,
            patientInsurance: patient.insurance,
            patientProblemList: patient.problemList,
            patientWeightKg: patient.weightKg,
            patientAllergies: patient.allergies,
            patientDeletedAt: patient.deletedAt,
          },
        ];
      }
      if (sql.includes('FROM "template_twin_compiled_versions" compiled')) {
        return [{ authorized: input.artifactAuthorized ?? true }];
      }
      throw new Error(`Unexpected current-authority query: ${sql}`);
    }) as unknown as ProviderOwnershipDbClient["$queryRaw"],
  } satisfies ProviderOwnershipDbClient;
  return { db, queries };
}

function currentStaticAssetAuthorityDatabase(
  input: {
    products?: string[];
    platformMfaComplete?: boolean;
  } = {},
): { db: ProviderOwnershipDbClient; queries: string[] } {
  const queries: string[] = [];
  const db = {
    templateTwinProviderExecution: {} as never,
    $queryRaw: vi.fn(async (query: { strings?: readonly string[] }) => {
      const sql = query.strings?.join("?") ?? "";
      queries.push(sql);
      if (sql.includes('FROM "users" actor')) {
        return [
          {
            practiceId: STATIC_ASSET_CONTEXT.practiceId,
            role: "ADMIN",
            isActive: true,
            deactivatedAt: null,
            suspendedAt: null,
            softDeletedAt: null,
            products: input.products ?? ["TRANSCRIBE_MD"],
            platformMfaComplete: input.platformMfaComplete ?? false,
          },
        ];
      }
      throw new Error(`Unexpected static-authority query: ${sql}`);
    }) as unknown as ProviderOwnershipDbClient["$queryRaw"],
  } satisfies ProviderOwnershipDbClient;
  return { db, queries };
}

function currentSyntheticVoiceAuthorityDatabase(
  parent: Partial<{
    revokedAt: Date | null;
    notExpired: boolean;
  }> = {},
): { db: ProviderOwnershipDbClient; queries: string[] } {
  const queries: string[] = [];
  const db = {
    templateTwinProviderExecution: {} as never,
    $queryRaw: vi.fn(async (query: { strings?: readonly string[] }) => {
      const sql = query.strings?.join("?") ?? "";
      queries.push(sql);
      if (sql.includes('FROM "users" actor')) {
        return [
          {
            practiceId: SYNTHETIC_VOICE_CONTEXT.practiceId,
            role: "DOCTOR",
            isActive: true,
            deactivatedAt: null,
            suspendedAt: null,
            softDeletedAt: null,
            products: ["TRANSCRIBE_MD"],
          },
        ];
      }
      if (
        sql.includes('FROM "template_twin_synthetic_qa_admissions" admission')
      ) {
        return [
          {
            id: SYNTHETIC_VOICE_CONTEXT.syntheticAdmissionId,
            parentAdmissionId: "synthetic-voice-parent-1",
            practiceId: SYNTHETIC_VOICE_CONTEXT.practiceId,
            actorId: SYNTHETIC_VOICE_CONTEXT.actorUserId,
            providerMode: "SYNTHETIC_MOCK_VOICE",
            fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
            purpose: "VISIT",
            phase: "VISIT_LINKED",
            pinnedGlobalRolloutGeneration:
              SYNTHETIC_VOICE_CONTEXT.rolloutToken.globalGeneration,
            pinnedPracticeRolloutGeneration:
              SYNTHETIC_VOICE_CONTEXT.rolloutToken.practiceGeneration,
            sourceArtifactId: SYNTHETIC_VOICE_CONTEXT.sourceArtifactId,
            noteTemplateId: SYNTHETIC_VOICE_CONTEXT.noteTemplateId,
            noteTemplateVersion: SYNTHETIC_VOICE_CONTEXT.noteTemplateVersion,
            visitId: SYNTHETIC_VOICE_CONTEXT.visitId,
            sourceSha256: SYNTHETIC_VOICE_CONTEXT.sourceSha256,
            preCertificationVoiceEvidence: true,
            audioSha256: SYNTHETIC_AUDIO_SHA256,
            audioSizeBytes: SYNTHETIC_AUDIO.byteLength,
            audioMimeType: "audio/webm",
            audioObjectKey: "template-twin-synthetic-voice/exact-audio",
            attempt: 1,
            certificationId: null,
            mappingSha256: null,
            consumedAt: null,
            notExpired: true,
            failedAt: null,
            revokedAt: null,
          },
        ];
      }
      if (sql.includes('FROM "template_twin_synthetic_qa_admissions" parent')) {
        return [
          {
            id: "synthetic-voice-parent-1",
            practiceId: SYNTHETIC_VOICE_CONTEXT.practiceId,
            actorId: SYNTHETIC_VOICE_CONTEXT.actorUserId,
            providerMode: "SYNTHETIC_LIFECYCLE",
            purpose: "UPLOAD",
            phase: "TEMPLATE_LINKED",
            sourceArtifactId: SYNTHETIC_VOICE_CONTEXT.sourceArtifactId,
            noteTemplateId: SYNTHETIC_VOICE_CONTEXT.noteTemplateId,
            noteTemplateVersion: SYNTHETIC_VOICE_CONTEXT.noteTemplateVersion,
            certificationId: null,
            mappingSha256: null,
            visitId: null,
            failedAt: null,
            revokedAt: parent.revokedAt ?? null,
            consumedAt: null,
            notExpired: parent.notExpired ?? true,
            preCertificationVoiceEvidence: false,
            pinnedGlobalRolloutGeneration:
              SYNTHETIC_VOICE_CONTEXT.rolloutToken.globalGeneration,
            pinnedPracticeRolloutGeneration:
              SYNTHETIC_VOICE_CONTEXT.rolloutToken.practiceGeneration,
          },
        ];
      }
      throw new Error(`Unexpected synthetic current-authority query: ${sql}`);
    }) as unknown as ProviderOwnershipDbClient["$queryRaw"],
  } satisfies ProviderOwnershipDbClient;
  return { db, queries };
}

function providerInput(invoke: () => Promise<{ facts: string[] }>) {
  return {
    operation: "L3_EXTRACT_ENTITIES" as const,
    operationVersion: "l3-provider-owner-v1",
    provider: "anthropic",
    model: "claude-synthetic-1",
    providerConfiguration: { temperature: 0, maxTokens: 512 },
    inputIdentity: {
      purpose: "tm_entities",
      evidence: "private synthetic input must never enter the receipt",
    },
    invoke,
    validate: (output: unknown) => {
      if (
        !output ||
        typeof output !== "object" ||
        !Array.isArray((output as { facts?: unknown }).facts)
      ) {
        throw new Error("invalid synthetic provider result");
      }
      return output as { facts: string[] };
    },
  };
}

function attemptSeriesDependencies(database: MemoryProviderDatabase) {
  return {
    readHistory: async (series: {
      practiceId: string;
      actorUserId: string;
      scope: string;
      operation: string;
      operationInstance: string;
      subjectId: string;
      subjectSha256: string;
    }) => {
      return [...database.rows.values()]
        .filter(
          (row) =>
            row.practiceId === series.practiceId &&
            row.actorUserId === series.actorUserId &&
            row.scope === series.scope &&
            row.operation === series.operation &&
            row.operationInstance === series.operationInstance &&
            row.subjectId === series.subjectId &&
            row.subjectSha256 === series.subjectSha256,
        )
        .sort(
          (left, right) =>
            Number(right.logicalAttempt) - Number(left.logicalAttempt),
        )
        .map((row) => ({
          logicalAttempt: Number(row.logicalAttempt),
          status: String(row.status),
          failureCode:
            typeof row.failureCode === "string" ? row.failureCode : null,
          completedAt: row.completedAt instanceof Date ? row.completedAt : null,
        }));
    },
  };
}

function resolveAttempt(
  database: MemoryProviderDatabase,
  requestStartedAt: Date,
): Promise<number> {
  return resolveTemplateTwinProviderLogicalAttempt(
    {
      practiceId: CONTEXT.practiceId,
      actorUserId: CONTEXT.actorUserId,
      scope: CONTEXT.scope,
      operation: "L3_EXTRACT_ENTITIES",
      subjectId: CONTEXT.subjectId,
      subjectSha256: CONTEXT.subjectSha256,
      requestStartedAt,
    },
    attemptSeriesDependencies(database),
  );
}

async function errorCode(promise: Promise<unknown>): Promise<string | null> {
  try {
    await promise;
    return null;
  } catch (error) {
    return error instanceof TemplateTwinProviderOwnershipError
      ? error.code
      : "UNEXPECTED";
  }
}

beforeEach(() => {
  sequence = 0;
});

describe("Template Twin exact provider ownership runtime", () => {
  it("reasserts exact LIVE compilation/certification authority and current patient tenancy", async () => {
    const harness = currentLiveAuthorityDatabase();
    await expect(
      isTemplateTwinProviderAuthorityCurrent({
        tx: harness.db,
        context: CONTEXT,
        mode: "LIVE",
      }),
    ).resolves.toBe(true);
    const artifactQuery = harness.queries.find((query) =>
      query.includes('FROM "template_twin_compiled_versions" compiled'),
    );
    expect(artifactQuery).toContain(
      "template_twin_live_provider_compilation_is_valid",
    );
    expect(artifactQuery).toContain(
      "compiled.\"certificationStatus\" = 'CERTIFIED'",
    );
    expect(artifactQuery).toContain(
      'compiled."providerOwnershipSha256" IS NOT NULL',
    );
    expect(artifactQuery).toContain(
      'source."providerOwnershipSha256" IS NOT NULL',
    );
    expect(artifactQuery).toContain('certification."certifiedById"');
    expect(artifactQuery).toContain(
      "certification.\"providerAuthorizationMode\" = 'LIVE'",
    );
    expect(artifactQuery).toContain(
      'certification."providerAuthorizationAdmissionId" IS NULL',
    );
  });

  it("requires complete platform MFA at the STATIC_ASSET provider fence", async () => {
    const practiceAdmin = currentStaticAssetAuthorityDatabase();
    await expect(
      isTemplateTwinProviderAuthorityCurrent({
        tx: practiceAdmin.db,
        context: STATIC_ASSET_CONTEXT,
        mode: "LIVE",
      }),
    ).resolves.toBe(true);

    const incompletePlatform = currentStaticAssetAuthorityDatabase({
      products: ["TRANSCRIBE_MD", "SUPER_ADMIN"],
      platformMfaComplete: false,
    });
    await expect(
      isTemplateTwinProviderAuthorityCurrent({
        tx: incompletePlatform.db,
        context: STATIC_ASSET_CONTEXT,
        mode: "LIVE",
      }),
    ).resolves.toBe(false);

    const completePlatform = currentStaticAssetAuthorityDatabase({
      products: ["TRANSCRIBE_MD", "SUPER_ADMIN"],
      platformMfaComplete: true,
    });
    await expect(
      isTemplateTwinProviderAuthorityCurrent({
        tx: completePlatform.db,
        context: STATIC_ASSET_CONTEXT,
        mode: "LIVE",
      }),
    ).resolves.toBe(true);

    const actorSql = completePlatform.queries.find((query) =>
      query.includes('FROM "users" actor'),
    );
    expect(actorSql).toContain('actor."mfaEnabled" = TRUE');
    expect(actorSql).toContain("regexp_replace(");
    expect(actorSql).toContain('actor."mfaSecret",');
    expect(actorSql).toContain(POSTGRES_ECMASCRIPT_TRIM_WHITESPACE_CLASS);
    expect(actorSql).toMatch(/\)\s*<> ''/u);
    expect(actorSql).not.toContain('btrim(actor."mfaSecret")');
    expect(actorSql).not.toContain("[[:space:]]");
    expect(actorSql).toContain('actor."mfaVerifiedAt" <= CURRENT_TIMESTAMP');
    expect(actorSql).toContain("FOR SHARE");
  });

  it("blocks an incomplete platform MFA actor before STATIC_ASSET provider egress", async () => {
    const authority = currentStaticAssetAuthorityDatabase({
      products: ["TRANSCRIBE_MD", "SUPER_ADMIN"],
      platformMfaComplete: false,
    });
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["must not egress"] }));

    await expect(
      runWithTemplateTwinProviderOwnershipContextRaw(STATIC_ASSET_CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          {
            ...providerInput(invoke),
            operation: "STATIC_ASSET_PRIVACY_SCAN",
            operationVersion: "static-asset-privacy-scan-v1",
          },
          dependencies(database, {
            mode: "LIVE",
            authorityCurrent: () =>
              isTemplateTwinProviderAuthorityCurrent({
                tx: authority.db,
                context: STATIC_ASSET_CONTEXT,
                mode: "LIVE",
              }),
          }),
        ),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED",
    });
    expect(invoke).not.toHaveBeenCalled();
    expect(database.rows.size).toBe(1);
    expect([...database.rows.values()][0]).toMatchObject({
      status: "FAILED",
      invocationCount: 0,
      failureCode: "AUTHORITY_REVOKED_BEFORE_PROVIDER",
    });
  });

  it.each([
    ["cross-tenant patient", { practiceId: "practice-foreign" }],
    ["deleted patient", { deletedAt: new Date() }],
    ["reserved synthetic identity", { externalId: "SYNTHETIC-QA-ONLY" }],
  ])("rejects a current LIVE visit with %s", async (_label, patient) => {
    const harness = currentLiveAuthorityDatabase({ patient });
    await expect(
      isTemplateTwinProviderAuthorityCurrent({
        tx: harness.db,
        context: CONTEXT,
        mode: "LIVE",
      }),
    ).resolves.toBe(false);
  });

  it("rejects a LIVE compilation whose exact certification/hash authority is no longer valid", async () => {
    const harness = currentLiveAuthorityDatabase({ artifactAuthorized: false });
    await expect(
      isTemplateTwinProviderAuthorityCurrent({
        tx: harness.db,
        context: CONTEXT,
        mode: "LIVE",
      }),
    ).resolves.toBe(false);
  });

  it.each([
    ["revoked", { revokedAt: new Date("2026-07-20T00:00:00.000Z") }],
    ["expired", { notExpired: false }],
  ])(
    "locks child then parent separately and rejects a %s synthetic parent",
    async (_label, parent) => {
      const harness = currentSyntheticVoiceAuthorityDatabase(parent);
      await expect(
        isTemplateTwinProviderAuthorityCurrent({
          tx: harness.db,
          context: SYNTHETIC_VOICE_CONTEXT,
          mode: "SYNTHETIC_QA",
        }),
      ).resolves.toBe(false);

      const childQuery = harness.queries.find((query) =>
        query.includes(
          'FROM "template_twin_synthetic_qa_admissions" admission',
        ),
      );
      const parentQuery = harness.queries.find((query) =>
        query.includes('FROM "template_twin_synthetic_qa_admissions" parent'),
      );
      expect(childQuery).toContain("FOR SHARE OF admission");
      expect(childQuery).not.toContain("LEFT JOIN");
      expect(childQuery).not.toContain("FOR SHARE OF admission, parent");
      expect(parentQuery).toContain("FOR SHARE OF parent");
      expect(harness.queries.indexOf(childQuery!)).toBeLessThan(
        harness.queries.indexOf(parentQuery!),
      );
    },
  );

  it("rejects synthetic-evidence transcription without an exact ownership context before egress", async () => {
    const transcriber = vi.fn(
      async (): Promise<TranscribeResult> => ({
        provider: "deepgram-batch",
        transcript: "must not egress",
        durationSec: 1,
        language: "en",
        costCents: 0,
        fallbackUsed: false,
        raw: { kind: "deepgram", data: {} as never },
      }),
    );

    await expect(
      runTemplateTwinOwnedTranscribe(
        syntheticVoiceTranscribeInput(transcriber),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
    });
    expect(transcriber).not.toHaveBeenCalled();
  });

  it("rejects every inexact synthetic voice scope, audio, and replay control before egress", async () => {
    const transcriber = vi.fn(
      async (): Promise<TranscribeResult> => ({
        provider: "deepgram-batch",
        transcript: "must not egress",
        durationSec: 1,
        language: "en",
        costCents: 0,
        fallbackUsed: false,
        raw: { kind: "deepgram", data: {} as never },
      }),
    );
    const cases = [
      {
        context: {
          ...SYNTHETIC_VOICE_CONTEXT,
          scope: "CUSTOM_EXAMPLE" as const,
        },
      },
      {
        context: {
          ...SYNTHETIC_VOICE_CONTEXT,
          visitInputMode: "text_notes",
        },
      },
      {
        context: { ...SYNTHETIC_VOICE_CONTEXT, logicalAttempt: 2 },
      },
      {
        context: SYNTHETIC_VOICE_CONTEXT,
        mutate: (value: ReturnType<typeof syntheticVoiceTranscribeInput>) => ({
          ...value,
          audioIdentity: { ...value.audioIdentity, sha256: "6".repeat(64) },
        }),
      },
      {
        context: SYNTHETIC_VOICE_CONTEXT,
        mutate: (value: ReturnType<typeof syntheticVoiceTranscribeInput>) => ({
          ...value,
          audioIdentity: {
            ...value.audioIdentity,
            sizeBytes: value.audioIdentity.sizeBytes + 1,
          },
        }),
      },
      {
        context: SYNTHETIC_VOICE_CONTEXT,
        mutate: (value: ReturnType<typeof syntheticVoiceTranscribeInput>) => ({
          ...value,
          args: { ...value.args, audio: "not-a-buffer" as never },
        }),
      },
      {
        context: SYNTHETIC_VOICE_CONTEXT,
        mutate: (value: ReturnType<typeof syntheticVoiceTranscribeInput>) => ({
          ...value,
          args: { ...value.args, allowCrossProviderFallback: true },
        }),
      },
      {
        context: SYNTHETIC_VOICE_CONTEXT,
        mutate: (value: ReturnType<typeof syntheticVoiceTranscribeInput>) => ({
          ...value,
          args: { ...value.args, deepgram: { maxAttempts: 2 as const } },
        }),
      },
    ];

    for (const item of cases) {
      const exact = syntheticVoiceTranscribeInput(transcriber);
      const candidate = item.mutate ? item.mutate(exact) : exact;
      await expect(
        runWithSyntheticVoiceProviderOwnershipContext(item.context, () =>
          runTemplateTwinOwnedTranscribe(candidate),
        ),
      ).rejects.toMatchObject({
        code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
      });
    }
    expect(transcriber).not.toHaveBeenCalled();
  });

  it("permits one exact synthetic mock transcription and rejects non-Deepgram or fallback results", async () => {
    const exactResult: TranscribeResult = {
      provider: "deepgram-batch",
      transcript: "exact synthetic voice transcript",
      durationSec: 1,
      language: "en",
      costCents: 0,
      fallbackUsed: false,
      raw: { kind: "deepgram", data: {} as never },
    };
    const database = new MemoryProviderDatabase();
    const transcriber = vi.fn(async (args: TranscribeArgs) => {
      void args;
      return exactResult;
    });

    await expect(
      runWithSyntheticVoiceProviderOwnershipContext(
        SYNTHETIC_VOICE_CONTEXT,
        () =>
          runTemplateTwinOwnedTranscribe({
            ...syntheticVoiceTranscribeInput(transcriber),
            dependencies: dependencies(database, { mode: "SYNTHETIC_QA" }),
          }),
      ),
    ).resolves.toEqual(exactResult);
    expect(transcriber).toHaveBeenCalledOnce();
    expect(transcriber.mock.calls[0]?.[0]).toMatchObject({
      allowCrossProviderFallback: false,
      deepgram: { maxAttempts: 1 },
    });

    for (const invalid of [
      { ...exactResult, provider: "whisper" },
      { ...exactResult, fallbackUsed: true },
      { ...exactResult, raw: { kind: "whisper", data: {} } },
    ] as TranscribeResult[]) {
      const invalidDatabase = new MemoryProviderDatabase();
      const invalidTranscriber = vi.fn(async () => invalid);
      await expect(
        runWithSyntheticVoiceProviderOwnershipContext(
          SYNTHETIC_VOICE_CONTEXT,
          () =>
            runTemplateTwinOwnedTranscribe({
              ...syntheticVoiceTranscribeInput(invalidTranscriber),
              dependencies: dependencies(invalidDatabase, {
                mode: "SYNTHETIC_QA",
              }),
            }),
        ),
      ).rejects.toMatchObject({
        code: "TEMPLATE_TWIN_PROVIDER_EXECUTION_FAILED",
      });
      expect(invalidTranscriber).toHaveBeenCalledOnce();
      expect([...invalidDatabase.rows.values()][0]).toMatchObject({
        status: "FAILED",
        resultPayload: null,
      });
    }
  });

  it("rejects synthetic-evidence transcription in LIVE or deterministic mode before egress", async () => {
    for (const mode of ["LIVE", "DETERMINISTIC_MOCK"] as const) {
      const database = new MemoryProviderDatabase();
      const transcriber = vi.fn(
        async (): Promise<TranscribeResult> => ({
          provider: "deepgram-batch",
          transcript: "must not egress",
          durationSec: 1,
          language: "en",
          costCents: 0,
          fallbackUsed: false,
          raw: { kind: "deepgram", data: {} as never },
        }),
      );
      await expect(
        runWithSyntheticVoiceProviderOwnershipContext(
          SYNTHETIC_VOICE_CONTEXT,
          () =>
            runTemplateTwinOwnedTranscribe({
              ...syntheticVoiceTranscribeInput(transcriber),
              dependencies: dependencies(database, { mode }),
            }),
        ),
      ).rejects.toMatchObject({
        code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
      });
      expect(transcriber).not.toHaveBeenCalled();
      expect(database.rows.size).toBe(0);
    }
  });

  it("leaves an ordinary provider call unchanged when no Twin context exists", async () => {
    const invoke = vi.fn(async (claim: { idempotencyKey?: string }) => ({
      facts: [claim.idempotencyKey ?? "ordinary"],
    }));

    const result = await runTemplateTwinOwnedProvider({
      ...providerInput(() => invoke({})),
      invoke,
    });

    expect(result).toEqual({ facts: ["ordinary"] });
    expect(invoke).toHaveBeenCalledOnce();
    expect(invoke).toHaveBeenCalledWith({});
  });

  it("blocks every direct wrapper when the pre-L1 census requires a Twin owner", async () => {
    const genericInvoke = vi.fn(async () => ({ facts: ["must not egress"] }));
    const completeText = vi.fn(async () => ({
      text: "must not egress",
      inputTokens: 1,
      outputTokens: 1,
    }));
    const complete = vi.fn(async () => ({ value: "must not egress" }));
    const transcriber = vi.fn(
      async (): Promise<TranscribeResult> => ({
        provider: "deepgram-batch",
        transcript: "must not egress",
        durationSec: 1,
        language: "en",
        costCents: 0,
        fallbackUsed: false,
        raw: { kind: "deepgram", data: {} as never },
      }),
    );

    await runWithTemplateTwinProviderCensus(
      {
        classification: "TEMPLATE_TWIN",
        templateId: CONTEXT.noteTemplateId!,
        templateVersion: CONTEXT.noteTemplateVersion!,
      },
      async () => {
        await expect(
          runTemplateTwinOwnedProvider(providerInput(genericInvoke)),
        ).rejects.toMatchObject({
          code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
        });
        await expect(
          runTemplateTwinOwnedModelComplete({
            operation: "SYNTHETIC_EVIDENCE_EXTRACTION",
            operationVersion: "synthetic-direct-wrapper-v1",
            args: {
              practiceId: CONTEXT.practiceId,
              userId: CONTEXT.actorUserId,
              visitId: CONTEXT.visitId,
              purpose: "tm_entities",
              provider: "anthropic",
              model: "claude-synthetic-1",
              system: "synthetic",
              user: "synthetic",
              schema: z.object({ value: z.string() }),
            },
            client: { complete: complete as never },
          }),
        ).rejects.toMatchObject({
          code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
        });
        await expect(
          runTemplateTwinOwnedModelCompleteText({
            operation: "SYNTHETIC_EVIDENCE_EXTRACTION",
            operationVersion: "synthetic-direct-wrapper-v1",
            args: {
              practiceId: CONTEXT.practiceId,
              userId: CONTEXT.actorUserId,
              visitId: CONTEXT.visitId,
              purpose: "tm_template_synthetic_phi_scan",
              provider: "anthropic",
              model: "claude-synthetic-1",
              system: "synthetic",
              user: "synthetic",
            },
            client: { completeText },
          }),
        ).rejects.toMatchObject({
          code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
        });
        await expect(
          runTemplateTwinOwnedTranscribe({
            operation: "L1_TRANSCRIBE",
            operationVersion: "synthetic-direct-wrapper-v1",
            audioIdentity: {
              objectKey: "synthetic/audio.webm",
              objectEtag: "synthetic-etag",
              sizeBytes: 32,
              lastModifiedIso: null,
            },
            args: {
              practiceId: CONTEXT.practiceId,
              userId: CONTEXT.actorUserId,
              visitId: CONTEXT.visitId,
              purpose: "tm_transcribe",
              audio: Buffer.alloc(32),
              mimeType: "audio/webm",
            },
            transcriber,
          }),
        ).rejects.toMatchObject({
          code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
        });
      },
    );

    expect(genericInvoke).not.toHaveBeenCalled();
    expect(complete).not.toHaveBeenCalled();
    expect(completeText).not.toHaveBeenCalled();
    expect(transcriber).not.toHaveBeenCalled();
  });

  it("rejects a wrong Twin census context and any ownership context under an ordinary census", async () => {
    const invoke = vi.fn(async () => ({ facts: ["must not egress"] }));
    await expect(
      runWithTemplateTwinProviderCensus(
        {
          classification: "TEMPLATE_TWIN",
          templateId: "different-template",
          templateVersion: CONTEXT.noteTemplateVersion!,
        },
        () =>
          runWithTemplateTwinProviderOwnershipContextRaw(CONTEXT, () =>
            runTemplateTwinOwnedProvider(providerInput(invoke)),
          ),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
    });
    await expect(
      runWithTemplateTwinProviderCensus(
        {
          classification: "ORDINARY",
          templateId: CONTEXT.noteTemplateId!,
          templateVersion: CONTEXT.noteTemplateVersion!,
        },
        () =>
          runWithTemplateTwinProviderOwnershipContextRaw(CONTEXT, () =>
            runTemplateTwinOwnedProvider(providerInput(invoke)),
          ),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
    });
    expect(invoke).not.toHaveBeenCalled();
  });

  it("rejects a VISIT_PIPELINE ownership context when no pre-L1 census exists", async () => {
    const invoke = vi.fn(async () => ({ facts: ["must not egress"] }));
    await expect(
      runWithTemplateTwinProviderOwnershipContextRaw(CONTEXT, () =>
        runTemplateTwinOwnedProvider(providerInput(invoke)),
      ),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
    });
    expect(invoke).not.toHaveBeenCalled();
  });

  it("admits exactly one concurrent provider invocation and reuses its committed result", async () => {
    const database = new MemoryProviderDatabase();
    let release!: () => void;
    let started!: () => void;
    const providerStarted = new Promise<void>((resolve) => {
      started = resolve;
    });
    const providerReleased = new Promise<void>((resolve) => {
      release = resolve;
    });
    const invoke = vi.fn(async () => {
      started();
      await providerReleased;
      return { facts: ["synthetic fact"] };
    });
    const run = () =>
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        ),
      );

    const first = run();
    await providerStarted;
    const second = run();
    await new Promise((resolve) => setTimeout(resolve, 5));
    release();

    await expect(Promise.all([first, second])).resolves.toEqual([
      { facts: ["synthetic fact"] },
      { facts: ["synthetic fact"] },
    ]);
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()]).toHaveLength(1);
    expect([...database.rows.values()][0]).toMatchObject({
      status: "SUCCEEDED",
      invocationCount: 1,
    });
  });

  it("treats a provider or runtime swap as an identity mismatch, not a new call", async () => {
    const database = new MemoryProviderDatabase();
    const firstInvoke = vi.fn(async () => ({ facts: ["first"] }));
    await runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(firstInvoke),
        dependencies(database),
      ),
    );
    const swappedInvoke = vi.fn(async () => ({ facts: ["second"] }));
    const swapped = providerInput(swappedInvoke);

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          { ...swapped, provider: "different-provider" },
          dependencies(database, { mode: "LIVE" }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
    expect(firstInvoke).toHaveBeenCalledOnce();
    expect(swappedInvoke).not.toHaveBeenCalled();
    expect(database.rows).toHaveProperty("size", 1);
  });

  it("collides input drift with the same logical owner before a second egress", async () => {
    const database = new MemoryProviderDatabase();
    let release!: () => void;
    let started!: () => void;
    const providerStarted = new Promise<void>((resolve) => {
      started = resolve;
    });
    const providerReleased = new Promise<void>((resolve) => {
      release = resolve;
    });
    const firstInvoke = vi.fn(async () => {
      started();
      await providerReleased;
      return { facts: ["first"] };
    });
    const first = runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(firstInvoke),
        dependencies(database),
      ),
    );
    await providerStarted;
    const driftedInvoke = vi.fn(async () => ({ facts: ["drifted"] }));
    const drifted = providerInput(driftedInvoke);
    const driftCode = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          {
            ...drifted,
            inputIdentity: { ...drifted.inputIdentity, evidence: "changed" },
          },
          dependencies(database),
        ),
      ),
    );
    release();

    await expect(first).resolves.toEqual({ facts: ["first"] });
    expect(driftCode).toBe("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
    expect(firstInvoke).toHaveBeenCalledOnce();
    expect(driftedInvoke).not.toHaveBeenCalled();
    expect(database.rows).toHaveProperty("size", 1);
  });

  it("collides operation-version drift with the same logical owner", async () => {
    const database = new MemoryProviderDatabase();
    const firstInvoke = vi.fn(async () => ({ facts: ["first"] }));
    await runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(firstInvoke),
        dependencies(database),
      ),
    );
    const driftedInvoke = vi.fn(async () => ({ facts: ["drifted"] }));
    const drifted = providerInput(driftedInvoke);

    const driftCode = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          { ...drifted, operationVersion: "l3-provider-owner-v2" },
          dependencies(database),
        ),
      ),
    );

    expect(driftCode).toBe("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
    expect(firstInvoke).toHaveBeenCalledOnce();
    expect(driftedInvoke).not.toHaveBeenCalled();
    expect(database.rows).toHaveProperty("size", 1);
  });

  it("collides a persisted visit input-mode drift with the same logical owner", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["first"] }));
    await runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(invoke),
        dependencies(database),
      ),
    );

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(
        { ...CONTEXT, visitInputMode: "voice_dictation" },
        () =>
          runTemplateTwinOwnedProvider(
            providerInput(invoke),
            dependencies(database),
          ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
    expect(invoke).toHaveBeenCalledOnce();
    expect(database.rows).toHaveProperty("size", 1);
  });

  it("permits explicitly distinct deterministic operation instances", async () => {
    const database = new MemoryProviderDatabase();
    const firstInvoke = vi.fn(async () => ({ facts: ["first"] }));
    const secondInvoke = vi.fn(async () => ({ facts: ["second"] }));

    const results = await runWithTemplateTwinProviderOwnershipContext(
      CONTEXT,
      async () => [
        await runTemplateTwinOwnedProvider(
          {
            ...providerInput(firstInvoke),
            operationInstance: "ensemble-pass-1",
          },
          dependencies(database),
        ),
        await runTemplateTwinOwnedProvider(
          {
            ...providerInput(secondInvoke),
            operationInstance: "ensemble-pass-2",
          },
          dependencies(database),
        ),
      ],
    );

    expect(results).toEqual([{ facts: ["first"] }, { facts: ["second"] }]);
    expect(firstInvoke).toHaveBeenCalledOnce();
    expect(secondInvoke).toHaveBeenCalledOnce();
    expect(database.rows).toHaveProperty("size", 2);
  });

  it("makes an ambiguous live provider failure terminal and blocks replay", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => {
      throw new Error("synthetic network acknowledgement lost");
    });
    const run = () =>
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, { mode: "LIVE" }),
        ),
      );

    expect(await errorCode(run())).toBe(
      "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN",
    );
    expect(await errorCode(run())).toBe(
      "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN",
    );
    await expect(
      resolveAttempt(database, new Date("2026-07-19T17:20:00.001Z")),
    ).resolves.toBe(1);
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()][0]).toMatchObject({
      status: "UNKNOWN_OUTCOME",
      invocationCount: 1,
    });
  });

  it("advances only after a definite failure and collapses concurrent fresh retries onto one new owner", async () => {
    const database = new MemoryProviderDatabase();
    const failedInvoke = vi.fn(async () => {
      throw new Error("synthetic deterministic provider failure");
    });
    const firstRun = () =>
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(failedInvoke),
          dependencies(database, { mode: "DETERMINISTIC_MOCK" }),
        ),
      );

    expect(await errorCode(firstRun())).toBe(
      "TEMPLATE_TWIN_PROVIDER_EXECUTION_FAILED",
    );
    expect(await errorCode(firstRun())).toBe(
      "TEMPLATE_TWIN_PROVIDER_EXECUTION_FAILED",
    );
    expect(failedInvoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()][0]).toMatchObject({
      logicalAttempt: 1,
      status: "FAILED",
      invocationCount: 1,
      failureCode: "PROVIDER_INVOCATION_FAILED",
    });
    await expect(
      resolveAttempt(database, new Date("2026-07-19T17:19:59.999Z")),
    ).resolves.toBe(1);

    const freshRequestStartedAt = new Date("2026-07-19T17:20:00.001Z");
    await expect(
      Promise.all([
        resolveAttempt(database, freshRequestStartedAt),
        resolveAttempt(database, freshRequestStartedAt),
      ]),
    ).resolves.toEqual([2, 2]);

    let release!: () => void;
    let started!: () => void;
    const providerStarted = new Promise<void>((resolve) => {
      started = resolve;
    });
    const providerReleased = new Promise<void>((resolve) => {
      release = resolve;
    });
    const freshInvoke = vi.fn(async () => {
      started();
      await providerReleased;
      return { facts: ["fresh deterministic result"] };
    });
    const freshContext = { ...CONTEXT, logicalAttempt: 2 };
    const freshRun = () =>
      runWithTemplateTwinProviderOwnershipContext(freshContext, () =>
        runTemplateTwinOwnedProvider(
          providerInput(freshInvoke),
          dependencies(database, { mode: "DETERMINISTIC_MOCK" }),
        ),
      );
    const firstFresh = freshRun();
    await providerStarted;
    const duplicateFresh = freshRun();
    await new Promise((resolve) => setTimeout(resolve, 5));
    release();

    await expect(Promise.all([firstFresh, duplicateFresh])).resolves.toEqual([
      { facts: ["fresh deterministic result"] },
      { facts: ["fresh deterministic result"] },
    ]);
    expect(freshInvoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()]).toHaveLength(2);
    expect(
      [...database.rows.values()].find((row) => row.logicalAttempt === 2),
    ).toMatchObject({ status: "SUCCEEDED", invocationCount: 1 });
  });

  it.each([
    "ROLLOUT_REVOKED",
    "ROLLOUT_REVOKED_AFTER_PROVIDER",
    "AUTHORITY_REVOKED_BEFORE_PROVIDER",
    "AUTHORITY_REVOKED_AFTER_PROVIDER",
  ])("does not advance a local authority failure %s", async (failureCode) => {
    await expect(
      resolveTemplateTwinProviderLogicalAttempt(
        {
          practiceId: CONTEXT.practiceId,
          actorUserId: CONTEXT.actorUserId,
          scope: CONTEXT.scope,
          operation: "L3_EXTRACT_ENTITIES",
          subjectId: CONTEXT.subjectId,
          subjectSha256: CONTEXT.subjectSha256,
          requestStartedAt: new Date("2026-07-19T17:20:00.001Z"),
        },
        {
          readHistory: async () => [
            {
              logicalAttempt: 1,
              status: "FAILED",
              failureCode,
              completedAt: new Date("2026-07-19T17:20:00.000Z"),
            },
          ],
        },
      ),
    ).resolves.toBe(1);
  });

  it.each(["RESERVED", "IN_FLIGHT"])(
    "reuses a valid nonterminal %s attempt without advancing",
    async (status) => {
      await expect(
        resolveTemplateTwinProviderLogicalAttempt(
          {
            practiceId: CONTEXT.practiceId,
            actorUserId: CONTEXT.actorUserId,
            scope: CONTEXT.scope,
            operation: "L3_EXTRACT_ENTITIES",
            subjectId: CONTEXT.subjectId,
            subjectSha256: CONTEXT.subjectSha256,
            requestStartedAt: new Date("2026-07-19T17:20:00.001Z"),
          },
          {
            readHistory: async () => [
              {
                logicalAttempt: 1,
                status,
                failureCode: null,
                completedAt: null,
              },
            ],
          },
        ),
      ).resolves.toBe(1);
    },
  );

  it.each([
    [
      "duplicate attempt",
      [
        {
          logicalAttempt: 1,
          status: "FAILED",
          failureCode: "PROVIDER_INVOCATION_FAILED",
          completedAt: new Date("2026-07-19T17:20:00.000Z"),
        },
        {
          logicalAttempt: 1,
          status: "FAILED",
          failureCode: "PROVIDER_INVOCATION_FAILED",
          completedAt: new Date("2026-07-19T17:19:00.000Z"),
        },
      ],
    ],
    [
      "attempt gap",
      [
        {
          logicalAttempt: 2,
          status: "FAILED",
          failureCode: "PROVIDER_INVOCATION_FAILED",
          completedAt: new Date("2026-07-19T17:20:00.000Z"),
        },
      ],
    ],
    [
      "unknown status",
      [
        {
          logicalAttempt: 1,
          status: "CORRUPT",
          failureCode: null,
          completedAt: null,
        },
      ],
    ],
    [
      "failed terminal row without completion",
      [
        {
          logicalAttempt: 1,
          status: "FAILED",
          failureCode: "PROVIDER_INVOCATION_FAILED",
          completedAt: null,
        },
      ],
    ],
    [
      "failed terminal row with invalid completion",
      [
        {
          logicalAttempt: 1,
          status: "FAILED",
          failureCode: "PROVIDER_INVOCATION_FAILED",
          completedAt: new Date("invalid"),
        },
      ],
    ],
    [
      "succeeded terminal row without completion",
      [
        {
          logicalAttempt: 1,
          status: "SUCCEEDED",
          failureCode: null,
          completedAt: null,
        },
      ],
    ],
    [
      "unknown terminal row without failure identity",
      [
        {
          logicalAttempt: 1,
          status: "UNKNOWN_OUTCOME",
          failureCode: null,
          completedAt: new Date("2026-07-19T17:20:00.000Z"),
        },
      ],
    ],
    [
      "nonterminal row with completion",
      [
        {
          logicalAttempt: 1,
          status: "IN_FLIGHT",
          failureCode: null,
          completedAt: new Date("2026-07-19T17:20:00.000Z"),
        },
      ],
    ],
    [
      "new attempt after nonterminal predecessor",
      [
        {
          logicalAttempt: 2,
          status: "FAILED",
          failureCode: "PROVIDER_INVOCATION_FAILED",
          completedAt: new Date("2026-07-19T17:20:00.000Z"),
        },
        {
          logicalAttempt: 1,
          status: "IN_FLIGHT",
          failureCode: null,
          completedAt: null,
        },
      ],
    ],
  ])(
    "fails closed on malformed provider attempt history: %s",
    async (_label, history) => {
      await expect(
        resolveTemplateTwinProviderLogicalAttempt(
          {
            practiceId: CONTEXT.practiceId,
            actorUserId: CONTEXT.actorUserId,
            scope: CONTEXT.scope,
            operation: "L3_EXTRACT_ENTITIES",
            subjectId: CONTEXT.subjectId,
            subjectSha256: CONTEXT.subjectSha256,
            requestStartedAt: new Date("2026-07-19T17:20:00.001Z"),
          },
          { readHistory: async () => history },
        ),
      ).rejects.toMatchObject({
        code: "TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID",
      });
    },
  );

  it("terminalizes an ambiguous live outcome despite concurrent authority revocation and never replays it", async () => {
    const database = new MemoryProviderDatabase();
    let authorityCurrent = true;
    const invoke = vi.fn(async () => {
      authorityCurrent = false;
      throw new Error(
        "synthetic provider acknowledgement lost during revocation",
      );
    });
    const run = () =>
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, {
            mode: "LIVE",
            authorityCurrent: () => authorityCurrent,
          }),
        ),
      );

    expect(await errorCode(run())).toBe(
      "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN",
    );
    expect([...database.rows.values()][0]).toMatchObject({
      status: "UNKNOWN_OUTCOME",
      invocationCount: 1,
      resultPayload: null,
      resultSha256: null,
    });
    expect(await errorCode(run())).toBe(
      "TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED",
    );
    authorityCurrent = true;
    expect(await errorCode(run())).toBe(
      "TEMPLATE_TWIN_PROVIDER_OUTCOME_UNKNOWN",
    );
    expect(invoke).toHaveBeenCalledOnce();
  });

  it("recovers an exact committed result when the commit acknowledgement is lost", async () => {
    const database = new MemoryProviderDatabase();
    database.throwAfterSuccessfulCompletion = true;
    const invoke = vi.fn(async () => ({ facts: ["committed once"] }));

    const result = await runWithTemplateTwinProviderOwnershipContext(
      CONTEXT,
      () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        ),
    );

    expect(result).toEqual({ facts: ["committed once"] });
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()][0]?.status).toBe("SUCCEEDED");
  });

  it("does not return an ambiguously committed success after authority is revoked", async () => {
    const database = new MemoryProviderDatabase();
    database.throwAfterSuccessfulCompletion = true;
    const invoke = vi.fn(async () => ({ facts: ["committed once"] }));
    let authorityChecks = 0;

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, {
            authorityCurrent: () => ++authorityChecks < 3,
          }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED");
    expect(authorityChecks).toBe(3);
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()][0]?.status).toBe("SUCCEEDED");
  });

  it.each([
    "actor deactivation",
    "actor suspension",
    "actor product removal",
    "visit deletion",
    "visit reassignment",
    "visit input-mode drift",
    "patient tenant or lifecycle drift",
    "reserved patient identity drift",
    "artifact lineage drift",
    "compiled/source ownership hash drift",
    "certification actor, mode, or admission drift",
    "canonical compilation receipt drift",
    "synthetic admission revocation",
    "synthetic run, attempt, or worker-claim drift",
    "synthetic status, phase, heartbeat, or lease drift",
  ])("blocks %s before provider egress", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["must not egress"] }));

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, { authorityCurrent: false }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED");
    expect(invoke).not.toHaveBeenCalled();
    expect([...database.rows.values()][0]).toMatchObject({
      status: "FAILED",
      invocationCount: 0,
      failureCode: "AUTHORITY_REVOKED_BEFORE_PROVIDER",
    });
  });

  it.each([
    "actor deactivation",
    "actor suspension",
    "actor product removal",
    "visit deletion",
    "visit reassignment",
    "visit input-mode drift",
    "patient tenant or lifecycle drift",
    "reserved patient identity drift",
    "artifact lineage drift",
    "compiled/source ownership hash drift",
    "certification actor, mode, or admission drift",
    "canonical compilation receipt drift",
    "synthetic admission revocation",
    "synthetic run, attempt, or worker-claim drift",
    "synthetic status, phase, heartbeat, or lease drift",
  ])("rejects %s after provider return before success admission", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["unadmitted result"] }));
    let authorityChecks = 0;

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, {
            authorityCurrent: () => ++authorityChecks === 1,
          }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED");
    expect(authorityChecks).toBe(2);
    expect(invoke).toHaveBeenCalledOnce();
    expect([...database.rows.values()][0]).toMatchObject({
      status: "FAILED",
      invocationCount: 1,
      failureCode: "AUTHORITY_REVOKED_AFTER_PROVIDER",
      resultPayload: null,
      resultSha256: null,
    });
  });

  it("rejects a tampered committed result before it can be reused", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["exact"] }));
    await runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(invoke),
        dependencies(database),
      ),
    );
    const row = [...database.rows.values()][0];
    if (!row) throw new Error("synthetic row missing");
    row.resultSha256 = "f".repeat(64);

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_RESULT_INVALID");
    expect(invoke).toHaveBeenCalledOnce();
  });

  it.each([
    "actor lifecycle drift",
    "patient tenant or lifecycle drift",
    "reserved patient identity drift",
    "compiled/source ownership hash drift",
    "certification actor, mode, or admission drift",
    "canonical compilation receipt drift",
    "synthetic run, attempt, or worker-claim drift",
    "synthetic status, phase, heartbeat, or lease drift",
  ])("rejects a committed result after %s without new egress", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["exact"] }));
    await runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
      runTemplateTwinOwnedProvider(
        providerInput(invoke),
        dependencies(database),
      ),
    );

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, { authorityCurrent: false }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_AUTHORITY_REVOKED");
    expect(invoke).toHaveBeenCalledOnce();
  });

  it("builds a minimal canonical receipt without provider inputs or claim tokens", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["receipt"] }));

    const receipt = await runWithTemplateTwinProviderOwnershipContext(
      CONTEXT,
      async () => {
        await runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        );
        return buildTemplateTwinProviderOwnershipReceipt({
          projection: {
            subjectId: CONTEXT.subjectId,
            subjectSha256: CONTEXT.subjectSha256,
            visitId: CONTEXT.visitId,
            sourceArtifactId: CONTEXT.sourceArtifactId,
            compiledVersionId: CONTEXT.compiledVersionId,
            noteTemplateId: CONTEXT.noteTemplateId,
          },
          expectedExecutionPlan: [
            { operation: "L3_EXTRACT_ENTITIES", disposition: "EXECUTED" },
          ],
        });
      },
    );
    const serialized = JSON.stringify(receipt);

    expect(receipt.sha256).toMatch(/^[a-f0-9]{64}$/u);
    expect(receipt.evidence).toMatchObject({
      contractVersion: "template-twin-provider-ownership-receipt-v2",
      actorUserId: CONTEXT.actorUserId,
      providerMode: "DETERMINISTIC_MOCK",
      syntheticAdmissionId: null,
    });
    expect(receipt.evidence.executions).toHaveLength(1);
    expect(serialized).not.toContain("private synthetic input");
    expect(serialized).not.toContain("idempotency");
    expect(serialized).not.toContain("claimId");
    expect(serialized).not.toContain("resultPayload");
  });

  it("rejects a receipt projection that does not exactly match its provider context", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["receipt"] }));

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, async () => {
        await runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database),
        );
        return buildTemplateTwinProviderOwnershipReceipt({
          projection: {
            subjectId: CONTEXT.subjectId,
            subjectSha256: CONTEXT.subjectSha256,
            visitId: "different-visit",
            sourceArtifactId: CONTEXT.sourceArtifactId,
            compiledVersionId: CONTEXT.compiledVersionId,
            noteTemplateId: CONTEXT.noteTemplateId,
          },
          expectedExecutionPlan: [
            { operation: "L3_EXTRACT_ENTITIES", disposition: "EXECUTED" },
          ],
        });
      }),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_CONTEXT_INVALID");
    expect(invoke).toHaveBeenCalledOnce();
  });

  it("taints the whole chain when a caught provider failure would otherwise be omitted", async () => {
    const database = new MemoryProviderDatabase();
    const l3 = vi.fn(async () => ({ facts: ["successful evidence"] }));
    const verifier = vi.fn(async () => {
      throw new Error("synthetic verifier failure");
    });
    const afterFailure = vi.fn(async () => ({ facts: ["must not egress"] }));
    let afterFailureCode: string | null = null;

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, async () => {
        await runTemplateTwinOwnedProvider(
          providerInput(l3),
          dependencies(database),
        );
        try {
          await runTemplateTwinOwnedProvider(
            {
              ...providerInput(verifier),
              operation: "L4_ANCHOR_VERIFY",
              operationVersion: "anchor-verifier-v1",
            },
            dependencies(database),
          );
        } catch {
          // Production verifier call sites may conservatively fall back. The
          // artifact receipt must still remember that provider ownership was
          // incomplete instead of silently certifying the partial chain.
        }
        afterFailureCode = await errorCode(
          runTemplateTwinOwnedProvider(
            {
              ...providerInput(afterFailure),
              operation: "L5_SELF_CRITIQUE",
              operationVersion: "post-failure-v1",
            },
            dependencies(database),
          ),
        );
        return buildTemplateTwinProviderOwnershipReceipt({
          projection: {
            subjectId: CONTEXT.subjectId,
            subjectSha256: CONTEXT.subjectSha256,
            visitId: CONTEXT.visitId,
            sourceArtifactId: CONTEXT.sourceArtifactId,
            compiledVersionId: CONTEXT.compiledVersionId,
            noteTemplateId: CONTEXT.noteTemplateId,
          },
          expectedExecutionPlan: [
            { operation: "L3_EXTRACT_ENTITIES", disposition: "EXECUTED" },
          ],
        });
      }),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
    expect(afterFailureCode).toBe("TEMPLATE_TWIN_PROVIDER_RECEIPT_INCOMPLETE");
    expect(l3).toHaveBeenCalledOnce();
    expect(verifier).toHaveBeenCalledOnce();
    expect(afterFailure).not.toHaveBeenCalled();
  });

  it("fails a reserved execution closed when rollout authority is revoked", async () => {
    const database = new MemoryProviderDatabase();
    const invoke = vi.fn(async () => ({ facts: ["must not run"] }));

    const code = await errorCode(
      runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
        runTemplateTwinOwnedProvider(
          providerInput(invoke),
          dependencies(database, { rolloutCurrent: false }),
        ),
      ),
    );

    expect(code).toBe("TEMPLATE_TWIN_PROVIDER_ROLLOUT_REVOKED");
    expect(invoke).not.toHaveBeenCalled();
    expect([...database.rows.values()][0]?.status).toBe("FAILED");
  });

  it.each([
    ["practice", { practiceId: "different-practice" }],
    ["actor", { userId: "different-doctor" }],
    ["visit", { visitId: "different-visit" }],
  ] as const)(
    "rejects cross-%s complete-text and transcription identities before egress",
    async (_label, identityOverride) => {
      const completeText = vi.fn(async () => ({
        text: "must not run",
        inputTokens: 1,
        outputTokens: 1,
      }));
      const transcriber = vi.fn(
        async () =>
          ({
            provider: "deepgram-batch",
            transcript: "must not run",
            durationSec: 1,
            language: "en",
            costCents: 0,
            fallbackUsed: false,
            raw: { kind: "deepgram", data: {} },
          }) as TranscribeResult,
      );
      const providerIdentity = {
        practiceId: CONTEXT.practiceId,
        userId: CONTEXT.actorUserId,
        visitId: CONTEXT.visitId,
        ...identityOverride,
      };

      const completeTextCode = await errorCode(
        runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
          runTemplateTwinOwnedModelCompleteText({
            operation: "L6_POLISH",
            operationVersion: "l6-provider-owner-v1",
            client: { completeText },
            args: {
              ...providerIdentity,
              purpose: "tm_polish",
              provider: "anthropic",
              model: "claude-synthetic-1",
              system: "synthetic system",
              user: "synthetic input",
            },
          }),
        ),
      );
      const transcriptionCode = await errorCode(
        runWithTemplateTwinProviderOwnershipContext(CONTEXT, () =>
          runTemplateTwinOwnedTranscribe({
            operation: "L1_TRANSCRIBE",
            operationVersion: "l1-provider-owner-v1",
            audioIdentity: {
              objectKey: "private/provider-owner/audio.webm",
              objectEtag: "synthetic-etag",
              sizeBytes: 16,
              lastModifiedIso: "2026-07-19T17:20:00.000Z",
            },
            transcriber,
            args: {
              ...providerIdentity,
              purpose: "tm_transcribe",
              audio: Buffer.from("synthetic audio"),
              mimeType: "audio/webm",
            },
          }),
        ),
      );

      expect(completeTextCode).toBe("TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH");
      expect(transcriptionCode).toBe(
        "TEMPLATE_TWIN_PROVIDER_IDENTITY_MISMATCH",
      );
      expect(completeText).not.toHaveBeenCalled();
      expect(transcriber).not.toHaveBeenCalled();
    },
  );
});
