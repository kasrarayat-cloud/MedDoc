// ============================================================================
// F22 — A DEPLOY REFUSES A COMMIT ITS OWN GATE HAS NOT SEEN.
// ----------------------------------------------------------------------------
// ⚠️ THE INCIDENT, MEASURED AND OWNER-RULED 2026-08-20:
//
//     06:14:42Z   `e2e` created on 7c42d2d7
//     06:15:13Z   `secrets-scan` finishes — THE ONLY CHECK THAT HAD
//     06:15:17Z   deploy-prod.sh STARTS
//     06:52:02Z   `e2e` finishes
//
// All four passed in the end, so nothing unverified survives in production.
// That is luck wearing a process's clothes: the deploy was taken on evidence
// that did not yet exist, and a red `e2e` would have found the tree already live
// for thirty-seven minutes.
//
// ── WHAT THIS GATE DRIVES ───────────────────────────────────────────────────
// The REAL `scripts/lib/citation-gate.sh`, sourced by a real bash, in throwaway
// trees under $TMPDIR. Nothing here re-implements the mapping — a second copy
// drifts from the first the day either is fixed.
//
// The ONE thing that is stubbed is `scripts/gh-runs.sh`, and it is stubbed
// because it is the boundary: its job is to answer "what ran on this SHA?" and
// it is already guarded by its own refusals (short sha, fabricated sha, zero
// runs, dead API, truncated payload). What is unproven, and what this file
// proves, is that the DEPLOY maps its four answers onto deploy/refuse correctly
// and that the refusal actually stops the deploy.
//
// ⚠️ THE ACCEPT ARM COMES FIRST AND IT IS THE POINT. A gate that refused
// everything would pass every refusal arm below and be strictly worse than no
// gate — `retire-branch.sh` passed 9 of 9 refusal tests and then printed a false
// green on the one path that mattered. "PROVE IT IN BOTH DIRECTIONS, and the
// green half is the one usually skipped" is the ruling's own wording.
//
// ⚠️ AND THE MUTATIONS IT IS PROVED AGAINST ARE THE *PARTIAL* ONES. Deleting the
// whole gate is the tidy case nobody ships. The versions a tired session
// actually lands are: the lib added and never called; called and its return
// value ignored; called with the SHORT sha (which matches nothing on the runs
// routes, silently); or called after the build has already happened. Each of
// those has an arm in `THE WIRING` below, because every one of them leaves the
// lib itself perfect and all of its own arms green.
//
// ⚠️ IT REAPS ITS OWN TMPDIR. The FOUNDATION loop runs unattended and `shred`
// and `rm` are DENIED to it by design, so a gate that mints a directory per run
// mints scratch the only actor present cannot delete.
//
// ⚠️ HONEST LIMITS, NAMED RATHER THAN IMPLIED:
//   · This proves the MAPPING and the WIRING. It does not deploy anything, and
//     it cannot — a test that recreates production containers is not a test.
//   · It does not re-prove `gh-runs.sh`'s own refusals. Those are that file's
//     product and are asserted where they live.
//   · The wiring arms read `deploy-prod.sh` as TEXT. A text arm is defeated by
//     a rename, which is why `PARSES` is asserted too: a deploy script that does
//     not parse would leave every text arm green while nothing could ship.
// ============================================================================

import { execFileSync } from 'node:child_process';
import { copyFileSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const REPO_ROOT = `${__dirname}/../../../../..`;
const REAL_LIB_DIR = join(REPO_ROOT, 'scripts/lib');
const DEPLOY = join(REPO_ROOT, 'scripts/deploy-prod.sh');
const LIB = join(REAL_LIB_DIR, 'citation-gate.sh');

/** A real, full-length sha. Read from this repository, never built — a
 *  40-hex string that was PADDED or remembered looks full and is not. */
const SHA = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: REPO_ROOT, encoding: 'utf8' }).trim();

let TMP: string;
let seq = 0;

beforeAll(() => {
  TMP = mkdtempSync(join(tmpdir(), 'f21-citation-'));
});

