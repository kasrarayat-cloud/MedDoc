// ============================================================================
// THE ONE RULE THAT DECIDES WHETHER A FACT SATISFIES A MAPPING.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE EXISTS BECAUSE THERE WERE THREE COPIES OF IT, AND THEY DISAGREED.
//
// Before this module, `factMatchesMapping` lived in `validation/index.ts`, a
// byte-copy of its pre-#179 self lived in `bridge-evidence.ts`, and
// `resolver/index.ts` carried a third open-coded form. #179 changed ONE of the
// three. Measured across the full (mapping.temporality x fact.temporality)
// matrix, the bridge and the resolver each disagreed with the validator in
// exactly 3 cells — every one of them at `mapping.temporality === null`.
//
// The consequence was not a wrong value; it was a WITHHELD DOCUMENT. The
// resolver filled a field and CITED its fact, the validator then rejected that
// same citation as SOURCE_FACT_CONCEPT_MISMATCH (blocking), and
// `fill-engine.ts` turned that into `render: null` — the doctor's own form was
// not produced at all, and `native-export.ts` fell back to the generic styled
// export.
//
// ⚠️ AND EACH FILE SAID IT WAS THE SHARED ONE. `validation/index.ts` carried
// "ONE IMPLEMENTATION, SHARED BY BOTH MATCH PATHS. A second copy would drift
// the day either is fixed" while being one of three; `bridge-evidence.ts`'s own
// header said it applies "the validator's own rule ... so it can only ever cite
// a fact the validator will accept". A comment asserting a shared rule that is
// not shared is worse than no comment: it answers the question a reader would
// otherwise go and check.
//
// ⚠️ IT IS A LEAF, DELIBERATELY, AND THAT CONSTRAINS ITS IMPORTS TO `import
// type`. `bridge-evidence.ts` had exactly one import before this change and it
// was type-only. Importing `validation/index.ts` instead of extracting would
// have pulled zod, encounter-facts, field-value-derivation, semantic-mapping,
// denial-contract and practice-default into a module that had no runtime
// dependencies at all. Anything added here must keep that property.
// ============================================================================

import type { EncounterFact, SemanticMapping } from './ir';
// ⚠️ THE ONE RUNTIME IMPORT, AND THE LEAF PROPERTY SURVIVES IT. `ros-lexicon`
// imports only `concept-segment`, which imports nothing — both are pure data
// and string work, no zod, no db, no framework. `bridge-evidence` therefore
// still pulls in no graph of consequence.
import { isUnnamedRosConcept } from './ros-lexicon';

/**
 * NFKC, trimmed, lower-cased — the one spelling comparison for concepts.
 *
 * Moved verbatim from `validation/index.ts`, where it was one of three
 * identical private copies (the others in `resolver/index.ts` and
 * `procedure-date.ts`). They agreed, which is exactly why nothing reported
 * them: identical copies drift silently, and only on the day one is fixed.
 */
export function normalizeConcept(value: string): string {
  return value.normalize('NFKC').trim().toLocaleLowerCase('en-US');
}

/**
 * ⚠️ WHAT A NULL MAPPING TEMPORALITY ACCEPTS — AND THIS IS THE ONE LINE THAT
 * CARRIES THE WHOLE QUESTION.
 *
 * `'any'`  — a mapping that declares no tense accepts a fact in any tense.
 *            This is what `origin/main` ships, what the resolver and the
 *            bridge have always meant, and what is restored here.
 *
 * ⚠️ PR #985 SET THIS TO `'current'` IN THE VALIDATOR ONLY, CITING `#179(6)`.
 * That part number has NO RECORDED CONTENT. Measured across the ledger head
 * and every archive with a control that discriminates — `laterality` 17 hits
 * in 3 files, `scaffolded` 36, `unmentionedPolicy` 11, `conceptScope` 3 —
 * `temporality` scores ZERO, in any ruling, ever. #179's own body states it:
 * "Parts 4 and 6 are not described here because this session was not given
 * their content."
 *
 * So the change is reverted to the proven meaning rather than propagated to the
 * other two readers, because a clinical matching rule may not rest on an
 * authority nobody can produce. The question is filed for the owner at
 * `docs/foundation/board/179-REPAIR-OWNER-QUESTIONS.md`.
 *
 * ⚠️ AND #179(6)'s STATED INTENT IS NOT ABANDONED BY THIS. "The patient denies
 * chest pain must not be contradicted by chest pain the patient had in 2019"
 * is a claim about ROS SCAFFOLD CLAUSES, and it is delivered by declaring
 * `temporality: 'current'` ON THOSE MAPPINGS — narrow, explicit, and visible in
 * the mapping a doctor confirms. Redefining null globally reached every field
 * of every template instead, including Past Medical History and Family
 * History, whose facts are `historical` BY CONSTRUCTION
 * (`encounter-facts/index.ts`) — so the rule blanked, and then withheld, the
 * very fields it was never aimed at.
 *
 * If the owner confirms he ruled (6), THIS CONSTANT IS THE EDIT — one line,
 * here, and all eight call sites move together.
 */
const NULL_TEMPORALITY_MEANS: 'any' | 'current' = 'any';

