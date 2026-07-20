import { Prisma } from "@prisma/client";

/**
 * Fixed, PHI-free error used when current physician authority cannot be proven.
 * Callers must not replace this with a database/provider error message.
 */
export class TemplateTwinCurrentPhysicianAuthorityError extends Error {
  readonly code = "TEMPLATE_TWIN_CURRENT_PHYSICIAN_REQUIRED" as const;

  constructor() {
    super("Current physician authorization is required for Template Twin.");
    this.name = "TemplateTwinCurrentPhysicianAuthorityError";
  }
}

interface TemplateTwinAuthorityLockClient {
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
}

/**
 * Acquire the tenant row before the physician row whenever a transaction
 * needs authority to remain current across more than one content-bearing
 * statement. Holding this lock prevents practice deactivation from committing
 * between an authority-bound source query and a later projection.
 */
export async function lockAndAssertActiveTemplateTwinPractice(input: {
  tx: TemplateTwinAuthorityLockClient;
  practiceId: string;
}): Promise<void> {
  const rows = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT practice."id"
    FROM "practices" practice
    WHERE practice."id" = ${input.practiceId}
      AND practice."isActive" = true
    FOR UPDATE
  `);
  if (
    !Array.isArray(rows) ||
    rows.length !== 1 ||
    rows[0]?.id !== input.practiceId
  ) {
    throw new TemplateTwinCurrentPhysicianAuthorityError();
  }
}

/**
 * Linearizable final-claim authority fence.
 *
 * The session/JWT and the route's initial database read are admission hints,
 * never the final authorization decision. Call this inside the same database
 * transaction that claims a review, correction, signature, or delivery. The
 * row lock orders a concurrent suspension, deactivation, account deletion, or
 * practice transfer against that final claim.
 */
export async function lockAndAssertCurrentTemplateTwinPhysician(input: {
  tx: TemplateTwinAuthorityLockClient;
  actor: { userId: string; practiceId: string };
}): Promise<{ email: string }> {
  const rows = await input.tx.$queryRaw<
    Array<{ id: string; email: string | null }>
  >(Prisma.sql`
    SELECT actor."id", actor."email"
    FROM "users" actor
    WHERE actor."id" = ${input.actor.userId}
      AND actor."practiceId" = ${input.actor.practiceId}
      AND actor."role" = 'DOCTOR'::"UserRole"
      AND actor."isActive" = true
      AND actor."deactivatedAt" IS NULL
      AND actor."suspendedAt" IS NULL
      AND actor."softDeletedAt" IS NULL
      AND 'TRANSCRIBE_MD'::"Product" = ANY(actor."products")
    FOR UPDATE
  `);

  if (
    !Array.isArray(rows) ||
    rows.length !== 1 ||
    rows[0]?.id !== input.actor.userId ||
    typeof rows[0]?.email !== "string" ||
    rows[0].email.trim().length === 0
  ) {
    throw new TemplateTwinCurrentPhysicianAuthorityError();
  }

  return { email: rows[0].email };
}

/**
 * Locks the admitted patient after the actor and before the visit row.
 *
 * A current physician claim alone does not authorize a patient that moved to
 * another practice after the initial clinical projection. Callers must use
 * actor -> patient -> visit ordering in the transaction that owns the final
 * review, correction, signature, or delivery claim.
 */
export async function lockAndAssertCurrentTemplateTwinPatient(input: {
  tx: TemplateTwinAuthorityLockClient;
  patientId: string;
  practiceId: string;
}): Promise<void> {
  const rows = await input.tx.$queryRaw<
    Array<{ id: string; practiceId: string }>
  >(Prisma.sql`
    SELECT patient."id", patient."practiceId"
    FROM "transcribe_md_patients" patient
    WHERE patient."id" = ${input.patientId}
      AND patient."practiceId" = ${input.practiceId}
    FOR UPDATE
  `);

  if (
    !Array.isArray(rows) ||
    rows.length !== 1 ||
    rows[0]?.id !== input.patientId ||
    rows[0].practiceId !== input.practiceId
  ) {
    throw new TemplateTwinCurrentPhysicianAuthorityError();
  }
}
