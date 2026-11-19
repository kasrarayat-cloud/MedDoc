# Design v2: the judge's decision on each refutation finding

Judge's record, 2026-11-12. The refutation of `design-v2/FINAL-V2.md` ran four lenses (self-certification, holds, contract,
migration and operations) and returned 28 findings: 1 critical, 8 high, 15 medium and 4 low. Each is decided below,
critical and high first: accepted, with the design change and where it is; or accepted in part, with the rejected part's
reason and a concrete input that shows it does not hold. No finding was rejected whole, because each one that I checked
held.

- **The text decided on:** FINAL-V2 before the revision, kept unchanged as `design-v2/FINAL-V2-pre-refutation.md`
  (sha256 `cc5c288872a1c1a65af241997f12414a3e538b7e49eb6c2d043d3a6c5a796a00`, the hash the holds lens cites).
- **The revised design:** `design-v2/FINAL-V2.md` (sha256 `9d650797c41091d3ab9ce2f783c1838e5aa394bb926c5d5b2733c2186d733b21`).
  Every change carries a tag `[R:<finding>]`. Section 0 has a summary paragraph, "What the refutation changed".
- **How it was applied:** 157 scripted replacements (`design-v2/revise/p1` to `p10`), applied by
  `design-v2/revise/apply_patches.py`, which asserts that each one applies exactly once and writes nothing unless all of
  them do ("expected 157 / applied 157"). The ten sections and the three appendices are kept. The last replacement also
  repairs a table row the pre-refutation text had malformed (4.3 LIMITED, one column short).
- **Finding ids:** SC-A to SC-D (self-certification), HO-1 to HO-9 (holds), CO-1 to CO-8 (contract), MO-1 to MO-7
  (migration and operations), in the order of the lenses' own lists.
- **What was not opened:** `acceptance-a1/`, any sealed set, docs-c6, docs-c7, walk-c6, walk-c7, g1-stage and
  `/home/claude/cpt-studio-completion-20261106/acceptance/`.
- **What was not done:** nothing was edited in the worktree, nothing was sent to a provider, and docker was not run. Every
  measurement below reads recorded files only.

---

## 1. What I verified myself before deciding

| claim a finding relies on | how I checked it | result |
|---|---|---|
| v1 counts a doubt as a positive act (HO-1) | `events.py` 1213 and `combination.py` 370-375 at the worktree head | Both include `uncertain` beside `verify.POSITIVE` |
| v1's `_focused` asks h1 across every candidate first (HO-8) | `events.py` 1227-1245 | Confirmed: the rule loop is outside the candidate loop |
| Gemini commits values and raises doubts beside them (CO-1) | a read-only count over the 358 recorded v1 answers in `fresh-frozen/` and `fresh2-frozen/` | 2,950 events; status `uncertain` 0; time `unknown` 6; 111 open questions in 81 answers |
| BF2's recorded answers (CO-1) | both recordings of `W1-u30a-rel-f4-unread-before-017` | FRESH-1 r1: time `earlier_encounter`, words "Once", plus an open question on time. FRESH-2 r1: time `unknown`, plus open questions on time and performer |
| The placing sentences exist as quoted (CO-2) | `f2-after-002`, `twins-015` and the last lines of `W1S-222`, read | Confirmed, verbatim |
| Note #8's wrapped denials and its 4-unit sentence (CO-3, CO-5) | the pre-refutation unit rule re-run on `fresh/inputs/A/note8.txt` | "historical only; no" / "esophagogastroduodenoscopy ... was performed ..." (S44/S45), "No colonic" / "stent was placed." (S127/S128), "No" / "hemostatic cautery ... was performed in the rectum." (S221/S222); the extent sentence is S85-S88; "Endoscopist: E." / "Morgan, MD ..." (S10/S11) |
| Words that cross a unit (CO-4) | `design-v2/judge-data/measure_v2r.py` over the 358 answers, against the old rule and the revised one | Old rule: 1,760 of 20,057 words values cross a unit, as the lens says. Revised rule: 21 cross, and 13 of 2,950 events have kind or status words that cross a unit (545 under the old rule). Every v1 passage spans at most 6 units. Note #8 drops from 317 units to 181 |
| D36's rule (CO-6) | DECISIONS D36 | "A reach entry is verified only when one of its passages belongs to its examination event or to no act of the session." See section 6 below |
| The two same-kind denials in one unit (CO-7) | `fresh/inputs/B/fb08.txt` line 9 | Confirmed |
| The v3 pin (HO-2) | `tests/fixtures/interpretation/MANIFEST.json` | `independent:time:another_time` present |
| The install doc's re-runs (MO-1) | `ops/INSTALL.md` 601-650 | "On a served site `app` is the blue/green switch"; same-revision `app` re-runs (D83) documented |
| The vendor pattern misses `gemini_unknown` (MO-2) | `customer_api.FORBIDDEN`'s provider alternation, run in Python | `gemini_unknown`: no match. `cause: gemini_contradicted`: no match. `gemini unknown` and `gemini-unknown`: match. The revised pattern was run too: it matches `gemini_unknown`, `reading_gemini_x`, `Gemini` and `gemini-4-argon`, and not `corticosteroid`, `cortical`, `Claudette`, `astral` or `googled` |
| A reviewer is a customer member (MO-2) | `studio/models.py` 89 | `OWNER, REVIEWER, VIEWER` are workspace membership roles |
| Pass 2's timeout against D49 (MO-3) | `adapter.py` 69-74 (D49's comment); the 179 FRESH-2 recordings' usage | 44 of 179 calls thought; 3 thought more than 5,000 tokens; p99 6,544; maximum 16,776 (`twins-015` r3, 848 characters, 218.5 s for 18,016 output tokens: 82.4 tokens per second) |
| A context save on a legacy revision queues a reading (MO-4) | `jobs.py` 4443-4530 (`_change_context`, `_save_before_reading`) | Confirmed: with no inventory and `_legacy_reading_allowed()` false, it enqueues `interpret:...:after-save:<uuid>` |
| The cap's 429 and the shared credential (MO-6) | `PLAN.md` (2026-11-10 13:56Z); `testinst/gemini_cred.sh` | "429 RESOURCE_EXHAUSTED ... monthly spending cap"; a TEST-ONLY copy of the owner's credential |
| D59's rollback limit (MO-7) | DECISIONS D59, finding 13 | "a reinstatement made THERE can leave the diagnostic [base code approvable]"; INTERPRETATION_MADE names such encounters `reinstatable` |
| The base did not move | `git diff --stat 95d8aa347 HEAD` limited to `studio/`, `ops/`, `cptstudio/`, `tests/` and `scripts/` | Empty: the commits after the base add only the a1 freeze and scoring documents, which were not opened |

