import {
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  assertTemplateTwinSyntheticQaProviderEnvironment,
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
import {
  assertTemplateTwinStagingQaGate,
  isTemplateTwinStagingQaRequested,
} from "./staging-qa-gate";
import {
  confirmTemplateTwinStagingQaMappings,
  type TemplateTwinStagingQaExpectedMappingConfirmation,
} from "./staging-qa-mapping-confirmation";
import {
  certifyTemplateTwinStagingQaAdmission,
  lockAndAssertTemplateTwinStagingQaAdmission,
  markTemplateTwinStagingQaAdmissionFailed,
  runWithVerifiedTemplateTwinStagingQaAdmissionProvider,
  TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT,
  TemplateTwinStagingQaAdmissionError,
  type TemplateTwinStagingQaAdmissionRow,
} from "./staging-qa-admission";

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
  readonly admission: TemplateTwinStagingQaAdmissionRow | null;
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

export type TemplateTwinStagingQaExpectedBusinessError = (
  error: unknown,
) => boolean;

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
            select: {
              practiceId: true,
              sha256: true,
              sizeBytes: true,
              quarantineArtifact: {
                select: {
                  practiceId: true,
                  intakeMode: true,
                  status: true,
                  sha256: true,
                  sizeBytes: true,
                },
              },
            },
          },
        },
      },
      templateTwinSyntheticQaAdmissions: {
        where: {
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          purpose: "UPLOAD",
          providerMode: "SYNTHETIC_LIFECYCLE",
        },
        orderBy: { createdAt: "desc" as const },
        take: 1,
        select: TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT,
      },
    },
  });
  const source = row?.templateTwinCompiledVersion?.sourceArtifact;
  if (!source || source.practiceId !== input.actor.practiceId) return null;
  const admittedRaw = source.quarantineArtifact;
  const lifecycleSource =
    admittedRaw &&
    admittedRaw.practiceId === input.actor.practiceId &&
    admittedRaw.intakeMode === "NATIVE_TEMPLATE" &&
    admittedRaw.status === "ADMITTED"
      ? { sha256: admittedRaw.sha256, sizeBytes: admittedRaw.sizeBytes }
      : { sha256: source.sha256, sizeBytes: source.sizeBytes };
  return {
    source: lifecycleSource,
    stagingQa:
      isTemplateTwinStagingQaFixtureSource(lifecycleSource) ||
      row.templateTwinSyntheticQaAdmissions.length > 0,
    admission: row.templateTwinSyntheticQaAdmissions[0] ?? null,
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
  /**
   * Route-owned predicate for recoverable domain errors thrown by `operation`.
   * Admission and provider-capability failures are handled before this
   * predicate and can never be classified as recoverable.
   */
  isExpectedBusinessError?: TemplateTwinStagingQaExpectedBusinessError;
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
  const env = input.dependencies?.env ?? process.env;
  if (!provenance.stagingQa) {
    if (isTemplateTwinStagingQaRequested(env)) {
      throw new TemplateTwinStagingQaLifecycleGuardError();
    }
    return input.operation(null);
  }
  if (!provenance.admission) {
    throw new TemplateTwinStagingQaLifecycleGuardError();
  }

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

  let result: T;
  const operationFailure: { occurred: boolean; error: unknown } = {
    occurred: false,
    error: undefined,
  };
  try {
    result = await runWithVerifiedTemplateTwinStagingQaAdmissionProvider({
      admissionId: provenance.admission.id,
      actor: input.actor,
      allowedPhases:
        input.purpose === "certification-activation"
          ? ["TEMPLATE_LINKED"]
          : ["TEMPLATE_LINKED", "CERTIFIED"],
      expectedProviderMode: "SYNTHETIC_LIFECYCLE",
      expectedSource: provenance.source,
      expectedTemplate: { id: input.noteTemplateId },
      evidenceText,
      operation: async (providerVisitId) => {
        try {
          return await input.operation(providerVisitId);
        } catch (error) {
          operationFailure.occurred = true;
          operationFailure.error = error;
          throw error;
        }
      },
      env,
    });
  } catch (error) {
    if (error instanceof TemplateTwinStagingQaAdmissionError) {
      throw new TemplateTwinStagingQaLifecycleGuardError();
    }
    let expectedBusinessError = false;
    if (
      operationFailure.occurred &&
      Object.is(operationFailure.error, error)
    ) {
      try {
        expectedBusinessError =
          input.isExpectedBusinessError?.(error) === true;
      } catch {
        // A faulty classifier must fail closed and preserve the admission's
        // terminal failure semantics.
      }
    }
    if (expectedBusinessError) throw error;
    try {
      await markTemplateTwinStagingQaAdmissionFailed({
        admissionId: provenance.admission.id,
        actor: {
          userId: input.actor.userId,
          practiceId: input.actor.practiceId,
        },
        failureCode: "TEMPLATE_TWIN_STAGING_QA_LIFECYCLE_PROVIDER_FAILED",
      });
    } catch {
      throw new TemplateTwinStagingQaLifecycleGuardError();
    }
    throw error;
  }

  if (input.purpose !== "certification-activation") return result;

  // Certification admission advances only after the business operation has
  // completed successfully. Errors from this admission phase are never
  // eligible for route-level business-error classification.
  try {
    await certifyTemplateTwinStagingQaAdmission({
      admissionId: provenance.admission.id,
      actor: input.actor,
      noteTemplateId: input.noteTemplateId,
      env,
    });
  } catch (error) {
    if (error instanceof TemplateTwinStagingQaAdmissionError) {
      throw new TemplateTwinStagingQaLifecycleGuardError();
    }
    try {
      await markTemplateTwinStagingQaAdmissionFailed({
        admissionId: provenance.admission.id,
        actor: {
          userId: input.actor.userId,
          practiceId: input.actor.practiceId,
        },
        failureCode: "TEMPLATE_TWIN_STAGING_QA_LIFECYCLE_PROVIDER_FAILED",
      });
    } catch {
      throw new TemplateTwinStagingQaLifecycleGuardError();
    }
    throw error;
  }
  return result;
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
  const env = input.dependencies?.env ?? process.env;
  if (!provenance.stagingQa) {
    if (isTemplateTwinStagingQaRequested(env)) {
      throw new TemplateTwinStagingQaLifecycleGuardError();
    }
    return;
  }
  if (!provenance.admission) {
    throw new TemplateTwinStagingQaLifecycleGuardError();
  }

  try {
    assertTemplateTwinStagingQaGate(env);
    assertTemplateTwinSyntheticQaProviderEnvironment(env);
    const lockFinal =
      input.dependencies?.lockFinal ?? lockTemplateTwinRolloutForFinalClaim;
    const decision = await prisma.$transaction(
      async (tx: Prisma.TransactionClient) => {
        const decision = await lockFinal({
          tx,
          practiceId: input.actor.practiceId,
          pinnedToken: input.actor.rolloutToken,
          env,
        });
        if (!decision.allowed) return decision;
        await lockAndAssertTemplateTwinStagingQaAdmission({
          tx,
          admissionId: provenance.admission!.id,
          actor: input.actor,
          currentToken: decision.token,
          allowedPhases: ["TEMPLATE_LINKED", "CERTIFIED"],
          expectedProviderMode: "SYNTHETIC_LIFECYCLE",
          expectedTemplate: { id: input.noteTemplateId },
        });
        return decision;
      },
      { isolationLevel: "Serializable" },
    );
    if (!decision.allowed) {
      throw new TemplateTwinStagingQaLifecycleGuardError();
    }
  } catch {
    throw new TemplateTwinStagingQaLifecycleGuardError();
  }
}
