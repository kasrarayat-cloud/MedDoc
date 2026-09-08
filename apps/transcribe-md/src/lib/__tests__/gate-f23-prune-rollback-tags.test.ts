// ============================================================================
// F23 — ROLLBACK TAGS ARE PRUNED BY NAME, AND THE KEEP SET IS A UNION.
// ----------------------------------------------------------------------------
// Ruling #137. `docker image prune -a` removes every image no CONTAINER
// references — TAGGED ONES INCLUDED — and this host holds ~150
// `meddoc-pro-*:pre-…` rollback tags, the only artifact that makes a past
// deploy reversible. Preflight's Check 2 used to prescribe exactly that sweep.
// `scripts/ops/prune-rollback-tags.sh` is its sanctioned replacement.
//
// ── WHAT THIS GATE WATCHES, DIFFED AGAINST WHAT RULING #137 NAMES ───────────
// #137 and RELAY F23 name six things. Each is a describe block below:
//
//   "KEEP SET (ruling #297): the last 5 JUDGED deploys' pre-* tags PLUS any tag <= 72h old.
//    Union, not intersection."              -> `the keep set is a UNION`
//   "the 10-deploy arm and the 14-day arm are proved SEPARATELY, because a
//    union whose arms are only ever tested together cannot show that either
//    one works — a script keeping everything satisfies both."
//                                           -> the two arm-alone arms, which
//                                              assert the REASON on each row,
//                                              not merely the survival
//   "DRY-RUN BY DEFAULT."                   -> `clause 1 — DRY RUN`
//   "The KEEP-LIST is PRINTED BEFORE any deletion."
//                                           -> `clause 2 — KEEP FIRST`
//   "Deletion is BY NAME. Never -a, never a bare --filter."
//                                           -> `clause 3 — BY NAME`
//   "a tag inside the keep set is NOT deleted — and a tag outside it IS"
//                                           -> both directions, in every arm
//
// ── WHAT IT DRIVES ─────────────────────────────────────────────────────────
// The REAL script, run by a real bash. Nothing here re-implements the keep-set
// logic — a second copy would drift from the first the day either is fixed.
//
// The inventory is fed through the script's documented `_INVENTORY` hook and
// `docker` is replaced by a PATH STUB that records every argv it is handed.
// That is what makes the DELETE path provable in CI with no daemon, no images
// and no risk: the arms below assert the exact `rmi <name>` calls that would
// have been made, and assert their ABSENCE on a dry run.
//
// ⚠️ HONEST LIMITS, STATED SO THE GREEN IS NOT READ WIDER THAN IT IS:
//
//   1. THE STUB IS NOT DOCKER. It proves which commands the script ISSUES, not
//      what a daemon does with them. The real delete path was exercised
//      in-session on 2026-08-21 against THROWAWAY tags minted for the purpose
//      (`docker tag` of an existing image to `pre-<hex>-<old date>`), run with
//      `--delete`, and confirmed gone with the real 152 untouched. The
//      transcript is in RELAY's F23 row. A daemon-mutating arm has no place in
//      CI on a shared runner.
//   2. IT DOES NOT PROVE THE GRANT. `.claude/settings.json` naming this script
//      is asserted by an arm below as SOURCE TEXT only; whether the permission
//      layer honours it is not a question a test in this repo can answer.
//   3. THE `--delete` ARMS RUN WITH A STUB THAT ALWAYS SUCCEEDS UNLESS TOLD
//      OTHERWISE. The failure path is proved by the arm that tells it to fail.
// ============================================================================

