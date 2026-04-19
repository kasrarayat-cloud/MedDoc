// ============================================================================
// Wait-for-READY helper — poll /api/visits/[id]/status until the
// pipeline is done. With MOCK_AI_CALLS=true on the worker this is
// typically 1-3 seconds; we give it 60s of headroom before declaring
// a timeout (the worker might be restarting, a job might be queued
// behind another, etc.).
// ============================================================================

import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';

export type VisitStatus =
  | 'QUEUED'
  | 'TRANSCRIBING'
  | 'EXTRACTING'
  | 'DRAFTING'
  | 'CRITIQUING'
  | 'POLISHING'
  | 'AUTOMATING'
  | 'READY'
  | 'FAILED'
  | 'SIGNED';

export async function waitForVisitStatus(
  page: Page,
  visitId: string,
  desired: VisitStatus | VisitStatus[],
  { timeoutMs = 60_000, intervalMs = 1_000 }: { timeoutMs?: number; intervalMs?: number } = {}
): Promise<VisitStatus> {
  const target = new Set(Array.isArray(desired) ? desired : [desired]);
  const deadline = Date.now() + timeoutMs;
  let lastStatus: VisitStatus | 'UNKNOWN' = 'UNKNOWN';
  let lastHttp = 0;

  while (Date.now() < deadline) {
    // Use the page's own fetch via evaluate so the request rides on
    // the exact same cookie jar the SSR + middleware see. page.request
    // uses the context's APIRequestContext which occasionally drops
    // Secure cookies on HTTP origins — this variant never has to care.
    const probe = await page.evaluate(async (id) => {
      const r = await fetch(`/api/visits/${id}/status`, { credentials: 'include' });
      const txt = await r.text();
      return { status: r.status, body: txt };
    }, visitId);
    lastHttp = probe.status;
    if (probe.status === 200) {
      try {
        const body = JSON.parse(probe.body) as { status: VisitStatus };
        lastStatus = body.status;
        if (target.has(body.status)) return body.status;
        if (body.status === 'FAILED') {
          throw new Error(
            `visit ${visitId} went to FAILED while waiting for ${[...target].join('/')}`
          );
        }
      } catch {
        // JSON parse failed — fall through and retry.
      }
    }
    await page.waitForTimeout(intervalMs);
  }

  expect(
    lastStatus,
    `waitForVisitStatus timed out after ${timeoutMs}ms; last seen HTTP ${lastHttp}, last status = ${lastStatus}`
  ).toEqual([...target][0]);
  return lastStatus as VisitStatus;
}
