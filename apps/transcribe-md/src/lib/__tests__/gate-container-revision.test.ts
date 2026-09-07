// ============================================================================
// RULING #262 — the ruled act runs INSIDE the container, and only if the
// container is running THIS TREE.
// ----------------------------------------------------------------------------
// ⚠️ THE MODE EXISTS BECAUSE A DOOR WAS REPORTED AS A WALL. Every TypeScript
// ruled mutation ran on the HOST, and a host `npx tsx` needs `DATABASE_URL` from
// `/opt/meddoc-pro/.env` — a file `.claude/settings.json` denies reading. So a
// session hit that and escalated a BLOCKER, when `deploy-prod.sh` had had the
// shape all along: it runs migrations with `docker compose run --rm db-migrate`
// and reads counts with `docker exec … psql`, both on the CONTAINER's own
// environment, which compose fills from `.env` without any agent reading it.
//
// ── WHAT THIS GATE IS ACTUALLY PROTECTING ───────────────────────────────────
// Not the convenience. The GUARD that had to come with it.
//
//   A CONTAINER CARRIES THE REPOSITORY AS OF ITS BUILD.
//
// Run a ruled mutation `--in` a container built at an older commit and the
// program that executes is NOT the program the declaration's author read —
// while every guard, every printed count and every timestamp in the transcript
// still looks correct. That is the deploy hazard *"a declaration naming the
// wrong commit is worse than no declaration, because it looks like evidence"*,
// one layer down, and this one cannot be rolled back.
//
// ── WHY A VITEST GATE AND NOT A SHELL HARNESS ───────────────────────────────
// The house has both. `scripts/test-verify-post-reboot.sh` is hand-run, and a
// proof nobody re-runs is a proof that decays. `gate-f9-deploy-cuts-its-rollback-tag`
// made the opposite choice for the same reason this file does: it runs in CI on
// every PR, forever.
//
// ── AND IT DRIVES THE REAL LIBRARY, WITH A FAKE `docker` ────────────────────
// Nothing here re-implements the logic. `container-revision.sh` routes every
// docker call through `$DOCKER`, so the arm injects a fake and exercises both
// halves without touching a real container.
//
// ⚠️ RUN UNDER THE CALLER'S SHELL OPTIONS. F9's gate proved every refusal in a
// `bash -c` WITHOUT `set -e`, a universe production does not run, and hid a
// defect that would have killed the deploy. `run-ruled-mutation.sh` runs
// `set -uo pipefail`, so that is what these arms use — and a second set runs
// under `set -euo pipefail` as well, so the library's behaviour cannot depend
// on which caller sources it.
// ============================================================================
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, chmodSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

import { afterAll, describe, expect, it } from 'vitest';

const REPO = resolve(__dirname, '../../../../..');
const LIB = resolve(REPO, 'scripts/lib/container-revision.sh');
// ⚠️ SOURCED TOO, BECAUSE THE CARRY-FORWARD READS ITS ALLOWLIST. The library
// refuses loudly when DECLARATION_NONRUNTIME_RE is absent — there is an arm for
// exactly that below — so the arms that exercise the carry-forward must reproduce
// the caller's real scope rather than a convenient subset of it.
const DECL_LIB = resolve(REPO, 'scripts/lib/declaration.sh');
const SHELLS = ['set -uo pipefail', 'set -euo pipefail'] as const;

const tmps: string[] = [];
afterAll(() => {
  for (const d of tmps) {
    try {
      rmSync(d, { recursive: true, force: true });
    } catch {
      /* a leaked temp dir is not worth failing a gate over */
    }
  }
});

/** Run a snippet with the real library sourced, under the given shell options. */
function sh(snippet: string, opts: string, fakeDocker?: string): string {
  let env = '';
  if (fakeDocker !== undefined) {
    const dir = mkdtempSync(join(tmpdir(), 'ctrrev-'));
    tmps.push(dir);
    const p = join(dir, 'docker');
    writeFileSync(p, `#!/usr/bin/env bash\n${fakeDocker}\n`);
    chmodSync(p, 0o755);
    env = `export DOCKER=${p}\n`;
  }
  try {
    return execFileSync(
      'bash',
      ['-c', `${opts}\n${env}. ${JSON.stringify(DECL_LIB)}\n. ${JSON.stringify(LIB)}\n${snippet}`],
      { encoding: 'utf8', timeout: 20_000, cwd: REPO },
    ).trim();
  } catch (e) {
    const err = e as { stdout?: string; stderr?: string; message: string };
    return `EXIT-NONZERO\n${err.stdout ?? ''}${err.stderr ?? ''}${err.message}`.trim();
  }
}

