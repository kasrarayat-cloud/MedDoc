/**
 * AUTO-CERTIFICATION ELIGIBILITY — which proposals may confirm themselves.
 *
 * OWNER RULING 2026-08-17: auto-certification by AI is the DEFAULT path. The
 * doctor uploads and runs visits; the model confirms its own proposals and the
 * template certifies, provided the round-trip proof passes.
 *
 * ⚠️ THE ONE THING THE MODEL MAY NEVER ASSERT IS LATERALITY. Left/Right on an
 * imaging report is the field whose loss deleted content from a signed record
 * earlier this month, and this house's standing rule is fail-closed on it. So
 * the ruling's structural-resolution clause governs:
 *
 *   A laterality-critical mapping auto-confirms ONLY when the DOCUMENT'S OWN
 *   STRUCTURE pins the side. That is the document asserting its side —
 *   deterministic, not a model judgement. Anything else stays unconfirmed and
 *   is named in the needs-review banner.
 *
 * The distinction is not cosmetic. On the customer form this was measured
 * against, it separates cleanly:
 *
 *   "Right deep venous system Choose an item."  -> structural, auto-confirms
 *   "Left Choose an item. is Choose an item."   -> structural, auto-confirms
 *   "SIDE OF EXAM: Choose an item."             -> NO anchor, refuses, named
 *
 * Six of seven resolve from the document; one genuinely does not, because
 * nothing in the document says which side that exam was. A model guessing there
 * would be inventing a clinical fact.
 */

/** Why a mapping was (or was not) auto-confirmed. Recorded on the audit row. */
export type AutoConfirmProvenance =
  /** The document's own structure pinned it — deterministic, no model judgement. */
  | 'structural'
  /** The model proposed it and it carries no laterality risk. */
  | 'model'
  /**
   * The field has NO AUTOMATIC SOURCE and renders blank — a human types it at
   * fill time (the technologist on shift, the referring physician).
   *
   * ⚠️ DELIBERATELY NOT NAMED 'manual'. `sourceType === 'manual'` is a settled
   * term for WHAT THE FIELD IS. This enum answers a different question — WHO
   * CONFIRMED THIS MAPPING — and for these rows the answer is THE MODEL.
   * Measured on the owner's production template before this was written: all 5
   * manual rows carry `proposedByModel` and ZERO carry an `approvedById`.
   * Labelling them 'manual' would have written a human attestation into an
   * audit row that no human ever made.
   */
  | 'blank_by_design';

export interface AutoConfirmDecision {
  confirm: boolean;
  provenance: AutoConfirmProvenance | null;
  /** Doctor-facing, PHI-free. Present exactly when confirm === false. */
  reason: string | null;
}

/**
 * ⚠️ WORD-BOUNDARY MATCHING, NOT SUBSTRING. "left" appears inside "cleft" and
 * "Bilateral" contains "lateral" — a substring test is the recorded trap family
 * and would silently anchor a field the document never sided.
 *
 * `bilateral` counts as an anchor: it names BOTH sides explicitly, which is a
 * determinate statement about laterality, not an absence of one.
 */
const SIDED_TOKEN = /\b(right|left|bilateral)\b/i;

/**
 * Does the document itself pin this field's side?
 *
 * @param originalLabel the field's own label, as the .docx wrote it
 * @param sectionHeading the nearest enclosing heading, when the compiler
 *        supplies one. On forms whose fields carry the side in their own label
 *        this is null and the label alone decides — which is the shape the
 *        measured customer form actually has.
 */
export function hasStructuralLateralityAnchor(
  originalLabel: string | null | undefined,
  sectionHeading?: string | null,
): boolean {
  // ⚠️ THE LABEL IS CHECKED FIRST AND IS SUFFICIENT. A field literally named
  // "Right deep venous system" is sided by the document more directly than by
  // any heading above it.
  if (originalLabel && SIDED_TOKEN.test(originalLabel)) return true;
  if (sectionHeading && SIDED_TOKEN.test(sectionHeading)) return true;
  return false;
}

export interface AutoConfirmCandidate {
  originalLabel: string | null;
  /** Field-definition criticality. 'laterality' is the fail-closed class. */
  criticality: string | null;
  /** 'extraction' | 'verified_note_selection' | 'manual' */
  sourceType: string | null;
  /** Whether a clinical concept is present. Required for non-manual fields. */
  hasClinicalConcept: boolean;
  /**
   * ⚠️ #208 — THE DECLARED SCOPE, BECAUSE AUTO-CONFIRM USED TO CERTIFY ONE IT
   * HAD NEVER LOOKED AT. `planAutoConfirm` spreads the whole mapping into
   * `status: 'certified'`, so a model-proposed `conceptScope` was carried
   * through by a decision function that could not see it — silently accepted,
   * which is exactly what the ruling forbids. A scope is a MAPPING the model
   * may propose, so it travels the same route as `clinicalConcept`: proposed,
   * validated, SURFACED, confirmed.
   */
  conceptScope?: readonly string[] | undefined;
  /** Nearest enclosing sided heading, when the compiler supplies one. */
  sectionHeading?: string | null;
}

