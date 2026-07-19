import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";

import { adminApi, type AdminContext } from "@/lib/admin-api-gate";
import {
  activateTemplateTwinReleaseCheckpoint,
  createTemplateTwinReleaseCandidate,
  freezeTemplateTwinReleaseCandidate,
  inspectTemplateTwinReleaseControl,
  passTemplateTwinReleaseCheckpoint,
  recordTemplateTwinReleaseApproval,
  recordTemplateTwinReleaseMetricSnapshot,
  revokeTemplateTwinRelease,
  TemplateTwinReleaseControlError,
  type TemplateTwinReleaseActor,
} from "@/lib/template-twin/release-control";
import { TemplateTwinReleaseContractError } from "@/lib/template-twin/release-control-contracts";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const MAX_BODY_BYTES = 256 * 1024;
const Uuid = z.string().uuid();
const Generation = z.string().regex(/^[1-9][0-9]{0,18}$/u);
const Sha256 = z.string().regex(/^[0-9a-f]{64}$/u);
const CommitSha = z.string().regex(/^[0-9a-f]{40}$/u);
const ImageDigest = z.string().regex(/^sha256:[0-9a-f]{64}$/u);
const Stage = z.enum([
  "CANARY",
  "PERCENT_10",
  "PERCENT_25",
  "PERCENT_50",
  "PERCENT_100",
]);
const Discipline = z.enum([
  "DESKTOP_WORD",
  "CLINICAL_SAFETY",
  "PRIVACY_LEGAL",
  "OPERATIONS",
]);

const CreateBody = z
  .object({
    action: z.literal("create"),
    confirmation: z.literal("CREATE EXACT RELEASE"),
    evidence: z
      .object({
        sourceCommitSha: CommitSha,
        baseCommitSha: CommitSha,
        appImageDigest: ImageDigest,
        workerImageDigest: ImageDigest,
        migratorImageDigest: ImageDigest,
        testCensusEvidenceSha256: Sha256,
        independentReviewEvidenceSha256: Sha256,
        securityEvidenceSha256: Sha256,
        migrationRestoreEvidenceSha256: Sha256,
        officeWordEvidenceSha256: Sha256,
      })
      .strict(),
    guardrailPolicy: z.unknown(),
    authorizedPracticeIds: z
      .array(z.string().min(2).max(128))
      .min(1)
      .max(10_000),
    canaryPracticeIds: z.array(z.string().min(2).max(128)).min(1).max(1_000),
  })
  .strict();
const FreezeBody = z
  .object({
    action: z.literal("freeze"),
    releaseId: Uuid,
    expectedReleaseGeneration: Generation,
    confirmation: z.string().min(1).max(160),
  })
  .strict();
const ApprovalBody = z
  .object({
    action: z.literal("record_approval"),
    releaseId: Uuid,
    expectedReleaseGeneration: Generation,
    discipline: Discipline,
    decision: z.enum(["APPROVE", "REJECT", "REVOKE"]),
    evidenceSha256: Sha256,
    confirmation: z.string().min(1).max(160),
  })
  .strict();
const ActivateBody = z
  .object({
    action: z.literal("activate_checkpoint"),
    releaseId: Uuid,
    stage: Stage,
    expectedReleaseGeneration: Generation,
    expectedGlobalGeneration: Generation,
    confirmation: z.string().min(1).max(160),
  })
  .strict();
const MetricsBody = z
  .object({
    action: z.literal("record_metrics"),
    releaseId: Uuid,
    stage: Stage,
    expectedReleaseGeneration: Generation,
    expectedGlobalGeneration: Generation,
    sampleCount: z.number().int().min(0).max(1_000_000_000),
    observationStartedAt: z.iso.datetime({ offset: true }),
    observationEndedAt: z.iso.datetime({ offset: true }),
    metrics: z.record(z.string(), z.number()),
  })
  .strict();
const PassBody = z
  .object({
    action: z.literal("pass_checkpoint"),
    releaseId: Uuid,
    stage: Stage,
    expectedReleaseGeneration: Generation,
    expectedGlobalGeneration: Generation,
    confirmation: z.string().min(1).max(160),
  })
  .strict();
const RevokeBody = z
  .object({
    action: z.literal("revoke_release"),
    releaseId: Uuid,
    expectedReleaseGeneration: Generation,
    expectedGlobalGeneration: Generation,
    reasonCode: z.string().regex(/^[A-Z][A-Z0-9_]{2,79}$/u),
    confirmation: z.string().min(1).max(160),
  })
  .strict();
const Body = z.discriminatedUnion("action", [
  CreateBody,
  FreezeBody,
  ApprovalBody,
  ActivateBody,
  MetricsBody,
  PassBody,
  RevokeBody,
]);

function json(body: unknown, status = 200): NextResponse {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, private",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
    },
  });
}

function actor(ctx: AdminContext): TemplateTwinReleaseActor {
  return {
    userId: ctx.session.user.id,
    sessionId: ctx.verifiedSessionId,
  };
}

