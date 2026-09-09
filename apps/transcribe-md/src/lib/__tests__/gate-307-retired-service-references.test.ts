// ============================================================================
// A REMOVED COMPOSE SERVICE LEAVES ITS PROCEDURES BEHIND, AND NOTHING SAYS SO
// ----------------------------------------------------------------------------
// Ruling #307 deleted the `meddoc-pro` service from `docker-compose.yml`. The
// commit touched two files. It did not touch the EIGHT tracked procedures that
// tell an operator to run that service by name — and nothing anywhere would
// have told it to.
//
// ⚠️ THE COST IS NOT COSMETIC, BECAUSE ONE OF THEM DISMANTLES A SAFETY CONTROL
// BEFORE THE STEP THAT NOW ERRORS. `DEPLOYMENT_RUNBOOK.md` §3.5 restores
// `pro.quillmd.com` by (1) deleting the host-nginx 410 block, (2) putting the
// hostname back on `:443`, (3) `systemctl reload nginx`, (4) bringing the
// service up. After #307 step 4 fails with `no such service: meddoc-pro` — and
// §3.5 has no step 5. The operator is left on a hostname whose termination was
// an owner ruling, answering the exact state `scripts/check-cotenants.sh` calls
// THE FINDING: *"a 502 wearing its place"*.
//
// ⚠️ AND THE CLASS HAD ALREADY BITTEN THIS REPO UNNOTICED. Before #307,
// `RUNBOOK_ENCRYPTED_VOLUME.md` §2.2/§2.6/§4 named `patient-app` and
// `meddoc-pro-clinician` in five compose invocations. Neither service has ever
// existed in this file. That staleness sat in a data-migration runbook — the
// kind you read at 03:00 with postgres stopped — for months, green.
//
// ⚠️ SO THE FIX IS NOT "UPDATE THE RUNBOOK". A per-instance repair leaves the
// class open for whoever removes the NEXT service, and they will not read this
// file either. The reference set is DERIVED from the tree and every service
// named in an instruction must exist.
//
// ── WHAT IS WATCHED, AND WHY THE EXCLUSIONS ARE NOT HOLES ───────────────────
// The gate watches INSTRUCTIONS. A record of a past act is not an instruction,
// and rewriting one to satisfy a linter would be falsifying history — so two
// kinds of record are out of scope, both by the same principle:
//
//   · dated report/declaration directories (`docs/deploy-reports/`,
//     `docs/preflight-reports/`, `docs/qa-reports/`, `docs/audit-reports/`,
//     `docs/deploy-declarations/`, `docs/foundation/deploys|mutations/`), and
//   · TICKED checklist items (`- [x]`), which assert a step was already run.
//
// ⚠️ THE SECOND IS AN AVAILABLE BYPASS AND IS NAMED HERE RATHER THAN HIDDEN:
// ticking a box silences this gate for that line. Ticking a box is also a claim
// that the step was performed, which is a lie somebody signs. The alternative —
// forcing history to be rewritten — is worse.
//
// ⚠️ AND THE EXTRACTOR ONLY BELIEVES WHAT THE DOCUMENT ITSELF MARKS AS A
// COMMAND: fenced blocks and inline code spans in markdown, non-comment lines
// in shell. A first draft that read whole lines scored 1145 "findings", almost
// all of them English — `docker compose ps` followed by "shows worker healthy
// but ..." yielded the services `shows`, `worker`, `healthy`, `but`. A check
// that noisy gets muted, and a muted check is an absent one.
// ============================================================================
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

/** Repo root, from `apps/transcribe-md` (the vitest CWD). */
const REPO = join(process.cwd(), '..', '..');
const COMPOSE = join(REPO, 'docker-compose.yml');

/** ⚠️ MISSING IS A FAILURE, NEVER A SKIP — same doctrine as
 *  `gate-workflows-parse`. `js-yaml` reaches this tree transitively. */
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

export function definedServices(composeSrc: string): Set<string> {
  const doc = loadYaml()(composeSrc) as { services?: Record<string, unknown> };
  return new Set(Object.keys(doc?.services ?? {}));
}

/** Directories whose contents are RECORDS of past acts, not instructions. */
const RECORD_DIRS = [
  'docs/deploy-reports/',
  'docs/deploy-logs/',
  'docs/preflight-reports/',
  'docs/qa-reports/',
  'docs/audit-reports/',
  'docs/deploy-declarations/',
  'docs/foundation/deploys/',
  'docs/foundation/mutations/',
];

