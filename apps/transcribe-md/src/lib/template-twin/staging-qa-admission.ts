import { createHash } from "node:crypto";

import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  SyntheticQaProviderContextError,
  assertTemplateTwinSyntheticQaProviderEnvironment,
  getTemplateTwinSyntheticQaProviderContext,
  type SyntheticQaProviderEnvironment,
} from "@meddoc/ai";
import { runWithTemplateTwinSyntheticQaProviderContext } from "@meddoc/ai/internal/synthetic-qa-context";
import prisma from "@meddoc/db";
import { Prisma } from "@prisma/client";

import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";

import { enqueueTemplateTwinAudit } from "./audit-outbox";
import { canonicalSha256 } from "./canonical";
import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from "./staging-qa-fixture-contract";
import { templateTwinStagingQaRunRequestSha256 } from "./staging-qa-digest";
import {
  assertTemplateTwinStagingQaGate,
  isTemplateTwinStagingQaRequested,
} from "./staging-qa-gate";
import {
  lockTemplateTwinRolloutForFinalClaim,
  pinTemplateTwinRollout,
  type TemplateTwinRolloutToken,
} from "./rollout";

export const TEMPLATE_TWIN_STAGING_QA_ADMISSION_TTL_MS = 24 * 60 * 60 * 1000;

export const TEMPLATE_TWIN_STAGING_QA_ADMISSION_PHASES = [
  "ADMITTED",
  "SOURCE_VERIFIED",
  "TEMPLATE_LINKED",
  "CERTIFIED",
  "VISIT_LINKED",
  "PROCESSING",
  "REVIEW_READY",
  "SIGNED",
  "FAILED",
  "REVOKED",
] as const;

export type TemplateTwinStagingQaAdmissionPhase =
  (typeof TEMPLATE_TWIN_STAGING_QA_ADMISSION_PHASES)[number];

export type TemplateTwinStagingQaAdmissionProviderMode =
  | "SYNTHETIC_LIFECYCLE"
  | "SYNTHETIC_TYPED"
  | "SYNTHETIC_MOCK_VOICE";

export type TemplateTwinStagingQaAdmissionCode =
  | "TEMPLATE_TWIN_STAGING_QA_ADMISSION_NOT_FOUND"
  | "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE"
  | "TEMPLATE_TWIN_STAGING_QA_ADMISSION_PHASE_INVALID"
  | "TEMPLATE_TWIN_STAGING_QA_ADMISSION_MISMATCH"
  | "TEMPLATE_TWIN_STAGING_QA_ADMISSION_FAILED";

export class TemplateTwinStagingQaAdmissionError extends Error {
  constructor(
    readonly code: TemplateTwinStagingQaAdmissionCode,
    message = "Template Twin synthetic QA admission is unavailable.",
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "TemplateTwinStagingQaAdmissionError";
  }
}

export interface TemplateTwinStagingQaAdmissionActor {
  readonly userId: string;
  readonly userEmail?: string | null;
  readonly practiceId: string;
  readonly rolloutToken: TemplateTwinRolloutToken;
}

export interface TemplateTwinStagingQaAdmissionRow {
  readonly id: string;
  readonly practiceId: string;
  readonly actorId: string;
  readonly parentAdmissionId: string | null;
  readonly sourceSha256: string;
  readonly sourceSizeBytes: number;
  readonly fixtureVersion: string;
  readonly providerMode: string;
  readonly purpose: string;
  readonly phase: string;
  readonly requestSha256: string;
  readonly payloadSha256: string | null;
  readonly pinnedGlobalRolloutGeneration: bigint;
  readonly pinnedPracticeRolloutGeneration: bigint;
  readonly sourceArtifactId: string | null;
  readonly noteTemplateId: string | null;
  readonly noteTemplateVersion: number | null;
  readonly certificationId: string | null;
  readonly mappingSha256: string | null;
  readonly visitId: string | null;
  readonly attempt: number;
  readonly expiresAt: Date;
  readonly failedAt: Date | null;
  readonly revokedAt: Date | null;
  readonly consumedAt: Date | null;
}

