/**
 * RULING #179(6) — TWO HALVES, BOTH FOUND UNARMED BY THE MANDATORY PASS.
 *
 * (a) NARRATIVE_SENTENCES may only carry concepts the extractor actually
 *     emits, and must cover the ROS lexicon it claims to serve.
 * (b) ⚠️ REVERSED 2026-09-07 — A NULL MAPPING TEMPORALITY MEANS `any` AGAIN,
 *     AND THE REASON IS THAT (6) HAS NO RECORDED CONTENT.
 *
 * ⚠️ THE ORIGINAL WORDING IS KEPT HERE BECAUSE THE CORRECTION IS THE POINT:
 * "(b) A NULL mapping temporality means `current`, NEVER `any`. ⚠️ (b) IS THE
 * CLINICALLY SHARP ONE, AND IT REDDED NOTHING. Mutating 'null means current'
 * into 'null means any' passed 674 of 674 twin tests."
 *
 * That observation was TRUE and the arm was right to exist. What was missing
 * is that the rule it armed cannot be produced. Measured across the ledger head
 * and every archive, with controls that discriminate — `laterality` 17 hits in
 * 3 files, `scaffolded` 36, `unmentionedPolicy` 11, `conceptScope` 3 —
 * **`temporality` scores ZERO, in any ruling, ever.** And #179's own body says
 * so: "Parts 4 and 6 are not described here because this session was not given
 * their content. An empty row is honest; a plausible one written to make the
 * table look complete would be a fabrication wearing a ledger's authority."
 *
 * ⚠️ AND THE RULE WAS APPLIED IN ONE OF THREE READERS, WHICH IS WHAT MADE IT
 * HARMFUL RATHER THAN MERELY UNSUPPORTED. The resolver and `bridge-evidence`
 * still read null as `any`, so the resolver FILLED a field and CITED its fact
 * and the validator then rejected that same citation as
 * SOURCE_FACT_CONCEPT_MISMATCH — and `fill-engine` turns a blocking issue into
 * `render: null`. The failure was not a wrong value; it was the doctor's WHOLE
 * DOCUMENT not being produced. Measured over the (mapping.temporality x
 * fact.temporality) matrix: 3 disagreeing cells before, 0 after, and every one
 * of the three sat at `mapping.temporality === null`.
 *
 * ⚠️ THE CLINICAL INTENT IS NOT ABANDONED, IT IS RE-AIMED. "The patient denies
 * chest pain must not be contradicted by chest pain the patient had in 2019" is
 * a claim about ROS SCAFFOLD CLAUSES, and it is delivered by declaring
 * `temporality: 'current'` ON THOSE MAPPINGS — explicit, narrow, and visible in
 * the mapping a doctor confirms. Redefining null globally reached every field
 * of every template instead, including Past Medical History and Family History,
 * whose facts are `historical` BY CONSTRUCTION.
 *
 * The question is filed for the owner at
 * `docs/foundation/board/179-REPAIR-OWNER-QUESTIONS.md`. If he confirms he
 * ruled (6), the edit is ONE constant in `fact-mapping-match.ts` and these arms
 * inverting with it.
 *
 * ⚠️ AND (a)'s SOURCE COMMENT CLAIMED AN ARM THAT DID NOT EXIST. It named
 * `gate-f5i2-narrative-encounter.test.ts` as asserting the table "with a
 * mutation that reddens both"; that file has ZERO references to it. The
 * load-time assertion is real and does fire — the claimed test was fiction.
 * A comment asserting coverage is what the next reader checks INSTEAD of the
 * tests, which is why it is corrected in source rather than quietly replaced.
 */
import { describe, it, expect } from 'vitest';
import { factMatchesMapping } from '../validation/index';
import { resolveTemplateFields } from '../resolver/index';
import { narrativeSentence } from '../verification-encounter';
import { isRegisteredConcept } from '../concept-registry';
import { ROS_SYSTEMS, symptomsFor, rosConcept, ROS_OTHER } from '../ros-lexicon';
import {
  SemanticMappingSchema,
  EncounterFactSchema,
  TemplateFieldSchema,
  type SemanticMapping,
  type EncounterFact,
  type TemplateField,
} from '../ir';

const SHA = 'a'.repeat(64);

/** A narrative field the resolver will actually fill — the agreement arm needs
 *  a real resolution, not a predicate call. Mirrors the shipped factory in
 *  `gate-179-checkbox-scope.test.ts`. */
