import { describe, expect, it, vi } from "vitest";

import {
  parseTemplateTwinRuntimeAttestation,
  refreshTemplateTwinRuntimeAttestation,
  registerTemplateTwinRuntimeAttestation,
  TemplateTwinRuntimeAttestationError,
} from "../runtime-attestation";

function environment(overrides: Record<string, unknown> = {}) {
  const sourceCommitSha = "a".repeat(40);
  const envelope = {
    version: "template-twin-runtime-attestation-v1",
    keyId: "synthetic-runtime-v1",
    nonce: "dd2157fe-cb68-4ae5-af85-1bea87cd5346",
    releaseIdentitySha256: "b".repeat(64),
    instanceId: "app-1",
    component: "APP",
    sourceCommitSha,
    imageDigest: `sha256:${"c".repeat(64)}`,
    issuedAtEpochSeconds: 1_784_470_000,
    expiresAtEpochSeconds: 1_784_473_600,
    signature: "d".repeat(64),
    ...overrides,
  };
  return {
    QUILLMD_IMAGE_REVISION: sourceCommitSha,
    QUILLMD_RUNTIME_COMPONENT: "APP",
    TEMPLATE_TWIN_RUNTIME_ATTESTATION: Buffer.from(
      JSON.stringify(envelope),
      "utf8",
    ).toString("base64url"),
  };
}

describe("Template Twin deployment runtime attestation", () => {
  it("accepts only the exact bounded envelope matching baked image identity", () => {
    expect(parseTemplateTwinRuntimeAttestation(environment())).toMatchObject({
      instanceId: "app-1",
      component: "APP",
    });
    expect(() =>
      parseTemplateTwinRuntimeAttestation({
        ...environment(),
        QUILLMD_IMAGE_REVISION: "e".repeat(40),
      }),
    ).toThrow(TemplateTwinRuntimeAttestationError);
    expect(() =>
      parseTemplateTwinRuntimeAttestation(environment({ unsupported: true })),
    ).toThrow(/unsupported shape/u);
  });

  it("converts database signature or manifest rejection into a closed error", async () => {
    const tx = {
      $queryRaw: vi.fn().mockRejectedValue(new Error("database detail")),
    };

    await expect(
      registerTemplateTwinRuntimeAttestation({ tx, env: environment() }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_RUNTIME_ATTESTATION_INVALID",
      message: "The database rejected this deployment runtime attestation.",
    });
  });

  it("distinguishes a disabled, unconfigured release from a live gate", async () => {
    const tx = { $queryRaw: vi.fn().mockResolvedValue([{ receiptId: null }]) };
    await expect(
      refreshTemplateTwinRuntimeAttestation({
        tx,
        env: { ...environment(), TEMPLATE_TWIN_KILL_SWITCH: "true" },
      }),
    ).resolves.toBe("NOT_CONFIGURED");
    await expect(
      refreshTemplateTwinRuntimeAttestation({
        tx,
        env: { ...environment(), TEMPLATE_TWIN_KILL_SWITCH: "false" },
      }),
    ).rejects.toThrow(/live production gate/u);
  });

  it("requires an attestation only when the process gate is live and never hides a revoked key", async () => {
    const idleTx = { $queryRaw: vi.fn() };
    await expect(
      refreshTemplateTwinRuntimeAttestation({
        tx: idleTx,
        env: { TEMPLATE_TWIN_KILL_SWITCH: "true" },
      }),
    ).resolves.toBe("NOT_CONFIGURED");
    expect(idleTx.$queryRaw).not.toHaveBeenCalled();
    await expect(
      refreshTemplateTwinRuntimeAttestation({
        tx: idleTx,
        env: { TEMPLATE_TWIN_KILL_SWITCH: "false" },
      }),
    ).rejects.toThrow(/signed runtime attestation/u);

    const revokedTx = {
      $queryRaw: vi.fn().mockRejectedValue(new Error("revoked signing key")),
    };
    await expect(
      refreshTemplateTwinRuntimeAttestation({
        tx: revokedTx,
        env: { ...environment(), TEMPLATE_TWIN_KILL_SWITCH: "true" },
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_RUNTIME_ATTESTATION_INVALID",
    });
  });
});
