// ============================================================================
// Template Twin — VISIT METADATA fill (#247 family 3, Stage B).
// ----------------------------------------------------------------------------
// The patient's NAME and AGE are printed on the owner's consult letter, and no
// dictation contains them: the doctor does not say his own patient's name into
// the microphone. They are read off the PATIENT RECORD, and this module is the
// only place that happens.
//
// ⚠️ IT IS MODELLED ON `withProcedureDateFact` ON PURPOSE, AND FOR THE REASON
// THAT MODULE STATES: the fill path is built on cited `EncounterFact`s that the
// evidence resolver resolves and an INDEPENDENT validator re-checks. A
// resolution overlay would cite no real fact and flip validation to invalid,
// suppressing the native render — so metadata is injected as a FACT and then
// travels the ordinary road.
//
// ⚠️ AND IT WEARS `sourceType: 'visit_record'`, WHICH IS THE WHOLE OF #247.
// A record value carrying `encounter_evidence` makes the frozen manifest say
// the clinician SAID it. That is not a style point — the manifest is what a
// later reader consults to find out where a sentence on a signed document came
// from, and there is no way back from an answer that is wrong.
//
// WHAT IT WILL NOT DO, each one a decision rather than an omission:
//   - it never invents. No record, no name, no date of birth, no unambiguous
//     visit date -> nothing is injected and the control renders blank.
//   - it never overrides. A fact already speaking to the concept wins, always.
//   - it fills ONLY what the certified mapping asked for, keyed on the
//     mapping's own `sourceType`/`clinicalConcept` — never on the label. The
//     label was already read once, by `classifyFieldSource`, and reading it a
//     second time here is how one rule acquires two readers that disagree.
//   - it carries NOTHING but name and age. `visit_metadata.referring_physician`
//     is DICTATED and is emitted by the projector as ordinary evidence; the
//     registry deliberately has no term for an address, an MRN or a birth date,
//     so this module has nothing to reach for even if somebody asked it to.
// ============================================================================
import { createHash } from 'node:crypto';

import {
  EncounterFactSchema,
  type EncounterFact,
  type SemanticMapping,
  type TemplateField,
} from './ir';
import {
  conceptMatches,
  normalizeConcept,
  requiredFactTemporality,
} from './fact-mapping-match';

/** The two concepts this module may inject. Referring physician is NOT here. */
export const RECORD_DERIVED_CONCEPTS = {
  name: 'visit_metadata.patient_name',
  age: 'visit_metadata.patient_age',
} as const;

const METADATA_ANCHOR = 'visit-record-metadata';

/** The patient record, narrowed to the two columns this module may read. */
export interface VisitPatientRecord {
  name: string | null | undefined;
  dateOfBirth: Date | string | null | undefined;
}

