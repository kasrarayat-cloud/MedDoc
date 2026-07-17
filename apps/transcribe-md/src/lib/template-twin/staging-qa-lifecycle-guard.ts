import { createHash } from "node:crypto";

import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  SyntheticQaProviderContextError,
  assertTemplateTwinSyntheticQaProviderEnvironment,
  getTemplateTwinSyntheticQaProviderContext,
  runWithTemplateTwinSyntheticQaProviderContext,
  type SyntheticQaProviderEnvironment,
} from "@meddoc/ai";
import { Prisma } from "@prisma/client";
import prisma from "@meddoc/db";

import {
  lockTemplateTwinRolloutForFinalClaim,
  pinTemplateTwinRollout,
  type TemplateTwinRolloutToken,
} from "./rollout";
import { isTemplateTwinStagingQaFixtureSource } from "./staging-qa-fixtures";
import { assertTemplateTwinStagingQaGate } from "./staging-qa-gate";
import {
  confirmTemplateTwinStagingQaMappings,
  type TemplateTwinStagingQaExpectedMappingConfirmation,
} from "./staging-qa-mapping-confirmation";

export const TEMPLATE_TWIN_STAGING_QA_LIFECYCLE_GUARD_CODE =
  "TEMPLATE_TWIN_STAGING_QA_LIFECYCLE_UNAVAILABLE" as const;

export class TemplateTwinStagingQaLifecycleGuardError extends Error {
  readonly code = TEMPLATE_TWIN_STAGING_QA_LIFECYCLE_GUARD_CODE;

  constructor() {
    super("Template Twin synthetic QA is unavailable.");
    this.name = "TemplateTwinStagingQaLifecycleGuardError";
  }
}

export interface TemplateTwinStagingQaLifecycleActor {
  readonly userId: string;
  readonly practiceId: string;
  readonly rolloutToken: TemplateTwinRolloutToken;
}

export interface TemplateTwinStagingQaLifecycleProvenance {
  readonly stagingQa: boolean;
  readonly source: { readonly sha256: string; readonly sizeBytes: number };
}

interface GuardDependencies {
  readonly env: SyntheticQaProviderEnvironment;
  readonly inspect: (input: {
    noteTemplateId: string;
    actor: Pick<TemplateTwinStagingQaLifecycleActor, "userId" | "practiceId">;
  }) => Promise<TemplateTwinStagingQaLifecycleProvenance | null>;
  readonly pinRollout: typeof pinTemplateTwinRollout;
  readonly confirmMappings: typeof confirmTemplateTwinStagingQaMappings;
}

function sameRolloutGeneration(
  pinned: TemplateTwinRolloutToken,
  current: TemplateTwinRolloutToken,
): boolean {
  return (
    pinned.practiceId === current.practiceId &&
    pinned.globalGeneration === current.globalGeneration &&
    pinned.practiceGeneration === current.practiceGeneration
  );
}

