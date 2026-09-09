// ============================================================================
// DMP-a — NOTHING CI RUNS MAY REQUIRE THE RETIRED `meddoc-pro` WORKSPACE
// ----------------------------------------------------------------------------
// DELETE-MEDDOC-PRO is a scheduled act. Every CI step that needs that workspace
// to EXIST is a landmine under it, and the ones that hurt are the ones nobody
// enumerated.
//
// ⚠️ THE INSTANCE THAT MADE THIS A GATE. PR #1088's first pass fixed three
// references inside the `test` job of `test.yml` — a cache key and two
// `working-directory:` lines — and left `run: npm run test:all` THREE LINES
// BELOW one of them. That resolves at the repo root to
// `npm run test:all -w meddoc-pro`, so with the app gone the step exits 1 with
//
//     npm error No workspaces found:
//     npm error   --workspace=meddoc-pro
//
// in the job named `test`, which branch protection lists as a REQUIRED context
// (`docs/foundation/RELAY.md:510`). Not "CI goes red on main" — every PR in the
// repository becomes unmergeable at once. Measured: EXIT=1 with the directory
// moved out of the tree, EXIT=0 with it present.
//
// ⚠️ AND "I READ THE WORKFLOW" IS THE THING THAT FAILED. The coupling is not
// spelled `meddoc-pro` anywhere in `test.yml`; it is one hop away, in a root
// script. A grep of the workflow files for the app name returns nothing for it.
// So this gate RESOLVES the hop instead of grepping for a name, and enumerates
// the workflows off the filesystem so one added tomorrow is watched tomorrow.
// ============================================================================
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO = resolve(__dirname, '..', '..', '..', '..', '..');
const WF_DIR = join(REPO, '.github', 'workflows');

/** The workspace slated for deletion. */
const RETIRED = 'meddoc-pro';

/** ⚠️ RESOLVED AT RUNTIME, AND MISSING IS A FAILURE — NEVER A SKIP.
 *  Same doctrine as `gate-186`: `js-yaml` reaches this tree transitively, and a
 *  `try { … } catch { return }` here would make the guard VANISH on an
 *  unrelated lockfile change. A guard that silently stops running is the defect
 *  class this file exists to catch.
 */
const req = createRequire(__filename);
function loadYaml(): (src: string) => unknown {
  try {
    return (req('js-yaml') as { load: (s: string) => unknown }).load;
  } catch {
    throw new Error(
      'the YAML parser is not installed, so this guard cannot check anything. ' +
        'js-yaml reaches this tree transitively via eslint; if that changed, add ' +
        'it as an explicit devDependency rather than deleting this test.',
    );
  }
}

/**
 * Does this shell command require the retired workspace to EXIST?
 * Covers `-w x`, `-w=x`, `--workspace x`, `--workspace=x`. The trailing
 * lookahead is load-bearing: `e2e.yml` builds a docker image tagged
 * `meddoc-pro-transcribe-md:rounds`, which must NOT match.
 */
export function needsRetiredWorkspace(cmd: string): boolean {
  return new RegExp(`(?:-w|--workspace)[=\\s]+${RETIRED}(?![-\\w])`).test(cmd);
}

/** Root scripts whose command needs the retired workspace. */
export function rootScriptsNeedingRetired(scripts: Record<string, string>): string[] {
  return Object.entries(scripts)
    .filter(([, cmd]) => needsRetiredWorkspace(cmd))
    .map(([name]) => name)
    .sort();
}

/**
 * ⚠️ A `#` LINE INSIDE A `run: |` BLOCK IS PART OF THE STRING, and it is a
 * SHELL comment, not an instruction. `test.yml`'s Playwright-version step
 * carries the DMP-a explanation inside its own run block, naming the path it
 * STOPPED reading — so a scan that does not strip these reds on the note
 * describing the fix. (It did: the first form of this gate red on exactly that
 * line.) YAML comments never survive parsing; shell comments do.
 */
export function stripShellComments(run: string): string {
  return run
    .split('\n')
    .filter((l) => !l.trimStart().startsWith('#'))
    .join('\n');
}

