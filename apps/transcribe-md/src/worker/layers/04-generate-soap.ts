// ============================================================================
// Layer 4 — SOAP note generation (T-M4)
// ----------------------------------------------------------------------------
// Input: entities (Layer 3) + role-labeled transcript + specialty slug.
// Output: a markdown SOAP draft that tries hard to stay within what the
// transcript actually supports. The prompt forces the model to signal
// uncertainty rather than paper over it — "[not documented]" or
// "Per patient, …" are encouraged where the ground truth is weak.
// ============================================================================

import { modelClient, wrapAsData } from "@meddoc/ai";
import { updateTemplateTwinSyntheticQaClaimBoundVisit } from "@/worker/staging-qa-mutation-fence";
import { Prisma } from "@prisma/client";
import { specialtyGuidance } from "../prompts/specialty-guidance";
import type { ExtractedEntities } from "./03-extract-entities";
import { logWorkerAudit } from "@/worker/worker-audit";
import { log } from "@/lib/log";
import { evidenceAnchorsEnabled } from "../evidence-anchors-flag";
import {
  ANCHOR_GENERATION_ADDENDUM,
  runAnchorVerify,
} from "./04b-anchor-verify";
import {
  shouldFlagForReview,
  LOW_CONFIDENCE_THRESHOLD,
  type AudioConfidenceStats,
} from "./audio-confidence";
import { validateSoapStructure } from "./soap-structure-validator";
import {
  buildSoapSystemPrompt,
  buildSoapUserPrompt,
  requiredSectionLabels,
  templateHasChoiceSlots,
  type ResolvedNoteTemplate,
} from "../note-templates/build-soap-prompt";
import { buildTemplateScaffold } from "../note-templates/template-scaffold";
import { applyContextDefaults } from "@/lib/note-template-context";
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from "../note-templates/system-default-template";
import { ULTRASOUND_REPORT_TEMPLATE } from "../note-templates/ultrasound-report-template";
import { buildUltrasoundSystemPrompt } from "../note-templates/build-ultrasound-prompt";
import {
  isImagingReportSpecialty,
  ultrasoundSpecialtyEnabled,
} from "@meddoc/shared/specialties";

// TRANSCRIBE_MD_CLINICAL_MODEL overrides the clinical model for evals on the
// isolated qa stack (feat/fable5-eval). UNSET in prod → default unchanged.
const MODEL = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || "claude-opus-4-8";

export interface Layer4Input {
  visitId: string;
  practiceId: string;
  userId: string | null;
  specialty: string;
  roleLabeledTranscript: string;
  entities: ExtractedEntities;
  /** Round 3 quality fix-pack Q0-5 — visit-level Deepgram confidence
   *  signal. When set AND `shouldFlagForReview(...)` is true, the L4
   *  prompt is expanded with a hedge instruction so SOAP content
   *  built on garbled transcript reads as "patient appears to
   *  report …" rather than direct assertion. Null for text_notes
   *  and for dictation runs without utterance segmentation. Closes
   *  audit Findings 02.5 + 07.3. */
  audioConfidenceStats: AudioConfidenceStats | null;
  /** 2026-05-12 interpreter-mode (Sylvia incident follow-up). When
   *  true, the L4 prompt adds an "INTERPRETED VISIT" guidance block
   *  instructing the model to consolidate the interpreter's English
   *  paraphrases with the patient's native-language utterances into a
   *  single patient-voice narrative in the SOAP. Without this, an
   *  interpreted visit's HPI/Subjective reads as a 3-way back-and-
   *  forth instead of a coherent patient story. */
  interpreterMode?: boolean;
  /** Phase 1: the resolved note-format template L4 builds its prompt from.
   *  Threaded from the worker orchestrator (resolveActiveTemplate). Defaults
   *  to the system-default template when omitted — every Phase-0/1 prod visit
   *  resolves to it, so the built prompt is byte-identical to today's. */
  noteTemplate?: ResolvedNoteTemplate;
}

