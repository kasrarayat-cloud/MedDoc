import { createHash, randomUUID } from "node:crypto";

import {
  assertTemplateTwinSyntheticQaProviderEnvironment,
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
} from "@meddoc/ai";
import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";

import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";

import { enqueueTemplateTwinAudit } from "./audit-outbox";
import { canonicalSha256 } from "./canonical";
import { lockAndAssertCurrentTemplateTwinPhysician } from "./final-claim-authority";
import {
  buildTemplateTwinProviderOwnershipReceipt,
  runTemplateTwinOwnedTranscribe,
  runWithTemplateTwinProviderOwnershipContext,
  templateTwinSyntheticVoiceSubjectSha256,
  type TemplateTwinProviderOwnershipContext,
  type TemplateTwinSyntheticVoiceSubjectIdentity,
} from "./provider-ownership";
import {
  lockTemplateTwinRolloutForFinalClaim,
  pinTemplateTwinRollout,
} from "./rollout";
import {
  lockAndAssertTemplateTwinStagingQaAdmission,
  markTemplateTwinStagingQaAdmissionFailed,
  runWithVerifiedTemplateTwinStagingQaAdmissionProvider,
  TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT,
  TEMPLATE_TWIN_STAGING_QA_ADMISSION_TTL_MS,
  TemplateTwinStagingQaAdmissionError,
  type TemplateTwinStagingQaAdmissionActor,
  type TemplateTwinStagingQaAdmissionRow,
} from "./staging-qa-admission";
import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from "./staging-qa-fixture-contract";
import { TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT } from "./staging-qa-fixtures";
import { assertTemplateTwinStagingQaGate } from "./staging-qa-gate";
import {
  confirmTemplateTwinStagingQaMappings,
  type TemplateTwinStagingQaExpectedMappingConfirmation,
} from "./staging-qa-mapping-confirmation";
import {
  TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
  TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_NAME,
} from "./synthetic-qa-patient";

const SHA256 = /^[a-f0-9]{64}$/u;
const SAFE_AUDIO_MIME = /^audio\/[a-z0-9.+-]{1,60}$/u;

export class TemplateTwinSyntheticVoiceProviderError extends Error {
  readonly code = "TEMPLATE_TWIN_SYNTHETIC_VOICE_UNAVAILABLE" as const;

  constructor(options?: ErrorOptions) {
    super("The synthetic voice review is unavailable.", options);
    this.name = "TemplateTwinSyntheticVoiceProviderError";
  }
}

export interface TemplateTwinSyntheticVoiceReservation {
  readonly admission: TemplateTwinStagingQaAdmissionRow;
  readonly parentAdmissionId: string;
  readonly visitId: string;
  readonly visitInputMode: string;
  readonly visitStatus: string;
  readonly visitUserId: string;
  readonly visitNoteTemplateId: string | null;
  readonly visitNoteTemplateVersion: number | null;
  readonly visitAudioKey: string | null;
  readonly visitAudioMimeType: string | null;
  readonly visitAudioSizeBytes: number | null;
  readonly visitDeletedAt: Date | null;
  readonly visitArchivedAt: Date | null;
  readonly visitSignedAt: Date | null;
  readonly patientPracticeId: string;
  readonly patientName: string;
  readonly patientExternalId: string | null;
  readonly patientDeletedAt: Date | null;
  readonly compiledVersionId: string;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
}

function unavailable(cause?: unknown): TemplateTwinSyntheticVoiceProviderError {
  return new TemplateTwinSyntheticVoiceProviderError(
    cause === undefined ? undefined : { cause },
  );
}

function sameRollout(
  actor: TemplateTwinStagingQaAdmissionActor,
  token: Awaited<ReturnType<typeof pinTemplateTwinRollout>>,
): boolean {
  return (
    token.practiceId === actor.practiceId &&
    token.globalGeneration === actor.rolloutToken.globalGeneration &&
    token.practiceGeneration === actor.rolloutToken.practiceGeneration &&
    token.releaseId === actor.rolloutToken.releaseId &&
    token.releaseIdentitySha256 === actor.rolloutToken.releaseIdentitySha256 &&
    token.runtimeManifestSha256 === actor.rolloutToken.runtimeManifestSha256 &&
    token.runtimeInstanceId === actor.rolloutToken.runtimeInstanceId
  );
}

