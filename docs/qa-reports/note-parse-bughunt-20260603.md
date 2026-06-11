# Phase 2a parse-engine bug hunt — Dr. A note (2026-06-03)

**Discovery run only — nothing fixed this pass.** Ran the dormant `parseNoteToTemplate` against the exact Dr. A note, 5 total real-LLM runs (3 end-to-end + 2 with full intermediate visibility). Source unchanged; the only writes were a throwaway script (deleted) and this doc.

---

## HEADLINE — PHI-gate verdict: NO LEAK ✅

**No PHI leaked, in any run, pre- or post-gate.** A substring leak-test against the built template for every fake identifier (name "Gonzalez"/"Maria", MRN value `RFM-0098214`, DOB `04/12/1979`, doctor "Whitfield", NPI `1487654321`, insurance `XQ4471892`, clinic name/address/phone, and patient values `142/88`/`31.2`/`7.9`/glucose/doses/ICD codes) was **CLEAN on every run**. The LLM extracted format-only; the gate is a backstop that never had to catch a real value. **2b is NOT blocked on a PHI leak.**

The gate's failure mode is the SAFE one: it **rejects** (over-conservative) rather than leaks. But that over-rejection is itself the main bug below.

---

## What worked well (the engine is mostly good)

- **Structure (B):** captured all of Dr. A's sections with his custom labels preserved — `CHIEF COMPLAINT` `INTERVAL HISTORY` `EXAM` `IMPRESSION & PLAN` `PATIENT INSTRUCTIONS` — mapped to sensible canonical keys (`chief_complaint`/`subjective`/`objective`/`assessment_plan`/`patient_education`). The **combined Impression & Plan was kept as ONE section** (faithful to his format, not split). The non-standard PATIENT INSTRUCTIONS section was kept.
- **Normals separation (C) — excellent, the subtle one passed.** The EXAM default captured exactly his generic canned normal (General/HEENT/Neck/CV/Resp/Abdomen/Extremities/Neuro) and **dropped the patient-specific Vitals line** (run 1) or **blanked the values to a format skeleton** `"Vitals: BP , HR , RR , Temp ..."` (run 2). Diabetic-specific addenda ("no foot ulcers; monofilament intact") were dropped from the generic default. `defaultTextMode` correctly forced to `scaffold_confirm`.
- **Formatting (D):** IMPRESSION & PLAN → `numbered`; narrative sections → `prose`. Correct (EXAM varied prose/bullets — both defensible).
- **Clinical specifics (E):** ICD codes (E11.65/I10/R42) and doses (metformin 1000mg, lisinopril 20mg) did **not** leak as values — the LLM described them as a *convention* in `styleInstructions` ("diagnosis with ICD-10 code in parentheses") and **flagged** them ("Plan items include ICD-10 codes inline — confirm whether to keep this convention").
- **Robustness (F):** no crash, no malformed/typed-error, no empty sections, no dropped meaningful content.

---

## Findings (numbered, with severity)

### P1-1 — Regex PHI detector over-rejects on PHI *field-name keywords* (the headline bug) — CLEAR BUG
**4 of 5 runs REJECTED the entire parse** on a false positive. When the LLM (nondeterministically) creates a demographics/header section and writes field-NAME words in its `styleInstructions` — e.g. *"…followed by patient identifiers (name, **MRN**, **DOB**/age/sex…)"* — `detectStructuredPhi` matches the bare word **"MRN"** (`/\bmrn\b/i`) → `applyPhiGate` treats it as PHI in a *structural* field → **rejects**.
- The word "MRN" is a format descriptor, **not** a value. No MRN value was present. The LLM PHI-scan correctly returned `phiFields:[]` — only the **regex** over-triggers.
- **Impact:** real notes almost always have a demographics header, so this rejects most realistic input → the feature appears broken to doctors. Same note → sometimes a great template (run 1), usually a rejection (runs 2–5).
- **Repro:** `detectStructuredPhi("patient identifiers (name, MRN, DOB...)")` → `['mrn']`.
- **Fix direction (triage):** the structured detectors should match VALUE shapes, not bare keywords — e.g. require an adjacent id (`/\bmrn\b[\s:#-]*[a-z0-9-]*\d/i`), digit-bearing record numbers, etc. Keep the bare-keyword signal as an *input* to the LLM scan / a soft flag, not a hard structural reject. (Also see P1-2 — removing the header section removes most of these.)

