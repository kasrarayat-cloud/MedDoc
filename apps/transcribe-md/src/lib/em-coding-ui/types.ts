// ============================================================================
// EmScore + BumpSuggestion — STUB types for Phase 5.2 Coding Coach UI
// ----------------------------------------------------------------------------
// STUB — replaced by lib/em-coding/types.ts in merge.
//
// This file gives Subagent C's standalone build a typed surface that mirrors
// the rubric §3 (deterministic counts) + §4 (LLM MDM judgement) + §5 (Bump
// CTA logic) schemas. When Subagent B's engine branch lands, this file is
// deleted and consumers re-import from `@/lib/em-coding/types`.
//
// All fields below intentionally match the agreed wire schema verbatim so the
// migration is a path swap, not a surface rewrite.
// ============================================================================

/** AMA 2021 Office E&M code surface used by the Coding Coach. */
export type EmCode =
  | '99202'
  | '99203'
  | '99204'
  | '99205'
  | '99211'
  | '99212'
  | '99213'
  | '99214'
  | '99215';

/** Whether a code belongs to the new- or established-patient ladder. */
export type EmVisitType = 'new' | 'established';

/** AMA 2021 MDM tier (rubric §2). */
export type MdmTier = 'straightforward' | 'low' | 'moderate' | 'high';

/** Per-element MDM level — used by both LLM + deterministic fallback. */
export type ElementLevel = 'minimal' | 'low' | 'moderate' | 'high';

/** Pass/warn state of a single rail criterion row. */
export type CriterionStatus = 'ok' | 'warn';

/** A single deterministic-count criterion (HPI/ROS/PFSH/Exam) row. */
export interface EmCriterion {
  /** Stable id for re-render keying + nudge cross-ref (e.g. 'hpi.elements'). */
  id: string;
  status: CriterionStatus;
  /** Primary (Inter, weight 500) line — e.g. "4+ HPI elements detected". */
  head: string;
  /** Secondary (text-3) line — e.g. "location · quality · duration · timing". */
  sub: string;
  /** Optional warn-state nudge — "+ add 1 line" + tooltip suggestion. */
  nudge?: {
    text: string;
    suggestion: string;
  };
}

/** A grouped rail section (History / Exam / MDM). */
export interface EmCriterionGroup {
  /** Rail group id ('history' | 'exam' | 'mdm'). */
  id: 'history' | 'exam' | 'mdm';
  /** Display title — e.g. "History (HPI)". */
  title: string;
  /** Right-aligned summary in group head — e.g. "3 satisfied · 1 gap". */
  summary: string;
  /** Children rows. */
  items: EmCriterion[];
  /** Footer — micro-meta line at the bottom of the group, optional. */
  footer?: {
    /** Sage-tinted "satisfied" text. */
    satisfied: string;
    /** Right-aligned "next-level requirement" hint. */
    nextLevel?: string;
  };
}

/** Time-band tied to the suggested code (rubric §1.1/§1.2). */
export interface EmTimeBand {
  /** Lower threshold of the band (seconds). */
  min: number;
  /** Upper threshold of the band (seconds). */
  max: number;
  /** The CPT code this band corresponds to (display only). */
  code: EmCode;
}

/** Override snapshot — doctor-set code + reason (rubric §5.1). */
export interface EmOverride {
  code: EmCode;
  reason?: string;
  /** ISO timestamp. */
  overriddenAt: string;
}

/** A "bump to next level" CTA payload (rubric §5). */
export interface BumpSuggestion {
  /** 'almost-there' (gap ≤ 2) | 'confirm-bump' (already meets next level). */
  mode: 'almost-there' | 'confirm-bump';
  /** Code to bump to. */
  toCode: EmCode;
  /** Human-readable gap descriptions, AMA-criterion language. */
  gaps: Array<{
    /** Criterion id this gap maps to (cross-ref to EmCriterion.id). */
    criterionId: string;
    /** AMA-criterion language verbatim. */
    label: string;
    /** Auto-suggestion text the doctor reviews + edits before applying. */
    suggestion: string;
  }>;
  /** Static reference table revenue delta in dollars (UI display only). */
  revenueDelta: number;
}

/** Per-section pulse hints — sage 'ok' or amber 'boost' for SOAP body header. */
export type SectionPulseHint = 'ok' | 'boost';

/** The SOAP body section keys re-used here for hint mapping. */
export type SoapSectionKey = 'subjective' | 'objective' | 'assessment' | 'plan';

/** The full E&M score the rail consumes (POST /api/visits/[id]/em-score response). */
export interface EmScore {
  /** Suggested CPT code per the rubric. */
  suggestedCode: EmCode;
  /** Whether visit is new or established (drives the override listbox set). */
  visitType: EmVisitType;
  /** Resolved MDM tier (LLM-judged or deterministic-fallback). */
  mdmTier: MdmTier;
  /** True when the LLM judged MDM (vs heuristic fallback). */
  llmJudged: boolean;
  /** 0..1 confidence of the MDM judgement (rubric §4). */
  confidence: number;
  /** Total time band for the suggested code. */
  timeBand: EmTimeBand;
  /** Lower-bound visit time from `audioDurationSec` / dictation / wall clock. */
  visitTimeSec: number;
  /** Multiplier-extrapolated estimate (informational only). */
  estimatedTotalSec?: number;
  /** Three rail groups (history / exam / mdm) ready for render. */
  groups: EmCriterionGroup[];
  /** Bump suggestion (null means CTA hidden — already at top tier or gap > 2). */
  bump: BumpSuggestion | null;
  /** Doctor explicit override, persists in cptCodes.em.override. */
  override?: EmOverride;
  /** Per-SOAP-section pulse hints — Subagent A's body listens to these. */
  sectionPulseHints?: Partial<Record<SoapSectionKey, SectionPulseHint>>;
  /** Server compute timestamp — for stale-detection fade-in. */
  computedAt: string;
}

// ============================================================================
// Rail ↔ SOAP body coupling — direct prop callbacks, NOT window CustomEvents.
// ----------------------------------------------------------------------------
// The Phase-5.2 design originally used `window.dispatchEvent(...)` for loose
// coupling between rail + body, but every dispatcher landed without a
// listener (and vice versa) because Subagent A's branch never merged. The
// QA Interaction Auditor caught five orphan endpoints in 2026-05-05's
// audit. We removed the CustomEvent constants entirely and switched to
// direct prop coupling — same shape PR #132 used for the bump-additions
// flow:
//
//   - SOAP edits → parent `soap-editor.tsx` passes `currentSoapText` to
//     `<CodingRail>`; the rail debounces and calls POST /em-score
//     itself. (Replaces the SOAP_EDITED_EVENT contract.)
//   - Bump-CTA highlight → `<BumpCtaButton>` calls `onHighlight(criterionIds)`;
//     parent maps to SOAP section keys + sets `highlightedSections`
//     state. (Replaces SOAP_HIGHLIGHT_CRITERIA_EVENT.)
//   - Override → `<CodingRail>` calls `onApplyOverride(code, reason?)`;
//     parent fetches POST /em-score/override + updates emScore on
//     success. (Replaces EM_OVERRIDE_EVENT — also adds the missing
//     server route + EM_OVERRIDE_APPLIED audit row.)
//   - Boost hints / section pulse dots → derived from
//     `EmScore.sectionPulseHints` (server-computed); no runtime event.
//
// SOAP_JUMP_EVENT was deliberately removed in the §P5.2 a11y restore
// (see EmCriterion.tsx) — the constant + interface are now gone too.
// ============================================================================
