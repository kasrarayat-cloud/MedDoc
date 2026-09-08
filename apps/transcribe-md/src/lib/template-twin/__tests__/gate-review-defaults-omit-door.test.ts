// ============================================================================
// GATE — REVIEW-DEFAULTS item 2: `omit` gets a door, and the door does not lie.
// ----------------------------------------------------------------------------
// Ruling #194 left exactly one surviving policy — `'omit'` — and no way for a
// doctor to choose it. Measured before this change: `grep -c unmentionedPolicy`
// over every `.tsx` is ZERO, against a 12-file `.ts` positive control. The
// server has accepted it the whole time (`certification-lifecycle.ts:415` parses
// the doctor's payload with `SemanticMappingSchema`, which permits `'omit'`;
// `:521` persists it). Only the interface was missing.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL, stated first:
//   · any ONE of the five requires-input clauses is
//     dropped from the shared predicate            -> the five-clause block
//   · the resolver grows a SECOND copy of that
//     predicate instead of importing it            -> the one-copy block
//   · the surface OFFERS omit where the resolver
//     would not honour it                          -> the BICONDITIONAL matrix
//   · a seventh guard is added to
//     `omitBranchUnreachable` without declaring
//     the resolver tokens it stands for            -> the completeness arm
//   · a guard names a token the resolver does
//     not actually return                          -> the token-family check
//   · `omit` starts changing the PAGE and not just
//     the prompt                                   -> the page-is-identical block
//   · an omitted field falls into NO bucket, or
//     into BOTH                                    -> the accounting block
//
// ⚠️ AND THE ARM THAT USED TO STAND WHERE THE MATRIX NOW STANDS WAS GREEN, AND
// PINNED THE BUG. It asserted `canOmitWhenUnmentioned` was "the exact negation
// of `requiresClinicianInput`" — over a table that varied only the five
// requires-input inputs. That was TRUE of the code and FALSE of the product:
// `requiresClinicianInput` is evaluated inside `missingResolution`, five guards
// further down than the offer needed to look, so the control was offered on
// `manual` fields, `verified_note_selection` fields, fields with no concept,
// unsupported fields, and fields already carrying an approved practice default.
// A doctor ticking it there pays a forced re-certification and is asked about
// the field on every visit forever.
//
// The arm was not merely blind to that — it would have RED-FLAGGED the fix. A
// green control over a table that never varies the deciding input is the
// vacuity failure wearing a control's clothes, and the replacement compares the
// predicate to the RESOLVER'S OWN BEHAVIOUR instead of to another predicate.
//
// ⚠️ AND THE FIVE-CLAUSE BLOCK EXISTS BECAUSE THE SUITE DID NOT COVER IT.
// Measured while extracting the predicate: dropping
// `mapping.blankPolicy === 'requires_input'` from it and running the FULL unit
// suite gave **434 files, 6071 tests, 0 failures** — with the mutation asserted
// present in the file at the end of the run. A clause that decides whether a
// field is put to the clinician or left silently blank was load-bearing and
// unguarded. That is not a gap this feature introduced; it is one the extraction
// exposed, and it is closed here because the extraction is what makes a single
// dropped clause a plausible edit.
//
// ⚠️ WHAT THIS FILE DOES *NOT* MEASURE, said plainly:
//   · THE RENDERED BYTES. The page-is-identical block asserts the RESOLUTION is
//     identical (status and value) and that only the reason token differs. That
//     the DOCX bytes are then identical is `gate-157b-denial-contract`'s
//     property, proved there, and is not re-proved here.
//   · WHETHER OMIT FIRES ON THE NEXT VISIT. The resolver also requires
//     `conceptUnmatched && reason === undefined && facts.length > 0` — all three
//     are properties of a PARTICULAR ENCOUNTER. This file proves the choice can
//     matter, never that it will.
//   · THE CLIENT CONTROL'S DOM. The panel arms live beside the panel, in
//     `app/settings/note-format/__tests__`. What is proved HERE is the predicate
//     the panel is required to call.
//   · ANY AUDIT ROW. Mapping edits ARE audited (93 production
//     `TEMPLATE_TWIN_MAPPING_UPDATED` rows — my first note here claimed the
//     opposite and was wrong). The row does not record WHICH policy was chosen.
//     This change adds no new audit action.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';

import {
  TemplateFieldSchema,
  TemplateTwinDetectionStatusSchema,
  templateTwinCounts,
} from '../ir';
// ⚠️ THE PROBE IS SHARED, NOT COPIED — see `resolver-probe.ts` for why two other
// files had been reading the resolver's SOURCE for want of it.
import {
  field,
  mapping,
  factFor,
  resolveOne,
  resolveOneDictated,
  resolveOneCertifying,
} from './resolver-probe';
import { scaffoldDefaultOfferable } from '../clinician-override';
import { expectedDataTypeForFieldKind } from '../field-kind-data-type';
import {
  requiresClinicianInput,
  canOmitWhenUnmentioned,
  omitBranchUnreachable,
  resolverLadderExit,
  OMIT_LADDER_CERTIFICATION_GUARD_FOLLOWS,
  OMIT_LADDER_PRE_CONCEPT,
  OMIT_GUARD_NAMES,
  OMIT_GUARD_TOKEN_PREFIXES,
  OMIT_CONTROL_LABEL,
  OMIT_CONTROL_HINT,
  OMIT_INERT_LABEL,
} from '../unmentioned-policy';
import type { EncounterFact, SemanticMapping, TemplateField } from '../ir';

// ============================================================================
// THE FIVE CLAUSES ARE EACH LOAD-BEARING — one arm per clause, so dropping ANY
// ONE of them reds EXACTLY ONE arm and names it.
// ============================================================================
/**
 * ⚠️ EVERY SPELLING THE EXTRACTOR CAN NAME — RULING #234.
 *
 * The previous form was a single regex with TWO alternatives (`field.p` and
 * `(field as X).p`) capturing only the PROPERTY. Round five demonstrated three
 * consequences, and all three were false greens:
 *
 *   · **destructuring**, **bracket access** and a **nested binding read** were
 *     invisible, so *"a guard added without its dimension reds HERE"* was false
 *     for four shapes;
 *   · the property alone is not an identity — `mapping.unknownPolicy` was
 *     constant in all rows and reported VARIED because `field.unknownPolicy`
 *     shares its name;
 *   · a helper whose parameters are not literally named `field`/`mapping` read
 *     as nothing at all.
 *
 * So this returns `"field.prop"` / `"mapping.prop"` PAIRS, and takes an alias
 * map so a helper's own parameter names resolve to the right role.
 */
type Role = 'field' | 'mapping';
const IDENT = '[A-Za-z_$][\\w$]*';

function readsIn(
  code: string,
  alias: Readonly<Record<string, Role>> = { field: 'field', mapping: 'mapping' },
): Set<string> {
  const names = Object.keys(alias);
  const out = new Set<string>();
  if (names.length === 0) return out;
  const N = names.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  const add = (obj: string, path: string) => out.add(`${alias[obj]}.${path}`);

  // 1 · dotted, with optional chaining and the cast form:
  //     field.p   field?.p   (field as X).p
  for (const m of code.matchAll(
    new RegExp(`(?:\\(\\s*(${N})\\s+as\\s+[^)]*\\)|\\b(${N})\\b)\\s*\\??\\.\\s*(${IDENT})`, 'g'),
  )) add((m[1] ?? m[2])!, m[3]!);

  // 2 · NESTED — `field.rendererBinding?.bindingType`. Recorded as the full
  //     path as well as its head, because the matrix varies the LEAF.
  for (const m of code.matchAll(
    new RegExp(`\\b(${N})\\b\\s*\\??\\.\\s*(${IDENT})\\s*\\??\\.\\s*(${IDENT})`, 'g'),
  )) add(m[1]!, `${m[2]}.${m[3]}`);

  // 3 · bracket access — `field['p']`, `mapping["p"]`.
  for (const m of code.matchAll(
    new RegExp(`\\b(${N})\\b\\s*\\??\\[\\s*['"]([^'"]+)['"]\\s*\\]`, 'g'),
  )) add(m[1]!, m[2]!);

  // 4 · destructuring — `const { a, b: c, d = e, ...rest } = field`.
  for (const m of code.matchAll(new RegExp(`\\{([^{}]*)\\}\\s*=\\s*(${N})\\b`, 'g'))) {
    for (const part of m[1]!.split(',')) {
      const key = part.split(':')[0]!.split('=')[0]!.trim();
      if (new RegExp(`^${IDENT}$`).test(key)) add(m[2]!, key);
    }
  }
  return out;
}

/**
 * ⚠️ THE READ SET, OBSERVED AT RUNTIME — RULING #251. THIS IS THE AUTHORITY.
 *
 * `readsIn()` below is a TEXT scanner and it has been defeated four times: a
 * mid-chain cast erases the read; a destructured helper parameter drops two; a
 * guard delegated to a helper outside the two hardcoded source regions is
 * invisible; and — the sharpest, found by a verifier rather than a lens — a pure
 * REFACTOR of an existing guard into an imported helper, which is this module's
 * own idiom, silently dropped `field.kind` and `mapping.expectedDataType` from
 * the watched set at 48/48 green. Those are precisely the two inputs whose
 * constancy caused the historical false green the arm exists to prevent.
 *
 * **Each fix closed a spelling and left the class open.** So the question stops
 * being asked of the SOURCE: the inputs are wrapped in Proxies and the mirror is
 * CALLED, and what it reads is recorded as it reads it. No regex, no source
 * slice, no alias resolution — and it **follows helpers by construction**,
 * imported ones included, because a helper reading `f.kind` reads it off the
 * same proxied object.
 *
 * ⚠️ ITS OWN HONEST LIMIT, STATED SO IT IS NOT THE FIFTH INSTRUMENT NOBODY
 * QUESTIONED: a tracer records reads that HAPPEN. A guard sitting behind an
 * early return is not exercised by an input that returns early, so the set must
 * be accumulated across the WHOLE matrix — which is what the arm does — and a
 * guard no matrix row ever reaches contributes nothing. That is a real blind
 * spot, and it is strictly smaller than the regex's: a guard no row reaches also
 * cannot affect the biconditional it is being checked against.
 */
/**
 * Filled by the biconditional arm as it runs — RULING #251.
 *
 * `TRACED_READS` is what the mirror ACTUALLY read, recorded by Proxy.
 * `OBSERVED_VALUES` is what the fixtures actually varied, recorded by walking
 * each row's inputs. Both are runtime facts. Neither is parsed from source, and
 * neither can be satisfied by a comment, a cast, a refactor into a helper, or a
 * dimension list nobody loops over — the four ways the regex version was beaten.
 */
const TRACED_READS = new Set<string>();
/**
 * The RESOLVER's own reads, recorded by the SAME Proxy over `resolverLadderExit`
 * — ruling #280. It sits beside `TRACED_READS` because it is the same
 * instrument on the other half of the biconditional; the arm that consumes it
 * used to derive this set with a regex over two byte ranges of a source file.
 */
const RESOLVER_READS = new Set<string>();

/** The same Proxy, wrapping whatever it is handed. One tracer, two subjects. */
function traceInto(into: Set<string>, target: object, path: string): object {
  return new Proxy(target, {
    get(t, prop, recv) {
      if (typeof prop === 'string') into.add(`${path}.${prop}`);
      const v = Reflect.get(t, prop, recv);
      return v !== null && typeof v === 'object' && !Array.isArray(v) && !(v instanceof Date)
        ? traceInto(into, v as object, `${path}.${String(prop)}`)
        : v;
    },
  });
}
const OBSERVED_VALUES = new Map<string, Set<string>>();

/** Record every (object, property) -> value this row actually presents. */
function observeValues(field: TemplateField, mapping: SemanticMapping): void {
  const walk = (obj: Record<string, unknown>, path: string, depth: number) => {
    for (const [k, v] of Object.entries(obj)) {
      const key = `${path}.${k}`;
      if (v !== null && typeof v === 'object' && !Array.isArray(v) && depth > 0) {
        walk(v as Record<string, unknown>, key, depth - 1);
        continue;
      }
      let seenSet = OBSERVED_VALUES.get(key);
      if (!seenSet) OBSERVED_VALUES.set(key, (seenSet = new Set<string>()));
      seenSet.add(JSON.stringify(v ?? null));
    }
  };
  walk(field as unknown as Record<string, unknown>, 'field', 1);
  walk(mapping as unknown as Record<string, unknown>, 'mapping', 1);
}

function tracedReads(
  field: TemplateField,
  mapping: SemanticMapping,
  into: Set<string>,
): void {
  const wrap = (target: object, path: string): object =>
    new Proxy(target, {
      get(t, prop, recv) {
        if (typeof prop === 'string') into.add(`${path}.${prop}`);
        const v = Reflect.get(t, prop, recv);
        // Nested objects are wrapped too, so `field.rendererBinding.bindingType`
        // records the LEAF — the thing the matrix actually varies.
        return v !== null && typeof v === 'object' && !Array.isArray(v) && !(v instanceof Date)
          ? wrap(v as object, `${path}.${String(prop)}`)
          : v;
      },
    });
  // The return value is discarded: this call exists for its READS.
  omitBranchUnreachable(
    wrap(field, 'field') as TemplateField,
    wrap(mapping, 'mapping') as SemanticMapping,
  );
}

/** The parameter names a module-local helper binds to `field` / `mapping`. */
function aliasesOf(signature: string): Record<string, Role> {
  const out: Record<string, Role> = {};
  const params = signature.slice(signature.indexOf('(') + 1).split(')')[0] ?? '';
  for (const part of params.split(',')) {
    const name = part.split(':')[0]!.trim();
    const type = (part.split(':')[1] ?? '').trim();
    if (!new RegExp(`^${IDENT}$`).test(name)) continue;
    if (/Field/i.test(type) || name === 'field') out[name] = 'field';
    else if (/Mapping/i.test(type) || name === 'mapping') out[name] = 'mapping';
  }
  return out;
}

