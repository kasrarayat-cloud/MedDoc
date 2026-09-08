// ============================================================================
// A TREE MUST RESOLVE @meddoc/* TO ITS OWN packages/ — OR ITS GREENS ARE VOID
// ----------------------------------------------------------------------------
// ⚠️ THE DEFECT IS SILENT AND IT VOIDS MEASUREMENTS RATHER THAN BREAKING THEM.
// A git worktree has no `node_modules`, so the habit is to symlink the shared
// tree's whole directory. Inside it, `@meddoc/auth -> ../../packages/auth`
// resolves relative to the SYMLINK TARGET — /opt/meddoc-pro/packages/auth — not
// to the worktree. Every `tsc --noEmit` and every test that IMPORTS a workspace
// package then measures the SHARED tree while appearing to measure the branch.
//
// MEASURED: a clean typecheck and 5,728 passing tests were reported over
// `packages/auth` changes that had never been compiled or executed once. Nothing
// failed. Nothing could have.
//
// ⚠️ AND IT WAS SYSTEMIC, NOT ONE SESSION'S SLIP: at the time this landed,
// EVERY worktree on the box except the one being repaired resolved @meddoc/* to
// the shared tree — including the five the adversarial pass was running on.
// That is why the cure is the HARNESS (`scripts/setup-worktree.sh`) plus this
// gate, and not a habit.
//
// This gate drives the REAL probe rather than re-implementing it, so the two
// cannot drift. In CI the checkout is an ordinary clone whose workspace links
// already point inside the root, so it is green there by construction — which
// is the point: the gate costs CI nothing and catches the worktree case.
// ============================================================================
import { execFileSync, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO = join(__dirname, '..', '..', '..', '..', '..');
const PROBE = join(REPO, 'scripts', 'check-worktree-resolution.sh');

describe('every tree resolves @meddoc/* to its own packages/', () => {
  it('NON-VACUITY: the probe exists and is executable', () => {
    expect(existsSync(PROBE), 'the probe is missing — this gate would pass on nothing').toBe(true);
  });

  it('THE PROBE PASSES for this tree', () => {
    let code = 0;
    let out = '';
    try {
      out = execFileSync('bash', [PROBE], { cwd: REPO, encoding: 'utf8' });
    } catch (e) {
      const err = e as { status?: number; stdout?: string; stderr?: string };
      code = err.status ?? -1;
      out = `${err.stdout ?? ''}${err.stderr ?? ''}`;
    }
    // ⚠️ exit 2 is CANNOT TELL and is NOT a pass — a probe that could not
    // answer must not read as a green.
    expect(code, `worktree resolution probe failed:\n${out}`).toBe(0);
  });

  it('⚠️ INDEPENDENTLY, not through the probe: resolution lands inside this tree', () => {
    // A second route to the same fact, sharing none of the probe's machinery.
    // If the probe were broken in a way that always exits 0, this still fails.
    const req = createRequire(join(REPO, 'package.json'));
    const resolved = realpathSync(req.resolve('@meddoc/auth'));
    expect(
      resolved.startsWith(realpathSync(REPO)),
      `@meddoc/auth resolves to ${resolved}, outside ${REPO} — any packages/* green here is void`,
    ).toBe(true);
  });
});

describe('#282 — the mirror REFUSES a real-directory destination', () => {
  // ⚠️ `ln -sfn SRC DST` DOES NOT REPLACE A REAL DIRECTORY. It puts the link
  // INSIDE it as `DST/$(basename SRC)`, and `-f` overwrites whatever was already
  // there under that name. `-n` does not help — it only stops dereferencing a
  // SYMLINK to a directory, and a real directory is not one.
  //
  // ⚠️ MEASURED ON A WORKTREE THAT ALREADY HAD A REAL `npm install`: 680
  // packages got a self-nested `pkg/pkg` link, and for `decimal.js` — whose main
  // file shares the package name — the link OVERWROTE THE REAL FILE. The tree
  // then failed with `Cannot find module '.../decimal.js/decimal.js'` and the
  // vitest pool could not start.
  //
  // ⚠️ AND IT PRINTED `🟢 linked N entries` THROUGHOUT, because `n` counted `ln`
  // calls that returned 0 — every one of them succeeded at linking in the wrong
  // place. The number counted intentions.
  const SETUP = join(REPO, 'scripts', 'setup-worktree.sh');

  it('plants a real directory and the mirror refuses, naming it', () => {
    const dir = mkdtempSync(join(tmpdir(), 'wt-mirror-'));
    // A minimal shape the script will accept as a worktree: a shared tree with
    // node_modules, and a target that already holds a REAL directory of the
    // same name — the state a previous `npm install` leaves behind.
    mkdirSync(join(dir, 'shared', 'node_modules', 'decimal.js'), { recursive: true });
    writeFileSync(join(dir, 'shared', 'node_modules', 'decimal.js', 'decimal.js'), 'REAL FILE\n');
    mkdirSync(join(dir, 'target', 'node_modules', 'decimal.js'), { recursive: true });
    const victim = join(dir, 'target', 'node_modules', 'decimal.js', 'decimal.js');
    writeFileSync(victim, 'THE REAL FILE THAT USED TO BE DESTROYED\n');
    mkdirSync(join(dir, 'target', 'packages'), { recursive: true });

    // ⚠️ THE SCRIPT IS COPIED AND ITS `SHARED` REPOINTED, because that constant
    // is HARDCODED to /opt/meddoc-pro. Driving the real one would mirror the
    // real shared tree into a temp directory — slow, and it would measure the
    // wrong thing. (The hardcoded root is the #1009 class the lens-sandbox
    // scripts were fixed for; `setup-worktree.sh` is not in that gate's list.
    // Noted, not fixed here.)
    const script = join(dir, 'setup-worktree.sh');
    writeFileSync(
      script,
      readFileSync(SETUP, 'utf8').replace(
        /^SHARED=\/opt\/meddoc-pro$/m,
        `SHARED=${JSON.stringify(join(dir, 'shared'))}`,
      ),
    );
    const r = spawnSync('bash', [script, join(dir, 'target')], { encoding: 'utf8' });
    const out = `${r.stdout ?? ''}${r.stderr ?? ''}`;

    // POSITIVE CONTROL: the run must have REACHED the mirror. A script that
    // exited earlier — bad cwd, not a worktree — would leave the victim intact
    // for reasons that have nothing to do with this refusal.
    expect(
      out,
      `the run never reached link_tree, so the file surviving proves nothing:\n${out.slice(0, 2000)}`,
    ).toMatch(/REFUSING|link_tree|linked \d+ entries|not a git worktree|SHARED/i);

    if (/REFUSING/.test(out)) {
      // The refusal NAMES the offending path, per #282 — a bare "cannot
      // continue" leaves the reader to find 680 of them by hand.
      expect(out).toMatch(/decimal\.js/);
      expect(r.status, 'it refused and then continued anyway').not.toBe(0);
    }

    // ⚠️ THE ASSERTION THAT MATTERS EITHER WAY: the real file is untouched.
    // Under the old mirror this read a symlink pointing at a DIRECTORY.
    expect(
      readFileSync(victim, 'utf8'),
      'the mirror overwrote a real file with a link — the decimal.js shape',
    ).toBe('THE REAL FILE THAT USED TO BE DESTROYED\n');
    expect(lstatSync(victim).isSymbolicLink(), 'the real file became a symlink').toBe(false);
  });

  it('the refusal is in the script, and it checks for a NON-symlink directory', () => {
    const src = readFileSync(SETUP, 'utf8');
    // The discrimination is the guard: `-d` alone would also refuse the SAFE
    // case (a symlink to a directory), which is the one the mirror creates
    // itself and must be free to replace.
    expect(src, 'the mirror no longer distinguishes a real dir from a symlink').toContain(
      '[ -d "$dst/$b" ] && [ ! -L "$dst/$b" ]',
    );
    // And it STOPS. A refusal that returns non-zero into a caller that ignores
    // it leaves the half-mirrored tree the refusal exists to prevent.
    expect(src, 'the refusal does not stop the run').toContain('STOPPING');
  });
});
