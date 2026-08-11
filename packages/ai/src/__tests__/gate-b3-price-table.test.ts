// @vitest-environment node
// ============================================================================
// B3 GATE — THE PRICE TABLE IS VERSIONED, SOURCED, AND COVERS WHAT RUNS.
// ----------------------------------------------------------------------------
// RELAY's gate for B3 is one sentence: "re-pricing a historical row DOES NOT
// CHANGE IT — the snapshot is proven by changing a rate and re-running."
//
// ⚠️ THAT SENTENCE IS SATISFIABLE BY A TEST THAT PROVES NOTHING, so it is not
// the whole gate here. A lookup that always returned the same constant would
// pass it. What makes it a real check is the COUNTERFACTUAL: every versioning
// assertion below runs the period-correct lookup AND the obvious wrong
// implementation (`ORDER BY effectiveFrom DESC LIMIT 1`) side by side, and
// asserts they DISAGREE after the rate change. If both columns move together,
// the fixture cannot tell a versioned table from an unversioned one and the
// gate is decoration.
//
// ── THE FIVE THINGS THIS FILE ASSERTS ──────────────────────────────────────
//
//   1. VERSIONING      a later rate never moves an earlier price  (the gate)
//   2. FAIL-CLOSED     an unpriced model is `null`, NEVER 0
//   3. THE SEED        44 rows, every one carrying a dated source
//   4. THE WATCHED SET what the table prices, diffed against what the CODE can
//                      actually emit — the check that catches a price table
//                      keyed on names nothing produces
//   5. INTEGER MONEY   no float touches a price; half-up at the micro-dollar
//
// ⚠️ ON (4), AND WHY IT IS HERE. AGENTS.md: "before any gate's zero is
// believed, diff what it WATCHES against what the item's acceptance criteria
// NAME." A price table is exactly the artefact where that fails invisibly — a
// rate keyed on `claude-opus-4.8` instead of `claude-opus-4-8` is findable by
// nothing, produces no error, and simply never matches. Both a complete table
// and a table nobody can look anything up in return zero missing rates if you
// only ask the table about itself. So the model list comes from the SOURCE, and
// the scanner that produces it is positive-controlled.
//
// ⚠️ WHAT THIS FILE DOES NOT CLAIM. It does not claim any rate is CORRECT
// against the vendor — a unit test cannot read deepgram.com. It claims each
// rate is present, integral, in-period, and carries a source somebody can go
// and check. The correctness evidence is DISCOVERY §D and the URLs on the rows.
// It also does not claim anything is BILLED from the table: nothing is, until
// B4/B6 repoint the meter.
// ============================================================================

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  UNIT_QUANTITY,
  audioSeconds,
  costMicroUsd,
  divRoundHalfUp,
  selectRate,
  tokens,
  type PriceRateRow,
} from '../price-table';

const HERE = dirname(fileURLToPath(import.meta.url));
/** packages/ai/src/__tests__ → repo root */
const ROOT = resolve(HERE, '..', '..', '..', '..');

const MIGRATION = join(
  ROOT,
  'packages/db/prisma/migrations/20260810011500_b3_price_table/migration.sql',
);

// ---------------------------------------------------------------------------
// PARSING THE SEED
//
// The migration SQL is the ONE source of truth for the rates — there is no
// TypeScript copy of them, deliberately, because two copies of a price list is
// two price lists. This parser exists only so the test can census what the
// migration actually inserts, rather than what somebody believes it inserts.
// ---------------------------------------------------------------------------

interface SeedRow {
  id: string;
  provider: string;
  modelName: string;
  deliveryMode: string;
  unitType: string;
  rateMicroUsd: bigint;
  unitQuantity: bigint;
  effectiveFrom: string;
  effectiveTo: string | null;
  provenance: string;
  sourceUrl: string | null;
  sourceReadAt: string | null;
  note: string | null;
}

/** Split one `(...)` VALUES tuple into its fields, respecting quoted strings.
 *  A naive `split(',')` is wrong here — several notes contain commas, and a
 *  parser that silently mis-splits would produce a census of the wrong thing
 *  while looking like it worked. */
