// ============================================================================
// THE LAUNCH LOG NAMES THE TREE THE SESSION ACTUALLY WORKED ON.
// ----------------------------------------------------------------------------
// ⚠️ THE DEFECT: `foundation-loop.sh` printed its session header — including
// `commit :` — and THEN fast-forwarded the shared tree. So the one commit a
// reader takes from the log is the PRE-SYNC head, and the sync that moved it
// echoed to the runner's stdout with no `tee`, which never reaches "$LOG".
//
// MEASURED 2026-08-26, run `20260826-072351-b1` session 01:
//
//     log header  : commit  : e0e1389b
//     actual HEAD : 44929454              <- git rev-parse, in /opt/meddoc-pro
//     distance    : 10 commits, e0e1389b a proven ancestor
//
// ⚠️ AND THE CORRECTING LINE HAD NEVER ONCE BEEN IN A LOG. Row-anchored over
// every file in docs/foundation/logs/, with a positive control:
//
//     "[loop] marker:"                    -> 103 logs   <- tee'd; the CONTROL
//     "[loop] shared tree fast-forwarded" ->   0 logs
//     "[loop] shared tree is"             ->   0 logs
//
// The control fires and the targets do not, so the zero is a measurement rather
// than a token-match.
//
// ⚠️ A BARE grep FOR "fast-forwarded" RETURNS NINE HITS AND WOULD HAVE REFUTED
// ALL OF THAT. Every one of the nine is session PROSE — "I fast-forwarded the
// shared tree…" — written by sessions in their own reports. That is this
// house's *counting tokens instead of classifying rows*, caught mid-diagnosis:
// the file's own prose is exactly where the string appears without the kind.
//
// ── WHY IT IS WORTH A GATE AND NOT A SHRUG ──────────────────────────────────
// The session log is the artifact a morning report is reconstructed FROM, and
// it is the ONLY artifact when a session ends without one. This run opened with
// `REPORT-MISSING: 01` in its own halt footer; a reconstruction that starts
// from a base commit ten commits stale attributes work to the wrong tree, and
// nothing in the log says so. It is the `DEPLOYMENT_RUNBOOK §5.6` shape — a
// document asserting a state in the present tense and read as evidence — aimed
// at the loop's own audit trail.
//
// ── WHAT THIS GATE DOES AND DOES NOT CLAIM ──────────────────────────────────
// It reads `scripts/foundation-loop.sh` as TEXT. It therefore proves the lines
// are present, tee'd, and positioned — never that a live launch emitted them.
// Driving a real launch would mean starting the loop, which is not something a
// test may do. **Stated rather than papered over**, and the non-vacuity arm
// below is what stops the text arms from passing over an empty extraction.
// ============================================================================

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const REPO_ROOT = `${__dirname}/../../../../..`;
const RUNNER = `${REPO_ROOT}/scripts/foundation-loop.sh`;

const runner = (): string => readFileSync(RUNNER, 'utf8');

/**
 * The launch sync block: from the fetch that opens it to the POST-SYNC commit
 * line that closes it. Extracted by ANCHOR rather than by line number, because
 * a line number is wrong the first time anybody edits the file above it.
 */
function syncBlock(src: string): string {
  const start = src.indexOf('git fetch --quiet origin');
  const end = src.indexOf('[loop] commit (POST-SYNC');
  if (start < 0 || end < 0 || end <= start) return '';
  return src.slice(start, end);
}