afterAll(() => {
  rmSync(TMP, { recursive: true, force: true });
});

interface TreeOpts {
  /** exit code the stubbed `gh-runs.sh` returns for `cited` / `wait` */
  decide?: number;
  /** exit code the stubbed `gh-runs.sh` returns for `status` */
  statusExit?: number;
  /** omit `scripts/gh-runs.sh` entirely */
  omitRunner?: boolean;
  /** omit `scripts/lib/inflight.sh` — the shared declaration validator */
  omitInflight?: boolean;
}

/** A throwaway `scripts/` tree: the REAL libs, plus a stub gh-runs.sh whose
 *  answers this test controls. */
function tree(opts: TreeOpts = {}): string {
  const root = join(TMP, `t${seq++}`);
  const libDir = join(root, 'scripts/lib');
  mkdirSync(libDir, { recursive: true });

  for (const f of readdirSync(REAL_LIB_DIR)) {
    if (!f.endsWith('.sh')) continue;
    if (opts.omitInflight && f === 'inflight.sh') continue;
    copyFileSync(join(REAL_LIB_DIR, f), join(libDir, f));
  }

  if (!opts.omitRunner) {
    const decide = opts.decide ?? 0;
    const statusExit = opts.statusExit ?? 0;
    writeFileSync(
      join(root, 'scripts/gh-runs.sh'),
      [
        '#!/usr/bin/env bash',
        'cmd="${1:-}"; sha="${2:-}"',
        'case "$cmd" in',
        `  status) printf '  CI: completed success\\n  e2e: completed success\\n'; exit ${statusExit} ;;`,
        `  cited|wait) echo "STUB $cmd $sha"; exit ${decide} ;;`,
        'esac',
        'echo "STUB: unknown command $cmd" >&2; exit 2',
        '',
      ].join('\n'),
      { mode: 0o755 },
    );
  }
  return root;
}

interface Probe {
  rc: number;
  out: string;
}

/** Sources the REAL library from the throwaway tree and calls the REAL
 *  function, exactly as `deploy-prod.sh` does. */