The revised cost and pass-2 bounds come from `design-v2/judge-data/cost_model_v2r.py` (output `cost_model_v2r.out.json`),
the pre-refutation model with the two parameters the revision changes.

---

## 2. Summary

| id | severity | finding (short) | decision | where the design changed |
|---|---|---|---|---|
| HO-1 | critical | a stated doubt is never "possibly performed" | accepted | 1.3, 2.1 P7, 3.3, 4.2, 4.4, 4.6, 4.7, 4.8, 9.4, 9.5 |
| SC-A | high | the unlisted drop by geometry cancels pass 2's report | accepted | 2.4 A6, 3.2.6, 1.7, 9.1, R8 |
| SC-B | high | pass 1's lists read as complete | accepted in part | 3.2.2, 3.2.3, 4.2, 4.3 STATIONS, 4.5, 4.11, 9.4 |
| HO-2 | high | statement attributes claimed with act sentences | accepted | 3.2.1, 3.2.2, 4.5, 4.6, 4.10 |
| HO-3 | high | a caught misfiled denial stops being a statement | accepted | 4.2, 4.5, 1.9, 3.8, 9.5 |
| HO-4 | high | health cannot see a yes-man or a no-man | accepted in part | 3.2.3, 3.2.6, 9.2 |
| CO-1 | high | the doubt channel Gemini uses was deleted | accepted in part | 1.3, 1.4, 2.1 P7, 2.2, 3.3, 9.2 G-DOUBT |
| CO-2 | high | a placing sentence outside the act cannot be encoded | accepted in part | 1.3, 1.5, 1.6, 2.1 P4 and P10, 2.2, 2.4 A4, 3.1 G1 and K7, 9.6 |
| MO-1 | high | the pre-switch assertion refuses every later install | accepted | 6.2, 8.1 step 6b, 9.3 |
| SC-C | medium | READY-deciding facts without a control | accepted | 2.4, 3.2.2, 3.2.3, 3.6, 9.4, R7 |
| SC-D | medium | entry through `restates` decided by an unappraised label | accepted | 1.5, 3.2.1, 3.2.2, 3.2.3, 3.3 |
| HO-5 | medium | an unresolved statement kind narrows the pairing | accepted | 3.5, 4.2, 4.5, 9.4 |
| HO-6 | medium | an unlisted denial dropped by geometry, a kind-less one pairs with nothing | accepted | 3.2.6 |
| HO-7 | medium | K2 demotes the examination for another act's performer | accepted | 3.1 K2, 4.3 row 7, 4.9, 9.4 |
| HO-8 | medium | the binding drops genuine questions | accepted | 4.4, 4.8 |
| CO-3 | medium | the negator falls in another unit on hard-wrapped text | accepted | 1.2, 1.9, 3.7, 3.8 |
| CO-4 | medium | one-unit `words` against wraps and initials | accepted | 1.2, 2.1 P2, 3.1 I2 and I3 |
| CO-5 | medium | four units per source equals the measured maximum | accepted | 1.8, 3.1 I3 |
| CO-6 | medium | an examination told across sections fails G5 | accepted | 3.1 G5 |
| MO-2 | medium | a vendor-named cause reaches a customer role | accepted | 4.4, 4.8, 4.12, 9.1, 9.9 |
| MO-3 | medium | pass 2's 300 s read brings back D49 | accepted | 1.8, 7.2, 7.4, 7.5, 9.2 |
| MO-4 | medium | "saves never call Gemini" is false for legacy encounters | accepted | 6.2, 7.4, 8.1 |
| MO-5 | medium | an inventory-version change cannot be re-settled without a send | accepted | 1.1, 1.7, 2.5, 3.1 B1 and L1, 3.2.4, 6.2, 7.4 |
| MO-6 | medium | the budget does not fit a repair cycle under the cap | accepted in part | 7.6, 8.1, R23 |
| HO-9 | low | a reach given both polarities is not a contradiction | accepted | 3.1 K8, 3.3, 4.8 |
| CO-7 | low | identical cards make a control true of the sibling | accepted | 2.4, 3.2.3, 3.3 |
| CO-8 | low | `reached` and `reached_instrument` conflict; completion undefined | accepted in part | 1.4, 2.1 P19, 3.1 K6, 4.3 |
| MO-7 | low | the rollback image can approve a base code after a reinstatement | accepted | 6.4 |

