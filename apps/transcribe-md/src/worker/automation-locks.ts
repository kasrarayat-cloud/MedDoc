import {
  assertTemplateTwinSyntheticQaWorkerLeaseHealthy,
  getTemplateTwinSyntheticQaProviderContext,
} from "@meddoc/ai";
import prisma from "@meddoc/db";
import { Prisma, TranscribeVisitStatus } from "@prisma/client";

import { runSerializableTransactionWithRetry } from "@/lib/db/transaction-retry";
import {
  getTemplateTwinProviderOwnershipContext,
  type TemplateTwinProviderOwnershipContext,
} from "@/lib/template-twin/provider-ownership";
import { templateTwinVisitProviderSubjectSha256 } from "@/lib/template-twin/live-provider-ownership";
import {
  lockTemplateTwinRolloutForFinalClaim,
  TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID,
} from "@/lib/template-twin/rollout";
import { lockAndAssertTemplateTwinStagingQaAttempt } from "@/lib/template-twin/staging-qa-visit-guard";
import {
  TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
  TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_NAME,
} from "@/lib/template-twin/synthetic-qa-patient";

export const VISIT_AUTOMATION_CANONICAL_LOCK_ORDER = [
  "global_rollout",
  "practice",
  "staging_admission",
  "staging_run",
  "actor",
  "template",
  "compiled_version",
  "source_artifact",
  "certification",
  "patient",
  "visit",
  "automation_manifest",
  "automation_layers",
  "provider_execution",
  "audit_outbox",
] as const;

export interface LockedAutomationVisit {
  id: string;
  patientId: string;
  userId: string;
  status: TranscribeVisitStatus;
  soapVersion: number;
  soapFinal: string | null;
  reviewReason: string | null;
  deletedAt: Date | null;
  archivedAt: Date | null;
  inputMode: string;
  noteTemplateId: string | null;
  noteTemplateVersion: number | null;
  manualRetryCount: number;
}

interface LockedAutomationActor {
  id: string;
  practiceId: string;
  role: string;
  isActive: boolean;
  deactivatedAt: Date | null;
  suspendedAt: Date | null;
  softDeletedAt: Date | null;
  products: string[];
}

interface LockedAutomationTemplate {
  id: string;
  version: number;
  doctorId: string | null;
  templateKind: string;
  status: string;
}

interface LockedAutomationCompilation {
  id: string;
  noteTemplateId: string;
  sourceArtifactId: string;
  certificationStatus: string;
  providerOwnershipSha256: string | null;
}

interface LockedAutomationSource {
  id: string;
  practiceId: string;
  createdById: string | null;
  lineageId: string;
  lineageVersion: number;
  sha256: string;
  validationStatus: string;
  providerOwnershipSha256: string | null;
}

interface LockedAutomationCertification {
  id: string;
  compiledVersionId: string;
  certifiedById: string;
  providerAuthorizationMode: string;
  providerAuthorizationAdmissionId: string | null;
}

interface LockedAutomationPatient {
  id: string;
  practiceId: string;
  externalId: string | null;
  deletedAt: Date | null;
}

interface LockedSyntheticAutomationPatient extends LockedAutomationPatient {
  name: string;
  dateOfBirth: Date | null;
  mrn: string | null;
  insurance: string | null;
  problemList: unknown | null;
  weightKg: number | null;
  allergies: string[];
}

const liveAuthorityRejectionProof = Symbol(
  "visit-automation-live-authority-rejection",
);

interface LiveAuthorityIdentity {
  readonly practiceId: string;
  readonly userId: string;
  readonly visitId: string;
  readonly noteTemplateId: string;
  readonly noteTemplateVersion: number;
  readonly inputMode: string;
  readonly compiledVersionId: string;
  readonly sourceArtifactId: string;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
  readonly logicalAttempt: number;
  readonly subjectSha256: string;
}

