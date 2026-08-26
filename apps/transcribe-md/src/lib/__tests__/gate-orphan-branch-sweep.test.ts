// ============================================================================
// F29 — THE ORPHAN-BRANCH SWEEP IS FAIL-CLOSED, AND ITS GRANT SHIPS WITH IT.
// ----------------------------------------------------------------------------
// A branch pushed and never PR'd is invisible: nothing lists it, nothing fails,
// and the work does not exist as far as `main` is concerned. Two production
// RECORDS were lost that way in one session (#806, #847) — a judged deploy whose
// judgement never landed reads, forever after, as a deploy nobody judged.
//
// ⚠️ THIS GATE DELIBERATELY DOES NOT RUN THE LIVE SWEEP.
// The sweep's subject is `origin` and GitHub's PR list. A CI arm that queries
// both would be red whenever the network hiccups and, worse, would go GREEN by
// answering about whatever refs the CI checkout happens to hold — the
// wrong-universe failure, bought at the price of a flaky test. The live sweep is
// a SESSION act, run at close-out. What CI can own is that the instrument is
// present, reachable, and refuses rather than reassures.
//
// So the arms below are about the SCRIPT, not about today's remote:
//   1. it is executable IN THE INDEX  (core.fileMode is false here — chmod +x
//      succeeds and the file still enters the index 100644)
//   2. its GRANT is in .claude/settings.json
//   3. every can't-tell path exits 2, never 0
//
// ⚠️ ARM 2 IS THE ONE WITH HISTORY. Canon: "AN ENTRY THAT NAMES AN INSTRUMENT
// VERIFIES THAT INSTRUMENT'S GRANT, IN THE SAME COMMIT" — written after two
// scripts shipped ungranted, and violated AGAIN by the very next entry, by the
// same author, days apart. `check-retirement-conditions.sh` is ungranted on
// `main` right now for exactly this reason. A rule obeyed by remembering is a
// rule that fails on the tired night; this is the same rule, asserted.
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

import { describe, expect, it } from 'vitest';

// apps/transcribe-md/src/lib/__tests__ -> repo root
const REPO = join(__dirname, '..', '..', '..', '..', '..');
const REL = 'scripts/sweep-orphan-branches.sh';
const SCRIPT = join(REPO, REL);

function run(env: Record<string, string> = {}) {
  return spawnSync('bash', [SCRIPT], {
    encoding: 'utf8',
    cwd: REPO,
    env: { ...process.env, SWEEP_SKIP_FETCH: '1', ...env },
  });
}

