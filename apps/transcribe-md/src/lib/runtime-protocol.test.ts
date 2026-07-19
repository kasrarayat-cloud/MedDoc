import { describe, expect, it } from "vitest";

import {
  QUILLMD_RUNTIME_PROTOCOL_EPOCH,
  RuntimeProtocolConfigurationError,
  assertQuillmdRuntimeProtocol,
  isTemplateTwinRollbackCompatRuntime,
  resolveTemplateTwinRuntimeMode,
  templateTwinRuntimeEnabled,
} from "./runtime-protocol";

describe("QuillMD runtime protocol", () => {
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
        QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH:
          QUILLMD_RUNTIME_PROTOCOL_EPOCH,
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
        QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH:
          QUILLMD_RUNTIME_PROTOCOL_EPOCH,
      }),
    ).toThrow(RuntimeProtocolConfigurationError);
    expect(() =>
      assertQuillmdRuntimeProtocol({
        NODE_ENV: "production",
        QUILLMD_RUNTIME_PROTOCOL_EPOCH,
      }),
    ).toThrow(RuntimeProtocolConfigurationError);
  });

  it("requires the process kill switch to stay active in bridge mode", () => {
    expect(() =>
      assertQuillmdRuntimeProtocol({
        NODE_ENV: "production",
        QUILLMD_RUNTIME_PROTOCOL_EPOCH,
        QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH:
          QUILLMD_RUNTIME_PROTOCOL_EPOCH,
        TEMPLATE_TWIN_RUNTIME_MODE: "rollback-compat-v2",
        TEMPLATE_TWIN_KILL_SWITCH: "false",
      }),
    ).toThrow(RuntimeProtocolConfigurationError);

    expect(
      assertQuillmdRuntimeProtocol({
        NODE_ENV: "production",
        QUILLMD_RUNTIME_PROTOCOL_EPOCH,
        QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH:
          QUILLMD_RUNTIME_PROTOCOL_EPOCH,
        TEMPLATE_TWIN_RUNTIME_MODE: "rollback-compat-v2",
        TEMPLATE_TWIN_KILL_SWITCH: "true",
      }),
    ).toMatchObject({ mode: "rollback-compat-v2" });
  });
});
