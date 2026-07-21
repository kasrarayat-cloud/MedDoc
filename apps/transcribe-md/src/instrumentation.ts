/** Next.js 16 server-start hook; see node_modules/next/dist/docs. */
export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("../sentry.edge.config");
    return;
  }
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  try {
    const {
      isUnconfiguredNextProductionBuild,
      requiresExactQuillmdRuntimeIdentity,
    } = await import("@meddoc/auth/runtime-identity");
    // `next build` can load instrumentation while producing standalone
    // output; the actual production-server process is the startup boundary.
    if (isUnconfiguredNextProductionBuild(process.env)) {
      return;
    }
    const { assertQuillmdRuntimeProtocol } =
      await import("./lib/runtime-protocol");
    assertQuillmdRuntimeProtocol(process.env);
    if (requiresExactQuillmdRuntimeIdentity(process.env)) {
      const serviceRole = process.env.QUILLMD_SERVICE_ROLE;
      const principalProfile = process.env.QUILLMD_DATABASE_PRINCIPAL_PROFILE;
      if (
        process.env.NODE_ENV !== "production" ||
        ![
          "physician-app",
          "template-twin-admin-app",
          "template-twin-admin-control",
        ].includes(serviceRole ?? "") ||
        (principalProfile !== "exact-production-v1" &&
          !(
            serviceRole === "physician-app" &&
            principalProfile === "synthetic-disposable-qa-v1"
          ))
      ) {
        throw new Error(
          "TranscribeMD application runtime identity is invalid.",
        );
      }
      const [
        { default: prisma },
        { assertProductionRuntimeDatabasePrincipal },
        { evaluateTemplateTwinStagingQaResourceBoundary },
      ] = await Promise.all([
        import("@meddoc/db"),
        import("@meddoc/db/production-runtime-principal"),
        import("./lib/template-twin/staging-qa-gate"),
      ]);
      await assertProductionRuntimeDatabasePrincipal({
        prisma,
        environment: process.env,
        syntheticQaResourceBoundaryAllowed:
          evaluateTemplateTwinStagingQaResourceBoundary(process.env).allowed,
      });
    }
    const { assertAdminSurfaceRuntimeConfiguration } =
      await import("./lib/admin-host");
    assertAdminSurfaceRuntimeConfiguration(process.env);
    const [{ assertAuthOriginRuntimeConfiguration }, { APP_URL }] =
      await Promise.all([
        import("./lib/auth-origin"),
        import("./lib/constants"),
      ]);
    assertAuthOriginRuntimeConfiguration(process.env, APP_URL);
    const { assertMfaSecretRuntimeConfiguration } =
      await import("./lib/mfa-secret-envelope");
    assertMfaSecretRuntimeConfiguration(process.env);
  } catch (error) {
    const { terminateForFatalStartupConfiguration } =
      await import("./lib/fatal-startup");
    terminateForFatalStartupConfiguration(error);
  }
  await import("../sentry.server.config");
}
