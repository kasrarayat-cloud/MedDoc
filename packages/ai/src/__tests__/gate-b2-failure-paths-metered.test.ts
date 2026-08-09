// @vitest-environment node
// ============================================================================
// B2 GATE — EVERY FAILED-BUT-BILLED VENDOR CALL REACHES THE DURABLE METER.
// ----------------------------------------------------------------------------
// DISCOVERY §C.3, HOLE 1: the failure branches extracted and priced REAL,
// VENDOR-REPORTED usage, wrote it to `ai_calls`, and dropped it. In production
// that was 44 calls worth ~$1.53 — ~4% of all Anthropic calls — living in one
// table and not the other.
//
// ⚠️ THE ITEM'S ORIGINAL GATE WOULD HAVE PASSED WITH THE HOLE OPEN. It read
// "force a SCHEMA_FAIL and a Deepgram timeout and prove a usage row exists for
// each" — two branches out of FOURTEEN, and one of the two (the Deepgram
// timeout) is a branch that legitimately writes NO row at all, so the gate as
// written would have been half-satisfied by a defect and half by a correct
// refusal. The correction recorded in RELAY.md is: ONE FORCED FAILURE PER
// ENUMERATED BRANCH, counted against the list.
//
// ── THE PREDICATE, WRITTEN DOWN BEFORE THE SCAN ────────────────────────────
// The universe is not "catch blocks" and not "logApiUsage call sites". It is:
//
//     every site that logs a FAILED vendor call
//         AND holds the vendor's OWN reported units at that point
//
// The second conjunct is what decides the row, and it is observable in source:
// a failure site that carries `inputTokens:` / `costUsdCents:` had a real
// `response` in hand. A failure site that carries neither did not — the SDK
// threw, or the vendor answered non-2xx, and there is nothing to meter but
// invented zeroes.
//
// So every failure site lands in exactly one bucket:
//
//     BILLED_METERED     units in hand, usage row written  →  the goal
//     BILLED_UNMETERED   units in hand, NO usage row       →  MUST BE EMPTY
//     NO_UNITS           no units in hand                  →  declared by file
//
// and the three sum to the per-file failure census, which in turn reconciles
// against the total `logAiCall` census. A site cannot be added, moved or
// deleted anywhere without moving one of these numbers.
//
// ⚠️ BUCKET NAMES ARE CLAIMS, SO THEY ARE CHECKED. `BILLED_UNMETERED` being
// empty is only meaningful if the scanner can produce it — the mutation proof
// recorded at that assertion is what establishes it, and the controls below
// establish that the scanner sees anything at all. A scan that silently matches
// nothing and a clean codebase produce identical output.
// ============================================================================

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { stripComments } from './helpers/strip-comments';

const HERE = dirname(fileURLToPath(import.meta.url));
/** packages/ai/src/__tests__ → repo root */
const ROOT = resolve(HERE, '..', '..', '..', '..');

// ---------------------------------------------------------------------------
// THE WATCHED SET
// ---------------------------------------------------------------------------
// ⚠️ Deliberately the SAME five files as B1-b step 1's gate, which re-derives
// this list from the tree and fails if a sixth vendor caller ever appears. That
// test is what keeps this one honest about its universe; duplicating the
// re-derivation here would be two hand-kept lists instead of one.
const CALLERS = [
  'packages/ai/src/anthropic.ts',
  'packages/ai/src/deepgram-batch.ts',
  'packages/ai/src/embed.ts',
  'packages/ai/src/whisper-batch.ts',
  'apps/transcribe-md/src/lib/em-coding/llm-mdm.ts',
] as const;

/**
 * Failure sites that hold NO vendor-reported units, declared by file and count
 * with the reason. Every one of these is stated in place at the code, too — the
 * comment there is the argument, this is the count that keeps it from drifting.
 *
 * ⚠️ THESE ARE NOT WAIVERS. Each is a branch where writing a row would mean
 * INVENTING its units: `unitCount`, `unitCostUsd` and `totalCostUsd` are NOT
 * NULL, so a row could only be zeroes carrying the `vendor` marker — a positive
 * claim that a real vendor reported nothing billable. That is the same
 * fail-open shape as a minted request id (B1-b) and a defaulted provenance
 * column (B0 ruling, 2026-08-08).
 */
