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
//
// ⚠️ ROUND SIX, 2026-09-10 — THE RESOLVER UNDER-FLAGGED, AND ITS OWN COMMENT
// SAID IT OVER-FLAGGED. Fed through this file's own exports, seven one-step
// workflows that each exit 1 once the app is gone scored `detected=false`: a
// line was skipped WHOLE if any command on it carried `-w`; only the FIRST
// `npm run` per line was resolved; `npm start` / `npm run-script` were not npm
// to it; a quoted `-w "meddoc-pro"` did not match; and a root script that READ
// a path inside the app was invisible to both the hop arm and the FILED arm.
// Now: the step is cut into simple commands, each read as npm reads it
// (aliases, lifecycle commands, implicit pre/post hooks, quotes stripped), root
// scripts resolve to a fixed point, and — because no small shell reader is
// complete — a CENSUS reds on any line naming the token that nobody judged.
// ============================================================================
import { createHash } from 'node:crypto';
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
 * Covers `-w x`, `-w=x`, `--workspace x`, `--workspace=x`, and every QUOTED
 * spelling of them. The trailing lookahead is load-bearing: `e2e.yml` builds a
 * docker image tagged `meddoc-pro-transcribe-md:rounds`, which must NOT match.
 *
 * ⚠️ ROUND SIX — QUOTES ARE STRIPPED FIRST. The shell removes them before npm
 * ever sees the argument, so `-w "meddoc-pro"` IS `-w meddoc-pro`; the previous
 * form matched only the unquoted spelling and scored `detected=false` on it.
 */
