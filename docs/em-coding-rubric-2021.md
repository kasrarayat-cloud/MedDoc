# AMA 2021 E&M Coding Rubric (QuillMD canonical reference)

**Single source of truth** for the QuillMD Coding Coach. Both the deterministic rule engine (HPI / ROS / exam counts) and the LLM MDM judge consume this document. When AMA publishes 2026 updates the LLM rubric prompt + deterministic constants both flow from edits here.

> **Scope.** Office or other outpatient services, established + new patient (CPT 99202–99205, 99211–99215). QuillMD does not currently scope hospital, ED, or critical care codes — those are out of scope for the Coding Coach v1.

---

## 1. Code ladder

### 1.1 Established patient (99211–99215)

The doctor selects the code based on **either** the level of MDM (medical decision making) **OR** total time on the date of the encounter. Whichever supports the higher level wins (and is documented as the basis).

| CPT | MDM tier | Time threshold (total time, date of encounter) |
|---|---|---|
| 99211 | n/a — minimal, may not require physician | n/a |
| 99212 | Straightforward | 10–19 min |
| 99213 | Low | 20–29 min |
| 99214 | Moderate | 30–39 min |
| 99215 | High | 40–54 min |
| 99417 | (add-on, prolonged) | each additional 15 min beyond 99215 max |

### 1.2 New patient (99202–99205)

| CPT | MDM tier | Time threshold |
|---|---|---|
| 99202 | Straightforward | 15–29 min |
| 99203 | Low | 30–44 min |
| 99204 | Moderate | 45–59 min |
| 99205 | High | 60–74 min |
| 99417 | (add-on, prolonged) | each additional 15 min beyond 99205 max |

99201 was deleted in 2021.

### 1.3 Time definition (AMA 2021)

"Total time" = the practitioner's time spent on the date of the encounter, including:
- Preparing to see the patient (review of records)
- Obtaining and reviewing separately obtained history
- Performing a medically appropriate examination
- Counseling and educating the patient
- Ordering medications, tests, or procedures
- Documenting clinical information
- Independently interpreting results and communicating
- Care coordination (when not separately reported)

Excluded: time on travel, teaching general principles, time billed separately under other codes.

QuillMD operationalization for the Coding Coach:
- **`audioDurationSec`** for `audio_upload` visits = **lower bound** (recorded face-to-face only). When this is the only time signal, multiply by 1.7× to estimate total time (literature suggests doctors spend ~70% additional time on documentation + chart review + after-visit work for typical PCP encounters). Mark this estimate as such in the UI rationale.
- **`dictationDurationSec`** for `voice_dictation` = the dictation length (not face-to-face; treat as documentation time only, do not extrapolate)
- **Wall-clock from `createdAt → signedAt`** for `text_notes` or as a sanity ceiling
- The Coding Coach time meter shows the LOWER bound (recorded) prominently, with an "estimated total ≈ Xm" tooltip that uses the multiplier.

The deterministic engine MUST NOT auto-bump a code purely on the multiplier-extrapolated estimate — only the lower bound + MDM justification can move the code. The doctor can manually set total time via the override dropdown if their actual time differs.

---

## 2. MDM tier definitions

Each MDM tier requires **2 of 3** elements at that level:
- A: Number / complexity of problems addressed
- B: Amount / complexity of data reviewed and analyzed
- C: Risk of complications and/or morbidity or mortality of patient management

### 2.1 Straightforward (99202 / 99212)

| Element | Definition |
|---|---|
| A — Problems | 1 self-limited or minor problem |
| B — Data | Minimal or none |
| C — Risk | Minimal risk of morbidity from additional dx testing or treatment |

Examples: routine cold w/o complication, simple URI requiring rest + OTC.

### 2.2 Low (99203 / 99213)

