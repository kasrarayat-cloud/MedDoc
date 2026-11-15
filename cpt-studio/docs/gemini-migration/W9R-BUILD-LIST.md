# BUILD-LIST - every w9r FIX for AMENDMENT-2's build round (D280-D291)

Written 2026-11-15 (session 31dfc45d) by the judge of the w9r rulings, from `RULINGS-DRAFT.md`. Steps and file plan are
AMENDMENT-2 section 10's (A2:1238-1263), amended by D291:
- F3 also owns, for this round, `engine/evaluate.py`, `engine/questions.py`, the whole of `interpretation/wording.py`
  and `studio/customer_api.py`, with `tests/v2/test_evaluate.py`, `test_questions.py`, `test_wording.py` and
  `test_update_customer.py`;
- the integration owner (F0) applies texts in files no step owns.

Code lines are the built tree's (step8-195e06e90). "Before the ten-pair test" means before the first of D277's pairs
(S01-S10 short, L01-L10 realistic). "Before the install" means before the install, after the pairs if need be.

## Conditions on every item

1. **D276's proofs** for every FIX that moves a status, an item or a sentence (D291):
   - one synthetic input outside the development set that it must release or reword, and one it must still hold;
   - replay over every recorded batch with a complete pass 2 (F3all, F3long, F2high-p2, D2low, D2medium, D1v, D1w, each
     through a copy of the tree that recorded it), reporting each status, item and sentence that moves;
   - the whole `tests.v2` package against a clean baseline; refutation with a generality lens.
2. **One owner per file** (F2 8.0); a change in another step's file goes through the integration owner, serially.
3. **A mutation proof asserts its own application and restoration** (sha256 before and after, printed; AGENTS.md).
4. **The build's integration** runs the seam check (D252) with D283's named scenes and the mandatory refutation of the
   finished diff before merge (A2:1253-1255).
5. **The replay counts D277 moved here** (D291), reported with the install's evidence: Q-UNNAMED, Q-F8's consequence,
   R3D-NC, the 43255 count, the claimed-device DRE holds (D280.3), G3-25's input.

## Summary

