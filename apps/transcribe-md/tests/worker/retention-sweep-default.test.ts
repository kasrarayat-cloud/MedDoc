// ============================================================================
// Retention default ↔ public-claim tripwire.
// ----------------------------------------------------------------------------
// The pricing page (apps/marketing/src/app/pricing/pricing-faq.tsx, "Is the
// audio stored permanently?") tells physicians audio auto-deletes 90 days
// after the visit is signed. That promise is only true if the retention
// sweep's default window stays 90. This test pins it so a future change to
// the retention policy can't silently make the public claim false — change
// this and you MUST update the pricing copy (and vice-versa).
//
// Gated by the CI unit job (test.yml). It needs no DB/MinIO — it asserts the
// pure constant, not a live sweep.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { DEFAULT_AUDIO_RETENTION_DAYS } from '@/worker/cleanup/retention-sweep';

describe('audio retention default ↔ pricing-page claim', () => {
  it('default audio retention is 90 days (matches the public "90 days" promise + Practice.audioRetentionDays @default(90))', () => {
    expect(DEFAULT_AUDIO_RETENTION_DAYS).toBe(90);
  });
});
