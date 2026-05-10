// ============================================================================
// Tests for lib/mfa.ts — TOTP + recovery code round trip
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  generateMfaEnrollment,
  verifyTotpToken,
  generateRecoveryCodes,
  hashRecoveryCodes,
  hashRecoveryCode,
  findMatchingRecoveryHash,
  formatRecoveryCodesForDisplay,
} from './mfa';
import { generateSync } from 'otplib';

describe('mfa', () => {
  describe('generateMfaEnrollment', () => {
    it('returns a non-empty secret + an otpauth URI + a QR data URL', async () => {
      const out = await generateMfaEnrollment('test@example.com');
      expect(out.secret.length).toBeGreaterThan(0);
      expect(out.otpauthUri).toMatch(/^otpauth:\/\/totp\/QuillMD/);
      expect(out.otpauthUri).toContain(encodeURIComponent('test@example.com'));
      expect(out.qrPngDataUrl).toMatch(/^data:image\/png;base64,/);
    });
  });

  describe('verifyTotpToken', () => {
    it('verifies a current TOTP code generated from the same secret', async () => {
      const enroll = await generateMfaEnrollment('roundtrip@example.com');
      const validToken = await generateSync({ secret: enroll.secret });
      expect(verifyTotpToken(enroll.secret, validToken)).toBe(true);
    });

    it('rejects an empty string', async () => {
      const enroll = await generateMfaEnrollment('e@example.com');
      expect(verifyTotpToken(enroll.secret, '')).toBe(false);
    });

    it('rejects a non-6-digit input', async () => {
      const enroll = await generateMfaEnrollment('e@example.com');
      expect(verifyTotpToken(enroll.secret, '12345')).toBe(false);
      expect(verifyTotpToken(enroll.secret, '1234567')).toBe(false);
      expect(verifyTotpToken(enroll.secret, 'ABCDEF')).toBe(false);
    });

    it('rejects a wrong 6-digit code', async () => {
      const enroll = await generateMfaEnrollment('e@example.com');
      // 000000 is overwhelmingly unlikely to be valid for a random secret.
      expect(verifyTotpToken(enroll.secret, '000000')).toBe(false);
    });

    it('strips whitespace before validating', async () => {
      const enroll = await generateMfaEnrollment('e@example.com');
      const validToken = await generateSync({ secret: enroll.secret });
      const formatted = `${validToken.slice(0, 3)} ${validToken.slice(3)}`;
      expect(verifyTotpToken(enroll.secret, formatted)).toBe(true);
    });

    it('returns false for malformed secret without throwing', () => {
      expect(verifyTotpToken('', '123456')).toBe(false);
      expect(verifyTotpToken('not-base32!@#', '123456')).toBe(false);
    });
  });

  describe('generateRecoveryCodes', () => {
    it('generates 10 codes by default in the documented format', () => {
      const codes = generateRecoveryCodes();
      expect(codes).toHaveLength(10);
      for (const c of codes) {
        // 4 + 1 dash + 4 = 9 chars
        expect(c).toMatch(/^[A-Z2-9]{4}-[A-Z2-9]{4}$/);
      }
    });

    it('generates 10 distinct codes (high entropy)', () => {
      const codes = generateRecoveryCodes();
      expect(new Set(codes).size).toBe(10);
    });

    it('honours the count argument', () => {
      expect(generateRecoveryCodes(3)).toHaveLength(3);
    });
  });

  describe('hashRecoveryCodes / findMatchingRecoveryHash', () => {
    it('round-trips: a generated code matches its hash', () => {
      const codes = generateRecoveryCodes(3);
      const hashed = hashRecoveryCodes(codes);
      const matched = findMatchingRecoveryHash(codes[1], hashed);
      expect(matched).toBe(hashed[1]);
    });

    it('normalizes case + dashes when matching', () => {
      const codes = generateRecoveryCodes(1);
      const hashed = hashRecoveryCodes(codes);
      const original = codes[0]; // e.g. "AB23-9XYZ"
      // User typed lowercase + no dash
      const variant = original.toLowerCase().replace(/-/g, '');
      const matched = findMatchingRecoveryHash(variant, hashed);
      expect(matched).toBe(hashed[0]);
    });

    it('returns null on no match', () => {
      const codes = generateRecoveryCodes(3);
      const hashed = hashRecoveryCodes(codes);
      expect(findMatchingRecoveryHash('NOPE-NOPE', hashed)).toBeNull();
    });

    it('hashRecoveryCode is stable (same input → same hash)', () => {
      const a = hashRecoveryCode('ABCD-1234');
      const b = hashRecoveryCode('ABCD-1234');
      expect(a).toBe(b);
      expect(a).toHaveLength(64); // SHA-256 hex
    });
  });

  describe('formatRecoveryCodesForDisplay', () => {
    it('uppercases + joins with newlines', () => {
      expect(formatRecoveryCodesForDisplay(['ab23-9xyz', 'ef45-pqrs'])).toBe(
        'AB23-9XYZ\nEF45-PQRS',
      );
    });
  });
});
