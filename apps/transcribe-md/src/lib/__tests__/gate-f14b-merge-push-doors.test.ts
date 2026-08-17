// ============================================================================
// F14-b — THE MERGE AND PUSH DOORS SURVIVE A REPO-WIDE RUNS-API OUTAGE.
// ----------------------------------------------------------------------------
// On 2026-08-17 GitHub's repo-wide `/actions/runs` route returned 404 for this
// repository for hours while every other Actions route answered 200. Every
// citation and in-flight instrument here funnelled through that one route, so
// nothing could be cited, pushed or merged. F14-a routed the CITATION door
// around it via `scripts/lib/runs-api.sh`. It deliberately left the other two,
// because getting them wrong in an unattended session means nothing can be
// merged or pushed to FIX it — so they landed as their own item, this one.
//
// ⚠️ THE REFUSALS WERE CORRECT AND ARE NOT WHAT CHANGED. A missing `gh`, an
// unauthenticated one, a failed query and an unreadable payload all still
// produce CANNOT TELL and both doors still refuse. What changed is that a
// repo-wide outage ALONE no longer produces that state. The `REFUSES` arms
// below exist to keep that true.
//
// ── WHAT THIS GATE WATCHES, DIFFED AGAINST WHAT THE ITEM NAMES ──────────────
// RELAY's F14-b row names three things. Each is an arm here:
//
//   "`gh-runs.sh` and `lib/inflight.sh` onto `runs-api.sh`"
//                                        -> `the wiring` describe block
//   "with the refusal arms re-proved on both doors"
//                                        -> every `REFUSES` arm
//   "`retire-branch.sh` passed 9 of 9 refusals and still printed a false green
//    on the happy path, so prove the SUCCESS direction too."
//                                        -> the `ANSWERS` arms, asserted FIRST
//
// ⚠️ THE ACCEPT ARMS ARE THIS GATE'S POSITIVE CONTROL AND THEY COME FIRST. An
// `inflight_count` that refused everything would satisfy every refusal arm in
// this file. That is the `retire-branch.sh` shape the item's own row names, and
// it is the half that gets skipped.
//
// ── WHAT IT DRIVES ─────────────────────────────────────────────────────────
// The REAL `scripts/lib/inflight.sh`, sourced by a real bash. Nothing here
// re-implements the logic. The two QUERY functions are then redefined to return
// fixed payloads, so the arms exercise the real parsing, the real transport
// bookkeeping and the real refusal paths with NO NETWORK — which is what makes
// this runnable in CI, where `gh` has no credentials.
//
// ⚠️ HONEST LIMITS, STATED SO THE GREEN IS NOT READ WIDER THAN IT IS:
//
//   1. IT DOES NOT PROVE THE LIVE TRANSPORT. `runs_api_for_sha` /
//      `runs_api_for_branch` are stubbed here. Their real behaviour — that the
//      per-workflow union returns the SAME verdict as the repo-wide route —
//      was measured by hand on 2026-08-17 through `scripts/gh-runs.sh` on two
//      real shas, one green and one with two failed runs, and BOTH transports
//      returned identical run sets and identical exit codes (0 and 3). The
//      numbers are in RELAY's F14-b row. A network arm here would burn API
//      calls on every CI run and go red on GitHub's weather.
//   2. IT DOES NOT PROVE THE HOOK FIRES. `check-hooks-installed.sh` and
//      FOUNDATION STEP 0 own that question; a gate cannot assert its own
//      installation.
//   3. THE WIRING ARMS ARE SOURCE-TEXT ASSERTIONS, and text presence is not
//      membership. They are therefore positive-controlled: the same extractor
//      must FIND a call that is present before its zero for an absent one is
//      believed.
// ============================================================================

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const REPO_ROOT = `${__dirname}/../../../../..`;
const INFLIGHT = join(REPO_ROOT, 'scripts/lib/inflight.sh');
const GH_RUNS = join(REPO_ROOT, 'scripts/gh-runs.sh');
const MERGE_PR = join(REPO_ROOT, 'scripts/merge-pr.sh');
const PRE_PUSH = join(REPO_ROOT, 'scripts/hooks/pre-push');

const SHA = 'b2f30ea2cda2d22693b063c51254ba45610358f6'; // 40 chars, shape only

let TMP: string;

beforeAll(() => {
  TMP = mkdtempSync(join(tmpdir(), 'f14b-doors-'));
});