function visitPipelineAuthorityIdentity(
  context: TemplateTwinProviderOwnershipContext,
): LiveAuthorityIdentity | null {
  if (context.scope !== "VISIT_PIPELINE") return null;
  if (
    context.visitId === null ||
    context.visitInputMode === null ||
    context.noteTemplateId === null ||
    context.noteTemplateVersion === null ||
    context.compiledVersionId === null ||
    context.sourceArtifactId === null ||
    context.sourceLineageId === null ||
    context.sourceLineageVersion === null ||
    context.sourceSha256 === null
  ) {
    throw new VisitAutomationLockError();
  }
  const identity: LiveAuthorityIdentity = {
    practiceId: context.practiceId,
    userId: context.actorUserId,
    visitId: context.visitId,
    noteTemplateId: context.noteTemplateId,
    noteTemplateVersion: context.noteTemplateVersion,
    inputMode: context.visitInputMode,
    compiledVersionId: context.compiledVersionId,
    sourceArtifactId: context.sourceArtifactId,
    sourceLineageId: context.sourceLineageId,
    sourceLineageVersion: context.sourceLineageVersion,
    sourceSha256: context.sourceSha256,
    logicalAttempt: context.logicalAttempt,
    subjectSha256: context.subjectSha256,
  };
  if (
    context.subjectId !== context.visitId ||
    context.subjectSha256 !==
      templateTwinVisitProviderSubjectSha256({
        practiceId: identity.practiceId,
        actorUserId: identity.userId,
        visitId: identity.visitId,
        noteTemplateId: identity.noteTemplateId,
        noteTemplateVersion: identity.noteTemplateVersion,
        compiledVersionId: identity.compiledVersionId,
        sourceArtifactId: identity.sourceArtifactId,
        sourceLineageId: identity.sourceLineageId,
        sourceLineageVersion: identity.sourceLineageVersion,
        sourceSha256: identity.sourceSha256,
        logicalAttempt: identity.logicalAttempt,
        visitInputMode: identity.inputMode,
      })
  ) {
    throw new VisitAutomationLockError();
  }
  return identity;
}

function liveAuthorityIdentity(
  context: TemplateTwinProviderOwnershipContext,
): LiveAuthorityIdentity | null {
  const identity = visitPipelineAuthorityIdentity(context);
  return context.syntheticAdmissionId === null ? identity : null;
}

function assertVisitPipelineContextMatchesInput(input: {
  context: TemplateTwinProviderOwnershipContext;
  visitId: string;
  userId: string;
  practiceId: string;
}): LiveAuthorityIdentity | null {
  if (input.context.scope !== "VISIT_PIPELINE") return null;
  if (
    input.context.practiceId !== input.practiceId ||
    input.context.actorUserId !== input.userId ||
    input.context.visitId !== input.visitId ||
    input.context.rolloutToken.practiceId !== input.practiceId
  ) {
    throw new VisitAutomationLockError();
  }
  // Validate the immutable visit/template/source subject even for synthetic
  // contexts. Only the LIVE branch returns it to the live compilation locks.
  visitPipelineAuthorityIdentity(input.context);
  return liveAuthorityIdentity(input.context);
}

function syntheticAuthorityIdentity(input: {
  providerContext: TemplateTwinProviderOwnershipContext | null;
  syntheticContext: NonNullable<
    ReturnType<typeof getTemplateTwinSyntheticQaProviderContext>
  >;
  visitId: string;
  userId: string;
  practiceId: string;
}): LiveAuthorityIdentity {
  const provider = input.providerContext;
  const synthetic = input.syntheticContext;
  const identity = provider ? visitPipelineAuthorityIdentity(provider) : null;
  if (
    !provider ||
    !identity ||
    provider.practiceId !== input.practiceId ||
    provider.actorUserId !== input.userId ||
    provider.visitId !== input.visitId ||
    provider.syntheticAdmissionId !== synthetic.admissionId ||
    provider.logicalAttempt !== synthetic.attempt ||
    provider.rolloutToken.practiceId !== synthetic.practiceId ||
    provider.rolloutToken.globalGeneration !==
      synthetic.pinnedGlobalGeneration ||
    provider.rolloutToken.practiceGeneration !==
      synthetic.pinnedPracticeGeneration ||
    synthetic.practiceId !== input.practiceId ||
    synthetic.visitId !== input.visitId
  ) {
    throw new VisitAutomationLockError();
  }
  return identity;
}