| # | items | step | files | when |
|---|---|---|---|---|
| B1 | G3-09, G1-05 (iii), G1-06 | F3 | engine/evaluate.py, engine/questions.py, interpretation/wording.py | before the ten-pair test |
| B2 | G3-24 | F3 | engine/pairing.py | before the ten-pair test |
| B3 | G1-05 (i)-(ii), case B | F3 | engine/questions.py, interpretation/wording.py | before the ten-pair test |
| B4 | G1-07 | F3 | engine/questions.py | before the ten-pair test |
| B5 | G3-10 | F3 | interpretation/wording.py | before the ten-pair test |
| B6 | G3-27 (the verb) | F3 | interpretation/wording.py | before the ten-pair test |
| B7 | G3-15 | F3, F6 | wording.py, questions.py, customer_api.py (F3); overlay.py (F6) | before the ten-pair test |
| B8 | G1-08 | F3 | studio/customer_api.py | before the install |
| B9 | G3-28 | F3 | engine/facts.py, engine/questions.py, engine/coverage.py, engine/classes.py | before the ten-pair test |
| B10 | G3-02, G3-03, G3-11 | F3 | engine/combination.py | before the ten-pair test |
| B11 | G4-02 | F3 | tests/v2/test_combination.py | before the ten-pair test |
| B12 | G3-12 | F3 | engine/combination.py (+ a catalogue test) | before the ten-pair test |
| B13 | G3-13 | F3 | engine/coverage.py | before the ten-pair test |
| B14 | G3-14 | F3 | engine/combination.py, engine/coverage.py | before the ten-pair test |
| B15 | G1-01 | F3, F6 | engine/assess.py (F3); studio/review.py (F6) | before the install |
| B16 | G1-02, G1-03 | F3, F6, F0 | engine/assess.py (F3); overlay.py, readers.py (F6); the seam harness (F0) | before the install |
| B17 | G1-04 | F6 | studio/review.py | before the install |
| B18 | G3-16 | F3 | engine/assess.py | before the install |
| B19 | G3-17 | F6 | interpretation/overlay.py, studio/review.py | before the install |
| B20 | G3-32 | F6 | interpretation/overlay.py | before the ten-pair test (before the build's seam check) |
| B21 | G2-01 | F0, F8, F6, T | cptstudio/settings.py and three guard modules (F0); ops/test_install_harness.py (F8); order with F6; tools/v2/record_v2.py (T) | before the ten-pair test |
| B22 | G2-03 | F3, F0 | contract/claims.py (F3); cptstudio/settings.py (F0) | before the install (texts; settings.py's with B21) |
| B23 | G3-04 | F3 | tests/v2/test_properties.py | before the install |
| B24 | G4-01 | F3 | tests/v2/test_questions.py | before the install |
| B25 | G4-03 | F3 | tests/v2/test_coverage.py | before the install |
| B26 | G4-04 | F3 | tests/v2/test_assess.py | before the install |
| B27 | G4-05 | F6 | tests/v2/test_review_binding.py | before the install |
| B28 | G4-06 | F6 | studio/review.py | before the install |
| B29 | G4-07 | F3 | tests/v2/test_properties.py | before the install (with F3's generator change) |
| B30 | G4-08 | F3 | tests/v2/test_properties.py | before the ten-pair test |
| B31 | G4-09 | F0 | tests/v2_documents.py | before the install |
| B32 | G4-10 | F0 | tests/test_readers_dispatch.py | before the install |
| B33 | G4-12 (with G2-04's texts) | F0 | HARNESS.md, tests/test_interpretation_replay.py | before the install |

Files added to a step's list by D291 (not in A2 section 10): `engine/evaluate.py`, `engine/questions.py`,
`studio/customer_api.py` and the rest of `interpretation/wording.py` (to F3). There is one new function,
`facts.established_kind` (B9). New messages (B1's residual form, B7's ADDON) are appended to `wording.Message` and
mirrored in `questions.MessageId`. No new module and no migration.

## F3

**B1 - G3-09, G1-05 (iii), G1-06 (D280.1, D280.3).**
- Change, row 7: `engine/evaluate.py` `_row_done` (:822-825) skips an examination established as a digital examination
  (kind supported examination and device supported manual).
- Change, the residual form: whenever a held examination's device claims manual without establishing it
  (`pairing.digital_examination`, device not supported manual, the overfilled device of A2 4.3.3 c included), every
  item resting on it is worded in D258's shape, whatever its held fact (status, date, performer, entry, doubt, conflict,
  device).
  - The question names the held session's examination by its service and asks whether it is documented as performed (in
    full or in part) on the date of service. It quotes only `_quoted_examination`'s examination (questions.py:1120-1131),
    never the claimed one.
  - The reason quotes the claimed examination's own words as a statement whose technique CPT Studio could not confirm,
    with its open fact; sides are quoted for a conflict, the owner named for an entry.
  - The clarification keeps the held fact's key (`wording.fact_key` may take it from the item).
  - `questions.py:969-978` builds the Fill; `wording.py` adds the form (a message of its own, appended, or one per fact
    key).
  - The status, held facts and rank are unchanged.
- Pinning tests:
  - in test_evaluate and test_questions: D265's grids (F1 104 rows, F3 20, Q4, Q4+, D253's A2 shapes),
    refute-r4a-r1's v9_dre_own_rows, v9_dre_own_rows2, v9_dre_conflict and refute-safety's qd2_steer. Each
    established-DRE row equals the no-DRE document (45385 READY). Each claimed-device row is held, its question naming
    the session's examination and quoting none of the claimed examination's words, its reason quoting them;
  - `D265Items.test_qd2_the_digital_examinations_own_rows_never_name_it_as_the_session`'s eight rows restated to READY;
  - G2-28's input (a colonoscope examination, device doubted endoscope|manual, status open) pinned held;
  - P-WORDED and D254 rule 4's property cover the new form.
  - Mutants: `_digital` (claimed) read in row 7 in place of the established device (G2-28's pin fails); the residual
    question asking about the claimed examination (the claimed-device pins fail).
- When: before the ten-pair test.

**B2 - G3-24 (D280.2).**
- Change: `engine/pairing.py` `statement_kinds` (:398-403). A statement whose kind is supported examination and whose
  device is supported manual concerns no examination act (its kinds less Kind.EXAMINATION). The claimed device keeps
  pairing (option (a)).
- Pinning tests:
  - test_pairing `D265DigitalExaminationTests.test_the_statement_side_is_read_as_before` (tests/v2/test_pairing.py:2006)
    restated: an established DRE statement is not paired, a claimed one is;
  - g3b's 18-shape G3-24 grid and refute-safety's dre_statement as pins: every established-device row READY with no held
    fact, every claimed or negated-device row held;
  - PMono, Pairing and Independence green.
  - Mutant: the claimed device read in place of the established one (a device weakened into a manual claim releases:
    P-MONO fails).
- Prototype measured: the whole tests.v2 on ruling C plus this rule gives exactly 9 failures, B1's eight pins and this
  pin (`judge/logs/t-g324b-testsv2.log`).
- When: before the ten-pair test.

**B3 - G1-05 (i), (ii), case B (D281).**
- Change:
  - `engine/questions.py` `_session_named` (:1133-1144) clears the owner with the device, place and lesion where the held
    act's words are not quoted;
  - `wording.py` `_another_entry` (:1400-1412) names the code's group ("this code accounts for") only for the code's own
    act, and names a held session examination with no group by the Fill's act.
- Pinning tests:
  - test_questions D265Items' entry rows (nursing, anesthesia, another clinician);
  - test_wording, case B ("The colonoscopy is documented only in the nursing entry ...");
  - a property over the D265 and D266 grids: whenever a Fill's words are not its held event's anchor, its owner, device,
    place and lesion are empty.
  - Mutants: the owner kept; the group named for a row-7 act.
- When: before the ten-pair test.

**B4 - G1-07 (D281).**
- Change: `engine/questions.py` routes rank-2 unlisted holds by the act's claimed kind (a predicate over
  `facts_.fact(R, event, KIND).value`) at :1089 and :1421-1424, never by `act_kind`. `_quotable` (:1111-1117)
  requires the act's kind to hold examination.
- Pinning tests: test_questions grid - E1 kind supported, unresolved, doubted examination|snare, silent; no-card doubt
  and denial; carded X1. UNLISTED_SCOPE, or the session's DOUBT, for the first three; DOUBT for silent; E1 quoted only
  when its kind is supported; the denial rows in B5's form. Mutant: routing by act_kind.
- When: before the ten-pair test.

**B5 - G3-10 (D281).**
- Change: `wording.py` `_doubt` (:1299-1301; DENIAL_STATED :1311-1313). A DENIAL reads "The document states
  “<denial>”, a statement that an act was not done; CPT Studio could not confirm from the document whether it is about
  <the act>." With no statement: "The document states that an act was not done; ...". The question, held fact and
  status are unchanged.
- Pinning tests:
  - test_wording's D266 rows (:2735-2736, D266NoQuote's DENIAL rows) restated;
  - an engine-to-renderer test over refute-r4a-r1's v9_denial_pairs (kind snare, removal or none, by no card or carded
    X1), v9_denial_same_unit and refute-r3c-r1's two-session input. Every DENIAL reason has the new form and never "was
    not done" after the act's label;
  - P-SLOTS, P-WORDED and the customer denylist scan green.
  - Mutant: DENIAL_STATED restored.