/**
 * ⚠️ THE TENSE A *SYNTHESISED* FACT CARRIES — A DIFFERENT QUESTION FROM THE ONE
 * ABOVE, AND THEY MUST NOT SHARE AN ANSWER.
 *
 * Five call sites build a fact that did not come from the transcript — an
 * approved practice default, a clinician's correction, a clinician's inserted
 * text, a verified-note selection, an injected procedure date. Each hand-rolled
 * the identical ternary, and `procedure-date.ts` had written this function out
 * longhand. They must carry a tense their own mapping will accept, or the fact
 * they synthesise blocks the document it was created to fill.
 *
 * `'current'` is right here on its own merits and NOT because of the constant
 * above: a fact asserted now, by a person, about this encounter, is present
 * tense. That stays true whichever way the owner rules the matcher.
 *
 * ⚠️ COLLAPSING THE TWO WOULD BE THE `isRegisteredConcept` MISTAKE. One
 * predicate answering two questions is how a change aimed at one silently moves
 * the other; here it would mean an owner ruling about MATCHING quietly
 * re-tensed every synthesised fact in the system.
 */
export function requiredFactTemporality(
  mapping: Pick<SemanticMapping, 'temporality'>,
): EncounterFact['temporality'] {
  return mapping.temporality && mapping.temporality !== 'any'
    ? mapping.temporality
    : 'current';
}

/**
 * Does the fact's tense satisfy the mapping's declared tense?
 *
 * An explicit `'any'` accepts everything. An explicit tense demands that tense.
 * A NULL declaration means whatever `NULL_TEMPORALITY_MEANS` says — see the
 * note there, which is where the decision lives.
 */
export function temporalityMatches(
  fact: Pick<EncounterFact, 'temporality'>,
  mapping: Pick<SemanticMapping, 'temporality'>,
): boolean {
  if (mapping.temporality === 'any') return true;
  if (mapping.temporality === null) {
    return NULL_TEMPORALITY_MEANS === 'any' || fact.temporality === 'current';
  }
  return fact.temporality === mapping.temporality;
}

/**
 * Does the fact's CONCEPT satisfy the mapping — by declared scope if there is
 * one, otherwise by the approved concept set?
 *
 * ⚠️ #179(3) — A DECLARED SCOPE MATCHES BY SET MEMBERSHIP AND IS CHECKED FIRST.
 * A scaffolded clause covers a named set of symptom concepts; a fact satisfies
 * it only by being IN that set. No text is compared, here or anywhere else.
 *
 * ⚠️ THE SCOPE REPLACES `clinicalConcept`, IT DOES NOT WIDEN IT. Falling
 * through to the concept check as well would let a system-level concept satisfy
 * a clause that scopes three of its fourteen symptoms — the defect #179(3)
 * exists to end.
 */
export function conceptMatches(fact: EncounterFact, mapping: SemanticMapping): boolean {
  const factConcept = normalizeConcept(fact.concept);

  // ⚠️ #179(1) — AN UNNAMED ROS CONCEPT CANNOT ANSWER A CLAUSE THAT NAMES
  // SYMPTOMS. `ros.<system>.other` carries a real finding the doctor stated, so
  // it must reach the note somewhere — but it names a symptom outside the
  // lexicon, and letting it satisfy a specific clause asserts that "the patient
  // denies heartburn, dysphagia, odynophagia" was contradicted by a finding
  // none of those three words name. #179's own body rules this; nothing
  // implemented it until now.
  const unnamed = isUnnamedRosConcept(fact.concept);

  if (mapping.conceptScope && mapping.conceptScope.length > 0) {
    // A declared scope is a list of NAMED symptoms by definition, so an unnamed
    // concept is excluded from it — the ruling's literal words.
    if (unnamed) return false;
    const scope = new Set(mapping.conceptScope.map(normalizeConcept));
    return scope.has(factConcept);
  }

  if (!mapping.clinicalConcept) return false;

  // ⚠️ AND THE LIVE ROUTE WAS `approvedSynonyms`, NOT `conceptScope` — a guard
  // aimed only at scope would have landed entirely in dark code and changed
  // nothing observable. An unnamed concept matches ONLY a mapping whose own
  // concept IS that concept (a form's literal "Other:" row); a synonym list is
  // exactly how a specific-symptom clause silently acquired `other`.
  if (unnamed) return normalizeConcept(mapping.clinicalConcept) === factConcept;

  const concepts = new Set(
    [mapping.clinicalConcept, ...mapping.approvedSynonyms].map(normalizeConcept),
  );
  return concepts.has(factConcept);
}

/**
 * The whole rule: concept AND tense.
 *
 * ⚠️ THE TWO HALVES ARE EXPORTED SEPARATELY BECAUSE THE RESOLVER NEEDS THEM
 * APART, AND THAT IS LOAD-BEARING RATHER THAN TIDY. The resolver asks the
 * concept question first (`conceptCandidates.length === 0` — the ONE site that
 * earns #191's kept practice default, per `missingResolution`'s own parameter
 * doc) and the tense question second (`temporalCandidates.length === 0` — a
 * DEFERRAL, which must NOT earn it). A single combined predicate cannot tell
 * those two apart, and collapsing them would silently re-route kept defaults.
 */
export function factMatchesMapping(fact: EncounterFact, mapping: SemanticMapping): boolean {
  return conceptMatches(fact, mapping) && temporalityMatches(fact, mapping);
}
