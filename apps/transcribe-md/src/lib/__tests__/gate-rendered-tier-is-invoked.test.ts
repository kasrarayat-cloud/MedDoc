// ============================================================================
// THE RENDERED TIER IS EXCLUDED FROM THIS SUITE — SO THIS SUITE WATCHES THAT IT
// STILL RUNS SOMEWHERE.
// ----------------------------------------------------------------------------
// `src/**/__rendered__/` proves ruling #117(e) against the REAL Gotenberg /
// LibreOffice sidecar. The `CI` workflow starts no sidecar, so those files are
// excluded from `vitest.config.ts` and run in the `e2e` workflow instead, via
// `vitest.rendered.config.ts`.
//
// ⚠️ THAT EXCLUSION IS THE RISK, AND IT IS THE EXACT SHAPE THIS HOUSE KEEPS
// PAYING FOR: a gate nobody runs is indistinguishable from a gate that passes.
// Nothing about deleting the e2e step would turn anything red. The rendered
// files would still exist, still be correct, still be excluded — and never
// execute again. No test fails, no sweep complains, and the next person to read
// `__rendered__/` reasonably concludes #117(e) is covered.
//
// So the default suite — the one that always runs — asserts the invocation
// exists. This is the watched-set discipline pointed at a WORKFLOW rather than
// a model list: diff what the gate WATCHES against what the ruling NAMES.
//
// ⚠️ WHAT THIS DOES NOT CLAIM. It asserts the step is WIRED, not that it PASSED
// — a workflow file is text, and text cannot tell you a converter was healthy.
// The passing is the e2e run's job. This closes exactly one hole: silent
// retirement.
// ============================================================================
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const REPO_ROOT = resolve(__dirname, '../../../../..');
const E2E_WORKFLOW = resolve(REPO_ROOT, '.github/workflows/e2e.yml');
const RENDERED_CONFIG = 'vitest.rendered.config.ts';
const RENDERED_OVERRIDE = 'docker-compose.qa.rendered.yml';
const RENDERED_SERVICE = 'rendered-tests';

function read(p: string): string {
  return readFileSync(p, 'utf8');
}

/** ⚠️ COMMENTS ARE STRIPPED BEFORE ANY ASSERTION, AND THIS IS THE WHOLE REASON
 *  THIS HELPER EXISTS. The first version of this guard asserted `toContain` over
 *  raw file text, and THREE of its assertions were satisfiable by PROSE —
 *  `docker-compose.qa.rendered.yml` appears in an explanatory comment in
 *  `e2e.yml` one line above the step that uses it, and `converter` and
 *  `vitest.rendered.config.ts` each appear in comments in the override. Deleting
 *  the step and leaving the comment would have kept this guard GREEN.
 *
 *  That is the substring trap this house has now met five times, and a file's
 *  own comments are the one place the words you are grepping for are guaranteed
 *  to appear — doubly so here, where the comments explain the very mechanism
 *  being asserted.
 *
 *  ⚠️ ONLY FULL-LINE COMMENTS ARE STRIPPED, deliberately. Cutting from the first
 *  `//` anywhere would truncate `http://gotenberg:3000` and silently change what
 *  the haystack contains — a fix that introduces the defect it is fixing, one
 *  layer down.
 */
function stripFullLineComments(src: string, marker: '#' | '//'): string {
  return src
    .split('\n')
    .filter((line) => !line.trim().startsWith(marker))
    .join('\n');
}

