// ============================================================================
// ⚠️ SUPERSEDED 2026-09-12 — self-hosted retired; this gate now FORBIDS a
// self-hosted lane (see the describe block below). The historical rationale is
// KEPT because it explains WHY the shared-box hazard existed and why removing
// the box removes it — the correction is the point.
// ----------------------------------------------------------------------------
// A JOB WITH FIXED-PORT SERVICE CONTAINERS MAY NOT RIDE A SHARED-BOX LANE
// ----------------------------------------------------------------------------
// Both self-hosted runners live on the SAME BOX and share its network namespace.
// A job that binds a fixed host port (5432, 6379) therefore excludes every other
// such job — and before the second runner existed, that exclusion was free,
// because one runner runs one job at a time.
//
// ⚠️ ADDING THE SECOND RUNNER REMOVED AN INVARIANT NOBODY HAD WRITTEN DOWN. The
// light lane can schedule on either runner, so two service-declaring jobs became
// concurrent and collided:
//
//   failed to set up container networking: driver failed programming external
//   connectivity on endpoint ..._pgvectorpgvectorpg16_...
//
// It failed the loop's own F6.5 PR (#903) — a change that touches no CI config at
// all. A capacity fix that breaks unrelated PRs is worse than the queue it cured,
// and the failure names Docker rather than the cause, so it will not diagnose
// itself next time.
//
// ⚠️ AMENDED 2026-09-04 — THE PREDICATE WAS WIDER THAN ITS OWN MECHANISM.
// The hazard this gate exists for is a SHARED NETWORK NAMESPACE, which the header
// above states outright: it is a property of the one self-hosted box, not of
// declaring services. A `ubuntu-latest` job gets its own ephemeral VM, so two
// hosted service-declaring jobs cannot collide on 5432 — they are different
// machines. The original third arm nonetheless matched on `services` ALONE, so
// moving the heavy lane to GitHub-hosted runners (PR #955) failed it with
// `a11y.yml:axe` and `test.yml:test`, both of which are now inherently isolated.
//
// Narrowing the arm to self-hosted lanes is therefore a correction to the WATCHED
// SET, not a loosening: it keeps the gate biting for every job that can actually
// reach the hazard, and stops it reporting a collision that is impossible.
//
// ⚠️ AND THE HONEST CONSEQUENCE, STATED SO NOBODY READS THIS GATE AS EXERCISED:
// as of 2026-09-04 the population arm 3 watches is ZERO — every service-declaring
// job in the tree (`a11y.yml:axe`, `test.yml:test`) now runs hosted. Arm 3 is
// therefore LATENT: it is a correct guard with nothing currently to guard, and it
// passes today by having no members, not by judging any. It RE-ARMS the moment a
// `services:`-declaring job is placed on any `self-hosted` lane — which is exactly
// when the collision above becomes reachable again.
//
// The better fix remains dynamic ports (`job.services.postgres.ports['5432']`),
// after which the shared-box hazard disappears and this gate can be deleted
// outright rather than narrowed again.
// ============================================================================
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const WF = join(__dirname, '..', '..', '..', '..', '..', '.github', 'workflows');
const LIGHT = 'quillmd-ci-light';

/** Jobs, with their runs-on lane and whether they declare service containers. */
function jobs(): { file: string; job: string; lane: string; services: boolean }[] {
  const out: { file: string; job: string; lane: string; services: boolean }[] = [];
  for (const f of readdirSync(WF).filter((n) => n.endsWith('.yml'))) {
    const lines = readFileSync(join(WF, f), 'utf8').split('\n');
    let job = '';
    let lane = '';
    let svc = false;
    const flush = () => {
      if (job) out.push({ file: f, job, lane, services: svc });
    };
    for (const l of lines) {
      const m = /^ {2}([a-z0-9_-]+):\s*$/.exec(l);
      if (m) {
        flush();
        job = m[1];
        lane = '';
        svc = false;
        continue;
      }
      if (/^ {4}runs-on:/.test(l)) lane = l;
      if (/^ {4}services:\s*$/.test(l)) svc = true;
    }
    flush();
  }
  return out;
}

/**
 * ⚠️ THE HAZARD'S POPULATION, NAMED ONCE AND USED BY BOTH ARMS BELOW. A job can
 * only collide on a fixed host port if it SHARES a network namespace with another
 * job — i.e. if it runs on the one self-hosted box. Asking this question in one
 * place means the two arms cannot drift into disagreeing about what the hazard is.
 */
const sharesTheBox = (lane: string) => lane.includes('self-hosted');

// ⚠️ SUPERSEDED 2026-09-12 — THE SELF-HOSTED POOL IS RETIRED (owner directive).
// Every CI lane moved to GitHub-hosted `ubuntu-latest` because the self-hosted
// `quillmd-ci-light` pool blocked the program three times in two days. The
// shared-box hazard this gate managed is now GONE by construction: there is no
// shared box. So the gate is inverted — instead of keeping fixed-port services
// OFF the self-hosted lane, it now forbids ANY job from riding a self-hosted lane
// at all, which is the invariant the migration must keep true. If a `self-hosted`
// lane ever returns, this fails and the shared-box collision (and the outages)
// are back on the table.
describe('CI lanes — the self-hosted pool is retired; every lane is GitHub-hosted', () => {
  it('parses a populated set of jobs — the arm is not vacuous', () => {
    // Without this, a parser that silently matched nothing would pass the
    // assertion below by having no jobs to judge.
    const all = jobs();
    expect(all.length).toBeGreaterThan(8);
    expect(all.filter((j) => j.lane.includes('ubuntu-latest')).length).toBeGreaterThan(5);
    expect(all.filter((j) => j.services).length).toBeGreaterThan(0);
  });

  it('NO job runs on a self-hosted lane — the retirement is enforced', () => {
    const onSelfHosted = jobs()
      .filter((j) => sharesTheBox(j.lane) || j.lane.includes(LIGHT))
      .map((j) => `${j.file}:${j.job} -> ${j.lane.trim()}`);
    expect(
      onSelfHosted,
      'a self-hosted lane returned — the shared-box collision and the runner outages come back with it',
    ).toEqual([]);
  });
});
