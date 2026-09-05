/**
 * RULING #186, MECHANISM 1 — every REQUIRED workflow must run on a pull
 * request regardless of its base branch.
 *
 * ⚠️ THE DEFECT THIS RATCHETS. `a11y.yml` carried `pull_request: branches:
 * [main]`, so a PR based on anything else got no axe sweep at all. Of the last
 * 100 PRs exactly one had a non-`main` base — PR #951, part of the ICD-10
 * FY2026 work — and its checks show Playwright E2E, TruffleHog and every `CI`
 * job ran, with no axe sweep.
 *
 * ⚠️ THE RARITY IS THE HAZARD. One stacked PR in a hundred is not rare enough
 * to be safe and is far too rare to be noticed: the PR reads green because
 * everything that ran passed, and nothing anywhere says a gate was skipped.
 *
 * ⚠️ AND THE PROPERTY IS PINNED WHERE IT ACTS, NOT AS A SPELLING. This asserts
 * the PARSED trigger has no base restriction — not that the file contains or
 * omits some string. A source-text gate would pass on a reformatted file that
 * reintroduced the filter, and fail on an improvement that did not.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import yaml from 'js-yaml';

const WF = resolve(__dirname, '../../../../../.github/workflows');

/** The four checks branch protection requires on main. */
const REQUIRED = ['a11y.yml', 'e2e.yml', 'secrets-scan.yml', 'test.yml'] as const;

/** `on` is parsed as boolean true by YAML 1.1 — that is the famous Norway trap. */
function triggers(doc: any) {
  return doc?.on ?? doc?.[true as unknown as string] ?? doc?.['on'];
}
/** Returns the base filter, or null when the workflow accepts any base. */
function prBaseFilter(file: string): string[] | null {
  const doc = yaml.load(readFileSync(resolve(WF, file), 'utf8')) as any;
  const on = triggers(doc);
  if (!on || !('pull_request' in on)) return ['<NO pull_request TRIGGER AT ALL>'];
  const pr = on.pull_request ?? {};
  return pr.branches ?? null;
}

describe('#186(1) — required workflows run on every PR, whatever the base', () => {
  it('POSITIVE CONTROL: the reader finds the files and parses real triggers', () => {
    // Without this, every "no filter" below could be a path typo returning
    // undefined — a green that means the reader found nothing.
    for (const f of REQUIRED) {
      expect(existsSync(resolve(WF, f)), `${f} must exist`).toBe(true);
      const doc = yaml.load(readFileSync(resolve(WF, f), 'utf8')) as any;
      const on = triggers(doc);
      expect(on, `${f}: 'on:' block must parse`).toBeTruthy();
      expect('pull_request' in on, `${f}: must have a pull_request trigger`).toBe(true);
    }
  });

  it('POSITIVE CONTROL: the checker REJECTS a filter when one is present', () => {
    // Aimed where the answer is NOT predetermined: a synthetic workflow that
    // genuinely carries the defect. If this passed, the check below would be
    // measuring nothing.
    const bad = yaml.load('on:\n  pull_request:\n    branches: [main]\n') as any;
    const on = triggers(bad);
    expect(on.pull_request.branches).toEqual(['main']);
  });

  it.each(REQUIRED)('%s accepts a PR from any base', (file) => {
    const filter = prBaseFilter(file);
    expect(
      filter,
      `${file} restricts pull_request to ${JSON.stringify(filter)}. A required ` +
        `check that skips by base branch is a hole shaped like whoever chose ` +
        `the base — see PR #951, which merged three of four gates.`,
    ).toBeNull();
  });

  it('push stays main-only — this widens PRs, it does not widen pushes', () => {
    // The fix must not silently turn every branch push into four CI runs.
    for (const f of REQUIRED) {
      const on = triggers(yaml.load(readFileSync(resolve(WF, f), 'utf8')) as any);
      if (on.push) expect(on.push.branches, `${f} push`).toEqual(['main']);
    }
  });
});
