// ============================================================================
// F8-S1 GATE — the ICD decision substrate.
// ----------------------------------------------------------------------------
// The claims this file exists to break, stated as claims rather than as
// intentions (AGENTS.md: give the pass the CLAIMS, not the intent):
//
//   1. the projection is a PARTITION and it reconciles against its own total
//   2. `orphaned` is a real, named bucket — a decision whose code a later
//      pipeline run removed is NOT accepted and NOT silently dropped
//   3. a code the suggester never proposed is REFUSED
//   4. one matcher serves the read path and the write path
//   5. a no-op writes nothing and reports `changed: false`
//   6. the suggester's own output is never mutated by a decision
//   7. the three new AuditAction labels are creatable in POSTGRES, not merely
//      declared — the third-layer failure that has shipped here three times
//
// ⚠️ NON-VACUITY FIRST. Every assertion below is quantified over a fixture; if
// the fixture parsed to nothing the partition arithmetic would hold trivially
// and read exactly like a clean run.
// ============================================================================

import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  applyIcdDecision,
  duplicateSuggestionCount,
  icdDecisionSummary,
  normalizeIcdCode,
  projectIcdDecisions,
  readIcdDecisions,
  suggestedIcdCodes,
} from '../icd-decisions';

const USER = 'user-1';
const AT = '2026-08-25T13:00:00.000Z';

/** Layer 7a's real output shape: `{ codes: [...] }` with the per-code fields
 *  `07a-icd-coding.ts` actually emits, including the mandatory evidence. */
function icdBlob(codes: string[]) {
  return {
    codes: codes.map((code, i) => ({
      code,
      description: `desc ${code}`,
      evidence_quote: `quote ${code}`,
      confidence: 0.9 - i * 0.1,
      confidenceLevel: 'high',
    })),
  };
}

const THREE = icdBlob(['K21.00', 'I10', 'E11.9']);

describe('F8-S1 — non-vacuity', () => {
  it('the fixture is real: three suggested codes, none empty', () => {
    const s = suggestedIcdCodes(THREE);
    expect(s.length).toBe(3);
    expect(s.every((c) => c.length > 0)).toBe(true);
    expect(s).toEqual(['K21.00', 'I10', 'E11.9']);
  });

  it('the LEGACY bare-array shape is understood too, by the one shared normaliser', () => {
    // `em-coding/icd-rows.ts` handles both shapes seen across migrations, and
    // this module reads through it rather than re-deriving the shape. If that
    // ever stops being true, this arm is what says so.
    expect(suggestedIcdCodes(THREE.codes)).toEqual(['K21.00', 'I10', 'E11.9']);
  });
});

describe('F8-S1 — the projection is a PARTITION that reconciles', () => {
  it('accepted + rejected + undecided === suggested, on every state', () => {
    let decisions: unknown = null;
    const seen: string[] = [];
    // F8-S2 / ruling #154 — a rejection carries a reason token. The partition
    // itself is unchanged and that is the point of leaving this arm alone
    // otherwise: the reason rides along, it does not re-bucket anything.
    for (const [code, intent, reason] of [
      ['K21.00', 'accepted', undefined],
      ['I10', 'rejected', 'not_supported_by_note'],
    ] as const) {
      const r = applyIcdDecision(
        { rawIcdCodes: THREE, rawIcdDecisions: decisions },
        { code, decision: intent, userId: USER, at: AT, reason },
      );
      expect(r.ok).toBe(true);
      if (!r.ok) return;
      decisions = r.decisions;
      seen.push(code);
    }

    const p = projectIcdDecisions(THREE, decisions);
    expect(p.accepted).toEqual(['K21.00']);
    expect(p.rejected).toEqual(['I10']);
    expect(p.undecided).toEqual(['E11.9']);
    expect(p.orphaned).toEqual([]);

    // THE RECONCILIATION — computed a different way from the buckets, so a
    // bucket that silently dropped a member cannot satisfy it.
    expect(p.accepted.length + p.rejected.length + p.undecided.length).toBe(
      p.suggested.length,
    );
    expect(seen.length).toBe(2);
  });

  it('a DUPLICATE suggested row is a named quantity, not a silent collapse', () => {
    const dup = icdBlob(['I10', 'I10', 'E11.9']);
    expect(suggestedIcdCodes(dup)).toEqual(['I10', 'E11.9']);
    expect(duplicateSuggestionCount(dup)).toBe(1);
    const p = projectIcdDecisions(dup, null);
    // 2 distinct + 1 collapsed == the 3 raw rows the suggester emitted.
    expect(p.suggested.length + p.duplicateSuggestions).toBe(dup.codes.length);
  });

  it('the SUMMARY is derived from the projection, so chip and sections agree', () => {
    const r = applyIcdDecision(
      { rawIcdCodes: THREE, rawIcdDecisions: null },
      { code: 'I10', decision: 'accepted', userId: USER, at: AT },
    );
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    const p = projectIcdDecisions(THREE, r.decisions);
    expect(icdDecisionSummary(p)).toEqual({
      suggested: 3,
      accepted: 1,
      needsReview: 2,
    });
  });
});