---

## 3. Critical

### HO-1. A stated doubt is never "possibly performed"

**Finding.** `stated_doubt` had value `""` (S2 forced it) and no options, and `possibly(f, v)` matched only the claimed
value, an option or silence. So `possibly(status, performed)` was false for the design's most explicit doubt: the doubted
act was not positive, not doubted, not a same-day procedure, invisible to 4.6(5), and RANK row 2 was unreachable. Base and
E/M codes went READY beside it ("It is unclear whether the polyp was removed with the cold snare." beside 45378; "A
flexible sigmoidoscopy may have been performed in the office today" beside 99214).

**Verified.** The design text (1.3, 3.1 S2, 4.2), and v1, which counts `uncertain` as positive (`events.py` 1213,
`combination.py` 374). P-MONO's weakenings never produced a stated doubt, so no property could see it.

**Decision: accepted.** Merged with CO-1, which shows why the state was also the wrong channel.
- `ambiguous` and `stated_doubt` are gone. A doubt is an answer-level `doubts` entry `{about, objects, units, basis,
  readings}`, shaped like v1's `open_questions`. The doubted fact keeps its value (1.3, 1.4, 2.1 P7). Settle makes a
  `stated` or `unclear` doubt unknown with the value and readings kept, and a `conflict` doubt contradicted (3.3 rows 1
  and 2).
- `possibly` (4.2): a status that is not established leaves every status possible, so a doubted act is a positive
  candidate, a doubted act of its session, a same-day procedure for C-3, a blocker of 4.6(5), and a statement for
  pairing. RANK row 2 names "a doubt pass 1 reported on status" (4.8).
- P-MONO's weakenings include an added doubt (9.4). Fixtures, one per consumer of the doubt arm: the positive candidate,
  doubted and base_included, the C-3 procedure day, and 4.6(5), as "a cited rectal biopsy denial beside a doubted sigmoid
  biopsy, which must not exclude 45380" (9.5).

With the change, document A binds 45385's item at rank 2 and holds 45378 as base_included; document B holds 99214
(4.4).

---

## 4. High

### SC-A. The unlisted "drop by geometry" lets pass 1's anchor cancel pass 2's report

**Finding.** An unlisted entry was dropped when its unit already anchored an event "of the same nature", comparing unit
and nature only. One sentence routinely tells two acts or denies two, so pass 1's report of one cancelled pass 2's report
of the other. Examples: "The existing biliary stent was removed and replaced with a new ... stent." (placement filed,
removal unlisted: 43274 READY for an exchange); "biopsied with cold forceps and then removed with a hot snare" (45380
READY instead of 45385); a shared denial anchor. Dropped entries were not stored, so the export would have filed the
wrong READY as an omission pass 2 never reported.

**Verified.** 3.2.6's text compares unit and nature only, and the kind field that FINAL added was unused there.

**Decision: accepted.** 3.2.6: an entry is dropped only when an event at its unit has the same nature, a compatible kind
(equal, or one an umbrella of the other) and, when pass 2 names a session card, that session; every dropped entry is
recorded in `verification` and in the measure export with the event that absorbed it (1.7, 9.1 "absorbed unlisted
statement"). A6 now tells pass 2 that a sentence can tell or deny more than one act, and to list each one the claims do not
describe even when a card names the sentence (2.4). R8 measures absorbed entries apart from omissions neither pass
reported.

### SC-B. Pass 1's lists are treated as complete

**Finding.** No claim tested that a list is complete, yet two rules read completeness: STATIONS' "no station stated at
all" arm read pass 1's empty list as "no limitation" (BF6 with an empty list made 43259 READY), and the target row's
"both place sets established and disjoint" read pass 1's place list as complete (biopsies "from the transverse colon and
the rectum" filed with the transverse colon only, beside "No biopsies were taken from the rectum.": INDEPENDENT, 45380
READY, a dropped genuine question). P-MONO only weakened to unresolved, so it could not see a deletion.

**Verified.** The STATIONS row and the target row (4.3, 4.5). The contrast control of the transverse colon is not the
rectum, so it could not catch the second case.

**Decision: accepted in part.**
- A list's completeness is read only through an appraised claim (P3, 3.5).
  - STATIONS (4.3): the empty-list arm now needs the completeness claim established. That claim is "The document does not
    say that the ultrasound examination of session X covered only some of the esophagus, the stomach and the duodenum."
    It is CPT Studio's rendering of pass 1's empty answer to P20, appraised with its limitation-form control (3.2.2,
    3.2.3). BF6 with an empty list gets that claim contradicted, and is held.
  - Place and lesion independence (4.2 `apart_by_place`, `apart_by_lesion`; 3.2.3 "Pair controls"): wherever a rule sets
    two objects apart by disjoint places or different lesions (the target row, D118's one stricture, bundling identity),
    the difference counts only when the pair controls ("This act was done in the rectum.", in both directions) were
    rejected. The second case: pass 2 supports the pair control, so the relation is UNRESOLVED and 45380 is held (4.11).
- P-MONO's weakenings include deleting a member of a multi-valued list, with the list's completeness claim and pair
  controls left as they were (9.4).

**Rejected part: "add deletion of ... events to P-MONO's weakenings."** Deleting a whole event is not a weakening in the
information order. It changes what the document says, and the right outcome can then move from HELD to READY.
Counter-input: "[S5] A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare. [S6] No polypectomy was
performed." E5 is performed and D6 is an all_of_kind denial, so the pair is a CONTRADICTION and 45385 is held. Delete D6
and 45385 is READY, which is correct for a document without S6. A property that forbade it would forbid correct
behaviour. An event neither pass reports stays the measured omission residual (R8); it cannot be proved away.

### HO-2. Statement attributes are claimed with act sentences

**Finding.** A denial's session, timing, target and device were claimed as "This act was done during session X", "... on
a date before the date of service", "... in the {landmark}". For an act that was not done, a faithful pass 2 must
contradict them (A3; the reading probe (a) relies on). With "the first row that returns decides", the unestablished timing
row stopped every later row, so no denial could be set apart, CONTRADICTION was unreachable, and 4.6(1) and the
broad-statement rule were unreachable. Examples: the v3 development document (45386 held; v1 sets it apart by time); "No
prior colonoscopy." (45378, the only code, held); BF17 holding the injection it excepts.

**Verified.** 3.2.2's templates; 4.5's row order; the v3 pin (`independent:time:another_time`).

**Decision: accepted, with a second change the finding implies.**
- Statement-phrased templates and controls for every attribute an event with a negated status is claimed on ("This
  statement is about dilations on a date before the date of service.", "... about session X2", "... in the rectum", "...
  with a hot snare"), versioned in APPRAISAL_VERSION (3.2.1, 3.2.2, 3.2.3).
- Every row of 4.5 is evaluated, and the pair is INDEPENDENT when at least one row proves it on established facts
  (preconditions kept: the target row needs a single, listed or segment breadth); UNRESOLVED when no row proves it and
  any row is unresolved; SAME only when all rows are SAME. An unknown never counts as a difference (P-ANY-ROW, 9.4).
- A negated statement of the code's kinds whose session or date relation is not established gives `statement_scope`,
  never `not_documented`, so a broad denial is never dropped (4.6).

Under both changes, the v3 document is set apart by session and timing (45386 READY), "No prior colonoscopy." by timing
(45378 READY), and BF17's excepted injection by its exception.

### HO-3. A caught misfiled denial stops being a statement

**Finding.** Only an established negated status made an event a statement. When pass 2 caught probe (a)'s misfiling
(a denial filed as a performed snare), the event's status was merely unresolved, it paired with nothing, and a genuine
snare elsewhere made 45385 READY against a document that denies it.

**Verified.** 4.5's "Which pairs" and 4.4's `found` short-circuit.

**Decision: accepted.**
- An event whose status is not established, for any reason, is a POSSIBLE statement and pairs with every compatible act
  (4.5); `possibly` leaves every status open for it (4.2).
- A possible statement's scope is its own target when act-phrased claims established it (its place or lesion stands for
  a single target); otherwise nothing sets it apart, and an UNRESOLVED relation asks `statement_scope`, quoting both
  statements.
- The probe-(a)-plus-genuine-snare case is held (1.9, 3.8, 9.5), and P-MONO weakens an event's status to unresolved (9.4).
- The cost is new holds from appraisal noise on one act's status. It is stated as a limit (3.7) and as R25, and measured
  by the cause `relation:possible_statement` (G-NOISE).

### HO-4. Appraisal health cannot see a degenerate appraisal

**Finding.** `health = 1 - (unclear + incoherent pairs) / claims`, refused below 0.5, was never below 0.5 for a yes-man
(at least 0.5 by construction) and was 1.0 for an all-contradicts, all-qualified or all-detached answer. Each settled into
the all-held page 3.2.6 says must never exist.

**Verified.** The arithmetic.

**Decision: accepted in part.** Health is now three measures, pinned in APPRAISAL_VERSION and set from D3 before the
acceptance run (3.2.6):
- control acceptance (controls not rejected) above 0.5 refuses: a yes-sayer;
- establishment (non-control claims established) below 0.5 refuses: a no-sayer, a detached answer, or a pass 1 so wrong
  that no page should pose as its assessment;
- more than 10% of claims with no verdict refuses.

G-HEALTH checks them against development documents (9.2).

**Rejected part: "count both-rejected pairs as incoherent."** A claim and its control can both be false, so rejecting
both is often the correct answer, and counting it as incoherence would mark a correct appraisal as degenerate.
Counter-input: "[S6] A repeat colonoscopy is planned in 3 years.", filed by pass 1 (wrongly) with its own date relation
on_date_of_service. "This act was done on the date of service." is contradicted, and so is its control "This act was done
on a date before the date of service." Both verdicts are correct: the act is planned for later. Such pairs settle
unresolved (`appraisal_contradicts`) and count against establishment, so an appraisal made mostly of them is refused
anyway, without calling a correct verdict incoherent (3.2.3 coherence table).

### CO-1. The doubt channel Gemini uses was deleted

**Finding.** Gemini commits a value and raises its doubt in a separate open question (status `uncertain` 0 of 2,950;
time `unknown` 6; 111 open questions; time and performer questions on events with a definite value 124 of 129). v2 deleted
`open_questions` and `contradicts[]` and expected a state Gemini does not use. BF2 could then be EXCLUDED where HELD is
expected, and a finding-versus-act conflict (W1S-499: "Body and fundus normal" against "7. Gastric body polyp removed with
cold snare.") had no encoding at all.

**Verified.** The counts (section 1) and BF2's two recordings.

**Decision: accepted in part.** The `doubts` list of HO-1 is the channel the lens asks for: it keeps the committed value,
holds the doubt's units and readings, and settles per named fact (unknown, or contradicted for basis `conflict`). It is
answer-level, like v1's open questions, rather than a second per-object list, so one meaning has one encoding. BF2 (2.2)
is held on `event_time` and never excluded, because an exclusion needs an established other date. W1S-499 (2.2 BF24) is a
`conflict` doubt on the act's status, so 43251 is held `conflict:snare` with both statements quoted. G-DOUBT (9.2):
on every development case whose expected outcome rests on a doubt, v2 must report it in every run.

**Rejected part: "v2 must raise at least as many doubts as v1 raised open questions."** Parity is the wrong target,
because many of v1's questions concerned attributes that v2 represents as silence. Counter-input: on BF2's document,
FRESH-2 r1 raised an open question about the performer of E2, whose performer the document simply does not state. In v2
that is an empty slot, already unknown, and it already holds every code that needs it. A parity target would push the
prompt to emit a doubt for every unstated attribute: two encodings of one meaning, and over-doubting, which is
unnecessary holds. v1's count is printed beside v2's as a diagnostic, never as a target.

### CO-2. A placing sentence outside the act or section cannot be encoded

**Finding.** P10 (own statement or a frame in it), G1 (`frame` inside the section, `antecedent` before the act), 1.5 and
1.6 left no valid encoding for a placing sentence after the act ("This was done at the referring facility in 2024."), in
another section (an Indication's "the procedure is described below"; a Plan's "the narratives above are from 2023"), or an
attestation governing the findings sections (C2MEM-031). The only allowed filing made acts inherit "today".

**Verified.** The three documents, read; the rules as written.

**Decision: accepted in part.**
- New link `placing`: any unit that is not the object's own anchor, with its meaning (which acts it governs) appraised per
  act (1.3, 3.1 G1, 2.4 A4).
- A section's occasion or performer, and an act's own date relation or performer, may cite it (1.5, 1.6, 2.1 P4 and P10).
  BF2, BF22 and BF23 are consistent with P10 (2.2).
- K7 now also refuses a `placing` source that gives "today" or "the team" to a history, indication, medication or plan
  section (3.1).
- C2MEM-031, twins-015, W1S-222 and f2-after-002 are in D3 (9.6). The attachment rests on pass 2, stated as a limit (3.7)
  and as R22.

**Rejected part: "with which acts or sections it governs as Gemini's own fact (ids)."** A separate `governs` list would
be a second encoding of a fact the answer already carries: which facts cite the placing sentence. Two encodings can
disagree. Counter-input: W1S-222's "No endoscopy was done today; the narratives above are from 2023." With a `governs`
list naming N2 only while N3's occasion also cites the sentence, the design would have to choose which of Gemini's two
statements wins. Without the list, each section that cites it is governed, and each of its acts is appraised against it.

### MO-1. The pre-switch assertion refuses every install after v2's first row

**Finding.** "EventInventory absent or empty, and no Assessment `cpt-studio-events@%`" also matches v2's own rows, on
append-only tables. After the walk writes one v2 row, a fix release, a re-install after a switch-back, and a same-revision
`app` re-run are all refused, and only a deletion of records (owner class d) could clear it.

**Verified.** INSTALL.md: `app` is the blue/green switch, and same-revision re-runs (D83) are documented.

**Decision: accepted.** The installer asserts only that no v1 rows exist: no Assessment with engine version
`cpt-studio-events@1`, and no EventInventory row with `interpretation_version` `gemini-events@1` (6.2). A test runs
install, writes one v2 row, switches back, re-installs and re-runs `app` (8.1 step 6b, 9.3).

---

## 5. Medium

### SC-C. READY-deciding facts without a control

**Finding.** The hand-listed control table left `session.kind`, about a dozen codable kinds, `anatomy.subtype`,
`reached_anatomy`, `lesion.multiplicity`, `visit.basis`, a statement's targets and `performer_person` decided by a single
"supports". Example: a balloon sphincteroplasty filed as a sphincterotomy went READY as 43262. Cards labelled with pass
1's kind would also let a control be rejected against the card rather than the document.

**Decision: accepted.**
- Controls are generated from the read-sets (3.2.3). P-CONTROLLED (9.4) fails in CI when a READY- or exclusion-path
  attribute has no control and is not on the pinned UNCONTROLLED list. That list (`act.date`, `encounter.date_of_service`,
  `part_of`, `part_relation`, purposes other than hemostasis, `covers`, `same_as`) gives, for each entry, why a single
  verdict there can only hold. 3.6(3) and R7 cite it.
- KIND_SIBLINGS covers every codable kind (sphincterotomy/dilation among them); SESSION_SIBLINGS, subtype, multiplicity,
  basis, statement-target and person controls are added.
- Cards name only the object's type and its sentence (2.4), and `act.session` prints no label (3.2.2).

### SC-D. Entry through a `restates` restatement is decided by an unappraised label

**Finding.** The restates-versus-summarizes label that flipped an act's entry to the documenting clinician was a plain
pass-1 value: no state, no source, no claim, no control. A nursing-note biopsy with a summarizing impression went READY.

**Decision: accepted.** The role is a claimed fact ("... tells this act in full, in its own words, not only as a summary,
a title or a reference to another part."), with the summary form as its control (3.2.2, 3.2.3). The entry moves only when
the role and the owner of the restatement's section are established. An unestablished role leaves the entry where it is,
and `event_entry` becomes a question rather than an explanation (1.5). 3.3 now states the per-act entry rule the same way.

### HO-5. An unresolved statement kind narrows the pairing

**Finding.** Compatibility compared D's claimed kind whatever its result, so a sibling misfiling caught by pass 2 (D filed
`emr` beside a snare) dropped the denial out of every pair.

**Decision: accepted.** A statement whose kind is not established is compatible with every kind of its session's family,
or every kind when the session is unknown too (4.2, 4.5). As a candidate for a code, an act's unestablished kind stays at
its claimed value, readings and control sibling, so one noisy kind claim does not make an act a candidate for every code.
Kind is in 3.5's list, and P-UNKNOWN-KIND is a property (9.4).

### HO-6. An unlisted denial dropped by geometry; a kind-less one pairs with nothing

**Decision: accepted**, together with SC-A. Same drop rule (nature and compatible kind). Rule 4 now pairs a kind-less
unlisted denial or doubt with every possibly-positive act of its session, or of every session when it names none (3.2.6).

### HO-7. K2 demotes the examination when one act has another performer

**Finding.** K2 made both the act's and the examination's performer unresolved, and row 7 reads the examination, so a
surgeon called in to place clips held every code of the session. P-INDEP could not see a coupling made in settle.

**Decision: accepted.** K2 has no performer arm, because different performers in one session are legitimate. Its date arm
unresolves only the act's own `session` fact and never touches the examination (3.1, 4.3 row 7). P-INDEP-SETTLE runs the
perturbation through settle, from constructed answers (4.9, 9.4), and the two-performer session is a fixture (8.1 step 2b,
9.5).

### HO-8. The binding drops genuine questions

**Finding.** Only the bound act's witnesses were recorded, and tie-break (3) preferred an act whose item was an
unanswerable explanation.

**Verified.** v1's `_focused` (section 1).

**Decision: accepted.** Every positive candidate's witnesses go into `held_facts` (4.4). The binding (4.8) is now:
- kept-span overlap;
- then rank across the candidates, so a contradiction on any candidate is asked first;
- then the fewest non-T requirements;
- then, at an equal rank, a question before an explanation;
- then document order.

Both cases are fixtures (4.8, 8.1 step 4a).

### CO-3. On hard-wrapped text the negator falls in another unit

**Finding.** The unit rule cut at every line break, so Note #8's three wrapped denials put the negator in the previous
unit, and the probe-(a) guarantee did not hold. For S45, L1 even confirmed the misfiling.

**Decision: accepted.**
- A line break inside a paragraph is a hard wrap, and the unit continues, when the earlier line does not end in `.`, `!`,
  `?` or `:` and the next line begins with a lowercase letter. This is a two-character test, never a word (1.2 rule 2).
- Claims cite, and cards show, the anchor's sentence closure, which carries a negator across a wrap the join misses
  (rule 6).
- Measured: Note #8's three denials are each one unit (1.2). The probe-(a) statement is rewritten in those terms (1.9,
  3.8). The residual, a wrap continued by an uppercase letter and longer than the 12-unit closure, is stated (3.7, R9).

### CO-4. One-unit `words` against wraps and initials

**Finding.** I2 required words inside one unit, while I3 said "inside the anchor's units". 8.8% of v1 words values and
18.5% of events' kind or status words crossed a unit, and PAIR-4-W2's correct READY became a hold.

**Decision: accepted.**
- Words may run over the source's consecutive units, with whitespace runs matched loosely. One rule serves anchors and
  sources (1.2 rule 7, 3.1 I2 and I3, 2.1 P2).
- A period after a one- or two-letter token beginning with an uppercase letter ("E. Morgan", "Dr. B. Prior") does not
  end a unit (rule 3).
- Measured: words crossing a unit fall from 1,760 to 21, and events whose kind or status words cross a unit from 545 to 13.
  "An over-split is harmless" is now true, and the design says why (1.2).

### CO-5. Four units per source equals the measured maximum

**Decision: accepted.** At most 12 units per source, D32's margin over the measured maximum of 6 under the revised rule,
and an over-long source is an ITEM-level finding (`source_too_long`), never a whole-answer refusal (1.8, 3.1 I3).

### CO-6. An examination told across several sections fails G5

**Finding.** G5's "a unit stating an act of that session" was undefined, and Note #8 tells its reach in three sections, so
the owner's "extent on all five" hold would have returned.

**Decision: accepted, and corrected further.** Re-reading D36 showed that the natural reading of the old clause
admitted exactly what D36 forbids: a reach cited from another act's sentence (W1S-399). G5 is restated from D36. A
session's extent sources must lie in its examination's anchor or restatements, or in a unit that anchors no act at all; a
source lying only in other acts' anchors is `extent_inferred`. There is no section test (3.1 G5). Note #8's completion and
neo-terminal-ileum sentences anchor no act, so its extent is accepted. Both documents are fixtures (8.1 step 1c).

### MO-2. A vendor-named hold cause reaches a customer role

**Finding.** `gemini_unknown` and `gemini_contradicted` were shown to the reviewer, a customer member, and both
confidentiality nets missed them, because `_` is a word character.

**Decision: accepted.**
- Causes are `reading_unknown` and `reading_contradicted` (4.4). Causes are operator data; the reviewer sees each held fact
  only as CPT Studio's fixed sentence for its fact key (4.8, 4.12).
- `customer_api.FORBIDDEN` and `customer-denylist.json` replace the word boundaries around provider names with
  letter-and-digit boundaries, `(?i)(?<![a-z0-9])(?:corti|...|google)(?![a-z0-9])`. The judge ran this pattern: it matches
  the joined forms and not clinical words such as `corticosteroid`.
- Test vectors pin both sides (4.12, 8.1 steps 3c and 6b, 9.3, 9.9).

### MO-3. Pass 2's 300 s read brings back D49

**Finding.** At 82.4 tokens per second, the slowest measured rate, a cut-off answer needs about 398 s. A thinking spike
like FRESH-2's maximum pushes the largest pass 2 past 300 s. The outcome would be UNKNOWN (reconcile, an encounter-wide
block, a paid resend, unrecorded usage) instead of TOO_LONG. The claim bound of 1,200 could never fit the cap.

**Decision: accepted.**
- Pass 2 takes D49's 480/510/560 s (7.4, 8.1 step 0b). The modelled largest pass 2 with the measured maximum thinking is
  about 29,400 tokens, about 356 s (7.2).
- The claims per request are bounded at 640, computed so that the bound times the output per verdict plus the largest
  measured thinking fits the cap, and recomputed from D2 (1.8). A claim set over it is not sent (7.4 door 0, 7.5).
- G-SIZE measures the claim count and the thinking tail (9.2).

### MO-4. "Saves never call Gemini" is false for every live legacy encounter

**Finding.** On a c2e53f8e revision, the kept code's context save queues a reading (two paid calls). The new assessment's
fingerprints then drop the legacy approval, and the downloaded report no longer matches the decisions.

**Decision: accepted.**
- On a revision with no v2 inventory, a context save stores the values and queues nothing. The encounter says its codes
  were checked before the change, and a new approval or export of the stale legacy assessment is refused (6.2).
- The explicit "Check again with the current reading" action says, before it runs, that the document will be read again
  and that earlier decisions will need review. Only that action queues the reading (6.2, 7.4, 8.1 step 5b).
- That a legacy approval does not carry across engines goes to the owner before the install as an accepted-capability loss
  (class b). Existing decisions and downloaded reports stay as records.

### MO-5. An inventory-version change cannot be "re-settled from the stored bytes, no send"

**Finding.** The checks decide which facts are claimed, so a check change changes pass 2's request. Verdicts matched by
positional claim id would be read against different claims. Every first-release v2 assessment would become UNREADABLE,
and development pass-2 recordings unreplayable.

**Decision: accepted.**
- Identity and binding:
  - The appraisal request is a function of INVENTORY_VERSION too (3.1 B1, 7.4).
  - The appraise key is the request's sha (99 characters; 196 of 200 with the longest suffixes) (7.4).
  - The claim list's sha is among the row's bindings (1.7).
  - Every verdict is stored with its claim's content key: template, subject, value and units (3.2.4).
- Re-settling:
  - A re-settle reuses verdicts only for claims whose content is unchanged.
  - A changed claim set needs a new pass-2 send, which for an existing record is an explicit act (6.2).
  - EventReader reads every shipped v2 inventory version as stored, so nothing becomes UNREADABLE (6.2).
- L1 judges against the document's own date at claim time, never a member value; the member date only demotes later
  (3.1 L1).
- Pass-2 re-sends after a check repair are budgeted (6.2, 7.6).

### MO-6. The recording budget does not fit one repair cycle under the shared cap

**Finding.** At December prices, D1-D3, iterations, A and a second A after a request-changing repair come to more than
the ~$300 monthly cap. After the switch, a reached cap is a bare 429 that pauses the installed site, which shares the
project through the test credential.

**Decision: accepted in part.**
- 7.6 budgets A' (one re-run) and states the total: about $350 at December prices.
- Before A is sent, the owner receives the total against the cap and the month's spend (class d).
- The harness stops when the month's recorded spend (its own ledger plus the installed site's usage) plus the next batch's
  cap would exceed the cap less a pinned reserve for the site.

