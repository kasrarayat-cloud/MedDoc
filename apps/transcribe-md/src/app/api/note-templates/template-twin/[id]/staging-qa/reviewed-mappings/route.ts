import { NextResponse } from "next/server";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import {
  TemplateTwinStagingQaLifecycleGuardError,
  runWithTemplateTwinStagingQaLifecycleGuard,
} from "@/lib/template-twin/staging-qa-lifecycle-guard";
import {
  loadTemplateTwinStagingQaReviewedMappingDraft,
  TemplateTwinStagingQaReviewedMappingsError,
} from "@/lib/template-twin/staging-qa-reviewed-mappings";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store, private" },
  });
}

/**
 * Return a client-side draft for the exact reviewed synthetic fixture. This
 * endpoint does not save mappings or field intents and cannot certify or
 * activate a template version.
 */
export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return response(
      { ok: false, error: "The reviewed mapping request was not same-origin." },
      403,
    );
  }
  try {
    const session = await requireDoctorSession();
    const { id } = await context.params;
    const actor = {
      userId: session.user.id,
      userEmail: session.user.email,
      practiceId: session.user.practiceId,
      rolloutToken: session.templateTwinRolloutToken,
    };

    // Resolve and validate the read-only draft before entering the lifecycle
    // provider guard. A contract mismatch is not a provider failure and must
    // never retire the fixture's durable staging admission.
    const reviewed = await loadTemplateTwinStagingQaReviewedMappingDraft({
      noteTemplateId: id,
      doctorId: actor.userId,
      practiceId: actor.practiceId,
    });
    const admitted = await runWithTemplateTwinStagingQaLifecycleGuard({
      noteTemplateId: id,
      actor,
      purpose: "reviewed-mappings-load",
      operation: () => reviewed,
    });
    return response({ ok: true, reviewed: admitted }, 200);
  } catch (error) {
    if (error instanceof AuthError) {
      return response(
        {
          ok: false,
          error:
            error.code === "FORBIDDEN"
              ? error.message
              : "Sign in again before loading reviewed mappings.",
        },
        error.code === "FORBIDDEN" ? 403 : 401,
      );
    }
    if (error instanceof TemplateTwinStagingQaReviewedMappingsError) {
      if (error.code === "NOT_EDITABLE") {
        return response({ ok: false, error: error.message }, 409);
      }
      return response(
        { ok: false, error: "Reviewed synthetic mappings are unavailable." },
        404,
      );
    }
    if (error instanceof TemplateTwinStagingQaLifecycleGuardError) {
      return response(
        { ok: false, error: "Reviewed synthetic mappings are unavailable." },
        404,
      );
    }
    return response(
      { ok: false, error: "Reviewed synthetic mappings were not loaded." },
      500,
    );
  }
}