describe('F8-S1 — ⚠️ ORPHANED: the codes change under a live decision', () => {
  // ⚠️ THIS PATH IS UNREACHABLE IN THE SHIPPED CODE, AND THE ARMS STAY.
  // `icdCodes` has one writer (`07a-icd-coding.ts:572`) and `layer-skip.ts:101`
  // skips L7a whenever that column has content, so a retry does not rewrite it.
  // These arms pin the FAIL-SAFE DIRECTION for the day something does — a
  // re-code action, a force-rerun flag, a data repair. Said plainly so nobody
  // later cites them as evidence that the path is live.
  const decisions = {
    'K21.00': { state: 'accepted', at: AT, byUserId: USER },
    I10: { state: 'accepted', at: AT, byUserId: USER },
  };
  const afterRerun = icdBlob(['I10', 'E11.9']); // K21.00 is gone

  it('an accepted code the suggester no longer proposes is NOT accepted', () => {
    const p = projectIcdDecisions(afterRerun, decisions);
    expect(p.accepted).toEqual(['I10']);
    expect(p.accepted).not.toContain('K21.00');
  });

  it('and it is NOT silently discarded either — it lands in `orphaned`', () => {
    const p = projectIcdDecisions(afterRerun, decisions);
    expect(p.orphaned).toEqual(['K21.00']);
    // Disjoint from every other bucket, by construction; asserted rather than
    // trusted.
    for (const bucket of [p.accepted, p.rejected, p.undecided, p.suggested]) {
      expect(bucket).not.toContain('K21.00');
    }
  });

  it('and it counts as NEEDS REVIEW, never as a settled decision', () => {
    const p = projectIcdDecisions(afterRerun, decisions);
    // 1 undecided (E11.9) + 1 orphaned (K21.00)
    expect(icdDecisionSummary(p)).toEqual({
      suggested: 2,
      accepted: 1,
      needsReview: 2,
    });
  });
});

describe('F8-S1 — the suggested set is the authority for what may be decided', () => {
  it('REFUSES a code the suggester never proposed', () => {
    const r = applyIcdDecision(
      { rawIcdCodes: THREE, rawIcdDecisions: null },
      { code: 'Z99.9', decision: 'accepted', userId: USER, at: AT },
    );
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.reason).toBe('code_not_suggested');
  });

  it('REFUSES garbage rather than creating a record under an empty key', () => {
    for (const bad of ['', '   ', null, undefined, 42, {}]) {
      const r = applyIcdDecision(
        { rawIcdCodes: THREE, rawIcdDecisions: null },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        { code: bad as any, decision: 'accepted', userId: USER, at: AT },
      );
      expect(r.ok, `accepted a decision on ${JSON.stringify(bad)}`).toBe(false);
    }
  });

  it('POSITIVE CONTROL — the same call on a SUGGESTED code succeeds', () => {
    // Without this the refusal arms above would pass on a function that
    // refuses everything, which is a guard proven only in the red direction.
    const r = applyIcdDecision(
      { rawIcdCodes: THREE, rawIcdDecisions: null },
      { code: 'E11.9', decision: 'accepted', userId: USER, at: AT },
    );
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.changed).toBe(true);
    expect(r.decisions['E11.9']?.state).toBe('accepted');
  });
});

