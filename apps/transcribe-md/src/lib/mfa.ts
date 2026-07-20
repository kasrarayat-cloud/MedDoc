// ============================================================================
// MFA (TOTP + recovery codes) — HIPAA §164.312(d) authentication factor
// ----------------------------------------------------------------------------
// Closes the BLOCKING_TIER_1 finding HIPAA_FINDING_001 from the
// 2026-05-10 baseline shadow audit (zero MFA coverage on 49 active
// accounts).
//
// Design choices, recorded so future readers can audit them:
//   - TOTP via `otplib` (`@otplib/preset-default`). Maintained, widely
//     used, no rolled-own crypto.
//   - 30-second window, 6-digit codes (RFC 6238 default).
//   - Verification accepts ±1 step (so a clock drift up to 30s either
//     way still works; matches Google Authenticator's tolerance).
//   - Recovery codes: 10 codes per enrollment, 28 unbiased base32 symbols
//     (140 random bits) grouped 4-4-4-4-4-4-4 for typability. Stored as
//     explicitly versioned SHA-256 verifiers (single-use; matched once then
//     dropped). Legacy unversioned ~40-bit verifiers are deliberately rejected;
//     they cannot be made stronger without issuing fresh random codes.
//   - SHA-256 is appropriate for newly issued codes because their 140-bit
//     entropy, plus the existing remote rate limit, makes offline guessing
//     infeasible without adding a slow verifier to every login attempt.
//   - Issuer label = "QuillMD" so the user's authenticator app shows
//     "QuillMD: their-email@…".
//
// Never throws on user-facing paths; returns null/false on invalid
// input. Throws only on programmer error (e.g. malformed stored hash).
// ============================================================================

import { generateSecret, generateURI, verifySync } from "otplib";
import qrcode from "qrcode";
import { createHash, randomBytes } from "node:crypto";
import {
  decryptMfaSecretForUser,
  isLegacyPlaintextMfaSecret,
  legacyPlaintextMfaReadAllowed,
} from "./mfa-secret-envelope";

const TOTP_ISSUER = "QuillMD";

/** Symmetric tolerance window in seconds for TOTP verification.
 *  30 = accept the previous, current, and next 30-second steps —
 *  matches authenticator-app drift tolerance and Google Authenticator's
 *  default. */
const TOTP_EPOCH_TOLERANCE_SEC = 30;

// Alphabet excludes 0/O/I/1/l to prevent transcription mistakes.
const RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const RECOVERY_CODE_GROUPS = 7;
const RECOVERY_CODE_GROUP_LEN = 4;
const RECOVERY_CODE_SYMBOLS = RECOVERY_CODE_GROUPS * RECOVERY_CODE_GROUP_LEN;
const RECOVERY_HASH_PREFIX = "qmfa-recovery:v2:sha256:";
const CURRENT_RECOVERY_HASH_PATTERN = /^qmfa-recovery:v2:sha256:[0-9a-f]{64}$/u;
const COMPACT_RECOVERY_CODE_PATTERN = /^[A-HJ-NP-Za-hj-np-z2-9]{28}$/u;
const FORMATTED_RECOVERY_CODE_PATTERN =
  /^(?:[A-HJ-NP-Za-hj-np-z2-9]{4}-){6}[A-HJ-NP-Za-hj-np-z2-9]{4}$/u;

export const RECOVERY_CODE_ENTROPY_BITS =
  RECOVERY_CODE_GROUPS *
  RECOVERY_CODE_GROUP_LEN *
  Math.log2(RECOVERY_ALPHABET.length);

export interface MfaEnrollmentArtifact {
  /** Base32 secret. The enrollment route immediately stages only its
   * user-bound encrypted envelope; it never writes this plaintext to DB. */
  secret: string;
  /** otpauth://-shaped URI for the QR code. */
  otpauthUri: string;
  /** Pre-rendered PNG data URL (base64). */
  qrPngDataUrl: string;
}

/**
 * Generate a fresh TOTP secret + a QR data-URL the user can scan with
 * their authenticator app. The secret is NOT yet committed to the DB
 * here. The enrollment route stages an encrypted envelope while keeping
 * mfaEnabled=false; the verify-enrollment step confirms the first code.
 */
export async function generateMfaEnrollment(
  userEmail: string,
): Promise<MfaEnrollmentArtifact> {
  const secret = await generateSecret();
  const otpauthUri = generateURI({
    issuer: TOTP_ISSUER,
    label: userEmail,
    secret,
  });
  const qrPngDataUrl = await qrcode.toDataURL(otpauthUri, {
    width: 240,
    margin: 1,
    errorCorrectionLevel: "M",
  });
  return { secret, otpauthUri, qrPngDataUrl };
}

/**
 * Validate a 6-digit token against a stored secret. Returns false on
 * any failure (wrong digits, malformed secret, otplib internal
 * error). Never throws.
 */
export function verifyTotpToken(secret: string, token: string): boolean {
  if (typeof secret !== "string" || secret.length === 0) return false;
  if (typeof token !== "string") return false;
  // Strip whitespace + non-digits — users sometimes paste with spaces.
  const clean = token.replace(/\s+/g, "");
  if (!/^\d{6}$/.test(clean)) return false;
  try {
    const result = verifySync({
      secret,
      token: clean,
      epochTolerance: TOTP_EPOCH_TOLERANCE_SEC,
    });
    return result.valid === true;
  } catch {
    return false;
  }
}