import { execFileSync } from 'node:child_process';
import { chmodSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const REPO_ROOT = `${__dirname}/../../../../..`;
const SCRIPT = join(REPO_ROOT, 'scripts/ops/prune-rollback-tags.sh');
const SETTINGS = join(REPO_ROOT, '.claude/settings.json');

// "Today" for every arm. Fixed, so the arms describe a date arithmetic that
// cannot drift into passing (or failing) with the wall clock.
const TODAY = '20260821';
const CUTOFF = '20260818'; // TODAY - 3 days (72h), inclusive — ruling #297

let TMP: string;

beforeAll(() => {
  TMP = mkdtempSync(join(tmpdir(), 'f23-prune-'));
});

afterAll(() => {
  // The FOUNDATION loop cannot reap — `shred` and `rm` are denied to it by
  // design — so a gate that mints a directory per run mints scratch the only
  // actor present cannot delete.
  rmSync(TMP, { recursive: true, force: true });
});

type Row = { repo?: string; tag: string; id?: string; created?: string };
type Run = { code: number; out: string; rmi: string[]; argv: string[][] };

let seq = 0;

/** One `docker images --format` line. */
function line(r: Row): string {
  const repo = r.repo ?? 'meddoc-pro-transcribe-md';
  const id = r.id ?? `img${(seq++).toString(16).padStart(8, '0')}`;
  const created = r.created ?? '2026-08-01 00:00:00 +0000 UTC';
  return `${repo}:${r.tag}\t${id}\t${created}`;
}

/**
 * Run the REAL script against a synthetic inventory, with `docker` stubbed by
 * a shim that appends its argv to a log. `failOn` makes the shim exit 1 for a
 * chosen argument, which is the only way to reach the failure path.
 */
function run(
  rows: Row[],
  opts: { args?: string[]; inUse?: string[]; now?: string; failOn?: string; rawInventory?: string; judged?: string[] } = {},
): Run {
  const dir = join(TMP, `r${seq++}`);
  execFileSync('mkdir', ['-p', join(dir, 'bin')]);

  const invFile = join(dir, 'inventory.txt');
  writeFileSync(invFile, opts.rawInventory ?? rows.map(line).join('\n') + (rows.length ? '\n' : ''));

  const argvLog = join(dir, 'argv.log');
  const stub = join(dir, 'bin', 'docker');
  writeFileSync(
    stub,
    [
      '#!/usr/bin/env bash',
      `printf '%s\\n' "$*" >> ${JSON.stringify(argvLog)}`,
      opts.failOn
        ? `for a in "$@"; do [ "$a" = ${JSON.stringify(opts.failOn)} ] && { echo "stub: refusing $a" >&2; exit 1; }; done`
        : '',
      'exit 0',
    ].join('\n') + '\n',
  );
  chmodSync(stub, 0o755);
  writeFileSync(argvLog, '');

  const env: NodeJS.ProcessEnv = {
    ...process.env,
    PATH: `${join(dir, 'bin')}:${process.env.PATH ?? ''}`,
    PRUNE_ROLLBACK_TAGS_INVENTORY: invFile,
    PRUNE_ROLLBACK_TAGS_NOW: opts.now ?? TODAY,
  };
  // ⚠️ #297 — THE FIXTURE DECLARES WHICH DEPLOYS WERE JUDGED. A deploy is
  // judged when a §2.5 declaration `<YYYYMMDD>-<sha>.md` exists for its date,
  // and only a judged deploy consumes one of the five keep slots. Default:
  // every date present in the inventory is judged, so the arms that are about
  // RANKING can be written without thinking about judgement. `judged: [...]`
  // overrides it, and `judged: []` exercises the fail-closed probe.
  const declDir = join(dir, 'decls');
  execFileSync('mkdir', ['-p', declDir]);
  // ⚠️ READ FROM THE INVENTORY THAT WILL ACTUALLY BE USED, not from `rows`. The
  // `rawInventory` arms pass `rows: []`, so deriving from `rows` wrote ZERO
  // declarations and the fail-closed probe refused them — a harness gap that
  // looked exactly like a policy failure.
  const inventoryText = opts.rawInventory ?? rows.map(line).join('\n');
  const judgedDates =
    opts.judged ??
    [...new Set([...inventoryText.matchAll(/-(\d{8})(?:\s|$)/gm)].map((m) => m[1]))];
  for (const d of judgedDates as string[]) {
    writeFileSync(join(declDir, `${d}-deadbeef.md`), '# synthetic declaration\n');
  }
  env.PRUNE_ROLLBACK_TAGS_JUDGED_DIR = declDir;

  if (opts.inUse) {
    const f = join(dir, 'inuse.txt');
    writeFileSync(f, opts.inUse.join('\n') + '\n');
    env.PRUNE_ROLLBACK_TAGS_INUSE = f;
  }

  let code = 0;
  let out = '';
  try {
    out = execFileSync('bash', [SCRIPT, ...(opts.args ?? [])], {
      encoding: 'utf8',
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } catch (e) {
    const err = e as { status?: number; stdout?: string; stderr?: string };
    code = err.status ?? -1;
    out = `${err.stdout ?? ''}${err.stderr ?? ''}`;
  }

  const argv = readFileSync(argvLog, 'utf8')
    .split('\n')
    .filter(Boolean)
    .map((l) => l.split(' '));
  const rmi = argv.filter((a) => a[0] === 'rmi').map((a) => a[1]);
  return { code, out, rmi, argv };
}

/** The tags the run reports as deletable, read out of the DELETABLE block. */
function deletable(out: string): string[] {
  const start = out.indexOf('──────── DELETABLE');
  const end = out.indexOf('  reconciliation');
  if (start < 0 || end < 0) return [];
  return out
    .slice(start, end)
    .split('\n')
    .filter((l) => l.trimStart().startsWith('✗ '))
    .map((l) => l.trim().replace(/^✗\s+/, '').split(/\s{2,}/)[0]);
}

/** The keep rows as `suffix -> reason`. */
function keepReasons(out: string): Record<string, string> {
  const start = out.indexOf('──────── KEEP');
  const end = out.indexOf('──────── DELETABLE');
  const seg = start >= 0 && end >= 0 ? out.slice(start, end) : '';
  const map: Record<string, string> = {};
  for (const l of seg.split('\n')) {
    const m = l.match(/^\s*✔ (\S+)\s+rank\s+#\d+\s+date \d{8}\s+\((.+)\)\s*$/);
    if (m) map[m[1]] = m[2];
  }
  return map;
}

/** `n` deploys, newest first, one per date walking backwards from `from`. */
function deploys(n: number, from: string, repos = ['meddoc-pro-transcribe-md']): Row[] {
  const rows: Row[] = [];
  const y = Number(from.slice(0, 4));
  const mo = Number(from.slice(4, 6));
  const d0 = Number(from.slice(6, 8));
  for (let i = 0; i < n; i++) {
    const dt = new Date(Date.UTC(y, mo - 1, d0 - i));
    const ymd = dt.toISOString().slice(0, 10).replace(/-/g, '');
    const sha = (0xa0000000 + i).toString(16);
    // CreatedAt DESCends with the deploy, matching the real host.
    const created = `${dt.toISOString().slice(0, 10)} 12:00:00 +0000 UTC`;
    for (const repo of repos) rows.push({ repo, tag: `pre-${sha}-${ymd}`, created });
  }
  return rows;
}

// ---------------------------------------------------------------------------

describe('F23 — non-vacuity, asserted before any partition is believed', () => {
  // ⚠️ THIS ARM EXISTS BECAUSE IT CAUGHT THE REAL DEFECT. The first draft
  // assigned the deploy ordering to a variable named `GROUPS` — a bash SPECIAL
  // ARRAY holding the user's group ids. The assignment was silently IGNORED,
  // `"$GROUPS"` expanded to the gid `1000`, every deploy collapsed into one
  // group, and the script printed a cheerful green
  // `0 tag(s) would be removed` against 152 real tags.
  //
  // Nothing else here would have failed: keep-list empty, delete-list empty,
  // reconciliation self-consistent, exit 0. A script that keeps everything
  // satisfies every "is X kept?" assertion in this file.
  it('a 12-deploy fixture is SEEN as 12 deploys, not collapsed', () => {
    const r = run(deploys(12, '20260821'));
    expect(r.out).toContain('12  = 12 dated + 0 unclassifiable');
    expect(r.out).toMatch(/KEEP — \d+ of 12 deploys SURVIVE/);
    expect(Object.keys(keepReasons(r.out)).length).toBeGreaterThan(1);
  });

  it('the same fixture across TWO repositories is still 12 deploys, 24 tags', () => {
    const r = run(deploys(12, '20260821', ['meddoc-pro-transcribe-md', 'meddoc-pro-transcribe-md-worker']));
    expect(r.out).toContain('24  = 24 dated + 0 unclassifiable');
    expect(r.out).toMatch(/of 12 deploys SURVIVE/);
  });

  it('a run where everything is inside the keep set deletes nothing and exits 0', () => {
    const r = run(deploys(3, '20260821'));
    expect(r.code).toBe(0);
    expect(deletable(r.out)).toEqual([]);
    expect(r.rmi).toEqual([]);
  });
});

describe('#297 — JUDGED is load-bearing, and the probe for it fails CLOSED', () => {
  it('⚠️ ZERO DECLARATIONS IS A REFUSAL, NOT AN ANSWER — and nothing is deleted', () => {
    // ⚠️ THE WORST FAILURE THIS SCRIPT COULD HAVE. #297 keeps the last five
    // JUDGED deploys, so if the declarations directory is missing or empty then
    // NOTHING is judged, the count arm keeps nothing, and every tag past 72h
    // becomes deletable in a single run — the script would offer to delete the
    // entire rollback path while printing a confident keep-list of zero.
    const r = run(deploys(12, '20260701'), { judged: [], args: ['--delete'] });

    expect(r.code, 'a broken judged-probe did not refuse').toBe(2);
    expect(r.out).toContain('CANNOT TELL');
    // AND THE ACT DID NOT HAPPEN. A refusal that still deletes is not a refusal.
    expect(r.rmi, 'it deleted despite refusing').toEqual([]);
  });

  it('⚠️ AN UNJUDGED DEPLOY CONSUMES NO SLOT — five unjudged cannot evict five real ones', () => {
    // Counting an unjudged deploy toward the five would let a run of unjudged
    // deploys exhaust the arm and evict five genuine rollback targets, which is
    // the opposite of what #297 asks for. Here the six NEWEST deploys are
    // unjudged; the five older judged ones must still hold every slot.
    const rows = deploys(11, '20260701');
    const judged = ['20260626', '20260625', '20260624', '20260623', '20260622'];
    const r = run(rows, { judged });
    const kept = keepReasons(r.out);

    expect(Object.keys(kept).sort()).toEqual(
      [
        'pre-a0000005-20260626',
        'pre-a0000006-20260625',
        'pre-a0000007-20260624',
        'pre-a0000008-20260623',
        'pre-a0000009-20260622',
      ].sort(),
    );
    for (const reason of Object.values(kept)) expect(reason).toBe('judged-top-5');

    // …and the six unjudged NEWER deploys are the ones that go, which is the
    // whole point: recency alone does not buy a slot.
    expect(deletable(r.out)).toHaveLength(6);
  });
});

describe('F23 — the keep set is a UNION, and each arm is proved ALONE', () => {
  // ARM 1 ALONE. Every deploy is far older than 72 hours, so the date arm can
  // keep nothing. Only the judged-top-5 arm is load-bearing here.
  it('THE 5-JUDGED-DEPLOY ARM ALONE — 12 ancient deploys, newest 5 kept, oldest 7 deleted', () => {
    const rows = deploys(12, '20260701'); // all ~7 weeks old
    const r = run(rows);
    const kept = keepReasons(r.out);

    expect(Object.keys(kept)).toHaveLength(5);
    // Every survivor is here on the COUNT arm and nothing else — if the date
    // arm were contributing, a reason would read `<=3d`.
    for (const reason of Object.values(kept)) expect(reason).toBe('judged-top-5');

    expect(deletable(r.out)).toEqual([
      'meddoc-pro-transcribe-md:pre-a0000005-20260626',
      'meddoc-pro-transcribe-md:pre-a0000006-20260625',
      'meddoc-pro-transcribe-md:pre-a0000007-20260624',
      'meddoc-pro-transcribe-md:pre-a0000008-20260623',
      'meddoc-pro-transcribe-md:pre-a0000009-20260622',
      'meddoc-pro-transcribe-md:pre-a000000a-20260621',
      'meddoc-pro-transcribe-md:pre-a000000b-20260620',
    ]);
  });

  // ARM 2 ALONE. Four deploys inside 72 hours plus one ancient. With the
  // judged arm deliberately EMPTIED (nothing judged), the count arm keeps
  // nothing at all — so every survivor here is the date arm's doing, and the
  // ancient one going proves the date arm is not simply keeping everything.
  //
  // ⚠️ THIS IS THE ARM THAT CHANGED MOST UNDER #297, and the reason is worth
  // stating: with 5 slots and a 3-day window the two arms overlap so heavily
  // that "rank #11 survives on the date arm" is no longer constructible. The
  // clean way to prove ONE arm alone is now to switch the other OFF, which the
  // `judged` seam makes possible.
  it('THE 72-HOUR ARM ALONE — with NOTHING judged, only the date arm can keep', () => {
    const rows = [...deploys(4, '20260821'), ...deploys(1, '20260801')];
    // ⚠️ NOT `judged: []` — that is ZERO declarations, which the fail-closed
    // probe REFUSES by design (with nothing judged the keep-set would collapse
    // and the run would offer to delete the whole rollback path). The way to
    // switch the count arm off is a declaration that exists and matches NO
    // deploy here, which is also the "an unjudged deploy consumes no slot"
    // case in its purest form.
    const r = run(rows, { judged: ['20200101'] });
    const kept = keepReasons(r.out);

    expect(Object.keys(kept)).toHaveLength(4);
    for (const reason of Object.values(kept)) expect(reason).toBe('<=3d');

    // …and the one outside both arms goes.
    expect(deletable(r.out)).toEqual(['meddoc-pro-transcribe-md:pre-a0000000-20260801']);
  });

  it('a deploy satisfying BOTH arms says so, so the two are distinguishable in the output', () => {
    // 8 daily deploys: ranks 1-4 are inside 72h AND inside the top 5 (both
    // arms); rank 5 is top-5 only; ranks 6-8 are outside both.
    const r = run(deploys(8, '20260821'));
    const kept = keepReasons(r.out);
    expect(kept['pre-a0000000-20260821']).toBe('judged-top-5 + <=3d');
    expect(kept['pre-a0000004-20260817']).toBe('judged-top-5');
  });

  it('the 72-hour boundary is INCLUSIVE — the cutoff date itself is kept, the day before is not', () => {
    // ⚠️ THE FIXTURE PACKS TWO DEPLOYS PER DAY, AND #297 IS WHY. With five keep
    // slots and a three-day window, five DAILY deploys always reach back past
    // the window — the count arm strictly CONTAINS the date arm, and no tag can
    // survive on the date arm alone. The date arm only adds something when more
    // than five deploys land inside 72 hours, i.e. several in one day, which is
    // this programme's actual cadence (two deploys on 2026-09-07).
    //
    // So: six deploys across three recent days spend ranks 1-5 and leave rank 6
    // alive on the date arm, and the two boundary tags below sit at ranks 7-8
    // where only the date arm can reach them.
    const rows = [
      { tag: 'pre-a0000000-20260821', created: '2026-08-21 18:00:00 +0000 UTC' },
      { tag: 'pre-a0000001-20260821', created: '2026-08-21 09:00:00 +0000 UTC' },
      { tag: 'pre-a0000002-20260820', created: '2026-08-20 18:00:00 +0000 UTC' },
      { tag: 'pre-a0000003-20260820', created: '2026-08-20 09:00:00 +0000 UTC' },
      { tag: 'pre-a0000004-20260819', created: '2026-08-19 18:00:00 +0000 UTC' },
      { tag: 'pre-a0000005-20260819', created: '2026-08-19 09:00:00 +0000 UTC' },
      { tag: `pre-b0000001-${CUTOFF}`, created: '2026-08-18 09:00:00 +0000 UTC' }, // exactly 72h
      { tag: 'pre-b0000002-20260817', created: '2026-08-17 09:00:00 +0000 UTC' }, // a day past
    ];
    const r = run(rows);
    const kept = keepReasons(r.out);
    expect(kept[`pre-b0000001-${CUTOFF}`]).toBe('<=3d');
    expect(kept['pre-b0000002-20260817']).toBeUndefined();
    expect(deletable(r.out)).toEqual(['meddoc-pro-transcribe-md:pre-b0000002-20260817']);
  });
});

describe('F23 — the tag population has THREE shapes and all three are dated', () => {
  // ⚠️ THE REGRESSION ARM FOR THIS SCRIPT'S OWN FIRST DRAFT. A positional
  // regex of `^pre-<sha>-<date>$` classified 104 of the host's 152 real tags as
  // unparseable and therefore kept them forever — a script that would have
  // passed a keep-set test and reclaimed nothing.
  it('sha-then-date, label-then-date and date-then-label all parse', () => {
    const rows = [
      { tag: 'pre-d7cc0246-20260821' }, // F9's automatic form
      { tag: 'pre-footer-20260815' }, // the pre-F9 manual habit
      { tag: 'pre-20260802-attest' }, // the manual habit, fields reversed
    ];
    const r = run(rows);
    expect(r.out).toContain('3  = 3 dated + 0 unclassifiable');
  });

  it('and the date is read from the TAG, never from the image CreatedAt', () => {
    // The real host: `pre-7c42d2d7-20260820` points at an image built on the
    // 19th, because a pre-* tag names the image that was running BEFORE the
    // deploy. Ageing by CreatedAt would age every tag by one deploy interval.
    // ⚠️ THE FIXTURE PACKS TWO DEPLOYS PER DAY — #297 again. Five DAILY deploys
    // reach back past a three-day window, so ranks 1-5 would already cover
    // everything inside it and no tag could be kept by the date arm alone.
    // Packing the days spends ranks 1-5 within the window and leaves rank 6
    // inside it too, which is the only shape that isolates the date arm.
    //
    // The subject: rank 6's tag DATE is inside 72h while its CreatedAt is over
    // a year and a half stale. Ageing by CreatedAt would delete it.
    const rows = [
      { tag: 'pre-a0000000-20260821', created: '2026-08-21 18:00:00 +0000 UTC' },
      { tag: 'pre-a0000001-20260821', created: '2026-08-21 09:00:00 +0000 UTC' },
      { tag: 'pre-a0000002-20260820', created: '2026-08-20 18:00:00 +0000 UTC' },
      { tag: 'pre-a0000003-20260820', created: '2026-08-20 09:00:00 +0000 UTC' },
      { tag: 'pre-a0000004-20260819', created: '2026-08-19 18:00:00 +0000 UTC' },
      { tag: 'pre-c0000001-20260819', created: '2025-01-01 00:00:00 +0000 UTC' },
    ];
    const r = run(rows);
    expect(keepReasons(r.out)['pre-c0000001-20260819']).toBe('<=3d');
    expect(deletable(r.out)).toEqual([]);
  });
});

describe('F23 — what cannot be classified is KEPT, and named', () => {
  const spent = deploys(5, '20260821'); // ranks 1-5 spent; nothing below is rescued by count

  it('a pre-* tag with NO date token is kept and listed', () => {
    const r = run([...spent, { tag: 'pre-hotfix' }]);
    expect(r.out).toContain('1 unclassifiable');
    expect(r.out).toContain('meddoc-pro-transcribe-md:pre-hotfix');
    expect(deletable(r.out)).toEqual([]);
    expect(r.rmi).toEqual([]);
  });

  it('a pre-* tag with TWO date tokens is AMBIGUOUS, and ambiguous is kept', () => {
    const r = run([...spent, { tag: 'pre-20200101-20260821' }]);
    expect(r.out).toContain('1 unclassifiable');
    expect(r.rmi).toEqual([]);
  });

  it('an 8-digit token that is not a real calendar date is not a date', () => {
    // 20261345 — month 13, day 45. If `date -d` validation were skipped this
    // would parse and the tag would be aged as if it were from the future.
    const r = run([...spent, { tag: 'pre-20261345-x' }]);
    expect(r.out).toContain('1 unclassifiable');
  });

  it('…and the control: a real date in the same position IS parsed', () => {
    const r = run([...spent, { tag: 'pre-20260721-x' }]);
    expect(r.out).toContain('0 unclassifiable');
    expect(deletable(r.out)).toEqual(['meddoc-pro-transcribe-md:pre-20260721-x']);
  });
});

describe('F23 — the watched set is exactly meddoc-pro-* rollback tags', () => {
  const spent = deploys(5, '20260821');

  it('a non-pre tag is never considered, whatever its age', () => {
    const r = run([...spent, { tag: 'latest' }, { tag: 'qa' }]);
    expect(r.out).toContain('5  = 5 dated + 0 unclassifiable');
    expect(r.rmi).toEqual([]);
    expect(r.out).not.toContain(':latest');
  });

  it('a co-tenant repository is counted separately and NEVER deleted', () => {
    // Co-tenants share this host and are untouchable.
    const r = run([...spent, { repo: 'someone-else', tag: 'pre-aaaaaaa-20200101' }]);
    expect(r.out).toContain('co-tenant pre-*   : 1');
    expect(deletable(r.out)).toEqual([]);
    expect(r.rmi).toEqual([]);
  });

  it('…and the control: the SAME ancient tag on our repository IS deletable', () => {
    const r = run([...spent, { repo: 'meddoc-pro-gotenberg', tag: 'pre-aaaaaaa-20200101' }]);
    expect(deletable(r.out)).toEqual(['meddoc-pro-gotenberg:pre-aaaaaaa-20200101']);
  });
});

describe('F23 — a container-backed image is HELD, never deleted', () => {
  const spent = deploys(5, '20260821');

  it('an out-of-keep-set tag whose image backs a container is held', () => {
    const rows = [...spent, { tag: 'pre-aaaaaaa-20200101', id: 'deadbeef1234' }];
    const r = run(rows, { inUse: ['sha256:deadbeef1234aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'] });
    expect(r.out).toContain('HELD, a container references this image');
    expect(deletable(r.out)).toEqual([]);
    expect(r.rmi).toEqual([]);
    expect(r.code).toBe(0);
  });

  it('…and the control: the same tag with nothing referencing it IS deleted', () => {
    const rows = [...spent, { tag: 'pre-aaaaaaa-20200101', id: 'deadbeef1234' }];
    const r = run(rows, { inUse: ['sha256:0000000000000000000000000000000000000000000000000000000000000000'], args: ['--delete'] });
    expect(r.rmi).toEqual(['meddoc-pro-transcribe-md:pre-aaaaaaa-20200101']);
  });

  it('a BLANK image id does not hold the entire delete list', () => {
    // `grep -qF -- ""` matches every line. Without the emptiness guard a single
    // malformed row would mark everything container-backed and report zero.
    const raw = [...spent.map(line), 'meddoc-pro-transcribe-md:pre-aaaaaaa-20200101\t\t2020-01-01 00:00:00 +0000 UTC'].join('\n');
    const r = run([], { rawInventory: raw + '\n', inUse: ['sha256:abc'] });
    expect(deletable(r.out)).toEqual(['meddoc-pro-transcribe-md:pre-aaaaaaa-20200101']);
  });

  // ⚠️ THIS ARM IS THE ONE THAT DISCRIMINATES THE INTERNAL SEPARATOR, AND IT
  // WAS ADDED BECAUSE A MUTATION PROOF SHOWED THE OTHERS DO NOT.
  // Reverting `SEP` from `\x1f` to a tab left all 35 arms GREEN: the manual
  // field split covers a blank *id* on its own. A blank *CreatedAt* is what
  // reaches the grouping rows — `date<SEP><SEP>tag` — where a tab IFS collapses
  // the pair and the deploy suffix reads back empty. The tag then falls out of
  // both buckets. With `\x1f` it groups normally; the assertion is that it is
  // classified at all, in whichever direction the dates dictate.
  it('a blank CreatedAt does not drop the tag out of the partition', () => {
    const raw = [
      ...spent.map(line),
      'meddoc-pro-transcribe-md:pre-aaaaaaa-20200101\tdeadbeef1234\t',
    ].join('\n');
    const r = run([], { rawInventory: raw + '\n', inUse: ['sha256:none'] });
    expect(r.code).toBe(0); // not the group-reconciliation CANNOT TELL
    expect(r.out).toContain('of 6 deploys SURVIVE');
    expect(deletable(r.out)).toEqual(['meddoc-pro-transcribe-md:pre-aaaaaaa-20200101']);
  });
});

describe('F23 — CANNOT TELL is distinguishable from a clean zero', () => {
  it('an inventory naming ZERO images of any kind is exit 2, not a green zero', () => {
    const r = run([]);
    expect(r.code).toBe(2);
    expect(r.out).toContain('CANNOT TELL');
    expect(r.rmi).toEqual([]);
  });

  it('…and the control: images present with no rollback tag is a REAL zero, exit 0', () => {
    const r = run([{ tag: 'latest' }, { tag: 'qa' }]);
    expect(r.code).toBe(0);
    expect(r.out).toContain('nothing to do');
  });

  it('an unreadable inventory override is exit 2', () => {
    const r = run([], { rawInventory: '' });
    // Non-existent path: point the hook at a file we never write.
    const dir = mkdtempSync(join(TMP, 'missing-'));
    let code = 0;
    try {
      execFileSync('bash', [SCRIPT], {
        encoding: 'utf8',
        env: { ...process.env, PRUNE_ROLLBACK_TAGS_INVENTORY: join(dir, 'nope.txt') },
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (e) {
      code = (e as { status?: number }).status ?? -1;
    }
    expect(code).toBe(2);
    expect(r.code).toBe(2); // the empty-inventory case above, unchanged
  });

  it('an unknown argument is exit 2 and nothing is deleted', () => {
    const r = run(deploys(7, '20260701'), { args: ['--yolo'] });
    expect(r.code).toBe(2);
    expect(r.rmi).toEqual([]);
  });
});

describe('F23 — ruling #137 clause 1: DRY RUN IS THE DEFAULT', () => {
  const rows = deploys(7, '20260701'); // 7 deploys, 5 kept, 2 outside the keep set (ruling #297)

  it('with no flag, the run REPORTS a non-empty delete list and issues no rmi', () => {
    const r = run(rows);
    expect(deletable(r.out)).toHaveLength(2); // non-vacuous: there IS something to delete
    expect(r.out).toContain('DRY RUN — nothing was deleted');
    expect(r.rmi).toEqual([]);
    expect(r.code).toBe(0);
  });

  it('--dry-run is explicit and identical', () => {
    const r = run(rows, { args: ['--dry-run'] });
    expect(r.rmi).toEqual([]);
    expect(r.out).toContain('DRY RUN');
  });

  it('…and the control: --delete on the SAME input does issue exactly those two', () => {
    const r = run(rows, { args: ['--delete'] });
    expect(r.rmi).toEqual([
      'meddoc-pro-transcribe-md:pre-a0000005-20260626',
      'meddoc-pro-transcribe-md:pre-a0000006-20260625',
    ]);
    expect(r.code).toBe(0);
  });
});

describe('F23 — ruling #137 clause 2: THE KEEP-LIST IS PRINTED FIRST', () => {
  it('KEEP precedes DELETABLE, and both precede any deletion', () => {
    const r = run(deploys(7, '20260701'), { args: ['--delete'] });
    const keep = r.out.indexOf('──────── KEEP');
    const del = r.out.indexOf('──────── DELETABLE');
    const act = r.out.indexOf('──────── DELETING BY NAME');
    expect(keep).toBeGreaterThanOrEqual(0);
    expect(del).toBeGreaterThan(keep);
    expect(act).toBeGreaterThan(del);
  });

  it('the keep block NAMES the survivors — a count alone is not a keep-list', () => {
    const r = run(deploys(7, '20260701'));
    const seg = r.out.slice(r.out.indexOf('──────── KEEP'), r.out.indexOf('──────── DELETABLE'));
    expect(seg).toContain('pre-a0000000-20260701');
    expect(seg.split('\n').filter((l) => l.includes('✔ pre-'))).toHaveLength(5);
  });
});

describe('F23 — ruling #137 clause 3: DELETION IS BY NAME', () => {
  it('every docker invocation that removes anything is `rmi <repo:tag>`', () => {
    const r = run(deploys(7, '20260701'), { args: ['--delete'] });
    const removing = r.argv.filter((a) => a[0] === 'rmi' || a[0] === 'image' || a[0] === 'system');
    expect(removing.length).toBeGreaterThan(0);
    for (const a of removing) {
      expect(a[0]).toBe('rmi');
      expect(a).toHaveLength(2);
      expect(a[1]).toMatch(/^meddoc-pro-[a-z-]+:pre-\S+$/);
    }
  });

  it('no invocation ever carries prune, --all or --filter', () => {
    const r = run(deploys(7, '20260701'), { args: ['--delete'] });
    const flat = r.argv.map((a) => a.join(' ')).join('\n');
    expect(flat).not.toMatch(/\bprune\b/);
    expect(flat).not.toMatch(/--all\b/);
    expect(flat).not.toMatch(/--filter\b/);
    // ⚠️ `-a` IS NOT ASSERTED ACROSS ALL INVOCATIONS, AND THE FIRST DRAFT OF
    // THIS ARM WAS — it went red on the script's own `docker ps -a`, a READ.
    // A title saying "no invocation carries -a" measured something wider than
    // the clause it enforces: #137 forbids `-a` on a REMOVAL. So the reads are
    // named, and the removal arm above asserts `rmi <name>` and nothing else.
    const reads = r.argv.filter((a) => a[0] === 'ps' || a[0] === 'inspect' || a[0] === 'images');
    expect(reads.length).toBeGreaterThan(0); // control: the reads really happen
    for (const a of r.argv.filter((x) => x[0] === 'rmi')) expect(a).not.toContain('-a');
  });

  it('the SOURCE contains no prune and no -a form — positive-controlled', () => {
    const src = readFileSync(SCRIPT, 'utf8');
    // Strip comments first: this file EXPLAINS `prune -a` at length, and a
    // source scan that trips on its own prose is this repo's substring trap.
    const code = src
      .split('\n')
      .filter((l) => !/^\s*#/.test(l))
      .join('\n');
    expect(code).toContain('docker rmi "$reftag"'); // the control: the extractor sees real code
    expect(code).not.toMatch(/docker\s+(image\s+)?prune/);
    expect(code).not.toMatch(/docker\s+system\s+prune/);
    expect(code).not.toMatch(/rmi[^\n]*\s-a\b/);
  });

  it('the grant names this script, so the rule and its instrument ship together', () => {
    // Canon: "an entry that names an instrument verifies that instrument's
    // grant in the same commit". The grant shipped with ruling #137.
    expect(readFileSync(SETTINGS, 'utf8')).toContain('scripts/ops/prune-rollback-tags.sh');
  });
});

describe('F23 — a failed deletion is reported, not swallowed', () => {
  it('a single failure yields exit 1, names the tag, and does not abort the rest', () => {
    const rows = deploys(7, '20260701');
    const r = run(rows, {
      args: ['--delete'],
      failOn: 'meddoc-pro-transcribe-md:pre-a0000005-20260626',
    });
    expect(r.code).toBe(1);
    expect(r.out).toContain('FAILED meddoc-pro-transcribe-md:pre-a0000005-20260626');
    // BOTH were attempted — a failure mid-list must not stop the remainder.
    expect(r.rmi).toHaveLength(2);
    expect(r.out).toContain('deleted 1, failed 1');
  });

  it('…and the control: with nothing told to fail, the same input exits 0', () => {
    const r = run(deploys(7, '20260701'), { args: ['--delete'] });
    expect(r.code).toBe(0);
    expect(r.out).toContain('retired BY NAME');
  });
});

describe('F23 — the reconciliation is observed, not derived', () => {
  it('every dated tag lands in exactly one bucket and the buckets sum', () => {
    const rows = [
      ...deploys(7, '20260701', ['meddoc-pro-transcribe-md', 'meddoc-pro-transcribe-md-worker']),
      { tag: 'pre-nodate' },
      { repo: 'someone-else', tag: 'pre-aaaaaaa-20200101' },
    ];
    const r = run(rows);
    const m = r.out.match(/reconciliation\s+: (\d+) dated tags = (\d+) kept\/held \+ (\d+) deletable/);
    expect(m).not.toBeNull();
    const [, total, kept, del] = (m as RegExpMatchArray).map(Number);
    expect(total).toBe(14); // 7 deploys × 2 repositories
    expect(kept + del).toBe(total);
    expect(del).toBe(4); // the 2 deploys outside the keep set × 2 repositories
    expect(r.out).toContain('15  = 14 dated + 1 unclassifiable');
    expect(r.out).toContain('co-tenant pre-*   : 1');
  });
});
