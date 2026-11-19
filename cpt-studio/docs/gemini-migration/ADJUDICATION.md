# Adjudication of the design refutation (integration owner, session 30a58364, 2026-11-09 ~10:10Z)

`design/FINAL.md` (the judge's design) is adopted, AS AMENDED BY THIS FILE. Where they differ, THIS FILE GOVERNS.
- The refuters' 30 findings are in `refutes.json`.
- Verified first-hand before deciding: the five blocking findings.
  - P-1: `ops/install.py:4540-4541`, `phase_switch_back` refuses on any undo hazard, and FINAL §13 adds a refusing reason.
  - R-1: `studio/apps.py:1` and `studio/models.py:7-12` import only Django, so `AppConfig.ready` sees no legacy module.
  - C-1: `catalogue.code_profile('43242').covers == ('eus_exam', 'fna')`.
  - C-2 and C-3: read in FINAL §7.7 and §7.9.
- The majors and minors were read against the cited design sections. Their fixes make the design more conservative or more
  correct, and each is re-proven by the slice tests and the finished-diff refutation.

## EB: the owner's principle on evidence binding (supersedes contract 5.3's passage guards and FINAL C10)

The owner's directive makes Gemini the primary interpreter, and forbids the legacy reader to "independently reinterpret
Gemini's accepted events or veto them through keyword matching". Evidence binding checks that Gemini's own evidence states
Gemini's own value. It is not a second reading of the document. Therefore:

- **EB1. A check reads only the cited WORDS of the attribute it verifies,** and literal values inside those words: a date, a
  size, a person's name, a landmark, a device, or a marker from the C1 lexicons where the value can decide an exclusion. A check
  never scans the rest of a passage, a neighbouring sentence, a heading or the document for words that might contradict
  Gemini's value.
  - REMOVED: the foreign-date guard, the foreign-name guard (and so C10), and any "marker in passage" scan.
- **EB2. The frame defaults are accepted as Gemini's reading.** A current-encounter time or a documenting-team performer, which
  Gemini states without words, is accepted (`basis: default`).
  - Where Gemini DID give time words, a date literal in those words that differs from the service date leaves the time
    unverified.
  - Where Gemini gave performer words, a name in those words that is not the documenting endoscopist or a listed team member
    leaves the performer unverified.
  - Either way, the code gets a focused question, never an exclusion.
- **EB3. C1's markers stay.** They read only the words of a value that could EXCLUDE (planned, attempted_not_completed, earlier or
  future without a date, other facility without a name). A missing marker turns a would-be exclusion into a question. They
  never touch the READY path.
- **EB4. The residual risk is stated and measured, not patched with word lists.**
  - The case: Gemini labels a history-section act as current with no time words (refuter C-12, the E5 class). The new path
    then holds no guard against it. That is Gemini's interpretation error, never the old reader's veto.
  - It is measured on the FRESH corpora and reported. Every false READY found is investigated and repaired in the new
    architecture: in the prompt or schema (asking for the words), or in a structural rule. A passage word list is never the
    repair.
  - The prompt asks for time words whenever the document gives ANY time indication for the act, including "prior",
    "previous", "at that time", a section such as "History:", and a date.
  - In the 2026-11-09 trial Gemini made no time-attribution error in 7 of 7 cases.

## Decisions on the 30 findings

The preservation, rollback, install, tenancy and cost lens:

