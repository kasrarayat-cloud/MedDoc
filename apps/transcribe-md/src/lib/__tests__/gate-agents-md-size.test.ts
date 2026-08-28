// ============================================================================
// AGENTS.md STAYS READABLE IN ONE READ. Enforced in CI, not remembered.
// ----------------------------------------------------------------------------
// On 2026-08-26 AGENTS.md was 243,023 characters against a 150,000-character
// tool read limit. A session could therefore load a TRUNCATED rulebook and
// never be told — and a rule you cannot read is not a weaker rule, it is an
// absent one. The failure is SILENT, which is what makes it a stale-authority
// hazard on the file that governs a clinical system, rather than a formatting
// complaint.
//
// The cure was a SPLIT, never a trim: AGENTS.md keeps the live instruction set
// plus a one-row-per-entry CANON INDEX, and every full body lives verbatim in
// docs/canon/. This gate is what stops it growing back, because "a stated
// invariant is a WISH until something asserts it" — and a shell check nobody
// runs is exactly that wish.
//
// ⚠️ THIS GATE DRIVES scripts/check-agents-md-size.sh; IT DOES NOT
// RE-IMPLEMENT THE BUDGET. One implementation, two callers — a session running
// the script at STEP 0, and CI running it here. A second copy of the threshold
// would drift from the first the day either is changed, which is the same
// reasoning that keeps the push-side hook and merge-pr.sh sharing one
// inflight check.
//
// ⚠️ AND IT ASSERTS THE GUARD CAN STILL GO RED, IN THE SAME RUN. A budget
// check that only ever sees a passing file is indistinguishable from one that
// always exits 0 — so the red arm drives the real script against a deliberately
// tiny budget and requires both the non-zero exit AND the split instructions in
// its message. A guard proved only in the green direction is half-proved, and
// it is the cheaper half.
// ============================================================================

import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

import { describe, expect, it } from 'vitest';

// apps/transcribe-md/src/lib/__tests__ -> repo root
const REPO = join(__dirname, '..', '..', '..', '..', '..');
const SCRIPT = join(REPO, 'scripts', 'check-agents-md-size.sh');
const BUDGET = 120_000;
const HARD_LIMIT = 150_000;

function run(env: Record<string, string> = {}) {
  return spawnSync('bash', [SCRIPT], {
    encoding: 'utf8',
    env: { ...process.env, ...env },
  });
}