/** Every string VALUE in a parsed workflow — YAML comments are gone already. */
export function stringValues(node: unknown, out: string[] = []): string[] {
  if (typeof node === 'string') out.push(node);
  else if (Array.isArray(node)) for (const v of node) stringValues(v, out);
  else if (node && typeof node === 'object') for (const v of Object.values(node)) stringValues(v, out);
  return out;
}

type Step = { job: string; name: string; run: string };

/** Every `run:` step in a parsed workflow document. */
export function runSteps(doc: unknown): Step[] {
  const out: Step[] = [];
  const jobs = (doc as { jobs?: Record<string, { steps?: unknown[] }> })?.jobs ?? {};
  for (const [job, def] of Object.entries(jobs)) {
    for (const raw of def?.steps ?? []) {
      const s = raw as { name?: string; run?: string };
      if (typeof s?.run === 'string') out.push({ job, name: s.name ?? '<unnamed>', run: s.run });
    }
  }
  return out;
}

/** String values with SHELL comments stripped out of every `run:` block. */
export function effectiveStrings(doc: unknown): string[] {
  const runs = new Set(runSteps(doc).map((s) => s.run));
  return stringValues(doc).map((v) => (runs.has(v) ? stripShellComments(v) : v));
}

/**
 * The couplings a workflow carries, resolved ONE HOP through the root scripts.
 *
 * ⚠️ IT OVER-FLAGS ON PURPOSE. A `npm run <name>` that carries no `-w` of its
 * own is treated as root-resolved even if the line `cd`s first, because the
 * alternative — inferring the resolution from shell text — is a heuristic that
 * fails toward GREEN, and a coupling that fails toward green is the whole
 * incident above. A false positive costs one reasoned row in
 * WORKFLOW_COUPLINGS_ACCEPTED; a false negative costs the merge queue.
 */
export function couplingsIn(file: string, doc: unknown, rootScripts: Record<string, string>): string[] {
  const coupled = new Set(rootScriptsNeedingRetired(rootScripts));
  const found: string[] = [];
  for (const step of runSteps(doc)) {
    const script = stripShellComments(step.run);
    if (needsRetiredWorkspace(script)) {
      found.push(`${file} :: ${step.job} :: ${step.name} :: names the workspace directly`);
      continue;
    }
    for (const line of script.split('\n')) {
      // an invocation carrying its OWN workspace flag is not root-resolved, and
      // it is not the retired one — the check above already ruled that out.
      if (/(?:-w|--workspace)[=\s]/.test(line)) continue;
      const m = line.match(/npm run ([\w:.@/-]+)/);
      if (m && coupled.has(m[1])) {
        found.push(`${file} :: ${step.job} :: ${step.name} :: npm run ${m[1]} -> ${rootScripts[m[1]]}`);
      }
    }
  }
  return found;
}

const ROOT_SCRIPTS: Record<string, string> = JSON.parse(
  readFileSync(join(REPO, 'package.json'), 'utf8'),
).scripts;

const WORKFLOWS = readdirSync(WF_DIR)
  .filter((f) => f.endsWith('.yml') || f.endsWith('.yaml'))
  .sort();

/**
 * ⚠️ CI STEPS ALLOWED TO NEED THE RETIRED WORKSPACE, EACH WITH ITS REASON.
 * Empty, and it fails closed: a new coupling is NOT here, so it reds. Adding a
 * row is a decision someone signs, not a way to get green.
 */
const WORKFLOW_COUPLINGS_ACCEPTED: Record<string, string> = {};

/**
 * ⚠️ ROOT SCRIPTS THAT STILL HOP TO THE RETIRED WORKSPACE — the FILED list, so
 * that "unfiled" can never again be the finding. None of these is reachable
 * from any workflow (that is the arm above, and it is what makes them
 * survivable until DELETE-MEDDOC-PRO); each breaks a HUMAN's local command the
 * moment the app is deleted.
 *
 * ⚠️ THEY ARE DELIBERATELY NOT REPOINTED HERE. `dev`/`build`/`start`/`lint`
 * decide WHICH APP a bare root command drives, and that is a product-shaped
 * call with live workflows (`a11y.yml`, `e2e.yml`) reading the same verbs — it
 * does not belong inside a CI-decoupling fix that cannot run CI to check it.
 * Filed as recon row A5·1.
 *
 * RETIRES: when DELETE-MEDDOC-PRO lands, every row here must be repointed or
 * removed in the same change — this map is the checklist for that act.
 */