| # | sev | decision |
|---|---|---|
| P-1 | blocking | **ADOPT fix (a).** `interpretation` is NOT a refusing `UNDO_HAZARDS` or `SHOWN_HAZARDS` reason. It is written as a declared, non-refusing note in the switch-back and rollback receipts ("N assessments were made from event inventories; the earlier image reads them fail-closed"). FINAL §12.3 assertion 5 becomes: the note names exactly the new-path encounters, and the switch-back PROCEEDS. The D15 runtime test performs the established `switch-back` itself on the test instance. |
| P-2 | major | **ADOPT.** Door 2 (reuse) reuses only a run with no EventInventory at the current versions, or one whose inventory is `read`. It skips a run whose inventory at the current versions is `refused`, and any run released for retry. A recorded retry may release a SUCCEEDED-but-refused run (except MAX_TOKENS, C5). |
| P-3 | major | **ADOPT.** `holds.classify` reads the HTTP code, the error body's `error.status` and the `google.rpc.ErrorInfo.reason`. An installation hold is set for API_KEY_INVALID, API_KEY_EXPIRED, API_KEY_SERVICE_BLOCKED, SERVICE_DISABLED, BILLING_DISABLED, FAILED_PRECONDITION, PERMISSION_DENIED and UNAUTHENTICATED, and for 401 and 403. A 400 INVALID_ARGUMENT without those reasons is a request failure, with no hold. Tested with synthetic bodies of each shape. |
| P-4 | minor | **ADOPT.** A 429 is classified by the QuotaFailure violation's `quotaId` or `quotaMetric`. PerMinute: a failure of that attempt (no hold), with RetryInfo recorded. PerDay, limit 0, or billing: an operator-released hold. Tested with the trial's own recorded 429 bodies (`gemini-trial/archive/attempt1-20261109T0549Z/*.json`, which carry PerDay and PerMinute violations together and are therefore a hold). |
| P-5 | minor | **ADOPT.** A modelVersion that is not exactly `gemini-4-argon` is refused and never read, AND sets an installation hold (reason `model`) released by the recorded operator command, so a substituted alias is not paid for again and again. |
| P-6 | minor | **ADOPT.** mark_stale settles an interpretation run whose turn-1 exchange is `succeeded` with HTTP 200 and a response sha256 that checks, from that exchange, as SUCCEEDED (the settled path). It does the same before an after-reconcile send. Nothing is sent. |
| P-7 | minor | **ADOPT.** The verify self-test counts legacy-engine assessments created after the app receipt's new-worker start (S4), never after the install start. |
| P-8 | minor | **ADOPT**, together with R-2. |

The hidden reread, veto and guard lens:

| # | sev | decision |
|---|---|---|
| R-1 | blocking | **ADOPT.** `sentinel.install()` explicitly imports a committed, pinned list of deny modules before it walks code objects, and asserts the list equals `glob(studio/gi/*.py)` minus `profiles` and `catalogue`, plus the named validation files and `candidates.py`. It runs in EVERY process: web workers, worker and one-shots. A process whose sentinel failed to install refuses new-path writes. |
| R-2 | major | **ADOPT.** The code-shape helpers that unchanged consumers call are RE-HOMED into a neutral module, which the legacy modules import back with identity preserved (the same move as the gi.context predicates). They are `reconcile.act_label` / `kind_label` (reconcile.py:61-82), `review_view.service_answers` (204-209), and `engine._listable` / `participant_listable` / `participant_unlisted_count` / `participant_unlisted_codes` (3868-3903). FINAL §8.3's table lists every consumer that reaches them, and the §10.4 matrix fixtures include participant records that carry codes. |
| R-3 | major | **ADOPT** the three CALL forms: a `re.Pattern` method descriptor with a denied pattern as arg0; a bound builtin whose `__self__` is a denied pattern; `re.search` / `match` / `fullmatch` / `finditer` / `findall` / `sub` / `subn` / `split` with a denied pattern as arg0. A planted proof covers each form. |
| R-4 | minor | **ADOPT.** `incomplete_check` is removed from the 7.1 allowlist. The service.incomplete check is worded in `wording.py` from the event's verified failure-marker words. `_held_blocker` and `answered_by_engine` move into the 8.1 seam table. |
| R-5 | minor | **ADOPT.** checks.py is an ALLOWLIST: the new package and the edited consumers may reference only the 7.1 names, and the sentinel denies every other checks.py function. |
| R-6 | minor | **ADOPT.** The matrix also runs on a database that holds ONLY new-path encounters, and asserts zero denied executions under every label (new_path, other, unscoped). The list, session and operator-list loops and the installer scripts label per encounter row. |

The correctness lens:

