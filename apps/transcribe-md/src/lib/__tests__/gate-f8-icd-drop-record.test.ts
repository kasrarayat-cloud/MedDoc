// ============================================================================
// F8-S1b GATE — the drop record, and the forward-compat narrowers.
// ----------------------------------------------------------------------------
// The claims this file exists to BREAK, stated as claims rather than as
// intentions (AGENTS.md: give the pass the CLAIMS, not the intent):
//
//   1. each of L7a's four exits produces ITS OWN reason — swapping two is the
//      whole product of this slice inverted
//   2. ⚠️ THE SAFETY CLAIM: a code that SURVIVED into `codes[]` is never also
//      reported as dropped, so a dropped code can never be accepted
//   3. no code appears twice in the stored record
//   4. `dropped` is invisible to every existing reader of `icdCodes`
//   5. no MODEL-AUTHORED string is stored
//   6. the narrowers are exhaustive over their own record types
//
// ⚠️ **THIS FILE WAS REWRITTEN AFTER THE ADVERSARIAL PASS, AND THE REWRITE IS
// THE POINT.** The first version proved claim 1 by REGEXING `07a-icd-coding.ts`
// for `dropRecord(… 'reason')` call sites. The pass demonstrated that arm stays
// GREEN when two reason tokens are SWAPPED between their loops — four call
// sites, four tokens, one each, and every varicose suppression reported to the
// physician as "the note explicitly denies this". It also went RED on
// `dropRecord(normalizeIcdCode(c.code), …)` because `[^)]*` cannot cross a
// nested paren: false green on the regression that matters and false rejection
// on a tightening, from one line.
//
// **The cure was not a better regex.** The accumulation moved into
// `buildIcdDropRecords`, a pure exported function, and this gate DRIVES it.
// A source scan cannot see a swap; an execution can.
//
// ⚠️ NON-VACUITY FIRST. Every count arm is quantified over the real allowlist
// and real record shapes; `codes: 0` from a barrel re-export is this
// programme's own reference case for what an unchecked zero costs.
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';
import { ICD10_ALLOWLIST, isValidIcd10 } from '@meddoc/ai';

import {
  ICD_DROP_REASONS,
  ICD_DROP_RECORD_KEYS,
  amberIcdDrops,
  buildIcdDropRecords,
  icdDropCountsByReason,
  readIcdDrops,
  type IcdDropInputs,
  type IcdDropRecord,
} from '../icd-drops';
import {
  ICD_DECISION_RECORD_KEYS,
  applyIcdDecision,
  projectIcdDecisions,
  readIcdDecisions,
  suggestedIcdCodes,
} from '../icd-decisions';
import { extractIcdRows } from '../em-coding/icd-rows';

const SRC = join(__dirname, '..', '..');

/**
 * ⚠️ COMMENTS OUT, ALWAYS, BEFORE ANY SOURCE ASSERTION.
 *
 * The first draft of the export-surface arm went RED against correct code:
 * `visit-export-server.ts:104`, `ehr-formatters.ts:111` and
 * `docx-generator.ts:471,667` all contain the ENGLISH WORD "dropped" in prose
 * about unrelated things. AGENTS.md's substring-trap family — *a file's comments
 * are the one place where the words you are grepping for are guaranteed to
 * appear.*
 */
function codeOnly(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((l) => !l.trim().startsWith('//'))
    .join('\n');
}

/** Layer 7a's real stored shape, as this slice writes it. */
function blob(codes: string[], dropped: IcdDropRecord[] = []) {
  return {
    codes: codes.map((code, i) => ({
      code,
      description: `desc ${code}`,
      evidence_quote: `quote ${code}`,
      confidence: 0.9 - i * 0.05,
      confidenceLevel: 'high' as const,
    })),
    dropped,
  };
}

const NO_DROPS: IcdDropInputs = {
  notInVerifiedAllowlist: [],
  incoherentVaricose: [],
  contradictedByDenial: [],
  unsupportedDeficiency: [],
  survivors: [],
};

