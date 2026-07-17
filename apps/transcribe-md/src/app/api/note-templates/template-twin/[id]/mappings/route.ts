import { NextResponse } from "next/server";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import {
  TemplateTwinLifecycleError,
  updateTemplateTwinMappings,
} from "@/lib/template-twin/certification-lifecycle";
import { TemplateTwinUpdateMappingsRequestSchema } from "@/lib/template-twin/contracts";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import {
  TemplateTwinStagingQaLifecycleGuardError,
  runWithTemplateTwinStagingQaLifecycleGuard,
} from "@/lib/template-twin/staging-qa-lifecycle-guard";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store, private" },
  });
}

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return response(
      { ok: false, error: "The update request was not same-origin." },
      403,
    );
  }
  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, session.user.id);
    if (blocked) return blocked;
    const { id } = await context.params;
    const parsed = TemplateTwinUpdateMappingsRequestSchema.safeParse(
      await request.json(),
    );
    if (!parsed.success) {
      return response(
        { ok: false, error: "The mapping draft is invalid." },
        400,
      );
    }
    const actor = {
      userId: session.user.id,
      userEmail: session.user.email,
      practiceId: session.user.practiceId,
      rolloutToken: session.templateTwinRolloutToken,
    };
    const workspace = await runWithTemplateTwinStagingQaLifecycleGuard({
      noteTemplateId: id,
      actor,
      purpose: "mapping-update",
      operation: () =>
        updateTemplateTwinMappings({
          noteTemplateId: id,
          actor,
          ...parsed.data,
        }),
    });
    return response({ ok: true, workspace }, 200);
  } catch (error) {
    if (error instanceof AuthError) {
      return response(
        {
          ok: false,
          error:
            error.code === "FORBIDDEN"
              ? error.message
              : "Sign in again before saving.",
        },
        error.code === "FORBIDDEN" ? 403 : 401,
      );
    }
    if (error instanceof TemplateTwinLifecycleError) {
      const status =
        error.code === "NOT_FOUND"
          ? 404
          : error.code === "MAPPING_INVALID" ||
              error.code === "FIELD_SET_MISMATCH" ||
              error.code === "UNSUPPORTED_CLINICAL_CONCEPT"
            ? 422
            : 409;
      return response({ ok: false, error: error.message }, status);
    }
    if (error instanceof TemplateTwinStagingQaLifecycleGuardError) {
      return response(
        { ok: false, error: "Template Twin version not found." },
        404,
      );
    }
    return response({ ok: false, error: "Mappings were not saved." }, 500);
  }
}
