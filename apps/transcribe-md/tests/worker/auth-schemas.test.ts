// Email max-length coverage for the auth schemas (P2-001 fix).
// Round 2 audit caught a 180-char email landing in the users table
// because z.string().email() doesn't enforce a length cap. This file
// pins the .max(254) behavior so a future refactor can't quietly drop
// the constraint and reopen the row-pollution surface.
//
// Pre-fix: SignupSchema accepted any-length email; the QA bypass
// auto-confirm landed a 180-char row in production.
// Post-fix: every auth/* email schema has .max(254) per RFC 5321.

import { describe, expect, it } from 'vitest';

import { LoginSchema, SignupSchema } from '@/actions/auth-schemas';

const VALID_PASSWORD = 'CorrectHorse9Battery';
const VALID_NAME = 'QA Test Doctor';

function emailOfLocalLen(localLen: number): string {
  // Total length = localLen + '@example.com'.length (12) = localLen + 12.
  return 'a'.repeat(localLen) + '@example.com';
}

describe('SignupSchema email cap', () => {
  it('accepts a normal-length email', () => {
    const r = SignupSchema.safeParse({
      email: 'doctor@quillmd-test.local',
      password: VALID_PASSWORD,
      name: VALID_NAME,
      acceptTerms: 'on',
    });
    expect(r.success).toBe(true);
  });

  it('accepts an email at exactly 254 chars (RFC 5321 boundary)', () => {
    const email = emailOfLocalLen(254 - 12); // 242 + '@example.com'
    expect(email.length).toBe(254);
    const r = SignupSchema.safeParse({
      email,
      password: VALID_PASSWORD,
      name: VALID_NAME,
      acceptTerms: 'on',
    });
    expect(r.success).toBe(true);
  });

  it('rejects an email at 255 chars (one over the cap)', () => {
    const email = emailOfLocalLen(255 - 12);
    expect(email.length).toBe(255);
    const r = SignupSchema.safeParse({
      email,
      password: VALID_PASSWORD,
      name: VALID_NAME,
      acceptTerms: 'on',
    });
    expect(r.success).toBe(false);
    if (!r.success) {
      const onEmail = r.error.issues.some((i) => i.path[0] === 'email');
      expect(onEmail).toBe(true);
    }
  });

  it('rejects pathological multi-KB emails (DB-pollution sentinel)', () => {
    // The Round 2 audit DB row was 210 chars (under 254, so the cap
    // wouldn't have stopped that specific input — by design: 254 is
    // RFC 5321's compliant ceiling, not a defense against any-too-long
    // address). The real protection is against the 1KB+ / 10KB+ shape
    // that an attacker would actually use to grow the email column
    // index. Sentinel here is a 1024-char local-part — clearly
    // pathological, schema fires.
    const r = SignupSchema.safeParse({
      email: 'a'.repeat(1024) + '@quillmd-test.local',
      password: VALID_PASSWORD,
      name: VALID_NAME,
      acceptTerms: 'on',
    });
    expect(r.success).toBe(false);
  });

  it('still rejects a malformed email regardless of length', () => {
    const r = SignupSchema.safeParse({
      email: 'not-an-email',
      password: VALID_PASSWORD,
      name: VALID_NAME,
      acceptTerms: 'on',
    });
    expect(r.success).toBe(false);
  });
});

describe('LoginSchema email cap', () => {
  it('accepts a normal-length email', () => {
    const r = LoginSchema.safeParse({
      email: 'doctor@quillmd-test.local',
      password: 'anything-non-empty',
    });
    expect(r.success).toBe(true);
  });

  it('rejects an email over 254 chars', () => {
    const r = LoginSchema.safeParse({
      email: emailOfLocalLen(300),
      password: 'anything-non-empty',
    });
    expect(r.success).toBe(false);
  });
});

// Static-style coverage: read the API route source files and assert
// every z.string().email() call has the cap. Keeps the 5 inline-schema
// routes honest without exporting each `Body` const just for tests.
describe('static check — every email schema has .max(254)', () => {
  it('admin user routes + visit export-email + visit sign cap all email fields', async () => {
    const fs = await import('node:fs/promises');
    const files = [
      'apps/transcribe-md/src/app/api/admin/users/[id]/grant-admin/route.ts',
      'apps/transcribe-md/src/app/api/admin/users/[id]/revoke-admin/route.ts',
      'apps/transcribe-md/src/app/api/admin/users/[id]/soft-delete/route.ts',
      'apps/transcribe-md/src/app/api/visits/[id]/export/email/route.ts',
      'apps/transcribe-md/src/app/api/visits/[id]/sign/route.ts',
      'apps/transcribe-md/src/app/api/auth/forgot-password/route.ts',
      'apps/transcribe-md/src/app/api/auth/resend-verification/route.ts',
      'apps/transcribe-md/src/app/api/settings/change-email/route.ts',
    ];
    for (const rel of files) {
      const path = '/opt/meddoc-pro/' + rel;
      let src: string;
      try {
        src = await fs.readFile(path, 'utf8');
      } catch {
        // CI runs from a checked-out tree; fall back to repo-relative
        src = await fs.readFile(rel, 'utf8');
      }
      // For every z.string().email() chain, walk to the end of the
      // chain (until newline / semicolon) and assert .max(254) is
      // somewhere along it. Tolerant of whitespace + .optional() +
      // any modifier order.
      const emailCalls = src.matchAll(/z\.string\(\)\.email\(\)([^;\n]*)/g);
      for (const m of emailCalls) {
        const tail = m[1];
        expect(tail, `${rel}: z.string().email()${tail} is missing .max(254)`).toMatch(
          /\.max\(\s*254\s*\)/
        );
      }
    }
  });
});