export const TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT = {
  id: true,
  practiceId: true,
  actorId: true,
  parentAdmissionId: true,
  sourceSha256: true,
  sourceSizeBytes: true,
  fixtureVersion: true,
  providerMode: true,
  purpose: true,
  phase: true,
  requestSha256: true,
  payloadSha256: true,
  pinnedGlobalRolloutGeneration: true,
  pinnedPracticeRolloutGeneration: true,
  sourceArtifactId: true,
  noteTemplateId: true,
  noteTemplateVersion: true,
  certificationId: true,
  mappingSha256: true,
  visitId: true,
  attempt: true,
  expiresAt: true,
  failedAt: true,
  revokedAt: true,
  consumedAt: true,
} as const;

const IDEMPOTENCY_KEY = /^[A-Za-z0-9._~-]{16,128}$/u;
const FAILURE_CODE = /^[A-Z0-9_]{3,80}$/u;

function sameRolloutGeneration(
  expected: TemplateTwinRolloutToken,
  current: TemplateTwinRolloutToken,
): boolean {
  return (
    expected.practiceId === current.practiceId &&
    expected.globalGeneration === current.globalGeneration &&
    expected.practiceGeneration === current.practiceGeneration
  );
}

function deterministicClaimId(value: string): string {
  const hash = createHash("sha256")
    .update(`template-twin-staging-admission-claim:${value}`, "utf8")
    .digest("hex");
  return `${hash.slice(0, 8)}-${hash.slice(8, 12)}-4${hash.slice(13, 16)}-8${hash.slice(17, 20)}-${hash.slice(20, 32)}`;
}

function admissionRequestSha256(input: {
  practiceId: string;
  actorId: string;
  idempotencyKey: string;
  purpose: "UPLOAD" | "VISIT";
}): string {
  if (!IDEMPOTENCY_KEY.test(input.idempotencyKey)) {
    throw new TemplateTwinStagingQaAdmissionError(
      "TEMPLATE_TWIN_STAGING_QA_ADMISSION_MISMATCH",
    );
  }
  return canonicalSha256({
    contractVersion: "template-twin-staging-admission-v1",
    practiceId: input.practiceId,
    actorId: input.actorId,
    purpose: input.purpose,
    idempotencyKey: input.idempotencyKey,
  });
}

function assertAdmissionMatches(input: {
  admission: TemplateTwinStagingQaAdmissionRow | null | undefined;
  actor: Pick<TemplateTwinStagingQaAdmissionActor, "userId" | "practiceId">;
  currentToken: TemplateTwinRolloutToken;
  allowedPhases: readonly TemplateTwinStagingQaAdmissionPhase[];
  expectedProviderMode?: TemplateTwinStagingQaAdmissionProviderMode;
  expectedSource?: { sha256: string; sizeBytes: number };
  expectedTemplate?: { id: string; version?: number };
  expectedVisitId?: string;
  now?: Date;
}): TemplateTwinStagingQaAdmissionRow {
  const admission = input.admission;
  if (!admission) {
    throw new TemplateTwinStagingQaAdmissionError(
      "TEMPLATE_TWIN_STAGING_QA_ADMISSION_NOT_FOUND",
    );
  }
  if (
    admission.practiceId !== input.actor.practiceId ||
    admission.actorId !== input.actor.userId ||
    input.currentToken.practiceId !== input.actor.practiceId
  ) {
    throw new TemplateTwinStagingQaAdmissionError(
      "TEMPLATE_TWIN_STAGING_QA_ADMISSION_NOT_FOUND",
    );
  }
  const now = input.now ?? new Date();
  const signedConsumptionIsExpected =
    admission.phase === "SIGNED" &&
    input.allowedPhases.includes("SIGNED") &&
    admission.consumedAt !== null;
  if (
    admission.failedAt !== null ||
    admission.revokedAt !== null ||
    admission.phase === "FAILED" ||
    admission.phase === "REVOKED" ||
    (admission.consumedAt !== null && !signedConsumptionIsExpected) ||
    admission.expiresAt <= now ||
    !sameRolloutGeneration(
      {
        practiceId: admission.practiceId,
        globalGeneration: admission.pinnedGlobalRolloutGeneration,
        practiceGeneration: admission.pinnedPracticeRolloutGeneration,
      },
      input.currentToken,
    )
  ) {
    throw new TemplateTwinStagingQaAdmissionError(
      "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE",
    );
  }
  if (
    !input.allowedPhases.includes(
      admission.phase as TemplateTwinStagingQaAdmissionPhase,
    )
  ) {
    throw new TemplateTwinStagingQaAdmissionError(
      "TEMPLATE_TWIN_STAGING_QA_ADMISSION_PHASE_INVALID",
    );
  }
  if (
    admission.fixtureVersion !== TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION ||
    admission.sourceSha256 !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 ||
    admission.sourceSizeBytes !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES ||
    (input.expectedProviderMode !== undefined &&
      admission.providerMode !== input.expectedProviderMode) ||
    (input.expectedSource !== undefined &&
      (admission.sourceSha256 !== input.expectedSource.sha256 ||
        admission.sourceSizeBytes !== input.expectedSource.sizeBytes)) ||
    (input.expectedTemplate !== undefined &&
      (admission.noteTemplateId !== input.expectedTemplate.id ||
        (input.expectedTemplate.version !== undefined &&
          admission.noteTemplateVersion !== input.expectedTemplate.version))) ||
    (input.expectedVisitId !== undefined &&
      admission.visitId !== input.expectedVisitId)
  ) {
    throw new TemplateTwinStagingQaAdmissionError(
      "TEMPLATE_TWIN_STAGING_QA_ADMISSION_MISMATCH",
    );
  }
  return admission;
}

