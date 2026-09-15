// ============================================================================
// Template Twin — THE derivation of a field's value from its cited fact.
// ----------------------------------------------------------------------------
// ONE RULE, EVERY CALLER. This module exists because the rule had two callers
// and only one of them was using it.
//
// The validator re-derives a supported field's value from the fact the
// resolution cites and compares the two with strict `===`
// (validation/index.ts, assertionSupported). Anything that WRITES a supported
// resolution must therefore write exactly what this function returns for that
// (field, mapping, fact) — otherwise the value is refused as
// ASSERTION_NOT_SUPPORTED, which is a BLOCKING issue and kills the entire
// native fill for the visit, not merely the one cell.
//
// ⚠️ WHAT THIS COST, AND WHY IT IS A MODULE RATHER THAN A COMMENT.
// bridge-fill.ts wrote the MODEL'S markdown cell text — "3.10" — while the
// validator re-derived the FACT'S own value — "3.1". The two agree
// NUMERICALLY (the matcher had already proved identity to 1e-9) and differ
// only in TEXT, so `"3.1" === "3.10"` was false and two cells of the owner's
// real template blocked certification three times running. Reproduced and
// named at FILE:LINE by F5-d(a); fixed here per ruling #135.
//
// The failure needs a trailing zero to appear at all, which is why 18 of 20
// diameters round-tripped fine and nothing surfaced it for weeks. A doctor
// dictating "three point one zero millimetres" reproduces it on a real visit.
//
// ⚠️ THIS IS A TIGHTENING, NOT A LOOSENING. The document now carries the CITED
// FACT'S value instead of model-authored text. Making the validator compare
// numerically instead would have "worked" and would have weakened a shipped
// gate on the clinical path — explicitly ruled out by #135.
//
// ⚠️ PROVENANCE, STATED EXACTLY. `isStrictIsoDate` and `exactOption` came out
// of validation/index.ts byte-identical. `deriveFieldValueFromFact` is its
// `valueFromFact` plus exactly ONE line — `if (!mapping) return null;` — and
// nothing else; measured by comparing normalised function bodies against
// origin/main rather than by eye. The validator cannot reach that line (it
// refuses a mapping-less field with MAPPING_MISSING before assertionSupported
// runs), so its behaviour is unchanged.
//
// The third producer, resolver/index.ts's convertValue, is a SEPARATE
// implementation of the same rule and is deliberately NOT folded in here
// today: it converts from a raw fact value under resolver-specific failure
// CODES that its own callers switch on, and it already derives FROM THE FACT
// rather than from model text — so it does not carry THIS defect (the bridge's
// note-text copy). Named here so the next reader knows the duplication is seen
// rather than missed.
//
// ⚠️ AN EARLIER VERSION OF THAT SENTENCE STOPPED AT "does not carry this
// defect", AND AN ADVERSARIAL PASS CORRECTLY READ IT AS WIDER THAN INTENDED.
// The resolver carries the same FAMILY — a writer and the validator disagreeing
// by one character, costing the whole document — through a different door:
// `resolver/index.ts:107` TRIMS before matching an option and this module does
// not (nor did the validator's private copy it came from, so the extraction
// introduced nothing). A `single_select` fact value of `"Normal "` therefore
// resolves in the resolver and fails to re-derive in the validator →
// ASSERTION_NOT_SUPPORTED → the native document is silently withheld. That is
// live on `main` today, it is OUT OF SCOPE for F5-d, and it is filed in RELAY
// rather than fixed here, because folding it in is a behaviour change to the
// resolver on the clinical path and needs its own proof.
//
// ⚠️ AND THE DUPLICATION LIST IS THREE, NOT TWO — an adversarial pass caught
// this note being short by one. `isStrictIsoDate` also has a THIRD copy at
// note-template-docx/renderer.ts:883, outside this package entirely. None of
// the three is folded in today; enumerating them is the point, because "the
// duplication is seen" is a claim that decays the moment a copy is missed.
// ============================================================================

import type { EncounterFact, SemanticMapping, TemplateField } from './ir';
import { parseExplicitNumberAndUnit } from './encounter-facts';
import { canonicalConcept } from './concept-registry';