function narrativeField(): TemplateField {
  return TemplateFieldSchema.parse({
    fieldId: FIELD_ID,
    kind: 'narrative_text',
    originalLabel: 'Past Medical History',
    labelSource: 'left_cell',
    displayOrder: 0,
    detectionStatus: 'certified',
    allowedOptions: [],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: 'content_control',
      path: '/document/pmh',
      ordinal: 0,
      sdtId: '1',
      tag: 'synthetic',
      alias: null,
      legacyName: null,
      rowLaterality: 'unknown',
      tableIndex: null,
      rowIndex: null,
      cellIndex: null,
      repeatAncestorPath: null,
      sourceControlSha256: SHA,
      originalContentSha256: SHA,
    },
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: false,
    criticality: 'routine',
    tableId: null,
    rowPrototype: false,
  });
}

const FIELD_ID = 'ttf_0123456789abcdef01234567';
const CONCEPT = 'ros.gastrointestinal.heartburn';

function mapping(over: Partial<SemanticMapping> = {}): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId: FIELD_ID,
    sourceType: 'extraction',
    clinicalConcept: CONCEPT,
    expectedDataType: 'text',
    polarityBehavior: 'value_only',
    temporality: 'current',
    laterality: 'optional',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
    ...over,
  });
}

function fact(temporality: EncounterFact['temporality']): EncounterFact {
  return EncounterFactSchema.parse({
    factId: 'ttfact_000000000000000000000001',
    sourceType: 'encounter_evidence',
    concept: CONCEPT,
    value: 'yes',
    polarity: 'affirmed',
    temporality,
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: 'Doctor',
    sourceTranscriptOffsets: { start: 0, end: 20 },
    audioTimestampSeconds: null,
    evidenceAnchorIds: ['anchor-1'],
    evidenceQuote: 'Synthetic evidence',
    quality: { asr: 'high', evidence: 'direct' },
    segment: null,
  });
}

describe('#179(6b) — REVERSED: a null mapping temporality means `any`', () => {
  it('NON-VACUITY: a null-temporality mapping matches a CURRENT fact', () => {
    // Kept from the original arms. Without it every assertion below is
    // consistent with a matcher that accepts everything unconditionally.
    expect(factMatchesMapping(fact('current'), mapping({ temporality: null }))).toBe(true);
  });

  it('a HISTORICAL fact DOES satisfy a null-temporality clause — `main`\'s meaning', () => {
    // ⚠️ THIS ARM IS INVERTED FROM ITS ORIGINAL FORM, deliberately. It is the
    // Past Medical History case: `encounter-facts` stamps `historical` on every
    // PMH and family-history item BY CONSTRUCTION, so under the branch's rule
    // those fields were filled by the resolver and then refused by the
    // validator — costing the whole document, on every visit, for any template
    // carrying one.
    expect(factMatchesMapping(fact('historical'), mapping({ temporality: null }))).toBe(true);
  });

  it('so does a PLANNED fact', () => {
    expect(factMatchesMapping(fact('planned'), mapping({ temporality: null }))).toBe(true);
  });

  it('and an UNKNOWN-temporality fact', () => {
    expect(factMatchesMapping(fact('unknown'), mapping({ temporality: null }))).toBe(true);
  });

  it('⚠️ DISCRIMINATION: a null mapping is not a matcher that accepts everything', () => {
    // The arms above would all pass against a `factMatchesMapping` that
    // returned true unconditionally. This is what says it does not: an
    // EXPLICIT tense still refuses a fact in another tense, so the null arms
    // are measuring the null branch and not a broken predicate.
    expect(factMatchesMapping(fact('historical'), mapping({ temporality: 'current' }))).toBe(false);
    expect(factMatchesMapping(fact('current'), mapping({ temporality: 'historical' }))).toBe(false);
  });

  it('an EXPLICIT `any` still matches everything', () => {
    for (const t of ['current', 'historical', 'planned', 'unknown'] as const) {
      expect(factMatchesMapping(fact(t), mapping({ temporality: 'any' })), t).toBe(true);
    }
  });

  it('an EXPLICIT `historical` matches historical and not current', () => {
    expect(factMatchesMapping(fact('historical'), mapping({ temporality: 'historical' }))).toBe(true);
    expect(factMatchesMapping(fact('current'), mapping({ temporality: 'historical' }))).toBe(false);
  });
});