interface AdmissionTransactionClient {
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
}

export async function lockAndAssertTemplateTwinStagingQaAdmission(input: {
  tx: AdmissionTransactionClient;
  admissionId: string;
  actor: Pick<TemplateTwinStagingQaAdmissionActor, "userId" | "practiceId">;
  currentToken: TemplateTwinRolloutToken;
  allowedPhases: readonly TemplateTwinStagingQaAdmissionPhase[];
  expectedProviderMode?: TemplateTwinStagingQaAdmissionProviderMode;
  expectedTemplate?: { id: string; version?: number };
  expectedVisitId?: string;
}): Promise<TemplateTwinStagingQaAdmissionRow> {
  const rows = await input.tx.$queryRaw<TemplateTwinStagingQaAdmissionRow[]>(
    Prisma.sql`
      SELECT
        "id", "practiceId", "actorId", "parentAdmissionId",
        "sourceSha256", "sourceSizeBytes", "fixtureVersion", "providerMode",
        "purpose", "phase", "requestSha256", "payloadSha256",
        "pinnedGlobalRolloutGeneration", "pinnedPracticeRolloutGeneration",
        "sourceArtifactId", "noteTemplateId", "noteTemplateVersion",
        "certificationId", "mappingSha256", "visitId", "attempt",
        "expiresAt", "failedAt", "revokedAt", "consumedAt"
      FROM "template_twin_synthetic_qa_admissions"
      WHERE "id" = ${input.admissionId}
      FOR UPDATE
    `,
  );
  const clockRows = await input.tx.$queryRaw<{ databaseNow: Date }[]>(
    Prisma.sql`SELECT clock_timestamp() AS "databaseNow"`,
  );
  return assertAdmissionMatches({
    admission: rows[0] ?? null,
    actor: input.actor,
    currentToken: input.currentToken,
    allowedPhases: input.allowedPhases,
    expectedProviderMode: input.expectedProviderMode,
    expectedTemplate: input.expectedTemplate,
    expectedVisitId: input.expectedVisitId,
    now: clockRows[0]?.databaseNow,
  });
}

async function currentRollout(input: {
  actor: TemplateTwinStagingQaAdmissionActor;
  env: SyntheticQaProviderEnvironment;
}): Promise<TemplateTwinRolloutToken> {
  assertTemplateTwinStagingQaGate(input.env);
  assertTemplateTwinSyntheticQaProviderEnvironment(input.env);
  const token = await pinTemplateTwinRollout({
    practiceId: input.actor.practiceId,
    env: input.env,
  });
  if (!sameRolloutGeneration(input.actor.rolloutToken, token)) {
    throw new TemplateTwinStagingQaAdmissionError(
      "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE",
    );
  }
  return token;
}

