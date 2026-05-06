// ============================================================================
// page-rsc-audits.test.ts — F-09 + F-11 closure guards
// ----------------------------------------------------------------------------
// QA Interaction Auditor v3.2 PASS A surfaced two §164.312(b) audit-row
// gaps on PHI-adjacent server components:
//
//   F-09 — /dashboard reads patient + visit lists; previously emitted
//          no VIEWED_DASHBOARD audit row (the most-trafficked
//          authenticated page, post-Round-3-PR-C).
//   F-11 — /settings reads users + user_sessions (the latter exposes
//          ipAddress + userAgent — device-fingerprint columns); no
//          VIEWED_SETTINGS audit row was emitted.
//
// We can't mount the full RSC in jsdom (it composes <AppFrame>,
// <Greeting>, <StatCard>, etc.), and the audit emit happens at the
// data-fetching boundary BEFORE the render. So the test pins the
// shape of the source — the literal `logAudit({ ... })` call,
// imported by the page module — by reading the file + asserting:
//
//   1. The page module imports `logAudit` from '@/lib/audit'.
//   2. The page module contains a `void logAudit({ ... })` call with
//      the right `action` value, `targetType`, and `metadata.source`.
//
// This catches the regression where someone refactors the page +
// drops the audit call. It's not a full-runtime test, but it's the
// pragmatic level given that Round 3 PR-C didn't ship runtime tests
// for its own VIEWED_PATIENT_FILE / VIEWED_VISIT_LIST emits either —
// they're verified end-to-end via the QA agent's sweep-all run, which
// is the canonical closure proof.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const REPO_ROOT = resolve(__dirname, '..', '..', '..', '..');

function readSource(relPath: string): string {
  return readFileSync(resolve(REPO_ROOT, relPath), 'utf-8');
}

describe('F-09: /dashboard emits VIEWED_DASHBOARD audit row', () => {
  const src = readSource('apps/transcribe-md/src/app/dashboard/page.tsx');

  it("imports logAudit from '@/lib/audit'", () => {
    expect(src).toMatch(/import\s+\{\s*logAudit\s*\}\s+from\s+['"]@\/lib\/audit['"]/);
  });

  it('contains a void logAudit call with action=VIEWED_DASHBOARD', () => {
    // Match the call with whitespace tolerance; the surrounding `void`
    // pattern keeps audit fire-and-forget per the file's precedents.
    expect(src).toMatch(/void\s+logAudit\s*\(\s*\{[\s\S]*?action:\s*['"]VIEWED_DASHBOARD['"]/);
  });

  it("audit metadata declares source='rsc:/dashboard'", () => {
    expect(src).toMatch(/source:\s*['"]rsc:\/dashboard['"]/);
  });

  it("targets the user (targetType='User', targetId=userId)", () => {
    // The dashboard is an aggregate view of one user's surface; the
    // user is the audit target.
    const auditBlock = src.match(
      /void\s+logAudit\s*\(\s*\{[\s\S]*?\n\s*\}\s*\)\s*;/m
    );
    expect(auditBlock?.[0]).toMatch(/targetType:\s*['"]User['"]/);
    expect(auditBlock?.[0]).toMatch(/targetId:\s*userId/);
  });
});

describe('F-11: /settings emits VIEWED_SETTINGS audit row', () => {
  const src = readSource('apps/transcribe-md/src/app/settings/page.tsx');

  it("imports logAudit from '@/lib/audit'", () => {
    expect(src).toMatch(/import\s+\{\s*logAudit\s*\}\s+from\s+['"]@\/lib\/audit['"]/);
  });

  it('contains a void logAudit call with action=VIEWED_SETTINGS', () => {
    expect(src).toMatch(/void\s+logAudit\s*\(\s*\{[\s\S]*?action:\s*['"]VIEWED_SETTINGS['"]/);
  });

  it("audit metadata declares source='rsc:/settings'", () => {
    expect(src).toMatch(/source:\s*['"]rsc:\/settings['"]/);
  });

  it("targets the user (targetType='User', targetId=session.user.id)", () => {
    const auditBlock = src.match(
      /void\s+logAudit\s*\(\s*\{[\s\S]*?\n\s*\}\s*\)\s*;/m
    );
    expect(auditBlock?.[0]).toMatch(/targetType:\s*['"]User['"]/);
    expect(auditBlock?.[0]).toMatch(/targetId:\s*session\.user\.id/);
  });
});

describe('AuditAction type union accepts the 3 new values', () => {
  // Lint-style guard: catches the case where someone adds an enum to
  // the schema but forgets to mirror it into the TS union (or vice
  // versa). The `audit.ts` union is hand-written; it has to grow when
  // schema.prisma's enum grows.
  const src = readSource('apps/transcribe-md/src/lib/audit.ts');

  it("AuditAction union includes 'VIEWED_DASHBOARD'", () => {
    expect(src).toMatch(/\|\s*['"]VIEWED_DASHBOARD['"]/);
  });

  it("AuditAction union includes 'VISIT_CREATED'", () => {
    expect(src).toMatch(/\|\s*['"]VISIT_CREATED['"]/);
  });

  it("AuditAction union includes 'VIEWED_SETTINGS'", () => {
    expect(src).toMatch(/\|\s*['"]VIEWED_SETTINGS['"]/);
  });
});