export function isStrictIsoDate(value: string): boolean {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

export function exactOption(
  field: TemplateField,
  value: string,
): { value: string; displayText: string; ordinal: number } | null {
  return (
    field.allowedOptions.find(
      (option) => option.value === value || option.displayText === value,
    ) ?? null
  );
}

/**
 * The value this field must carry if it cites this fact — or `null` when the
 * fact cannot support a renderable value for this field at all.
 *
 * A `null` return is a REFUSAL and must be honoured as one: a writer that sees
 * null leaves the field blank with a named reason. It must never fall back to
 * some other value, because "some other value" is precisely the defect this
 * module was extracted to remove.
 *
 * ⚠️ THE RETURN TYPE IS PART OF THE CONTRACT, NOT AN IMPLEMENTATION DETAIL.
 * A `number` field returns a NUMBER and a `narrative_text` field returns a
 * STRING, and note-template-docx/renderer.ts:778-824 independently refuses the
 * wrong one with FIELD_VALUE_INVALID. So a caller that stringifies this result
 * breaks the renderer even where it satisfies the validator. Write it through
 * unchanged.
 *
 * `mapping` is OPTIONAL because only the `measurement` branch consults it (for
 * unitPolicy); every other kind derives from the fact alone. A `measurement`
 * field with no mapping REFUSES rather than guessing a unit policy — there is
 * no safe default, and the validator, which always has the mapping, would
 * refuse the guess anyway.
 *
 * ⚠️⚠️ **"WRITE IT THROUGH UNCHANGED" IS SOUND FOR FIVE OF THE SEVEN KINDS AND
 * WRONG FOR TWO.** This function was born COMPARE-ONLY inside the validator,
 * where a return value is only ever `===`-tested. Making it public made its
 * return a WRITE-SIDE contract, and for two kinds that contract is incomplete.
 * Both were found by an adversarial pass; both are stated here rather than
 * papered over, because the previous version of this docstring told a caller to
 * do something that produces a blocking issue and a thrown render:
 *
 *  - **`multi_select` returns a bare STRING, and every consumer needs
 *    `string[]`.** Writing it through yields MULTI_SELECT_TYPE_INVALID
 *    (blocking) plus `failTemplateDocxRender('FIELD_VALUE_INVALID')`. Compare
 *    against a `string[]` element; do not write the result.
 *  - **`single_select` returns the option's VALUE and drops its ORDINAL**,
 *    which is the half a writer needs: the validator checks
 *    `selectedOptionOrdinal` against the option (DROPDOWN_ORDINAL_MISMATCH) and
 *    the renderer resolves the option THROUGH the ordinal. Its sibling
 *    implementation, resolver/index.ts's `convertValue`, returns the PAIR for
 *    exactly this reason.
 *
 * So: any future writer beyond the measurement bridge must handle those two
 * kinds explicitly or refuse them, as `supportedNumeric` does. The refusal
 * lives on the CALLER today, which is the weaker place for it — recorded as a
 * known limit rather than claimed as a design.
 */
/**
 * Is this text nothing at all? — ruling #218's second half.
 *
 * ⚠️ AN EMPTY STRING IS NOT A VALUE, AND TREATING IT AS ONE IS WORSE THAN THE
 * DEFECT IT CAME FROM. #218 blanks the bare `other` escape hatch so a machine
 * token cannot print. But `''` then flowed through as an ordinary string: the
 * resolver minted `supported` / `direct_evidence_supported`, the validator
 * computed `populated = value !== null` and returned VALID with zero issues,
 * and the renderer emitted a **`filled`** proof over a control it had just
 * emptied — destroying the template's own placeholder prose and putting nothing
 * in its place.
 *
 * That is strictly worse than what it replaced. Printing `other` was wrong and
 * VISIBLE; a silent blank attested as filled is wrong and invisible, and it
 * also satisfies `fill-engine`'s `counts.filled > 0` — the only check standing
 * between a doctor and an empty document.
 *
 * ⚠️ ONE PREDICATE, IMPORTED BY BOTH DERIVERS. The resolver is a SECOND
 * implementation of this decision by design, and this house has already paid
 * for the two disagreeing about what a null means. They must not now disagree
 * about what an empty string means.
 *
 * The refusal is a `null`, which is the bounded clear: the field is COUNTED as
 * blank and the doctor is told, rather than being told it was filled.
 */
export function isEmptyText(value: string): boolean {
  return value.trim().length === 0;
}

export function deriveFieldValueFromFact(
  field: TemplateField,
  mapping: SemanticMapping | undefined,
  fact: EncounterFact,
): string | number | boolean | null {
  switch (field.kind) {
    case 'narrative_text':
      return typeof fact.value === 'string' && !isEmptyText(fact.value)
        ? fact.value
        : null;
    case 'single_select': {
      if (typeof fact.value !== 'string') return null;
      return exactOption(field, fact.value)?.value ?? null;
    }
    case 'multi_select':
      return typeof fact.value === 'string'
        ? exactOption(field, fact.value)?.value ?? null
        : null;
    case 'checkbox': {
      // ⚠️ #179(5) — A CHECKBOX ANSWERS FOR EXACTLY ONE SYMPTOM.
      //
      // This arm reads only `fact.polarity`; the finding is discarded, and
      // that is correct ONLY when the fact could not have been about a
      // different symptom. Before #179(2) it could: every clause in a system
      // shared `ros.<system>`, so one affirmed heartburn ticked nausea,
      // dysphagia and every other box — measured, and the exact class of false
      // assertion the owner reported.
      //
      // Symptom-granular concepts fix that BY CONSTRUCTION: a box mapped to
      // `ros.gastrointestinal.heartburn` is only ever reached by a heartburn
      // fact. What construction cannot rule out is a MIS-CONFIGURED box — one
      // whose declared scope covers several symptoms, where "affirmed" is
      // ambiguous between them. That is refused rather than guessed: a null
      // leaves the doctor's own default standing, and an unticked box a
      // clinician can tick is recoverable where a wrongly-ticked one is not.
      if (mapping?.conceptScope && mapping.conceptScope.length > 1) return null;
      return fact.polarity === 'affirmed'
        ? true
        : fact.polarity === 'denied'
          ? false
          : null;
    }
    case 'date':
      return typeof fact.value === 'string' && isStrictIsoDate(fact.value.trim())
        ? fact.value.trim()
        : null;
    case 'number': {
      const parsed = parseExplicitNumberAndUnit(fact.value);
      const number = fact.number ?? parsed.number;
      const unit = fact.unit ?? parsed.unit;
      return number !== null && unit === null ? number : null;
    }
    case 'measurement': {
      if (!mapping) return null;
      const parsed = parseExplicitNumberAndUnit(fact.value);
      const number = fact.number ?? parsed.number;
      const unit = fact.unit ?? parsed.unit;
      if (number === null) return null;
      if (mapping.unitPolicy === 'required' && !unit) return null;
      if (mapping.unitPolicy === 'forbidden' && unit) return null;
      return unit ? `${number} ${unit}` : number;
    }
  }
}

// ============================================================================
// LIST-VALUED NARRATIVE SECTIONS — the concepts that genuinely ACCUMULATE.
// ----------------------------------------------------------------------------
// A past medical history is "hypertension AND type 2 diabetes". A plan is
// "continue medications AND review in three months". Those are not competing
// answers to one question, and the resolver was calling every such pair
// `multiple_distinct_supported_values` -> FIELD_CONFLICT -> blocking. The owner's
// own form could not certify for exactly that reason.
//
// ⚠️ THIS IS AN ALLOWLIST BECAUSE THE DENYLIST FAILED OPEN, MEASURABLY. The first
// version of this asked `!concept.startsWith('measurement.')` — "everything that
// is not a measurement accumulates". Four independent refutation lenses broke it
// with concrete inputs, and the premise is simply false:
//
//   · `hpi.severity`  -> joined "moderate; severe"        (a severity is ONE value)
//   · `test.name`     -> joined two study types           (a study is ONE study)
//   · `test.*.result` -> joined "Normal; Abnormal"        (a contradiction, as prose)
//   · `exam.vascular` -> the SAME joined text in a "Right" control and a "Left"
//                        control, laterality discarded, so the right-leg field
//                        asserted the left leg's reflux. Zero blocking issues.
//   · `medication.dose` via the mapping editor -> joined "10 mg; 20 mg"
//
// Every one of those printed onto a doctor's form with nothing blocking, and
// every one was a `FIELD_CONFLICT` before. A denylist also cannot be completed:
// `updateTemplateTwinMappings` does not registry-check, so an edited mapping can
// carry ANY string, and each concept the registry gains later joins by default.
// An allowlist fails closed — a new concept conflicts until somebody decides it
// accumulates, which is the direction this decision should fail in.
//
// ⚠️ AND `exam.*` / `test.*` ARE DELIBERATELY ABSENT. One lens proposed including
// them; two others demonstrated the harm above with concrete inputs. A
// demonstration outranks a suggestion, so they conflict until a per-region or
// per-study concept exists to bind them safely.
//
// ⚠️ MEASUREMENTS ARE EXCLUDED BY GROUND, NOT BY SPELLING. `canonicalConcept`
// runs FIRST: `exam.vascular.diameter` is a registry SYNONYM of
// `measurement.diameter` and IS a measurement, and concept-registry.ts's own
// docstring records that a raw `startsWith('measurement.')` test already shipped
// this bug once. NFKC first as well, matching the fact matcher — a full-width
// `\uFF4Deasurement.diameter` matches ASCII facts and must not classify differently.

/** Separator for a joined narrative section. */
export const NARRATIVE_LIST_SEPARATOR = '; ';

/**
 * ⚠️ #313 — THE TWO REASON TOKENS A SUPPORTED NARRATIVE CAN CARRY FROM ITS OWN
 * EVIDENCE, DECLARED ONCE. The resolver mints them; the bullet distribution
 * pass both READS them (a group is distributed only from one of these, or the
 * mixed-polarity token) and WRITES them (each rewritten bullet carries the one
 * its own citation earns). Two string literals in two files is how a pass
 * silently stops matching the thing it was written to find.
 */
export const DIRECT_EVIDENCE_SUPPORTED_REASON = 'direct_evidence_supported' as const;
export const LIST_VALUED_NARRATIVE_JOINED_REASON = 'list_valued_narrative_joined' as const;

/**
 * Canonical concepts whose clinical shape is a SECTION that accumulates several
 * facts, rather than a slot holding one answer.
 *
 * Exact canonical strings only — no prefixes, no patterns. A prefix rule is how
 * `exam.*` and `test.*` leaked in.
 */
export const ACCUMULATING_NARRATIVE_CONCEPTS: ReadonlySet<string> = new Set([
  'assessment',
  'chief_complaint',
  'past_medical_history',
  // #246 family 1 — a surgical history is a LIST, exactly as the medical one
  // is. Without this a form with three "Past Surgical History" bullets takes
  // one procedure and drops the rest.
  'past_surgical_history',
  'family_history',
  'social_history',
  'plan',
  'medication',
  'allergy',

  // ⚠️ #319 REGISTRY-2 — THE TWO OPERATIVE-NOTE SECTIONS THAT ACCUMULATE.
  // A colonoscopy names several findings ("a sigmoid polyp AND scattered
  // diverticulosis AND normal mucosa to the cecum") and several recommendations
  // ("repeat surveillance in five years AND a high-fibre diet AND follow the
  // polyp pathology"). Those are one section holding a LIST, not competing
  // answers to one slot — exactly the past_medical_history / plan shape above.
  // The SINGLE procedure.* concepts are absent here, so a second
  // `procedure.performed` fact fails closed to FIELD_CONFLICT rather than
  // silently joining two procedures into one line.
  // ⚠️ REGISTRY-3 (#323) — procedure.specimens ALSO accumulates: a colonoscopy
  // sends several biopsies to pathology. The other four new concepts
  // (bowel_prep, extent_of_exam, estimated_blood_loss, complications) are SINGLE
  // and stay absent.
  'procedure.findings',
  'procedure.recommendations',
  'procedure.specimens',

  // ⚠️ #159(b) — THE ENTITY-NAMING SUB-CONCEPTS, AND ONLY THOSE **TWO**.
  // A field the doctor maps to `allergy.substance` is an ALLERGY LIST and must
  // accumulate, exactly as a field mapped to bare `allergy` does. Without these
  // rows the second allergen becomes `multiple_distinct_supported_values` and
  // the section conflicts instead of listing.
  //
  // ⚠️ AND `family_history.condition` WAS HERE UNTIL THE ADVERSARIAL PASS
  // MEASURED WHAT IT DOES. A condition is meaningless without its RELATIVE, and
  // the relation travels on a SEPARATE fact (`family_history.relation`), so no
  // code path can bind them. Driven end to end: two entries — Mother/Diabetes,
  // Father/Hypertension — render `"Diabetes; Hypertension"`, `supported`,
  // `valid:true`, ZERO blocking issues. The WHO the doctor dictated is
  // destroyed, and on a form with per-relation fields BOTH print the same
  // joined text.
  //
  // That is precisely the shape this file's own header bans `exam.*` for — "the
  // SAME joined text in a 'Right' control and a 'Left' control, laterality
  // discarded... Zero blocking issues." A discriminator that cannot be carried
  // is not a discriminator, and an honest blank beats a lossy assertion on a
  // document somebody signs.
  //
  // FILED, NOT BUILT: relation-binding as a DECLARED COMPOSITION — relative +
  // condition, template-owned, zero NLP. Same family as DECLARED DENIAL TEXT.
  // Until it exists, a family-history field stays where `main` left it.
  //
  // ⚠️ AND THE ATTRIBUTE MEMBERS ARE ABSENT ON PURPOSE. `medication.dose`,
  // `.route`, `.frequency`, `allergy.reaction`, `family_history.relation` and
  // every `social_history.*` are SINGLE-VALUED: a dose field holds one dose, a
  // Tobacco field holds one status. `gate-list-valued-narrative-sections`'s arm
  // "refuses to join medication.dose" exists because four refutation lenses
  // demonstrated a dose field printing "10 mg; 20 mg" onto a doctor's form with
  // nothing blocking. These three rows must never grow into the attributes.
  'allergy.substance',
  'medication.name',
]);

/**
 * Whether this (field, mapping) is a narrative SECTION that accumulates facts.
 *
 * Deliberately conservative: prose fields only. A `single_select` bound to
 * `allergy` still cannot hold two answers, so it keeps conflicting.
 */
export function isListValuedNarrative(
  field: TemplateField,
  mapping: SemanticMapping | undefined,
): boolean {
  if (field.kind !== 'narrative_text') return false;
  // Repeating rows already have their own accumulating path (rowPrototypeValue).
  if (field.rowPrototype) return false;
  const raw = mapping?.clinicalConcept ?? '';
  if (!raw.trim()) return false;
  // NFKC first (the fact matcher's normalisation), then canonicalise synonyms.
  const canonical = canonicalConcept(raw.normalize('NFKC'));
  return ACCUMULATING_NARRATIVE_CONCEPTS.has(canonical);
}

/**
 * THE joined value for a list-valued narrative, composed from the cited facts.
 *
 * Built out of `deriveFieldValueFromFact` — the very function the validator
 * re-derives with — so the two cannot disagree. Order follows the cited facts;
 * exact repeats collapse (a section should not read "Hypertension;
 * Hypertension").
 *
 * ⚠️ RETURNS NULL — MEANING "REFUSE THE JOIN" — RATHER THAN A PARTIAL SECTION.
 * Every caller treats null as "fall through", which lands on the conflict the
 * join was avoiding. That is the safe direction: a blocked fill is visible and a
 * quietly incomplete history is not. Two refusals are load-bearing:
 *
 *   · ANY cited fact that does not derive. Skipping it would drop clinical
 *     content from a section the note presents as complete — and the validator
 *     would accept it, because it re-derives with this same function.
 *   · MORE THAN ONE laterality among the cited facts. `projectEncounterFacts`
 *     emits one coarse concept per exam system and the laterality rides on the
 *     FACT, so a join would silently merge a left-leg and a right-leg finding
 *     into one unattributed string. The resolver's own laterality guard only
 *     fires when `mapping.laterality === 'required'`, and narrative mappings are
 *     `optional` or null — so this is the only thing standing there.
 */
export function joinListValuedNarrative(
  field: TemplateField,
  mapping: SemanticMapping | undefined,
  facts: ReadonlyArray<EncounterFact>,
): string | null {
  const lateralities = new Set(
    facts
      .map((fact) => fact.laterality)
      .filter((side) => side !== 'not_applicable' && side !== 'unknown'),
  );
  if (lateralities.size > 1) return null;

  const parts: string[] = [];
  for (const fact of facts) {
    const derived = deriveFieldValueFromFact(field, mapping, fact);
    if (derived === null) return null;
    const text = String(derived).trim();
    if (!text) continue;
    if (!parts.includes(text)) parts.push(text);
  }
  return parts.length > 0 ? parts.join(NARRATIVE_LIST_SEPARATOR) : null;
}