export async function beginTemplateTwinStagingQaUploadAdmission(input: {
  actor: TemplateTwinStagingQaAdmissionActor;
  idempotencyKey: string;
  source: { sha256: string; sizeBytes: number };
  env?: SyntheticQaProviderEnvironment;
}): Promise<TemplateTwinStagingQaAdmissionRow> {
  if (
    input.source.sha256 !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 ||
    input.source.sizeBytes !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES
  ) {
    throw new TemplateTwinStagingQaAdmissionError(
      "TEMPLATE_TWIN_STAGING_QA_ADMISSION_MISMATCH",
    );
  }
  const env = input.env ?? process.env;
  const token = await currentRollout({ actor: input.actor, env });
  const requestSha256 = admissionRequestSha256({
    practiceId: input.actor.practiceId,
    actorId: input.actor.userId,
    idempotencyKey: input.idempotencyKey,
    purpose: "UPLOAD",
  });
  const now = new Date();
  const expiresAt = new Date(now.getTime() + TEMPLATE_TWIN_STAGING_QA_ADMISSION_TTL_MS);

  return prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: token,
        env,
      });
      if (!rollout.allowed) {
        throw new TemplateTwinStagingQaAdmissionError(
          "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE",
        );
      }
      const existing = await tx.templateTwinSyntheticQaAdmission.findFirst({
        where: {
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          requestSha256,
        },
        select: TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT,
      });
      if (existing) {
        return assertAdmissionMatches({
          admission: existing,
          actor: input.actor,
          currentToken: rollout.token,
          allowedPhases: [
            "ADMITTED",
            "SOURCE_VERIFIED",
            "TEMPLATE_LINKED",
            "CERTIFIED",
          ],
          expectedProviderMode: "SYNTHETIC_LIFECYCLE",
          expectedSource: input.source,
        });
      }
      const admission = await tx.templateTwinSyntheticQaAdmission.create({
        data: {
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          sourceSha256: input.source.sha256,
          sourceSizeBytes: input.source.sizeBytes,
          fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
          providerMode: "SYNTHETIC_LIFECYCLE",
          purpose: "UPLOAD",
          phase: "ADMITTED",
          requestSha256,
          pinnedGlobalRolloutGeneration: token.globalGeneration,
          pinnedPracticeRolloutGeneration: token.practiceGeneration,
          expiresAt,
        },
        select: TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT,
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:staging-admission:created:${admission.id}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail ?? null,
        action: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_CREATED",
        targetType: "TemplateTwinSyntheticQaAdmission",
        targetId: admission.id,
        metadata: {
          purpose: admission.purpose,
          providerMode: admission.providerMode,
          phase: admission.phase,
          sourceSha256: admission.sourceSha256,
          sourceSizeBytes: admission.sourceSizeBytes,
          globalRolloutGeneration: token.globalGeneration.toString(),
          practiceRolloutGeneration: token.practiceGeneration.toString(),
        },
      });
      return admission;
    },
    { isolationLevel: "Serializable" },
  );
}

export async function runWithVerifiedTemplateTwinStagingQaAdmissionProvider<T>(
  input: {
    admissionId: string;
    actor: TemplateTwinStagingQaAdmissionActor;
    allowedPhases: readonly TemplateTwinStagingQaAdmissionPhase[];
    expectedProviderMode: TemplateTwinStagingQaAdmissionProviderMode;
    expectedSource?: { sha256: string; sizeBytes: number };
    expectedTemplate?: { id: string; version?: number };
    evidenceText?: string;
    operation: (providerVisitId: string) => Promise<T> | T;
    env?: SyntheticQaProviderEnvironment;
  },
): Promise<T> {
  if (input.allowedPhases.includes("SIGNED")) {
    throw new TemplateTwinStagingQaAdmissionError(
      "TEMPLATE_TWIN_STAGING_QA_ADMISSION_PHASE_INVALID",
    );
  }
  const env = input.env ?? process.env;
  const token = await currentRollout({ actor: input.actor, env });
  // This read intentionally uses the root Prisma client. A row created only
  // inside an uncommitted caller transaction is invisible and cannot mint a
  // provider capability.
  const admission = await prisma.templateTwinSyntheticQaAdmission.findFirst({
    where: { id: input.admissionId },
    select: TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT,
  });
  const verified = assertAdmissionMatches({
    admission,
    actor: input.actor,
    currentToken: token,
    allowedPhases: input.allowedPhases,
    expectedProviderMode: input.expectedProviderMode,
    expectedSource: input.expectedSource,
    expectedTemplate: input.expectedTemplate,
  });
  const evidenceText = input.evidenceText ?? TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT;
  const active = getTemplateTwinSyntheticQaProviderContext();
  if (active) {
    if (
      active.admissionId !== verified.id ||
      active.practiceId !== verified.practiceId ||
      active.pinnedGlobalGeneration !== verified.pinnedGlobalRolloutGeneration ||
      active.pinnedPracticeGeneration !==
        verified.pinnedPracticeRolloutGeneration ||
      active.evidenceSha256 !==
        createHash("sha256").update(evidenceText, "utf8").digest("hex")
    ) {
      throw new TemplateTwinStagingQaAdmissionError(
        "TEMPLATE_TWIN_STAGING_QA_ADMISSION_MISMATCH",
      );
    }
    return input.operation(active.visitId);
  }

  const providerVisitId =
    verified.visitId ?? `template-twin-staging-admission-visit:${verified.id}`;
  try {
    return await runWithTemplateTwinSyntheticQaProviderContext(
      {
        mode: TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
        fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
        admissionId: verified.id,
        runId: verified.id,
        visitId: providerVisitId,
        practiceId: verified.practiceId,
        requestSha256: verified.requestSha256,
        attempt: verified.attempt,
        workerClaimId: deterministicClaimId(verified.id),
        pinnedGlobalGeneration: verified.pinnedGlobalRolloutGeneration,
        pinnedPracticeGeneration: verified.pinnedPracticeRolloutGeneration,
        evidenceText,
      },
      () => input.operation(providerVisitId),
      env,
    );
  } catch (error) {
    if (error instanceof SyntheticQaProviderContextError) {
      throw new TemplateTwinStagingQaAdmissionError(
        "TEMPLATE_TWIN_STAGING_QA_ADMISSION_MISMATCH",
        undefined,
        { cause: error },
      );
    }
    throw error;
  }
}

