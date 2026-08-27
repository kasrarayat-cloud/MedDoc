// ============================================================================
// EVERY FILE STEP 0 ORDERS A SESSION TO READ IS EITHER READABLE, OR SAYS IT IS
// NOT. Enforced in CI, not remembered.
// ----------------------------------------------------------------------------
// gate-agents-md-size.test.ts guards ONE file. MASTER STEP 0.3 names FOUR:
//
//     "Read docs/foundation/SPEC.md, RELAY.md, RULINGS.md, and AGENTS.md."
//
// Measured on 87c9d3bc — the commit that landed the AGENTS.md split:
//
//     AGENTS.md      87,383    readable
//     SPEC.md        28,340    readable
//     RULINGS.md    371,533    2.5x the 150,000-character read limit
//     RELAY.md    1,793,436    12.0x
//
// Two of the four could not be read, one of them by twelve times, and nothing
// anywhere said so. That is the split's own lesson — a gate's WATCHED SET
// diffed against the rule's NAMED SET — arriving one file over.
//
// ⚠️ AND THE LEDGER'S TRUNCATION IS THE WORSE ONE. RELAY.md is APPEND-ONLY, so
// the front of the file is its OLDEST content: a plain read returns the stale
// end and omits every current arc, with no signal that anything is missing.
//
// The cure is not a budget — a ledger that may not grow is not a ledger. The
// cure is that an oversize file DECLARES itself where a truncated reader still
// sees it, and this gate holds that in both directions.
//
// ⚠️ THIS GATE DRIVES scripts/check-read-budget.sh; IT DOES NOT RE-IMPLEMENT
// THE RULE. Same reasoning as gate-agents-md-size.test.ts, and it matters twice
// as much here: the script is NOT in the loop's .claude/settings.json allow
// list, so `npx vitest` is the ONLY way an unattended session can execute it at
// all. This file is that session's instrument as well as CI's gate.
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

import { describe, expect, it } from 'vitest';

// apps/transcribe-md/src/lib/__tests__ -> repo root
const REPO = join(__dirname, '..', '..', '..', '..', '..');
const SCRIPT = join(REPO, 'scripts', 'check-read-budget.sh');
const HARD_LIMIT = 150_000;

// Every file a STANDING INSTRUCTION tells a session to read. Kept here as well
// as in the script deliberately: if the two lists ever disagree, one of them
// was edited without the other, and that IS the defect this gate watches.
//
// ⚠️ THE ROUNDS LEDGER IS IN THIS LIST BECAUSE THE FIRST DRAFT LEFT IT OUT.
// MASTER STEP 0.3 does not name it; AGENTS.md § "Multi-session programs have
// relay ledgers — READ THEM FIRST" does, and it measured 235,184 chars — 1.57x
// the limit. The guard that exists to diff a WATCHED set against a NAMED set
// had a watched set narrower than the named set, one file over.
const NAMED = [
  'AGENTS.md',
  'docs/foundation/MASTER.md',
  'docs/foundation/SPEC.md',
  'docs/foundation/RELAY.md',
  'docs/foundation/RULINGS.md',
  'docs/foundation/DISCOVERY.md',
  'docs/foundation/INBOX.md',
  'docs/rounds/SPEC.md',
  'docs/rounds/RELAY.md',
];

const OVERSIZE_BANNER = /^<!-- READ-PROTOCOL: OVERSIZE/m;

function run(env: Record<string, string> = {}) {
  return spawnSync('bash', [SCRIPT], {
    encoding: 'utf8',
    env: { ...process.env, ...env },
  });
}

function chars(rel: string): number {
  return [...readFileSync(join(REPO, rel), 'utf8')].length;
}

