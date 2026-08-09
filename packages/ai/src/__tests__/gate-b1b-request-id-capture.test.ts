// @vitest-environment node
// ============================================================================
// B1-b step 1 GATE — EVERY real-vendor caller captures the vendor's request id,
// not just the one file B1-a happened to watch.
// ----------------------------------------------------------------------------
// ⚠️ THIS GATE EXISTS BECAUSE THE PREVIOUS ONE PASSED TRUTHFULLY OVER THE WRONG
// UNIVERSE. B1-a's gate read "every success row carries a vendor id, not a
// randomUUID()" and it watched `packages/ai/src/anthropic.ts`. That file was
// perfect. FOUR OTHER FILES CALL A VENDOR AND LOG AiCall ROWS, and three of them
// captured nothing at all — so the gate was green, the ledger said the capture
// shipped, and ~18% of a visit's vendor calls were still writing NULL.
//
// A NULL is indistinguishable from "the vendor supplied no id" (see
// vendor-request-id.ts). That is precisely the quantity B1-b must size before it
// can decide whether `vendor ⇒ id` may be strict — so an uncaptured id does not
// merely miss a column, IT FABRICATES THE MEASUREMENT, recording our own
// omission as the vendor's silence. And `api_usage_events` has no deleter
// anywhere in the tree, so a contaminated sample is permanent.
//
// ── SO THIS GATE IS WRITTEN AS A RECONCILIATION, NOT A GREP ────────────────
// The lesson from T5 is that a check must name every bucket it can sort a site
// into and assert the TOTAL, because a scan that silently drops a site produces
// the same output as a clean codebase. Every `logAiCall(...)` site in every
// real-vendor caller lands in exactly one bucket:
//
//     SUCCESS_CAPTURES    success:true  + requestId  →  must be ALL of them
//     SUCCESS_NO_ID       success:true  , no id      →  MUST BE EMPTY (the ratchet)
//     FAILURE_CAPTURES    success:false + requestId  →  the vendor answered anyway
//     FAILURE_NO_ID       success:false , no id      →  declared BY FILE AND COUNT
//
// and the four bucket sizes must sum to a declared per-file census. A new call
// site cannot be added anywhere without landing in a bucket and moving a number.
//
// ⚠️ THE COMMENT STRIPPER IS LOAD-BEARING AND IS ITSELF POSITIVE-CONTROLLED.
// This repo has been bitten four times by a source check matching its own prose
// (AGENTS.md, "the substring trap"). The fix for THIS item wrote the word
// `requestId` into explanatory comments sitting directly on top of sites that
// deliberately do NOT pass one — so a naive scan would now report the Deepgram
// failure paths as capturing. Comments are stripped before classification, and
// a fixture proves the stripper works in both directions.
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
// THE WATCHED SET — stated by hand, and diffed against reality below.
// ---------------------------------------------------------------------------
// ⚠️ A hand-kept list is wrong eventually, so it is not trusted: the
// "no unwatched caller" test re-derives this set from the tree and fails if the
// two disagree. The list is here to be CHECKED, not to be believed.
const CALLERS = [
  'packages/ai/src/anthropic.ts',
  'packages/ai/src/deepgram-batch.ts',
  'packages/ai/src/embed.ts',
  'packages/ai/src/whisper-batch.ts',
  'apps/transcribe-md/src/lib/em-coding/llm-mdm.ts',
] as const;

/**
 * Sites that log a FAILURE and legitimately pass no request id, declared by
 * file and count with the reason. Anything beyond these numbers is a finding.
 *
 * ⚠️ These are NOT waived — they are B2's item by name ("wire the failure paths
 * into the durable table"). They are declared here so that the success ratchet
 * can be exact without pretending the failure paths are done.
 */