// ---------------------------------------------------------------------------
describe('NON-VACUITY — the instruments read real data, not a barrel', () => {
  it('the allowlist is read THROUGH the Set and is populated', () => {
    // ⚠️ A FLOOR, NOT `toBe(604)`. The pass pointed out that an exact total
    // reddens this gate on any routine allowlist addition — a precedented change
    // here (AGENTS.md's GI cohort) — with a message about 604 that has nothing
    // to do with the drop record, in a file that author has no reason to read.
    // A false rejection is a defect, and it is the kind an author fixes by
    // weakening the guard. The floor plus the two membership controls below
    // carry the same non-vacuity weight without that.
    expect(ICD10_ALLOWLIST.size).toBeGreaterThanOrEqual(604);
    // Positive control: a known member resolves THROUGH the Set.
    expect(isValidIcd10('K21.00')).toBe(true);
    // Negative control: a shape that is not a member.
    expect(isValidIcd10('ZZZ.99')).toBe(false);
  });

  it('the reason set is the four exits, distinct', () => {
    expect(ICD_DROP_REASONS.length).toBe(4);
    expect(new Set(ICD_DROP_REASONS).size).toBe(4);
  });

  it('⚠️ the token names COVERAGE, not billability — the name is the finding', () => {
    // `isValidIcd10` is membership of a 604-code STARTER set that its own header
    // says does not replace the ~70 000-code CMS list. Measured on production:
    // of 65 distinct refused codes, 51 are REAL submittable codes absent from
    // that set. A token reading `not_in_billable_set` asserted something false
    // about those 51, in the under-coding direction. Pinned so the rename cannot
    // silently regress.
    expect(ICD_DROP_REASONS as readonly string[]).toContain('not_in_verified_allowlist');
    expect(ICD_DROP_REASONS as readonly string[]).not.toContain('not_in_billable_set');
  });
});