const HEAD = 'a'.repeat(40);

describe.each(SHELLS)('container_revision_verdict — under `%s`', (opts) => {
  // ⚠️ THE POSITIVE CONTROL IS FIRST. `retire-branch.sh` passed 9 of 9 refusal
  // tests and still printed a false green, because refusals were never its
  // broken half. If this arm regresses, every refusal below is refusing
  // something that was already broken and the suite stays green on all of them.
  it('says ok when the label EQUALS this tree, and says so in the reason', () => {
    const out = sh(`container_revision_verdict "${HEAD}" "${HEAD}"`, opts);
    expect(out.startsWith('ok|')).toBe(true);
    expect(out).toContain(HEAD.slice(0, 12));
  });

  it('REFUSES a 40-hex sha this repository does not contain', () => {
    // ⚠️ WRITTEN WITH A FABRICATED SHA ON PURPOSE, AND ASSERTING THE *RIGHT*
    // REFUSAL. This arm originally expected the mismatch message, and it passed
    // for the wrong reason: the instrument was answering correctly about a
    // commit that does not exist. The programme has paid for that confusion
    // once already (canon 61). The mismatch path has its own arms below, driven
    // by REAL commits from this repository's history.
    const other = 'b'.repeat(40);
    const out = sh(`container_revision_verdict "${other}" "${HEAD}"`, opts);
    expect(out.startsWith('refuse|')).toBe(true);
    expect(out).toContain('not a commit in THIS repository');
    expect(out).toContain(other.slice(0, 12));
  });

  it("REFUSES the literal 'unknown' — the Dockerfile ARG default", () => {
    // ⚠️ THIS IS THE REACHABLE ONE. `Dockerfile:212` is `ARG GIT_REVISION=unknown`
    // and compose passes `${GIT_REVISION:-unknown}`, so ANY image built without
    // the deploy script exporting it carries exactly this string. It is hex-ish
    // enough to look like an identifier and is not one.
    const out = sh(`container_revision_verdict "unknown" "${HEAD}"`, opts);
    expect(out.startsWith('refuse|')).toBe(true);
    expect(out).toContain('never recorded');
  });

  it('REFUSES an EMPTY label — an image with no such label at all', () => {
    const out = sh(`container_revision_verdict "" "${HEAD}"`, opts);
    expect(out.startsWith('refuse|')).toBe(true);
    expect(out).toContain('no org.opencontainers.image.revision label');
  });

  it('REFUSES a non-hex label', () => {
    for (const bad of ['not-a-sha', 'HEAD', 'deadbeefzz', '../../etc']) {
      const out = sh(`container_revision_verdict ${JSON.stringify(bad)} "${HEAD}"`, opts);
      expect(out.startsWith('refuse|'), `'${bad}' must refuse`).toBe(true);
    }
  });

  it('REFUSES an ABBREVIATION, even a correct one — it never completes an identifier', () => {
    // ⚠️ A 12-char prefix of HEAD is hex, is a real prefix of the right commit,
    // and is still refused. `declaration_resolve` applies the same rule to a
    // declaration's filename: full-looking is not full, and short is ambiguous
    // by construction.
    const out = sh(`container_revision_verdict "${HEAD.slice(0, 12)}" "${HEAD}"`, opts);
    expect(out.startsWith('refuse|')).toBe(true);
    expect(out).toContain('not 40');
  });

  it('REFUSES when there is no HEAD to compare against', () => {
    const out = sh(`container_revision_verdict "${HEAD}" ""`, opts);
    expect(out.startsWith('refuse|')).toBe(true);
  });

  it('the happy path is an EQUALITY, not a resemblance', () => {
    // One character apart, both 40 hex, neither in this repo -> still refuses.
    const almost = 'a'.repeat(39) + 'b';
    const out = sh(`container_revision_verdict "${almost}" "${HEAD}"`, opts);
    expect(out.startsWith('refuse|')).toBe(true);
  });

  it('NEVER echoes an empty verdict — every path answers', () => {
    // A caller splits on '|'; a silent path would give V_MODE='' which is
    // neither 'ok' nor a refusal, and the caller's `!= ok` test would then
    // refuse for a reason nobody wrote. Assert totality.
    for (const [a, b] of [
      ['', ''],
      ['unknown', ''],
      [HEAD, HEAD],
      ['zz', HEAD],
      ['b'.repeat(40), HEAD],
      [HEAD, 'c'.repeat(40)],
    ]) {
      const out = sh(`container_revision_verdict ${JSON.stringify(a)} ${JSON.stringify(b)}`, opts);
      expect(out.length, `verdict for (${a || '<empty>'}, ${b || '<empty>'})`).toBeGreaterThan(3);
      expect(out.includes('|')).toBe(true);
    }
  });
});

