import { Prisma } from "@prisma/client";

import { TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID } from "./synthetic-qa-patient";

export type TemplateTwinClinicalMutationAuthorizationCode =
  | "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED"
  | "TEMPLATE_TWIN_MUTATION_PROVENANCE_INVALID"
  | "TEMPLATE_TWIN_MUTATION_ROLLOUT_REVOKED"
  | "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED";

/** Fixed, PHI-free denial for generic visit mutation boundaries. */
export class TemplateTwinClinicalMutationAuthorizationError extends Error {
  constructor(readonly code: TemplateTwinClinicalMutationAuthorizationCode) {
    super("Current Template Twin mutation authorization is required.");
    this.name = "TemplateTwinClinicalMutationAuthorizationError";
  }
}

/**
 * Final fence for a mutation admitted on the ordinary (non-Twin) path.
 *
 * The actor's canonical active practice and exact current physician row are
 * locked before the template, patient, and visit to serialize suspension,
 * deactivation, entitlement removal, account deletion, and practice transfer
 * against the write. Compiled lineage is checked independently of mutable
 * kind. The visit lock then proves the exact admitted owner/epoch and excludes
 * every durable Twin marker in the same database statement. Foreign-key
 * writers for fill/run/admission/provider evidence cannot cross the visit lock
 * before the caller's transaction commits.
 */
export async function lockAndAssertOrdinaryClinicalMutation(input: {
  tx: Prisma.TransactionClient;
  visitId: string;
  actorUserId: string;
  admittedVisitUpdatedAt: Date;
  admittedPatientId: string;
  admittedNoteTemplateId: string | null;
}): Promise<void> {
  const practices = await input.tx.$queryRaw<
    Array<{ id: string; isActive: boolean }>
  >(Prisma.sql`
    SELECT practice."id", practice."isActive"
    FROM "practices" practice
    WHERE practice."id" = (
      SELECT actor."practiceId"
      FROM "users" actor
      WHERE actor."id" = ${input.actorUserId}
    )
      AND practice."isActive" = TRUE
    FOR UPDATE
  `);
  const practice = practices[0];
  if (
    practices.length !== 1 ||
    !practice ||
    typeof practice.id !== "string" ||
    practice.id.length === 0 ||
    !practice.isActive
  ) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
    );
  }

  const actors = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT actor."id"
    FROM "users" actor
    WHERE actor."id" = ${input.actorUserId}
      AND actor."practiceId" = ${practice.id}
      AND actor."role" = 'DOCTOR'::"UserRole"
      AND actor."isActive" = TRUE
      AND actor."deactivatedAt" IS NULL
      AND actor."suspendedAt" IS NULL
      AND actor."softDeletedAt" IS NULL
      AND 'TRANSCRIBE_MD'::"Product" = ANY(actor."products")
    FOR UPDATE
  `);
  if (actors.length !== 1 || actors[0]?.id !== input.actorUserId) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_NOT_AUTHORIZED",
    );
  }

  if (input.admittedNoteTemplateId !== null) {
    const template = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
      SELECT template."id"
      FROM "note_templates" template
      WHERE template."id" = ${input.admittedNoteTemplateId}
        AND template."templateKind" <> 'template_twin_docx'
        AND NOT EXISTS (
          SELECT 1
          FROM "template_twin_compiled_versions" compiled
          WHERE compiled."noteTemplateId" = template."id"
        )
      FOR UPDATE
    `);
    if (
      template.length !== 1 ||
      template[0]?.id !== input.admittedNoteTemplateId
    ) {
      throw new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
      );
    }
  }

  const ordinary = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT visit."id"
    FROM "transcribe_visits" visit
    JOIN "transcribe_md_patients" patient
      ON patient."id" = visit."patientId"
    WHERE visit."id" = ${input.visitId}
      AND visit."userId" = ${input.actorUserId}
      AND visit."updatedAt" = ${input.admittedVisitUpdatedAt}
      AND visit."patientId" = ${input.admittedPatientId}
      AND visit."noteTemplateId" IS NOT DISTINCT FROM ${input.admittedNoteTemplateId}
      AND patient."practiceId" = ${practice.id}
      AND patient."externalId" IS DISTINCT FROM ${TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID}
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_fill_manifests" fill
        WHERE fill."visitId" = visit."id"
      )
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_synthetic_qa_runs" run
        WHERE run."visitId" = visit."id"
      )
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_synthetic_qa_admissions" admission
        WHERE admission."visitId" = visit."id"
      )
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_provider_executions" execution
        WHERE execution."visitId" = visit."id"
      )
    FOR UPDATE OF patient, visit
  `);
  if (ordinary.length !== 1 || ordinary[0]?.id !== input.visitId) {
    throw new TemplateTwinClinicalMutationAuthorizationError(
      "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
    );
  }
}
