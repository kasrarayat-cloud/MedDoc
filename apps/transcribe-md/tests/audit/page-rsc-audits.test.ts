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

// ============================================================================
// ⚠️ F-09's /dashboard SUITE WAS RETIRED 2026-08-05 (F-ret.3), AND RETIRING AN
// AUDIT TEST NEEDS EVIDENCE, NOT AN ARGUMENT.
// ----------------------------------------------------------------------------
// It asserted four things about `app/dashboard/page.tsx`: that it imports
// `logAudit`, calls it with `action: 'VIEWED_DASHBOARD'`, declares
// `source: 'rsc:/dashboard'`, and targets the user. That page is now a
// 51-line unconditional `redirect('/board')` — the 682-line body those
// assertions read had not executed in production since 2026-08-02, because the
// skin flag redirected above it.
//
// THE OBLIGATION MOVED; IT WAS NOT DROPPED. §164.312(b) wants a doctor's read of
// a PHI-adjacent landing page recorded, and `/board` — the surface that replaced
// /dashboard as the home — writes its own row. Measured on PRODUCTION, read-only:
//
//     VIEWED_DASHBOARD    2361 rows   2026-05-06 → 2026-08-03
//     VIEWED_VISIT_LIST    301 rows   2026-08-02 → 2026-08-05 (current)
//
// The old row stops at the flip; the new one starts at it and is current, with a
// one-day overlap during the transition. So F-09 stays CLOSED, by its successor.
//
// ⚠️ WITHOUT THAT QUERY THIS WOULD HAVE BEEN A COMPLIANCE CHANGE WEARING A
// REFACTOR'S CLOTHES. "The code is unreachable" is an argument about source; it
// is not evidence that the audit trail is unbroken. The rows are.
//
// The F-11 /settings suite below is UNTOUCHED and still enforced — /settings is
// still a page, and still writes VIEWED_SETTINGS.
//
// UN-RETIRE CONDITION: if /dashboard ever renders again rather than forwarding,
// its access row comes back and this suite is where its test belongs.
// ============================================================================

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
