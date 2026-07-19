import { NextResponse } from "next/server";

import releaseControlDatabase, {
  templateTwinReleaseControlProcessEnabled,
} from "@/lib/template-twin/release-control-db";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(): Promise<NextResponse> {
  if (!templateTwinReleaseControlProcessEnabled()) {
    return new NextResponse("Not Found", { status: 404 });
  }
  try {
    await releaseControlDatabase.$queryRawUnsafe("SELECT 1");
    return NextResponse.json(
      { status: "healthy", service: "template-twin-admin-control" },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return NextResponse.json(
      { status: "unhealthy", service: "template-twin-admin-control" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