export function assertTemplateTwinSyntheticVoiceReservation(input: {
  readonly reservation: TemplateTwinSyntheticVoiceReservation;
  readonly actor: Pick<
    TemplateTwinStagingQaAdmissionActor,
    "userId" | "practiceId"
  >;
  readonly noteTemplateId: string;
  readonly audio: {
    sha256: string;
    sizeBytes: number;
    mimeType: string;
  };
  readonly now?: Date;
}): TemplateTwinSyntheticVoiceReservation {
  const row = input.reservation;
  const admission = row.admission;
  const now = input.now ?? new Date();
  const expectedObjectKey =
    `template-twin-synthetic-voice/${admission.practiceId}/` +
    `${admission.actorId}/${admission.id}/${input.audio.sha256}`;
  if (
    admission.practiceId !== input.actor.practiceId ||
    admission.actorId !== input.actor.userId ||
    admission.parentAdmissionId !== row.parentAdmissionId ||
    admission.purpose !== "VISIT" ||
    admission.providerMode !== "SYNTHETIC_MOCK_VOICE" ||
    admission.phase !== "VISIT_LINKED" ||
    admission.attempt !== 1 ||
    !admission.preCertificationVoiceEvidence ||
    admission.certificationId !== null ||
    admission.mappingSha256 !== null ||
    admission.failedAt !== null ||
    admission.revokedAt !== null ||
    admission.consumedAt !== null ||
    admission.expiresAt <= now ||
    admission.noteTemplateId !== input.noteTemplateId ||
    admission.visitId !== row.visitId ||
    admission.audioSha256 !== input.audio.sha256 ||
    admission.audioSizeBytes !== input.audio.sizeBytes ||
    admission.audioMimeType !== input.audio.mimeType ||
    admission.audioObjectKey !== expectedObjectKey ||
    admission.sourceSha256 !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 ||
    admission.sourceSizeBytes !== TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES ||
    admission.fixtureVersion !== TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION ||
    row.visitInputMode !== "audio_upload" ||
    row.visitStatus !== "QUEUED" ||
    row.visitUserId !== input.actor.userId ||
    row.visitNoteTemplateId !== admission.noteTemplateId ||
    row.visitNoteTemplateVersion !== admission.noteTemplateVersion ||
    row.visitAudioKey !== expectedObjectKey ||
    row.visitAudioMimeType !== input.audio.mimeType ||
    row.visitAudioSizeBytes !== input.audio.sizeBytes ||
    row.visitDeletedAt !== null ||
    row.visitArchivedAt !== null ||
    row.visitSignedAt !== null ||
    row.patientPracticeId !== input.actor.practiceId ||
    row.patientName !== TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_NAME ||
    row.patientExternalId !== TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID ||
    row.patientDeletedAt !== null ||
    admission.sourceSha256 !== row.sourceSha256
  ) {
    throw unavailable();
  }
  return row;
}

async function readReservation(
  tx: Prisma.TransactionClient,
  admissionId: string,
): Promise<TemplateTwinSyntheticVoiceReservation | null> {
  const admission = await tx.templateTwinSyntheticQaAdmission.findUnique({
    where: { id: admissionId },
    select: {
      ...TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT,
      visit: {
        select: {
          id: true,
          inputMode: true,
          status: true,
          userId: true,
          noteTemplateId: true,
          noteTemplateVersion: true,
          audioKey: true,
          audioMimeType: true,
          audioSizeBytes: true,
          deletedAt: true,
          archivedAt: true,
          signedAt: true,
          patient: {
            select: {
              practiceId: true,
              name: true,
              externalId: true,
              deletedAt: true,
            },
          },
        },
      },
      noteTemplate: {
        select: {
          templateTwinCompiledVersion: {
            select: {
              id: true,
              sourceArtifact: {
                select: {
                  lineageId: true,
                  lineageVersion: true,
                  sha256: true,
                },
              },
            },
          },
        },
      },
    },
  });
  const visit = admission?.visit;
  const patient = visit?.patient;
  const compiled = admission?.noteTemplate?.templateTwinCompiledVersion;
  const source = compiled?.sourceArtifact;
  if (
    !admission ||
    !admission.parentAdmissionId ||
    !visit ||
    !patient ||
    !compiled ||
    !source
  ) {
    return null;
  }
  return {
    admission,
    parentAdmissionId: admission.parentAdmissionId,
    visitId: visit.id,
    visitInputMode: visit.inputMode,
    visitStatus: visit.status,
    visitUserId: visit.userId,
    visitNoteTemplateId: visit.noteTemplateId,
    visitNoteTemplateVersion: visit.noteTemplateVersion,
    visitAudioKey: visit.audioKey,
    visitAudioMimeType: visit.audioMimeType,
    visitAudioSizeBytes: visit.audioSizeBytes,
    visitDeletedAt: visit.deletedAt,
    visitArchivedAt: visit.archivedAt,
    visitSignedAt: visit.signedAt,
    patientPracticeId: patient.practiceId,
    patientName: patient.name,
    patientExternalId: patient.externalId,
    patientDeletedAt: patient.deletedAt,
    compiledVersionId: compiled.id,
    sourceLineageId: source.lineageId,
    sourceLineageVersion: source.lineageVersion,
    sourceSha256: source.sha256,
  };
}

