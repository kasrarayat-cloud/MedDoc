import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";

import {
  recordTemplateTwinReleaseMetricSnapshot,
  TemplateTwinReleaseControlError,
} from "@/lib/template-twin/release-control";
import { TEMPLATE_TWIN_METRIC_DEFINITIONS } from "@/lib/template-twin/release-control-contracts";
import { templateTwinReleaseControlProcessEnabled } from "@/lib/template-twin/release-control-db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

const MAX_BODY_BYTES = 64 * 1024;
const metricKeys = Object.keys(TEMPLATE_TWIN_METRIC_DEFINITIONS) as [
  keyof typeof TEMPLATE_TWIN_METRIC_DEFINITIONS,
  ...(keyof typeof TEMPLATE_TWIN_METRIC_DEFINITIONS)[],
];
const DecimalAggregate = z
  .string()
  .regex(/^(0|[1-9][0-9]*)(\.[0-9]{1,12})?$/u)
  .max(32);
const Body = z
  .object({
    releaseId: z.string().uuid(),
    stage: z.enum([
      "CANARY",
      "PERCENT_10",
      "PERCENT_25",
      "PERCENT_50",
      "PERCENT_100",
    ]),
    expectedReleaseGeneration: z.string().regex(/^[1-9][0-9]{0,18}$/u),
    expectedGlobalGeneration: z.string().regex(/^[1-9][0-9]{0,18}$/u),
    sampleCount: z.number().int().min(0).max(1_000_000_000),
    observationStartedAt: z.iso.datetime({ offset: true }),
    observationEndedAt: z.iso.datetime({ offset: true }),
    metrics: z.record(z.enum(metricKeys), DecimalAggregate),
    attestation: z
      .object({
        version: z.literal("template-twin-metric-attestation-v1"),
        keyId: z.string().regex(/^[A-Za-z0-9][A-Za-z0-9._:-]{2,79}$/u),
        nonce: z.string().uuid(),
        issuedAtEpochSeconds: z.number().int().positive(),
        signature: z.string().regex(/^[0-9a-f]{64}$/u),
      })
      .strict(),
  })
  .strict();

function json(body: unknown, status: number): NextResponse {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, private",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
    },
  });
}

function isAdminHost(request: NextRequest): boolean {
  const configured = process.env.ADMIN_PUBLIC_HOST?.trim().toLowerCase();
  const forwarded = request.headers
    .get("x-forwarded-host")
    ?.split(",")[0]
    ?.trim()
    .toLowerCase();
  const host = (forwarded || request.headers.get("host") || "")
    .split(":")[0]
    ?.toLowerCase();
  if (!configured || host !== configured) return false;
  if (process.env.NODE_ENV === "production") {
    return (
      request.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ===
      "https"
    );
  }
  return true;
}

async function boundedBody(request: NextRequest): Promise<unknown> {
  if (
    !/^application\/json(?:\s*;|$)/iu.test(
      request.headers.get("content-type") ?? "",
    )
  ) {
    throw new Error("INVALID_CONTENT_TYPE");
  }
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) {
    throw new Error("BODY_TOO_LARGE");
  }
  const bytes = new Uint8Array(await request.arrayBuffer());
  if (bytes.byteLength === 0 || bytes.byteLength > MAX_BODY_BYTES) {
    throw new Error("BODY_SIZE_INVALID");
  }
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  if (!templateTwinReleaseControlProcessEnabled() || !isAdminHost(request)) {
    return json({ ok: false, error: "Not found." }, 404);
  }
  let parsed: z.infer<typeof Body>;
  try {
    const result = Body.safeParse(await boundedBody(request));
    if (!result.success) {
      return json(
        { ok: false, error: "The aggregate monitoring payload is invalid." },
        400,
      );
    }
    parsed = result.data;
  } catch {
    return json({ ok: false, error: "Provide bounded UTF-8 JSON." }, 400);
  }

  try {
    return json(
      {
        ok: true,
        result: await recordTemplateTwinReleaseMetricSnapshot({
          ...parsed,
          observationStartedAt: new Date(parsed.observationStartedAt),
          observationEndedAt: new Date(parsed.observationEndedAt),
        }),
      },
      200,
    );
  } catch (error) {
    if (error instanceof TemplateTwinReleaseControlError) {
      const status =
        error.code === "TEMPLATE_TWIN_RELEASE_INVALID_REQUEST"
          ? 400
          : error.code === "TEMPLATE_TWIN_RELEASE_UNAUTHORIZED"
            ? 403
            : error.code === "TEMPLATE_TWIN_RELEASE_CONTROL_UNAVAILABLE"
              ? 503
              : 409;
      return json(
        { ok: false, code: error.code, error: error.message },
        status,
      );
    }
    return json(
      { ok: false, error: "Signed monitoring ingestion failed closed." },
      503,
    );
  }
}