function sameLiveRolloutAuthority(
  context: TemplateTwinProviderOwnershipContext,
  token: TemplateTwinProviderOwnershipContext["rolloutToken"],
): boolean {
  return (
    token.practiceId === context.practiceId &&
    token.globalGeneration === context.rolloutToken.globalGeneration &&
    token.practiceGeneration === context.rolloutToken.practiceGeneration &&
    token.releaseId === context.rolloutToken.releaseId &&
    token.releaseIdentitySha256 ===
      context.rolloutToken.releaseIdentitySha256 &&
    token.runtimeManifestSha256 ===
      context.rolloutToken.runtimeManifestSha256 &&
    token.runtimeInstanceId === context.rolloutToken.runtimeInstanceId
  );
}

function actorOwnsLiveAutomation(
  actor: LockedAutomationActor | undefined,
  identity: LiveAuthorityIdentity,
): boolean {
  return (
    actor?.id === identity.userId &&
    actor.practiceId === identity.practiceId &&
    actor.role === "DOCTOR" &&
    actor.isActive === true &&
    actor.deactivatedAt === null &&
    actor.suspendedAt === null &&
    actor.softDeletedAt === null &&
    actor.products.includes("TRANSCRIBE_MD")
  );
}

function templateOwnsLiveAutomation(
  template: LockedAutomationTemplate | undefined,
  identity: LiveAuthorityIdentity,
): boolean {
  return (
    template?.id === identity.noteTemplateId &&
    template.version === identity.noteTemplateVersion &&
    template.doctorId === identity.userId &&
    template.templateKind === "template_twin_docx" &&
    (template.status === "active" || template.status === "inactive")
  );
}

function compilationOwnsLiveAutomation(
  compilation: LockedAutomationCompilation | undefined,
  identity: LiveAuthorityIdentity,
): boolean {
  return (
    compilation?.id === identity.compiledVersionId &&
    compilation.noteTemplateId === identity.noteTemplateId &&
    compilation.sourceArtifactId === identity.sourceArtifactId &&
    compilation.certificationStatus === "CERTIFIED" &&
    compilation.providerOwnershipSha256 !== null
  );
}

function sourceOwnsLiveAutomation(
  source: LockedAutomationSource | undefined,
  identity: LiveAuthorityIdentity,
): boolean {
  return (
    source?.id === identity.sourceArtifactId &&
    source.practiceId === identity.practiceId &&
    source.createdById === identity.userId &&
    source.lineageId === identity.sourceLineageId &&
    source.lineageVersion === identity.sourceLineageVersion &&
    source.sha256 === identity.sourceSha256 &&
    source.validationStatus === "accepted" &&
    source.providerOwnershipSha256 !== null
  );
}

function certificationOwnsLiveAutomation(
  certification: LockedAutomationCertification | undefined,
  identity: LiveAuthorityIdentity,
): boolean {
  return (
    certification?.compiledVersionId === identity.compiledVersionId &&
    certification.certifiedById === identity.userId &&
    certification.providerAuthorizationMode === "LIVE" &&
    certification.providerAuthorizationAdmissionId === null
  );
}