afterAll(() => {
  // The FOUNDATION loop cannot reap — `shred` and `rm` are denied to it by
  // design — so a gate that mints a directory per run mints scratch the only
  // actor present cannot delete. F9's gate filed that against itself after nine
  // leftovers; cheaper to copy than to relearn.
  rmSync(TMP, { recursive: true, force: true });
});

type Run = { code: number; out: string };

// ⚠️ `set -uo pipefail` MATCHES THE SHELLS THAT ACTUALLY SOURCE THIS LIB —
// `scripts/hooks/pre-push:55` and `scripts/merge-pr.sh:39` both set exactly
// that. A harness running a MILDER shell than production proves the tidy case;
// this repo has paid for a wrong universe more than once.
function bash(body: string): Run {
  const file = join(TMP, `t${Math.random().toString(36).slice(2)}.sh`);
  writeFileSync(file, `set -uo pipefail\n. ${JSON.stringify(INFLIGHT)}\n${body}\n`);
  try {
    const out = execFileSync('bash', [file], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    return { code: 0, out };
  } catch (e) {
    const err = e as { status?: number; stdout?: string; stderr?: string };
    return { code: err.status ?? -1, out: `${err.stdout ?? ''}${err.stderr ?? ''}` };
  }
}

/** A payload in `runs-api.sh`'s emitted shape. `pending` runs are `queued`;
 *  the rest are `completed`, which is the only distinction `inflight_count`
 *  makes. `_transport` is what drives the degradation bookkeeping. */
function payload(pending: number, done: number, transport: string): string {
  const runs = [
    ...Array.from({ length: pending }, (_, i) => ({ name: `p${i}`, status: 'queued', conclusion: null })),
    ...Array.from({ length: done }, (_, i) => ({ name: `d${i}`, status: 'completed', conclusion: 'success' })),
  ];
  return JSON.stringify({ total_count: runs.length, workflow_runs: runs, _transport: transport, _control: '' });
}

/** Drive the REAL `inflight_count` with the two query functions stubbed.
 *  `rcC` / `rcB` let an arm simulate a transport that cannot answer at all. */
function count(opts: {
  commit: string;
  branch: string;
  sha?: string;
  rcC?: number;
  rcB?: number;
}): Run {
  const { commit, branch, sha = SHA, rcC = 0, rcB = 0 } = opts;
  return bash(`
inflight_repo()        { printf '%s' 'owner/repo'; }
runs_api_for_sha()     { printf '%s' ${JSON.stringify(commit)}; return ${rcC}; }
runs_api_for_branch()  { printf '%s' ${JSON.stringify(branch)}; return ${rcB}; }
if inflight_count main ${JSON.stringify(sha)}; then
  echo "RC=0 C=$INFLIGHT_BY_COMMIT B=$INFLIGHT_BY_BRANCH TOTAL=$(inflight_total) T=$INFLIGHT_TRANSPORT D=$INFLIGHT_DEGRADED"
  echo "NOTE=$INFLIGHT_NOTE"
else
  echo "RC=1"
fi`);
}

/** Non-comment lines only. A shell comment is any line whose first non-space
 *  character is `#`; a trailing `# …` on a code line is left alone, because a
 *  line that also runs code is code. */
function codeLines(path: string): string {
  return readFileSync(path, 'utf8')
    .split('\n')
    .filter((l) => !/^\s*#/.test(l))
    .join('\n');
}

// ─────────────────────────────────────────────────────────────────────────────
describe('F14-b · inflight_count ANSWERS (the positive control — asserted first)', () => {
  it('counts a quiet ref as zero, on the primary transport, undegraded', () => {
    const r = count({ commit: payload(0, 4, 'repo-wide'), branch: payload(0, 9, 'repo-wide') });
    expect(r.out).toContain('RC=0 C=0 B=0 TOTAL=0 T=repo-wide D=0');
    // ⚠️ THE NOTE MUST BE EMPTY HERE. A door that always printed a degradation
    // banner would train its reader to ignore the one that matters.
    expect(r.out).toContain('NOTE=\n');
  });

  it('counts runs that are IN FLIGHT — the under-report is the direction that costs a run', () => {
    const r = count({ commit: payload(2, 2, 'repo-wide'), branch: payload(3, 6, 'repo-wide') });
    expect(r.out).toContain('RC=0 C=2 B=3 TOTAL=5 T=repo-wide D=0');
  });

  it('answers on the FALLBACK transport instead of refusing — this IS the item', () => {
    const r = count({ commit: payload(1, 3, 'per-workflow'), branch: payload(0, 9, 'per-workflow') });
    // The whole product of F14-b: an outage no longer shuts both doors.
    expect(r.out).toContain('RC=0 C=1 B=0 TOTAL=1 T=per-workflow D=1');
  });

  it('ANNOUNCES the degradation, and names the branch count as a FLOOR', () => {
    const r = count({ commit: payload(0, 4, 'per-workflow'), branch: payload(0, 9, 'per-workflow') });
    expect(r.out).toContain('D=1');
    expect(r.out).toMatch(/NOTE=.*FALLBACK/);
    // ⚠️ THE WORD "FLOOR" IS THE ASSERTION, NOT DECORATION. The branch view has
    // no per-commit coverage control in fallback mode, so its zero is a floor
    // rather than a measurement. A degradation announced without that word is a
    // banner that says "something is different" and not "this number can be
    // low", which is the only part a reader can act on.
    expect(r.out).toMatch(/NOTE=.*FLOOR/);
  });

  it('reports a MIXED transport when only one view fell back', () => {
    const r = count({ commit: payload(0, 4, 'per-workflow'), branch: payload(0, 9, 'repo-wide') });
    expect(r.out).toContain('T=mixed');
    expect(r.out).toContain('D=1');
  });
});

describe('F14-b · inflight_count REFUSES (cannot-tell is not an all-clear)', () => {
  it('refuses an abbreviated sha', () => {
    const r = count({ commit: payload(0, 4, 'repo-wide'), branch: payload(0, 9, 'repo-wide'), sha: 'b2f30ea2' });
    expect(r.out).toContain('RC=1');
  });

  it('refuses an empty sha', () => {
    const r = count({ commit: payload(0, 4, 'repo-wide'), branch: payload(0, 9, 'repo-wide'), sha: '' });
    expect(r.out).toContain('RC=1');
  });

  it('refuses when the COMMIT transport cannot answer', () => {
    const r = count({ commit: '', branch: payload(0, 9, 'repo-wide'), rcC: 1 });
    expect(r.out).toContain('RC=1');
  });

  it('refuses when the BRANCH transport cannot answer', () => {
    // ⚠️ BOTH VIEWS, SEPARATELY. A refusal proved on one query hides a caller
    // that forgot to check the other — and the branch view is the one that is
    // right first in the propagation window this whole check exists for.
    const r = count({ commit: payload(0, 4, 'repo-wide'), branch: '', rcB: 1 });
    expect(r.out).toContain('RC=1');
  });

  // ⚠️ THESE TWO ARMS EXIST BECAUSE MUTATION M5 DID NOT REDDEN, AND THE
  // NON-REDDENING WAS THE FINDING. Deleting the branch query's `|| return 1`
  // left the suite at 28 of 28 — because the arm above hands the stub an EMPTY
  // payload, so the refusal still fired one line later, from the `jq`
  // unreadable-payload check. The arm was real and it was guarding a DIFFERENT
  // guard: the return-code path had never been exercised at all.
  //
  // A valid payload paired with a non-zero rc is the only input that isolates
  // it. It is not a contrived shape either — a transport that emits a stale or
  // partial body and then reports failure is exactly what a degrading API does,
  // and reading that body as an answer is how a floor becomes a verdict.
  it('refuses on a non-zero COMMIT rc even when the payload PARSES', () => {
    const r = count({ commit: payload(0, 4, 'repo-wide'), branch: payload(0, 9, 'repo-wide'), rcC: 1 });
    expect(r.out).toContain('RC=1');
  });

  it('refuses on a non-zero BRANCH rc even when the payload PARSES', () => {
    const r = count({ commit: payload(0, 4, 'repo-wide'), branch: payload(0, 9, 'repo-wide'), rcB: 1 });
    expect(r.out).toContain('RC=1');
  });

  it('refuses an unreadable payload rather than reading it as zero', () => {
    // A broken instrument and a quiet ref produce the same zero. This is that
    // sentence as an executable arm.
    const r = count({ commit: 'not json at all', branch: payload(0, 9, 'repo-wide') });
    expect(r.out).toContain('RC=1');
  });

  it('refuses when the repository cannot be resolved', () => {
    const r = bash(`
inflight_repo() { return 1; }
runs_api_for_sha()    { printf '%s' ${JSON.stringify(payload(0, 4, 'repo-wide'))}; }
runs_api_for_branch() { printf '%s' ${JSON.stringify(payload(0, 9, 'repo-wide'))}; }
if inflight_count main ${JSON.stringify(SHA)}; then echo "RC=0"; else echo "RC=1"; fi`);
    expect(r.out).toContain('RC=1');
  });
});

describe('F14-b · the declaration override — refused as a token, accepted as prose', () => {
  it.each(['1', 'true', 'yes', 'y', 'on', 'force', 'skip'])('refuses the bypass token %s', (tok) => {
    const r = bash(`if inflight_declaration_ok ${JSON.stringify(tok)}; then echo OK; else echo REFUSED; fi`);
    expect(r.out).toContain('REFUSED');
  });

  it('refuses a declaration shorter than prose', () => {
    const r = bash(`if inflight_declaration_ok "nope"; then echo OK; else echo REFUSED; fi`);
    expect(r.out).toContain('REFUSED');
  });

  it('ACCEPTS a real declaration — the sanctioned door is not welded shut', () => {
    const r = bash(
      `if inflight_declaration_ok "merging #716 and #717 as one declared batch; the cancelled e2e is mine"; then echo OK; else echo REFUSED; fi`,
    );
    expect(r.out).toContain('OK');
  });

  it('ACCEPTS an absent declaration (no override offered is not an error)', () => {
    const r = bash(`if inflight_declaration_ok ""; then echo OK; else echo REFUSED; fi`);
    expect(r.out).toContain('OK');
  });
});

describe('F14-b · the wiring — what the item NAMED, diffed against what shipped', () => {
  it('POSITIVE CONTROL: the extractor finds a call that IS present', () => {
    // ⚠️ WITHOUT THIS, EVERY ZERO BELOW IS WORTHLESS. A `codeLines` that
    // returned nothing — a bad regex, an unreadable file — would satisfy all
    // three absence arms perfectly.
    expect(codeLines(INFLIGHT)).toContain('gh repo view');
    expect(codeLines(INFLIGHT)).toContain('runs_api_for_sha');
    expect(codeLines(GH_RUNS)).toContain('runs_api_for_sha');
  });

  it('POSITIVE CONTROL: the needle itself is findable, in the comments it survives in', () => {
    // The absence arms assert `gh run list` is gone from CODE. Both files still
    // discuss it at length in prose — so a needle that matched nothing anywhere
    // would also produce a green. It must match the raw text and not the code.
    expect(readFileSync(INFLIGHT, 'utf8')).toContain('gh run list');
    expect(readFileSync(GH_RUNS, 'utf8')).toContain('gh run list');
  });

  it('lib/inflight.sh no longer CALLS gh run list', () => {
    expect(codeLines(INFLIGHT)).not.toContain('gh run list');
  });

  it('gh-runs.sh no longer CALLS gh run list', () => {
    expect(codeLines(GH_RUNS)).not.toContain('gh run list');
  });

  it('lib/inflight.sh sources runs-api.sh — the transport is real, not aspirational', () => {
    expect(codeLines(INFLIGHT)).toMatch(/\.\s+"\$_INFLIGHT_LIB_DIR\/runs-api\.sh"/);
  });

  it('BOTH doors surface the degradation — a known limit that is not printed is an invisible one', () => {
    // ⚠️ THIS IS THE ARM THAT WOULD HAVE CAUGHT A HALF-LANDED FIX. Wiring the
    // lib and forgetting one door is exactly the "do the obvious first step"
    // partial application this repo names: the transport would work, the floor
    // would be real, and one of the two doors would never say so.
    for (const door of [MERGE_PR, PRE_PUSH]) {
      expect(codeLines(door)).toContain('INFLIGHT_DEGRADED');
      expect(codeLines(door)).toContain('INFLIGHT_NOTE');
    }
  });

  it('gh-runs.sh exposes --force-fallback, because an env-only hatch is inert for the loop', () => {
    // `VAR=1 bash …` and `env` are both refused to the unattended session, so a
    // fallback reachable only by env var is reachable only by the actors that
    // never need it. F14-a learned this on check-citation.sh.
    expect(codeLines(GH_RUNS)).toContain('--force-fallback');
    expect(codeLines(GH_RUNS)).toContain('RUNS_API_FORCE_FALLBACK');
  });
});