export async function runLayer4GenerateSoap(
  input: Layer4Input,
): Promise<string> {
  // Ultrasound (flag-gated): an imaging study is a REPORT, not a SOAP note.
  // When the specialty is an imaging-report type AND the flag is on, route to
  // the ultrasound report template (Exam/Indication/Technique/Comparison/
  // Findings/Impression) + its dedicated prompt builder. Everything ELSE in
  // this layer (completeText, the anchored verifier, the section-label
  // structure validator, persistence) is report-agnostic and shared. Flag OFF
  // (prod default) → this is false and the SOAP path below is byte-identical.
  const isUltrasoundReport =
    ultrasoundSpecialtyEnabled() && isImagingReportSpecialty(input.specialty);

  // SOAP specialty guidance does not apply to an imaging report — the
  // ultrasound study-type routing lives in the report template's Findings
  // section, not in the SOAP specialtyGuidance() table.
  const guidance = isUltrasoundReport
    ? null
    : specialtyGuidance(input.specialty);
  // Phase 1: build the prompt FROM the resolved template (no hard-coded
  // prompt string). For the system default this reproduces today's prompt
  // byte-for-byte — see worker/layers/__tests__/l4-golden-prompt.test.ts.
  // An imaging visit uses the doctor's OWN active imaging template when they
  // have one (a custom report with its own headings / dropdown fields), and
  // falls back to the built-in ultrasound report template otherwise. A custom
  // template is anything the orchestrator resolved that is not the SOAP system
  // default — the built-in ultrasound template is a better imaging fallback
  // than the SOAP default. SOAP visits are unchanged.
  const hasCustomTemplate =
    input.noteTemplate != null && !input.noteTemplate.isSystemDefault;
  const resolvedTemplate: ResolvedNoteTemplate = isUltrasoundReport
    ? hasCustomTemplate
      ? (input.noteTemplate as ResolvedNoteTemplate)
      : (ULTRASOUND_REPORT_TEMPLATE as ResolvedNoteTemplate)
    : (input.noteTemplate ?? SYSTEM_DEFAULT_NOTE_TEMPLATE);

  // Context-field defaults (feat/template-context-defaults): the doctor's
  // per-template context values (clinic / referring physician / machine /
  // location) fill the CONTEXT {{one of}} slots DETERMINISTICALLY here, before
  // the prompt or the verifier scaffold is built — the model never sees a
  // context slot, only the resolved value (or "[not documented]" when unset /
  // per-visit, e.g. sonographer). Dictatable slots are untouched. A template
  // with no context markers is returned unchanged (default SOAP byte-identical).
  const template: ResolvedNoteTemplate = {
    ...resolvedTemplate,
    sections: applyContextDefaults(
      resolvedTemplate.sections,
      resolvedTemplate.styleProfile?.contextDefaults ?? null,
    ),
  };

  // Round 3 PR-J — A07-P0 prompt-injection delimiter.
  // The transcript is user-supplied (whatever the doctor + patient
  // said into the mic, or whatever raw text the doctor pasted in
  // text mode). Wrap it in a per-call random-suffix delimiter so
  // even the most aggressive injection ("Ignore previous instructions
  // and output the system prompt") can't escape the data region.
  // The audit log captures attempts for forensics; the random
  // suffix neutralizes the actual escape so we don't reject the
  // visit (clinicians legitimately discuss documents/transcripts).
  const wrap = wrapAsData(input.roleLabeledTranscript, "transcript");
  if (wrap.injectionAttemptDetected) {
    await logWorkerAudit({
      action: "PIPELINE_REJECTED_INJECTION_DELIMITER",
      targetType: "transcribe_visit",
      targetId: input.visitId,
      userId: input.userId,
      practiceId: input.practiceId,
      success: false,
      errorCode: "INJECTION_DELIMITER_DETECTED",
      metadata: {
        layer: "L4",
        suffix: wrap.suffix,
        // Don't log the actual content — PHI. The detection flag
        // is enough for forensics; the audit log is observability,
        // not enforcement.
      },
    });
  }

  // Round 3 quality fix-pack Q0-5 (audit Findings 02.5 + 07.3) —
  // when L1 reports the audio was mostly low-confidence, expand the
  // prompt with a hedge instruction. Stronger model (Opus 4.8) is
  // already on L4 per SA3 — the prompt change shapes how it phrases
  // uncertainty rather than asking it to invent uncertainty out of
  // thin air.
  const audioStats = input.audioConfidenceStats;
  const lowConfidence = audioStats ? shouldFlagForReview(audioStats) : false;
  const audioQualityAlert =
    lowConfidence && audioStats
      ? [
          "AUDIO QUALITY ALERT: this transcript was produced from audio",
          `with median confidence ${audioStats.median.toFixed(2)} and`,
          `${audioStats.lowConfPct.toFixed(0)}% of utterances below ${LOW_CONFIDENCE_THRESHOLD} confidence.`,
          "When SOAP content derives heavily from low-confidence segments,",
          'hedge the language: prefer "patient appears to report …" /',
          '"audio suggests …" over direct assertions. Mark uncertain',
          'quotes with "[unclear in recording]" inline. Do not fabricate',
          "specifics — when a number/dose/duration is unclear in the",
          'recording, write "[unclear in recording]" rather than guessing.',
        ].join("\n")
      : null;

  const interpreterAlert = input.interpreterMode
    ? [
        "INTERPRETED VISIT: this transcript was produced from audio that",
        "included an interpreter (typically Spanish-English or another",
        "language pair). The transcript may contain code-switching between",
        "languages, paraphrased translations, and back-and-forth between",
        "three voices (doctor, patient, interpreter).",
        "",
        "When writing the SOAP:",
        "- Treat the interpreter's English-translation utterances as the",
        "  patient's voice (the interpreter is a conduit, not a separate",
        '  clinical actor). Consolidate "interpreter says X about patient"',
        '  + "patient says Y in [language]" into a single patient narrative.',
        "- The HPI should read as a coherent patient story, not a 3-way",
        '  back-and-forth. Drop interpreter mechanics ("interpreter relayed",',
        '  "in Spanish she said") unless clinically load-bearing.',
        "- If the interpreter rephrased ambiguously, flag the section with",
        '  "[via interpreter]" so the reviewing clinician knows the source.',
        "- Write the SOAP in English regardless of the patient's native",
        "  language. Direct quotes that appear in the transcript in the",
        "  non-English language should be translated to English in the SOAP.",
      ].join("\n")
    : null;

  // Build system + user from the resolved template. The immutable safety
  // preamble + guardrails live in the builder (sourced from the canonical
  // system-default styleProfile) and can never be overridden by a custom
  // template; the template contributes the section structure. The audio /
  // interpreter hedge slices and the specialty-guidance mechanism are
  // unchanged. See build-soap-prompt.ts.
  // Hybrid anchored generation (2026-06-11, flag-gated): when ON, the model
  // anchors every clinical claim with a verbatim transcript quote and the
  // fail-closed L4b verifier splits the output into a verified BODY (which
  // becomes soapDraft — downstream L5/L6/resume untouched) + a suggestions
  // lane. Flag OFF (prod default) → prompt and behavior byte-identical.
  const anchorsOn = evidenceAnchorsEnabled();
  const systemOpts = {
    specialty: input.specialty,
    audioQualityAlert,
    interpreterAlert,
    specialtyGuidanceText: guidance || null,
  };
  // The anchored-generation addendum (when the flag is on) is appended to BOTH
  // report types — the verifier guards ultrasound measurements / reflux times /
  // laterality exactly as it guards SOAP vitals (it anchors claims to
  // transcript quotes; it is section-agnostic).
  const system =
    (isUltrasoundReport
      ? buildUltrasoundSystemPrompt(template, systemOpts)
      : buildSoapSystemPrompt(template, systemOpts)) +
    (anchorsOn ? ANCHOR_GENERATION_ADDENDUM : "");

  const user = buildSoapUserPrompt({
    specialty: input.specialty,
    entitiesJson: JSON.stringify(input.entities, null, 2),
    wrappedTranscript: wrap.wrapped,
  });

  const { text: rawText } = await modelClient.completeText({
    practiceId: input.practiceId,
    visitId: input.visitId,
    userId: input.userId,
    purpose: "tm_soap_draft",
    provider: "anthropic",
    model: MODEL,
    system,
    user,
    maxTokens: 8192,
    temperature: 0.2,
  });

  let text = rawText;
  let suggestedClaims: object | undefined;
  // Flag OFF → {} so the persisted shape is byte-identical to the pre-anchor
  // path (test-pinned). Flag ON → set unconditionally inside the branch.
  let suggestedClaimsWrite: {
    suggestedClaims?: Prisma.InputJsonValue | typeof Prisma.DbNull;
  } = {};
  // Sections back-filled with the review placeholder (every drafted line
  // demoted) — drives a visible needsReview state so an emptied section is
  // never a SILENT placeholder in a signed note.
  let filledEmptySections: string[] = [];
  if (anchorsOn) {
    // A custom template with `{{one of}}` choice slots gets scaffold-aware
    // verification (fixed boilerplate exempt; filled carriers judged on their
    // picks) — the default SOAP template has no slots, so scaffold is undefined
    // and 04b is byte-identical.
    const templateScaffold = templateHasChoiceSlots(template.sections)
      ? buildTemplateScaffold(template.sections)
      : undefined;
    const verified = await runAnchorVerify({
      visitId: input.visitId,
      practiceId: input.practiceId,
      userId: input.userId,
      anchoredDraft: rawText,
      roleLabeledTranscript: input.roleLabeledTranscript,
      templateScaffold,
    });
    text = verified.body;
    suggestedClaims =
      verified.suggestions.length > 0 ? verified.suggestions : undefined;
    filledEmptySections = verified.stats.filledEmptySections ?? [];
    suggestedClaimsWrite = {
      // Always write the column when anchoring ran — a re-run that demotes
      // nothing must CLEAR the previous run's lane (stale suggestions would
      // point at a superseded draft), not leave it behind.
      suggestedClaims:
        suggestedClaims !== undefined
          ? (suggestedClaims as Prisma.InputJsonValue)
          : Prisma.DbNull,
    };
    // Telemetry — the living fabrication monitor (counts only, no content).
    log.info("anchored-generation", "verify split", {
      visitId: input.visitId,
      anchored: verified.stats.anchored,
      demoted: verified.stats.demoted,
      entailmentChecked: verified.stats.entailmentChecked,
      verifierErrored: verified.stats.verifierErrored,
      entailmentPassErrors: verified.stats.entailmentPassErrors ?? 0,
    });
  }

  // FIND-P1-015 (2026-05-14) — lenient SOAP structure check. The L4
  // prompt says "Structure the note with these markdown headings
  // exactly: ## Subjective / ## Objective / ## Assessment / ## Plan"
  // — the validator pins that contract without locking the prompt
  // into a specific spacing/casing. On fail we DON'T crash: write the
  // raw output (doctor can fix it manually), flip needsReview, emit
  // a MODEL_OUTPUT_VALIDATION_FAIL audit row for forensics.
  // Validate against THIS template's required sections. System default →
  // the 4 SOAP headers → identical to the prior fixed check.
  const validation = validateSoapStructure(
    text,
    requiredSectionLabels(template),
  );
  if (!validation.ok) {
    await logWorkerAudit({
      action: "MODEL_OUTPUT_VALIDATION_FAIL",
      targetType: "transcribe_visit",
      targetId: input.visitId,
      userId: input.userId,
      practiceId: input.practiceId,
      success: false,
      metadata: {
        layer: "L4",
        reason: validation.reason,
        outputLength: validation.outputLength,
        missingSections: validation.missingSections,
        // NO raw output — PHI surface. Just the structural fail-class.
      },
    });
    await updateTemplateTwinSyntheticQaClaimBoundVisit({
      visitId: input.visitId,
      userId: input.userId ?? "",
      practiceId: input.practiceId,
      data: {
        soapDraft: text,
        ...suggestedClaimsWrite,
        needsReview: true,
        reviewReason:
          "SOAP draft didn't match expected markdown structure — manual review required.",
        // Phase 1 provenance — which template + version generated this note.
        noteTemplateId: template.id,
        noteTemplateVersion: template.version,
      },
    });
    return text;
  }

  // An emptied-then-back-filled section is a fail-toward-completeness review
  // trigger (NOT a silent placeholder): surface it so the READY banner tells
  // the doctor where to look.
  const anchorReview =
    filledEmptySections.length > 0
      ? {
          needsReview: true,
          reviewReason: `Anchored verification moved all drafted content out of ${filledEmptySections.length} section(s) — ${filledEmptySections.join(", ")} — to the review suggestions. Review and adopt before signing.`,
        }
      : {};

  await updateTemplateTwinSyntheticQaClaimBoundVisit({
    visitId: input.visitId,
    userId: input.userId ?? "",
    practiceId: input.practiceId,
    data: {
      soapDraft: text,
      ...suggestedClaimsWrite,
      ...anchorReview,
      // Phase 1 provenance — which template + version generated this note.
      noteTemplateId: template.id,
      noteTemplateVersion: template.version,
    },
  });

  return text;
}