// ---------------------------------------------------------------------------
describe('buildIcdDropRecords — DRIVEN, because a source scan cannot see a swap', () => {
  it('⚠️ each exit produces ITS OWN reason — the arm a regex could not make', () => {
    // Distinct code per bucket, so ANY permutation of the four assignments
    // produces a different result. This is the arm that replaces the source
    // scan the pass defeated by swapping two tokens.
    const out = buildIcdDropRecords({
      notInVerifiedAllowlist: ['A00.0'],
      incoherentVaricose: ['I83.90'],
      contradictedByDenial: ['K21.9'],
      unsupportedDeficiency: ['E53.8'],
      survivors: [],
    });
    expect(out).toEqual([
      { code: 'A00.0', reason: 'not_in_verified_allowlist' },
      { code: 'I83.90', reason: 'incoherent_asymptomatic_varicose' },
      { code: 'K21.9', reason: 'contradicted_by_denial' },
      { code: 'E53.8', reason: 'unsupported_deficiency' },
    ]);
  });

  it('every reason token is reachable — no exit is unwired', () => {
    const reached = new Set(
      buildIcdDropRecords({
        notInVerifiedAllowlist: ['A00.0'],
        incoherentVaricose: ['I83.90'],
        contradictedByDenial: ['K21.9'],
        unsupportedDeficiency: ['E53.8'],
        survivors: [],
      }).map((d) => d.reason),
    );
    expect([...reached].sort()).toEqual([...ICD_DROP_REASONS].sort());
  });

  it('⚠️ THE SAFETY CLAIM — a SURVIVING code is never also reported dropped', () => {
    // The clinical finding from the adversarial pass. The coherence floors
    // decide per CANDIDATE OBJECT on its `evidence_quote`; a drop record is
    // keyed by CODE; `IcdResult` places no uniqueness constraint on the model's
    // array. So one code emitted twice with different evidence has one instance
    // kept and one dropped, and without the survivor exclusion the blob asserts
    // both "E63.9 is suggested" and "E63.9 was suppressed".
    const out = buildIcdDropRecords({
      ...NO_DROPS,
      unsupportedDeficiency: ['E63.9'],
      survivors: ['E63.9'],
    });
    expect(out).toEqual([]);
  });

  it('the exclusion is by NORMALISED code, not by string identity', () => {
    const out = buildIcdDropRecords({
      ...NO_DROPS,
      unsupportedDeficiency: [' e63.9 '],
      survivors: ['E63.9'],
    });
    expect(out).toEqual([]);
  });

  it('and it excludes ONLY the survivor — a genuine drop still lands', () => {
    // Non-vacuity for the arm above: an exclusion that swallowed everything
    // would satisfy it just as well.
    const out = buildIcdDropRecords({
      ...NO_DROPS,
      unsupportedDeficiency: ['E63.9', 'E53.8'],
      survivors: ['E63.9'],
    });
    expect(out).toEqual([{ code: 'E53.8', reason: 'unsupported_deficiency' }]);
  });

  it('⚠️ dedupes within a bucket — a real production response emitted a repeat', () => {
    // `["I87.312","I87.312","I87.302", …]` is an actual rejected-codes payload
    // from `audit_logs`. The ACCEPTED side already dedupes
    // (`suggestedIcdCodes`); before this the drop side did not, so a partition
    // drawn across both could not reconcile and the surface rendered one code
    // twice.
    const out = buildIcdDropRecords({
      ...NO_DROPS,
      notInVerifiedAllowlist: ['I87.312', 'I87.312', 'I87.302'],
    });
    expect(out.map((d) => d.code)).toEqual(['I87.312', 'I87.302']);
  });

  it('dedupes ACROSS buckets deterministically — first reason in the array wins', () => {
    // Unreachable upstream (the buckets are disjoint), so this pins the
    // behaviour rather than describing today's data.
    const out = buildIcdDropRecords({
      ...NO_DROPS,
      notInVerifiedAllowlist: ['K21.9'],
      contradictedByDenial: ['K21.9'],
    });
    expect(out).toEqual([{ code: 'K21.9', reason: 'not_in_verified_allowlist' }]);
  });

  it('drops unusable codes rather than recording an empty one', () => {
    const out = buildIcdDropRecords({
      ...NO_DROPS,
      notInVerifiedAllowlist: ['', '   ', 'K21.9'],
    });
    expect(out).toEqual([{ code: 'K21.9', reason: 'not_in_verified_allowlist' }]);
  });

  it('no drops in, no records out', () => {
    expect(buildIcdDropRecords(NO_DROPS)).toEqual([]);
  });

  it('the built list carries EXACTLY the record keys — no model prose can ride in', () => {
    const out = buildIcdDropRecords({ ...NO_DROPS, notInVerifiedAllowlist: ['K21.9'] });
    expect(Object.keys(out[0]).sort()).toEqual([...ICD_DROP_RECORD_KEYS].sort());
  });
});

