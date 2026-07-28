# Custom Note Template ("My Note Format") — end-to-end QA + optimization report

**Run:** 2026-07-02, fully autonomous (recon → fixtures → matrix → grading → fix → ship → re-verify)
**Scope:** the doctor-uploads-their-own-format path — the highest-stakes client-facing flow
**Stack:** isolated `meddoc-qa` stack (:9020), prod images (built 2026-06-17), **real Opus/Sonnet generation**, `TRANSCRIBE_MD_EVIDENCE_ANCHORS=true`, `NEXT_PUBLIC_ULTRASOUND_SPECIALTY=true`, migrations fully current (through `20260616064500`). Prod untouched by all testing.
**Deliverable ship:** PR #350 `fix/custom-template-quality` — see §7.

---

## 1. Verdict up front

**Custom-template output is CLIENT-READY on clinical accuracy and structure — with the shipped fix pack.** Before the fixes it was NOT client-ready for two non-clinical reasons: doctors could not read their own notes on the review screen (F-1), and the default activation path saved templates that silently never applied (F-2 — one real prod row was already affected).

| Dimension | Verdict |
|---|---|
| D1 Structure fidelity | **PASS** — 15/17 cells perfect (all custom headings verbatim, ordered, zero default-SOAP leakage); 2 deviations explained + 1 fixed |
| D2 Content placement | **PASS w/ known cost** — custom mean 74.5 vs control 81.9; deficit driven ~entirely by verifier lane demotions (fail-safe, disclosed), not by lost or misplaced facts |
| D3 Clinical accuracy | **GREEN, 17/17 cells** — zero fabrications, zero negation flips, zero med/dose errors, zero notStated-trap hits (adversarial judge + refutation pass) |
| D4 Safety gates | **PASS, all four** — a custom template bypasses nothing (proofs in §6) |
| D5 Export | **PASS** — every heading of every cell present in PDF; clipboard verbatim; email = PDF path |
| D6 Ultrasound × custom template | **PASS** — custom template correctly discarded for imaging; collision cell scored 100/GREEN, byte-equivalent behavior to control |
| Failure handling (bad files) | **PASS** — graceful errors, zero rows persisted, app stays up |

---

## 2. How the flow actually works (map)

1. **Upload/paste** (Settings → My Note Format): `.pdf` (unpdf, ≤50 pages, 20s step timeouts) / `.docx` (mammoth raw text) / `.txt` `.md` (UTF-8); paste ≤50k chars. Nothing persisted during parse; all bytes in memory only.
2. **Parse** (2 LLM calls, Opus 4-8, temp 0, forced tool-use): format extraction → sections `{key, label, order, formatHint, styleInstructions, defaultText(scaffold_confirm forced)}` + styleProfile; then a conservative PHI scan; deterministic fail-safe gate (uncertain→reject, defaultText PHI→scrub, structural PHI→reject). Injection-delimiter text rejects outright.
3. **Review/activate**: editable review screen + live sample preview (real L4 prompt on a fixed synthetic transcript, Redis-cached). Transactional supersede; one-active-per-(doctor, encounterType) partial-unique index; editing an active row forks v+1; revert = delete row (falls back to system default). No half-activated states exist.
4. **Resolution** (worker, per visit): doctor's active exact-`encounterType` match → doctor's active catch-all (NULL) → system default. `encounterType` must equal the visit's specialty slug — the crux of finding F-2.
5. **Generation (L4)**: custom sections emitted as `## {label}` + the IMMUTABLE safety preamble/rules (always from the system default — a custom template can never weaken safety; verified in-prompt) + specialty guidance (still applied — orthogonal) + anchors addendum. **Ultrasound visits bypass the custom template entirely inside L4** (in-code `ULTRASOUND_REPORT_TEMPLATE` wins; deliberate and correct).
6. **Verifier (L4b)**: section-agnostic; anchors per line; deterministic hard overrides (digits/negation/gloss/process-verb/form-route) + k=3 entailment ensemble. Unsupported lines are demoted to the SuggestionsLane (never silently kept).
7. **L5 critique / L6 polish**: template-aware for structure validation; SOAP-framed prompts otherwise.
8. **Persistence**: markdown blob + `noteTemplateId/Version` provenance. **Gates** (Rx override / E/M confirm / lane / audit) read structured data, not section names. **Exports** (PDF/DOCX/email/clipboard) are line-walkers — custom headings render verbatim.

