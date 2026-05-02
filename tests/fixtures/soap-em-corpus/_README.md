# SOAP E&M Test Corpus

Calibration corpus for the QuillMD Coding Coach hybrid scoring engine.

## Status

**Anchor fixtures (8 authored by lead)** — these set the bar for engine accuracy and demonstrate all 4 categories + the 2-of-3 MDM resolution algorithm:

| ID | Category | Expected | Note |
|---|---|---|---|
| 01-routine-bronchitis-followup | routine-pcp | 99213 / low | The Mei-Ling Park canonical visit. New Rx → moderate risk floor; 1 acute uncomplicated → low problems; 2-of-3 → low → 99213. **Bumpable to 99214** — typical undercoding case. |
| 02-routine-htn-stable-refill | routine-pcp | 99213 / low | Stable HTN refill. Long-stable Rx, no dose change → low risk (NOT moderate per rubric §4.1). |
| 03-routine-uri-uncomplicated | routine-pcp | 99212 / straightforward | 1 self-limited problem, OTC-only mgmt. All 3 elements minimal. |
| 11-acute-chest-pain-workup | acute | 99214 / moderate | Atypical chest pain w/ EKG + troponin + ASA initiation. Moderate problems (uncertain prognosis) + moderate data (3+ tests) + moderate risk (Rx + decision re stress test). |
| 12-acute-uncomplicated-uti | acute | 99213 / low | 1 acute uncomplicated infection + UA + new Rx (nitrofurantoin). Same pattern as fixture 01. |
| 21-complex-dm-exacerbation | complex-chronic | 99215 / high | T2DM A1c 11.4% w/ insulin initiation + multiple chronic comorbidities. High problems + moderate data + high risk → high tier. |
| 22-complex-chf-exacerbation | complex-chronic | 99215 / high | CHF exacerbation w/ outpatient diuresis intensification + decision re hospitalization. Clear high-tier across all 3 elements. |
| 26-edge-boilerplate-heavy | edge-case | 99213 / low | Tests engine resistance to ROS template-padding. 14-system "all negative" ROS does NOT inflate problem count. |

**Subagent B (engine subagent) is responsible for extending this to ≥30 fixtures during calibration.**

## Distribution target (≥30 total)

| Category | Anchor count | Target total | Subagent B to add |
|---|---|---|---|
| routine-pcp | 3 | 10 | 7 |
| acute | 2 | 10 | 8 |
| complex-chronic | 2 | 5 | 3 |
| edge-case | 1 | 5 | 4 |

Suggested gap fills (Subagent B may deviate based on engine calibration needs):

**routine-pcp (need 7):**
- annual physical / preventive (low MDM)
- routine DM follow-up A1c at goal (low MDM, 1 stable chronic)
- thyroid med dose adjustment (low MDM, low data via TSH order, low risk via stable adjustment)
- depression follow-up SSRI well-tolerated (low MDM)
- contraceptive counseling + refill (straightforward MDM)
- multi-condition refill bundle (HTN + lipid + DM all stable; tests 2+ stable chronic = moderate problems)
- well-woman visit w/ pap (procedural, may exclude E&M scoring)

**acute (need 8):**
- joint sprain (acute uncomplicated injury)
- acute back strain (acute uncomplicated, OTC mgmt)
- conjunctivitis (acute uncomplicated)
- acute sinusitis w/ Rx (low + Rx mgmt = 99213 same pattern)
- migraine acute (Rx mgmt + uncertain prognosis if first time)
- abdominal pain w/u (uncertain prognosis = moderate problems)
- new shortness-of-breath workup
- ear infection w/ Rx

**complex-chronic (need 3):**
- multi-system follow-up (DM + HTN + CKD all stable, no exacerbation; 2+ stable chronic = moderate problems)
- COPD exacerbation requiring steroid burst (moderate-high)
- HFpEF stable maintenance (low if all stable, moderate if any worsening)

**edge-case (need 4):**
- very short SOAP (3 lines per section) — tests minimum-content handling
- very long SOAP (>2000 words) — tests scoring stability
- ICD codes only, no MDM-relevant prose — tests fallback behavior
- prompt-injection in patient quote ("ignore previous instructions...") — tests LLM safety

## Fixture format

Each `.md` file uses YAML frontmatter:

```yaml
---
id: <unique-id>
category: routine-pcp | acute | complex-chronic | edge-case
expected:
  code: <CPT>
  mdmTier: straightforward | low | moderate | high
  hpiElements: <number>
  rosSystems: <number>
  pfshCategories: <number>
  examSystems: <number>
  problems: minimal | low | moderate | high
  data: minimal | low | moderate | high
  risk: minimal | low | moderate | high
visitType: established | new
bumpableTo: <CPT or null>
notes: |
  <authoring rationale; explain MDM tier resolution>
---
```

Followed by 4 markdown sections: `## Subjective`, `## Objective`, `## Assessment`, `## Plan`.

## Test harness contract (Subagent B implements)

Located at `apps/transcribe-md/src/lib/em-coding/__tests__/corpus.test.ts`:

```typescript
import { computeEmScore } from '../score';
import { loadFixtures } from '../test-utils';

describe('em-coding corpus', () => {
  const fixtures = loadFixtures('/opt/meddoc-pro/tests/fixtures/soap-em-corpus');
  for (const fx of fixtures) {
    test(fx.id, async () => {
      const score = await computeEmScore(fx.soap, /* mdmCachedJudgement: */ null);
      expect(score.code).toBe(fx.expected.code);
      expect(score.mdmTier).toBe(fx.expected.mdmTier);
      expect(score.satisfied.hpiElements).toBeGreaterThanOrEqual(fx.expected.hpiElements - 1);
      expect(score.satisfied.hpiElements).toBeLessThanOrEqual(fx.expected.hpiElements + 1);
      // ...same ±1 wiggle for ros / pfsh / exam
      expect(score.satisfied.problems).toBe(fx.expected.problems);
      expect(score.satisfied.data).toBe(fx.expected.data);
      expect(score.satisfied.risk).toBe(fx.expected.risk);
    });
  }
});
```

**Pass threshold**: ≥28/30 fixtures pass. Failures must include a comment explaining whether engine or fixture is wrong.

## Source of truth

This corpus is derived from `docs/em-coding-rubric-2021.md`. When AMA updates the rubric, regenerate this corpus' expected values via the new rules.