describe('container_id_for_service — ambiguity is a refusal, not a head -1', () => {
  const opts = 'set -uo pipefail';

  it('returns the id when EXACTLY ONE container matches', () => {
    const out = sh(
      'container_id_for_service /tmp/compose.yml worker',
      opts,
      'if [ "$1" = "compose" ]; then echo c0ffee; fi',
    );
    expect(out).toBe('c0ffee');
  });

  it('returns EMPTY when the service is scaled to more than one', () => {
    // ⚠️ THE FAILURE THIS EXCLUDES: silently tagging whichever sorted first.
    // `rollback-tag.sh` refuses the identical shape with a rollback target as
    // the prize; here the prize is an irreversible write.
    const out = sh(
      'container_id_for_service /tmp/compose.yml worker',
      opts,
      'if [ "$1" = "compose" ]; then printf "aaa\\nbbb\\n"; fi',
    );
    expect(out).toBe('');
  });

  it('returns EMPTY when nothing is running', () => {
    const out = sh('container_id_for_service /tmp/compose.yml worker', opts, 'exit 0');
    expect(out).toBe('');
  });

  it('returns EMPTY when docker itself FAILS — cannot-tell is not all-clear', () => {
    const out = sh(
      'container_id_for_service /tmp/compose.yml worker',
      opts,
      'echo "Cannot connect to the Docker daemon" >&2; exit 1',
    );
    expect(out).toBe('');
  });

  it('passes the compose file EXPLICITLY, so cwd cannot select a different stack', () => {
    // ⚠️ `docker-compose.yml` carries RELATIVE bind mounts; resolving it from a
    // worktree points them at that directory. `ps` creates nothing, but the -f
    // is what makes that structurally impossible rather than merely unlikely.
    const out = sh(
      'container_id_for_service /opt/meddoc-pro/docker-compose.yml worker',
      opts,
      'echo "$@"',
    );
    expect(out).toContain('-f /opt/meddoc-pro/docker-compose.yml');
    expect(out).toContain('ps -q worker');
  });
});

describe('container_revision_of', () => {
  const opts = 'set -uo pipefail';

  it('reads the label through docker inspect', () => {
    const out = sh('container_revision_of abc123', opts, `echo ${HEAD}`);
    expect(out).toBe(HEAD);
  });

  it('is EMPTY when inspect fails, rather than propagating a failure', () => {
    // Empty is the value `container_revision_verdict` refuses on, so the two
    // halves compose into a refusal instead of into an unhandled error.
    const out = sh('container_revision_of abc123', opts, 'exit 1');
    expect(out).toBe('');
  });

  it('asks for the RIGHT label key', () => {
    const out = sh('container_revision_of abc123', opts, 'echo "$@"');
    expect(out).toContain('org.opencontainers.image.revision');
  });
});

