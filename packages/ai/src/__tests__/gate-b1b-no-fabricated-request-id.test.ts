// ============================================================================
// GATE — B1-b STEP 2. `api_usage_events.requestId` is never invented.
// ----------------------------------------------------------------------------
// Step 1 proved the vendor's id is CAPTURED at every success site in `ai_calls`.
// This proves the other half, on the other table: that when there is no id to
// capture, nothing manufactures one.
//
// ⚠️ THE DEFECT THIS WATCHES WAS INVISIBLE BY CONSTRUCTION, AND THAT IS WHY THE
// GATE IS SHAPED LIKE THIS. Every builder used to end
// `requestId: ctx.requestId ?? randomUUID()`. The column was NOT NULL, so it was
// 100% populated — and a query could not distinguish a real vendor correlation
// id from a UUID minted a microsecond earlier. There was no error state, no
// failing test, and no surface where the difference showed. A ratchet counting
// "rows with a requestId" would have read 100% and meant nothing.
//
// So this gate does not count populated rows. It asserts the two things that
// actually make the column true:
//
//   1. BEHAVIOUR — every builder yields `null` when given no id, and passes a
//      real one through VERBATIM. Both directions, because a builder that
//      returned null unconditionally would satisfy "no fabrication" perfectly
//      and destroy the data.
//   2. CENSUS — every `logApiUsage` call site in the tree is bucketed, the
//      buckets sum to a per-file total, and the FILE LIST IS RE-DERIVED from
//      the tree and diffed against the hand-kept one.
//
// ⚠️ (2)'s last clause is the assertion that would have caught B1-a's gap — the
// one where a gate was green and truthful over a universe that did not contain
// the question. Every other test here is exact about the files it was handed;
// only that one asks whether the list is the right list.
//
// ⚠️ AND THE SOURCE ARM IS COMMENT-STRIPPED FOR A REASON THIS FILE'S OWN
// SUBJECT DEMONSTRATES. `api-usage.ts` now says the word `randomUUID` THREE
// times in prose — in the import's replacement note, in the `requestId` doc
// comment, and at the writer — explaining what was removed and why. A naive
// `'randomUUID' in source` check would fail forever on the documentation of the
// fix. That is the substring trap, and it caught this session's own occurrence
// count before it caught anything else: `grep -c 'ctx.requestId ?? randomUUID()'`
// reported SIX code sites when there were five, the sixth being a doc comment
// written minutes earlier. The stripper is positive-controlled against the REAL
// file below, not only against a fixture.
// ============================================================================

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { stripComments } from './helpers/strip-comments';

/** Captured `apiUsageEvent.create` payloads. Hoisted — see the mock below. */
const created = vi.hoisted(() => ({ calls: [] as any[] }));

const HERE = dirname(fileURLToPath(import.meta.url));
/** packages/ai/src/__tests__ → repo root */
const ROOT = resolve(HERE, '..', '..', '..', '..');

const WRITER = 'packages/ai/src/api-usage.ts';

// ---------------------------------------------------------------------------
// THE WATCHED SET — stated by hand, diffed against the tree below.
// ---------------------------------------------------------------------------
// ⚠️ NOT TRUSTED. The "no unwatched caller" test re-derives this from the tree.
// It is here to be CHECKED, not believed.
const USAGE_CALLERS = [
  'packages/ai/src/anthropic.ts',
  'packages/ai/src/deepgram-batch.ts',
  'packages/ai/src/embed.ts',
  'packages/ai/src/whisper-batch.ts',
  'apps/transcribe-md/src/lib/em-coding/llm-mdm.ts',
  'apps/transcribe-md/src/lib/email.ts',
] as const;

/**
 * Usage sites that legitimately pass NO request id, declared by file and count
 * with the reason. Anything beyond these numbers is a finding.
 *
 * ⚠️ DECLARED, NOT WAIVED — the distinction the step 1 gate also drew. A
 * declared count is a number a future change has to move deliberately; a waiver
 * is a hole with a label.
 */