function visitOwnsLiveAutomation(
  visit: LockedAutomationVisit | undefined,
  identity: LiveAuthorityIdentity,
): visit is LockedAutomationVisit {
  return (
    visit?.id === identity.visitId &&
    visit.userId === identity.userId &&
    visit.inputMode === identity.inputMode &&
    visit.noteTemplateId === identity.noteTemplateId &&
    visit.noteTemplateVersion === identity.noteTemplateVersion &&
    visit.manualRetryCount + 1 === identity.logicalAttempt &&
    visit.deletedAt === null &&
    visit.archivedAt === null
  );
}

function patientOwnsLiveAutomation(
  patient: LockedAutomationPatient | undefined,
  visit: LockedAutomationVisit | undefined,
  identity: LiveAuthorityIdentity,
): boolean {
  return (
    patient !== undefined &&
    visit !== undefined &&
    patient.id === visit.patientId &&
    patient.practiceId === identity.practiceId &&
    patient.deletedAt === null &&
    patient.externalId !== TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID
  );
}

function patientOwnsSyntheticAutomation(
  patient: LockedSyntheticAutomationPatient | undefined,
  visit: LockedAutomationVisit | undefined,
  identity: LiveAuthorityIdentity,
): boolean {
  return (
    patient !== undefined &&
    visit !== undefined &&
    patient.id === visit.patientId &&
    patient.practiceId === identity.practiceId &&
    patient.name === TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_NAME &&
    patient.externalId === TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID &&
    patient.dateOfBirth === null &&
    patient.mrn === null &&
    patient.insurance === null &&
    patient.problemList === null &&
    patient.weightKg === null &&
    patient.allergies.length === 0 &&
    patient.deletedAt === null
  );
}

/** Admission/run/actor locks must already be held. Resolve patient identity
 * without a lock, then lock patient before visit and recheck the binding. */
async function lockAndAssertSyntheticPatientThenVisit(input: {
  tx: Prisma.TransactionClient;
  identity: LiveAuthorityIdentity;
}): Promise<LockedAutomationVisit> {
  const visitIdentities = await input.tx.$queryRaw<
    Array<{ patientId: string }>
  >(Prisma.sql`
    SELECT "patientId"
    FROM "transcribe_visits"
    WHERE "id" = ${input.identity.visitId}
  `);
  const patientId = visitIdentities[0]?.patientId;
  const patients = patientId
    ? await input.tx.$queryRaw<LockedSyntheticAutomationPatient[]>(Prisma.sql`
        SELECT "id", "practiceId", "name", "externalId", "dateOfBirth",
          "mrn", "insurance", "problemList", "weightKg", "allergies",
          "deletedAt"
        FROM "transcribe_md_patients"
        WHERE "id" = ${patientId}
        FOR UPDATE
      `)
    : [];
  const visit = await lockVisit({
    tx: input.tx,
    visitId: input.identity.visitId,
    userId: input.identity.userId,
  });
  if (
    !visitOwnsLiveAutomation(visit, input.identity) ||
    !patientOwnsSyntheticAutomation(patients[0], visit, input.identity)
  ) {
    throw new VisitAutomationLockError();
  }
  return visit;
}

