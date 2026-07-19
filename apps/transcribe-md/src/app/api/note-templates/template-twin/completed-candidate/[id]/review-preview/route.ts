import { NextResponse } from "next/server";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { completedCandidateSyntheticModeEnabled } from "@/lib/template-twin/completed-candidate-access";
import {
  CompletedCandidateServiceError,
  issueCompletedCandidateReviewPreview,
} from "@/lib/template-twin/completed-candidate-service";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import { isTemplateTwinStagingQaRequested } from "@/lib/template-twin/staging-qa-gate";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, private",
      Pragma: "no-cache",
      "Referrer-Policy": "no-referrer",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

export async function POST(
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
      { ok: false, error: "The comparison request was not same-origin." },
      403,
    );
  }
  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, session.user.id);
    if (blocked) return blocked;
    const { id } = await context.params;
    const preview = await issueCompletedCandidateReviewPreview({
      candidateId: id,
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
        rolloutToken: session.templateTwinRolloutToken,
      },
    });
    return response({ ok: true, ...preview }, 200);
  } catch (error) {
    if (error instanceof AuthError) {
      return response(
        {
          ok: false,
          error:
            error.code === "FORBIDDEN"
              ? error.message
              : "Sign in again before opening the comparison.",
        },
        error.code === "FORBIDDEN" ? 403 : 401,
      );
    }
    if (error instanceof CompletedCandidateServiceError) {
      const status =
        error.code === "NOT_FOUND"
          ? 404
          : error.code === "REVIEW_CONFLICT" ||
              error.code === "ROLLOUT_CHANGED" ||
              error.code === "REVIEW_PREVIEW_REQUIRED"
            ? 409
            : error.code === "INVALID_INPUT"
              ? 400
              : 503;
      return response({ ok: false, error: error.message }, status);
    }
    return response(
      { ok: false, error: "The protected comparison could not be opened." },
      500,
    );
  }
}
