// ============================================================================
// §2.5 ROWS AT PR-OPEN — THE GATE FOR A RULE THAT DID NOT WORK TWICE.
// ----------------------------------------------------------------------------
// A deployer can measure what a change TOUCHES. Only its author can say what it
// is SUPPOSED to do, and therefore what would be a FINDING. Ruling #184 makes a
// passenger without rows a finding rather than a pass; the standing rule puts
// those rows at PR-OPEN time.
//
// ⚠️ MEASURED TWICE, AND THE SECOND WAS WORSE THAN THE FIRST:
//     b54a3b3a    8 passengers,  0 with rows
//     832f8e81   16 passengers,  1 with rows
// The rule was written after the first and had not changed behaviour by the
// second. One of the unrowed passengers was an IRREVERSIBLE migration —
// `ALTER TYPE … ADD VALUE`, which Postgres cannot undo — judged only by rows
// the DEPLOYING lane derived.
//
// ⚠️ AND THE GATE REFUSED ITS OWN PR, WHICH IS ITS BEST FIRST APPLICATION.
// A gate whose author is exempt is not a gate.
// ============================================================================

import { execFileSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const REPO = join(__dirname, '../../../../..');
const SCRIPT = join(REPO, 'scripts/check-pr-rows-file.sh');
const WORKFLOW = join(REPO, '.github/workflows/test.yml');
const LIB = join(REPO, 'scripts/lib/rows.sh');

describe('§2.5 rows-at-PR-open gate', () => {
  it('the script exists and is EXECUTABLE IN THE INDEX', () => {
    // ⚠️ `core.fileMode` is false in this repo, so `chmod +x` succeeds on disk
    // and the file still enters the index 100644 — a hook or gate committed
    // INERT, with nothing anywhere saying so. The mode must be read from git.
    expect(existsSync(SCRIPT)).toBe(true);
    const { execFileSync } = require('node:child_process') as typeof import('node:child_process');
    const mode = execFileSync('git', ['ls-files', '-s', 'scripts/check-pr-rows-file.sh'], {
      cwd: REPO, encoding: 'utf8',
    }).trim().split(' ')[0];
    expect(mode).toBe('100755');
  });

  it('⚠️ IT IS ANCHORED TO ITS OWN LOCATION, NEVER THE CWD — F28', () => {
    // The family that has bitten this house three times: a persisted `cd` makes
    // a granted script read a DIFFERENT REAL TREE, which is a confident wrong
    // answer rather than a loud failure.
    const body = readFileSync(SCRIPT, 'utf8');
    expect(body).toMatch(/BASH_SOURCE\[0\]/);
  });

  it('⚠️ IT SOURCES THE DEPLOY GATE\'S RUNTIME REGEX, it does not define a second', () => {
    // Two definitions of "runtime" drift the day either is fixed, and what
    // drifts decides whether a change needs rows at all. The first version of
    // this script COPIED the regex — hours after "one normaliser, two callers"
    // was recorded as canon from a defect of exactly this shape. This arm
    // caught it.
    const body = readFileSync(SCRIPT, 'utf8');
    expect(body).toContain('DECLARATION_NONRUNTIME_RE');
    expect(body, 'it must not carry its own literal').not.toMatch(/NONRUNTIME_RE='\^\(/);
    // and the shared definition must still exist where it is sourced from
    const lib = readFileSync(join(REPO, 'scripts/lib/declaration.sh'), 'utf8');
    expect(lib).toMatch(/DECLARATION_NONRUNTIME_RE=/);
  });

  it('⚠️ CANNOT-TELL IS NOT A PASS — every early bail exits 2', () => {
    // A broken instrument must never read as a pass. Measured on CODE lines
    // only: the first version of this arm scanned comments too and matched the
    // string "exit 127" inside a docblock — a probe reading its own prose.
    const body = readFileSync(SCRIPT, 'utf8');
    const head = body.slice(0, body.indexOf('CHANGED='));
    const code = head.split('\n').filter((l) => !/^\s*#/.test(l)).join('\n');
    const exits = [...code.matchAll(/exit (\d)/g)].map((m) => m[1]);
    expect(exits.length, 'the head must have bail-outs to check').toBeGreaterThan(2);
    expect(exits.every((e) => e === '2')).toBe(true);
  });

  it('CI runs it on pull requests, and NOT short-circuited', () => {
    const wf = readFileSync(WORKFLOW, 'utf8');
    expect(wf).toContain('check-pr-rows-file.sh');
    const line = wf.split('\n').find((l) => l.includes('check-pr-rows-file.sh'));
    expect(line).toBeDefined();
    // it must actually RUN — not be commented out or `|| true`-d into silence
    expect(line!).not.toMatch(/^\s*#/);
    expect(line!).not.toMatch(/\|\|\s*true/);
  });

  it('⚠️ THIS PR CARRIES ITS OWN ROWS — the gate is not exempt from itself', () => {
    // The number is this PR's real one, claimed from the opened PR rather than
    // guessed. The earlier draft of this branch hardcoded `PR-1008.md`, which
    // names ANOTHER LANE'S PR — see `scripts/lib/rows.sh` for why that would
    // have exempted the real #1008 from this gate forever.
    expect(existsSync(join(REPO, 'docs/foundation/deploys/rows/PR-1022.md'))).toBe(true);
  });

  it('⚠️ IT SOURCES THE ROWS-IDENTITY LIB, it does not inline a second copy', () => {
    const body = readFileSync(SCRIPT, 'utf8');
    expect(body).toContain('scripts/lib/rows.sh');
    expect(body).toContain('rows_file_matches_pr "$PR_NUMBER"');
    expect(existsSync(LIB)).toBe(true);
  });
});

// ============================================================================
// ⚠️ THE ROWS FILE MUST NAME **THIS** PR — driven, not asserted about.
//
// This block runs the real shell function. It is a separate lib precisely so
// these arms need no git range, no merge-base and no network: the one decision
// a future edit could quietly widen is a pure function over strings.
//
// WHAT WOULD MAKE THIS BLOCK FAIL, stated first:
//   · `rows_file_matches_pr` accepts a rows file naming another PR  -> the
//     mismatch arm, which is the shipped defect it exists to prevent
//   · it answers TRUE when the PR number is unknown                 -> the
//     fail-closed arm
//   · the path grammar loosens to match a nested or suffixed name   -> the
//     grammar arm
// ============================================================================
function matches(pr: string, ...paths: string[]): boolean {
  const args = [pr, ...paths].map((a) => `'${a.replace(/'/g, `'\\''`)}'`).join(' ');
  const out = execFileSync(
    'bash',
    ['-c', `. ${JSON.stringify(LIB)}; if rows_file_matches_pr ${args}; then echo YES; else echo NO; fi`],
    { encoding: 'utf8' },
  ).trim();
  expect(['YES', 'NO'], `unexpected output: ${out}`).toContain(out);
  return out === 'YES';
}

const ROWS = (n: string) => `docs/foundation/deploys/rows/PR-${n}.md`;

describe('rows-file identity — a rows file is bound to a CHANGE', () => {
  it('⚠️ NON-VACUITY CONTROL — the matching number is ACCEPTED', () => {
    expect(matches('1021', ROWS('1021'))).toBe(true);
    expect(matches('1021', 'apps/x.ts', ROWS('1021'), 'scripts/y.sh')).toBe(true);
  });

  it('⚠️ A ROWS FILE NAMING ANOTHER PR IS REFUSED — the shipped defect', () => {
    // The gate's own branch carried `PR-1008.md` describing the gate, while
    // #1008 is another lane's `fix/citation-sigpipe`. Accepting it would have
    // passed this PR on somebody else's artifact AND exempted the real #1008
    // forever, on rows its author never wrote.
    expect(matches('1021', ROWS('1008'))).toBe(false);
    expect(matches('1021', ROWS('1008'), ROWS('999'))).toBe(false);
    // …and it is still accepted when the right one is ALSO present.
    expect(matches('1021', ROWS('1008'), ROWS('1021'))).toBe(true);
  });

  it('⚠️ AN UNKNOWN PR NUMBER IS NOT A PASS — fail-closed', () => {
    expect(matches('', ROWS('1021'))).toBe(false);
    expect(matches('abc', ROWS('abc'))).toBe(false);
    expect(matches('10 21', ROWS('1021'))).toBe(false);
  });

  it('⚠️ THE PATH GRAMMAR IS EXACT — no nesting, no suffix, no prefix', () => {
    expect(matches('1021', 'docs/foundation/deploys/rows/sub/PR-1021.md')).toBe(false);
    expect(matches('1021', 'docs/foundation/deploys/rows/PR-1021-draft.md')).toBe(false);
    expect(matches('1021', 'docs/foundation/deploys/rows/PR-1021.markdown')).toBe(false);
    expect(matches('1021', 'docs/deploy-reports/PR-1021.md')).toBe(false);
    expect(matches('1021', 'PR-1021.md')).toBe(false);
    // ⚠️ and a LONGER number that merely starts with it — the substring trap
    expect(matches('102', ROWS('1021'))).toBe(false);
    expect(matches('1021', ROWS('10210'))).toBe(false);
  });

  it('no paths at all is refused, whatever the number', () => {
    expect(matches('1021')).toBe(false);
  });
});