describe('item 2 — every requires-input clause is guarded', () => {
  it('CONTROL — with no requires-input signal at all, the field is left blank', () => {
    const { resolution } = resolveOne();
    expect(resolution.status).toBe('not_mentioned');
    expect(requiresClinicianInput(field('1'), mapping(field('1'), 'x'))).toBe(false);
  });

  const CLAUSES: ReadonlyArray<{
    name: string;
    fieldOver: Partial<TemplateField>;
    mappingOver: Partial<SemanticMapping>;
  }> = [
    { name: 'field.required', fieldOver: { required: true }, mappingOver: {} },
    { name: 'mapping.required', fieldOver: {}, mappingOver: { required: true } },
    {
      name: "field.unknownPolicy === 'requires_input'",
      fieldOver: { unknownPolicy: 'requires_input' },
      mappingOver: {},
    },
    {
      name: "mapping.unknownPolicy === 'requires_input'",
      fieldOver: {},
      mappingOver: { unknownPolicy: 'requires_input' },
    },
    {
      // ⚠️ THIS ONE WAS UNGUARDED BY ALL 6071 TESTS. See the header.
      name: "mapping.blankPolicy === 'requires_input'",
      fieldOver: {},
      mappingOver: { blankPolicy: 'requires_input' },
    },
  ];

  for (const clause of CLAUSES) {
    it(`${clause.name} alone puts the field to the clinician`, () => {
      const f = field('1', clause.fieldOver);
      const m = mapping(f, 'ros.cardiovascular', clause.mappingOver);

      // The predicate says so...
      expect(requiresClinicianInput(f, m)).toBe(true);

      // ...and the REAL resolver acts on it. Asserting only the predicate would
      // pass against a predicate nothing calls.
      const { resolution } = resolveOne(clause.fieldOver, clause.mappingOver);
      expect(resolution.status).toBe('needs_clinician_input');
      expect(resolution.status).not.toBe('not_mentioned');
    });

    it(`${clause.name} alone WITHDRAWS the omit offer`, () => {
      const f = field('1', clause.fieldOver);
      const m = mapping(f, 'ros.cardiovascular', clause.mappingOver);
      expect(canOmitWhenUnmentioned(f, m)).toBe(false);

      // And the resolver agrees: an `omit` set on such a field is NOT honoured,
      // so offering the control there would have been a lie.
      const { resolution } = resolveOne(clause.fieldOver, {
        ...clause.mappingOver,
        unmentionedPolicy: 'omit',
      });
      expect(resolution.reasonCode).not.toBe('omitted_unsupported_default');
    });
  }
});