/**
 * Decrypt and verify a stored MFA secret against the exact owning user. Any
 * plaintext, unknown-key, wrong-user, malformed, or tampered envelope fails
 * closed without exposing the cryptographic failure class to the caller.
 */
export function verifyStoredMfaTotpToken(
  userId: string,
  encryptedSecret: string,
  token: string,
): boolean {
  try {
    const plaintextSecret = decryptMfaSecretForUser({
      userId,
      encryptedSecret,
    });
    return verifyTotpToken(plaintextSecret, token);
  } catch {
    return (
      legacyPlaintextMfaReadAllowed() &&
      isLegacyPlaintextMfaSecret(encryptedSecret) &&
      verifyTotpToken(encryptedSecret, token)
    );
  }
}

/**
 * Generate 10 plaintext recovery codes. The caller must show these to
 * the user once + store the SHA-256 hash array via
 * `hashRecoveryCodes(codes)` immediately.
 */
export function generateRecoveryCodes(count = 10): string[] {
  if (!Number.isInteger(count) || count < 1 || count > 100) {
    throw new RangeError("Recovery code count must be between 1 and 100.");
  }
  const codes: string[] = [];
  for (let i = 0; i < count; i++) {
    const characterCount = RECOVERY_CODE_SYMBOLS;
    let ungrouped = "";
    const unbiasedLimit =
      Math.floor(256 / RECOVERY_ALPHABET.length) * RECOVERY_ALPHABET.length;
    while (ungrouped.length < characterCount) {
      const bytes = randomBytes(characterCount - ungrouped.length);
      for (const byte of bytes) {
        if (byte >= unbiasedLimit) continue;
        ungrouped += RECOVERY_ALPHABET[byte % RECOVERY_ALPHABET.length];
        if (ungrouped.length === characterCount) break;
      }
    }
    const groups = Array.from({ length: RECOVERY_CODE_GROUPS }, (_, group) =>
      ungrouped.slice(
        group * RECOVERY_CODE_GROUP_LEN,
        (group + 1) * RECOVERY_CODE_GROUP_LEN,
      ),
    );
    codes.push(groups.join("-"));
  }
  return codes;
}

/**
 * Hash recovery codes for storage. Returns an equally sized array of
 * explicitly versioned SHA-256 verifier strings. No salt is required because
 * the newly issued codes carry 140 unbiased random bits and are stored
 * per-user.
 */
export function hashRecoveryCodes(codes: string[]): string[] {
  return codes.map((c) => hashRecoveryCode(c));
}

/**
 * Hash one server-generated recovery code. This write-side operation is
 * intentionally strict: only the exact 28-symbol generated alphabet is
 * accepted, either compact or grouped with six ASCII hyphens.
 */
export function hashRecoveryCode(code: string): string {
  const normalized = normalizeRecoveryCode(code);
  if (normalized === null) {
    throw new TypeError("Recovery code does not match the current format.");
  }
  return recoveryCodeVerifier(normalized);
}

function recoveryCodeVerifier(normalized: string): string {
  const digest = createHash("sha256").update(normalized).digest("hex");
  return `${RECOVERY_HASH_PREFIX}${digest}`;
}

export function isCurrentRecoveryCodeVerifier(value: unknown): value is string {
  return typeof value === "string" && CURRENT_RECOVERY_HASH_PATTERN.test(value);
}

/**
 * Verify a plaintext recovery code against the stored hash list. Uses
 * a constant-time per-code comparison to avoid timing leaks. Returns
 * the matched-hash string if present (so the caller can drop just that
 * one from the user's mfaBackupCodes array), or null if no match.
 */
export function findMatchingRecoveryHash(
  plaintext: string,
  storedHashes: string[],
): string | null {
  const normalized = normalizeRecoveryCode(plaintext);
  if (normalized === null) return null;
  const candidate = recoveryCodeVerifier(normalized);
  for (const h of storedHashes) {
    if (!isCurrentRecoveryCodeVerifier(h)) continue;
    if (constantTimeEqual(candidate, h)) return h;
  }
  return null;
}

/**
 * Authentication input normalization is deliberately ASCII-only and narrow:
 * accept the generated alphabet case-insensitively, in either the exact
 * seven-by-four grouped form or the exact 28-symbol compact form. Reject all
 * other separators, whitespace, ambiguous symbols, Unicode compatibility
 * characters/confusables, and wrong lengths instead of deleting them.
 */
function normalizeRecoveryCode(input: string): string | null {
  if (COMPACT_RECOVERY_CODE_PATTERN.test(input)) return input.toUpperCase();
  if (!FORMATTED_RECOVERY_CODE_PATTERN.test(input)) return null;
  return input.replaceAll("-", "").toUpperCase();
}

/** Constant-time string compare — both inputs must be the same length for the
 * result to be safe. Current candidates and stored verifiers share one fixed
 * version prefix plus a 64-character SHA-256 digest. */
function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

/** Group + format recovery codes for visual display. Pure formatter —
 *  the stored hashes are independent of presentation. */
export function formatRecoveryCodesForDisplay(codes: string[]): string {
  return codes.map((c) => c.toUpperCase()).join("\n");
}