/**
 * WHOLE YEARS AT A GIVEN DATE, OR NULL.
 *
 * ⚠️ CALENDAR ARITHMETIC, NOT DIVISION BY 365.25. A year length is not a
 * constant and the answer is read by a human as a fact about a person: the
 * patient whose birthday is tomorrow is not yet a year older, and a rounding
 * scheme that says otherwise puts a wrong age on a clinical letter roughly one
 * day in three hundred and sixty five.
 *
 * ⚠️ COMPARED ON UTC CALENDAR PARTS, AND THAT IS HONEST ONLY ABOUT ONE SIDE.
 * The first version of this paragraph claimed "so a server timezone cannot move
 * a birthday across midnight", and a refutation lens showed the claim is true of
 * the DOB (a `@db.Date`, stored at UTC midnight) and FALSE of the visit: the
 * caller passes `visit.createdAt`, a `timestamptz`. Measured — DOB 1958-06-14,
 * a visit at 2026-06-13 19:00 America/Los_Angeles = `2026-06-14T02:00Z` — this
 * returns **68** where the patient is 67 on the local day of the encounter.
 *
 * ⚠️ THE RESIDUAL IS NO LONGER ACCEPTED — RULING #264, "AGE NEVER GUESSES".
 * A practice still has no timezone column (measured: `practices` has ten
 * columns and none of them is one), so "the local calendar date of the visit"
 * remains uncomputable. What changed is the ANSWER to that: the previous
 * paragraph said the error was "recorded rather than hidden" and left a wrong
 * number in a consult letter. A one-year-high age is a CLINICAL ERROR, not a
 * documented quirk, and a doctor does not read the comment.
 *
 * ⚠️ AND THE OLD PARAGRAPH WAS HALF-RIGHT IN A WAY THAT MATTERS: it named only
 * the "one year HIGH" direction. The error runs BOTH ways, because the local
 * date can be either side of the UTC date:
 *
 *     DOB 1958-06-14, visit 2026-06-13 19:00 America/Los_Angeles (= 06-14T02:00Z)
 *         UTC says the birthday has passed -> 68.  Locally it is the 13th -> 67.
 *     DOB 1958-06-14, visit 2026-06-14 09:00 Pacific/Auckland   (= 06-13T21:00Z)
 *         UTC says it has not -> 67.  Locally it is the 14th -> 68.
 *
 * `ageAtDateResolved` therefore REFUSES, with a named reason, whenever the age
 * would differ anywhere in the UTC-12..UTC+14 window of the visit instant —
 * a total predicate that needs no practice timezone, which is exactly why the
 * ruling picked it.
 *
 * ⚠️ WHAT IT COSTS, SO NOBODY HAS TO GUESS: the window is 26 hours wide, so it
 * fires only for a patient whose birthday boundary falls inside it — of the
 * order of 26/24 days a year, ~0.3% of visits. Those are precisely the visits
 * where the old answer was a coin flip. Every other visit is unaffected.
 *
 * Returns null — never 0, never a guess — for an unparseable date, a birth date
 * in the future, or an implausible result. `0` is a legitimate age (an infant),
 * so it cannot double as the failure value.
 */
/** Why an age could not be stated. A refusal is never silent — #264. */
export type AgeRefusal =
  | 'age_input_absent'
  | 'age_unparseable'
  | 'age_implausible'
  | 'age_timezone_ambiguous';

export type AgeResolution =
  | { ok: true; years: number }
  | { ok: false; reason: AgeRefusal };

/** UTC-12..UTC+14 — the real span of civil offsets, and the whole predicate. */
const TZ_MIN_MS = -12 * 60 * 60 * 1000;
const TZ_MAX_MS = 14 * 60 * 60 * 1000;

/**
 * The age, or a NAMED reason there isn't one. `ageAtDate` is the thin
 * `number | null` wrapper over this, kept so existing callers are undisturbed.
 */
export function ageAtDateResolved(
  dateOfBirth: Date | string | null | undefined,
  at: Date | string | null | undefined,
): AgeResolution {
  if (dateOfBirth == null || at == null) return { ok: false, reason: 'age_input_absent' };
  const dob = dateOfBirth instanceof Date ? dateOfBirth : new Date(dateOfBirth);
  const on = at instanceof Date ? at : new Date(at);
  if (Number.isNaN(dob.getTime()) || Number.isNaN(on.getTime())) {
    return { ok: false, reason: 'age_unparseable' };
  }

  // ⚠️ THE ENDPOINTS SUFFICE, AND THAT IS NOT AN APPROXIMATION. The local
  // calendar date at offset `o` is the UTC date of `instant + o`, and age is
  // monotonic in date — so if the two extremes agree, every offset between them
  // agrees too. Checking the endpoints is the whole window, not a sample of it.
  const low = ageOnUtcDate(dob, new Date(on.getTime() + TZ_MIN_MS));
  const high = ageOnUtcDate(dob, new Date(on.getTime() + TZ_MAX_MS));
  if (low === null || high === null) return { ok: false, reason: 'age_implausible' };
  if (low !== high) return { ok: false, reason: 'age_timezone_ambiguous' };
  return { ok: true, years: low };
}