describe('#117(e) — the rendered tier is actually invoked', () => {
  it('the e2e workflow runs the rendered-tests service', () => {
    const wf = stripFullLineComments(read(E2E_WORKFLOW), '#');

    // ⚠️ POSITIVE CONTROL FIRST. A path that moved, a workflow that was
    // renamed, or a read that silently returned '' would make every assertion
    // below vacuously... fail — but a `toContain` over an empty string failing
    // for the WRONG reason sends the next reader to the wrong place. Establish
    // the haystack is the haystack.
    expect(wf.length, 'e2e.yml read empty — the assertions below would be meaningless').
      toBeGreaterThan(1000);
    expect(wf, 'this is not the e2e workflow').toContain('name: e2e');

    // The override and the service, by exact token. Either one missing means
    // the step cannot run what it claims to.
    expect(
      wf,
      `${RENDERED_OVERRIDE} is not referenced by e2e.yml — the rendered tier has no way to reach the sidecar`
    ).toContain(RENDERED_OVERRIDE);
    expect(
      wf,
      `the '${RENDERED_SERVICE}' service is not invoked by e2e.yml — #117(e) would never execute`
    ).toContain(RENDERED_SERVICE);
  });

  it('the rendered config exists and points at __rendered__', () => {
    const cfg = stripFullLineComments(
      read(resolve(REPO_ROOT, 'apps/transcribe-md', RENDERED_CONFIG)),
      '//'
    );
    expect(cfg).toContain('__rendered__');
  });

  it('the compose override runs THAT config, in the converter network', () => {
    const override = stripFullLineComments(read(resolve(REPO_ROOT, RENDERED_OVERRIDE)), '#');

    expect(override).toContain(RENDERED_SERVICE);
    expect(
      override,
      'the override does not run vitest.rendered.config.ts — it would run some other suite'
    ).toContain(RENDERED_CONFIG);

    // ⚠️ THE NETWORK IS PART OF THE CONTRACT, NOT AN IMPLEMENTATION DETAIL.
    // The sidecar is only reachable from inside `converter`; a future edit that
    // drops this joins the default network and every arm times out looking like
    // a converter fault.
    expect(
      override,
      'the runner must join the internal `converter` network — the sidecar publishes no port'
    ).toContain('converter');
  });

  it('⚠️ the stripper actually strips — the defect this guard shipped with, pinned', () => {
    // ⚠️ THE ASSERTION THAT WOULD HAVE CAUGHT THE ORIGINAL DEFECT, kept as a
    // permanent control. `e2e.yml` genuinely contains the override's filename in
    // BOTH a comment and the live command; if the stripper ever stops working,
    // the arms above quietly go back to being satisfiable by prose and nothing
    // else would say so.
    const raw = read(E2E_WORKFLOW);
    const stripped = stripFullLineComments(raw, '#');

    expect(raw, 'e2e.yml no longer explains itself — has the comment block gone?').toContain(
      '# bound. See docker-compose.qa.rendered.yml.'
    );
    expect(
      stripped,
      'the stripper left a full-line comment in place — every arm above is now prose-satisfiable'
    ).not.toContain('# bound. See docker-compose.qa.rendered.yml.');

    // ...and it must NOT have eaten the real command with it.
    expect(stripped, 'the stripper removed the actual step').toContain(RENDERED_SERVICE);

    // ⚠️ AND IT MUST NOT TRUNCATE MID-LINE. A stripper that cut from the first
    // `//` would take `http://gotenberg:3000` with it.
    const override = stripFullLineComments(read(resolve(REPO_ROOT, RENDERED_OVERRIDE)), '#');
    expect(override, 'mid-line truncation — the in-network URL was eaten').toContain(
      'http://gotenberg:3000'
    );
  });

  it('the default vitest config still EXCLUDES the rendered tier', () => {
    // The other half of the same contract. If someone "fixes" the exclusion,
    // these files land in the `CI` workflow, which has no sidecar — and the
    // fail-closed health check turns every CI run red for an environmental
    // reason. That is a real failure mode with a tempting one-line cause.
    const cfg = stripFullLineComments(
      read(resolve(REPO_ROOT, 'apps/transcribe-md/vitest.config.ts')),
      '//'
    );
    expect(
      cfg,
      'vitest.config.ts no longer excludes __rendered__ — CI has no converter and will fail closed'
    ).toContain('__rendered__');
  });
});
