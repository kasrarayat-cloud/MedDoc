// ============================================================================
// F10 — a §2.5 declaration is COMMITTABLE BEFORE ITS DEPLOY, and the judgement
//       still covers the exact tree that ships.
// ----------------------------------------------------------------------------
// ⚠️ THE BUG WAS STRUCTURAL, NOT CARELESS. `scripts/deploy-prod.sh` derived the
// declaration path from `git rev-parse --short HEAD` of the deploying tree, and
// this programme's normal cadence moves `main` between a feature merge and its
// deploy — a citation PR, a ledger row, a docs fix. So:
//
//     feature merges as X       ->  you write <date>-X.md
//     canon: nothing reaches `main` outside a PR
//     the PR carrying it merges  ->  HEAD is now Y
//     the gate now wants <date>-Y.md, which does not exist
//
// AND IT DOES NOT CONVERGE: the commit that would CARRY the declaration is
// itself what MOVES HEAD. Session 03 hit it and filed the root cause; session 05
// deployed with a carried declaration `tracked: no` and said so loudly rather
// than pretending otherwise. Ruling #121 set the acceptance criteria.
//
// ── THE THREE CRITERIA, AND WHERE EACH IS PROVED ────────────────────────────
//
//   (1) THE GATE DOES NOT WEAKEN. `present` is untouched on the exact match —
//       #96(b) stands, and #121 names "flip it to strict" as the misreading.
//       The carry-forward door resolves at `strict`, so the only movement is
//       TIGHTER.                                → `mode is present`/`mode is strict`
//
//   (2) THE CIRCULARITY BREAKS. A declaration naming X, committed in the docs
//       PR that becomes Y, is accepted at HEAD=Y — committed BEFORE the act.
//                                               → `the carry-forward is ACCEPTED`
//
//   (3) FALSIFIABILITY DOES NOT NARROW. It cannot name "whatever ships": it
//       refuses a non-ancestor, ANY runtime movement, a fabricated sha, an
//       uncommitted carry-forward, and an ambiguous pair.
//                                               → every `REFUSES` arm below
//
// ── AND IT PROVES BOTH DIRECTIONS, WHICH IS THE HALF THAT GETS SKIPPED ──────
// `retire-branch.sh` passed 9 of 9 REFUSAL tests and then printed a false green
// on the happy path, because refusals were never its broken half. #121 names
// that precedent by hand. So the accept arms here assert the EXIT CODE, the
// RESOLVED PATH and the MODE — not merely "it did not refuse".
//
// ⚠️ AND THE REFUSAL ARMS ARE ONLY MEANINGFUL BECAUSE THE ACCEPT ARMS PASS. A
// resolver that found nothing ever would satisfy every refusal test in this
// file. The accept arms are this gate's positive control, and they are asserted
// first for that reason.
//
// ── WHAT IT DRIVES ─────────────────────────────────────────────────────────
// The REAL `scripts/lib/declaration.sh`, sourced by a real bash, against
// THROWAWAY git repositories under $TMPDIR. Nothing here re-implements the
// logic — a second copy would drift from the first the day either is fixed,
// which is why `declaration.sh` is shared by the deploy and the mutation runner
// in the first place.
//
// ⚠️ IT REAPS ITS OWN TMPDIR. The FOUNDATION loop runs unattended and `shred`
// and `rm` are DENIED to it by design, so a gate that mints a directory per run
// mints scratch the only actor present cannot delete. That is F9's gate's
// lesson, filed against itself after nine leftovers (`1cf669a8`), and it is
// cheaper to copy than to relearn.
//
// ⚠️ HONEST LIMIT, NAMED RATHER THAN IMPLIED: this proves the RESOLVER against
// synthetic histories. It does not deploy anything, and it cannot — a test that
// recreates production containers is not a test. The integration is one line in
// `deploy-prod.sh` (`declaration_resolve` then `declaration_gate "$DECL"
// "$DECLARATION_MODE"`), and the arm below that greps the deploy script for it
// is what stops that wiring being silently reverted.
// ============================================================================

