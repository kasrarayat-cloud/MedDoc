// ============================================================================
// Every shipped workflow file must be valid YAML.
// ----------------------------------------------------------------------------
// ⚠️ WRITTEN BECAUSE C1-f BROKE THE REQUIRED E2E GATE WITH A STEP NAME, AND THE
// FAILURE DID NOT LOOK LIKE A SYNTAX ERROR.
//
// The edit was cosmetic — renaming a step so it stopped claiming it ran only
// C1-d's tests. The new name contained `C1-d/e/f: auth, …`, and a COLON
// FOLLOWED BY A SPACE inside an unquoted YAML scalar starts a mapping. The file
// stopped parsing at that line.
//
// What made it dangerous is how it presented. GitHub could not read the
// workflow's own `name:`, so the run was listed as `.github/workflows/e2e.yml`
// rather than `e2e`; it failed instantly with no job log to fetch; and — the
// part that matters — the check-run `Playwright E2E (transcribe-md)` was NEVER
// CREATED. The PR showed **six checks, all green**. A reader polling "are any
// checks pending?" gets "no", and "did they pass?" gets "yes". The required
// gate had simply vanished from the set being asked about.
//
// That is this project's most-repeated defect wearing yet another face: an
// answer about a set whose boundary was never established. Rule 2a's own
// corollary already says a `cancelled` run is absence of evidence; a run that
// never registers a check is worse, because nothing appears to be missing.
//
// Same shape and same cure as `gate-css-parses`, which exists because a comment
// edit broke an image build ten minutes in: the check is trivial, runs in
// milliseconds, and names the file and line.
// ============================================================================

import { createRequire } from 'node:module';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

/** ⚠️ RESOLVED AT RUNTIME, AND MISSING IS A FAILURE — NEVER A SKIP.
 *
 *  `js-yaml` is present in this tree only as a TRANSITIVE dependency (eslint →
 *  @eslint/eslintrc), so it is not a promise anyone made to this file. The
 *  tempting shapes are both wrong: importing it directly makes the guard die on
 *  an unrelated lockfile change with a module-resolution stack that says
 *  nothing about workflows, and `try { … } catch { return }` makes it VANISH —
 *  a guard that silently stops running is the defect this file exists to catch,
 *  in the guard itself.
 *
 *  So: resolve it here, and if it is gone say exactly that and what to do. */
const req = createRequire(__filename);
function loadYaml(): (src: string) => unknown {
  try {
    return (req('js-yaml') as { load: (s: string) => unknown }).load;
  } catch {
    throw new Error(
      'the YAML parser is not installed, so this guard cannot check anything. ' +
        'js-yaml reaches this tree transitively via eslint; if that changed, ' +
        'add it as an explicit devDependency rather than deleting this test.',
    );
  }
}
const parse = loadYaml();

/** Repo root, from `apps/transcribe-md` (the vitest CWD). */
const WORKFLOW_DIR = '../../.github/workflows';

function workflowFiles(): string[] {
  return readdirSync(WORKFLOW_DIR)
    .filter((f) => /\.ya?ml$/.test(f))
    .map((f) => join(WORKFLOW_DIR, f))
    .sort();
}

const FILES = workflowFiles();

describe('every workflow file is valid YAML', () => {
  it('the traversal found the workflows — positive control', () => {
    // A walk that returns [] would make the assertion below pass by covering
    // nothing, which is the failure mode this whole file is about.
    expect(FILES.length, 'no workflow files found — the traversal is wrong').toBeGreaterThan(3);
    expect(
      FILES.some((f) => f.endsWith('e2e.yml')),
      'e2e.yml — the required gate — is not in the derived set',
    ).toBe(true);
  });

  it('each one parses, and the message names the file', () => {
    const broken: string[] = [];
    for (const f of FILES) {
      try {
        const doc = parse(readFileSync(f, 'utf8'));
        // A file that parses to a scalar or null is not a workflow. Without
        // this, a file emptied to `#comment only` would pass.
        if (doc === null || typeof doc !== 'object') {
          broken.push(`${f}: parsed to ${doc === null ? 'null' : typeof doc}, not a mapping`);
          continue;
        }
        if (!('jobs' in doc)) broken.push(`${f}: parsed, but declares no \`jobs\``);
      } catch (e) {
        broken.push(`${f}: ${(e as Error).message.split('\n')[0]}`);
      }
    }
    expect(
      broken,
      'a workflow file does not parse. GitHub will list the run by FILENAME ' +
        'instead of its `name`, fail it before any job starts, and never create ' +
        "the check-run — so the gate disappears from the PR's check list rather " +
        'than going red:\n  ' + broken.join('\n  '),
    ).toEqual([]);
  });

  it('the parser rejects the exact defect that motivated this — negative control', () => {
    // Without this, a parser that silently accepted everything would make the
    // assertion above green on a broken tree. This is the real string.
    expect(() =>
      parse('jobs:\n  x:\n    steps:\n      - name: Run E2E (rounds-c1 — C1-d/e/f: auth, settings)\n'),
    ).toThrow();
    // …and it accepts the repaired form, so the control is not just "throws on
    // everything".
    expect(() =>
      parse('jobs:\n  x:\n    steps:\n      - name: Run E2E (rounds-c1 — C1-d, C1-e and C1-f — auth)\n'),
    ).not.toThrow();
  });
});