const NO_UNITS_DECLARED: Record<string, { count: number; why: string }> = {
  'packages/ai/src/anthropic.ts': {
    count: 2,
    why:
      'The two outer catches (anthropicComplete, anthropicCompleteText). ' +
      'Network / 429 / auth / SDK-throw: no `response` is in scope, so ' +
      'Anthropic reported no tokens. If a future SDK surfaces billed usage on ' +
      'a thrown error this count drops and the branch becomes metered.',
  },
  'packages/ai/src/deepgram-batch.ts': {
    count: 2,
    why:
      'Both Deepgram failure sites, for two DIFFERENT reasons. fetch-threw: no ' +
      'response at all, and on a TIMEOUT the request may never have reached ' +
      'Deepgram. !res.ok: Deepgram answered (an id exists in the ' +
      '`dg-request-id` header) but did not transcribe, so there is no ' +
      '`metadata.duration` — billable seconds are the VENDOR\'S measurement ' +
      'and the local audio length is a different quantity.',
  },
  'packages/ai/src/embed.ts': {
    count: 1,
    why:
      'The outer catch — the SDK threw, so no `response` exists and ' +
      '`response.usage.total_tokens` (the only source of units here) is ' +
      'unreachable.',
  },
  'packages/ai/src/whisper-batch.ts': {
    count: 1,
    why:
      'The SDK threw, so there is no `response.duration`. Whisper bills by the ' +
      'duration IT measured; the local file\'s byte length is not that number.',
  },
  'apps/transcribe-md/src/lib/em-coding/llm-mdm.ts': {
    count: 1,
    why:
      'The judge catch. ⚠️ Before B2 this branch wrote to NEITHER table — not ' +
      'even `ai_calls` — so a failed judge was invisible to both meters and to ' +
      "§C.3's own diagnostic query. B2 adds the telemetry row; no usage row " +
      'follows because `withTimeout` RACES the SDK without aborting the HTTP ' +
      'request, so a timed-out call may be billed by Anthropic and its token ' +
      'counts never reach this process. A structural ceiling, not an omission.',
  },
};

/** Failure sites that DO hold vendor units and therefore MUST meter. */
const BILLED_EXPECTED: Record<string, number> = {
  'packages/ai/src/anthropic.ts': 6,
  'packages/ai/src/embed.ts': 1,
};

// ---------------------------------------------------------------------------
// Source utilities
// ---------------------------------------------------------------------------

/**
 * Extract every `logAiCall(` site as `{ args, tailStart }` — the balanced
 * argument text, plus the offset just past it so the following statements can
 * be inspected for the paired usage write.
 */
function logAiCallSites(cleaned: string): { args: string; tailStart: number }[] {
  const sites: { args: string; tailStart: number }[] = [];
  const needle = 'logAiCall(';
  let from = 0;
  for (;;) {
    const start = cleaned.indexOf(needle, from);
    if (start === -1) break;

    // Skip the DECLARATION in log.ts — it matches the needle exactly. B1-b's
    // gate caught this on its first run; left unfixed it inflates the census.
    const before = cleaned.slice(0, start).trimEnd();
    if (/\bfunction$/.test(before) || /\bdeclare$/.test(before)) {
      from = start + needle.length;
      continue;
    }

    let depth = 0;
    let i = start + needle.length - 1;
    for (; i < cleaned.length; i++) {
      if (cleaned[i] === '(') depth++;
      else if (cleaned[i] === ')') {
        depth--;
        if (depth === 0) break;
      }
    }
    sites.push({ args: cleaned.slice(start + needle.length, i), tailStart: i + 1 });
    from = i + 1;
  }
  return sites;
}

/** Does this site's payload carry the vendor's own reported units? */
function holdsVendorUnits(argText: string): boolean {
  return /\binputTokens\s*:/.test(argText) || /\bcostUsdCents\s*:/.test(argText);
}

function isFailureSite(argText: string): boolean {
  return /\bsuccess\s*:\s*false\b/.test(argText);
}

/**
 * Is a usage write paired with this site — i.e. between the end of this
 * `logAiCall(...)` and the start of the NEXT one (or EOF)?
 *
 * ⚠️ Bounded by the next site on purpose. An unbounded search would let one
 * file's single success-path `logApiUsage` satisfy every failure site in it,
 * which is precisely the defect this gate exists to detect — the scan would go
 * green on the unfixed tree.
 */
