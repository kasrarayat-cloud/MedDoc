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
}): Promise<void> {
  const rows = await input.tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT actor."id"
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
    rows[0]?.id !== input.actor.userId
  ) {
    throw new TemplateTwinCurrentPhysicianAuthorityError();
  }
}