import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const REPO_ROOT = `${__dirname}/../../../../..`;
const LIB = join(REPO_ROOT, 'scripts/lib/declaration.sh');
const DEPLOY = join(REPO_ROOT, 'scripts/deploy-prod.sh');
const DECL_DIR = 'docs/foundation/deploys';

let TMP: string;
let repoSeq = 0;

beforeAll(() => {
  TMP = mkdtempSync(join(tmpdir(), 'f10-decl-'));
});

afterAll(() => {
  // See the header. The loop cannot reap; the gate reaps itself.
  rmSync(TMP, { recursive: true, force: true });
});

function git(cwd: string, ...args: string[]): string {
  return execFileSync('git', args, { cwd, encoding: 'utf8' }).trim();
}

/** A throwaway repo with one initial commit and a deploys dir that already
 *  contains a `README.md` — because the real one does, and a resolver that
 *  choked on a non-sha filename would break on the first real invocation. */
function newRepo(): string {
  const dir = join(TMP, `r${repoSeq++}`);
  mkdirSync(join(dir, DECL_DIR), { recursive: true });
  git(dir, 'init', '-q', '-b', 'main');
  git(dir, 'config', 'user.email', 'f10-gate@example.invalid');
  git(dir, 'config', 'user.name', 'F10 gate');
  git(dir, 'config', 'commit.gpgsign', 'false');
  write(dir, `${DECL_DIR}/README.md`, '# deploy declarations\n');
  commit(dir, 'initial');
  return dir;
}

function write(dir: string, rel: string, body: string): void {
  mkdirSync(join(dir, rel, '..'), { recursive: true });
  writeFileSync(join(dir, rel), body);
}

function commit(dir: string, msg: string, allowEmpty = false): string {
  git(dir, 'add', '-A');
  const args = ['commit', '-q', '-m', msg];
  if (allowEmpty) args.push('--allow-empty');
  git(dir, ...args);
  return git(dir, 'rev-parse', 'HEAD');
}

/** A declaration file naming `sha`. Content is irrelevant to the resolver —
 *  the NAME is the claim it verifies — but a realistic body keeps the arms
 *  honest about what the file is. */
function declFor(sha: string): string {
  return `${DECL_DIR}/20260817-${sha.slice(0, 8)}.md`;
}

type Run = { code: number; out: string };