async function lockAndAssertSyntheticVoiceFinalClaim(input: {
  readonly tx: Prisma.TransactionClient;
  readonly actor: TemplateTwinStagingQaAdmissionActor;
  readonly reservation: TemplateTwinSyntheticVoiceReservation;
  readonly noteTemplateId: string;
  readonly audio: { sha256: string; sizeBytes: number; mimeType: string };
}): Promise<TemplateTwinSyntheticVoiceReservation> {
  const rollout = await lockTemplateTwinRolloutForFinalClaim({
    tx: input.tx,
    practiceId: input.actor.practiceId,
    pinnedToken: input.actor.rolloutToken,
  });
  if (!rollout.allowed || !sameRollout(input.actor, rollout.token)) {
    throw unavailable();
  }
  await lockAndAssertCurrentTemplateTwinPhysician({
    tx: input.tx,
    actor: input.actor,
  });
  const child = await lockAndAssertTemplateTwinStagingQaAdmission({
    tx: input.tx,
    admissionId: input.reservation.admission.id,
    actor: input.actor,
    currentToken: rollout.token,
    allowedPhases: ["VISIT_LINKED"],
    expectedProviderMode: "SYNTHETIC_MOCK_VOICE",
    expectedTemplate: {
      id: input.noteTemplateId,
      version: input.reservation.admission.noteTemplateVersion!,
    },
    expectedVisitId: input.reservation.visitId,
    expectedParentAdmissionId: input.reservation.parentAdmissionId,
    expectedPurpose: "VISIT",
    expectedAttempt: 1,
    expectedPreCertificationVoiceAudio: {
      ...input.audio,
      objectKey: input.reservation.admission.audioObjectKey!,
    },
  });

  const authority = await input.tx.$queryRaw<Array<{ parentId: string }>>(
    Prisma.sql`
      SELECT parent."id" AS "parentId"
      FROM "template_twin_synthetic_qa_admissions" child
      JOIN "template_twin_synthetic_qa_admissions" parent
        ON parent."id" = child."parentAdmissionId"
      JOIN "transcribe_visits" visit ON visit."id" = child."visitId"
      JOIN "transcribe_md_patients" patient ON patient."id" = visit."patientId"
      JOIN "note_templates" template ON template."id" = child."noteTemplateId"
      JOIN "template_twin_compiled_versions" compiled
        ON compiled."noteTemplateId" = template."id"
      JOIN "template_twin_source_artifacts" source
        ON source."id" = compiled."sourceArtifactId"
      JOIN "template_twin_quarantine_artifacts" quarantine
        ON quarantine."id" = source."quarantineArtifactId"
      WHERE child."id" = ${child.id}
        AND child."preCertificationVoiceEvidence" = TRUE
        AND child."practiceId" = ${input.actor.practiceId}
        AND child."actorId" = ${input.actor.userId}
        AND child."purpose" = 'VISIT'
        AND child."providerMode" = 'SYNTHETIC_MOCK_VOICE'
        AND child."phase" = 'VISIT_LINKED'
        AND child."attempt" = 1
        AND child."certificationId" IS NULL
        AND child."mappingSha256" IS NULL
        AND child."consumedAt" IS NULL
        AND child."audioSha256" = ${input.audio.sha256}
        AND child."audioSizeBytes" = ${input.audio.sizeBytes}
        AND child."audioMimeType" = ${input.audio.mimeType}
        AND child."audioObjectKey" = ${child.audioObjectKey}
        AND parent."practiceId" = child."practiceId"
        AND parent."actorId" = child."actorId"
        AND parent."purpose" = 'UPLOAD'
        AND parent."providerMode" = 'SYNTHETIC_LIFECYCLE'
        AND parent."preCertificationVoiceEvidence" = FALSE
        AND parent."phase" = 'TEMPLATE_LINKED'
        AND parent."sourceSha256" = child."sourceSha256"
        AND parent."sourceSizeBytes" = child."sourceSizeBytes"
        AND parent."fixtureVersion" = child."fixtureVersion"
        AND parent."sourceArtifactId" = child."sourceArtifactId"
        AND parent."noteTemplateId" = child."noteTemplateId"
        AND parent."noteTemplateVersion" = child."noteTemplateVersion"
        AND parent."certificationId" IS NULL
        AND parent."mappingSha256" IS NULL
        AND parent."visitId" IS NULL
        AND parent."failedAt" IS NULL
        AND parent."revokedAt" IS NULL
        AND parent."consumedAt" IS NULL
        AND parent."expiresAt" > clock_timestamp()
        AND parent."pinnedGlobalRolloutGeneration" =
          child."pinnedGlobalRolloutGeneration"
        AND parent."pinnedPracticeRolloutGeneration" =
          child."pinnedPracticeRolloutGeneration"
        AND visit."userId" = child."actorId"
        AND visit."patientName" = 'Template Twin Synthetic QA'
        AND visit."inputMode" = 'audio_upload'
        AND visit."status" = 'QUEUED'
        AND visit."audioKey" = child."audioObjectKey"
        AND visit."audioMimeType" = child."audioMimeType"
        AND visit."audioSizeBytes" = child."audioSizeBytes"
        AND visit."audioUploadedAt" IS NOT NULL
        AND visit."dictationAudioKey" IS NULL
        AND visit."rawTextInput" IS NULL
        AND visit."noteTemplateId" = child."noteTemplateId"
        AND visit."noteTemplateVersion" = child."noteTemplateVersion"
        AND visit."deletedAt" IS NULL
        AND visit."archivedAt" IS NULL
        AND visit."signedAt" IS NULL
        AND patient."practiceId" = child."practiceId"
        AND patient."name" = 'Template Twin Synthetic QA'
        AND patient."externalId" = 'SYNTHETIC-QA-ONLY'
        AND patient."dateOfBirth" IS NULL
        AND patient."mrn" IS NULL
        AND patient."insurance" IS NULL
        AND patient."problemList" IS NULL
        AND patient."weightKg" IS NULL
        AND cardinality(patient."allergies") = 0
        AND patient."deletedAt" IS NULL
        AND template."doctorId" = child."actorId"
        AND template."version" = child."noteTemplateVersion"
        AND template."templateKind" = 'template_twin_docx'
        AND compiled."id" = ${input.reservation.compiledVersionId}
        AND compiled."sourceArtifactId" = child."sourceArtifactId"
        AND compiled."certificationStatus" <> 'CERTIFIED'
        AND source."practiceId" = child."practiceId"
        AND source."validationStatus" = 'accepted'
        AND source."sha256" = child."sourceSha256"
        AND source."sizeBytes" = child."sourceSizeBytes"
        AND source."lineageId" = ${input.reservation.sourceLineageId}
        AND source."lineageVersion" = ${input.reservation.sourceLineageVersion}
        AND quarantine."practiceId" = child."practiceId"
        AND quarantine."intakeMode" = 'NATIVE_TEMPLATE'
        AND quarantine."status" = 'ADMITTED'
        AND quarantine."sha256" = child."sourceSha256"
        AND quarantine."sizeBytes" = child."sourceSizeBytes"
      FOR UPDATE OF parent
      FOR SHARE OF visit, patient, template, compiled, source, quarantine
    `,
  );
  if (
    authority.length !== 1 ||
    authority[0]?.parentId !== input.reservation.parentAdmissionId
  ) {
    throw unavailable();
  }
  const current = await readReservation(input.tx, child.id);
  if (!current) throw unavailable();
  return assertTemplateTwinSyntheticVoiceReservation({
    reservation: current,
    actor: input.actor,
    noteTemplateId: input.noteTemplateId,
    audio: input.audio,
  });
}

