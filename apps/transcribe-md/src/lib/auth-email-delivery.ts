import crypto from "node:crypto";

import prisma from "@meddoc/db";
import { Prisma, type AuthEmailPurpose } from "@prisma/client";

import { APP_URL } from "@/lib/constants";
import {
  sendAccountExistsEmail,
  sendEmailChangeRequestEmail,
  sendEmailVerification,
  sendPasswordResetEmail,
} from "@/lib/email";

interface ClaimedDelivery {
  id: string;
  claimToken: string;
}

interface PreparedDelivery {
  userId: string;
  email: string;
  name: string | null;
  tokenId: string | null;
  purpose: AuthEmailPurpose;
}

interface AuthEmailHealthRow {
  pending: bigint | number;
  claimed: bigint | number;
  ambiguous: bigint | number;
  oldestPendingSeconds: bigint | number;
}

const RAW_TOKEN_BYTES = 32;
const PROVIDER_TIMEOUT_MS = 30_000;
const FINISH_ATTEMPTS = 3;

class AuthEmailProviderTimeoutError extends Error {
  constructor() {
    super("Auth email provider timed out.");
    this.name = "AuthEmailProviderTimeoutError";
  }
}

function rawToken(): string {
  return crypto.randomBytes(RAW_TOKEN_BYTES).toString("base64url");
}

function tokenHash(token: string): string {
  return crypto.createHash("sha256").update(token).digest("hex");
}

function providerReceiptHash(providerReceipt: string): string {
  return crypto
    .createHash("sha256")
    .update(`resend:${providerReceipt}`)
    .digest("hex");
}

async function withProviderTimeout<T>(promise: Promise<T>): Promise<T> {
  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      promise,
      new Promise<never>((_resolve, reject) => {
        timeout = setTimeout(
          () => reject(new AuthEmailProviderTimeoutError()),
          PROVIDER_TIMEOUT_MS,
        );
      }),
    ]);
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}

async function claim(limit: number): Promise<ClaimedDelivery[]> {
  return (await prisma.$queryRaw(Prisma.sql`
    SELECT "id"::text, "claimToken"::text
    FROM public.auth_email_claim(${limit})
  `)) as ClaimedDelivery[];
}

async function prepare(
  request: ClaimedDelivery,
  tokenId: string,
  hash: string,
): Promise<PreparedDelivery | null> {
  const rows = (await prisma.$queryRaw(Prisma.sql`
    SELECT "userId", "email", "name", "tokenId", "purpose"
    FROM public.auth_email_prepare_delivery(
      ${request.id}::uuid,
      ${request.claimToken}::uuid,
      ${tokenId},
      ${hash}
    )
  `)) as PreparedDelivery[];
  return rows[0] ?? null;
}

async function finish(input: {
  request: ClaimedDelivery;
  tokenId: string | null;
  delivered: boolean;
  errorCode?: string;
  providerReceiptSha256?: string;
}): Promise<void> {
  await prisma.$queryRaw(Prisma.sql`
    SELECT public.auth_email_finish_delivery(
      ${input.request.id}::uuid,
      ${input.request.claimToken}::uuid,
      ${input.tokenId}::text,
      ${input.delivered},
      ${input.errorCode ?? null}::text,
      ${input.providerReceiptSha256 ?? null}::text
    )
  `);
}

async function finishWithRetry(
  input: Parameters<typeof finish>[0],
): Promise<void> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= FINISH_ATTEMPTS; attempt += 1) {
    try {
      await finish(input);
      return;
    } catch (error) {
      lastError = error;
      if (attempt < FINISH_ATTEMPTS) {
        await new Promise<void>((resolve) =>
          setTimeout(resolve, attempt * 100),
        );
      }
    }
  }
  throw lastError;
}

function requireBearerToken(
  delivery: PreparedDelivery,
  token: string,
): { token: string; tokenId: string } {
  if (!delivery.tokenId || !token) {
    throw new Error("Auth email bearer material is unavailable.");
  }
  return { token, tokenId: delivery.tokenId };
}

