// ============================================================================
// Layer 6 — Final polish (T-M4)
// ----------------------------------------------------------------------------
// Applies the fixable issues from Layer 5's critique to the draft,
// returning the polished SOAP. Unfixable critical issues (e.g. "no
// red-flag screening") are not auto-patched; the note is saved as-is
// with needsReview=true so the clinician sees the gap.
// ============================================================================

import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';
import { logAudit } from '@/lib/audit';
import { applyAdditiveReviewState } from '@/worker/finalize-review-state';
import { structureMismatchReason } from './structure-mismatch-reason';
import {
  findNovelContentTerms,
  runPolishFidelityGate,
} from './06b-polish-fidelity-gate';
import {
  classifyCritique,
  type CritiqueReport,
  type CritiqueIssue,
} from './05-self-critique';
import { validateSoapStructure } from './soap-structure-validator';
import {
  requiredSectionLabels,
  type ResolvedNoteTemplate,
} from '../note-templates/build-soap-prompt';
import { findStaticDivergence } from '../note-templates/section-assembly';
import { staticRegionsFromNote } from '../note-templates/assemble-note';
import { noteStaticDivergence } from '../note-templates/static-divergence-counter';
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from '../note-templates/system-default-template';

// TRANSCRIBE_MD_CLINICAL_MODEL — eval override (feat/fable5-eval); unset → default unchanged.
const MODEL = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-sonnet-4-6';

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
  /** Whether the anchored verifier left anything in the review lane.
   *
   *  A deferred additive fix is reported by pointing the doctor AT the
   *  suggestions ("review the suggestions and draft before signing"). When the
   *  lane is empty that sentence sends them hunting for cards that do not
   *  exist. Absent ⇒ true, so every existing caller and test is unchanged. */
  hasSuggestions?: boolean;

  // --- Q1 audit §07.1: the context the worker already had, and polish did not.
  //
  // These are a DISAMBIGUATION source and never a content source. The L6b
  // fidelity gate below still measures the polished note against the DRAFT
  // ALONE — it is not weakened here, and it must never be, or the fabrication
  // backstop disappears. Anything polish tried to import from the transcript
  // would be rejected as novel and take the whole polish down with it.
  //
  // What they buy is the fixes polish previously had to GUESS at. "The
  // Assessment contradicts the Subjective about chest pain" can be applied in
  // either direction; both readings use vocabulary already in the draft, so
  // both pass the gate, and until now L6 picked one blind.
  //
  // All three are optional, so every existing caller is byte-identical.

  /** The visit's specialty. Polish has been editing ultrasound reports and
   *  paediatric visits without knowing which it was looking at. */
  specialty?: string;
  /** L3's extracted entities, verbatim JSON. */
  entitiesJson?: string;
  /** The role-labeled transcript L4 and L5 already read. */
  roleLabeledTranscript?: string;
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
const ADD_VERB_RE = /\b(add|adds|adding|insert|include|includes|populate|append|restore|introduce|state|document|check|checks|checked|mark|marks|marked|tick|ticks|fill|fills|filled|select|selects)\b/i;
const REMOVAL_VERB_RE = /\b(remove|removes|delete|deletes|strike|drop|omit the|take out)\b/i;
// Instruction/editorial vocabulary that is "novel vs the draft" for nearly
// any fix text but carries no clinical payload — excluded before counting.
const EDITORIAL_TERMS = new Set([
  'apply', 'applied', 'described', 'above', 'below', 'fix', 'fixes', 'issue',
  'issues', 'auditor', 'consolidate', 'consolidated', 'reword', 'reworded',
  'rephrase', 'rephrased', 'merge', 'merged', 'reorder', 'reordered',
  'shorten', 'clarify', 'clarified', 'combine', 'combined', 'tighten',
  'deduplicate', 'duplicate', 'duplicated', 'redundant', 'repeated',
  'overlapping', 'formatting', 'format', 'wording', 'phrasing', 'sentence',
  'sentences', 'paragraph', 'section', 'sections', 'heading', 'headings',
  'bullet', 'bullets', 'line', 'lines', 'item', 'items', 'move', 'moved',
  'single', 'instead', 'statement', 'statements', 'draft', 'note',
]);

/** True when applying this fix would require content the draft lacks —
 *  the class the L6b gate rejects unconditionally. */