/**
 * THE DECISION, per mapping. Pure — no I/O, no model call, fully testable.
 *
 * ⚠️ ORDER MATTERS AND IS DELIBERATE. The laterality refusal is evaluated
 * BEFORE the generic model path, so a laterality field can never fall through
 * into 'model' provenance by satisfying the ordinary conditions.
 */
export function decideAutoConfirm(c: AutoConfirmCandidate): AutoConfirmDecision {
  // ⚠️ OWNER RULING, #247 — A `visit_metadata` MAPPING NEVER AUTO-CONFIRMS, AND
  // IT IS REFUSED FIRST SO NO LATER ARM CAN CONFIRM IT BY SATISFYING SOMETHING
  // ELSE.
  //
  // "A control that prints a patient's NAME requires a human to have seen it."
  // Every other class this function confirms puts CLINICAL content on the page,
  // and a wrong clinical value is wrong in a way the doctor reading the note
  // can see. A wrong IDENTITY is different in kind: it is the one error that
  // makes the whole document belong to somebody else, and nothing further down
  // the page contradicts it.
  //
  // ⚠️ AND THE MACHINE HAS NO STANDING HERE. Auto-confirm's whole argument is
  // that the model may accept a mapping the DOCUMENT decided. It did decide
  // this one — `classifyFieldSource` reads the label — so the model would be
  // confirming a proposal nobody ever doubted, and the value of the human act
  // is not the concept check. It is that a person looked at a control that
  // prints a patient's name and agreed it should.
  //
  // ⚠️ THIS IS A REFUSAL TO CONFIRM, NOT A REFUSAL TO CERTIFY. The doctor's
  // ordinary confirm in the review workspace carries it — ruling #247 declines
  // a fourth confirm act — so the template still certifies in one sitting. What
  // it costs is exactly one click that a human has to make.
  if (c.sourceType === 'visit_metadata') {
    return {
      confirm: false,
      provenance: null,
      reason:
        'this control prints a value from the patient record — confirm it yourself',
    };
  }

  // A manual field has no concept BY CONSTRUCTION — nothing dictates who the
  // technologist on shift was. It is ready when attested, renders blank.
  if (c.sourceType === 'manual') {
    return { confirm: true, provenance: 'blank_by_design', reason: null };
  }

  // Certification requires a concept for every non-manual field. Without one
  // there is nothing to confirm, whatever else is true.
  if (!c.hasClinicalConcept) {
    return {
      confirm: false,
      provenance: null,
      reason: 'no clinical concept was proposed for this field',
    };
  }

  // ⚠️ #208 — A DECLARED SCOPE IS CONFIRMED, NEVER SILENTLY ACCEPTED.
  //
  // The model may PROPOSE a scope; it may not have one certified on its own
  // say-so. The parse layer refuses unregistered and unnamed tokens, so a scope
  // arriving here through the model path is already well-formed — but a mapping
  // can also be hand-built or restored, and this is the seam that decides
  // whether a human ever saw it. An entry that cannot satisfy any fact would
  // otherwise certify a clause whose coverage claim is undeliverable.
  //
  // ⚠️ IT DECLINES RATHER THAN REPAIRS, and the reason is #208's own shape:
  // shrinking a scope here would change what a clause CLAIMS TO COVER without
  // the doctor seeing it — the confirm list shows the scope precisely so the
  // claim is read before it is agreed to.
  const badScope = (c.conceptScope ?? []).filter(
    (concept) => !isRegisteredConcept(concept) || isUnnamedRosConcept(concept),
  );
  if (badScope.length > 0) {
    return {
      confirm: false,
      provenance: null,
      reason:
        `the declared scope names ${badScope.length === 1 ? 'a concept' : 'concepts'} ` +
        `no fact can carry (${badScope.slice(0, 3).join(', ')}) — confirm it by hand`,
    };
  }

  // ⚠️ LATERALITY IS RECORDED HERE, NOT GATED HERE — AMENDED, RULING #127.
  //
  // The first version REFUSED to auto-confirm any laterality-critical field the
  // document did not structurally side. That was wrong, and the measurement is
  // what corrected it: CERTIFICATION NEVER ENCODES A SIDE. A mapping declares
  // what a field MEANS; the side is derived per visit from the dictation, every
  // time, by `defaultLaterality()` — a word-boundary regex over the dictated
  // text, with no model judgement anywhere in it.
  //
  // Fail-closed lives DOWNSTREAM, at fill, and is asserted rather than assumed:
  //   resolver/index.ts:551  laterality 'required' + unknown  -> needs_clinician_input
  //                          two sides for one field          -> conflict, no value
  //   bridge-fill.ts:206     "a right-leg value simply cannot fill a left-leg row"
  //   row-laterality.test.ts CROSS-LEG CANARY, both directions refused
  //
  // ⚠️ AND THE HISTORY IS THE ARGUMENT. resolver/index.ts:462-468 records that
  // judging laterality at RESOLVE time made spurious conflicts out of unrelated
  // sentences and "blocked certification on a field about which the encounter had
  // said nothing selectable. Seven fields, every run." Those are the same seven
  // fields this gate would have blocked. Re-adding an upstream laterality gate
  // re-creates a defect this codebase already diagnosed and moved downstream.
  //
  // Provenance is still recorded, because HOW a mapping was confirmed belongs in
  // the audit trail even when it does not change the outcome.
  if (c.criticality === 'laterality') {
    return {
      confirm: true,
      provenance: hasStructuralLateralityAnchor(c.originalLabel, c.sectionHeading)
        ? 'structural'
        : 'model',
      reason: null,
    };
  }

  return { confirm: true, provenance: 'model', reason: null };
}