- When: before the ten-pair test.

**B6 - G3-27, the verb (D281).**
- Change: `wording.py`. Whenever a question asks whether the held session's examination was done on the date of
  service, its words say row 7's done ("documented as performed, in full or in part, on the date of service"). This
  covers `_unlisted_scope` (:2437), the session's DOUBT question (:1297) and B1's form. One form for every state, or
  that form for an examination established begun and not completed: either is true.
- Pinning tests: refute-safety's begun_scope shape (E1 attempted_not_completed beside a no-card examination doubt): the
  question says "in part" and quotes E1; D266Quotes' 'begun' row kept. Mutant: "documented as done" restored for a begun
  examination.
- When: before the ten-pair test.

**B7 - G3-15 (D284), F3's half.**
- Change:
  - `wording.py` `Message.ADDON` appended, from `code` and `codes` alone, TEXT_FREE, with a true absence form for
    `codes`;
  - `questions.py` `MessageId.ADDON`, with `message_of` (:668-708) returning it for a performed_status witness whose
    cause is `engine/assess.ADDON_CAUSE`;
  - `customer_api.py` gets a fixed sentence chosen by the recorded message, and a WITHHELD_WORDS entry for ADDON_CHECK.
  - The fact key and rank stay; the fingerprint changes with the message and Fill (assess.py:768-775).