function bash(script: string, cwd: string): Run {
  try {
    const out = execFileSync('bash', ['-c', script], {
      cwd,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    return { code: 0, out };
  } catch (e) {
    const err = e as { status?: number; stdout?: string; stderr?: string };
    return { code: err.status ?? -1, out: `${err.stdout ?? ''}${err.stderr ?? ''}` };
  }
}

// ⚠️ THE FLAGS ARE PART OF THE UNIVERSE, AND THIS HARNESS GOT THEM WRONG FIRST.
// `scripts/deploy-prod.sh:50` runs `set -euo pipefail`. The first version of
// these helpers used a bare `set -u`, which is a MILDER shell than the one the
// code actually runs in — and the resolver's accept path contains two pipelines
// (`… | wc -l`, `… | grep -Ecv …`) where `pipefail` is exactly what would bite:
// `grep -c` exits 1 when the count is zero, which under `pipefail` propagates
// and under `set -e` would abort. It is caught by `|| true`, and that is a claim
// this file has to TEST rather than assert.
//
// "A test that defaults a flag OFF while production runs it ON is testing the
// rollback" — the same rule, one layer down from env vars.
const PROD_FLAGS = 'set -euo pipefail';

/** Resolution ONLY — what `deploy-prod.sh` calls first.
 *  ⚠️ `|| rc=$?` rather than a bare call: under `set -e` a non-zero return
 *  aborts the script before the outputs are echoed, which would make every
 *  refusal arm read as "bash died" instead of "the resolver refused". */
function resolve(dir: string): Run & { path: string; mode: string } {
  const r = bash(
    `${PROD_FLAGS}
     . "${LIB}"
     rc=0
     declaration_resolve "${DECL_DIR}" || rc=$?
     echo "F10_PATH=\${DECLARATION_PATH:-}"
     echo "F10_MODE=\${DECLARATION_MODE:-}"
     exit $rc`,
    dir,
  );
  const path = /F10_PATH=(.*)/.exec(r.out)?.[1]?.trim() ?? '';
  const mode = /F10_MODE=(.*)/.exec(r.out)?.[1]?.trim() ?? '';
  return { ...r, path, mode };
}

/** Resolution THEN the gate — the full sequence the deploy performs, so an arm
 *  cannot pass by resolving something the gate would then throw out. */
function resolveAndGate(dir: string): Run {
  return bash(
    `${PROD_FLAGS}
     . "${LIB}"
     rc=0
     declaration_resolve "${DECL_DIR}" || rc=$?
     [ "$rc" = "0" ] || exit $rc
     declaration_gate "$DECLARATION_PATH" "$DECLARATION_MODE" "deploy declaration" || exit 1
     echo "F10_GATE=passed"`,
    dir,
  );
}

// ────────────────────────────────────────────────────────────────────────────
// THE POSITIVE CONTROLS. Asserted first: every refusal arm below is vacuous if
// the resolver cannot accept anything at all.
// ────────────────────────────────────────────────────────────────────────────
describe('F10 · the accept direction (positive control)', () => {
  it('takes the EXACT match and leaves it at `present` — pre-F10 behaviour, ruling #96(b) intact', () => {
    const dir = newRepo();
    const head = git(dir, 'rev-parse', 'HEAD');
    write(dir, declFor(head), '# baseline: nothing but the image ids\n');

    const r = resolve(dir);
    expect(r.code).toBe(0);
    expect(r.path).toBe(declFor(head));
    // ⚠️ THE MODE IS THE CRITERION-(1) ASSERTION. #121 names flipping this to
    // `strict` as the misreading of "the gate does not weaken", so an exact
    // match that silently became strict would refuse every same-PR declaration
    // — the habit #96(b) exists to protect.
    expect(r.mode).toBe('present');
    expect(r.out).toContain('EXACT');
  });

  it('ACCEPTS the carry-forward: a declaration naming X, committed, deployed at Y — the circularity broken', () => {
    const dir = newRepo();
    // the feature merge
    write(dir, 'apps/transcribe-md/src/feature.ts', 'export const x = 1;\n');
    const X = commit(dir, 'feat: the change being declared');
    // the docs PR that carries the declaration — this is what moved HEAD, and
    // under the old scheme it invalidated the filename it was creating.
    write(dir, declFor(X), '# baseline / must change / must not change\n');
    const Y = commit(dir, 'docs: the §2.5 declaration for X');

    expect(git(dir, 'rev-parse', 'HEAD')).toBe(Y);

    const r = resolve(dir);
    expect(r.code).toBe(0);
    expect(r.path).toBe(declFor(X));
    // ⚠️ CRITERION (1), THE OTHER HALF: the new door is the STRICTER one. A
    // carry-forward means a commit existed to ride, so the declaration must be
    // committed — which is exactly what the interim exception could not require.
    expect(r.mode).toBe('strict');
    expect(r.out).toContain('CARRY-FORWARD');
    // the non-vacuity control, printed by the script itself rather than by the
    // operator's habit: an empty runtime diff over an EMPTY range proves nothing.
    expect(r.out).toContain('the range is NON-EMPTY');

    // and it survives the gate it is handed to — `strict` is satisfiable here
    // precisely because the declaration was committed before the deploy.
    const g = resolveAndGate(dir);
    expect(g.code).toBe(0);
    expect(g.out).toContain('F10_GATE=passed');
  });

  it('names the IDENTICAL-TREES case rather than reporting a measurement over an empty set', () => {
    const dir = newRepo();
    write(dir, 'apps/transcribe-md/src/feature.ts', 'export const x = 1;\n');
    const X = commit(dir, 'feat: the change');
    commit(dir, 'chore: an empty commit', true);
    // untracked on purpose — this is the shape that reaches total === 0, and it
    // is also the shape ruling #121's interim exception permitted.
    write(dir, declFor(X), '# carried forward\n');

    const r = resolve(dir);
    expect(r.code).toBe(0);
    expect(r.out).toContain('IDENTICAL TREES');
    // ⚠️ AND IT IS STILL REFUSED DOWNSTREAM, because `strict` wants it committed.
    // Resolution and admission are different questions and this arm holds both.
    const g = resolveAndGate(dir);
    expect(g.code).toBe(1);
    expect(g.out).toContain('NOT COMMITTED');
  });
});

// ────────────────────────────────────────────────────────────────────────────
// THE REFUSAL DIRECTION — criterion (3). A scheme that resolves to the deployed
// tree BY CONSTRUCTION cannot come out false, so each of these is a way it can.
// ────────────────────────────────────────────────────────────────────────────
describe('F10 · the refuse direction (criterion 3 — it can come out false)', () => {
  it('REFUSES when no declaration exists at all, and names the path it wanted', () => {
    const dir = newRepo();
    const r = resolve(dir);
    expect(r.code).toBe(1);
    expect(r.path).toBe('');
    expect(r.out).toContain('no delta declaration covers the tree you are shipping');
  });

  it('REFUSES a declaration naming a commit that is NOT AN ANCESTOR — another branch is another program', () => {
    const dir = newRepo();
    const base = git(dir, 'rev-parse', 'HEAD');
    git(dir, 'checkout', '-q', '-b', 'other');
    write(dir, 'docs/side.md', 'side\n');
    const O = commit(dir, 'docs: on the other branch');
    git(dir, 'checkout', '-q', 'main');
    expect(git(dir, 'rev-parse', 'HEAD')).toBe(base);

    // the declaration names O, which main has never contained
    write(dir, declFor(O), '# a declaration about a tree that is not being shipped\n');
    commit(dir, 'docs: land a declaration naming a foreign commit');

    const r = resolve(dir);
    expect(r.code).toBe(1);
    expect(r.path).toBe('');
  });

  it('REFUSES when a RUNTIME file moved between the declared commit and HEAD', () => {
    const dir = newRepo();
    write(dir, 'apps/transcribe-md/src/feature.ts', 'export const x = 1;\n');
    const X = commit(dir, 'feat: the change being declared');
    write(dir, declFor(X), '# declared\n');
    commit(dir, 'docs: the declaration');
    // ⚠️ THE UNDECLARED CHANGE. This is the whole point of criterion (1): the
    // judgement must cover the EXACT tree shipped, and this tree is not the one
    // the declaration was written about.
    write(dir, 'apps/transcribe-md/src/sneaky.ts', 'export const y = 2;\n');
    commit(dir, 'feat: something nobody declared');

    const r = resolve(dir);
    expect(r.code).toBe(1);
    expect(r.out).toContain('git diff --name-only');
  });

  it('REFUSES when a SCRIPT moved — scripts run from the tree, so they are runtime here', () => {
    const dir = newRepo();
    write(dir, 'apps/transcribe-md/src/feature.ts', 'export const x = 1;\n');
    const X = commit(dir, 'feat: the change');
    write(dir, declFor(X), '# declared\n');
    commit(dir, 'docs: the declaration');
    // ⚠️ NOT HYPOTHETICAL: `deploy-prod.sh` and everything it sources are read
    // off the working tree at deploy time, which is why F9 was "effective for
    // the NEXT deploy" the moment it merged. A changed script IS a changed
    // deploy, and the non-runtime allowlist is fail-closed for exactly this.
    write(dir, 'scripts/deploy-prod.sh', '#!/usr/bin/env bash\n# changed\n');
    commit(dir, 'chore: touch a script');

    const r = resolve(dir);
    expect(r.code).toBe(1);
  });

  it('REFUSES a FABRICATED sha in the filename — hex-looking is not a commit', () => {
    const dir = newRepo();
    write(dir, 'apps/transcribe-md/src/feature.ts', 'export const x = 1;\n');
    commit(dir, 'feat: the change');
    // 16 hex characters, correctly shaped, and no such object exists. This is
    // the "full-looking is not full" trap that cost a batch citation on
    // 2026-08-16, arriving at the declaration gate instead of at `gh`.
    write(dir, `${DECL_DIR}/20260817-abcdef0123456789.md`, '# names nothing\n');
    commit(dir, 'docs: a declaration naming a commit that does not exist');

    const r = resolve(dir);
    expect(r.code).toBe(1);
    expect(r.path).toBe('');
  });

  it('REFUSES an UNCOMMITTED carry-forward — the record must be able to prove the ORDER', () => {
    const dir = newRepo();
    write(dir, 'apps/transcribe-md/src/feature.ts', 'export const x = 1;\n');
    const X = commit(dir, 'feat: the change');
    write(dir, 'docs/unrelated.md', 'a citation row\n');
    commit(dir, 'docs: main moved for an unrelated reason');
    // written to the tree and never committed — legal under #121's INTERIM
    // posture, and the thing F10 exists to stop being necessary.
    write(dir, declFor(X), '# carried forward, uncommitted\n');

    const r = resolve(dir);
    expect(r.code).toBe(0);
    expect(r.mode).toBe('strict');

    const g = resolveAndGate(dir);
    expect(g.code).toBe(1);
    expect(g.out).toContain('NOT COMMITTED');
  });

  it('REFUSES two declarations naming THIS commit — the date prefix is decoration, not identity', () => {
    // ⚠️ THE PRE-F10 CODE COULD NOT REACH THIS, which is why it needs its own
    // arm: the old name was DERIVED including today's date, so only one file
    // could ever match. Resolution is by SHA now, so a deploy that crosses
    // midnight and gets a second declaration written produces two exact
    // matches — and silently taking the last would be precisely the defect the
    // carry-forward tie already refuses.
    const dir = newRepo();
    const head = git(dir, 'rev-parse', 'HEAD');
    write(dir, `${DECL_DIR}/20260816-${head.slice(0, 8)}.md`, '# written before midnight\n');
    write(dir, `${DECL_DIR}/20260817-${head.slice(0, 8)}.md`, '# written after midnight\n');

    const r = resolve(dir);
    expect(r.code).toBe(2);
    expect(r.path).toBe('');
    expect(r.out).toContain('name THIS commit');
  });

  it('REFUSES an AMBIGUOUS pair — two declarations equally near cannot both be about this deploy', () => {
    const dir = newRepo();
    const base = git(dir, 'rev-parse', 'HEAD');
    write(dir, 'docs/p.md', 'p\n');
    const P = commit(dir, 'docs: P');
    git(dir, 'checkout', '-q', '-b', 'side', base);
    write(dir, 'docs/q.md', 'q\n');
    const Q = commit(dir, 'docs: Q');
    git(dir, 'checkout', '-q', 'main');
    git(dir, 'merge', '-q', '--no-ff', '-m', 'merge side', 'side');

    write(dir, declFor(P), '# about P\n');
    write(dir, declFor(Q), '# about Q\n');

    const r = resolve(dir);
    // ⚠️ EXIT 2, NOT 1 — "I cannot tell" is a different claim from "there is
    // none", the same distinction `gh-runs.sh` and `check-citation.sh` draw.
    expect(r.code).toBe(2);
    expect(r.path).toBe('');
    expect(r.out).toContain('equally near');
  });
});

// ────────────────────────────────────────────────────────────────────────────
// THE PRODUCTION UNIVERSE. Every arm above runs on a SYNTHETIC repository with
// two or three commits and one declaration. That is the right shape for proving
// the logic and it is not the shape the resolver actually meets: the real
// directory holds ~37 files including a `README.md` whose name carries no sha,
// eight-character abbreviations, and a history thousands of commits deep.
//
// ⚠️ A WELL-CHOSEN FIXTURE DISGUISES A WRONG UNIVERSE. This arm is the cheap
// insurance against that — it runs the SAME library against the REAL repo.
// ────────────────────────────────────────────────────────────────────────────
describe('F10 · against the real declaration set', () => {
  it('survives contact with the real directory and answers coherently', () => {
    const r = resolve(REPO_ROOT);

    // ⚠️ IT DELIBERATELY DOES NOT ASSERT *WHICH* ANSWER. The right answer here
    // changes every time `main` moves, and an arm pinned to today's value would
    // be a tripwire on the calendar rather than on the code. What is invariant
    // is that the resolver terminates, classifies, and pairs its outputs.
    expect([0, 1, 2]).toContain(r.code);

    // the non-vacuity control: a resolver that silently scanned NOTHING would
    // also "answer coherently", and would refuse everything forever.
    const seen = execFileSync('bash', ['-c', `ls ${REPO_ROOT}/${DECL_DIR}/*.md | wc -l`], {
      encoding: 'utf8',
    }).trim();
    expect(Number(seen)).toBeGreaterThan(10);

    // path and mode move together or not at all — a resolved path with no mode
    // would reach `declaration_gate` as an empty second argument, and the gate's
    // `${2:?}` would abort a deploy with a shell error instead of a reason.
    if (r.code === 0) {
      expect(r.path).not.toBe('');
      expect(['present', 'strict']).toContain(r.mode);
    } else {
      expect(r.path).toBe('');
      expect(r.mode).toBe('');
    }
  });

  it('is not confused by `README.md`, which names no sha', () => {
    // the real directory contains one, and a resolver that treated `README` as
    // an abbreviation would have died on the first real invocation.
    const readme = join(REPO_ROOT, DECL_DIR, 'README.md');
    expect(readFileSync(readme, 'utf8').length).toBeGreaterThan(0);
    expect(resolve(REPO_ROOT).code).not.toBe(-1); // -1 is "bash itself died"
  });
});

// ────────────────────────────────────────────────────────────────────────────
// THE WIRING. The logic above is worth nothing if `deploy-prod.sh` stops
// calling it, and a revert of one line would be invisible to every arm above.
// ────────────────────────────────────────────────────────────────────────────
describe('F10 · the deploy actually uses it', () => {
  const deploy = () => readFileSync(DEPLOY, 'utf8');

  it('calls declaration_resolve and hands its OUTPUT to the gate', () => {
    const src = deploy();
    expect(src).toContain('declaration_resolve "$DECL_DIR"');
    expect(src).toContain('DECL="$DECLARATION_PATH"');
    expect(src).toContain('declaration_gate "$DECL" "$DECLARATION_MODE"');
  });

  it('no longer derives the declaration path from the deploying HEAD — the circular line is GONE', () => {
    // ⚠️ THE REGRESSION THIS WATCHES FOR IS A ONE-LINE REVERT, and it would
    // reintroduce F10 in full while every behavioural arm above stayed green,
    // because the library would still be correct and simply not consulted.
    expect(deploy()).not.toContain('DECL="$DECL_DIR/$(date -u +%Y%m%d)-${DEPLOY_SHA}.md"');
  });

  it('keeps the non-runtime allowlist FAIL-CLOSED — an allowlist, never a denylist', () => {
    // If this ever becomes a denylist, everything not named becomes non-runtime
    // and a carry-forward would sail past real code changes. The shape is the
    // guarantee, so the shape is asserted.
    const lib = readFileSync(LIB, 'utf8');
    expect(lib).toContain("DECLARATION_NONRUNTIME_RE='^(docs/|[^/]+\\.md$)'");
  });
});
