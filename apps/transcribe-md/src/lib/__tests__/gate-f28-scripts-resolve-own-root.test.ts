// ============================================================================
// F28 — A GRANTED SCRIPT RESOLVES ITS PATHS FROM ITS OWN LOCATION, NEVER THE CWD.
// ----------------------------------------------------------------------------
// ⚠️ THE FAMILY BIT THREE TIMES BEFORE IT WAS FILED, AND ONLY THE THIRD WAS LOUD:
//
//   1. `git merge --ff-only` ran in a WORKTREE while the report said
//      "tree head == origin/main" — one command from a wrong-commit deploy.
//   2. `npx vitest` ran from the repo root, where the `@/` alias does not
//      resolve — 218 failed / 177 passed against a true 16 / 301.
//   3. `check-citation.sh` returned `127 — No such file or directory`: the cwd
//      had persisted into `apps/transcribe-md`, and the GRANTS ARE RELATIVE.
//
// The third is the LUCKY one. A persisted `cd` that makes a script vanish is a
// loud failure; a persisted `cd` that makes it read a DIFFERENT REAL TREE is a
// confident wrong answer, and this house has already paid for that shape.
//
// ── WHAT THIS GATE WATCHES, STATED AS A SET ────────────────────────────────
// The `scripts/` entry points a session is GRANTED to run by name, read from
// `.claude/settings.json` at run time. It is deliberately NOT a hand-kept list:
// canon says hand-kept lists go stale, and the whole point is that a script
// added to the grant list TOMORROW inherits the invariant without anybody
// remembering this file exists.
//
// ⚠️ THE CENSUS RECONCILES OR THE GATE FAILS. Every granted script sorts into
// exactly one of three named buckets — ANCHORED / NO-REPO-PATHS / VIOLATION —
// and the three must sum to the number of granted scripts that exist on disk.
// A partition that does not add up has an unnamed bucket in it, and the unnamed
// bucket is where the finding lives.
//
// ⚠️ AND THE BEHAVIOURAL ARM DOES NOT TRUST THE STATIC ONE. Reading a script and
// concluding it anchors correctly is an argument. Running it from a foreign cwd
// and watching the answer NOT MOVE is a measurement. Both are here, and the
// second is the one with teeth.
//
// ⚠️ ITS CONTROL IS BUILT, NOT BORROWED — because a control aimed where the
// answer is predetermined is not a control. Pointing the old form at another
// worktree would prove nothing in CI, where only one tree exists. So the control
// mints a THROWAWAY git repository under $TMPDIR: there the OLD form
// (`git rev-parse --show-toplevel`) provably resolves somewhere else, and the
// NEW form (`BASH_SOURCE`) provably does not. That discriminates on this host
// and on a CI runner alike.
//
// ⚠️ IT REAPS ITS OWN TMPDIR. The FOUNDATION loop runs unattended and `shred`
// and `rm` are DENIED to it by design, so a gate that mints a directory per run
// mints scratch the only actor present cannot delete.
//
// ⚠️ HONEST LIMITS, NAMED SO THE GATE IS NOT READ WIDER THAN IT IS:
//   · It watches the GRANTED entry points. A script reached by `source` from one
//     of them is covered only insofar as its caller anchors before sourcing.
//   · The static arm classifies by reading the source. A script that builds a
//     repo-relative path by string arithmetic the regex cannot see would sort as
//     NO-REPO-PATHS. The behavioural arm is what covers the one script whose
//     anchoring actually changed; extending it to all 23 would mean executing
//     every granted script, several of which deploy, migrate or merge.
//   · It says nothing about scripts NOT in the grant list.
// ============================================================================

import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const REPO_ROOT = join(__dirname, '../../../../..');
const SETTINGS = join(REPO_ROOT, '.claude/settings.json');

/** The script whose anchoring F28 actually changed — the behavioural arm's subject. */
const SUBJECT = 'scripts/check-hooks-installed.sh';

let TMP: string;

beforeAll(() => {
  TMP = mkdtempSync(join(tmpdir(), 'f28-root-'));
});

afterAll(() => {
  rmSync(TMP, { recursive: true, force: true });
});

/**
 * Every `bash scripts/…` entry point the session is granted to run BY NAME.
 * Read from the grant file itself so the watched set cannot go stale.
 */