async function lockLiveAuthorityRows(input: {
  tx: Prisma.TransactionClient;
  identity: LiveAuthorityIdentity;
}): Promise<{
  actor: LockedAutomationActor | undefined;
  template: LockedAutomationTemplate | undefined;
  compilation: LockedAutomationCompilation | undefined;
  source: LockedAutomationSource | undefined;
  certification: LockedAutomationCertification | undefined;
  liveProviderCompilationValid: boolean;
  patient: LockedAutomationPatient | undefined;
  visit: LockedAutomationVisit | undefined;
}> {
  const actors = await input.tx.$queryRaw<LockedAutomationActor[]>(Prisma.sql`
    SELECT "id", "practiceId", "role", "isActive", "deactivatedAt",
      "suspendedAt", "softDeletedAt", "products"
    FROM "users"
    WHERE "id" = ${input.identity.userId}
    FOR UPDATE
  `);
  const templates = await input.tx.$queryRaw<LockedAutomationTemplate[]>(
    Prisma.sql`
      SELECT "id", "version", "doctorId", "templateKind", "status"
      FROM "note_templates"
      WHERE "id" = ${input.identity.noteTemplateId}
      FOR UPDATE
    `,
  );
  const compilations = await input.tx.$queryRaw<
    LockedAutomationCompilation[]
  >(Prisma.sql`
    SELECT "id", "noteTemplateId", "sourceArtifactId",
      "certificationStatus", "providerOwnershipSha256"
    FROM "template_twin_compiled_versions"
    WHERE "id" = ${input.identity.compiledVersionId}
    FOR UPDATE
  `);
  const sources = await input.tx.$queryRaw<LockedAutomationSource[]>(Prisma.sql`
    SELECT "id", "practiceId", "createdById", "lineageId", "lineageVersion",
      "sha256", "validationStatus", "providerOwnershipSha256"
    FROM "template_twin_source_artifacts"
    WHERE "id" = ${input.identity.sourceArtifactId}
    FOR UPDATE
  `);
  const certifications = await input.tx.$queryRaw<
    LockedAutomationCertification[]
  >(Prisma.sql`
    SELECT "id", "compiledVersionId", "certifiedById",
      "providerAuthorizationMode", "providerAuthorizationAdmissionId"
    FROM "template_twin_certifications"
    WHERE "compiledVersionId" = ${input.identity.compiledVersionId}
    FOR UPDATE
  `);
  const receiptValidity = await input.tx.$queryRaw<Array<{ valid: boolean }>>(
    Prisma.sql`
      SELECT public.template_twin_live_provider_compilation_is_valid(
        ${input.identity.compiledVersionId}, ${input.identity.userId}
      ) AS "valid"
    `,
  );
  // Resolve the patient identity without a lock, then acquire patient before
  // visit. The locked visit must still reference that exact patient below, so
  // a concurrent reassignment loses closed without inverting patient -> visit.
  const visitIdentities = await input.tx.$queryRaw<
    Array<{ patientId: string }>
  >(Prisma.sql`
    SELECT "patientId"
    FROM "transcribe_visits"
    WHERE "id" = ${input.identity.visitId}
  `);
  const patientId = visitIdentities[0]?.patientId;
  const patients = patientId
    ? await input.tx.$queryRaw<LockedAutomationPatient[]>(Prisma.sql`
        SELECT "id", "practiceId", "externalId", "deletedAt"
        FROM "transcribe_md_patients"
        WHERE "id" = ${patientId}
        FOR UPDATE
      `)
    : [];
  const visits = await input.tx.$queryRaw<LockedAutomationVisit[]>(Prisma.sql`
    SELECT
      "id", "patientId", "userId", "status", "soapVersion", "soapFinal", "reviewReason",
      "deletedAt", "archivedAt", "inputMode", "noteTemplateId",
      "noteTemplateVersion", "manualRetryCount"
    FROM "transcribe_visits"
    WHERE "id" = ${input.identity.visitId}
    FOR UPDATE
  `);
  return {
    actor: actors[0],
    template: templates[0],
    compilation: compilations[0],
    source: sources[0],
    certification: certifications[0],
    liveProviderCompilationValid: receiptValidity[0]?.valid === true,
    patient: patients[0],
    visit: visits[0],
  };
}

