import { NextResponse } from "next/server";
import { z } from "zod";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import {
  acknowledgeTemplateTwinCustomExamples,
  runTemplateTwinCustomExamples,
  TemplateTwinCustomExampleError,
} from "@/lib/template-twin/custom-example-service";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

const RequestSchema = z.discriminatedUnion("action", [
  z.object({ action: z.literal("run") }).strict(),
  z
    .object({
      action: z.literal("acknowledge"),
      batchId: z.string().uuid(),
    })
    .strict(),
]);

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store, private" },
  });
}

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return response(
      { ok: false, error: "The example request was not same-origin." },
      403,
    );
  }
  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, session.user.id);
    if (blocked) return blocked;
    const parsed = RequestSchema.safeParse(await request.json());
    if (!parsed.success) {
      return response(
        { ok: false, error: "The custom-field example action is invalid." },
        400,
      );
    }
    const { id } = await context.params;
    const actor = {
      userId: session.user.id,
      userEmail: session.user.email,
      practiceId: session.user.practiceId,
      rolloutToken: session.templateTwinRolloutToken,
    };
    const coverage =
      parsed.data.action === "run"
        ? await runTemplateTwinCustomExamples({
            noteTemplateId: id,
            actor,
          })
        : await acknowledgeTemplateTwinCustomExamples({
            noteTemplateId: id,
            batchId: parsed.data.batchId,
            actor,
          });
    return response({ ok: true, coverage }, 200);
  } catch (error) {
    if (error instanceof AuthError) {
      return response(
        {
          ok: false,
          error:
            error.code === "FORBIDDEN"
              ? error.message
              : "Sign in again before testing custom fields.",
        },
        error.code === "FORBIDDEN" ? 403 : 401,
      );
    }
    if (error instanceof TemplateTwinCustomExampleError) {
      const status =
        error.code === "NOT_FOUND" || error.code === "BATCH_NOT_FOUND"
          ? 404
          : error.code === "NO_CUSTOM_FIELDS" ||
              error.code === "EXAMPLES_FAILED"
            ? 422
            : 409;
      return response({ ok: false, error: error.message }, status);
    }
    return response(
      {
        ok: false,
        error:
          "The custom-field examples could not be verified. No review was recorded.",
      },
      500,
    );
  }
}
