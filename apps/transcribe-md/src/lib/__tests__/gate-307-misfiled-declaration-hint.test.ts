// ============================================================================
// THE HINT THAT EXISTS TO FIND A MISFILED DECLARATION HAD ITS OWN WATCHED-SET
// FAILURE — AND IT WAS FOUND BY WATCHING IT MISS
// ----------------------------------------------------------------------------
// `declaration_resolve` refuses a deploy whose tree no declaration covers, and
// then goes looking for a declaration filed in the wrong place, because that
// error had been made twice in one day with the rule in hand.
//
// ⚠️ IT LOOKED IN ONE DIRECTORY, FOR BASENAMES CONTAINING `decl`. Measured
// 2026-09-09 on this branch: `docs/deploy-declarations/` held ten
// declaration-shaped files that NOTHING IN THIS REPOSITORY READS (the count is
// not the point and it grew again the same afternoon) —
// `grep -rn deploy-declarations` over *.sh/*.ts/*.yml returns only references
// this PR itself created — and not one would have been found, because the word
// "declaration" is in the DIRECTORY name and never in the basenames
// (`307-retire-meddoc-pro-service-20260909.md`, `admin1-seats-20260905.md`).
//
// The refusal fired for real, printed two unrelated files from
// `docs/deploy-reports/`, and stayed silent about the declaration actually
// written for the tree being shipped:
//
//     🔴 REFUSING — no delta declaration covers the tree you are shipping.
//        expected: docs/foundation/deploys/20260909-d96ab444.md
//        ⚠️ BUT THESE LOOK LIKE DECLARATIONS, AND THEY ARE IN THE WRONG PLACE:
//             docs/deploy-reports/decl-f24-slice1-2-20260821T222409Z.md
//             docs/deploy-reports/decl-f5f-f5h-20260821T075139Z.md
//
// ⚠️ A HINT THAT NAMES THE WRONG FILE IS WORSE THAN NO HINT. The operator reads
// "these look like declarations" and concludes theirs is not among them — the
// check answered confidently about the wrong universe. So the search is DERIVED
// from the tree rather than remembered, and it over-matches on purpose: a
// spurious line costs a glance, a missing one costs a deploy.
//
// ⚠️ WHAT THIS GATE DOES NOT ASSERT, SAID PLAINLY: that any particular file is
// in the right place. Choosing the declaration for a deploy names a COMMIT that
// does not exist until the merge, and a malformed name in the gate's own
// directory refuses EVERY deploy from EVERY lane. That is an owner decision.
// This only guarantees the refusal can SEE the candidates.
// ============================================================================
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO = join(process.cwd(), '..', '..');
const LIB = join(REPO, 'scripts', 'lib', 'declaration.sh');

/** A throwaway git repo whose only interesting property is where its
 *  declaration-shaped files live. */
function scratchRepo(files: Record<string, string>): string {
  const dir = mkdtempSync(join(tmpdir(), 'decl-hint-'));
  execFileSync('git', ['init', '-q', '-b', 'main'], { cwd: dir });
  execFileSync('git', ['config', 'user.email', 'gate@example.invalid'], { cwd: dir });
  execFileSync('git', ['config', 'user.name', 'gate'], { cwd: dir });
  execFileSync('git', ['config', 'commit.gpgsign', 'false'], { cwd: dir });
  for (const [rel, body] of Object.entries(files)) {
    const abs = join(dir, rel);
    mkdirSync(join(abs, '..'), { recursive: true });
    writeFileSync(abs, body);
  }
  execFileSync('git', ['add', '-A'], { cwd: dir });
  execFileSync('git', ['commit', '-q', '-m', 'scratch'], { cwd: dir });
  return dir;
}

