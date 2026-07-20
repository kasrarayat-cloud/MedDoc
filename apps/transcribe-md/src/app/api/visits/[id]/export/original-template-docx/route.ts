import { NextResponse } from "next/server";
import { randomUUID } from "node:crypto";

import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";
import { apiError, withApiHandler } from "@/lib/api-error";
import { AuthError, requireFreshDoctorIdentity } from "@/lib/auth";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { logDelivery } from "@/lib/deliveries";
import { log } from "@/lib/log";
import { auth } from "@/lib/nextauth";
import {
  assessTemplateTwinSigning,
  TEMPLATE_TWIN_SIGNING_VISIT_SELECT,
} from "@/lib/template-twin/signing-gate";
import {
  createTemplateTwinArtifactStore,
  TemplateTwinArtifactIntegrityError,
  TemplateTwinStorageUnavailableError,
} from "@/lib/template-twin/storage/artifact-store";
import { DOCX_MIME_TYPE } from "@/lib/template-twin/storage/keys";
import { TemplateTwinArtifactNotFoundError } from "@/lib/template-twin/storage/ownership";
import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";
import { enqueueTemplateTwinAudit } from "@/lib/template-twin/audit-outbox";
import { lockCurrentTemplateTwinVisit } from "@/lib/template-twin/fill-engine";
import {
  lockTemplateTwinRolloutForFinalClaim,
  pinTemplateTwinRollout,
  templateTwinRolloutAuditMetadata,
  TemplateTwinRolloutError,
  type TemplateTwinRolloutToken,
} from "@/lib/template-twin/rollout";
import {
  isTemplateTwinStagingQaRequested,
  TemplateTwinStagingQaDisabledError,
} from "@/lib/template-twin/staging-qa-gate";
import {
  assertTemplateTwinStagingQaVisitGuard,
  lockAndAssertTemplateTwinStagingQaOperation,
  type LockedStagingQaRunRow,
  TemplateTwinStagingQaVisitGuardError,
} from "@/lib/template-twin/staging-qa-visit-guard";
import {
  assessVisitAutomationProof,
  lockAndAssertVisitAutomationProof,
  VisitAutomationIncompleteError,
} from "@/worker/automation-finalization";
import { persistedTemplateTwinEncounterEvidenceIsValid } from "@/lib/template-twin/encounter-evidence-verification";
import {
  lockAndAssertCurrentTemplateTwinPatient,
  lockAndAssertCurrentTemplateTwinPhysician,
  TemplateTwinCurrentPhysicianAuthorityError,
} from "@/lib/template-twin/final-claim-authority";
import { canonicalSha256 } from "@/lib/template-twin/canonical";
import {
  requireTemplateTwinVisitReadAuthority,
  TemplateTwinVisitReadAuthorityError,
} from "@/lib/template-twin/read-authority";
import {
  requireTemplateTwinSyntheticReadAdmission,
  type TemplateTwinSyntheticReadAdmission,
  TemplateTwinSyntheticReadAdmissionError,
} from "@/lib/template-twin/synthetic-read-admission";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

/**
 * Delivers the already-rendered clone of the physician's immutable source
 * template. This route never regenerates a document. It authorizes visit
 * ownership, re-runs the signing-readiness proof, then verifies object key,
 * tenant, size, metadata, and SHA-256 while reading the immutable bytes.
 */