/* ──────────────────────────────────────────────────────────────────────────
 * THE PLANNER. Kept in this module BECAUSE IT IS PURE and this module imports
 * nothing — so it is testable without dragging next-auth, and by extension the
 * whole Next runtime, into a unit test. The audit writer lives next door in
 * auto-certify.ts, which does the I/O.
 * ────────────────────────────────────────────────────────────────────────── */
import { isRegisteredConcept } from './concept-registry';
import { isUnnamedRosConcept } from './ros-lexicon';
import type { TemplateTwinWorkspace } from './client-types';
import type { SemanticMapping } from './ir';

export interface AutoConfirmOutcome {
  /** The mapping set to persist. */
  mappings: SemanticMapping[];
  /** Fields the engine declined, with the reason, for the needs-review banner. */
  declined: Array<{ label: string; reason: string }>;
  /** provenance -> count. Recorded on the audit row and in the log line. */
  provenanceCounts: Record<AutoConfirmProvenance, number>;
}

/**
 * PURE. Decide the whole mapping set. No I/O, so it is testable against a real
 * workspace shape without a database.
 *
 * ⚠️ IT MIRRORS `confirmed()` FROM THE MANUAL SCREEN RATHER THAN INVENTING A
 * SECOND SHAPE. Two writers producing "a confirmed mapping" differently is how
 * the manual and automatic paths drift until only one of them satisfies
 * MAPPINGS_NOT_READY. Same two demands: a concept except for manual, and
 * status 'certified'.
 */
export function planAutoConfirm(workspace: TemplateTwinWorkspace): AutoConfirmOutcome {
  const declined: AutoConfirmOutcome['declined'] = [];
  const provenanceCounts: Record<AutoConfirmProvenance, number> = {
    structural: 0,
    model: 0,
    blank_by_design: 0,
  };

  const mappings = workspace.fields.map(({ field, mapping }) => {
    // ⚠️ S3 — AN ALREADY-CERTIFIED ROW IS KEPT, NOT RE-DECIDED. A re-upload
    // transfers prior certified dispositions by identity (#274) and lands them
    // 'certified'; the doctor already confirmed those on the prior version, so
    // re-running decideAutoConfirm over them would (e.g. for a laterality or
    // scoped row) needlessly re-open a settled disposition — and for a
    // transferred row it must not. Auto-confirm only decides the REPROPOSED
    // remainder; the transfer is what carried the rest.
    if (mapping.status === 'certified') {
      return mapping;
    }
    const decision = decideAutoConfirm({
      originalLabel: field.originalLabel ?? null,
      criticality: field.criticality ?? null,
      sourceType: mapping.sourceType ?? null,
      hasClinicalConcept: Boolean(mapping.clinicalConcept),
      // #208 — the decision cannot judge what it is not given.
      conceptScope: mapping.conceptScope,
    });

    if (!decision.confirm) {
      declined.push({
        label: field.originalLabel ?? '(unnamed field)',
        reason: decision.reason ?? 'this field could not be confirmed automatically',
      });
      return mapping;
    }

    if (decision.provenance) provenanceCounts[decision.provenance] += 1;
    // ⚠️ THE CONCEPT IS NOT REWRITTEN, AND THAT IS THE POINT. `confirmed()` on the
    // manual screen takes a concept because the DOCTOR may be changing it there.
    // Auto-confirm changes nothing about meaning — it accepts the proposal as
    // proposed. The spread carries `clinicalConcept` through untouched.
    // (An earlier draft had a ternary here whose branches were identical: it
    // looked deliberate and did nothing.)
    return { ...mapping, status: 'certified' as const };
  });

  return { mappings, declined, provenanceCounts };
}
