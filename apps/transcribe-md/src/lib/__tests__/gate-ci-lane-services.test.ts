// ============================================================================
// A JOB WITH FIXED-PORT SERVICE CONTAINERS MAY NOT RIDE THE LIGHT LANE
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
// The rule is therefore asserted, not remembered: service-declaring jobs stay on
// `quillmd-ci`, which serialises. The better fix is dynamic ports
// (`job.services.postgres.ports['5432']`), after which this gate's exemption list
// can shrink to nothing.
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

describe('CI lanes — fixed-port services stay off the shared lane', () => {
  it('parses a populated set of jobs — the arm is not vacuous', () => {
    // Without this, a parser that silently matched nothing would pass every
    // assertion below by having no jobs to judge.
    const all = jobs();
    expect(all.length).toBeGreaterThan(8);
    expect(all.filter((j) => j.lane.includes('self-hosted')).length).toBeGreaterThan(5);
    expect(all.filter((j) => j.services).length).toBeGreaterThan(0);
  });

  it('no job on the LIGHT lane declares service containers', () => {
    const offenders = jobs()
      .filter((j) => j.lane.includes(LIGHT) && j.services)
      .map((j) => `${j.file}:${j.job}`);
    expect(
      offenders,
      'two runners share one box — fixed host ports collide when these run concurrently',
    ).toEqual([]);
  });

  it('every service-declaring job sits on the serialising lane', () => {
    const misplaced = jobs()
      .filter((j) => j.services && !/quillmd-ci\]/.test(j.lane))
      .map((j) => `${j.file}:${j.job} -> ${j.lane.trim()}`);
    expect(misplaced).toEqual([]);
  });
});
