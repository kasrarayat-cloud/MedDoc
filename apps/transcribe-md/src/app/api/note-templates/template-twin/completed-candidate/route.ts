import { NextResponse } from "next/server";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import { TemplateDocxError } from "@/lib/note-template-docx";
import { RATE_LIMITS, rateLimitOr429 } from "@/lib/rate-limit";
import { completedCandidateSyntheticModeEnabled } from "@/lib/template-twin/completed-candidate-access";
import { CompletedCandidateIdentitySchema } from "@/lib/template-twin/completed-candidate-contract";
import { CompletedCandidateConversionError } from "@/lib/template-twin/completed-candidate-converter";
import {
  CompletedCandidateServiceError,
  createCompletedCandidate,
} from "@/lib/template-twin/completed-candidate-service";
import {
  TemplateTwinMalwareRejectedError,
  TemplateTwinMalwareScanUnavailableError,
} from "@/lib/template-twin/malware-scan";
import { TemplateTwinQuarantineError } from "@/lib/template-twin/quarantine-admission";
import {
  boundedMultipartFormData,
  isMultipartFile,
  isSameOriginTemplateTwinMutation,
  TemplateTwinMultipartError,
} from "@/lib/template-twin/request-security";
import { isTemplateTwinStagingQaRequested } from "@/lib/template-twin/staging-qa-gate";
import {
  TemplateTwinArtifactTooLargeError,
  TemplateTwinStorageUnavailableError,
} from "@/lib/template-twin/storage";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

const MAX_EXAMPLE_BYTES = 10 * 1024 * 1024;
const MAX_MULTIPART_BYTES = 3 * MAX_EXAMPLE_BYTES + 512 * 1024;
const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, private",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function safeFailure(error: unknown): { status: number; message: string } {
  if (error instanceof AuthError) {
    return {
      status: error.code === "FORBIDDEN" ? 403 : 401,
      message:
        error.code === "FORBIDDEN"
          ? error.message
          : "Sign in again before converting examples.",
    };
  }
  if (error instanceof CompletedCandidateConversionError) {
    return { status: 422, message: error.message };
  }
  if (error instanceof TemplateTwinMalwareRejectedError) {
    return { status: 422, message: error.message };
  }
  if (error instanceof TemplateTwinMalwareScanUnavailableError) {
    return { status: 503, message: error.message };
  }
  if (error instanceof TemplateTwinQuarantineError) {
    return {
      status:
        error.code === "TEMPLATE_TWIN_QUARANTINE_STATE_CONFLICT" ? 409 : 503,
      message: error.message,
    };
  }
  if (error instanceof TemplateTwinMultipartError) {
    return {
      status: error.code === "MULTIPART_TOO_LARGE" ? 413 : 400,
      message:
        error.code === "MULTIPART_TOO_LARGE"
          ? "Upload two or three DOCX examples, each no larger than 10 MB."
          : "The completed-example request was malformed.",
    };
  }
  if (
    error instanceof TemplateTwinStorageUnavailableError ||
    error instanceof TemplateTwinArtifactTooLargeError
  ) {
    return {
      status: error instanceof TemplateTwinArtifactTooLargeError ? 413 : 503,
      message:
        error instanceof TemplateTwinArtifactTooLargeError
          ? "A generated artifact exceeds the supported size."
          : "Private Template Twin storage is unavailable. The examples remain isolated.",
    };
  }
  if (error instanceof TemplateDocxError) {
    return {
      status: 422,
      message:
        "A Word package failed the completed-example safety boundary. Save clean macro-free DOCX copies and try again.",
    };
  }
  if (error instanceof CompletedCandidateServiceError) {
    return {
      status:
        error.code === "INVALID_INPUT"
          ? 400
          : error.code === "ROLLOUT_CHANGED" || error.code === "REVIEW_CONFLICT"
            ? 409
            : error.code === "NOT_FOUND"
              ? 404
              : 503,
      message: error.message,
    };
  }
  return {
    status: 500,
    message:
      "The completed examples were not converted. No template was activated.",
  };
}

export async function POST(request: Request) {
  if (
    !completedCandidateSyntheticModeEnabled() ||
    isTemplateTwinStagingQaRequested()
  ) {
    return response({ ok: false, error: "not found" }, 404);
  }
  if (!isSameOriginTemplateTwinMutation(request)) {
    return response(
      { ok: false, error: "The conversion request was not same-origin." },
      403,
    );
  }
  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > MAX_MULTIPART_BYTES) {
    return response(
      {
        ok: false,
        error: "Upload two or three DOCX examples, each no larger than 10 MB.",
      },
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
    const files = formData.getAll("examples");
    if (
      files.length < 2 ||
      files.length > 3 ||
      files.some((file) => !isMultipartFile(file))
    ) {
      return response(
        {
          ok: false,
          error: "Choose two or three completed synthetic DOCX examples.",
        },
        400,
      );
    }
    const typedFiles = files as File[];
    for (const file of typedFiles) {
      const lowerName = file.name.toLowerCase();
      if (!lowerName.endsWith(".docx") || lowerName.endsWith(".docm")) {
        return response(
          {
            ok: false,
            error: "Every example must be a macro-free .docx file.",
          },
          415,
        );
      }
      if (
        file.type &&
        file.type !== DOCX_MIME &&
        file.type !== "application/octet-stream"
      ) {
        return response(
          {
            ok: false,
            error: "Every selected example must be a DOCX package.",
          },
          415,
        );
      }
      if (file.size < 1 || file.size > MAX_EXAMPLE_BYTES) {
        return response(
          {
            ok: false,
            error: "Each completed DOCX example must be no larger than 10 MB.",
          },
          413,
        );
      }
    }
    const identity = CompletedCandidateIdentitySchema.safeParse({
      name: formData.get("candidateName"),
      encounterScope: formData.get("encounterScope"),
      versionDescription: formData.get("versionDescription"),
    });
    if (!identity.success) {
      return response(
        {
          ok: false,
          error: "Name the candidate, choose its visit scope, and describe it.",
        },
        400,
      );
    }
    if (formData.get("syntheticAttestation") !== "true") {
      return response(
        {
          ok: false,
          error:
            "Confirm that every example is synthetic and contains no patient information.",
        },
        400,
      );
    }
    const examples = await Promise.all(
      typedFiles.map(async (file) => {
        const source = new Uint8Array(await file.arrayBuffer());
        if (source.byteLength !== file.size) {
          throw new CompletedCandidateServiceError(
            "INVALID_INPUT",
            "An uploaded example was incomplete. Try again.",
          );
        }
        return source;
      }),
    );
    const result = await createCompletedCandidate({
      examples,
      identity: identity.data,
      actor: {
        userId: session.user.id,
        userEmail: session.user.email,
        practiceId: session.user.practiceId,
        rolloutToken: session.templateTwinRolloutToken,
      },
    });
    return response({ ok: true, ...result }, 201);
  } catch (error) {
    const safe = safeFailure(error);
    return response({ ok: false, error: safe.message }, safe.status);
  }
}
