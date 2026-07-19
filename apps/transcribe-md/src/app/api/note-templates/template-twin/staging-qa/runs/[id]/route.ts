import { NextResponse } from "next/server";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import {
  readTemplateTwinStagingQaRun,
  TemplateTwinStagingQaError,
} from "@/lib/template-twin/staging-qa-service";
import { TemplateTwinStagingQaDisabledError } from "@/lib/template-twin/staging-qa-gate";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  try {
    const session = await requireDoctorSession();
    const { id } = await context.params;
    const run = await readTemplateTwinStagingQaRun({
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
        rolloutToken: session.templateTwinRolloutToken,
      },
      runId: id,
    });
    return NextResponse.json(
      { ok: true, run },
      { headers: { "Cache-Control": "no-store, private" } },
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
    if (
      error instanceof TemplateTwinStagingQaError &&
      error.code === "ROLLOUT_CHANGED"
    ) {
      return NextResponse.json(
        { error: error.message, code: error.code },
        { status: 409, headers: { "Cache-Control": "no-store, private" } },
      );
    }
    return NextResponse.json(
      { error: "Synthetic QA status is unavailable." },
      { status: 503 },
    );
  }
}
