// ============================================================================
// ⚠️ ITS OWN FILE, DELIBERATELY. A static import of `practice-owner-guard` is
// HOISTED above `vi.mock('@meddoc/db')` in the sibling gate, so the REAL Prisma
// client loaded and an arm that had always passed tried to open a socket —
// "SASL: SCRAM-SERVER-FIRST-MESSAGE: client password must be a string". A
// scanner needs no mocks and must not disturb a file that depends on them.
// ============================================================================
// ⚠️ THE RATCHET `practice-owner-guard.ts` SAYS EXISTS — AND DID NOT.
// ----------------------------------------------------------------------------
// `DEMOTING_WRITERS`' own doc comment reads: "gate-admin5-owner-guard pins the
// set by name and reds when a new one appears." Measured before this block was
// written: `grep -rn DEMOTING_WRITERS --include=*.ts apps packages` returned
// exactly ONE line — its own declaration. Nothing consumed it. The obligation
// was a comment describing a gate that did not exist, which is this house's
// oldest failure mode: a stated invariant is a wish until something asserts it.
//
// ⚠️ AND BUILDING IT IMMEDIATELY SURFACED THREE WRITERS THE LIST DOES NOT NAME.
// They are listed below as KNOWN AND UNGUARDED — reported, not accepted. The
// distinction matters: an accepted capability loss is the owner's call, and
// nothing here makes it. What this block buys is that a FOURTH cannot arrive
// unnoticed.
// ============================================================================
import { describe, expect, it } from 'vitest';
import { readdirSync as _rd, readFileSync as _rf, statSync as _st } from 'node:fs';
import { join as _join } from 'node:path';

import { DEMOTING_WRITERS } from '../practice-owner-guard';

/** Writers that can move a user OUT of the counted owner set, found today and
 *  NOT routed through the guard. Reported on PR #1026; adjudication pending. */
const KNOWN_UNGUARDED = [
  'apps/meddoc-pro/src/app/system-admin/actions.ts',
  'apps/transcribe-md/src/app/api/settings/delete-account/route.ts',
] as const;

function walkRepo(dir: string, out: string[] = []): string[] {
  for (const e of _rd(dir)) {
    if (e === 'node_modules' || e === '.next' || e === 'dist' || e.startsWith('.')) continue;
    const p = _join(dir, e);
    if (_st(p).isDirectory()) walkRepo(p, out);
    else if (/\.tsx?$/.test(p) && !/__tests__|\.test\./.test(p)) out.push(p);
  }
  return out;
}

describe('ADMIN-5 — the demoting-writer set is pinned, and a new one reds', () => {
  const REPO = _join(__dirname, '..', '..', '..', '..', '..');
  const roots = ['apps/transcribe-md/src', 'apps/meddoc-pro/src'].map((r) => _join(REPO, r));
  const files = roots.flatMap((r) => walkRepo(r));

  /** A write that can REMOVE a user from `practiceRole='OWNER' AND deactivatedAt IS NULL`. */
  const DEMOTING = /prisma\.user\.(update|updateMany|delete|deleteMany)|tx\.user\.(update|updateMany|delete|deleteMany)/;
  const TOUCHES = /practiceRole|deactivatedAt|isActive|\.delete\(/;

  function demotingWriters(): string[] {
    const hits: string[] = [];
    for (const f of files) {
      const src = _rf(f, 'utf8');
      if (!DEMOTING.test(src)) continue;
      if (!TOUCHES.test(src)) continue;
      hits.push(f.slice(REPO.length + 1));
    }
    return hits.sort();
  }

  it('NON-VACUITY — the scanner finds demoting writers at all', () => {
    // Without this, a moved source root or a broken regex makes every assertion
    // below trivially true and the gate reports green about nothing.
    expect(files.length, 'the walker found no source files').toBeGreaterThan(100);
    expect(demotingWriters().length, 'the scanner found NO demoting writers').toBeGreaterThan(0);
  });

  it('⚠️ every demoting writer is the guard module or a KNOWN-UNGUARDED one', () => {
    const allowed = new Set<string>([...DEMOTING_WRITERS, ...KNOWN_UNGUARDED]);
    const unexpected = demotingWriters().filter((f) => !allowed.has(f));
    expect(
      unexpected,
      'a NEW writer can move a user out of OWNER without going through ' +
        'practice-owner-guard.ts. Route it through withPracticeLock, or add it to ' +
        'KNOWN_UNGUARDED with a PR reference — do not delete this assertion.',
    ).toEqual([]);
  });

  it('⚠️ the KNOWN-UNGUARDED list is not stale — every entry still exists and still writes', () => {
    // A list of exceptions nobody re-checks becomes a list of guesses. If one of
    // these is fixed, this reds and the entry comes off.
    const found = new Set(demotingWriters());
    for (const f of KNOWN_UNGUARDED) {
      expect(found.has(f), `${f} no longer demotes — remove it from KNOWN_UNGUARDED`).toBe(true);
    }
  });

  it('⚠️ DEMOTING_WRITERS is actually consumed — the comment promised a gate', () => {
    expect(DEMOTING_WRITERS.length).toBeGreaterThan(0);
    expect(DEMOTING_WRITERS).toContain('apps/transcribe-md/src/lib/practice-owner-guard.ts');
  });
});
