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

import { readFileSync } from 'node:fs';
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
});
