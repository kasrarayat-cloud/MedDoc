import { NextResponse } from "next/server";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { TemplateTwinFieldCorrectionRequestSchema } from "@/lib/template-twin/contracts";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import {
  reviewTemplateTwinField,
  TemplateTwinReviewError,
} from "@/lib/template-twin/review-service";
import {
  TemplateTwinArtifactIntegrityError,
  TemplateTwinStorageUnavailableError,
} from "@/lib/template-twin/storage";
import { TemplateTwinStagingQaDisabledError } from "@/lib/template-twin/staging-qa-gate";
import { TemplateTwinStagingQaVisitGuardError } from "@/lib/template-twin/staging-qa-visit-guard";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, private",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

async function mutate(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return response(
      { ok: false, error: "The correction request was not same-origin." },
      403,
    );
  }

  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.VISIT_OPS, session.user.id);
    if (blocked) return blocked;
    const { id } = await context.params;
    const parsed = TemplateTwinFieldCorrectionRequestSchema.safeParse(
      await request.json(),
    );
    if (!parsed.success) {
      return response(
        { ok: false, error: "The field correction is incomplete or invalid." },
        400,
      );
    }
    const result = await reviewTemplateTwinField({
      visitId: id,
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
      },
      correction: parsed.data,
    });
    return response({ ok: true, result }, 200);
  } catch (error) {
    if (
      error instanceof TemplateTwinStagingQaDisabledError ||
      (error instanceof TemplateTwinStagingQaVisitGuardError &&
        error.code === "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND")
    ) {
      return response({ ok: false, error: "not found" }, 404);
    }
    if (error instanceof TemplateTwinStagingQaVisitGuardError) {
      return response(
        { ok: false, error: error.message, code: error.code, retry: false },
        409,
      );
    }
    if (error instanceof AuthError) {
      return response(
        {
          ok: false,
          error:
            error.code === "FORBIDDEN"
              ? error.message
              : "Sign in again before reviewing.",
        },
        error.code === "FORBIDDEN" ? 403 : 401,
      );
    }
    if (error instanceof TemplateTwinReviewError) {
      const status =
        error.code === "NOT_FOUND"
          ? 404
          : error.code === "CORRECTION_INVALID" ||
              error.code === "MANIFEST_INVALID" ||
              error.code === "TEMPLATE_PROVENANCE_INVALID"
            ? 422
            : 409;
      return response(
        {
          ok: false,
          error: error.message,
          code: error.code,
          retry: error.code.startsWith("TEMPLATE_TWIN_"),
        },
        status,
      );
    }
    if (
      error instanceof TemplateTwinStorageUnavailableError ||
      error instanceof TemplateTwinArtifactIntegrityError
    ) {
      return response(
        {
          ok: false,
          error:
            "Private Template Twin storage could not verify the source or corrected output.",
        },
        503,
      );
    }
    return response(
      {
        ok: false,
        error:
          "The correction was not saved because verification did not complete.",
      },
      500,
    );
  }
}

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  return mutate(request, context);
}

/** POST is retained for progressively enhanced form clients; it runs the
 * exact same same-origin, auth, validation, and optimistic-concurrency path. */
export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  return mutate(request, context);
}