export function isAdditiveFix(draft: string, issue: CritiqueIssue): boolean {
  const fix = issue.suggested_fix ?? '';
  // Deletion fixes are gate-passable (deletions are explicitly allowed) and
  // safety-relevant (they REMOVE unsupported content) — never defer them,
  // even when the sentence also contains an add-verb ("remove X and add a
  // shorter form of Y" still nets toward removal; the gate backstops).
  if (REMOVAL_VERB_RE.test(fix)) return false;
  if (ADD_VERB_RE.test(fix)) return true;
  const novel = findNovelContentTerms([draft], fix).filter(
    (t) => !EDITORIAL_TERMS.has(t)
  );
  return novel.length >= 3;
}

/** Remove any leading model prose before the first markdown heading. The polish
 *  prompt forbids preamble, but a suggested fix that conflicts with the custom
 *  structure lock can make the model explain its refusal in prose ("I cannot
 *  apply Issue #1…"). A clinical note always begins with a heading, so anything
 *  before the first `#`-heading is not note content. No-op when the note already
 *  starts with a heading or has none. */
export function stripModelPreamble(text: string): string {
  const idx = text.search(/^#{1,6}\s/m);
  return idx > 0 ? text.slice(idx) : text;
}

export async function runLayer6Polish(input: Layer6Input): Promise<Layer6Output> {
  const { fixable: fixableAll, unfixable } = classifyCritique(input.critique);
  const deferredAdditive = fixableAll.filter((i) => isAdditiveFix(input.soapDraft, i));
  const fixable = fixableAll.filter((i) => !isAdditiveFix(input.soapDraft, i));
  // Phase 1: validate the polished note against the resolved template's
  // required sections. System default → the 4 SOAP headers → unchanged.
  const template: ResolvedNoteTemplate =
    input.noteTemplate ?? SYSTEM_DEFAULT_NOTE_TEMPLATE;
  const requiredSections = requiredSectionLabels(template);
  // Phase-1 custom-template fix (2026-07-23): emit an explicit heading-lock ONLY
  // for a non-default custom template with a known section set. The system
  // default keeps its original structure-agnostic prompt (byte-identical) — this
  // matters because an IMAGING visit by a non-customizing doctor reaches L6 with
  // the SOAP default here while the draft carries the ultrasound report headings
  // (L4 swaps ULTRASOUND_REPORT_TEMPLATE in internally, never reflected back).
  // Locking to this template's labels there would wrongly force the imaging
  // report into SOAP. Gating on isSystemDefault leaves SOAP + ultrasound paths
  // untouched and pins only genuine custom templates (the KUK operative note),
  // whose draft DOES match these labels.
  const emitStructureLock = !template.isSystemDefault && requiredSections.length > 0;
  // §07.1 — whether there is anything to disambiguate WITH. Specialty alone is
  // a one-line hint and does not open the reference block.
  const hasContext = Boolean(input.entitiesJson || input.roleLabeledTranscript);
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
  /** Section labels whose ASSEMBLED bytes did not survive the polisher. Drives
   *  a doctor-facing reason that NAMES the section, per #106(g)(4) — "polish
   *  was rejected" tells a clinician nothing they can act on. */
  let divergedStaticLabels: string[] = [];

  if (fixable.length === 0) {
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
      'IMMUTABLE RULES — these override every other instruction below:',
      '1. You are a copy editor, not a clinician author. You may reword,',
      '   reorganize, and reformat ONLY content already present in the',
      '   draft.',
      '2. Do NOT introduce new clinical facts. Do NOT add, infer, or',
      '   expand clinical content of any kind — no new findings, symptoms,',
      '   exam results, diagnoses, differentials, contraindication or risk',
      '   reasoning, referrals, screenings or red-flag statements,',
      '   follow-up instructions, patient education, medications, or doses',
      '   — even if a suggested fix appears to call for them.',
      '3. If a fix requires information that is not in the draft, leave',
      '   the flagged area as-is and keep moving.',
      '4. Never flip a negation or change the clinical meaning of a',
      '   statement.',
      '',
      'You are editing a clinical SOAP note. A separate auditor has',
      'flagged specific issues; apply ONLY those fixes and return the',
      'complete revised SOAP note in the same markdown structure as the',
      'draft.',
      '',
      // Phase-1 custom-template fix (2026-07-23): for a doctor-uploaded custom
      // template (e.g. an operative note) the draft does NOT use the default
      // SOAP layout. Without an explicit lock the model "helpfully" reverts a
      // sparse custom note back to Subjective/Objective/Assessment/Plan — which
      // then fails the structure validator and drops the doctor's chosen format.
      // Pin polish to this template's own headings. Gated to non-default
      // templates so the SOAP + ultrasound-imaging paths stay structure-agnostic
      // (see emitStructureLock above).
      ...(emitStructureLock
        ? [
            'The revised note MUST use these markdown section headings, exactly',
            'as written below, in this order, and NO OTHERS. Do not rename, add,',
            'remove, reorder, merge, or split them, and do not restructure the',
            'note under a different set of headings:',
            ...requiredSections.map((label) => `## ${label}`),
            'If one of these sections has no supporting content in the draft,',
            'keep its heading and leave the body empty — a later step marks empty',
            'sections. Never drop a required heading and never invent content to',
            'fill one.',
            'If a suggested fix would change, replace, reorder, or restructure',
            'these headings, silently skip that one fix and keep the headings as',
            'they are — do NOT add any explanation, apology, or commentary about',
            'skipping it. Output the note itself and nothing else.',
            '',
          ]
        : []),
      // ⚠️ UNGATED, DELIBERATELY — THE ANTI-COMMENTARY RULE IS NOT A
      // STRUCTURE-LOCK CONCERN. The block above carries the only sentence in
      // this prompt forbidding commentary ("do NOT add any explanation,
      // apology, or commentary about skipping it"), and it is gated on
      // `emitStructureLock`, i.e. non-default templates only.
      //
      // ⚠️ SO IT WAS ABSENT FOR THE SYSTEM DEFAULT **AND FOR IMAGING** — and
      // imaging is the worse half: per the note at the top of this module, an
      // imaging visit reaches L6 with `noteTemplate` = the SOAP system default
      // (L4 swaps the ultrasound template in internally and never reflects it
      // back), so `isSystemDefault` is TRUE and the lock does not emit.
      //
      // ⚠️ AND L6 IS THE LAYER THAT WRITES THE SIGNED NOTE. `runLayer6Polish`
      // returns `soapFinal`, and `sign/route.ts` writes `signedSoap` from it.
      // The never-editorialize clause added to L4's `globalRules` governs
      // `soapDraft`; L6 rewrites the note wholesale whenever there is a fixable
      // issue, from a prompt that never carried it. Found by an adversarial
      // pass — the survival gate's watched set was the two L4 builders, and
      // `tm_polish` is a THIRD model call that writes note text.
      //
      // `stripModelPreamble` is not a substitute: it strips only text BEFORE
      // the first heading, so an aside inside a section survives, and the L6b
      // fidelity gate classifies additions of CLINICAL content — a process
      // aside is neither an addition nor a meaning change.
      'Never address the reader and never describe your own process. Do not',
      'comment on the template, on the dictation, or on why a section reads as',
      'it does. Recording that a finding was not documented is clinical content',
      'and must be preserved; a sentence about what you could or could not do',
      'is commentary and does not belong in a medical record.',
      '',
      'Rules:',
      '- Preserve all clinical content that the auditor did not flag.',
      '- Apply each "suggested_fix" as closely as possible, using only',
      '  information already present in the draft.',
      '- Output ONLY the revised SOAP markdown. No preamble, no summary',
      '  of changes.',
      ...(input.specialty ? ['', `Specialty: ${input.specialty}.`] : []),
      ...(hasContext
        ? [
            '',
            'WHAT WAS ACTUALLY SAID — reference only.',
            'The material below is provided so you can tell which reading of an',
            'ambiguous fix is the correct one — for example when the draft',
            'contradicts itself and the fix says only "reconcile these". Use it',
            'to CHOOSE between statements already in the draft, and',
            'never as content to add.',
            'Rules 1–4 above still bind: if the right correction',
            'would require a fact that is not in the draft, leave the flagged',
            'area as-is and keep moving.',
          ]
        : []),
    ].join('\n');

    const fixesText = fixable
      .map(
        (i, idx) =>
          `${idx + 1}. [${i.severity}] ${i.location}: ${i.description}\n    Fix: ${i.suggested_fix}`
      )
      .join('\n');

    const user = [
      'Draft:',
      input.soapDraft,
      '',
      'Issues to apply (apply in order):',
      fixesText,
      ...(input.entitiesJson
        ? ['', 'Extracted entities (reference only):', input.entitiesJson]
        : []),
      ...(input.roleLabeledTranscript
        ? ['', 'Transcript (reference only):', input.roleLabeledTranscript]
        : []),
    ].join('\n');

    const { text } = await modelClient.completeText({
      practiceId: input.practiceId,
      visitId: input.visitId,
      userId: input.userId,
      purpose: 'tm_polish',
      provider: 'anthropic',
      model: MODEL,
      system,
      user,
      maxTokens: 8192,
      // Q2 fix-pack — polish is constrained edit ("apply these fixes").
      // Tightened from 0.2 to 0.1 so the same draft + critique produce
      // the same revised SOAP run-to-run.
      temperature: 0.1,
    });
    // Strip any leading refusal/preamble prose the model may emit when a
    // suggested fix conflicts with the structure lock (see stripModelPreamble).
    soapFinal = stripModelPreamble(text);

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
        void logAudit({
          action: 'L6_FABRICATION_REJECTED',
          targetType: 'transcribe_visit',
          targetId: input.visitId,
          userId: input.userId,
          practiceId: input.practiceId,
          success: false,
          metadata: {
            layer: 'L6',
            violationCount: gate.violationCount,
            kinds: gate.kinds,
            novelTermCount: gate.novelTermCount,
            gateError: gate.gateError,
            fellBackToDraft: true,
            // NO note content — counts + enum-class strings only.
          },
        });
      }
    }

    // ── L6b STATIC-REGION ARM (ruling #106(g)) ────────────────────────────
    //
    // ⚠️ THE VERIFIER ABOVE CANNOT SEE THIS CLASS, AND THAT IS WHY THIS EXISTS.
    // Its whole contract is "no NEW clinical content relative to the draft", and
    // `500 milliseconds` → `0.5 seconds` adds nothing, removes nothing and flips
    // no negation — the verifier's own rules call it rewording and let it
    // through, correctly, for the question it was asked. The doctor's form is a
    // different question: those bytes are not a phrasing choice, they are the
    // product's promise (SPEC §4.3a(a)).
    //
    // ⚠️ IT RIDES THE FIDELITY GATE'S EXISTING FALLBACK RATHER THAN INVENTING A
    // SECOND ONE — one rejection path, one audit action, one review-banner
    // composition. A parallel mechanism would drift from the first the day
    // either was fixed.
    //
    // ⚠️ THE REGIONS ARE READ FROM THE DRAFT, not passed down from L4, because
    // L4 is skippable on resume — see `staticRegionsFromNote`. A no-op returning
    // `[]` for every template with no `always_include` sections, which today is
    // all of them, so this is inert until the reclassification lands.
    // ⚠️ NO `soapFinal.trim().length > 0` GUARD HERE, DELIBERATELY, AND THE
    // OMISSION IS A FIX. The fidelity gate above is exempt on empty output
    // because empty output "cannot carry an addition" — true for the ADDITION
    // question and invalid for the SURVIVAL question this arm asks. A polisher
    // returning "\n \n" skipped both gates, `polishRejected` stayed false, and
    // that value was written to soapFinal AND soapL6Original, taking the
    // doctor's assembled sections with it. An empty note contains no region, so
    // the arm now rejects it and the draft is served.
    if (!polishRejected) {
      const regions = staticRegionsFromNote(input.soapDraft, template.sections);
      const diverged = findStaticDivergence(soapFinal, regions);
      if (diverged.length > 0) {
        polishRejected = true;
        divergedStaticLabels = diverged.map((d) => d.label);
        soapFinal = input.soapDraft;
        const total = noteStaticDivergence(template.id);
        void logAudit({
          action: 'L6_FABRICATION_REJECTED',
          targetType: 'transcribe_visit',
          targetId: input.visitId,
          userId: input.userId,
          practiceId: input.practiceId,
          success: false,
          metadata: {
            layer: 'L6',
            // THE NAMED REASON. Distinct from the verifier's `gateError`
            // values so the two classes can never be summed by accident.
            gateError: 'static_region_diverged',
            // Section KEYS, not text — a label is the doctor's own heading and
            // is structural; the section body never leaves the note.
            divergedSections: diverged.map((d) => d.sectionKey),
            divergedCount: diverged.length,
            regionsChecked: regions.length,
            // The durable per-template count lives in these rows; the in-process
            // counter is the live signal. Written on EVERY such row so the
            // group-by has something to group on.
            noteTemplateId: template.id,
            noteTemplateVersion: template.version,
            templateDivergenceCount: total,
            fellBackToDraft: true,
          },
        });
      }
    }

    // FIND-P1-016 — same validator L4 uses, now scoped to the resolved
    // template's required sections. Fail → keep raw output, flag the
    // validation reason so the reviewReason calculation below includes it
    // alongside the unfixable-criticals reason. Skipped on gate fallback:
    // the draft we fell back to was already L4-validated when it landed.
    if (!polishRejected) {
      const validation = validateSoapStructure(soapFinal, requiredSections);
      if (!validation.ok) {
        void logAudit({
          action: 'MODEL_OUTPUT_VALIDATION_FAIL',
          targetType: 'transcribe_visit',
          targetId: input.visitId,
          userId: input.userId,
          practiceId: input.practiceId,
          success: false,
          metadata: {
            layer: 'L6',
            reason: validation.reason,
            outputLength: validation.outputLength,
            missingSections: validation.missingSections,
            // NO raw output — PHI surface.
          },
        });
        // ⚠️ RETIRED VOCABULARY. This said "Polish output didn't match expected
        // markdown structure — manual review required (…)" — the system-facing
        // phrasing the L4 banner was rewritten to replace, landing immediately
        // after it on the very visits that change targets, and calling
        // operative-note headings "SOAP sections".
        //
        // Same measured-claim discipline as the new banner: it says the
        // headings could not be found, never that the content was unsupported,
        // because heading presence is all `validateSoapStructure` measures.
        polishValidationFailReason = structureMismatchReason(
          validation.missingSections,
          requiredSections,
          validation.reason,
        );
      }
    }
  }

  // Surface unfixable critical issues as a review banner reason. The
  // fabrication-gate rejection (when present) or the FIND-P1-016
  // validation-fail reason prepends so the operator/clinician sees the
  // most urgent issue first. (Rejection and validation-fail are mutually
  // exclusive — validation is skipped on the gate-fallback path.)
  const polishRejectedReason = !polishRejected
    ? null
    : divergedStaticLabels.length > 0
      ? // NAMES THE SECTION, deliberately. A clinician who is told "polish was
        // rejected" learns nothing actionable; one who is told the polisher
        // tried to reword TECHNIQUE knows exactly where to look and that the
        // wording they are seeing is their own.
        `Auto-polish tried to reword text that comes from your own form (${divergedStaticLabels.join(', ')}) and was not applied — the note keeps your template's exact wording. The auditor-flagged fixes remain unapplied; review the draft.`
      : 'Auto-polish was rejected by the fabrication gate and not applied — the auditor-flagged fixes remain unapplied; review the draft.';
  const prefixReason = polishRejectedReason ?? polishValidationFailReason;
  // Survival tuning: deferred additive fixes still reach the doctor — their
  // content usually sits in the suggestions lane (adopt flow), so point there.
  const deferredReason =
    deferredAdditive.length > 0 && (input.hasSuggestions ?? true)
      ? `Auto-polish deferred ${deferredAdditive.length} auditor fix${
          deferredAdditive.length === 1 ? '' : 'es'
        } that would add content not in the draft — review the suggestions and draft before signing.`
      : null;
  const baseReason =
    unfixable.length > 0
      ? `Auto-polish could not fix ${unfixable.length} critical issue${
          unfixable.length === 1 ? '' : 's'
        }: ${unfixable.map((i) => i.description).join('; ')}`
      : !input.critique.safe_to_sign_without_review
        ? 'Auditor flagged issues worth a quick review before signing.'
        : null;
  const reviewReason =
    [prefixReason, deferredReason, baseReason].filter(Boolean).join(' ') || null;

  const needsReview =
    unfixable.length > 0 ||
    deferredAdditive.length > 0 ||
    !input.critique.safe_to_sign_without_review ||
    polishValidationFailReason !== null ||
    polishRejected;

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
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
  await applyAdditiveReviewState(input.visitId, { needsReview, reviewReason });

  return { soapFinal, needsReview, reviewReason, unfixable, polishRejected };
}