const FAILURE_NO_ID_DECLARED: Record<string, { count: number; why: string }> = {
  'packages/ai/src/anthropic.ts': {
    count: 2,
    why:
      '⚠️ 8 → 2 on 2026-08-09 (B2). The six branches that hold a real ' +
      '`response` now pass `requestId` to the queryable column, so only the ' +
      'TWO OUTER CATCHES remain. On those the SDK threw and there is no ' +
      'response object: the id is reachable only as `err.request_id` / the ' +
      '`request-id` header, which `anthropicErrorDetailsJson(err)` already ' +
      'captures into the `errorDetails` JSON blob. Promoting THAT to the ' +
      'column is a separate shape (an error-path reader, not a response ' +
      'reader) and is not claimed by B2 — B2 wires the DURABLE METER, and ' +
      'these two branches have no units to meter either.',
  },
  'apps/transcribe-md/src/lib/em-coding/llm-mdm.ts': {
    count: 1,
    why:
      'NEW on 2026-08-09 (B2). The judge catch previously wrote to NEITHER ' +
      'table; B2 gives it an `ai_calls` telemetry row. No id: `withTimeout` ' +
      'races the SDK, so on the branch that matters there is no response and ' +
      'no `err.request_id` to read.',
  },
  'packages/ai/src/deepgram-batch.ts': {
    count: 2,
    why:
      'Two different shapes, both stated in place. fetch-threw: no response ' +
      'exists and on a TIMEOUT the request may never have reached Deepgram. ' +
      '!res.ok: Deepgram answered and the id is in the `dg-request-id` ' +
      'RESPONSE HEADER — a third id-source shape, deliberately left to B2.',
  },
  'packages/ai/src/embed.ts': {
    count: 1,
    why:
      'The outer catch — the SDK threw, so no response object exists. The id ' +
      'is reachable as APIError.requestID (openai 6.34.0 core/error.js:14); ' +
      'that is B2 input, recorded in RELAY.md.',
  },
  'packages/ai/src/whisper-batch.ts': {
    count: 1,
    why: 'Same as embed.ts — the SDK threw; no response object. B2 input.',
  },
};

// ---------------------------------------------------------------------------
// Source utilities
// ---------------------------------------------------------------------------

// ⚠️ `stripComments` MOVED to ./helpers/strip-comments when B1-b step 2's gate
// needed it. It is re-exported here so this file's own history and any external
// import keep working; the implementation and the reasoning live in the helper.
export { stripComments } from './helpers/strip-comments';

/** Extract the balanced `(...)` argument text of every `logAiCall(` call. */
function logAiCallSites(cleaned: string): string[] {
  const sites: string[] = [];
  const needle = 'logAiCall(';
  let from = 0;
  for (;;) {
    const start = cleaned.indexOf(needle, from);
    if (start === -1) break;

    // ⚠️ SKIP THE DECLARATION. `log.ts` defines `function logAiCall(input:
    // AiCallLogInput)`, which matches the needle exactly — and the unwatched-
    // caller test caught it on this gate's very first run, reporting `log.ts`
    // as a vendor caller. It is the opposite: the sink every caller writes to.
    // Left unfixed, the declaration would also have been classified into a
    // bucket and quietly inflated the census by one.
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
    sites.push(cleaned.slice(start + needle.length, i));
    from = i + 1;
  }
  return sites;
}

type Bucket = 'SUCCESS_CAPTURES' | 'SUCCESS_NO_ID' | 'FAILURE_CAPTURES' | 'FAILURE_NO_ID';

function classify(argText: string): Bucket {
  const success = /\bsuccess\s*:\s*true\b/.test(argText);
  const hasId = /\brequestId\s*:/.test(argText);
  if (success) return hasId ? 'SUCCESS_CAPTURES' : 'SUCCESS_NO_ID';
  return hasId ? 'FAILURE_CAPTURES' : 'FAILURE_NO_ID';
}

function censusFor(file: string) {
  const cleaned = stripComments(readFileSync(resolve(ROOT, file), 'utf8'));
  const sites = logAiCallSites(cleaned);
  const buckets: Record<Bucket, number> = {
    SUCCESS_CAPTURES: 0, SUCCESS_NO_ID: 0, FAILURE_CAPTURES: 0, FAILURE_NO_ID: 0,
  };
  for (const s of sites) buckets[classify(s)]++;
  return { total: sites.length, buckets };
}