/** The UTC-calendar age. Null for a negative or superhuman result. */
function ageOnUtcDate(dob: Date, on: Date): number | null {
  let years = on.getUTCFullYear() - dob.getUTCFullYear();
  const monthDelta = on.getUTCMonth() - dob.getUTCMonth();
  if (monthDelta < 0 || (monthDelta === 0 && on.getUTCDate() < dob.getUTCDate())) {
    years -= 1;
  }
  // A negative age means the record and the visit disagree about time; an age
  // past the verified human maximum means the column holds something that is
  // not this patient's birth date. Both are refusals, not clamps.
  if (years < 0 || years > 130) return null;
  return years;
}

/**
 * The age, or null.
 *
 * ⚠️ A THIN WRAPPER, NEVER A SECOND IMPLEMENTATION. It delegates to
 * `ageAtDateResolved` and throws the reason away. Two functions computing an
 * age two ways is the "one rule, many readers" failure this repository has a
 * canon entry for — and the reader that drifted would be the one a document
 * prints. There is no production caller of this wrapper outside this module
 * (measured: every other reference is in `gate-247-visit-metadata.test.ts`);
 * it is kept because a `number | null` reads better at a call site that does
 * not need the reason.
 */
export function ageAtDate(
  dateOfBirth: Date | string | null | undefined,
  at: Date | string | null | undefined,
): number | null {
  const resolved = ageAtDateResolved(dateOfBirth, at);
  return resolved.ok ? resolved.years : null;
}

/**
 * The `expectedDataType`s a record-derived value may legitimately fill.
 *
 * ⚠️ THE SECOND WALL, AND THE FIRST ONE IS `classifyFieldSource`'s KIND CHECK.
 * A refutation lens ticked a CHECKBOX labelled `Patient` by putting a
 * record-derived fact against a `boolean` mapping: the resolver's checkbox arm
 * reads polarity and discards the value, so a chart with a name in it renders
 * ☒ on a signed form. The classifier now refuses to call such a control
 * `visit_metadata` at all — but a certified mapping is DATA, restored and
 * hand-editable, and the classifier does not run again at fill time. So the
 * injector checks the shape it is actually filling.
 */
const RECORD_DERIVABLE_DATA_TYPES: ReadonlySet<string> = new Set(['text', 'number']);

/** A stable 24-hex fact id for one record-derived value. */
function recordFactId(
  concept: string,
  value: string,
  temporality: EncounterFact['temporality'],
): string {
  return `ttfact_${createHash('sha256')
    .update(`visit_record ${concept} ${temporality} ${value}`, 'utf8')
    .digest('hex')
    .slice(0, 24)}`;
}

/**
 * Return the fact set with the patient record's name and age injected, for the
 * concepts this template's CERTIFIED mappings actually ask for. Pure; returns a
 * NEW array. A no-op when there is no patient record, no such mapping, or the
 * concept is already spoken to.
 *
 * ⚠️ ONE FACT PER CONCEPT, NOT ONE PER FIELD. Facts are matched to fields by
 * concept, so a single `visit_metadata.patient_name` fact satisfies the header
 * control AND the letter's opening line. Minting one per field would put N
 * identical values in the manifest and give `multiple_distinct_supported_values`
 * something to trip over the day two controls disagree about nothing.
 */