describe('AGENTS.md size budget', () => {
  it('is under the budget, with the budget itself below the read limit', () => {
    const chars = [...readFileSync(join(REPO, 'AGENTS.md'), 'utf8')].length;
    expect(BUDGET).toBeLessThan(HARD_LIMIT); // the alarm must arrive with room to act
    expect(chars).toBeLessThanOrEqual(BUDGET);
  });

  it('the shipped check agrees — and it is the check, not a copy of its logic', () => {
    const r = run();
    expect(r.status).toBe(0);
    expect(r.stdout).toContain('under the');
  });

  // ⚠️ the arm that proves the gate is not decoration.
  it('the shipped check GOES RED when the file exceeds its budget', () => {
    const r = run({ AGENTS_MD_BUDGET: '1000' });
    expect(r.status).toBe(1);
    expect(r.stdout).toContain('OVER BUDGET');
  });

  it('a red names the SPLIT rule, and refuses the tempting repair', () => {
    const out = run({ AGENTS_MD_BUDGET: '1000' }).stdout;
    expect(out).toContain('docs/canon/');
    expect(out).toContain('CANON INDEX');
    expect(out).toMatch(/Deleting canon to pass this check is the one repair that is not allowed/);
  });

  // the split's own invariant: an archived body is reachable from this file.
  it('every CANON INDEX row points at a docs/canon file that exists', () => {
    const agents = readFileSync(join(REPO, 'AGENTS.md'), 'utf8');
    const pointers = [...agents.matchAll(/→ `(docs\/canon\/[^`]+\.md)`/g)].map((m) => m[1]);
    expect(pointers.length).toBeGreaterThan(50); // non-vacuity: the index is populated
    const missing = pointers.filter((p) => {
      try {
        return readFileSync(join(REPO, p), 'utf8').length === 0;
      } catch {
        return true;
      }
    });
    expect(missing).toEqual([]);
  });

  // ==========================================================================
  // ⚠️ THE ARM ABOVE CHECKS ONE DIRECTION ONLY — row → file. Added 2026-08-26.
  //
  // A row pointing at nothing is the LOUD failure: a reader follows it and gets
  // a missing file. The silent one is the inverse — a BODY nobody points at.
  // The README's rule is "the full body goes here and its one-line row goes in
  // the index, IN THE SAME COMMIT", and until now only half of that was
  // asserted. An orphaned body is an entry no grep of AGENTS.md can reach,
  // which is the same stale-authority hazard the split was performed to cure,
  // reintroduced one file at a time.
  // ==========================================================================
  it('every docs/canon body is reachable FROM the index — no orphans', () => {
    const agents = readFileSync(join(REPO, 'AGENTS.md'), 'utf8');
    const indexed = new Set(
      [...agents.matchAll(/→ `docs\/canon\/([^`]+\.md)`/g)].map((m) => m[1]),
    );
    const onDisk = readdirSync(join(REPO, 'docs', 'canon'))
      .filter((f) => f.endsWith('.md') && f !== 'README.md');

    expect(onDisk.length).toBeGreaterThan(50); // non-vacuity: we actually read the directory
    const orphaned = onDisk.filter((f) => !indexed.has(f));
    expect(orphaned).toEqual([]);
  });

  // ⚠️ AND THE COUNT IN THE PROSE IS A CLAIM, SO IT IS MEASURED. Added
  // 2026-08-26 by the first session to add canon AFTER the split — which had to
  // hand-edit "92 entries" to "95" with nothing anywhere able to catch the
  // omission. ARITHMETIC THAT DOES NOT RECONCILE IS A FINDING; a header that
  // silently drifts from the list beneath it is how a reader learns to stop
  // trusting the numbers in this file.
  // ==========================================================================
  // ⚠️ DUPLICATE NUMBERS — ordered 2026-08-28, after a collision that would have
  // landed silently. Three branches were open, each adding canon entries. Two
  // independently claimed 69 and two claimed 70. The SLUGS differ, so git merges
  // all four cleanly and main ends up holding two entries numbered 69 and two
  // numbered 70, with the index pointing at whichever a reader finds first.
  // Nothing fails. The numbering simply stops meaning anything.
  //
  // ⚠️ AND EVERY BRANCH RECONCILED INDIVIDUALLY — all four were checked and each
  // one's stated count matched its own row count. A PER-BRANCH INVARIANT IS NOT
  // A MERGE INVARIANT: nothing any single branch can assert about itself catches
  // a collision that only exists in the union. This arm is on main for exactly
  // that reason — it is the first thing that sees the union, and it reds the
  // first post-merge run instead of letting the collision live forever.
  // ==========================================================================
  it('no two canon bodies share a number', () => {
    const files = readdirSync(join(REPO, 'docs/canon'))
      .filter((f) => /^\d+-.*\.md$/.test(f));
    expect(files.length).toBeGreaterThan(50); // non-vacuity: the directory was read
    const byNumber = new Map<string, string[]>();
    for (const f of files) {
      const n = f.match(/^(\d+)-/)![1];
      byNumber.set(n, [...(byNumber.get(n) ?? []), f]);
    }
    const dupes = [...byNumber.entries()].filter(([, v]) => v.length > 1);
    expect(
      dupes.map(([n, v]) => `${n}: ${v.join(' vs ')}`),
      'two canon bodies claim the same number — a cross-branch collision landed',
    ).toEqual([]);
  });

  it('no two index rows point at different files with the same number', () => {
    const agents = readFileSync(join(REPO, 'AGENTS.md'), 'utf8');
    const pointers = [...agents.matchAll(/→ `docs\/canon\/(\d+)-([^`]+\.md)`/g)];
    expect(pointers.length).toBeGreaterThan(50); // non-vacuity
    const byNumber = new Map<string, Set<string>>();
    for (const m of pointers) {
      const set = byNumber.get(m[1]) ?? new Set<string>();
      set.add(m[2]);
      byNumber.set(m[1], set);
    }
    const dupes = [...byNumber.entries()].filter(([, v]) => v.size > 1);
    expect(
      dupes.map(([n, v]) => `${n}: ${[...v].join(' vs ')}`),
      'the index points at two different bodies under one number',
    ).toEqual([]);
  });

  it('the stated entry count reconciles with the rows actually in the index', () => {
    const agents = readFileSync(join(REPO, 'AGENTS.md'), 'utf8');

    const claim = agents.match(/\*\*(\d+) entries live in full at `docs\/canon\/`\.\*\*/);
    expect(claim, 'the CANON INDEX header must state an entry count').not.toBeNull();

    const index = agents.slice(agents.indexOf('## CANON INDEX'));
    const rows = index.split('\n').filter((l) => /^(- | {2}- ↳ )/.test(l));

    expect(rows.length).toBeGreaterThan(50); // non-vacuity: the rows matched
    expect(Number(claim![1])).toBe(rows.length);

    // every row carries its pointer — a row without one is a dead end, and it
    // would also slip past the row → file arm above, which only sees arrows.
    expect(rows.filter((l) => !l.includes('→ `docs/canon/'))).toEqual([]);
  });
});
