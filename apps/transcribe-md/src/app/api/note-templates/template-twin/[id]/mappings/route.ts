import { NextResponse } from "next/server";

import { AuthError, requireDoctorSession } from "@/lib/auth";
import {
  TemplateTwinLifecycleError,
  updateTemplateTwinMappings,
} from "@/lib/template-twin/certification-lifecycle";
import { TemplateTwinUpdateMappingsRequestSchema } from "@/lib/template-twin/contracts";
import { templateTwinMappingSaveRateLimitOrError } from "@/lib/template-twin/mapping-save-rate-limit";
import { isSameOriginTemplateTwinMutation } from "@/lib/template-twin/request-security";
import {
  TemplateTwinStagingQaLifecycleGuardError,
  runWithTemplateTwinStagingQaLifecycleGuard,
} from "@/lib/template-twin/staging-qa-lifecycle-guard";
import { readTemplateTwinWorkspace } from "@/lib/template-twin/workspace-read";
import { readGuardedTemplateTwinWorkspaceRecovery } from "@/lib/template-twin/workspace-recovery-guarded";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function response(body: unknown, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store, private" },
  });
}

function requestFieldErrors(
  body: unknown,
  issues: readonly { path: readonly PropertyKey[]; message: string }[],
) {
  if (!body || typeof body !== "object") return [];
  const record = body as Record<string, unknown>;
  return issues.flatMap((issue) => {
    const collectionName = issue.path[0];
    const index = issue.path[1];
    const rawSetting = issue.path.at(-1);
    if (
      (collectionName !== "mappings" && collectionName !== "fieldIntents") ||
      typeof index !== "number" ||
      typeof rawSetting !== "string"
    ) {
      return [];
    }
    const collection = record[collectionName];
    const field = Array.isArray(collection) ? collection[index] : null;
    const fieldId =
      field &&
      typeof field === "object" &&
      typeof (field as Record<string, unknown>).fieldId === "string"
        ? String((field as Record<string, unknown>).fieldId)
        : `request-${collectionName}-${index + 1}`;
    const clinicalDetailMissing =
      collectionName === "fieldIntents" && rawSetting === "supportedConcept";
    return [
      {
        fieldId,
        fieldLabel: fieldId,
        fieldNumber: index + 1,
        setting: clinicalDetailMissing ? "clinicalDetail" : rawSetting,
        message: clinicalDetailMissing
          ? "Choose a clinical detail before confirming this field."
          : issue.message,
      },
    ];
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
  let session: Awaited<ReturnType<typeof requireDoctorSession>> | null = null;
  let noteTemplateId: string | null = null;
  try {
    session = await requireDoctorSession();
    const blocked = await templateTwinMappingSaveRateLimitOrError(
      session.user.id,
    );
    if (blocked) return blocked;
    const { id } = await context.params;
    noteTemplateId = id;
    const requestBody = await request.json();
    const parsed =
      TemplateTwinUpdateMappingsRequestSchema.safeParse(requestBody);
    if (!parsed.success) {
      const fieldErrors = requestFieldErrors(requestBody, parsed.error.issues);
      return response(
        {
          ok: false,
          code: "MAPPING_INVALID",
          error:
            fieldErrors[0]?.message ??
            "The mapping draft is invalid. Review the highlighted setting.",
          fieldErrors,
        },
        fieldErrors.length > 0 ? 422 : 400,
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
      isExpectedBusinessError: (error) =>
        error instanceof TemplateTwinLifecycleError,
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
      let latestWorkspace: Awaited<
        ReturnType<typeof readTemplateTwinWorkspace>
      > = null;
      let latestTemplateId: string | null = null;
      if (
        session &&
        noteTemplateId &&
        (error.code === "CONFLICT" ||
          error.code === "IMMUTABLE" ||
          error.code === "NOT_FOUND")
      ) {
        try {
          const recovery = await readGuardedTemplateTwinWorkspaceRecovery({
            noteTemplateId,
            actor: {
              userId: session.user.id,
              practiceId: session.user.practiceId,
              rolloutToken: session.templateTwinRolloutToken,
            },
          });
          if (recovery) {
            latestWorkspace = recovery.workspace;
            latestTemplateId = recovery.candidate.id;
          } else if (error.code === "CONFLICT") {
            // An optimistic save conflict on the same editable version can be
            // rebased against its current authoritative snapshot. Immutable or
            // missing versions must never return their old dead-end workspace.
            latestWorkspace = await readTemplateTwinWorkspace({
              noteTemplateId,
              doctorId: session.user.id,
              practiceId: session.user.practiceId,
            });
            latestTemplateId = latestWorkspace?.template.id ?? null;
          }
        } catch {
          latestWorkspace = null;
          latestTemplateId = null;
        }
      }
      if (
        error.code === "CONFLICT" ||
        error.code === "IMMUTABLE" ||
        error.code === "NOT_FOUND"
      ) {
        return response(
          {
            ok: false,
            code:
              error.code === "CONFLICT"
                ? "VERSION_CONFLICT"
                : error.code === "IMMUTABLE"
                  ? "VERSION_IMMUTABLE"
                  : "VERSION_STALE",
            error:
              error.code === "CONFLICT"
                ? error.message
                : error.code === "IMMUTABLE"
                  ? "This saved version is immutable. Refresh its editable successor to recover your draft."
                  : "This saved version is no longer available. Refresh an editable successor to recover your draft.",
            recoverable: true,
            latestTemplateId,
            latestWorkspace,
            fieldErrors: error.fieldErrors,
          },
          409,
        );
      }
      const status =
        error.code === "MAPPING_INVALID" ||
        error.code === "FIELD_SET_MISMATCH" ||
        error.code === "UNSUPPORTED_CLINICAL_CONCEPT"
          ? 422
          : 409;
      return response(
        {
          ok: false,
          code: error.code,
          error: error.message,
          fieldErrors: error.fieldErrors,
        },
        status,
      );
    }
    if (error instanceof TemplateTwinStagingQaLifecycleGuardError) {
      let latestTemplateId: string | null = null;
      let latestWorkspace: Awaited<
        ReturnType<typeof readTemplateTwinWorkspace>
      > = null;
      if (session && noteTemplateId) {
        try {
          const recovery = await readGuardedTemplateTwinWorkspaceRecovery({
            noteTemplateId,
            actor: {
              userId: session.user.id,
              practiceId: session.user.practiceId,
              rolloutToken: session.templateTwinRolloutToken,
            },
          });
          latestTemplateId = recovery?.candidate.id ?? null;
          latestWorkspace = recovery?.workspace ?? null;
        } catch {
          latestTemplateId = null;
          latestWorkspace = null;
        }
      }
      return response(
        {
          ok: false,
          code: "VERSION_STALE",
          error:
            "This Template Twin version changed or its synthetic authorization expired. Refresh an available version to recover your draft.",
          recoverable: true,
          latestTemplateId,
          latestWorkspace,
        },
        409,
      );
    }
    return response({ ok: false, error: "Mappings were not saved." }, 500);
  }
}