export function withVisitMetadataFacts(input: {
  fields: ReadonlyArray<TemplateField>;
  mappings: ReadonlyArray<SemanticMapping>;
  facts: ReadonlyArray<EncounterFact>;
  patient: VisitPatientRecord | null | undefined;
  visitDate: Date | string | null | undefined;
  /**
   * ⚠️ #264 — AN OUT-PARAMETER, AND THE SHAPE IS DELIBERATE. This function
   * composes by NESTING in `fill-engine.ts` (`withProcedureDateFact({ facts:
   * withVisitMetadataFacts({ facts: withApprovedPracticeDefaultFacts(...) }) })`),
   * so returning `{ facts, refusals }` would have to be unwrapped at every
   * layer and would change three signatures to carry information only one of
   * them produces. A collector the caller owns keeps the composition intact.
   *
   * Optional, so every existing caller — the certification path included — is
   * undisturbed and simply does not learn the reason.
   */
  refusals?: Array<{ fieldId: string; unfilled: string; required: string }>;
}): EncounterFact[] {
  const facts = [...input.facts];
  const patient = input.patient;
  if (!patient) return facts;

  const fieldIds = new Set(input.fields.map((field) => field.fieldId));

  /**
   * REAL EVIDENCE WINS — and "real evidence" is whatever the RESOLVER would
   * accept for this mapping, not whatever shares its concept string.
   *
   * ⚠️ THE FIRST DRAFT COMPARED CONCEPT STRINGS AND THE RESOLVER DID NOT, SO
   * THE TWO WERE ANSWERING DIFFERENT QUESTIONS ABOUT THE SAME PAIR. A
   * refutation lens built the gap: a mapping citing `visit_metadata.patient_name`
   * with `approvedSynonyms: ['chief_complaint']`, plus a dictated
   * chief-complaint fact. The concept strings differ, so this injected anyway;
   * the resolver then matched BOTH and produced one `supported` resolution
   * citing a dictated fact AND a record fact — which the validator's own
   * provenance arm refuses as BLOCKING, and a blocking issue is `render: null`.
   * **The doctor loses the whole native document** because two guards read the
   * same relation differently.
   *
   * Asking `conceptMatches` makes them one question. It reads the PRE-EXISTING
   * facts only, and is never mutated as this function injects — see the
   * per-tense loop below, where two facts for one concept are legitimate.
   */
  const alreadySpokenTo = (mapping: SemanticMapping): boolean =>
    input.facts.some((f) => conceptMatches(f, mapping));

  // What this template ASKS FOR, keyed by CONCEPT **and the tense that concept's
  // mappings approve**, so the injected fact can satisfy the mapping that asked
  // rather than one the resolver will then refuse.
  //
  // ⚠️ ONE FACT PER CONCEPT WAS NOT ENOUGH, AND A REFUTATION LENS MEASURED WHY.
  // The first draft kept the FIRST mapping per concept and inherited its
  // `requiredFactTemporality`. Two `visit_metadata.patient_name` controls whose
  // mappings declare different tenses — legal, and the model may propose a
  // tense — gave: control 1 `record_derived`, control 2 `not_mentioned /
  // temporality_not_approved`, silently blank; and with `required: true` on the
  // second, `needs_clinician_input` -> BLOCKING -> the whole document withheld.
  // The outcome depended on the order of the `mappings` array.
  //
  // Keying on the tense as well makes each demanded tense its own fact, so
  // every control is answered. In the ordinary case both mappings want the same
  // tense and this is still exactly one fact — the module header's claim about
  // the header control and the letter's opening line is unchanged.
  const wanted = new Map<string, { mapping: SemanticMapping; concept: string; temporality: EncounterFact['temporality'] }>();
  for (const mapping of input.mappings) {
    if (!fieldIds.has(mapping.fieldId)) continue;
    if (mapping.sourceType !== 'visit_metadata') continue;
    if (mapping.status !== 'certified') continue;
    // ⚠️ THE SECOND WALL — see `RECORD_DERIVABLE_DATA_TYPES`. A `boolean`
    // mapping here means a checkbox, and a checkbox cannot carry a name.
    if (!RECORD_DERIVABLE_DATA_TYPES.has(mapping.expectedDataType)) continue;
    const concept = mapping.clinicalConcept;
    if (!concept) continue;
    const normalized = normalizeConcept(concept);
    if (
      normalized !== RECORD_DERIVED_CONCEPTS.name &&
      normalized !== RECORD_DERIVED_CONCEPTS.age
    ) {
      // A `visit_metadata` mapping citing anything else is not this module's
      // business. Ignoring it is right: the registry closes the family at
      // three, and the third member is dictated.
      continue;
    }
    const temporality = requiredFactTemporality(mapping);
    const key = `${normalized}|${temporality}`;
    if (!wanted.has(key)) wanted.set(key, { mapping, concept: normalized, temporality });
  }
  if (wanted.size === 0) return facts;

  const patientName = patient.name?.trim();
  // ⚠️ RESOLVED, NOT COERCED — the reason has to survive to the manifest.
  // A refusal that reaches the resolver as "no fact carried this concept" is
  // reported as `fact_not_mentioned`, i.e. "nobody said it" — and here somebody
  // DID say it: the patient record carries a date of birth and this code
  // declined to turn it into a number. #264 requires the blank to be NAMED.
  const ageResolved = ageAtDateResolved(patient.dateOfBirth, input.visitDate);
  const age = ageResolved.ok ? ageResolved.years : null;
  // Both quotes are written to be TRUE OF THE ACT and to carry no identifier of
  // their own. The value carries the name; the evidence line says where it came
  // from, and that sentence is what a doctor reads in the manifest.
  const values: ReadonlyArray<readonly [string, string | null, string]> = [
    [
      RECORD_DERIVED_CONCEPTS.name,
      patientName && patientName.length > 0 ? patientName : null,
      'Patient name from the patient record.',
    ],
    [
      RECORD_DERIVED_CONCEPTS.age,
      age === null ? null : String(age),
      'Patient age in whole years, computed from the date of birth in the patient record at the date of this visit.',
    ],
  ];

  const byConcept = new Map<string, string | null>(values.map(([c, v]) => [c, v]));
  const quoteFor = new Map<string, string>(values.map(([c, , q]) => [c, q]));

  for (const { mapping, concept, temporality } of wanted.values()) {
    const value = byConcept.get(concept) ?? null;
    const quote = quoteFor.get(concept)!;
    if (value === null) {
      // ⚠️ #264 — THE BLANK IS NAMED. Skipping silently was the whole defect:
      // the resolver would go on to report `fact_not_mentioned`, which reads as
      // "nobody said it" when the record said it and this code declined to
      // answer. Only the AGE carries a structured reason today, because it is
      // the only value here that can be refused for a reason other than
      // absence — a missing name is simply missing.
      if (
        input.refusals &&
        concept === RECORD_DERIVED_CONCEPTS.age &&
        !ageResolved.ok &&
        !alreadySpokenTo(mapping)
      ) {
        input.refusals.push({
          fieldId: mapping.fieldId,
          unfilled: ageResolved.reason,
          required: `required_${ageResolved.reason}`,
        });
      }
      continue;
    }
    if (alreadySpokenTo(mapping)) continue;
    facts.push(
      EncounterFactSchema.parse({
        factId: recordFactId(concept, value, temporality),
        // ⚠️ #247 — THE CLASS, AND THE ONLY REASON THIS MODULE EXISTS.
        sourceType: 'visit_record',
        concept,
        value,
        // Stated, never inferred — canon 135. There is no such thing as a
        // denied patient name, and `inferPolarity` reading the word "no" out of
        // a name or an evidence sentence would blank the control on a document
        // with nothing wrong with it.
        polarity: 'affirmed',
        temporality,
        // The subject IS the patient. (The referring physician, the one member
        // of this family that is not, is emitted by the projector with
        // `experiencer: 'other'` and is not injected here at all.)
        experiencer: 'patient',
        laterality: 'not_applicable',
        // ⚠️ `number` STAYS NULL FOR THE AGE, AND THAT IS DELIBERATE. The
        // controls this fills compile `narrative_text` (canon 134 — kind and
        // concept are independent axes), and the resolver's number arm refuses
        // a value whose unit policy it cannot satisfy. The digits travel as the
        // string that is actually printed.
        number: null,
        unit: null,
        speaker: 'Patient record',
        sourceTranscriptOffsets: null,
        audioTimestampSeconds: null,
        evidenceAnchorIds: [`${METADATA_ANCHOR}:${concept}`],
        evidenceQuote: quote,
        quality: { asr: 'unknown', evidence: 'direct' },
      }),
    );
  }
  return facts;
}
