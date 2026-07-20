// ============================================================================
// Layer 6 — Final polish (T-M4)
// ----------------------------------------------------------------------------
// Applies the fixable issues from Layer 5's critique to the draft,
// returning the polished SOAP. Unfixable critical issues (e.g. "no
// red-flag screening") are not auto-patched; the note is saved as-is
// with needsReview=true so the clinician sees the gap.
// ============================================================================

import {
  getTemplateTwinProviderOwnershipContext,
  recordTemplateTwinProviderNotApplicable,
  runTemplateTwinOwnedModelCompleteText,
} from "@/lib/template-twin/provider-ownership";
import { updateTemplateTwinSyntheticQaClaimBoundVisit } from "@/worker/staging-qa-mutation-fence";
import { logWorkerAudit } from "@/worker/worker-audit";
import { applyAdditiveReviewState } from "@/worker/finalize-review-state";
import {
  findNovelContentTerms,
  runPolishFidelityGate,
} from "./06b-polish-fidelity-gate";
import {
  classifyCritique,
  type CritiqueReport,
  type CritiqueIssue,
} from "./05-self-critique";
import { validateSoapStructure } from "./soap-structure-validator";
import {
  requiredSectionLabels,
  type ResolvedNoteTemplate,
} from "../note-templates/build-soap-prompt";
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from "../note-templates/system-default-template";

// TRANSCRIBE_MD_CLINICAL_MODEL — eval override (feat/fable5-eval); unset → default unchanged.
const MODEL = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || "claude-sonnet-4-6";

export interface Layer6Input {
  visitId: string;
  practiceId: string;
  userId: string | null;
  soapDraft: string;
  critique: CritiqueReport;
  /** Phase 1: the resolved template, so polish validates against ITS
   *  structure (not the fixed 4 SOAP headers). Defaults to the system
   *  default — whose labels ARE the 4 SOAP headers, so behavior is
   *  unchanged for non-customizing doctors. The polish prompt already
   *  preserves "the same markdown structure as the draft", so the model
   *  polishes in whatever structure the draft has. */
  noteTemplate?: ResolvedNoteTemplate;
}

export interface Layer6Output {
  soapFinal: string;
  needsReview: boolean;
  reviewReason: string | null;
  unfixable: CritiqueIssue[];
  /** 2026-06-11 fabrication gate — true when the polish output was
   *  rejected and soapFinal fell back to the pre-L6 draft. */
  polishRejected: boolean;
}

// ---------------------------------------------------------------------------
// L6 survival tuning (2026-07-02, the pre-registered follow-up from the
// 2026-06-11 reconciliation): under anchored generation, L5 routinely asks
// polish to ADD content the L4b verifier demoted to the suggestions lane —
// and the L6b gate rejects ANY addition by construction (iteration 1 closed
// the fixes channel deliberately). Applying those fixes rejected the ENTIRE
// polish on essentially every visit (17/17 in the 2026-07-02 QA matrix),
// losing the legitimate rewording fixes too. Partition BEFORE the model
// call: additive-class fixes are DEFERRED to the review banner (their
// content already sits in the adopt-flow lane); only rewording-class fixes
// are sent to tm_polish. The gate itself is untouched and remains the
// backstop for anything misclassified.
// Caution-first bias: a rewording fix wrongly deferred costs one cosmetic
// edit; an additive fix wrongly applied is exactly what the gate rejects.
// ---------------------------------------------------------------------------
// feat/structured-templates (2026-07-02): structured-fill verbs — "check the
// fatigue box", "mark option X", "fill in the BP cell" — are additive edits
// whose content words already exist in the draft as skeleton text, so the
// novel-term fallback misses them. Caution-first: a wrongly deferred fix
// costs one cosmetic edit; a checkbox flip that slips through is an
// unanchored clinical claim the deterministic L6b screen cannot see.
const ADD_VERB_RE =
  /\b(add|adds|adding|insert|include|includes|populate|append|restore|introduce|state|document|check|checks|checked|mark|marks|marked|tick|ticks|fill|fills|filled|select|selects)\b/i;
const REMOVAL_VERB_RE =
  /\b(remove|removes|delete|deletes|strike|drop|omit the|take out)\b/i;
