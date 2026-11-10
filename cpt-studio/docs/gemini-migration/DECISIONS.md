# Integration owner's decisions for the Gemini migration (session 30a58364, 2026-11-09 ~08:30Z)

These answer the 22 open questions of the code map (`understand-synthesis.json`) within the owner's directive. They are recorded as
the session's interpretation, not as owner rulings. They are constraints for the design; a design may argue against one with
evidence, and such an argument comes back to the owner of these decisions.

- **D1 Stage placement.**
  - New job kind `interpret` (<= 10 chars), queued by `extract` in place of `analyze`'s legacy reading.
  - The chain: extract -> interpret (Gemini) -> analyze -> predict (Corti) -> astra -> fable -> assess #1 -> astra_peer ->
    fable_peer -> assess #2.
    - analyze now only derives the context and routing records from the inventory: bounded, no network, no legacy reader.
  - The interpret request carries the revision text only: no member values, no filename, no participant output. It therefore
    cannot depend on the member-date hold, and it precedes it; the hold is decided in analyze from the inventory's documented
    date and the member's value.
- **D2 Corti's date.** The member's entered date if any, else the inventory's VERIFIED date of service; with neither, Corti's
  request carries no date. Request hashes change for new revisions only; legacy encounters are not re-processed silently.
- **D3 Other context facts** (setting, billing_context, patient_status) come from member-entered values only on the new path. With
  none entered, the existing "not documented" handling applies. Gemini does not read them in v1. Measure any new question this
  causes.
- **D4 Mention gate.** Replaced by a non-semantic size bound (characters and pages of the revision text), with a clear refusal.
- **D5 Exclusion safety.**
  - A code is EXCLUDED (not done, another time, another performer, planned) only by an inventory event whose status, time or
    performer attribute is anchored in its own located passage and passes the deterministic checks.
  - Anything unverified becomes a focused QUESTION on the dependent code, never an exclusion, and never READY.
  - A reviewer can still reinstate, as today.
- **D6 Persistence.**
  - A new `EventInventory` table (ImmutableModel): revision FK, interpretation version, Gemini ProviderRun FK, normalized events
    JSON, encounter facts, open questions, verification report, sha256. Unique per (revision, interpretation version,
    provider run).
  - A nullable `Assessment.event_inventory` FK, set at insert.
  - The new path still writes an `EncounterContext` (`gemini-context@1`) and a `RoutingRun` (`gemini-routing@1`), DERIVED from the
    inventory, because the foreign keys are NOT NULL.
  - `Assessment.services` holds a legacy-shaped record the old image can read without error and that creates no hold in it;
    rollback is proven by a runtime test.
- **D7 Re-assessment of legacy encounters.**
  - It happens only on an explicit act: an answer, a context save that re-checks, an addendum, Resume, or reconcile.
  - Decisions carry by fingerprint as today. Where fingerprints differ, the existing invalidation records the reason "the
    interpretation changed".
  - Member answers re-bind by question fingerprint as today, and otherwise become ASKED_DIFFERENTLY / NO_LONGER_ASKED, as stated.
  - Nothing is re-assessed by the install.
- **D8 Saves never call Gemini.**
  - A context or answer save re-applies member values onto the FROZEN interpretation, in the worker, with no new request.
  - A new Gemini request is made only for a new revision (upload, addendum), or by an explicit retry after a recorded FAILED or
    reconciled-unknown attempt.
