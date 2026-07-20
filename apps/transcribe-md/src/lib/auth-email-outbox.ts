import "server-only";

import prisma from "@meddoc/db";
import { Prisma, type AuthEmailPurpose } from "@prisma/client";

type AuthEmailWriteClient = Pick<Prisma.TransactionClient, "$queryRaw">;

function requireNormalizedEmail(email: string): string {
  const normalized = email.trim().toLowerCase();
  if (
    normalized !== email ||
    normalized.length < 3 ||
    normalized.length > 254
  ) {
    throw new TypeError("Auth email request must be normalized.");
  }
  return normalized;
}

export async function enqueueAuthEmailRequestInTransaction(
  tx: AuthEmailWriteClient,
  input: {
    email: string;
    purpose: Exclude<AuthEmailPurpose, "EMAIL_CHANGE">;
  },
): Promise<void> {
  const normalized = requireNormalizedEmail(input.email);
  const rows = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT public.auth_email_enqueue(
      ${normalized},
      ${input.purpose}::"AuthEmailPurpose"
    )::text AS "id"
  `);
  if (rows.length !== 1 || !rows[0]?.id) {
    throw new Error("Auth email request was not durably accepted.");
  }
}

export async function enqueueAuthEmailRequest(input: {
  email: string;
  purpose: Exclude<AuthEmailPurpose, "EMAIL_CHANGE">;
}): Promise<void> {
  await enqueueAuthEmailRequestInTransaction(prisma, input);
}

export async function enqueueAuthEmailChangeRequestInTransaction(
  tx: AuthEmailWriteClient,
  input: {
    userId: string;
    expectedCurrentEmail: string;
    requestedNewEmail: string;
    expectedPracticeId: string;
    expectedSessionToken: string;
    expectedPasswordHash: string;
  },
): Promise<void> {
  if (!input.userId) {
    throw new TypeError("Auth email change user is required.");
  }
  const currentEmail = requireNormalizedEmail(input.expectedCurrentEmail);
  const newEmail = requireNormalizedEmail(input.requestedNewEmail);
  if (
    currentEmail === newEmail ||
    !input.expectedPracticeId ||
    !input.expectedSessionToken ||
    !input.expectedPasswordHash
  ) {
    throw new TypeError("Auth email change must use a new address.");
  }
  const rows = await tx.$queryRaw<Array<{ id: string }>>(Prisma.sql`
    SELECT public.auth_email_enqueue_change(
      ${input.userId},
      ${currentEmail},
      ${newEmail},
      ${input.expectedPracticeId},
      ${input.expectedSessionToken},
      ${input.expectedPasswordHash}
    )::text AS "id"
  `);
  if (rows.length !== 1 || !rows[0]?.id) {
    throw new Error("Auth email change was not durably accepted.");
  }
}