function splitTuple(inner: string): string[] {
  const out: string[] = [];
  let cur = '';
  let inString = false;
  for (let i = 0; i < inner.length; i++) {
    const ch = inner[i]!;
    if (inString) {
      if (ch === "'" && inner[i + 1] === "'") {
        cur += "''";
        i++;
      } else if (ch === "'") {
        inString = false;
        cur += ch;
      } else {
        cur += ch;
      }
    } else if (ch === "'") {
      inString = true;
      cur += ch;
    } else if (ch === ',') {
      out.push(cur.trim());
      cur = '';
    } else {
      cur += ch;
    }
  }
  out.push(cur.trim());
  return out;
}

function unquote(field: string): string | null {
  if (field === 'NULL') return null;
  if (field.startsWith("'") && field.endsWith("'")) {
    return field.slice(1, -1).replace(/''/g, "'");
  }
  return field;
}

function parseSeed(): SeedRow[] {
  const sql = readFileSync(MIGRATION, 'utf8');
  const rows: SeedRow[] = [];
  for (const rawLine of sql.split('\n')) {
    const line = rawLine.trim();
    if (!line.startsWith("('b3seed_")) continue;
    const close = line.lastIndexOf(')');
    const f = splitTuple(line.slice(1, close));
    expect(f, `seed tuple must have 13 fields: ${line.slice(0, 60)}`).toHaveLength(13);
    rows.push({
      id: unquote(f[0]!)!,
      provider: unquote(f[1]!)!,
      modelName: unquote(f[2]!)!,
      deliveryMode: unquote(f[3]!)!,
      unitType: unquote(f[4]!)!,
      rateMicroUsd: BigInt(f[5]!),
      unitQuantity: BigInt(f[6]!),
      effectiveFrom: unquote(f[7]!)!,
      effectiveTo: unquote(f[8]!),
      provenance: unquote(f[9]!)!,
      sourceUrl: unquote(f[10]!),
      sourceReadAt: unquote(f[11]!),
      note: unquote(f[12]!),
    });
  }
  return rows;
}

const SEED = parseSeed();

// ---------------------------------------------------------------------------
// 1. VERSIONING — THE GATE
// ---------------------------------------------------------------------------

/** The counterfactual: the implementation somebody writes when they have not
 *  thought about history. Newest row wins, whatever instant you asked about. */
function latestRate(rows: readonly PriceRateRow[]): PriceRateRow | null {
  const sorted = [...rows].sort(
    (a, b) => b.effectiveFrom.getTime() - a.effectiveFrom.getTime(),
  );
  return sorted[0] ?? null;
}

function row(
  rateMicroUsd: bigint,
  effectiveFrom: string,
  effectiveTo: string | null,
): PriceRateRow {
  return {
    // B6 made `id` required — the ledger row snapshots WHICH rate priced it.
    id: `rate_${effectiveFrom}_${rateMicroUsd}`,
    provider: 'anthropic',
    modelName: 'claude-sonnet-5',
    deliveryMode: 'not_applicable',
    unitType: 'tokens_input',
    rateMicroUsd,
    unitQuantity: 1_000_000n,
    effectiveFrom: new Date(effectiveFrom),
    effectiveTo: effectiveTo === null ? null : new Date(effectiveTo),
    provenance: 'published',
    sourceUrl: 'https://example.test/pricing',
    sourceReadAt: new Date('2026-08-04T00:00:00Z'),
  };
}