function hasPairedUsageWrite(cleaned: string, site: { tailStart: number }, next?: { tailStart: number }): boolean {
  const end = next ? cleaned.lastIndexOf('logAiCall(', next.tailStart) : cleaned.length;
  const window = cleaned.slice(site.tailStart, end > site.tailStart ? end : cleaned.length);
  return /\blogApiUsage\s*\(/.test(window) || /\blogFailedAnthropicUsage\s*\(/.test(window);
}

type Bucket = 'BILLED_METERED' | 'BILLED_UNMETERED' | 'NO_UNITS';

function censusFor(file: string) {
  const cleaned = stripComments(readFileSync(resolve(ROOT, file), 'utf8'));
  const sites = logAiCallSites(cleaned);
  const buckets: Record<Bucket, number> = {
    BILLED_METERED: 0, BILLED_UNMETERED: 0, NO_UNITS: 0,
  };
  let failures = 0;
  const unmetered: string[] = [];

  sites.forEach((site, idx) => {
    if (!isFailureSite(site.args)) return;
    failures++;
    if (!holdsVendorUnits(site.args)) {
      buckets.NO_UNITS++;
      return;
    }
    if (hasPairedUsageWrite(cleaned, site, sites[idx + 1])) {
      buckets.BILLED_METERED++;
    } else {
      buckets.BILLED_UNMETERED++;
      unmetered.push(`${file} — failure site #${idx} holds vendor units and writes no usage row`);
    }
  });

  return { total: sites.length, failures, buckets, unmetered };
}

// ---------------------------------------------------------------------------
// THE CONTROLS — a broken scanner and a clean tree look identical.
// ---------------------------------------------------------------------------

describe('the scanner discriminates (controls)', () => {
  it('POSITIVE CONTROL: it finds logAiCall sites in every declared caller', () => {
    for (const file of CALLERS) {
      expect(censusFor(file).total, `${file} — scanner found no logAiCall sites`)
        .toBeGreaterThan(0);
    }
  });

  it('POSITIVE CONTROL: it finds FAILURE sites in every declared caller', () => {
    // Stronger than the above and it is the one that matters: a scanner that
    // finds sites but classifies none of them as failures would report a
    // perfectly empty BILLED_UNMETERED bucket forever.
    for (const file of CALLERS) {
      expect(censusFor(file).failures, `${file} — scanner found no FAILURE sites`)
        .toBeGreaterThan(0);
    }
  });

  it('NEGATIVE CONTROL: a billed failure site with no usage write is CAUGHT', () => {
    // The bucket this gate exists to keep empty must be reachable, or its
    // emptiness says nothing. This is the pre-B2 shape of anthropic.ts.
    const fixture = `
      logAiCall({ success: false, errorCode: 'SCHEMA_FAIL', inputTokens: usage.inputTokens });
      throw new Error('SCHEMA_FAIL');
    `;
    const cleaned = stripComments(fixture);
    const sites = logAiCallSites(cleaned);
    expect(sites).toHaveLength(1);
    expect(holdsVendorUnits(sites[0].args)).toBe(true);
    expect(hasPairedUsageWrite(cleaned, sites[0], undefined)).toBe(false);
  });

  it('NEGATIVE CONTROL: `logApiUsage` in a COMMENT does not count as a write', () => {
    // The substring trap, fifth sighting territory — B2 wrote the words
    // "usage row" and "logApiUsage" into prose sitting directly on top of the
    // branches that deliberately write none.
    const fixture = `
      logAiCall({ success: false, inputTokens: 5 });
      // B2 — no logApiUsage( here, deliberately: no vendor units in hand.
      throw err;
    `;
    const cleaned = stripComments(fixture);
    const sites = logAiCallSites(cleaned);
    expect(hasPairedUsageWrite(cleaned, sites[0], undefined)).toBe(false);
  });

  it('NEGATIVE CONTROL: a real paired write DOES count (the stripper is not eating code)', () => {
    const fixture = `
      logAiCall({ success: false, inputTokens: 5 });
      logFailedAnthropicUsage(args, usage, id, latencyMs, 'SCHEMA_FAIL');
      throw err;
    `;
    const cleaned = stripComments(fixture);
    const sites = logAiCallSites(cleaned);
    expect(hasPairedUsageWrite(cleaned, sites[0], undefined)).toBe(true);
  });

  it('the pairing window STOPS at the next logAiCall site', () => {
    // Without the bound, the success path's `logApiUsage` at the bottom of a
    // file would satisfy every failure site above it — the unfixed tree would
    // read as fully metered. This is the assertion that makes the census mean
    // what its name says.
    const fixture = `
      logAiCall({ success: false, inputTokens: 5 });
      throw new Error('boom');
      logAiCall({ success: true, inputTokens: 5 });
      logApiUsage(buildAnthropicUsage({}, 1, 2, 'm', 'p', 0, 0));
    `;
    const cleaned = stripComments(fixture);
    const sites = logAiCallSites(cleaned);
    expect(sites).toHaveLength(2);
    expect(hasPairedUsageWrite(cleaned, sites[0], sites[1])).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// THE RATCHET
// ---------------------------------------------------------------------------

describe('B2 — no failed-but-billed call is dropped', () => {
  it('BILLED_UNMETERED is empty across every caller', () => {
    const offenders: string[] = [];
    for (const file of CALLERS) offenders.push(...censusFor(file).unmetered);

    // ⚠️ MUTATION-PROVEN 2026-08-09, ON TWO DIFFERENT FILES, and what was
    // actually observed is recorded rather than what would sound strongest:
    //
    //   removing `logFailedAnthropicUsage(...)` from the SCHEMA_FAIL branch
    //     → packages/ai/src/anthropic.ts — failure site #4 holds vendor units …
    //       and `BILLED_METERED: expected 5 to be 6`
    //
    //   removing the `logApiUsage(...)` block from embed.ts's dim-mismatch
    //     → packages/ai/src/embed.ts — failure site #0 holds vendor units …
    //       and `BILLED_METERED: expected +0 to be 1`
    //
    // ⚠️ THE EMBED MUTATION IS ALSO A REAL-FILE POSITIVE CONTROL OF THE
    // PAIRING WINDOW. `embed.ts` keeps a `logApiUsage(...)` on its SUCCESS path
    // further down the same function; an unbounded search would have let that
    // one satisfy the failure site and reported green on a genuinely broken
    // tree. It reported the offender instead, so the bound is doing its job
    // against real code and not only against the fixture above.
    //
    // NOT claimed: that this assertion was watched going red-with-seven on the
    // pre-B2 tree. Each wiring was mutated away individually and the count
    // moved by exactly one each time, which is the same mechanism at unit
    // scale — but it is a narrower observation and is stated as one.
    expect(offenders).toEqual([]);
  });

  it('each caller meters exactly the number of billed failure sites it has', () => {
    for (const file of CALLERS) {
      const expected = BILLED_EXPECTED[file] ?? 0;
      expect(censusFor(file).buckets.BILLED_METERED, `${file} — see BILLED_EXPECTED`)
        .toBe(expected);
    }
  });

  it('each caller\'s NO_UNITS count matches its declaration exactly', () => {
    for (const file of CALLERS) {
      const declared = NO_UNITS_DECLARED[file]?.count ?? 0;
      expect(censusFor(file).buckets.NO_UNITS, `${file} — see NO_UNITS_DECLARED`)
        .toBe(declared);
    }
  });

  it('the three buckets sum to the failure census, in every caller', () => {
    // The reconciliation. Anything the scan cannot sort into a named bucket is
    // the finding — this is what makes the two counts above a census rather
    // than two independent numbers that happen to be right.
    for (const file of CALLERS) {
      const { failures, buckets } = censusFor(file);
      expect(
        buckets.BILLED_METERED + buckets.BILLED_UNMETERED + buckets.NO_UNITS,
        `${file} — a failure site fell outside every bucket`,
      ).toBe(failures);
    }
  });

  it('the whole-programme totals are 14 failure branches, 7 of them billed', () => {
    // The number RELAY.md's enumeration commits to. Stated here so that a
    // branch appearing or vanishing anywhere in the five callers moves a
    // number a human reads, not just a per-file assertion.
    let failures = 0, billed = 0, noUnits = 0;
    for (const file of CALLERS) {
      const c = censusFor(file);
      failures += c.failures;
      billed += c.buckets.BILLED_METERED + c.buckets.BILLED_UNMETERED;
      noUnits += c.buckets.NO_UNITS;
    }
    expect({ failures, billed, noUnits }).toEqual({ failures: 14, billed: 7, noUnits: 7 });
  });

  it('the declarations have no stale entries', () => {
    // A file that gets fully wired must lose its row, or the declaration
    // becomes a list of things that used to be true.
    for (const file of Object.keys(NO_UNITS_DECLARED)) {
      expect(CALLERS as readonly string[], `${file} is declared but not watched`)
        .toContain(file);
      expect(censusFor(file).buckets.NO_UNITS, `${file} — declared but has no NO_UNITS sites`)
        .toBeGreaterThan(0);
    }
    for (const file of Object.keys(BILLED_EXPECTED)) {
      expect(CALLERS as readonly string[], `${file} is declared but not watched`)
        .toContain(file);
    }
  });

  it('every declaration carries a REASON, not just a number', () => {
    for (const [file, d] of Object.entries(NO_UNITS_DECLARED)) {
      expect(d.why.length, `${file} — a count with no reason is a waiver`)
        .toBeGreaterThan(80);
    }
  });
});