function probe(root: string, mode = 'refuse', override = ''): Probe {
  const script = `
set -uo pipefail
. ${JSON.stringify(join(root, 'scripts/lib/citation-gate.sh'))}
citation_gate ${JSON.stringify(SHA)} ${JSON.stringify(mode)} ${JSON.stringify(override)}
printf 'RC=%s\\n' "$?"
`;
  let raw: string;
  try {
    raw = execFileSync('bash', ['-c', script], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  } catch (e) {
    const err = e as { stdout?: string; stderr?: string };
    throw new Error(
      `bash aborted — the library did not merely return non-zero, it DIED. ` +
        `That is the set -u class F14-a paid for.\nstdout: ${err.stdout}\nstderr: ${err.stderr}`,
    );
  }
  const m = /RC=(\d+)/.exec(raw);
  if (!m) throw new Error(`no RC line in output:\n${raw}`);
  return { rc: Number(m[1]), out: raw };
}

// ───────────────────────────────────────────────────────────────────────────
// THE GREEN HALF FIRST. A gate that refuses everything passes every arm below.
// ───────────────────────────────────────────────────────────────────────────
describe('F22 — a FULLY CITED commit still deploys (the positive control)', () => {
  it('returns 0 when gh-runs.sh says cited', () => {
    const p = probe(tree({ decide: 0 }));
    expect(p.rc).toBe(0);
    expect(p.out).toContain('CITED');
  });

  it('returns 0 in WAIT mode too, and it is the wait subcommand that is called', () => {
    const p = probe(tree({ decide: 0 }), 'wait');
    expect(p.rc).toBe(0);
    // The stub echoes which subcommand it received: `wait`, not `cited`.
    expect(p.out).toContain('STUB wait ');
    expect(p.out).not.toContain('STUB cited ');
  });

  it('the default mode calls `cited`, not `wait` — a deploy does not hang by default', () => {
    const p = probe(tree({ decide: 0 }), 'refuse');
    expect(p.out).toContain('STUB cited ');
    expect(p.out).not.toContain('STUB wait ');
  });

  it('passes the FULL 40-character sha through to the instrument', () => {
    const p = probe(tree({ decide: 0 }));
    expect(SHA).toHaveLength(40);
    expect(p.out).toContain(SHA);
  });

  it('records the per-run listing, so a citation in the log is not a bare claim', () => {
    const p = probe(tree({ decide: 0 }));
    expect(p.out).toContain('CI: completed success');
    expect(p.out).toContain('e2e: completed success');
  });

  it('⚠️ a FAILED listing does not flip a verdict already taken', () => {
    // The listing is descriptive and runs AFTER the decision. If it could turn
    // a green into a refusal, a flaky read would block a legitimate deploy —
    // and if its failure were silent, the log would look complete when it was
    // not. Neither: the verdict stands, and the gap is named.
    const p = probe(tree({ decide: 0, statusExit: 2 }));
    expect(p.rc).toBe(0);
    expect(p.out).toContain('per-run listing could not be read');
  });

  it('works with NO declaration validator present, as long as no override is offered', () => {
    // The validator's absence must cost the OVERRIDE, not the gate. A fix that
    // took the whole gate down when a neighbouring lib moved would be a worse
    // failure than the one being fixed.
    const p = probe(tree({ decide: 0, omitInflight: true }));
    expect(p.rc).toBe(0);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// THE FOUR STATES, EACH MAPPED. 0 IS THE ONLY ONE THAT SHIPS.
// ───────────────────────────────────────────────────────────────────────────
describe('F22 — every non-zero answer REFUSES', () => {
  it('PENDING (1) refuses — this is the 2026-08-20 incident itself', () => {
    const p = probe(tree({ decide: 1 }));
    expect(p.rc).toBe(1);
    expect(p.out).toContain('has NOT finished looking at this commit');
    // The refusal is actionable or it is just an obstacle.
    expect(p.out).toContain('bash scripts/gh-runs.sh wait');
    expect(p.out).toContain('--wait-for-citation');
  });

  it('⚠️ CANNOT TELL (2) refuses — fail-closed, the load-bearing arm', () => {
    // A runs-API outage is not a licence to ship. A blind instrument and a
    // green commit produce the same silence.
    const p = probe(tree({ decide: 2 }));
    expect(p.rc).toBe(1);
    expect(p.out).toContain('CANNOT TELL');
    expect(p.out).toContain('--declare-citation-override');
  });

  it('FAILED (3) refuses, and says it is TERMINAL rather than retryable', () => {
    const p = probe(tree({ decide: 3 }));
    expect(p.rc).toBe(1);
    expect(p.out).toContain('CONCLUDED NON-SUCCESS');
    expect(p.out).toContain('TERMINAL');
  });

  it('⚠️ an UNMAPPED exit code refuses rather than proceeding', () => {
    // `gh-runs.sh` grew its 2 and its 3 one incident at a time, each because two
    // states had been collapsed into one code. The next state it learns to
    // report must not arrive here as a silent PROCEED.
    const p = probe(tree({ decide: 7 }));
    expect(p.rc).toBe(1);
    expect(p.out).toContain('unmapped exit code 7');
  });

  it('a MISSING instrument refuses — absence is never an all-clear', () => {
    const p = probe(tree({ omitRunner: true }));
    expect(p.rc).toBe(1);
    expect(p.out).toContain('missing or unreadable');
  });

  it('an unknown MODE refuses rather than silently defaulting to the loose one', () => {
    const p = probe(tree({ decide: 0 }), 'whatever');
    expect(p.rc).toBe(1);
    expect(p.out).toContain("unknown citation-gate mode");
  });

  it('every refusal states that production is untouched', () => {
    for (const decide of [1, 2, 3, 7]) {
      const p = probe(tree({ decide }));
      expect(p.rc).toBe(1);
      expect(p.out).toContain('Production is untouched');
    }
  });
});

// ───────────────────────────────────────────────────────────────────────────
// THE OVERRIDE IS A DECLARATION, NEVER A FLAG.
// ───────────────────────────────────────────────────────────────────────────
describe('F22 — the emergency override', () => {
  const REASON = 'GitHub Actions is degraded and the ingress fix must ship now';

  it('a real REASON lets a cannot-tell through, and echoes itself into the log', () => {
    const p = probe(tree({ decide: 2 }), 'refuse', REASON);
    expect(p.rc).toBe(0);
    expect(p.out).toContain('CITATION GATE OVERRIDDEN BY DECLARATION');
    expect(p.out).toContain(REASON);
  });

  it('⚠️ it still PROBES, so the log records WHAT was overridden', () => {
    // A waiver with no state attached is indistinguishable from never having
    // looked, and the record of what was waived is the entire product.
    const p = probe(tree({ decide: 3 }), 'refuse', REASON);
    expect(p.rc).toBe(0);
    expect(p.out).toContain('state at the moment of override');
    expect(p.out).toContain('exit 3');
  });

  it('and the probe it runs is the FAST one, never the polling one', () => {
    // An override is reached during an incident. A gate that hangs for an hour
    // after being waived is a gate somebody kills.
    const p = probe(tree({ decide: 2 }), 'wait', REASON);
    expect(p.rc).toBe(0);
    expect(p.out).toContain('STUB cited ');
    expect(p.out).not.toContain('STUB wait ');
  });

  it('REFUSES a bypass token wearing a declaration’s clothes', () => {
    for (const token of ['1', 'true', 'yes', 'force', 'skip']) {
      const p = probe(tree({ decide: 2 }), 'refuse', token);
      expect(p.rc, `token '${token}' was accepted`).toBe(1);
    }
  });

  it('REFUSES prose that is too short to be a reason', () => {
    const p = probe(tree({ decide: 2 }), 'refuse', 'outage');
    expect(p.rc).toBe(1);
  });

  it('⚠️ REFUSES an override it cannot VALIDATE — a waiver nothing checks is not a waiver', () => {
    const p = probe(tree({ decide: 2, omitInflight: true }), 'refuse', REASON);
    expect(p.rc).toBe(1);
    expect(p.out).toContain('cannot be validated');
  });

  it('the validator is the SHARED one, not a second copy of it', () => {
    // Two definitions of "what counts as a reason" is two doors with two
    // different locks. `inflight_declaration_ok` guards the push hook and the
    // merge wrapper; this is the third caller, not the second implementation.
    const src = readFileSync(LIB, 'utf8');
    expect(src).toContain('inflight_declaration_ok');
    expect(src).toContain('inflight.sh');
    expect(src).not.toMatch(/inflight_declaration_ok\(\)\s*\{/);
  });
});

// ───────────────────────────────────────────────────────────────────────────
// THE WIRING — every arm here fails a PARTIAL landing of this fix, and every
// partial landing leaves the library above perfect and all of its arms green.
// ───────────────────────────────────────────────────────────────────────────
describe('F22 — deploy-prod.sh actually uses it', () => {
  // ⚠️ COMMENTS ARE STRIPPED, AND THIS GATE CAUGHT ITS OWN AUTHOR TWICE ON THE
  // FIRST RUN FOR WANT OF IT.
  //
  //   · the ORDERING arm read `docker compose run --rm db-migrate` at index 465
  //     — inside the script's own HEADER, which explains why db-migrate is
  //     rebuilt. The gate "must precede the migration" therefore failed against
  //     a correctly-ordered file.
  //   · the ANTI-REGRESSION arm read `"${1:-}" != "--skip-backup"` from the
  //     comment written one line above the replacement, explaining what it
  //     replaced. The retired form was gone from the code and the assertion
  //     said it was still there.
  //
  // Both are this house's named substring trap, and the file's comments are the
  // one place where the words you are grepping for are guaranteed to appear.
  // `deploy()` is CODE ONLY, deliberately — the header of this very script
  // documents the incident being fixed, so prose here talks about everything.
  const deploy = () =>
    readFileSync(DEPLOY, 'utf8')
      .split('\n')
      .filter((l) => !/^\s*#/.test(l))
      .join('\n');

  it('the comment stripper actually strips (harness control)', () => {
    // Without this, a stripper that returned '' would make every `not.toContain`
    // arm below pass and every `toContain` arm fail loudly — but a stripper that
    // returned the file UNCHANGED would silently restore the trap it exists for.
    const raw = readFileSync(DEPLOY, 'utf8');
    expect(raw).toContain('# ⚠️ THE OLD FORM WAS');
    expect(deploy()).not.toContain('# ⚠️ THE OLD FORM WAS');
    expect(deploy().length).toBeGreaterThan(500);
  });

  it('PARSES — both the deploy script and the library it sources', () => {
    expect(() => execFileSync('bash', ['-n', DEPLOY], { encoding: 'utf8' })).not.toThrow();
    expect(() => execFileSync('bash', ['-n', LIB], { encoding: 'utf8' })).not.toThrow();
  });

  it('sources the library and CALLS the gate', () => {
    const src = deploy();
    expect(src).toContain('citation-gate.sh');
    expect(src).toMatch(/citation_gate "\$DEPLOY_SHA_FULL"/);
  });

  it('⚠️ the call ABORTS the deploy on refusal — a return value nobody reads is a comment', () => {
    expect(deploy()).toContain('citation_gate "$DEPLOY_SHA_FULL" "$CITATION_MODE" "$CITATION_OVERRIDE" || exit 1');
  });

  it('⚠️ it passes the FULL sha, never the short one used for naming', () => {
    const src = deploy();
    expect(src).toContain('DEPLOY_SHA_FULL="$(git rev-parse HEAD)"');
    // The short form still exists — it names the declaration — but it must not
    // be what the runs routes are asked about. An abbreviation matches NOTHING
    // there, with exit 0 and no warning.
    expect(src).not.toMatch(/citation_gate "\$DEPLOY_SHA"/);
  });

  it('⚠️ it runs BEFORE anything is built, migrated, tagged or recreated', () => {
    const src = deploy();
    const gate = src.indexOf('citation_gate "$DEPLOY_SHA_FULL"');
    expect(gate).toBeGreaterThan(-1);
    for (const later of [
      'rollback_tag_cut',
      'pre-deploy backup',
      'docker compose build db-migrate',
      'docker compose run --rm db-migrate',
      'docker compose up -d transcribe-md',
    ]) {
      const at = src.indexOf(later);
      expect(at, `'${later}' not found`).toBeGreaterThan(-1);
      expect(gate, `the citation gate must precede '${later}'`).toBeLessThan(at);
    }
  });

  it('a missing library is fail-closed at the call site too, not only inside it', () => {
    const src = deploy();
    expect(src).toMatch(/if \[ ! -r "\$CITE_LIB" \]; then/);
  });

  it('the mode and the override reach the gate from the command line', () => {
    const src = deploy();
    expect(src).toContain('--wait-for-citation');
    expect(src).toContain('--declare-citation-override');
    // ⚠️ AND THE FLAG EXISTS BECAUSE `VAR=... cmd` IS REFUSED TO THE UNATTENDED
    // LOOP, which is the only deploy actor. An env-only hatch would be inert in
    // exactly the sessions that would ever need it.
    expect(src).toContain('DEPLOY_CITATION_OVERRIDE');
  });

  it('⚠️ the old positional --skip-backup test is GONE, and unknown flags refuse', () => {
    const src = deploy();
    // `[ "${1:-}" != "--skip-backup" ]` took a full backup on a typo and ignored
    // the flag anywhere but position one. Neither said anything.
    expect(src).not.toContain('"${1:-}" != "--skip-backup"');
    expect(src).toContain('SKIP_BACKUP');
    expect(src).toContain("unknown argument");
  });
});