describe('the launch log names the tree the session worked on', () => {
  // ⚠️ FIRST, BECAUSE EVERY OTHER ARM HERE READS THE RUNNER AS TEXT. A syntax
  // error would leave them all green while the loop could not start at all —
  // which costs the whole night rather than one item.
  it('PARSES — the runner is still a valid bash script', () => {
    expect(() => execFileSync('bash', ['-n', RUNNER], { encoding: 'utf8' })).not.toThrow();
  });

  // ── NON-VACUITY, AND IT COMES BEFORE THE ARMS THAT DEPEND ON IT ───────────
  // If `syncBlock` returns '' — an anchor renamed, the block moved — then the
  // "every echo is tee'd" arm below passes over ZERO echoes and asserts
  // nothing. A gate that reports success having looked at an empty set is this
  // programme's most-repeated defect, so the floor is asserted explicitly.
  it('NON-VACUITY — the sync block is found and carries the echoes this gate judges', () => {
    const block = syncBlock(runner());
    expect(block).not.toBe('');

    const loopEchoes = block.split('\n').filter((l) => l.includes('echo "[loop]'));
    // Three arms: ff-succeeded (1), ff-FAILED (2), not-synced (3). Six lines.
    expect(loopEchoes.length).toBeGreaterThanOrEqual(6);
  });

  // ── THE PREMISE THE "PRE-SYNC" LABEL RESTS ON ────────────────────────────
  // The label is only honest if the header really is printed first. Assert the
  // ORDER rather than trusting the comment beside it.
  it('the header block is emitted BEFORE the sync — which is why its commit is pre-sync', () => {
    const src = runner();
    const header = src.indexOf('echo "FOUNDATION session $RUN of $MAX_SESSIONS"');
    const fetch = src.indexOf('git fetch --quiet origin');
    expect(header).toBeGreaterThan(-1);
    expect(fetch).toBeGreaterThan(-1);
    expect(header).toBeLessThan(fetch);
  });

  it('LABELS the header commit as PRE-SYNC, so an unlabelled sha cannot be read as the worked tree', () => {
    const src = runner();
    expect(src).toContain('echo "commit  : $(git rev-parse --short HEAD 2>/dev/null) (PRE-SYNC)"');
  });

  // ── THE FIX ITSELF ───────────────────────────────────────────────────────
  it('EVERY [loop] line in the sync block is tee\'d into "$LOG"', () => {
    const block = syncBlock(runner());
    const offenders = block
      .split('\n')
      .filter((l) => l.includes('echo "[loop]'))
      .filter((l) => !l.includes('tee -a "$LOG"'))
      .map((l) => l.trim());

    // Named individually, because "some line is bare" is not actionable and
    // this gate's whole subject is a line that went somewhere nobody reads.
    expect(offenders).toEqual([]);
  });

  it('emits a POST-SYNC commit line, tee\'d, naming the tree the session works on', () => {
    const src = runner();
    const line = src
      .split('\n')
      .find((l) => l.includes('[loop] commit (POST-SYNC'));
    expect(line).toBeDefined();
    expect(line).toContain('git rev-parse --short HEAD');
    expect(line).toContain('tee -a "$LOG"');
  });

  // ⚠️ THE ARM THAT MATTERS MOST, AND THE ONE A CARELESS FIX WOULD MISS.
  // The `_behind = 0` branch is a silent `:`. A POST-SYNC line placed inside
  // the if/else would print on a tree that MOVED and stay silent on a tree that
  // was already current — and "no line" is indistinguishable from "the header
  // was right". The line has to sit AFTER the closing `fi`.
  it('the POST-SYNC line is OUTSIDE the if/else, so an already-current tree still names its commit', () => {
    const src = runner();
    const fetch = src.indexOf('git fetch --quiet origin');
    const post = src.indexOf('[loop] commit (POST-SYNC');
    expect(fetch).toBeGreaterThan(-1);
    expect(post).toBeGreaterThan(fetch);

    // The last `fi` between the fetch and the post-sync line closes the sync
    // conditional. The post-sync echo must come after it.
    const between = src.slice(fetch, post);
    const lastFi = between.lastIndexOf('\n  fi');
    expect(lastFi).toBeGreaterThan(-1);
    expect(fetch + lastFi).toBeLessThan(post);
  });

  // ── THE RETIRED FORMS. Their return is the whole regression. ─────────────
  it('does NOT reintroduce a bare (untee\'d) sync echo', () => {
    const src = runner();
    expect(src).not.toContain(
      'echo "[loop] shared tree fast-forwarded $_behind commit(s) → $(git rev-parse --short HEAD)"\n',
    );
    expect(src).not.toContain('echo "commit  : $(git rev-parse --short HEAD 2>/dev/null)"\n');
  });
});
