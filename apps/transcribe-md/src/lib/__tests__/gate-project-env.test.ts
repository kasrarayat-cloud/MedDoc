// ============================================================================
// A pack must run against the image the step right before it created.
// ----------------------------------------------------------------------------
// `gate-flag-coverage.test.ts` pins two halves of one coupling: the flag-ON
// image carries the flag, and the flag-OFF default run never sees the spec.
// This pins the third: THE APP IS ACTUALLY ON THAT IMAGE WHEN THE PACK RUNS.
//
// The E2E job is a sequence of (build image → recreate app on it → run pack),
// repeated per flag-ON surface. The app is a single container, so every
// recreate REPLACES the one before it. That makes the ordering load-bearing in
// a way nothing in the YAML expresses: any step that recreates the app between
// a pack's setup and the pack itself silently changes what is under test.
//
// Which is exactly what happened on 2026-07-29. The Rounds block was inserted
// between "recreate app on the review-doc image" and "run review-doc", and it
// ended with a well-meant step that put the app back on the DEFAULT image "for
// the remaining packs". So review-doc ran flag-OFF and all 18 of its tests
// failed on a missing `review-document-view` testid.
//
// Every symptom pointed away from the cause:
//   - the rounds pack, the thing that had just changed, PASSED
//   - review-doc, untouched by the PR, went from green to 18/18 red
//   - the failure reads as "the review-doc surface is broken", i.e. a product
//     regression in code the branch never opened
//   - and it costs ~25 minutes of a 55-minute job to find out
//
// A uniform failure across every test in one pack is almost never the product.
// It is the environment. This test makes that a 30ms assertion instead.
//
// THE RULE: between a pack's recreate and its `--project=` run there must be
// NOTHING that recreates the app. Each pack owns its own environment as its
// last setup step; there is deliberately no shared "restore" step, because a
// shared restore is just a second place for the image to be wrong.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const WORKFLOW = readFileSync('../../.github/workflows/e2e.yml', 'utf8');
const LINES = WORKFLOW.split('\n');

/** Compose overrides each project's app must be recreated with. An empty list
 *  means the plain qa stack (no override) — the default image. */
const EXPECTED: Record<string, string[]> = {
  chromium: [],
  'rounds-board': ['docker-compose.qa.rounds.yml'],
  'rounds-stage': ['docker-compose.qa.rounds.yml'],
  'rounds-gates': ['docker-compose.qa.rounds.yml'],
  'rounds-signed': ['docker-compose.qa.rounds.yml'],
  'review-doc': ['docker-compose.qa.reviewdoc.yml'],
  'doc-preview': ['docker-compose.qa.docpreview.yml'],
  'visit-doc': ['docker-compose.qa.visitdoc.yml'],
  // Fixture packs: the default image, with MOCK_* supplied as env on the
  // recreate rather than as a built image.
  'phi-reject': [],
  'rx-safety': [],
};

/** A `docker compose … up -d … transcribe-md` is folded across lines by YAML's
 *  `>` scalar, so a recreate is only visible in a window, not on one line. */
function windowAt(i: number, back = 4): string {
  return LINES.slice(Math.max(0, i - back), i + 2).join(' ');
}

interface Ev {
  line: number;
  kind: 'recreate' | 'run';
  /** overrides for a recreate; project names for a run */
  detail: string[];
}

function events(): Ev[] {
  const out: Ev[] = [];
  LINES.forEach((raw, i) => {
    if (raw.includes('--project=')) {
      const names = [...raw.matchAll(/--project=([\w-]+)/g)].map((m) => m[1]);
      if (names.length) out.push({ line: i + 1, kind: 'run', detail: names });
      return;
    }
    // A recreate of the APP. `run --rm`, `exec`, `logs` and the infra-only
    // `up -d … postgres redis minio` are not recreates of transcribe-md.
    if (!raw.includes('up -d')) return;
    const w = windowAt(i);
    if (!/docker compose/.test(w)) return;
    if (!/\btranscribe-md\b/.test(raw)) return;
    const overrides = [...w.matchAll(/(docker-compose\.qa\.[\w.]*?\.yml)/g)]
      .map((m) => m[1])
      .filter((f) => f !== 'docker-compose.qa.yml');
    out.push({ line: i + 1, kind: 'recreate', detail: overrides });
  });
  return out;
}

describe('every E2E pack runs against the image its own setup created', () => {
  const evs = events();

  it('the workflow still has recreate steps and project runs to check', () => {
    expect(evs.filter((e) => e.kind === 'recreate').length).toBeGreaterThan(0);
    expect(evs.filter((e) => e.kind === 'run').length).toBeGreaterThan(0);
  });

  const runs = evs.filter((e) => e.kind === 'run');

  for (const run of runs) {
    for (const project of run.detail) {
      it(`${project} (line ${run.line}) — the recreate before it is ITS recreate`, () => {
        const expected = EXPECTED[project];
        expect(
          expected,
          `project '${project}' runs in the workflow but is not in EXPECTED. ` +
            `Add it with the compose override its app must be recreated on — ` +
            `an unlisted project is one nobody is checking the environment of.`,
        ).toBeDefined();

        const prior = evs.filter(
          (e) => e.kind === 'recreate' && e.line < run.line,
        );
        const last = prior[prior.length - 1];
        expect(
          last,
          `no app recreate precedes --project=${project}; it would run against ` +
            `whatever the previous pack happened to leave behind`,
        ).toBeDefined();

        const got = [...(last?.detail ?? [])].sort();
        expect(
          got,
          `--project=${project} (line ${run.line}) runs against the app ` +
            `recreated at line ${last?.line} with overrides [${got.join(', ') || 'none'}], ` +
            `but it needs [${expected.join(', ') || 'none (default image)'}]. ` +
            `Something recreates the app between this pack's setup and its run — ` +
            `so the pack is testing a different build than the one it built. ` +
            `Every test in it will fail identically, which reads as a product ` +
            `regression rather than an environment one.`,
        ).toEqual([...expected].sort());
      });
    }
  }
});