export const GET = withApiHandler<{ id: string }>(
  "api:visits:export:original-template-docx",
  async (_request, { params }) => {
    const { id: visitId } = await params;
    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError("unauthorized", 401);

    // This classifier projects identifiers and durable provenance only. It
    // must run before the signing select below can load SOAP, transcripts, or
    // other clinical evidence into application memory.
    let preReadAuthority;
    try {
      preReadAuthority = await requireTemplateTwinVisitReadAuthority({
        db: prisma,
        visitId,
        actorUserId: userId,
      });
    } catch (error) {
      if (error instanceof TemplateTwinVisitReadAuthorityError) {
        return apiError("not found", 404);
      }
      throw error;
    }
    // This endpoint has no ordinary-visit behavior: the stored Original
    // Template DOCX exists only for an admitted Twin. Stop an ordinary visit
    // before the signing projection rather than loading clinical columns that
    // can only be rejected later.
    if (!preReadAuthority.isTemplateTwin || !preReadAuthority.practiceId) {
      return apiError("not found", 404);
    }
    if (
      isTemplateTwinStagingQaRequested() &&
      !preReadAuthority.isSyntheticTemplateTwin
    ) {
      return apiError("not found", 404);
    }

    let syntheticReadAdmission: TemplateTwinSyntheticReadAdmission | null;
    try {
      syntheticReadAdmission = await requireTemplateTwinSyntheticReadAdmission({
        visitId,
        actorUserId: userId,
        readDecision: preReadAuthority,
      });
    } catch (error) {
      if (error instanceof TemplateTwinSyntheticReadAdmissionError) {
        return apiError("not found", 404);
      }
      throw error;
    }

    let practiceId: string;
    let rolloutToken: TemplateTwinRolloutToken;
    try {
      practiceId = (await requireFreshDoctorIdentity(userId)).practiceId;
    } catch (error) {
      if (error instanceof AuthError) {
        return apiError("physician role required", 403, {
          code: "DOCTOR_ROLE_REQUIRED",
          retry: false,
        });
      }
      throw error;
    }
    if (
      (preReadAuthority.isTemplateTwin &&
        preReadAuthority.practiceId !== practiceId) ||
      (syntheticReadAdmission &&
        syntheticReadAdmission.practiceId !== practiceId)
    ) {
      return apiError("not found", 404);
    }

    try {
      rolloutToken = await pinTemplateTwinRollout({ practiceId });
    } catch (error) {
      if (!(error instanceof TemplateTwinRolloutError)) throw error;
      return apiError(error.message, 409, {
        code: error.code,
        retry: true,
      });
    }

    const visit = await prisma.transcribeVisit.findFirst({
      where: {
        id: visitId,
        AND: [
          currentClinicalVisitActorWhere(userId),
          { patient: { is: { practiceId } } },
        ],
        status: TranscribeVisitStatus.SIGNED,
        deletedAt: null,
        ...(preReadAuthority.isTemplateTwin
          ? {}
          : TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE),
      },
      select: {
        id: true,
        patientId: true,
        status: true,
        ...TEMPLATE_TWIN_SIGNING_VISIT_SELECT,
      },
    });
    if (!visit) return apiError("not found", 404);

    // Rebind the exact identifier/provenance decision immediately after the
    // clinical projection. The ordinary predicate above prevents a durable
    // Twin marker committed between admission and SELECT from being projected;
    // this recheck also closes transitions committed immediately afterward.
    let projectedReadAuthority;
    try {
      projectedReadAuthority = await requireTemplateTwinVisitReadAuthority({
        db: prisma,
        visitId,
        actorUserId: userId,
        ...(preReadAuthority.isTemplateTwin
          ? {
              expectedPracticeId: preReadAuthority.practiceId!,
              requireTemplateTwin: true,
            }
          : {}),
      });
    } catch (error) {
      if (error instanceof TemplateTwinVisitReadAuthorityError) {
        return apiError("not found", 404);
      }
      throw error;
    }
    if (
      projectedReadAuthority.visitId !== preReadAuthority.visitId ||
      projectedReadAuthority.isTemplateTwin !==
        preReadAuthority.isTemplateTwin ||
      projectedReadAuthority.isSyntheticTemplateTwin !==
        preReadAuthority.isSyntheticTemplateTwin ||
      projectedReadAuthority.practiceId !== preReadAuthority.practiceId
    ) {
      return apiError("not found", 404);
    }
    if (syntheticReadAdmission) {
      try {
        if (
          visit.templateTwinSyntheticQaRun?.id !==
            syntheticReadAdmission.runId ||
          visit.templateTwinSyntheticQaRun.attempt !==
            syntheticReadAdmission.attempt
        ) {
          return apiError("not found", 404);
        }
        syntheticReadAdmission =
          await requireTemplateTwinSyntheticReadAdmission({
            visitId,
            actorUserId: userId,
            readDecision: projectedReadAuthority,
            expected: syntheticReadAdmission,
          });
        if (!syntheticReadAdmission) return apiError("not found", 404);
      } catch (error) {
        if (error instanceof TemplateTwinSyntheticReadAdmissionError) {
          return apiError("not found", 404);
        }
        throw error;
      }
    }

    let stagingQaRunId: string | null = null;
    let stagingQaAttempt: number | null = null;
    try {
      const stagingAdmission = assertTemplateTwinStagingQaVisitGuard({
        run: visit.templateTwinSyntheticQaRun,
        actor: { userId, practiceId },
        currentRolloutToken: rolloutToken,
        allowedAdmissionPhases: ["SIGNED"],
      });
      stagingQaRunId = stagingAdmission.applies ? stagingAdmission.runId : null;
      stagingQaAttempt = stagingAdmission.applies
        ? visit.templateTwinSyntheticQaRun!.attempt
        : null;
    } catch (error) {
      if (
        error instanceof TemplateTwinStagingQaDisabledError ||
        (error instanceof TemplateTwinStagingQaVisitGuardError &&
          error.code === "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND")
      ) {
        return apiError("not found", 404);
      }
      if (error instanceof TemplateTwinStagingQaVisitGuardError) {
        return apiError(error.message, 409, {
          code: error.code,
          retry: false,
        });
      }
      throw error;
    }

    const automationProof = assessVisitAutomationProof({
      visitId: visit.id,
      practiceId,
      soapVersion: visit.soapVersion,
      soapFinal: visit.soapFinal,
      manifest: visit.automationManifest,
      staging: visit.templateTwinSyntheticQaRun
        ? {
            admissionId: visit.templateTwinSyntheticQaRun.admissionId ?? "",
            runId: visit.templateTwinSyntheticQaRun.id,
            globalGeneration:
              visit.templateTwinSyntheticQaRun.pinnedGlobalRolloutGeneration,
            practiceGeneration:
              visit.templateTwinSyntheticQaRun.pinnedPracticeRolloutGeneration,
          }
        : null,
    });
    if (!automationProof.ready) {
      return apiError(
        "Required visit automation is incomplete. Retry processing before download.",
        409,
        { code: "VISIT_AUTOMATION_INCOMPLETE", retry: true },
      );
    }

    const assessment = assessTemplateTwinSigning({
      visitId: visit.id,
      practiceId,
      actorUserId: userId,
      visitStatus: visit.status,
      soapFinal: visit.soapFinal,
      soapVersion: visit.soapVersion,
      manualRetryCount: visit.manualRetryCount,
      inputMode: visit.inputMode,
      rawTextInput: visit.rawTextInput,
      transcriptText: visit.transcriptText,
      transcriptRaw: visit.transcriptRaw,
      speakerMap: visit.speakerMap,
      templateTwinSyntheticQaRun: visit.templateTwinSyntheticQaRun,
      noteTemplateId: visit.noteTemplateId,
      noteTemplateVersion: visit.noteTemplateVersion,
      noteTemplate: visit.noteTemplate,
      templateTwinFill: visit.templateTwinFill,
    });
    if (!assessment.applies) return apiError("not found", 404);
    if (!assessment.ready || !assessment.claim || !visit.templateTwinFill) {
      log.warn(
        "api:visits:export:original-template-docx",
        "verified output unavailable",
        {
          userId,
          visitId,
          blockerCodes: assessment.blockerCodes,
          blockerCount: assessment.blockerCodes.length,
        },
      );
      try {
        await enqueueTemplateTwinAudit(prisma, {
          eventKey: `template-twin-export-blocked:${visitId}:${randomUUID()}`,
          practiceId,
          actorId: userId,
          actorEmailSnapshot: session.user.email ?? null,
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          targetType: "TranscribeVisit",
          targetId: visitId,
          metadata: {
            reasonCode: "TEMPLATE_TWIN_OUTPUT_UNVERIFIED",
            blockerCodes: [...assessment.blockerCodes],
            blockerCount: assessment.blockerCodes.length,
            compiledVersionId: assessment.compiledVersionId,
            fillManifestId: assessment.fillManifestId,
          },
        });
      } catch {
        return apiError(
          "The export safety decision could not be recorded. Try again.",
          503,
          { code: "TEMPLATE_TWIN_AUDIT_UNAVAILABLE", retry: true },
        );
      }
      return NextResponse.json(
        {
          ok: false,
          error: "The verified Original Template DOCX is not available.",
          code: "TEMPLATE_TWIN_OUTPUT_UNVERIFIED",
        },
        { status: 409 },
      );
    }

    const fill = visit.templateTwinFill;
    if (
      fill.pinnedGlobalRolloutGeneration !== rolloutToken.globalGeneration ||
      fill.pinnedPracticeRolloutGeneration !==
        rolloutToken.practiceGeneration ||
      fill.signedGlobalRolloutGeneration !== rolloutToken.globalGeneration ||
      fill.signedPracticeRolloutGeneration !== rolloutToken.practiceGeneration
    ) {
      try {
        await enqueueTemplateTwinAudit(prisma, {
          eventKey: `template-twin-export-rollout-stale:${visitId}:${randomUUID()}`,
          practiceId,
          actorId: userId,
          actorEmailSnapshot: session.user.email ?? null,
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          targetType: "TranscribeVisit",
          targetId: visitId,
          metadata: {
            reasonCode: "TEMPLATE_TWIN_OUTPUT_ROLLOUT_STALE",
            fillManifestId: fill.id,
            currentGlobalGeneration: rolloutToken.globalGeneration.toString(),
            currentPracticeGeneration:
              rolloutToken.practiceGeneration.toString(),
          },
        });
      } catch {
        return apiError(
          "The export safety decision could not be recorded. Try again.",
          503,
          { code: "TEMPLATE_TWIN_AUDIT_UNAVAILABLE", retry: true },
        );
      }
      return apiError(
        "The Original Template DOCX was generated before rollout changed. Regenerate and sign it again.",
        409,
        { code: "TEMPLATE_TWIN_OUTPUT_ROLLOUT_STALE", retry: true },
      );
    }
    // These columns are proven non-null by assessTemplateTwinSigning. Keep the
    // guard explicit so a future refactor cannot weaken that invariant.
    if (
      !fill.outputObjectKey ||
      !fill.outputVersionId ||
      !fill.outputEtag ||
      !fill.outputSha256 ||
      !fill.outputSizeBytes
    ) {
      return apiError("verified output unavailable", 409);
    }

    let document: Buffer;
    try {
      document = await createTemplateTwinArtifactStore().readOutputArtifact({
        practiceId,
        objectKey: fill.outputObjectKey,
        expectedObjectVersionId: fill.outputVersionId,
        expectedObjectEtag: fill.outputEtag,
        expectedSha256: fill.outputSha256,
        expectedSizeBytes: fill.outputSizeBytes,
      });
    } catch (error) {
      const unavailable = error instanceof TemplateTwinStorageUnavailableError;
      const integrityFailure =
        error instanceof TemplateTwinArtifactIntegrityError ||
        error instanceof TemplateTwinArtifactNotFoundError;
      log.warn(
        "api:visits:export:original-template-docx",
        "artifact read failed",
        {
          userId,
          visitId,
          errorCode: unavailable
            ? "TEMPLATE_TWIN_STORAGE_UNAVAILABLE"
            : integrityFailure
              ? "TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED"
              : "TEMPLATE_TWIN_OUTPUT_READ_FAILED",
        },
      );
      const reasonCode = unavailable
        ? "TEMPLATE_TWIN_STORAGE_UNAVAILABLE"
        : "TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED";
      try {
        await enqueueTemplateTwinAudit(prisma, {
          eventKey: `template-twin-export-blocked:${visitId}:${randomUUID()}`,
          practiceId,
          actorId: userId,
          actorEmailSnapshot: session.user.email ?? null,
          action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
          targetType: "TranscribeVisit",
          targetId: visitId,
          metadata: {
            reasonCode,
            compiledVersionId: assessment.compiledVersionId,
            fillManifestId: assessment.fillManifestId,
          },
        });
      } catch {
        return apiError(
          "The export safety decision could not be recorded. Try again.",
          503,
          { code: "TEMPLATE_TWIN_AUDIT_UNAVAILABLE", retry: true },
        );
      }
      return NextResponse.json(
        {
          ok: false,
          error: unavailable
            ? "Original Template DOCX storage is temporarily unavailable."
            : "The Original Template DOCX failed integrity verification.",
          code: unavailable
            ? "TEMPLATE_TWIN_STORAGE_UNAVAILABLE"
            : "TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED",
        },
        { status: unavailable ? 503 : 409 },
      );
    }

    let finalAuthorization:
      | { allowed: true }
      | { allowed: false; code: string; reason: string };
    try {
      finalAuthorization = await runSerializableTransactionWithRetry({
        prisma,
        operation: "original_template_docx_download_final_claim",
        context: { visitId, practiceId, runId: stagingQaRunId ?? undefined },
        transaction: async (tx: Prisma.TransactionClient) => {
          const finalRollout = await lockTemplateTwinRolloutForFinalClaim({
            tx,
            practiceId,
            pinnedToken: rolloutToken,
          });
          if (!finalRollout.allowed) {
            await enqueueTemplateTwinAudit(tx, {
              eventKey: `template-twin-export-rollout-blocked:${visitId}:${randomUUID()}`,
              practiceId,
              actorId: userId,
              actorEmailSnapshot: session.user.email ?? null,
              action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
              targetType: "TranscribeVisit",
              targetId: visitId,
              metadata: {
                reasonCode: finalRollout.code,
                operation: "download_final_authorization",
                fillManifestId: fill.id,
                ...templateTwinRolloutAuditMetadata(
                  rolloutToken,
                  finalRollout.currentToken,
                ),
              },
            });
            return {
              allowed: false as const,
              code: finalRollout.code,
              reason: finalRollout.reason,
            };
          }
          let lockedStagingRun: LockedStagingQaRunRow | null = null;
          if (stagingQaRunId) {
            try {
              const expectedStagingRun = visit.templateTwinSyntheticQaRun;
              if (
                stagingQaAttempt === null ||
                !expectedStagingRun?.admissionId
              ) {
                throw new TemplateTwinStagingQaVisitGuardError(
                  "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
                  "Synthetic QA attempt identity is unavailable.",
                );
              }
              lockedStagingRun =
                await lockAndAssertTemplateTwinStagingQaOperation({
                  tx,
                  runId: stagingQaRunId,
                  expectedAdmissionId: expectedStagingRun.admissionId,
                  expectedAttempt: stagingQaAttempt,
                  actor: { userId, practiceId },
                  currentRolloutToken: finalRollout.token,
                  allowedStatuses: ["COMPLETED"],
                  allowedAdmissionPhases: ["SIGNED"],
                });
              if (
                !syntheticReadAdmission ||
                !expectedStagingRun.admission ||
                !lockedStagingRun.admission ||
                lockedStagingRun.id !== expectedStagingRun.id ||
                lockedStagingRun.id !== syntheticReadAdmission.runId ||
                lockedStagingRun.admissionId !==
                  expectedStagingRun.admissionId ||
                lockedStagingRun.visitId !== visit.id ||
                lockedStagingRun.visitId !== syntheticReadAdmission.visitId ||
                lockedStagingRun.practiceId !== practiceId ||
                lockedStagingRun.practiceId !==
                  syntheticReadAdmission.practiceId ||
                lockedStagingRun.doctorId !== userId ||
                lockedStagingRun.noteTemplateId !== visit.noteTemplateId ||
                lockedStagingRun.noteTemplateVersion !==
                  visit.noteTemplateVersion ||
                lockedStagingRun.requestSha256 !==
                  expectedStagingRun.requestSha256 ||
                lockedStagingRun.payloadSha256 !==
                  expectedStagingRun.payloadSha256 ||
                lockedStagingRun.mode !== expectedStagingRun.mode ||
                lockedStagingRun.fixtureVersion !==
                  expectedStagingRun.fixtureVersion ||
                lockedStagingRun.pinnedGlobalRolloutGeneration !==
                  expectedStagingRun.pinnedGlobalRolloutGeneration ||
                lockedStagingRun.pinnedPracticeRolloutGeneration !==
                  expectedStagingRun.pinnedPracticeRolloutGeneration ||
                lockedStagingRun.attempt !== syntheticReadAdmission.attempt ||
                lockedStagingRun.admission.id !==
                  expectedStagingRun.admissionId ||
                lockedStagingRun.admission.id !==
                  expectedStagingRun.admission.id ||
                lockedStagingRun.admission.visitId !== visit.id ||
                lockedStagingRun.admission.practiceId !== practiceId ||
                lockedStagingRun.admission.actorId !== userId ||
                lockedStagingRun.admission.parentAdmissionId !==
                  expectedStagingRun.admission.parentAdmissionId ||
                lockedStagingRun.admission.requestSha256 !==
                  expectedStagingRun.admission.requestSha256 ||
                lockedStagingRun.admission.payloadSha256 !==
                  expectedStagingRun.admission.payloadSha256 ||
                lockedStagingRun.admission.providerMode !==
                  expectedStagingRun.admission.providerMode ||
                lockedStagingRun.admission.purpose !==
                  expectedStagingRun.admission.purpose ||
                lockedStagingRun.admission.sourceSha256 !==
                  expectedStagingRun.admission.sourceSha256 ||
                lockedStagingRun.admission.sourceSizeBytes !==
                  expectedStagingRun.admission.sourceSizeBytes ||
                lockedStagingRun.admission.sourceArtifactId !==
                  expectedStagingRun.admission.sourceArtifactId ||
                lockedStagingRun.admission.noteTemplateId !==
                  visit.noteTemplateId ||
                lockedStagingRun.admission.noteTemplateVersion !==
                  visit.noteTemplateVersion ||
                lockedStagingRun.admission.certificationId !==
                  expectedStagingRun.admission.certificationId ||
                lockedStagingRun.admission.mappingSha256 !==
                  expectedStagingRun.admission.mappingSha256 ||
                lockedStagingRun.admission.attempt !== stagingQaAttempt
              ) {
                throw new TemplateTwinStagingQaVisitGuardError(
                  "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
                  "Synthetic QA authority changed before download authorization.",
                );
              }
            } catch (error) {
              if (
                error instanceof TemplateTwinStagingQaDisabledError ||
                error instanceof TemplateTwinStagingQaVisitGuardError
              ) {
                const code = error.code;
                await enqueueTemplateTwinAudit(tx, {
                  eventKey: `template-twin-export-staging-blocked:${visitId}:${code}`,
                  practiceId,
                  actorId: userId,
                  actorEmailSnapshot: session.user.email ?? null,
                  action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
                  targetType: "TranscribeVisit",
                  targetId: visitId,
                  metadata: {
                    reasonCode: code,
                    operation: "staging_download_final_authorization",
                    stagingQaRunId,
                    fillManifestId: fill.id,
                  },
                });
                return {
                  allowed: false as const,
                  code,
                  reason:
                    "Synthetic QA authorization changed before download. Create a new run.",
                };
              }
              throw error;
            }
          }
          await lockAndAssertCurrentTemplateTwinPhysician({
            tx,
            actor: { userId, practiceId },
          });
          await lockAndAssertCurrentTemplateTwinPatient({
            tx,
            patientId: visit.patientId,
            practiceId,
          });

          const lockedVisit = await lockCurrentTemplateTwinVisit(tx, visitId);
          const currentVisitIdentity = await tx.transcribeVisit.findUnique({
            where: { id: visitId },
            select: { manualRetryCount: true },
          });
          if (
            !lockedVisit ||
            !currentVisitIdentity ||
            lockedVisit.id !== visit.id ||
            lockedVisit.userId !== userId ||
            lockedVisit.patientId !== visit.patientId ||
            lockedVisit.status !== TranscribeVisitStatus.SIGNED ||
            lockedVisit.soapVersion !== visit.soapVersion ||
            lockedVisit.soapFinal !== visit.soapFinal ||
            lockedVisit.noteTemplateId !== visit.noteTemplateId ||
            lockedVisit.noteTemplateVersion !== visit.noteTemplateVersion ||
            currentVisitIdentity.manualRetryCount !== visit.manualRetryCount ||
            canonicalSha256({
              inputMode: lockedVisit.inputMode,
              rawTextInput: lockedVisit.rawTextInput,
              transcriptText: lockedVisit.transcriptText,
              transcriptRaw: lockedVisit.transcriptRaw,
              speakerMap: lockedVisit.speakerMap,
            }) !==
              canonicalSha256({
                inputMode: visit.inputMode,
                rawTextInput: visit.rawTextInput,
                transcriptText: visit.transcriptText,
                transcriptRaw: visit.transcriptRaw,
                speakerMap: visit.speakerMap,
              }) ||
            lockedVisit.deletedAt !== null ||
            lockedVisit.archivedAt !== null
          ) {
            return {
              allowed: false as const,
              code: "VISIT_AUTOMATION_PROOF_STALE",
              reason: "Download authorization changed. Refresh and try again.",
            };
          }
          if (
            !persistedTemplateTwinEncounterEvidenceIsValid({
              visit: lockedVisit,
              manifest: fill.fillManifest,
            })
          ) {
            await enqueueTemplateTwinAudit(tx, {
              eventKey: `template-twin-export-evidence-stale:${visitId}:${randomUUID()}`,
              practiceId,
              actorId: userId,
              actorEmailSnapshot: session.user.email ?? null,
              action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
              targetType: "TranscribeVisit",
              targetId: visitId,
              metadata: {
                reasonCode: "ENCOUNTER_EVIDENCE_INVALID",
                operation: "download_final_authorization",
                fillManifestId: fill.id,
              },
            });
            return {
              allowed: false as const,
              code: "TEMPLATE_TWIN_ENCOUNTER_EVIDENCE_STALE",
              reason:
                "The encounter evidence changed before download authorization. Regenerate and review the document.",
            };
          }
          await lockAndAssertVisitAutomationProof({
            tx,
            visitId,
            practiceId,
            soapVersion: lockedVisit.soapVersion,
            soapFinal: lockedVisit.soapFinal,
            staging: lockedStagingRun
              ? {
                  admissionId: lockedStagingRun.admissionId ?? "",
                  runId: lockedStagingRun.id,
                  globalGeneration: finalRollout.token.globalGeneration,
                  practiceGeneration: finalRollout.token.practiceGeneration,
                }
              : null,
          });

          const currentFill = await tx.templateTwinFillManifest.findUnique({
            where: { id: fill.id },
            select: {
              practiceId: true,
              visitId: true,
              compiledVersionId: true,
              noteTemplateId: true,
              noteTemplateVersion: true,
              status: true,
              signedDecisionAt: true,
              outputObjectKey: true,
              outputVersionId: true,
              outputEtag: true,
              outputSha256: true,
              outputSizeBytes: true,
              providerOwnershipEvidence: true,
              providerOwnershipSha256: true,
              pinnedGlobalRolloutGeneration: true,
              pinnedPracticeRolloutGeneration: true,
              signedGlobalRolloutGeneration: true,
              signedPracticeRolloutGeneration: true,
            },
          });
          if (
            !currentFill ||
            currentFill.practiceId !== practiceId ||
            currentFill.practiceId !== fill.practiceId ||
            currentFill.visitId !== visit.id ||
            currentFill.visitId !== fill.visitId ||
            currentFill.compiledVersionId !== assessment.compiledVersionId ||
            currentFill.compiledVersionId !== fill.compiledVersionId ||
            currentFill.noteTemplateId !== visit.noteTemplateId ||
            currentFill.noteTemplateId !== fill.noteTemplateId ||
            currentFill.noteTemplateVersion !== visit.noteTemplateVersion ||
            currentFill.noteTemplateVersion !== fill.noteTemplateVersion ||
            currentFill.status !== "SIGNED" ||
            currentFill.signedDecisionAt === null ||
            currentFill.outputObjectKey !== fill.outputObjectKey ||
            currentFill.outputVersionId !== fill.outputVersionId ||
            currentFill.outputEtag !== fill.outputEtag ||
            currentFill.outputSha256 !== fill.outputSha256 ||
            currentFill.outputSizeBytes !== fill.outputSizeBytes ||
            currentFill.providerOwnershipSha256 !==
              fill.providerOwnershipSha256 ||
            canonicalSha256(currentFill.providerOwnershipEvidence) !==
              canonicalSha256(fill.providerOwnershipEvidence) ||
            currentFill.pinnedGlobalRolloutGeneration !==
              rolloutToken.globalGeneration ||
            currentFill.pinnedPracticeRolloutGeneration !==
              rolloutToken.practiceGeneration ||
            currentFill.signedGlobalRolloutGeneration !==
              rolloutToken.globalGeneration ||
            currentFill.signedPracticeRolloutGeneration !==
              rolloutToken.practiceGeneration
          ) {
            await enqueueTemplateTwinAudit(tx, {
              eventKey: `template-twin-export-claim-stale:${visitId}:${randomUUID()}`,
              practiceId,
              actorId: userId,
              actorEmailSnapshot: session.user.email ?? null,
              action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
              targetType: "TranscribeVisit",
              targetId: visitId,
              metadata: {
                reasonCode: "TEMPLATE_TWIN_OUTPUT_CLAIM_STALE",
                operation: "download_final_authorization",
                fillManifestId: fill.id,
              },
            });
            return {
              allowed: false as const,
              code: "TEMPLATE_TWIN_OUTPUT_CLAIM_STALE",
              reason:
                "The Original Template DOCX changed before download authorization. Refresh and try again.",
            };
          }

          await enqueueTemplateTwinAudit(tx, {
            eventKey: `template-twin-exported:${visitId}:${randomUUID()}`,
            practiceId,
            actorId: userId,
            actorEmailSnapshot: session.user.email ?? null,
            action: "EXPORT_TEMPLATE_TWIN_DOCX_DOWNLOADED",
            targetType: "TranscribeVisit",
            targetId: visitId,
            metadata: {
              sizeBytes: document.byteLength,
              compiledVersionId: assessment.compiledVersionId,
              fillManifestId: assessment.fillManifestId,
              noteTemplateVersion: visit.noteTemplateVersion,
              rolloutGlobalGeneration: rolloutToken.globalGeneration.toString(),
              rolloutPracticeGeneration:
                rolloutToken.practiceGeneration.toString(),
            },
          });
          return { allowed: true as const };
        },
      });
    } catch (error) {
      if (error instanceof TemplateTwinCurrentPhysicianAuthorityError) {
        return apiError(
          "Current physician authorization is required for Template Twin.",
          403,
          { code: error.code, retry: false },
        );
      }
      if (error instanceof VisitAutomationIncompleteError) {
        return apiError(
          "Required visit automation changed before download. Retry processing.",
          409,
          { code: "VISIT_AUTOMATION_INCOMPLETE", retry: true },
        );
      }
      return apiError("The export could not be recorded. Try again.", 503, {
        code: "TEMPLATE_TWIN_AUDIT_UNAVAILABLE",
        retry: true,
      });
    }
    if (!finalAuthorization.allowed) {
      return apiError(finalAuthorization.reason, 409, {
        code: finalAuthorization.code,
        retry: true,
      });
    }
    logDelivery({
      visitId,
      channel: "docx_original_template",
      sizeBytes: document.byteLength,
    });

    return new NextResponse(document as unknown as BodyInit, {
      status: 200,
      headers: {
        "Content-Type": DOCX_MIME_TYPE,
        "Content-Length": String(document.byteLength),
        "Content-Disposition": `attachment; filename="quillmd-original-template-${visitId}.docx"`,
        "Cache-Control": "no-store, private",
        "X-Content-Type-Options": "nosniff",
      },
    });
  },
);
