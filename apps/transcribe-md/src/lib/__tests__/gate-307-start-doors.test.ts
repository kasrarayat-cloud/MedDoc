// ============================================================================
// "NOBODY CAN START IT" IS A CLAIM ABOUT A **SET OF DOORS**, AND THE SET WAS
// NEVER ENUMERATED
// ----------------------------------------------------------------------------
// Ruling #307's change removed the `meddoc-pro` compose SERVICE and its comment
// said: *"'Nobody starts it' and 'nobody CAN start it' are different properties.
// This removes the second gap."* It removed one verb.
//
// ⚠️ THE DOORS THAT SURVIVED IT, ALL MEASURED, NONE HYPOTHETICAL:
//
//   1. `docker start meddoc-pro-meddoc-pro-1` — the container OBJECT outlives the
//      service definition. `docker start` is a daemon API call against config
//      persisted at CREATE time; it reads no compose file. The object is
//      `Exited (143)`, its image is present, its network alias and its baked
//      `DATABASE_URL` (sha-identical to the live app's) are intact.
//      ⚠️ AND IT REVIVES THE BAKED 2026-05-05 IMAGE, NOT HEAD — an unaudited
//      build carrying unlocked `isActive` / `deactivatedAt` writers and an
//      unlocked `users` DELETE, with `withPracticeLock` absent from the whole
//      bundle. `practiceRole` is not in it; that column landed two days after
//      the container last ran. Different verb, different code — "it restores
//      the four writers" would have been wrong in both directions.
//      ⚠️ **THIS GATE DOES NOT CLOSE THAT DOOR** — closing it means
//      `docker rm`, an irreversible production deletion, which is an owner act.
//      What this gate enforces is that the DECLARATION keeps naming it.
//   2. `npm run start -w meddoc-pro` / `dev` / `build` — the repo's own scripts
//      start the identical CRM with docker not involved at all, resolving
//      `apps/meddoc-pro/.env` (a symlink to the root `.env`) for its DSN.
//   3. the on-disk `.next/standalone` bundle, which a verifier BOOTED to a
//      live Prisma path with no compose service, no image and no container.
//
// ⚠️ SO THE FAILURE WAS NOT THE CHANGE — IT WAS THE CLAIM. Door 2 is closed
// here. Doors 1 and 3 cannot be closed by a commit, so they are RECORDED, and
// this gate makes the record load-bearing: delete the residual-door names from
// the declaration and the gate reds.
//
// ⚠️ AND THE CLOSURE HAS **ONE** READER, DELIBERATELY. The root scripts keep
// delegating to the workspace, so `apps/meddoc-pro/package.json` is the single
// place the refusal lives. A repo whose rule is written down four times
// contradicts itself the day one copy is edited, and every arm stays green
// because each arm points at one copy.
//
// ⚠️ WHAT THIS GATE CANNOT SEE, SAID PLAINLY: door 3 is a build ARTIFACT under
// a gitignored path. A CI runner has no `.next/` at all, so asserting its
// absence would pass vacuously everywhere and prove nothing. It is named in the
// declaration instead, which is why arm 4 exists.
// ============================================================================
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO = join(process.cwd(), '..', '..');
const APP_PKG = join(REPO, 'apps', 'meddoc-pro', 'package.json');
const ROOT_PKG = join(REPO, 'package.json');
const COMPOSE = join(REPO, 'docker-compose.yml');
const DECLARATION = join(
  REPO, 'docs', 'deploy-declarations', '307-retire-meddoc-pro-service-20260909.md',
);

const req = createRequire(__filename);
function composeDoc(): { services?: Record<string, { build?: unknown }> } {
  let load: (s: string) => unknown;
  try {
    load = (req('js-yaml') as { load: (s: string) => unknown }).load;
  } catch {
    throw new Error(
      'the YAML parser is not installed, so this guard cannot check anything. ' +
        'js-yaml reaches this tree transitively via eslint; add it as an explicit ' +
        'devDependency rather than deleting this test.',
    );
  }
  return load(readFileSync(COMPOSE, 'utf8')) as { services?: Record<string, { build?: unknown }> };
}

/** A command that would actually bring the app up (or rebuild it so it can be). */
export const RUN_SHAPE = /\bnext\s+(?:dev|start|build)\b|\bnode\b[^;&|]*server\.js/;

/** npm's own run-shaped lifecycle names. Derived-plus-named on purpose: the
 *  content arm catches a NEW door, the name arm keeps the set non-empty after
 *  the known ones are closed — a set that empties itself is a vacuous gate. */
const LIFECYCLE = new Set(['dev', 'start', 'build', 'serve']);