// ---------------------------------------------------------------------------
describe('⚠️ THE SAFETY CLAIM, end to end — a dropped code cannot reach the record', () => {
  const dropped = buildIcdDropRecords({ ...NO_DROPS, notInVerifiedAllowlist: ['K21.0'] });
  const poison = blob(['E11.9'], dropped);

  it('non-vacuity: the fixture really does carry a drop', () => {
    expect(dropped).toHaveLength(1);
    expect(readIcdDrops(poison)).toHaveLength(1);
  });

  it('extractIcdRows — the ONE normaliser — never yields a dropped code', () => {
    const rows = extractIcdRows(poison).map((r) => r.code);
    expect(rows).toEqual(['E11.9']); // exact, not toContain — the substring trap
  });

  it('a dropped code is not SUGGESTED, so it can never be decided', () => {
    expect(suggestedIcdCodes(poison)).toEqual(['E11.9']);
    const r = applyIcdDecision(
      { rawIcdCodes: poison, rawIcdDecisions: {} },
      { code: 'K21.0', decision: 'accepted', userId: 'u1', at: '2026-08-25T00:00:00.000Z' },
    );
    expect(r.ok).toBe(false);
    expect(r.ok === false && r.reason).toBe('code_not_suggested');
  });

  it('the projection partition is unchanged by the presence of drops', () => {
    const p = projectIcdDecisions(poison, {});
    expect(p.suggested).toEqual(['E11.9']);
    expect(p.accepted.length + p.rejected.length + p.undecided.length).toBe(
      p.suggested.length,
    );
    expect(p.orphaned).toEqual([]);
  });

  it('⚠️ the EXPORT surface has no path to `dropped` — a controlled zero', () => {
    const exporters = [
      'lib/visit-export-server.ts',
      'lib/ehr-formatters.ts',
      'lib/docx-generator.ts',
    ];
    // ⚠️ THE MATCHER INCLUDES DESTRUCTURING. The pass showed the first version
    // missed `const { codes, dropped } = icdBlob ?? {}` — which is exactly how
    // anyone would pull the record in `visit-export-server.ts`, beside the
    // existing `const icdBlob = …` — and `blob["dropped"]`.
    const CARRIER =
      /\.dropped\b|\bdropped\s*[:,}]|\{[^}]*\bdropped\b[^}]*\}\s*=|\[\s*['"]dropped['"]\s*\]|readIcdDrops|amberIcdDrops|icd-drops/;
    for (const rel of exporters) {
      const src = codeOnly(readFileSync(join(SRC, rel), 'utf8'));
      expect(src, `${rel} must not reach the drop record`).not.toMatch(CARRIER);
    }
  });

  it('⚠️ and the carrier matcher DISCRIMINATES — every escape the pass found', () => {
    // AGENTS.md: *a control aimed where the answer is predetermined is not a
    // control.* The first version's control counted files matching /icdCodes/ —
    // a DIFFERENT regex from the assertion, over files `readFileSync` would have
    // thrown on. It could not detect a broken carrier matcher, which is the only
    // thing the arm depends on. This one feeds the matcher the exact strings a
    // future reader would write.
    const CARRIER =
      /\.dropped\b|\bdropped\s*[:,}]|\{[^}]*\bdropped\b[^}]*\}\s*=|\[\s*['"]dropped['"]\s*\]|readIcdDrops|amberIcdDrops|icd-drops/;
    const mustCatch = [
      'const { codes, dropped } = icdBlob ?? {};',
      'const { dropped: amberCards } = blob;',
      'const amber = icdBlob?.dropped ?? [];',
      'const amber = icdBlob?.["dropped"] ?? [];',
      "import { readIcdDrops } from '@/lib/icd-drops';",
      'const x = { dropped };',
    ];
    for (const s of mustCatch) expect(s, `matcher missed: ${s}`).toMatch(CARRIER);
    // And it does not fire on prose, which is what made the first version red.
    const mustNotCatch = [
      '// Separator rows are dropped at flush time.',
      'const droppedFrames = 0;',
    ];
    for (const s of mustNotCatch) expect(s, `matcher over-fired: ${s}`).not.toMatch(CARRIER);
  });
});