export async function completeTemplateTwinStagingQaUploadAdmission(input: {
  admissionId: string;
  actor: TemplateTwinStagingQaAdmissionActor;
  noteTemplateId: string;
  env?: SyntheticQaProviderEnvironment;
}): Promise<void> {
  const env = input.env ?? process.env;
  const token = await currentRollout({ actor: input.actor, env });
  await prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: token,
        env,
      });
      if (!rollout.allowed) {
        throw new TemplateTwinStagingQaAdmissionError(
          "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE",
        );
      }
      const admission = await lockAndAssertTemplateTwinStagingQaAdmission({
        tx,
        admissionId: input.admissionId,
        actor: input.actor,
        currentToken: rollout.token,
        allowedPhases: ["ADMITTED", "SOURCE_VERIFIED", "TEMPLATE_LINKED"],
        expectedProviderMode: "SYNTHETIC_LIFECYCLE",
      });
      if (admission.phase === "TEMPLATE_LINKED") {
        if (admission.noteTemplateId !== input.noteTemplateId) {
          throw new TemplateTwinStagingQaAdmissionError(
            "TEMPLATE_TWIN_STAGING_QA_ADMISSION_MISMATCH",
          );
        }
        return;
      }
      const template = await tx.noteTemplate.findFirst({
        where: {
          id: input.noteTemplateId,
          doctorId: input.actor.userId,
          templateKind: "template_twin_docx",
          templateTwinCompiledVersion: {
            is: {
              sourceArtifact: {
                is: {
                  practiceId: input.actor.practiceId,
                  validationStatus: "accepted",
                  quarantineArtifact: {
                    is: {
                      practiceId: input.actor.practiceId,
                      intakeMode: "NATIVE_TEMPLATE",
                      status: "ADMITTED",
                      sha256: admission.sourceSha256,
                      sizeBytes: admission.sourceSizeBytes,
                    },
                  },
                },
              },
            },
          },
        },
        select: {
          id: true,
          version: true,
          templateTwinCompiledVersion: {
            select: { sourceArtifactId: true },
          },
        },
      });
      const sourceArtifactId =
        template?.templateTwinCompiledVersion?.sourceArtifactId ?? null;
      if (!template || !sourceArtifactId) {
        throw new TemplateTwinStagingQaAdmissionError(
          "TEMPLATE_TWIN_STAGING_QA_ADMISSION_MISMATCH",
        );
      }
      const now = new Date();
      if (admission.phase === "ADMITTED") {
        await tx.templateTwinSyntheticQaAdmission.update({
          where: { id: admission.id },
          data: {
            phase: "SOURCE_VERIFIED",
            sourceArtifactId,
            sourceVerifiedAt: now,
          },
        });
      }
      await tx.templateTwinSyntheticQaAdmission.update({
        where: { id: admission.id },
        data: {
          phase: "TEMPLATE_LINKED",
          sourceArtifactId,
          sourceVerifiedAt: now,
          noteTemplateId: template.id,
          noteTemplateVersion: template.version,
          templateLinkedAt: now,
        },
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:staging-admission:template-linked:${admission.id}:${template.id}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail ?? null,
        action: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_ADVANCED",
        targetType: "TemplateTwinSyntheticQaAdmission",
        targetId: admission.id,
        metadata: {
          phase: "TEMPLATE_LINKED",
          noteTemplateId: template.id,
          noteTemplateVersion: template.version,
          sourceArtifactId,
        },
      });
    },
    { isolationLevel: "Serializable" },
  );
}

