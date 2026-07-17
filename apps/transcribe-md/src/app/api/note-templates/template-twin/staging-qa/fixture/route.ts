import { NextResponse } from "next/server";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { templateTwinStagingQaFixtureDescriptor } from "@/lib/template-twin/staging-qa-fixtures";
import {
  assertTemplateTwinStagingQaGate,
  TemplateTwinStagingQaDisabledError,
} from "@/lib/template-twin/staging-qa-gate";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    assertTemplateTwinStagingQaGate();
    await requireDoctorSession();
    const fixture = await templateTwinStagingQaFixtureDescriptor();
    return new NextResponse(fixture.bytes as unknown as BodyInit, {
      status: 200,
      headers: {
        "Content-Type": fixture.mimeType,
        "Content-Length": String(fixture.sizeBytes),
        "Content-Disposition": `attachment; filename="${fixture.filename}"`,
        "Cache-Control": "no-store, private",
        "X-Content-Type-Options": "nosniff",
        "X-Template-Twin-Fixture-Version": fixture.fixtureVersion,
        "X-Template-Twin-Fixture-SHA256": fixture.sha256,
      },
    });
  } catch (error) {
    if (
      error instanceof AuthError ||
      error instanceof TemplateTwinStagingQaDisabledError
    ) {
      return NextResponse.json({ error: "not found" }, { status: 404 });
    }
    return NextResponse.json(
      { error: "Synthetic QA fixture is unavailable." },
      { status: 503 },
    );
  }
}