export function needsRetiredWorkspace(cmd: string): boolean {
  return new RegExp(`(?:-w|--workspace)[=\\s]+(?:apps/)?${RETIRED}(?![-\\w])`).test(cmd.replace(/['"]/g, ''));
}

/** Names a path INSIDE the retired app — a read that ENOENTs once it is gone. */
export function readsRetiredPath(cmd: string): boolean {
  return cmd.includes(`apps/${RETIRED}`);
}

/**
 * Names the bare retired token anywhere — the census predicate. The lookarounds
 * keep the compose-project prefix out (`meddoc-pro-transcribe-md:rounds`,
 * `meddoc-pro_pgdata`), which is a NAME, not the workspace.
 */
export function mentionsRetired(text: string): boolean {
  return new RegExp(`(?<![\\w-])${RETIRED}(?![-\\w])`).test(text);
}

/**
 * Root scripts that need the retired workspace — DIRECTLY (a workspace flag or a
 * path inside the app) or TRANSITIVELY (they `npm run` another root script that
 * does). ⚠️ ROUND SIX: this used to be the `-w` detector alone, so a root script
 * that READ `apps/meddoc-pro/...` was invisible to the hop arm AND to the FILED
 * arm at once, and a root script that hopped to a coupled root script was
 * invisible too. Resolved to a fixed point, so a chain of any length is seen.
 */
export function rootScriptsNeedingRetired(scripts: Record<string, string>): string[] {
  const coupled = new Set(
    Object.entries(scripts)
      .filter(([, cmd]) => needsRetiredWorkspace(cmd) || readsRetiredPath(cmd))
      .map(([name]) => name),
  );
  for (let grew = true; grew; ) {
    grew = false;
    for (const [name, cmd] of Object.entries(scripts)) {
      if (coupled.has(name)) continue;
      const hops = shellSegments(cmd)
        .map(npmCall)
        .filter((c): c is NpmCall => c !== null && c.rootResolved);
      if (hops.some((c) => c.scripts.some((s) => coupled.has(s)))) {
        coupled.add(name);
        grew = true;
      }
    }
  }
  return [...coupled].sort();
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
 * A shell script cut into SIMPLE COMMANDS — every `&&`, `||`, `;`, `|`, `&`,
 * subshell and substitution boundary is a cut, and line continuations are
 * joined first. ⚠️ ROUND SIX: the resolver used to reason per LINE, so
 * `npm run lint && npm run test:unit -w transcribe-md` was skipped WHOLE because
 * SOME command on the line carried a `-w`, and `npm run db:generate && npm run
 * build` resolved only its FIRST `npm run`. Both were `detected=false` on a
 * step that exits 1 once the app is gone. It over-splits on purpose (a `|`
 * inside a quoted JS string is cut too); an over-cut costs nothing, because a
 * fragment that is not an npm call resolves to nothing.
 */
export function shellSegments(script: string): string[] {
  return stripShellComments(script)
    .replace(/\\\r?\n/g, ' ')
    .split(/\r?\n|&&|\|\||[;|&()`]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** npm's spellings of `run`, and the lifecycle commands that run a root script. */
const RUN_ALIASES = new Set(['run', 'run-script', 'rum', 'urn']);
const LIFECYCLE_ALIASES = new Map<string, string[]>([
  ['start', ['start']],
  ['test', ['test']],
  ['t', ['test']],
  ['tst', ['test']],
  ['stop', ['stop']],
  ['restart', ['restart', 'stop', 'start']],
]);
/** `npm ci` / `npm install` run the ROOT package's install lifecycle scripts. */
const INSTALL_ALIASES = new Set([
  'ci', 'clean-install', 'ic', 'install-clean', 'isntall-clean', 'install', 'i', 'in', 'ins',
  'inst', 'insta', 'instal', 'isnt', 'isnta', 'isntal', 'isntall', 'add',
  'install-test', 'it', 'install-ci-test', 'cit',
]);
const INSTALL_LIFECYCLE = ['preinstall', 'install', 'postinstall', 'prepublish', 'preprepare', 'prepare', 'postprepare'];
/** Flags whose NEXT token is their value, so it is not the subcommand. */
const VALUE_FLAGS = new Set(['--loglevel', '--userconfig', '--cache', '--registry', '--script-shell', '--tag']);

export type NpmCall = {
  /** the call names the retired workspace itself (flag or `--prefix`) */
  retiredFlag: boolean;
  /** the call resolves against the ROOT package.json's scripts */
  rootResolved: boolean;
  /** every script name the call runs, INCLUDING npm's implicit pre/post hooks */
  scripts: string[];
};

/**
 * One simple command, read as npm would read it. `null` when it is not npm.
 *
 * ⚠️ ROUND SIX, the shapes the old `line.match(/npm run (…)/)` could not see,
 * each a step that fails once the app is deleted: `npm start` (root `start` →
 * `-w meddoc-pro`), `npm run-script build` (npm's canonical name for `run`),
 * `npm run -s build` / `npm --prefix . run build` (a flag between the words),
 * and the implicit `pre<name>` / `post<name>` hooks npm runs around every
 * script. Quotes are stripped per token for the same reason as the detector.
 */
export function npmCall(segment: string): NpmCall | null {
  const t = segment
    .split(/\s+/)
    .map((x) => x.replace(/['"]/g, ''))
    .filter(Boolean);
  const at = t.findIndex((x) => x === 'npm' || x.endsWith('/npm'));
  if (at < 0) return null;
  const args = t.slice(at + 1);
  const workspaces: string[] = [];
  let allWorkspaces = false;
  let includeRoot = false;
  let prefix: string | null = null;
  const positional: string[] = [];
  for (let i = 0; i < args.length; i += 1) {
    const a = args[i]!;
    if (a === '--') break; // the rest belongs to the script
    const eq = a.match(/^(-w|--workspace|--prefix|-C)=(.*)$/);
    if (eq) {
      if (eq[1] === '-w' || eq[1] === '--workspace') workspaces.push(eq[2]!);
      else prefix = eq[2]!;
      continue;
    }
    if (a === '-w' || a === '--workspace') { workspaces.push(args[i + 1] ?? ''); i += 1; continue; }
    if (a === '--prefix' || a === '-C') { prefix = args[i + 1] ?? ''; i += 1; continue; }
    if (a === '-ws' || a === '--workspaces' || a.startsWith('--workspaces=')) { allWorkspaces = true; continue; }
    if (a === '--include-workspace-root' || a.startsWith('--include-workspace-root=')) { includeRoot = true; continue; }
    if (VALUE_FLAGS.has(a)) { i += 1; continue; }
    if (a.startsWith('-')) continue;
    positional.push(a);
  }
  const sub = positional[0] ?? '';
  const hooks = (n: string) => [`pre${n}`, n, `post${n}`];
  let scripts: string[] = [];
  if (RUN_ALIASES.has(sub)) scripts = positional[1] ? hooks(positional[1]) : [];
  else if (LIFECYCLE_ALIASES.has(sub)) scripts = LIFECYCLE_ALIASES.get(sub)!.flatMap(hooks);
  else if (INSTALL_ALIASES.has(sub)) {
    scripts = [...INSTALL_LIFECYCLE, ...(/^(install-test|it|install-ci-test|cit)$/.test(sub) ? hooks('test') : [])];
  }
  const retiredFlag = workspaces.some(mentionsRetired) || (prefix !== null && mentionsRetired(prefix));
  const atRoot = prefix === null || /^\.\/?$/.test(prefix);
  const rootResolved =
    !retiredFlag && atRoot && ((workspaces.length === 0 && !allWorkspaces) || includeRoot);
  return { retiredFlag, rootResolved, scripts };
}

/**
 * The couplings a workflow carries, resolved through the root scripts — every
 * simple command, every hop, every implicit hook.
 *
 * ⚠️ IT OVER-FLAGS ON PURPOSE. A `npm run <name>` that carries no `-w` of its
 * own is treated as root-resolved even if the step `cd`s first, because the
 * alternative — inferring the resolution from shell text — is a heuristic that
 * fails toward GREEN, and a coupling that fails toward green is the whole
 * incident above. A false positive costs one reasoned row in
 * WORKFLOW_COUPLINGS_ACCEPTED; a false negative costs the merge queue.
 *
 * ⚠️ AND ROUND SIX FOUND THAT CLAIM WAS FALSE AS WRITTEN: the per-line skip on
 * ANY `-w` was exactly such a heuristic, and it failed toward green. No shell
 * parser this small is complete, so the census arm below backstops it: every
 * line that NAMES the retired token must be either a coupling this resolver
 * found or a line somebody adjudicated.
 */
export function couplingsIn(file: string, doc: unknown, rootScripts: Record<string, string>): string[] {
  const coupled = new Set(rootScriptsNeedingRetired(rootScripts));
  const found: string[] = [];
  for (const step of runSteps(doc)) {
    const where = `${file} :: ${step.job} :: ${step.name}`;
    for (const seg of shellSegments(step.run)) {
      const call = npmCall(seg);
      if (needsRetiredWorkspace(seg) || call?.retiredFlag) {
        found.push(`${where} :: names the workspace directly :: ${seg}`);
        continue;
      }
      if (!call?.rootResolved) continue;
      for (const s of call.scripts) {
        if (coupled.has(s)) found.push(`${where} :: ${seg} -> root \`${s}\` = ${rootScripts[s]}`);
      }
    }
  }
  return found;
}

/** Every line of a workflow's effective strings that NAMES the retired token. */
export function workflowMentions(file: string, doc: unknown): string[] {
  const out = new Set<string>();
  for (const v of effectiveStrings(doc)) {
    for (const line of v.split('\n')) if (mentionsRetired(line)) out.add(`${file} :: ${line.trim()}`);
  }
  return [...out].sort();
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

/**
 * ⚠️ ROUND SIX — THE CENSUS. Every workflow line that NAMES the retired token
 * and is NOT a coupling, each adjudicated with its reason. The resolver above is
 * a shell reader, and no small shell reader is complete — `WS=meddoc-pro; npm
 * run x -w $WS`, `cd apps; cd meddoc-pro` and the next spelling nobody has
 * thought of all get past it. They cannot get past this: a line that names the
 * token and is neither a found coupling nor on this list REDS.
 *
 * Keyed by the WHOLE trimmed line, so any edit to an adjudicated line — say, a
 * real coupling appended to it — changes the key and reds until re-judged.
 *
 * ⚠️ ONE DIRECTION ONLY, DELIBERATELY: an unlisted mention reds; a stale row
 * does not. A row can only ever excuse byte-identical text that was already
 * judged harmless, so staleness cannot hide a new coupling — and `main` is
 * `strict: false` (RELAY, "the gate reads SIX check runs"), so an exact
 * both-ways match on free text would turn `main` red the day an unrelated PR
 * rewords an echo and merges without re-running this file.
 */
const WORKFLOW_MENTIONS_ADJUDICATED: Record<string, string> = {
  'test.yml :: Audit (fail on high/critical only; decommissioned meddoc-pro excluded)':
    'a step NAME. Prose; it executes nothing.',
  "test.yml :: | node -e \"let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{for(const w of JSON.parse(s)){if(w.name!=='meddoc-pro')console.log(w.name)}})\")":
    'the audit workspace FILTER. It EXCLUDES the retired workspace by name; with the app gone the ' +
    'comparison simply never matches and every other workspace is still listed. Nothing reads the app.',
  'test.yml :: echo "Auditing ${#WS[@]} in-scope workspaces, PRODUCTION deps only (meddoc-pro excluded): ${WS[*]}"':
    'echo text naming the exclusion above.',
  'test.yml :: echo "Dev-inclusive audit over ${#WS[@]} workspaces (meddoc-pro excluded): ${WS[*]}"':
    'echo text naming the exclusion above.',
};

/**
 * Root scripts that NAME the token and are NOT couplings — the same census, one
 * layer in. Pinned by a hash of the COMMAND, not by the script name, so an edit
 * that turns the echo into `WS=meddoc-pro; npm run x -w $WS` changes the hash
 * and reds. (A name-keyed row would have excused exactly that.)
 */
const ROOT_SCRIPT_MENTIONS_ADJUDICATED: Record<string, { sha: string; reason: string }> = {
  'test:all': {
    sha: '5b6a6085ce9f335a', // sha256(command)[0:16], computed 2026-09-10 — never typed from memory
    reason: 'an ECHO whose text explains the decoupling by naming the retired app; it invokes nothing.',
  },
};

const sha16 = (s: string) => createHash('sha256').update(s).digest('hex').slice(0, 16);

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

  it('⚠️ POSITIVE CONTROL: the resolver catches every shape round six planted — and passes their look-alikes', () => {
    // Every YES below exits 1 once the app is gone, and every one of the first
    // seven scored `detected=false` against the previous resolver (round six,
    // reproduced through this file's own exports). Synthetic root scripts, so
    // this control cannot decay with the tree.
    const root: Record<string, string> = {
      start: `npm run start -w ${RETIRED}`,
      build: `npm run build -w ${RETIRED}`,
      lint: `npm run lint -w ${RETIRED}`,
      'db:generate': 'npm run generate -w @meddoc/db',
      'prisma:crm': `prisma generate --schema apps/${RETIRED}/prisma/schema.prisma`,
      chain: 'npm run build',
      pretest: `npm run seed -w ${RETIRED}`,
      test: 'vitest run',
      postinstall: `node apps/${RETIRED}/scripts/x.js`,
      'test:unit': 'npm run test:unit -w transcribe-md',
    };
    expect(rootScriptsNeedingRetired(root), 'the fixed point missed a direct, path or chained root script').toEqual(
      ['build', 'chain', 'lint', 'postinstall', 'pretest', 'prisma:crm', 'start'],
    );
    const wf = (run: string) => loadYaml()(`jobs:\n  j:\n    steps:\n      - name: s\n        run: ${JSON.stringify(run)}\n`);
    const YES = [
      'npm start',
      'npm run lint && npm run test:unit -w transcribe-md',
      'npm run db:generate && npm run build',
      `npm run seed:e2e -w "${RETIRED}"`,
      'npm run-script build',
      'npm run prisma:crm',
      'npm run chain',
      `npm run x --workspace='${RETIRED}'`,
      `npm run x -w apps/${RETIRED}`,
      'npm run -s build',
      'npm --prefix . run build',
      'npm test',
      'npm ci',
      'FOO=1 npm run build',
      'cd /app\nnpm run build',
      'npm run build \\\n  --if-present',
    ];
    for (const run of YES) expect(couplingsIn('p.yml', wf(run), root), `missed: ${run}`).not.toEqual([]);
    const NO = [
      'npm run test:unit -w transcribe-md',
      'npm run db:generate',
      'npm --prefix apps/transcribe-md run build',
      'npm run build --workspaces',
      'npm run build -w transcribe-md && npm run lint -w transcribe-md',
      'npx playwright install chromium',
      `docker build -t ${RETIRED}-transcribe-md:rounds .`,
    ];
    for (const run of NO) expect(couplingsIn('p.yml', wf(run), root), `false positive: ${run}`).toEqual([]);
  });

  it('⚠️ POSITIVE CONTROL: the census SEES what the resolver cannot — which is why it exists', () => {
    // A spelling no small shell reader resolves. The resolver says NO; the
    // census must say it NAMES the token, so the arm below reds on it.
    const doc = loadYaml()(`jobs:\n  j:\n    steps:\n      - run: WS=${RETIRED}; npm run x -w $WS\n`);
    expect(couplingsIn('p.yml', doc, {}), 'the resolver now resolves shell variables — update this control').toEqual([]);
    expect(workflowMentions('p.yml', doc)).toEqual([`p.yml :: WS=${RETIRED}; npm run x -w $WS`]);
    // and the compose-project look-alike is NOT a mention
    const tag = loadYaml()(`jobs:\n  j:\n    steps:\n      - run: docker build -t ${RETIRED}-transcribe-md:rounds .\n`);
    expect(workflowMentions('p.yml', tag)).toEqual([]);
  });

  it('⚠️ CENSUS: every workflow line naming the retired token is ADJUDICATED — the resolver is not trusted alone', () => {
    const all: string[] = [];
    for (const f of WORKFLOWS) all.push(...workflowMentions(f, loadYaml()(readFileSync(join(WF_DIR, f), 'utf8'))));
    // NON-VACUITY: the census reads the live tree, not an empty set.
    expect(
      all.some((m) => m in WORKFLOW_MENTIONS_ADJUDICATED),
      'the census found NONE of the lines it adjudicates — they were all removed (delete the rows) or the census reads nothing',
    ).toBe(true);
    expect(
      all.filter((m) => !(m in WORKFLOW_MENTIONS_ADJUDICATED)),
      'a workflow line names the retired workspace and nobody has judged it. If it is a coupling, the ' +
        'arms above name it too — repoint it. If it is not, add the WHOLE line to ' +
        'WORKFLOW_MENTIONS_ADJUDICATED with the reason it survives the deletion.',
    ).toEqual([]);
  });

  it('⚠️ CENSUS: every root script naming the retired token is FILED as coupled or ADJUDICATED by command hash', () => {
    const offenders: string[] = [];
    for (const [name, cmd] of Object.entries(ROOT_SCRIPTS)) {
      if (!mentionsRetired(cmd) || name in ROOT_SCRIPTS_STILL_COUPLED) continue;
      const adj = ROOT_SCRIPT_MENTIONS_ADJUDICATED[name];
      if (!adj) offenders.push(`${name}: names the retired workspace and is neither filed nor adjudicated`);
      else if (adj.sha !== sha16(cmd)) offenders.push(`${name}: command changed since it was adjudicated (now ${sha16(cmd)}) — re-judge it`);
    }
    expect(offenders).toEqual([]);
  });
});