async function sendPreparedDelivery(
  delivery: PreparedDelivery,
  token: string,
  requestId: string,
): Promise<{ id: string | null }> {
  const options = {
    trackUsage: false,
    idempotencyKey: `auth-email-${requestId}`,
  } as const;
  switch (delivery.purpose) {
    case "PASSWORD_RESET": {
      const bearer = requireBearerToken(delivery, token);
      return sendPasswordResetEmail(
        {
          toEmail: delivery.email,
          resetUrl: `${APP_URL}/reset-password?token=${encodeURIComponent(bearer.token)}`,
          userName: delivery.name,
        },
        options,
      );
    }
    case "EMAIL_VERIFICATION": {
      const bearer = requireBearerToken(delivery, token);
      return sendEmailVerification(
        {
          toEmail: delivery.email,
          verifyUrl: `${APP_URL}/api/auth/verify-email?token=${encodeURIComponent(bearer.token)}`,
          userName: delivery.name,
        },
        options,
      );
    }
    case "EMAIL_CHANGE": {
      const bearer = requireBearerToken(delivery, token);
      return sendEmailChangeRequestEmail(
        {
          toEmail: delivery.email,
          confirmUrl: `${APP_URL}/api/auth/confirm-email?token=${encodeURIComponent(bearer.token)}`,
          userName: delivery.name,
        },
        options,
      );
    }
    case "ACCOUNT_EXISTS":
      if (delivery.tokenId !== null) {
        throw new Error("Account-exists email unexpectedly has a token.");
      }
      return sendAccountExistsEmail(
        {
          toEmail: delivery.email,
          signInUrl: `${APP_URL}/login`,
          userName: delivery.name,
        },
        options,
      );
    default: {
      const exhaustive: never = delivery.purpose;
      throw new Error(`Unsupported auth email purpose: ${String(exhaustive)}`);
    }
  }
}

async function deliver(
  request: ClaimedDelivery,
): Promise<"delivered" | "noop" | "ambiguous"> {
  const token = rawToken();
  const tokenId = crypto.randomUUID();
  const delivery = await prepare(request, tokenId, tokenHash(token));
  if (!delivery) return "noop";

  try {
    const result = await withProviderTimeout(
      sendPreparedDelivery(delivery, token, request.id),
    );
    const providerId = result.id?.trim();
    if (!providerId || providerId.length > 512) {
      throw new Error("Auth email provider acceptance is unverified.");
    }
    await finishWithRetry({
      request,
      tokenId: delivery.tokenId,
      delivered: true,
      providerReceiptSha256: providerReceiptHash(providerId),
    });
  } catch {
    await finishWithRetry({
      request,
      tokenId: delivery.tokenId,
      delivered: false,
      errorCode: "AUTH_EMAIL_PROVIDER_AMBIGUOUS",
    });
    return "ambiguous";
  }
  return "delivered";
}

export async function drainAuthEmailOutbox(input: {
  limit: number;
  onProgress?: () => void | Promise<void>;
}): Promise<{
  claimed: number;
  delivered: number;
  noop: number;
  ambiguous: number;
  purged: number;
  health: {
    pending: number;
    claimed: number;
    ambiguous: number;
    oldestPendingSeconds: number;
  };
}> {
  if (
    !Number.isSafeInteger(input.limit) ||
    input.limit < 1 ||
    input.limit > 100
  ) {
    throw new TypeError("Auth email drain limit is invalid.");
  }
  const ids = await claim(input.limit);
  await input.onProgress?.();
  let delivered = 0;
  let noop = 0;
  let ambiguous = 0;
  for (const request of ids) {
    try {
      const result = await deliver(request);
      if (result === "delivered") delivered += 1;
      else if (result === "noop") noop += 1;
      else ambiguous += 1;
    } catch {
      // An expired prepared lease is terminalized as AMBIGUOUS by the claim
      // function. Never log the request id, recipient, token, or driver text.
      ambiguous += 1;
    }
    await input.onProgress?.();
  }
  const purgeRows = (await prisma.$queryRaw(Prisma.sql`
    SELECT public.auth_email_purge(1000) AS "count"
  `)) as Array<{ count: number }>;
  const healthRows = (await prisma.$queryRaw(Prisma.sql`
    SELECT "pending", "claimed", "ambiguous", "oldestPendingSeconds"
    FROM public.auth_email_health()
  `)) as AuthEmailHealthRow[];
  await input.onProgress?.();
  const health = healthRows[0];
  if (!health) {
    throw new Error("Auth email health census is unavailable.");
  }
  return {
    claimed: ids.length,
    delivered,
    noop,
    ambiguous,
    purged: Number(purgeRows[0]?.count ?? 0),
    health: {
      pending: Number(health.pending),
      claimed: Number(health.claimed),
      ambiguous: Number(health.ambiguous),
      oldestPendingSeconds: Number(health.oldestPendingSeconds),
    },
  };
}
