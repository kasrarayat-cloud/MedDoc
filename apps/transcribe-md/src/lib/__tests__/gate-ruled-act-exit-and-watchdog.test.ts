import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it, expect } from 'vitest';

// ─────────────────────────────────────────────────────────────────────────────
// RULING C follow-up, 2026-09-15: a ruled-act certify script printed its whole
// transcript and then HUNG for 5h24m on an open pg pool handle, because its
// success path never called process.exit(); the mutation door waited on it in
// silence. Two fixes, proven here:
//   · scripts/lib/exit-cleanly.ts  — the script exits despite an open handle
//     AND prints a completion sentinel.
//   · scripts/lib/run-watched.sh   — the door times out instead of waiting,
//     but NEVER kills on silence alone (that would SIGKILL a healthy in-flight
//     irreversible act): it fast-kills only after the sentinel; otherwise the
//     wall-clock ceiling — which cannot be disabled — is the backstop.
// The design and these cases answer the 2026-09-16 adversarial refutation pass.
// ─────────────────────────────────────────────────────────────────────────────

// One named constant per shell-out, shared by the subprocess timeout and the
// enclosing `it` budget, per ruling #265(c) (gate-265-shellout-budgets).
const RW_BUDGET_MS = 30_000;
const TSX_BUDGET_MS = 20_000;

const REPO_ROOT = execFileSync('git', ['rev-parse', '--show-toplevel'], {
  encoding: 'utf8',
}).trim();

const RUN_WATCHED = path.join(REPO_ROOT, 'scripts/lib/run-watched.sh');
const EXIT_CLEANLY = path.join(
  REPO_ROOT,
  'apps/transcribe-md/scripts/lib/exit-cleanly.ts',
);
const TSX = path.join(REPO_ROOT, 'node_modules/.bin/tsx');
const EXIT_FIXTURE = path.join(
  REPO_ROOT,
  'apps/transcribe-md/scripts/lib/__tests__/exit-cleanly-fixture.ts',
);
const SENTINEL = '__RULED_ACT_COMPLETE__';

