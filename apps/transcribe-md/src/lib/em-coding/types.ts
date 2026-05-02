// ============================================================================
// E&M Coding — shared types (Phase 5.2)
// ----------------------------------------------------------------------------
// Source-of-truth ENUMs and the EmScore contract consumed by the
// Coding Coach right-rail. The types deliberately mirror the AMA 2021
// rubric (docs/em-coding-rubric-2021.md) — when AMA publishes 2026
// updates the new constants flow into rubric.ts and any new fields land
// here first.
// ============================================================================

/** Per-element MDM level — minimum unit of decisional weight. */
export type ElementLevel = 'minimal' | 'low' | 'moderate' | 'high';

/** Resolved MDM tier — derived via 2-of-3 rule across (problems, data, risk). */
export type MdmTier = 'straightforward' | 'low' | 'moderate' | 'high';

/** New vs established patient (drives 99202-99205 vs 99211-99215). */
export type VisitType = 'established' | 'new';

/** Set of CPT codes the engine can suggest. */
export type EmCode =
  | '99202' | '99203' | '99204' | '99205'
  | '99211' | '99212' | '99213' | '99214' | '99215';

/** Per-HPI-element confidence (0..1) — used by the rail to render gradations. */
export interface HpiConfidence {
  location: number;
  quality: number;
  severity: number;
  duration: number;
  timing: number;
  context: number;
  modifyingFactors: number;
  associatedSignsSymptoms: number;
}

/** What the engine believes the SOAP supports. */
export interface SatisfiedCriteria {
  /** Count of distinct HPI elements detected (out of 8). */
  hpiElements: number;
  /** Count of distinct ROS systems detected (out of 14). */
  rosSystems: number;
  /** Count of PFSH categories detected (out of 3). */
  pfshCategories: number;
  /** Count of distinct exam organ systems detected (out of 11). */
  examSystems: number;
  /** MDM A — Number / complexity of problems addressed. */
  problems: ElementLevel;
  /** MDM B — Amount / complexity of data reviewed. */
  data: ElementLevel;
  /** MDM C — Risk of complications / morbidity. */
  risk: ElementLevel;
}

/** LLM judgement payload (per rubric §4.1 schema). */
export interface MdmJudgement {
  tier: MdmTier;
  elements: {
    problems: { level: ElementLevel; summary: string };
    data: { level: ElementLevel; summary: string };
    risk: { level: ElementLevel; summary: string };
  };
  confidence: number;
  rationale: string;
}

/** Time-fit info — how the recorded duration maps to the chosen code. */
export interface TimeFitScore {
  /** Code whose time band best fits the recorded minutes. */
  code: EmCode;
  /** Minutes inferred (lower bound — recorded face-to-face). */
  minutesUsed: number;
  /** Display string for the matched band, e.g. "20-29 min". */
  band: string;
}

/** Bump-CTA suggestion (per rubric §5). */
export interface BumpSuggestion {
  /** 'almost-there' = N gaps remain; 'confirm-bump' = already meets next level. */
  mode: 'almost-there' | 'confirm-bump';
  /** Target CPT code we're suggesting the doctor bump to. */
  toCode: EmCode;
  /** Human-readable gap descriptions. Empty for 'confirm-bump'. */
  gaps: string[];
  /** Static reference revenue delta (Medicare 2024 national avg). */
  revenueDelta: number;
}

/** Master output of computeEmScore — what the right-rail renders. */
export interface EmScore {
  /** Suggested CPT code given current SOAP content. */
  code: EmCode;
  /** Resolved MDM tier (2-of-3 across satisfied.{problems,data,risk}). */
  mdmTier: MdmTier;
  /** New vs established patient. */
  visitType: VisitType;
  /** Detected criteria — see SatisfiedCriteria. */
  satisfied: SatisfiedCriteria;
  /** Per-HPI-element confidence (0..1) so the rail can render gradations. */
  perElementConfidence: {
    hpi: HpiConfidence;
  };
  /** Next code up if achievable AND ≤2 gaps; null if no upgrade plausible. */
  bumpableTo: EmCode | null;
  /** Human-readable gap descriptions when bumpableTo !== null. */
  bumpGaps?: string[];
  /** Time-band fit for the chosen code, if a self-reported time was found. */
  timeFitScore: TimeFitScore | null;
  /** True if the LLM judged MDM successfully; false on fallback path. */
  llmJudged: boolean;
  /** Rubric version used (currently '2021.1'). */
  rubricVersion: '2021.1';
  /** ISO timestamp of when this score was computed. */
  computedAt: string;
  /** True if the LLM judgement came from cache (telemetry only). */
  cacheHit: boolean;
  /** Rationale text from the LLM (for audit / "why this score?" hover). */
  mdmRationale?: string;
  /** LLM confidence in its judgement (0..1). */
  mdmConfidence?: number;
}

/** Map of detected criteria (used internally for bump-gap diff). */
export interface CriterionMap {
  hpiElements: number;
  rosSystems: number;
  pfshCategories: number;
  examSystems: number;
  problems: ElementLevel;
  data: ElementLevel;
  risk: ElementLevel;
}
