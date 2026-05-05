// ============================================================================
// to-ui-score.ts — Phase 5.2 integration adapter
// ----------------------------------------------------------------------------
// The Coding Coach engine (Subagent B) produces `EmScore` per
// `lib/em-coding/types`. The rail UI (Subagent C) consumes a different
// shape from `lib/em-coding-ui/types` — the components were authored
// against UI-friendly field names (`suggestedCode`, `groups[]`,
// `bump.{mode, toCode, gaps, revenueDelta}`, `timeBand`) before the
// engine landed.
//
// Rather than rename either side at the field level (high blast radius
// for both branches' tests + components), this adapter does a one-way
// projection at the page.tsx integration boundary. The rail's API
// route (POST /api/visits/[id]/em-score) returns the engine shape; the
// CodingRail component consumes the UI shape. This adapter is the
// translation layer.
//
// Reference: rubric §5 (bump CTA) + §1.1/§1.2 (time bands).
// ============================================================================

import type { EmScore as EngineEmScore, ElementLevel, MdmTier } from './types';
import type {
  EmScore as UiEmScore,
  EmCriterion,
  EmCriterionGroup,
  EmTimeBand,
  BumpSuggestion as UiBumpSuggestion,
} from '../em-coding-ui/types';
import { revenueDelta } from '../em-coding-ui/revenueDelta';
import {
  criterionIdForGapLabel,
  suggestionForCriterionId,
} from './criterion-to-section';

/** AMA 2021 time bands (rubric §1.1/§1.2). Returned in seconds for UI consistency. */
const TIME_BANDS: Record<string, { min: number; max: number }> = {
  // Established
  '99211': { min: 0, max: 599 },
  '99212': { min: 600, max: 1140 },
  '99213': { min: 1200, max: 1740 },
  '99214': { min: 1800, max: 2340 },
  '99215': { min: 2400, max: 3240 },
  // New
  '99202': { min: 900, max: 1740 },
  '99203': { min: 1800, max: 2640 },
  '99204': { min: 2700, max: 3540 },
  '99205': { min: 3600, max: 4440 },
};

function timeBandFor(code: string): EmTimeBand {
  const band = TIME_BANDS[code] ?? { min: 0, max: 1800 };
  return { code: code as UiEmScore['suggestedCode'], min: band.min, max: band.max };
}

const LEVEL_RANK: Record<ElementLevel, number> = {
  minimal: 0,
  low: 1,
  moderate: 2,
  high: 3,
};

const TIER_RANK: Record<MdmTier, number> = {
  straightforward: 0,
  low: 1,
  moderate: 2,
  high: 3,
};

const TIER_LABEL: Record<MdmTier, string> = {
  straightforward: 'Straightforward',
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
};

const LEVEL_LABEL: Record<ElementLevel, string> = {
  minimal: 'Minimal',
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
};

/** Derive the History / Exam / MDM rail groups from the engine's
 *  satisfied counts. Each group has 2-3 criteria the rail renders. */
