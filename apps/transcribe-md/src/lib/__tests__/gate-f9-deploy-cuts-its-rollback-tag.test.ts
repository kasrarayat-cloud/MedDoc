// ============================================================================
// F9 — the deploy cuts its OWN rollback tag, from the RUNNING container.
// ----------------------------------------------------------------------------
// ⚠️ TWO CONSECUTIVE DEPLOYS LEFT PRODUCTION WITH NO ROLLBACK TARGET.
// `docs/DEPLOYMENT_RUNBOOK.md` §3.1 has said since 2026-08-02 that tagging the
// outgoing images is a MANUAL pre-step and that forgetting it leaves nothing to
// roll back to. It was forgotten twice on 2026-08-16 — F3 at 04:02Z, F4 at
// 11:35Z — and the second time by a session that then asserted IN ITS OWN §2.5
// DECLARATION that the tags had been cut. Both images were recovered by hand
// from dangling images; the ~8h window in which a rollback would have required
// a REBUILD is what was actually paid.
//
//   A PRE-STEP THAT LIVES ONLY IN PROSE IS A PRE-STEP THAT GETS SKIPPED.
//
// Same argument that turned the in-flight-runs rule into `scripts/hooks/pre-push`
// and the §2.5 rule into `scripts/lib/declaration.sh`. So `scripts/deploy-prod.sh`
// now sources `scripts/lib/rollback-tag.sh` at STEP 0b and REFUSES if it cannot
// tag — before the backup, before any build, before anything is recreated.
//
// ── WHY THIS GATE IS A VITEST FILE AND NOT A SHELL HARNESS ──────────────────
// It was first written as `scripts/test-rollback-tag.sh`, in the house style of
// `scripts/test-verify-post-reboot.sh`. That shape is HAND-RUN — and a proof
// nobody re-runs is a proof that decays. As a gate it runs in `CI` on every PR,
// forever, which is the artifact F9 actually wanted.
//
// ── WHAT IT DRIVES ──────────────────────────────────────────────────────────
// The REAL library, sourced by a real bash, with a FAKE `docker` injected
// through the lib's own `$DOCKER` indirection. Nothing here re-implements the
// logic — a second copy would drift from the first the day either is fixed,
// which is the same reason `declaration.sh` and `inflight.sh` are shared.
//
// ⚠️ HONEST LIMIT, NAMED RATHER THAN IMPLIED: a fake docker proves the LOGIC,
// not the INTEGRATION. The integration was proved separately and by hand
// against the real running containers on 2026-08-16 (see the F9 ledger row);
// this file cannot do that, because a test that tags real production images is
// not a test.
//
// ── AND IT PROVES BOTH DIRECTIONS ───────────────────────────────────────────
// `retire-branch.sh` passed 9 of 9 REFUSAL tests and still printed a false
// green, because refusals were never its broken half. F9's own ledger row
// demands the pair: prove it refuses when it cannot tag, AND prove the tag
// exists and resolves to the outgoing image afterwards.
// ============================================================================

import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, readFileSync, existsSync, chmodSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const REPO_ROOT = `${__dirname}/../../../../..`;
const LIB = join(REPO_ROOT, 'scripts/lib/rollback-tag.sh');
const DEPLOY = join(REPO_ROOT, 'scripts/deploy-prod.sh');

const APP_IMG = `sha256:${'a'.repeat(64)}`;
const WRK_IMG = `sha256:${'b'.repeat(64)}`;
const OTHER_IMG = `sha256:${'c'.repeat(64)}`;

let TMP: string;

/** The fake docker. Behaviour is driven by files under `state/`, so each arm
 *  bends exactly ONE thing and everything else stays at the happy default.
 *
 *  ⚠️ It APPENDS every `docker tag` to `state/tags`. That file is how the gate
 *  distinguishes "refused" from "refused AFTER tagging something" — the same
 *  move `merge-pr.sh`'s proof makes by recording whether `gh pr merge` was
 *  invoked at all. A refusal that already mutated is not a refusal. */