| Element | Definition |
|---|---|
| A — Problems | 2+ self-limited or minor problems; OR 1 stable chronic illness; OR 1 acute uncomplicated illness or injury; OR 1 stable acute illness; OR 1 acute uncomplicated illness or injury requiring hospital observation level of care |
| B — Data | Must meet ≥1 of: <br/>• Category 1 — review of any combination of 2 unique tests/notes/sources (e.g., review prior external note + review test result; OR order 2 tests; OR review external test + order 1 test; OR independent historian assessment) <br/>• Category 2 — assessment requiring an independent historian |
| C — Risk | Low risk of morbidity from additional dx testing or treatment |

Examples: HTN follow-up well-controlled on monotherapy; sprain w/ rest + ice; uncomplicated UTI w/ macrobid.

### 2.3 Moderate (99204 / 99214)

| Element | Definition |
|---|---|
| A — Problems | 1+ chronic illness with exacerbation/progression/side effects of treatment; OR 2+ stable chronic illnesses; OR 1 undiagnosed new problem with uncertain prognosis; OR 1 acute illness with systemic symptoms; OR 1 acute complicated injury |
| B — Data | Must meet ≥1 of: <br/>• Category 1 — review of any combination of 3 unique tests/notes/sources <br/>• Category 2 — independent interpretation of test performed by another physician (not separately reported) <br/>• Category 3 — discussion of management or test interpretation with external physician (not separately reported) |
| C — Risk | Moderate risk of morbidity. Examples: prescription drug management; decision regarding minor surgery with identified risk factors; decision regarding elective major surgery without identified risk factors; diagnosis or treatment significantly limited by social determinants of health; drug therapy requiring intensive monitoring for toxicity |

Examples: bronchitis on otherwise-stable HTN patient with rx of albuterol (Rx mgmt = moderate risk by itself); CHF exacerbation requiring loop diuretic adjustment; new-onset chest pain w/ uncertain prognosis pending stress test.

### 2.4 High (99205 / 99215)

| Element | Definition |
|---|---|
| A — Problems | 1+ chronic illness w/ severe exacerbation/progression or side effects of treatment; OR 1 acute or chronic illness or injury that poses a threat to life or bodily function |
| B — Data | Must meet ≥2 of: <br/>• Category 1 (3+ tests reviewed/ordered) <br/>• Category 2 (independent interpretation) <br/>• Category 3 (discussion with external physician) |
| C — Risk | High risk of morbidity. Examples: drug therapy requiring intensive monitoring for toxicity; decision regarding elective major surgery with identified risk factors; decision regarding emergency major surgery; decision regarding hospitalization or escalation of care; decision not to resuscitate or to deescalate care; parenteral controlled substances |

Examples: STEMI requiring transfer to cath lab; acute decompensated CHF requiring admission; suicidal ideation requiring hospitalization decision.

### 2.5 Tier resolution algorithm

```
function resolveTier(A: ElementLevel, B: ElementLevel, C: ElementLevel): MdmTier {
  // Sort element levels descending. Tier = 2nd-highest level.
  const sorted = [A, B, C].sort((x, y) => levelRank(y) - levelRank(x));
  return sorted[1];  // 2nd of 3
}
```

This implements "2 of 3 at that level" exactly — if the top 2 are at level X, tier = X.

---

## 3. Deterministic counting rules (the engine's pure-TS half)

### 3.1 HPI elements (8 standard, count distinct)

The 1995/1997 HPI elements remain the canonical taxonomy for "elements of HPI" even under 2021 guidelines (which relax the formal requirement, but auditors still reference the 8 elements when defending counts). The deterministic engine extracts these from the Subjective section:

| Element | Detection heuristic |
|---|---|
| Location | Body region or site (e.g., "chest", "right knee", "epigastric") |
| Quality | Adjective describing nature (e.g., "sharp", "dull", "productive cough") |
| Severity | Numeric scale or qualitative (e.g., "8/10", "moderate") |
| Duration | Time span (e.g., "3 days", "since Tuesday", "1 week h/o") |
| Timing | Temporal pattern (e.g., "intermittent", "constant", "morning only") |
| Context | Setting / triggers (e.g., "after eating", "at rest") |
| Modifying factors | What helps / worsens (e.g., "improved with rest", "worse with movement") |
| Associated signs/symptoms | Co-occurring (e.g., "with nausea", "denies fever") |

