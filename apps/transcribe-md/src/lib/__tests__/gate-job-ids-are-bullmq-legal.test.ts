import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * ⚠️ BULLMQ REFUSES A CUSTOM JOB ID CONTAINING ':' — `Custom Id cannot contain :`
 * — and it refuses at ADD time. The enqueue throws, no job is created, and a
 * caller that (correctly) does not let a queue failure break a user action
 * swallows it. The feature is then silently, permanently dead.
 *
 * This has now happened TWICE in this file: once for the DLQ enqueuer (G10,
 * documented in place), and once for auto-certification, written a hundred
 * lines above that comment. A lesson recorded in prose did not stop its own
 * recurrence in its own file — so it is a test now.
 *
 * ⚠️ IT READS SOURCE ON PURPOSE. The enqueue helpers construct their ids from a
 * runtime payload, and every unit test of them mocks the Queue — which is
 * exactly why the real validator was never met. A source-level assertion is the
 * only thing here that sees the literal a mock cannot.
 */
const QUEUE = join(__dirname, '..', 'queue.ts');

describe('every composed jobId is BullMQ-legal', () => {
  const src = readFileSync(QUEUE, 'utf8');

  // Comment lines are stripped: this file DISCUSSES colons at length, and a
  // matcher that reads prose would fail on its own documentation.
  const code = src
    .split('\n')
    .filter((l) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
    .join('\n');

  const jobIdLines = code
    .split('\n')
    .filter((l) => /jobId\s*:/.test(l));

  it('the scan is non-vacuous — it found the jobId assignments', () => {
    // Without this, a regex that silently matched nothing would pass forever.
    expect(jobIdLines.length).toBeGreaterThanOrEqual(2);
  });

  it('no jobId literal contains a colon', () => {
    for (const line of jobIdLines) {
      const value = line.slice(line.indexOf('jobId'));
      // `jobId: ` itself contains a colon; check what comes AFTER the key.
      const rhs = value.replace(/^jobId\s*:/, '');
      expect(rhs, `BullMQ refuses this id at add() time: ${line.trim()}`).not.toMatch(/:/);
    }
  });

  it('the auto-certify id uses the recorded separator', () => {
    expect(code).toMatch(/jobId: `autocert--\$\{payload\.noteTemplateId\}`/);
  });
});
