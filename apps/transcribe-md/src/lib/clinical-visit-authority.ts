import prisma from "@meddoc/db";
import { Prisma } from "@prisma/client";

/**
 * Same-statement actor, product, lifecycle, practice, and patient-tenant
 * predicate for every visit query that projects clinical data or storage
 * locators. A request-start session or an earlier identifier-only admission is
 * never sufficient because either can race a suspension or practice transfer.
 */
export function currentClinicalVisitActorWhere(
  actorUserId: string,
): Prisma.TranscribeVisitWhereInput {
  const currentActor = {
    id: actorUserId,
    role: "DOCTOR" as const,
    isActive: true,
    deactivatedAt: null,
    suspendedAt: null,
    softDeletedAt: null,
    products: { has: "TRANSCRIBE_MD" as const },
  };
  return {
    userId: actorUserId,
    user: { is: currentActor },
    patient: {
      is: {
        practice: {
          is: {
            isActive: true,
            users: { some: currentActor },
          },
        },
      },
    },
  };
}

interface CurrentOrdinaryDeliveryQueryClient {
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
}

export interface CurrentOrdinaryVisitDeliveryActor {
  id: string;
  practiceId: string;
  email: string;
}

/**
 * Final query-native authority claim for ordinary visit delivery.
 *
 * This intentionally does not consult Template Twin rollout. It proves in one
 * locking statement that the visit is still ordinary, its current owner is an
 * active TranscribeMD physician, the practice is active, and the patient still
 * belongs to that same practice. The current database email is returned for an
 * immediately following physician-only email side effect.
 */
export async function claimCurrentOrdinaryVisitDeliveryActor(
  input: { visitId: string; actorUserId: string },
  db: CurrentOrdinaryDeliveryQueryClient = prisma,
): Promise<CurrentOrdinaryVisitDeliveryActor | null> {
  if (!input.visitId || !input.actorUserId) return null;
  const rows = await db.$queryRaw<CurrentOrdinaryVisitDeliveryActor[]>(
    Prisma.sql`
      SELECT actor."id", actor."practiceId", actor."email"
      FROM "practices" practice
      JOIN "users" actor
        ON actor."practiceId" = practice."id"
      JOIN "transcribe_visits" visit
        ON visit."userId" = actor."id"
      JOIN "transcribe_md_patients" patient
        ON patient."id" = visit."patientId"
        AND patient."practiceId" = practice."id"
      WHERE visit."id" = ${input.visitId}
        AND actor."id" = ${input.actorUserId}
        AND practice."isActive" = TRUE
        AND actor."role" = 'DOCTOR'::"UserRole"
        AND actor."isActive" = TRUE
        AND actor."deactivatedAt" IS NULL
        AND actor."suspendedAt" IS NULL
        AND actor."softDeletedAt" IS NULL
        AND 'TRANSCRIBE_MD'::"Product" = ANY(actor."products")
        AND patient."externalId" IS DISTINCT FROM 'SYNTHETIC-QA-ONLY'
        AND NOT EXISTS (
          SELECT 1
          FROM "note_templates" provenance_template
          WHERE provenance_template."id" = visit."noteTemplateId"
            AND provenance_template."templateKind" = 'template_twin_docx'
        )
        AND NOT EXISTS (
          SELECT 1
          FROM "template_twin_compiled_versions" provenance_compiled
          WHERE provenance_compiled."noteTemplateId" = visit."noteTemplateId"
        )
        AND NOT EXISTS (
          SELECT 1 FROM "template_twin_fill_manifests" provenance_fill
          WHERE provenance_fill."visitId" = visit."id"
        )
        AND NOT EXISTS (
          SELECT 1 FROM "template_twin_synthetic_qa_runs" provenance_run
          WHERE provenance_run."visitId" = visit."id"
        )
        AND NOT EXISTS (
          SELECT 1 FROM "template_twin_synthetic_qa_admissions" provenance_admission
          WHERE provenance_admission."visitId" = visit."id"
        )
        AND NOT EXISTS (
          SELECT 1 FROM "template_twin_provider_executions" provenance_execution
          WHERE provenance_execution."visitId" = visit."id"
        )
      FOR SHARE OF practice, actor, patient, visit
    `,
  );
  const actor = rows[0];
  if (
    rows.length !== 1 ||
    !actor ||
    actor.id !== input.actorUserId ||
    typeof actor.practiceId !== "string" ||
    actor.practiceId.length === 0 ||
    typeof actor.email !== "string" ||
    actor.email.trim().length === 0
  ) {
    return null;
  }
  return actor;
}