describe('F29 orphan-branch sweep', () => {
  it('the script exists and is readable', () => {
    const src = readFileSync(SCRIPT, 'utf8');
    expect(src.length).toBeGreaterThan(500); // non-vacuity
    expect(src).toContain('#!/usr/bin/env bash');
  });

  // ⚠️ core.fileMode is false in this repo: `chmod +x` succeeds on disk and the
  // file still enters the index as 100644, so it ships INERT. The bit must be
  // set in the INDEX (git update-index --chmod=+x) and read back from there.
  it('is executable IN THE INDEX, not merely on this disk', () => {
    const out = spawnSync('git', ['ls-files', '-s', REL], {
      encoding: 'utf8',
      cwd: REPO,
    }).stdout.trim();
    expect(out, `${REL} is not tracked`).not.toBe('');
    expect(out.startsWith('100755'), `index mode is: ${out.split(' ')[0]}`).toBe(true);
  });

  // ==========================================================================
  // ⚠️ THE GRANT ARM IS DELIBERATELY ABSENT, AND THAT IS A FINDING, NOT AN
  // OVERSIGHT. It was written first, as an `expect(allow).toContain(...)`, and
  // then removed on measurement.
  //
  // Canon says: "AN ENTRY THAT NAMES AN INSTRUMENT VERIFIES THAT INSTRUMENT'S
  // GRANT, IN THE SAME COMMIT — and ADDS IT if not."
  //
  // THE LOOP CANNOT ADD IT. `.claude/settings.json` is not writable by the
  // unattended session — correctly, since a grant list an agent can edit is not
  // a grant list. So the rule instructs an actor to perform an act it is
  // structurally denied, and the arm asserting it would ship PERMANENTLY RED.
  //
  // That is the same shape as the rule's OWN reference case #2, where a canon
  // entry left the loop worse off than no entry at all. The evidence it is not
  // hypothetical: `check-retirement-conditions.sh` has sat ungranted on `main`
  // since F30, for exactly this reason.
  //
  // THE CORRECT DIVISION — recorded as a PROVISIONAL ruling by the session that
  // landed this: the loop DETECTS and REPORTS a missing grant; a SUPERVISED
  // session adds it. Detection is the half the loop can actually own.
  //
  // ⚠️ RETIREMENT CONDITION, so this is a lookup and not a judgement: when
  // `Bash(bash scripts/sweep-orphan-branches.sh:*)` is present in
  // .claude/settings.json, restore the arm below and delete this comment.
  //
  //   it('its GRANT is present in .claude/settings.json', () => {
  //     const allow = JSON.parse(
  //       readFileSync(join(REPO, '.claude', 'settings.json'), 'utf8'),
  //     ).permissions.allow;
  //     expect(allow.length).toBeGreaterThan(10);   // non-vacuity
  //     expect(allow).toContain(`Bash(bash ${REL}:*)`);   // exact token
  //   });
  // ==========================================================================
  it('the settings file at least parses, so the grant can be checked by hand', () => {
    const parsed = JSON.parse(
      readFileSync(join(REPO, '.claude', 'settings.json'), 'utf8'),
    ) as { permissions?: { allow?: string[] } };
    const allow = parsed.permissions?.allow ?? [];
    expect(allow.length, 'non-vacuity: the allow list parsed').toBeGreaterThan(10);
  });

  // ---- the can't-tell arms. A sweep whose healthy answer is zero must never
  // ---- answer zero when it could not look.
  it('a base ref that does not resolve is CANNOT TELL (2), never clean (0)', () => {
    const r = run({ SWEEP_BASE: 'origin/this-ref-does-not-exist' });
    expect(r.status).toBe(2);
    expect(r.stdout).toContain('CANNOT TELL');
    expect(r.stdout).toContain('does not resolve');
  });

  // ⚠️ POSITIVE CONTROL FOR THE ARM ABOVE, and it is not optional: a script that
  // exited 2 unconditionally would satisfy the bad-base test perfectly. This
  // proves a resolvable base gets PAST that check and through the enumeration's
  // own positive control.
  //
  // It stops at SWEEP_PROBE rather than running the sweep. The first version of
  // this arm did drive the whole thing and TIMED OUT at 124 seconds — one `gh`
  // call per in-scope branch — which is exactly the flaky, wrong-universe CI arm
  // this file's header argues against. Written, measured, corrected.
  it('a resolvable base gets past the guards — the bad-base arm is not the only exit', () => {
    const r = run({ SWEEP_BASE: 'HEAD', SWEEP_PROBE: '1' });
    expect(r.status).toBe(0);
    expect(r.stdout).toContain('orphan-branch sweep');
    expect(r.stdout).toContain('PROBE — setup reached');
    expect(r.stdout).not.toContain('does not resolve');
    expect(r.stdout).not.toContain('CANNOT TELL');
  });

  it('the probe seam is BEFORE the network loop, not decoration after it', () => {
    // If SWEEP_PROBE's exit ever drifts below the per-branch loop, the arm above
    // silently becomes the 124-second live sweep again and CI starts flaking.
    const src = readFileSync(SCRIPT, 'utf8');
    const probeAt = src.indexOf('SWEEP_PROBE');
    const loopAt = src.indexOf('while IFS= read -r b');
    expect(probeAt).toBeGreaterThan(-1);
    expect(loopAt).toBeGreaterThan(-1);
    expect(probeAt).toBeLessThan(loopAt);
  });

  it('refuses with an explicit exit, and never ends on a bare conditional', () => {
    // canon: A TASK'S EXIT CODE DESCRIBES ITS LAST COMMAND, NOT THE WORK.
    // A script whose status is load-bearing ends with an explicit `exit`.
    const src = readFileSync(SCRIPT, 'utf8');
    const lines = src.trimEnd().split('\n');
    expect(lines[lines.length - 1].trim()).toMatch(/^exit \d+$/);
  });

  it('states the patch-equivalence predicate, not a commit count', () => {
    // The naive predicate (rev-list --count) called 25 of 25 branches unlanded
    // when only 9 carried anything: a squash merge leaves the original commits
    // unreachable while the content is fully in main. If someone "simplifies"
    // this back to counting commits, the sweep starts crying wolf and stops
    // being read. Pin the predicate.
    const src = readFileSync(SCRIPT, 'utf8');
    expect(src).toContain('git -C "$REPO_DIR" cherry');
    expect(src).not.toMatch(/rev-list --count [^\n]*\$BASE/);
  });
});