**Rejected part: "after the switch, run tests on a separate project or key."** This is not rejected on the merits. It is
a decision about keys and money, which belongs to the owner (class d), so the design cannot take it. The design asks it
before any post-switch batch, and keeps post-switch batches inside the reserve rule until it is answered (7.6, 8.1,
R23).

---

## 6. Low

### HO-9. A reach reported with both polarities is not a contradiction

**Decision: accepted.** K8: a supported and a negated fact of one value (or a contained value) on one object's `reached`,
`stations` or act `places` settle as one contradicted fact of pass 1, asked at rank 1 (3.1, 3.3 row 1, 4.8). It creates
nothing: pass 1 reported both sides.

### CO-7. Identical cards make a control true of the sibling act

**Decision: accepted.** When two events share an anchor unit, each card quotes that event's own anchor words, which are
document text, never a value (2.4). In fb08 the two denials' status words differ, so the cards differ and each timing is
appraised apart. Cards still identical while the events' values differ settle `cards_indistinct` (3.2.3, 3.3).

### CO-8. `reached` and `reached_instrument` contradict each other; completion is undefined

**Decision: accepted in part.**
- `reached` is the endoscope's reach by definition.
- A point only a guidewire, catheter or capsule reached goes in `device_reached`, which no rule reads (1.4, 2.1 P19).
- K6 unresolves a point listed in both (3.1).
- Completion is defined against the examination's own intended extent, as the document states it (1.4, 2.1 P19).
- v6 is a fixture: the endoscope reaches the anastomosis, and the guidewire's point is kept apart (2.2 BF25).

