// ============================================================================
// worker.ts PHI-scrub posture (Security Audit 2026-05-13, P0-A + P1-F)
// ----------------------------------------------------------------------------
// The worker's error-handling sites historically used `redactPhi()` on the
// happy paths (worker.ts:954, 1021, 1041, 1050, 1423) but missed the DLQ
// enqueue's `lastError` payload and 5 sibling `console.error` sites. The
// DLQ payload in particular is durable storage reviewed via /admin/queues
// — leaking err.message there ships PHI into an admin-visible table
// indefinitely.
//
// Full BullMQ integration testing of the on-failed handler would require
// a live Redis + a failing job; this test pins the SOURCE SHAPE so a
// future edit can't silently drop the wrap. Pattern mirrors
// tests/audit/page-rsc-audits.test.ts (source-pinning RSC audit emits)
// and tests/lib/audit-worker-context.test.ts (worker-context audit).
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const WORKER_SRC = readFileSync(
  resolve(__dirname, '..', '..', 'src', 'worker.ts'),
  'utf-8',
);

describe('worker.ts — redactPhi posture', () => {
  it('imports redactPhi from @meddoc/ai (helper available)', () => {
    expect(WORKER_SRC).toMatch(
      /import\s+\{[\s\S]*?redactPhi[\s\S]*?\}\s+from\s+['"]@meddoc\/ai['"]/,
    );
  });

  it('DLQ enqueue payload `lastError` is wrapped in redactPhi (P0-A)', () => {
    // The DLQ payload is durable + admin-visible. err.message can
    // quote Prisma column values + Anthropic 400 prompt fragments,
    // both of which are PHI.
    expect(WORKER_SRC).toMatch(
      /lastError:\s*redactPhi\([\s\S]*?err instanceof Error[\s\S]*?\)/,
    );
  });

  it("worker.on('failed') stdout log scrubs err (P1-F-1)", () => {
    expect(WORKER_SRC).toMatch(
      /\[transcribe-md-worker\] job \$\{job\?\.id\} visit \$\{job\?\.data\.visitId\} FAILED:[\s\S]*?redactPhi\(/,
    );
  });

  it('DLQ-enqueue-catch stdout log scrubs dlqErr (P1-F-2)', () => {
    expect(WORKER_SRC).toMatch(
      /DLQ enqueue failed for job \$\{job\.id\}:[\s\S]*?redactPhi\(/,
    );
  });

  it('em-judge prewarm error log scrubs err (P1-F-3)', () => {
    expect(WORKER_SRC).toMatch(
      /em-judge prewarm failed:[\s\S]*?redactPhi\(/,
    );
  });

  it("cleanupWorker.on('failed') stdout log scrubs err (P1-F-4)", () => {
    expect(WORKER_SRC).toMatch(
      /\[ops:cleanup\] job \$\{job\?\.name\}\/\$\{job\?\.id\} failed:[\s\S]*?redactPhi\(/,
    );
  });

  it('heartbeat write error log scrubs err (P1-F-5)', () => {
    expect(WORKER_SRC).toMatch(
      /heartbeat write failed:[\s\S]*?redactPhi\(/,
    );
  });

  it('no `console.error(...err)` invocations remain (regression guard)', () => {
    // Catch the exact anti-pattern: `console.error(..., err)` where
    // err is the bare Error object (which stringifies to the
    // unscrubbed `message: stack`). Every err that reaches a log
    // line must now be funneled through redactPhi or an explicit
    // metadata field.
    //
    // The catch-binding allowlist below is the CLOSED SET of names
    // we've audited in worker.ts as of 2026-05-13. If you add a new
    // try/catch with a different binding name (e.g. `catch (cleanupErr)`)
    // AND log it, extend this regex so the test still catches a
    // missed redactPhi wrap on the new site.
    const matches = WORKER_SRC.match(
      /console\.error\([^)]*,\s*(?:err|writeErr|dlqErr|notifyErr)\s*\)/g,
    );
    expect(matches, `bare-err console.error survivors: ${JSON.stringify(matches)}`).toBeNull();
  });
});