async function lockAndAssessLiveAuthority(input: {
  tx: Prisma.TransactionClient;
  context: TemplateTwinProviderOwnershipContext;
  identity: LiveAuthorityIdentity;
}): Promise<{
  allowed: boolean;
  visit: LockedAutomationVisit | undefined;
}> {
  const rollout = await lockTemplateTwinRolloutForFinalClaim({
    tx: input.tx,
    practiceId: input.identity.practiceId,
    pinnedToken: input.context.rolloutToken,
  });
  const rows = await lockLiveAuthorityRows(input);
  const allowed =
    rollout.allowed &&
    sameLiveRolloutAuthority(input.context, rollout.token) &&
    actorOwnsLiveAutomation(rows.actor, input.identity) &&
    templateOwnsLiveAutomation(rows.template, input.identity) &&
    compilationOwnsLiveAutomation(rows.compilation, input.identity) &&
    sourceOwnsLiveAutomation(rows.source, input.identity) &&
    certificationOwnsLiveAutomation(rows.certification, input.identity) &&
    rows.liveProviderCompilationValid &&
    patientOwnsLiveAutomation(rows.patient, rows.visit, input.identity) &&
    visitOwnsLiveAutomation(rows.visit, input.identity);
  return { allowed, visit: rows.visit };
}

async function lockOrdinaryScope(input: {
  tx: Prisma.TransactionClient;
  visitId: string;
  userId: string;
  practiceId: string;
  beforeVisitLock?: (tx: Prisma.TransactionClient) => Promise<void>;
}): Promise<LockedAutomationVisit> {
  const practices = await input.tx.$queryRaw<
    Array<{ id: string; isActive: boolean }>
  >(Prisma.sql`
    SELECT "id", "isActive"
    FROM "practices"
    WHERE "id" = ${input.practiceId}
    FOR UPDATE
  `);
  const practice = practices[0];
  if (
    practices.length !== 1 ||
    practice?.id !== input.practiceId ||
    practice.isActive !== true
  ) {
    throw new VisitAutomationLockError();
  }

  const actors = await input.tx.$queryRaw<LockedAutomationActor[]>(Prisma.sql`
    SELECT "id", "practiceId", "role", "isActive", "deactivatedAt",
      "suspendedAt", "softDeletedAt", "products"
    FROM "users"
    WHERE "id" = ${input.userId}
    FOR UPDATE
  `);
  const actor = actors[0];
  if (
    actor?.id !== input.userId ||
    actor.practiceId !== input.practiceId ||
    actor.role !== "DOCTOR" ||
    actor.isActive !== true ||
    actor.deactivatedAt !== null ||
    actor.suspendedAt !== null ||
    actor.softDeletedAt !== null ||
    !actor.products.includes("TRANSCRIBE_MD")
  ) {
    throw new VisitAutomationLockError();
  }
  await input.beforeVisitLock?.(input.tx);
  return lockVisit(input);
}

async function lockVisit(input: {
  tx: Prisma.TransactionClient;
  visitId: string;
  userId: string;
}): Promise<LockedAutomationVisit> {
  const visits = await input.tx.$queryRaw<LockedAutomationVisit[]>(Prisma.sql`
    SELECT
      "id", "patientId", "userId", "status", "soapVersion", "soapFinal", "reviewReason",
      "deletedAt", "archivedAt", "inputMode", "noteTemplateId",
      "noteTemplateVersion", "manualRetryCount"
    FROM "transcribe_visits"
    WHERE "id" = ${input.visitId}
    FOR UPDATE
  `);
  const visit = visits[0];
  if (!visit || visit.userId !== input.userId) {
    throw new VisitAutomationLockError();
  }
  return visit;
}

export class VisitAutomationLockError extends Error {
  readonly code = "VISIT_AUTOMATION_LOCK_REJECTED" as const;

  constructor() {
    super("The visit automation transaction no longer owns this visit.");
    this.name = "VisitAutomationLockError";
  }
}

/**
 * An internal proof that the exact live Template Twin authority failed while
 * its transaction held the relevant authority rows. The constructor requires
 * a module-private token so other call sites cannot manufacture permission to
 * enter the fail-only ledger terminalization path.
 */
export class VisitAutomationLiveAuthorityRevokedError extends VisitAutomationLockError {
  readonly authorityIdentity: LiveAuthorityIdentity;
  readonly [liveAuthorityRejectionProof] = true;

