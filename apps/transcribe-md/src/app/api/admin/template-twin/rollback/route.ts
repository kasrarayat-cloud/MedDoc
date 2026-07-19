import { NextResponse } from "next/server";
import { z } from "zod";

import { adminApi, type AdminContext } from "@/lib/admin-api-gate";
import {
  cancelPreparedTemplateTwinRollback,
  inspectTemplateTwinRollback,
  prepareTemplateTwinRollback,
  revokeTemplateTwinRollout,
  TemplateTwinRollbackControlError,
  type TemplateTwinRollbackActor,
} from "@/lib/template-twin/rollback-control";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";

export const dynamic = "force-dynamic";

const OperationId = z.string().uuid();
const PrepareBody = z.object({
  action: z.literal("prepare"),
  operationId: OperationId,
  reasonCode: z.string().regex(/^[A-Z][A-Z0-9_]{2,79}$/u),
  changeId: z.string().regex(/^[A-Za-z0-9][A-Za-z0-9._:-]{2,79}$/u),
  confirmation: z.literal("FENCE_TEMPLATE_TWIN"),
});
const RevokeBody = z.object({
  action: z.literal("revoke"),
  operationId: OperationId,
  confirmation: z.literal("REVOKE_TEMPLATE_TWIN"),
});
const CancelBody = z.object({
  action: z.literal("cancel_prepare"),
  operationId: OperationId,
  confirmation: z.literal("REOPEN_TEMPLATE_TWIN_FENCE"),
});
const Body = z.discriminatedUnion("action", [
  PrepareBody,
  RevokeBody,
  CancelBody,
]);

function json(body: unknown, status = 200): NextResponse {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, private",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function actor(ctx: AdminContext): TemplateTwinRollbackActor | null {
  const practiceId = ctx.session.user.practiceId;
  if (!practiceId) return null;
  return {
    userId: ctx.session.user.id,
    userEmail: ctx.session.user.email,
    practiceId,
  };
}

function errorResponse(error: unknown): NextResponse {
  if (!(error instanceof TemplateTwinRollbackControlError)) {
    return json({ ok: false, error: "Rollback control failed closed." }, 500);
  }
  const status =
    error.code === "TEMPLATE_TWIN_ROLLBACK_INVALID_REQUEST"
      ? 400
      : error.code === "TEMPLATE_TWIN_ROLLBACK_OPERATOR_UNAUTHORIZED"
        ? 403
        : error.code === "TEMPLATE_TWIN_ROLLBACK_CONTROL_UNAVAILABLE"
          ? 503
          : 409;
  return json(
    {
      ok: false,
      code: error.code,
      error: error.message,
      status: error.status,
    },
    status,
  );
}

export const GET = adminApi("template-twin:rollback:inspect", async () => {
  try {
    return json({ ok: true, status: await inspectTemplateTwinRollback() });
  } catch (error) {
    return errorResponse(error);
  }
});

export const POST = adminApi(
  "template-twin:rollback:mutate",
  async (req, ctx) => {
    if (!isSameOriginTemplateTwinMutation(req)) {
      return json(
        { ok: false, error: "The rollback request was not same-origin." },
        403,
      );
    }
    const rollbackActor = actor(ctx);
    if (!rollbackActor) {
      return json(
        {
          ok: false,
          error:
            "The SUPER_ADMIN account must belong to an active audit practice.",
        },
        409,
      );
    }
    const parsed = Body.safeParse(await req.json().catch(() => null));
    if (!parsed.success) {
      return json(
        {
          ok: false,
          error:
            "Provide a valid operation identifier and the exact confirmation for one rollback action.",
        },
        400,
      );
    }

    try {
      const result =
        parsed.data.action === "prepare"
          ? await prepareTemplateTwinRollback({
              operationId: parsed.data.operationId,
              reasonCode: parsed.data.reasonCode,
              changeId: parsed.data.changeId,
              actor: rollbackActor,
            })
          : parsed.data.action === "revoke"
            ? await revokeTemplateTwinRollout({
                operationId: parsed.data.operationId,
                actor: rollbackActor,
              })
            : await cancelPreparedTemplateTwinRollback({
                operationId: parsed.data.operationId,
                actor: rollbackActor,
              });
      return json({ ok: true, ...result });
    } catch (error) {
      return errorResponse(error);
    }
  },
);