const ROOT_SCRIPTS_STILL_COUPLED: Record<string, string> = {
  dev: 'bare `npm run dev` drives the CRM. Repointing it chooses a default app.',
  build: 'bare `npm run build`. a11y.yml/e2e.yml call `-w transcribe-md` explicitly, so CI is unaffected.',
  start: 'bare `npm run start`. Same as build.',
  lint: 'bare `npm run lint`. CI lints per-workspace.',
  'test:unit': 'the unit job calls `-w transcribe-md` explicitly; this bare form is local only.',
  'test:unit:watch': 'local watch mode only.',
  'test:e2e': 'the transcribe-md e2e has its own root alias, `test:e2e:transcribe-md`.',
  'test:e2e:ui': 'local UI mode only.',
  'seed:e2e': 'seeds the CRM fixtures; no workflow calls the bare form.',
  'seed:e2e-admin': 'seeds the CRM super-admin; no workflow calls the bare form.',
  'eval:doc-editor': 'the Doc Editor eval lives in the CRM workspace and is run by hand.',
  'eval:clinical-notes': 'same, run by hand.',
};

describe('DMP-a — the retired workspace is not a CI dependency', () => {
  it('⚠️ POSITIVE CONTROL: the reader actually found and parsed the workflows', () => {
    // Without this, every empty set below could be an empty INPUT — the
    // "assertion over a possibly-empty set" failure, which reads identical to
    // a clean tree.
    expect(WORKFLOWS.length, 'no workflow files were read').toBeGreaterThan(3);
    let steps = 0;
    for (const f of WORKFLOWS) steps += runSteps(loadYaml()(readFileSync(join(WF_DIR, f), 'utf8'))).length;
    expect(steps, 'the parser found no `run:` steps at all — it is reading nothing').toBeGreaterThan(20);
    expect(Object.keys(ROOT_SCRIPTS).length, 'root scripts did not load').toBeGreaterThan(5);
  });

  it('⚠️ POSITIVE CONTROL: the detector says YES to the real coupling and NO to its look-alikes', () => {
    // The string that actually shipped, and the shapes a sloppy regex eats.
    expect(needsRetiredWorkspace('npm run test:all -w meddoc-pro')).toBe(true);
    expect(needsRetiredWorkspace('npm run x --workspace=meddoc-pro')).toBe(true);
    expect(needsRetiredWorkspace('npm run test:unit -w transcribe-md')).toBe(false);
    // e2e.yml really builds this tag; a `\b` after the name would match it.
    expect(needsRetiredWorkspace('docker build -t meddoc-pro-transcribe-md:rounds .')).toBe(false);
  });

  it('⚠️ POSITIVE CONTROL: the ONE-HOP resolution catches a planted coupling', () => {
    // Aimed where the answer is NOT predetermined. The live set below is empty;
    // without this, an empty set would also be what a broken resolver returns.
    // Both inputs are synthetic, so this control cannot decay with the tree.
    const planted = loadYaml()('jobs:\n  ci:\n    steps:\n      - name: gate\n        run: npm run ci-thing\n');
    const hits = couplingsIn('planted.yml', planted, { 'ci-thing': `npm run test -w ${RETIRED}` });
    expect(hits, 'the resolver did not follow `npm run ci-thing` into the root script').toHaveLength(1);
    expect(hits[0]).toContain('npm run ci-thing');
    // and it does NOT flag the same step when the root script is clean
    expect(couplingsIn('planted.yml', planted, { 'ci-thing': 'npm run test -w transcribe-md' })).toEqual([]);
  });

  it('⚠️ POSITIVE CONTROL: the path scan reads VALUES, and knows a comment from a command', () => {
    // ⚠️ THE FIRST FORM OF THE ARM BELOW GREPPED THE RAW FILE AND RED ON FIVE
    // YAML COMMENTS — including the ones PR #1088 wrote explaining the fix. Its
    // second form red on ONE shell comment living inside a `run: |` block. A
    // gate that cannot tell a comment from an instruction measures prose.
    const yamlDoc = loadYaml()(
      `# apps/${RETIRED}/package.json in a YAML COMMENT must not count\n` +
        `jobs:\n  j:\n    steps:\n      - run: cat apps/${RETIRED}/package.json\n`,
    );
    const vals = effectiveStrings(yamlDoc);
    expect(vals.filter((v) => v.includes(`apps/${RETIRED}`)), 'the planted VALUE was not seen').toHaveLength(1);
    expect(vals.some((v) => v.includes('YAML COMMENT')), 'a YAML comment survived parsing').toBe(false);

    const shellDoc = loadYaml()(
      `jobs:\n  j:\n    steps:\n      - run: |\n          # apps/${RETIRED}/x.json in a SHELL comment\n          echo real\n`,
    );
    const shellVals = effectiveStrings(shellDoc);
    expect(shellVals.some((v) => v.includes(`apps/${RETIRED}`)), 'a shell comment counted as a read').toBe(false);
    expect(shellVals.some((v) => v.includes('echo real')), 'stripping ate the actual command').toBe(true);
  });

  it('NO workflow step requires the retired workspace, directly or one hop away', () => {
    const found: string[] = [];
    for (const f of WORKFLOWS) {
      found.push(...couplingsIn(f, loadYaml()(readFileSync(join(WF_DIR, f), 'utf8')), ROOT_SCRIPTS));
    }
    const unaccepted = found.filter((c) => !(c in WORKFLOW_COUPLINGS_ACCEPTED));
    expect(
      unaccepted,
      'a CI step needs the `meddoc-pro` workspace to exist. DELETE-MEDDOC-PRO ' +
        'makes it exit 1 with `npm error No workspaces found`, and `test` is a ' +
        'REQUIRED context — so this does not turn main red, it makes every PR ' +
        'unmergeable. Repoint the step (or the root script it resolves to), or ' +
        'add a reasoned row to WORKFLOW_COUPLINGS_ACCEPTED.',
    ).toEqual([]);
  });

  it('NO workflow step reads a path inside the retired app', () => {
    // The cache key `require("./apps/meddoc-pro/package.json")` was this shape,
    // and a path read fails the step just as hard as a missing workspace.
    const offenders: string[] = [];
    for (const f of WORKFLOWS) {
      const doc = loadYaml()(readFileSync(join(WF_DIR, f), 'utf8'));
      for (const v of effectiveStrings(doc)) {
        if (v.includes(`apps/${RETIRED}`)) offenders.push(`${f} :: ${v.trim().slice(0, 90)}`);
      }
    }
    expect(offenders, 'these workflow steps read a file inside the app slated for deletion').toEqual([]);
  });

  it('the root scripts that still hop there are FILED — exactly, both directions', () => {
    // A stale row hides a script somebody already fixed; a missing row is a new
    // coupling nobody looked at. Equality catches both.
    expect(
      rootScriptsNeedingRetired(ROOT_SCRIPTS),
      'root package.json scripts needing `meddoc-pro` do not match the filed ' +
        'list. A new one: repoint it, or file it with a reason. One that is gone: ' +
        'delete its row — a stale exemption is how the last one hid.',
    ).toEqual(Object.keys(ROOT_SCRIPTS_STILL_COUPLED).sort());
  });

  it('`test:all` specifically is decoupled — it is the one CI runs', () => {
    expect(existsSync(join(WF_DIR, 'test.yml')), 'test.yml is gone — this gate is measuring nothing').toBe(true);
    expect(readFileSync(join(WF_DIR, 'test.yml'), 'utf8')).toContain('run: npm run test:all');
    expect(
      needsRetiredWorkspace(ROOT_SCRIPTS['test:all']),
      'root `test:all` hops to the retired workspace again, and `.github/workflows/' +
        'test.yml` runs it in the REQUIRED `test` job',
    ).toBe(false);
  });
});