// Instruction/editorial vocabulary that is "novel vs the draft" for nearly
// any fix text but carries no clinical payload — excluded before counting.
const EDITORIAL_TERMS = new Set([
  "apply",
  "applied",
  "described",
  "above",
  "below",
  "fix",
  "fixes",
  "issue",
  "issues",
  "auditor",
  "consolidate",
  "consolidated",
  "reword",
  "reworded",
  "rephrase",
  "rephrased",
  "merge",
  "merged",
  "reorder",
  "reordered",
  "shorten",
  "clarify",
  "clarified",
  "combine",
  "combined",
  "tighten",
  "deduplicate",
  "duplicate",
  "duplicated",
  "redundant",
  "repeated",
  "overlapping",
  "formatting",
  "format",
  "wording",
  "phrasing",
  "sentence",
  "sentences",
  "paragraph",
  "section",
  "sections",
  "heading",
  "headings",
  "bullet",
  "bullets",
  "line",
  "lines",
  "item",
  "items",
  "move",
  "moved",
  "single",
  "instead",
  "statement",
  "statements",
  "draft",
  "note",
]);

/** True when applying this fix would require content the draft lacks —
 *  the class the L6b gate rejects unconditionally. */
export function isAdditiveFix(draft: string, issue: CritiqueIssue): boolean {
  const fix = issue.suggested_fix ?? "";
  // Deletion fixes are gate-passable (deletions are explicitly allowed) and
  // safety-relevant (they REMOVE unsupported content) — never defer them,
  // even when the sentence also contains an add-verb ("remove X and add a
  // shorter form of Y" still nets toward removal; the gate backstops).
  if (REMOVAL_VERB_RE.test(fix)) return false;
  if (ADD_VERB_RE.test(fix)) return true;
  const novel = findNovelContentTerms([draft], fix).filter(
    (t) => !EDITORIAL_TERMS.has(t),
  );
  return novel.length >= 3;
}