**Rejected part: "make reach a list of {point, instrument, anatomy} entries."** That would add an instrument field to
every reached point, nearly all of them the endoscope, for no rule that reads it. Counter-input: v6, "the colonoscope was
advanced to the ileocolonic anastomosis" with a guidewire beyond it, files as `reached` [anastomosis] with
`reached_anatomy` Y1 (ileocolic) and `device_reached` [neo_terminal_ileum]. COLFULL's ileocolic arm is met and 45386 is
READY, and nothing the per-point form would add changes that or any other rule's input.

### MO-7. 6.4 says the old image "approves or exports none of it"

**Decision: accepted.** 6.4 now says that the old image reads statuses as stored, and states D59 finding 13's limit: a
reinstatement made on the old web can leave the diagnostic base code approvable. The `reinstatable` note stays in v2's
receipts (6.4, 8.1 step 6b).

---

## 7. Corrections found while verifying (not in the finding list)

1. **G5 inverted D36** (with CO-6, section 5). The pre-refutation clause "a unit stating an act of that session" would have
   readmitted W1S-399's four false READYs, a reach cited from a biopsy sentence. G5 now follows D36's wording.
2. **The `date_literals` guard gap** (named in the self-certification write-up, not in its finding list). The copied
   parsers need v1's month and weekday tables, which NoWordLists refuses, so the builder had to exempt the one module L1
   relies on. It is now pinned: its functions are AST-equal to v1's eight, its two tables match by sha, and any other
   module-level string collection there fails (5.6, 5.7).
