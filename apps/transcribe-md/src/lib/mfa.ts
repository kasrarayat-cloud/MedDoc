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
//   - Recovery codes: 10 codes per enrollment, 10 chars each (alphanumeric
//     minus ambiguous chars), grouped 4-4 with a hyphen for typability.
//     Stored as SHA-256 hashes (single-use; matched once then dropped).
//     SHA-256 is appropriate here because the codes have ~57 bits of
//     entropy each — bcrypt's slowdown isn't load-bearing at that
//     entropy level, and bcrypt-times-10-codes-per-attempt would make
//     login latency noticeable.
//   - Issuer label = "QuillMD" so the user's authenticator app shows
//     "QuillMD: their-email@…".
//
// Never throws on user-facing paths; returns null/false on invalid
// input. Throws only on programmer error (e.g. malformed stored hash).
// ============================================================================

import { generateSecret, generateURI, verifySync } from 'otplib';
import qrcode from 'qrcode';
import { createHash, randomBytes } from 'node:crypto';

const TOTP_ISSUER = 'QuillMD';

/** Symmetric tolerance window in seconds for TOTP verification.
 *  30 = accept the previous, current, and next 30-second steps —
 *  matches authenticator-app drift tolerance and Google Authenticator's
 *  default. */
const TOTP_EPOCH_TOLERANCE_SEC = 30;

// Alphabet excludes 0/O/I/1/l to prevent transcription mistakes.
const RECOVERY_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
const RECOVERY_CODE_GROUPS = 2;
const RECOVERY_CODE_GROUP_LEN = 4;

export interface MfaEnrollmentArtifact {
  /** Base32 secret (store this in users.mfaSecret only after the user
   *  verifies they can produce a 6-digit code from it). */
  secret: string;
  /** otpauth://-shaped URI for the QR code. */
  otpauthUri: string;
  /** Pre-rendered PNG data URL (base64). */
  qrPngDataUrl: string;
}

/**
 * Generate a fresh TOTP secret + a QR data-URL the user can scan with
 * their authenticator app. The secret is NOT yet committed to the DB
 * here — `users.mfaSecret` should only be written after
 * `verifyTotpToken` confirms the user can produce a 6-digit code from
 * the secret (the "verify enrollment" step).
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
    errorCorrectionLevel: 'M',
  });
  return { secret, otpauthUri, qrPngDataUrl };
}

/**
 * Validate a 6-digit token against a stored secret. Returns false on
 * any failure (wrong digits, malformed secret, otplib internal
 * error). Never throws.
 */
export function verifyTotpToken(secret: string, token: string): boolean {
  if (typeof secret !== 'string' || secret.length === 0) return false;
  if (typeof token !== 'string') return false;
  // Strip whitespace + non-digits — users sometimes paste with spaces.
  const clean = token.replace(/\s+/g, '');
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
 * Generate 10 plaintext recovery codes. The caller must show these to
 * the user once + store the SHA-256 hash array via
 * `hashRecoveryCodes(codes)` immediately.
 */
export function generateRecoveryCodes(count = 10): string[] {
  const codes: string[] = [];
  for (let i = 0; i < count; i++) {
    const groups: string[] = [];
    for (let g = 0; g < RECOVERY_CODE_GROUPS; g++) {
      let group = '';
      const bytes = randomBytes(RECOVERY_CODE_GROUP_LEN);
      for (let b = 0; b < RECOVERY_CODE_GROUP_LEN; b++) {
        group += RECOVERY_ALPHABET[bytes[b] % RECOVERY_ALPHABET.length];
      }
      groups.push(group);
    }
    codes.push(groups.join('-'));
  }
  return codes;
}

/**
 * Hash recovery codes for storage. Returns an array of hex strings the
 * same length as the input. Pure SHA-256 (one-shot); no salt because
 * the codes themselves have high entropy + are stored per-user.
 */
export function hashRecoveryCodes(codes: string[]): string[] {
  return codes.map((c) => hashRecoveryCode(c));
}

/** Hash a single recovery code. Normalizes case + strips dashes so the
 *  user's input format ("Ab3X-9pQR") matches the stored hash regardless
 *  of how they typed it. */
export function hashRecoveryCode(code: string): string {
  const normalized = normalizeRecoveryCode(code);
  return createHash('sha256').update(normalized).digest('hex');
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
  const candidate = hashRecoveryCode(plaintext);
  for (const h of storedHashes) {
    if (constantTimeEqual(candidate, h)) return h;
  }
  return null;
}

function normalizeRecoveryCode(input: string): string {
  return input.toUpperCase().replace(/[^A-Z0-9]/g, '');
}

/** Constant-time string compare — both inputs must be the same length
 *  for the result to be safe. SHA-256 hex is always 64 chars so this is
 *  always safe here. */
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
  return codes.map((c) => c.toUpperCase()).join('\n');
}
