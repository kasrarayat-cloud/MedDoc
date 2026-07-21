export type QuillmdRuntimeIdentityEnvironment = Readonly<
  Record<string, string | undefined>
>;

const RUNTIME_IDENTITY_ENVIRONMENTS = Object.freeze([
  "QUILLMD_SERVICE_ROLE",
  "QUILLMD_DATABASE_PRINCIPAL_PROFILE",
  "QUILLMD_AUTH_SESSION_VERIFIER_PROFILE",
] as const);

/**
 * Presence is intentional: an explicitly configured blank identity must not
 * regain the unconfigured local-development exemption.
 */
export function hasConfiguredQuillmdRuntimeIdentity(
  environment: QuillmdRuntimeIdentityEnvironment,
): boolean {
  return RUNTIME_IDENTITY_ENVIRONMENTS.some(
    (key) => environment[key] !== undefined,
  );
}

/** Every real production or explicitly identified process must prove its
 * exact production identity. Identity-free local development remains usable. */
export function requiresExactQuillmdRuntimeIdentity(
  environment: QuillmdRuntimeIdentityEnvironment,
): boolean {
  return (
    environment.NODE_ENV === "production" ||
    hasConfiguredQuillmdRuntimeIdentity(environment)
  );
}

/** Next may load instrumentation while building without runtime identity. */
export function isUnconfiguredNextProductionBuild(
  environment: QuillmdRuntimeIdentityEnvironment,
): boolean {
  return (
    environment.NEXT_PHASE === "phase-production-build" &&
    !hasConfiguredQuillmdRuntimeIdentity(environment)
  );
}