export function isRecord(path: string): boolean {
  return RECORD_DIRS.some((d) => path.startsWith(d));
}

export function isWatched(path: string): boolean {
  if (isRecord(path)) return false;
  return path.endsWith('.md') || path.endsWith('.sh');
}

/** Verbs whose every positional argument is a service name. */
const SERVICES_ALL = new Set([
  'up', 'stop', 'start', 'restart', 'build', 'rm', 'logs',
  'pull', 'create', 'kill', 'ps', 'pause', 'unpause', 'port',
]);
/** Verbs whose FIRST positional is a service and the rest is a command. */
const SERVICES_FIRST = new Set(['exec', 'run']);

/** Flags that consume the following token, so it is never a service name. */
const FLAGS_WITH_VALUE = new Set([
  '-f', '--file', '-p', '--project-name', '--profile', '--project-directory',
  '--env-file', '--tail', '--since', '--until', '-e', '--env', '-v', '--volume',
  '-w', '--workdir', '--entrypoint', '--scale', '-u', '--user', '--index',
  '-l', '--label', '--timeout', '-t', '--format', '--memory', '-m',
  '--publish', '--name',
]);

/** Everything after these is shell plumbing or prose, never a service. */
const TAIL = /\s(?:#|\|\||\||&&|;|>|2>)/;

export type Ref = { line: number; verb: string; service: string; text: string };

/** Spans the DOCUMENT ITSELF marks as a command. */
function commandSpans(path: string, text: string): { line: number; cmd: string }[] {
  const out: { line: number; cmd: string }[] = [];
  const lines = text.split('\n');
  if (path.endsWith('.sh')) {
    lines.forEach((l, i) => {
      const s = l.trim();
      if (s && !s.startsWith('#')) out.push({ line: i + 1, cmd: l });
    });
    return out;
  }
  let inFence = false;
  lines.forEach((l, i) => {
    if (l.trimStart().startsWith('```')) {
      inFence = !inFence;
      return;
    }
    if (inFence) {
      out.push({ line: i + 1, cmd: l });
      return;
    }
    // A TICKED checklist item records a completed act — see the header.
    if (/^\s*[-*]\s*\[x\]/i.test(l)) return;
    for (const m of l.matchAll(/`([^`\n]+)`/g)) out.push({ line: i + 1, cmd: m[1] });
  });
  return out;
}

/** Every compose service named by a command in this document. */
export function composeServiceRefs(path: string, text: string): Ref[] {
  const refs: Ref[] = [];
  for (const { line, cmd } of commandSpans(path, text)) {
    const m = /docker[-\s]compose\b/.exec(cmd);
    if (!m) continue;
    let rest = cmd.slice(m.index + m[0].length);
    const cut = TAIL.exec(rest);
    if (cut) rest = rest.slice(0, cut.index);
    const toks = rest.replace(/\\/g, ' ').trim().split(/\s+/).filter(Boolean);

    let i = 0;
    let verb: string | undefined;
    while (i < toks.length) {
      const t = toks[i];
      if (FLAGS_WITH_VALUE.has(t)) { i += 2; continue; }
      if (t.startsWith('-')) { i += 1; continue; }
      verb = t;
      break;
    }
    if (!verb || !(SERVICES_ALL.has(verb) || SERVICES_FIRST.has(verb))) continue;

    const positionals: string[] = [];
    i += 1;
    while (i < toks.length) {
      const t = toks[i];
      if (FLAGS_WITH_VALUE.has(t)) { i += 2; continue; }
      if (t.startsWith('-')) { i += 1; continue; }
      positionals.push(t);
      i += 1;
    }
    const named = SERVICES_FIRST.has(verb) ? positionals.slice(0, 1) : positionals;
    for (const s of named) {
      if (!/^[a-z][a-z0-9._-]*$/.test(s)) continue;
      refs.push({ line, verb, service: s, text: cmd.trim().slice(0, 120) });
    }
  }
  return refs;
}

function watchedFiles(): string[] {
  return execFileSync('git', ['ls-files'], { cwd: REPO, encoding: 'utf8' })
    .split('\n')
    .filter(isWatched);
}

function allRefs(): { file: string; ref: Ref }[] {
  const out: { file: string; ref: Ref }[] = [];
  for (const f of watchedFiles()) {
    let text: string;
    try {
      text = readFileSync(join(REPO, f), 'utf8');
    } catch {
      continue;
    }
    for (const ref of composeServiceRefs(f, text)) out.push({ file: f, ref });
  }
  return out;
}

describe('#307 — every compose service named by a tracked instruction exists', () => {
  it('names no service that docker-compose.yml does not define', () => {
    const services = definedServices(readFileSync(COMPOSE, 'utf8'));
    const dangling = allRefs()
      .filter(({ ref }) => !services.has(ref.service))
      .map(({ file, ref }) => `${file}:${ref.line}  ${ref.verb} -> '${ref.service}'   | ${ref.text}`);

    expect(
      dangling,
      'A tracked procedure names a compose service that does not exist. Following ' +
        'it errors `no such service: <name>` — and §3.5 is the proof that the ' +
        'error can arrive AFTER a safety control has already been dismantled. ' +
        'Update the procedure in the commit that removes the service.',
    ).toEqual([]);
  });

  // ── CONTROLS ──────────────────────────────────────────────────────────────
  // ⚠️ The arm above passes when the corpus is empty, when the parser is blind,
  // and when every file was excluded. Each of those is proved false separately.

  it('POSITIVE CONTROL — the compose file parses and #307 actually landed', () => {
    const services = definedServices(readFileSync(COMPOSE, 'utf8'));
    expect(services.has('transcribe-md')).toBe(true);
    expect(services.has('caddy')).toBe(true);
    expect(services.has('postgres')).toBe(true);
    // The fact under test: the service is gone. If this flips, the gate above
    // starts passing for the WRONG reason.
    expect(services.has('meddoc-pro')).toBe(false);
  });

  it('POSITIVE CONTROL — the watched corpus is non-empty in the files that matter', () => {
    const refs = allRefs();
    const byFile = new Map<string, number>();
    for (const { file } of refs) byFile.set(file, (byFile.get(file) ?? 0) + 1);

    // Named rather than counted: a threshold rots, a named procedure does not.
    for (const f of [
      'docs/DEPLOYMENT_RUNBOOK.md',
      'docs/ROTATION_RUNBOOK.md',
      'docs/runbooks/disaster-recovery.md',
      'docs/RUNBOOK_ENCRYPTED_VOLUME.md',
    ]) {
      expect(
        byFile.get(f) ?? 0,
        `${f} is a compose procedure and the extractor read NO service reference ` +
          'out of it. Either the file moved, or the extractor stopped working — ' +
          'and a silent zero here makes the arm above vacuous.',
      ).toBeGreaterThan(0);
    }
    expect(byFile.size).toBeGreaterThan(5);
  });

  it('DISCRIMINATION CONTROL — the extractor catches a planted bad reference, and does not invent one', () => {
    const doc = [
      '# planted',
      '',
      '```bash',
      'docker compose up -d transcribe-md transcribe-md-worker',
      'docker compose up -d ghost-service',
      'docker compose exec -T postgres psql -U meddoc -d meddoc',
      '```',
      '',
      'Prose: `docker compose ps` shows worker healthy but the queue is growing.',
      '',
      '- [x] `docker compose up -d ghost-service`',
      '- [ ] `docker compose stop ghost-service`',
    ].join('\n');

    const got = composeServiceRefs('docs/planted.md', doc);
    const names = got.map((r) => `${r.verb}:${r.service}`).sort();

    // Real services are read, the planted ghost is read, the ticked one is not,
    // and English after a code span is not mistaken for a service list.
    expect(names).toEqual([
      'exec:postgres',
      'stop:ghost-service',
      'up:ghost-service',
      'up:transcribe-md',
      'up:transcribe-md-worker',
    ]);

    const services = definedServices(readFileSync(COMPOSE, 'utf8'));
    expect(got.filter((r) => !services.has(r.service)).map((r) => r.service)).toEqual([
      'ghost-service',
      'ghost-service',
    ]);
  });

  it('DISCRIMINATION CONTROL — the record exclusions do not swallow a procedure', () => {
    expect(isWatched('docs/DEPLOYMENT_RUNBOOK.md')).toBe(true);
    expect(isWatched('docs/runbooks/disaster-recovery.md')).toBe(true);
    expect(isWatched('scripts/deploy-prod.sh')).toBe(true);
    expect(isRecord('docs/preflight-reports/preflight-20260101T000000Z.md')).toBe(true);
    expect(isRecord('docs/deploy-declarations/307-retire-meddoc-pro-service-20260909.md')).toBe(true);
    // Source is never scanned — this test file names `ghost-service` itself, and
    // a probe whose pattern appears in the probe cannot return false.
    expect(isWatched('apps/transcribe-md/src/lib/__tests__/gate-307-retired-service-references.test.ts')).toBe(false);
  });
});
