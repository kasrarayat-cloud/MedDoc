// ============================================================================
// #164 item 4 — AN AMENDMENT MUST BE REACHABLE FROM THE LEDGER HEAD.
// ----------------------------------------------------------------------------
// This gate DRIVES `scripts/check-amendment-reachability.sh` rather than
// re-implementing it, so the CI check and the local check cannot drift — the
// same shape as `gate-agents-md-size` driving its script.
//
// ⚠️ WHAT IT GUARDS. An amended ruling APPENDS into its archive row, so the
// row's opening text stays the ORIGINAL title forever. On 2026-09-01 a plain
// regeneration of `main` reverted #157's head row to its explicitly-falsified
// original and `grep -c '157(d)'` went 1 -> 0 — the mandated citation route
// stopped resolving, on a ruling about what may be printed into a signed
// document. The `<!-- head: … -->` marker makes the amendment durable DATA;
// this says so when somebody forgets it.
// ============================================================================
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO = resolve(process.cwd(), '../..');
const SCRIPT = resolve(REPO, 'scripts/check-amendment-reachability.sh');

function run(): { code: number; out: string } {
  try {
    return { code: 0, out: execFileSync('bash', [SCRIPT], { encoding: 'utf8' }) };
  } catch (error) {
    const e = error as { status?: number; stdout?: string };
    return { code: e.status ?? -1, out: e.stdout ?? '' };
  }
}

describe('#164 — ledger amendments stay reachable from the head', () => {
  it('the tree has no NEW unreachable amendment', () => {
    const { code, out } = run();
    expect(out).toMatch(/amendment-reach/);
    expect(code, out).toBe(0);
  });

  it('⚠️ #157(d) — the exact row a regeneration once ate — resolves on the head', () => {
    // Not a proxy: this is the citation route AGENTS.md mandates, on the ruling
    // whose original wording would print a denied entity into a signed note.
    const head = readFileSync(resolve(REPO, 'docs/foundation/RULINGS.md'), 'utf8');
    expect(head).toContain('157(d)');
    expect(head).toContain('FINAL FORM');
  });

  it('the durability marker is what makes that true, not a hand edit', () => {
    // If the head row were hand-maintained again, the next regeneration eats it.
    const archive = readFileSync(
      resolve(REPO, 'docs/foundation/rulings/2026-08-30.md'),
      'utf8',
    );
    expect(archive).toMatch(/<!--\s*head:\s*⚠️ FINAL FORM #157\(d\)/);
  });

  it('⚠️ the script is a RATCHET and says so — the baseline may only shrink', () => {
    // Measured 2026-09-01: 38 amendment tokens, 29 already unreachable on main.
    // A literal "all reachable" gate reds main on arrival (canon 73), so the
    // pre-existing set is baselined BY NAME and only NEW ones fail. The backlog
    // is real; this arm exists so nobody reads the green as "all reachable".
    const script = readFileSync(SCRIPT, 'utf8');
    expect(script).toMatch(/BASELINE=/);
    expect(script).toMatch(/SHRINK ONLY|may only SHRINK/);
    const { out } = run();
    expect(out).toMatch(/baseline \d+/);
  });
});
