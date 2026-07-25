// ============================================================================
// Regression guard — AuditAction is a Postgres ENUM, so LIKE needs ::text.
// ----------------------------------------------------------------------------
// `WHERE action LIKE 'EXPORT_%'` against the enum throws
//   ERROR: operator does not exist: "AuditAction" ~~ unknown   (SQLSTATE 42883)
// The PHI-export volume-spike detector shipped with exactly that, and a bare
// `.catch(() => [])` turned the throw into a clean "no threats" render — so the
// detector was BLIND in production from 2026-04-26 until 2026-07-25 while prod
// Postgres logged 975 occurrences of the error and /admin/security said
// all-clear.
//
// This is a source-level guard rather than a query test on purpose: the failure
// mode is a query *form* that only errors against a live enum column, so a
// mocked-DB unit test would happily pass on the broken version. Reading the
// shipped SQL is what actually catches the regression.
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = join(__dirname, '..', 'dashboard-data.ts');
const raw = readFileSync(SRC, 'utf-8');

/** Scan CODE, not prose. The helper's own doc comment quotes the buggy forms
 *  verbatim (`action LIKE 'EXPORT_%'`, `.catch(() => [])`) so future readers
 *  know what the bug looked like — without this strip, the guard matches its
 *  own documentation and fails on a correct file. */
const src = raw
  .replace(/\/\*[\s\S]*?\*\//g, '')   // block comments
  .replace(/^\s*\/\/.*$/gm, '');       // line comments

describe('admin threat detectors — AuditAction enum handling', () => {
  it('never applies LIKE to the raw enum column', () => {
    // Any `action LIKE` that is not `action::text LIKE` is the 42883 bug.
    const bad = [...src.matchAll(/action\s+LIKE/gi)];
    expect(
      bad.length,
      'found `action LIKE` without a ::text cast — this throws 42883 against the ' +
        'AuditAction enum and silently blinds the detector'
    ).toBe(0);
  });

  it('the export-volume detector still filters on EXPORT_ actions (cast form)', () => {
    const cast = [...src.matchAll(/action::text\s+LIKE\s+'EXPORT_%'/g)];
    // Two copies exist by design: the live getThreats() query and its history
    // mirror. If one is refactored away this count changes and we look again.
    expect(cast.length).toBe(2);
  });

  it('detector query failures are LOUD, never a bare swallow', () => {
    // A bare `.catch(() => [])` makes a dead detector indistinguishable from
    // "no threats found" — the precise reason this went unnoticed for 90 days.
    const bareSwallow = [...src.matchAll(/\.catch\(\(\)\s*=>\s*\[\]/g)];
    expect(
      bareSwallow.length,
      'a detector query still swallows failures silently; route it through ' +
        'detectorFail() so a blind detector is logged rather than rendered as clean'
    ).toBe(0);
    expect(src).toContain('function detectorFail');
  });
});