- Pinning tests: test_wording (every present/absent combination, never "could not confirm ... done", no quote);
  test_questions Mirrors and message_of; test_assess AddonTests (43273 alone; 99213 + 99417: the item is ADDON naming
  the primaries); test_update_customer (the customer sentence in the three states, never STALE_WORDS); the renderer
  sweep and P-WORDED.
- When: before the ten-pair test. F6's half is B7 under F6 below.

**B8 - G1-08 (D284).**
- Change: `customer_api.py` HELD_FACT_ASKS (:202-209). ENTEROSCOPY_APPROACH, EXAMINATION_APPROACH and ANOTHER_TRACT
  read "whether the <service> this code describes was performed".
- Pinning tests: test_update_customer `D267HeldFactWords` (tests/v2/test_update_customer.py:640-645, :694-699) restated
  - explanation ids carry the class phrase and no phrase of the attribute they state.
- When: before the install (latent; built with B7 in the same file).

**B9 - G3-28 (D287).**
- Change:
  - new `engine/facts.py` `established_kind(R, event) -> Kind`: the catalogue kind of the supported kind with its
    supported purpose, else Kind.OTHER - questions.act_kind's event branch (:775-781) moved, not copied;
  - `questions.act_kind`, `coverage._kind_of` (:429-436) and `classes._conflict_kind` (:495-505) call it;
  - `coverage.py:1519` keys a relation conflict over an OTHER act `conflict:other`.
- Pinning tests:
  - (i) for an act whose kind is silent, unresolved, doubted, contradicted, negated, supported, or a clip supported for
    hemostasis, each beside a broad denial and with its own status contradicted: every key from
    `coverage.Reader.conflicts`, `act_witnesses`, the bundling verdict and classes' witnesses equals
    `conflict:<established_kind>`;
  - (ii) g3c's shapes 2-4 through the renderer's calls name "another act" or "the bleeding control";
  - (iii) a population property;
  - (iv) mutants: `_kind_of`'s claimed read, the pair branch, classes' read.
- When: before the ten-pair test.