async function reserveSyntheticVoice(input: {
  readonly actor: TemplateTwinStagingQaAdmissionActor;
  readonly noteTemplateId: string;
  readonly audio: { sha256: string; sizeBytes: number; mimeType: string };
  readonly expectedMappingConfirmation: TemplateTwinStagingQaExpectedMappingConfirmation;
}): Promise<TemplateTwinSyntheticVoiceReservation> {
  const requestSha256 = canonicalSha256({
    contractVersion: "template-twin-synthetic-voice-request-v1",
    practiceId: input.actor.practiceId,
    actorUserId: input.actor.userId,
    noteTemplateId: input.noteTemplateId,
    audio: input.audio,
    expectedMappingConfirmation: input.expectedMappingConfirmation,
  });
  const payloadSha256 = canonicalSha256({
    contractVersion: "template-twin-synthetic-voice-payload-v1",
    sourceSha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
    sourceSizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
    audio: input.audio,
    expectedMappingConfirmation: input.expectedMappingConfirmation,
  });

  return runSerializableTransactionWithRetry({
    prisma,
    operation: "reserve_template_twin_synthetic_voice",
    context: { practiceId: input.actor.practiceId },
    transaction: async (tx: Prisma.TransactionClient) => {
      const rollout = await lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.actor.practiceId,
        pinnedToken: input.actor.rolloutToken,
      });
      if (!rollout.allowed || !sameRollout(input.actor, rollout.token)) {
        throw unavailable();
      }
      // Serialize the exact browser/audio request before the read/create pair.
      // This turns concurrent duplicates into one committed child/visit rather
      // than relying on a unique-violation being classified as serialization.
      await tx.$queryRaw(Prisma.sql`
        SELECT pg_advisory_xact_lock(
          hashtextextended(${requestSha256}, 0)
        )
      `);
      const existing = await tx.templateTwinSyntheticQaAdmission.findFirst({
        where: {
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          requestSha256,
        },
        select: { id: true },
      });
      if (existing) {
        const reservation = await readReservation(tx, existing.id);
        if (!reservation) throw unavailable();
        assertTemplateTwinSyntheticVoiceReservation({
          reservation,
          actor: input.actor,
          noteTemplateId: input.noteTemplateId,
          audio: input.audio,
        });
        return lockAndAssertSyntheticVoiceFinalClaim({
          tx,
          actor: input.actor,
          reservation,
          noteTemplateId: input.noteTemplateId,
          audio: input.audio,
        });
      }

      const template = await tx.noteTemplate.findFirst({
        where: {
          id: input.noteTemplateId,
          doctorId: input.actor.userId,
          templateKind: "template_twin_docx",
          templateTwinCompiledVersion: {
            is: {
              certificationStatus: { not: "CERTIFIED" },
              sourceArtifact: {
                is: {
                  practiceId: input.actor.practiceId,
                  validationStatus: "accepted",
                  sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
                  sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
                  quarantineArtifact: {
                    is: {
                      practiceId: input.actor.practiceId,
                      intakeMode: "NATIVE_TEMPLATE",
                      status: "ADMITTED",
                      sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
                      sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
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
          encounterType: true,
          templateTwinCompiledVersion: {
            select: {
              id: true,
              sourceArtifactId: true,
              sourceArtifact: {
                select: {
                  lineageId: true,
                  lineageVersion: true,
                  sha256: true,
                },
              },
            },
          },
        },
      });
      const compiled = template?.templateTwinCompiledVersion;
      if (!template || !compiled) throw unavailable();

      const now = new Date();
      const parent = await tx.templateTwinSyntheticQaAdmission.findFirst({
        where: {
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          purpose: "UPLOAD",
          providerMode: "SYNTHETIC_LIFECYCLE",
          phase: "TEMPLATE_LINKED",
          attempt: 1,
          sourceSha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
          sourceSizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
          fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
          sourceArtifactId: compiled.sourceArtifactId,
          noteTemplateId: template.id,
          noteTemplateVersion: template.version,
          certificationId: null,
          mappingSha256: null,
          visitId: null,
          failedAt: null,
          revokedAt: null,
          consumedAt: null,
          expiresAt: { gt: now },
          pinnedGlobalRolloutGeneration: rollout.token.globalGeneration,
          pinnedPracticeRolloutGeneration: rollout.token.practiceGeneration,
          preCertificationVoiceEvidence: false,
          audioSha256: null,
          audioSizeBytes: null,
          audioMimeType: null,
          audioObjectKey: null,
        },
        orderBy: { createdAt: "desc" },
        select: TEMPLATE_TWIN_STAGING_QA_ADMISSION_SELECT,
      });
      if (!parent) throw unavailable();

      const patientId = `ttqa-${canonicalSha256({
        contractVersion: "template-twin-synthetic-qa-patient-v1",
        practiceId: input.actor.practiceId,
        doctorId: input.actor.userId,
      }).slice(0, 40)}`;
      const patient = await tx.transcribeMdPatient.upsert({
        where: { id: patientId },
        create: {
          id: patientId,
          practiceId: input.actor.practiceId,
          name: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_NAME,
          externalId: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
        },
        update: {},
        select: {
          id: true,
          practiceId: true,
          name: true,
          externalId: true,
          dateOfBirth: true,
          mrn: true,
          insurance: true,
          problemList: true,
          weightKg: true,
          allergies: true,
          deletedAt: true,
        },
      });
      if (
        patient.practiceId !== input.actor.practiceId ||
        patient.name !== TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_NAME ||
        patient.externalId !== TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID ||
        patient.dateOfBirth !== null ||
        patient.mrn !== null ||
        patient.insurance !== null ||
        patient.problemList !== null ||
        patient.weightKg !== null ||
        patient.allergies.length !== 0 ||
        patient.deletedAt !== null
      ) {
        throw unavailable();
      }

      const admissionId = randomUUID();
      const visitId = randomUUID();
      const audioObjectKey =
        `template-twin-synthetic-voice/${input.actor.practiceId}/` +
        `${input.actor.userId}/${admissionId}/${input.audio.sha256}`;
      const admission = await tx.templateTwinSyntheticQaAdmission.create({
        data: {
          id: admissionId,
          practiceId: input.actor.practiceId,
          actorId: input.actor.userId,
          parentAdmissionId: parent.id,
          sourceSha256: parent.sourceSha256,
          sourceSizeBytes: parent.sourceSizeBytes,
          fixtureVersion: parent.fixtureVersion,
          providerMode: "SYNTHETIC_MOCK_VOICE",
          purpose: "VISIT",
          phase: "ADMITTED",
          requestSha256,
          payloadSha256,
          preCertificationVoiceEvidence: true,
          audioSha256: input.audio.sha256,
          audioSizeBytes: input.audio.sizeBytes,
          audioMimeType: input.audio.mimeType,
          audioObjectKey,
          pinnedGlobalRolloutGeneration: rollout.token.globalGeneration,
          pinnedPracticeRolloutGeneration: rollout.token.practiceGeneration,
          sourceArtifactId: parent.sourceArtifactId,
          noteTemplateId: parent.noteTemplateId,
          noteTemplateVersion: parent.noteTemplateVersion,
          expiresAt: new Date(
            now.getTime() + TEMPLATE_TWIN_STAGING_QA_ADMISSION_TTL_MS,
          ),
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
      await tx.transcribeVisit.create({
        data: {
          id: visitId,
          userId: input.actor.userId,
          patientId: patient.id,
          patientName: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_NAME,
          specialty: template.encounterType ?? "synthetic-template-review",
          chiefComplaint: "Synthetic Template Twin voice review only",
          inputMode: "audio_upload",
          status: TranscribeVisitStatus.QUEUED,
          audioKey: audioObjectKey,
          audioMimeType: input.audio.mimeType,
          audioSizeBytes: input.audio.sizeBytes,
          audioUploadedAt: now,
          noteTemplateId: template.id,
          noteTemplateVersion: template.version,
        },
      });
      await tx.templateTwinSyntheticQaAdmission.update({
        where: { id: admission.id },
        data: { phase: "VISIT_LINKED", visitId, visitLinkedAt: now },
      });
      await enqueueTemplateTwinAudit(tx, {
        eventKey: `template-twin:synthetic-voice:reserved:${admission.id}`,
        practiceId: input.actor.practiceId,
        actorId: input.actor.userId,
        actorEmailSnapshot: input.actor.userEmail ?? null,
        action: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_CREATED",
        targetType: "TemplateTwinSyntheticQaAdmission",
        targetId: admission.id,
        metadata: {
          purpose: "VISIT",
          providerMode: "SYNTHETIC_MOCK_VOICE",
          phase: "VISIT_LINKED",
          parentAdmissionId: parent.id,
          visitId,
          noteTemplateId: template.id,
          noteTemplateVersion: template.version,
          audioSha256: input.audio.sha256,
          audioSizeBytes: input.audio.sizeBytes,
          audioMimeType: input.audio.mimeType,
        },
      });
      const reservation = await readReservation(tx, admission.id);
      if (!reservation) throw unavailable();
      assertTemplateTwinSyntheticVoiceReservation({
        reservation,
        actor: input.actor,
        noteTemplateId: input.noteTemplateId,
        audio: input.audio,
      });
      return lockAndAssertSyntheticVoiceFinalClaim({
        tx,
        actor: input.actor,
        reservation,
        noteTemplateId: input.noteTemplateId,
        audio: input.audio,
      });
    },
  });
}

export async function transcribeTemplateTwinSyntheticVoice(input: {
  readonly noteTemplateId: string;
  readonly actor: TemplateTwinStagingQaAdmissionActor;
  readonly audio: Buffer;
  readonly audioSha256: string;
  readonly mimeType: string;
  readonly expectedMappingConfirmation: TemplateTwinStagingQaExpectedMappingConfirmation;
}): Promise<{ readonly transcript: string }> {
  if (
    !Buffer.isBuffer(input.audio) ||
    input.audio.byteLength < 1 ||
    !SHA256.test(input.audioSha256) ||
    createHash("sha256").update(input.audio).digest("hex") !==
      input.audioSha256 ||
    !SAFE_AUDIO_MIME.test(input.mimeType)
  ) {
    throw unavailable();
  }
  try {
    assertTemplateTwinStagingQaGate(process.env);
    assertTemplateTwinSyntheticQaProviderEnvironment(process.env);
    const token = await pinTemplateTwinRollout({
      practiceId: input.actor.practiceId,
    });
    if (!sameRollout(input.actor, token)) throw unavailable();
    const mappingsConfirmed = await confirmTemplateTwinStagingQaMappings({
      noteTemplateId: input.noteTemplateId,
      doctorId: input.actor.userId,
      practiceId: input.actor.practiceId,
      source: {
        sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
        sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
      },
      expected: input.expectedMappingConfirmation,
    });
    if (!mappingsConfirmed) throw unavailable();
  } catch (error) {
    if (error instanceof TemplateTwinSyntheticVoiceProviderError) throw error;
    throw unavailable(error);
  }

  let reservation: TemplateTwinSyntheticVoiceReservation;
  try {
    reservation = await reserveSyntheticVoice({
      actor: input.actor,
      noteTemplateId: input.noteTemplateId,
      audio: {
        sha256: input.audioSha256,
        sizeBytes: input.audio.byteLength,
        mimeType: input.mimeType,
      },
      expectedMappingConfirmation: input.expectedMappingConfirmation,
    });
  } catch (error) {
    if (error instanceof TemplateTwinSyntheticVoiceProviderError) throw error;
    throw unavailable(error);
  }

  const admission = reservation.admission;
  const audioIdentity = {
    sha256: input.audioSha256,
    sizeBytes: input.audio.byteLength,
    mimeType: input.mimeType,
    objectKey: admission.audioObjectKey!,
  };
  const subjectIdentity: TemplateTwinSyntheticVoiceSubjectIdentity = {
    admissionId: admission.id,
    parentAdmissionId: reservation.parentAdmissionId,
    practiceId: input.actor.practiceId,
    actorUserId: input.actor.userId,
    visitId: reservation.visitId,
    inputMode: "audio_upload",
    audioSha256: input.audioSha256,
    audioSizeBytes: input.audio.byteLength,
    audioMimeType: input.mimeType,
    audioObjectKey: audioIdentity.objectKey,
    sourceArtifactId: admission.sourceArtifactId!,
    compiledVersionId: reservation.compiledVersionId,
    noteTemplateId: admission.noteTemplateId!,
    noteTemplateVersion: admission.noteTemplateVersion!,
    sourceLineageId: reservation.sourceLineageId,
    sourceLineageVersion: reservation.sourceLineageVersion,
    sourceSha256: reservation.sourceSha256,
    logicalAttempt: 1,
  };
  const context: TemplateTwinProviderOwnershipContext = {
    practiceId: input.actor.practiceId,
    actorUserId: input.actor.userId,
    visitId: reservation.visitId,
    visitInputMode: "audio_upload",
    scope: "SYNTHETIC_EVIDENCE",
    logicalAttempt: 1,
    subjectId: admission.id,
    subjectSha256: templateTwinSyntheticVoiceSubjectSha256(subjectIdentity),
    sourceArtifactId: admission.sourceArtifactId,
    compiledVersionId: reservation.compiledVersionId,
    noteTemplateId: admission.noteTemplateId,
    noteTemplateVersion: admission.noteTemplateVersion,
    sourceLineageId: reservation.sourceLineageId,
    sourceLineageVersion: reservation.sourceLineageVersion,
    sourceSha256: reservation.sourceSha256,
    syntheticAdmissionId: admission.id,
    rolloutToken: input.actor.rolloutToken,
  };

  try {
    const result = await runWithVerifiedTemplateTwinStagingQaAdmissionProvider({
      admissionId: admission.id,
      actor: input.actor,
      allowedPhases: ["VISIT_LINKED"],
      expectedProviderMode: "SYNTHETIC_MOCK_VOICE",
      expectedSource: {
        sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
        sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
      },
      expectedTemplate: {
        id: input.noteTemplateId,
        version: admission.noteTemplateVersion!,
      },
      expectedVisitId: reservation.visitId,
      expectedParentAdmissionId: reservation.parentAdmissionId,
      expectedPurpose: "VISIT",
      expectedAttempt: 1,
      expectedPreCertificationVoiceAudio: audioIdentity,
      evidenceText: TEMPLATE_TWIN_STAGING_QA_VOICE_TRANSCRIPT,
      operation: async (providerVisitId) => {
        if (providerVisitId !== reservation.visitId) throw unavailable();
        return runWithTemplateTwinProviderOwnershipContext(
          context,
          async () => {
            const transcription = await runTemplateTwinOwnedTranscribe({
              operation: "SYNTHETIC_EVIDENCE_TRANSCRIPTION",
              operationVersion: "synthetic-evidence-transcription-v1",
              audioIdentity: {
                objectKey: audioIdentity.objectKey,
                objectEtag: input.audioSha256,
                sha256: input.audioSha256,
                sizeBytes: input.audio.byteLength,
                lastModifiedIso: admission.createdAt.toISOString(),
              },
              args: {
                practiceId: input.actor.practiceId,
                userId: input.actor.userId,
                visitId: reservation.visitId,
                purpose: "tm_transcribe",
                audio: input.audio,
                mimeType: input.mimeType,
                allowCrossProviderFallback: false,
                deepgram: {
                  maxAttempts: 1,
                  options: { diarize: false, utterances: false },
                },
              },
            });
            const receipt = buildTemplateTwinProviderOwnershipReceipt({
              projection: {
                subjectId: context.subjectId,
                subjectSha256: context.subjectSha256,
                visitId: context.visitId,
                sourceArtifactId: context.sourceArtifactId,
                compiledVersionId: context.compiledVersionId,
                noteTemplateId: context.noteTemplateId,
              },
              expectedExecutionPlan: [
                {
                  operation: "SYNTHETIC_EVIDENCE_TRANSCRIPTION",
                  disposition: "EXECUTED",
                },
              ],
            });
            if (
              receipt.evidence.providerMode !== "SYNTHETIC_QA" ||
              receipt.evidence.syntheticAdmissionId !== admission.id ||
              receipt.evidence.logicalAttempt !== 1 ||
              receipt.evidence.visitInputMode !== "audio_upload"
            ) {
              throw unavailable();
            }
            return transcription;
          },
        );
      },
    });

    // Final locked read prevents returning a transcript after concurrent
    // parent/child/visit revocation or identity drift.
    await prisma.$transaction(
      async (tx: Prisma.TransactionClient) => {
        await lockAndAssertSyntheticVoiceFinalClaim({
          tx,
          actor: input.actor,
          reservation,
          noteTemplateId: input.noteTemplateId,
          audio: {
            sha256: input.audioSha256,
            sizeBytes: input.audio.byteLength,
            mimeType: input.mimeType,
          },
        });
      },
      { isolationLevel: Prisma.TransactionIsolationLevel.Serializable },
    );
    return { transcript: result.transcript };
  } catch (error) {
    try {
      await markTemplateTwinStagingQaAdmissionFailed({
        admissionId: admission.id,
        actor: input.actor,
        failureCode: "SYNTHETIC_VOICE_PROVIDER_FAILED",
      });
    } catch {
      // The caller still receives a closed capability even when terminal audit
      // persistence is unavailable. The provider ledger prevents replay.
    }
    if (error instanceof TemplateTwinSyntheticVoiceProviderError) throw error;
    if (error instanceof TemplateTwinStagingQaAdmissionError) {
      throw unavailable(error);
    }
    throw unavailable(error);
  }
}