function grantedScripts(): string[] {
  const raw = readFileSync(SETTINGS, 'utf8');
  const out = new Set<string>();
  for (const m of raw.matchAll(/"Bash\(bash (scripts\/[^:)"]+\.sh)/g)) out.add(m[1]);
  return [...out].sort();
}

/**
 * Strip comments, HEREDOC BODIES and echo/printf prose — a path NAMED in advice
 * text is not a path RESOLVED.
 *
 * ⚠️ THE FIRST DRAFT OF THIS FUNCTION WAS WRONG IN BOTH DIRECTIONS AND THE GATE
 * CAUGHT IT ON ITS FIRST RUN, which is the strongest evidence a guard can give
 * about itself. It skipped a line that *started* with `cat <<` but not the
 * heredoc BODY that followed (`check-ingress-tls.sh:112`), and it anchored the
 * echo filter at `^`, so prose inside a compound line survived
 * (`[ -z "$BR" ] && { echo "usage: bash scripts/retire-branch.sh …"; }`).
 * Both produced FALSE POSITIVES — and a gate that cries wolf on prose is a gate
 * somebody switches off.
 */
function codeLines(body: string): string[] {
  const out: string[] = [];
  let heredocTerminator: string | null = null;

  for (const raw of body.split('\n')) {
    const line = raw.trim();

    if (heredocTerminator !== null) {
      if (line === heredocTerminator) heredocTerminator = null;
      continue; // inside a heredoc: prose, never code
    }

    const opens = raw.match(/<<-?\s*'?"?([A-Za-z_][A-Za-z0-9_]*)'?"?/);
    if (opens) {
      heredocTerminator = opens[1];
      continue;
    }

    if (line.length === 0 || line.startsWith('#')) continue;

    // Remove every echo/printf/say argument ANYWHERE on the line, not only at ^.
    const stripped = line.replace(/\b(echo|printf|say)\b[^;)}]*/g, ' ');
    if (stripped.trim().length === 0) continue;
    out.push(stripped);
  }
  return out;
}

/** Does this script anchor itself to its OWN location? */
function anchorsToBashSource(body: string): boolean {
  return /BASH_SOURCE\[0\]/.test(body);
}