export function appDoors(scripts: Record<string, string>): string[] {
  return Object.keys(scripts)
    .filter((n) => LIFECYCLE.has(n) || RUN_SHAPE.test(scripts[n]))
    .sort();
}

export function isClosed(command: string): boolean {
  return !RUN_SHAPE.test(command) && /\bexit\s+[1-9]/.test(command);
}

function scriptsOf(path: string): Record<string, string> {
  return (JSON.parse(readFileSync(path, 'utf8')) as { scripts?: Record<string, string> }).scripts ?? {};
}

describe('#307 — every start door for the retired CRM is closed or recorded', () => {
  it('no compose service builds or runs apps/meddoc-pro', () => {
    const svcs = composeDoc().services ?? {};
    const offenders = Object.entries(svcs)
      .filter(([, def]) => JSON.stringify(def ?? {}).includes('apps/meddoc-pro'))
      .map(([name]) => name);
    expect(offenders).toEqual([]);
  });

  it('every run-shaped script in apps/meddoc-pro refuses', () => {
    const scripts = scriptsOf(APP_PKG);
    const doors = appDoors(scripts);
    const open = doors.filter((n) => !isClosed(scripts[n]));
    expect(
      open,
      'A script in the retired CRM still starts or rebuilds it. `next start` there ' +
        'serves the identical app against the production clinical database with ' +
        'docker not involved at all — the door the #307 compose removal does not ' +
        'reach. Make it refuse, or say in the declaration why it may stay open.',
    ).toEqual([]);
  });

  it('every root script that delegates into the retired CRM inherits the refusal', () => {
    const root = scriptsOf(ROOT_PKG);
    const appScripts = scriptsOf(APP_PKG);
    const doors = new Set(appDoors(appScripts));

    const leaks: string[] = [];
    for (const [name, cmd] of Object.entries(root)) {
      // A root script that runs the app itself, without delegating.
      if (RUN_SHAPE.test(cmd) && /meddoc-pro/.test(cmd)) {
        leaks.push(`${name}: ${cmd}`);
        continue;
      }
      const m = /npm\s+run\s+([\w:.-]+)\s+-w\s+meddoc-pro\b/.exec(cmd);
      if (!m) continue;
      const target = m[1];
      if (doors.has(target) && !isClosed(appScripts[target] ?? '')) {
        leaks.push(`${name} -> meddoc-pro:${target}`);
      }
    }
    expect(
      leaks,
      'A root script reaches an OPEN run door in the retired CRM. The closure is ' +
        'meant to have exactly one reader (the workspace package.json); this says ' +
        'the delegation no longer lands on a closed one.',
    ).toEqual([]);
  });

  it('the declaration NAMES the doors this change does not close', () => {
    const decl = readFileSync(DECLARATION, 'utf8');
    // ⚠️ These are the identifiers of the two doors a commit cannot close. The
    // defect this whole repair answers was a claim wider than its mechanism; if
    // the residual doors stop being named, the claim silently widens again.
    for (const needle of ['meddoc-pro-meddoc-pro-1', 'docker start', '.next/standalone']) {
      expect(
        decl.includes(needle),
        `the §2.5 declaration no longer names the residual door '${needle}'. ` +
          'A retirement note that lists only what it closed reads as a closure.',
      ).toBe(true);
    }
  });

  // ── CONTROLS ──────────────────────────────────────────────────────────────

  it('POSITIVE CONTROL — the door set is non-empty and the classifier discriminates', () => {
    const scripts = scriptsOf(APP_PKG);
    const doors = appDoors(scripts);
    expect(doors.length).toBeGreaterThan(0);
    expect(doors).toContain('start');
    expect(doors).toContain('dev');
    expect(doors).toContain('build');
    // Not everything is a door: the app has scripts that are not run-shaped.
    expect(Object.keys(scripts).length).toBeGreaterThan(doors.length);
    expect(doors).not.toContain('lint');
  });

  it('DISCRIMINATION CONTROL — an open door is reported and a closed one is not', () => {
    const planted = {
      start: 'next start',
      dev: "echo 'retired' >&2; exit 1",
      serve: 'node .next/standalone/apps/meddoc-pro/server.js',
      lint: 'eslint',
      'test:unit': 'vitest run',
    };
    expect(appDoors(planted)).toEqual(['build', 'dev', 'serve', 'start'].filter((n) => n in planted).sort());
    expect(appDoors(planted).filter((n) => !isClosed(planted[n as keyof typeof planted]))).toEqual([
      'serve',
      'start',
    ]);
    // A refusal that forgets to exit is not a closure.
    expect(isClosed("echo 'retired'")).toBe(false);
    // Nor is one that still runs the thing.
    expect(isClosed("next start; exit 1")).toBe(false);
  });
});