/**
 * ⚠️ THE ARM THAT WOULD HAVE CAUGHT THE ORIGINAL DEFECT, AND THE ONE THAT KEEPS
 * IT SHUT. Its subject is the AGREEMENT of the readers, not any one reader.
 *
 * Three modules answered "does this fact satisfy this mapping" — the validator,
 * the resolver, and `bridge-evidence` — and #179 changed one. Every arm in this
 * repository pointed at ONE of them, so all three could be green while the
 * system contradicted itself. The rule now lives in `fact-mapping-match.ts` and
 * is imported, but a future edit can re-open the gap by open-coding a filter
 * again; this arm is what fails when it does.
 *
 * MEASURED, same harness, two trees: 3 disagreements on the unmodified branch,
 * 0 after the consolidation — so it discriminates, and it is not asserting a
 * property that was already true.
 */
/**
 * ⚠️ #179(3) HAD THE IDENTICAL VALIDATOR-ONLY DEFECT, AND ITS FAILURE MODE WAS
 * THE WORSE ONE: A DESTROYED DOCUMENT RATHER THAN A WRONG TICK.
 *
 * `conceptScope` was read by the validator and by `field-value-derivation`, and
 * NOT by the resolver — whose candidate universe was its own
 * `new Set([clinicalConcept, ...approvedSynonyms])`. So a fact OUTSIDE a
 * declared scope was selected by the resolver, written as the field's value and
 * CITED; the validator then refused that citation and `fill-engine` withheld the
 * whole package.
 *
 * MEASURED, same harness, both trees — a scope that EXCLUDES the fact's concept:
 *   before   validator=false   resolver=supported/true, 1 cited   -> document withheld
 *   after    validator=false   resolver=not_mentioned/null, 0 cited -> document renders
 * The other three rows (scope includes, multi-scope, no scope) are unchanged in
 * both trees, so the harness is measuring the scope branch and not a resolver
 * that stopped filling.
 *
 * ⚠️ WHAT THIS DOES NOT CLOSE, SAID PLAINLY: #179(5)'s MULTI-SCOPE CHECKBOX
 * REFUSAL. `deriveFieldValueFromFact` refuses to tick a box whose scope covers
 * more than one symptom, and the resolver still does not call it — it has its
 * own inline `case 'checkbox'`. A multi-scope box is therefore still ticked from
 * one fact. That is a separate fix and it is NOT claimed here.
 */
describe('#179(3) — a declared conceptScope is enforced where the value is WRITTEN', () => {
  const IN_SCOPE = CONCEPT;
  const OUT_OF_SCOPE = 'ros.gastrointestinal.dysphagia';

  function resolveWithScope(scope: string[] | undefined, factConcept: string) {
    const m = mapping(scope ? { conceptScope: scope } : {});
    const f = EncounterFactSchema.parse({ ...fact('current'), concept: factConcept });
    const [resolution] = resolveTemplateFields({
      fields: [narrativeField()],
      mappings: [m],
      facts: [f],
      certifiedFieldIds: [FIELD_ID],
    });
    return { validator: factMatchesMapping(f, m), resolution };
  }

  it('⚠️ a fact OUTSIDE the declared scope is not written and not cited', () => {
    const { validator, resolution } = resolveWithScope([OUT_OF_SCOPE], IN_SCOPE);
    expect(validator).toBe(false);
    // The whole point: the resolver AGREES rather than filling something the
    // validator will then refuse. A cited fact here is a withheld document.
    expect(resolution.sourceFactIds).toEqual([]);
    expect(resolution.value).toBeNull();
  });

  it('NON-VACUITY: a fact INSIDE the declared scope still fills the field', () => {
    // Without this the arm above is satisfied by a resolver that stopped
    // filling scoped mappings altogether, which would blank every clause.
    const { validator, resolution } = resolveWithScope([IN_SCOPE], IN_SCOPE);
    expect(validator).toBe(true);
    expect(resolution.sourceFactIds.length).toBeGreaterThan(0);
  });

  it('CONTROL: an unscoped mapping is unaffected', () => {
    const { validator, resolution } = resolveWithScope(undefined, IN_SCOPE);
    expect(validator).toBe(true);
    expect(resolution.sourceFactIds.length).toBeGreaterThan(0);
  });
});