export async function runLayer6Polish(
  input: Layer6Input,
): Promise<Layer6Output> {
  const { fixable: fixableAll, unfixable } = classifyCritique(input.critique);
  const deferredAdditive = fixableAll.filter((i) =>
    isAdditiveFix(input.soapDraft, i),
  );
  const fixable = fixableAll.filter((i) => !isAdditiveFix(input.soapDraft, i));
  // Phase 1: validate the polished note against the resolved template's
  // required sections. System default → the 4 SOAP headers → unchanged.
  const template: ResolvedNoteTemplate =
    input.noteTemplate ?? SYSTEM_DEFAULT_NOTE_TEMPLATE;
  const requiredSections = requiredSectionLabels(template);
  let soapFinal: string;
  // FIND-P1-016 (2026-05-14) — when the model edits the draft, the
  // output goes through the same SOAP-structure validator L4 uses.
  // Passthrough branch (fixable.length === 0) doesn't need re-validation
  // because L4 already validated `soapDraft` when it landed in the row.
  // On model-call validation fail, the layer still persists the raw
  // output and flips needsReview so a doctor can fix it manually; the
  // audit row gives operators a grep target for prompt regressions.
  let polishValidationFailReason: string | null = null;
  let polishRejected = false;
  const providerOwnershipActive =
    getTemplateTwinProviderOwnershipContext()?.scope === "VISIT_PIPELINE";

  if (fixable.length === 0) {
    if (providerOwnershipActive) {
      await recordTemplateTwinProviderNotApplicable({
        operation: "L6_POLISH",
        reasonCode: "NO_FIXABLE_CRITIQUE_WORK",
      });
      await recordTemplateTwinProviderNotApplicable({
        operation: "L6_FIDELITY_VERIFY",
        reasonCode: "POLISH_NOT_EXECUTED",
      });
    }
    // Nothing to auto-patch — the draft itself is our final note.
    // Still persist it so /visits/[id] renders soapFinal rather than
    // soapDraft (simpler UI state machine).
    soapFinal = input.soapDraft;
  } else {
    // 2026-06-11 fabrication-fix (a): immutable preamble, same discipline
    // as L4's unconditional rules. The PriMock57 full-chain eval proved
    // the polish step ADDS clinical content (contraindication reasoning,
    // referrals, red-flag narratives) when "applying" expansive critique
    // fixes — these rules override that, and the L6b gate below catches
    // whatever slips through anyway.
    const system = [
      "IMMUTABLE RULES — these override every other instruction below:",
      "1. You are a copy editor, not a clinician author. You may reword,",
      "   reorganize, and reformat ONLY content already present in the",
      "   draft.",
      "2. Do NOT introduce new clinical facts. Do NOT add, infer, or",
      "   expand clinical content of any kind — no new findings, symptoms,",
      "   exam results, diagnoses, differentials, contraindication or risk",
      "   reasoning, referrals, screenings or red-flag statements,",
      "   follow-up instructions, patient education, medications, or doses",
      "   — even if a suggested fix appears to call for them.",
      "3. If a fix requires information that is not in the draft, leave",
      "   the flagged area as-is and keep moving.",
      "4. Never flip a negation or change the clinical meaning of a",
      "   statement.",
      "",
      "You are editing a clinical SOAP note. A separate auditor has",
      "flagged specific issues; apply ONLY those fixes and return the",
      "complete revised SOAP note in the same markdown structure as the",
      "draft.",
      "",
      "Rules:",
      "- Preserve all clinical content that the auditor did not flag.",
      '- Apply each "suggested_fix" as closely as possible, using only',
      "  information already present in the draft.",
      "- Output ONLY the revised SOAP markdown. No preamble, no summary",
      "  of changes.",
    ].join("\n");

    const fixesText = fixable
      .map(
        (i, idx) =>
          `${idx + 1}. [${i.severity}] ${i.location}: ${i.description}\n    Fix: ${i.suggested_fix}`,
      )
      .join("\n");

    const user = [
      "Draft:",
      input.soapDraft,
      "",
      "Issues to apply (apply in order):",
      fixesText,
    ].join("\n");

    const { text } = await runTemplateTwinOwnedModelCompleteText({
      operation: "L6_POLISH",
      operationVersion: "soap-polish-v1",
      args: {
        practiceId: input.practiceId,
        visitId: input.visitId,
        userId: input.userId,
        purpose: "tm_polish",
        provider: "anthropic",
        model: MODEL,
        system,
        user,
        maxTokens: 8192,
        // Q2 fix-pack — polish is constrained edit ("apply these fixes").
        // Tightened from 0.2 to 0.1 so the same draft + critique produce
        // the same revised SOAP run-to-run.
        temperature: 0.1,
      },
    });
    soapFinal = text;

    // 2026-06-11 fabrication-fix (b) — L6b post-polish fidelity gate.
    // The L5 critique runs BEFORE this model call and structurally cannot
    // catch what it adds; the gate verifies the polished note introduces
    // no new clinical claims relative to the DRAFT (iteration 1: the
    // critique's suggested_fixes are deliberately NOT an allowance — the
    // re-measure proved L5 fixes carry encounter-ungrounded clinical
    // reasoning into the note; an additive fix now causes rejection).
    // FAIL-CLOSED: any violation OR any gate/verifier failure falls back
    // to the pre-L6 draft (the measured-clean artifact) — losing polish is
    // acceptable, gaining content is not. Empty output is exempt (it
    // cannot carry an addition; the structure validator owns that class).
    if (soapFinal.trim().length > 0) {
      const gate = await runPolishFidelityGate({
        practiceId: input.practiceId,
        visitId: input.visitId,
        userId: input.userId,
        draft: input.soapDraft,
        polished: soapFinal,
      });
      if (!gate.ok) {
        polishRejected = true;
        soapFinal = input.soapDraft;
        await logWorkerAudit({
          action: "L6_FABRICATION_REJECTED",
          targetType: "transcribe_visit",
          targetId: input.visitId,
          userId: input.userId,
          practiceId: input.practiceId,
          success: false,
          metadata: {
            layer: "L6",
            violationCount: gate.violationCount,
            kinds: gate.kinds,
            novelTermCount: gate.novelTermCount,
            gateError: gate.gateError,
            fellBackToDraft: true,
            // NO note content — counts + enum-class strings only.
          },
        });
      }
    } else if (providerOwnershipActive) {
      await recordTemplateTwinProviderNotApplicable({
        operation: "L6_FIDELITY_VERIFY",
        reasonCode: "EMPTY_POLISH_OUTPUT",
      });
    }

    // FIND-P1-016 — same validator L4 uses, now scoped to the resolved
    // template's required sections. Fail → keep raw output, flag the
    // validation reason so the reviewReason calculation below includes it
    // alongside the unfixable-criticals reason. Skipped on gate fallback:
    // the draft we fell back to was already L4-validated when it landed.
    if (!polishRejected) {
      const validation = validateSoapStructure(soapFinal, requiredSections);
      if (!validation.ok) {
        await logWorkerAudit({
          action: "MODEL_OUTPUT_VALIDATION_FAIL",
          targetType: "transcribe_visit",
          targetId: input.visitId,
          userId: input.userId,
          practiceId: input.practiceId,
          success: false,
          metadata: {
            layer: "L6",
            reason: validation.reason,
            outputLength: validation.outputLength,
            missingSections: validation.missingSections,
            // NO raw output — PHI surface.
          },
        });
        polishValidationFailReason = `Polish output didn't match expected markdown structure — manual review required (${validation.reason}).`;
      }
    }
  }

  // Surface unfixable critical issues as a review banner reason. The
  // fabrication-gate rejection (when present) or the FIND-P1-016
  // validation-fail reason prepends so the operator/clinician sees the
  // most urgent issue first. (Rejection and validation-fail are mutually
  // exclusive — validation is skipped on the gate-fallback path.)
  const polishRejectedReason = polishRejected
    ? "Auto-polish was rejected by the fabrication gate and not applied — the auditor-flagged fixes remain unapplied; review the draft."
    : null;
  const prefixReason = polishRejectedReason ?? polishValidationFailReason;
  // Survival tuning: deferred additive fixes still reach the doctor — their
  // content usually sits in the suggestions lane (adopt flow), so point there.
  const deferredReason =
    deferredAdditive.length > 0
      ? `Auto-polish deferred ${deferredAdditive.length} auditor fix${
          deferredAdditive.length === 1 ? "" : "es"
        } that would add content not in the draft — review the suggestions and draft before signing.`
      : null;
  const baseReason =
    unfixable.length > 0
      ? `Auto-polish could not fix ${unfixable.length} critical issue${
          unfixable.length === 1 ? "" : "s"
        }: ${unfixable.map((i) => i.description).join("; ")}`
      : !input.critique.safe_to_sign_without_review
        ? "Auditor flagged issues worth a quick review before signing."
        : null;
  const reviewReason =
    [prefixReason, deferredReason, baseReason].filter(Boolean).join(" ") ||
    null;

  const needsReview =
    unfixable.length > 0 ||
    deferredAdditive.length > 0 ||
    !input.critique.safe_to_sign_without_review ||
    polishValidationFailReason !== null ||
    polishRejected;

  await updateTemplateTwinSyntheticQaClaimBoundVisit({
    visitId: input.visitId,
    userId: input.userId ?? "",
    practiceId: input.practiceId,
    data: {
      soapFinal,
      // T-M14.1: immutable snapshot of the AI's final output. soapFinal
      // gets overwritten when the doctor edits; soapL6Original does not.
      // The sign-time capture hook reads this to record the
      // (original_ai, doctor_edited) pair into doctor_edit_patterns.
      // Always written alongside soapFinal so the two columns agree at
      // the end of a clean pipeline run.
      soapL6Original: soapFinal,
    },
  });

  // Review state is ADDITIVE (2026-06-13, #315 obs#1): an earlier layer may
  // already have flagged review with its own reason — most notably L4's
  // anchored-generation "all content moved out of section X" set-aside. A
  // direct `reviewReason` write here CLOBBERED that, so the doctor saw only
  // the L6 reason. Compose instead, so the banner shows EVERY reason the note
  // needs review (existing reason first — it's usually the more safety-
  // relevant one; applyAdditiveReviewState concatenates SQL-side, atomic).
  await applyAdditiveReviewState(
    input.visitId,
    { needsReview, reviewReason },
    { userId: input.userId ?? "", practiceId: input.practiceId },
  );

  return { soapFinal, needsReview, reviewReason, unfixable, polishRejected };
}