/** Run the SHIPPED resolver against that repo and return everything it said. */
function resolveIn(dir: string): { out: string; code: number } {
  try {
    const out = execFileSync(
      'bash',
      ['-c', `source ${JSON.stringify(LIB)}; declaration_resolve docs/foundation/deploys`],
      { cwd: dir, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] },
    );
    return { out, code: 0 };
  } catch (e) {
    const err = e as { stdout?: string; stderr?: string; status?: number };
    return { out: `${err.stdout ?? ''}${err.stderr ?? ''}`, code: err.status ?? -1 };
  }
}

const KEEP = { 'docs/foundation/deploys/README.md': 'the gate reads this directory\n' };

describe('#307 — the misfiled-declaration hint can see the directory declarations actually land in', () => {
  it('names a declaration filed under docs/deploy-declarations/', () => {
    // ⚠️ THE FILENAME DELIBERATELY CONTAINS NO `decl`. That is the exact shape
    // the old glob was blind to, and the reason this is a behavioural test
    // rather than a grep: the signal is in the PATH.
    const dir = scratchRepo({
      ...KEEP,
      'docs/deploy-declarations/admin1-seats-20260905.md': '# a real declaration\n',
    });
    const { out, code } = resolveIn(dir);
    expect(code).not.toBe(0); // nothing covers the tree — the refusal path
    expect(out).toContain('WRONG PLACE');
    expect(out).toContain('docs/deploy-declarations/admin1-seats-20260905.md');
  });

  it('still names one filed under docs/deploy-reports/ — the case that motivated the hint', () => {
    const dir = scratchRepo({
      ...KEEP,
      'docs/deploy-reports/decl-something-20260821T222409Z.md': '# evidence dir\n',
    });
    const { out } = resolveIn(dir);
    expect(out).toContain('WRONG PLACE');
    expect(out).toContain('docs/deploy-reports/decl-something-20260821T222409Z.md');
  });

  // ── CONTROLS ──────────────────────────────────────────────────────────────

  it('POSITIVE CONTROL — with no candidate anywhere it stays silent AND still finishes', () => {
    // ⚠️ TWO CLAIMS IN ONE ARM, AND THE SECOND IS THE INTERESTING ONE. The
    // search must not fire on an empty tree (or "WRONG PLACE" would be noise
    // that proves nothing above), and the function must REACH ITS LAST LINE.
    // Reaching the end is not free: this is the refusal path, the one that only
    // runs when something is already wrong, and a search that exits non-zero
    // there truncates the message that tells the operator what to write.
    const dir = scratchRepo({ ...KEEP, 'docs/notes/unrelated.md': 'nothing to see\n' });
    const { out } = resolveIn(dir);
    expect(out).toContain('REFUSING — no delta declaration covers the tree');
    expect(out).not.toContain('WRONG PLACE');
    expect(out).toContain('Nothing has been changed.');
  });

  it('DISCRIMINATION CONTROL — the gate\'s own directory is never reported as misfiled', () => {
    // A file sitting correctly in docs/foundation/deploys/ must not be offered
    // back to the operator as "in the wrong place".
    //
    // ⚠️ THE NAME HERE IS LOAD-BEARING AND THE FIRST DRAFT GOT IT WRONG, WHICH
    // IS WORTH RECORDING. `20260101-declaration-note.md` is not `<date>-<sha>`,
    // so the resolver refused with exit 2 (CANNOT TELL) before it ever reached
    // the misfiled search — a real behaviour, and the one
    // `gate-declaration-filenames` exists for: ONE badly-named file in that
    // directory blocks EVERY deploy from EVERY lane. The control needs a
    // well-formed declaration naming a commit that is simply not an ancestor.
    const dir = scratchRepo({
      ...KEEP,
      'docs/foundation/deploys/20260101-deadbee.md': '# correctly filed\n',
      'docs/foundation/mutations/b7-backfill-declaration.md': '# the OTHER gate\n',
    });
    const { out } = resolveIn(dir);
    expect(out).toContain('REFUSING — no delta declaration covers the tree');
    expect(out).not.toContain('20260101-deadbee.md');
    expect(out).not.toContain('docs/foundation/mutations/');
  });
});
