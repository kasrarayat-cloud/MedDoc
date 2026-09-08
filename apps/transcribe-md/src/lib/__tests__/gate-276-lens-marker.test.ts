// ============================================================================
// #276 / #213 — A LENS SANDBOX CARRIES ITS PROVENANCE, AND THE REAPER REFUSES
// ONE THAT IS STILL SOMEBODY'S.
// ----------------------------------------------------------------------------
// ⚠️ THE REAPER USED TO CHECK A FILENAME PREFIX AND A DIRECTORY, THEN
// `worktree remove --force`. Three sessions share one account on this box, so
// that would remove a PEER'S LIVE SANDBOX mid-round — the lens would find its
// tree gone with no error anyone could attribute.
//
// #206 specified a marker. **#213 amended it** — *session id + start-time,
// NEVER `$$`* — and named the custom-file session to implement it. #276 ruled
// that the twenty `.lens-1018-*` trees are Design/Admin's and that this marker
// is what converts *"not mine"* into *"abandoned, and safe to reap"*.
//
// ── WHY NOT `$$`, MEASURED FIRST-HAND ───────────────────────────────────────
// `$$` in a tool shell is a FRESH SUBSHELL. Measured while building this:
// `CLAUDE_PID=2204890` against `$$=3555429`. A liveness check against `$$`
// answers about a process that was already dead when the file was written, and
// it answers **"dead"** — the direction that costs somebody their tree.
//
// ── AND THE START-TIME BINDS THE PID TO AN IDENTITY ─────────────────────────
// A bare pid is reused. Field 22 of `/proc/<pid>/stat` is the process's own
// start tick and cannot be inherited by a later process wearing the same number.
//
// ── WHAT THIS GATE DRIVES ───────────────────────────────────────────────────
// The REAL scripts, against REAL temporary sandboxes, in a throwaway git repo —
// not a re-implementation. The shell arms were hand-run first and a hand-run
// proof decays, which is the same argument `gate-f9` makes for being a vitest
// file rather than a shell harness.
// ============================================================================
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

import { afterAll, describe, expect, it } from 'vitest';

const REPO = resolve(__dirname, '../../../../..');
const REAP = resolve(REPO, 'scripts/reap-lens-sandbox.sh');
const MAKE = resolve(REPO, 'scripts/make-lens-sandbox.sh');

/**
 * ⚠️ ONE BUDGET, USED TWICE — #265(c), which this session ratified and then
 * immediately violated in this very file. The first version handed
 * `execFileSync` a `timeout: 60_000` and stated no `it` budget, so every arm ran
 * under vitest's DEFAULT 5_000 and every one of them died with
 * `Error: Test timed out in 5000ms` — the subprocess's own message unreachable,
 * exactly as `c4e778a2` describes.
 *
 * The reaper is genuinely slow: its positive control spawns a holder, sleeps,
 * and scans every `/proc/<pid>/cwd` twice, plus an `lsof +D`. ~10s per arm
 * measured. 30s is a ~3x margin under parallel load.
 *
 * ⚠️ WRITING A RULE DOWN IS NOT OBEYING IT. That sentence is already canon here,
 * and this is its next instance — caught by the failure, not by the author.
 */
const ARM_BUDGET_MS = 30_000;

const tmps: string[] = [];
afterAll(() => {
  for (const d of tmps) {
    try {
      rmSync(d, { recursive: true, force: true });
    } catch {
      /* a leaked temp dir is not worth failing a gate over */
    }
  }
});

/** A throwaway sandbox with the shape the reaper checks, and a marker we control. */
function fakeSandbox(marker: Record<string, string> | null): string {
  const root = mkdtempSync(join(tmpdir(), 'lensgate-'));
  tmps.push(root);
  const dir = join(root, '.lens-fake');
  mkdirSync(join(dir, '.lens-hooks'), { recursive: true });
  if (marker) {
    writeFileSync(
      join(dir, '.lens-marker'),
      Object.entries(marker)
        .map(([k, v]) => `${k}=${v}`)
        .join('\n') + '\n',
    );
  }
  return dir;
}

function reap(dir: string, env: Record<string, string> = {}): { rc: number; out: string } {
  try {
    const out = execFileSync('bash', [REAP, dir], {
      encoding: 'utf8',
      timeout: ARM_BUDGET_MS,
      env: { ...process.env, ...env },
      cwd: REPO,
    });
    return { rc: 0, out };
  } catch (e) {
    const err = e as { status?: number; stdout?: string; stderr?: string; message: string };
    return { rc: err.status ?? 1, out: `${err.stdout ?? ''}${err.stderr ?? ''}${err.message}` };
  }
}

const OUR_PID = String(process.pid);
const ourStart = () => readFileSync(`/proc/${OUR_PID}/stat`, 'utf8').split(' ')[21]!;

describe('#213 — the marker is written, and it is session id + start-time', () => {
  it('POSITIVE CONTROL — `make-lens-sandbox.sh` writes every field the reaper reads', () => {
    // ⚠️ A GATE THAT ONLY TESTED THE REAPER WOULD PASS FOREVER ON SANDBOXES THAT
    // CARRY NO MARKER — the reaper would simply refuse them all, which is
    // "correct" and useless. This asserts the producer's side too.
    const src = readFileSync(MAKE, 'utf8');
    for (const key of [
      'owner_session=',
      'owner_pid=',
      'owner_starttime=',
      'created_utc=',
      'heartbeat_utc=',
      'ref_under_test=',
      'ref_sha=',
    ]) {
      expect(src, `make-lens-sandbox.sh no longer writes ${key}`).toContain(key);
    }
  });

  it('⚠️ it stamps CLAUDE_PID, and NEVER `$$` — #213', () => {
    const src = readFileSync(MAKE, 'utf8');
    expect(src).toContain('CLAUDE_PID');
    // the marker block must not take its pid from the subshell
    const markerBlock = src.slice(src.indexOf('cat > "$DIR/.lens-marker"'));
    expect(markerBlock, 'the marker records `$$`, which #213 forbids by name').not.toMatch(
      /owner_pid=\$\$|owner_pid=\$\{?\$\}?[^A-Z_]/,
    );
  });

  it('the start-time comes from field 22 of /proc/<pid>/stat', () => {
    expect(readFileSync(MAKE, 'utf8')).toContain("awk '{print $22}'");
  });
});