const NO_ID_DECLARED: Record<string, { count: number; why: string }> = {
  'apps/transcribe-md/src/lib/email.ts': {
    count: 2,
    why:
      'Resend. It returns a MESSAGE id, not a request/correlation id — a ' +
      'different thing with a different lifetime, and threading it here would ' +
      'put a message identifier in a column whose contract is "the vendor\'s ' +
      'own id for THIS CALL". Whether Resend belongs in this table at all is a ' +
      'live question: GATE 0.5 ruled Resend NOT METERED, and these two sites ' +
      'predate it. Recorded in RELAY.md for B3/B5; not resolved by inventing an ' +
      'id in the meantime.',
  },
};

// ---------------------------------------------------------------------------
// Source utilities — find `logApiUsage(...)` sites and read their ctx object.
// ---------------------------------------------------------------------------

/** Balanced-paren extraction of each `logApiUsage(` argument, comment-free. */
function usageSites(cleaned: string): string[] {
  const out: string[] = [];
  const needle = 'logApiUsage(';
  let from = 0;
  for (;;) {
    const at = cleaned.indexOf(needle, from);
    if (at === -1) break;
    // ⚠️ SKIP THE DECLARATION AND RE-EXPORTS. `api-usage.ts` defines
    // `export function logApiUsage(event: UsageEvent)` and `index.ts` re-exports
    // the name; both contain the needle and neither is a call site. The step 1
    // gate hit precisely this — it reported `log.ts` as a caller on its first
    // run, which was the `logAiCall` declaration. Left unfixed it inflates the
    // census by one and makes the total reconcile against the wrong number.
    const before = cleaned.slice(Math.max(0, at - 40), at);
    if (/\b(function|const|let|var)\s*$/.test(before)) {
      from = at + needle.length;
      continue;
    }
    let depth = 0;
    let i = at + needle.length - 1;
    for (; i < cleaned.length; i++) {
      if (cleaned[i] === '(') depth++;
      else if (cleaned[i] === ')') {
        depth--;
        if (depth === 0) break;
      }
    }
    out.push(cleaned.slice(at + needle.length, i));
    from = i + 1;
  }
  return out;
}

/** Does this call site hand the builder a request id at all? */
function passesRequestId(argText: string): boolean {
  return /\brequestId\s*:/.test(argText);
}

function censusFor(file: string) {
  const cleaned = stripComments(readFileSync(resolve(ROOT, file), 'utf8'));
  const sites = usageSites(cleaned);
  const withId = sites.filter(passesRequestId).length;
  return { total: sites.length, withId, withoutId: sites.length - withId };
}

// ---------------------------------------------------------------------------

