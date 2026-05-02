// ============================================================================
// E&M Coding — deterministic counters (Phase 5.2)
// ----------------------------------------------------------------------------
// Pure-TS counters that extract the auditable surface of a SOAP note:
//   countHpiElements   — 8 HPI elements (per rubric §3.1)
//   countRosSystems    — 14 ROS systems (per rubric §3.2)
//   countPfshCategories— 3 PFSH categories (per rubric §3.3)
//   countExamSystems   — 11 organ systems on exam (per rubric §3.4)
//   detectTimeBasedHints — explicit "Visit time:" mentions (per rubric §3.5)
//
// Strict design:
//   * No I/O (no DB, no Redis, no LLM).
//   * The Subjective body drives HPI / ROS / PFSH detection; Objective
//     drives exam. Each function takes a section string so callers can
//     pre-split via parseSoapSections() or pass raw markdown that the
//     internal soapToSections() helper splits.
//   * False positives at the long tail are accepted (rubric §3.1).
// ============================================================================

import { parseSoapSections, type SoapSection } from '@/lib/parse-soap-sections';
import {
  EXAM_KEYWORDS,
  EXAM_SYSTEMS,
  HPI_ELEMENTS,
  HPI_PATTERNS,
  PFSH_CATEGORIES,
  PFSH_KEYWORDS,
  ROS_KEYWORDS,
  ROS_SYSTEMS,
  TIME_HINT_PATTERNS,
  type ExamSystem,
  type HpiElement,
  type PfshCategory,
  type RosSystem,
} from './rubric';
import type { HpiConfidence } from './types';

/** Internal — split markdown SOAP into S/O/A/P bodies once per call. */
function soapToSections(markdown: string): Record<'S' | 'O' | 'A' | 'P', string> {
  const sections: SoapSection[] = parseSoapSections(markdown);
  const out: Record<'S' | 'O' | 'A' | 'P', string> = {
    S: '', O: '', A: '', P: '',
  };
  for (const s of sections) out[s.key] = s.body;
  return out;
}

/** Strip markdown bold/italic markers + collapse whitespace so regex
 *  patterns aren't tripped by `**Quality:**` style headers. */
function normalize(text: string): string {
  return text
    .replace(/\*\*?/g, '')
    .replace(/_+/g, ' ')
    .replace(/\s+/g, ' ');
}

// ============================================================================
// HPI — 8 elements
// ============================================================================

export interface HpiResult {
  /** Number of distinct HPI elements detected (0-8). */
  count: number;
  /** Per-element confidence (0..1). 0 = no signal, 1 = explicit tag match. */
  confidence: HpiConfidence;
  /** Names of elements that fired (subset of HPI_ELEMENTS). */
  matched: HpiElement[];
}

/** Score a single HPI element against the Subjective body. Returns
 *  0..1 confidence — explicit "Quality:" tag match scores 1, looser
 *  keyword family match scores 0.5–0.7, no match scores 0. */
function scoreHpiElement(element: HpiElement, body: string): number {
  const patterns = HPI_PATTERNS[element];
  for (let i = 0; i < patterns.length; i++) {
    if (patterns[i].test(body)) {
      // First pattern in each family is the explicit-tag one ("location:")
      // — give it max confidence. Others are heuristic; bump them down
      // a notch so the rail can render gradations.
      return i === 0 ? 1 : 0.65;
    }
  }
  return 0;
}

/** Counts the number of distinct HPI elements that fire in the
 *  Subjective body. Pass either the raw SOAP markdown or the
 *  Subjective body directly; the function handles both. */
export function countHpiElements(input: string): HpiResult {
  const body = normalize(
    input.includes('## Subjective') || input.includes('## subjective')
      ? soapToSections(input).S
      : input
  );

  const confidence: HpiConfidence = {
    location: 0,
    quality: 0,
    severity: 0,
    duration: 0,
    timing: 0,
    context: 0,
    modifyingFactors: 0,
    associatedSignsSymptoms: 0,
  };
  const matched: HpiElement[] = [];

  for (const elem of HPI_ELEMENTS) {
    const score = scoreHpiElement(elem, body);
    confidence[elem] = score;
    if (score > 0) matched.push(elem);
  }

  return {
    count: matched.length,
    confidence,
    matched,
  };
}

// ============================================================================
// ROS — 14 systems
// ============================================================================

export interface RosResult {
  count: number;
  matched: RosSystem[];
}

export function countRosSystems(input: string): RosResult {
  const body = normalize(
    input.includes('## Subjective') || input.includes('## subjective')
      ? soapToSections(input).S
      : input
  );

  const matched: RosSystem[] = [];
  for (const sys of ROS_SYSTEMS) {
    const patterns = ROS_KEYWORDS[sys];
    for (const p of patterns) {
      if (p.test(body)) {
        matched.push(sys);
        break; // one hit per system is enough
      }
    }
  }

  return { count: matched.length, matched };
}

// ============================================================================
// PFSH — 3 categories
// ============================================================================

export interface PfshResult {
  count: number;
  matched: PfshCategory[];
}

export function countPfshCategories(input: string): PfshResult {
  const body = normalize(
    input.includes('## Subjective') || input.includes('## subjective')
      ? soapToSections(input).S
      : input
  );

  const matched: PfshCategory[] = [];
  for (const cat of PFSH_CATEGORIES) {
    const patterns = PFSH_KEYWORDS[cat];
    for (const p of patterns) {
      if (p.test(body)) {
        matched.push(cat);
        break;
      }
    }
  }

  return { count: matched.length, matched };
}

// ============================================================================
// Exam — 11 organ systems (1995 guidelines)
// ============================================================================

export interface ExamResult {
  count: number;
  matched: ExamSystem[];
}

export function countExamSystems(input: string): ExamResult {
  const body = normalize(
    input.includes('## Objective') || input.includes('## objective')
      ? soapToSections(input).O
      : input
  );

  const matched: ExamSystem[] = [];
  for (const sys of EXAM_SYSTEMS) {
    const patterns = EXAM_KEYWORDS[sys];
    for (const p of patterns) {
      if (p.test(body)) {
        matched.push(sys);
        break;
      }
    }
  }

  return { count: matched.length, matched };
}

// ============================================================================
// Time-based hints (rubric §3.5)
// ============================================================================

export interface TimeHintResult {
  /** Self-reported total time in minutes, or null if no explicit mention. */
  minutes: number | null;
  /** The specific phrase that matched (for audit). */
  matchedPhrase?: string;
}

export function detectTimeBasedHints(input: string): TimeHintResult {
  // Time hints can appear anywhere in the note — search the full text
  // (don't restrict to a section).
  const text = input;
  for (const p of TIME_HINT_PATTERNS) {
    const m = p.exec(text);
    if (m && m[1]) {
      const mins = parseInt(m[1], 10);
      if (!Number.isNaN(mins) && mins > 0 && mins < 600) {
        return { minutes: mins, matchedPhrase: m[0] };
      }
    }
  }
  return { minutes: null };
}