describe('B3 gate 1 — a later rate never re-prices an earlier call', () => {
  // Sonnet 5's real, published, two-period rate: $2/MTok through 2026-08-31,
  // $3/MTok from 2026-09-01. Not an invented fixture — it is in the seed.
  const before = [
    row(2_000_000n, '2026-08-04T00:00:00Z', '2026-09-01T00:00:00Z'),
    row(3_000_000n, '2026-09-01T00:00:00Z', null),
  ];
  // The rate change: close the incumbent, append its successor. The table is
  // never UPDATEd in place — that is what makes the history stable.
  const after = [
    row(2_000_000n, '2026-08-04T00:00:00Z', '2026-09-01T00:00:00Z'),
    row(3_000_000n, '2026-09-01T00:00:00Z', '2026-11-01T00:00:00Z'),
    row(9_000_000n, '2026-11-01T00:00:00Z', null),
  ];

  const august = new Date('2026-08-15T12:00:00Z');
  const september = new Date('2026-09-15T12:00:00Z');
  const november = new Date('2026-11-15T12:00:00Z');

  it('prices each instant from the period that contained it', () => {
    expect(selectRate(before, august)?.rateMicroUsd).toBe(2_000_000n);
    expect(selectRate(before, september)?.rateMicroUsd).toBe(3_000_000n);
  });

  it('THE GATE: the August and September prices do not move when a new rate lands', () => {
    expect(selectRate(after, august)?.rateMicroUsd).toBe(2_000_000n);
    expect(selectRate(after, september)?.rateMicroUsd).toBe(3_000_000n);
    // …and the new rate does apply to calls made under it, so the table is not
    // simply frozen.
    expect(selectRate(after, november)?.rateMicroUsd).toBe(9_000_000n);
  });

  it('and the gate is NOT VACUOUS — the wrong implementation moves all three', () => {
    // If this ever passes, the fixture cannot distinguish a versioned table
    // from an unversioned one and every assertion above is worthless.
    expect(latestRate(after)?.rateMicroUsd).toBe(9_000_000n);
    expect(selectRate(after, august)?.rateMicroUsd).not.toBe(
      latestRate(after)?.rateMicroUsd,
    );
    expect(selectRate(after, september)?.rateMicroUsd).not.toBe(
      latestRate(after)?.rateMicroUsd,
    );
  });

  it('treats a period as [from, to) so a midnight handover has exactly one answer', () => {
    const boundary = new Date('2026-09-01T00:00:00Z');
    expect(selectRate(before, boundary)?.rateMicroUsd).toBe(3_000_000n);
    const justBefore = new Date('2026-08-31T23:59:59.999Z');
    expect(selectRate(before, justBefore)?.rateMicroUsd).toBe(2_000_000n);
  });

  it('refuses to guess when two rates overlap, rather than picking one', () => {
    const overlapping = [
      row(2_000_000n, '2026-08-04T00:00:00Z', null),
      row(3_000_000n, '2026-09-01T00:00:00Z', null),
    ];
    // Unrepresentable in the database — `price_rates_no_overlap` refuses it.
    // If the constraint is ever dropped, the reader must not silently pick.
    expect(() => selectRate(overlapping, new Date('2026-10-01T00:00:00Z'))).toThrow(
      /overlapping rates/,
    );
  });
});

// ---------------------------------------------------------------------------
// 2. FAIL-CLOSED — `null`, never 0
// ---------------------------------------------------------------------------