describe('B1-b step 2 — the meter never invents a request id', () => {
  // ── 1. BEHAVIOUR: the builders ──────────────────────────────────────────

  // Every builder, with the shape of ctx each one actually takes. Kept as data
  // so a NEW builder is a one-line addition here rather than a forgotten case —
  // and so the count below can be asserted against the module's real exports.
  const BUILDERS = [
    { name: 'buildDeepgramUsage', call: (m: any, ctx: any) => m.buildDeepgramUsage(ctx, 60) },
    { name: 'buildWhisperUsage', call: (m: any, ctx: any) => m.buildWhisperUsage(ctx, 60) },
    {
      name: 'buildAnthropicUsage',
      call: (m: any, ctx: any) => m.buildAnthropicUsage(ctx, 100, 50, 'claude-sonnet-4-6'),
    },
    {
      name: 'buildOpenAIEmbedUsage',
      call: (m: any, ctx: any) => m.buildOpenAIEmbedUsage(ctx, 100, 'text-embedding-3-small'),
    },
    { name: 'buildResendUsage', call: (m: any, ctx: any) => m.buildResendUsage(ctx, 1) },
  ] as const;

  it('NO FABRICATION — every builder yields null when given no id', async () => {
    const mod: any = await import('../api-usage');
    for (const b of BUILDERS) {
      const event = b.call(mod, { unitsSource: 'vendor' });
      expect(
        event.requestId,
        `${b.name} invented a request id. A minted value is indistinguishable ` +
          'from a real vendor id one row later, which is the whole defect.',
      ).toBeNull();
    }
  });

  it('PASSTHROUGH — every builder carries a real id VERBATIM', async () => {
    // ⚠️ THE OTHER DIRECTION, AND IT IS NOT CEREMONY. A builder hardcoded to
    // `requestId: null` would pass the arm above perfectly and silently discard
    // every real vendor id in the system. "Never fabricates" and "never
    // records" are the same assertion from one side only.
    const mod: any = await import('../api-usage');
    for (const b of BUILDERS) {
      const event = b.call(mod, { unitsSource: 'vendor', requestId: 'req_011CQ8real' });
      expect(event.requestId, `${b.name} dropped or rewrote a real vendor id`).toBe(
        'req_011CQ8real',
      );
    }
  });

  it('the builder list covers every build*Usage export', async () => {
    // The BUILDERS array is a hand-kept list. Same treatment as the file list:
    // re-derive and diff, so a sixth builder cannot be added without either
    // being tested or reddening this.
    const mod: any = await import('../api-usage');
    const exported = Object.keys(mod)
      .filter((k) => /^build.*Usage$/.test(k))
      .sort();
    expect(exported).toEqual([...BUILDERS.map((b) => b.name)].sort());
  });

  // ── 2. BEHAVIOUR: the writer ────────────────────────────────────────────

  beforeEach(() => {
    created.calls.length = 0;
    vi.resetModules();
    vi.doMock('@meddoc/db', () => ({
      default: {
        apiUsageEvent: {
          create: async (args: any) => {
            created.calls.push(args.data);
            return args.data;
          },
        },
      },
    }));
  });
  afterEach(() => {
    vi.doUnmock('@meddoc/db');
  });

  /** logApiUsage defers via setImmediate — drain it before asserting. */
  const drain = () => new Promise((r) => setImmediate(r));

  const BASE = {
    provider: 'anthropic' as const,
    operation: 'gate-probe',
    unitCount: 1,
    unitType: 'tokens_in' as const,
    unitCostUsd: 1,
    totalCostUsd: 1,
  };

  it('A MOCK ROW CARRIES NO ID, even when a caller supplies one', async () => {
    // ⚠️ THIS IS THE ARM THAT PROTECTS B0-a. `logApiUsage` is fire-and-forget:
    // it catches its own write error and console.warns. The database refuses a
    // mock row with an id (`api_usage_events_request_id_requires_vendor`), so
    // if the writer let one through, the row would simply NOT EXIST — no error
    // surfaced, no test red, and B0-a's guarantee that a mocked run meters
    // would quietly stop being true. Zeroing it in the writer means the writer
    // and the constraint cannot disagree.
    const { logApiUsage } = await import('../api-usage');
    logApiUsage({ ...BASE, unitsSource: 'mock', requestId: 'leaked-from-somewhere' });
    await drain();
    expect(created.calls).toHaveLength(1);
    expect(
      created.calls[0].requestId,
      'a mock row reached the database carrying a request id — the CHECK would ' +
        'refuse it and the fire-and-forget writer would swallow the refusal',
    ).toBeNull();
    // And the money is still zeroed — the two invariants share a code path, so
    // an edit to one can break the other.
    expect(created.calls[0].totalCostUsd).toBe(0);
  });

  it('A VENDOR ROW KEEPS ITS ID', async () => {
    const { logApiUsage } = await import('../api-usage');
    logApiUsage({ ...BASE, unitsSource: 'vendor', requestId: 'req_011CQ8real' });
    await drain();
    expect(created.calls).toHaveLength(1);
    expect(created.calls[0].requestId).toBe('req_011CQ8real');
  });

  it('A VENDOR ROW WITH NO ID WRITES NULL, not undefined', async () => {
    // `undefined` in a Prisma payload means "field absent", which on a NOT NULL
    // column is a different failure and on a nullable one is a different write.
    // Be explicit about which value lands.
    const { logApiUsage } = await import('../api-usage');
    logApiUsage({ ...BASE, unitsSource: 'vendor' });
    await drain();
    expect(created.calls).toHaveLength(1);
    expect(created.calls[0].requestId).toBeNull();
  });

  // ── 3. SOURCE: no fabrication survives ──────────────────────────────────

  it('the writer module contains no UUID fabrication in CODE', () => {
    const raw = readFileSync(resolve(ROOT, WRITER), 'utf8');
    const cleaned = stripComments(raw);
    expect(
      cleaned.includes('randomUUID'),
      'a UUID fabrication is back in api-usage.ts code. If this is a deliberate ' +
        'change it needs a ruling: the column is nullable precisely so nothing ' +
        'has to invent a value for it.',
    ).toBe(false);
  });

  it('POSITIVE CONTROL — the stripper is tested against the REAL file', () => {
    // ⚠️ WITHOUT THIS, THE ARM ABOVE IS UNFALSIFIABLE. A stripper that returned
    // the empty string would pass it forever. `api-usage.ts` deliberately
    // documents the removed fabrication in prose, so the raw file DOES contain
    // the token and the stripped file must NOT — which exercises the stripper
    // in both directions against real content rather than a fixture.
    const raw = readFileSync(resolve(ROOT, WRITER), 'utf8');
    expect(
      raw.includes('randomUUID'),
      'api-usage.ts no longer explains what was removed — the control this ' +
        'test depends on is gone, and so is the note that stops someone ' +
        'reaching for a UUID again',
    ).toBe(true);
    const cleaned = stripComments(raw);
    expect(cleaned.length).toBeGreaterThan(500);
    expect(cleaned).toContain('logApiUsage');
  });

  // ── 4. CENSUS: every site, in a named bucket, over the right universe ───

  it('every usage site is in a named bucket and the buckets sum', () => {
    let total = 0;
    for (const file of USAGE_CALLERS) {
      const c = censusFor(file);
      expect(c.total, `${file}: no logApiUsage site found — the census is blind here`)
        .toBeGreaterThan(0);
      expect(
        c.withId + c.withoutId,
        `${file}: buckets do not sum to the site count`,
      ).toBe(c.total);

      const declared = NO_ID_DECLARED[file]?.count ?? 0;
      expect(
        c.withoutId,
        `${file}: ${c.withoutId} usage site(s) pass no request id; ${declared} ` +
          `are declared. ${NO_ID_DECLARED[file]?.why ?? 'No declaration exists for this file.'}`,
      ).toBe(declared);
      total += c.total;
    }
    // The reconciled figure, stated so a change to it is deliberate.
    //
    // 8 → 10 on 2026-08-09 (B2): the six anthropic failure branches meter
    // through one shared helper (one site) and embed.ts's dim-mismatch branch
    // meters directly (one site). ⚠️ NOTE WHAT DID **NOT** MOVE — `withoutId`
    // stayed at its declaration, because both new sites pass a real vendor id
    // rather than minting one. That is this gate doing its job across an item
    // it was not written for: B2 added writers, and the no-fabrication ratchet
    // held without being touched.
    expect(total, 'the total usage-site count moved').toBe(10);
  });

  it('USAGE_CALLERS covers every file in the tree that calls logApiUsage', () => {
    // ⚠️ THE ONLY ARM THAT QUESTIONS THE LIST ITSELF. Everything above is exact
    // about six files; this asks whether six is the right number. A seventh
    // caller added tomorrow is invisible to every other assertion here.
    const found = new Set<string>();
    for (const abs of walk(resolve(ROOT, 'packages/ai/src'), resolve(ROOT, 'apps/transcribe-md/src'))) {
      if (!abs.endsWith('.ts') && !abs.endsWith('.tsx')) continue;
      if (abs.includes('__tests__') || abs.includes('/tests/')) continue;
      const rel = abs.slice(ROOT.length + 1);
      // The declaration lives in api-usage.ts and the re-export in index.ts;
      // neither is a call site.
      if (rel === WRITER || rel === 'packages/ai/src/index.ts') continue;
      const cleaned = stripComments(readFileSync(abs, 'utf8'));
      if (usageSites(cleaned).length > 0) found.add(rel);
    }
    expect([...found].sort()).toEqual([...USAGE_CALLERS].sort());
  });
});

function* walk(...roots: string[]): Generator<string> {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { readdirSync } = require('node:fs') as typeof import('node:fs');
  const stack = [...roots];
  while (stack.length) {
    const dir = stack.pop() as string;
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const e of entries) {
      const full = resolve(dir, e.name);
      if (e.isDirectory()) {
        if (e.name === 'node_modules' || e.name === '.next') continue;
        stack.push(full);
      } else {
        yield full;
      }
    }
  }
}