// ---------------------------------------------------------------------------
// THE CONTROLS — run these first. A broken scanner and a clean tree look alike.
// ---------------------------------------------------------------------------

describe('the scanner discriminates (controls)', () => {
  it('POSITIVE CONTROL: it finds call sites at all, in every declared caller', () => {
    // Without this, every assertion below is satisfied by a scanner that
    // returns nothing — the "answer about a set whose boundary was never
    // established" failure this repo has hit three times.
    for (const file of CALLERS) {
      expect(censusFor(file).total, `${file} — scanner found no logAiCall sites`)
        .toBeGreaterThan(0);
    }
  });

  it('NEGATIVE CONTROL: `requestId` in a COMMENT does not count as capture', () => {
    // This is not hypothetical. B1-b step 1 wrote exactly this shape into
    // deepgram-batch.ts: prose explaining why the id is absent, directly above
    // a site that passes none.
    const fixture = `
      // requestId: readOpenAIRequestId(response) -- explanatory prose only
      /* another mention of requestId: in a block comment */
      logAiCall({ provider: 'openai', success: true });
    `;
    const sites = logAiCallSites(stripComments(fixture));
    expect(sites).toHaveLength(1);
    expect(classify(sites[0])).toBe('SUCCESS_NO_ID');
  });

  it('NEGATIVE CONTROL: a real capture DOES count (the stripper is not eating code)', () => {
    const fixture = `
      // requestId is discussed here and must be ignored
      logAiCall({ provider: 'openai', success: true, requestId: readOpenAIRequestId(response) });
    `;
    const sites = logAiCallSites(stripComments(fixture));
    expect(sites).toHaveLength(1);
    expect(classify(sites[0])).toBe('SUCCESS_CAPTURES');
  });

  it('the stripper is quote-aware — an https:// literal is not a comment', () => {
    const fixture = `
      const url = 'https://api.deepgram.com/v1/listen';
      logAiCall({ success: true, requestId: id, url });
    `;
    const cleaned = stripComments(fixture);
    expect(cleaned).toContain('api.deepgram.com');
    expect(logAiCallSites(cleaned)).toHaveLength(1);
  });

  it('balanced extraction survives nested calls in the argument', () => {
    const sites = logAiCallSites(
      stripComments(`logAiCall({ costUsdCents: cost(a, b(c, d)), success: true, requestId: r(x) });`),
    );
    expect(sites).toHaveLength(1);
    expect(classify(sites[0])).toBe('SUCCESS_CAPTURES');
  });
});

// ---------------------------------------------------------------------------
// THE RATCHET
// ---------------------------------------------------------------------------

describe('B1-b step 1 — every real-vendor SUCCESS row carries a vendor id', () => {
  it('SUCCESS_NO_ID is empty across every caller', () => {
    const offenders: string[] = [];
    for (const file of CALLERS) {
      const { buckets } = censusFor(file);
      if (buckets.SUCCESS_NO_ID > 0) {
        offenders.push(`${file} — ${buckets.SUCCESS_NO_ID} success site(s) pass no requestId`);
      }
    }
    // ⚠️ MUTATION-PROVEN 2026-08-09, by removing the four `requestId:` lines
    // this item added while LEAVING THEIR COMMENTS IN PLACE — which also
    // positive-controls the comment stripper against the real files rather than
    // only against the fixture above. This assertion then failed with exactly:
    //
    //     packages/ai/src/embed.ts        — 1 success site(s) pass no requestId
    //     packages/ai/src/whisper-batch.ts — 1 success site(s) pass no requestId
    //     .../em-coding/llm-mdm.ts        — 1 success site(s) pass no requestId
    //
    // (three FILES; the fourth removed line was embed.ts's failure-path capture,
    // which reds the declaration test below instead — 1 → 2.)
    //
    // If it ever fails again, the fix is to thread the id — never to add the
    // file to a declaration.
    expect(offenders).toEqual([]);
  });

  it('every caller has at least one capturing success site', () => {
    // Guards the degenerate pass: a file whose success sites were all deleted
    // would satisfy the ratchet above vacuously.
    for (const file of CALLERS) {
      expect(censusFor(file).buckets.SUCCESS_CAPTURES, `${file}`).toBeGreaterThan(0);
    }
  });
});

