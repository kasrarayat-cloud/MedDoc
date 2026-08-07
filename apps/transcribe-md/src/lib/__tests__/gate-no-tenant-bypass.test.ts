// ============================================================================
// T6 — NO ROLE BYPASSES THE PRACTICE WALL. Ruled 2026-08-06 (RULINGS.md).
// ----------------------------------------------------------------------------
// ⚠️ WHY A GUARD AND NOT JUST THE DELETION. `canBypassTenantScope` was deleted
// in the same commit as this file. A deletion is a fact about today; a guard is
// a fact about every tomorrow. The helper existed because somebody once needed a
// platform-operator view, and that need has not gone away — it has been ROUTED,
// to the ADMIN phase, which already rules zero clinical content in admin. The
// next person who wants it will reach for exactly the same shape.
//
// ⚠️ AND THE BLAST RADIUS WAS NOT WHAT IT LOOKED LIKE, which is the reason this
// file argues for itself. Enumerated before removal:
//
//   consumers in apps/meddoc-pro ....... 4   (auditLog ×2, user, apiUsage)
//   consumers in apps/transcribe-md .... 0   (positive control: 15 in meddoc-pro)
//   clinical-table reads in meddoc-pro . 0   (it reads none, at all)
//   meddoc-pro's status ................ STOPPED since 2026-08-04; pro.quillmd.com 410
//
// So the removal closed NO active leak. It closed the DOOR to one. The live
// clinical app never had a bypass, and the point of this guard is that it still
// will not have one after somebody builds the next admin surface.
// ============================================================================

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, it, expect } from 'vitest';

/** Repo root, from apps/transcribe-md. */
const ROOT = join(process.cwd(), '..', '..');

/**
 * Shapes that mean "this code can read across the practice wall".
 *
 * ⚠️ MATCHED ON INTENT, NOT ON ONE IDENTIFIER. Banning the exact string
 * `canBypassTenantScope` would be satisfied by renaming it, which is not a fix —
 * it is the same hole with a different label. These patterns catch the shape.
 */
const BYPASS_SHAPES: Array<{ re: RegExp; why: string }> = [
  {
    re: /\bcanBypassTenantScope\b/,
    why: 'the removed helper is back',
  },
  {
    re: /function\s+\w*[Bb]ypass\w*TenantScope/,
    why: 'a renamed tenant-scope bypass',
  },
  {
    re: /role\s*===\s*['"]SUPER_ADMIN['"][\s\S]{0,80}return\s*\{\s*\}/,
    why: 'a role check that returns an empty predicate — Prisma reads {} as EVERY tenant',
  },
];

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === '.next' || entry === 'dist' || entry === '.git') {
      continue;
    }
    const p = join(dir, entry);
    let st;
    try {
      st = statSync(p);
    } catch {
      continue;
    }
    if (st.isDirectory()) walk(p, out);
    else if (p.endsWith('.ts') || p.endsWith('.tsx')) out.push(p);
  }
  return out;
}

/** Blanks comments so a file that EXPLAINS the ban does not trip it. */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/(^|[^:])\/\/[^\n]*/g, '$1 ');
}

const FILES = [
  join(ROOT, 'packages', 'auth', 'src'),
  join(ROOT, 'apps', 'transcribe-md', 'src'),
  join(ROOT, 'apps', 'meddoc-pro', 'src'),
]
  .filter((d) => {
    try {
      return statSync(d).isDirectory();
    } catch {
      return false;
    }
  })
  .flatMap((d) => walk(d));

describe('T6 — no role bypasses the practice wall', () => {
  it('NON-VACUITY — the scanner actually reads source', () => {
    // Without this, a moved directory makes every assertion below trivially
    // true and the gate reports green about nothing.
    expect(FILES.length, 'the scanner found no source files at all').toBeGreaterThan(200);
    const anyPrisma = FILES.some((f) => readFileSync(f, 'utf8').includes('prisma.'));
    expect(anyPrisma, 'no file mentions prisma — the roots are wrong').toBe(true);
  });

  it('⚠️ no tenant-scope bypass exists, in any of the three trees', () => {
    const offenders: string[] = [];
    for (const file of FILES) {
      if (file.includes('__tests__') || file.endsWith('gate-no-tenant-bypass.test.ts')) continue;
      const code = stripComments(readFileSync(file, 'utf8'));
      for (const { re, why } of BYPASS_SHAPES) {
        if (re.test(code)) offenders.push(`${file.replace(ROOT + '/', '')}: ${why}`);
      }
    }
    expect(
      offenders,
      'a tenant-scope bypass is back. Platform-operator needs route through the ' +
        'ADMIN phase, which rules ZERO clinical content in admin — not through a ' +
        'role that reads across the practice wall.',
    ).toEqual([]);
  });

  it('POSITIVE CONTROL — each banned shape is actually detectable', () => {
    // Proves the patterns can fire. A regex that matches nothing keeps the
    // offender list empty forever and the gate passes through anything.
    const samples = [
      'if (canBypassTenantScope(session)) return {};',
      'export function mayBypassTenantScope(s: Session) { return true; }',
      "if (session.user.role === 'SUPER_ADMIN') { return {}; }",
    ];
    samples.forEach((sample, i) => {
      const hit = BYPASS_SHAPES.some(({ re }) => re.test(sample));
      expect(hit, `banned shape ${i} is not detected by any pattern`).toBe(true);
    });
  });

  it('NEGATIVE CONTROL — a comment explaining the ban does not trip it', () => {
    // This file and the auth package both discuss `canBypassTenantScope` by
    // name. If prose counted, the guard would red on its own explanation —
    // the failure that has already been made twice in this repo.
    const prose = '// canBypassTenantScope was removed 2026-08-06; do not restore it.\n';
    const code = stripComments(prose);
    expect(
      BYPASS_SHAPES.some(({ re }) => re.test(code)),
      'a comment about the ban trips the ban',
    ).toBe(false);
  });

  it('tenantScope returns a REQUIRED practiceId, never an optional one', () => {
    // An optional key is how this failed open: Prisma drops a `where` key whose
    // value is undefined, so `{ practiceId: undefined }` is `{}` — every tenant,
    // silently. The signature itself has to forbid it.
    const src = readFileSync(join(ROOT, 'packages', 'auth', 'src', 'index.ts'), 'utf8');
    expect(src).toMatch(/export function tenantScope\([^)]*\):\s*\{\s*practiceId: string\s*\}/);
    expect(src, 'tenantScope may return a predicate with no practice').not.toMatch(
      /export function tenantScope\([^)]*\):\s*\{\s*practiceId\?/,
    );
  });
});
