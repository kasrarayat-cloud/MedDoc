import { describe, expect, it, vi } from "vitest";
import { ScureBase32Plugin } from "otplib";

import {
  assertMfaSecretRuntimeConfiguration,
  createMfaSecretEnvelopeCodec,
  isLegacyPlaintextMfaSecret,
  legacyPlaintextMfaReadAllowed,
  MfaSecretConfigurationError,
  MfaSecretEnvelopeError,
} from "./mfa-secret-envelope";

const SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP";
const BASE32_CODEC = new ScureBase32Plugin();
const KEY_A = Buffer.alloc(32, 0x11);
const KEY_B = Buffer.alloc(32, 0x22);
const KEY_A_ID = "mfa-kek-2026-a";
const KEY_B_ID = "mfa-kek-2026-b";
const CONFIGURATION_MESSAGE =
  "MFA secret encryption configuration is unavailable.";
const ENVELOPE_MESSAGE = "MFA secret ciphertext could not be authenticated.";

function codec(activeKeyId = KEY_A_ID, includeOld = true) {
  return createMfaSecretEnvelopeCodec({
    activeKeyId,
    keys: [
      ...(includeOld ? [{ id: KEY_A_ID, key: KEY_A }] : []),
      ...(activeKeyId === KEY_B_ID ? [{ id: KEY_B_ID, key: KEY_B }] : []),
    ],
  });
}

function secretWithBytes(byteLength: number): string {
  return BASE32_CODEC.encode(new Uint8Array(byteLength).fill(0x11), {
    padding: false,
  });
}

function keyringJson() {
  return JSON.stringify({
    version: 1,
    keys: [
      { id: KEY_A_ID, keyBase64Url: KEY_A.toString("base64url") },
      { id: KEY_B_ID, keyBase64Url: KEY_B.toString("base64url") },
    ],
  });
}

function fileAccess(
  overrides: Partial<{ uid: number; gid: number; mode: number }> = {},
) {
  return {
    lstat: vi.fn(() => ({
      isFile: () => true,
      isSymbolicLink: () => false,
      uid: overrides.uid ?? 0,
      gid: overrides.gid ?? 1001,
      mode: overrides.mode ?? 0o100440,
      size: Buffer.byteLength(keyringJson()),
    })),
    read: vi.fn(() => keyringJson()),
  };
}

function productionEnvironment(role: string) {
  return {
    NODE_ENV: "production",
    QUILLMD_SERVICE_ROLE: role,
    MFA_SECRET_ACTIVE_KEY_ID: KEY_B_ID,
    MFA_SECRET_KEYRING_FILE: "/run/secrets/quillmd-mfa-keyring.json",
    MFA_SECRET_LEGACY_READ_MODE: "strict",
  };
}

