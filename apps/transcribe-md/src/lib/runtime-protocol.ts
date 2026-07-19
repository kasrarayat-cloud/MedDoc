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

export const TEMPLATE_TWIN_RUNTIME_MODE_ENV =
  "TEMPLATE_TWIN_RUNTIME_MODE" as const;
export const TEMPLATE_TWIN_STANDARD_RUNTIME_MODE = "standard" as const;
export const TEMPLATE_TWIN_ROLLBACK_COMPAT_RUNTIME_MODE =
  "rollback-compat-v2" as const;

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

  if (
    advertisedEpoch &&
    advertisedEpoch !== QUILLMD_RUNTIME_PROTOCOL_EPOCH
  ) {
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
    normalized(env.NODE_ENV) === "production" &&
    advertisedEpoch !== QUILLMD_RUNTIME_PROTOCOL_EPOCH
  ) {
    throw new RuntimeProtocolConfigurationError(
      "A production image must advertise its compiled runtime protocol epoch.",
    );
  }
  if (
    normalized(env.NODE_ENV) === "production" &&
    requiredEpoch !== QUILLMD_RUNTIME_PROTOCOL_EPOCH
  ) {
    throw new RuntimeProtocolConfigurationError(
      "A production deployment must require this image's runtime protocol epoch.",
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
