// ============================================================================
// Unit tests for the QA-only email auto-confirm bypass.
// ----------------------------------------------------------------------------
// The bypass is one of the few code paths that can affect production auth
// posture, so we keep its tests close to the source and check both the
// "fire" and "DON'T fire" cases plus the misconfiguration safety net.
// ============================================================================

import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import { isAutoConfirmDomain } from './email-auto-confirm';

const ENV_KEY = 'EMAIL_AUTO_CONFIRM_DOMAINS';

describe('isAutoConfirmDomain', () => {
  let original: string | undefined;

  beforeEach(() => {
    original = process.env[ENV_KEY];
    delete process.env[ENV_KEY];
  });

  afterEach(() => {
    if (original === undefined) delete process.env[ENV_KEY];
    else process.env[ENV_KEY] = original;
  });

  it('returns true for a domain on the allowlist (RFC 6762 reserved .local)', () => {
    process.env[ENV_KEY] = 'quillmd-test.local';
    expect(isAutoConfirmDomain('qa-sweep-1234@quillmd-test.local')).toBe(true);
  });

  it('returns false for a real-mail domain even when present in the allowlist', () => {
    // Defensive: even if an operator fat-fingers the env var to include
    // gmail.com, the hard-coded denylist refuses to bypass.
    process.env[ENV_KEY] = 'gmail.com,quillmd-test.local';
    expect(isAutoConfirmDomain('test@gmail.com')).toBe(false);
    // The non-denied domain in the same env var still works.
    expect(isAutoConfirmDomain('test@quillmd-test.local')).toBe(true);
  });

  it('returns false for our own production domain even if listed', () => {
    process.env[ENV_KEY] = 'quillmd.com';
    expect(isAutoConfirmDomain('founder@quillmd.com')).toBe(false);
  });

  it('returns false when env var is unset', () => {
    expect(process.env[ENV_KEY]).toBeUndefined();
    expect(isAutoConfirmDomain('qa@quillmd-test.local')).toBe(false);
  });

  it('returns false when env var is empty / whitespace', () => {
    process.env[ENV_KEY] = '';
    expect(isAutoConfirmDomain('qa@quillmd-test.local')).toBe(false);

    process.env[ENV_KEY] = '   ';
    expect(isAutoConfirmDomain('qa@quillmd-test.local')).toBe(false);
  });

  it('returns false for a domain NOT in the allowlist', () => {
    process.env[ENV_KEY] = 'quillmd-test.local';
    expect(isAutoConfirmDomain('qa@example.com')).toBe(false);
    expect(isAutoConfirmDomain('qa@quillmd-test.example')).toBe(false);
  });

  it('parses comma-separated allowlists with whitespace', () => {
    process.env[ENV_KEY] = ' a.test , b.example  ,c.invalid';
    expect(isAutoConfirmDomain('x@a.test')).toBe(true);
    expect(isAutoConfirmDomain('x@b.example')).toBe(true);
    expect(isAutoConfirmDomain('x@c.invalid')).toBe(true);
    expect(isAutoConfirmDomain('x@d.test')).toBe(false);
  });

  it('matches the domain case-insensitively', () => {
    process.env[ENV_KEY] = 'QuillMD-Test.LOCAL';
    expect(isAutoConfirmDomain('Q@quillmd-test.local')).toBe(true);
    expect(isAutoConfirmDomain('Q@QUILLMD-TEST.LOCAL')).toBe(true);
  });

  it('returns false for malformed input (no @, multiple @, empty parts)', () => {
    process.env[ENV_KEY] = 'quillmd-test.local';
    expect(isAutoConfirmDomain('plainstring')).toBe(false);
    expect(isAutoConfirmDomain('@quillmd-test.local')).toBe(false);
    expect(isAutoConfirmDomain('a@')).toBe(false);
    expect(isAutoConfirmDomain('')).toBe(false);
    // multiple @ — split takes everything after last @ which IS the
    // listed domain, so the bypass DOES fire. Matches the standard
    // "right of last @" interpretation. Documented behavior.
    expect(isAutoConfirmDomain('a@b@quillmd-test.local')).toBe(true);
  });

  it('does not match on substring overlap', () => {
    process.env[ENV_KEY] = 'test.local';
    // exact match wins; partial-suffix match must NOT fire
    expect(isAutoConfirmDomain('x@test.local')).toBe(true);
    expect(isAutoConfirmDomain('x@quillmd-test.local')).toBe(false);
    expect(isAutoConfirmDomain('x@nottest.local')).toBe(false);
  });

  it('handles non-string input defensively', () => {
    process.env[ENV_KEY] = 'quillmd-test.local';
    // @ts-expect-error — testing runtime guard against bad callers
    expect(isAutoConfirmDomain(undefined)).toBe(false);
    // @ts-expect-error
    expect(isAutoConfirmDomain(null)).toBe(false);
    // @ts-expect-error
    expect(isAutoConfirmDomain(42)).toBe(false);
  });
});
