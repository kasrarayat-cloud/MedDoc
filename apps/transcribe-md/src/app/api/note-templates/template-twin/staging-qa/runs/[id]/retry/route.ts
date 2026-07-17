import { NextResponse } from "next/server";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import {
  retryTemplateTwinStagingQaRun,
  TemplateTwinStagingQaError,
  TemplateTwinStagingQaRetryRequestSchema,
} from "@/lib/template-twin/staging-qa-service";
import { TemplateTwinStagingQaDisabledError } from "@/lib/template-twin/staging-qa-gate";
import {
  readBoundedTemplateTwinStagingQaJson,
  TemplateTwinStagingQaRequestError,
} from "@/lib/template-twin/staging-qa-request";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const MAX_RETRY_REQUEST_BYTES = 1024;

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.VISIT_OPS, session.user.id);
    if (blocked) return blocked;
    const raw = await readBoundedTemplateTwinStagingQaJson(
      request,
      MAX_RETRY_REQUEST_BYTES,
    );
    const retryRequest = TemplateTwinStagingQaRetryRequestSchema.safeParse(raw);
    if (!retryRequest.success) {
      return NextResponse.json(
        { error: "Refresh this synthetic QA run before retrying." },
        { status: 400, headers: { "Cache-Control": "no-store, private" } },
      );
    }
    const { id: runId } = await context.params;
    const run = await retryTemplateTwinStagingQaRun({
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
        rolloutToken: session.templateTwinRolloutToken,
      },
      runId,
      expectedAttempt: retryRequest.data.expectedAttempt,
    });
    return NextResponse.json(
      { ok: true, run },
      {
        status: 202,
        headers: { "Cache-Control": "no-store, private" },
      },
    );
  } catch (error) {
    if (
      error instanceof AuthError ||
      error instanceof TemplateTwinStagingQaDisabledError ||
      (error instanceof TemplateTwinStagingQaError &&
        error.code === "NOT_FOUND")
    ) {
      return NextResponse.json({ error: "not found" }, { status: 404 });
    }
    if (error instanceof TemplateTwinStagingQaRequestError) {
      return NextResponse.json(
        { error: error.message, code: error.code },
        {
          status: error.code === "REQUEST_TOO_LARGE" ? 413 : 400,
          headers: { "Cache-Control": "no-store, private" },
        },
      );
    }
    if (error instanceof TemplateTwinStagingQaError) {
      return NextResponse.json(
        { error: error.message, code: error.code },
        {
          status:
            error.code === "ROLLOUT_CHANGED" ||
            error.code === "RETRY_ATTEMPT_STALE" ||
            error.code === "RUN_NOT_RETRYABLE" ||
            error.code === "RUN_NOT_REGENERABLE"
              ? 409
              : 503,
        },
      );
    }
    return NextResponse.json(
      { error: "Synthetic QA retry failed." },
      { status: 503 },
    );
  }
}