describe('the CARRY-FORWARD — widened by PROOF, never by tolerance', () => {
  const opts = 'set -uo pipefail';

  // ⚠️ WHY THIS EXISTS AT ALL, said where the next reader will meet it: the
  // exact-match test alone FALSELY REFUSES THE NORMAL CADENCE. Deploy, then land
  // a docs PR — `main` has moved, the container has not, and the script about to
  // run is byte-identical. A guard that refuses legitimate work does not stay a
  // guard; it gets worked around, and then it protects nothing.

  /** Two real commits from this repository's own history, N apart. */
  function headAnd(n: number): { head: string; older: string } {
    const out = execFileSync('git', ['rev-list', '-n', String(n + 1), 'HEAD'], {
      cwd: REPO,
      encoding: 'utf8',
    })
      .trim()
      .split('\n');
    return { head: out[0]!, older: out[out.length - 1]! };
  }

  it('ACCEPTS an ancestor when ZERO runtime files moved — and says WHY it accepted', () => {
    const { head } = headAnd(0);
    // HEAD against itself is the degenerate case; use the real docs-only pair:
    // this branch's own rulings commit changed only docs/, so its child carries
    // zero runtime movement from it... unless it does not, in which case this
    // arm must not silently pass. So assert the PREMISE first.
    const rulings = execFileSync(
      'git',
      ['log', '--format=%H', '-n', '1', '--', 'docs/foundation/rulings/2026-09-07-261-266.md'],
      { cwd: REPO, encoding: 'utf8' },
    ).trim();
    const moved = execFileSync('git', ['diff', '--name-only', rulings, head], {
      cwd: REPO,
      encoding: 'utf8',
    })
      .trim()
      .split('\n')
      .filter(Boolean);
    const runtimeMoved = moved.filter((f) => !/^(docs\/|[^/]+\.md$)/.test(f));

    const out = sh(`container_revision_verdict "${rulings}" "${head}"`, opts);
    if (runtimeMoved.length === 0) {
      expect(out.startsWith('ok|'), out).toBe(true);
      expect(out).toContain('ZERO runtime files moved');
    } else {
      // ⚠️ THE ARM STILL ASSERTS SOMETHING when the premise does not hold —
      // it must REFUSE, and name the count. A test that quietly skips is a test
      // that reports success for a run it never made.
      expect(out.startsWith('refuse|'), out).toBe(true);
      expect(out).toContain('RUNTIME file(s) moved');
    }
  });

  it('REFUSES an ancestor when a RUNTIME file moved — the discriminating case', () => {
    // This branch's own HEAD is a source commit, so HEAD's PARENT -> HEAD moved
    // runtime files by construction. If that ever stops being true the arm reds,
    // which is correct: it would no longer be testing what it claims to.
    const { head, older } = headAnd(1);
    const moved = execFileSync('git', ['diff', '--name-only', older, head], {
      cwd: REPO,
      encoding: 'utf8',
    })
      .trim()
      .split('\n')
      .filter(Boolean);
    const runtimeMoved = moved.filter((f) => !/^(docs\/|[^/]+\.md$)/.test(f));
    expect(runtimeMoved.length, `premise: ${older.slice(0, 8)}..${head.slice(0, 8)} must move runtime files`).toBeGreaterThan(0);

    const out = sh(`container_revision_verdict "${older}" "${head}"`, opts);
    expect(out.startsWith('refuse|'), out).toBe(true);
    expect(out).toContain('DIFFERENT PROGRAMS');
  });

  it('REFUSES a commit this repository does not contain', () => {
    const out = sh(`container_revision_verdict "${'d'.repeat(40)}" "$(git rev-parse HEAD)"`, opts);
    expect(out.startsWith('refuse|')).toBe(true);
    expect(out).toContain('not a commit in THIS repository');
  });

  it('REFUSES when the container is NEWER than the tree — direction is load-bearing', () => {
    // ⚠️ A SYMMETRIC TEST WOULD WAVE THIS THROUGH. The container being ahead of
    // the tree is a different fault with a different remedy, and it is not
    // answered by running the act.
    const { head, older } = headAnd(1);
    const out = sh(`container_revision_verdict "${head}" "${older}"`, opts);
    expect(out.startsWith('refuse|'), out).toBe(true);
    expect(out).toContain('NOT an ancestor');
  });

  it('REFUSES, loudly, when the shared allowlist is not in scope — fail-closed', () => {
    // The one arm that must NOT source declaration.sh: it is testing what
    // happens when nobody did.
    const { head, older } = headAnd(1);
    const out = execFileSync(
      'bash',
      ['-c', `set -uo pipefail\n. ${JSON.stringify(LIB)}\ncontainer_revision_verdict "${older}" "${head}"`],
      { encoding: 'utf8', cwd: REPO, timeout: 20_000 },
    ).trim();
    expect(out.startsWith('refuse|'), out).toBe(true);
    expect(out).toContain('DECLARATION_NONRUNTIME_RE is not in scope');
  });
});
