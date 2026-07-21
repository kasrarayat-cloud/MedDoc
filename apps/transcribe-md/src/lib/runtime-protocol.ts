import {
  evaluateSyntheticQaResourceBoundary,
  isExactSyntheticQaRuntimeProfile,
} from "@meddoc/auth/synthetic-qa-runtime-profile";
import { hasConfiguredQuillmdRuntimeIdentity } from "@meddoc/auth/runtime-identity";

/**
 * Runtime protocol identity shared by the TranscribeMD web and worker images.
 *
 * The epoch is compiled into code and stamped onto both OCI images. Production
 * deployment tooling verifies the image label/revision before a post-contract
 * swap; this startup guard independently prevents a current image from
 * starting under a contradictory runtime configuration.
 */
export const QUILLMD_RUNTIME_PROTOCOL_EPOCH =
  "template-twin-final-schema-v2" as const;
export const QUILLMD_RUNTIME_PROTOCOL_EPOCH_ENV =
  "QUILLMD_RUNTIME_PROTOCOL_EPOCH" as const;
export const QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH_ENV =
  "QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH" as const;
export const QUILLMD_DATABASE_PRINCIPAL_PROFILE_ENV =
  "QUILLMD_DATABASE_PRINCIPAL_PROFILE" as const;
export const QUILLMD_EXACT_PRODUCTION_DATABASE_PRINCIPAL_PROFILE =
  "exact-production-v1" as const;
export const QUILLMD_SYNTHETIC_QA_DATABASE_PRINCIPAL_PROFILE =
  "synthetic-disposable-qa-v1" as const;

export const TEMPLATE_TWIN_RUNTIME_MODE_ENV =
  "TEMPLATE_TWIN_RUNTIME_MODE" as const;
export const TEMPLATE_TWIN_STANDARD_RUNTIME_MODE = "standard" as const;
export const TEMPLATE_TWIN_ROLLBACK_COMPAT_RUNTIME_MODE =
  "rollback-compat-v2" as const;

export const QUILLMD_DETERMINISTIC_PROVIDER_ENVIRONMENTS = Object.freeze([
  "MOCK_AI_CALLS",
  "MOCK_TEMPLATE_TWIN_E2E",
  "MOCK_TEMPLATE_PHI_FLAG",
  "MOCK_RX_WARNINGS",
] as const);

export const QUILLMD_SYNTHETIC_AUTH_BYPASS_BOOLEAN_ENVIRONMENTS = Object.freeze(
  [
    "AUTH_USE_MOCK",
    "EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD",
    "RATE_LIMIT_DISABLED",
    "RATE_LIMIT_DISABLE_ALLOW_IN_PROD",
  ] as const,
);
export const QUILLMD_SYNTHETIC_AUTH_BYPASS_VALUE_ENVIRONMENTS = Object.freeze([
  "EMAIL_AUTO_CONFIRM_DOMAINS",
] as const);
export const QUILLMD_AUTH_SESSION_VERIFIER_PROFILE_ENV =
  "QUILLMD_AUTH_SESSION_VERIFIER_PROFILE" as const;
export const QUILLMD_TEMPLATE_TWIN_ADMIN_CONTROL_SESSION_VERIFIER_PROFILE =
  "template-twin-admin-control-v1" as const;

export type TemplateTwinRuntimeMode =
  | typeof TEMPLATE_TWIN_STANDARD_RUNTIME_MODE
  | typeof TEMPLATE_TWIN_ROLLBACK_COMPAT_RUNTIME_MODE;

export class RuntimeProtocolConfigurationError extends Error {
  readonly code = "QUILLMD_RUNTIME_PROTOCOL_CONFIGURATION_INVALID";

  constructor(message: string) {
    super(message);
    this.name = "RuntimeProtocolConfigurationError";
  }
}

function normalized(value: string | undefined): string {
  return value?.trim().toLowerCase() ?? "";
}

export function isTemplateTwinKillSwitchExplicitlyOff(
  env: Readonly<Record<string, string | undefined>> = process.env,
): boolean {
  return normalized(env.TEMPLATE_TWIN_KILL_SWITCH) === "false";
}

export function resolveTemplateTwinRuntimeMode(
  env: Readonly<Record<string, string | undefined>> = process.env,
): TemplateTwinRuntimeMode {
  const value = normalized(env[TEMPLATE_TWIN_RUNTIME_MODE_ENV]);
  if (!value || value === TEMPLATE_TWIN_STANDARD_RUNTIME_MODE) {
    return TEMPLATE_TWIN_STANDARD_RUNTIME_MODE;
  }
  if (value === TEMPLATE_TWIN_ROLLBACK_COMPAT_RUNTIME_MODE) {
    return TEMPLATE_TWIN_ROLLBACK_COMPAT_RUNTIME_MODE;
  }
  throw new RuntimeProtocolConfigurationError(
    "The Template Twin runtime mode is not recognized.",
  );
}

/** Fail-closed convenience for request/read boundaries. Startup still throws. */
export function templateTwinRuntimeEnabled(
  env: Readonly<Record<string, string | undefined>> = process.env,
): boolean {
  try {
    return (
      resolveTemplateTwinRuntimeMode(env) ===
      TEMPLATE_TWIN_STANDARD_RUNTIME_MODE
    );
  } catch {
    return false;
  }
}

export function isTemplateTwinRollbackCompatRuntime(
  env: Readonly<Record<string, string | undefined>> = process.env,
): boolean {
  try {
    return (
      resolveTemplateTwinRuntimeMode(env) ===
      TEMPLATE_TWIN_ROLLBACK_COMPAT_RUNTIME_MODE
    );
  } catch {
    return false;
  }
}