describe('F8-S1 — ONE matcher serves the read path and the write path', () => {
  it('a client echoing back a differently-cased code resolves to the SAME record', () => {
    const written = applyIcdDecision(
      { rawIcdCodes: THREE, rawIcdDecisions: null },
      { code: 'K21.00', decision: 'accepted', userId: USER, at: AT },
    );
    expect(written.ok).toBe(true);
    if (!written.ok) return;

    // The read path: lower-cased and padded, as a round-trip through a form
    // field or a URL can easily produce.
    const cleared = applyIcdDecision(
      { rawIcdCodes: THREE, rawIcdDecisions: written.decisions },
      { code: '  k21.00 ', decision: 'cleared', userId: USER, at: AT },
    );
    expect(cleared.ok).toBe(true);
    if (!cleared.ok) return;
    // If the two paths used different matchers this would be a no-op — the
    // silent-no-op class this repo has already paid for once.
    expect(cleared.changed).toBe(true);
    expect(cleared.from).toBe('accepted');
    expect(cleared.to).toBe(null);
    expect(Object.keys(cleared.decisions)).toEqual([]);
  });

  it('normalizeIcdCode returns the empty string for every non-string', () => {
    expect(normalizeIcdCode(' k21.00 ')).toBe('K21.00');
    for (const bad of [null, undefined, 7, {}, []]) expect(normalizeIcdCode(bad)).toBe('');
  });
});

describe('F8-S1 — a NO-OP is not an event', () => {
  it('re-asserting the stored state reports changed:false and the SAME map', () => {
    const first = applyIcdDecision(
      { rawIcdCodes: THREE, rawIcdDecisions: null },
      { code: 'I10', decision: 'rejected', userId: USER, at: AT, reason: 'other' },
    );
    expect(first.ok).toBe(true);
    if (!first.ok) return;

    // ⚠️ THE SAME REASON ON BOTH CALLS, OR IT IS NOT A NO-OP. F8-S2 makes a
    // no-op sameness of the whole RECORD, not just of the state — see the
    // reason-change arm added below, which asserts the other direction.
    const again = applyIcdDecision(
      { rawIcdCodes: THREE, rawIcdDecisions: first.decisions },
      { code: 'I10', decision: 'rejected', userId: USER, at: '2026-08-25T14:00:00.000Z', reason: 'other' },
    );
    expect(again.ok).toBe(true);
    if (!again.ok) return;
    expect(again.changed).toBe(false);
    // The timestamp must NOT move — a no-op that rewrites `at` would make the
    // audit trail claim a decision happened when none did.
    expect(again.decisions).toEqual(first.decisions);
    expect(again.decisions['I10']?.at).toBe(AT);
  });

  it('CLEARING a code with no decision is a no-op, not a refusal', () => {
    const r = applyIcdDecision(
      { rawIcdCodes: THREE, rawIcdDecisions: null },
      { code: 'I10', decision: 'cleared', userId: USER, at: AT },
    );
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.changed).toBe(false);
    expect(r.from).toBe(null);
    expect(r.to).toBe(null);
  });
});

describe("F8-S1 — the suggester's output is never touched", () => {
  it('applying a decision leaves `icdCodes` byte-identical', () => {
    const before = JSON.stringify(THREE);
    const r = applyIcdDecision(
      { rawIcdCodes: THREE, rawIcdDecisions: null },
      { code: 'K21.00', decision: 'accepted', userId: USER, at: AT },
    );
    expect(r.ok).toBe(true);
    expect(JSON.stringify(THREE)).toBe(before);
  });

  it('and the PREVIOUS decision map is not mutated in place', () => {
    const prior = { I10: { state: 'accepted' as const, at: AT, byUserId: USER } };
    const before = JSON.stringify(prior);
    const r = applyIcdDecision(
      { rawIcdCodes: THREE, rawIcdDecisions: prior },
      { code: 'I10', decision: 'cleared', userId: USER, at: AT },
    );
    expect(r.ok).toBe(true);
    expect(JSON.stringify(prior)).toBe(before);
  });
});

describe('F8-S1 — a malformed stored record is DROPPED, never repaired', () => {
  it('drops entries missing a state, an actor or a timestamp', () => {
    const raw = {
      'K21.00': { state: 'accepted', at: AT, byUserId: USER }, // good
      I10: { state: 'maybe', at: AT, byUserId: USER }, // bad state
      'E11.9': { state: 'accepted', byUserId: USER }, // no timestamp
      'J45.909': { state: 'accepted', at: AT }, // no actor
      'R51.9': 'accepted', // not an object
    };
    expect(Object.keys(readIcdDecisions(raw))).toEqual(['K21.00']);
  });

  it('an array, a string and a null all read as no decisions', () => {
    for (const bad of [[], ['K21.00'], 'K21.00', null, undefined, 7]) {
      expect(readIcdDecisions(bad)).toEqual({});
    }
  });
});

