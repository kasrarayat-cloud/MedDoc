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

  while (Date.now() < deadline) {
    const res = await page.request.get(`/api/visits/${visitId}/status`);
    if (res.ok()) {
      const body = (await res.json()) as { status: VisitStatus };
      lastStatus = body.status;
      if (target.has(body.status)) return body.status;
      if (body.status === 'FAILED') {
        throw new Error(
          `visit ${visitId} went to FAILED while waiting for ${[...target].join('/')}`
        );
      }
    }
    await page.waitForTimeout(intervalMs);
  }

  expect(
    lastStatus,
    `waitForVisitStatus timed out after ${timeoutMs}ms; last seen status = ${lastStatus}`
  ).toEqual([...target][0]);
  return lastStatus as VisitStatus;
}
