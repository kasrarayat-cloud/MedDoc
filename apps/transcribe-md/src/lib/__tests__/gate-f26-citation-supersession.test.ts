// ============================================================================
// F26 — A CANCELLED RUN THAT A RE-RUN ALREADY REPLACED IS NOT A FAILURE.
// ----------------------------------------------------------------------------
// ⚠️ THE DEFECT, MEASURED 2026-08-24 ON A LIVE PR.
//
// `gh-runs.sh cited` counted `status=="completed" and .conclusion!="success"`
// as TERMINAL, per RUN. `check-citation.sh:301-309` had understood since it was
// written that such a run is SUPERSEDED NOISE when its WORKFLOW also carries a
// success on the same sha — its own comment says "without this the normal
// push-cancels-then-reruns pattern would make every such commit un-citable."
//
// The two scripts therefore returned OPPOSITE verdicts on one commit:
//
//     f76242c4…   check-citation.sh -> 🟡 STILL RUNNING — WAIT   (exit 2)
//                 gh-runs.sh cited  -> 🔴 TERMINAL, can NEVER cite (exit 3)
//
// ⚠️ AND IT REACHED THE DEPLOY GATE, WHICH IS WHY IT IS A GATE AND NOT A TIDY-UP.
// Ruling #134 put `gh-runs.sh` on the deploy path: `lib/citation-gate.sh:44`
// maps `3 -> REFUSE`. So a commit whose `a11y-ci` was cancelled and re-run to
// success was PERMANENTLY UNDEPLOYABLE, and the only way past was
// `--declare-citation-override` — certifying past a gate on a false premise,
// which is the sanctioned-hatch-becomes-the-undisciplined-door failure canon
// names explicitly.
//
// ⚠️ THE TRIGGER IS THE LOOP'S OWN DOCUMENTED HABIT. `gh pr ready` emits
// `ready_for_review`; `a11y.yml` is its only subscriber; `cancel-in-progress`
// kills the push-triggered run and a fresh one succeeds. Every PR opened as a
// draft and then converted lands in exactly this shape.
//
// ── WHAT THIS GATE DRIVES ───────────────────────────────────────────────────
// The REAL `scripts/lib/citation-state.sh`, sourced by a real bash. Nothing
// here re-implements the verdict — a second copy is what caused the defect
// being fixed, and writing a third to test it would be the same mistake in a
// test file.
//
// Rows are SYNTHETIC and that is deliberate: the verdict is a pure function of
// `[{name,status,conclusion}]`, so driving it from the network would make the
// gate slow, flaky, and unable to express the states production has not
// happened to produce yet.
//
// ⚠️ HONEST LIMITS, NAMED RATHER THAN IMPLIED:
//   · This proves the VERDICT. It does not prove `gh-runs.sh` sources the lib,
//     which is a different claim and has its own arm below (THE WIRING).
//   · It does not re-prove the transport, the short-sha refusal or the
//     fabricated-sha refusal. Those are `gh-runs.sh`'s product and are asserted
//     where they live.
//   · The wiring arm reads `gh-runs.sh` as TEXT, so it is defeated by a rename.
//     `PARSES` is asserted alongside it for that reason.
// ============================================================================

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO_ROOT = join(__dirname, '../../../../..');
const LIB = join(REPO_ROOT, 'scripts/lib/citation-state.sh');
const RUNNER = join(REPO_ROOT, 'scripts/gh-runs.sh');

interface Row {
  name: string;
  status: 'completed' | 'in_progress' | 'queued';
  conclusion: string | null;
}

/** Source the REAL lib and ask it for a verdict on these rows.
 *  Returns the exit code and the COMBINED output — the exit code IS the verdict.
 *
 *  ⚠️ `2>&1` IS LOAD-BEARING AND ITS ABSENCE WAS A VACUOUS ASSERTION.
 *  The TERMINAL banner and the "Offending runs:" list are written to STDERR.
 *  The first version of this helper captured stdout only, so the arm asserting
 *  `not.toMatch(/a11y-ci: cancelled/)` passed against a string that could never
 *  have contained it — a negative assertion over an empty haystack, which is
 *  this programme's most-repeated defect wearing a test's clothes. Caught by a
 *  POSITIVE arm (`toMatch(/CI: failure/)`) failing, which is the only direction
 *  that could have found it. */
