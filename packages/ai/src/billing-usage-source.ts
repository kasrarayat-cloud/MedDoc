// ============================================================================
// FOUNDATION B8 step 2 — WHERE A VISIT'S CHARGEABLE USAGE COMES FROM
// ----------------------------------------------------------------------------
// B6 shipped `commitVisitCharge` taking its usage rows as a PARAMETER rather
// than reading them, and ruling 90(e) recorded why in as many words:
//
//     "`logApiUsage` is fire-and-forget behind `setImmediate`: a caller that
//      reads `api_usage_events` at pipeline end inherits EXACTLY the
//      `worker.ts:983` read-after-write race ruling 42 assigned to B1/B4 and
//      nobody has fixed. So whoever wires this must solve the ordering, and
//      cannot do it by accident."
//
// This file is that solution. It is the ONE place a visit's chargeable rows are
// obtained, and it drains before it reads.
//
// ============================================================================
// ⚠️ THE DRAIN IS INSIDE THE LOADER, NOT A STEP THE CALLER PERFORMS FIRST
// ----------------------------------------------------------------------------
// The obvious shape is `await drainApiUsage(); const rows = await load(...)` at
// the call site. It is correct exactly as long as every present and future call
// site remembers, which is the hand-kept list AGENTS.md says is wrong
// eventually — and the failure mode is silent, because forgetting the drain
// produces a slightly small number rather than an error.
//
// So the behaviour lives ON the loader: there is no way to obtain these rows
// without having waited for the writes. A second call site inherits it for
// free, which is the "put it where it cannot be forgotten" rule applied to an
// ordering constraint instead of to a component.
//
// ============================================================================
// ⚠️ `timestamp` → `createdAt` IS AN EXPLICIT MAPPING, AND IT IS LOAD-BEARING
// ----------------------------------------------------------------------------
// `ChargeableUsageRow` declares `createdAt: Date`. **The column is called
// `timestamp`** — `ApiUsageEvent.timestamp` in `schema.prisma`, with no
// `@map`. So a loader that did
//
//     const rows = await prisma.apiUsageEvent.findMany({ where: { visitId } });
//     return commitVisitCharge({ ..., rows });
//
// hands `priceUsageRows` a row whose `createdAt` is `undefined`, and that field
// is not decorative: `billing-charge.ts:294` passes it as `at` to the rate
// lookup, which is how `price_rates.effectiveFrom` picks the period. Ruling
// 87(b) makes a lookup with no matching period return `null`, so EVERY
// component would come back `no_rate_for_key_at_instant` and the whole visit
// would decline as `unpriced` — a charge of nothing, reported as a pricing gap,
// for a reason that has nothing to do with pricing.
//
// ⚠️ AND `tsc` CATCHES THIS ONLY WHERE THE CLIENT IS TYPED. This repo reaches
// for `(prisma as any)` in several places — `api-usage.ts:175` is one — and a
// loader written that way compiles clean and fails at the rate table. The
// mapping is therefore written out field by field rather than spread, so the
// column names that exist and the field names that are needed are both visible
// in one place.
//
// ============================================================================
// ⚠️ NO FILTERING HAPPENS HERE, DELIBERATELY
// ----------------------------------------------------------------------------
// Mock rows and non-billable providers must not be charged, and it is tempting
// to narrow the query — `WHERE provider IN (...) AND "unitsSource" = 'vendor'`.
// **`priceUsageRows` already applies both exclusions** (`billing-charge.ts:269`
// for ruling 66's mock rule, `:271` for GATE 0.5's provider set), and a second
// copy in SQL is a hand-kept list that drifts from the ruled one silently — in
// whichever direction a future edit happens to touch first.
//
// So this returns what the visit HAS and lets the ruled filter decide what is
// chargeable. One rule, one place.
// ============================================================================

import prisma from '@meddoc/db';

import type { ChargeableUsageRow } from './billing-charge';
import { drainApiUsage } from './api-usage';

/** The columns `ChargeableUsageRow` needs, named as the DATABASE has them. */
interface UsageEventRow {
  id: string;
  provider: string;
  modelName: string | null;
  unitsSource: string;
  timestamp: Date;
  audioSeconds: number | null;
  inputTokens: number | null;
  outputTokens: number | null;
  cacheReadInputTokens: number | null;
  cacheCreationInputTokens: number | null;
}

/**
 * EVERY USAGE ROW RECORDED AGAINST A VISIT, AFTER THE METER HAS SETTLED.
 *
 * Ordered by `timestamp` so a pricing snapshot reads in the order the calls
 * happened; nothing depends on the order, and a caller that starts to would be
 * relying on something this comment is the only guarantee of.
 *
 * ⚠️ THIS CANNOT DISTINGUISH "NO ROWS" FROM "ROWS WE FAILED TO WRITE". A usage
 * write that Postgres refused is dropped at warn by the fire-and-forget writer,
 * and by the time this runs there is no trace of it. That is not fixed here —
 * fixing it means making the meter durable, which is a different item — but it
 * bounds what a charge computed from these rows may claim: it is what we
 * RECORDED, never provably what we SPENT. B9's reconciliation against the
 * vendors' own invoices is the thing that can tell the difference, and it is the
 * reason B9 exists.
 */
export async function loadVisitChargeableUsage(
  visitId: string,
): Promise<ChargeableUsageRow[]> {
  // Ordering, not politeness: see the header. Every write issued before this
  // point has landed (or failed and been dropped) once this resolves.
  await drainApiUsage();

  const rows: UsageEventRow[] = await prisma.apiUsageEvent.findMany({
    where: { visitId },
    select: {
      id: true,
      provider: true,
      modelName: true,
      unitsSource: true,
      timestamp: true,
      audioSeconds: true,
      inputTokens: true,
      outputTokens: true,
      cacheReadInputTokens: true,
      cacheCreationInputTokens: true,
    },
    orderBy: { timestamp: 'asc' },
  });

  return rows.map((row) => ({
    id: row.id,
    provider: row.provider,
    modelName: row.modelName,
    unitsSource: row.unitsSource,
    // THE MAPPING. See the header — this line is the whole reason the shape is
    // written out rather than spread.
    createdAt: row.timestamp,
    audioSeconds: row.audioSeconds,
    inputTokens: row.inputTokens,
    outputTokens: row.outputTokens,
    cacheReadInputTokens: row.cacheReadInputTokens,
    cacheCreationInputTokens: row.cacheCreationInputTokens,
  }));
}