/** Run run-watched.sh over `inner`, return { rc (RUN_RC), out (combined) }. */
// shell-budget-governed-by: RW_BUDGET_MS
function runWatched(
  inner: string[],
  env: Record<string, string> = {},
): { rc: number; out: string } {
  const driver = '. "$1"; RUN_RC=; run_watched -- "${@:2}"; echo "___RUN_RC=$RUN_RC"';
  const out = execFileSync('bash', ['-c', driver, '_', RUN_WATCHED, ...inner], {
    encoding: 'utf8',
    cwd: REPO_ROOT,
    env: { RULED_ACT_POLL: '1', ...process.env, ...env },
    timeout: RW_BUDGET_MS,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const m = out.match(/___RUN_RC=(\d+)/);
  if (!m) throw new Error(`no RUN_RC in output:\n${out}`);
  return { rc: Number(m[1]), out };
}

/** Source run-watched.sh and echo a shell expression (for the pure helpers). */
function shEval(expr: string): string {
  return execFileSync('bash', ['-c', `. "$1"; ${expr}`, '_', RUN_WATCHED], {
    encoding: 'utf8',
    cwd: REPO_ROOT,
  }).trim();
}

describe('the door watchdog — pass-through of a command that exits on its own', () => {
  it('exists and is committed', () => {
    expect(existsSync(RUN_WATCHED)).toBe(true);
  });

  it('passes a clean success straight through (RUN_RC=0, output streamed)', () => {
    const { rc, out } = runWatched(['sh', '-c', 'echo hi; exit 0']);
    expect(rc).toBe(0);
    expect(out).toContain('hi');
  }, RW_BUDGET_MS);

  it("preserves a command's own non-zero exit code", () => {
    const { rc } = runWatched(['sh', '-c', 'echo boom; exit 3']);
    expect(rc).toBe(3);
  }, RW_BUDGET_MS);

  it('passes the exit-2 "refused before acting" code through unchanged', () => {
    const { rc } = runWatched(['sh', '-c', 'exit 2']);
    expect(rc).toBe(2);
  }, RW_BUDGET_MS);
});

describe('the door watchdog — timing out a hang without murdering a quiet act', () => {
  it('fast-kills only AFTER the completion sentinel (finished-and-hung shape)', () => {
    const started = Date.now();
    const { rc, out } = runWatched(
      ['sh', '-c', `echo working; echo "${SENTINEL} rc=0"; sleep 25`],
      { RULED_ACT_IDLE_SECS: '2', RULED_ACT_POLL: '1', RULED_ACT_MAX_SECS: '60' },
    );
    expect(rc).toBe(124);
    expect(out).toContain('SIGNALLED COMPLETION BUT DID NOT EXIT');
    // it must NOT wait out the full sleep NOR the 60s ceiling
    expect(Date.now() - started).toBeLessThan(20_000);
  }, RW_BUDGET_MS);

  it('does NOT idle-kill a busy-quiet act with no sentinel — the ceiling does', () => {
    const started = Date.now();
    // idle window (2s) is far shorter than the quiet stretch, but WITHOUT a
    // sentinel the watchdog must not kill at idle — only at the 5s ceiling.
    const { rc, out } = runWatched(['sh', '-c', 'echo working; sleep 30'], {
      RULED_ACT_IDLE_SECS: '2',
      RULED_ACT_POLL: '1',
      RULED_ACT_MAX_SECS: '5',
    });
    const elapsedMs = Date.now() - started;
    expect(rc).toBe(124);
    expect(out).toContain('WALL-CLOCK CEILING');
    expect(out).toContain('NOT killing'); // the heartbeat, not a kill
    expect(out).not.toContain('SIGNALLED COMPLETION'); // never claims it landed
    // proves it waited for the ~5s ceiling, not the 2s idle window
    expect(elapsedMs).toBeGreaterThan(4_000);
  }, RW_BUDGET_MS);
});

describe('the door watchdog — the ceiling cannot be disabled (adversarial F1)', () => {
  it('coerces every numeric zero (0, 00, 000), empty, and non-numeric to the default', () => {
    expect(shEval('_watch_int 0 3600')).toBe('3600');
    expect(shEval('_watch_int 00 3600')).toBe('3600'); // leading-zero zero (pass-2)
    expect(shEval('_watch_int 000 3600')).toBe('3600');
    expect(shEval('_watch_int "" 3600')).toBe('3600');
    expect(shEval('_watch_int abc 3600')).toBe('3600');
    expect(shEval('_watch_int 7200 3600')).toBe('7200'); // a real value is honored
    // leading-zero non-zero normalizes to base-10 (no octal-in-arithmetic trap)
    expect(shEval('_watch_int 010 3600')).toBe('10');
    expect(shEval('_watch_int 007 3600')).toBe('7');
  });
});

describe('the door watchdog — the pkill signature is matched literally (adversarial F6/F7/F8)', () => {
  it('ERE-escapes shell operators so pkill cannot over/under-match or error', () => {
    expect(shEval("_ere_escape 'a || b'")).toBe('a \\|\\| b');
    expect(shEval("_ere_escape 'prisma.$exec'")).toBe('prisma\\.\\$exec');
    expect(shEval("_ere_escape 'id IN [set'")).toBe('id IN \\[set');
  });
});

describe('a ruled-act script exits explicitly and announces completion', () => {
  it('exitCleanly() exits despite an open handle, prints the sentinel, no truncation', () => {
    // If exitCleanly failed to exit, the fixture's setInterval would hang the
    // process and this call would throw on the timeout.
    const out = execFileSync(TSX, [EXIT_FIXTURE], {
      encoding: 'utf8',
      cwd: REPO_ROOT,
      timeout: TSX_BUDGET_MS,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    expect(out).toContain('FIXTURE_MARKER_BEGIN');
    expect(out).toContain('FIXTURE_MARKER_END');
    expect(out).toContain(SENTINEL);
  }, TSX_BUDGET_MS);

  it('the sentinel literal is identical in the printer and the door (one rule, two readers)', () => {
    expect(readFileSync(EXIT_CLEANLY, 'utf8')).toContain(SENTINEL);
    expect(readFileSync(RUN_WATCHED, 'utf8')).toContain(SENTINEL);
  });

  it('the certify ruled-act scripts wire the explicit-exit helper', () => {
    const scriptsDir = path.join(REPO_ROOT, 'apps/transcribe-md/scripts');
    for (const f of [
      'certify-colon-323.ts',
      'certify-colon-twin-319.ts',
      'certify-native-twin.ts',
    ]) {
      const src = readFileSync(path.join(scriptsDir, f), 'utf8');
      expect(src, `${f} imports exitCleanly`).toContain(
        "from './lib/exit-cleanly'",
      );
      expect(src, `${f} exits on success`).toMatch(
        /\.then\(\(\)\s*=>\s*exitCleanly\(0\)\)/,
      );
    }
  });
});
