import { NextResponse } from "next/server";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { completedCandidateSyntheticModeEnabled } from "@/lib/template-twin/completed-candidate-access";
import {
  CompletedCandidateServiceError,
  reviewCompletedCandidate,
} from "@/lib/template-twin/completed-candidate-service";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import { isTemplateTwinStagingQaRequested } from "@/lib/template-twin/staging-qa-gate";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_REVIEW_BYTES = 256 * 1024;

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, private",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

async function boundedJson(request: Request): Promise<unknown> {
  const length = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(length) && length > MAX_REVIEW_BYTES) {
    throw new CompletedCandidateServiceError(
      "INVALID_INPUT",
      "The review request is too large.",
    );
  }
  const reader = request.body?.getReader();
  if (!reader) {
    throw new CompletedCandidateServiceError(
      "INVALID_INPUT",
      "The review request is empty.",
    );
  }
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      total += next.value.byteLength;
      if (total > MAX_REVIEW_BYTES) {
        await reader.cancel();
        throw new CompletedCandidateServiceError(
          "INVALID_INPUT",
          "The review request is too large.",
        );
      }
      chunks.push(next.value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    throw new CompletedCandidateServiceError(
      "INVALID_INPUT",
      "The review request is malformed.",
    );
  }
}

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  if (
    !completedCandidateSyntheticModeEnabled() ||
    isTemplateTwinStagingQaRequested()
  ) {
    return response({ ok: false, error: "not found" }, 404);
  }
  if (!isSameOriginTemplateTwinMutation(request)) {
    return response(
      { ok: false, error: "The review request was not same-origin." },
      403,
    );
  }
  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, session.user.id);
    if (blocked) return blocked;
    const { id } = await context.params;
    const result = await reviewCompletedCandidate({
      candidateId: id,
      payload: await boundedJson(request),
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
        rolloutToken: session.templateTwinRolloutToken,
      },
    });
    return response({ ok: true, ...result }, 200);
  } catch (error) {
    if (error instanceof AuthError) {
      return response(
        {
          ok: false,
          error:
            error.code === "FORBIDDEN"
              ? error.message
              : "Sign in again before saving the review.",
        },
        error.code === "FORBIDDEN" ? 403 : 401,
      );
    }
    if (error instanceof CompletedCandidateServiceError) {
      const status =
        error.code === "NOT_FOUND"
          ? 404
          : error.code === "REVIEW_CONFLICT" || error.code === "ROLLOUT_CHANGED"
            ? 409
            : error.code === "INVALID_INPUT"
              ? 400
              : 503;
      return response({ ok: false, error: error.message }, status);
    }
    return response(
      { ok: false, error: "The candidate review was not saved." },
      500,
    );
  }
}