function deriveGroups(score: EngineEmScore): EmCriterionGroup[] {
  const sat = score.satisfied;
  const visitType = score.visitType;
  const isNew = visitType === 'new';

  // ── History group ──
  const hpiThreshold = 4;
  const rosThreshold = 2;
  const pfshThreshold = isNew ? 3 : 1;

  const historyItems: EmCriterion[] = [
    {
      id: 'hpi.elements',
      status: sat.hpiElements >= hpiThreshold ? 'ok' : 'warn',
      head:
        sat.hpiElements >= hpiThreshold
          ? `${sat.hpiElements}+ HPI elements detected`
          : `${sat.hpiElements} HPI elements (need ${hpiThreshold}+)`,
      sub:
        sat.hpiElements >= hpiThreshold
          ? 'location · quality · duration · timing (or similar)'
          : 'Add severity / context / modifying factors / associated sx',
      nudge:
        sat.hpiElements < hpiThreshold
          ? {
              text: '+ add 1 element',
              suggestion: 'e.g. "Severity 6/10, worse with deep breathing"',
            }
          : undefined,
    },
    {
      id: 'ros.systems',
      status: sat.rosSystems >= rosThreshold ? 'ok' : 'warn',
      head:
        sat.rosSystems >= rosThreshold
          ? `${sat.rosSystems} ROS systems documented`
          : `${sat.rosSystems} ROS systems (need ${rosThreshold}+)`,
      sub:
        sat.rosSystems >= rosThreshold
          ? 'pertinent positives + negatives'
          : 'Add 1 more system (e.g. constitutional / GI / GU)',
      nudge:
        sat.rosSystems < rosThreshold
          ? {
              text: '+ add 1 system',
              suggestion: 'e.g. "Constitutional: denies fever, weight loss"',
            }
          : undefined,
    },
    {
      id: 'pfsh.categories',
      status: sat.pfshCategories >= pfshThreshold ? 'ok' : 'warn',
      head:
        sat.pfshCategories >= pfshThreshold
          ? `${sat.pfshCategories} PFSH ${sat.pfshCategories === 1 ? 'category' : 'categories'} documented`
          : `${sat.pfshCategories} PFSH (need ${pfshThreshold}+)`,
      sub:
        sat.pfshCategories >= pfshThreshold
          ? 'past medical / family / social hx'
          : 'add 1 family / social hx line for 99214 boost',
      nudge:
        sat.pfshCategories < pfshThreshold
          ? {
              text: '+ add 1 line',
              suggestion: 'e.g. "Family hx HTN, mother. Lives with husband + 6yo son."',
            }
          : undefined,
    },
  ];

  const historySatisfied = historyItems.filter((i) => i.status === 'ok').length;

  // ── Exam group ──
  const examItems: EmCriterion[] = [
    {
      id: 'exam.systems',
      status: sat.examSystems >= 2 ? 'ok' : 'warn',
      head:
        sat.examSystems >= 8
          ? `${sat.examSystems} organ systems (comprehensive)`
          : sat.examSystems >= 5
            ? `${sat.examSystems} organ systems (detailed)`
            : sat.examSystems >= 2
              ? `${sat.examSystems} organ systems (expanded problem-focused)`
              : `${sat.examSystems} organ system (problem-focused)`,
      sub:
        sat.examSystems >= 2
          ? 'medically appropriate per AMA 2021'
          : 'Document findings on at least 1 more organ system',
    },
  ];

  // ── MDM group ──
  const mdmItems: EmCriterion[] = [
    {
      id: 'mdm.problems',
      status: 'ok',
      head: `Problems: ${LEVEL_LABEL[sat.problems]}`,
      sub: `Tier element A — ${LEVEL_LABEL[sat.problems]} complexity`,
    },
    {
      id: 'mdm.data',
      status: 'ok',
      head: `Data reviewed: ${LEVEL_LABEL[sat.data]}`,
      sub: `Tier element B — ${LEVEL_LABEL[sat.data]} amount`,
    },
    {
      id: 'mdm.risk',
      status: 'ok',
      head: `Risk: ${LEVEL_LABEL[sat.risk]}`,
      sub: `Tier element C — ${LEVEL_LABEL[sat.risk]} morbidity risk`,
    },
  ];

  return [
    {
      id: 'history',
      title: 'History (HPI)',
      summary: `${historySatisfied} of 3 satisfied`,
      items: historyItems,
      footer:
        historySatisfied === 3
          ? { satisfied: 'extended history complete' }
          : { satisfied: `${historySatisfied} of 3`, nextLevel: 'Need 3 of 3 for 99214' },
    },
    {
      id: 'exam',
      title: 'Exam',
      summary: `${sat.examSystems} systems`,
      items: examItems,
    },
    {
      id: 'mdm',
      title: 'Medical Decision Making',
      summary: `${TIER_LABEL[score.mdmTier]} tier (${TIER_RANK[score.mdmTier] + 1} of 4)`,
      items: mdmItems,
      footer: { satisfied: `2-of-3 → ${TIER_LABEL[score.mdmTier]}` },
    },
  ];
}

/** Project engine bump → UI bump.
 *  Phase 5.2 stub completion — gap.criterionId now derives from the
 *  gap label's prefix so the BumpModal's apply-additions payload
 *  carries a meaningful id (`hpi.elements` / `ros.systems` / etc.)
 *  that the server route can map to a SOAP section. The pre-fix
 *  positional `gap.0` ids were placeholders for the never-landed
 *  Subagent B integration. */
function deriveBump(score: EngineEmScore): UiBumpSuggestion | null {
  if (!score.bumpableTo) return null;
  const gaps = (score.bumpGaps ?? []).map((label) => {
    const criterionId = criterionIdForGapLabel(label);
    return {
      criterionId,
      label,
      suggestion: suggestionForCriterionId(criterionId),
    };
  });
  return {
    mode: gaps.length === 0 ? 'confirm-bump' : 'almost-there',
    toCode: score.bumpableTo as UiBumpSuggestion['toCode'],
    gaps,
    revenueDelta: revenueDelta(
      score.code as Parameters<typeof revenueDelta>[0],
      score.bumpableTo as Parameters<typeof revenueDelta>[1]
    ),
  };
}

/** The integration adapter. */
export function engineToUiScore(engine: EngineEmScore, visitTimeSec = 0): UiEmScore {
  return {
    suggestedCode: engine.code,
    visitType: engine.visitType,
    mdmTier: engine.mdmTier,
    llmJudged: engine.llmJudged,
    confidence: engine.perElementConfidence?.hpi
      ? 0.9
      : 0.75,
    timeBand: timeBandFor(engine.code),
    visitTimeSec: engine.timeFitScore?.minutesUsed
      ? engine.timeFitScore.minutesUsed * 60
      : visitTimeSec,
    estimatedTotalSec: engine.timeFitScore?.minutesUsed
      ? Math.round(engine.timeFitScore.minutesUsed * 60 * 1.7)
      : undefined,
    groups: deriveGroups(engine),
    bump: deriveBump(engine),
    override: undefined,
    computedAt: new Date().toISOString(),
  };
}