| # | sev | decision |
|---|---|---|
| C-1 | blocking | **ADOPT.** Examination kinds (`*_exam`, `examination`) are the SESSION, never an act. A code whose covers hold an examination kind plus other kinds needs a supporting performed event of EACH non-examination kind. One test per EUS code on an exam-only document and on a document with the act. |
| C-2 | blocking | **ADOPT.** The same-passage arm is ported: a biopsy and a removal on the same lesion entry that cite a common passage are bundled, whatever the multiplicity. A group lesion whose two acts sit in separate passages gets a `bundling_identity` question and is never READY. |
| C-3 | blocking | **ADOPT.** `procedure_day` is by DATE OF SERVICE. It counts events whose time is current_encounter or whose own words place them on the effective service date. Undatable events give UNRESOLVED(time) for the E/M code, a question and never READY. |
| C-4 | major | **ADOPT.** Base-within inclusion is derived structurally: a current, performed EGD examination in an encounter with a current, performed upper EUS examination is the EUS's endoscopic portion. `part_of` is extra evidence only. |
| C-5 | major | **ADOPT.** An injection event (not a tattoo, and not with a verified hemostasis purpose), in a session with a current, performed EMR or ESD at compatible landmarks, is bundled into it. Where its lesion or site is unresolved, the pair joins `bundling_identity`: asked, never READY. |
| C-6 | major | **ADOPT, stricter than proposed.** A code with no catalogue profile (route c) is NEVER READY on the new path. It is held ("outside CPT Studio's coding profiles; review required"), as legacy lists such codes as unsupported (engine.py:3740-3763). Route (c) is removed. |
| C-7 | major | **ADOPT, through the schema, not a lexicon.** The scope enum gains `exceptive` (statements such as "no further / no other / no additional intervention"). Gemini assigns it, with scope words verified as words. An exceptive scope never pairs with positive acts of its kind and never excludes. A broad (all_of_kind) statement excludes only when the code's kept spans overlap the broad statement itself; otherwise it gives a `statement_scope` question. |
| C-8 | major | **ADOPT.** The pairing table gains a procedure/session row. Verified different families are INDEPENDENT. An unverified family in a multi-family encounter is UNRESOLVED(procedure). `all_of_kind` means every act of that kind in the statement's own examination or session. |
| C-9 | major | **ADOPT.** For a non-base code, attempted_not_completed is a HOLD (performed_status plus the 52/53 consideration), never an exclusion. |
| C-10 | major | **ADOPT.** Exclusion by overlap requires the code's kept span to lie within the union of the deciding event's own attribute word spans (kind, status, time, target). A span reaching words no D word covers gives a `statement_scope` question. The shared-sentence omission fixture is added to the P4 test. |
| C-11 | major | **ADOPT.** Size establishes distinctness only beyond a tolerance (difference > 2 mm AND > 20%), and only when no shared distance or site literal says "same". A model `contradicts[]` claim between two events is dismissed only by disjoint landmarks or another hard literal; otherwise it is UNRESOLVED(target), a question. |
| C-12 | major | **REJECTED as proposed** (a time-marker lexicon applied to passages is the keyword reader the owner ended). Handled by EB4 instead: the prompt asks for time words on any time indication, the residual is measured, and any false READY is repaired structurally. |
| C-13 | major | **RESOLVED by EB1/EB2**: no foreign-date passage guard, so a date in purpose words never fails the time default. Pinned by a test (the tattoo for a colectomy scheduled 12/01). |
| C-14 | minor | **RESOLVED by EB1/EB2**: no foreign-name guard. Pinned by a test (the referring Dr. Patel). |
| C-15 | minor | **ADOPT.** LANDMARKS gain right colon, left colon, proximal colon and distal colon with their containment. |
| C-16 | minor | **ADOPT.** When an event of the same kind and target denies a specific technique and the performed event's device is absent, the result is UNRESOLVED(technique), with a question on the codes that event supports. |

## What this changes in the slices
- S01-S03 (the contract): apply EB1-EB4, C-7's `exceptive` scope (prompt and schema), C-15's landmarks, C-11, C-16 and C-8.
  Remove the passage guards and C10.
- S06 (the adapter): P-3, P-4, P-5 (classification and holds).
- S07 (holds, sentinel): R-1, R-3 (test side in S12), P-5 hold reason `model`.
- S08 (the engine): C-1 to C-6, C-9, C-10; the route-(c) removal; R-4 (wording of incomplete).
- S09-S10 (the pipeline): P-2, P-6.
- S11 (read time): R-2 / P-8 re-homing and the consumer table; R-6 labels.
- S12 (the guard proofs): R-3's three forms; R-5's allowlist; R-6's new-path-only database.
- S14 (the installer): P-1 (non-refusing note), P-7.
- S17 (pre-install validation): P-1's switch-back performed on the test instance.