/**
 * Web/worker startup contract. Bridge mode is deliberately stricter than the
 * ordinary disabled rollout: the process kill switch must also remain active.
 * Persisted global/practice revocation and queue draining are verified by the
 * deployment guard before a bridge swap.
 */
export function assertQuillmdRuntimeProtocol(
  env: Readonly<Record<string, string | undefined>> = process.env,
): {
  epoch: typeof QUILLMD_RUNTIME_PROTOCOL_EPOCH;
  mode: TemplateTwinRuntimeMode;
} {
  const advertisedEpoch = env[QUILLMD_RUNTIME_PROTOCOL_EPOCH_ENV]?.trim();
  const requiredEpoch =
    env[QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH_ENV]?.trim();
  const principalProfile = env[QUILLMD_DATABASE_PRINCIPAL_PROFILE_ENV];
  const configuredRuntimeIdentity = hasConfiguredQuillmdRuntimeIdentity(env);
  const productionSafetyPosture =
    normalized(env.NODE_ENV) === "production" || configuredRuntimeIdentity;
  const syntheticQaBoundaryAllowed =
    evaluateSyntheticQaResourceBoundary(env).allowed;

  if (configuredRuntimeIdentity && env.NODE_ENV !== "production") {
    throw new RuntimeProtocolConfigurationError(
      "A configured runtime identity requires the exact production Node environment.",
    );
  }
  const sessionVerifierProfile =
    env[QUILLMD_AUTH_SESSION_VERIFIER_PROFILE_ENV]?.trim() ?? "";
  if (
    configuredRuntimeIdentity &&
    (env.QUILLMD_SERVICE_ROLE === "template-twin-admin-control") !==
      (sessionVerifierProfile ===
        QUILLMD_TEMPLATE_TWIN_ADMIN_CONTROL_SESSION_VERIFIER_PROFILE)
  ) {
    throw new RuntimeProtocolConfigurationError(
      "The authentication session-verifier profile does not match the runtime role.",
    );
  }

  if (advertisedEpoch && advertisedEpoch !== QUILLMD_RUNTIME_PROTOCOL_EPOCH) {
    throw new RuntimeProtocolConfigurationError(
      "This image advertises an incompatible runtime protocol epoch.",
    );
  }
  if (requiredEpoch && requiredEpoch !== QUILLMD_RUNTIME_PROTOCOL_EPOCH) {
    throw new RuntimeProtocolConfigurationError(
      "The deployment requires an incompatible runtime protocol epoch.",
    );
  }
  if (
    productionSafetyPosture &&
    advertisedEpoch !== QUILLMD_RUNTIME_PROTOCOL_EPOCH
  ) {
    throw new RuntimeProtocolConfigurationError(
      "A production image must advertise its compiled runtime protocol epoch.",
    );
  }
  const authBypassConfigured =
    QUILLMD_SYNTHETIC_AUTH_BYPASS_BOOLEAN_ENVIRONMENTS.some(
      (key) => normalized(env[key]) === "true",
    ) ||
    QUILLMD_SYNTHETIC_AUTH_BYPASS_VALUE_ENVIRONMENTS.some((key) =>
      Boolean(env[key]?.trim()),
    );
  if (
    productionSafetyPosture &&
    authBypassConfigured &&
    !isExactSyntheticQaRuntimeProfile(env)
  ) {
    throw new RuntimeProtocolConfigurationError(
      "Synthetic authentication controls are forbidden outside the exact isolated synthetic QA runtime profile.",
    );
  }
  if (
    productionSafetyPosture &&
    (Boolean(env.EMAIL_AUTO_CONFIRM_DOMAINS?.trim()) !==
      (normalized(env.EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD) === "true") ||
      (normalized(env.RATE_LIMIT_DISABLED) === "true") !==
        (normalized(env.RATE_LIMIT_DISABLE_ALLOW_IN_PROD) === "true"))
  ) {
    throw new RuntimeProtocolConfigurationError(
      "Synthetic authentication controls require exact paired configuration.",
    );
  }
  if (
    productionSafetyPosture &&
    requiredEpoch !== QUILLMD_RUNTIME_PROTOCOL_EPOCH
  ) {
    throw new RuntimeProtocolConfigurationError(
      "A production deployment must require this image's runtime protocol epoch.",
    );
  }
  if (
    principalProfile === QUILLMD_SYNTHETIC_QA_DATABASE_PRINCIPAL_PROFILE &&
    !syntheticQaBoundaryAllowed
  ) {
    throw new RuntimeProtocolConfigurationError(
      "The synthetic database-principal profile is forbidden outside the exact isolated synthetic QA resource boundary.",
    );
  }
  if (
    productionSafetyPosture &&
    QUILLMD_DETERMINISTIC_PROVIDER_ENVIRONMENTS.some(
      (key) => normalized(env[key]) === "true",
    ) &&
    (principalProfile !== QUILLMD_SYNTHETIC_QA_DATABASE_PRINCIPAL_PROFILE ||
      !syntheticQaBoundaryAllowed)
  ) {
    throw new RuntimeProtocolConfigurationError(
      "Deterministic provider fixtures are forbidden outside the exact isolated synthetic QA resource boundary.",
    );
  }

  const mode = resolveTemplateTwinRuntimeMode(env);
  if (
    mode === TEMPLATE_TWIN_ROLLBACK_COMPAT_RUNTIME_MODE &&
    isTemplateTwinKillSwitchExplicitlyOff(env)
  ) {
    throw new RuntimeProtocolConfigurationError(
      "Rollback compatibility mode requires the Template Twin process kill switch to remain active.",
    );
  }
  return { epoch: QUILLMD_RUNTIME_PROTOCOL_EPOCH, mode };
}