export async function readTemplateTwinStagingQaAdmittedDraft(input: {
  admission: TemplateTwinStagingQaAdmissionRow;
  actor: Pick<TemplateTwinStagingQaAdmissionActor, "userId" | "practiceId">;
}): Promise<{
  noteTemplateId: string;
  sourceSha256: string;
  compilerVersion: string;
  fieldCount: number;
  blockingUnsupportedCount: number;
} | null> {
  if (
    input.admission.actorId !== input.actor.userId ||
    input.admission.practiceId !== input.actor.practiceId ||
    !["TEMPLATE_LINKED", "CERTIFIED"].includes(input.admission.phase) ||
    !input.admission.noteTemplateId
  ) {
    return null;
  }
  const row = await prisma.noteTemplate.findFirst({
    where: {
      id: input.admission.noteTemplateId,
      doctorId: input.actor.userId,
      version: input.admission.noteTemplateVersion ?? undefined,
      templateKind: "template_twin_docx",
      templateTwinCompiledVersion: {
        is: {
          sourceArtifactId: input.admission.sourceArtifactId ?? undefined,
          sourceArtifact: {
            is: {
              practiceId: input.actor.practiceId,
              quarantineArtifact: {
                is: {
                  practiceId: input.actor.practiceId,
                  intakeMode: "NATIVE_TEMPLATE",
                  status: "ADMITTED",
                  sha256: input.admission.sourceSha256,
                  sizeBytes: input.admission.sourceSizeBytes,
                },
              },
            },
          },
        },
      },
    },
    select: {
      id: true,
      templateTwinCompiledVersion: {
        select: {
          compilerVersion: true,
          blockingUnsupportedCount: true,
          _count: { select: { fields: true } },
        },
      },
    },
  });
  const compiled = row?.templateTwinCompiledVersion;
  return row && compiled
    ? {
        noteTemplateId: row.id,
        sourceSha256: input.admission.sourceSha256,
        compilerVersion: compiled.compilerVersion,
        fieldCount: compiled._count.fields,
        blockingUnsupportedCount: compiled.blockingUnsupportedCount,
      }
    : null;
}

export async function certifyTemplateTwinStagingQaAdmission(input: {
  admissionId: string;
  actor: TemplateTwinStagingQaAdmissionActor;
  noteTemplateId: string;
  env?: SyntheticQaProviderEnvironment;
}): Promise<void> {
  const env = input.env ?? process.env;
  const token = await currentRollout({ actor: input.actor, env });
  await prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: token,
        env,
      });
      if (!rollout.allowed) {
        throw new TemplateTwinStagingQaAdmissionError(
          "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE",
        );
      }
      const admission = await lockAndAssertTemplateTwinStagingQaAdmission({
        tx,
        admissionId: input.admissionId,
        actor: input.actor,
        currentToken: rollout.token,
        allowedPhases: ["TEMPLATE_LINKED", "CERTIFIED"],
        expectedProviderMode: "SYNTHETIC_LIFECYCLE",
        expectedTemplate: { id: input.noteTemplateId },
      });
      const certification = await tx.templateTwinCertification.findFirst({
        where: {
          compiledVersion: {
            is: {
              noteTemplateId: input.noteTemplateId,
              certificationStatus: "CERTIFIED",
              sourceArtifactId: admission.sourceArtifactId!,
            },
          },
        },
        select: { id: true, approvedMappingsSha256: true },
      });
      if (!certification) {
        throw new TemplateTwinStagingQaAdmissionError(
          "TEMPLATE_TWIN_STAGING_QA_ADMISSION_PHASE_INVALID",
        );
      }
      if (admission.phase === "CERTIFIED") {
        if (
          admission.certificationId !== certification.id ||
          admission.mappingSha256 !== certification.approvedMappingsSha256
        ) {
          throw new TemplateTwinStagingQaAdmissionError(
            "TEMPLATE_TWIN_STAGING_QA_ADMISSION_MISMATCH",
          );
        }
        return;
      }
      await tx.templateTwinSyntheticQaAdmission.update({
        where: { id: admission.id },
        data: {
          phase: "CERTIFIED",
          certificationId: certification.id,
          mappingSha256: certification.approvedMappingsSha256,
          certifiedAt: new Date(),
        },
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:staging-admission:certified:${admission.id}:${certification.id}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail ?? null,
        action: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_ADVANCED",
        targetType: "TemplateTwinSyntheticQaAdmission",
        targetId: admission.id,
        metadata: {
          phase: "CERTIFIED",
          noteTemplateId: input.noteTemplateId,
          certificationId: certification.id,
          mappingSha256: certification.approvedMappingsSha256,
        },
      });
    },
    { isolationLevel: "Serializable" },
  );
}

