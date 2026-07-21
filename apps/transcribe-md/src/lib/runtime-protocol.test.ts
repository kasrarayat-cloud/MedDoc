import { describe, expect, it } from "vitest";

import {
  QUILLMD_RUNTIME_PROTOCOL_EPOCH,
  QUILLMD_DETERMINISTIC_PROVIDER_ENVIRONMENTS,
  RuntimeProtocolConfigurationError,
  assertQuillmdRuntimeProtocol,
  isTemplateTwinKillSwitchExplicitlyOff,
  isTemplateTwinRollbackCompatRuntime,
  resolveTemplateTwinRuntimeMode,
  templateTwinRuntimeEnabled,
} from "./runtime-protocol";

const PRODUCTION_PROTOCOL_ENV = Object.freeze({
  NODE_ENV: "production",
  QUILLMD_RUNTIME_PROTOCOL_EPOCH,
  QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH: QUILLMD_RUNTIME_PROTOCOL_EPOCH,
});

const SYNTHETIC_QA_DATABASE_CREDENTIAL = "s".repeat(43);
const EXACT_ISOLATED_QA_ENV = Object.freeze({
  ...PRODUCTION_PROTOCOL_ENV,
  QUILLMD_SERVICE_ROLE: "physician-app",
  QUILLMD_DATABASE_PRINCIPAL_PROFILE: "synthetic-disposable-qa-v1",
  TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "qa",
  TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: "isolated-disposable-qa-v1",
  TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
  DATABASE_URL: `postgresql://meddoc_runtime:${SYNTHETIC_QA_DATABASE_CREDENTIAL}@postgres:5432/meddoc_synthetic_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic`,
  REDIS_URL: "redis://redis:6379/15",
  MINIO_ENDPOINT: "minio:9000",
  MINIO_USE_SSL: "false",
  TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio-qa",
  TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-template-artifacts-qa",
  ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION:
    "accepted-isolated-synthetic-qa-shared-host",
  ADMIN_PUBLIC_HOST: "localhost",
  PHYSICIAN_PUBLIC_HOST: "localhost",
  AUTH_URL: "http://localhost:9020",
  NEXTAUTH_URL: "http://localhost:9020",
});

