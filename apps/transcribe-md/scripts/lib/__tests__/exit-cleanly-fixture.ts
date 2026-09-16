// Fixture for gate-ruled-act-exit-and-watchdog.test.ts — NOT a test itself.
//
// It opens a handle (setInterval) that would keep Node's event loop alive
// forever — the exact shape of the open pg pool that hung the 2026-09-15
// colon-note ruled act for 5h24m — then calls exitCleanly(0). If the helper
// works, the process prints both markers (no truncation) and exits 0 promptly.
// If it did not force the exit, the setInterval would hang the process and the
// spawning test would time out.
import { exitCleanly } from '../exit-cleanly';

const keepAlive = setInterval(() => {}, 1000);
// reference it so no optimizer can argue it away
if (!keepAlive) throw new Error('unreachable');

console.log('FIXTURE_MARKER_BEGIN');
process.stdout.write('FIXTURE_MARKER_END\n');

exitCleanly(0);
