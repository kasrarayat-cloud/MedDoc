// ============================================================================
// Next.js register() hook — Sentry runtime dispatch (M7)
// ----------------------------------------------------------------------------
// Next calls register() once per runtime. We load the matching Sentry
// config based on which runtime is active. Sentry docs style.
// ============================================================================

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    try {
      const {
        isUnconfiguredNextProductionBuild,
        requiresExactQuillmdRuntimeIdentity,
      } = await import("@meddoc/auth/runtime-identity");
      if (
        !isUnconfiguredNextProductionBuild(process.env) &&
        requiresExactQuillmdRuntimeIdentity(process.env)
      ) {
        if (
          process.env.NODE_ENV !== "production" ||
          process.env.QUILLMD_SERVICE_ROLE !== "meddoc-pro-app" ||
          process.env.QUILLMD_DATABASE_PRINCIPAL_PROFILE !==
            "exact-production-v1" ||
          Boolean(process.env.QUILLMD_AUTH_SESSION_VERIFIER_PROFILE?.trim())
        ) {
          throw new Error("MedDoc Pro runtime identity is invalid.");
        }
        const [
          { default: prisma },
          { assertProductionRuntimeDatabasePrincipal },
        ] = await Promise.all([
          import("@meddoc/db"),
          import("@meddoc/db/production-runtime-principal"),
        ]);
        await assertProductionRuntimeDatabasePrincipal({
          prisma,
          environment: process.env,
          syntheticQaResourceBoundaryAllowed: false,
        });
      }
    } catch (error) {
      const { terminateForFatalStartupConfiguration } =
        await import("./src/lib/fatal-startup");
      terminateForFatalStartupConfiguration(error);
    }
    await import("./sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}