describe('B3 gate 2 — an unpriced call is null, never zero', () => {
  const rates = [row(2_000_000n, '2026-08-04T00:00:00Z', null)];

  it('returns null before the earliest known period', () => {
    // The seed starts at the READ-DATE because that is the day we know the
    // rate held. Backdating to '-infinity' would assert something unverified.
    const answer = selectRate(rates, new Date('2026-07-01T00:00:00Z'));
    expect(answer).toBeNull();
    expect(answer).not.toBe(0);
  });

  it('nova-3-medical — the model that actually runs — is deliberately absent', () => {
    // SPEC §4.5 disqualifies its only public figure (an UNDATED announcement
    // post) from a `published` provenance. Its absence is the honest state, and
    // the migration asserts it too, so this cannot drift silently.
    const medical = SEED.filter((r) => r.modelName === 'nova-3-medical');
    expect(medical).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// 3. THE SEED
// ---------------------------------------------------------------------------

describe('B3 gate 3 — every seeded rate carries a source somebody can check', () => {
  it('parsed the migration at all (positive control on the parser)', () => {
    // A parser that silently matches nothing and a table with no rows produce
    // the same census, so the census is worthless without this line.
    expect(SEED.length).toBeGreaterThan(0);
    expect(SEED.map((r) => r.modelName)).toContain('claude-opus-4-8');
  });

  it('holds exactly the 44 rows the migration declares', () => {
    expect(SEED).toHaveLength(44);
    const byProvider = (p: string) => SEED.filter((r) => r.provider === p).length;
    expect(byProvider('anthropic')).toBe(40);
    expect(byProvider('deepgram')).toBe(2);
    expect(byProvider('openai')).toBe(2);
  });

  it('every row is `published` with BOTH a url and a read-date — SPEC §4.5', () => {
    for (const r of SEED) {
      expect(r.provenance, r.id).toBe('published');
      expect(r.sourceUrl, r.id).toMatch(/^https:\/\//);
      expect(r.sourceReadAt, r.id).toBe('2026-08-04T00:00:00Z');
    }
  });

  it('every rate is a non-negative integer against its declared denominator', () => {
    for (const r of SEED) {
      expect(r.rateMicroUsd >= 0n, r.id).toBe(true);
      const declared = UNIT_QUANTITY[r.unitType as keyof typeof UNIT_QUANTITY];
      expect(declared, `${r.id}: undeclared unit type ${r.unitType}`).toBeDefined();
      // The TypeScript mirror and the SQL CHECK must agree. Keeping them in one
      // place is impossible; keeping them diffed is not.
      expect(r.unitQuantity, `${r.id} unitQuantity`).toBe(declared);
    }
  });

  it('CORRECTION 1 — Anthropic has TWO cache-write classes, not one', () => {
    // The vendor charges 1.25x and 2x; `pricing.ts:claudeCostCents` collapses
    // them into a single 1.25x. If these two ever seed equal, the correction
    // has been undone.
    const models = [...new Set(SEED.filter((r) => r.provider === 'anthropic').map((r) => r.modelName))];
    expect(models.length).toBeGreaterThan(0);
    for (const m of models) {
      const of = (u: string) =>
        SEED.filter((r) => r.modelName === m && r.unitType === u).map((r) => r.rateMicroUsd);
      const w5 = of('cache_write_5m');
      const w1h = of('cache_write_1h');
      expect(w5.length, `${m} cache_write_5m`).toBeGreaterThan(0);
      expect(w1h.length, `${m} cache_write_1h`).toBeGreaterThan(0);
      for (let i = 0; i < w5.length; i++) {
        expect(w1h[i], `${m}: the two cache-write classes must differ`).not.toBe(w5[i]);
        // 1.25x -> 2x is exactly 1.6x between the two write classes.
        expect(w1h[i]! * 5n).toBe(w5[i]! * 8n);
      }
    }
  });

  it('CORRECTION 2 — the Deepgram rate is the vendor’s, not the in-code 3.4x one', () => {
    // `pricing.ts:32` DEFAULT_DEEPGRAM_CENTS_PER_MIN = 1.45 -> $0.0145/min ->
    // 14500 micro-dollars. The published Nova-3 pre-recorded rate is $0.0077.
    const dgPre = SEED.find(
      (r) => r.provider === 'deepgram' && r.deliveryMode === 'pre_recorded',
    );
    expect(dgPre?.rateMicroUsd).toBe(7_700n);
    expect(dgPre?.rateMicroUsd).not.toBe(14_500n);
  });

  it('CORRECTION 3 — three Deepgram rates are owed and TWO are seeded, on purpose', () => {
    const dg = SEED.filter((r) => r.provider === 'deepgram');
    expect(dg).toHaveLength(2);
    expect(dg.map((r) => `${r.modelName}/${r.deliveryMode}`).sort()).toEqual([
      'nova-3/pre_recorded',
      'nova-3/streaming',
    ]);
  });

  it('CORRECTION 4 — the embedding rate is $0.02/M, not api-usage.ts’s $0.13/M', () => {
    // Two in-code surfaces disagree by 6.5x and the DURABLE one (ruling 78b
    // makes `api_usage_events` the billing source) holds the wrong, higher
    // number: `api-usage.ts:66` openai_embedding: 0.13.
    const embed = SEED.find((r) => r.modelName === 'text-embedding-3-small');
    expect(embed?.rateMicroUsd).toBe(20_000n);
    expect(embed?.rateMicroUsd).not.toBe(130_000n);
  });

  it('Resend has no rate at all — GATE 0.5, a subscription is not a meter', () => {
    expect(SEED.filter((r) => r.provider === 'resend')).toHaveLength(0);
  });

  it('no two seeded rows share a key AND an overlapping period', () => {
    // The database enforces this with an EXCLUDE constraint; asserting it on
    // the seed too means a bad row is caught in CI rather than at deploy time.
    const seen = new Map<string, Array<[number, number]>>();
    for (const r of SEED) {
      const key = `${r.provider}|${r.modelName}|${r.unitType}|${r.deliveryMode}`;
      const from = Date.parse(r.effectiveFrom);
      const to = r.effectiveTo === null ? Number.POSITIVE_INFINITY : Date.parse(r.effectiveTo);
      expect(to, r.id).toBeGreaterThan(from);
      for (const [f, t] of seen.get(key) ?? []) {
        expect(from < t && f < to, `${r.id} overlaps another row on ${key}`).toBe(false);
      }
      seen.set(key, [...(seen.get(key) ?? []), [from, to]]);
    }
  });
});

// ---------------------------------------------------------------------------
// 4. THE WATCHED SET — what the table prices vs what the CODE can emit
// ---------------------------------------------------------------------------

/** Model ids the pipeline can put on a usage row. Read from the SOURCE, because
 *  asking the price table which models it prices can only ever return "all of
 *  them". */
function emittableModelNames(): Map<string, string[]> {
  const roots = [
    join(ROOT, 'packages/ai/src'),
    join(ROOT, 'apps/transcribe-md/src'),
  ];
  const found = new Map<string, string[]>();

  const walk = (dir: string): string[] => {
    const out: string[] = [];
    for (const entry of readdirSync(dir)) {
      const p = join(dir, entry);
      if (statSync(p).isDirectory()) {
        // Tests name models that no production path sends — `claude-opus-4-6`
        // exists only to exercise temperature stripping. Including them would
        // demand rates for models nobody calls.
        if (entry === '__tests__' || entry === 'tests') continue;
        out.push(...walk(p));
      } else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) {
        out.push(p);
      }
    }
    return out;
  };

  // The three shapes a model id reaches a vendor call through on this stack:
  //   const MODEL = process.env.X || 'id'      — the layer default
  //   const DEFAULT_BATCH_MODEL = 'id'         — the package default
  //   model: 'id'                              — a per-call override
  const patterns = [
    /process\.env\.[A-Z_]+\s*(?:\?\?|\|\|)\s*'([a-z0-9][a-z0-9.\-]*)'/g,
    /\bDEFAULT_[A-Z_]*MODEL\s*(?::\s*string)?\s*=\s*'([a-z0-9][a-z0-9.\-]*)'/g,
    /\bmodel:\s*'([a-z0-9][a-z0-9.\-]*)'/g,
  ];
  const looksLikeAModel = /^(claude|nova|whisper|text-embedding|gpt)-/;

  for (const rootDir of roots) {
    for (const file of walk(rootDir)) {
      const src = readFileSync(file, 'utf8');
      for (const re of patterns) {
        re.lastIndex = 0;
        let m: RegExpExecArray | null;
        while ((m = re.exec(src)) !== null) {
          const id = m[1]!;
          if (!looksLikeAModel.test(id)) continue;
          // `whisper-fallback` is a PROVIDER tag, not a model id — the canary
          // value written to `transcriptionProvider`. It is the one string that
          // passes the shape test and is not a model.
          if (id === 'whisper-fallback') continue;
          found.set(id, [...(found.get(id) ?? []), file.slice(ROOT.length + 1)]);
        }
      }
    }
  }
  return found;
}

/** Emittable model ids that are KNOWINGLY unpriced, each with the reason.
 *  ⚠️ Adding a name here is a decision, not a fix. An entry with no reason is
 *  a hole with a label. */
const KNOWINGLY_UNPRICED: Readonly<Record<string, string>> = {
  'nova-3-medical':
    'PARKED — SPEC §4.5 disqualifies its only public figure (an undated ' +
    'announcement post) from a `published` provenance. Needs invoice or ' +
    'console truth; see docs/foundation/B3-deepgram-rate-request.md.',
};

describe('B3 gate 4 — the table prices what the code can actually emit', () => {
  const emittable = emittableModelNames();
  const priced = new Set(SEED.map((r) => r.modelName));

  it('the scanner works (positive control) — it finds the two live defaults', () => {
    // Without this, a scanner that matches nothing reports full coverage.
    expect([...emittable.keys()]).toContain('claude-opus-4-8');
    expect([...emittable.keys()]).toContain('claude-sonnet-4-6');
    expect(emittable.size).toBeGreaterThanOrEqual(4);
  });

  it('every emittable model is priced, or named as knowingly unpriced', () => {
    const unaccounted = [...emittable.entries()]
      .filter(([id]) => !priced.has(id) && !(id in KNOWINGLY_UNPRICED))
      .map(([id, files]) => `${id}  (${files.join(', ')})`);
    expect(unaccounted, 'model ids the code emits that nothing prices').toEqual([]);
  });

  it('the park list is not stale — every entry is still emittable and still unpriced', () => {
    // A park entry for a model that has since been priced, or that no code
    // sends any more, is a comment pretending to be a decision.
    for (const [id, reason] of Object.entries(KNOWINGLY_UNPRICED)) {
      expect(reason.length, `${id} needs a reason`).toBeGreaterThan(40);
      expect(emittable.has(id), `${id} is parked but nothing emits it`).toBe(true);
      expect(priced.has(id), `${id} is parked but IS priced — remove the entry`).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
// 5. INTEGER MONEY
// ---------------------------------------------------------------------------

describe('B3 gate 5 — no float touches a price', () => {
  const rate = (micro: bigint, qty: bigint): PriceRateRow => ({
    ...row(micro, '2026-08-04T00:00:00Z', null),
    unitQuantity: qty,
  });

  it('rounds half-up at the micro-dollar, on both sides of the boundary', () => {
    expect(divRoundHalfUp(1n, 2n)).toBe(1n); // 0.5  -> 1
    expect(divRoundHalfUp(1n, 3n)).toBe(0n); // 0.33 -> 0
    expect(divRoundHalfUp(2n, 3n)).toBe(1n); // 0.67 -> 1
    expect(divRoundHalfUp(1n, 4n)).toBe(0n); // 0.25 -> 0
    expect(divRoundHalfUp(3n, 4n)).toBe(1n); // 0.75 -> 1
    expect(divRoundHalfUp(0n, 7n)).toBe(0n);
  });

  it('refuses a negative quantity rather than pricing it', () => {
    expect(() => divRoundHalfUp(-1n, 2n)).toThrow(/negative/);
    expect(() => divRoundHalfUp(1n, 0n)).toThrow(/positive/);
  });

  it('prices tokens exactly — 1.2M input tokens at $5/MTok is $6.00', () => {
    expect(costMicroUsd(tokens(1_200_000), rate(5_000_000n, 1_000_000n))).toBe(6_000_000n);
  });

  it('prices audio exactly — 90s at $0.0077/min is 11550 micro-dollars', () => {
    // 1.5 minutes x 7700 = 11550. Exact, because the /60 never became a float.
    expect(costMicroUsd(audioSeconds(90), rate(7_700n, 1n))).toBe(11_550n);
  });

  it('a sub-cent call is not rounded away — the reason the unit is micro-dollars', () => {
    // 1000 tokens at $0.10/MTok = $0.0001 = 100 micro-dollars. In CENTS this is
    // 0.01c and rounds to 0 — which is why 98 of 1085 priced `ai_calls` rows
    // store costUsdCents = 0 for calls that really cost money.
    expect(costMicroUsd(tokens(1_000), rate(100_000n, 1_000_000n))).toBe(100n);
  });

  it('summing 231 identical sub-cent calls does not drift', () => {
    const one = costMicroUsd(tokens(1_333), rate(3_000_000n, 1_000_000n));
    let total = 0n;
    for (let i = 0; i < 231; i++) total += one;
    expect(total).toBe(one * 231n);
  });
});