describe("MFA secret AES-256-GCM envelope", () => {
  it.each([16, 64])(
    "accepts canonical Base32 at the otplib %i-byte guardrail boundary",
    (byteLength) => {
      const plaintextSecret = secretWithBytes(byteLength);
      const encrypted = codec().encrypt({
        userId: "user-synthetic-boundary",
        plaintextSecret,
      });

      expect(isLegacyPlaintextMfaSecret(plaintextSecret)).toBe(true);
      expect(
        codec().decrypt({
          userId: "user-synthetic-boundary",
          encryptedSecret: encrypted,
        }),
      ).toBe(plaintextSecret);
    },
  );

  it.each([
    ["10 decoded bytes", "JBSWY3DPEHPK3PXP"],
    ["lowercase", SECRET.toLowerCase()],
    ["padding", `${SECRET}=`],
    ["noncanonical tail bits", `${secretWithBytes(16).slice(0, -1)}F`],
    ["65 decoded bytes", secretWithBytes(65)],
  ])("rejects %s with the fixed envelope error", (_label, plaintextSecret) => {
    expect(isLegacyPlaintextMfaSecret(plaintextSecret)).toBe(false);
    expect(() =>
      codec().encrypt({
        userId: "user-synthetic-invalid",
        plaintextSecret,
      }),
    ).toThrowError(MfaSecretEnvelopeError);
    expect(() =>
      codec().encrypt({
        userId: "user-synthetic-invalid",
        plaintextSecret,
      }),
    ).toThrowError(ENVELOPE_MESSAGE);
  });

  it("round-trips through a per-secret wrapped data key without storing plaintext or a KEK", () => {
    const encrypted = codec().encrypt({
      userId: "user-synthetic-a",
      plaintextSecret: SECRET,
    });

    expect(encrypted).toMatch(/^qmfa:v1:mfa-kek-2026-a:/u);
    expect(encrypted).not.toContain(SECRET);
    expect(encrypted).not.toContain(KEY_A.toString("base64url"));
    expect(
      codec().decrypt({
        userId: "user-synthetic-a",
        encryptedSecret: encrypted,
      }),
    ).toBe(SECRET);
  });

  it("authenticates the exact user and rejects plaintext, unknown keys, and tampering identically", () => {
    const encrypted = codec().encrypt({
      userId: "user-synthetic-a",
      plaintextSecret: SECRET,
    });
    const parts = encrypted.split(":");
    const tag = parts.at(-1) ?? "";
    parts[parts.length - 1] =
      `${tag.startsWith("A") ? "B" : "A"}${tag.slice(1)}`;
    const tampered = parts.join(":");
    const rotatedWithoutOldKey = codec(KEY_B_ID, false);

    const attempts = [
      () =>
        codec().decrypt({
          userId: "user-synthetic-b",
          encryptedSecret: encrypted,
        }),
      () =>
        codec().decrypt({
          userId: "user-synthetic-a",
          encryptedSecret: SECRET,
        }),
      () =>
        rotatedWithoutOldKey.decrypt({
          userId: "user-synthetic-a",
          encryptedSecret: encrypted,
        }),
      () =>
        codec().decrypt({
          userId: "user-synthetic-a",
          encryptedSecret: tampered,
        }),
    ];

    for (const attempt of attempts) {
      expect(attempt).toThrowError(MfaSecretEnvelopeError);
      expect(attempt).toThrowError(ENVELOPE_MESSAGE);
    }
  });

  it("decrypts old envelopes after active-key rotation and issues new envelopes under the new key", () => {
    const beforeRotation = codec().encrypt({
      userId: "user-synthetic-a",
      plaintextSecret: SECRET,
    });
    const afterRotationCodec = codec(KEY_B_ID, true);
    const afterRotation = afterRotationCodec.encrypt({
      userId: "user-synthetic-a",
      plaintextSecret: SECRET,
    });

    expect(
      afterRotationCodec.decrypt({
        userId: "user-synthetic-a",
        encryptedSecret: beforeRotation,
      }),
    ).toBe(SECRET);
    expect(afterRotation).toMatch(/^qmfa:v1:mfa-kek-2026-b:/u);
    expect(
      afterRotationCodec.decrypt({
        userId: "user-synthetic-a",
        encryptedSecret: afterRotation,
      }),
    ).toBe(SECRET);
  });

  it("does not log key, ciphertext, or cryptographic diagnostics on failure", () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    const encrypted = codec().encrypt({
      userId: "user-synthetic-a",
      plaintextSecret: SECRET,
    });

    expect(() =>
      codec().decrypt({
        userId: "wrong-user",
        encryptedSecret: encrypted,
      }),
    ).toThrowError(ENVELOPE_MESSAGE);
    expect(consoleError).not.toHaveBeenCalled();
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain(encrypted);
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain(
      KEY_A.toString("base64url"),
    );
    consoleError.mockRestore();
  });
});

describe("MFA secret production keyring contract", () => {
  it.each(["physician-app", "template-twin-admin-app"])(
    "accepts an exact root-owned read-only keyring for %s",
    (role) => {
      expect(() =>
        assertMfaSecretRuntimeConfiguration(
          productionEnvironment(role),
          fileAccess(),
        ),
      ).not.toThrow();
    },
  );

  it.each([
    [
      "missing active key",
      {
        ...productionEnvironment("physician-app"),
        MFA_SECRET_ACTIVE_KEY_ID: "",
      },
      fileAccess(),
    ],
    [
      "group-writable keyring",
      productionEnvironment("physician-app"),
      fileAccess({ mode: 0o100460 }),
    ],
    [
      "non-root-owned keyring",
      productionEnvironment("physician-app"),
      fileAccess({ uid: 1001 }),
    ],
    [
      "wrong runtime group",
      productionEnvironment("physician-app"),
      fileAccess({ gid: 1000 }),
    ],
    [
      "key material leaked to a worker",
      productionEnvironment("template-twin-audit-dispatcher"),
      fileAccess(),
    ],
  ])("rejects %s with one fixed message", (_label, environment, access) => {
    expect(() =>
      assertMfaSecretRuntimeConfiguration(environment, access),
    ).toThrowError(MfaSecretConfigurationError);
    expect(() =>
      assertMfaSecretRuntimeConfiguration(environment, access),
    ).toThrowError(CONFIGURATION_MESSAGE);
  });

  it("allows legacy plaintext only under an attested, unexpired, at-most-24-hour backfill window", () => {
    const now = new Date("2026-07-20T12:00:00.000Z");
    const approved = {
      MFA_SECRET_LEGACY_READ_MODE: "backfill-v1",
      MFA_SECRET_LEGACY_READ_UNTIL: "2026-07-21T11:59:59.000Z",
      MFA_SECRET_LEGACY_READ_ATTESTATION:
        "accepted-bounded-mfa-secret-backfill-v1",
    };

    expect(legacyPlaintextMfaReadAllowed(approved, now)).toBe(true);
    expect(
      legacyPlaintextMfaReadAllowed(
        {
          ...approved,
          MFA_SECRET_LEGACY_READ_UNTIL: "2026-07-21T12:00:01.000Z",
        },
        now,
      ),
    ).toBe(false);
    expect(
      legacyPlaintextMfaReadAllowed(
        { ...approved, MFA_SECRET_LEGACY_READ_ATTESTATION: "" },
        now,
      ),
    ).toBe(false);
    expect(
      legacyPlaintextMfaReadAllowed(
        { MFA_SECRET_LEGACY_READ_MODE: "strict" },
        now,
      ),
    ).toBe(false);
  });
});
