import { NextResponse } from "next/server";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import {
  createTemplateTwinStagingQaRun,
  TemplateTwinStagingQaError,
  TemplateTwinStagingQaRunRequestSchema,
} from "@/lib/template-twin/staging-qa-service";
import { TemplateTwinStagingQaDisabledError } from "@/lib/template-twin/staging-qa-gate";
import {
  readBoundedTemplateTwinStagingQaJson,
  TemplateTwinStagingQaRequestError,
} from "@/lib/template-twin/staging-qa-request";
import {
  TemplateTwinSyntheticEvidenceRejectedError,
  TemplateTwinSyntheticEvidenceScanUnavailableError,
} from "@/lib/template-twin/synthetic-evidence-gate";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const MAX_REQUEST_BYTES = 8 * 1024;

function json(body: Record<string, unknown>, status: number): NextResponse {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store, private" },
  });
}

export async function POST(request: Request) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return json({ ok: false, error: "not found" }, 404);
  }
  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, session.user.id);
    if (blocked) return blocked;
    const raw = await readBoundedTemplateTwinStagingQaJson(
      request,
      MAX_REQUEST_BYTES,
    );
    const parsed = TemplateTwinStagingQaRunRequestSchema.safeParse(raw);
    if (!parsed.success) {
      return json(
        { ok: false, error: "The synthetic QA run request is invalid." },
        400,
      );
    }
    const run = await createTemplateTwinStagingQaRun({
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
        rolloutToken: session.templateTwinRolloutToken,
      },
      request: parsed.data,
    });
    return json(
      {
        ok: true,
        runId: run.runId,
        visitId: run.visitId,
        reused: run.reused,
        run,
        visitUrl: `/visits/${encodeURIComponent(run.visitId)}`,
      },
      run.reused ? 200 : 202,
    );
  } catch (error) {
    if (
      error instanceof AuthError ||
      error instanceof TemplateTwinStagingQaDisabledError
    ) {
      return json({ ok: false, error: "not found" }, 404);
    }
    if (error instanceof TemplateTwinStagingQaRequestError) {
      return json(
        { ok: false, error: error.message, code: error.code },
        error.code === "REQUEST_TOO_LARGE" ? 413 : 400,
      );
    }
    if (error instanceof TemplateTwinSyntheticEvidenceRejectedError) {
      return json({ ok: false, error: error.message, code: error.code }, 422);
    }
    if (error instanceof TemplateTwinSyntheticEvidenceScanUnavailableError) {
      return json({ ok: false, error: error.message, code: error.code }, 503);
    }
    if (error instanceof TemplateTwinStagingQaError) {
      const status =
        error.code === "NOT_FOUND"
          ? 404
          : error.code === "TEMPLATE_NOT_READY"
            ? 422
            : error.code === "IDEMPOTENCY_CONFLICT" ||
                error.code === "ROLLOUT_CHANGED" ||
                error.code === "RUN_NOT_RETRYABLE" ||
                error.code === "RUN_NOT_REGENERABLE"
              ? 409
              : 503;
      return json(
        { ok: false, error: error.message, code: error.code },
        status,
      );
    }
    return json({ ok: false, error: "Synthetic QA admission failed." }, 503);
  }
}