- **D9 Peer requests.** `_cpt_studio_reading` is derived from the new-path assess #1 rows, its shape `{open_questions, held,
  excluded}` unchanged. It is labelled neutrally as CPT Studio's reading after the first assessment, which may be wrong.
- **D10 Second review.** The member-asked bounded Corti second review stays. Its eligible items are the new path's held codes
  with an open focused question, with no routing agreement. Its excerpt comes from the events' anchors.
- **D11 Failures.**
  - A Gemini authentication or permission error (401/403), or a quota exhaustion (429 with a QuotaFailure), sets a persisted
    installation-wide INTERPRETER HOLD. While it stands, no Gemini request is sent: the stage records not_sent with the reason,
    and the encounter says plainly that interpretation is paused.
  - An operator clears the hold with a recorded command.
  - An unknown outcome blocks the encounter, as today, and is reconciled through the existing reconcile flow, extended for the
    interpret purpose.
  - Any other definite failure (5xx, 429 rate) fails that attempt; a member or operator can explicitly retry (a recorded action).
    There is no automatic retry and no fallback to the legacy reader.
- **D12 Exchange.** One exchange, no tools; the extracted text only (the PDF original is NOT sent in v1, recorded as a limit).
  Timeouts as for the participants: connect 10 s, read 300 s, send deadline 330 s, under the existing watched-socket discipline
  and the installation-wide send lock.
- **D13 Model.** `gemini-4-argon` is a code constant. The response's modelVersion must equal it exactly, or the answer is refused
  and never read. finishReason must be STOP. The JSON is read strictly and validated locally against the production schema
  (the OpenAPI-subset responseSchema is a hint, not trusted).
- **D14 The credential.** Root 0600, 69 bytes, one line `GEMINI_API_KEY=<53 chars>`, no export prefix, no quotes (shape probed
  2026-11-09; no value read). The installer copies it unread to /etc/cpt-studio/gemini.env (10150:10150 0400) and mounts it
  read-only in the WORKER ONLY. The key travels only in the x-goog-api-key header, never in a URL.
- **D15 Rollback depth.** To the installed `cpt-studio:c2e53f8e7d33`. A runtime test runs that image (web, worker, RECOMPUTE_STATES,
  list, detail, reports) against a migrated database that holds new-path records, before the install.
- **D16 phase_reassess** is not run for this install.
- **D17 Imports versus calls.** Importing studio.gi is not calling it. The rule is execution:
  - On the new path NO studio.gi function executes except the reference tables (`gi.profiles`, `gi.catalogue` constants and
    pure lookups), and none of the semantic validation functions the map lists (`semantic_to_replace`) execute either.
  - Proven by a runtime call guard in tests on every path: assess FIRST, FINAL and AGAIN, answer recompute, context save, review
    view, decision save, reload (customer_state and list), export (approved, draft and operator), and peer request.
- **D18 I1 (Corti-only parity)** is retired for the new path, superseded by the owner's directive; legacy assessments keep their
  records.
- **D19 Dormant confirmations** stay dormant behind STUDIO_OFFER_CONFIRMATIONS=False, and the new path never uses them.
- **D20 E/M and other GI.** Gemini's event schema includes a separately documented evaluation-and-management service and other GI
  procedures as event procedures. E/M readiness comes from those events, with no cue readers.
- **D21 procedure_day** (same-day E/M rules) is fed by the inventory's current-encounter procedure events.
- **D22 Operator evidence.**
  - Every new-path assessment records the interpretation version, the inventory id and the Gemini run.
  - A production legacy-call sentinel counts calls into the legacy semantic entry points made during new-path work, and the
    count is recorded on the assessment's operator record.
  - A management command reports, for a window: Gemini runs (state, model, usage, cost), assessments by engine version, the
    interpreter hold and the sentinel totals.
  - Customer screens and downloads never name a provider or model (denylist extended with gemini, google and the model id;
    never bare "argon", which is GI vocabulary).

## Integration owner's decisions during S15-S17 (2026-11-10, session 30a58364)

- **D23 The S15 narrower scope (FINAL 14.6).** Mechanics test classes run on the production chain with recorded synthetic
  interpretations; reading-outcome classes stay on the test-only legacy chain, where they are the regression suite for
  legacy records, the rollback image and the migration (FINAL 14.6's own split). S15 switched 84 classes. Its 12
  "test structure only" leftovers are being moved by a bounded agent. The other 272 classes (S15's triage: reading-specific
  documents with no recorded interpretation, reading-dependent outcomes, legacy records, the legacy engine) are ACCEPTED on
  the legacy chain. Their per-class list is runs/s15-uncovered-legacy-chain-classes.tsv. The new path's reading outcomes are
  measured by FRESH, g1 and the walks, never by an authored interpretation standing in for Gemini's.
- **D24 One act verified to a lesion and one act naming none, in one passage (S03's open question).** They stay separate acts
  (Gemini's '' reads as 'not tied to that lesion'), as S03 pinned. The separate-lesion modifier review is offered only
  between acts on verified, distinct lesions (combination.modifier_review), so the pair is never offered 59/XS on an
  unverified distinctness. NCCI edits remain unchecked and the customer screen says so. Reported to the owner as an open
  product question; FRESH and g1 measure it.
- **D25 The D4 size bound (C9) is set from the measured output, not C9's literal formula.** The literal formula, 24,000 divided
  by the p99 of output tokens per input character, is dominated by the short inputs' fixed output, about 2,000 tokens
  of encounter facts and schema. On FRESH that p99 is about 4.4 tokens per character. The bound would then be about 5,400
  characters and would refuse Note #8 and every long live document. C9's intent is that an answer stays well inside
  maxOutputTokens (32,768). So the bound is the largest length whose predicted output stays at or under the budget,
  predicted as intercept + slope x characters plus the p99 residual, fitted on FRESH-A/B/C. Measured inputs: the live
  documents' text lengths, from the read-only dump of 2026-11-10T08:25Z (86 texts; max 19,398; none over 21,000).
- **D26 Hand-offs checked in code (cf0b76e20).** S10's KNOWN_ERRORS sentences were added. S07's reuse-door, sentinel and
  worker-mode hand-offs were already met. confirm_finding's trip re-record is not reachable: confirmations are off in this
  release.
- **D27-D30 The S16 false-READY repairs (2026-11-10).** Every false READY found is repaired in the new architecture, never
  waived (FINAL 5.7). The four found on FRESH-A and FRESH-B (the frozen recordings, re-read with no resend) are all
  code-definition gaps the legacy engine shared. Each is repaired by a structural rule over verified structure and the
  catalogue, never a passage word list (EB4), and never by a change to studio/gi (the S12 legacy manifest).
  - **D27 Defining kinds (FINAL 7.3).** D(C) is C's covers minus every kind that another code of its family covers alone.
    When D(C) is non-empty and smaller than the covers, C is matched only by a supporting event whose kind is in D(C).
    Otherwise it takes the not-documented hold (7.6). Found: fb13 43265 READY on a balloon extraction. Computed table:
    43265 lithotripsy; the EUS FNA, drainage and injection codes their sampling act; 44365 hot_biopsy; 49440 peg.
  - **D28 The EUS examination class (R6).** A code with catalogue exam 'full' needs the session's EUS examination
    reach verified at or beyond the duodenum (duodenum, bulb, second portion, ampulla, jejunum). A code with 'limited'
    needs it verified short of the duodenum. An unverified reach, or a class that does not fit, holds; it never
    excludes. Found: fb12 43238 READY beside 43242, on an echoendoscope advanced to the second portion of the duodenum.
  - **D29 The dilation site (R4).** The site-specific dilation codes, by their CPT descriptors: esophageal 43213, 43214,
    43220, 43226, 43233, 43248, 43249; gastric or duodenal 43245. Each is supported only by a dilation whose target
    landmark is verified, directly or through its verified lesion, in that class. A verified target outside the class
    does not support. An unverified or ambiguous target (an anastomosis) holds. Found: fb07 43249 READY on a
    gastrojejunal anastomotic stricture.
  - **D30 Procedural adjuncts (7.7).** An ablation or a bleeding control that is verifiably part_of a current, performed
    removal (snare, emr, esd, hot_biopsy), or that is on that removal's verified lesion, is bundled into it. It is
    included in the removal and never reported alone (CPT: control of bleeding the procedure causes; the EMR's adjunct
    coagulation). Found: note8 r1 45388 READY on the snare-tip soft coagulation that Gemini verified as part_of the EMR.
- **D25 (measured, 2026-11-10T09:15Z).** On all 179 FRESH answers: output tokens (with thoughts) = 2,173 + 1.081 x
  input characters, residual p99 3,593. The 14 runs at 19,398-19,460 characters gave 21,201-25,036 output tokens, at
  most 76% of maxOutputTokens 32,768. C9's literal formula (p99 ratio 6.45) gives 3,722 characters and would refuse
  about a tenth of live documents (live median 2,354, p90 3,810). **INTERPRET_MAX_CHARS = 20,000**: the edge of the
  measured range, where fit plus p99 residual predicts 27,378 tokens (84% of the cap). It refuses 0 of the 86 live
  texts (maximum 19,398). INTERPRET_MAX_PAGES stays 40. An answer cut off at the cap is refused as too long (C5).
- **D31 A Gemini open question on a session's examination holds that session (S16, FRESH-C PAR-006 r3 and PAR-008 r1).**
  "Both done by her previous gastroenterologist." covers the EGD and the colonoscopy. In every run Gemini kept the
  EGD acts at the documenting team and raised its doubt as an open question. The question was about performer in two
  runs and 'other' in one; it named the examination event and not the biopsies. So 43239 went READY in 2 of 4 runs.
  Performer, time and status are properties of the session: an open question about performer, time, status or 'other'
  that names a session's examination event holds every code that session supports, asking that question. An
  act-level question (kind, target, technique) holds its own act only, as today. This is Gemini's own expressed doubt,
  read structurally; it is not a word list.
- **D32 The reader's bounds refuse ordinary long reports (S16, FRESH-C).** Four answers were refused whole:
  lesions[i].passages listed 9, 10 and 13 ids (bound 8), and one open question listed 18 events (bound 16). All four
  are the 19.4k-character Note #8 variants. Raise those bounds to what a 20,000-character report needs, as long as the
  bounds are not part of the request (no re-recording). They exist to refuse pathological answers, not long documents.
- **D33 The prompt asks for the framing sentence (S16 round 3, 2026-11-10).** EB4's residual appeared on FRESH-C: Gemini
  gave acts told in a reproduced or earlier narrative no time words, so they took the default current time. The
  narrative is framed before ("...outside reports are reproduced.") or after ("...findings at her index colonoscopy.").
  These acts were masked as holds by unrelated false-unverified attributes, so the hold repairs would have made them
  false READY. The time and performer lines now ask that such a framing sentence be given as the words of every act
  in the part it frames; the examples are neutral and appear in no corpus. INTERPRETATION_VERSION stays @1, because
  nothing has been recorded by the product (FINAL 5.2). The FRESH corpora are recorded again under the new
  instructions (FRESH-2). FRESH-1 is kept as evidence.
- **D34 An anastomosis takes the place its own anatomy entry states (S16 round 3).** The landmark 'anastomosis' has no
  place in the landmark order. So a dilation of the anastomotic stricture can never be placed apart from a lesion at a
  verified site, or inside a D29 site class. Note #8's 45386 is held in every run as 'possibly the polyp' that a dilation
  denial names, and fb07's 43245 is held. Rule: when the encounter's verified anatomy lists exactly one anastomosis,
  and that entry's own words name its type with a literal place word, an act whose verified target landmark is
  'anastomosis' takes that place (for comparisons and D29 only). The type lexicon: ileocolonic/ileocolic -> right
  colon side; colorectal/coloanal/ileorectal -> rectum; gastrojejunal -> stomach side (gastric/duodenal class);
  esophagojejunal/esophagogastric -> esophagus side. Several anastomoses, no type word, or an unknown type keep today's
  ambiguity and hold. EB1-compatible: literal place words in the anatomy entry's own words, never a passage scan.
- **Round 3 scope is FINAL for the engine.** Apply the two held-back patches (the procedure from a heading found at
  several places; the hot-snare device words) and D34; measure on FRESH-1 and on FRESH-2. Whatever remains after this
  round is reported, not tuned further before install.
- **FRESH-2 (2026-11-10T11:13-12:01Z, D33 prompt):** 179/179 answered and read, $12.17; frozen at 12:01:40-43Z
  (FREEZE-A 1e204684, FREEZE-B e6d0fb27, FREEZE-C 269f883e). Scored on e0f92d62f (the round-2 engine), score dir
  fresh2-score/f2base: A 93/9/0, B 177/15/0, C 150 correct / 30 false hold / 6 false READY, 0 false exclusion. The six
  false READY fall into two classes, repaired by D35 and D36.
- **D35 A current time whose own words name another occasion is unverified (EB1).** In aside-of-twins-023 r1 and r2,
  Gemini cites "At the original procedure" as the acts' time words and gives current_encounter; 43239 went READY.
  Evidence binding checks that Gemini's own words state Gemini's own value. A time of current_encounter whose own words
  carry an earlier or future marker (the C1 lexicon, plus "original") is unverified: a time question, never an
  exclusion. This narrows EB3's "markers never touch the READY path". The marker is read only in the attribute's own
  words, and only where those words contradict its value; it never scans a passage.
- **D36 A reach stated only through another act's site is unverified.** In W1S-399 r1 and W1S-112 r1, Gemini gives the
  colonoscopy reach from a biopsy or finding sentence ("Biopsies of the ascending colon were taken"). The examination's
  extent is never stated ("advanced under direct vision"), the registry rules that the extent must be asked, and four
  codes went READY. A reach entry is verified only when one of its passages belongs to its examination event or to no
  act of the session. A reach cited only from passages of other acts is inferred from where they were done and is
  unverified (reason reach_inferred): R6 asks the extent. This is a structural binding check over Gemini's passages,
  not a word list.
- **Round 3 results (2026-11-10, agent):** ed0af2756 applies the two held-back repairs: the procedure cited from a heading
  passage found at several places, and the hot-snare device words. c336b0690 adds D34. On FRESH-2 at c336b0690:
  A 96/6/0, B 180/12/0, C 170/7/9 (correct / false hold / false READY), 0 false exclusion. The 9 false READY are
  D35 x2, D36 x4, and W1S-075, -076, -171 r1 43239, which the heading repair unmasks. In those three, Gemini reads the
  whole note as today's despite "Her outside reports are reproduced.", and D33 did not change that.
- **D37 The heading repair is withdrawn; the trade goes to the owner.** The installed release HOLDS W1S-075, -076, -171
  (and -193) 43239, and the registry expects NOT_READY. By the owner's rule of 2026-11-09 (registry REGISTRY.md), a
  candidate that turns an exact input from held to READY against the expected outcome has a REGRESSION, and a material
  one disqualifies. So the procedure half of ed0af2756 (place-independent verification of a procedure cited from a
  repeated passage) is reverted. 11 false holds of 43239 on the registry's "EGD heading" family remain, and are
  reported with the patch ready. Fixing those headings exposes Gemini's reading of an ambiguous "reproduced reports"
  sentence, which arguably refers to the outside ERCP reports; accepting that is the owner's decision. The hot-snare
  half stays: its one blocked case, C2MEM-032 r1, is fixed by D33 on FRESH-2.
- **D38 A colonoscopy reach short of the cecum with no stated incompleteness asks the extent (2026-11-10).** This
  closes the last FRESH-2 false READY, W1S-112 r1 45385, whose reach Gemini took from a finding sentence. The rule
  follows CPT's colonoscopy extent (rectum to cecum, terminal ileum or small intestine beyond an anastomosis). A
  stated incomplete examination keeps its reach. On both recordings, no colonoscopy code expected READY sits on such a
  reach. FRESH-2 after D38: A 96/6/0, B 180/12/0, C 168/18/0, zero false exclusion.
- **D39 A 429 with no QuotaFailure is a quota HOLD, not a rate limit (2026-11-10, measured live; amends P-4).** The
  Gemini project's monthly spending cap was reached between 13:53:20Z (the last 200) and 13:56:33Z (the first 429).
  From then on Google answered every request with HTTP 429 RESOURCE_EXHAUSTED, the message "Your project has exceeded
  its monthly spending cap...", and no QuotaFailure, ErrorInfo or RetryInfo. P-4 read a 429 with no violations as a
  per-attempt rate limit (FAILED), so the candidate 2fe6efe89 kept sending, once per new upload. That made 23 refused
  sends across three g1 test databases (1 + 11 + 11), against the directive: "Authentication/quota failures must stop
  requests." Amended rule: a 429 (or RESOURCE_EXHAUSTED) is FAILED only when it has at least one violation and every
  violation is a per-minute, paid-tier quota with a stated limit above 0. With NO violation it is a HOLD (quota),
  with its own operator wording. This covers a spending cap, an empty or non-JSON body, and an unnamed quota. The trade
  is accepted: a bare transient 429 now needs an operator's release instead of a retry. Pins:
  - the adapter test: 6 bodies, including the recorded message;
  - the holds-table row;
  - a pipeline test: the hold is set, and the next upload, in another workspace, sends nothing.
  Mutation proof (the old arm restored, in a private copy): 9 assertions fail across the 3 pins.
  Consequence for S17: g1 runs 2 and 3 are VOID (in each, 1 of 12 documents was interpreted), and run 1 is complete
  but for g1c4 (refused). S17's Gemini cost on the test instance: walk $0.5736 (10 sends), g1 r1 $1.2414 (12 sent,
  11 priced), r2 $0.1110 and r3 $0.1102 (12 sent, 1 priced each); $2.0362 in all (in-image interpretation_report,
  published rates, an upper bound).
- **D40 Two codes for one act compete whoever proposed them (2026-11-10; S17 refutation finding 5; amends FINAL 7.9).**
  FINAL 7.9 copied harness repair 3's P-ADMIT2, which held two codes on one act only when one was a participant's. The
  installed engine's completion repair (2026-11-06) replaced that rule: two codes for one documented act compete
  whoever proposed them. So Corti's own 43249 + 43233 for one dilation (and 43239 + 43202 for one biopsy) were both
  READY on the new path where the installed release holds both: held turned to READY on the exact input, a
  regression under the owner's rule. combination.competition no longer reads the origin. Measured on c2e53f8e's
  engine: two E/M codes for one visit are held with base_included plus competing_codes, and the new path now asks the
  same. Cost on FRESH-2: B fb12 r1-r3 43242 is held, competing with 43238, the limited class sibling the scoring
  proposes for the same FNA. That is the installed doctrine (CPT Studio never chooses between two codes for one act),
  so B goes 180/12/0 -> 177/15/0. A and C are unchanged.
- **D44 An anastomosis completes a colonoscopy's reach only on the right colon side (2026-11-10; S17 refutation
  finding 9; amends D38).** D38 counted any 'anastomosis' reach as complete. A colorectal anastomosis at 12 cm, which
  D34 itself places in the rectum, made 45385 READY with 'extent reached = anastomosis', while the same exam written
  as 'rectum' asked the extent. The reach is now full only when the encounter's one anastomosis is placed on the
  right colon side (D34: ileocolonic or ileocolic). A colorectal, coloanal or ileorectal anastomosis, or one with no
  type word, asks the extent (fail-closed; an ileorectal one, arguably complete, is asked too). On FRESH-2 it is
  exercised by the 3 v6 colonoscopies, whose anastomosis D34 places on the right colon: no change.
- **D41 A removal's adjunct is asked unless something verified sets it apart (2026-11-10; S17 refutation finding 6;
  completes D30).** D30 bundled an ablation or bleeding control into a removal only through a verified part_of or the
  removal's verified lesion. With the link missing, a hemoclip on the polypectomy site's oozing, or snare-tip soft
  coagulation of an EMR's margins, made 45382 or 45388 READY beside the removal code. The relations step now records a
  procedural_adjunct bundling identity for such an adjunct beside a current performed removal of its session. R5 asks
  it (act_target), never READY, unless incompatible verified places, two distinct verified lesions, or a verified
  part_of naming another act set it apart. Not a regression (the installed release shares the gap). FRESH-2: no
  change (all 56 recorded adjuncts beside a removal carry a verified part_of).
- **D42 A worded current time must be anchored to this encounter (2026-11-10; S17 refutation finding 7; completes
  D35).** D35's list is one a word must be ABSENT from, so every other-occasion wording it lacked ('At the index
  procedure', 'At that procedure', 'At her first colonoscopy', 'Back then', 'over the summer') left the time current.
  Fail-closed inversion: a current_encounter time whose own words carry no date literal is verified only if they hold
  an anchor of this encounter (lexicon.CURRENT_ANCHORS: today, this, present, current, now, same, date of service; or
  PROCEDURE_PHASES: on withdrawal, on insertion, retroflexion). Otherwise it is unverified (current_unanchored): a time
  question, never an exclusion. A current time with no words stays Gemini's reading. D35's markers stay, and stand
  alone where found. Census of every recorded current time: FRESH-2 1,079 events, 860 with no words, 19 distinct
  texts; FRESH-1 991, 872, 17. Left unanchored: "index colonoscopy", "over the summer", "initially", "then", and a bare
  "findings". Cost on FRESH-2: C/PAIR-5-W3 r1 45385 is now asked the date, because its "initially/then" is a sequence
  within the procedure. "Initially" can also open another occasion, so it stays unsafe, and C goes 168/18 ->
  167/19. The committed replay pins move on exactly two recordings (PAIR-5-W3 r1: 2 times unverified; W1S-316 r1:
  1), checked by regenerating every fixture into scratch: only MANIFEST.json's sha changed.
- **D43 The lower-tract EUS codes take the class of their endoscopy (2026-11-10; S17 refutation finding 8).** The
  catalogue gave 45341, 45342, 45391, 45392, 44406 and 44407 no class. So 45392 was READY on an upper EUS-FNA through
  the duodenum (fb12's recorded answers) and on a rectal EUS that reached the rectosigmoid. They now read the EUS
  session's verified reach as D28 reads the upper classes:
  - sigmoidoscopic: rectum to the descending colon;
  - colonoscopic: beyond the splenic flexure, to the cecum or ileum;
  - stoma: a colonic reach plus the encounter's verified stoma.
  The splenic flexure fits neither. A misfit is held with the class question, never excluded. A full upper
  examination stated incomplete no longer fits the full class, whatever its reach (finding 8 a, in the reading where
  Gemini states the limit as the completion; legacy holds that input). FRESH-2: no change.
- **D45 An ERCP sphincterotomy or dilation is part of a stent placement or exchange in its duct (2026-11-10; S17
  refutation finding 10).** 43274 and 43276 include "sphincterotomy, when performed" and pre- and post-dilation, but
  43262 was READY beside 43274 for one biliary duct. coverage.bundled_reason now bundles an ERCP sphincterotomy or
  dilation beside a current performed ERCP stent placement or exchange of its session (stent_included): R5's
  "part of another documented act" hold, never READY alone. Both ducts verified and different (a biliary
  sphincterotomy beside a pancreatic stent) keep it separate. A duct not verified on either act, or the ampulla, which
  opens on both, never sets them apart. The stent code alone no longer leaves the sphincterotomy as an open act. Not a
  regression (installed shares the gap). FRESH-2: no change (no recording pairs them).
- **D48 The words bound is one passage's, 600 characters (2026-11-10; S17 refutation finding 18; amends contract
  3.3).** D33 asks Gemini for the whole framing sentence as the time and performer words. A 343-character framing
  sentence passed the 300 bound and refused the whole answer: no codes, and a paid retry of the same request. A words
  value is located in its passage, so its bound is now passage_chars' 600 (the longest measured is 189, across
  FRESH-2's 15,949 words values). BOUNDS is never sent, so no recording or replay key changes. The BOUNDS pin beside
  gemini-events@1 moves, and the label stays @1 because nothing is recorded under it in production.
- **D49 The interpreter's read timeout is 480 s and its send deadline 510 s (2026-11-10; S17 refutation finding 19;
  amends D12).** A unary answer arrives whole, so the read timeout bounds its generation. At 300 s, two things
  timed out:
  - a cut-off answer (32,768 tokens at the slowest measured 82.4 tok/s, about 398 s);
  - D25's p99 STOP answer at the size bound (about 332 s).
  Both were recorded UNKNOWN (an operator's reconcile and a paid resend) instead of TOO_LONG, or instead of being
  read. The interpreter now has its own setting, INTERPRETER_READ_TIMEOUT_SECONDS 480; until now it read the
  participants' 300. The send deadline is 510 and the interpret stage 560. These keep D12's margins: 30 s over the
  read, 15 s of recording plus 35 s of stage work, and 40 s before the 600 s stale sweep, which the worker's 600 s stop
  timeout outlasts (now asserted in ops/test_install_harness). Cost: a stuck request holds the worker up to 510 s.
- **D50 No decision but a revoke on a record this release cannot read (2026-11-10; S17 refutation finding 15;
  enforces FINAL 8.1).** An unreadable new-path event coding (a version this release does not read, as after a
  rollback from a later release) put UNREADABLE_EVENTS_BLOCKER on readiness: "cannot be approved or exported until
  it is assessed again". Yet the code still offered and accepted approve and reject (201), and the draft listed it as
  Approved. review._allowed now asks the same reader as readiness (readers.EventReader.unreadable). While a new-path
  record cannot be read, it allows only a revoke of a decision already taken, so a reviewer can always take one back.
  No approve, reject, confirm or reinstate. Residual, recorded: a decision taken BEFORE the record became unreadable
  still shows in the draft, as the decision record it is.
- **D51 A switch-back refuses only on what its target would mishandle (2026-11-10; the S17 rollback test D15
  assertion 5; S17 refutation findings 13 and 14).** The hazard read refuses an undo while records exist that an
  older revision would act on, or show, wrongly. It reads them as the oldest revision, 057a7d39, would, whatever the
  target. On live-shaped data (cptg_d15: 86 legacy encounters from the live dump plus the walk) it named 24 encounters
  (participant 18, member_answer 7, modifier 2). 23 of them are legacy encounters that c2e53f8e itself wrote and reads.
  So the switch-back back to c2e53f8e refused whatever this revision had done, and so would any switch-back since the
  harness (a pre-existing limit D15 made visible). For a switch-back the check is now target-aware:
  - a reason the previous revision reads is dropped: participants when its worker runs astra or fable, the second
    review reasons when it runs review2, member_answer and modifier when its models read them (TARGET_MODEL_READS,
    run in its image; measured on cpt-studio:c2e53f8e7d33: both);
  - an encounter with no record created since this revision's pair was created is dropped (touched_since:
    creations, answers, revocations and reconciliations only).
  The 24 drop to 0 for c2e53f8e. A new reason, 'reinstatement' (finding 13; SHOWN), names a reviewer's reinstatement
  on a new-path assessment: c2e53f8e's overlay adds no base-rule hold for it, so its readiness and export would bill
  45378 beside 45386. It refuses until revoked, whatever the target. The interpretation note is read again at B7, once
  this revision's web is stopped (finding 14). rollback-app and the app phase's undo keep the conservative read.
  ops/rollback_check.py applies the same filter (raw and filtered both recorded).
- **D52 An operator's reconciliation survives a retry release (2026-11-10; S17 refutation finding 0).** FINAL 11.3
  writes a retry release on the released run's reconciled_by, reconciled_at and reconciliation_note. A run an operator
  had reconciled (an unknown outcome that P-6 then settled from its exchange, its reading refused) lost who, when and
  the note on a member's retry, and those columns are their only copy (the audit trail keeps no note text by design).
  The release now writes those columns only on a run with no reconciliation. On a reconciled run the release is the
  retry stage queued for it in the same transaction (its key, 'retry:<run>'), which released_for_retry now reads too.
- **D53 A hold an unsettled answer sets is recorded before the next send (2026-11-10; S17 refutation finding 16).** A
  run whose own bytes classify as a HOLD (a substituted model, a refused key, an exhausted quota) set no hold when its
  stage ended before settling it: the reading child was killed, or the worker died between the outcome and the settle.
  The next document's stage, or the member's retry, then sent again. Right before any interpret stage sends (after
  every door, all of which send nothing), the hold of every sent interpretation run that no stage settled (no effect
  on its scope) and that classifies as a HOLD is recorded (holds.record: one per answer). If a hold then stands, the
  send stops, paused. Nothing is read or marked: the owning stage, or the stale sweep's settled path, still settles
  its run.
- **S17 refutation triage, the findings recorded and not repaired in this round (2026-11-10).** Each was reproduced
  by its verifier. None turns a held code READY against the installed release.
  - #11 (medium): the balloon-diameter and esophagoscopy-extent sibling codes are READY when the proposer picks the
    wrong sibling (43233 on an 18 mm dilation, 43202 on duodenal biopsies, 43239 on an esophagoscopy to the GE
    junction). The installed release shares it; ACCURACY-RESIDUALS.md:1411-1412 already records it.
  - #1 (low): a member's date of service saved on a legacy revision is shown as entered by the uploader (attribution
    only; the value is right).
  - #2 and #3 (low): D35's list, and the ported procedure-name list, hold some current acts Gemini read correctly
    (false holds).
  - #12 (low): D36 reads a denial sharing the reach's sentence as the reach's source, so a stated reach is asked
    (false hold).
  - #17 (low): P-6 settles only on the keyed after-reconcile stage; a retry or context save after that stage was
    stopped pays for the request again.
  - #20 (low): a cut-off answer caused by a thinking runaway on a short document is told 'too long to be read in one
    piece', and the member's retry is refused (an operator's override remains).
  - #4: not a defect.
  - #14 is repaired in D51.