describe("QuillMD runtime protocol", () => {
  it("uses one canonical fail-closed kill-switch parser", () => {
    expect(
      isTemplateTwinKillSwitchExplicitlyOff({
        TEMPLATE_TWIN_KILL_SWITCH: "  FaLsE  ",
      }),
    ).toBe(true);
    for (const value of [undefined, "", "0", "true", "off", "no"]) {
      expect(
        isTemplateTwinKillSwitchExplicitlyOff({
          TEMPLATE_TWIN_KILL_SWITCH: value,
        }),
      ).toBe(false);
    }
  });

  it("uses the standard runtime when no explicit bridge is requested", () => {
    expect(resolveTemplateTwinRuntimeMode({})).toBe("standard");
    expect(templateTwinRuntimeEnabled({})).toBe(true);
    expect(isTemplateTwinRollbackCompatRuntime({})).toBe(false);
  });

  it("identifies rollback-compat-v2 and disables Template Twin", () => {
    const env = { TEMPLATE_TWIN_RUNTIME_MODE: " rollback-compat-v2 " };
    expect(resolveTemplateTwinRuntimeMode(env)).toBe("rollback-compat-v2");
    expect(templateTwinRuntimeEnabled(env)).toBe(false);
    expect(isTemplateTwinRollbackCompatRuntime(env)).toBe(true);
  });

  it("fails closed for an unknown runtime mode", () => {
    expect(() =>
      resolveTemplateTwinRuntimeMode({
        TEMPLATE_TWIN_RUNTIME_MODE: "legacy-image-bypass",
      }),
    ).toThrow(RuntimeProtocolConfigurationError);
    expect(
      templateTwinRuntimeEnabled({
        TEMPLATE_TWIN_RUNTIME_MODE: "legacy-image-bypass",
      }),
    ).toBe(false);
  });

  it("requires an exact advertised epoch in production", () => {
    expect(
      assertQuillmdRuntimeProtocol({
        NODE_ENV: "production",
        QUILLMD_RUNTIME_PROTOCOL_EPOCH,
        QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH: QUILLMD_RUNTIME_PROTOCOL_EPOCH,
      }),
    ).toEqual({
      epoch: QUILLMD_RUNTIME_PROTOCOL_EPOCH,
      mode: "standard",
    });
    expect(() =>
      assertQuillmdRuntimeProtocol({ NODE_ENV: "production" }),
    ).toThrow(RuntimeProtocolConfigurationError);
    expect(() =>
      assertQuillmdRuntimeProtocol({
        NODE_ENV: "production",
        QUILLMD_RUNTIME_PROTOCOL_EPOCH: "pre-stack-v1",
        QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH: QUILLMD_RUNTIME_PROTOCOL_EPOCH,
      }),
    ).toThrow(RuntimeProtocolConfigurationError);
    expect(() =>
      assertQuillmdRuntimeProtocol({
        NODE_ENV: "production",
        QUILLMD_RUNTIME_PROTOCOL_EPOCH,
      }),
    ).toThrow(RuntimeProtocolConfigurationError);
  });

  it.each([
    [
      "service role",
      {
        NODE_ENV: "development",
        QUILLMD_SERVICE_ROLE: "physician-app",
      },
    ],
    [
      "blank service role",
      {
        NODE_ENV: "development",
        QUILLMD_SERVICE_ROLE: "",
      },
    ],
    [
      "exact principal profile",
      {
        NODE_ENV: "test",
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1",
      },
    ],
    [
      "unknown principal profile",
      {
        NODE_ENV: "development",
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: "unreviewed-profile",
      },
    ],
    [
      "blank principal profile",
      {
        NODE_ENV: "test",
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: "",
      },
    ],
    [
      "blank session verifier profile",
      {
        NODE_ENV: "development",
        QUILLMD_AUTH_SESSION_VERIFIER_PROFILE: "",
      },
    ],
    [
      "session verifier profile",
      {
        NODE_ENV: "development",
        QUILLMD_AUTH_SESSION_VERIFIER_PROFILE: "template-twin-admin-control-v1",
      },
    ],
  ] as const)(
    "requires the production epoch posture for a configured %s despite NODE_ENV drift",
    (_label, environment) => {
      expect(() => assertQuillmdRuntimeProtocol(environment)).toThrow(
        RuntimeProtocolConfigurationError,
      );
      expect(() =>
        assertQuillmdRuntimeProtocol({
          ...environment,
          QUILLMD_RUNTIME_PROTOCOL_EPOCH,
          QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH:
            QUILLMD_RUNTIME_PROTOCOL_EPOCH,
        }),
      ).toThrow(RuntimeProtocolConfigurationError);
    },
  );

  it("requires the explicit verifier profile only for the control runtime", () => {
    const control = {
      ...PRODUCTION_PROTOCOL_ENV,
      QUILLMD_SERVICE_ROLE: "template-twin-admin-control",
      QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1",
    };
    expect(() => assertQuillmdRuntimeProtocol(control)).toThrow(
      RuntimeProtocolConfigurationError,
    );
    expect(
      assertQuillmdRuntimeProtocol({
        ...control,
        QUILLMD_AUTH_SESSION_VERIFIER_PROFILE: "template-twin-admin-control-v1",
      }),
    ).toEqual({ epoch: QUILLMD_RUNTIME_PROTOCOL_EPOCH, mode: "standard" });
    expect(() =>
      assertQuillmdRuntimeProtocol({
        ...PRODUCTION_PROTOCOL_ENV,
        QUILLMD_SERVICE_ROLE: "physician-app",
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1",
        QUILLMD_AUTH_SESSION_VERIFIER_PROFILE: "template-twin-admin-control-v1",
      }),
    ).toThrow(RuntimeProtocolConfigurationError);
  });

  it.each([
    ["mock authentication", { AUTH_USE_MOCK: "true" }],
    [
      "email auto-confirm acknowledgement",
      { EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD: "true" },
    ],
    [
      "email auto-confirm allowlist",
      { EMAIL_AUTO_CONFIRM_DOMAINS: "synthetic.test" },
    ],
    ["rate-limit bypass", { RATE_LIMIT_DISABLED: "true" }],
    [
      "rate-limit bypass acknowledgement",
      { RATE_LIMIT_DISABLE_ALLOW_IN_PROD: "true" },
    ],
  ] as const)(
    "rejects production %s outside exact synthetic QA",
    (_label, bypass) => {
      expect(() =>
        assertQuillmdRuntimeProtocol({
          ...PRODUCTION_PROTOCOL_ENV,
          ...bypass,
        }),
      ).toThrow(RuntimeProtocolConfigurationError);
    },
  );

  it("admits paired synthetic authentication controls only under the exact QA profile", () => {
    expect(
      assertQuillmdRuntimeProtocol({
        ...EXACT_ISOLATED_QA_ENV,
        AUTH_USE_MOCK: "true",
        EMAIL_AUTO_CONFIRM_DOMAINS: "synthetic.test,example.test",
        EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD: "true",
        RATE_LIMIT_DISABLED: "true",
        RATE_LIMIT_DISABLE_ALLOW_IN_PROD: "true",
      }),
    ).toEqual({ epoch: QUILLMD_RUNTIME_PROTOCOL_EPOCH, mode: "standard" });
  });

  it.each([
    [
      "email allowlist without acknowledgement",
      {
        EMAIL_AUTO_CONFIRM_DOMAINS: "synthetic.test",
        EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD: "false",
      },
    ],
    [
      "email acknowledgement without allowlist",
      {
        EMAIL_AUTO_CONFIRM_DOMAINS: "",
        EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD: "true",
      },
    ],
    [
      "rate bypass without acknowledgement",
      {
        RATE_LIMIT_DISABLED: "true",
        RATE_LIMIT_DISABLE_ALLOW_IN_PROD: "false",
      },
    ],
    [
      "rate acknowledgement without bypass",
      {
        RATE_LIMIT_DISABLED: "false",
        RATE_LIMIT_DISABLE_ALLOW_IN_PROD: "true",
      },
    ],
  ] as const)("rejects %s", (_label, override) => {
    expect(() =>
      assertQuillmdRuntimeProtocol({
        ...EXACT_ISOLATED_QA_ENV,
        ...override,
      }),
    ).toThrow(RuntimeProtocolConfigurationError);
  });

  it("requires the process kill switch to stay active in bridge mode", () => {
    expect(() =>
      assertQuillmdRuntimeProtocol({
        NODE_ENV: "production",
        QUILLMD_RUNTIME_PROTOCOL_EPOCH,
        QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH: QUILLMD_RUNTIME_PROTOCOL_EPOCH,
        TEMPLATE_TWIN_RUNTIME_MODE: "rollback-compat-v2",
        TEMPLATE_TWIN_KILL_SWITCH: "false",
      }),
    ).toThrow(RuntimeProtocolConfigurationError);

    expect(
      assertQuillmdRuntimeProtocol({
        NODE_ENV: "production",
        QUILLMD_RUNTIME_PROTOCOL_EPOCH,
        QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH: QUILLMD_RUNTIME_PROTOCOL_EPOCH,
        TEMPLATE_TWIN_RUNTIME_MODE: "rollback-compat-v2",
        TEMPLATE_TWIN_KILL_SWITCH: "true",
      }),
    ).toMatchObject({ mode: "rollback-compat-v2" });
  });

  it.each(QUILLMD_DETERMINISTIC_PROVIDER_ENVIRONMENTS)(
    "rejects production %s outside the isolated QA boundary",
    (flag) => {
      expect(() =>
        assertQuillmdRuntimeProtocol({
          ...PRODUCTION_PROTOCOL_ENV,
          [flag]: "true",
        }),
      ).toThrow(RuntimeProtocolConfigurationError);
    },
  );

  it.each([
    [
      "unnamed environment",
      { TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: undefined },
    ],
    ["explicit production profile", { APP_ENV: "production" }],
    [
      "missing resource attestation",
      { TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: undefined },
    ],
    ["production database", { DATABASE_URL: "postgresql:///meddoc" }],
    ["shared Redis namespace", { REDIS_URL: "redis://redis:6379/0" }],
    [
      "unmarked object bucket",
      { TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio" },
    ],
    [
      "remote object storage without TLS",
      {
        MINIO_ENDPOINT: "minio-qa.synthetic.test:9000",
        MINIO_USE_SSL: "false",
      },
    ],
    ["non-QA storage profile", { TEMPLATE_TWIN_STORAGE_PROFILE: "production" }],
  ] as const)(
    "rejects deterministic production runtime with %s",
    (_label, override) => {
      expect(() =>
        assertQuillmdRuntimeProtocol({
          ...EXACT_ISOLATED_QA_ENV,
          MOCK_AI_CALLS: "true",
          ...override,
        }),
      ).toThrow(RuntimeProtocolConfigurationError);
    },
  );

  it("admits deterministic fixtures only at the exact isolated QA resource boundary without enabling staging", () => {
    expect(
      assertQuillmdRuntimeProtocol({
        ...EXACT_ISOLATED_QA_ENV,
        TEMPLATE_TWIN_STAGING_QA_ENABLED: undefined,
        MOCK_AI_CALLS: "true",
        MOCK_TEMPLATE_TWIN_E2E: "true",
        MOCK_TEMPLATE_PHI_FLAG: "true",
        MOCK_RX_WARNINGS: "true",
      }),
    ).toEqual({ epoch: QUILLMD_RUNTIME_PROTOCOL_EPOCH, mode: "standard" });
  });

  it("rejects the synthetic principal profile outside the exact QA boundary even without deterministic fixtures", () => {
    expect(() =>
      assertQuillmdRuntimeProtocol({
        ...PRODUCTION_PROTOCOL_ENV,
        QUILLMD_SERVICE_ROLE: "physician-app",
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: "synthetic-disposable-qa-v1",
      }),
    ).toThrow(RuntimeProtocolConfigurationError);
  });

  it("rejects deterministic fixtures at the QA resource boundary unless the exact synthetic profile is configured", () => {
    expect(() =>
      assertQuillmdRuntimeProtocol({
        ...EXACT_ISOLATED_QA_ENV,
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: "exact-production-v1",
        MOCK_AI_CALLS: "true",
      }),
    ).toThrow(RuntimeProtocolConfigurationError);
    expect(() =>
      assertQuillmdRuntimeProtocol({
        ...EXACT_ISOLATED_QA_ENV,
        QUILLMD_DATABASE_PRINCIPAL_PROFILE: undefined,
        MOCK_AI_CALLS: "true",
      }),
    ).toThrow(RuntimeProtocolConfigurationError);
  });
});
