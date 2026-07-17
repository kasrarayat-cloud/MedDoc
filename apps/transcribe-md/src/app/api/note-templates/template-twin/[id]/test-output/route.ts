import { NextResponse } from "next/server";
import prisma from "@meddoc/db";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import {
  createTemplateTwinArtifactStore,
  DOCX_MIME_TYPE,
} from "@/lib/template-twin/storage";
import {
  assertTemplateTwinStagingQaLifecycleFinality,
  TemplateTwinStagingQaLifecycleGuardError,
  runWithTemplateTwinStagingQaLifecycleGuard,
} from "@/lib/template-twin/staging-qa-lifecycle-guard";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function json(error: string, status: number) {
  return NextResponse.json(
    { ok: false, error },
    { status, headers: { "Cache-Control": "no-store, private" } },
  );
}

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  try {
    const session = await requireDoctorSession();
    const { id } = await context.params;
    const actor = {
      userId: session.user.id,
      practiceId: session.user.practiceId,
      rolloutToken: session.templateTwinRolloutToken,
    };
    return await runWithTemplateTwinStagingQaLifecycleGuard({
      noteTemplateId: id,
      actor,
      purpose: "synthetic-test-output-download",
      operation: async () => {
        const row = await prisma.noteTemplate.findFirst({
          where: {
            id,
            doctorId: session.user.id,
            templateKind: "template_twin_docx",
          },
          select: {
            name: true,
            templateTwinCompiledVersion: {
              select: {
                latestTestOutputObjectKey: true,
                latestTestOutputVersionId: true,
                latestTestOutputEtag: true,
                latestTestOutputSha256: true,
                latestTestVerifiedAt: true,
                latestTestRoundTrip: true,
                sourceArtifact: { select: { practiceId: true } },
              },
            },
          },
        });
        const compiled = row?.templateTwinCompiledVersion;
        const roundTrip = compiled?.latestTestRoundTrip as {
          verified?: boolean;
        } | null;
        if (
          !row ||
          !compiled ||
          compiled.sourceArtifact.practiceId !== session.user.practiceId ||
          !compiled.latestTestOutputObjectKey ||
          !compiled.latestTestOutputVersionId ||
          !compiled.latestTestOutputEtag ||
          !compiled.latestTestOutputSha256 ||
          !compiled.latestTestVerifiedAt ||
          roundTrip?.verified !== true
        ) {
          return json("No verified synthetic DOCX is available.", 404);
        }
        const document =
          await createTemplateTwinArtifactStore().readOutputArtifact({
            practiceId: session.user.practiceId,
            objectKey: compiled.latestTestOutputObjectKey,
            expectedObjectVersionId: compiled.latestTestOutputVersionId,
            expectedObjectEtag: compiled.latestTestOutputEtag,
            expectedSha256: compiled.latestTestOutputSha256,
          });
        // This is the response authorization linearization point. A disable
        // either commits before these locks and rejects the download, or waits
        // until this authorization commits; stale generations never re-pin.
        await assertTemplateTwinStagingQaLifecycleFinality({
          noteTemplateId: id,
          actor,
        });
        const safeName =
          row.name.replace(/[^A-Za-z0-9._-]+/g, "-").slice(0, 80) ||
          "template-twin";
        return new NextResponse(new Uint8Array(document), {
          status: 200,
          headers: {
            "Content-Type": DOCX_MIME_TYPE,
            "Content-Disposition": `attachment; filename="${safeName}-synthetic-test.docx"`,
            "Content-Length": String(document.byteLength),
            "Cache-Control": "no-store, private",
            "X-Content-Type-Options": "nosniff",
          },
        });
      },
    });
  } catch (error) {
    if (error instanceof AuthError) {
      return json(
        error.code === "FORBIDDEN"
          ? error.message
          : "Sign in again before downloading.",
        error.code === "FORBIDDEN" ? 403 : 401,
      );
    }
    if (error instanceof TemplateTwinStagingQaLifecycleGuardError) {
      return json("No verified synthetic DOCX is available.", 404);
    }
    return json("The verified synthetic DOCX could not be downloaded.", 500);
  }
}