function verdict(rows: Row[]): { code: number; out: string } {
  const script = `
set -uo pipefail
exec 2>&1
. ${JSON.stringify(LIB)}
rows=$(cat)
citation_state "$rows" deadbeefdeadbeefdeadbeefdeadbeefdeadbeef
echo "EXIT:$?"
`;
  const out = execFileSync('bash', ['-c', script], {
    input: JSON.stringify(rows),
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  const m = out.match(/EXIT:(\d+)/);
  if (!m) throw new Error(`no EXIT marker in output:\n${out}`);
  return { code: Number(m[1]), out };
}

const ok = (name: string): Row => ({ name, status: 'completed', conclusion: 'success' });
const cancelled = (name: string): Row => ({ name, status: 'completed', conclusion: 'cancelled' });
const failed = (name: string): Row => ({ name, status: 'completed', conclusion: 'failure' });
const running = (name: string): Row => ({ name, status: 'in_progress', conclusion: null });

const REQUIRED = ['CI', 'e2e', 'a11y-ci', 'secrets-scan'];
const allGreen = (): Row[] => REQUIRED.map(ok);

// ── 0 · THE HARNESS ITSELF ─────────────────────────────────────────────────
// ⚠️ A gate whose lib is missing would report every arm as whatever bash does
// with a failed `source`. Establish the instrument before believing it.
describe('the harness', () => {
  it('the lib exists and is a file this test actually sources', () => {
    expect(existsSync(LIB)).toBe(true);
  });

  it('bash can parse the lib — a syntax error must be loud, not a silent 0', () => {
    expect(() => execFileSync('bash', ['-n', LIB], { encoding: 'utf8' })).not.toThrow();
  });
});

// ── 1 · THE ACCEPT ARM COMES FIRST, AND IT IS THE POINT ────────────────────
// ⚠️ A verdict function that returned 3 for everything would pass every refusal
// arm below and be strictly worse than none. `retire-branch.sh` passed 9 of 9
// refusal tests and then printed a false green on the one path that mattered.
describe('CITED (0) — the green half, which is the one usually skipped', () => {
  it('every required workflow green, one run each -> 0', () => {
    expect(verdict(allGreen()).code).toBe(0);
  });

  it('⚠️ THE DEFECT: a workflow cancelled AND re-run to success -> 0, not 3', () => {
    // This is the exact shape `gh pr ready` produces.
    const rows = [...allGreen(), cancelled('a11y-ci')];
    const r = verdict(rows);
    expect(r.code).toBe(0);
    // and it SAYS so, rather than quietly counting 4 of 5
    expect(r.out).toMatch(/superseded/);
  });

  it('several workflows each cancelled and re-run -> still 0', () => {
    const rows = [...allGreen(), cancelled('a11y-ci'), cancelled('CI'), cancelled('e2e')];
    expect(verdict(rows).code).toBe(0);
  });

  it('a startup_failure superseded by a success of the same workflow -> 0', () => {
    // startup_failure is the other supersedable conclusion: the run never
    // produced evidence at all, so a re-run supplies what was missing.
    const rows = [...allGreen(), { name: 'e2e', status: 'completed' as const, conclusion: 'startup_failure' }];
    expect(verdict(rows).code).toBe(0);
  });
});

// ── 1b · ⚠️ AND ONLY TWO CONCLUSIONS ARE SUPERSEDABLE ─────────────────────
// THE FIRST DRAFT OF THIS FIX SUPERSEDED *EVERY* NON-SUCCESS CONCLUSION, AND
// THIS BLOCK IS WHY THAT WAS WRONG — in the loosening direction, which is the
// one a provisional ruling may not be wrong in.
//
//   cancelled / startup_failure -> evidence DESTROYED or never produced.
//                                  A re-run legitimately supplies it.
//   failure / timed_out         -> evidence PRODUCED, AND IT SAID NO.
//                                  A later green is re-run-and-hope.
//
// `check-citation.sh:272-274` buckets the first pair separately and `:320`
// fails on a red UNCONDITIONALLY — no supersession check on that branch.
// Superseding a red here would make this script MORE PERMISSIVE THAN THE
// AUTHORITY: the very divergence this lib exists to end, inverted.
describe('⚠️ a RED is never superseded — the authority does not supersede it either', () => {
  it('a FAILED run with a green re-run of the same workflow -> 3, NOT 0', () => {
    expect(verdict([...allGreen(), failed('e2e')]).code).toBe(3);
  });

  it('a TIMED_OUT run with a green re-run of the same workflow -> 3, NOT 0', () => {
    const rows = [...allGreen(), { name: 'e2e', status: 'completed' as const, conclusion: 'timed_out' }];
    expect(verdict(rows).code).toBe(3);
  });

  it('a red and a superseded cancellation together -> 3, naming only the red', () => {
    const rows = [...allGreen(), failed('CI'), cancelled('a11y-ci')];
    const r = verdict(rows);
    expect(r.code).toBe(3);
    expect(r.out).toMatch(/CI: failure/);
    expect(r.out).not.toMatch(/a11y-ci: cancelled/);
  });
});

// ── 2 · TERMINAL (3) — AND THE NEGATIVE CONTROL IS THE WHOLE VALUE ─────────
// ⚠️ Anybody can stop a verdict firing. A fix that made nothing terminal would
// be strictly worse than the bug, because #134's deploy gate would then admit
// a commit whose gate genuinely failed.
describe('TERMINAL (3) — a live failure is UNCHANGED by the supersession rule', () => {
  it('a failure with no re-run -> 3', () => {
    const rows = [ok('CI'), ok('a11y-ci'), ok('secrets-scan'), failed('e2e')];
    expect(verdict(rows).code).toBe(3);
  });

  it('a cancellation with no re-run -> 3 (the 82158f90 shape, measured)', () => {
    const rows = [ok('secrets-scan'), ok('a11y-ci'), cancelled('CI'), cancelled('e2e')];
    const r = verdict(rows);
    expect(r.code).toBe(3);
  });

  it('⚠️ a re-run of a DIFFERENT workflow does NOT supersede -> 3', () => {
    // The trap a "was anything re-run?" implementation would fall into.
    // `a11y-ci` passing twice says nothing about `e2e` having been cancelled.
    const rows = [ok('CI'), ok('secrets-scan'), ok('a11y-ci'), ok('a11y-ci'), cancelled('e2e')];
    expect(verdict(rows).code).toBe(3);
  });

  it('the terminal message names ONLY the un-superseded runs', () => {
    const rows = [...allGreen(), cancelled('a11y-ci'), failed('e2e'), cancelled('e2e')];
    // e2e has no success -> live. a11y-ci does -> superseded.
    // (allGreen contains ok('e2e'), so remove it for this shape)
    const live = rows.filter((r) => !(r.name === 'e2e' && r.conclusion === 'success'));
    const r = verdict(live);
    expect(r.code).toBe(3);
    expect(r.out).not.toMatch(/a11y-ci: cancelled/);
  });
});

// ── 3 · PENDING (1) — AND IT OUTRANKS AN EARLIER GREEN ────────────────────
describe('PENDING (1)', () => {
  it('a run still in flight -> 1', () => {
    const rows = [ok('CI'), ok('a11y-ci'), ok('secrets-scan'), running('e2e')];
    expect(verdict(rows).code).toBe(1);
  });

  it('⚠️ superseded cancellation PLUS a run in flight -> 1, never 0', () => {
    // The exact live state of f76242c4 when this gate was written.
    const rows = [ok('CI'), ok('secrets-scan'), ok('a11y-ci'), cancelled('a11y-ci'), running('e2e')];
    expect(verdict(rows).code).toBe(1);
  });

  it('⚠️ EVERY workflow green AND a re-run of one still in flight -> 1, never 0', () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE MUTATION PROOF CAUGHT ITS ABSENCE.
    //
    // The arm above was written to pin "PENDING is tested BEFORE CITED", and it
    // CANNOT DO THAT: with `e2e` running and never green, `wf_green != wf_total`
    // either way, so swapping the two lines left all 19 arms green. The proof
    // that was supposed to establish the ordering could not have come out
    // otherwise — canon's own family, found in this gate by mutating toward it.
    //
    // The discriminating shape is a workflow that ALREADY has a green with a
    // SECOND run of itself still in flight — a re-run fired after the original
    // passed. Then `wf_green == wf_total` is true while the sha is still moving.
    //
    // The shipped order returns PENDING, deliberately and strictly: #134 turns
    // a `0` here into a DEPLOY, and a citation taken while a run is still in
    // flight is evidence about a sha whose verdict is not final.
    const rows = [...allGreen(), running('e2e')];
    expect(verdict(rows).code).toBe(1);
  });

  it('⚠️ a LIVE failure outranks a pending run -> 3, not 1', () => {
    // Otherwise the canonical `until … cited` loop polls forever on a commit
    // that can never reach a full citation — the 2026-08-17 defect this
    // function was already fixed for once.
    const rows = [ok('CI'), ok('secrets-scan'), failed('a11y-ci'), running('e2e')];
    expect(verdict(rows).code).toBe(3);
  });
});

// ── 4 · CANNOT TELL (2) — the vacuity floor ────────────────────────────────
describe('CANNOT TELL (2)', () => {
  it('⚠️ zero runs is NOT cited — vacuous, not clean', () => {
    const r = verdict([]);
    expect(r.code).toBe(2);
    expect(r.out).toMatch(/vacuous/);
  });

  it('⚠️ a COMPLETED run with a NULL conclusion REFUSES — never cited', () => {
    // Canon records `conclusion: null` on a "completed" check-run as an
    // observed impossible value. It must never reach `0`.
    //
    // ⚠️ HONEST LIMIT, PINNED DELIBERATELY LOOSE: this asserts REFUSAL, not
    // which refusal. The shipped code counts it as a live failure and returns
    // `3` ("will never cite"), which is fail-closed and is a slightly stronger
    // claim than the evidence supports — `2` = CANNOT TELL is arguably the
    // honest code for an instrument anomaly. Both refuse the deploy under
    // #134, so the distinction costs nothing today. Recorded rather than
    // changed, so a future session finds the question already asked.
    const rows = [
      { name: 'CI', status: 'completed' as const, conclusion: null },
      ...REQUIRED.filter((n) => n !== 'CI').map(ok),
    ];
    expect([2, 3]).toContain(verdict(rows).code);
  });
});

// ── 5 · THE WIRING — a lib nothing sources is a lib with no caller ─────────
// ⚠️ Canon: "a library capability with no caller passes every test it has."
// Every arm above would stay green if `gh-runs.sh` kept its own inlined copy.
describe('THE WIRING', () => {
  const runner = readFileSync(RUNNER, 'utf8');

  it('gh-runs.sh SOURCES the lib', () => {
    expect(runner).toMatch(/\.\s+"\$HERE\/lib\/citation-state\.sh"/);
  });

  it('⚠️ gh-runs.sh no longer DEFINES citation_state — one copy, not two', () => {
    // The half-landed version of this change is "add the lib, leave the
    // original in place": the source line lands, the inlined definition wins
    // (it is defined after the source), and every arm above stays green while
    // production behaviour is completely unchanged.
    const code = runner
      .split('\n')
      .filter((l) => !l.trimStart().startsWith('#'))
      .join('\n');
    expect(code).not.toMatch(/citation_state\s*\(\)\s*\{/);
  });

  it('gh-runs.sh still CALLS citation_state', () => {
    expect(runner).toMatch(/citation_state\s+"/);
  });

  it('gh-runs.sh parses — a text arm is worthless if the script is broken', () => {
    expect(() => execFileSync('bash', ['-n', RUNNER], { encoding: 'utf8' })).not.toThrow();
  });

  it('⚠️ check-citation.sh still carries ITS supersession rule', () => {
    // The two scripts drifted once. If somebody "simplifies" the other side,
    // they diverge again in the opposite direction and this gate would be
    // silent — it only watches one of the pair.
    const checker = readFileSync(join(REPO_ROOT, 'scripts/check-citation.sh'), 'utf8');
    expect(checker).toMatch(/superseded/);
  });
});