## 3. Fixture library (Phase 1 — all uploaded through the real UI, real parse)

| # | Fixture | Tests | Parse result |
|---|---|---|---|
| F1 | Classic private-practice variant (.docx) — "Reason for Visit / History / Examination / Impression & Plan / Follow-Up", bold labels, clinic header | renamed+reordered sections, chrome dropping | ✅ 5/5 labels verbatim; letterhead + e-signature dropped into dismissible suggestions |
| F2 | Pain management (.pdf) — med list, "Opioid Agreement & Risk Review", functional status | domain sections, pdf text layer | ✅ all 8 sections |
| F3 | Cardiology consult LETTER (.docx) — "Dear Dr.", narrative, echo block, signature | letter-shape → sectionization | ✅ parsed to 6 sections incl. "Referral Greeting"/"Closing" (letter becomes structured; salutation preserved as a section, not chrome) |
| F4 | Tables-heavy (.docx, real Word tables) — vitals + meds tables | table extraction | ✅ 5 sections; table structure flattens (mammoth) but sections correct |
| F5 | Numbered headings (.pdf) — 1. / 1.1 / 1.2 | hierarchy | ⚠️ parsed flat and **numbering stripped from labels** → downstream validation noise (fixed in PR #350; post-fix labels keep "1. / 1.1" verbatim) |
| F6 | Minimal 3-section (paste) — Story/Findings/Plan | terse paste path | ✅ |
| F7 | Adversarial — Plan-first order, duplicate "Notes", emoji/symbol headings, embedded prompt-injection heading | parser robustness | ✅ order kept, duplicates auto-disambiguated ("Notes (patient education)"), `$$ Billing shorthand $$`/`⚡` kept, **injection heading correctly NOT turned into a section** |
| F8 | Failure set — image-only PDF, corrupt .docx, empty file, 2 MB file | graceful failure | ✅ specific friendly errors for the first three, zero rows persisted, app responsive. Oversized: generic "Something went wrong" (F-4, fixed) |

## 4. Scenario×template matrix (Phase 2/3) — per-cell scores

Scenarios (dense synthetic, self-authored with ground-truth annotations incl. `notStated` traps): **a** multi-problem HTN/DM f/u (28 min counseling, drug-interaction bait, penicillin allergy), **b** pain-mgmt opioid refill (UDT/PDMP/MEDD), **c** cardiology f/u (echo numbers, pacemaker interrogation, titration), **d** post-op check, **e** terse allergy visit, **u** ultrasound venous reflux dictation. Driven through the real text-to-SOAP pipeline (L3→L7c, real models, anchors ON).

| Cell | D2 placement | lane-captured | misplaced | omitted | D3 accuracy | verifier FP/GC |
|---|---|---|---|---|---|---|
| f1-a | **100** | 0 | 0 | 0 | GREEN | 1/1 |
| f1-e | 75 | 1 | 0 | 0 | GREEN | 1/0 |
| f2-b | 62.7 | 1 | 2¹ | 0 | GREEN | 8/0 |
| f3-c | 73 | 3² | 0 | 0 | GREEN | 4/0 |
| f3-a (fallback ctl) | **100** | 0 | 0 | 0 | GREEN | 6/0 |
| f4-a (tables) | 80 | 3 | 0 | 0 | GREEN | **7/0 (+10 unclear; 17 lane rows — worst cell)** |
| f5-a (numbered) | 45³ | 3 | 3³ | 0 | GREEN | 4/0 |
| f6-a | 93 | 1 | 0 | 0 | GREEN | 1/0 |
| f6-d | 66.7 | 2 | 0 | 0 | GREEN | 1/1 |
| f7-e (adversarial) | 75 | 1 | 0 | 0 | GREEN | 2/0 |
| ctrl-a | 93 | 1 | 0 | 0 | GREEN | 5/0 |
| ctrl-b | 58.6 | 3 | 1 | 0 | GREEN | 7/1 |
| ctrl-c | **100** | 0 | 0 | 0 | GREEN | 6/0 |
| ctrl-d | 83 | 1 | 0 | 0 | GREEN | 4/0 |
| ctrl-e | 75 | 1 | 0 | 0 | GREEN | 3/0 |
| **f1-u (ultrasound × custom)** | **100** | 4 | 0 | 0 | GREEN | 3/1 |
| ctrl-u | 66.7⁴ | 2 | 0 | 2⁴ | GREEN | 3/1 |

¹ f2-b: model added an extra "Objective / Exam" section because the pain template defines no exam section — content-preserving by instinct; the 2 "misplacements" are exam facts placed there. Documented behavior, not fixed (dropping the facts would be worse).
² f3-c: the echo-numbers block was demoted whole to the lane (multi-fact aggregate line).
³ f5-a pre-fix: numbering mismatch pushed content into wrong subsections + spurious structure-validation fail. **Fixed** (see §7 BEFORE/AFTER).
⁴ ctrl-u judge scored partially-placed facts as omitted per the against-passing rule; both "omissions" are lane-captured, and the identical content pattern in f1-u was scored 100 by its judge — judge-severity variance, not a custom-template delta.

**Custom D2 mean 74.5 vs control 81.9.** The deficit is NOT misplacement or loss — facts are never silently lost (0 true omissions from the system across 17 cells; everything lands in the body or the disclosed lane). The driver is **anchored-verifier lane demotions**, which hit controls too (ctrl-b 58.6) and concentrate on: table rows (every row = one claim needing its own anchor), aggregate/summary lines (echo blocks, "Reason for Visit" recaps — anchors rarely cover every clause, e.g. a missing laterality word demotes the whole line), and boilerplate-ish sections (Technique/Exam in ultrasound). Judged demotion quality matrix-wide: **66 false positives, 5 good catches, 14 unclear** — >90% FP rate on demotions, consistent with the known AMBER accept-and-disclose posture for the anchored hybrid; template shapes amplify volume but create no new unsafe class.

**E/M with custom formats (R3):** billing E/M code identical custom-vs-control on every scenario (99214/99214/99215/99212/99212). Deterministic sub-counters (HPI/ROS/PFSH/exam) drift mildly on most custom shapes and zero out on numbered-heading notes, but the persisted code (L7b LLM) and the displayed/gate-shared projection were unaffected in all cells. Rail/gate parity holds by construction.

## 5. Findings

| # | Sev | Finding | Status |
|---|---|---|---|
| F-1 | **P0** | Review screen parses ONLY S/O/A/P headings → every custom-format note **and every prod ultrasound imaging report** rendered as 4 empty blocks; content invisible in read mode (data intact; exports fine) | **FIXED** (PR #350, display-only parser; classic SOAP byte-identical) |
| F-2 | **P1** | Parse emits free-text `encounterType`; review editor displayed "All my visits" while saving the free text → template **silently never applies** (resolver needs canonical slug/NULL). 6/7 QA fixtures dead on arrival; **1 real prod row affected** (`'Follow-up office visit'`) | **FIXED** (UI coercion + server catalog validation) + prod data repair at deploy |
| F-3 | P2 | Verifier lane demotions concentrate on tables/aggregate sections (f4-a: 17 rows, 3 sections gutted); >90% of demotions judged FPs. Fail-safe (disclosed lane, adopt flow works) but a real workflow cost for exactly the formats clients bring | **DOCUMENTED** — verifier surfaces are byte-frozen (PR #346 scope); any change requires the pre-registered zero-regression eval. Recommendation §8 |
| F-4 | P3 | 1–5 MB upload → generic "Something went wrong" (Next 1 MB action limit fires before the friendly 5 MB message) | **FIXED** (honest client-side 1 MB check) |
| F-5 | P2 | f5 numbered templates: parse stripped heading numbering → guaranteed spurious structure-validation `needsReview` on every visit | **FIXED** (parse prompt preserves numbering verbatim) |
| F-6 | P2 | **Ultrasound-generic (pre-existing, likely visible on prod):** every ultrasound visit's reviewReason includes "Auto-coding incomplete — cpt-coding: no E&M code emitted (status:ok). Click Retry" — spurious for imaging where E/M suppression is by design (confidenceScores itself records `skipped`); invites doctors to chase a non-defect | **REPORTED ONLY** — out of scope per the "ultrasound path byte-identical" constraint of this run |
| F-7 | P2 | A visit can be signed + exported while verifier placeholders still occupy sections (f1-a was signed with 2 placeholder sections; the PDF carries them). needsReview is advisory by design — but for custom templates whose sections get gutted this is easy to hit | **REPORTED** — product decision (block? warn harder?) for Kasra |
| F-8 | P3 | Pipeline-wide observations (controls too, NOT template-caused): L6 auto-polish was fabrication-gate-rejected on ~every cell (critique fixes never apply); the designed amlodipine+simvastatin-40mg cap interaction produced NO Rx warning in either arm; ICD coding returned empty on 2 control cells; referral export invents "(age inferred)" demographics outside soapFinal | **REPORTED** for the pipeline backlog |
| F-9 | P3 | Imaging `### Right/### Left` sub-blocks render as their own sections in the new display parser (Findings parent shows empty) — content fully readable, nesting cosmetic | **REPORTED** (follow-up polish) |

## 6. Safety-gate proofs (D4) — with an ACTIVE custom template

- **Rx critical-warning gate:** visit resolved the custom template AND carried a critical warning → `POST /sign` → **422 OVERRIDE_REQUIRED**; UI Sign button disabled with "Resolve the critical interaction to sign →"; typed-reason override through the real modal → `rx_warning_overrides` row → sign succeeds. Audit trio `RX_SIGN_BLOCKED_NO_OVERRIDE → RX_OVERRIDE_RECORDED → VISIT_SIGNED`. (Mechanics pass under the MOCK warning fixture; real-generation cells produced no critical warning to trip organically.)
- **E/M visible-confirm gate:** armed `emPendingChange` on a READY custom-template visit → sign w/o ack **400 EM_CHANGE_UNACKNOWLEDGED**; wrong `{from,to}` echo **400**; exact echo **200 → SIGNED**; 2 block-audit rows.
- **SuggestionsLane:** custom section names round-trip on lane chips; Adopt mutates `soapFinal` (17→15 claims) + `SUGGESTION_ADOPTED` audits; E/M recompute ran on adopt.
- **Audit:** `VIEWED_VISIT` on every review load; full trail incl. `L6_FABRICATION_REJECTED`, export events.
- **Immutable safety layer:** custom rows persist style only; safety preamble/rules sourced from the system default at prompt build (golden test intact).

## 7. What shipped (Phase 4) — PR #350 `fix/custom-template-quality`

Four fixes, 9 app files, **zero** worker/verifier/gate files; fabrication-gate frozen surfaces byte-unchanged (re-eval not triggered, by diff inspection); L4 golden prompt + 53 verifier canaries + 1792 unit tests green.

1. **`src/lib/parse-note-sections.ts` (new, display-only)** + SoapBody/SoapSection/soap-editor: any-heading rendering; classic-SOAP delegates to the legacy parser (unit-tested byte parity); `parse-soap-sections.ts` untouched so E/M counters keep exact inputs.
2. **encounterType**: review editor coerces non-catalog parse values to catch-all on init; `ReviewedTemplateSchema` refines to the static specialty catalog. Prod data repair: 1 row → NULL.
3. **Parse prompt**: heading numbering preserved verbatim in labels.
4. **Upload limit**: honest client-side 1 MB message.

**BEFORE/AFTER (QA stack, fix image, real models):**

| Check | BEFORE | AFTER |
|---|---|---|
| f1-a review screen | 4 × "section is empty", content invisible | all 5 custom sections rendered with content ("5 sections") |
| f1-u imaging review | 4 empty SOAP blocks | Exam→Impression + Right/Left rendered, measurements visible |
| Default-path activation | `encounterType='Follow-up progress note'` → template never applies (visit used system default) | `encounterType=NULL` → visit resolves the doctor's template ✅ |
| f5 numbered template | labels stripped of numbers → structure-validation fail + needsReview every visit | labels "1. Subjective Data / 1.1 …" verbatim → zero structure noise |
| 2 MB upload | "Something went wrong" | "larger than 1 MB — paste instead" |
| D1 structure (16 unaffected cells) | pass | unchanged (display fix only; generation untouched) |

**Ship trail:**
- code-quality-auditor: **SHIP-WITH-NITS** (0 BLOCK · 3 WARN · 4 NIT; all hard scope constraints PASS — verifier/worker/gates/parse-soap-sections verified untouched by the auditor independently). W1 (flag-off coercion could widen an ultrasound-scoped template), W2 (missing zod canaries), W3-doc, N2, N4 remediated in commit 37076c5; N1 (stale comment in status route) + N3 (2-digit eyebrow chip width at >9 sections) left as follow-ups.
- CI checks (6): **ALL GREEN** — one unrelated repo-wide breakage cleared en route: new upstream undici HIGH advisories (GHSA-vmh5-mc38-953g + GHSA-p88m-4jfj-68fv) broke the npm-audit gate on every PR; fixed by transitive bump 7.25.0→7.28.0 (commit 6c7c631, the established #342/#345 workflow).
- squash-merge: **main `7b83649`** (PR #350).
- prod deploy: **LIVE** — app image rebuilt from main (`docker compose build transcribe-md`, .env flags), `up -d --no-deps transcribe-md`; **worker untouched** (zero worker files in the diff). Rollback tag **`meddoc-pro-transcribe-md:pre-customfix-20260702`** (= 978f79f6, the 2026-06-17 image). Rollback = `docker tag … :latest && docker compose up -d --no-deps transcribe-md` + revert the data repair if desired.
- **Prod data repair:** `note_templates cmpz63jsw…` (doctor **hshabatian@yahoo.com** — a real external user) had `encounterType='Follow-up office visit'` since 2026-06-04 → their activated format NEVER applied for a month. Repaired to NULL (the "All my visits" the UI displayed when they saved). **Kasra: consider telling this doctor their custom format now actually takes effect.**
- prod smoke: **PASS** (1.2m, synthetic account, real prod pipeline) — paste→parse→activate saved `encounterType=NULL` (F-2 live); text visit reached READY and **resolved the custom template**; review screen rendered Story/Findings/Plan with content (F-1 live); PDF exported. All smoke rows deleted transactionally; baseline verified: 1 pre-existing visit (kasra.rayat@gmail.com), 3 template rows (2 system + the repaired row), 0 smoke residue; app health green; co-tenants 200.

## 8. Remaining risks / limitations + recommendation

**Ready for doctor testing?** **YES** for accuracy + safety + (post-fix) usability, with two disclosures for clients:
1. **Format support:** section names/order/numbering/prose-vs-bullets are reproduced faithfully. Word/PDF **visual** formatting (tables as grids, bold, fonts) is not — tables come back as labeled lines; exports are QuillMD-styled PDF/DOCX, not the clinic's letterhead. Set expectations accordingly.
2. **Review workload by format shape:** templates built around tables or aggregate summary blocks will see more "set aside for review" content (the anchored verifier's strictness working as disclosed). The doctor adopts from the lane — nothing is lost, but tables-heavy formats feel it most (worst observed: 17 lane rows on a dense annual). If client feedback confirms the pain, the next lever is the pre-registered verifier-FP process (PR #346 pattern: cached-draft A/B, zero-catch-regression eval, canary pinning) targeting multi-span aggregate claims + table rows — NOT attempted in this run because those surfaces are byte-frozen and the eval budget/risk was not justified before client feedback.
3. Open product decisions: F-7 (sign-with-placeholders), F-6 ultrasound Retry-nag, F-8 pipeline items, F-9 nesting polish.

## 9. Run confirmations

- All 4 gates intact (re-proven post-fix); fabrication-gate eval **not required** (frozen surfaces byte-identical — verified by diff); no verifier/judge/threshold/override change shipped.
- Default SOAP render byte-identical (parity unit test + control screenshots); generation paths untouched.
- Co-tenants: healthy through the whole run and post-deploy (pro.quillmd.com + quillmd.com 200; only stray in the worktree remains the expected LeatherERP Caddyfile edit, untouched).
- QA stack: torn down with volumes (`down -v`) at end of run; temp specs + overlays removed from repo paths.
- Prod: deployed + smoked + baseline restored (see ship trail). Prod worker never restarted (unchanged image, no leaked handles observed; BullMQ queue idle at end of run).
- Anthropic spend: ~17 real-pipeline visits + 8 real parses + previews + 4 verification runs ≈ $12–18 (ai_calls costCents captured per cell in artifacts).

*Artifacts (scratchpad, session-scoped): phase1-artifacts (8 fixture runs + screenshots), phase2-artifacts (17 cells × visit/aicalls/audit/screenshots/PDF/clipboard + gate logs), phase3-bundles (grading bundles + 17 judge JSONs), phase4-artifacts (AFTER screenshots).*
