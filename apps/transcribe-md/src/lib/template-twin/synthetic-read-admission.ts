import prisma from "@meddoc/db";

import { AuthError, requireFreshDoctorIdentity } from "@/lib/auth";

import type { TemplateTwinVisitReadDecision } from "./read-authority";
import { TemplateTwinStagingQaDisabledError } from "./staging-qa-gate";
import {
  assertTemplateTwinStagingQaVisitGuard,
  TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT,
  TemplateTwinStagingQaVisitGuardError,
} from "./staging-qa-visit-guard";

/** Fixed, PHI-free denial for a generic synthetic visit read boundary. */
export class TemplateTwinSyntheticReadAdmissionError extends Error {
  readonly code = "TEMPLATE_TWIN_SYNTHETIC_READ_NOT_ADMITTED" as const;

  constructor() {
    super("The requested visit is not available.");
    this.name = "TemplateTwinSyntheticReadAdmissionError";
  }
}

export interface TemplateTwinSyntheticReadAdmission {
  visitId: string;
  practiceId: string;
  runId: string;
  attempt: number;
}

/**
 * PHI-minimal admission/reassertion for the one generic read exception granted
 * to full synthetic QA. Admission-only, pre-certification, reserved-patient
 * orphans, stale attempts, and disabled/non-isolated environments all deny.
 * Ordinary and live-Twin reads return null and retain their normal boundary.
 */
export async function requireTemplateTwinSyntheticReadAdmission(input: {
  visitId: string;
  actorUserId: string;
  readDecision: TemplateTwinVisitReadDecision;
  expected?: TemplateTwinSyntheticReadAdmission;
}): Promise<TemplateTwinSyntheticReadAdmission | null> {
  if (input.readDecision.visitId !== input.visitId) {
    throw new TemplateTwinSyntheticReadAdmissionError();
  }
  if (!input.readDecision.isSyntheticTemplateTwin) {
    if (input.expected !== undefined) {
      throw new TemplateTwinSyntheticReadAdmissionError();
    }
    return null;
  }
  if (!input.readDecision.isTemplateTwin || !input.readDecision.practiceId) {
    throw new TemplateTwinSyntheticReadAdmissionError();
  }

  const marker = await prisma.transcribeVisit.findUnique({
    // Keep the admission relation PHI-free and actor-scoped in the same
    // statement; a prior visibility decision is not authority to project a
    // run after a concurrent ownership change.
    where: { id: input.visitId, userId: input.actorUserId },
    select: {
      id: true,
      userId: true,
      templateTwinSyntheticQaRun: {
        select: TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT,
      },
    },
  });
  const run = marker?.templateTwinSyntheticQaRun ?? null;
  if (
    !marker ||
    marker.userId !== input.actorUserId ||
    !run ||
    (input.expected !== undefined &&
      (input.expected.visitId !== input.visitId ||
        run.id !== input.expected.runId ||
        run.attempt !== input.expected.attempt ||
        input.readDecision.practiceId !== input.expected.practiceId))
  ) {
    throw new TemplateTwinSyntheticReadAdmissionError();
  }

  try {
    const doctor = await requireFreshDoctorIdentity(input.actorUserId);
    if (doctor.practiceId !== input.readDecision.practiceId) {
      throw new TemplateTwinSyntheticReadAdmissionError();
    }
    assertTemplateTwinStagingQaVisitGuard({
      run,
      actor: {
        userId: input.actorUserId,
        practiceId: doctor.practiceId,
      },
      currentRolloutToken: doctor.rolloutToken,
      expectedRunId: input.expected?.runId ?? run.id,
    });
    return {
      visitId: input.visitId,
      practiceId: doctor.practiceId,
      runId: run.id,
      attempt: run.attempt,
    };
  } catch (error) {
    if (
      error instanceof AuthError ||
      error instanceof TemplateTwinStagingQaDisabledError ||
      error instanceof TemplateTwinStagingQaVisitGuardError ||
      error instanceof TemplateTwinSyntheticReadAdmissionError
    ) {
      throw new TemplateTwinSyntheticReadAdmissionError();
    }
    throw error;
  }
}