// ---------------------------------------------------------------------------
// THE THIRD LAYER — the labels must be creatable in POSTGRES
// ---------------------------------------------------------------------------
// `gate-audit-enum-migration.test.ts` already asserts this for the whole enum.
// These arms name F8-S1's OWN three, the same way B7's gate names its own —
// because a whole-set check that goes green tells you nothing about which
// member you were adding, and the failure mode here is silent.
describe('F8-S1 — the three ICD decision AuditAction labels', () => {
  const MIGRATIONS_DIR = '../../packages/db/prisma/migrations';
  const SCHEMA_PATH = '../../packages/db/prisma/schema.prisma';
  const AUDIT_TS = 'src/lib/audit.ts';
  const LABELS = [
    'ICD_CODE_ACCEPTED',
    'ICD_CODE_REJECTED',
    'ICD_CODE_DECISION_CLEARED',
  ] as const;

  function stripSqlComments(sql: string): string {
    return sql.replace(/--[^\n]*/g, '');
  }

  function migrationLabels(): Set<string> {
    const out = new Set<string>();
    for (const dir of readdirSync(MIGRATIONS_DIR)) {
      let sql: string;
      try {
        sql = stripSqlComments(
          readFileSync(join(MIGRATIONS_DIR, dir, 'migration.sql'), 'utf8'),
        );
      } catch {
        continue;
      }
      for (const m of sql.matchAll(/ALTER\s+TYPE\s+"AuditAction"[^;]*;/gi)) {
        for (const v of m[0].matchAll(/'([A-Z][A-Z0-9_]*)'/g)) out.add(v[1]);
      }
    }
    return out;
  }

  it('POSITIVE CONTROL — the migration parser is not returning an empty set', () => {
    const creatable = migrationLabels();
    expect(creatable.size).toBeGreaterThan(20);
    expect(creatable).toContain('PROMO_GRANT_CREDITED');
    expect(creatable.has('THIS_LABEL_IS_IN_NO_MIGRATION')).toBe(false);
  });

  it('each label is creatable by an ALTER TYPE migration', () => {
    const creatable = migrationLabels();
    for (const label of LABELS) {
      expect(creatable, `${label} has no ALTER TYPE migration`).toContain(label);
    }
  });

  it('each label is declared in schema.prisma AND in the TS union', () => {
    // ⚠️ Comments are stripped on both sides. This file's own header names all
    // three labels in prose, and the migration's header does too — the
    // substring family in AGENTS.md is four sightings deep precisely because a
    // comment is where the token you are grepping for is guaranteed to appear.
    const schema = readFileSync(SCHEMA_PATH, 'utf8').replace(/\/\/[^\n]*/g, '');
    const ts = readFileSync(AUDIT_TS, 'utf8').replace(/\/\/[^\n]*/g, '');
    for (const label of LABELS) {
      expect(schema, `${label} missing from schema.prisma`).toContain(`\n  ${label}\n`);
      expect(ts, `${label} missing from the TS union`).toContain(`| '${label}'`);
    }
  });

  it('the `icdDecisions` COLUMN is created by a migration and declared in the schema', () => {
    // The decision map has nowhere to live without it, and a Prisma field with
    // no migration is the same silent class one table over.
    const schema = readFileSync(SCHEMA_PATH, 'utf8').replace(/\/\/[^\n]*/g, '');
    expect(schema).toMatch(/^\s+icdDecisions\s+Json\?\s*$/m);

    let created = false;
    let control = false;
    for (const dir of readdirSync(MIGRATIONS_DIR)) {
      let sql: string;
      try {
        sql = stripSqlComments(
          readFileSync(join(MIGRATIONS_DIR, dir, 'migration.sql'), 'utf8'),
        );
      } catch {
        continue;
      }
      if (/ALTER\s+TABLE\s+"transcribe_visits"[^;]*"icdDecisions"/i.test(sql)) created = true;
      // POSITIVE CONTROL — the same matcher against a column that provably
      // exists. Without it, a broken regex reports "not created" for both and
      // the two answers are indistinguishable.
      if (/ALTER\s+TABLE\s+"transcribe_visits"[^;]*"frozenFillManifestId"/i.test(sql)) {
        control = true;
      }
    }
    expect(control, 'the column matcher found NOTHING it should have found').toBe(true);
    expect(created, 'no migration adds transcribe_visits.icdDecisions').toBe(true);
  });
});
