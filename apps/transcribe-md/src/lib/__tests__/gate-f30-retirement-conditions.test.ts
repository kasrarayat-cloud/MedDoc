// ============================================================================
// F30 — A RETIREMENT CONDITION IS TESTED, NOT REMEMBERED.
// ----------------------------------------------------------------------------
// `INBOX.md` is printed into EVERY session's log at launch. Four separate
// sessions found entries that had met their own retirement conditions and were
// still being delivered — every one found BY HAND, while waiting on a gate, and
// every one filed and then left in place. That is the cost this gate prices:
//
//   · an expired TASK wastes a session (run04's session 04 spent its whole run
//     establishing that finished work was finished, landed nothing, and the
//     loop went dark);
//   · an expired PERMISSION is worse — a session that OBEYS it does the
//     forbidden thing correctly. The F10 carry-forward clause licenses writing
//     a §2.5 declaration onto the SHARED TREE, which is the deploy surface.
//
// ── ⚠️ WHAT THIS GATE IS ACTUALLY GUARDING, AND IT IS NOT "ARE THINGS STALE" ─
// The DUE list changes as work lands; asserting today's DUE set forever would
// be a gate that reddens when the programme SUCCEEDS — canon's own first
// question, and the reason T5's non-vacuity floor had to be rewritten.
//
// So this gate asserts the SWEEP'S DISCRIMINATION, not the file's contents:
//   1. it parses entries at all (non-vacuity, known member named);
//   2. its partition RECONCILES against the entry count;
//   3. registry ⟷ INBOX SET-EQUALITY holds in BOTH directions;
//   4. ⚠️ it puts a demonstrably-unmet condition in NOT-DUE and **not** in DUE.
//
// (4) is the control the filing item demanded in as many words — *"positive-
// control it: an entry whose condition is demonstrably NOT met must not appear
// in the expired list"* — and it is the arm that separates this from a script
// that returns everything.
//
// ⚠️ THE CONTROL IS NOT AIMED WHERE THE ANSWER IS PREDETERMINED. It uses the
// F12 pointer, whose predicate consults the SAME ledger, by the SAME mechanism,
// as the F10 pointer that lands in DUE. One returns true and one returns false
// off one code path, so a broken predicate cannot satisfy both.
// ============================================================================

import { execFileSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

import { beforeAll, describe, expect, it } from 'vitest';

/**
 * ⚠️ THE SWEEP MAKES NETWORK CALLS (`git ls-remote`), so it is run ONCE and the
 * output shared. Re-running it per arm cost 16 round trips and blew vitest's
 * 5s default — a gate that is slow is a gate somebody marks `.skip`.
 */
const TIMEOUT_MS = 60_000;

const REPO_ROOT = join(__dirname, '../../../../..');
const SCRIPT = join(REPO_ROOT, 'scripts/check-retirement-conditions.sh');
const INBOX = join(REPO_ROOT, 'docs/foundation/INBOX.md');

function run(cwd: string = REPO_ROOT): { code: number; out: string } {
  try {
    const out = execFileSync('bash', [SCRIPT], { cwd, encoding: 'utf8', stdio: 'pipe' });
    return { code: 0, out };
  } catch (e) {
    const err = e as { status?: number; stdout?: string; stderr?: string };
    return { code: err.status ?? -1, out: `${err.stdout ?? ''}${err.stderr ?? ''}` };
  }
}

/** Everything printed under one bucket heading, up to the blank line. */
function bucket(out: string, heading: string): string {
  const i = out.indexOf(heading);
  if (i === -1) return '';
  const rest = out.slice(i + heading.length);
  const end = rest.indexOf('\n\n');
  return end === -1 ? rest : rest.slice(0, end);
}

const DUE = '✅ DUE FOR RETIREMENT';
const NOT_DUE = '⛔ NOT DUE';
const UNREG = '🔴 UNREGISTERED';
const ORPHAN = '🔴 ORPHANED REGISTRY ROWS';

describe('F30 · retirement conditions are tested, not remembered', () => {
  let SHARED: { code: number; out: string };
  beforeAll(() => {
    SHARED = run();
  }, TIMEOUT_MS);

  it('the sweep exists and is script-relative (F28), not cwd-relative', () => {
    expect(existsSync(SCRIPT)).toBe(true);
    const body = readFileSync(SCRIPT, 'utf8');
    expect(body).toMatch(/BASH_SOURCE\[0\]/);
    expect(body).not.toMatch(/cd "\$\(git rev-parse --show-toplevel/);
  });

  // ── NON-VACUITY FIRST ─────────────────────────────────────────────────────
  // A matcher that read nothing would empty every bucket and the partition
  // would reconcile perfectly at zero. That is the shape this house has paid
  // for repeatedly, so the floor comes before any verdict is believed.
  it('parses real entries and names a known member — never a bare zero', () => {
    const out = SHARED.out;
    const m = out.match(/parsed (\d+) entries/);
    expect(m, `no parse line in:\n${out}`).not.toBeNull();
    expect(Number(m![1])).toBeGreaterThanOrEqual(10);
    expect(out).toContain('positive control: known member 2026-08-20T16:40:00Z found');
  });

  // ── THE PARTITION RECONCILES ─────────────────────────────────────────────
  it('every entry lands in exactly one bucket and the arithmetic adds up', () => {
    const out = SHARED.out;
    const parsed = Number(out.match(/parsed (\d+) entries/)![1]);
    const sum = out.match(/(\d+) == (\d+) entries parsed/);
    expect(sum, `no reconciliation line in:\n${out}`).not.toBeNull();
    expect(Number(sum![1])).toBe(Number(sum![2]));
    expect(Number(sum![2])).toBe(parsed);

    // and the buckets it printed must themselves total the same number
    const counts = out.match(
      /due (\d+) · not-due (\d+) · needs-human (\d+) · no-condition (\d+) · retired (\d+) · unregistered (\d+) · cannot-tell (\d+)/,
    );
    expect(counts).not.toBeNull();
    const total = counts!.slice(1, 8).reduce((a, b) => a + Number(b), 0);
    expect(total).toBe(parsed);
  });

  // ── SET-EQUALITY, BOTH DIRECTIONS — the anti-stale-list ratchet ──────────
  // A hand-kept registry is safe ONLY because neither direction can rot
  // quietly: an unregistered entry is a finding, and so is an orphan row.
  it('registry ⟷ INBOX is a SET EQUALITY — no unregistered entry, no orphan row', () => {
    const out = SHARED.out;
    // ⚠️ THE FAILURE CARRIES THE CENSUS, AND THAT IS THE WHOLE POINT OF THIS
    // MESSAGE. This arm went RED twice in CI on one unchanged tree, naming a
    // DIFFERENT entry each time, while every local and CI-shaped reproduction
    // was clean. The bucket alone says WHICH row was called an orphan; it does
    // not say what the sweep READ. Without that, "an entry went missing from
    // the file" and "the registry rotted" are the same red — two states
    // collapsed into one, which is this house's most-repeated defect.
    const census = out.match(/· census\([0-9]+\):.*/)?.[0] ?? '(no census line — an OLD sweep)';
    const registry = out.match(/· registry\([0-9]+\):.*/)?.[0] ?? '(no registry line — an OLD sweep)';
    const evidence = `\n${census}\n${registry}`;
    expect(bucket(out, UNREG).trim(), `unregistered entries:\n${bucket(out, UNREG)}${evidence}`).toBe('');
    expect(bucket(out, ORPHAN).trim(), `orphan registry rows:\n${bucket(out, ORPHAN)}${evidence}`).toBe('');
  });

  // ── ⚠️ THE CONTROL THE FILING ITEM DEMANDED ──────────────────────────────
  it('CONTROL — a demonstrably UNMET condition lands in NOT-DUE and never in DUE', () => {
    const out = SHARED.out;

    // F12's pointer: F12 is open (F12-g is unclosed), so its condition is unmet.
    expect(bucket(out, NOT_DUE)).toContain('2026-08-17T12:00:00Z');
    expect(bucket(out, DUE)).not.toContain('2026-08-17T12:00:00Z');

    // ...and the SAME predicate, over the SAME file, does return true for a
    // closed item. One mechanism, two answers — so a broken predicate that
    // always-says-no could not satisfy the arm below.
    expect(bucket(out, DUE)).toContain('2026-08-16T19:30:00Z');

    // The NOT-DUE bucket must not be empty: a sweep that returned everything
    // would be indistinguishable from a broken one.
    expect(bucket(out, NOT_DUE).trim().length).toBeGreaterThan(0);
  });

  // ── ⚠️ A BROKEN INSTRUMENT MUST NOT LOOK LIKE AN UNMET CONDITION ─────────
  // The `merged:` predicate asks two questions — is the branch gone (network),
  // and is the file on `origin/main` (a LOCAL ref). A CI checkout is routinely
  // shallow or single-branch, so the ref can be missing with the network up.
  // Without a control, that failure reports NOT MET — "we could not look" and
  // "the condition is unmet" collapsed into one answer, which is this house's
  // most-repeated defect and would keep a retired entry alive forever.
  //
  // This arm is CONDITIONAL on the controls, so it is honest on a runner that
  // genuinely cannot resolve the ref: there, the entry must be CANNOT-TELL.
  it('a control failure routes to CANNOT-TELL, never to NOT-DUE', () => {
    const out = SHARED.out;
    const controls = out.match(/origin reachable=(\d) · origin\/main resolvable=(\d)/);
    expect(controls, `no controls line in:\n${out}`).not.toBeNull();
    const [, net, ref] = controls!;

    const AUTOCERT = '2026-08-18T07:00:00Z';
    if (net === '1' && ref === '1') {
      // Both instruments answered, so the verdict must be a real one.
      expect(bucket(out, DUE)).toContain(AUTOCERT);
    } else {
      // An instrument was blind — the ONLY legal answer is cannot-tell.
      expect(bucket(out, NOT_DUE)).not.toContain(AUTOCERT);
      expect(bucket(out, DUE)).not.toContain(AUTOCERT);
    }
  });

  // ── IT IS REPORT-ONLY. It must not be able to change the file it reads. ──
  it('is READ-ONLY — INBOX.md is byte-identical before and after a run', () => {
    const before = readFileSync(INBOX);
    run();
    expect(readFileSync(INBOX).equals(before)).toBe(true);
  }, TIMEOUT_MS);

  // ── F28's OWN LESSON, APPLIED TO THIS SCRIPT ────────────────────────────
  it('gives the SAME answer from a foreign cwd as from the repo root', () => {
    const fromRoot = run(REPO_ROOT);
    const fromForeign = run(join(REPO_ROOT, 'apps/transcribe-md'));
    expect(fromForeign.code).toBe(fromRoot.code);
    expect(fromForeign.out).toBe(fromRoot.out);
    expect(fromRoot.out).toMatch(/retirement-condition sweep/);
  }, TIMEOUT_MS);

  // ── EXIT CODE IS A CLAIM, AND IT MUST MATCH THE BUCKETS ─────────────────
  // 0 = nothing due · 1 = a finding · 2 = can't tell. A green with a populated
  // DUE list, or a red with an empty one, is the check lying about itself.
  it('the exit code agrees with what it printed', () => {
    const { code, out } = SHARED;
    const dueCount = Number(out.match(/due (\d+) ·/)![1]);
    const cantCount = Number(out.match(/cannot-tell (\d+)/)![1]);
    const unregCount = Number(out.match(/unregistered (\d+)/)![1]);

    if (cantCount > 0) expect(code).toBe(2);
    else if (dueCount > 0 || unregCount > 0) expect(code).toBe(1);
    else expect(code).toBe(0);
  });
});