export async function beginTemplateTwinStagingQaVisitAdmission(input: {
  actor: TemplateTwinStagingQaAdmissionActor;
  idempotencyKey: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  mode: "typed" | "mock_voice";
  payloadSha256: string;
  env?: SyntheticQaProviderEnvironment;
}): Promise<TemplateTwinStagingQaAdmissionRow> {
  const env = input.env ?? process.env;
  const token = await currentRollout({ actor: input.actor, env });
  if (!IDEMPOTENCY_KEY.test(input.idempotencyKey)) {
    throw new TemplateTwinStagingQaAdmissionError(
      "TEMPLATE_TWIN_STAGING_QA_ADMISSION_MISMATCH",
    );
  }
  const requestSha256 = templateTwinStagingQaRunRequestSha256({
    practiceId: input.actor.practiceId,
    doctorId: input.actor.userId,
    idempotencyKey: input.idempotencyKey,
  });
  const providerMode: TemplateTwinStagingQaAdmissionProviderMode =
    input.mode === "typed" ? "SYNTHETIC_TYPED" : "SYNTHETIC_MOCK_VOICE";
  const now = new Date();

  return runSerializableTransactionWithRetry({
    prisma,
    operation: "begin_template_twin_staging_qa_visit_admission",
    context: { practiceId: input.actor.practiceId },
    transaction: async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: token,
        env,
      });
      if (!rollout.allowed) {
        throw new TemplateTwinStagingQaAdmissionError(
          "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE",
        );
      }
      const existing = await tx.templateTwinSyntheticQaAdmission.findFirst({
        where: {
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          requestSha256,
        },
        select: TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT,
      });
      if (existing) {
        if (existing.payloadSha256 !== input.payloadSha256) {
          throw new TemplateTwinStagingQaAdmissionError(
            "TEMPLATE_TWIN_STAGING_QA_ADMISSION_MISMATCH",
          );
        }
        return assertAdmissionMatches({
          admission: existing,
          actor: input.actor,
          currentToken: rollout.token,
          allowedPhases: [
            "CERTIFIED",
            "VISIT_LINKED",
            "PROCESSING",
            "REVIEW_READY",
            "SIGNED",
          ],
          expectedProviderMode: providerMode,
          expectedTemplate: {
            id: input.noteTemplateId,
            version: input.noteTemplateVersion,
          },
        });
      }
      const parent = await tx.templateTwinSyntheticQaAdmission.findFirst({
        where: {
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          purpose: "UPLOAD",
          providerMode: "SYNTHETIC_LIFECYCLE",
          phase: "CERTIFIED",
          noteTemplateId: input.noteTemplateId,
          noteTemplateVersion: input.noteTemplateVersion,
          sourceSha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
          sourceSizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
          pinnedGlobalRolloutGeneration: token.globalGeneration,
          pinnedPracticeRolloutGeneration: token.practiceGeneration,
          failedAt: null,
          revokedAt: null,
          expiresAt: { gt: now },
        },
        orderBy: { createdAt: "desc" },
        select: TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT,
      });
      if (
        !parent?.sourceArtifactId ||
        !parent.certificationId ||
        !parent.mappingSha256
      ) {
        throw new TemplateTwinStagingQaAdmissionError(
          "TEMPLATE_TWIN_STAGING_QA_ADMISSION_NOT_FOUND",
        );
      }
      const admission = await tx.templateTwinSyntheticQaAdmission.create({
        data: {
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          parentAdmissionId: parent.id,
          sourceSha256: parent.sourceSha256,
          sourceSizeBytes: parent.sourceSizeBytes,
          fixtureVersion: parent.fixtureVersion,
          providerMode,
          purpose: "VISIT",
          phase: "ADMITTED",
          requestSha256,
          payloadSha256: input.payloadSha256,
          pinnedGlobalRolloutGeneration: token.globalGeneration,
          pinnedPracticeRolloutGeneration: token.practiceGeneration,
          sourceArtifactId: parent.sourceArtifactId,
          noteTemplateId: parent.noteTemplateId,
          noteTemplateVersion: parent.noteTemplateVersion,
          certificationId: parent.certificationId,
          mappingSha256: parent.mappingSha256,
          expiresAt: new Date(now.getTime() + TEMPLATE_TWIN_STAGING_QA_ADMISSION_TTL_MS),
        },
        select: TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT,
      });
      await tx.templateTwinSyntheticQaAdmission.update({
        where: { id: admission.id },
        data: { phase: "SOURCE_VERIFIED", sourceVerifiedAt: now },
      });
      await tx.templateTwinSyntheticQaAdmission.update({
        where: { id: admission.id },
        data: { phase: "TEMPLATE_LINKED", templateLinkedAt: now },
      });
      const certified = await tx.templateTwinSyntheticQaAdmission.update({
        where: { id: admission.id },
        data: { phase: "CERTIFIED", certifiedAt: now },
        select: TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT,
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:staging-admission:visit-created:${certified.id}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail ?? null,
        action: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_CREATED",
        targetType: "TemplateTwinSyntheticQaAdmission",
        targetId: certified.id,
        metadata: {
          purpose: "VISIT",
          providerMode,
          phase: "CERTIFIED",
          parentAdmissionId: parent.id,
          noteTemplateId: input.noteTemplateId,
          noteTemplateVersion: input.noteTemplateVersion,
          requestSha256,
          payloadSha256: input.payloadSha256,
        },
      });
      return certified;
    },
  });
}