describe('#213 — the reaper REFUSES a tree that is still somebody else\'s', () => {
  it('REFUSES when the owner is ALIVE and is not this session', () => {
    // Our own pid is alive by construction, under a session id that is not ours.
    const dir = fakeSandbox({
      owner_session: 'some-other-session',
      owner_pid: OUR_PID,
      owner_starttime: ourStart(),
      created_utc: '2026-01-01T00:00:00Z',
    });
    const r = reap(dir);
    expect(r.rc).toBe(1);
    expect(r.out).toContain('STILL ALIVE');
    expect(existsSync(dir), 'the tree was removed anyway').toBe(true);
  }, ARM_BUDGET_MS);

  it('REAPS its OWN tree even though that session is alive — the close-out case', () => {
    // ⚠️ THE FIRST BUILD REFUSED THIS, AND IT IS THE ONE ACTION THE GUARD EXISTS
    // TO MAKE SAFE. Found by using it: the close-out sweep could not reap the
    // probe sandbox it had just created. A guard that refuses its own purpose
    // gets worked around, and then it protects nothing.
    const session = process.env.CLAUDE_CODE_SESSION_ID ?? 'gate-self-session';
    const dir = fakeSandbox({
      owner_session: session,
      owner_pid: OUR_PID,
      owner_starttime: ourStart(),
      created_utc: '2026-01-01T00:00:00Z',
    });
    const r = reap(dir, { CLAUDE_CODE_SESSION_ID: session });
    expect(r.rc, r.out).toBe(0);
    expect(existsSync(dir)).toBe(false);
  }, ARM_BUDGET_MS);

  it('REAPS when the recorded owner is DEAD', () => {
    const dir = fakeSandbox({
      owner_session: 'a-finished-session',
      owner_pid: '4194303', // above any real pid_max on this box
      owner_starttime: '999999999',
      created_utc: '2026-01-01T00:00:00Z',
    });
    const r = reap(dir);
    expect(r.rc, r.out).toBe(0);
    expect(existsSync(dir)).toBe(false);
  }, ARM_BUDGET_MS);

  it('⚠️ a REUSED PID does not read as alive — the start-time is what binds it', () => {
    // Our pid, alive — but stamped with a start-time that is not ours. That is
    // exactly the shape of a pid the kernel handed to somebody else after the
    // owner exited, and a bare-pid check would call it ALIVE and refuse forever.
    const dir = fakeSandbox({
      owner_session: 'a-finished-session',
      owner_pid: OUR_PID,
      owner_starttime: '1',
      created_utc: '2026-01-01T00:00:00Z',
    });
    const r = reap(dir);
    expect(r.rc, r.out).toBe(0);
    expect(existsSync(dir)).toBe(false);
  }, ARM_BUDGET_MS);
});

describe('#213 — fail-closed on cannot-tell, and the declaration is the door', () => {
  it('REFUSES an UNMARKED sandbox — unattributable is not "safe"', () => {
    const dir = fakeSandbox(null);
    const r = reap(dir);
    expect(r.rc).toBe(1);
    expect(r.out).toContain('carries no .lens-marker');
    expect(existsSync(dir)).toBe(true);
  }, ARM_BUDGET_MS);

  it('REFUSES a declaration wearing a token\'s clothes', () => {
    const dir = fakeSandbox(null);
    const r = reap(dir, { DECLARE_REAP: 'yes' });
    expect(r.rc).toBe(1);
    expect(existsSync(dir)).toBe(true);
  }, ARM_BUDGET_MS);

  it('ACCEPTS a real declaration, and ECHOES it — the log is the record', () => {
    const dir = fakeSandbox(null);
    const why = "Design/Admin's round-five sandbox, ruled reapable by #276";
    const r = reap(dir, { DECLARE_REAP: why });
    expect(r.rc, r.out).toBe(0);
    expect(r.out, 'the reason was not echoed — an audit trail needs the why').toContain(why);
    expect(existsSync(dir)).toBe(false);
  }, ARM_BUDGET_MS);

  it('REFUSES a marker whose pid/start-time cannot answer the question', () => {
    const dir = fakeSandbox({
      owner_session: 'x',
      owner_pid: 'unknown',
      owner_starttime: 'unknown',
      created_utc: '2026-01-01T00:00:00Z',
    });
    const r = reap(dir);
    expect(r.rc).toBe(1);
    expect(r.out).toContain('CANNOT BE ESTABLISHED');
    expect(existsSync(dir)).toBe(true);
  }, ARM_BUDGET_MS);

  it('REFUSES anything that is not a lens sandbox, and anything with no hooks', () => {
    const root = mkdtempSync(join(tmpdir(), 'lensgate-'));
    tmps.push(root);
    const notLens = join(root, 'ordinary-worktree');
    mkdirSync(join(notLens, '.lens-hooks'), { recursive: true });
    expect(reap(notLens).rc).toBe(1);

    const noHooks = join(root, '.lens-nohooks');
    mkdirSync(noHooks, { recursive: true });
    expect(reap(noHooks).rc).toBe(1);
    expect(existsSync(noHooks)).toBe(true);
  }, ARM_BUDGET_MS);
});
