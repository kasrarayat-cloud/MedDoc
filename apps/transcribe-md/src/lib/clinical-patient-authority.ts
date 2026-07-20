import { Prisma } from "@prisma/client";

import { TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID } from "@/lib/template-twin/synthetic-qa-patient";

export interface CurrentClinicalPatientActor {
  userId: string;
  practiceId: string;
}

export interface LockedCurrentClinicalPatient {
  id: string;
  practiceId: string;
  name: string;
  dateOfBirth: Date | null;
  externalId: string | null;
  mrn: string | null;
  insurance: string | null;
  problemList: Prisma.JsonValue | null;
  deletedAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

interface ClinicalPatientAuthorityQueryClient {
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
}

export type CurrentClinicalPatientSqlAlias = "patient" | "p";

/** Fixed, PHI-free denial for current clinical-patient authority failures. */
export class ClinicalPatientAuthorityError extends Error {
  readonly code = "CURRENT_CLINICAL_PATIENT_AUTHORITY_REQUIRED" as const;

  constructor() {
    super("Current clinical patient authorization is required.");
    this.name = "ClinicalPatientAuthorityError";
  }
}

/**
 * Query-native actor/tenant predicate for a patient projection. Any query that
 * selects identifying patient fields must bind the current physician account,
 * product entitlement, active exact practice, patient tenant, deletion state,
 * and reserved synthetic marker in that same database statement.
 */
export function currentClinicalPatientCollectionWhere(input: {
  actor: CurrentClinicalPatientActor;
  includeDeleted?: boolean;
}): Prisma.TranscribeMdPatientWhereInput {
  const currentActor: Prisma.UserWhereInput = {
    id: input.actor.userId,
    practiceId: input.actor.practiceId,
    role: "DOCTOR",
    isActive: true,
    deactivatedAt: null,
    suspendedAt: null,
    softDeletedAt: null,
    products: { has: "TRANSCRIBE_MD" },
  };

  return {
    practiceId: input.actor.practiceId,
    ...(input.includeDeleted ? {} : { deletedAt: null }),
    OR: [
      { externalId: null },
      {
        externalId: {
          not: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
        },
      },
    ],
    practice: {
      is: {
        id: input.actor.practiceId,
        isActive: true,
        users: { some: currentActor },
      },
    },
  };
}

export function currentClinicalPatientWhere(input: {
  actor: CurrentClinicalPatientActor;
  patientId: string;
  includeDeleted?: boolean;
}): Prisma.TranscribeMdPatientWhereInput {
  return {
    ...currentClinicalPatientCollectionWhere(input),
    id: input.patientId,
  };
}

/**
 * Query-native form for raw roster/search/rollup statements. The alias is a
 * closed code-owned union so no request value can become SQL syntax.
 */
export function currentClinicalPatientReadAuthoritySql(input: {
  actor: CurrentClinicalPatientActor;
  patientAlias: CurrentClinicalPatientSqlAlias;
  includeDeleted?: boolean;
}): Prisma.Sql {
  const patient = Prisma.raw(input.patientAlias);
  return Prisma.sql`
    ${patient}."practiceId" = ${input.actor.practiceId}
    ${input.includeDeleted ? Prisma.empty : Prisma.sql`AND ${patient}."deletedAt" IS NULL`}
    AND ${patient}."externalId" IS DISTINCT FROM ${TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID}
    AND EXISTS (
      SELECT 1
      FROM "practices" current_practice
      JOIN "users" current_actor
        ON current_actor."practiceId" = current_practice."id"
      WHERE current_practice."id" = ${input.actor.practiceId}
        AND current_practice."isActive" = TRUE
        AND current_actor."id" = ${input.actor.userId}
        AND current_actor."role" = 'DOCTOR'::"UserRole"
        AND current_actor."isActive" = TRUE
        AND current_actor."deactivatedAt" IS NULL
        AND current_actor."suspendedAt" IS NULL
        AND current_actor."softDeletedAt" IS NULL
        AND 'TRANSCRIBE_MD'::"Product" = ANY(current_actor."products")
        AND ${patient}."practiceId" = current_practice."id"
    )
  `;
}

/**
 * Canonical mutation lock order shared by visit creation and patient writes:
 * active exact practice, then exact current physician. The patient lock must
 * immediately follow in the same transaction.
 */
export async function lockAndAssertCurrentClinicalPatientActor(input: {
  tx: ClinicalPatientAuthorityQueryClient;
  actor: CurrentClinicalPatientActor;
}): Promise<void> {
  const practices = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT practice."id"
    FROM "practices" practice
    WHERE practice."id" = ${input.actor.practiceId}
      AND practice."isActive" = TRUE
    FOR UPDATE
  `);
  if (practices.length !== 1 || practices[0]?.id !== input.actor.practiceId) {
    throw new ClinicalPatientAuthorityError();
  }

  const actors = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT actor."id"
    FROM "users" actor
    WHERE actor."id" = ${input.actor.userId}
      AND actor."practiceId" = ${input.actor.practiceId}
      AND actor."role" = 'DOCTOR'::"UserRole"
      AND actor."isActive" = TRUE
      AND actor."deactivatedAt" IS NULL
      AND actor."suspendedAt" IS NULL
      AND actor."softDeletedAt" IS NULL
      AND 'TRANSCRIBE_MD'::"Product" = ANY(actor."products")
    FOR UPDATE
  `);
  if (actors.length !== 1 || actors[0]?.id !== input.actor.userId) {
    throw new ClinicalPatientAuthorityError();
  }
}