  constructor(
    identity: LiveAuthorityIdentity,
    proof: typeof liveAuthorityRejectionProof,
  ) {
    super();
    if (proof !== liveAuthorityRejectionProof)
      throw new VisitAutomationLockError();
    this.name = "VisitAutomationLiveAuthorityRevokedError";
    this.authorityIdentity = Object.freeze({ ...identity });
  }
}

function liveAuthorityRevoked(
  identity: LiveAuthorityIdentity,
): VisitAutomationLiveAuthorityRevokedError {
  return new VisitAutomationLiveAuthorityRevokedError(
    identity,
    liveAuthorityRejectionProof,
  );
}

function sameLiveAuthorityIdentity(
  left: LiveAuthorityIdentity,
  right: LiveAuthorityIdentity,
): boolean {
  return (
    left.practiceId === right.practiceId &&
    left.userId === right.userId &&
    left.visitId === right.visitId &&
    left.noteTemplateId === right.noteTemplateId &&
    left.noteTemplateVersion === right.noteTemplateVersion &&
    left.inputMode === right.inputMode &&
    left.compiledVersionId === right.compiledVersionId &&
    left.sourceArtifactId === right.sourceArtifactId &&
    left.sourceLineageId === right.sourceLineageId &&
    left.sourceLineageVersion === right.sourceLineageVersion &&
    left.sourceSha256 === right.sourceSha256 &&
    left.logicalAttempt === right.logicalAttempt &&
    left.subjectSha256 === right.subjectSha256
  );
}

/**
 * Converts only the caller's exact RESERVED/IN_FLIGHT provider row to a
 * result-free terminal state after a proven live-authority rejection. The
 * callback is deliberately unavailable without the module-issued rejection
 * proof. It takes the same rollout -> practice -> actor -> template -> visit
 * locks, but can never restore authority or project a provider result.
 */
export async function runVisitAutomationRevokedAuthorityTerminalization<
  T,
>(input: {
  operation: string;
  visitId: string;
  userId: string;
  practiceId: string;
  rejection: VisitAutomationLiveAuthorityRevokedError;
  transaction: (tx: Prisma.TransactionClient) => Promise<T>;
}): Promise<T> {
  const context = getTemplateTwinProviderOwnershipContext();
  if (!context) throw new VisitAutomationLockError();
  const identity = assertVisitPipelineContextMatchesInput({
    context,
    visitId: input.visitId,
    userId: input.userId,
    practiceId: input.practiceId,
  });
  if (
    !identity ||
    input.rejection[liveAuthorityRejectionProof] !== true ||
    !sameLiveAuthorityIdentity(identity, input.rejection.authorityIdentity)
  ) {
    throw new VisitAutomationLockError();
  }

  return runSerializableTransactionWithRetry({
    prisma,
    operation: input.operation,
    context: {
      visitId: input.visitId,
      practiceId: input.practiceId,
    },
    transaction: async (tx) => {
      // The process kill switch is evaluated before database I/O in the normal
      // rollout helper, so the fail-only path acquires these two canonical
      // locks explicitly even when that switch caused the rejection.
      await tx.$queryRaw(Prisma.sql`
        SELECT "id"
        FROM "template_twin_rollout_controls"
        WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
        FOR UPDATE
      `);
      await tx.$queryRaw(Prisma.sql`
        SELECT "id"
        FROM "practices"
        WHERE "id" = ${identity.practiceId}
        FOR UPDATE
      `);
      await lockLiveAuthorityRows({ tx, identity });
      return input.transaction(tx);
    },
  });
}

/**
 * Executes one idempotent automation database transaction under the shared
 * lock order. Provider calls and object writes must happen before this helper.
 */
