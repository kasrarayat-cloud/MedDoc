import { NextResponse } from "next/server";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { completedCandidateSyntheticModeEnabled } from "@/lib/template-twin/completed-candidate-access";
import {
  CompletedCandidateServiceError,
  readApprovedCompletedCandidate,
} from "@/lib/template-twin/completed-candidate-service";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import { isTemplateTwinStagingQaRequested } from "@/lib/template-twin/staging-qa-gate";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function failure(message: string, status: number) {
  return NextResponse.json(
    { ok: false, error: message },
    {
      status,
      headers: {
        "Cache-Control": "no-store, private",
        "X-Content-Type-Options": "nosniff",
      },
    },
  );
}

export async function GET(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  if (
    !completedCandidateSyntheticModeEnabled() ||
    isTemplateTwinStagingQaRequested()
  ) {
    return failure("not found", 404);
  }
  if (!isSameOriginTemplateTwinMutation(request)) {
    return failure("The download request was not same-origin.", 403);
  }
  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, session.user.id);
    if (blocked) return blocked;
    const { id } = await context.params;
    const bytes = await readApprovedCompletedCandidate({
      candidateId: id,
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
      },
    });
    return new NextResponse(new Uint8Array(bytes), {
      status: 200,
      headers: {
        "Content-Type":
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition":
          'attachment; filename="quillmd-template-candidate.docx"',
        "Content-Length": String(bytes.byteLength),
        "Cache-Control": "no-store, private",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch (error) {
    if (error instanceof AuthError) {
      return failure(
        error.code === "FORBIDDEN"
          ? error.message
          : "Sign in again before downloading the candidate.",
        error.code === "FORBIDDEN" ? 403 : 401,
      );
    }
    if (error instanceof CompletedCandidateServiceError) {
      return failure(error.message, error.code === "NOT_FOUND" ? 404 : 503);
    }
    return failure("The approved candidate could not be downloaded.", 500);
  }
}