/** Does this script resolve any repo-relative path, or cd to a CWD-derived root? */
function resolvesRepoPaths(body: string): boolean {
  return codeLines(body).some(
    (l) =>
      /(^|[=\s"'(])(docs|scripts|apps|packages|infra|prisma)\//.test(l) ||
      /git rev-parse --show-toplevel/.test(l),
  );
}

function bashOut(script: string, cwd: string): { code: number; out: string } {
  try {
    const out = execFileSync('bash', [script], { cwd, encoding: 'utf8', stdio: 'pipe' });
    return { code: 0, out };
  } catch (e) {
    const err = e as { status?: number; stdout?: string; stderr?: string };
    return { code: err.status ?? -1, out: `${err.stdout ?? ''}${err.stderr ?? ''}` };
  }
}

describe('F28 · a granted script resolves its own root', () => {
  // ── NON-VACUITY, FIRST ────────────────────────────────────────────────────
  // A regex that silently matched nothing would make every arm below pass while
  // checking nothing. This is the floor, and it names a known member.
  it('the grant list is READ and is not empty — with a known member named', () => {
    const scripts = grantedScripts();
    expect(scripts.length).toBeGreaterThanOrEqual(15);
    expect(scripts).toContain(SUBJECT);
    expect(scripts).toContain('scripts/deploy-prod.sh');
  });

  // ── THE CENSUS, AND IT RECONCILES ────────────────────────────────────────
  it('every granted script is ANCHORED or touches no repo path — the partition adds up', () => {
    const scripts = grantedScripts();
    const present = scripts.filter((s) => existsSync(join(REPO_ROOT, s)));

    const anchored: string[] = [];
    const noRepoPaths: string[] = [];
    const violations: string[] = [];

    for (const rel of present) {
      const body = readFileSync(join(REPO_ROOT, rel), 'utf8');
      if (anchorsToBashSource(body)) anchored.push(rel);
      else if (!resolvesRepoPaths(body)) noRepoPaths.push(rel);
      else violations.push(rel);
    }

    // The finding, named per file rather than as a count.
    expect(
      violations,
      `these granted scripts resolve a repo path from the CWD instead of from ` +
        `their own location (F28):\n  ${violations.join('\n  ')}`,
    ).toEqual([]);

    // ARITHMETIC THAT DOES NOT RECONCILE IS A FINDING.
    expect(anchored.length + noRepoPaths.length + violations.length).toBe(present.length);
    expect(anchored.length).toBeGreaterThan(0);
    expect(noRepoPaths.length).toBeGreaterThan(0);
  });

  it(`${SUBJECT} anchors to BASH_SOURCE and no longer to the caller's tree`, () => {
    const body = readFileSync(join(REPO_ROOT, SUBJECT), 'utf8');
    expect(anchorsToBashSource(body)).toBe(true);
    // The exact form it used to carry, which is what made it CWD-dependent.
    expect(codeLines(body).some((l) => /cd "\$\(git rev-parse --show-toplevel/.test(l))).toBe(false);
  });

  // ── THE BEHAVIOURAL ARM — RUN IT, DO NOT REASON ABOUT IT ─────────────────
  it('gives the SAME answer from a foreign cwd as from the repo root', () => {
    const abs = join(REPO_ROOT, SUBJECT);
    const fromRoot = bashOut(abs, REPO_ROOT);
    const fromForeign = bashOut(abs, TMP);

    expect(fromForeign.code).toBe(fromRoot.code);
    expect(fromForeign.out).toBe(fromRoot.out);
    // Non-vacuity: it must actually have produced a verdict, not an empty string.
    expect(fromRoot.out).toMatch(/check-hooks-installed/);
  });

  // ⚠️ retire-branch.sh IS COVERED BY THE STATIC ARM ONLY, AND THAT IS A LIMIT
  // RATHER THAN AN OVERSIGHT. Recorded here because the honest version of this
  // gate has to say which half it has.
  //
  // It has NO other behavioural test in the repository — `gate-f14b-merge-push-
  // doors` names it in prose and never drives it, so its 79 green arms say
  // nothing about this change. Checked, not assumed.
  //
  // ⚠️ AND A BEHAVIOURAL ARM WAS WRITTEN HERE, MUTATION-PROVED, AND DELETED
  // BECAUSE IT COULD NOT FAIL. It ran `retire-branch.sh main` from a foreign cwd
  // and asserted the refusal matched the repo-root run. Under MUTATION-M3 —
  // the CWD-derived form restored — it STAYED GREEN. The mechanism:
  //
  //     cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null
  //
  // when git fails, the substitution is empty and `cd ""` SUCCEEDS as a no-op.
  // The trunk-ref refusal is then reached by SHAPE, consulting no tree at all,
  // so both forms answer identically from everywhere. The arm was aimed where
  // the answer was PREDETERMINED — the failure inside the positive-control rule
  // — and a control that cannot come out false is decoration.
  //
  // No safe offline arm discriminates: every tree-dependent path in that script
  // (`git fetch`, `ls-remote`, `merge-base`, `worktree list`) is past a network
  // fetch and needs a real branch. Left as a named gap rather than a green.

  // ── THE CONTROL, BUILT SO IT CANNOT BE PREDETERMINED ─────────────────────
  // In a throwaway git repo the OLD form resolves THERE and the NEW form resolves
  // to the real tree. If this arm ever goes quiet, the control has stopped
  // discriminating and every arm above is worth less than it looks.
  it('CONTROL — the OLD form follows the caller; the NEW form does not', () => {
    const foreignRepo = mkdtempSync(join(TMP, 'repo-'));
    execFileSync('git', ['init', '-q'], { cwd: foreignRepo });

    const oldForm = execFileSync(
      'bash',
      ['-c', 'cd "$(git rev-parse --show-toplevel)" && pwd -P'],
      { cwd: foreignRepo, encoding: 'utf8' },
    ).trim();

    const newForm = execFileSync(
      'bash',
      ['-c', `cd "$(dirname "${join(REPO_ROOT, SUBJECT)}")/.." && pwd -P`],
      { cwd: foreignRepo, encoding: 'utf8' },
    ).trim();

    const realRoot = execFileSync('bash', ['-c', 'pwd -P'], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    }).trim();

    // The old form was dragged away by the caller — this is the defect, reproduced.
    expect(oldForm).not.toBe(realRoot);
    // The new form is immune to the same drag.
    expect(newForm).toBe(realRoot);
  });
});