// ============================================================================
// THE OFFER EQUALS THE HONOURING — item 1's rule, applied to item 2.
// "A surface must never offer an act its writer would refuse."
// ============================================================================
describe('item 2 — the offer and the honouring are one predicate', () => {
  it('⚠️ NON-VACUITY CONTROL — an OFFERABLE field DOES get the omit reason', () => {
    const f = field('1');
    const m = mapping(f, 'ros.cardiovascular');
    expect(canOmitWhenUnmentioned(f, m)).toBe(true);

    const { resolution } = resolveOne({}, { unmentionedPolicy: 'omit' });
    expect(resolution.reasonCode).toBe('omitted_unsupported_default');
  });

  // ==========================================================================
  // ⚠️ THE BICONDITIONAL. This is the instrument that makes the mirror in
  // `omitBranchUnreachable` safe, and it is the arm that would have caught the
  // shipped defect.
  //
  // The arm that used to stand here asserted `canOmitWhenUnmentioned` was the
  // exact negation of `requiresClinicianInput` — and it PASSED, because its
  // matrix varied only the five requires-input inputs. It was not merely
  // blind to the bug; it PINNED it, so the correct fix would have redded it.
  // A green arm over a table that never varies the deciding input is the
  // vacuity failure wearing a control's clothes.
  //
  // So this arm does not compare the predicate to another predicate. It
  // compares it to THE RESOLVER'S OWN BEHAVIOUR, over the cross-product of
  // every input that can reach the branch — and requires BOTH directions to
  // be witnessed, so neither half can pass by being empty.
  // ==========================================================================
/**
 * ⚠️ OWNER RULING #227 — THE MATRIX'S INTENTIONAL CONSTANTS, DECLARED.
 *
 * Every property the mirror reads must be either VARIED across the
 * cross-product or named here with the reason it is held constant. The
 * derived-dimension arm reds on anything that is neither.
 *
 * This exists because the arm previously checked *mentioned in code* rather
 * than *varied*, so a property written once at a constant satisfied it —
 * measured, with a guard keyed on `field.rowPrototype` passing while the matrix
 * never varied it. Deciding which constants are deliberate is a product
 * judgement; a declaration is how a product judgement gets written down instead
 * of inferred.
 *
 * ⚠️ ADDING A LINE HERE IS A CLAIM, NOT A TEST FIX. It says: this input cannot
 * change the answer, and here is why. If you cannot write the reason in one
 * line, the honest move is to vary it.
 *
 * ⚠️ BOTH HALVES OF THE ARM FIRED ON THIS TABLE'S OWN FIRST DRAFT, which is the
 * best evidence it discriminates. It contained a second entry —
 * `unmentionedPolicy`, "the policy is pinned to 'omit'" — and the stale-
 * declaration arm rejected it: the mirror does not read that property, so the
 * exemption covered nothing and would have sat here looking load-bearing. A
 * declaration that has outlived its constant exempts nothing and hides the next
 * one.
 */
/**
 * Every property of `field` / `mapping` the mirror READS — including through a
 * TYPE CAST.
 *
 * ⚠️ THE CAST ARM EXISTS BECAUSE A PROBE OF MINE WALKED PAST THE PLAIN ONE.
 * Testing the new RED state, I injected a guard written
 * `(field as { criticality?: string }).criticality === 'high'` — and the arm
 * stayed 37/37 green, because `field.` never appears literally in that text so
 * the property was never counted as read. Not a defect in the guard; a defect
 * in the instrument watching it, and it is the SAME SHAPE as the six admin
 * doors this programme found written `(prisma.user as any).update` and
 * invisible to the obvious grep.
 *
 * Two alternatives, because a cast is how the first form is spelled when the
 * property is not on the declared type — which is exactly when a new,
 * unwatched input arrives.
 */
// ⚠️ EMPTY, AND DELIBERATELY KEPT — RULING #234.
//
// Its only entry was `rowPrototype: 'prototypes never offer …'`, and that claim
// was FALSE: measured, a prototype was offered under both binding types and
// resolved through the very branch the entry said it did not. The false
// declaration bought a 37/37 green over a planted offered-but-not-honoured lie,
// and deleting only the entry would have left the next author the same trap.
//
// ⚠️ THE MECHANISM IS NOT AT FAULT AND IS NOT WEAKENED. #227's three states —
// varied, declared, or RED — are right. What failed is that a declaration is
// only as good as the claim inside it, and this house measures claims. The
// allowlist stays so a genuinely intentional constant has somewhere to go; it
// simply must never again carry a claim nobody checked.
const INTENTIONAL_CONSTANTS: Record<string, string> = {};

/**
 * Every guard the matrix actually WITNESSED firing, filled as it runs.
 *
 * ⚠️ THE DECLARATION ARM CONSUMES THIS INSTEAD OF READING SOURCE — RULING #258.
 * Its predecessor regexed `return '(\w+)'` out of `unmentioned-policy.ts`
 * between two anchors. That is a proof about spelling: it found six guards while
 * the module had eight decisions, and the moment the ladder became a table it
 * would have found ZERO and passed its `>= 6` floor only by failing louder
 * elsewhere. A guard is witnessed here because a row reached it.
 */
const WITNESSED_GUARDS = new Set<string>();

  it('⚠️ OFFERED  ⟺  HONOURED — the predicate matches the REAL resolver, both ways', () => {
    // ════════════════════════════════════════════════════════════════════════
    // ⚠️ REDESIGNED, NOT RE-SEEDED — RULING #259.
    //
    // The seeded sample this replaces failed in FOUR ways at once, and every one
    // of them survives a change of seed:
    //
    //   1 · Its first guard killed **2,935 of 4,000 rows**. `dataTypes` was the
    //       hand-written pair `['text','number']` against `kinds =
    //       ['narrative_text','date']`, so `'date'` had NO compatible partner in
    //       the list at all and every date row died at
    //       `semantic_mapping_type_mismatch` by construction. All 1,065
    //       survivors carried `narrative_text` AND `text` — **the two inputs the
    //       matrix had just been widened to watch were constant everywhere the
    //       other seven guards live.**
    //   2 · 4,000 draws over an 82,944-row product saturates at **6.42%**,
    //       forever, however long it runs.
    //   3 · Its coverage assertion was a tautology: the first pass walked each
    //       dimension in order, so `seen[k].size === d.length` held **by
    //       construction** at any `SAMPLES >= max(|d|)`. It passes at
    //       `SAMPLES = 3`.
    //   4 · Its green was a property of the seed LITERAL. Measured: 1 of 6
    //       seeds RED on unmutated code.
    //
    // What replaces it, clause by clause:
    //
    //   · the dimensions ARE the read set the Proxy tracer records — not a list
    //     somebody maintained beside it;
    //   · `(kind, expectedDataType)` pairs come from the COMPILER'S OWN TABLE
    //     (`expectedDataTypeForFieldKind`), never a guessed type list. That is
    //     the direct cure for (1);
    //   · coverage is asserted over **GUARD BRANCHES**, not rows or dimension
    //     values. A row that exits at guard k witnesses guard k TRUE and guards
    //     1..k-1 FALSE, so stratifying by EXIT POINT is exactly branch coverage
    //     and needs no inversion of any guard's closure;
    //   · a stratum witnessed zero times **FAILS**. It does not warn;
    //   · the product is enumerated EXHAUSTIVELY when it fits a STATED budget,
    //     and sampled only when it does not — stratified, with a per-stratum
    //     floor.
    // ════════════════════════════════════════════════════════════════════════

    // ── the read set, as the tracer records it ──────────────────────────────
    const bools = [false, true];
    const policies = ['blank', 'not_documented', 'requires_input'] as const;
    const sourceTypes = ['extraction', 'manual', 'verified_note_selection'] as const;
    // ⚠️ DERIVED FROM THE ENUM, NOT LISTED — RULING #303, AND IT IS #259
    // CLAUSE 2 POINTED AT THE COLUMN THAT STILL DISOBEYED IT.
    //
    // `TemplateTwinDetectionStatusSchema` has FOUR members. This literal named
    // TWO, so `recognized` and `needs_confirmation` were absent from every row
    // of an 870,912-row matrix that describes itself as exhaustive — the same
    // shape as the hand-written dataType list that "killed 73.4% of the rows",
    // and invisible for exactly the same reason: nothing compared the literal
    // to its source. A value the compiler can emit and the matrix never varies
    // is a dimension held constant while the arm reports full coverage.
    const detections = TemplateTwinDetectionStatusSchema.options;
    // ⚠️ `null`, NOT `''`. `ir.ts:372` is `z.string().min(1).max(160).nullable()`,
    // so an empty string is REFUSED by the schema and never reaches the resolver.
    // `null` is the value the confirm surface renders as '· no concept yet'.
    const concepts = ['ros.cardiovascular', null] as const;
    const defaults = [null, 'The patient consents.'] as const;
    const bindings = ['content_control', 'table_cell'] as const;
    // ⚠️ THE SAME ENUM, ON THE MAPPING — `ir.ts:452` is the same schema as
    // `ir.ts:130`. Derived from the one source so the two columns cannot drift
    // apart, which a second literal would eventually let them do.
    const statuses = TemplateTwinDetectionStatusSchema.options;
    // POSITIVE CONTROL, in `KINDS`' shape: a derivation that yields the old
    // two-member set, or an empty one, satisfies every assertion below while
    // covering strictly less than the literal it replaced.
    expect(detections.length, 'detection statuses not derived from the enum').toBe(4);
    for (const missed of ['recognized', 'needs_confirmation'] as const) {
      expect(
        detections as readonly string[],
        `${missed} is emittable by the compiler and the matrix must vary it`,
      ).toContain(missed);
    }
    expect(statuses, 'both columns must read ONE enum').toBe(detections);
    // ⚠️ THE DIMENSION THE EIGHTH DIVERGENCE READ AND THIS MATRIX HAD NEVER
    // NAMED. `resolver/index.ts` refuses a checkbox whose `conceptScope` covers
    // several symptoms — "affirmed" is ambiguous between them — and routes it to
    // a `missingResolution` call site that cannot honour an omit. With the scope
    // held absent, no row could witness it.
    const scopes: readonly (string[] | undefined)[] = [
      undefined,
      ['ros.palpitations'],
      ['ros.palpitations', 'ros.chest_pain'],
    ];

    // ⚠️ PAIRS FROM THE COMPILER'S OWN TABLE — RULING #259, CLAUSE 2.
    //
    // Each kind is paired with the type `expectedDataTypeForFieldKind` says is
    // compatible, and with ONE deliberately incompatible partner so the first
    // guard's TRUE branch is witnessed by every kind rather than by a type list
    // that happened to contain a mismatch. The kinds are the ones the IR schema
    // ACCEPTS: `fixed_table` and `repeating_table` have a compatible type in the
    // table but are refused by `TemplateFieldSchema`, and the schema's refusal
    // is the authority on what the compiler can emit — not this file's opinion.
    // ⚠️ DERIVED FROM THE SCHEMA, NOT LISTED — ROUND EIGHT, `F2`. #259 clause 2
    // says the (kind, dataType) pairs come from the compiler's own table and
    // never from a hand-written list, "because the hand-written list is what
    // killed 73.4% of the rows". The dataTypes obeyed that; the KINDS did not.
    // This was a literal whose comment CLAIMED to be "the kinds the IR schema
    // accepts" with nothing deriving or checking it, so dropping two accepted
    // kinds would narrow the matrix silently and every arm would stay green.
    //
    // `TemplateFieldSchema` is the authority on what the compiler can emit, and
    // it states its own exclusions, so the accepted set is a property of the
    // schema rather than of this file's opinion of it.
    const KINDS = TemplateFieldSchema.shape.kind.options as readonly TemplateField['kind'][];
    // POSITIVE CONTROL: the derivation must actually produce a set, and one
    // that excludes what the schema excludes — an empty or unfiltered result
    // would satisfy every assertion below while covering nothing.
    expect(KINDS.length, 'no field kinds derived — the matrix would be empty').toBeGreaterThan(3);
    for (const excluded of ['fixed_table', 'repeating_table', 'unsupported', 'static'] as const) {
      expect(
        KINDS as readonly string[],
        `${excluded} is not emittable by the compiler and must not be in the matrix`,
      ).not.toContain(excluded);
    }
    const pairs: { kind: (typeof KINDS)[number]; dataType: SemanticMapping['expectedDataType'] }[] = [];
    for (const kind of KINDS) {
      const compatible = expectedDataTypeForFieldKind(kind);
      expect(compatible, `the compiler's table has no type for '${kind}'`).not.toBeNull();
      pairs.push({ kind, dataType: compatible! });
      // The incompatible partner is drawn from the table too — any OTHER kind's
      // type — so it cannot become stale if the vocabulary changes.
      const other = KINDS.map((k) => expectedDataTypeForFieldKind(k)).find(
        (t) => t !== null && t !== compatible,
      );
      pairs.push({ kind, dataType: other! });
    }
    expect(pairs.length).toBe(KINDS.length * 2);
    // ⚠️ NON-VACUITY OF THE PAIR TABLE ITSELF: both directions must be present,
    // or clause 2 has produced a list as blind as the one it replaced.
    expect(
      pairs.filter((p) => expectedDataTypeForFieldKind(p.kind) === p.dataType).length,
    ).toBe(KINDS.length);
    expect(
      pairs.filter((p) => expectedDataTypeForFieldKind(p.kind) !== p.dataType).length,
    ).toBe(KINDS.length);

    const DIMS: readonly (readonly unknown[])[] = [
      bools, bools, policies, policies, policies, sourceTypes, detections,
      concepts, defaults, bindings, statuses, bools, pairs, scopes,
    ];

    // ── the exact product, and the budget the RESOLVER gets ────────────────
    // ⚠️ THERE IS NO SAMPLE AND NO SEED. The product over the traced read set is
    // 870,912 rows, and classifying every one of them — building the two objects
    // and walking the guards — was MEASURED at 724 ms. So the enumeration is
    // exhaustive and failure mode (4) is gone by construction: there is no seed
    // literal left for a green to be a property of.
    //
    // ⚠️ THE BUDGET MOVED TO WHERE THE COST ACTUALLY IS. Driving the REAL
    // resolver costs ~160 µs a row (three zod parses), so 870,912 of those is
    // ~70 s. The resolver therefore sees at most `RESOLVE_CAP` rows PER STRATUM,
    // spread evenly through the enumeration rather than taken from the front —
    // a contiguous prefix correlates with the low-order dimensions, which is a
    // smaller version of the same blindness this redesign exists to end.
    const RESOLVE_CAP = 300;
    // ⚠️ THE PER-STRATUM FLOOR — #259, CLAUSE 5. The cap bounds what a LARGE
    // stratum costs; the floor is what a SMALL one is owed. A stratum smaller
    // than the floor is resolved entirely, which is how the 16-row eighth guard
    // gets checked at all. Stated separately from the cap because they answer
    // opposite questions, and the arm that preceded this one had neither.
    const MIN_PER_STRATUM = 100;
    // ⚠️ THE KNOB THE COVERAGE ASSERTION MUST BE SENSITIVE TO. `ROW_LIMIT` bounds
    // the enumeration, and the control arm below proves this arm REDS at
    // `ROW_LIMIT = 3` — the acceptance test ruling #259 sets for the arm itself,
    // because its predecessor PASSED at three samples.
    //
    // ⚠️ AND THAT SENTENCE WAS FALSE WHEN IT WAS WRITTEN — recorded here rather
    // than quietly corrected. There was no control arm below. This name appeared
    // exactly ONCE in the repository, at the read on the next line, so nothing
    // ever set it: the acceptance test was performed by hand, passed, and was
    // then guarded by a claim that it had been guarded.
    const ROW_LIMIT = Number(process.env.OMIT_MATRIX_ROW_LIMIT ?? '0') || Infinity;
    const exact = DIMS.reduce((n, d) => n * d.length, 1);
    const total = Math.min(exact, ROW_LIMIT);

    const decode = (n: number): number[] => {
      const row: number[] = [];
      let rest = n;
      for (const d of DIMS) {
        row.push(rest % d.length);
        rest = Math.floor(rest / d.length);
      }
      return row;
    };
    const build = (row: number[]) => {
      const { kind, dataType } = pairs[row[12]!]!;
      const conceptScope = scopes[row[13]!];
      const fieldOverrides = {
        required: bools[row[0]!]!,
        unknownPolicy: policies[row[2]!]!,
        detectionStatus: detections[row[6]!]!,
        rendererBinding: { ...field('1').rendererBinding, bindingType: bindings[row[9]!]! },
        rowPrototype: bools[row[11]!]!,
        kind,
      };
      const mappingOverrides = {
        required: bools[row[1]!]!,
        unknownPolicy: policies[row[3]!]!,
        blankPolicy: policies[row[4]!]!,
        sourceType: sourceTypes[row[5]!]!,
        clinicalConcept: concepts[row[7]!]!,
        practiceDefault: defaults[row[8]!]!,
        expectedDataType: dataType,
        status: statuses[row[10]!]!,
        conceptScope: conceptScope === undefined ? undefined : [...conceptScope],
        unmentionedPolicy: 'omit' as const,
      };
      const f = field('1', fieldOverrides);
      const m = mapping(f, mappingOverrides.clinicalConcept ?? 'unused', mappingOverrides);
      return { f, m, fieldOverrides, mappingOverrides };
    };

    // PASS 1 — classify every row. Cheap, exhaustive, and it is what makes the
    // coverage claim a fact about the whole product rather than about a draw.
    const strataSize = new Map<string, number>();
    // ⚠️ AND WHAT EACH STRATUM'S DIMENSIONS ACTUALLY SPAN, which is what makes
    // the sampling assertion below derivable instead of hand-listed. A guard
    // ENTAILS some of its dimensions — every row of `manual_source_not_filled`
    // has `sourceType: 'manual'`, necessarily — and a dimension constant for
    // that reason is not a sampling defect. Only a dimension that varies across
    // the whole stratum and NOT across the resolved subset is one.
    const strataSpan = new Map<string, Set<number>[]>();
    const classOf: string[] = [];
    for (let n = 0; n < total; n += 1) {
      const row = decode(n);
      const { f, m } = build(row);
      const g = omitBranchUnreachable(f, m) ?? 'REACHABLE';
      classOf.push(g);
      strataSize.set(g, (strataSize.get(g) ?? 0) + 1);
      if (!strataSpan.has(g)) strataSpan.set(g, DIMS.map(() => new Set<number>()));
      strataSpan.get(g)!.forEach((seen, k) => seen.add(row[k]!));
    }

    // PASS 2 — resolve an evenly-spread subset of each stratum.
    const stride = new Map<string, number>();
    for (const [g, n] of strataSize) stride.set(g, Math.max(1, Math.ceil(n / RESOLVE_CAP)));

    // ⚠️ SELECTED BY A MIXED HASH OF THE INDEX, NOT BY ITS RESIDUE — and the
    // first cut of this arm got it wrong in exactly the way it was written to
    // prevent. `seen % stride === 0` looks unbiased and is not: the enumeration
    // is mixed-radix, so a stratum's stride shares factors with the dimension
    // periods. MEASURED on the largest stratum: stride 1452 = 12 x 121, and 12
    // is precisely the period of the three lowest-order dimensions, so
    // `field.required`, `mapping.required` and `field.unknownPolicy` were held
    // CONSTANT across all 300 resolved rows — 217,728 rows of the product could
    // never reach the resolver at all. A mutation keyed on `field.required`
    // survived the whole arm.
    //
    // That is failure mode (1) of the seeded matrix — "the inputs the matrix was
    // widened to watch, constant everywhere the guards live" — recurring one
    // layer down, in the redesign that diagnosed it.
    //
    // A multiplicative hash alone does NOT fix it (low bits stay correlated;
    // measured: two dimensions still collapsed). This is a murmur3 finalizer,
    // and it takes every stratum to ZERO collapsed dimensions.
    const mix = (n: number): number => {
      let h = n >>> 0;
      h ^= h >>> 16;
      h = Math.imul(h, 2246822507);
      h ^= h >>> 13;
      h = Math.imul(h, 3266489909);
      return (h ^ (h >>> 16)) >>> 0;
    };
    const rows: number[][] = [];
    const takenPerStratum = new Map<string, number>();
    for (let n = 0; n < total; n += 1) {
      const g = classOf[n]!;
      if (mix(n) % stride.get(g)! !== 0) continue;
      const taken = takenPerStratum.get(g) ?? 0;
      if (taken >= RESOLVE_CAP) continue;
      takenPerStratum.set(g, taken + 1);
      rows.push(decode(n));
    }

    // ── strata: the guard branches ─────────────────────────────────────────
    // ⚠️ THE EXIT POINT **IS** THE BRANCH, AND THAT IS WHY NO GUARD HAS TO BE
    // INVERTED. `omitBranchUnreachable` walks the guards in order and returns
    // the first that fires, so a row exiting at guard k witnesses k TRUE and
    // every earlier guard FALSE. Cover every exit — including `null`, the row
    // where they are ALL false — and every guard has been seen both ways.
    const CONSERVATIVE_GUARDS = new Set([
      'fixed_grid_cell_deferred',
      'row_prototype_not_offerable',
      // ⚠️ THE EIGHTH, AND IT IS THE SAME SHAPE AS THE FIXED GRID. A multi-scope
      // checkbox on a visit where nothing in scope was dictated DOES reach the
      // omit branch and IS honoured; the moment anything in scope is dictated,
      // the resolver refuses. Withheld for the fixed grid's reason.
      'multi_concept_checkbox_deferred',
    ]);
    const resolvedPerStratum = new Map<string, number>();
    let offeredAndHonoured = 0;
    let refusedAndNotHonoured = 0;
    let conservativeWithholds = 0;
    const disagreements: string[] = [];
    const tokenMismatches: string[] = [];
    // ⚠️ #303 — THE THIRD VERDICT, AND IT IS PROVEN PER ROW RATHER THAN LISTED.
    //
    // Deriving `detections`/`statuses` from the enum admitted `recognized` and
    // `needs_confirmation` for the first time, and they produce rows where the
    // offer withholds on `approved_practice_default` while `resolveOne` honours
    // the omit. That is NOT a mirror divergence: `practiceDefaultResolution`
    // requires `mapping.status === 'certified'` and the offer's guard does not,
    // a split the resolver states at the line and declines to share — "at
    // confirm time the mapping is being certified, so sharing it would offer a
    // control that stops working the moment the doctor certifies."
    //
    // ⚠️ THE ROWS ARE AN INSTRUMENT ARTIFACT, AND THE INSTRUMENT IS NAMED:
    // every probe here passes `allowUncertifiedForSyntheticTest: true`, which
    // SKIPS the certification guard. In production that guard fires first and
    // the row never reaches the omit branch at all.
    //
    // ⚠️ SO IT IS DEMONSTRATED, NOT ASSUMED — #303 FORBIDS A SILENT ALLOWLIST.
    // The question asked is the RESOLVER'S OWN, through the real exported
    // ladder in the production universe, and a row is set aside only when that
    // ladder actually refuses it. Nothing here reads the `status` column: if the
    // certification guard is ever reordered or weakened, these rows stop being
    // refused and come straight back as disagreements.
    const certificationUnreachable: string[] = [];
    const certificationTokenUnreachable: string[] = [];
    const refusedByCertification = (f: TemplateField, m: SemanticMapping) =>
      resolverLadderExit(f, m, {
        allowUncertified: false,
        certifiedFieldIds: new Set<string>(),
      })?.reasonCode === 'field_or_mapping_not_certified';

    for (const row of rows) {
      const { f, m, fieldOverrides, mappingOverrides } = build(row);
      const { kind, dataType } = pairs[row[12]!]!;
      const offered = canOmitWhenUnmentioned(f, m);
      tracedReads(f, m, TRACED_READS);
      // ⚠️ #280 — THE RESOLVER'S LADDER, TRACED OVER THE SAME PRODUCT. Both
      // certification universes, because the clause's position is behaviour and
      // its reads differ between them.
      for (const allowUncertified of [true, false]) {
        resolverLadderExit(
          traceInto(RESOLVER_READS, f, 'field') as typeof f,
          traceInto(RESOLVER_READS, m, 'mapping') as typeof m,
          { allowUncertified, certifiedFieldIds: new Set<string>() },
        );
      }
      observeValues(f, m);

      const stated = omitBranchUnreachable(f, m);
      const stratum = stated ?? 'REACHABLE';
      WITNESSED_GUARDS.add(stratum);
      resolvedPerStratum.set(stratum, (resolvedPerStratum.get(stratum) ?? 0) + 1);

      // Drive the ACTUAL resolver on the one encounter shape where
      // `conceptUnmatched && reason === undefined && facts.length > 0` all hold,
      // with the policy set to `omit`.
      const { resolution } = resolveOne(fieldOverrides, mappingOverrides);
      const honoured = resolution.reasonCode === 'omitted_unsupported_default';

      const shape =
        `fReq=${fieldOverrides.required} mReq=${mappingOverrides.required} ` +
        `fUnknown=${fieldOverrides.unknownPolicy} mBlank=${mappingOverrides.blankPolicy} ` +
        `mUnknown=${mappingOverrides.unknownPolicy} src=${mappingOverrides.sourceType} ` +
        `det=${fieldOverrides.detectionStatus} concept=${mappingOverrides.clinicalConcept ?? 'NONE'} ` +
        `default=${mappingOverrides.practiceDefault === null ? 'null' : 'set'} type=${dataType} ` +
        `bind=${fieldOverrides.rendererBinding.bindingType} status=${mappingOverrides.status} ` +
        `kind=${kind} proto=${fieldOverrides.rowPrototype} ` +
        `scope=${mappingOverrides.conceptScope?.length ?? 0}`;

      // ⚠️ THE TWO DIRECTIONS ARE NOT SYMMETRIC, AND CONFLATING THEM WOULD FORCE
      // THE WRONG FIX.
      //
      // `offered && !honoured` is THE LIE — the control promises something the
      // resolver will not do. Never acceptable.
      //
      // `!offered && honoured` is CONSERVATIVE — withheld where it would have
      // worked. That is a real cost, taken deliberately, and every such case must
      // be attributable to a NAMED guard or it is an accident wearing a policy.
      if (offered && !honoured) {
        disagreements.push(
          `${shape} -> OFFERED BUT NOT HONOURED (resolver said ${resolution.reasonCode})`,
        );
      } else if (!offered && honoured) {
        if (stated !== null && CONSERVATIVE_GUARDS.has(stated)) {
          conservativeWithholds += 1;
        } else if (refusedByCertification(f, m)) {
          // Production never reaches the omit branch for this row — proven just
          // now, by the resolver's own ladder, with certification ON.
          certificationUnreachable.push(shape);
        } else {
          disagreements.push(
            `${shape} -> withheld but HONOURABLE, and guard '${stated}' is not a ` +
              `declared conservative narrowing`,
          );
        }
      }
      if (offered && honoured) offeredAndHonoured += 1;
      if (!offered && !honoured) refusedAndNotHonoured += 1;

      // ⚠️ AND THE STATED REASON MUST BE THE RESOLVER'S OWN. A withhold on the
      // RIGHT field for the WRONG grounds is one refactor away from withholding
      // the wrong field — so the token is compared, not just the boolean.
      if (stated !== null && !honoured) {
        const prefixes = OMIT_GUARD_TOKEN_PREFIXES[stated];
        if (!prefixes) {
          tokenMismatches.push(`${shape} -> guard '${stated}' declares NO tokens`);
        } else if (!prefixes.some((prefix) => resolution.reasonCode.startsWith(prefix))) {
          if (refusedByCertification(f, m)) {
            certificationTokenUnreachable.push(shape);
          } else {
            tokenMismatches.push(
              `${shape} -> guard '${stated}' declares [${prefixes.join(', ')}], ` +
                `resolver returned '${resolution.reasonCode}'`,
            );
          }
        }
      }
    }

    expect(disagreements).toEqual([]);
    expect(tokenMismatches).toEqual([]);


    // ══════════════════════════════════════════════════════════════════════
    // ⚠️ BRANCH COVERAGE, AND A ZERO-WITNESSED STRATUM **FAILS** — #259.
    //
    // Every guard the module can return must be witnessed firing, and
    // `REACHABLE` — the row where they are all false — must be witnessed too, or
    // the biconditional held over a table that never reached the branch it
    // exists to check. The floor is per-stratum: one lucky row is not coverage.
    // ══════════════════════════════════════════════════════════════════════
    const expectedStrata = [...OMIT_GUARD_NAMES, 'REACHABLE'];
    const empty = expectedStrata.filter((g) => (strataSize.get(g) ?? 0) === 0);
    expect(
      empty,
      `these guard branches were witnessed ZERO times over ${total} rows (exact ` +
        `product ${exact}). A branch nobody reached is a branch this arm did not ` +
        `check — and it FAILS rather than warning, because the previous form of ` +
        `this assertion was satisfiable by construction at three samples.`,
    ).toEqual([]);

    // ⚠️ PLACED **AFTER** THE ZERO-WITNESS CHECK, AND THAT ORDER IS LOAD-BEARING.
    // #259's acceptance control drives this arm at `ROW_LIMIT = 3` and asserts
    // the ZERO-WITNESS message comes back. Asserted earlier, the check below
    // throws first at three rows and the control reds against its own arm —
    // which is how it was found: a correct assertion in the wrong position
    // silently changed what a different control was measuring.
    // ══════════════════════════════════════════════════════════════════════
    // ⚠️ #303 — THE ADJUDICATION IS CONTROLLED IN BOTH DIRECTIONS, BECAUSE A
    // CATEGORY THAT CANNOT SAY "NO" IS AN ALLOWLIST WEARING A PREDICATE'S NAME.
    // ══════════════════════════════════════════════════════════════════════
    //
    // (1) IT MUST STILL SAY "YES" TO SOMETHING. If the enum derivation is
    //     reverted, or the two new members stop reaching this branch, the
    //     category is dead code that would go on excusing rows nobody produces.
    //     It fails rather than warns, for the reason #259 gives about strata.
    expect(
      certificationUnreachable.length + certificationTokenUnreachable.length,
      'the certification-unreachable category adjudicated NOTHING. Either the ' +
        'status dimensions stopped being derived from the enum, or the rows it ' +
        'explains are gone — in which case DELETE it rather than leave an ' +
        'unexercised excuse standing.',
    ).toBeGreaterThan(0);
    //
    // (2) AND IT MUST BE ABLE TO SAY "NO", WHICH IS THE CONTROL THAT MATTERS.
    //     The obvious probe for this — `resolveOneCertifying` — refuses a row
    //     whose mapping is `certified` when the FIELD is not, so a check written
    //     against status alone would have been CONSTANT TRUE and would have
    //     excused every disagreement this arm exists to find, silently. Measured
    //     over the 4x4 of (detectionStatus, status): exactly ONE combination
    //     passes the guard, and it is the one where both columns certify.
    {
      const certifiedField = field('1', { detectionStatus: 'certified' });
      const bothCertified = mapping(certifiedField, 'ros.cardiovascular', {
        status: 'certified',
        unmentionedPolicy: 'omit',
      });
      expect(
        refusedByCertification(certifiedField, bothCertified),
        'refusedByCertification is CONSTANT TRUE — it would set aside every ' +
          'disagreement, including a real one. A fully certified field and ' +
          'mapping must pass the certification guard.',
      ).toBe(false);
      const uncertifiedMapping = mapping(certifiedField, 'ros.cardiovascular', {
        status: 'recognized',
        unmentionedPolicy: 'omit',
      });
      expect(
        refusedByCertification(certifiedField, uncertifiedMapping),
        'refusedByCertification is CONSTANT FALSE — it would adjudicate nothing ' +
          'and the category above could never be reached.',
      ).toBe(true);
    }
    // ⚠️ AND EVERY ROW OF A SMALL STRATUM IS RESOLVED, NOT JUST COUNTED. The
    // rarest exit here is `multi_concept_checkbox_deferred` at **16 rows in
    // 870,912** — 1 in 54,432, which is why no uniform sample of any practical
    // size could reach it and why the previous arm never witnessed the eighth
    // guard at all. Classification is exhaustive; the cap only bounds how many
    // of a LARGE stratum reach the resolver.
    // ══════════════════════════════════════════════════════════════════════
    // ⚠️ AND THE RESOLVED SUBSET MUST NOT HOLD A DIMENSION CONSTANT THAT THE
    // STRATUM ITSELF VARIES. This is the assertion the stride defect needed and
    // did not have: coverage of a BRANCH is not coverage of the branch's INPUTS,
    // and a selector correlated with the enumeration can satisfy every count
    // above while resolving one corner of every stratum.
    //
    // Derived, never listed: a dimension a guard ENTAILS is constant across the
    // whole stratum too, so comparing the two spans distinguishes "necessarily
    // constant" from "constant because of how we sampled" without anybody
    // deciding which is which.
    // ══════════════════════════════════════════════════════════════════════
    const resolvedSpan = new Map<string, Set<number>[]>();
    for (const row of rows) {
      const { f, m } = build(row);
      const g = omitBranchUnreachable(f, m) ?? 'REACHABLE';
      if (!resolvedSpan.has(g)) resolvedSpan.set(g, DIMS.map(() => new Set<number>()));
      resolvedSpan.get(g)!.forEach((seen, k) => seen.add(row[k]!));
    }
    const collapsed: string[] = [];
    for (const g of expectedStrata) {
      const whole = strataSpan.get(g);
      const sample = resolvedSpan.get(g);
      if (!whole || !sample) continue;
      whole.forEach((span, k) => {
        if (span.size > 1 && (sample[k]?.size ?? 0) <= 1) {
          collapsed.push(`${g}[dim ${k}]`);
        }
      });
    }
    expect(
      collapsed,
      `the resolver-visible sample holds these dimensions CONSTANT inside a ` +
        `stratum that varies them — the selector is correlated with the ` +
        `enumeration, so a mutation keyed on one of them can never be witnessed`,
    ).toEqual([]);

    for (const g of expectedStrata) {
      const n = strataSize.get(g) ?? 0;
      const resolved = resolvedPerStratum.get(g) ?? 0;
      expect(
        resolved,
        `stratum '${g}' holds ${n} rows and only ${resolved} of them reached the ` +
          `resolver — below the per-stratum floor of ${MIN_PER_STRATUM}`,
      ).toBeGreaterThanOrEqual(Math.min(n, MIN_PER_STRATUM));
      expect(resolved, `stratum '${g}' exceeded the resolver budget`).toBeLessThanOrEqual(
        RESOLVE_CAP,
      );
    }

    // ⚠️ NON-VACUITY, BOTH DIRECTIONS. A biconditional over a table that is
    // all-refused passes trivially and proves nothing.
    expect(offeredAndHonoured).toBeGreaterThan(0);
    expect(refusedAndNotHonoured).toBeGreaterThan(0);
    // ⚠️ AND THE CONSERVATIVE SET IS NOT A LOOPHOLE. If it stops witnessing
    // anything, the exemption is dead weight and should be deleted rather than
    // left standing as a permission nobody uses.
    expect(
      conservativeWithholds,
      'no conservative withhold witnessed — CONSERVATIVE_GUARDS is dead weight',
    ).toBeGreaterThan(0);
  },
  // ⚠️ AN EXPLICIT TIMEOUT — RULING #251. This arm ran under vitest's 5000 ms
  // DEFAULT at 40-60% of it, and round six observed it TIME OUT on an unmutated
  // tree. A default nobody chose is not a budget; it is the number that happened
  // to be there.
  20_000);

  // ==========================================================================
  // The named short-circuits get one arm each, so a dropped clause reds a test
  // that says WHICH clause — the matrix above says only "they disagree".
  // ==========================================================================
  it.each([
    ['a MANUAL source', {}, { sourceType: 'manual' as const }, 'manual_source_not_filled'],
    [
      'a VERIFIED NOTE SELECTION',
      {},
      { sourceType: 'verified_note_selection' as const },
      'awaiting_note_selection',
    ],
    ['an UNSUPPORTED field', { detectionStatus: 'unsupported' as const }, {}, 'field_or_mapping_unsupported'],
    ['an UNSUPPORTED mapping', {}, { status: 'unsupported' as const }, 'field_or_mapping_unsupported'],
    ['NO clinical concept', {}, { clinicalConcept: null }, 'clinical_concept_unmapped'],
    [
      'an approved PRACTICE DEFAULT',
      {},
      { practiceDefault: 'The patient consents.' },
      'approved_practice_default',
    ],
  ])('⚠️ %s WITHDRAWS the offer, and names the resolver\'s own reason', (_name, fo, mo, token) => {
    const f = field('1', fo as Partial<TemplateField>);
    const m = mapping(f, 'ros.cardiovascular', mo as Partial<SemanticMapping>);

    expect(canOmitWhenUnmentioned(f, m)).toBe(false);
    expect(omitBranchUnreachable(f, m)).toBe(token);
    expect(OMIT_GUARD_TOKEN_PREFIXES[token]).toBeDefined();

    // …and the resolver genuinely does NOT honour an `omit` set on it.
    const { resolution } = resolveOne(fo as Partial<TemplateField>, {
      ...(mo as Partial<SemanticMapping>),
      unmentionedPolicy: 'omit',
    });
    expect(resolution.reasonCode).not.toBe('omitted_unsupported_default');
  });

  it('⚠️ THE MATRIX VARIES EVERY INPUT THE MIRROR READS — the class, not the instance', () => {
    // ══════════════════════════════════════════════════════════════════════
    // ⚠️ REBUILT ON RUNTIME FACTS — RULING #251. NOTHING HERE READS SOURCE.
    //
    // This arm existed because the same failure happened three times: a guard
    // was invisible to the biconditional because the matrix held its input
    // constant. It was implemented as a REGEX over two hardcoded source regions,
    // and it was then defeated four more times — by a mid-chain cast, by a
    // destructured helper parameter, by a guard delegated outside those regions,
    // and (the sharpest, found by a verifier rather than a lens) by a pure
    // REFACTOR of an existing guard into an imported helper, which silently
    // dropped `field.kind` and `mapping.expectedDataType` at 48/48 green.
    //
    // Each fix closed a spelling and left the class open. So both halves are now
    // observed while the matrix runs:
    //   · what the mirror READ  — by Proxy, which follows helpers by
    //     construction because a helper reads off the same proxied object;
    //   · what the fixtures VARIED — by walking each row's actual values.
    //
    // A read the fixtures never varied is invisible to the biconditional, and
    // that is the finding, whatever spelling the guard used to make it.
    // ══════════════════════════════════════════════════════════════════════
    expect(
      TRACED_READS.size,
      'the tracer recorded nothing — the biconditional arm did not run, so this ' +
        'arm is measuring an empty set and would pass over anything',
    ).toBeGreaterThanOrEqual(8);

    // ⚠️ AN INTERMEDIATE OBJECT COUNTS AS VARIED WHEN A LEAF UNDER IT DOES.
    // `field.rendererBinding` is read only as a PATH to `…​.bindingType`, and the
    // binding object itself is never the thing a guard branches on. Requiring the
    // container to vary would force a declaration for a dimension the matrix
    // genuinely does exercise — a false entry on the allowlist, which is the one
    // thing #234 established the allowlist must never carry.
    const isVaried = (read: string) => {
      if ((OBSERVED_VALUES.get(read)?.size ?? 0) > 1) return true;
      for (const [key, vals] of OBSERVED_VALUES) {
        if (key.startsWith(`${read}.`) && vals.size > 1) return true;
      }
      return false;
    };

    const undeclared = [...TRACED_READS].filter(
      (r) => !isVaried(r) && !(r in INTENTIONAL_CONSTANTS),
    );
    expect(
      undeclared,
      `the mirror READ [${undeclared.join(', ')}] and the matrix presented only ` +
        `ONE value for ${undeclared.length === 1 ? 'it' : 'them'} — so a guard ` +
        `keyed on ${undeclared.length === 1 ? 'that input' : 'those inputs'} is ` +
        `invisible to the biconditional. Vary it, or declare it in ` +
        `INTENTIONAL_CONSTANTS with the reason. Ruling #227: an undeclared ` +
        `constant is an oversight wearing an intentional one's clothes.`,
    ).toEqual([]);

    // ⚠️ AND THE ALLOWLIST IS NOT A DUMPING GROUND — it may not name an input the
    // mirror never reads, or one the matrix already varies.
    const stale = Object.keys(INTENTIONAL_CONSTANTS).filter(
      (k) => !TRACED_READS.has(k) || isVaried(k),
    );
    expect(
      stale,
      `INTENTIONAL_CONSTANTS declares [${stale.join(', ')}] which the mirror does ` +
        `not read, or which the matrix now varies. A declaration that has ` +
        `outlived its constant exempts nothing and hides the next one.`,
    ).toEqual([]);
  });

  it("⚠️ THE **RESOLVER** SIDE'S OWN READS ARE TRACED — the regex is gone (#280)", () => {
    // ⚠️ THIS ARM USED TO READ SOURCE, AND #280 DELETED THAT RATHER THAN
    // IMPROVING IT. It derived the resolver's read set with a member-expression
    // REGEX over two `indexOf`-anchored byte ranges of `resolver/index.ts`.
    // Ruling #251 retires text scanning as a proof of behaviour, and this was a
    // survivor of that class living beside the arm that cured the OTHER side
    // with a Proxy.
    //
    // ⚠️ THE MEASUREMENT THAT CONDEMNED IT. On the shipped file, 4 reads fell
    // inside the anchored regions and EIGHT MORE sat in the same file outside
    // them — `practiceDefaultResolution` is called from inside a region and
    // lives wholly outside both. A paired control settled it: the same guard
    // written INLINE reddened the arm, and one function call away — a pure
    // refactor into an imported helper, this module's own idiom — it passed
    // 50/50 here and 892/892 across the suite with a live
    // offered-but-not-honoured divergence.
    //
    // ⚠️ A BETTER REGEX WOULD NOT HAVE HELPED, which is why the ruling says
    // DELETE. The next refactor defeats the next regex the same way.
    //
    // ⚠️ WHAT MADE THE PROXY POSSIBLE. The old comment here said "a Proxy cannot
    // do this job", and it was right about the code as it then stood:
    // `resolveTemplateFields` zod-parses its inputs and `parse` returns a NEW
    // object, so a Proxy on what the caller passes records ZOD touching every
    // key. The answer was not a cleverer tracer but a smaller subject —
    // `resolverLadderExit` is the resolver's ladder lifted to a pure function of
    // `(field, mapping, cert)`, called by the resolver and wrappable here, on
    // the far side of the parse.
    // Recorded by the matrix arm over the SAME product the biconditional uses,
    // exactly as `TRACED_READS` is for the mirror — so this is what the resolver
    // touches across every row, not on one hand-picked input.
    const reads = RESOLVER_READS;

    // ⚠️ NON-VACUITY, AND IT IS HIGHER THAN THE REGEX'S FLOOR WAS. The old arm
    // accepted 3 reads against an actual 4 — one refactor of margin. A Proxy
    // over the real ladder sees every guard's inputs, so the floor can be the
    // number of dimensions the guards genuinely key on.
    expect(
      reads.size,
      `the tracer recorded ${reads.size} reads — the ladder was not driven`,
    ).toBeGreaterThanOrEqual(6);

    const RESOLVER_CONSTANTS: Record<string, string> = {
      // Identity, not a decision — it selects nothing and gates nothing. Read by
      // the certification clause to consult the caller's certified-field set.
      'field.fieldId': 'the field identity, echoed into every resolution',
    };
    const isVariedRead = (read: string) => {
      if ((OBSERVED_VALUES.get(read)?.size ?? 0) > 1) return true;
      for (const [key, vals] of OBSERVED_VALUES) {
        if (key.startsWith(`${read}.`) && vals.size > 1) return true;
      }
      return false;
    };
    const unwatched = [...reads].filter(
      (r) => !isVariedRead(r) && !(r in RESOLVER_CONSTANTS),
    );
    expect(
      unwatched,
      `the RESOLVER reads [${unwatched.join(', ')}] on the path this arm compares, ` +
        `and the matrix presents only one value for ${unwatched.length === 1 ? 'it' : 'them'}. ` +
        `A guard keyed on one of those is invisible to the biconditional — which ` +
        `is how a planted offered-but-not-honoured lie survived 891 tests. Vary ` +
        `it, or declare it in RESOLVER_CONSTANTS with the reason it cannot vary.`,
    ).toEqual([]);

    // ⚠️ AND THE DECLARATION IS NOT A DUMPING GROUND: it may not name a property
    // the resolver does not read, or one the matrix already varies.
    const stale = Object.keys(RESOLVER_CONSTANTS).filter(
      (k) => !reads.has(k) || isVariedRead(k),
    );
    expect(
      stale,
      `RESOLVER_CONSTANTS declares [${stale.join(', ')}] which the resolver does ` +
        `not read, or which the matrix now varies.`,
    ).toEqual([]);
  });

  it('⚠️ EVERY guard the module can return DECLARES its tokens — no silent skips', () => {
    // ⚠️ THIS ARM USED TO READ SOURCE, AND RULING #258 SHOWED WHY THAT WAS
    // ALWAYS WRONG. It regexed `return '([a-z_]+)'` out of this file's text
    // between two anchors and asserted `returned.length >= 6`. Two failures were
    // latent in that the whole time: it could only ever find guards written as
    // bare string returns (the module had eight decisions and it saw six), and
    // when the ladder became a TABLE it found zero — the `>= 6` floor is what
    // reds, and a floor is not a description.
    //
    // Three real sets are compared instead, all of them derived:
    //   · `OMIT_GUARD_NAMES` — built from the table and the returned constants;
    //   · `OMIT_GUARD_TOKEN_PREFIXES` — the declaration;
    //   · `WITNESSED_GUARDS` — what the matrix actually reached.
    const declared = new Set(Object.keys(OMIT_GUARD_TOKEN_PREFIXES));
    const names = new Set(OMIT_GUARD_NAMES);

    expect(OMIT_GUARD_NAMES.length, 'the guard set collapsed — the table is empty')
      .toBeGreaterThanOrEqual(8);
    expect([...names].length, 'a guard name is duplicated').toBe(OMIT_GUARD_NAMES.length);

    // 1 · every guard the code can return declares its tokens…
    expect(
      OMIT_GUARD_NAMES.filter((g) => !declared.has(g)),
      'these guards can be returned and declare no resolver tokens',
    ).toEqual([]);
    // 2 · …and nothing is declared that the code cannot return.
    expect(
      [...declared].filter((g) => !names.has(g)),
      'these tokens are declared for a guard that no longer exists',
    ).toEqual([]);
    // 3 · ⚠️ AND EVERY ONE OF THEM WAS ACTUALLY REACHED. Sets 1 and 2 agree
    // trivially if both are wrong in the same way; only the matrix can say a
    // guard is real. This is the same check the strata floor makes, asserted
    // here as an identity so a guard that stops being reachable reds under its
    // own name rather than as a count.
    expect(
      OMIT_GUARD_NAMES.filter((g) => !WITNESSED_GUARDS.has(g)),
      'the matrix never reached these guards — they are declared, and dead',
    ).toEqual([]);
  });

  /**
   * ⚠️ ONE BUDGET, USED TWICE — the `gate-lens-sandbox` lesson, which cost a CI
   * red when an inner 120s sat under vitest's default 5s and the inner number
   * could never be reached. Measured on this box: the child completes in 1.93s.
   */
  const ROW_LIMIT_CONTROL_BUDGET_MS = 180_000;

  it(
    '⚠️ CONTROL — the coverage arms RED at ROW_LIMIT = 3 (#259\'s acceptance test for the ARM)',
    () => {
      // ⚠️ THIS ARM EXISTS BECAUSE ITS COMMENT ALREADY CLAIMED IT DID.
      // `ROW_LIMIT`'s declaration said "the control arm below proves this arm
      // REDS at ROW_LIMIT = 3" and NO SUCH ARM EXISTED. `OMIT_MATRIX_ROW_LIMIT`
      // appeared exactly ONCE in the whole repository — the read itself — so
      // nothing set it, and the behaviour ruling #259 makes the acceptance test
      // for this entire redesign was verified once by hand and then guarded by a
      // sentence. That is the #260 failure exactly, and one turn worse than the
      // version it names: a comment that reaches the right answer by a false
      // route will be trusted by the next reader FOR THE ROUTE — and a reader
      // who greps for this control and finds nothing cannot tell whether it was
      // deleted or never written.
      //
      // ⚠️ RECURSION GUARD. The child runs this same FILE, so this arm must not
      // spawn a grandchild. When the knob is set we are the child; skip.
      if (process.env.OMIT_MATRIX_ROW_LIMIT) return;

      let out = '';
      let code = 0;
      try {
        out = execFileSync(
          'npx',
          ['vitest', 'run', __filename, '--no-color'],
          {
            encoding: 'utf8',
            stdio: 'pipe',
            cwd: join(__dirname, '..', '..', '..', '..'),
            timeout: ROW_LIMIT_CONTROL_BUDGET_MS,
            env: { ...process.env, OMIT_MATRIX_ROW_LIMIT: '3', CI: '1' },
          },
        );
      } catch (e) {
        const err = e as { status?: number; stdout?: string; stderr?: string };
        code = err.status ?? -1;
        out = `${err.stdout ?? ''}${err.stderr ?? ''}`;
      }

      // ⚠️ POSITIVE CONTROL FIRST, AND IT IS THE WHOLE DIFFICULTY OF THIS ARM.
      // A non-zero exit is ALSO what a child that died at import produces, or a
      // missing `npx`, or a syntax error — and every one of those would satisfy
      // "the arm red at three rows" while proving the opposite of it. So the
      // child must be shown to have RUN the matrix before its failure means
      // anything.
      expect(out, `the child never ran the suite:\n${out.slice(0, 4000)}`).toContain(
        'gate-review-defaults-omit-door.test.ts',
      );
      expect(out, `the child ran no tests:\n${out.slice(0, 4000)}`).toMatch(/Tests\s+\d+\s+failed/);

      expect(code, `the arm PASSED at three rows — it is a tautology:\n${out.slice(0, 4000)}`)
        .not.toBe(0);

      // ⚠️ AND IT NAMES **WHICH** ARM FIRED, for `ARM 2`'s reason in the lens
      // gate: two refusals that read identically in a report and mean different
      // things prove nothing. Ruling #259's clause 4 is that a stratum witnessed
      // ZERO times FAILS rather than warns, so that is the sentence asserted —
      // not a bare red.
      expect(out, 'the zero-witness stratum check did not fire').toContain(
        'witnessed ZERO times over 3 rows',
      );
      expect(out, 'the dead-guard coverage check did not fire').toContain(
        'the matrix never reached these guards',
      );
    },
    ROW_LIMIT_CONTROL_BUDGET_MS,
  );

  it("⚠️ EVERY LADDER ROW'S `status` IS PINNED — the column nothing watched", () => {
    // ⚠️ ROUND EIGHT, `FG-2`. `resolver/index.ts:473` passes `guard.status`
    // straight into `makeResolution`, so this column decides what the DOCTOR is
    // shown — and no arm read it. Measured: flipping `manual_source_not_filled`
    // from `not_mentioned` to `needs_clinician_input` survived **51 of 51 here
    // and 893 of 893 across the whole template-twin suite**.
    //
    // ⚠️ AND THE FLIP IS NOT COSMETIC. The guard's own comment records what that
    // status did the last time it was wrong: "four such fields refused the
    // native document on every visit, forever, and the export fell back to the
    // styled path". `needs_clinician_input` is BLOCKING at visit time;
    // `not_mentioned` is a blank the certificate attests to. One enum apart.
    //
    // ⚠️ THE EXPECTED VALUES ARE LITERALS, AND THE FIRST VERSION OF THIS ARM WAS
    // VACUOUS FOR WANT OF THEM. It drove the real resolver and asserted
    // `resolution.status === guard.status` — but the resolver READS
    // `guard.status`, so both sides moved together and BOTH flips passed 52/52.
    // A control that re-derives its expectation from the thing under test agrees
    // with it by construction. The pin has to come from outside the table:
    // these five are the CLINICAL meaning, and changing one means arguing that
    // the doctor should be blocked differently.
    const EXPECTED: Record<string, { status: string; why: string }> = {
      // A type disagreement is a configuration error a human must resolve.
      semantic_mapping_type_mismatch: { status: 'needs_clinician_input', why: 'a mis-typed mapping is a real error' },
      // Likewise unsupported — the twin cannot answer it at all.
      field_or_mapping_unsupported: { status: 'needs_clinician_input', why: 'nothing can fill an unsupported field' },
      // ⚠️ NOT BLOCKING, AND THIS IS THE ONE WITH A BODY COUNT. A MANUAL field
      // carries no concept BY CONSTRUCTION and the certificate attests it
      // renders blank; blocking on it refused the native document forever.
      manual_source_not_filled: { status: 'not_mentioned', why: 'a designed blank is not an error' },
      // Same shape: the picks bridge answers it, so the baseline is honestly blank.
      awaiting_note_selection: { status: 'not_mentioned', why: 'another component answers it' },
      // No concept means nobody decided what this field means yet.
      clinical_concept_unmapped: { status: 'needs_clinician_input', why: 'an unmapped field is unconfigured' },
    };
    const INPUTS: Record<string, [Partial<TemplateField>, Partial<SemanticMapping>]> = {
      semantic_mapping_type_mismatch: [{ kind: 'checkbox' }, { expectedDataType: 'number' }],
      field_or_mapping_unsupported: [{}, { status: 'unsupported' }],
      manual_source_not_filled: [{}, { sourceType: 'manual' }],
      awaiting_note_selection: [{}, { sourceType: 'verified_note_selection' }],
      clinical_concept_unmapped: [{}, { clinicalConcept: null }],
    };

    // POSITIVE CONTROL ON THE MAPS THEMSELVES: a row added to the ladder later
    // is silently unwatched otherwise — the exact shape this arm exists to end.
    const rows = OMIT_LADDER_PRE_CONCEPT.map((g) => g.guard);
    expect(rows.filter((g) => !(g in INPUTS)), 'a ladder row has no input here').toEqual([]);
    expect(rows.filter((g) => !(g in EXPECTED)), 'a ladder row has no pinned status').toEqual([]);

    for (const guard of OMIT_LADDER_PRE_CONCEPT) {
      const [f, m] = INPUTS[guard.guard]!;
      const { resolution } = resolveOne(f, m);
      // The row was actually REACHED, or every assertion below is about some
      // other guard and passes for the wrong reason.
      expect(
        resolution.reasonCode,
        `the input for ${guard.guard} exits at a different guard`,
      ).toBe(guard.reasonCode);
      // 1 · the TABLE still declares the pinned value...
      expect(
        guard.status,
        `${guard.guard} changed status — ${EXPECTED[guard.guard]!.why}`,
      ).toBe(EXPECTED[guard.guard]!.status);
      // 2 · ...and the RESOLVER actually produced it. Both, because the table
      // could be right while the resolver stopped reading it.
      expect(
        resolution.status,
        `the resolver did not honour ${guard.guard}'s declared status`,
      ).toBe(EXPECTED[guard.guard]!.status);
    }
  });

  it('⚠️ `conceptScope` IS AN UNBOUNDED DIMENSION — three values are exhaustive ONLY because the code reads its LENGTH', () => {
    // ⚠️ ROUND EIGHT, `TRACER-2`. The matrix varies `conceptScope` over three
    // hand-picked values — absent, one concept, two concepts — and calls the
    // dimension "varied". But an array is UNBOUNDED: no finite sample is
    // exhaustive over it, so a guard keyed on its CONTENTS (a particular
    // concept, a third element) would be invisible to the biconditional and to
    // the resolver-reads arm alike.
    //
    // ⚠️ WIDENING THE SAMPLE WOULD CLOSE THE INSTANCE AND NOT THE CLASS — the
    // shape #259 was written to end. Three values are exhaustive if and only if
    // the code reads nothing but the LENGTH, so THAT is what this arm pins.
    //
    // BEHAVIOURAL HALF FIRST: scopes of the SAME LENGTH and completely
    // different contents must be indistinguishable to both sides.
    //
    // ⚠️ AT EVERY SAMPLED LENGTH, NOT JUST THE LONGEST — AND MY FIRST VERSION
    // COMPARED ONLY LENGTH 2, WHERE IT PROVED NOTHING. The live guard is
    // `length > 1`, so at length 2 it fires for both contents and the pair is
    // trivially equal. A planted read that made ONE concept trip the guard at
    // LENGTH 1 passed 54 of 54. The pairs are per-length now, so a content read
    // is visible at the length where the length test does not already answer.
    const PAIRS: ReadonlyArray<readonly [string[], string[]]> = [
      [['ros.palpitations'], ['gi.nausea']],
      [['ros.palpitations', 'ros.chest_pain'], ['gi.nausea', 'derm.pruritus']],
      [
        ['ros.palpitations', 'ros.chest_pain', 'ros.dyspnoea'],
        ['gi.nausea', 'derm.pruritus', 'msk.arthralgia'],
      ],
    ];
    for (const kind of ['checkbox', 'narrative_text'] as const) {
      // ⚠️ THE PAIR MUST REACH THE GUARD, AND MY FIRST TWO VERSIONS DID NOT.
      // With the probe's default `expectedDataType`, a `checkbox` trips ladder
      // row 1 (`semantic_mapping_type_mismatch`) and the deferral guard that
      // reads `conceptScope` is never consulted — so the pairs compared two
      // identical refusals and a planted content read passed 54 of 54, twice.
      // The compatible type comes from the compiler's own table, as #259
      // clause 2 requires of everything else in this file.
      const dataType = expectedDataTypeForFieldKind(kind) ?? undefined;
      for (const [A, B] of PAIRS) {
        const a = resolveOne({ kind }, { conceptScope: A, expectedDataType: dataType });
        const b = resolveOne({ kind }, { conceptScope: B, expectedDataType: dataType });
        // REACHABILITY CONTROL: neither side may exit at the type guard, or the
        // comparison below is between two answers that have nothing to do with
        // `conceptScope`.
        expect(
          a.resolution.reasonCode,
          `${kind}: the pair exits at the type guard and never reaches the scope read`,
        ).not.toBe('semantic_mapping_type_mismatch');
        expect(
          b.resolution.reasonCode,
          `${kind}: the resolver distinguished two scopes of equal length (${A.length}) — ` +
            'the matrix samples contents and cannot cover them',
        ).toBe(a.resolution.reasonCode);
        expect(
          canOmitWhenUnmentioned(b.field, b.mapping),
          `${kind}: the OFFER distinguished two scopes of equal length (${A.length})`,
        ).toBe(canOmitWhenUnmentioned(a.field, a.mapping));
      }
    }

    // STRUCTURAL HALF: every production read of `conceptScope` on the compared
    // path is a LENGTH read. This one is deliberately a source scan and it is
    // NOT a proof of behaviour — #251 retires those — it is a proof about the
    // MATRIX's coverage: it says the enumeration above is exhaustive by
    // construction rather than by luck, and it reds the day somebody adds a
    // content-sensitive read, which is exactly when the matrix must widen.
    const policy = readFileSync(join(__dirname, '..', 'unmentioned-policy.ts'), 'utf8');
    const code = policy
      .split('\n')
      .filter((l) => !l.trimStart().startsWith('*') && !l.trimStart().startsWith('//'))
      .join('\n');
    const reads = [...code.matchAll(/conceptScope[^\n]*/g)].map((m) => m[0]);
    // POSITIVE CONTROL: the read this arm is about must actually be found, or
    // an empty result would satisfy every assertion below.
    expect(reads.length, 'no conceptScope read found — this arm is vacuous').toBeGreaterThan(0);
    for (const r of reads) {
      expect(
        /conceptScope\?\.length|conceptScope'|conceptScope\b\s*$|conceptScope:/.test(r),
        `a conceptScope read that is not a length read: "${r.trim()}" — the ` +
          'matrix samples three values and cannot cover an unbounded dimension ' +
          'whose CONTENTS are read',
      ).toBe(true);
    }
  });

  it('⚠️ THE CERTIFICATION ANCHOR NAMES **WHICH** ROW — position, not membership', () => {
    // ⚠️ ROUND EIGHT, `FG-3`. `unmentioned-policy.ts` asserts at module scope
    // that `OMIT_LADDER_CERTIFICATION_GUARD_FOLLOWS` names A ROW of the ladder.
    // It never asserts WHICH — and the resolver runs its certification check
    // AFTER the row of that name, so the constant is a POSITION.
    //
    // Repoint it from the first row to the last and the module check still
    // passes: every earlier guard now returns before certification is consulted,
    // so an UNCERTIFIED mapping that also trips one of them resolves as that
    // guard's benign outcome instead of `field_or_mapping_not_certified`. For
    // `manual_source_not_filled` that is `not_mentioned` — a blank the
    // certificate attests to — on a mapping nobody ever certified.
    //
    // ⚠️ MEMBERSHIP AND POSITION ARE DIFFERENT CLAIMS, and only one of them was
    // being checked.
    expect(OMIT_LADDER_CERTIFICATION_GUARD_FOLLOWS).toBe('semantic_mapping_type_mismatch');
    expect(
      OMIT_LADDER_PRE_CONCEPT.findIndex(
        (g) => g.guard === OMIT_LADDER_CERTIFICATION_GUARD_FOLLOWS,
      ),
      'the certification check no longer runs after the FIRST ladder row',
    ).toBe(0);

    // ⚠️ AND THE BEHAVIOURAL HALF, because the two literals above are a text
    // claim and #251 retires those as proofs of behaviour. An uncertified
    // mapping that ALSO trips a later guard must still be refused for being
    // uncertified — that is what "the check runs first" MEANS.
    // ⚠️ UNCERTIFIED IS SET EXPLICITLY, AND MY FIRST ATTEMPT DID NOT — the
    // probe's defaults are `status: 'certified'` and
    // `detectionStatus: 'certified'`, so the "uncertified" case was certified
    // and the arm measured the manual row. The arm said so, which is the only
    // reason it was caught. `needs_confirmation` rather than `unsupported`,
    // because `unsupported` trips ladder row 2 and would answer before either
    // thing this arm is about.
    const { resolution } = resolveOneCertifying(
      { detectionStatus: 'needs_confirmation' },
      { sourceType: 'manual' },
    );
    expect(
      resolution.reasonCode,
      'an UNCERTIFIED manual mapping resolved as a designed blank — the ' +
        'certification check was consulted after the row that answered first',
    ).toBe('field_or_mapping_not_certified');
    expect(resolution.status).toBe('needs_clinician_input');

    // POSITIVE CONTROL: the same mapping CERTIFIED resolves as the manual blank,
    // so the arm above is about certification and not about `manual` per se.
    const certified = resolveOneCertifying({}, { sourceType: 'manual' });
    expect(
      certified.resolution.reasonCode,
      'the control never reaches the manual row, so the arm above proves nothing',
    ).toBe('manual_source_not_filled');
  });

  it('⚠️ THE OFFER DELEGATES — it holds no opinion the resolver does not — #258', () => {
    // ⚠️ THE IDENTITY CHECK THAT REPLACES A MIRROR. Ruling #258 ended the class
    // by making `resolver/index.ts` WALK this module's table rather than carry
    // its own copy of it, so the arm's job is no longer to hunt for divergence —
    // there is nothing left to diverge. It is to assert the delegation is real.
    const src = readFileSync(join(__dirname, '..', 'resolver', 'index.ts'), 'utf-8');

    // 1 · the resolver imports the shared decisions, by name…
    //
    // ⚠️ THE LIST CHANGED WITH #280 AND THE INVARIANT GOT STRONGER, NOT WEAKER.
    // It used to name `OMIT_LADDER_PRE_CONCEPT` and
    // `OMIT_LADDER_CERTIFICATION_GUARD_FOLLOWS`, because the resolver WALKED the
    // table itself — two walks of one table, which satisfied #258's letter while
    // leaving a second loop to drift. It now calls `resolverLadderExit`, the
    // walk itself, so the table and its anchor are consumed one module over and
    // the resolver cannot re-order them.
    // ⚠️ `requiresClinicianInput` IS NO LONGER IN THIS LIST, AND ITS REMOVAL IS
    // THE FINDING. This arm asserted the resolver CONTAINED that name — and the
    // refutation pass measured the name appearing exactly once, in the import
    // list, with ZERO call sites. `missingResolution` called
    // `ir.ts::fieldDemandsInput`, a byte-identical second statement of the same
    // five disjuncts. The gate was green on a MENTION while the invariant it
    // names was carried by a symbol nothing called.
    //
    // Containment is not use. The delegation is asserted below by the CALL
    // CHAIN, and the one-body property by `gate-288`'s own arms.
    for (const symbol of ['resolverLadderExit', 'omitDeferralGuard', 'practiceDefaultPreempts']) {
      expect(src, `the resolver stopped importing '${symbol}'`).toContain(symbol);
    }

    // …and the input predicate is REACHED, not merely named: the resolver calls
    // `fieldDemandsInput`, which delegates to the single body in
    // `unmentioned-policy.ts`. Asserting the call, not the import, is what makes
    // a dead symbol impossible to mistake for a live one.
    const code = src
      .split('\n')
      .filter((l) => !l.trimStart().startsWith('//') && !l.trimStart().startsWith('*'))
      .join('\n');
    expect(
      code,
      'the resolver no longer CALLS the shared input predicate — a dead import ' +
        'would satisfy any containment check',
    ).toMatch(/fieldDemandsInput\(/);
    // …and no longer carries its own copy of the walk. A `for` over the table
    // here would be the second implementation this ruling exists to forbid.
    expect(
      src,
      'the resolver walks the ladder itself again — that is the mirror returning',
    ).not.toMatch(/for \(const guard of OMIT_LADDER_PRE_CONCEPT\)/);

    // 2 · …and the inline ladder does not come back. Matching the SPELLING is
    // deliberate: a second copy is only dangerous if it is a copy.
    expect(src).not.toMatch(/if \(!isMappingTypeCompatible\(field, mapping\)\) \{/);
    expect(src).not.toMatch(/if \(mapping\.sourceType === 'manual'\) \{/);
    expect(src).not.toMatch(/if \(mapping\.sourceType === 'verified_note_selection'\) \{/);
    // ⚠️ COMMENTS STRIPPED — #275/#272 landed a comment in the resolver that
    // QUOTES this disjunction while explaining why the predicate moved to
    // `ir.ts`. A raw-source regex reports that prose as a restatement.
    expect(
      src.split('\n').filter((l) => !l.trimStart().startsWith('//') && !l.trimStart().startsWith('*')).join('\n'),
    ).not.toMatch(/field\.required\s*\|\|\s*\n?\s*mapping\.required/);

    // 3 · ⚠️ AND ONE BEHAVIOURAL CONTROL PER KNOWN GUARD, because (1) and (2)
    // are both statements about text. Delegating to the wrong function, or to a
    // stub that returns null, satisfies every import assertion above and reds
    // here. Each row drives the REAL resolver and names the token it must emit.
    const CONTROLS: [string, Partial<TemplateField>, Partial<SemanticMapping>, string][] = [
      ['type mismatch', { kind: 'date' }, { expectedDataType: 'text' }, 'semantic_mapping_type_mismatch'],
      ['unsupported field', { detectionStatus: 'unsupported' }, {}, 'field_or_mapping_unsupported'],
      ['unsupported mapping', {}, { status: 'unsupported' }, 'field_or_mapping_unsupported'],
      ['manual source', {}, { sourceType: 'manual' }, 'manual_source_not_filled'],
      ['note selection', {}, { sourceType: 'verified_note_selection' }, 'awaiting_note_selection'],
      ['no concept', {}, { clinicalConcept: null }, 'clinical_concept_unmapped'],
      ['a practice default', {}, { practiceDefault: 'The patient consents.' }, 'approved_practice_default'],
      ['requires input', { required: true }, {}, 'required_fact_not_mentioned'],
      // ⚠️ THE NINTH ROW, AND ITS ABSENCE WAS A REAL GAP — found by a round-eight
      // lens. This table claims to enumerate the ladder, and every guard had a
      // behavioural row EXCEPT the certification guard, whose coverage lived in
      // `resolver.test.ts` instead. A table that says "one control per known
      // guard" and skips one is a claim about itself that is false.
      //
      // It needs the production flag, so it does not use `resolveOne`.
      ['UNCERTIFIED', { detectionStatus: 'recognized' as const }, { status: 'recognized' as const }, 'field_or_mapping_not_certified'],
    ];
    for (const [name, fo, mo, token] of CONTROLS) {
      // ⚠️ THE CERTIFICATION ROW NEEDS THE PRODUCTION FLAG. Every other row runs
      // under `allowUncertifiedForSyntheticTest`, which SKIPS the very guard that
      // row exists to witness — so it is driven certified-for-real instead.
      const { resolution } =
        token === 'field_or_mapping_not_certified'
          ? resolveOneCertifying(fo, { ...mo, unmentionedPolicy: 'omit' })
          : resolveOne(fo, { ...mo, unmentionedPolicy: 'omit' });
      expect(
        resolution.reasonCode.startsWith(token),
        `${name}: the resolver returned '${resolution.reasonCode}', not '${token}' — ` +
          `the delegation is nominal`,
      ).toBe(true);
    }
    // ⚠️ AND THE CONTROLS ARE NOT ALL THE SAME ANSWER. Rows that agree on one
    // token would pass a stub; the set must discriminate.
    expect(new Set(CONTROLS.map((c) => c[3])).size).toBeGreaterThanOrEqual(7);

    // ⚠️ THE DEFERRALS NEED THE OTHER ENCOUNTER, AND THE FIRST DRAFT OF THIS ARM
    // GOT IT WRONG. Under `resolveOne` — whose fact carries a DIFFERENT concept —
    // a multi-scope checkbox and a fixed-grid cell both route to the omit branch
    // and ARE honoured, so a control asserting that passes against a stubbed
    // `omitDeferralGuard`. The deferral is only reachable with facts in hand.
    const DEFERRALS: [string, Partial<TemplateField>, Partial<SemanticMapping>][] = [
      [
        'a multi-scope checkbox',
        { kind: 'checkbox' },
        {
          expectedDataType: 'boolean' as const,
          // ⚠️ A **NAMED** ROS CONCEPT, AND THE FIRST TWO DRAFTS OF THIS ROW WERE
          // WRONG IN TWO DIFFERENT WAYS. The scope must contain the dictated
          // concept or the fact does not match at all — but `ros.cardiovascular`
          // is an UNNAMED ROS concept (`isUnnamedRosConcept` -> true), and
          // `conceptMatches` refuses those against ANY scoped mapping outright
          // (#179(1): a system-level finding cannot answer a clause that names
          // symptoms). So a scoped control built on the probe's default concept
          // can never reach the deferral, and passes because the row fell through
          // to the omit branch — the exact false green this arm exists to catch.
          clinicalConcept: 'ros.cardiovascular.palpitations',
          conceptScope: ['ros.cardiovascular.palpitations', 'ros.cardiovascular.chest_pain'],
        },
      ],
      [
        'a fixed-grid cell',
        { rendererBinding: { ...field('1').rendererBinding, bindingType: 'table_cell' } },
        {},
      ],
    ];
    for (const [name, fo, mo] of DEFERRALS) {
      const { resolution } = resolveOneDictated(fo, { ...mo, unmentionedPolicy: 'omit' });
      expect(
        resolution.status,
        `${name}: the resolver answered it from raw facts — the deferral is gone`,
      ).toBe('not_mentioned');
      expect(resolution.sourceFactIds).toEqual([]);
      expect(resolution.reasonCode).toBe('fact_not_mentioned');
    }
    // ⚠️ AND THE DEFERRAL IS NOT UNIVERSAL. A guard that defers EVERYTHING would
    // satisfy the two rows above; the ordinary field must still resolve.
    const ordinary = resolveOneDictated({}, { unmentionedPolicy: 'omit' });
    expect(
      ordinary.resolution.sourceFactIds,
      'every field deferred — `omitDeferralGuard` is returning a guard for all input',
    ).not.toEqual([]);
  });

  it('⚠️ THERE IS EXACTLY ONE COPY — the resolver IMPORTS the predicate', () => {
    const src = readFileSync(join(__dirname, '..', 'resolver', 'index.ts'), 'utf-8');
    expect(src).toContain("from '../unmentioned-policy'");
    // ⚠️ THE SYMBOL MOVED, THE INVARIANT DID NOT — #275 lifted the five
    // disjuncts into `ir.ts` as `fieldDemandsInput` so the validator and the
    // resolver read ONE definition. This arm follows the predicate rather than
    // its old name.
    expect(src).toContain('fieldDemandsInput(field, mapping)');
    // The inline chain that used to live here must not come back. Matching the
    // SPELLING is deliberate: a second copy is only dangerous if it is a copy.
    // ⚠️ COMMENTS STRIPPED — #275/#272 landed a comment in the resolver that
    // QUOTES this disjunction while explaining why the predicate moved to
    // `ir.ts`. A raw-source regex reports that prose as a restatement.
    expect(
      src.split('\n').filter((l) => !l.trimStart().startsWith('//') && !l.trimStart().startsWith('*')).join('\n'),
    ).not.toMatch(/field\.required\s*\|\|\s*\n?\s*mapping\.required/);
  });

  // ══════════════════════════════════════════════════════════════════════════
  // RULING #234 — THE PROPERTY THE FALSE DECLARATION WAS REACHING FOR.
  //
  // #227's allowlist asserted "prototypes never offer" and nobody measured it.
  // The cure is not a better sentence: it is this arm plus the varied
  // dimension. #192 says a prototype must not clone its text into every row;
  // that bound the KEEP and it binds the OFFER, because a judgement recorded
  // against a prototype is recorded against every row stamped from it —
  // including rows that do not exist yet and the doctor has never seen.
  // ══════════════════════════════════════════════════════════════════════════
  it.each([['content_control'], ['table_cell']] as const)(
    '⚠️ a repeating-section PROTOTYPE is never offered — %s binding',
    (bindingType) => {
      const f = field('1', {
        rowPrototype: true,
        rendererBinding: { ...field('1').rendererBinding, bindingType },
      });
      const m = mapping(f, 'ros.cardiovascular');

      expect(canOmitWhenUnmentioned(f, m)).toBe(false);
      expect(omitBranchUnreachable(f, m)).toBe('row_prototype_not_offerable');
      expect(OMIT_GUARD_TOKEN_PREFIXES['row_prototype_not_offerable']).toBeDefined();
    },
  );

  it('⚠️ …and the withhold is CONSERVATIVE, stated as one — the resolver WOULD have honoured it', () => {
    // The non-vacuity half. If a prototype were refused by the resolver anyway,
    // this guard would be free and the arm above would prove nothing about the
    // cost being accepted. It is not free: measured, the omit IS honoured.
    const { resolution } = resolveOne(
      { rowPrototype: true },
      { unmentionedPolicy: 'omit' },
    );
    expect(resolution.reasonCode).toBe('omitted_unsupported_default');
  });

  it('⚠️ the non-prototype grid cell still routes to its OWN guard, not the new one', () => {
    // The guard above returns first for every prototype, so the `table_cell`
    // ladder below it must still be reachable — otherwise this change silently
    // swallowed `fixed_grid_cell_deferred`.
    const f = field('1', {
      rowPrototype: false,
      rendererBinding: { ...field('1').rendererBinding, bindingType: 'table_cell' },
    });
    expect(omitBranchUnreachable(f, mapping(f, 'ros.cardiovascular')))
      .toBe('fixed_grid_cell_deferred');
  });
});

// ============================================================================
// RULING #234 — THE EXTRACTOR ITSELF IS TESTED, because the arm that uses it is
// only as good as what it can SEE. Round five demonstrated four blind spots and
// each one made "a guard added without its dimension reds HERE" false.
// ============================================================================
describe('readsIn — every spelling the extractor can name', () => {
  it('the dotted form, with optional chaining and the cast', () => {
    expect(readsIn('field.required')).toContain('field.required');
    expect(readsIn('mapping?.sourceType')).toContain('mapping.sourceType');
    expect(readsIn('(field as { x: 1 }).criticality')).toContain('field.criticality');
  });

  it('⚠️ DESTRUCTURING — invisible before, and it is how a helper usually reads', () => {
    expect(readsIn('const { required, kind } = field;')).toContain('field.kind');
    expect(readsIn('const { sourceType: s } = mapping;')).toContain('mapping.sourceType');
    expect(readsIn('const { practiceDefault = null } = mapping;'))
      .toContain('mapping.practiceDefault');
  });

  it('⚠️ BRACKET ACCESS — invisible before', () => {
    expect(readsIn("field['rowPrototype']")).toContain('field.rowPrototype');
    expect(readsIn('mapping["blankPolicy"]')).toContain('mapping.blankPolicy');
  });

  it('⚠️ THE NESTED BINDING READ — the leaf is the dimension, not the head', () => {
    const r = readsIn('field.rendererBinding?.bindingType === "table_cell"');
    expect(r).toContain('field.rendererBinding');
    expect(r).toContain('field.rendererBinding.bindingType');
  });

  it('⚠️ THE PAIR IS THE IDENTITY — the same property on two objects is two reads', () => {
    const r = readsIn('field.unknownPolicy === mapping.unknownPolicy');
    expect(r).toContain('field.unknownPolicy');
    expect(r).toContain('mapping.unknownPolicy');
    expect(r.size).toBe(2);
  });

  it('⚠️ A MODULE-LOCAL HELPER RESOLVES THROUGH ITS OWN PARAMETER NAMES', () => {
    const sig = 'function g(f: Pick<TemplateField, "kind">, m: SemanticMapping)';
    const alias = aliasesOf(sig);
    expect(alias).toEqual({ f: 'field', m: 'mapping' });
    expect(readsIn('f.kind || m.sourceType', alias))
      .toEqual(new Set(['field.kind', 'mapping.sourceType']));
  });

  it('does NOT invent reads from unrelated identifiers', () => {
    expect(readsIn('shielding.required || remapping.kind')).toEqual(new Set());
  });
});

// ============================================================================
// THE PAGE IS IDENTICAL — which is the claim the doctor-facing copy makes, so
// it is the claim that has to be pinned.
// ============================================================================
describe('item 2 — omit changes the PROMPT, never the PAGE', () => {
  it('⚠️ status and value are IDENTICAL to a null policy — only the reason moves', () => {
    const nullPolicy = resolveOne().resolution;
    const omitted = resolveOne({}, { unmentionedPolicy: 'omit' }).resolution;

    expect(omitted.status).toBe(nullPolicy.status);
    expect(omitted.value).toBe(nullPolicy.value);
    expect(omitted.value).toBeNull();
    expect(omitted.sourceFactIds).toEqual(nullPolicy.sourceFactIds);

    // The ONE difference, and it is a label rather than content.
    expect(nullPolicy.reasonCode).not.toBe('omitted_unsupported_default');
    expect(omitted.reasonCode).toBe('omitted_unsupported_default');
  });

  it('⚠️ THE COPY SAYS SO — it governs the prompt and disclaims the document', () => {
    // The board filing names this control "omit this line when not dictated",
    // which would tell a doctor the line is REMOVED. It is not. If somebody
    // re-adopts that phrasing, this arm is what stops it.
    expect(OMIT_CONTROL_LABEL.toLowerCase()).not.toContain('omit this line');
    expect(OMIT_CONTROL_HINT.toLowerCase()).toContain('still clears');
    expect(OMIT_CONTROL_HINT.toLowerCase()).toContain('blank');
  });
});

// ============================================================================
// THE RULED-MUTATION SCRIPT MUST CARRY EVERY POLICY THE WRITER PERSISTS.
// ============================================================================
describe('item 2 — a payload that omits a policy ERASES it', () => {
  it('⚠️ every `*Policy` the writer persists is listed by the confirm script', () => {
    const writer = readFileSync(join(__dirname, '..', 'certification-lifecycle.ts'), 'utf-8');
    const script = readFileSync(
      join(__dirname, '..', '..', '..', '..', 'scripts', 'confirm-live-template-mappings.ts'),
      'utf-8',
    );

    // Derived from the WRITER, not typed out here — a hand-written list is the
    // second copy that goes stale the day a fourth policy is added.
    const persisted = [...writer.matchAll(/(\w+Policy): mapping\./g)].map((m) => m[1]!);
    const unique = [...new Set(persisted)];

    // Non-vacuity: an empty or one-element set would satisfy the loop below
    // while checking nothing.
    expect(unique.length).toBeGreaterThanOrEqual(3);
    expect(unique).toContain('unmentionedPolicy');

    // ⚠️ THE WRITER COERCES `?? null`, SO SILENCE IS A WRITE. A payload that
    // does not mention a policy does not leave it alone — it nulls it. And
    // `as unknown as SemanticMapping` in that script makes the omission
    // invisible to `tsc`, which is why this arm reads the SOURCE.
    // ⚠️ SCOPED TO EACH BUILDER, BECAUSE A WHOLE-FILE `toContain` IS BLIND —
    // AND ITS BLINDNESS HID A REAL DEFECT. The script has TWO projections of a
    // mapping: the PAYLOAD it sends, and the `expectedSha` it computes to prove
    // it read the current state. The first pass patched only the payload, and
    // this arm still passed, because one occurrence anywhere in the file
    // satisfies it. The consequence was a script that refuses with CONFLICT —
    // naming a concurrent editor that does not exist — on exactly the
    // population the field was carried for.
    //
    // So each builder is located and asserted SEPARATELY, and the split itself
    // is asserted non-empty: a slice that silently came back empty would make
    // every assertion below it vacuous, which is the failure this whole arm is
    // about.
    const shaAt = script.indexOf('templateTwinMappingsSha256(');
    expect(shaAt, 'the expectedSha builder was not located').toBeGreaterThan(0);
    const payloadBuilder = script.slice(0, shaAt);
    const shaBuilder = script.slice(shaAt);
    expect(payloadBuilder.length).toBeGreaterThan(500);
    expect(shaBuilder.length).toBeGreaterThan(500);

    for (const policy of unique) {
      expect(payloadBuilder, `${policy} missing from the PAYLOAD builder`).toContain(
        `${policy}: m.${policy}`,
      );
      expect(shaBuilder, `${policy} missing from the expectedSha builder`).toContain(
        `${policy}: m.${policy}`,
      );
    }
  });
});

// ============================================================================
// ACCOUNTING — nothing may fall into no bucket, or into both.
// ============================================================================
describe('item 2 — the omitted field is counted exactly once', () => {
  it('an omit is in `omitted` and NOT in `notMentioned`; a null policy is the reverse', () => {
    const omitRun = resolveOne({}, { unmentionedPolicy: 'omit' });
    const plainRun = resolveOne();
    const omitted = templateTwinCounts(omitRun.resolutions, [omitRun.field]);
    const plain = templateTwinCounts(plainRun.resolutions, [plainRun.field]);

    // ⚠️ ASSERTED PRESENT, NOT COALESCED. `omitted` is optional on the counts
    // type, so `?? 0` here would turn "the bucket does not exist" into a
    // passing zero — the precise shape of the `default_kept` accident this arm
    // is named after.
    expect(omitted.omitted).toBeDefined();
    expect(plain.omitted).toBeDefined();

    expect(omitted.omitted).toBe(1);
    expect(omitted.notMentioned).toBe(0);

    expect(plain.omitted).toBe(0);
    expect(plain.notMentioned).toBe(1);

    // ⚠️ AND THE TOTAL IS CONSERVED. `default_kept` once fell into NO bucket and
    // one unrelated dictated sentence collapsed a form's blank count 11 -> 0.
    expect(omitted.omitted! + omitted.notMentioned).toBe(plain.omitted! + plain.notMentioned);
  });
});

// ============================================================================
// THE PROMPT THE CONTROL ACTUALLY GOVERNS — "Your blanks".
// ----------------------------------------------------------------------------
// ⚠️ THIS BLOCK EXISTS BECAUSE THE CONTROL'S LABEL WAS FALSE AND EVERY OTHER
// ARM WAS GREEN. `omit` moves the field out of `notMentioned` and into
// `omitted`, which the counts arm proves — but the "Your blanks" panel does not
// read the counts. It reads `scaffoldDefaultOfferable`, which tests
// `value === null`, and an `omit` resolution is `not_mentioned` with a null
// value. So the field kept its row under the heading "Nothing was dictated for
// these", and a doctor who ticked "do not ask me about this" was asked again on
// the very next visit — the exact sentence the module header warns about,
// shipped.
//
// The counts and the panel are two different questions, and only one of them
// was being asked.
// ============================================================================
describe('item 2 — an omitted field is not put back in front of the doctor', () => {
  // ⚠️ THE DECIDING INPUT IS THE RESOLUTION'S `reasonCode`, AND THE PREVIOUS
  // VERSION OF THIS BLOCK HELD IT CONSTANT. Every arm below used one shared
  // `blankNow = { status: 'not_mentioned', value: null }`, and BOTH universes
  // this feature must tell apart project onto exactly that shape:
  //
  //   HONOURED : { status:'not_mentioned', value:null, reasonCode:'omitted_unsupported_default' }
  //   REFUSED  : { status:'not_mentioned', value:null, reasonCode:'temporality_not_approved' }
  //
  // With `reasonCode` dropped they are byte-identical, so an arm asserting
  // `=== false` was satisfied by both and could never witness an
  // over-withdrawal. That is this file's own catalogued failure — a control
  // that holds constant the one input deciding the answer — and it PINNED the
  // bug: the correct fix turns the old green arm red.
  const base = mapping(field('1'), 'ros.cardiovascular') as Record<string, unknown>;
  const omitted = { status: 'not_mentioned', value: null, reasonCode: 'omitted_unsupported_default' };
  const refusedVisit = { status: 'not_mentioned', value: null, reasonCode: 'temporality_not_approved' };
  const noFacts = { status: 'not_mentioned', value: null, reasonCode: 'fact_not_mentioned' };

  it('⚠️ the offer is WITHDRAWN when the resolver ACTUALLY honoured the omit', () => {
    expect(
      scaffoldDefaultOfferable({ field: field('1'), mapping: base, current: omitted }),
    ).toBe(false);
  });

  it('⚠️ THE ARM THAT WOULD HAVE CAUGHT THE REGRESSION — a visit the omit did NOT fire on keeps the remedy', () => {
    // The doctor ticked "expected blank"; on THIS visit they dictated the
    // field's own concept at a temporality the mapping does not approve, so the
    // resolver returned `temporality_not_approved`, the field stayed in
    // `notMentioned`, and the surface says "1 still blank". Withdrawing the
    // remedy here leaves them strictly worse off than not ticking at all.
    //
    // The withdrawal used to be decided by `canOmitWhenUnmentioned`, a CONFIRM-
    // time property of the mapping — true for this field on EVERY visit. So it
    // withdrew here too. Measured over 7 visit shapes: 5 false rejections.
    const f = field('1');
    expect(
      scaffoldDefaultOfferable({ field: f, mapping: base, current: refusedVisit }),
      'a visit where the omit did not fire must keep "Insert my default"',
    ).toBe(true);
    expect(
      scaffoldDefaultOfferable({ field: f, mapping: base, current: noFacts }),
      'a visit that extracted no facts at all must keep it too',
    ).toBe(true);
  });

  it('⚠️ NON-VACUITY — the SAME field and SAME mapping differ ONLY by reasonCode', () => {
    // The two inputs below are identical except for the one property that
    // decides the answer, and they must give OPPOSITE answers. An arm that
    // varies nothing is satisfied by a predicate that always returns the same
    // thing, which is a different bug wearing this arm's green.
    const f = field('1');
    const withdrawn = scaffoldDefaultOfferable({ field: f, mapping: base, current: omitted });
    const kept = scaffoldDefaultOfferable({ field: f, mapping: base, current: refusedVisit });
    expect({ ...omitted, reasonCode: 'X' }).toEqual({ ...refusedVisit, reasonCode: 'X' });
    expect(withdrawn).toBe(false);
    expect(kept).toBe(true);
    expect(withdrawn).not.toBe(kept);
  });

  it('⚠️ THE TOKEN IS THE RESOLVER\'S OWN, not a string this test invented', () => {
    // A proof that retypes what it checks agrees with whichever copy its author
    // read last. The token is read from the emitter.
    const src = readFileSync(join(__dirname, '..', 'resolver', 'index.ts'), 'utf-8');
    expect(src, 'the resolver no longer emits the token this gate keys on').toContain(
      "'omitted_unsupported_default'",
    );
    // and the consumer keys on the same literal
    const consumer = readFileSync(join(__dirname, '..', 'clinician-override.ts'), 'utf-8');
    expect(consumer).toContain("current?.reasonCode === 'omitted_unsupported_default'");
  });

  it('⚠️ THE DECISION IS NOT TAKEN FROM THE MAPPING — that is what made it wrong', () => {
    // `unmentionedPolicy` and `canOmitWhenUnmentioned` are static properties of
    // the mapping: true on every visit or none. Neither may decide a per-visit
    // question, and the previous version used both.
    const consumer = readFileSync(join(__dirname, '..', 'clinician-override.ts'), 'utf-8');
    const fn = consumer.slice(consumer.indexOf('export function scaffoldDefaultOfferable'));
    const body = fn.slice(0, fn.indexOf('\n}'));
    const code = body
      .split('\n')
      .filter((l) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
      .join('\n');
    // NON-VACUITY: the slice must actually contain the clause under test.
    expect(code).toContain('reasonCode');
    expect(code, 'the mapping policy is being consulted again').not.toContain('unmentionedPolicy');
    expect(code, 'a confirm-time predicate is deciding a per-visit question').not.toContain(
      'canOmitWhenUnmentioned',
    );
  });

  it('⚠️ THE DOOR DOES NOT REFUSE ON THE STATIC POLICY — and this arm reads CODE, not prose', () => {
    // ⚠️ THE ARM THIS REPLACES WAS VACUOUS AND WAS CAUGHT BEING VACUOUS. It did
    // `expect(src).toMatch(/unmentionedPolicy === 'omit'/)` over the WHOLE FILE.
    // The static refusal was then deleted and this arm STAYED GREEN, because
    // the only remaining occurrence of that string is inside the comment
    // explaining the deletion. A substring assertion over a whole source file
    // is satisfied by the paragraph describing the thing it claims to check.
    //
    // So: comments are stripped before anything is asserted, and the arm proves
    // its own non-vacuity by requiring the stripped source to still contain the
    // symbols it reasons about.
    const raw = readFileSync(
      join(__dirname, '..', '..', '..', 'actions', 'set-template-control.ts'),
      'utf-8',
    );
    const code = raw
      .split('\n')
      .filter((l) => {
        const t2 = l.trim();
        return !t2.startsWith('//') && !t2.startsWith('*') && !t2.startsWith('/*');
      })
      .join('\n');

    // NON-VACUITY: the stripped source must still be the file we mean.
    expect(code).toContain('insertScaffoldDefaultAction');
    expect(code).toContain('undoScaffoldDefaultAction');

    // The door must NOT gate on a confirm-time property of the mapping. The
    // offer gates per visit; a static refusal here produced a button that
    // errored for the doctor on every visit the omit did not fire on.
    expect(
      code,
      'the insert door is refusing on the static policy again — it will refuse clicks the panel offers',
    ).not.toMatch(/unmentionedPolicy\s*===\s*'omit'/);

    // ...and it must not fetch the column for a decision it no longer makes.
    expect(code, 'a column fetched for a decision nobody makes').not.toContain(
      'unmentionedPolicy: true',
    );
  });

  it('⚠️ RULING #203 — THE CACHE KEY MOVED WITH THE FIX, or a warm entry serves the OLD offer list', () => {
    // `insertableDefaults` lives INSIDE the cached payload (`CachedFill`, TTL 30
    // minutes). This fix changes which fields that list CONTAINS and not its
    // SHAPE, so a pre-deploy entry deserialises perfectly and serves the
    // pre-fix offer list — a default offered on every omit field — for up to the
    // TTL. No schema check can see a contents-only change.
    const cache = readFileSync(join(__dirname, '..', '..', 'docx-preview', 'fill-cache.ts'), 'utf-8');
    const m = cache.match(/const KEY_VERSION = 'v(\d+)';/);
    // NON-VACUITY: a failed parse would make every assertion below trivially true.
    expect(m, 'KEY_VERSION did not parse — this arm proves nothing until it does').not.toBeNull();
    const v = Number((m as RegExpMatchArray)[1]);
    expect(v, 'KEY_VERSION must be at least v7 — ruling #203').toBeGreaterThanOrEqual(7);

    // ...and it is bound to THIS fix, not merely bumped at some point: the
    // per-visit gate and the key move together or the pairing is a coincidence.
    const offer = readFileSync(join(__dirname, '..', 'clinician-override.ts'), 'utf-8');
    expect(offer).toContain("current?.reasonCode === 'omitted_unsupported_default'");

    // The writer and the invalidation scan share ONE constant, by construction —
    // the v4->v5 bump moved the writer and not the scan. Divergence must stay
    // unrepresentable.
    expect(cache.match(/const KEY_VERSION/g) ?? []).toHaveLength(1);
    expect(cache.match(/\$\{KEY_VERSION\}/g) ?? []).toHaveLength(2);
  });

  it('⚠️ THE PER-VISIT GATE LIVES IN THE OFFER, and the two agree by construction', () => {
    // The offer and the door agreed before by both consulting the mapping. They
    // agree now by the door consulting NOTHING and the offer consulting the
    // resolution — which is the only place the per-visit answer exists.
    const offer = readFileSync(join(__dirname, '..', 'clinician-override.ts'), 'utf-8');
    expect(offer).toContain("current?.reasonCode === 'omitted_unsupported_default'");

    // An insert remains a HUMAN act and is audited as one — ruling #194's
    // principle, and the reason removing the door's refusal is safe.
    const door = readFileSync(
      join(__dirname, '..', '..', '..', 'actions', 'set-template-control.ts'),
      'utf-8',
    );
    expect(door).toContain('DEFAULT_INSERTED_BY_DOCTOR');
  });

});

// ============================================================================
// THE WRITER REFUSES AN `omit` THE RESOLVER COULD NEVER READ.
// ============================================================================
describe('item 2 — an unreachable omit cannot be persisted', () => {
  it('certification-lifecycle refuses it, using the SHARED predicate', () => {
    const src = readFileSync(join(__dirname, '..', 'certification-lifecycle.ts'), 'utf-8');
    // The rule, and that it is the imported one rather than a fourth copy.
    expect(src).toContain("from './unmentioned-policy'");
    expect(src).toMatch(/unmentionedPolicy === 'omit'\s*&&\s*\n?\s*!canOmitWhenUnmentioned\(field, mapping\)/);
  });

  it('the surface names the INERT variant rather than repeating the promise', () => {
    const src = readFileSync(
      join(__dirname, '..', '..', '..', 'app', 'settings', 'note-format', 'native-template-manager.tsx'),
      'utf-8',
    );
    expect(src).toContain('OMIT_INERT_LABEL');
    expect(src).toContain('twin-omit-readonly-inert-');
    // and the two labels must not be the same sentence, or the distinction is
    // decorative.
    expect(OMIT_INERT_LABEL).not.toBe(OMIT_CONTROL_LABEL);
    expect(OMIT_INERT_LABEL.toLowerCase()).toContain('no effect');
  });
});

// ============================================================================
// THE CLIENT BUNDLE — MEASURED, BECAUSE THE COMMENT THAT PROMISED IT WAS FALSE.
// ----------------------------------------------------------------------------
// ⚠️ FOUND BY A PEER SESSION'S INDEPENDENT PASS, AND IT WAS MY OWN FIX THAT
// CAUSED IT. `unmentioned-policy.ts` is value-imported by a `'use client'`
// component, so its transitive VALUE imports land in the browser. Moving
// `expectedDataTypeForFieldKind` out of `semantic-mapping/index.ts` (which
// pulls `@meddoc/ai`) into `ir.ts` looked like the safe home — and `ir.ts`
// value-imports zod and builds ~105 schemas at module scope.
//
//     746 bytes  ->  320,991 bytes, zod present     (429x)
//
// while the module header three lines above the import still read
// "NO RUNTIME IMPORTS — TYPES ONLY". A reader checks the comment, not the
// bundler.
//
// ⚠️ SO THIS ARM BUNDLES THE MODULE FOR REAL. A source-level assertion ("no
// import from ir") would have passed at 320KB the day somebody added a value
// import to the leaf instead. The property is the BYTES, so the bytes are what
// is measured — and the threshold is generous, because the failure it guards is
// three orders of magnitude, not a few hundred bytes.
// ============================================================================
describe('item 2 — the confirm surface does not pay for the engine', () => {
  it('⚠️ the client-imported module bundles small, with NO zod runtime', () => {
    // ⚠️ IN A CHILD PROCESS, DELIBERATELY. esbuild refuses to run inside
    // vitest's DOM-ish environment ("new TextEncoder().encode('') instanceof
    // Uint8Array is incorrectly false"), so an in-process attempt fails for a
    // reason that has nothing to do with the bundle. Driving the real bundler
    // out-of-process is the same shape this repo already uses for shell gates.
    const appRoot = join(__dirname, '..', '..', '..', '..');
    const modulePath = join(__dirname, '..', 'unmentioned-policy.ts');
    const script = `
      const { buildSync } = require('esbuild');
      const r = buildSync({
        stdin: {
          contents: ${JSON.stringify(
            'import { canOmitWhenUnmentioned, OMIT_CONTROL_LABEL, OMIT_CONTROL_HINT, OMIT_INERT_LABEL } from ',
          )} + ${JSON.stringify(JSON.stringify(modulePath))} + ';console.log(canOmitWhenUnmentioned,OMIT_CONTROL_LABEL,OMIT_CONTROL_HINT,OMIT_INERT_LABEL);',
          resolveDir: ${JSON.stringify(appRoot)},
          loader: 'ts',
        },
        bundle: true, platform: 'browser', format: 'esm', minify: true, write: false, logLevel: 'silent',
      });
      process.stdout.write(r.outputFiles[0].text);
    `;
    const out = execFileSync('node', ['-e', script], {
      encoding: 'utf8',
      cwd: appRoot,
      maxBuffer: 64 * 1024 * 1024,
    });

    // ⚠️ POSITIVE CONTROL FIRST. A bundle that resolved nothing would be tiny
    // and zod-free, and would satisfy both assertions below while proving
    // nothing at all.
    expect(out, 'the bundle does not contain the predicate').toContain('expectedDataType');
    expect(out.length, 'implausibly small — did it resolve?').toBeGreaterThan(300);

    expect(out.length, `client bundle is ${out.length} bytes — the engine leaked in`).toBeLessThan(
      20_000,
    );
    expect(/\bzod\b|ZodType|\$ZodError/i.test(out), 'zod reached the client bundle').toBe(false);
  });
});