describe('the failure paths are DECLARED, not waived', () => {
  it('each caller\'s FAILURE_NO_ID count matches its declaration exactly', () => {
    for (const file of CALLERS) {
      const declared = FAILURE_NO_ID_DECLARED[file]?.count ?? 0;
      expect(censusFor(file).buckets.FAILURE_NO_ID, `${file} — see FAILURE_NO_ID_DECLARED`)
        .toBe(declared);
    }
  });

  it('the declaration has no stale entries', () => {
    // A file that gets fixed must have its row REMOVED, or the declaration
    // slowly becomes a list of things that used to be true.
    for (const file of Object.keys(FAILURE_NO_ID_DECLARED)) {
      expect(CALLERS as readonly string[]).toContain(file);
    }
  });

  it('every declared reason is written down', () => {
    for (const [file, d] of Object.entries(FAILURE_NO_ID_DECLARED)) {
      expect(d.why.length, `${file} — a count without a reason is a waiver`).toBeGreaterThan(60);
    }
  });
});

describe('the total reconciles — nothing falls between the buckets', () => {
  it('the four buckets sum to the site count, per file and overall', () => {
    let grand = 0;
    for (const file of CALLERS) {
      const { total, buckets } = censusFor(file);
      const sum =
        buckets.SUCCESS_CAPTURES + buckets.SUCCESS_NO_ID +
        buckets.FAILURE_CAPTURES + buckets.FAILURE_NO_ID;
      expect(sum, `${file}`).toBe(total);
      grand += total;
    }
    // The census measured 2026-08-09. A change to this number is not a
    // failure — it is a prompt to re-read the buckets and update it knowingly.
    //
    // 19 → 20 on 2026-08-09 (B2). `llm-mdm.ts`'s judge catch gained an
    // `ai_calls` row; before B2 that branch wrote to NEITHER table, so a failed
    // judge was invisible to both meters. The prompt worked as designed: this
    // assertion is what surfaced the change for a deliberate re-read.
    expect(grand).toBe(20);
  });
});

// ---------------------------------------------------------------------------
// THE WATCHED SET vs THE TREE — the defect that produced this item
// ---------------------------------------------------------------------------

describe('no vendor caller is unwatched', () => {
  it('CALLERS covers every file in the tree that calls logAiCall', () => {
    // ⚠️ THIS IS THE ONE ASSERTION THAT WOULD HAVE CAUGHT B1-a's GAP. Every
    // other test here is exact about the five files it was handed. Only this
    // one asks whether the list of five is the right list — which is the
    // question nobody asked, and the reason three callers went unnoticed.
    const roots = ['packages/ai/src', 'apps/transcribe-md/src'];
    const found = new Set<string>();

    for (const root of roots) {
      for (const abs of walk(resolve(ROOT, root))) {
        if (!abs.endsWith('.ts') && !abs.endsWith('.tsx')) continue;
        if (/[\\/]__tests__[\\/]|\.test\.ts|\.spec\.ts/.test(abs)) continue;
        const cleaned = stripComments(readFileSync(abs, 'utf8'));
        if (logAiCallSites(cleaned).length > 0) {
          found.add(abs.slice(ROOT.length + 1));
        }
      }
    }

    expect([...found].sort()).toEqual([...CALLERS].sort());
  });
});

/** Recursive file walk, skipping node_modules / build output. */
function* walk(dir: string): Generator<string> {
  const { readdirSync } = require('node:fs') as typeof import('node:fs');
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const e of entries) {
    if (e.name === 'node_modules' || e.name === '.next' || e.name === 'dist') continue;
    const abs = resolve(dir, e.name);
    if (e.isDirectory()) yield* walk(abs);
    else yield abs;
  }
}
