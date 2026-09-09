// ============================================================================
// GATE — THE CITATION INSTRUMENT CARRIES NO EARLY-EXIT PIPELINE.
// ----------------------------------------------------------------------------
// `check-citation.sh` decides whether a commit may be deployed. It ran
// `set -o pipefail` and had FIVE `printf … | grep -q…` pipelines. `grep -q`
// exits 0 the instant it matches and closes the pipe; `printf` dies of SIGPIPE
// (141); `pipefail` promotes that to the pipeline's status — so a MATCH is
// reported as a MISS.
//
// ⚠️ AND THE HEADLINE FIGURE FROM THE f30 FIX DOES NOT TRANSFER HERE — MEASURED,
// AND THE MEASUREMENT REFUTED THE CLAIM I WAS ABOUT TO MAKE. f30's sweep raced
// 21 times in 54,000 over an EIGHTEEN-line `printf`. This file's array holds
// FOUR short entries, and the same A/B scored **0 false misses in 16,000 for the
// OLD form too** — printf finishes its single write before grep can close the
// pipe. The single-string sites (`printf '%s' "$SHA"`) are smaller still.
//
// So the exposure HERE is not measured to be live, and saying otherwise would be
// carrying a number across a different input size — the defect this repo calls a
// fabricated figure. What justifies the change anyway is narrower and honest:
// the output is byte-identical on ten real inputs, it deletes five subprocess
// forks, and — the actual argument — **`REQUIRED` can grow.** The window scales
// with what `printf` still has to write, so adding a fifth required workflow
// widens it with nothing anywhere to flag that it did.
//
// ⚠️ THE FAILURE DIRECTION WAS CHECKED AT EVERY SITE RATHER THAN ASSUMED, and
// the answer is the reassuring one: all five degrade to a REFUSAL, never to a
// false citation. That is worth stating precisely, because "the deploy gate can
// lie" and "the deploy gate can refuse spuriously" are different claims and only
// the second is true. It is still not acceptable — a spurious refusal at deploy
// time sends the operator to re-derive a SHA that was already right, files a
// REQUIRED run into the EXTRA bucket, and drops it from the tally, manufacturing
// an arithmetic finding out of nothing.
//
// ⚠️ AND THE FIX IS NOT ONE REWRITE. The five sites have THREE different
// semantics — a regex on one string, a CASE-INSENSITIVE regex on one string, and
// whole-line membership in an array. Copying the blob-substring rewrite that was
// correct in the f30 sweep into the `-x` sites here would have WIDENED what
// counts as a required workflow: measured, `''`, `ci`, `a11y`, `secrets`, `scan`
// and `e2` all match a substring test and none of them is a workflow.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL:
//   · any pipeline into grep -q returns          -> the shape block
//   · membership degrades to a substring test    -> the semantics block
//   · the case-insensitive SHA arm goes dead     -> the arms block
//   · pipefail is switched off instead of fixed  -> the shape block
// ============================================================================

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const REPO_ROOT = join(__dirname, '..', '..', '..', '..', '..');
const SCRIPT = join(REPO_ROOT, 'scripts/check-citation.sh');
const BODY = readFileSync(SCRIPT, 'utf8');
/** Comments stripped, or the gate reports its own documentation. */
const CODE = BODY.split('\n').filter((l) => !l.trimStart().startsWith('#')).join('\n');

const PIPE_INTO_GREP_Q = /\|\s*grep\s+-[a-zA-Z]*q/;

/**
 * Drive the REAL helper out of the REAL file — never a local re-implementation,
 * which would witness only itself.
 *
 * ⚠️ EXTRACTED, NOT SOURCED. `source`-ing the script would RUN it: it dies at
 * its own usage check before defining anything useful. So the function's text
 * and the REQUIRED array are lifted verbatim and evaluated together, which
 * means an edit to either in the shipped file changes what these arms measure.
 */
const REQUIRED_LINE = BODY.match(/^REQUIRED=\(.*\)$/m)?.[0] ?? '';
const IN_REQUIRED_FN = BODY.match(/^in_required\(\) \{[\s\S]*?^\}$/m)?.[0] ?? '';

function inRequired(needle: string): boolean {
  expect(REQUIRED_LINE, 'REQUIRED=() not found in the shipped script').not.toBe('');
  expect(IN_REQUIRED_FN, 'in_required() not found in the shipped script').not.toBe('');
  const out = execFileSync(
    'bash',
    ['-c',
     `set -uo pipefail\n${REQUIRED_LINE}\n${IN_REQUIRED_FN}\nin_required "$1" && echo Y || echo N`,
     '_', needle],
    { encoding: 'utf8' },
  );
  return out.trim() === 'Y';
}

