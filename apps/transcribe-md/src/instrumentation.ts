/** Next.js 16 server-start hook; see node_modules/next/dist/docs. */
export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("../sentry.edge.config");
    return;
  }
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  // `next build` can load instrumentation while producing standalone output;
  // the actual production-server process is the startup boundary.
  if (process.env.NEXT_PHASE === "phase-production-build") return;
  const { assertQuillmdRuntimeProtocol } = await import(
    "./lib/runtime-protocol"
  );
  assertQuillmdRuntimeProtocol(process.env);
  await import("../sentry.server.config");
}