// ---------------------------------------------------------------------------
describe('readIcdDrops — defensive narrowing, and the shapes the column holds', () => {
  it('reads a well-formed record', () => {
    expect(readIcdDrops(blob([], [{ code: 'K21.0', reason: 'not_in_verified_allowlist' }])))
      .toEqual([{ code: 'K21.0', reason: 'not_in_verified_allowlist' }]);
  });

  it('the LEGACY bare-array shape carries no drop record', () => {
    expect(readIcdDrops([{ code: 'E11.9' }])).toEqual([]);
  });

  it('a blob with no `dropped` key reads EMPTY, not undefined', () => {
    // Measured on production 2026-08-25: all 49 non-null rows are objects whose
    // only top-level key is `codes`, so this is the shape of the ENTIRE existing
    // corpus.
    expect(readIcdDrops({ codes: [] })).toEqual([]);
    expect(readIcdDrops(null)).toEqual([]);
    expect(readIcdDrops('nonsense')).toEqual([]);
    // ⚠️ length-8 truthy garbage — the shape that defeated
    // `hasDraftedPrescriptions` in AGENTS.md's medications gate.
    expect(readIcdDrops({ codes: [], dropped: 'nonsense' })).toEqual([]);
  });

  it('an UNKNOWN reason token is dropped rather than narrated', () => {
    expect(
      readIcdDrops({ codes: [], dropped: [{ code: 'K21.0', reason: 'because_i_said_so' }] }),
    ).toEqual([]);
  });

  it('the RETIRED token is not silently accepted', () => {
    expect(
      readIcdDrops({ codes: [], dropped: [{ code: 'K21.0', reason: 'not_in_billable_set' }] }),
    ).toEqual([]);
  });

  it('a record with no usable code is dropped', () => {
    expect(
      readIcdDrops({
        codes: [],
        dropped: [
          { code: '', reason: 'not_in_verified_allowlist' },
          { code: 42, reason: 'not_in_verified_allowlist' },
          { reason: 'not_in_verified_allowlist' },
        ],
      }),
    ).toEqual([]);
  });

  it('normalises the code with the shared matcher', () => {
    const d = readIcdDrops({
      codes: [],
      dropped: [{ code: ' k21.0 ', reason: 'not_in_verified_allowlist' }],
    });
    expect(d[0].code).toBe('K21.0');
  });

  it('the READER dedupes too — a hand-edited row cannot double a card', () => {
    const d = readIcdDrops({
      codes: [],
      dropped: [
        { code: 'K21.0', reason: 'not_in_verified_allowlist' },
        { code: 'k21.0', reason: 'not_in_verified_allowlist' },
      ],
    });
    expect(d).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
describe('the partition by reason reconciles, and every bucket is named', () => {
  const four = blob(
    [],
    buildIcdDropRecords({
      notInVerifiedAllowlist: ['A00.0'],
      incoherentVaricose: ['I83.90'],
      contradictedByDenial: ['K21.9'],
      unsupportedDeficiency: ['E53.8'],
      survivors: [],
    }),
  );

  it('every reason token gets a key whether or not it occurred', () => {
    const counts = icdDropCountsByReason(blob([]));
    expect(Object.keys(counts).sort()).toEqual([...ICD_DROP_REASONS].sort());
    for (const r of ICD_DROP_REASONS) expect(counts[r]).toBe(0);
  });

  it('the counts sum to the record count AND to the DISTINCT code count', () => {
    // ⚠️ THE SECOND HALF IS THE ONE THAT MATTERS. Summing to
    // `readIcdDrops().length` alone reconciles trivially when both sides
    // over-count the same duplicate — which is exactly what the pass found in
    // the first version.
    const records = readIcdDrops(four);
    const counts = icdDropCountsByReason(four);
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    expect(total).toBe(records.length);
    expect(total).toBe(new Set(records.map((d) => d.code)).size);
    expect(total).toBe(4);
  });

  it('⚠️ amber is the not-in-our-list subset ONLY — a suppression is not an amber card', () => {
    const amber = amberIcdDrops(four);
    expect(amber.map((d) => d.code)).toEqual(['A00.0']);
    expect(amber.length).toBeLessThan(readIcdDrops(four).length);
  });
});

// ---------------------------------------------------------------------------
describe('⚠️ NO MODEL-AUTHORED STRING IS STORED — the PHI posture', () => {
  it('the record type carries exactly two fields, and neither is free text', () => {
    expect([...ICD_DROP_RECORD_KEYS].sort()).toEqual(['code', 'reason'].sort());
    // `description` is the model's prose and 07a:471-473 already rules it can
    // carry patient context.
    expect(ICD_DROP_RECORD_KEYS as readonly string[]).not.toContain('description');
    expect(ICD_DROP_RECORD_KEYS as readonly string[]).not.toContain('evidence_quote');
  });

  it('a hostile record carrying prose has that prose STRIPPED by the narrower', () => {
    const d = readIcdDrops({
      codes: [],
      dropped: [
        {
          code: 'K21.0',
          reason: 'not_in_verified_allowlist',
          description: 'Mrs Patient, 71, of 4 Elm Street',
          evidence_quote: 'she reports burning after meals',
        },
      ],
    });
    expect(Object.keys(d[0]).sort()).toEqual([...ICD_DROP_RECORD_KEYS].sort());
    expect(JSON.stringify(d)).not.toMatch(/Elm Street|burning after meals/);
  });
});

// ---------------------------------------------------------------------------
describe('the narrowers are EXHAUSTIVE at runtime, not only at compile time', () => {
  it('readIcdDrops emits exactly ICD_DROP_RECORD_KEYS', () => {
    const d = readIcdDrops(blob([], [{ code: 'K21.0', reason: 'not_in_verified_allowlist' }]));
    expect(Object.keys(d[0]).sort()).toEqual([...ICD_DROP_RECORD_KEYS].sort());
  });

  // ⚠️ F8-S2 SPLIT THIS ARM IN TWO, AND THE SPLIT MAKES IT STRONGER.
  //
  // It used to assert that EVERY narrowed record carries EVERY key. Ruling
  // #154 added `reason`, which is present on `rejected` and absent on
  // `accepted` BY DESIGN — so the single arm became false for a reason that
  // was not a defect, and "make it pass" would have meant deleting the
  // exhaustiveness proof F8-S1 filed this residual to get.
  //
  // Instead both sides are asserted. The REJECTED arm keeps the original
  // guarantee in full — all four keys, so a field added to the interface and
  // forgotten in the narrower is still caught. The ACCEPTED arm adds what the
  // old one could not express: that `reason` is genuinely ABSENT, not merely
  // undefined, which is the half of #154's biconditional a stored
  // `{state:'accepted', reason:'…'}` would violate.
  it('⚠️ readIcdDecisions emits exactly ICD_DECISION_RECORD_KEYS on a REJECTED record', () => {
    const m = readIcdDecisions({
      'K21.00': {
        state: 'rejected',
        at: '2026-08-25T00:00:00.000Z',
        byUserId: 'u1',
        reason: 'not_supported_by_note',
      },
    });
    expect(Object.keys(m['K21.00']).sort()).toEqual([...ICD_DECISION_RECORD_KEYS].sort());
  });

  it('⚠️ an ACCEPTED record emits the required keys and NO `reason` key at all', () => {
    const m = readIcdDecisions({
      'K21.00': { state: 'accepted', at: '2026-08-25T00:00:00.000Z', byUserId: 'u1' },
    });
    const required = [...ICD_DECISION_RECORD_KEYS].filter((k) => k !== 'reason');
    expect(Object.keys(m['K21.00']).sort()).toEqual(required.sort());
    // `in`, not `=== undefined`: a present-but-undefined key serialises into
    // JSONB as `"reason": null` and would be a state-contradicting artefact.
    expect('reason' in m['K21.00']).toBe(false);
  });

  it('⚠️ a stray `reason` on an ACCEPTED record is STRIPPED, and the decision SURVIVES', () => {
    // The asymmetry is deliberate and is documented at the narrower: the state
    // is well formed and is a real clinical decision, so the uninterpretable
    // annotation goes and the decision stays. Deleting the record would
    // destroy a doctor's accept to punish a stray field beside it.
    const m = readIcdDecisions({
      'K21.00': {
        state: 'accepted',
        at: '2026-08-25T00:00:00.000Z',
        byUserId: 'u1',
        reason: 'not_supported_by_note',
      },
    });
    expect(m['K21.00']?.state).toBe('accepted');
    expect('reason' in m['K21.00']).toBe(false);
  });

  it('⚠️ a REJECTED record with an UNKNOWN reason is DROPPED, not repaired', () => {
    // Dropping returns the code to UNDECIDED, so it surfaces to the doctor
    // again — over-shooting to the edge, where there is a fence. Inventing a
    // reason would assert a clinical rationale nobody gave.
    const m = readIcdDecisions({
      'K21.00': {
        state: 'rejected',
        at: '2026-08-25T00:00:00.000Z',
        byUserId: 'u1',
        reason: 'because_i_said_so',
      },
    });
    expect(m['K21.00']).toBeUndefined();
  });

  it('⚠️ a field added to the stored decision and NOT to the narrower is STRIPPED', () => {
    // The residual F8-S1 filed and could not fix. The compile-time assertions in
    // `icd-decisions.ts` make forgetting the narrower a `tsc` error going
    // forward; this arm records the BEHAVIOUR so the cost stays legible — and it
    // is a DEFERRED DELETION, because the narrowed map is what
    // `applyIcdDecision` spreads back into the column.
    const stored = {
      'K21.00': {
        state: 'accepted',
        at: '2026-08-25T00:00:00.000Z',
        byUserId: 'u1',
        reasonGivenByDoctor: 'a field a later slice might add',
      },
    };
    expect(readIcdDecisions(stored)['K21.00']).not.toHaveProperty('reasonGivenByDoctor');

    const r = applyIcdDecision(
      { rawIcdCodes: blob(['K21.00', 'E11.9']), rawIcdDecisions: stored },
      { code: 'E11.9', decision: 'accepted', userId: 'u1', at: '2026-08-25T01:00:00.000Z' },
    );
    expect(r.ok && r.changed).toBe(true);
    expect(r.ok && r.decisions['K21.00']).not.toHaveProperty('reasonGivenByDoctor');
  });
});

// ---------------------------------------------------------------------------
describe('⚠️ THE CALLER IS WIRED — a capability with no caller passes every test it has', () => {
  const code = codeOnly(readFileSync(join(SRC, 'worker/layers/07a-icd-coding.ts'), 'utf8'));

  it('⚠️ L7a binds each named input to the RIGHT local — a swap here is the same defect', () => {
    // The builder's own reason binding is proven by DRIVING it, above. This is
    // the other half: the caller maps four local variables onto four named
    // fields, and swapping two of THOSE inverts the product exactly as swapping
    // the tokens would have.
    //
    // ⚠️ This is a source assertion and it is deliberately a PAIRING, not a
    // count. The arm the pass defeated counted `dropRecord(… 'token')` sites and
    // was invariant under a swap because the multiset of tokens did not change.
    // An exact `field: local` pairing is not: swapping two makes two of these
    // four expectations fail.
    expect(code).toMatch(/buildIcdDropRecords\(\{/);
    const binding: ReadonlyArray<readonly [string, string]> = [
      ['notInVerifiedAllowlist', 'rejected'],
      ['incoherentVaricose', 'droppedIncoherent'],
      ['contradictedByDenial', 'droppedDenied'],
      ['unsupportedDeficiency', 'droppedDeficiency'],
    ];
    for (const [field, local] of binding) {
      expect(code, `${field} must be fed by ${local}`).toMatch(
        new RegExp(`${field}:\\s*${local}\\.map`),
      );
    }
  });

  it('positive + negative control on the matcher itself', () => {
    expect(code).toMatch(/import \{ buildIcdDropRecords \}/);
    expect(code).not.toMatch(/notAFieldAnybodyPasses\s*:/);
  });

  it('the survivors it passes are the FINAL post-floor set, not an earlier one', () => {
    // `coherentFinal` is what lands in `codes[]`. Passing `accepted` or
    // `coherent` would leave a code that a later floor removed excluded from the
    // drop record AND absent from the note — the silent-loss direction.
    expect(code).toMatch(/survivors:\s*coherentFinal\.map/);
  });

  it('⚠️ the RETURN value is still the narrow shape — downstream is untouched', () => {
    // The pass showed a syntactic negative is escapable by mutating `filtered`
    // in place, so this asserts the SHAPE at its construction site too: nothing
    // may be added to `filtered` between its literal and the return.
    expect(code).toMatch(/const filtered:\s*typeof result\s*=\s*\{\s*codes:\s*coherentFinal\s*\}/);
    expect(code).toMatch(/return filtered;/);
    expect(code).not.toMatch(/filtered\s*\)?\.dropped\s*=/);
    expect(code).not.toMatch(/return \{\s*\.\.\.filtered/);
  });

  it('the stored blob carries `dropped`, and the retired token is gone repo-side', () => {
    expect(code).toMatch(/icdCodes:\s*\{[^}]*\.\.\.filtered[^}]*dropped/);
    expect(code).not.toMatch(/not_in_billable_set/);
  });
});