export async function runVisitAutomationTransaction<T>(input: {
  operation: string;
  visitId: string;
  userId: string;
  practiceId: string;
  /** Ordinary-only lock extension. Runs inside the retryable transaction
   * after practice/actor locks and before the canonical visit lock. */
  ordinaryBeforeVisitLock?: (tx: Prisma.TransactionClient) => Promise<void>;
  transaction: (
    tx: Prisma.TransactionClient,
    visit: LockedAutomationVisit,
  ) => Promise<T>;
}): Promise<T> {
  const context = getTemplateTwinSyntheticQaProviderContext();
  const providerContext = getTemplateTwinProviderOwnershipContext();
  const liveIdentity = providerContext
    ? assertVisitPipelineContextMatchesInput({
        context: providerContext,
        visitId: input.visitId,
        userId: input.userId,
        practiceId: input.practiceId,
      })
    : null;
  const syntheticIdentity = context
    ? syntheticAuthorityIdentity({
        providerContext,
        syntheticContext: context,
        visitId: input.visitId,
        userId: input.userId,
        practiceId: input.practiceId,
      })
    : null;
  if (context) {
    if (
      context.visitId !== input.visitId ||
      context.practiceId !== input.practiceId
    ) {
      throw new VisitAutomationLockError();
    }
    assertTemplateTwinSyntheticQaWorkerLeaseHealthy();
  }

  return runSerializableTransactionWithRetry({
    prisma,
    operation: input.operation,
    context: {
      visitId: input.visitId,
      practiceId: input.practiceId,
      runId: context?.runId,
    },
    transaction: async (tx) => {
      let visit: LockedAutomationVisit;
      if (context) {
        const rollout = await lockTemplateTwinRolloutForFinalClaim({
          tx,
          practiceId: input.practiceId,
          pinnedToken: {
            practiceId: input.practiceId,
            globalGeneration: context.pinnedGlobalGeneration,
            practiceGeneration: context.pinnedPracticeGeneration,
          },
        });
        if (!rollout.allowed) throw new VisitAutomationLockError();
        await lockAndAssertTemplateTwinStagingQaAttempt({
          tx,
          currentRolloutToken: rollout.token,
          claim: {
            admissionId: context.admissionId,
            runId: context.runId,
            visitId: context.visitId,
            practiceId: context.practiceId,
            doctorId: input.userId,
            sourceArtifactId: providerContext?.sourceArtifactId ?? undefined,
            noteTemplateId: providerContext?.noteTemplateId ?? undefined,
            noteTemplateVersion:
              providerContext?.noteTemplateVersion ?? undefined,
            fixtureVersion: context.fixtureVersion,
            requestSha256: context.requestSha256,
            attempt: context.attempt,
            workerClaimId: context.workerClaimId,
            pinnedGlobalGeneration: context.pinnedGlobalGeneration,
            pinnedPracticeGeneration: context.pinnedPracticeGeneration,
          },
          allowedStatuses: ["PROCESSING"],
          allowedAdmissionPhases: ["PROCESSING"],
          requireLiveWorkerLease: true,
        });
        // lockAndAssert... acquired admission -> run -> actor; preserve the
        // canonical actor -> patient -> visit order for the final L7 claim.
        visit = await lockAndAssertSyntheticPatientThenVisit({
          tx,
          identity: syntheticIdentity!,
        });
      } else if (providerContext && liveIdentity) {
        const authority = await lockAndAssessLiveAuthority({
          tx,
          context: providerContext,
          identity: liveIdentity,
        });
        if (!authority.allowed || !authority.visit) {
          throw liveAuthorityRevoked(liveIdentity);
        }
        visit = authority.visit;
      } else {
        visit = await lockOrdinaryScope({
          tx,
          visitId: input.visitId,
          userId: input.userId,
          practiceId: input.practiceId,
          beforeVisitLock: input.ordinaryBeforeVisitLock,
        });
      }
      if (visit.deletedAt !== null || visit.archivedAt !== null) {
        throw new VisitAutomationLockError();
      }
      return input.transaction(tx, visit);
    },
  });
}