describe('the validator and the resolver answer the temporality question identically', () => {
  const MAPPING_TENSES = [null, 'any', 'current', 'historical', 'planned'] as const;
  const FACT_TENSES = ['current', 'historical', 'planned', 'unknown'] as const;

  it('agrees on every cell of the (mapping x fact) temporality matrix', () => {
    const disagreements: string[] = [];
    let matched = 0;
    for (const mt of MAPPING_TENSES) {
      for (const ft of FACT_TENSES) {
        const m = mapping({ temporality: mt });
        const validatorSays = factMatchesMapping(fact(ft), m);
        const [resolution] = resolveTemplateFields({
          fields: [narrativeField()],
          mappings: [m],
          facts: [fact(ft)],
          certifiedFieldIds: [FIELD_ID],
        });
        // ⚠️ `sourceFactIds`, and the name matters. My first harness read
        // `citedFactIds` — a field that does not exist — and still printed the
        // right answer, because it fell through to a `status === 'supported'`
        // alternative. A probe that is right for the wrong reason is the thing
        // this whole arm exists to prevent, so it is read directly here with
        // no fallback to hide a typo.
        const resolverCites = resolution.sourceFactIds.length > 0;
        if (validatorSays !== resolverCites) {
          disagreements.push(`mapping=${String(mt)} fact=${ft}: validator=${validatorSays} resolver=${resolverCites}`);
        }
        if (validatorSays) matched += 1;
      }
    }
    // NON-VACUITY: the matrix must contain both answers, or "they agree" is a
    // statement about a predicate that never fired.
    expect(matched, 'no cell matched — the harness is not exercising the matcher').toBeGreaterThan(0);
    expect(matched, 'every cell matched — the harness cannot see a refusal').toBeLessThan(
      MAPPING_TENSES.length * FACT_TENSES.length,
    );
    expect(disagreements).toEqual([]);
  });
});

describe('#179(6a) — NARRATIVE_SENTENCES is bound to the registry and covers the lexicon', () => {
  it('NON-VACUITY: the lexicon is a real, populated set', () => {
    expect(ROS_SYSTEMS.length).toBeGreaterThanOrEqual(10);
    const total = ROS_SYSTEMS.reduce((n, s) => n + symptomsFor(s).length, 0);
    expect(total).toBeGreaterThanOrEqual(60);
  });

  it('every addressable ROS concept has a dictatable sentence', () => {
    // A concept the extractor can emit but the generator cannot dictate is a
    // field that can never be verified.
    const missing: string[] = [];
    for (const system of ROS_SYSTEMS) {
      for (const symptom of symptomsFor(system)) {
        if (symptom === ROS_OTHER) continue; // deliberately unaddressable
        const c = rosConcept(system, symptom);
        if (narrativeSentence(c) === null) missing.push(c);
      }
    }
    expect(missing, `concepts with no sentence: ${missing.slice(0, 8).join(', ')}`).toEqual([]);
  });

  it('⚠️ `ros.<system>.other` IS registered and IS dictatable — its exclusion is from SCOPES', () => {
    // ⚠️ CORRECTED BY MEASUREMENT. This arm first asserted `other` was not
    // dictatable; it is. The registry matches `ros.*` BY PATTERN, so every
    // `ros.<system>.<symptom>` is registered and the patterned generator
    // serves it. `other` exists precisely so a symptom outside the list is not
    // silently dropped — it must be speakable.
    const other = rosConcept(ROS_SYSTEMS[0], ROS_OTHER);
    expect(isRegisteredConcept(other)).toBe(true);
    expect(narrativeSentence(other)).not.toBeNull();
  });

  it('⚠️ and the REAL property: `other` cannot satisfy a clause scoped to named symptoms', () => {
    // This is what "excluded from every declared scope by construction" means,
    // and it is the half that carries clinical weight: a scaffolded clause
    // naming three symptoms must not be answered by a finding the extractor
    // could not place. Asserted through the shipped matcher.
    const scoped = mapping({
      conceptScope: [
        'ros.gastrointestinal.heartburn',
        'ros.gastrointestinal.dysphagia',
      ],
    });
    const otherFact = EncounterFactSchema.parse({
      ...fact('current'),
      concept: 'ros.gastrointestinal.other',
    });
    expect(factMatchesMapping(otherFact, scoped)).toBe(false);
  });

  it('a concept OUTSIDE the registry entirely has no sentence', () => {
    // The registry's pattern arm covers `ros.*`; something with no family at
    // all must still come back null, or the generator would dictate sentences
    // for fields no fact can ever fill.
    expect(isRegisteredConcept('completely.invented.concept')).toBe(false);
    expect(narrativeSentence('completely.invented.concept')).toBeNull();
  });
});
