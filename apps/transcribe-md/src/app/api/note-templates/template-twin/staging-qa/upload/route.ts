import { NextResponse } from "next/server";
import { z } from "zod";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import {
  createTemplateTwinDraft,
  TemplateTwinDraftError,
} from "@/lib/template-twin/create-draft";
import {
  boundedMultipartFormData,
  isMultipartFile,
  isSameOriginTemplateTwinMutation,
  TemplateTwinMultipartError,
} from "@/lib/template-twin/request-security";
import {
  TEMPLATE_TWIN_STAGING_QA_ENCOUNTER_SCOPE,
  TEMPLATE_TWIN_STAGING_QA_TEMPLATE_NAME,
  TEMPLATE_TWIN_STAGING_QA_VERSION_DESCRIPTION,
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  templateTwinStagingQaFixtureDescriptor,
  templateTwinStagingQaSha256,
} from "@/lib/template-twin/staging-qa-fixtures";
import {
  assertTemplateTwinStagingQaGate,
  TemplateTwinStagingQaDisabledError,
} from "@/lib/template-twin/staging-qa-gate";
import {
  runWithTemplateTwinStagingQaUploadProvider,
  TemplateTwinStagingQaUploadProviderError,
} from "@/lib/template-twin/staging-qa-upload-provider";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

const MAX_MULTIPART_BYTES = 1024 * 1024;
const IdentitySchema = z
  .object({
    templateName: z.literal(TEMPLATE_TWIN_STAGING_QA_TEMPLATE_NAME),
    encounterScope: z.literal(TEMPLATE_TWIN_STAGING_QA_ENCOUNTER_SCOPE),
    versionDescription: z.literal(TEMPLATE_TWIN_STAGING_QA_VERSION_DESCRIPTION),
  })
  .strict();

function response(body: Record<string, unknown>, status: number): NextResponse {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, private",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

export async function POST(request: Request) {
  if (!isSameOriginTemplateTwinMutation(request)) {
    return response({ ok: false, error: "not found" }, 404);
  }
  try {
    assertTemplateTwinStagingQaGate();
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, session.user.id);
    if (blocked) return blocked;
    const form = await boundedMultipartFormData(request, MAX_MULTIPART_BYTES);
    const file = form.get("file");
    if (!isMultipartFile(file)) {
      return response(
        { ok: false, error: "Choose the synthetic QA DOCX." },
        400,
      );
    }
    const identity = IdentitySchema.safeParse({
      templateName: form.get("templateName"),
      encounterScope: form.get("encounterScope"),
      versionDescription: form.get("versionDescription"),
    });
    if (!identity.success) {
      return response(
        {
          ok: false,
          error:
            "Name this synthetic template, scope it, and describe the version.",
        },
        400,
      );
    }
    const fixtureVersion = form.get("fixtureVersion");
    // Local file names and browser MIME values are advisory and can change
    // after download. The version plus exact byte length/SHA-256 below is the
    // immutable synthetic allowlist identity.
    if (fixtureVersion !== TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION) {
      return response(
        {
          ok: false,
          error: "Only the identified synthetic QA fixture is accepted here.",
          code: "SYNTHETIC_FIXTURE_IDENTITY_MISMATCH",
        },
        422,
      );
    }
    const source = new Uint8Array(await file.arrayBuffer());
    const fixture = await templateTwinStagingQaFixtureDescriptor();
    if (
      source.byteLength !== fixture.sizeBytes ||
      templateTwinStagingQaSha256(source) !== fixture.sha256
    ) {
      return response(
        {
          ok: false,
          error:
            "Only the byte-verified synthetic QA fixture is accepted here.",
          code: "SYNTHETIC_FIXTURE_NOT_ALLOWLISTED",
        },
        422,
      );
    }
    const actor = {
      userId: session.user.id,
      userEmail: session.user.email,
      practiceId: session.user.practiceId,
      rolloutToken: session.templateTwinRolloutToken,
    };
    const result = await runWithTemplateTwinStagingQaUploadProvider({
      source: { sha256: fixture.sha256, sizeBytes: fixture.sizeBytes },
      actor,
      operation: (providerVisitId) =>
        createTemplateTwinDraft({
          source,
          identity: {
            name: identity.data.templateName,
            encounterType: identity.data.encounterScope,
            versionDescription: identity.data.versionDescription,
          },
          actor,
          providerVisitId,
        }),
    });
    return response(
      {
        ok: true,
        noteTemplateId: result.noteTemplateId,
        certificationUrl: `/settings/note-format/${encodeURIComponent(result.noteTemplateId)}/certify`,
        sourceSha256: result.sourceSha256,
        compilerVersion: result.compilerVersion,
        fieldCount: result.fieldCount,
        blockingUnsupportedCount: result.blockingUnsupportedCount,
        fixtureVersion: fixture.fixtureVersion,
      },
      201,
    );
  } catch (error) {
    if (
      error instanceof AuthError ||
      error instanceof TemplateTwinStagingQaDisabledError ||
      error instanceof TemplateTwinStagingQaUploadProviderError
    ) {
      return response({ ok: false, error: "not found" }, 404);
    }
    if (error instanceof TemplateTwinMultipartError) {
      return response(
        { ok: false, error: error.message },
        error.code === "MULTIPART_TOO_LARGE" ? 413 : 400,
      );
    }
    if (error instanceof TemplateTwinDraftError) {
      return response(
        { ok: false, error: error.message },
        error.code === "ROLLOUT_CHANGED" ? 409 : 422,
      );
    }
    return response(
      { ok: false, error: "The synthetic template could not be admitted." },
      503,
    );
  }
}