describe('⚠️ no early-exit pipeline in the instrument that gates deploys', () => {
  it('the script contains no pipeline into `grep -q`', () => {
    const offenders = CODE.split('\n').filter((l) => PIPE_INTO_GREP_Q.test(l));
    expect(
      offenders,
      'each can report a MATCH as a MISS under pipefail; use `[[ =~ ]]` for a ' +
        'regex on one string and `in_required` for array membership',
    ).toEqual([]);
  });

  it('CONTROL — the check SEES a planted offender in the real file text', () => {
    // A control that never touches a file cannot guard files.
    const planted = `${BODY}\nprintf '%s\\n' "\${REQUIRED[@]}" | grep -qxF "$wf"\n`;
    const offenders = planted
      .split('\n')
      .filter((l) => !l.trimStart().startsWith('#'))
      .filter((l) => PIPE_INTO_GREP_Q.test(l));
    expect(offenders.length).toBeGreaterThan(0);
  });

  it('`pipefail` stays ON — the hazard exists only because it is, and that is right', () => {
    // ⚠️ THE CHEAP "FIX" IS TO TURN IT OFF. `pipefail` is what makes every other
    // pipeline in this file honest; the repair is to stop piping into a command
    // that exits early, not to stop noticing when a pipeline fails.
    expect(BODY).toMatch(/^set -[a-z]*o pipefail/m);
  });

  it('the membership helper exists and is used at both former -x sites', () => {
    expect(BODY).toMatch(/^in_required\(\) \{/m);
    expect(CODE.match(/in_required /g)?.length ?? 0).toBeGreaterThanOrEqual(2);
  });
});

describe('⚠️ membership is EXACT — a substring test would widen the gate', () => {
  const MEMBERS = ['CI', 'e2e', 'a11y-ci', 'secrets-scan'];
  // Every one of these is a substring of a real workflow name, or empty. A
  // blob-substring rewrite matches ALL of them; `grep -xF` matched none.
  const IMPOSTORS = ['', 'C', 'ci', 'a11y', 'secrets', 'scan', 'e2', 'CI '];

  it('every required workflow is a member', () => {
    for (const m of MEMBERS) expect(inRequired(m), `${m} should be required`).toBe(true);
  });

  it('⚠️ AND NO SUBSTRING OF ONE IS — including the EMPTY STRING', () => {
    // The empty string is the sharpest: a run whose workflow name failed to
    // parse would otherwise be admitted as a required workflow.
    for (const s of IMPOSTORS) {
      expect(inRequired(s), `'${s}' must NOT count as a required workflow`).toBe(false);
    }
  });
});

describe('⚠️ the SHA-shape arms stay distinct — the case arm must not go dead', () => {
  function shaVerdict(sha: string): string {
    try {
      execFileSync('bash', [SCRIPT, sha], { encoding: 'utf8', stdio: 'pipe' });
      return 'accepted';
    } catch (e) {
      const out = String((e as { stdout?: string; stderr?: string }).stdout ?? '') +
        String((e as { stderr?: string }).stderr ?? '');
      if (/not all lowercase/.test(out)) return 'case';
      if (/character\(s\)/.test(out)) return 'length';
      return 'other';
    }
  }

  it('40 hex in the WRONG CASE is refused for being the wrong case', () => {
    // `grep -qi` was case-insensitive; bash `=~` is NOT, so this arm only works
    // because the class is spelled `[0-9a-fA-F]`. If someone "simplifies" it to
    // `[0-9a-f]`, the arm goes dead and an uppercase SHA gets the LENGTH message
    // — advice that sends the operator to re-derive a SHA that is already right.
    expect(shaVerdict('6B5F4654973659146206DC034E22DE14229A1447')).toBe('case');
    expect(shaVerdict('6b5F4654973659146206dc034e22De14229a1447')).toBe('case');
  });

  it('and a genuinely wrong shape gets the LENGTH message, not the case one', () => {
    // Non-vacuity: the arm above is not passing because everything says "case".
    expect(shaVerdict('6b5f4654')).toBe('length');
    expect(shaVerdict('zzzz4654973659146206dc034e22de14229a1447')).toBe('length');
  });
});