3. **L1 at claim time.** Fixing L1 to the document's own date at claim time (MO-5) also means a day literal that meets
   no document date no longer stops the claim. Otherwise a document whose date of service the member supplies would have
   left every such timing fact unappraised forever.
4. **The appraise key's length.** Adding the claim set's identity to the key had to fit `Job.idempotency_key`'s 200
   characters with the longest suffixes. The request's 16-hex sha prefix keeps it at 196 (7.4).
5. **A contradiction outranks a doubt in settle.** With doubts as their own rows, the settle table puts contradiction
   first (3.3 rows 1 and 2), so a fact both contradicted and doubted is asked as a conflict.

## 8. What the revision costs and risks, stated

- **More claims.** Statement templates, generated controls, pair controls and the completeness claim raise pass 2 from
  about 10 to about 12 claims per event. Evidence without words lowers the output per verdict from about 28 to 24 tokens.
  Net: median $0.083, mean $0.118 per document at November rates; $0.166 and $0.236 from 2026-12-01 (7.1).
- **More holds in exchange for fewer wrong READYs, each measured by cause:**
  - possible statements (R25);
  - pair controls not rejected;
  - the completeness claim;
  - doubts Gemini reports.

  G-NOISE stays the gate (12% before the acceptance run). A failure is repaired in prompts, templates, geometry or a
  coding rule, never by weakening settle or the pairing.
- **Placing sentences cannot be filtered by geometry.** Their attachment is pass 2's per-act judgement (R22).
- **Two owner items (class b and class d) and one owner question (class d)** now sit in the plan before the acceptance run:
  - the legacy context-save loss (class b);
  - the budget against the cap (class d);
  - a separate test key after the switch (class d, a question).
