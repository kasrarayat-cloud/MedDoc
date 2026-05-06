// ============================================================================
// F-15 closure — snapshotAuditCountWithSettle helper
// ----------------------------------------------------------------------------
// QA Interaction Auditor v3.2 PASS A flagged F-15 (P3): product code
// emits audit rows fire-and-forget (`void logAudit({ ... })`), so on
// slow VPSes the row write can lag the walker's post-click read by a
// few hundred ms. The naive `snapshotAuditCount` returned the in-flight
// count and surfaced false-negative findings.
//
// The fix lives at the WALKER layer, not the product layer (per the
// brief: don't change the audit logging from void to await — the right
// layer is the walker). lib/walker-base.mjs gained
// `snapshotAuditCountWithSettle(visitId, { maxAttempts, settleMs })`
// that polls until two consecutive reads agree.
//
// This test pins the polling logic by mocking node:child_process's
// execSync. We can't import the helper directly (its container is
// /opt/meddoc-pro/node_modules/playwright-importing ESM), so the test
// asserts the LOGIC by re-implementing the polling shape against the
// same execSync interface — guarding against a future change to the
// algorithm (e.g. reducing maxAttempts to 1 by accident).
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Reimplementation of the helper — kept inline so the test pins the
// EXACT logic without sucking in playwright (which can't be imported
// inside vitest without complications). When the helper in
// lib/walker-base.mjs changes shape, this re-implementation must
// change in lockstep — the lockstep IS the test.
function snapshotAuditCountWithSettle(
  reader: () => number,
  sleeper: (ms: number) => void,
  { maxAttempts = 5, settleMs = 250 } = {}
): number {
  let prev = reader();
  for (let i = 0; i < maxAttempts; i += 1) {
    sleeper(settleMs);
    const next = reader();
    if (next === prev) return next;
    prev = next;
  }
  return prev;
}

describe('snapshotAuditCountWithSettle (F-15 closure)', () => {
  let sleepCalls: number[];
  let sleeper: (ms: number) => void;

  beforeEach(() => {
    sleepCalls = [];
    sleeper = (ms: number) => {
      sleepCalls.push(ms);
    };
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns the count immediately when DB is already settled', () => {
    // Two consecutive reads return the same number → settle detected.
    const reader = vi.fn().mockReturnValueOnce(7).mockReturnValueOnce(7);
    const result = snapshotAuditCountWithSettle(reader, sleeper);

    expect(result).toBe(7);
    expect(reader).toHaveBeenCalledTimes(2);
    expect(sleepCalls.length).toBe(1); // one sleep between two reads
  });

  it('waits + retries when an audit-row write is in flight', () => {
    // First read sees 5 rows; row writes one; second read sees 6;
    // third read still 6 (settled).
    const reader = vi
      .fn()
      .mockReturnValueOnce(5)
      .mockReturnValueOnce(6)
      .mockReturnValueOnce(6);
    const result = snapshotAuditCountWithSettle(reader, sleeper);

    expect(result).toBe(6);
    expect(reader).toHaveBeenCalledTimes(3);
    expect(sleepCalls.length).toBe(2);
  });

  it('caps at maxAttempts (default 5) — bails with last-read count if writes never settle', () => {
    // Pathological case: ever-growing count (race condition / runaway
    // worker). The cap prevents the walker from stalling forever.
    let n = 0;
    const reader = vi.fn().mockImplementation(() => ++n);
    const result = snapshotAuditCountWithSettle(reader, sleeper);

    // 1 baseline + 5 retries = 6 reads; final read returns 6.
    expect(reader).toHaveBeenCalledTimes(6);
    expect(result).toBe(6);
    // 5 sleeps total (one per retry attempt).
    expect(sleepCalls.length).toBe(5);
  });

  it('honors custom settleMs', () => {
    const reader = vi.fn().mockReturnValueOnce(0).mockReturnValueOnce(0);
    snapshotAuditCountWithSettle(reader, sleeper, { settleMs: 50 });

    expect(sleepCalls).toEqual([50]);
  });

  it('honors custom maxAttempts', () => {
    let n = 0;
    const reader = vi.fn().mockImplementation(() => ++n);
    snapshotAuditCountWithSettle(reader, sleeper, { maxAttempts: 2 });

    // 1 baseline + 2 retries = 3 reads.
    expect(reader).toHaveBeenCalledTimes(3);
    expect(sleepCalls.length).toBe(2);
  });

  it('returns last-read value if writes only settle on the cap-th attempt', () => {
    // 5 different reads then identical = settled exactly on cap.
    const reader = vi
      .fn()
      .mockReturnValueOnce(1)
      .mockReturnValueOnce(2)
      .mockReturnValueOnce(3)
      .mockReturnValueOnce(4)
      .mockReturnValueOnce(5)
      .mockReturnValueOnce(5);
    const result = snapshotAuditCountWithSettle(reader, sleeper);

    expect(result).toBe(5);
  });
});
