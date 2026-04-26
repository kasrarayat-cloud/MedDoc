// ============================================================================
// Shared audit-logs time window — single source of truth for the
// "last N hours" rolling window used by /admin/audit-logs/* + the
// Overview's TimelineChartCard.
// ----------------------------------------------------------------------------
// Phase 7A consistency fix. Two endpoints both claimed "last 24 hours"
// but used different windows:
//   - /api/admin/audit-logs/timeline floored `since` to the hour and then
//     generated 24 buckets [sinceFloor, sinceFloor+24h). That range
//     stopped at the previous full hour and excluded today's partial
//     hour entirely. Sum of buckets = events in [yesterday's
//     same-hour-floored, today's previous-full-hour].
//   - /api/admin/audit-logs/stats used raw `now - 24h..now`. Counted
//     events including the current partial hour.
// Result: stats.totalEvents could be > sum-of-timeline-buckets by
// however many events landed during the current partial hour. A probe
// in Phase 7A caught a 24-event drift around 05:33 UTC.
//
// Both endpoints + the SSR data layer now call resolveAuditWindow() so
// they (a) pick the same `since` and (b) the timeline loop can include
// the current partial hour as the rightmost bucket.
// ============================================================================

export interface AuditWindow {
  /** Lower bound (inclusive) for `WHERE timestamp >= since`. Snapped to
   *  the start of an hour so timeline bucket boundaries line up cleanly. */
  since: Date;
  /** Number of hourly buckets to display. The LAST bucket is the
   *  current partial hour (so its `total` is "this hour so far"). */
  hours: number;
  /** Anchor at the start of the current hour. Useful to drive a bucket
   *  loop that ends at the partial-hour bucket. */
  nowFloor: Date;
}

/** Default 24-hour rolling window, anchored to "this hour". The first
 *  bucket starts at `nowFloor - (hours - 1)` hours; the last bucket is
 *  the current partial hour. */
export function resolveAuditWindow(hours = 24): AuditWindow {
  const nowFloor = new Date();
  nowFloor.setMinutes(0, 0, 0);
  const since = new Date(nowFloor.getTime() - (hours - 1) * 60 * 60 * 1000);
  return { since, hours, nowFloor };
}
