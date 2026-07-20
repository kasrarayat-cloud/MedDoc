// ============================================================================
// Tests for lib/mfa.ts — TOTP + recovery code round trip
// ============================================================================

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  generateMfaEnrollment,
  verifyTotpToken,
  verifyStoredMfaTotpToken,
  generateRecoveryCodes,
  hashRecoveryCodes,
  hashRecoveryCode,
  findMatchingRecoveryHash,
  formatRecoveryCodesForDisplay,
  RECOVERY_CODE_ENTROPY_BITS,
} from "./mfa";
import { generateSync } from "otplib";
import { encryptMfaSecretForUser } from "./mfa-secret-envelope";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("mfa", () => {
  describe("generateMfaEnrollment", () => {
    it("returns a non-empty secret + an otpauth URI + a QR data URL", async () => {
      const out = await generateMfaEnrollment("test@example.com");
      expect(out.secret.length).toBeGreaterThan(0);
      expect(out.otpauthUri).toMatch(/^otpauth:\/\/totp\/QuillMD/);
      expect(out.otpauthUri).toContain(encodeURIComponent("test@example.com"));
      expect(out.qrPngDataUrl).toMatch(/^data:image\/png;base64,/);
    });
  });

  describe("verifyTotpToken", () => {
    it("verifies a current TOTP code generated from the same secret", async () => {
      const enroll = await generateMfaEnrollment("roundtrip@example.com");
      const validToken = await generateSync({ secret: enroll.secret });
      expect(verifyTotpToken(enroll.secret, validToken)).toBe(true);
    });

    it("rejects an empty string", async () => {
      const enroll = await generateMfaEnrollment("e@example.com");
      expect(verifyTotpToken(enroll.secret, "")).toBe(false);
    });

    it("rejects a non-6-digit input", async () => {
      const enroll = await generateMfaEnrollment("e@example.com");
      expect(verifyTotpToken(enroll.secret, "12345")).toBe(false);
      expect(verifyTotpToken(enroll.secret, "1234567")).toBe(false);
      expect(verifyTotpToken(enroll.secret, "ABCDEF")).toBe(false);
    });

    it("rejects a wrong 6-digit code", async () => {
      const enroll = await generateMfaEnrollment("e@example.com");
      // 000000 is overwhelmingly unlikely to be valid for a random secret.
      expect(verifyTotpToken(enroll.secret, "000000")).toBe(false);
    });

    it("strips whitespace before validating", async () => {
      const enroll = await generateMfaEnrollment("e@example.com");
      const validToken = await generateSync({ secret: enroll.secret });
      const formatted = `${validToken.slice(0, 3)} ${validToken.slice(3)}`;
      expect(verifyTotpToken(enroll.secret, formatted)).toBe(true);
    });

    it("returns false for malformed secret without throwing", () => {
      expect(verifyTotpToken("", "123456")).toBe(false);
      expect(verifyTotpToken("not-base32!@#", "123456")).toBe(false);
    });
  });

  describe("verifyStoredMfaTotpToken", () => {
    it("decrypts only for the exact owning user and rejects plaintext in strict mode", async () => {
      const enroll = await generateMfaEnrollment("bound@example.com");
      const validToken = await generateSync({ secret: enroll.secret });
      const encryptedSecret = encryptMfaSecretForUser({
        userId: "user-bound",
        plaintextSecret: enroll.secret,
      });

      expect(
        verifyStoredMfaTotpToken("user-bound", encryptedSecret, validToken),
      ).toBe(true);
      expect(
        verifyStoredMfaTotpToken("user-wrong", encryptedSecret, validToken),
      ).toBe(false);
      expect(
        verifyStoredMfaTotpToken("user-bound", enroll.secret, validToken),
      ).toBe(false);
    });

    it("permits bounded legacy plaintext dual-read only under the exact migration contract", async () => {
      const enroll = await generateMfaEnrollment("migration@example.com");
      const validToken = await generateSync({ secret: enroll.secret });
      vi.stubEnv("MFA_SECRET_LEGACY_READ_MODE", "backfill-v1");
      vi.stubEnv(
        "MFA_SECRET_LEGACY_READ_UNTIL",
        new Date(Date.now() + 60 * 60 * 1000).toISOString(),
      );
      vi.stubEnv(
        "MFA_SECRET_LEGACY_READ_ATTESTATION",
        "accepted-bounded-mfa-secret-backfill-v1",
      );

      expect(
        verifyStoredMfaTotpToken("user-bound", enroll.secret, validToken),
      ).toBe(true);
    });
  });

  describe("generateRecoveryCodes", () => {
    it("generates 10 codes by default in the documented format", () => {
      const codes = generateRecoveryCodes();
      expect(codes).toHaveLength(10);
      for (const c of codes) {
        expect(c).toMatch(/^(?:[A-Z2-9]{4}-){6}[A-Z2-9]{4}$/);
      }
      expect(RECOVERY_CODE_ENTROPY_BITS).toBe(140);
      expect(RECOVERY_CODE_ENTROPY_BITS).toBeGreaterThanOrEqual(128);
    });

    it("generates 10 distinct codes (high entropy)", () => {
      const codes = generateRecoveryCodes();
      expect(new Set(codes).size).toBe(10);
    });

    it("honours the count argument", () => {
      expect(generateRecoveryCodes(3)).toHaveLength(3);
    });
  });

  describe("hashRecoveryCodes / findMatchingRecoveryHash", () => {
    it("round-trips: a generated code matches its hash", () => {
      const codes = generateRecoveryCodes(3);
      const hashed = hashRecoveryCodes(codes);
      const matched = findMatchingRecoveryHash(codes[1], hashed);
      expect(matched).toBe(hashed[1]);
    });

    it("accepts the exact generated alphabet in canonical or compact ASCII form", () => {
      const codes = generateRecoveryCodes(1);
      const hashed = hashRecoveryCodes(codes);
      const original = codes[0];
      const variant = original.toLowerCase().replace(/-/g, "");
      const matched = findMatchingRecoveryHash(variant, hashed);
      expect(matched).toBe(hashed[0]);
    });

    it.each([
      ["short input", "ABCD-EFGH"],
      ["excluded ambiguous symbols", "ABCD-EFGH-IJKL-NPQR-STUV-WXYZ-2345"],
      ["arbitrary punctuation", "ABCD-EFGH-JKLM-NPQR.STUV-WXYZ-2345"],
      ["ASCII whitespace", "ABCD EFGH JKLM NPQR STUV WXYZ 2345"],
      ["Unicode dash", "ABCD–EFGH-JKLM-NPQR-STUV-WXYZ-2345"],
      [
        "full-width compatibility character",
        "ＡBCD-EFGH-JKLM-NPQR-STUV-WXYZ-2345",
      ],
      ["Unicode case-folding confusable", "ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-2345"],
      ["zero-width character", "ABCD-EFGH-JKLM-NPQR-S\u200BTUV-WXYZ-2345"],
    ])("fails closed without throwing for %s", (_label, input) => {
      const verifier = hashRecoveryCode("ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-2345");

      expect(() => findMatchingRecoveryHash(input, [verifier])).not.toThrow();
      expect(findMatchingRecoveryHash(input, [verifier])).toBeNull();
    });

    it("returns null on no match", () => {
      const codes = generateRecoveryCodes(3);
      const hashed = hashRecoveryCodes(codes);
      expect(findMatchingRecoveryHash("NOPE-NOPE", hashed)).toBeNull();
    });

    it("hashRecoveryCode is stable (same input → same hash)", () => {
      const formatted = "ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-2345";
      const compact = "abcdefghjklmnpqrstuvwxyz2345";
      const a = hashRecoveryCode(formatted);
      const b = hashRecoveryCode(compact);
      expect(a).toBe(b);
      expect(a).toMatch(/^qmfa-recovery:v2:sha256:[0-9a-f]{64}$/);
    });

    it("rejects invalid write-side values instead of hashing a normalized collision", () => {
      expect(() => hashRecoveryCode("ABCD-1234")).toThrow(TypeError);
      expect(() =>
        hashRecoveryCodes([
          "ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-2345",
          "ＡBCD-EFGH-JKLM-NPQR-STUV-WXYZ-2345",
        ]),
      ).toThrow(TypeError);
    });

    it("rejects a matching legacy unversioned low-entropy verifier", () => {
      const code = "ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-2345";
      const current = hashRecoveryCode(code);
      const legacyDigest = current.replace("qmfa-recovery:v2:sha256:", "");

      expect(findMatchingRecoveryHash(code, [legacyDigest])).toBeNull();
    });
  });

  describe("formatRecoveryCodesForDisplay", () => {
    it("uppercases + joins with newlines", () => {
      expect(formatRecoveryCodesForDisplay(["ab23-9xyz", "ef45-pqrs"])).toBe(
        "AB23-9XYZ\nEF45-PQRS",
      );
    });
  });
});