### P1-2 — Parser inconsistently TEMPLATES the demographics-header / signature block — BUG + DESIGN CALL
Run 1 **correctly omitted** the letterhead/demographics and flagged it ("Header block contains clinic/provider/patient identifiers — omitted; reconstruct via EHR fields"). Run 2 instead **created** a `"Clinic & Patient Header"` section (order 0) **and** a `"Signature"` section. The header section is (a) spurious — it's EHR-populated identifiers, not note FORMAT a doctor authors — and (b) the exact trigger for the P1-1 rejection.
- **Design call:** should the parse *ever* template a letterhead/demographics/signature block? Recommendation: **no** — explicitly instruct the parser to EXCLUDE letterhead/demographics/signature and list them in `flags`. That both stabilizes output (P2-1) and eliminates the dominant over-rejection trigger (P1-1).

### P2-1 — Run-to-run structure instability
Same note @ `temperature:0` produced 5 sections (run 1) vs 7 (run 2), EXAM as prose vs bullets, and pass vs reject (1 pass / 4 reject). The header/signature inclusion is the main variance; fixing P1-2 stabilizes it. Residual LLM variance is acceptable.

### P3 — Combined-section canonical key — DESIGN NOTE
The combined "IMPRESSION & PLAN" got key `assessment_plan`, which isn't in the documented canonical set (`subjective/objective/ros/pe/assessment/plan/patient_education`). It's a reasonable combined key and faithfully preserved Dr. A's format. **Design call:** bless combined keys (`assessment_plan`) or split. Minor.

### Not a finding — ICD-codes-as-convention
ICD codes appear in `styleInstructions` only as a *format convention* ("ICD-10 code in parentheses"), never as specific codes-as-values, and were flagged. Whether to keep that convention is a product call, not a leak.

---

## Triage view

| Item | Type | Action |
|---|---|---|
| **P1-1** regex over-rejects field-name keywords ("MRN"/"DOB"/"record number") | **Clear bug** | Fix: detectors match value-shapes, not bare keywords; demote keyword to a soft signal/LLM-scan input |
| **P1-2** templates the demographics/signature header | Bug + **design call** | Recommend: prompt the parser to EXCLUDE letterhead/demographics/signature, list in flags |
| **P2-1** structure instability run-to-run | Quality | Largely resolved by P1-2 |
| **P3** combined `assessment_plan` key | **Design call** | Bless combined keys or split |
| ICD-code-as-convention in styleInstructions | **Design call** | Keep / strip — no leak either way |

**Net:** the PHI gate is sound (no leak; fails safe by rejecting). The blocker for 2b usability is **P1-1** (regex keyword over-rejection) + the related **P1-2** (header-section policy) — together they reject most realistic notes. Fix P1-1 + adopt the header-exclusion policy and the parser should produce the clean, correct template it already produced in run 1.

---

## Step 3 — PDF→text preview (what 2b extraction will face)

Generated a realistic PDF (reportlab) and extracted with **pdfplumber** (note: neither `pdfplumber` nor `pdftotext` is installed on the VPS — used a throwaway venv, now removed). Artifacts for 2b's file→text layer:
- **2-column demographics tables collapse to one line:** `"Patient: Maria T. Gonzalez    MRN: RFM-0098214"` extracts as `"Patient: Maria T. Gonzalez MRN: RFM-0098214"` (column gap → single space; the two field:value pairs run together). The parser handled it (treated as a header block), but the PHI values are inline — relevant to stripping.
- **Mid-sentence line wraps insert newlines** (`"...130–162\nmg/dL..."`). 2b should rejoin wrapped lines before parsing (or rely on the LLM, which coped).
- **Unicode preserved by pdfplumber** (en-dash `–`, middot `·`). But other extractors (`.docx` via mammoth/python-docx, or `pdftotext`) may differ — 2b should **normalize unicode** (en-dash, middots, smart quotes) before parsing.
- **Watch repeating page header/footer bleed** in real multi-page EHR PDFs (letterhead/footer per page) — strip repeated headers/footers in extraction.
- `.docx` (the other 2b input) needs its own extractor (tables, styles) — separate handling, not covered here.

## Representative parse output (run 1 — the run that PASSED the gate)
```
name: "Family Medicine Follow-Up Note"   encounterType: "Outpatient follow-up"
sections:
  CHIEF COMPLAINT      [chief_complaint / prose]
  INTERVAL HISTORY     [subjective / prose]
  EXAM                 [objective / prose / +default = generic normal exam, Vitals line dropped]
  IMPRESSION & PLAN    [assessment_plan / numbered]   (combined, not split)
  PATIENT INSTRUCTIONS [patient_education / prose]
styleProfile: { tense: past(hx)/present(exam), tone: concise clinical 3rd-person, abbreviations: standard freely }
flags: [ header identifiers omitted→EHR, exam addenda confirm-before-adding, plan doses/ICD per-patient, signature auto-generated ]
→ gate: CLEAN, no PHI, would return this template.
Runs 2–5: same extraction quality BUT added a demographics "Header" section whose styleInstructions named "MRN" → regex reject.
```
