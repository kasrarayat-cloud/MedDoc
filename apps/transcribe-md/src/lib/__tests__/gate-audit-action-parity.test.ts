// ============================================================================
// Every AuditAction the code can emit must exist in the DATABASE enum.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE A REFUSAL WORKED AND ITS AUDIT ROW SILENTLY DID NOT.
//
// `audit_logs.action` is a Postgres ENUM (`AuditAction`). Adding a label to the
// TypeScript union in `lib/audit.ts` does NOT add it to the database — and
// `logAudit` is fire-and-forget (`void logAudit({...})`), so a rejected insert
// is discarded with no error anywhere.
//
// Measured on production, 2026-08-02: `SIGN_BLOCKED_NO_ATTESTATION` was added to
// the union and the route refused correctly — 400 ATTESTATION_REQUIRED, proven
// on the wire — while the audit row never wrote. The gate held and the record
// did not. A gate that refuses without recording is half a gate, and nothing in
// the build said so: tsc was happy, the unit tests mocked `logAudit`, and the
// E2E asserted the HTTP response.
//
// So the two lists are compared directly. This is a SOURCE comparison on
// purpose — it needs no database, so it runs in the normal unit suite where a
// mismatch is caught before it ships rather than after.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, it, expect } from 'vitest';

const TS_SRC = readFileSync('src/lib/audit.ts', 'utf8');
const PRISMA_SRC = readFileSync('../../packages/db/prisma/schema.prisma', 'utf8');

/** The union members in `lib/audit.ts` — lines shaped `  | 'NAME'`. */
function tsActions(): string[] {
  return [...TS_SRC.matchAll(/^\s*\|\s*'([A-Z0-9_]+)'/gm)].map((m) => m[1]);
}

/** The labels inside `enum AuditAction { … }` in the prisma schema. */
function prismaActions(): string[] {
  const start = PRISMA_SRC.indexOf('enum AuditAction {');
  if (start === -1) throw new Error('enum AuditAction not found in schema.prisma');
  const end = PRISMA_SRC.indexOf('\n}', start);
  const body = PRISMA_SRC.slice(start, end);
  return [...body.matchAll(/^\s{2}([A-Z][A-Z0-9_]*)\s*$/gm)].map((m) => m[1]);
}

describe('AuditAction parity — the TS union vs the database enum', () => {
  it('the parse is non-vacuous: both lists are real and substantial', () => {
    // Every assertion below is quantified over these. Empty lists would make
    // them all trivially true — the exact defect this file exists to catch,
    // wearing a different hat.
    expect(tsActions().length, 'the TS union parsed to (almost) nothing').toBeGreaterThan(20);
    expect(prismaActions().length, 'the prisma enum parsed to (almost) nothing').toBeGreaterThan(20);
  });

  it('EVERY action the code can emit exists in the database enum', () => {
    const inDb = new Set(prismaActions());
    const missing = tsActions().filter((a) => !inDb.has(a));
    expect(
      missing,
      'these are emittable from TypeScript but the Postgres enum does not accept ' +
        'them — `logAudit` is void-ed, so each one FAILS SILENTLY at runtime and ' +
        'the audit row simply never appears. Add them to ' +
        'packages/db/prisma/schema.prisma AND ship a migration',
    ).toEqual([]);
  });

  it('POSITIVE CONTROL — the comparison can actually fail', () => {
    // Without this, a parser that returned an empty TS list would report "no
    // missing actions" forever and read exactly like a pass.
    const inDb = new Set(prismaActions());
    expect(
      inDb.has('THIS_ACTION_DOES_NOT_EXIST_ANYWHERE'),
      'the db-side set claims to contain a fabricated label — the parse is wrong',
    ).toBe(false);
    const missing = ['THIS_ACTION_DOES_NOT_EXIST_ANYWHERE'].filter((a) => !inDb.has(a));
    expect(missing, 'the missing-detector cannot detect a missing label').toEqual([
      'THIS_ACTION_DOES_NOT_EXIST_ANYWHERE',
    ]);
  });

  it('the action this guard was born from is present on both sides', () => {
    expect(tsActions()).toContain('SIGN_BLOCKED_NO_ATTESTATION');
    expect(prismaActions()).toContain('SIGN_BLOCKED_NO_ATTESTATION');
  });
});