export async function markTemplateTwinStagingQaAdmissionFailed(input: {
  admissionId: string;
  actor: Pick<
    TemplateTwinStagingQaAdmissionActor,
    "userId" | "userEmail" | "practiceId"
  >;
  failureCode: string;
}): Promise<void> {
  const failureCode = FAILURE_CODE.test(input.failureCode)
    ? input.failureCode
    : "SYNTHETIC_PROVIDER_FAILED";
  await prisma.$transaction(async (tx: Prisma.TransactionClient) => {
    const admission = await tx.templateTwinSyntheticQaAdmission.findFirst({
      where: {
        id: input.admissionId,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
      },
      select: { id: true, phase: true },
    });
    if (!admission || admission.phase === "FAILED") return;
    if (admission.phase === "SIGNED" || admission.phase === "REVOKED") {
      throw new TemplateTwinStagingQaAdmissionError(
        "TEMPLATE_TWIN_STAGING_QA_ADMISSION_PHASE_INVALID",
      );
    }
    await tx.templateTwinSyntheticQaAdmission.update({
      where: { id: admission.id },
      data: {
        phase: "FAILED",
        failedAt: new Date(),
        failureCode,
      },
    });
    await enqueueTemplateTwinAudit(tx, {
      eventKey: `template-twin:staging-admission:failed:${admission.id}:${failureCode}`,
      practiceId: input.actor.practiceId,
      actorId: input.actor.userId,
      actorEmailSnapshot: input.actor.userEmail ?? null,
      action: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_FAILED",
      targetType: "TemplateTwinSyntheticQaAdmission",
      targetId: admission.id,
      metadata: { phase: "FAILED", failureCode },
    });
  });
}

export function stagingQaAdmissionIsRequired(
  env: Readonly<Record<string, string | undefined>> = process.env,
): boolean {
  return isTemplateTwinStagingQaRequested(env);
}
