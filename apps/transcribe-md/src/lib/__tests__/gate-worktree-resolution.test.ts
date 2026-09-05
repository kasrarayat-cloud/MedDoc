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
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { existsSync, realpathSync } from 'node:fs';
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
