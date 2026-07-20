import { NextResponse } from "next/server";

import prisma from "@meddoc/db";

import { configuredTemplateTwinLocalOcr } from "@/lib/template-twin/static-asset-ocr";
import { isTemplateTwinAdminAppService } from "@/lib/template-twin/admin-app-service";
import { refreshTemplateTwinRuntimeAttestation } from "@/lib/template-twin/runtime-attestation";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

function closed() {
  return new NextResponse("Not Found", {
    status: 404,
    headers: { "Cache-Control": "no-store" },
  });
}

export async function GET() {
  if (!isTemplateTwinAdminAppService()) return closed();

  const [database, localOcr, runtimeIdentity] = await Promise.all([
    prisma.$queryRaw`SELECT 1`.then(() => true).catch(() => false),
    configuredTemplateTwinLocalOcr().catch(() => ({
      ready: false as const,
      code: "TT_STATIC_ASSET_LOCAL_OCR_UNAVAILABLE" as const,
      message: "Local OCR readiness could not be verified.",
    })),
    refreshTemplateTwinRuntimeAttestation({ tx: prisma }).catch(
      () => "INVALID" as const,
    ),
  ]);
  const providerConfigured = Boolean(process.env.ANTHROPIC_API_KEY?.trim());
  const healthy =
    database &&
    localOcr.ready &&
    providerConfigured &&
    runtimeIdentity !== "INVALID";

  return NextResponse.json(
    {
      status: healthy ? "healthy" : "unhealthy",
      service: "template-twin-admin-app",
      checks: {
        database,
        localOcr: localOcr.ready,
        providerConfigured,
        runtimeIdentity,
      },
    },
    {
      status: healthy ? 200 : 503,
      headers: { "Cache-Control": "no-store, no-cache, must-revalidate" },
    },
  );
}