Detection is heuristic via regex / keyword family. False-positives accepted at the tail (counting "denies X" as an associated-symptoms mention is OK; missing a subtle "burning quality" hidden in prose is suboptimal but tolerable). The engine emits a **per-element confidence** (0–1) so the rail can render gradations.

Threshold:
- 1–3 elements = brief HPI
- 4+ elements = extended HPI (required for level 99214/99204+ history)

### 3.2 ROS systems (14 canonical)

Constitutional, Eyes, ENT/Mouth, Cardiovascular, Respiratory, Gastrointestinal, Genitourinary, Musculoskeletal, Integumentary (skin/breast), Neurological, Psychiatric, Endocrine, Hematologic/Lymphatic, Allergic/Immunologic.

Detection: explicit system name OR "denies [symptom-of-system]" pattern (e.g., "denies SOB" → respiratory). The engine uses a system→keyword map.

Thresholds:
- 1 system = problem-pertinent ROS
- 2–9 systems = extended ROS
- 10+ systems = complete ROS (rare in PCP; common in hospital admission notes)

### 3.3 PFSH (3 categories)

- **Past medical/surgical hx**: any line referencing prior conditions, surgeries, hospitalizations
- **Family hx**: explicit "family hx" / "FHx" / "father/mother/sibling has…"
- **Social hx**: tobacco / alcohol / drugs / occupation / living situation / diet / exercise

Thresholds (per 1995/1997 guidance):
- 0 categories = no PFSH
- 1 category = pertinent PFSH
- 2+ categories = complete PFSH for established patients (need 3 for new patients)

### 3.4 Exam organ systems (11 canonical, 1995 guidelines)

Constitutional, HEENT, Cardiovascular, Respiratory, Gastrointestinal, Genitourinary, Musculoskeletal, Skin, Neurologic, Psychiatric, Hematologic/Lymphatic/Immunologic.

Under AMA 2021 the formal exam requirement was dropped (only "medically appropriate" exam needed). But the Coding Coach uses system count as a *proxy for completeness* — it doesn't gate the suggested code on exam count alone, but rail criteria show count for clinical communication.

Thresholds:
- 1 system = problem-focused
- 2–4 systems = expanded problem-focused
- 5–7 systems = detailed
- 8+ systems = comprehensive

### 3.5 Time-based hints

Look for explicit time mentions in SOAP body or visit metadata:
- "Visit time: NN min"
- "Total time spent: NN min"
- "Counseling and coordination of care: NN min"

The engine returns `timeSelfReported: number | null`. If absent, fall back to the multiplier-extrapolated `audioDurationSec * 1.7` for the rail's *estimate* — but never use the estimate to auto-bump.

---

## 4. LLM MDM judgement (the engine's Claude half)

The LLM judges only the MDM tier (the genuinely subjective part). It does not count HPI/ROS/exam — those are deterministic.

### 4.1 Prompt template