describe('STEP 0 read budget', () => {
  it('passes on this tree — every named file is readable or declares that it is not', () => {
    const r = run();
    expect(r.stdout).toContain('every file STEP 0 names');
    expect(r.status).toBe(0);
  });

  // non-vacuity: a check that silently skips a file is indistinguishable from
  // one that passes it.
  it('accounts for every file STEP 0 names — none silently skipped', () => {
    const out = run().stdout;
    for (const rel of NAMED) expect(out).toContain(rel);
  });

  // ⚠️ the arm that proves the gate is not decoration: OVER the limit and
  // silent about it must be RED.
  it('GOES RED when a named file is over the limit and does not declare it', () => {
    // SPEC.md, MASTER.md, DISCOVERY.md and INBOX.md carry no banner, correctly
    // — so a limit below their size must make every one of them a finding.
    const r = run({ READ_BUDGET_LIMIT: '1000' });
    expect(r.status).toBe(1);
    expect(r.stdout).toContain('AND IT DOES NOT SAY SO');
    expect(r.stdout).toContain('docs/foundation/SPEC.md');
  });

  it('a red names the BANNER rule, and refuses the tempting repair', () => {
    const out = run({ READ_BUDGET_LIMIT: '1000' }).stdout;
    expect(out).toContain('THE FIX IS A BANNER, NOT A TRIM');
    expect(out).toMatch(
      /Deleting ledger history to pass this check is the one repair that is\s+not allowed/,
    );
  });

  // ⚠️ THE OTHER DIRECTION, which a one-sided check is blind to: a banner that
  // outlived its reason is a lie that reads like a warning. This is the arm
  // that will actually fire one day — on whoever splits RELAY.md by arc and
  // leaves the notice behind.
  it('GOES RED when a file UNDER the limit still carries the oversize banner', () => {
    const r = run({ READ_BUDGET_LIMIT: '10000000' });
    expect(r.status).toBe(1);
    expect(r.stdout).toContain('carries the READ-PROTOCOL: OVERSIZE banner');
    expect(r.stdout).toContain('A warning that outlived its reason');
  });

  // the banner has to sit where a TRUNCATED read still reaches it. Shrinking
  // the head window must therefore redden the real ledgers.
  it('the banner must sit in the HEAD — a banner below the window does not count', () => {
    const r = run({ READ_BUDGET_HEAD_LINES: '1' });
    expect(r.status).toBe(1);
    expect(r.stdout).toContain('docs/foundation/RELAY.md');
    expect(r.stdout).toContain('AND IT DOES NOT SAY SO');
  });

  // proves the AGENTS.md row is DELEGATED rather than a second copy of the
  // budget: only the real script honours AGENTS_MD_BUDGET.
  it('delegates AGENTS.md to check-agents-md-size.sh rather than re-implementing it', () => {
    const r = run({ AGENTS_MD_BUDGET: '1000' });
    expect(r.status).toBe(1);
    expect(r.stdout).toContain('delegated check is RED');
    expect(r.stdout).toContain('OVER BUDGET');
  });

  // the facts the whole item rests on, asserted rather than quoted, so the
  // ledger rows above cannot quietly stop being true.
  // ⚠️ THIS LIST SHRANK FROM THREE TO ONE ON 2026-08-26, AND THAT IS THIS ARM
  // DOING ITS JOB. F32 shipped predicting exactly this: "the negative arm will
  // hold you to it — on whoever eventually splits RELAY.md by arc and leaves the
  // notice behind." The split landed; docs/foundation/RELAY.md went 1,830,324 ->
  // 20,317 and RULINGS.md 375,008 -> 39,238, so both moved to the readable list
  // below and their banners were removed IN THE SAME COMMIT. The gate went red
  // until they were, which is the whole design.
  //
  // docs/rounds/RELAY.md stays here deliberately: it belongs to the Rounds
  // programme, not Foundation, and is scheduled as a named, triggered item
  // rather than swept up for tidiness.
  it('the oversize ledger really is over the read limit, and really does declare it', () => {
    for (const rel of [
      'docs/rounds/RELAY.md',
    ]) {
      const n = chars(rel);
      expect(n).toBeGreaterThan(HARD_LIMIT);
      const head = readFileSync(join(REPO, rel), 'utf8').split('\n').slice(0, 60).join('\n');
      expect(head).toMatch(OVERSIZE_BANNER);
    }
  });

  it('and the readable ones really are readable, and carry no banner', () => {
    for (const rel of [
      'docs/foundation/RELAY.md',
      'docs/foundation/RULINGS.md',
      'AGENTS.md',
      'docs/foundation/SPEC.md',
      'docs/foundation/MASTER.md',
      'docs/rounds/SPEC.md',
    ]) {
      expect(chars(rel)).toBeLessThan(HARD_LIMIT);
      expect(readFileSync(join(REPO, rel), 'utf8')).not.toMatch(OVERSIZE_BANNER);
    }
  });
});