function digest(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function lifecycleWorkerClaimId(input: string): string {
  const value = digest(`template-twin-staging-lifecycle-claim:${input}`);
  return `${value.slice(0, 8)}-${value.slice(8, 12)}-4${value.slice(13, 16)}-8${value.slice(17, 20)}-${value.slice(20, 32)}`;
}

/**
 * Resolve staging provenance without trusting a display name, route, or
 * caller-provided flag. The exact immutable source identity is sufficient;
 * once a durable staging run exists, that relation keeps every generic
 * lifecycle surface inside the staging boundary as defense in depth.
 */
export async function inspectTemplateTwinStagingQaLifecycleProvenance(input: {
  noteTemplateId: string;
  actor: Pick<TemplateTwinStagingQaLifecycleActor, "userId" | "practiceId">;
}): Promise<TemplateTwinStagingQaLifecycleProvenance | null> {
  const row = await prisma.noteTemplate.findFirst({
    where: {
      id: input.noteTemplateId,
      doctorId: input.actor.userId,
      templateKind: "template_twin_docx",
    },
    select: {
      templateTwinCompiledVersion: {
        select: {
          sourceArtifact: {
            select: { practiceId: true, sha256: true, sizeBytes: true },
          },
        },
      },
      templateTwinSyntheticQaRuns: {
        where: {
          practiceId: input.actor.practiceId,
          doctorId: input.actor.userId,
        },
        take: 1,
        select: { id: true },
      },
    },
  });
  const source = row?.templateTwinCompiledVersion?.sourceArtifact;
  if (!source || source.practiceId !== input.actor.practiceId) return null;
  return {
    source: { sha256: source.sha256, sizeBytes: source.sizeBytes },
    stagingQa:
      isTemplateTwinStagingQaFixtureSource(source) ||
      row.templateTwinSyntheticQaRuns.length > 0,
  };
}

/**
 * One admission boundary for every generic Template Twin lifecycle surface.
 * Ordinary templates are deliberately unchanged. Exact/durably related
 * staging templates require the staging resource gate, current rollout
 * generations, and a visit-bound deterministic provider context before the
 * operation can reach any privacy, transcription, or model callback.
 */
export async function runWithTemplateTwinStagingQaLifecycleGuard<T>(input: {
  noteTemplateId: string;
  actor: TemplateTwinStagingQaLifecycleActor;
  purpose: string;
  operation: (providerVisitId: string | null) => Promise<T> | T;
  evidenceText?: string;
  requireConfirmedMappings?: boolean;
  expectedMappingConfirmation?: TemplateTwinStagingQaExpectedMappingConfirmation;
  dependencies?: Partial<GuardDependencies>;
}): Promise<T> {
  const inspect =
    input.dependencies?.inspect ??
    inspectTemplateTwinStagingQaLifecycleProvenance;
  const provenance = await inspect({
    noteTemplateId: input.noteTemplateId,
    actor: input.actor,
  });
  if (!provenance) throw new TemplateTwinStagingQaLifecycleGuardError();
  if (!provenance.stagingQa) return input.operation(null);

  const env = input.dependencies?.env ?? process.env;
  const pinRollout = input.dependencies?.pinRollout ?? pinTemplateTwinRollout;
  const confirmMappings =
    input.dependencies?.confirmMappings ?? confirmTemplateTwinStagingQaMappings;
  const evidenceText =
    input.evidenceText ?? TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT;

  let currentToken: TemplateTwinRolloutToken;
  try {
    if (
      input.requireConfirmedMappings &&
      !(await confirmMappings({
        noteTemplateId: input.noteTemplateId,
        doctorId: input.actor.userId,
        practiceId: input.actor.practiceId,
        source: provenance.source,
        expected: input.expectedMappingConfirmation,
      }))
    ) {
      throw new TemplateTwinStagingQaLifecycleGuardError();
    }
    assertTemplateTwinStagingQaGate(env);
    assertTemplateTwinSyntheticQaProviderEnvironment(env);
    currentToken = await pinRollout({
      practiceId: input.actor.practiceId,
      env,
    });
  } catch {
    throw new TemplateTwinStagingQaLifecycleGuardError();
  }
  if (!sameRolloutGeneration(input.actor.rolloutToken, currentToken)) {
    throw new TemplateTwinStagingQaLifecycleGuardError();
  }

  const requestSha256 = digest(
    JSON.stringify({
      contract: "template-twin-staging-lifecycle-guard-v1",
      noteTemplateId: input.noteTemplateId,
      practiceId: input.actor.practiceId,
      purpose: input.purpose,
      sourceSha256: provenance.source.sha256,
      sourceSizeBytes: provenance.source.sizeBytes,
      evidenceSha256: digest(evidenceText),
      globalGeneration: currentToken.globalGeneration.toString(),
      practiceGeneration: currentToken.practiceGeneration.toString(),
    }),
  );
  const active = getTemplateTwinSyntheticQaProviderContext();
  if (active) {
    if (
      active.practiceId !== input.actor.practiceId ||
      active.pinnedGlobalGeneration !== currentToken.globalGeneration ||
      active.pinnedPracticeGeneration !== currentToken.practiceGeneration ||
      active.evidenceSha256 !== digest(evidenceText)
    ) {
      throw new TemplateTwinStagingQaLifecycleGuardError();
    }
    return input.operation(active.visitId);
  }

  const identity = digest(
    `${input.noteTemplateId}:${input.actor.userId}:${input.purpose}`,
  );
  const providerVisitId = `template-twin-staging-lifecycle-visit:${identity}`;
  try {
    return await runWithTemplateTwinSyntheticQaProviderContext(
      {
        mode: TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
        fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
        runId: `template-twin-staging-lifecycle-run:${identity}`,
        visitId: providerVisitId,
        practiceId: input.actor.practiceId,
        requestSha256,
        attempt: 1,
        workerClaimId: lifecycleWorkerClaimId(identity),
        pinnedGlobalGeneration: currentToken.globalGeneration,
        pinnedPracticeGeneration: currentToken.practiceGeneration,
        evidenceText,
      },
      () => input.operation(providerVisitId),
      env,
    );
  } catch (error) {
    if (error instanceof SyntheticQaProviderContextError) {
      throw new TemplateTwinStagingQaLifecycleGuardError();
    }
    throw error;
  }
}

/**
 * Final authorization point for a generic synthetic-test DOCX response. The
 * object may be read before this check, but no bytes are returned unless the
 * current process gate and the request's original rollout generations still
 * hold under the same global -> practice database locks used by disable.
 */
export async function assertTemplateTwinStagingQaLifecycleFinality(input: {
  noteTemplateId: string;
  actor: TemplateTwinStagingQaLifecycleActor;
  dependencies?: Pick<GuardDependencies, "env" | "inspect"> & {
    readonly lockFinal?: typeof lockTemplateTwinRolloutForFinalClaim;
  };
}): Promise<void> {
  const inspect =
    input.dependencies?.inspect ??
    inspectTemplateTwinStagingQaLifecycleProvenance;
  const provenance = await inspect({
    noteTemplateId: input.noteTemplateId,
    actor: input.actor,
  });
  if (!provenance) throw new TemplateTwinStagingQaLifecycleGuardError();
  if (!provenance.stagingQa) return;

  const env = input.dependencies?.env ?? process.env;
  try {
    assertTemplateTwinStagingQaGate(env);
    assertTemplateTwinSyntheticQaProviderEnvironment(env);
    const lockFinal =
      input.dependencies?.lockFinal ?? lockTemplateTwinRolloutForFinalClaim;
    const decision = await prisma.$transaction(
      (tx: Prisma.TransactionClient) =>
        lockFinal({
          tx,
          practiceId: input.actor.practiceId,
          pinnedToken: input.actor.rolloutToken,
          env,
        }),
      { isolationLevel: "Serializable" },
    );
    if (!decision.allowed) {
      throw new TemplateTwinStagingQaLifecycleGuardError();
    }
  } catch {
    throw new TemplateTwinStagingQaLifecycleGuardError();
  }
}