System prompt (for the LLM via QuillMD's ModelClient):

```
You are an expert AMA 2021 E&M auditor. Given a SOAP note, judge the MDM (medical decision making) tier per the AMA 2021 Office E&M guidelines. Use the 2-of-3 rule: tier = the 2nd-highest of (A) problems addressed, (B) data reviewed, (C) risk of complications.

Output ONLY a JSON object matching this exact schema:

{
  "tier": "straightforward" | "low" | "moderate" | "high",
  "elements": {
    "problems": {
      "level": "minimal" | "low" | "moderate" | "high",
      "summary": "<1-2 sentence justification>"
    },
    "data": {
      "level": "minimal" | "low" | "moderate" | "high",
      "summary": "<1-2 sentence justification>"
    },
    "risk": {
      "level": "minimal" | "low" | "moderate" | "high",
      "summary": "<1-2 sentence justification>"
    }
  },
  "confidence": 0.0..1.0,
  "rationale": "<2-4 sentences explaining how 2-of-3 was resolved>"
}

Rules:
- tier MUST equal the 2nd-highest of problems/data/risk levels
- confidence 0.95+ for unambiguous cases (clear textbook examples)
- confidence 0.70-0.94 for typical PCP encounters with some judgment calls
- confidence <0.70 for genuinely ambiguous cases
- Rx management = automatic moderate-risk floor (do not assign "low" risk to any encounter that prescribes a new medication or adjusts an existing one)
- Decision-not-to-resuscitate, hospitalization decision, parenteral controlled substances = automatic high-risk floor
- "Routine refill of long-stable medication" with no dose change = low-risk (NOT moderate)
- New diagnostic uncertainty = at least moderate-problems
```

User prompt: the SOAP body in markdown form. Nothing else.

### 4.2 Caching strategy

Two layers stack: a 5-min Anthropic prompt cache on the rubric system prompt (in front of the model) and a 7-day Redis cache on the JUDGEMENT (in front of the API call entirely).

- **Anthropic prompt cache (provider layer)**: the rubric system prompt block sets `cache_control: { type: 'ephemeral' }`. Within the 5-minute Anthropic cache window, repeat calls reuse the cached system tokens at ~10% of normal input cost. The rubric is intentionally sized at ~2.6K tokens — empirical probing on `claude-sonnet-4-6` (Anthropic SDK 0.85.0) showed the actual cache eligibility threshold is ~2048 tokens, NOT the 1024-token figure quoted in older docs. A 1591-token version of this prompt was tested and silently no-op'd (zero `cache_creation_input_tokens`). The current size leaves comfortable headroom above the threshold and the additional content is substantive (worked examples, common documentation traps), not filler.
- **Cache key (Redis layer)**: SHA-256 of the normalized SOAP body (collapse whitespace, lowercase, strip line numbers).
- **Cache duration (Redis layer)**: 7 days (visits don't typically get re-scored long after sign).
- **Cache layer (Redis)**: hash `em_mdm_cache:<sha256>`.
- **Cache hit path (Redis)**: deserialize the prior judgement, return immediately. Track cache-hit rate as a metric.
- **Cache miss path (Redis)**: call Claude (with prompt-cache control attached), store result in Redis with 7d TTL.
- **Bypass**: if SOAP edit changes >20% of characters since last cached judgement, force re-judge. Otherwise reuse cached.
- **Timeout policy**: 30s soft cap on the LLM call (the 5.2 hotfix bumped this from 8s after corpus runs showed cold calls realistically take 6-10s; 8s missed ~50% of cold calls and silently degraded Path C → Path A). Bail to deterministic if the call is genuinely stuck rather than block the UI.

### 4.3 Failure modes

- **Claude API down** (5xx) → return deterministic-MDM fallback (heuristic combining problem count + Rx presence + chronic-disease detection) with `llmJudged: false`. Rail shows mono "MDM auto-judged · refresh to re-score" subtle hint.
- **JSON parse error** → log to telemetry, retry once with stricter system message, then fall back to deterministic.
- **Timeout (>30s)** → cancel, return deterministic fallback.
- **Refused / empty response** → fallback.

### 4.4 Deterministic-MDM fallback heuristic

When the LLM is unavailable, score MDM heuristically:

```
function deterministicMdm(soap, icdCodes, rxDrafts): MdmTier {
  const problemCount = icdCodes.length;
  const hasRxNew = rxDrafts.some(r => r.action === 'new' || r.action === 'increase');
  const hasRxAdjust = rxDrafts.some(r => r.action === 'discontinue' || r.action === 'decrease');
  const chronicDiseaseCount = icdCodes.filter(c => isChronicDisease(c.code)).length;
  const acuteSystemicCount = icdCodes.filter(c => hasSystemicMarker(soap, c.code)).length;

  // Risk
  let risk = 'minimal';
  if (hasRxNew || hasRxAdjust) risk = 'moderate';  // Rx mgmt floor
  if (mentionsHospitalizationDecision(soap)) risk = 'high';

  // Problems
  let problems = 'minimal';
  if (problemCount === 1) problems = 'low';
  if (problemCount >= 2 && chronicDiseaseCount >= 2) problems = 'moderate';
  if (acuteSystemicCount >= 1) problems = 'moderate';
  if (mentionsLifeThreat(soap)) problems = 'high';

  // Data — fallback assumes "low" if any imaging/lab mention
  let data = 'minimal';
  if (mentionsLabsOrImaging(soap)) data = 'low';
  if (countLabsImagingMentions(soap) >= 3) data = 'moderate';

  return resolveTier(problems, data, risk);
}
```

This runs in <5 ms. Coverage tradeoff: misses LLM-judged nuance like "uncertain prognosis", but gets the 80% case right. Used only as fallback.

---

## 5. Bump-CTA logic

The "Bump to 99214 · +$32" CTA appears when the current code is N levels below the achievable code AND the gap is ≤2 deterministic criteria.

```
function shouldShowBumpCta(current: EmCode, score: EmScore): BumpSuggestion | null {
  const nextLevel = nextLevelUp(current);
  if (!nextLevel) return null;  // already 99215/99205
  const nextRequired = requirementsFor(nextLevel);
  const gaps = diffRequirements(score.satisfied, nextRequired);
  if (gaps.length === 0) {
    // Already meets next level — UI shows "Confirm 99214" instead
    return { mode: 'confirm-bump', toCode: nextLevel, gaps: [] };
  }
  if (gaps.length <= 2) {
    return {
      mode: 'almost-there',
      toCode: nextLevel,
      gaps,
      revenueDelta: revenueDelta(current, nextLevel)
    };
  }
  return null;  // gap too large — don't surface
}
```

Revenue delta uses a static 2024 reference table (Medicare physician fee schedule, national average):

| Code pair | Delta |
|---|---|
| 99213 → 99214 | $32 |
| 99214 → 99215 | $44 |
| 99203 → 99204 | $52 |
| 99204 → 99205 | $76 |
| 99212 → 99213 | $20 |
| 99202 → 99203 | $28 |

These are illustrative anchors for the CTA UI. Actual reimbursement varies by payer; the rail makes this clear with "Saves $7,800/yr · avg PCP" footer (AMA reference).

### 5.1 Override flow

Doctor explicit override stored as `cptCodes.em.override = { code, reason?, overriddenAt }`:
- Override does NOT bypass scoring — the rail still computes the suggested level, but presents the override prominently
- Audit trail captures both suggested + overridden + delta

---

## 6. Test corpus structure

Each fixture is a markdown file at `tests/fixtures/soap-em-corpus/<id>.md` with frontmatter:

```yaml
---
id: <unique-id>
category: routine-pcp | acute | complex-chronic | edge-case
expected:
  code: 99213
  mdmTier: low
  hpiElements: 4
  rosSystems: 3
  pfshCategories: 2
  examSystems: 4
  problems: low
  data: low
  risk: low
visitType: established | new
notes: <brief authoring rationale>
---
## Subjective
...
## Objective
...
## Assessment
...
## Plan
...
```

The engine's test harness loads each fixture, runs `computeEmScore`, and asserts:
- `score.code === expected.code` (exact match)
- `score.mdmTier === expected.mdmTier` (exact match)
- `score.satisfied.hpiElements >= expected.hpiElements - 1 && <= expected.hpiElements + 1` (±1 element wiggle)
- Same ±1 wiggle for ros / pfsh / exam counts
- `score.satisfied.problems === expected.problems` (exact)
- Same for data + risk

**Pass threshold**: ≥28/30 fixtures pass to ship. Fixture-level failures must include a comment explaining whether the engine or the fixture is wrong (sometimes the corpus needs re-calibration).

---

## 7. Versioning

Rubric v1.0 = AMA 2021 (effective 2021-01-01).

When AMA publishes 2026 updates:
1. Edit this document (single source of truth)
2. Update `lib/em-coding/rubric.ts` constants to match
3. Update LLM system prompt accordingly
4. Re-run test corpus; if accuracy drops, calibrate fixtures or add new ones
5. Bump rubric version + database migration adds `em_score.rubric_version` for audit

The rubric version is captured in `cptCodes.em.rubricVersion` so historical visits remain coded against the rubric in effect at sign time.