async function lockCurrentClinicalPatientByPredicate(input: {
  tx: ClinicalPatientAuthorityQueryClient;
  actor: CurrentClinicalPatientActor;
  predicate: Prisma.Sql;
  includeDeleted?: boolean;
  orderedSingleMatch?: boolean;
}): Promise<LockedCurrentClinicalPatient | null> {
  const rows = await input.tx.$queryRaw<LockedCurrentClinicalPatient[]>(
    Prisma.sql`
      SELECT
        patient."id", patient."practiceId", patient."name",
        patient."dateOfBirth", patient."externalId", patient."mrn",
        patient."insurance", patient."problemList", patient."deletedAt",
        patient."createdAt", patient."updatedAt"
      FROM "transcribe_md_patients" patient
      JOIN "practices" practice
        ON practice."id" = patient."practiceId"
      JOIN "users" actor
        ON actor."id" = ${input.actor.userId}
       AND actor."practiceId" = practice."id"
      WHERE ${input.predicate}
        AND practice."id" = ${input.actor.practiceId}
        AND practice."isActive" = TRUE
        AND actor."role" = 'DOCTOR'::"UserRole"
        AND actor."isActive" = TRUE
        AND actor."deactivatedAt" IS NULL
        AND actor."suspendedAt" IS NULL
        AND actor."softDeletedAt" IS NULL
        AND 'TRANSCRIBE_MD'::"Product" = ANY(actor."products")
        ${input.includeDeleted ? Prisma.empty : Prisma.sql`AND patient."deletedAt" IS NULL`}
        AND patient."externalId" IS DISTINCT FROM ${TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID}
      ${input.orderedSingleMatch ? Prisma.sql`ORDER BY patient."id" ASC LIMIT 1` : Prisma.empty}
      FOR UPDATE OF patient
    `,
  );

  return rows.length === 1 ? (rows[0] ?? null) : null;
}

/** Call only after `lockAndAssertCurrentClinicalPatientActor` in this tx. */
export function lockCurrentClinicalPatientAfterActor(input: {
  tx: ClinicalPatientAuthorityQueryClient;
  actor: CurrentClinicalPatientActor;
  patientId: string;
  includeDeleted?: boolean;
}): Promise<LockedCurrentClinicalPatient | null> {
  return lockCurrentClinicalPatientByPredicate({
    tx: input.tx,
    actor: input.actor,
    predicate: Prisma.sql`patient."id" = ${input.patientId}`,
    includeDeleted: input.includeDeleted,
  });
}

/** Case-insensitive exact-name match, locked before visit insertion. */
export function lockNamedCurrentClinicalPatientAfterActor(input: {
  tx: ClinicalPatientAuthorityQueryClient;
  actor: CurrentClinicalPatientActor;
  patientName: string;
}): Promise<LockedCurrentClinicalPatient | null> {
  return lockCurrentClinicalPatientByPredicate({
    tx: input.tx,
    actor: input.actor,
    predicate: Prisma.sql`LOWER(patient."name") = LOWER(${input.patientName})`,
    orderedSingleMatch: true,
  });
}

export async function lockAndReadCurrentClinicalPatient(input: {
  tx: ClinicalPatientAuthorityQueryClient;
  actor: CurrentClinicalPatientActor;
  patientId: string;
  includeDeleted?: boolean;
}): Promise<LockedCurrentClinicalPatient | null> {
  await lockAndAssertCurrentClinicalPatientActor({
    tx: input.tx,
    actor: input.actor,
  });
  return lockCurrentClinicalPatientAfterActor(input);
}
