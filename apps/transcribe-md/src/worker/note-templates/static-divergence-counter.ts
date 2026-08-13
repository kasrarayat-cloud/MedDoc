// ============================================================================
// PER-TEMPLATE STATIC-DIVERGENCE COUNTER — ruling #106(g)(4).
// ----------------------------------------------------------------------------
// WHY A COUNTER AND NOT JUST A LOG LINE
//
// A fail-closed fallback that leaves no trace is indistinguishable from a
// fallback that never fires. The audit row is the DURABLE record — it survives
// a restart and it is queryable by template — and this counter is the
// IN-PROCESS one, which exists for two reasons the audit row cannot serve:
//
//   1. It makes the increment READABLE BY A TEST. `logAudit` is fire-and-forget
//      by design (an audit write must never break a clinical action), so a test
//      that asserts "the rejection was recorded" by watching the audit call is
//      asserting the call, not the record. AGENTS.md's rule is that a
//      fire-and-forget writer is proved only by something that READS IT BACK.
//   2. It is PER TEMPLATE, which is the shape that carries the signal. "Polish
//      was rejected once" is noise; "THIS template's statics are rewritten on
//      every visit" is a mis-classified section, and only the per-template
//      figure can tell them apart.
//
// ⚠️ ITS LIMIT, STATED RATHER THAN DISCOVERED: this is per WORKER PROCESS and
// resets on restart. It is a live signal, never a ledger. The durable count is
// `audit_logs` filtered to `L6_FABRICATION_REJECTED` with
// `metadata->>'gateError' = 'static_region_diverged'`, grouped by
// `metadata->>'noteTemplateId'` — which is why that key is written on every
// such row.
// ============================================================================

const counts = new Map<string, number>();

/** Record one static-divergence rejection for a template. Returns the new
 *  total, so the caller can put the running figure in the same log line as the
 *  reason — a count you have to go and fetch separately is a count nobody
 *  reads. */
export function noteStaticDivergence(templateId: string): number {
  const next = (counts.get(templateId) ?? 0) + 1;
  counts.set(templateId, next);
  return next;
}

/** Rejections recorded for one template in this process. */
export function staticDivergenceCount(templateId: string): number {
  return counts.get(templateId) ?? 0;
}

/** Every template with at least one rejection, for a diagnostic dump. */
export function staticDivergenceCounts(): Record<string, number> {
  return Object.fromEntries(counts);
}

/** Test-only. Module state shared across test files is a cross-test dependency,
 *  and a counter that only ever grows makes the SECOND test that reads it
 *  depend on whether the first ran. */
export function resetStaticDivergenceCounts(): void {
  counts.clear();
}
