import { NextResponse } from "next/server";
import { z } from "zod";

import { AuthError, requireDoctorSession } from "@/lib/auth";
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
  TemplateTwinPhiRejectedError,
  TemplateTwinPhiScanUnavailableError,
  TemplateTwinSourcePrivacyUnsupportedError,
} from "@/lib/template-twin/source-phi";
import {
  TemplateTwinArtifactTooLargeError,
  TemplateTwinStorageUnavailableError,
} from "@/lib/template-twin/storage";
import { TemplateDocxError } from "@/lib/note-template-docx";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import {
  isTemplateTwinStagingQaFixtureSource,
  templateTwinStagingQaSha256,
} from "@/lib/template-twin/staging-qa-fixtures";
import { isTemplateTwinStagingQaRequested } from "@/lib/template-twin/staging-qa-gate";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

const MAX_SOURCE_BYTES = 10 * 1024 * 1024;
const MAX_MULTIPART_BYTES = MAX_SOURCE_BYTES + 256 * 1024;
const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const TemplateIdentitySchema = z.object({
  name: z.string().trim().min(3).max(120),
  encounterType: z.string().trim().min(3).max(120),
  versionDescription: z.string().trim().min(3).max(500),
});

function json(
  body: { ok: true; certificationUrl: string } | { ok: false; error: string },
  status: number,
) {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, private",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function safeError(error: unknown): { status: number; message: string } {
  if (error instanceof AuthError) {
    return {
      status: error.code === "FORBIDDEN" ? 403 : 401,
      message:
        error.code === "FORBIDDEN"
          ? error.message
          : "Sign in again before uploading a template.",
    };
  }
  if (error instanceof TemplateTwinPhiRejectedError) {
    return { status: 422, message: error.message };
  }
  if (error instanceof TemplateTwinSourcePrivacyUnsupportedError) {
    return { status: 422, message: error.message };
  }
  if (error instanceof TemplateTwinMultipartError) {
    return {
      status: error.code === "MULTIPART_TOO_LARGE" ? 413 : 400,
      message:
        error.code === "MULTIPART_TOO_LARGE"
          ? "Template Twin accepts DOCX files up to 10 MB."
          : "The template upload request was malformed.",
    };
  }
  if (error instanceof TemplateTwinPhiScanUnavailableError) {
    return { status: 503, message: error.message };
  }
  if (
    error instanceof TemplateTwinStorageUnavailableError ||
    error instanceof TemplateTwinArtifactTooLargeError
  ) {
    return {
      status: error instanceof TemplateTwinArtifactTooLargeError ? 413 : 503,
      message:
        error instanceof TemplateTwinArtifactTooLargeError
          ? "The compiled Word artifact exceeds the supported size."
          : "Private Template Twin storage is not available. The template was not activated.",
    };
  }
  if (error instanceof TemplateDocxError) {
    if (error.code === "DOCM_REJECTED") {
      return {
        status: 422,
        message:
          "Macro-enabled Word files are not accepted. Save a clean .docx copy.",
      };
    }
    if (
      error.code === "EXTERNAL_RELATIONSHIP_REJECTED" ||
      error.code === "EMBEDDED_OBJECT_REJECTED" ||
      error.code === "ACTIVE_CONTENT_REJECTED"
    ) {
      return {
        status: 422,
        message:
          "The Word file contains external, embedded, or active content that cannot be certified.",
      };
    }
    return {
      status: 422,
      message:
        "The Word package failed structural safety checks. Open it in Word, save a clean DOCX copy, and try again.",
    };
  }
  if (error instanceof TemplateTwinDraftError) {
    return {
      status:
        error.code === "INVALID_IDENTITY"
          ? 400
          : error.code === "NO_FILLABLE_FIELDS"
            ? 422
            : error.code === "ROLLOUT_CHANGED"
              ? 409
              : 500,
      message: error.message,
    };
  }
  return {
    status: 500,
    message: "The template could not be compiled. Nothing was activated.",
  };
}

export async function POST(request: Request) {
  // An explicit staging-QA request makes this process synthetic-only even when
  // the remaining staging resources are misconfigured. The generic endpoint
  // must not disclose or parse anything; the exact fixture has its own route.
  if (isTemplateTwinStagingQaRequested()) {
    return json({ ok: false, error: "not found" }, 404);
  }

  if (!isSameOriginTemplateTwinMutation(request)) {
    return json(
      { ok: false, error: "The upload request was not same-origin." },
      403,
    );
  }

  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > MAX_MULTIPART_BYTES) {
    return json(
      { ok: false, error: "Template Twin accepts DOCX files up to 10 MB." },
      413,
    );
  }

  try {
    const session = await requireDoctorSession();
    const blocked = rateLimitOr429(RATE_LIMITS.UPLOAD, session.user.id);
    if (blocked) return blocked;
    const formData = await boundedMultipartFormData(
      request,
      MAX_MULTIPART_BYTES,
    );
    const file = formData.get("file");
    if (!isMultipartFile(file)) {
      return json({ ok: false, error: "Choose one original DOCX file." }, 400);
    }
    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith(".docx") || lowerName.endsWith(".docm")) {
      return json({ ok: false, error: "Choose a macro-free .docx file." }, 415);
    }
    if (
      file.type &&
      file.type !== DOCX_MIME &&
      file.type !== "application/octet-stream"
    ) {
      return json(
        { ok: false, error: "The selected file is not a DOCX package." },
        415,
      );
    }
    if (file.size < 1 || file.size > MAX_SOURCE_BYTES) {
      return json(
        {
          ok: false,
          error: "Template Twin accepts non-empty DOCX files up to 10 MB.",
        },
        413,
      );
    }
    const identity = TemplateIdentitySchema.safeParse({
      name: formData.get("templateName"),
      encounterType: formData.get("encounterScope"),
      versionDescription: formData.get("versionDescription"),
    });
    if (!identity.success) {
      return json(
        {
          ok: false,
          error:
            "Name the template, choose its visit scope, and describe this version.",
        },
        400,
      );
    }

    const source = new Uint8Array(await file.arrayBuffer());
    if (source.byteLength !== file.size) {
      return json(
        { ok: false, error: "The uploaded file was incomplete. Try again." },
        400,
      );
    }
    // The reserved exact fixture may only enter through the staging-specific
    // route, which applies isolated-resource and deterministic-provider
    // admission before compilation. Never let generic upload create a draft
    // that can later traverse ordinary lifecycle routes.
    if (
      isTemplateTwinStagingQaFixtureSource({
        sha256: templateTwinStagingQaSha256(source),
        sizeBytes: source.byteLength,
      })
    ) {
      return json(
        {
          ok: false,
          error:
            "Use the Template Twin synthetic QA workflow for this reserved test document.",
        },
        422,
      );
    }

    const result = await createTemplateTwinDraft({
      source,
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
        rolloutToken: session.templateTwinRolloutToken,
      },
      identity: identity.data,
    });
    return json(
      {
        ok: true,
        certificationUrl: `/settings/note-format/${encodeURIComponent(result.noteTemplateId)}/certify`,
      },
      201,
    );
  } catch (error) {
    const safe = safeError(error);
    return json({ ok: false, error: safe.message }, safe.status);
  }
}