const FAKE_DOCKER = `#!/usr/bin/env bash
T="$FAKE_STATE"
if [ "$1 $2" = "compose ps" ]; then
  svc="\${4:-}"
  grep -E "^\${svc}\\|" "$T/containers" 2>/dev/null | cut -d'|' -f2
  exit 0
fi
if [ "$1" = "inspect" ]; then
  fmt=""; ref=""; shift
  while [ $# -gt 0 ]; do
    case "$1" in
      --format) fmt="$2"; shift 2 ;;
      --type=image) shift ;;
      *) ref="$1"; shift ;;
    esac
  done
  case "$fmt" in
    '{{.Image}}')        grep -E "^\${ref}\\|" "$T/cimages" 2>/dev/null | cut -d'|' -f2 ;;
    '{{.Config.Image}}') grep -E "^\${ref}\\|" "$T/cconfig" 2>/dev/null | cut -d'|' -f2 ;;
    '{{.Id}}')
      line=$(grep -E "^\${ref}\\|" "$T/tags" 2>/dev/null | tail -1 | cut -d'|' -f2)
      [ -z "$line" ] && line=$(grep -E "^\${ref}\\|" "$T/images" 2>/dev/null | cut -d'|' -f2)
      [ -z "$line" ] && exit 1
      printf '%s' "$line" ;;
  esac
  exit 0
fi
if [ "$1" = "tag" ]; then
  [ -f "$T/tag_fails" ] && { echo "Error response from daemon: no such image"; exit 1; }
  [ -f "$T/tag_lies" ] && { echo "$3|" >> "$T/tags"; exit 0; }
  echo "$3|$2" >> "$T/tags"
  exit 0
fi
exit 0
`;

type Bend = 'none' | 'no_worker_container' | 'tag_fails' | 'tag_lies' | 'bad_image_id' | 'bare_config_image';

function resetState(bend: Bend = 'none', seedTag?: [string, string]): string {
  const s = join(TMP, 'state');
  // ⚠️ THE BEND FLAGS ARE REMOVED, NOT JUST NOT-WRITTEN — AND THE FIRST DRAFT
  // ONLY DID THE LATTER. `tag_fails` written by one arm survived into the next
  // two, so the tag-lies arm and the bare-image arm both refused for the WRONG
  // REASON while still reporting a non-zero exit. That is a proof that passes
  // its `code !== 0` assertion having exercised none of the code it names — the
  // "reset that does not reset" flavour of an unapplied mutation. Only the
  // message assertions caught it, which is why they are here.
  rmSync(s, { recursive: true, force: true });
  mkdirSync(s, { recursive: true });
  writeFileSync(join(s, 'tags'), '');
  writeFileSync(join(s, 'images'), seedTag ? `${seedTag[0]}|${seedTag[1]}\n` : '');
  writeFileSync(
    join(s, 'containers'),
    bend === 'no_worker_container'
      ? 'transcribe-md|cid-app\n'
      : 'transcribe-md|cid-app\ntranscribe-md-worker|cid-wrk\n',
  );
  writeFileSync(
    join(s, 'cimages'),
    bend === 'bad_image_id'
      ? 'cid-app|sha256:not-a-real-digest\n'
      : `cid-app|${APP_IMG}\ncid-wrk|${WRK_IMG}\n`,
  );
  writeFileSync(
    join(s, 'cconfig'),
    bend === 'bare_config_image'
      ? `cid-app|sha256:${'d'.repeat(64)}\n`
      // ⚠️ deliberately ASYMMETRIC: app is untagged, worker carries `:latest`.
      // Both shapes occur on this host, and the tag-stripping must handle each.
      : 'cid-app|meddoc-pro-transcribe-md\ncid-wrk|meddoc-pro-transcribe-md-worker:latest\n',
  );
  if (bend === 'tag_fails') writeFileSync(join(s, 'tag_fails'), '');
  if (bend === 'tag_lies') writeFileSync(join(s, 'tag_lies'), '');
  return s;
}

/** ⚠️ `set -euo pipefail` IS THE POINT, NOT BOILERPLATE.
 *
 *  `deploy-prod.sh` runs with those options and SOURCES the library, so that is
 *  the universe the guards actually execute in. The first version of this gate
 *  used a bare `bash -c` and therefore proved every refusal MESSAGE in a shell
 *  mode production does not use: under `set -e`, a failing `var=$(cmd)` exits
 *  the shell on the spot, so the refusals would have been silent in the one
 *  place they matter. Measured before it was fixed —
 *
 *    set -euo pipefail; f(){ local v; v=$(docker inspect … nope); echo REACHED; }; f
 *    -> exit 1, "REACHED" never printed
 *
 *  Found by refuting this gate, not by running it. A well-chosen fixture in the
 *  wrong universe is this house's nastiest recorded shape, and a shell option
 *  is exactly the kind of universe nobody thinks to enumerate. */