**B10 - G3-02, G3-03, G3-11 (D285, ruling A).**
- Change: `engine/combination.py`.
  - `_one_session` (:1208-1220) counts beside the held session only a session that one of its own filed events
    establishes as performed today (session supported, done, not digital), and whose own established examinations do
    not establish it not done today (not_done_today's first arm, one derivation).
  - `not_done_today` (:1427-1442) keeps its second arm, which also reads a kept unlisted act or doubt of kind
    examination or none carded to S.
  - Docstrings :26-29, :82-86, :452-455, :1209-1215, :1237-1243 and :1428-1440 restated.
  - Built in one commit with A2 4.3.3 c's `_claims_session` change.
- Pinning tests:
  - refute-r4d-r1's count_probe shapes hold under every single 9.4 weakening;
  - ndt_count_probe's 72 scenes hold where the letter holds;
  - count_contradictory's shapes hold as filed, and their releasing weakenings are pinned under a P-MONO name with
    Q-UNNAMED;
  - pair_probe's 24 pairs and pair_probe_colon's 4 give one outcome per pair;
  - mono_probe 0 whole-side releases;
  - two sessions established performed today keep Q-UNNAMED;
  - the test_combination pins g3a lists are restated.
- When: before the ten-pair test.

**B11 - G4-02 (D285).**
- Change: `tests/v2/test_combination.py` after :3480 adds the q_ndt row "an examination negated in it, not established"
  (`unres(X2, state=State.NEGATED)`): X2 stays established not done. The row pins the whole side; under ruling A.1 the
  count no longer reads `_claims_session`.
- Pinning test: the row itself. Mutant MA (the condition dropped) fails it (g4's MAf).
- When: before the ten-pair test, landing with or before B10 and A2 4.3.3 c.

**B12 - G3-12 (D286).**
- Change: `engine/combination.py` `base_included` (:1290-1317) / `addon_acts` (:1279). The base rules (b) and (c) read
  no act - filed with its kind supported, or a kept unlisted entry by its named kind - of a kind that a counted add-on
  code of the same session covers and that no non-add-on code of the session's family covers. Without the add-on counted,
  as built. Docstrings restated, citing that this amends D268's narrowing.
- Pinning tests:
  - refute-r4d-r1's addon_synthetic inputs (43260 READY; 43273 READY in (a) and (b), held statement_scope in (c));
  - g3a's four controls held;
  - AddOnCodes' two "E* without the act" rows restated;
  - an overlay pin: with 43273 rejected, 43260 held;
  - **a catalogue test**: every kind an add-on of a family with base codes covers is covered by no non-add-on code of
    that family (today em_prolonged and cholangioscopy), so a catalogue change fails the gate.
- When: before the ten-pair test.

**B13 - G3-13 (D286, ruling F).**
- Change: `engine/coverage.py:2207` adds `or not including.done`; docstring :2204-2205.
- Pinning tests: refute-r4b-r1's c3_completeness grid and c3_told_by_nothing (the EGD's no_proposal item listed,
  completeness incomplete); c3_counted_eus's weakened row; the done-whole control unchanged; a generated pin over the
  four states.
- When: before the ten-pair test.

**B14 - G3-14 (D286).**
- Change:
  - `engine/combination.py:1492` and `:1522` read an empty part_of_session slot that a doubt names by its readings;
  - `engine/coverage.py:1882` compares `other == stated.value or other in stated.options` (an A2 4.3.3 claimed-value
    read, routed by F3's list);
  - G3-13's done-whole filter never applies to this set.
- Pinning tests:
  - test_coverage's claim-form test gains "an empty slot, a doubt naming X2" (both modules X2; base_within holds 43235)
    and V9R4B1-2's input (both none);
  - the generated D227 agreement includes doubted-empty claims;
  - test_combination base_within over the empty-slot claim equals the unresolved claim.
- When: before the ten-pair test.

**B15 - G1-01, F3's half (D283).**
- Change: `engine/assess.py:1742` records an answer to `_COMPETING_FACT` as NOT_APPLIED, as the date's. Docstrings
  :106-107 restated.
- Pinning tests: test_assess's four pins of the record's why restated to `not_applied` (g1/DRAFT.md section 10).
- When: before the install.

**B16 - G1-02, G1-03, F3's half (D283).**
- Change: `engine/assess.py` `_bind_in_passes` (:1873-1898) and `_apply_answers` (:1723-1777), as one function read
  time calls.
  - In each pass, the ADDON count leaves out every code an engine-read answer excluded, and every primary an
    overlay-bound answer of either value binds (accumulated).
  - The competition leaves out every code an overlay-bound "Not documented" binds in that pass (recomputed).
  - A code whose ADDON row moves is read again, and its answer binds only the item it then presents; one that no longer
    binds is recorded `no_longer_asked`.
  - Docstrings :54-55, :107-108, :1785-1786 and :1876-1886 restated.
- Pinning tests: listed under F6's B16.
- When: before the install.

**B18 - G3-16 (D283).**
- Change: `engine/assess.py` `_close_services` (:1925-1926). A service answer carrying the first service question's
  fingerprint of its (family, fact) closes every service question of that key.
- Pinning tests: test_assess's `test_each_service_answer_closes_the_question_it_was_given_to` restated as g3b's
  `scratch/fix_g316_test.py`; test_review_binding ServiceQuestionTests gains 5b's two-EGD scene.
- When: before the install.

**B22 - G2-03, F3's half (D289).**
- Change: `contract/claims.py:144-146`, the CLAIM_BOUND comment, restated as g2 writes it: the dormant Gemini path's
  bound, never recomputed.
- Test: none (a grep of `32,768` names only the first build or the dormant path).
- When: before the install.

**B23 - G3-04 (D288).**
- Change: `tests/v2/test_properties.py:42-45` and `:1212-1215` describe the class `_clean_row_release` accepts, with the
  order-twin reason.
- Test: the census `DRAWN_RELEASES` unchanged, the module green.
- When: before the install.

**B24 - G4-01 (D290).**
- Change: `tests/v2/test_questions.py` after :662-663 and :1121 asserts `fill.unlisted_what is UnlistedWhat.DOUBT` at
  assess and at read time.
- Pinning test: mutant X5 fails it (g4's X5f, 3 failures).
- When: before the install.

**B25 - G4-03 (D290).**
- Change: the docstring of `tests/v2/test_coverage.py:4091-4093` names its 16 done rows.
- Test: none (a docstring).
- When: before the install.

**B26 - G4-04 (D290).**
- Change: `tests/v2/test_assess.py` after :2198 asserts
  `AS._KEY_BOUND_FACTS == frozenset(RQ.fact_key(f) for f in RQ.KEY_BOUND)`.
- Pinning test: mutants KR and KV fail it.
- When: before the install.

**B29 - G4-07 (D290).**
- Change: the comments at `tests/v2/test_properties.py:1436-1438` and `:1598-1601` say what :2124-2127 says.
- Test: mutant MOQ fails as recorded.
- When: before the install, with F3's generator change.

**B30 - G4-08 (D290).**
- Change: `tests/v2/test_properties.py:2210-2211` swapped (the routed list asserted before `OPEN_RELEASES == ()`).
- Pinning test: MOQ2's failure names `43249 under deleted E1 target.places[0]`.
- When: before the ten-pair test, with F3's slot rule and generator change.

## F6

**B7 - G3-15, F6's half (D284).**
- Change: `interpretation/overlay.py` adds ADDON to TEXT_FREE (:207-210). `item_slots` gives
  `Slots(code=, codes=engine_assess.primaries(code), family=)`; the live question carries its message. An ADDON hold read
  time recomputes is `recomputed`, never `stale`.
- Pinning test: test_overlay D268AddonTests (43260 rejected: the view's questions carry the ADDON question, `recomputed`
  names coding_rule:ADDON, `stale` empty).
- When: before the ten-pair test.

**B15 - G1-01, F6's half (D283).**
- Change: `studio/review.py` `answer_states` (:406-457). On an events-reader assessment, a standing answer to
  `COMPETING_FACT` leaves `bound` and is listed `not_applied`.
- Pinning tests: test_review_binding - "Not documented" and "Cannot confirm" to a competing question, as asked and with
  no fingerprint: none bound, each `not_applied`, effective_view equal to the record; a rejection of 43233 then releases
  43249. Mutant: the answer bound again.
- When: before the install.

**B16 - G1-02, G1-03, F6's half (D283, with C7's and C8's corrections).**
- Change:
  - `overlay.review_view`'s answer loop (:1333-1372) calls F3's function with the standing answers, so its passes apply
    B16's rule - including reading again a code whose ADDON row moves - instead of letting a bound answer stand;
  - `recount` (:860) reads the codes assess left out of the ADDON count, derived from the stored record by one
    function. `_recount_or_none` (:1238-1249), `readers.py:323` and every test caller read it
    (tests/v2/test_overlay.py:209, :1526; tests/v2/test_jobs.py:364, :936; tests/v2/test_readers.py:211;
    tests/v2/test_assess.py:1966);
  - `_unchecked` (:802-809) gives {COMPETING, ADDON} for a code the engine excluded and {COMPETING} for a taken code;
  - texts :25-27, :53-58, :803-808 and :942-945 restated.
- Pinning tests:
  - refute-5a-r1's overlay fuzz through the build's seam harness, with G3-32's widening: 0 RecordMismatch, 0 "read before
    vs with differs", no "view differs from the record" of G1-03's class (today, on g1's prototype: 4 before/with, and 12
    RecordMismatch without the derived set - `judge/logs/f10c-g1all-2mod.json`, `f10b-g1all-2mod.json`);
  - named scenes S1-S4; test_gate6's 99417/99215 separate_em scene; test_combination's 99215 base_included scene; C7's
    office visit with prolonged time and a same-day flexible sigmoidoscopy, "Not documented" to both separate_em items;
  - test_overlay `W9rCombinationTests.test_i2_...` restated (99417 stored with its ADDON item, in the competition with
    99214, read time equal);
  - AnswerPassTests: the passes end on every answer combination of em_chain, office_prolonged and C7's scene.
  - Mutants: the freeze restored (the out-set accumulated); read time's bound answer left standing (C7's scene fails); a
    recount caller without the derived set (RecordMismatch).
- When: before the install; landed with F3's B16 in one integration step, through the seam check.

**B17 - G1-04 (D283).**
- Change: `studio/review.py` `_actions` (:685-697) and `_allowed` (:780-797). A rival named by a counted code's open
  competing question offers REJECT (REVOKE once decided), though detail unavailable.
- Pinning tests: egd_dilation with "Cannot confirm" to 43249's technique - `allowed_actions(43249)` is [reject], the
  rejection is accepted, 43213 then ready; controls "Not documented" and an unnamed detail-unavailable code give [].
  Mutant: `named_rival` ignored.
- When: before the install.

**B19 - G3-17 (D283, with RS-4's and C5's correction).**
- Change: one helper in `interpretation/overlay.py` beside `assessed_out` (:824) names every answer assess read: the
  competition's overlay-bound "Not documented", and B16's overlay-bound answer of either value on a primary. It is the
  same derivation as B16's recount reads. `studio/review.py` `_reads_a_withdrawn_answer` (:1721-1733) returns True when
  one of them no longer stands.
- Pinning tests: a SimpleTestCase over records (the readings and the controls: asked differently, no longer asked, an
  unbound "Cannot confirm", the answer standing); a pipeline test in test_review_binding (a key-bound "Not documented",
  then one read for the ADDON row, revoked with the recompute stopped: STALE_ANSWER_BLOCKER, gone after the recompute).
- When: before the install.

**B20 - G3-32 (D283).**
- Change: `interpretation/overlay.py:226`. `_RECOMPUTED` holds every cause in `_RULE_IDS` (base, within, competing,
  same-day, ADDON); docstrings :222-225 and :886-888 state the one rule.
- Pinning tests: `tests/v2/test_overlay.py:1500-1526` gains a tampered base, base-within and same-day hold, each a
  RecordMismatch; mutant: the two-cause set restored.
- When: before the ten-pair test (before the build's seam check, which it makes able to see F3's combination readers).

**B27 - G4-05 (D290).**
- Change: `tests/v2/test_review_binding.py` after :297 asserts the AGAIN still live, no 45385 row in
  `answers.details_needed` and `answers.earlier_answers == []`.
- Pinning test: mutant V8 fails it.
- When: before the install.

**B28 - G4-06 (D290).**
- Change: `studio/review.py:469`, the docstring "One query.".
- Test: none.
- When: before the install.

## F0 (the integration owner)

**B16 - the seam harness (D283).** Its recount reads B16's derived set, and the named scenes join it. This is before
the build's seam check.

**B21 - G2-01 (i) and (ii), F0's half (D289).**
- Change:
  - `cptstudio/settings.py`: A2 1.12's rows (1,320 / 1,320 / 1,380; the per-kind stale threshold read by F6).
  - Landed with F6's per-kind threshold in `mark_stale` and `_check_loop_time`, never before.
  - In the same commit, the guards: `tests/v2/test_adapter.py` TimeoutTests, `tests/v2/test_types.py` SettingsTests and
    `tests/test_interpretation_adapter.py` ConfiguredTests. The adapter's own constants keep their pins; the settings are
    pinned to 1.12's literals; the guard is `fable_adapter.MAX_TOKENS / 100 + 40 <= SEND_DEADLINE`, read timeout ≤
    deadline, stage ≥ deadline + recording + 45, stale > stage; the `32_768 / 82.4` lines go.
- Pinning test: the guard itself, shown to fail on a planted `MAX_TOKENS = 140_000` and a planted deadline of 1,319
  (applied and restored, sha256 printed).
- When: before the ten-pair test.

**B22 - G2-03, F0's half (D289).**
- Change: `cptstudio/settings.py:198-218`, the timeout comments, restated with 1.12's derivation in the same commit as
  B21.
- When: with B21.

**B31 - G4-09 (D290).**
- Change: `tests/v2_documents.py:13-16` says DocumentTests reads none of 7c8's SNARE and BIOPSY and reads ec5's VISIT.
- Test: none.
- When: before the install.

**B32 - G4-10 (D290).**
- Change: `tests/test_readers_dispatch.py:401-403` becomes q02's R1 text.
- Test: none.
- When: before the install.

**B33 - G4-12, with G2-04's texts (D289, D290).**
- Change: one edit of `HARNESS.md:4739-4742`. The twelve SYNTHETIC-SLIP fixtures are hand-written and labelled
  gemini-4-argon (D274), and the trial and FRESH recordings were answered by it. v1's read accepts the models v1's
  requests have named, v2's MODEL alone.
  `tests/test_interpretation_replay.py:8-10` restated likewise. adapter.py is not edited (A2 9).
- Test: test_harness2_r2_parity's HARNESS.md reader green.
- When: before the install.

## F8

**B21 - G2-01 (i), F8's half.**
- Change: `ops/test_install_harness.py` StopTimeoutTests, with `STOP_SECONDS['worker']` 1,500, assert
  `STOP_SECONDS['worker'] > JOB_DEADLINE_SECONDS[kind]`.
- When: before the ten-pair test.

## T (tools)

**B21 - G2-01 (iii).**
- Change: `tools/v2/record_v2.py` reports, per pair's batch, the slowest output rate, the longest inter-event gap and the
  bytes per output token.
  - A slowest rate below 110 tok/s re-derives the send deadline at 128,000 tokens at 80% of that rate plus 40 s, with the
    stage, stale, stop and queue rows.
  - 128,000 times the bytes per token above 16 MiB raises the cap.
  - Either breach stops the sends until the re-derived rows are built and the gate is green.
- When: before the first pair.

**The replay counts (D291).**
- Change: `tools/v2/replay_v2.py` counts, over every recorded batch with a complete pass 2, each status, item and
  sentence a FIX moves, and the D277-moved measurements (condition 5 above).
- When: before the install; each FIX's own replay proof is part of its build.