function isSameOriginAdminMutation(request: NextRequest): boolean {
  if (request.headers.get("sec-fetch-site") === "cross-site") return false;
  const origin = request.headers.get("origin");
  const host = request.headers.get("host")?.trim().toLowerCase();
  if (!origin || !host) return false;
  try {
    const parsed = new URL(origin);
    const protocol =
      request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ??
      new URL(request.url).protocol.replace(":", "");
    return (
      parsed.host.toLowerCase() === host && parsed.protocol === `${protocol}:`
    );
  } catch {
    return false;
  }
}

async function boundedJson(request: NextRequest): Promise<unknown> {
  const contentType = request.headers.get("content-type") ?? "";
  if (!/^application\/json(?:\s*;|$)/iu.test(contentType)) {
    throw new Error("INVALID_JSON_CONTENT_TYPE");
  }
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) {
    throw new Error("JSON_BODY_TOO_LARGE");
  }
  if (!request.body) throw new Error("INVALID_JSON_BODY");
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      size += next.value.byteLength;
      if (size > MAX_BODY_BYTES) {
        await reader.cancel();
        throw new Error("JSON_BODY_TOO_LARGE");
      }
      chunks.push(next.value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
}

function errorResponse(error: unknown): NextResponse {
  if (error instanceof TemplateTwinReleaseControlError) {
    const status =
      error.code === "TEMPLATE_TWIN_RELEASE_INVALID_REQUEST"
        ? 400
        : error.code === "TEMPLATE_TWIN_RELEASE_UNAUTHORIZED"
          ? 403
          : error.code === "TEMPLATE_TWIN_RELEASE_NOT_FOUND"
            ? 404
            : error.code === "TEMPLATE_TWIN_RELEASE_CONTROL_UNAVAILABLE"
              ? 503
              : 409;
    return json({ ok: false, code: error.code, error: error.message }, status);
  }
  if (error instanceof TemplateTwinReleaseContractError) {
    return json({ ok: false, code: error.code, error: error.message }, 400);
  }
  return json(
    { ok: false, error: "Template Twin release control failed closed." },
    500,
  );
}

export const GET = adminApi(
  "template-twin:releases:inspect",
  async (request, ctx) => {
    const releaseId =
      new URL(request.url).searchParams.get("releaseId") ?? undefined;
    try {
      return json({
        ok: true,
        control: await inspectTemplateTwinReleaseControl({
          releaseId,
          operatorUserId: ctx.session.user.id,
        }),
      });
    } catch (error) {
      return errorResponse(error);
    }
  },
);

export const POST = adminApi(
  "template-twin:releases:mutate",
  async (request, ctx) => {
    if (!isSameOriginAdminMutation(request)) {
      return json(
        {
          ok: false,
          error: "The release-control request was not same-origin.",
        },
        403,
      );
    }
    let parsedBody: z.infer<typeof Body>;
    try {
      const parsed = Body.safeParse(await boundedJson(request));
      if (!parsed.success) {
        return json(
          {
            ok: false,
            error:
              "Release-control input is invalid or contains unsupported fields.",
          },
          400,
        );
      }
      parsedBody = parsed.data;
    } catch {
      return json(
        { ok: false, error: "Provide a bounded UTF-8 JSON request body." },
        400,
      );
    }

    const releaseActor = actor(ctx);
    try {
      switch (parsedBody.action) {
        case "create":
          return json({
            ok: true,
            result: await createTemplateTwinReleaseCandidate({
              actor: releaseActor,
              confirmation: parsedBody.confirmation,
              evidence: parsedBody.evidence,
              guardrailPolicy: parsedBody.guardrailPolicy,
              authorizedPracticeIds: parsedBody.authorizedPracticeIds,
              canaryPracticeIds: parsedBody.canaryPracticeIds,
            }),
          });
        case "freeze":
          return json({
            ok: true,
            result: await freezeTemplateTwinReleaseCandidate({
              actor: releaseActor,
              ...parsedBody,
            }),
          });
        case "record_approval":
          return json({
            ok: true,
            result: await recordTemplateTwinReleaseApproval({
              actor: releaseActor,
              ...parsedBody,
            }),
          });
        case "activate_checkpoint":
          return json({
            ok: true,
            result: await activateTemplateTwinReleaseCheckpoint({
              actor: releaseActor,
              ...parsedBody,
            }),
          });
        case "record_metrics":
          return json({
            ok: true,
            result: await recordTemplateTwinReleaseMetricSnapshot({
              actor: releaseActor,
              ...parsedBody,
              observationStartedAt: new Date(parsedBody.observationStartedAt),
              observationEndedAt: new Date(parsedBody.observationEndedAt),
            }),
          });
        case "pass_checkpoint":
          return json({
            ok: true,
            result: await passTemplateTwinReleaseCheckpoint({
              actor: releaseActor,
              ...parsedBody,
            }),
          });
        case "revoke_release":
          return json({
            ok: true,
            result: await revokeTemplateTwinRelease({
              actor: releaseActor,
              ...parsedBody,
            }),
          });
      }
    } catch (error) {
      return errorResponse(error);
    }
  },
);