function cut(services: string[], slug = 'demo', stamp = '20260816'): { code: number; out: string } {
  const script = `set -euo pipefail; . "${LIB}"; rollback_tag_cut ${[slug, stamp, ...services].map((a) => `'${a}'`).join(' ')}`;
  try {
    const out = execFileSync('bash', ['-c', script], {
      encoding: 'utf8',
      env: { ...process.env, FAKE_STATE: join(TMP, 'state'), DOCKER: join(TMP, 'docker') },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    return { code: 0, out };
  } catch (e) {
    const err = e as { status?: number; stdout?: string; stderr?: string };
    return { code: err.status ?? -1, out: `${err.stdout ?? ''}${err.stderr ?? ''}` };
  }
}

/** Drop whole-line shell comments so an ordering or presence claim is made
 *  about CODE. Deliberately conservative: it does not try to strip trailing
 *  comments, because a `#` inside a string would then eat real code — and a
 *  stripper that removes too much is a worse instrument than one that removes
 *  too little. Positive-controlled by the arm below, which asserts the tokens
 *  survive stripping. */
function codeOnly(src: string): string {
  return src
    .split('\n')
    .map((l) => (/^\s*#/.test(l) ? '' : l))
    .join('\n');
}

function tagsWritten(): string[] {
  const p = join(TMP, 'state', 'tags');
  return existsSync(p) ? readFileSync(p, 'utf8').split('\n').filter(Boolean) : [];
}

function slugFor(declBody: string | null, fallback = 'fallback-sha'): string {
  const decl = declBody === null ? join(TMP, 'does-not-exist.md') : join(TMP, `decl-${Math.abs(hash(declBody))}.md`);
  if (declBody !== null) writeFileSync(decl, declBody);
  return execFileSync('bash', ['-c', `set -euo pipefail; . "${LIB}"; rollback_tag_slug '${decl}' '${fallback}'`], {
    encoding: 'utf8',
    env: { ...process.env, DOCKER: 'true' },
    stdio: ['ignore', 'pipe', 'ignore'],
  });
}
function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return h;
}

beforeAll(() => {
  TMP = mkdtempSync(join(tmpdir(), 'f9-rollback-tag-'));
  writeFileSync(join(TMP, 'docker'), FAKE_DOCKER);
  chmodSync(join(TMP, 'docker'), 0o755);
});
afterAll(() => {
  // ⚠️ THIS USED TO BE A DELIBERATE NO-OP — "left for the OS. Nothing here is
  // clinical and nothing is outside $TMPDIR." Both halves of that are still
  // TRUE, and it was still the wrong call, for a reason outside this file:
  //
  // the FOUNDATION loop runs unattended and `shred`/`rm` are DENIED to it by
  // design, so every run of this gate mints a directory that the only actor
  // present is structurally incapable of reaping. Session 04 filed it against
  // its own gate after counting NINE of them; a tenth appeared during session
  // 05's unit run, which is the growth rate stated as a measurement.
  //
  // "Ephemeral in CI" is true and it is not the environment that matters —
  // the developer box and the loop's own host keep them forever. A test that
  // cleans up after itself is cheaper than a close-out contract that has to
  // name what it could not delete.
  if (TMP) rmSync(TMP, { recursive: true, force: true });
});

describe('F9 — the library exists and the deploy is wired to it', () => {
  it('scripts/lib/rollback-tag.sh is present', () => {
    expect(existsSync(LIB)).toBe(true);
  });

  // ⚠️ THE WHOLE POINT IS THE WIRING, NOT THE LIBRARY. A perfectly correct
  // rollback-tag lib that no deploy calls protects exactly nothing — F4's own
  // defect (`updateTemplateTwinMappings` shipped with no caller) one file over.
  // ⚠️ THE FIRST VERSION OF THIS ARM ASSERTED `lib/rollback-tag.sh`, AND THE
  // ONLY PLACE THAT STRING APPEARS IS THE `# shellcheck source=` COMMENT. It
  // passed on PROSE. The stripper caught it on its first run — the substring
  // trap's fifth sighting, found by the control added for its own sake.
  // The real code says `…/lib" …)/rollback-tag.sh` and `. "$TAG_LIB"`.
  it('deploy-prod.sh sources it and calls rollback_tag_cut — in CODE, not prose', () => {
    const src = codeOnly(readFileSync(DEPLOY, 'utf8'));
    expect(src).toContain('rollback-tag.sh');
    expect(src).toContain('. "$TAG_LIB"');
    expect(src).toContain('rollback_tag_cut');
  });

  // ⚠️ THE STRIPPER'S OWN POSITIVE CONTROL. A `codeOnly` that returned '' would
  // make every arm above vacuous while looking stricter than the originals —
  // the wrong-quantity failure arriving inside the fix for the substring one.
  // So: it must remove a comment, and it must NOT remove the code beside it.
  it('codeOnly removes comments and keeps code (the stripper is controlled)', () => {
    const sample = '# rollback_tag_cut in a comment\nrollback_tag_cut real\n   # indented comment\n';
    const out = codeOnly(sample);
    expect(out).toContain('rollback_tag_cut real');
    expect(out).not.toContain('in a comment');
    expect(out).not.toContain('indented comment');
    // and on the real file it must not have eaten the thing under test
    expect(codeOnly(readFileSync(DEPLOY, 'utf8'))).toContain('rollback_tag_cut');
  });

  // ⚠️ ORDER IS THE CLAIM. Tagging AFTER the build would tag an image that is
  // no longer the outgoing one on a re-run, and tagging after `up -d` would be
  // useless. Assert it happens before the first thing that changes state.
  //
  // ⚠️ COMMENTS ARE STRIPPED FIRST, AND THAT IS THE SUBSTRING TRAP, NOT
  // fastidiousness. `deploy-prod.sh` is a heavily commented file whose prose
  // names the very tokens this arm searches for; a future comment mentioning
  // `rollback_tag_cut` above the call would move `indexOf` onto the COMMENT and
  // the ordering assertion would silently measure prose instead of code. This
  // repo has paid for that shape four times.
  it('cuts the tag BEFORE the backup, the build and the recreate', () => {
    const src = codeOnly(readFileSync(DEPLOY, 'utf8'));
    const tagAt = src.indexOf('rollback_tag_cut');
    expect(tagAt, 'rollback_tag_cut must appear in deploy-prod.sh CODE').toBeGreaterThan(-1);
    for (const later of ['pre-deploy backup', 'docker compose build db-migrate', 'docker compose up -d']) {
      const at = src.indexOf(later);
      expect(at, `'${later}' must appear in deploy-prod.sh`).toBeGreaterThan(-1);
      expect(tagAt, `rollback_tag_cut must precede '${later}'`).toBeLessThan(at);
    }
  });

  // The three services the deploy actually replaces. gotenberg is rebuilt AND
  // recreated at step 5b, so a rollback set without it restores an app against
  // a converter from a different build — the font-substitution failure that
  // step exists to prevent.
  it('names every service the deploy replaces — app, worker AND gotenberg', () => {
    const src = codeOnly(readFileSync(DEPLOY, 'utf8'));
    const call = src.slice(src.indexOf('rollback_tag_cut'), src.indexOf('rollback_tag_cut') + 300);
    for (const svc of ['transcribe-md', 'transcribe-md-worker', 'gotenberg']) {
      expect(call, `rollback_tag_cut must name ${svc}`).toContain(svc);
    }
  });
});

describe('F9 — THE HAPPY PATH (the half that is usually broken)', () => {
  it('a normal run exits 0 and reports the COUNT, not just the absence of errors', () => {
    resetState();
    const r = cut(['transcribe-md', 'transcribe-md-worker']);
    expect(r.code).toBe(0);
    expect(r.out).toContain('2 rollback tag(s) cut and verified');
  });

  it('the tag points at the RUNNING image, for an untagged Config.Image', () => {
    resetState();
    cut(['transcribe-md']);
    expect(tagsWritten()).toContain(`meddoc-pro-transcribe-md:pre-demo-20260816|${APP_IMG}`);
  });

  it("strips a ':latest' from Config.Image rather than tagging 'repo:latest:pre-…'", () => {
    resetState();
    cut(['transcribe-md-worker']);
    expect(tagsWritten()).toContain(`meddoc-pro-transcribe-md-worker:pre-demo-20260816|${WRK_IMG}`);
  });

  // Idempotence is not a nicety: a deploy that aborts at step 4 must be
  // re-runnable, and the second run must not trip the never-re-point refusal.
  it('re-running is idempotent — no second tag, still exit 0', () => {
    resetState();
    cut(['transcribe-md']);
    const r = cut(['transcribe-md']);
    expect(r.code).toBe(0);
    expect(tagsWritten().filter((l) => l.startsWith('meddoc-pro-transcribe-md:pre-demo-'))).toHaveLength(1);
  });
});

describe('F9 — THE REFUSALS, and none of them may mutate on the way out', () => {
  it('REFUSES when a named service has no running container', () => {
    resetState('no_worker_container');
    const r = cut(['transcribe-md', 'transcribe-md-worker']);
    expect(r.code).not.toBe(0);
    expect(r.out).toContain('no running container');
  });

  // ⚠️ SACRED BY CANON: a `pre-*` tag is never deleted and never re-pointed.
  // Silently overwriting one destroys the only reference to an older
  // production image — the exact loss the tag exists to prevent.
  it('REFUSES when the tag already exists on a DIFFERENT image, and tags nothing', () => {
    resetState('none', ['meddoc-pro-transcribe-md:pre-demo-20260816', OTHER_IMG]);
    const r = cut(['transcribe-md']);
    expect(r.code).not.toBe(0);
    expect(r.out).toContain('points somewhere ELSE');
    expect(tagsWritten()).toHaveLength(0);
  });

  it('REFUSES when docker tag fails', () => {
    resetState('tag_fails');
    const r = cut(['transcribe-md']);
    expect(r.code).not.toBe(0);
  });

  // ⚠️ THE ONE AN EXIT CODE CANNOT SEE, and the reason the verify step exists.
  // `docker tag` returns 0 and the tag does not resolve. Without the re-read
  // this is a silent false green — precisely the shape retire-branch.sh shipped.
  it('REFUSES when docker tag exits 0 but the tag does not resolve', () => {
    resetState('tag_lies');
    const r = cut(['transcribe-md']);
    expect(r.code).not.toBe(0);
    expect(r.out).toContain('does NOT resolve');
  });

  it('REFUSES a malformed image id', () => {
    resetState('bad_image_id');
    const r = cut(['transcribe-md']);
    expect(r.code).not.toBe(0);
    expect(r.out).toContain('usable image id');
  });

  it('REFUSES a container created from a bare image id — nothing to hang a tag on', () => {
    resetState('bare_config_image');
    const r = cut(['transcribe-md']);
    expect(r.code).not.toBe(0);
    expect(r.out).toContain('untagged image');
  });

  // ⚠️ AMBIGUITY IS A REFUSAL, NOT A `head -1`. A scaled service returns more
  // than one container and picking the first is a guessed rollback target.
  it('REFUSES when a service has MORE THAN ONE running container', () => {
    resetState();
    writeFileSync(
      join(TMP, 'state', 'containers'),
      'transcribe-md|cid-app\ntranscribe-md|cid-app2\n',
    );
    const r = cut(['transcribe-md']);
    expect(r.code).not.toBe(0);
    expect(r.out).toContain('MORE THAN ONE running container');
    expect(tagsWritten()).toHaveLength(0);
  });

  // A digest reference has no mutable tag to derive a name from. It already
  // failed closed via `docker tag`, but with a message that named the symptom.
  it('REFUSES a container created from a DIGEST reference, naming the cause', () => {
    resetState();
    writeFileSync(join(TMP, 'state', 'cconfig'), `cid-app|meddoc-pro-transcribe-md@${APP_IMG}\n`);
    const r = cut(['transcribe-md']);
    expect(r.code).not.toBe(0);
    expect(r.out).toContain('DIGEST reference');
  });

  // ⚠️ THE EMPTINESS FAILURE THIS HOUSE NAMES ON SIGHT. A run over an empty
  // set finds nothing wrong and protects nothing, and it would report success.
  it('REFUSES an empty service list', () => {
    resetState();
    const r = cut([]);
    expect(r.code).not.toBe(0);
    expect(r.out).toContain('no services named');
  });
});

describe('F9 — the slug', () => {
  it('uses a declared rollback-slug', () => {
    expect(slugFor('rollback-slug: f5b-door\n')).toBe('f5b-door');
  });

  it('falls back to the sha when the declaration names none', () => {
    expect(slugFor('no slug here\n')).toBe('fallback-sha');
  });

  // Falling back rather than refusing is deliberate: the tag must ALWAYS be
  // cut, and a bad label is not a reason to leave production without a
  // rollback target. Refusing here would make F9 a new way for a deploy to die.
  it('falls back rather than refusing on a malformed slug', () => {
    expect(slugFor('rollback-slug: Bad Slug!!\n')).toBe('fallback-sha');
  });

  it('falls back when the declaration does not exist', () => {
    expect(slugFor(null)).toBe('fallback-sha');
  });

  // ⚠️ THE SUBSTRING TRAP, FIFTH SIGHTING OF THE FAMILY. A declaration is prose,
  // and prose is exactly where the token you are grepping for is guaranteed to
  // appear. Only a LINE-ANCHORED match may win.
  it('is not fooled by prose that mentions "rollback-slug:" mid-sentence', () => {
    expect(slugFor('We follow the rollback-slug: convention here.\nrollback-slug: real-one\n')).toBe('real-one');
  });
});
