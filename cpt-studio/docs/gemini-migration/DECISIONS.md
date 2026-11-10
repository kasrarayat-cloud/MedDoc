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
- **S17 refutation round 2 (wf_20a87b6f-e16, 2026-11-10; 5 lenses over 2fe6efe89..cad5637b7): 20 findings, 18
  confirmed.** Repaired as D54-D61. Recorded and not repaired:
  - #2 and #6: a sibling the per-code rule held (D29's site, D27's not documented) does not compete with its rival
    for the act, so the rival is READY where c2e53f8e holds both with competing_codes. The READY code is the one the
    document supports in every demonstrated input (43249 on an 18 mm esophageal balloon dilation; 43264 on a balloon
    extraction without lithotripsy). FRESH-B grades them correct, and the misfit sibling stays held with its own
    question. By the registry's categories (false READY, exclusion, dropped question, wrong act, against the
    expected outcome) this is a correction, not a regression.
  - #18: a per-minute rate limit that Google names only in ErrorInfo becomes an installation-wide quota hold under
    D39: a fail-closed false hold an operator releases, accepted as D39's cost.
  - #17 and #19: not defects (their verifiers refuted them).
  The full suite on cad5637b7 also failed the guard matrix: TARGET_MODEL_READS and TOUCHED_SINCE_READ, D51's new
  in-image scripts, were not driven by tests/guard_support.py's in_image. They now are, with their answers asserted.
- **D54 A worded current time is verified only by whole present-encounter frames or a date at day precision
  (2026-11-10; round-2 refutation findings 0, 7 and 8; amends D42).** D42 verified a current time when an anchor WORD
  stood anywhere in its words ("this", "these", "same", "currently", a procedure's phase), or when the words held any
  date literal. So when Gemini called an index colonoscopy's act current, 45385 went READY with any of these words:
  "These were the findings at her index colonoscopy", "At her index colonoscopy this spring", "At her first colonoscopy
  the same", "At the index procedure, on withdrawal", "At her index colonoscopy in November 2026". On each exact input
  the installed release holds the code (needs_clarification, performed_status) or excludes it as historical (the
  "History:" lines). That is held turned to READY.
  - The rule. A current_encounter time given words is unverified (current_unanchored: a time question, never an
    exclusion) unless one of three things holds:
    - the words carry a date at day precision, and the date check decides (equal, or date_mismatch);
    - they carry a D35 marker, and other_occasion stands alone, as before;
    - they are made only of whole present-encounter frames. lexicon.current_frame folds the words, strips the
      punctuation and whitespace at their edges, and splits them at commas, semicolons and a standalone "and". It
      needs at least one part, and every part must equal a CURRENT_FRAMES entry.
  - CURRENT_FRAMES is the census of every current time FRESH-1 and FRESH-2 recorded:
    - the frozen answers: 1,099 + 1,079 current times, 136 + 219 of them worded, 24 distinct texts;
    - each recorded present-encounter wording, exactly as recorded: today; during the present encounter; during (and
      occurred during) the single date of service stated at the top of this report; this examination; at this
      examination; this time; this time as well; on this occasion; same session; on withdrawal;
    - eight obvious exact frames: this procedure; at this procedure; during this procedure; during this examination;
      at the present encounter; on the date of service; this morning; this afternoon.
    - D42's CURRENT_ANCHORS, PROCEDURE_PHASES and current_anchors are removed. The check name current_anchor, the reason
      and the @1 labels are unchanged (nothing is recorded under them in production; D33, D48).
  - A year or a month no longer anchors. "November 2026" alone is now unanchored: its two D42-era pins moved, the
    literal-precision pass test and the EB3 test.
    - A year or month that differs from the service date gives date_mismatch AND current_unanchored.
    - current_unanchored never depends on the service date. A member may supply that date after normalization, and
      time_state recomputes only the date reasons.
    - With no document date, D42 verified "At her index colonoscopy in 2025" outright, and it stayed verified when a
      member supplied a 2025 date. D54 leaves it unanchored whatever date is supplied.
  - Cost measured.
    - FRESH-2 re-scored on the repair (f2d54): A 96/6, B 177/15, C 167/19 plus 4 dropped_question and 2 safe_hold. This
      equals f2r1f: 0 of 486 rows, 0 of 179 runs and 0 of 358 inventory and assessment files differ.
    - FRESH-1 scored on e6f41f4f7 and on the repair: identical (0 of 486 rows, 0 of 179 runs, 0 of 358 files).
    - The census's other wordings were already unanchored under D42 ("Those were the findings at her index
      colonoscopy.", "Over the summer", "initially", "then", "FINDINGS"), are dated at day precision, or are D35's.
    - The replay pins, regenerated from f2d54, are byte-identical to the committed MANIFEST.json and FREEZE.sha256:
      none move.
    - One committed test outside this repair's files moves: tests/test_interpretation_slips.py:136. It pins the
      synthetic s1-e5 current time worded "in January 2024" as ['date_mismatch'], and D54 adds current_unanchored. The
      state is the same (unverified), and 45378 stays READY on the current examination
      (tests/test_interpretation_cases.py passes). Its one-line update is offered separately.
    - The fallback test's unlocated time words moved from "today SYNTHETIC-MODEL-TEXT-S02", which D54 now denies, to
      the frame "during this procedure".
  - Residual, recorded (EB4); D54 cannot close it.
    - Gemini misreads another occasion's act as current and gives no words, or gives words that are themselves a
      present-encounter frame (a reproduced report's own "on withdrawal" or "this examination"). That act reads READY.
    - It is recorded on FRESH-2. In aside-of-twins-023 r1 and r2, the biopsies inside the reproduced "original
      procedure" narrative carry the words "On withdrawal" and verify as current. 43239 is held there only by the
      extent question, exactly as under D42.
    - A date at day precision that equals the service date anchors, whatever else the words say. On an 11/09/2026
      service, "These were the findings at her index colonoscopy, faxed to us on 11/09/2026" verifies.
    - Finding 8's own control shows the same arm. The line is "History: At her index colonoscopy on 11/09/2026, a 12 mm
      sessile polyp in the ascending colon was removed with a hot snare." The words are "At her index colonoscopy on
      11/09/2026", on an 11/09/2026 service.
      - 45385 is READY under D42 and under D54.
      - The installed release EXCLUDES it as historical: excluded turned to READY.
    - Measured alternative, not built: a day-precision date anchors only when the words left once its dates (and a
      dangling "on") are removed are empty or whole frames. On FRESH-2 it changes 0 rows. It changes one inventory,
      aside-of-twins-019 r1: the three times worded "Summary of the upper endoscopy of 2026-09-30 for the referring
      physician." become unverified. They were already opened by an open question. That moves one committed replay
      pin. It would close this control.
    - The installed reader's section heuristics held some of these: finding 7's "History:" lines are EXCLUDED as
      historical. The owner's directive keeps the legacy reader off the new path, so the residual is measured, never
      patched with a passage word list.
  - Pins.
    - tests.test_interpretation_verify: test_d54_words_that_are_not_whole_frames_leave_a_current_time_unverified,
      test_d54_a_year_or_a_month_compares_and_anchors_nothing, test_d54_whole_frames_and_a_date_at_day_precision_verify
      and test_d54_d35_marker_stands_alone_where_found.
    - tests.test_interpretation_lexicon: test_d54_the_whole_frames_of_this_encounter (the tuple) and
      test_d54_current_frame_reads_the_words_whole.
    - tests.test_interpretation_normalize: test_d54_unbound_current_time_words_that_are_not_whole_frames_deny_the_default
      and test_d54_located_current_time_words_that_are_not_whole_frames_leave_it_unverified.
  - Mutation proof (each mutant in its own private copy; each applied exactly once and confirmed):
    - M1, the change undone: 7 of 8 pins fail. The D35 pin guards a behaviour D54 keeps; M8 fails it.
    - M2, D42's anchor-word test restored: 3 fail.
    - M3, any date literal anchoring: 3.
    - M4, any part a frame: 4.
    - M5, a frame inside a part: 3.
    - M6, a vacuous all() over no parts: 2.
    - M7, edges not stripped: 2.
    - M8, the D35 marker no longer standing alone: 1.
    - M9, "this spring" added as a frame: 3.
  - Each pin, and the mutants that fail it:
    - not_whole_frames: M1, M2, M4, M5, M6, M9.
    - year_or_a_month: M1, M3.
    - whole_frames_and_a_date: M1, M7.
    - d35_marker_stands_alone: M8.
    - the tuple: M1, M9.
    - current_frame_reads_the_words_whole: M1, M4, M5, M6, M7, M9.
    - unbound words: M1 to M5.
    - located words: M1 to M4.

- **D55 A code D27 narrows competes for every act its covers name (2026-11-10; the round-2 refutation, finding 1;
  completes D27 and D40).** D27 narrowed what MATCHES 43265 (its lithotripsy), and the narrowing also reached what the
  competition read: D40 compares E* sets, and 43265's E* was its lithotripsy alone. So 43264 (the balloon extraction)
  and 43265 (the lithotripsy) proposed for one stone clearance never intersected, and both were READY. The installed
  release holds both with competing_codes, because its competition reads the catalogue covers, and 43265 covers the
  extraction. The competition call in assess.py now passes each counted code's CLAIMS (assess._claims): its E*, plus,
  for a matched code that D27 narrows (CodeLink.defining non-empty, E* non-empty), every current performed event
  (coverage.current_performed) of its own family of a kind in its acts beside its defining kinds. Only 43265 (the stone
  extraction), 44365 (the ablation) and 49440 (the tube placement) gain claims; the EUS codes' acts are their defining
  kinds. A code the per-code rule held has an empty E* and claims nothing. So 43265 held not documented leaves 43264
  READY (D27's own test), and the competition of held codes is unchanged (findings 2 and 6, recorded as not
  regressions). E*, support['acts'], the coverage reconciliation and combination.competition are unchanged. The D27 pin
  that asserted both codes READY (test_the_lithotripsy_code_with_its_lithotripsy_is_ready) is replaced by the D55 pin.
  Cost on FRESH-2: no row changes. fb13 r1-r3 propose both codes, but 43265 is held not documented there.
  - Pins: tests/test_interpretation_events.py DefiningKinds.test_d55_* (four: the shared ERCP fixture; finding 1's own
    input, with Astra and Fable read and proposing nothing; 44365 beside 44369; 49440 beside 49441), and
    tests/test_interpretation_combination.py Competition.test_d55_* (the three-code table, and _claims on matched, held
    and earlier acts).
  - Mutation proof: with the call site restored to E*, the 4 behaviour pins fail (6 assertion failures); with _claims
    reduced to E*, all 5 D55 tests fail (7).
- **D56 A doubted 'incomplete' completion never fits the full EUS class (2026-11-10; the round-2 refutation, finding 3;
  completes D43).** D43 read the completion through _stated_incomplete, which is true only when the completion is
  usable. A confident 'incomplete' held 43259. The same 'incomplete' left unverified (words that do not bind) or
  opened (Gemini's own completion question) fitted the full class, so 43259 was READY on "The examination was
  incomplete: the esophagus and the stomach were not examined." The installed release holds that input. In
  _examination_class a FULL-class code now does not fit when its session examination's completion has the value
  'incomplete' in ANY state: verified, unverified or opened (fail-closed, _said_incomplete). The question keeps D43's
  "stated to be incomplete" form. The limited and lower-tract classes still read their reach only, and D38's reach rule
  keeps the verified predicate.
  - Cost on FRESH-2: no change. Its 4 'incomplete' completions are all verified, and none is on a full EUS code.
  - Pin: tests/test_interpretation_assess.py
    ExaminationClass.test_d56_a_doubted_or_unbound_incomplete_completion_holds_the_full_class_code. It covers five
    unbinding shapes (opened with and without passages, words not in their passage, words cited elsewhere, no words),
    each run with and without the participants.
  - Mutation proof: with the verified-only predicate restored, all 10 subtests fail.
- **D57 An anastomosis reach reads its own words (2026-11-10; the round-2 refutation, findings 4 and 9; completes
  D44).** D44 placed the reach only by the encounter's anatomy entry. A history of a right hemicolectomy (one ileocolic
  anastomosis entry) and a sigmoid colectomy, with "The colonoscope was advanced to the colorectal anastomosis at 15
  cm.", made 45385 READY with "extent reached = anastomosis". The installed release asks the extent. D34's
  compared_landmark already refuses that place for an act whose own words name another type.
  _full_colonoscopy_reach now takes the extent record and applies the same own-words guard: an 'anastomosis' reach is
  full only when the one anastomosis is placed on the right colon side (D44), and also when its own words name no
  anastomosis type of another place (lexicon.anastomosis_type_places) and no plural "anastomoses"
  (lexicon.ANASTOMOSES). The guard reads only literal type words in the reach's own words (EB1). The case needs Gemini
  to list only the ileocolic anastomosis; a faithful answer lists both, the place is then '', and the extent was
  already asked.
  - Cost on FRESH-2: no change. Its 3 colonoscopy anastomosis reaches (v6 r1-r3) name the ileocolic anastomosis
    their anatomy lists.
  - Pin: tests/test_interpretation_assess.py
    ColonoscopyReach.test_d57_a_reach_whose_own_words_name_the_other_anastomosis_asks_the_extent. It covers findings 4
    and 9 verbatim, a coloanal reach and "both anastomoses", with controls for an ileocolic reach and an untyped reach.
  - Mutation proof: with D44's anatomy-only reading restored, the 4 asked cases fail.
- **D61 A session stated incomplete through its completion carries the 52/53 consideration (2026-11-10; the round-2
  refutation, finding 10; ADJUDICATION R-4 and C-9).** On FRESH-2 Gemini states an examination's incompleteness only
  through the reach's completion: 4 answers (A/v6 r2, B/fb07 r1-r3, all verified), and the round-2 verifier found none
  through attempted_not_completed among 354 examinations. The 52/53 consideration and the service.incomplete warn
  were tied to the attempted status alone. So on "The examination was incomplete because of poor preparation." the
  READY 45385 and the held 45378 carried neither.
  The installed release gives both codes both. Now every code of a session whose examination's completion is VERIFIED
  'incomplete' carries both signals, each once (_incomplete_session), whatever the code's own state:
  - the service.incomplete warn (wording.incomplete_check), worded from the completion's own words;
  - the consideration (wording.incomplete_consideration), the installed release's sentence.
  An excluded code carries neither. Status, READY and held never change: a warn and a consideration only. On finding
  10's exact text the considerations equal the installed engine's, string for string (transverse and cecum reaches,
  measured on c2e53f8e with the harness reference). The check quotes Gemini's completion words, where the installed
  release quotes its cue sentence. On FRESH-2 those words are whole sentences ("The gastroscope could not be passed
  through the stricture."); in the synthetic fixture they are "incomplete".
  - Cost on FRESH-2 (f2asm against f2r1f): the summary is unchanged. 14 of 486 rows gain only a service.incomplete
    warn: v6 r2 (45378, 45386) and fb07 r1-r3 (43235, 43245, 43248, 43249). No status, question or verdict moves.
  - Pins: tests/test_interpretation_assess.py IncompleteCompletion (four tests). They cover finding 10's text with and
    without Astra; a cecum reach; the base code of an examination also stated attempted (its one check and one
    consideration), an act code, a held code and an excluded code; and controls (a completion that does not bind; an
    incomplete upper examination beside a complete colonoscopy).
  - Mutation proof: with the session's completion no longer read, all 4 tests fail (5 failures).
  - Residual, for the owner: an examination stated attempted_not_completed, with no completion, still gives the
    consideration to its base code only (FINAL 7.3). On finding 10's cecum text, read that way, 45385 is READY with
    neither signal, while installed gives both codes both.

- **D58 A removal's adjunct is set apart only by what verifiably separates it (2026-11-10; S17 refutation round 2,
  finding 5; narrows D41).** D41 asked an ablation or a bleeding control beside a removal of its session unless
  incompatible verified places, two distinct verified lesions or a verified part_of naming another act set it apart.
  Two of those let a polypectomy site's own hemostasis go READY: 45382 beside 45385 on a rectosigmoid polyp whose clip
  line says "the polypectomy site in the distal sigmoid colon" (lexicon.compatible reads the two as different places),
  on a hepatic flexure polyp with the clip in the proximal transverse colon, and on a clip whose part_of names the
  colonoscopy (normalize verifies a part_of only as naming an event that exists). c2e53f8e READYs all three, so this
  repairs a false READY, not a regression. relations.identity_in_doubt's procedural_adjunct arm now sets the adjunct
  apart:
  - by a verified part_of only when it names an ACT (names_an_act): an event whose catalogue kind is neither an
    examination (the session, ADJUDICATION C-1) nor an umbrella, read as every consumer reads one (FINAL 7.3 line 1:
    its kind usable). An 'other' event (no catalogue kind) or one whose kind is not usable is not established as one;
  - by places only when every pair is verifiably apart (adjunct_apart): both on one of the tract's two chains
    (TRACT_POSITION: the anal canal to the terminal ileum, with the appendiceal orifice and the ileocecal valve at the
    cecum; the proximal esophagus to the second portion of the duodenum), not compatible, and not ADJACENT (one step
    apart). A place on no chain never sets it apart: a region, the ampulla, an organ beside the tract, and an
    anastomosis, even one D34 places (that place is the anatomy entry's words, not the act's).
  The adjacency is this arm's alone. lexicon.compatible, the pairing table and the other bundling rules are unchanged.
  Cost: an adjunct that names no lesion and no act, one step from the removal or at a place on no chain, is now asked
  even when it is a separate act. D30's standalone-ablation control (angioectasias in the ascending colon beside a cecal
  EMR) goes from READY to act_target. That control now sits in the transverse colon, and the ascending-colon input is
  pinned as the cost. FRESH-2 (f2d58 against f2r1f): 0 of 486 rows and 0 of 179 inventories change. All 56 recorded
  adjunct-removal pairs carry a verified part_of naming an EMR (28 the removal itself, 28 the EMR beside a second
  removal), none names an examination, and no procedural_adjunct relation is recorded before or after. The replay pins
  do not move. Pins:
  - finding 5's three variants (45382 asked, act_target);
  - the cost, and an anastomosis, raw and D34-placed;
  - the chain table, adjacent pairs on both chains, places on no chain, every pair apart;
  - a part_of naming the examination, an umbrella, an 'other' event or an event whose kind is not verified;
  - controls kept: D41's ascending-colon diverticulum beside the sigmoid polypectomy (READY), a part_of naming a
    biopsy, and places two steps apart (READY).
  Mutation proof (9 private copies): with relations.py restored, all 10 pins fail and no control does. Each arm's own
  mutant (the place arm, the part_of arm, the D34 guard, any pair, no adjacency, places off the chains, an 'other'
  event as an act, an unverified kind as an act) fails only that arm's pins. Recorded, not repaired: a part_of naming
  an act that is itself part of the removal still sets the adjunct apart. Hemostatic clips part_of an epinephrine
  injection that names nothing (the injection is asked), or part_of closure clips, leave 45382 READY, as before D58.

- **D59 A switch-back's reinstatement guard holds through the approval, and its since is when this revision replaced
  the target (2026-11-10; S17 refutation round 2, findings 11, 12, 13 and 14; amends D51).** Four changes, one
  guard:
  - Finding 11. D51's 'reinstatement' read only a current REINSTATE decision. Approving the reinstated code, the
    normal end of a reinstatement, replaced it, so the reason cleared and switch-back and rollback-app refused nothing.
    On those rows c2e53f8e readied and exported 45378 beside 45385. In variant (b), with the base left undecided, it
    offered the base's approve, and one click billed both. The reason now names a new-path assessment while any code
    stands reinstated as the review overlay counts one: review.reinstated_codes (current decision REINSTATE or
    APPROVE), read where the image has it, else the same rule over the current decisions. Only a revoke of that code
    (or a reject of the reinstatement) clears it. Legacy assessments are untouched (is_new_assessment gates it).
  - Finding 12. The touched filter's since was the current containers' creation, while the target came from the
    newest successful app receipt. A later app of this same revision installed a pair and then failed (its recompute,
    or its access check: the pair stays installed). That moved the since past a standing reinstatement, and the
    switch-back went on. The since is now the earliest time that same receipt records for its phase
    (replaced_since: main's started_at). With none recorded, it falls back to the earliest of this revision's
    containers and of every later app receipt of this revision (fail-closed). The B4 and B7 closes keep their own
    since. The receipt records `touched_since`.
  - Finding 14. B7 now reads the interpretation note again before its close may refuse. A receipt stopped at B7,
    with the previous web serving and its worker held, carries B7's count, with B4's kept as `interpretation_at_b4`.
  - Finding 13. The limit is stated in INSTALL.md (Switching back) and in the note. The previous revision reads a
    new-path assessment through a stub that adds no base hold, so a reinstatement made THERE can leave the diagnostic
    base approvable beside the therapeutic code. Re-check each new-path encounter on the previous web (a context save
    reads it again) before reviewing it there. INTERPRETATION_MADE names, as `reinstatable`, the new-path encounters
    whose current assessment holds an excluded, reinstatable code. The key is given only when there is one, so the
    answer is as it was otherwise. The note counts them. Never a refusal (P-1).
  - Cost, measured. 13 of 13 real app receipts (/home/claude/cpt-studio-install-20261023) carry started_at, so the
    fallback never fires on them. On the 8 blue/green ones (24c49a50 to c2e53f8e), started_at precedes S1 (the
    incoming web's creation) by 14.4-17.4 s. The touched filter now reaches that much earlier, into a window where
    only the previous pair serves. A record it writes there for a reason it does not read (unknown, outcome, conflict)
    is now named: fail-closed, more refusals, never fewer. The guard matrix runs every in-image script under the
    sentinel. On 173e83336 (which drives the two D51 reads) with this patch, test_guard_matrix_new_path,
    test_guard_mutation and SwitchBackHazardTests pass, 25 of 25.
  - Pins. No existing test's expectation changed. BlueGreenWorld gained an opt-in answer to TOUCHED_SINCE_READ by
    record time, and its default is as before. The ops suite went from 631 to 639 tests; test_readers_dispatch with
    test_cux_undo went from 47 to 51.
    - ops/test_install_bluegreen.py SwitchBackSinceTests: finding 12's sequence through the real install.main, plus
      the since read at every check and the fallback.
    - SwitchBackCountTests: the B7 count, and a switch-back that states the limit and proceeds.
    - ExposedNoteTests: the note, and a malformed list not counted.
    - InstallDocTests (d59).
    - tests/test_readers_dispatch.py SwitchBackHazardTests: finding 11's variants (a) and (b), the reject boundary, the
      no-hasattr arm, and INTERPRETATION_MADE on real rows.
    - Mutation proof, ten private copies, each differing from the work copy in one file: every one of the 12 D59 pins
      fails under the copy that undoes its change and passes on the work copy. The D51 pins pass in all eleven.
  - Residual, to the owner. A switch-back refused at B7, followed by `app` to come back, gives a newer successful
    receipt naming the same target. Its started_at becomes the since, so a reinstatement written under the earlier
    pair is dropped again, and the switch-back completes. Reproduced on this patch in a scratch probe. Closing it means
    taking the earliest app receipt that names that target since this revision's last successful switch-back. A B7
    close that raises, rather than refuses, still leaves B4's count only.

- **D60 Only a retry that released a run is read as a release (2026-11-10; the round-2 refutation of cad5637b7,
  finding 15; amends D52).** D52 read any interpret stage keyed 'retry:<run>' as a release of that run's answer. But
  every retry is keyed that way, including one that releases nothing. The case is a usable answer whose reading failed
  on this server: the reading child overran or was killed, or the write gate refused. retry_target never releases that
  answer, because it stays reusable (FINAL 6.3, Read). Under D52 it still read as released, so the stored-answer door
  skipped it and the request was paid for again: by the retry or, if the retry was stopped, by the next upload of the
  same text in the workspace. Now:
  - The retry that releases a run an operator reconciled (D52's branch, which keeps the operator's record) is keyed
    'retry-release:<run>'. That key is 113 characters, or 157 with a Resume's suffix, inside the column's 200.
  - released_for_retry reads only that key.
  - Every other retry keeps 'retry:<run>', which is never a release. A Resume of it is not a release either.
  - Measured on synthetic probes, cad5637b7 -> the repair:
    - overrun, then a retry: 2 sends -> 1 (reused);
    - a stopped retry, then a new upload: 2 -> 1 (reused);
    - D52's own path, where an operator reconciled a usable answer, its reading overran and the console retried:
      1 send -> 0;
    - D52's sequence, a reconciled answer whose reading was refused and then a retry: 2 -> 2, with the operator's
      note kept.
  - The other key readers need no change:
    - a repeated retry's existence check and resume read whole keys;
    - keyed_interpretation_run and _settled_path read other marks;
    - ':retry:' never matches ':retry-release:';
    - the API and console doors parse no key.
  - Cost:
    - A stage that the D52 build (cad5637b7..e6f41f4f7, never installed in production) keyed 'retry:<run>' for a
      reconciled run is no longer a release. Measured: it stops at the failed-before door with nothing sent, and the
      next retry releases the run under the new key. This fails closed.
    - A run D52 already released can be retried again after its 'retry-release' stage was stopped before it ran. That
      retry writes nothing and is keyed 'retry:<run>'; the release stands on the first stage's key.
  - Pins:
    - test_pipeline_interpret UnreadAnswerRetryTests (3 tests): the retry, a stopped retry then a new upload, and a
      Resume of the retry.
    - test_pipeline_interpret ReconciledRetryTests: D52's pin, which now asserts the key 'retry-release:<run>', and
      test_d60_a_reconciled_runs_release_is_its_retry_release_stage_and_lets_one_attempt_send.
    - test_retry_reading_api UnreadAnswerRetryTests (2 tests): the member's door, and the console on D52's path.
    - Mutation proof in private copies: jobs.py as at e6f41f4f7 fails all 7 pins; the reader alone reverted fails 7;
      the writer alone reverted fails the 2 D52-path pins.
- **D53b A hold kept only in an unsettled run's exchange is recorded before the next send (2026-11-10; the round-2
  refutation of cad5637b7, finding 16; completes D53).** D53's scan read only runs with a definite outcome, and
  classified each from the run's own bytes. Two shapes keep the answer only in the run's recorded turn-1 exchange:
  - decision (k): the exchange was committed as it ended, then the run's outcome write failed, so the run is UNKNOWN
    with no bytes of its own;
  - a worker that died between the two leaves the run 'sending', marked unsent, until the stale sweep runs.

  In either shape, a substituted model's answer or the spending cap's 429 set no hold, and the next document's stage
  sent again. The scan now also reads:
  - every sent interpretation run left UNKNOWN, reconciled or not;
  - every run still 'sending' that may have reached the vendor (may_have_reached_vendor).

  It reads the run's turn-1 exchange as P-6 reads it, through _turn_one_exchange: the run's only exchange, with bytes
  that check against their sha256, answering the run's request. _settle_from_exchange now shares that reader, with its
  behaviour unchanged. An exchange recorded with an HTTP status is classified from its outcome, status and bytes by
  holds.classify, which is adapter.classify. A HOLD is recorded against the run with holds.record. A run left sending
  counts as sent, by may_have_reached_vendor's rule, for this record only. Nothing else is written: the owning stage,
  P-6 and the sweep settle the run as before, and one answer sets one hold.
  - Measured on synthetic probes, cad5637b7 -> the repair, with the next upload in another workspace:
    - decision (k) with a model answer: 2 sends -> 1, with the 'model' hold on the first run;
    - decision (k) with the cap's 429: 2 -> 1, with a 'quota' hold;
    - a dead worker's sending run before the sweep, with either answer: the next document sends -> paused, 0 sends;
    - the same after the sweep has made the run UNKNOWN: sends -> paused.
  - Cost:
    - The scan reads every UNKNOWN interpretation run on every send, and reconciled runs stay UNKNOWN for good.
      Measured queries per scan:
      - 3 with no such run (D53 alone: 1);
      - 13 with 10 unknown runs whose exchanges are no hold;
      - 4 more for each run whose exchange is a hold that is already recorded (63 with 10 of each kind).
    - A reconciled unknown outcome whose exchange is a hold now pauses its own after-reconcile stage until an
      operator releases the hold. Before, that stage sent again (measured: 2 sends -> 1).
    - An unsettled answer whose hold was never recorded sets that hold at the first send after the install. Since one
      answer sets one hold, such an answer can pause the installation once more after an operator has released
      another answer's hold. Production holds no interpretation run (c2e53f8e has no interpreter).
  - Pins, all in test_pipeline_interpret PauseTests:
    - test_d53b_a_hold_kept_only_in_an_unknown_runs_exchange_stops_the_next_send: finding 16 case A, the pin the spec
      asks for.
    - test_d53b_a_hold_kept_only_in_a_dead_workers_exchange_stops_the_next_send_before_the_sweep: case B, followed by
      the sweep and a reconciliation; one hold, nothing sent.
    - test_d53b_a_reconciled_unknown_runs_hold_pauses_its_own_after_reconcile_stage.
    - The control test_d53b_reads_an_unsettled_exchange_only_as_p6_reads_it_and_records_only_a_hold: an exchange that
      does not check, one answering another request, a replay, a usable 200 and a 503 set no hold.
  - Mutation proof:
    - the scan removed: the 3 pins fail;
    - without its sending branch, or without the in-memory sent flag: the dead-worker pin fails;
    - the UNKNOWN read narrowed to unreconciled runs: the reconciled pin fails;
    - the shared reader without its sha256 check: the control and P-6's own pin fail.

- **D62 An unverified current time is a doubt, never an absence, for the rules that hold other codes (2026-11-10;
  D54's review; structural).** coverage and relations read an event's currency only from a verified time. So
  unverifying a current time (D35, D42, D54, or words that do not bind) removed that event from every rule that holds
  OTHER codes by it. D54's reviewer measured two wrong READYs D54 created, and D42's own unanchored "then" already
  did the same:
  - an aside's examination ('These were the findings at her index colonoscopy') left today's session to the other
    examination, so 45385 was READY on the index colonoscopy's snare;
  - a removal whose time was 'During this colonoscopy' no longer bundled the biopsy of the lesion it removed, so 45380
    was READY.
  coverage.possibly_current: a current_encounter time, verified or not, unless its own words place the event
  elsewhere (date_mismatch, other_occasion: evidence, not a doubt). It now drives:
  - a session's examinations: a possibly current one beside a done one leaves the session unresolved, and is never
    the session;
  - the removal a part is bundled into (current_performed);
  - relations' bundling-identity doubts and unresolved sessions;
  - D55's claims.
  An earlier or future time stays not current, verified or not. FRESH-2: no change; replay pins unchanged. Pins:
  test_interpretation_coverage.PossiblyCurrent (3). Mutation proofs: each of the three parts fails its pin; the
  contradicted-time exclusion also fails tests.test_interpretation_cases' s1-e5 (a 2024 examination mislabelled
  current never takes today's session).
- **D63 An anastomosis reach is full only when its own words name the right colon side's type (2026-11-10; D57's
  review; fail-closed).** D57 read the reach's words as a deny list, so a bare 'anastomosis' (bound inside
  'colorectal anastomosis') or a type no list holds ('colocolonic', 'rectal anastomosis', 'anastomosis in the rectum')
  still counted as full beside an ileocolic anatomy entry. Now the reach's own words must name exactly the right
  colon side's type ('the ileocolic anastomosis'), besides the anatomy's one anastomosis being placed there, and no
  other type and no plural. Every recorded anastomosis reach names its type (FRESH-1 and FRESH-2: 6 of 6 'ileocolic
  anastomosis'): no change. Pins: test_interpretation_assess.ColonoscopyReach (the D44 rows now name their type; a
  bare reach beside an ileocolic anatomy asks), and the D57 rows. Mutation: the D57 deny-list form fails them.
- **D64 A same-day date anchors a current time only where its other words name nothing else (2026-11-10; D54's
  review).** D54 let any day-precision literal equal to the service date anchor the words around it. So 'At her index
  colonoscopy on 11/09/2026' and 'faxed to us on 11/09/2026' verified the act as current (installed: excluded as
  historical). With the literals cut out, every remaining part must be empty, a date connector ('on', 'dated', 'of',
  'as of', 'date', 'date of service') or a whole frame (lexicon.dated_frame). 'on November 8, 2026' (the census) and
  'today, 11/09/2026' still verify. Measured: FRESH-2 verdicts unchanged. One replay recording moves: C/W1-u29b-rel-p3-
  aside-of-twins-019 r1, 3 'Summary of the upper endoscopy of 2026-09-30 for the referring physician' times verified
  -> unverified, so MANIFEST.json and FREEZE.sha256 are regenerated and that is the only change. Mutation: the
  bool(day) form fails the D54 pin's two D64 rows.
- **D65 The switch-back's since is the earliest app receipt of this revision that replaced the same target
  (2026-11-10; D59's review).** D59 read the since from the newest successful app receipt. Running app again after a
  switch-back refused at B7 (the documented recovery) wrote a newer receipt naming the same target, and what this
  revision wrote under its earlier pair was then read as the target's own: a standing approved reinstatement went to
  c2e53f8e. replaced_since now also reads every earlier successful app receipt of this revision whose replaced web is
  the same revision, and takes the earliest. Pin: ops.test_install_bluegreen test_d65 (and the receipts of another
  target, a failed one and another revision's are not read). Mutation: it fails.
- **D66 A hazard answer that is not a dict refuses the switch-back (2026-11-10; the D15 re-run's verifier).**
  phase_switch_back's precheck and B4's read refused only on a non-empty answer, so None or any non-dict proceeded,
  against switch_back_hazards' own contract. Both now refuse, with nothing started or stopped. Pin: test_d66 (None,
  [], 'none', 0). Mutation: it fails.
- **D58 amended in integration (2026-11-10):** the upper tract's chain runs on to the jejunum, which an enteroscopy
  reaches. The ileum, which leads into the cecum on the lower chain, stays on no chain, so it never sets an adjunct
  apart (fail-closed). D55's enteroscopy pin moved its ablation to the gastric antrum, four steps from the jejunal
  removal.
- **The head-to-head against the installed engine (2026-11-10; the owner's question "is it much better than the old
  engine?"; tools and results in the session's gemini-migration/h2h/).** The installed tree (rjudge/tree-c2e53f8e,
  diff-verified identical to git c2e53f8e's cpt-studio) runs through the U32 registry runner (run_registry.py) on
  FRESH-A/B/C. Both engines get the same documents, the same proposals (score_fresh.proposals_for's codes and quotes)
  and the same expectations, and both are judged by run_registry.verdict INCLUDING its facts check (a READY with a
  'verify' block must sit on an act performed today by the physician, with the target, technique and extent words).
  - score_fresh never applied that check. compare.py now applies it to the new path from the matched events' own
    passages and labels, never from the proposal's citation, which is the corpus's own quote. target_not reads what
    an act is ABOUT (its label and target words). Read from every passage, it flagged 7 rows wrongly: a summary
    sentence naming both lesions is in both acts' passages.
  - ADJUDICATED: the new path's statement_scope question ("Does <the statement> apply to <the act>?") asks the
    contradiction that an expectation names as performed_status or conflict:<kind>, because the expectations use the
    installed engine's fact vocabulary. act_target never stands in for them.
  - Run 1, 234 code rows: installed 150 correct, 65 false_hold, 16 false_ready, 2 ready_wrong_facts, 1 safe_hold; new
    path 211 correct, 18 false_hold, 3 dropped_question, 2 safe_hold, no false_ready, no wrong facts.
  - The 3 dropped questions are REGRESSIONS by the owner's rule. They were counted since FRESH-1 and never adjudicated
    against it, and are repaired as D86.
  - 126 rows ran 3 times; 7 changed between runs, always between correct and false_hold.
- **S17 refutation round 3 (wf_87e54e74-274, 2026-11-10; 6 lenses over 173e83336..a4dcbea72): 21 findings, 21
  confirmed by independent verifiers (10 high, 8 medium, 3 low).** Repair workflow wf_b15fa458-ab1 builds them, with
  D86, as seven patches:
  - currency: D67 (#0) and D68 (#1, #18);
  - eus-sessions: D69-D73 (#2, #3, #4, #6, #7);
  - claims-base: D74 (#5) and D75 (#17);
  - adjuncts: D76-D79 (#8-#12);
  - families: D80 (#19) and D81 (#20);
  - ops: D82-D85 (#13-#16);
  - questions: D86.
  None are deliberately left unrepaired.
  - In the D62 class the lenses found 11 defects: 4 in D62 itself (#1/#18 the carve-out; #3 and #4 its readers) and
    the rest in rules D62 reached or should have.
  - New pre-existing gaps: time_state was never wired (#0); procedure-unverified acts never hold the base (#17);
    recognised-only families were READY on the catalogue route (#19); the same-day E/M rule was blind to gi.other
    (#20).
  - Lesson recorded with D62 ([[feedback_unverified_is_a_doubt_not_an_absence]]): carving an exception out of a
    fail-closed rule needs the same proof as the rule itself.
- **D67 A day-precision date anchors a current time only against a date, and every assess re-judges the stored times
  with the effective date (2026-11-10; the round-3 refutation of a4dcbea72, finding 0; completes D54 and D64, and
  wires contract 5.3).** With no verified, unopened date of service, normalize binds every time with no service date.
  _date_reasons then gave a current_encounter time nothing, and D54's dated arm (D64) anchored "On 03/14/2024" on the
  date alone, so the time was verified with nothing to compare it to. And verify.time_state, which contract 5.3 makes
  every assess call with the effective date ("so a member-supplied date re-judges the stored literals"), had no caller
  in production: jobs passes the frozen inventory straight to assess.
  - The finding's input. A document with no date line: 'The colonoscope was advanced to the cecum.' / 'A 4 mm polyp in
    the rectum was biopsied with cold forceps.' / 'On 03/14/2024, a 25 mm flat polyp in the cecum was resected by
    EMR.' Gemini gives the date not_stated, and the EMR (E3) the time current_encounter with the words 'On 03/14/2024'.
    The member enters 2026-11-09. 45390 on the 2024 EMR was READY. It was also READY in two variants: Gemini opens the
    document's own date line with its own question and the member settles 11/09; and 'several' dates with the member
    settling 11/09. Installed c2e53f8e EXCLUDES it as historical. With the document's own verified date, the new path
    holds it (event_time).
  - The rule.
    - (a) At normalize time, a current_encounter time whose words carry a date at day precision is unverified with
      date_unchecked while no service date is established. _date_reasons('current_encounter', day literals, None)
      gives ('date_unchecked',). date_unchecked already stood in verify.REEVALUATED, so time_state recomputes it.
      Unaffected:
      - a time anchored by whole frames, and one with no words (no literal);
      - a month or a year: it anchors nothing already (D54), so the time is current_unanchored and never date_unchecked.
    - (b) assess builds its Reading from a COPY of the inventory's event records, made once date_state is computed
      (verify.rejudged).
      - Each event's time is verify.time_state(time, date_state.value).
      - Its 'current' is recomputed from that time, as normalize._current derives it (verify.currency, pinned equal to
        normalize._current).
      - The stored inventory is never changed.
      - The member's date then decides the literals exactly as a normalized document date does: 03/14/2024 against
        2026-11-09 is date_mismatch, a time question.
      - With no effective date (none stated and none entered, or a held conflict), a day-precision current time is
        date_unchecked, whatever date normalize judged it against.
  - What each half does alone (mutation M1, M2).
    - (a) alone holds finding 0's 45390 on every member-date variant: the time stays date_unchecked. But a member's date
      EQUAL to the day can never verify it, which is a new false hold.
    - (b) alone holds 45390 too, and lets an equal date verify the time. Without (a), though, an undated assessment
      reads the dated act as verified.
  - Cost and consequences, measured.
    - FRESH-2 re-scored on the repair (f2r3-currency) against a4dcbea72 (f2int3, which a re-score of a pristine copy,
      f2r3-currency-pristine, reproduces exactly: 0 rows, 0 runs, 0 files):
      - correct / false hold: A 96/6, B 177/15, C 167/19 plus 4 dropped_question and 2 safe_hold; 0 false READY, 0
        false exclusion;
      - 0 of 486 rows and 0 of 179 runs (verification counts included) differ;
      - one inventory differs: C/W1-u29b-rel-p3-aside-of-twins-019 r1. Its 3 times worded 'Summary of the upper
        endoscopy of 2026-09-30 for the referring physician.' were already unverified (current_unanchored, D64). The
        document's date there is opened by Gemini's own question, so they gain date_unchecked
        (['date_unchecked', 'current_unanchored']). No state moves.
    - The head-to-head against installed c2e53f8e (h2h/compare.py on f2r3-currency) is identical to a4dcbea72's
      h2h.json, every key.
    - FRESH-1, scored on a pristine copy (fresh-score/f1r3-currency-pristine) and on the repair (f1r3-currency-work):
      - verdict counts identical: A 97/5, B 174/18, C 161/24 plus 4 dropped_question, 1 false_ready and 2 safe_hold,
        the same on both;
      - 1 of 486 rows changes, C/W1-u29b-rel-p3-aside-of-twins-019 r1 43239. It was expected NOT_READY and was HELD by
        the date ('several', no service date). It now also asks the extent, and stays correct;
      - why: its EGD examination's time is worded '2026-09-30'. Under (a) it is date_unchecked, so the reach is
        discarded and the session has no done examination. This is the examination-reach shape below, and on this
        document the date is unresolved anyway;
      - 1 run's verification counts change there: time 4 verified -> 3, and reach 1 verified -> 1 discarded.
    - The replay pins do not move: tests.test_interpretation_replay passes, because the manifest pins state counts and
      aside-of-twins-019 r1's counts are unchanged. No fixture was regenerated.
    - Held to EXCLUDED, member-date path only, matching the document-date path and installed. (b) also re-judges earlier
      and future times. On an undated document with the member's 2026-11-09:
      - the line is 'In 2024 a 10 mm polyp in the sigmoid colon was removed with a cold snare.', with an
        earlier_encounter time worded 'In 2024';
      - 45385 cites '10 mm polyp in the sigmoid colon was removed with a cold snare' (within the act's own words, C-10);
      - a4dcbea72 holds it (event_time: date_unchecked forever). The repair EXCLUDES it, historical, basis literal,
        reinstatable;
      - the same text with the document's own verified date is excluded on a4dcbea72 too, and installed c2e53f8e
        excludes it on the member's date.
      This is the one direction in D67 that is not only a hold, and contract 5.3 specifies it. Cited as the whole line
      (not within its words), it is asked statement_scope, as on the document-date path.
    - Excluded to held, under a held date conflict. The document states 11/09/2026 and the member enters 2026-11-10
      (conflict_differs, no effective date).
      - The 2024 removal's 45385, which a4dcbea72 excluded against the document's date, is held (event_time).
      - The same-day EMR's 45390 gains an event_time question beside the date's.
      - The safe direction: a conflict's date decides nothing until it is settled.
    - New false hold, accepted: an examination dated at day precision on an undated document. The input is 'On
      11/09/2026, the colonoscope was advanced to the cecum.' / 'A 4 mm polyp in the rectum was biopsied with cold
      forceps.', the examination's time worded 'On 11/09/2026', and the member's 2026-11-09.
      - (a) leaves the examination's time date_unchecked at normalize, so its reach is discarded (reach_not_permitted,
        normalize._attach_reach). assess re-judges the TIME, but no step re-attaches the reach.
      - So 45380 asks the extent where a4dcbea72 made it READY.
      - Installed c2e53f8e holds 45380 on this text too (performed_status, extent). Not a regression against installed.
        Not on FRESH-2; on FRESH-1 once (aside-of-twins-019 r1, on a code already held by its date).
  - Pins (tests.test_interpretation_r3_currency, new; synthetic, nothing sent):
    - test_d67_a_day_literal_with_no_service_date_anchors_nothing;
    - test_d67_whole_frames_no_words_and_a_month_or_year_are_unaffected (the control);
    - test_d67_time_state_decides_the_unchecked_day_with_the_effective_date;
    - test_d67_the_undated_documents_day_worded_current_time_is_unchecked;
    - test_d67_a_framed_or_wordless_current_time_on_the_undated_document_stays_verified (the control);
    - test_d67_control_the_documents_own_verified_date_holds_the_2024_emr;
    - test_d67_a_members_date_supplied_for_an_undated_document_holds_the_2024_emr;
    - test_d67_a_members_date_settling_geminis_own_date_question_holds_the_2024_emr;
    - test_d67_a_members_date_settling_several_dates_holds_the_2024_emr (one line and two lines);
    - test_d67_control_a_members_date_equal_to_the_day_verifies_the_time: the same-day EMR is READY with the equal date
      and held on 2026-11-10;
    - test_d67_the_stored_inventory_is_never_changed (and each copy's current follows its re-judged time);
    - test_d67_currency_is_normalizes_own_rule_and_rejudging_with_the_inventorys_date_changes_nothing: the drift guards,
      over every synthetic slip fixture and the finding's inventories;
    - the chain (D67Chain, built like tests.test_pipeline_assess_events, the legacy entry points failing if called):
      - test_d67_the_members_date_at_upload_and_saved_afterwards_holds_the_2024_emr: the date at upload, and saved
        afterwards by jobs.change_context;
      - test_d67_control_the_members_saved_date_equal_to_the_day_makes_the_same_day_emr_ready.
    - Two expectations in tests.test_interpretation_verify move (D67's own): test_a_literal_with_no_service_date
      ('on 11/09/2026' with no service date is ('date_unchecked',)) and test_a_current_encounter_date_follows_the_
      members_date (that record is stored unverified ['date_unchecked']).
  - Mutation proof. Each mutant was applied in its own private copy and confirmed applied by its marker and sha256;
    the counts are the runner's failures over the 28 pin tests (a failing subtest counts once).
    - M1, (a) undone: 9 failures (the verify, normalize, stored, control and chain pins, and the two moved verify
      expectations).
    - M2, (b) undone: 2 failures (the equal-date control, in the engine and in the chain).
    - M3, D67 undone: 13 failures, every finding-0 hold pin among them.
    - M7, rejudged keeping the stored current: 1 failure (the stored-inventory pin).
    - M8, (a) widened to every precision: 1 failure (the month-or-year control).
    - M9, rejudged writing into the stored record: 1 failure (the stored-inventory pin).
    - M10, any worded current time unchecked with no service date (an over-reach in time_words): 6 failures in the two
      "unaffected" controls (whole frames, and the framed EMR on the undated document).
    - M12, verify.currency drifting from normalize._current (an unverified current time read as 'yes'): 11 failures (10
      subtests of the drift guard, and the stored-inventory pin).
    - M0, a4dcbea72's code with these tests: every D67 pin fails except the controls, which hold there too.
    - The document's-own-date control (45390 held with event_time) is a reference: it passes on a4dcbea72 and under
      every mutant, as it should.
  - Recorded residuals.
    - The pairing relations (relations.relate) are made once, at normalize, with the normalize-time date. assess
      re-judges times but not relations. (a) makes them fail-closed on an undated document: a day-dated current time
      is unusable there, so its time row is UNKNOWN and asks. With a document date, a member's date that differs is a
      held conflict.
    - The reviewed-coverage recount at read time (readers.reading -> overlay.reviewed_completeness, after a reviewer
      reinstates a code) reads the STORED times, not re-judged ones. On an undated document they are the less verified
      ones (date_unchecked), so the recount is fail-closed. On a held conflict they are the document date's, but such
      an encounter is held by its date.
    - facts.routing_stand_in (the D8 stand-in) still reads the stored times.

- **D68 D35's marker and a date_mismatch are doubts, never proof of another occasion (2026-11-10; the round-3
  refutation of a4dcbea72, findings 1 and 18; completes D62).** D62 kept one carve-out: a current_encounter time whose
  reasons held other_occasion or date_mismatch was "evidence, not a doubt", so coverage.possibly_current and
  relations._possibly_current counted that event as not current. But D35's markers include sequence words within one
  procedure ('Next', 'Later in the procedure', 'At that time'; FUTURE_MARKERS also 'later' and 'repeat'), and the
  prompt asks Gemini for such words whatever time it gives. A clock time ('At 2030') reads as the year 2030. So a whole
  worded that way released the part it holds, and the part's code went READY where installed c2e53f8e holds it:
  - finding 1: a biopsied 6 mm sigmoid polyp then 'Later in the procedure / Next / At that time / At 2030, the polyp
    was removed with a cold snare.': 45380 READY. A cecal injection then 'Next, the polyp was resected by EMR en bloc.':
    45381 READY. A biliary sphincterotomy then 'Next, a 10 Fr by 7 cm plastic biliary stent was placed in the common
    bile duct.': 43262 READY;
  - finding 18: an 18 mm pedunculated polyp's head biopsied then 'Next, the polyp was removed with a hot snare and
    retrieved.': 45380 READY with 45385 held on its time. A lift injection then 'Next, the lesion was removed by
    endoscopic mucosal resection in three pieces.': 45381 READY. An EGD to D2 then 'Next, the linear echoendoscope was
    introduced ...' with an FNA: 43235 READY. The EUS examination left no session, so C-4 never made the EGD its
    portion.
  - The rule. Both functions count a current_encounter time as possibly current WHATEVER its reasons
    (coverage.CONTRADICTED_TIME is removed). Only an earlier or future time is not current, verified or not. The part
    stays held: bundled (biopsy_of_removed_lesion, lift_injection, stent_included), or its base question (base_included,
    the EUS examination a possible examination of its session). The whole's own code keeps its time question.
  - The accepted fail-closed cost, recorded: a 2024 examination Gemini calls current beside today's leaves today's
    session unresolved.
    - tests.test_interpretation_cases' s1-e5 'mislabelled-current-with-its-time-words' moves: 45378 was READY on E2 and
      is now asked the extent (needs_clarification, ['extent']). The session's event is '', and the 2024 reach is
      still discarded, never the extent.
    - tests.test_interpretation_coverage.PossiblyCurrent's dated-aside test moves: the session is unresolved (event '',
      unresolved True, examinations E1 and E3), never E3.
  - Measured on FRESH-2 (with D67, f2r3-currency):
    - 0 of 486 rows changed;
    - four assessment files differ only in completeness.event_coding.sessions['gi.egd'].examinations, [] -> ['E3'] or
      ['E1']: aside-of-twins-021 r1 and aside-of-twins-023 r1, r2 and r3;
    - there, the 'At the original procedure' EGD examination is now a possible examination of a session that has no
      done one: no session is unresolved, no verdict moves;
    - the replay pins and the head-to-head do not move.
  - Pins (tests.test_interpretation_r3_currency):
    - test_d68_a_sequence_word_or_a_clock_time_on_the_removal_keeps_the_biopsy_bundled ('Later in the procedure',
      'Next', 'At that time', 'At 2030');
    - test_d68_a_sequence_word_on_the_emr_keeps_its_injection_bundled (an injection naming the cecum or the polyp;
      'Next' and 'Later in the procedure');
    - test_d68_a_sequence_word_on_the_stent_keeps_the_sphincterotomy_part_of_it;
    - test_d68_the_polyp_heads_biopsies_stay_bundled_into_a_next_hot_snare_removal;
    - test_d68_the_lift_injection_stays_bundled_into_a_next_emr;
    - test_d68_the_egd_stays_the_endoscopic_portion_of_a_next_eus (43235 asked base_included);
    - test_d68_a_bleeding_control_beside_a_next_polypectomy_is_asked: the relations step's half, D41's
      procedural_adjunct bundling identity recorded beside a 'Next' removal; 45382 asked act_target;
    - test_d68_a_current_encounter_time_is_possibly_current_whatever_its_reasons (both functions; an earlier or future
      time never is).
  - Mutation proof:
    - M4, the carve-out restored in coverage: 20 failures, every D68 shape pin among them, plus the two moved
      expectations;
    - M5, restored in relations: 4 failures (the adjunct pin, and the unit pin's three contradicted reasons);
    - M6, both restored: 20 failures;
    - M0, a4dcbea72's code with these tests: every D68 pin fails.
  - Recorded residual: an unresolved session switches off what reads the session's one examination.
    - Not new: D62 already does this for an unanchored examination. D68 extends it to a D35-marked or date-mismatched
      examination. On a synthetic EGD + upper EUS + FNA document with a 'Previously, an EGD ...' or 'On 01/14/2024, an
      EGD ...' examination Gemini calls current:
      - the EGD session becomes unresolved, and C-4's part_of applies only to a session WITH an event;
      - so 43235 is asked the extent instead of base_included. It is held, never READY;
      - a4dcbea72 asks base_included, and installed c2e53f8e asks base_included on each of these texts.
      D62's unanchored 'At her index EGD' already asks the extent on a4dcbea72.
    - The same happens to a broad current denial: events.broad excludes an unresolved session. 45385 citing the scar
      beside 'No polyp was removed today.' is asked performed_status and extent instead of statement_scope, and 45380
      is asked the extent.
    - Not on FRESH-2. The repair belongs in coverage.sessions (C-4 and C3 read from the family's done examinations,
      whatever a possible one leaves unresolved), outside this repair's files.

- **D69 C-4's lower-EUS reader reads only today's done EUS examinations (2026-11-10; the round-3 refutation, finding 2;
  ADJUDICATION C-4).** `_lower_eus` read every gi.eus event of the reading, whatever its status and time. So when
  Gemini faithfully listed a rectal EUS line as an EUS examination targeting the rectum - "Plan: rectal EUS for
  staging of the rectal mass in 2 weeks." (planned, future), "History: a radial EUS of the rectum in 2024 showed a 1 cm
  rectal carcinoid." (earlier encounter), "No rectal EUS was performed." (not performed) - the EUS session read as
  lower, today's EGD was not the upper EUS's endoscopic portion, and 43235 went READY beside 43242. The installed
  release holds 43235 on all four texts, and the new path's own control (no such line) holds it with base_included:
  held turned to READY.
  - The rule. The lower reader takes the examinations it is given, and C-4 gives it the gi.eus session's DONE
    examinations only: coverage.done_examinations (new) - events.done (a usable performed or begun status, a usable
    current_encounter time, a usable documenting-team performer), a usable kind, an examination kind, and no digital
    examination (FINAL 5.6 E13). That is the predicate sessions() chooses a session's own examination from (its
    `exams`), pinned equal on every fixture of the new module. A planned, historical, denied or doubted EUS line, and
    D62's possible examinations, never make the session lower.
  - DONE is read as events.done, which includes an examination begun and not completed (D71 uses the same reading).
    Measured on a scratch probe: an EGD beside an attempted rectal EUS, the only EUS ("A radial echoendoscope was
    introduced into the rectum; the examination was aborted because of patient intolerance."). As built, the EGD keeps
    its own no_proposal item (second_review True) and 43235 is READY. With a performed-only lower reader, the EGD is
    read as that rectal EUS's endoscopic portion: its item is dropped and 43235 is held base_included.
  - Effect besides the finding, measured on scratch probes. With 43242 alone proposed on finding 2's planned,
    historical or denied text, the EGD is now read as included in 43242 (included_by {gi.egd: [43242]}). Its
    no_proposal item goes, and coding moves from incomplete to complete_pending_review with 43242 READY. That is
    exactly what a4dcbea72 gives the control text without the line.
    - c2e53f8e reads the EGD as included in 43242 on the control, planned and historical texts (no EGD item).
    - On the denied text, c2e53f8e lists a no_proposal item and no inclusion, where its legacy reader also holds 43242
      on performed_status.
    - Coding there is incomplete on every text, because c2e53f8e holds 43242.
  - Pins: tests/test_interpretation_r3_eus.py LowerEusReadsDoneExaminations
    test_d69_a_planned_historical_or_denied_rectal_eus_never_frees_43235_beside_43242 (finding 2's control, plan,
    history and denied texts: 43235 held with C-4's base-within check and question, 43242 READY), and
    test_d69_a_rectal_eus_done_today_still_includes_no_egd (the kept control: a rectal EUS done today, with the
    planned line beside it, leaves 43235 READY).
  - Residual, for the owner (finding 2's design said examinations; recorded with its input, not built): a lower place
    stated only on an EUS ACT no longer marks the session lower. "A standard gastroscope was advanced to the second
    portion of the duodenum." / "Radial EUS was then performed; a perirectal lymph node in the rectum was sampled with
    a 22-gauge needle." (the EUS examination names no place and no reach; the FNA's target is the rectum, verified),
    with no proposal: the EGD's no_proposal item and its second-review mark are gone (a4dcbea72 and c2e53f8e both list
    them), and 43235 alone is held base_included where a4dcbea72 READYs it (c2e53f8e holds it on performed_status and
    extent). With 45342 counted, nothing changes. FRESH-1 and FRESH-2 have no lower-tract EUS event, so this has no
    measured members. Reading the session's done ACTS too would keep that item, but it would read an upper EUS with an
    act verified in the colon as lower.
  - Residual, for the owner (not built, the same on a4dcbea72): C-4 keeps its structure, "any lower examination, no
    upper EUS". An upper EUS, an EGD and a rectal EUS all done today (performed, or begun and aborted) leave the EUS
    session unresolved and 43235 READY beside 43242. c2e53f8e holds 43235 (performed_status, extent) and 43242
    (target). Reading "some done examination is upper" would hold it. No FRESH member.

- **D70 C-4's upper EUS is the gi.eus session's done examinations only, and a possibly current upper EUS is a doubt the
  base-within rule reads (2026-11-10; the round-3 refutation, finding 3; amends D62's reach, ADJUDICATION C-4).** D62
  widened Session.examinations to the possibly current examinations, and C-4 still read any examination there as the
  upper EUS session. So the index EUS of "These were the findings at her index EUS: a 2 cm subepithelial lesion in the
  gastric body." (current_encounter worded with the aside's own words: current_unanchored, possibly current) made
  today's EGD the EUS's endoscopic portion.
  - With no proposal, the EGD's own no_proposal item was dropped by inclusion_asks_no_code and the not_listed guard,
    and so was its second-review mark (jobs._second_review_items offers the bounded second review only for marked
    no_proposal or not_covered items). Completeness was left with only the unestablished EUS. c2e53f8e and b3f3bedba
    keep the EGD's item.
  - The rule. upper_eus reads done_examinations(reading, 'gi.eus') only, so a possible examination never makes the EGD
    part of the EUS (part_of stays ''), and the EGD keeps its own items and second-review mark.
  - THE MECHANISM: a doubt in the stored record, read by the base rule.
    - coverage.sessions sets a new Session field, `possibly_part_of = 'gi.eus'`, on today's EGD session (its one done
      examination) when C-4 does not include it in a done upper EUS and C-4 read over the session's done and possible
      examinations together would: there are possible EUS examinations and none of the done or possible examinations is
      placed in the lower tract. A possibly current rectal EUS gives no doubt, since C-4 would include no EGD in it.
    - coverage.event_coding stores it in the session record (`possibly_part_of`).
    - combination.base_within reads `part_of or possibly_part_of`. So 43235 is held with C-4's base-within check and
      question ("Is 43235 reported separately from the endoscopic ultrasound for this examination?"), beside the counted
      EUS codes that include the EGD examination, or beside none. It is never READY and never excluded.
    - Nothing else reads the field: inclusion_asks_no_code, the not_listed guard, included_by and readers' included_in
      read part_of only.
    - Why the base rule, and not an extra hold in assess: the read-time overlay (overlay._bases) re-runs
      combination.base_within and base_included over the STORED event coding on every read, and it deletes and
      releases a stored base_included check that they no longer give. Measured as mutant M4 (the doubt kept out of the
      record, the engine holding 43235 itself): the engine's proposal is held, and the review view turns it to ready,
      released ['base_included'].
  - The doubt's check reason is base_within_hold's, which is pinned to the legacy wording: "The documented upper
    endoscopy is the endoscopic portion of the endoscopic ultrasound documented with it; ...". That states as fact what
    is here only possible; the question is C-4's. A doubt's own wording would need a new builder in combination and
    wording, which the overlay would also have to call (recorded, not built).
  - Pins: tests/test_interpretation_r3_eus.py PossibleUpperEus:
    - test_d70_another_occasions_eus_leaves_todays_egd_its_own_item_and_second_review_mark (finding 3, no proposal);
    - test_d70_43235_beside_a_possible_eus_is_held_with_c4s_question_never_ready (finding 3 with 43235: held
      base_included, the check and question equal to base_within_hold's, the record's possibly_part_of);
    - test_d70_the_read_time_overlay_holds_it_from_the_stored_record (overlay.review_view over the stored rows and a
      JSON-ready completeness: still held, nothing released or recomputed);
    - test_d70_controls (no EUS line, and the index EUS placed at an earlier encounter: the EGD's item kept, 43235
      READY; its time verified by default: C-4 holds as designed; a possibly current rectal EUS: no doubt, 43235 READY).
  - Recorded, not repaired: C3's own arm still reads a verified part_of naming ANY examination event of another family.
    Gemini's EGD `part_of: E2` naming the same possible index EUS still makes the EGD part of it, and with no proposal
    its no_proposal item is dropped. 43235 is held base_included there, which is fail-closed for the code.

- **D71 A session left unresolved by a possible examination keeps D61's signals from its done examination, and an
  examination begun and not completed gives every code of its session both (2026-11-10; the round-3 refutation,
  finding 4; completes D61).** _incomplete_session read only the session's one resolved examination. So a possibly
  current aside ("These were the findings at her index colonoscopy: diverticulosis.") beside D61's own finding-10
  examination (the colonoscope to the transverse colon, its completion verified 'incomplete') left the session
  unresolved, and 45385 and 45378 lost the 52/53 consideration and the service.incomplete warn. b3f3bedba and c2e53f8e
  give both codes both. The same mechanism left a READY, approvable 43253 on an incomplete upper EUS with neither
  signal (the verifier's probe 4).
  - Now every DONE examination of the code's session is read (coverage.done_examinations), in order:
    - a verified 'incomplete' completion gives its words (D61's, first);
    - otherwise a done examination whose status is a usable attempted_not_completed (verified by its failure marker,
      as the base code's own state reads it) gives its failure-marker words.
  - Every code of the session, whatever its own state, carries the warn and the consideration once. An excluded code
    carries neither. Status never changes.
  - The status arm also reaches resolved sessions, which closes D61's recorded residual: finding 10's cecum text with
    the examination stated begun and not completed and no completion now gives the READY 45385 both signals, as
    c2e53f8e does. Two done examinations of one family, one of them stated incomplete, now give both too.
  - Pins: tests/test_interpretation_r3_eus.py DoneExaminationsCarryD61:
    - test_d71_a_possible_aside_examination_keeps_d61s_signals_on_every_code (finding 4's input, the aside built both
      ways the verifier built it; the strings equal checks.incomplete_consideration and the warn);
    - test_d71_a_ready_code_beside_a_possible_aside_carries_them (43253 READY with both signals, with and without the
      aside);
    - test_d71_an_examination_begun_and_not_completed_gives_every_code_of_its_session_both (the act code in the
      status's words; the base code keeps its own one check and one consideration).

- **D72 A full-class EUS code does not fit an examination whose status is attempted_not_completed (2026-11-10; the
  round-3 refutation, finding 6; completes D43 and D56).** D43 and D56 read the incompleteness only through the
  completion. On D56's own pin text ("The examination was incomplete: the esophagus and the stomach were not
  examined."), with Gemini stating it on the examination's STATUS (attempted_not_completed, 'was incomplete', verified
  by the failure marker; completion not stated), 43259 was READY with no question while carrying "Documented as
  incomplete". On "The examination was aborted because of oxygen desaturation before the pancreatic body and tail were
  examined." the EUS-FNA 43242 was READY. c2e53f8e holds both texts. In _examination_class, a FULL-class code now also
  misfits when its session examination's status value is attempted_not_completed, in any state, with D56's "stated to
  be incomplete" question. The limited and lower-tract classes still read their reach.
  - Pins: tests/test_interpretation_r3_eus.py AttemptedStatusClass
    test_d72_43259_on_the_d56_text_with_the_incompleteness_on_the_status_is_held (with and without Astra proposing
    43259 and Fable nothing; the complete control READY) and test_d72_the_aborted_eus_fna_holds_43242 (43242 held on
    its class and carrying D71's signals in "was aborted"; 43238 held by its reach, as before).

- **D73 A second reach entry's 'incomplete' completion is never dropped with the entry (2026-11-10; the round-3
  refutation, finding 7).** Normalize kept the first reach entry for an examination and dropped the second whole. With
  its 'incomplete' completion it dropped what D56 reads, so on finding 7's answer (reach[0] at the second portion of
  the duodenum, completion not stated; reach[1] the same place, completion 'incomplete', words "The examination was
  incomplete") 43259 was READY. In the reach merge, when the dropped entry's completion says 'incomplete', the kept
  examination's completion becomes that completion, unverified, with the new closed-list reason second_reach
  (verify.REASONS). So D56 and D72 read it (any state), D61 does not (verified only), and D38 still asks a short
  colonoscopy reach. The problem "encounter.reach[1] gives a second reach for one examination; the first is kept."
  stays recorded.
  - Deviation from the literal design: when the kept completion already says 'incomplete', it is kept. Replacing a
    verified 'incomplete' with an unverified one would remove D61's warn and consideration. Measured as mutant M9
    (the guard removed), where the control loses them.
  - Pins: tests/test_interpretation_r3_eus.py SecondReachCompletion
    test_d73_a_second_reach_entrys_incomplete_completion_holds_43259 (finding 7's answer, long and short words, with
    and without the participants: the completion unverified with second_reach, the problem and the reason count
    recorded, 43259 held with D56's question), and test_d73_controls_one_reach_and_a_kept_incomplete (one reach
    READY; the incomplete entry first, then either second entry: its verified completion kept, D61's signals kept,
    no second_reach).
  - One existing test changed: tests/test_interpretation_normalize.py every_reason_scenario gains a second_reach
    scenario, because the closed list gained the reason (EveryReason pins one scenario per reason).
  - Residual, for the owner (not built): an entry whose landmark is not_stated is never attached and records no
    problem, so its completion is lost whatever its value. A no-landmark 'incomplete' entry beside a placed entry, in
    either order, leaves 43259 READY on the same text. Census: 0 of 191 FRESH-2 and 0 of 197 FRESH-1 reach entries
    carry 'incomplete' on a not_stated landmark.

- **D69-D73, what was edited, and the measurement.**
  - Files edited outside the listed ownership, each needed by the specified behaviour:
    - combination.base_within: 3 lines, so that the base rule reads the doubt (D70);
    - coverage.Session: one field, `possibly_part_of`;
    - coverage.event_coding: one key, so that the overlay sees the doubt;
    - verify.REASONS: one reason, `second_reach` (verify.ordered refuses a reason outside the closed list);
    - tests/test_interpretation_normalize.py: the one scenario above.
  - The module docstring of coverage.py is untouched. Its C-4 sentence ("a current performed EGD examination in an
    encounter with a current performed upper-tract EUS examination") is what the code now does.
  - Cost on FRESH-2 (f2r3-eus-sessions against f2int3, the a4dcbea72 scoring):
    - the summary is unchanged: A 96/6, B 177/15, C 167 correct / 19 false hold / 4 dropped_question / 2 safe_hold;
    - 0 of 486 rows and 0 of 179 runs differ;
    - all 179 inventories are byte-identical;
    - all 179 assessments are identical once the new session key is set aside, and no recording has a non-empty one.
  - The head-to-head against c2e53f8e (H2H_OUT h2h.json) is identical to a4dcbea72's h2h/h2h.json: worse 8, better 69,
    unstable 7, facts moved 1 (C2CL-013, unchanged).
  - Census of the frozen answers:
    - FRESH-2: 191 reach entries, 4 'incomplete' completions, 0 examinations with two reach entries, 0 of 354
      examinations attempted_not_completed;
    - FRESH-1: 197, 4, 0, and 0 of 356;
    - finding 2's class has 0 members in either corpus (the verifier's count).
  - The replay pins do not move. Neither does any other existing expectation.
  - Suites:
    - the new module: 13 tests;
    - every tests.test_interpretation_* module with test_pipeline_assess_events, test_readers_dispatch and
      test_overlay_differential: 1030 OK (a4dcbea72: 1017, plus the 13);
    - the full tests suite on the work copy, as four concurrent serial partitions of the 328 modules: 7829 tests,
      7828 pass. The one failure is a legacy-engine timing bound (test_repairs_r4_validation's CoverageCostTests,
      10.9 s against 10.0 s) under a machine loaded by other suites. studio/validation is untouched, and the module
      passes alone on both the work copy and a4dcbea72 (30 of 30 each);
    - ops.test_install_interpreter: 47 OK.
  - Mutation proof. Each mutant was built in its own copy of the work tree and each replacement was asserted to occur
    once. Each was confirmed applied by its marker and a sha256 change, with the work copy's sha256 unchanged.
    - M0, the whole change undone (a4dcbea72's engine with the new pins): 11 of the 13 new tests fail or error, and so
      does EveryReason. The overlay pin and the D73 control hold on a4dcbea72 too.
    - M1, the lower reader over every EUS event: the D69 pin fails (plan, history, denied).
    - M2, upper_eus over done and possible examinations: 3 D70 pins fail.
    - M3, the base rule reading part_of only: the hold pin and the overlay pin fail.
    - M4, an assess-only hold: the overlay pin fails ('ready', released ['base_included']).
    - M5, D71 undone: the 3 D71 pins and the aborted EUS-FNA pin fail.
    - M6, D71's status arm removed: the begun-and-not-completed pin and the aborted EUS-FNA pin fail.
    - M7, D72 undone: both D72 pins fail.
    - M8, D73 undone: the D73 pin and EveryReason fail.
    - M9, D73's guard removed: the D73 control fails.
    - M10, the doubt ignoring the lower tract: the D70 controls fail.
    - M11, done_examinations admitting possibly current examinations: the D69 pin and 2 D70 pins fail.
    - M12, the lower reader never reading lower: the D69 kept-control fails, on its session assertion (the EGD
      becomes part of the rectal EUS). test_interpretation_combination's test_a_lower_eus_includes_no_egd still passes
      under M12, because 45392 includes no EGD examination, so 43235 is READY either way.

- **D74 A narrowed code whose defining act is only doubted still claims what its covers name (2026-11-10; the round-3
  refutation of a4dcbea72, finding 5; widens D55).** D55 gave a code D27 narrows (CodeLink.defining) the claims of its
  covers' other kinds only when it was matched (E* non-empty). E* needs a usable status and a usable current time, so a
  lithotripsy whose time words are unanchored (D54: "During the procedure", "After biliary sphincterotomy") or whose
  status words do not bind ("was broken up") left 43265 held with no claims. 43264, proposed for the balloon extraction
  of the same stone's fragments, then went READY with no question. The installed release holds both with
  competing_codes on all three texts (Astra and Fable configured as in production). That is held turned to READY, on
  the wrong code: 43265 includes the extraction.
  - The rule. assess._claims gives those claims whenever the code is matched, OR its family has an event of a defining
    kind whose status value is positive (verify.POSITIVE) and whose time is possibly current (coverage.possibly_current,
    D62), in any verification state: the kind, status and time are read as values, and an unverified or opened state is
    not read.
    - No claims come from a defining act that is denied, planned, verified at an earlier encounter or stated in another
      family. Nor do they come from one worded with another occasion's marker, while D62's carve-out reads D35's
      marker as evidence, not a doubt: the rule follows coverage.possibly_current.
    - With no such act (not documented), 43264 stays READY (D27's test; and FRESH-2 fb13 r1-r3, where 43264 is READY,
      as expected, beside 43265 held not documented).
    - The claimed kinds are unchanged (D55): the covers' kinds beside the defining kinds. That is the extraction for
      43265, the ablation for 44365 and the tube placement for 49440, each act current and performed
      (coverage.current_performed).
    - E*, support['acts'], the coverage reconciliation and combination.competition are unchanged. The competition call
      site changes only its comment.
  - Cost measured.
    - FRESH-2 (f2r3-claims-base against f2int3): 0 of 486 rows change, and no recording changes through D74. fb13 r1-r3
      propose both codes with no lithotripsy stated, so 43265 is held not documented, as before.
    - Head-to-head against c2e53f8e: identical to a4dcbea72's.
    - "Covered kinds" was read as D55's "the kinds its covers name beside its defining kinds". The other reading,
      "every covered kind, the defining kinds included", was measured on a private copy: FRESH-2 changes 0 files. The
      two readings differ only on the EUS FNA codes, whose acts are their defining kinds. There, a doubted FNA would add
      competing_codes to EUS codes the per-code rule already holds.
  - Pins: tests/test_interpretation_r3_claims.py D74DoubtedDefiningAct, four tests:
    - finding 5's three texts, with no participant and with Astra and Fable read and proposing nothing (6 subtests);
    - _claims over three claimed shapes (time unanchored, status words unbound, attempted) and four unclaimed ones
      (denied, planned, an earlier encounter, another family). A time worded with another occasion's marker follows
      coverage.possibly_current, so the pin holds whatever the round-3 currency repair decides about D62's carve-out
      (findings 1 and 18). Today nothing is claimed for it;
    - 44365 beside 44369, and 49440 beside 49441;
    - the controls: a verified lithotripsy, a whole present-encounter frame, and not documented.
  - Mutation proof, in private copies, each mutation confirmed applied, with sha256 before and after:
    - _claims as at a4dcbea72: 10 subtests fail across the 3 behaviour pins, and the control passes;
    - the gate without the positive status: 2 fail (denied, planned);
    - without possibly_current: 2 fail (an earlier encounter, and the marker case under today's carve-out);
    - over every family's events: 1 fails;
    - needing a verified status: 4 fail.
  - Recorded, not repaired.
    - A lithotripsy attempted and abandoned (attempted_not_completed is positive) claims the extraction too. So 43264 for
      the balloon extraction that followed is held with competing_codes, beside 43265's own C-9 hold. This fails
      closed and may be a false hold. The installed release was not measured on that text.
    - D74 goes one way. A held rival that D27 does not narrow (43264 with its extraction time unanchored) still claims
      nothing, so a matched 43265 stays READY beside it (probed). This is round 2's recorded #2/#6 shape: the READY
      code is the one the document supports.

- **D75 An act whose procedure is not usable is doubted in its family's current session (2026-11-10; the round-3
  refutation of a4dcbea72, finding 17).** coverage.reportable needs a usable procedure, and coverage.doubted read only
  the kind, status, time and performer. So an act stated as done whose procedure was unverified was neither reportable
  nor doubted, and the base rules saw an empty session.
  - The finding. In each of finding 17's recordings, Gemini cites the 3-character heading 'EGD' as the procedure words
    of the four cold-forceps biopsies. The heading is too short to locate, and with two current families the default
    does not settle (passage_unlocated, procedure_unsettled).
    - 43235 proposed alone was READY with no question in 12 committed session-runs.
    - The installed release asks base_included (and the extent) there.
    - The registry expects 43239, and fb11 lists 43235 as must_not_ready beside EGD biopsies.
  - The rule. coverage.doubted also returns True for an act that meets all of these conditions:
    - stated positive and possibly current;
    - not verified at another time or by another performer;
    - its procedure not usable (unverified, or opened by Gemini's own question);
    - its family has a current session (a done examination).

    Two things follow:
    - combination.base_included holds the base code with base_included, worded "includes forceps biopsy (stated in
      doubt)".
    - The same predicate makes such an act in_doubt where no code reads it (FINAL 7.8: a candidate that an unverified
      attribute blocks). When the family has no counted code, it gets a service-scope procedure question.

    coverage.reportable is unchanged. It already needs a usable procedure, so no act is both reportable and doubted.
  - Not built: the spec's "for every family that has a current session". This goes to the owner.
    - Why. event_coding lists only a session's own events, those whose procedure value names its family, and
      event_coding is outside this repair's ownership (coverage.py: reportable and doubted only). So the act counts
      only in the session of the family that its unusable procedure names.
    - Concrete input, measured: an EGD to the duodenum and a colonoscopy to the cecum, with "Random cold forceps
      biopsies were taken from the right and left colon."
      - (a) The biopsies' procedure is 'egd' with no words, so the default is unsettled. 43235 alone is held
        (base_included), but 45378 alone stays READY with no question.
      - (b) Their procedure is 'unknown', so it is absent: the act has no family and is in no session. 43235 alone and
        45378 alone are both READY, and the biopsies appear in no unresolved item.
    - A private copy that also lists such an act as doubted in every session with a done examination holds all four.
      On FRESH-2 that variant changes 19 files (the colonoscopy sessions gain the EGD-labelled biopsies), 0 rows and 0
      differential probes.
    - Census of FRESH-2's positive, possibly current, not-other-performer acts:
      - 66 have an unusable procedure in a current own family;
      - 12 have an own family with no current session, all EGD-labelled biopsies beside a current colonoscopy (W1S-107,
        -112, -316);
      - none has an absent procedure.
  - Cost measured.
    - FRESH-2 (f2r3-claims-base against f2int3): 0 of 486 rows change. 16 of 358 files change: the EGD session's doubted
      list gains the unverified-procedure biopsies in 16 assessments (history-families-004 r1-r3,
      p11-colon-devices-001, p7-codes-025, W1S-068, -075, -076, -156, -171, -399, -438, -465, and -499 r1-r3).
    - Two of those assessments, p11-colon-devices-001 and p7-codes-025 (no EGD code proposed), also gain an in_doubt
      item, the service question "In which procedure was the forceps biopsy ... done?", and completeness reasons.
    - No row moves because no FRESH-2 proposal set pairs a diagnostic base code with these acts. The registry proposes
      43239, which is held by its own procedure question, and W1S-499's 45378 was already held.
    - Head-to-head against c2e53f8e: identical to a4dcbea72's. No new false_ready, false_exclusion, dropped_question or
      ready_wrong_facts.
    - Single-code differential over the 161 committed recordings: each family's base code proposed alone, citing its
      session examination, in every session with one done examination (162 probes in 142 recordings). 12 probes move,
      all of them 43235 from ready to needs_clarification [base_included]. These are exactly finding 17's 12
      session-runs. 45378 (8 READY), 45330 (3 READY) and every held probe are unchanged.
    - The replay pins are unchanged: test_interpretation_replay passes, and D75 reads only the assessment.
  - Pins: tests/test_interpretation_r3_claims.py.
    - D75UnusableProcedure, on finding 17's five committed recordings (history-families-004 r1-r3, W1S-438 r1, W1S-068
      r1): 43235 is held with base_included, the four biopsies are doubted, and none is reportable. In the control, with
      the biopsies' procedure verified, 43235 is held through reportable, as before.
    - D75Doubted, synthetic: an unsettled default, words that do not bind, and a procedure opened by an open question
      are each doubted, and each holds 43235. The bounds: a verified procedure is reportable, not doubted. A verified
      earlier time, another clinician, a denial, a plan, and a family with no current session are not doubted.
  - Mutation proof, in private copies:
    - doubted as at a4dcbea72: 8 subtests fail across the 2 behaviour pins, and the control passes;
    - without the current-session gate: the bounds pin fails;
    - reading only an unverified procedure, not an opened one: the opened shape fails.
    - One mutant survives, and why: dropping possibly_current from the new arm fails nothing. The arm is reached only
      with a usable time that is not verified at another time. normalize records such a time as verified with no
      reasons (a contradicted time is unverified, and 'unknown' is absent), so the time is always current there. The
      clause states the spec's condition.
  - Recorded for the owner: one service question can now name a different act. reconcile keeps one unresolved item per
    (session, act kind), and only the first act's in_doubt question is asked. A newly doubted act listed first therefore
    takes the question from another doubted act of the same kind. This is outside this repair's ownership (reconcile's
    merge and in_doubt_questions).
    - Probed: an EGD and a colonoscopy, with no EGD code proposed (45378 alone). Biopsy E2 has its procedure unsettled.
      Biopsy E3 is "Earlier that day, cold forceps biopsies were taken from the gastric body.", its time unverified
      (other_occasion).
    - Before D75 the service question asks E3's time ("Was the forceps biopsy (cold forceps) at the gastric body (“were
      taken”) done at this encounter?"). After D75 it asks E2's procedure, and E3's time is no longer asked.
    - No code changes status, and no proposal question moves. On FRESH-2 no service question is replaced: 2 are added,
      none is lost.
    - A repair in reconcile could ask one question per (family, fact) over every in_doubt event of a merged item.
  - Recorded wording, outside this repair's ownership. For these acts it is the procedure that is in doubt, not
    whether the act was done, yet two sentences say otherwise. The service question itself asks the procedure.
    - The base hold labels the act "(stated in doubt)".
    - The in_doubt item says CPT Studio "could not confirm from the document that it was done at this encounter".
  - The @1 labels are unchanged: nothing is recorded under them in production (D33, D48).

- **D76 Two distinct lesions set a removal's adjunct apart only through their places (2026-11-10; the round-3
  refutation, findings 8 and 9; narrows D41 and D58).** D41 and D58 let "two distinct verified lesions" set an ablation
  or a bleeding control apart from the removal beside it, through identity.distinct_reason: by landmarks
  (lexicon.disjoint, which knows no adjacency and no chain), distances, specimens, sizes or passage. So the polypectomy
  site's own hemostasis went READY whenever Gemini registered the bleeding site as a lesion of its own, as it does on
  FRESH-2 ('Minor oozing from the cut mucosal edge': note8 r2 E18->L10, C2MEM-029 r1, -031 r1 and r3, -032 r1,
  N8-CF-SITES r3):
  - finding 8: D58's own rectosigmoid pin with the oozing as L2 at the sigmoid colon (distinct by landmarks, though
    adjacent on the tract), and the polyp at the ileocecal valve with L2 'on the ileal side' at the ileum (on no
    chain): 45382 READY beside 45385;
  - finding 9: "A 2 mm visible vessel in the polypectomy base was treated with two hemoclips for hemostasis." with the
    vessel as L2 and no site (distinct from the 12 mm polyp by sizes), and "A 10 mm sessile polyp in the sigmoid colon
    was removed with a hot snare, and oozing from the polypectomy site was controlled with two hemoclips for
    hemostasis." with the oozing as L2 (distinct by passage): 45382 READY.
  c2e53f8e READYs all of them: a shared false READY, not a regression.
  - The rule. In relations.identity_in_doubt's procedural_adjunct arm, two distinct verified lesions no longer decide.
    They set the adjunct apart only through the place test D58 already runs: the lesions' verified sites are among both
    acts' places (Context.places), so they must be on the tract's chains and neither compatible nor adjacent. Otherwise
    the arm goes on to the part_of test, where a verified part_of naming another ACT still sets it apart (D58), and
    nothing else does. A distinctness by sizes, passage, distances, specimens or description, or by landmarks that are
    adjacent or on no chain, never does (fail-closed). The lesion block is unchanged for the other bundling rules.
  - Cost measured. FRESH-2 (f2r3-adjuncts against f2int3): 0 of 486 rows, 0 of 179 runs and 0 of 358 inventory and
    assessment files change; the summary is equal. The head-to-head against c2e53f8e (h2h.json) equals a4dcbea72's.
    The FRESH-2 adjuncts registered on a lesion of their own all carry a verified part_of naming the EMR at its own
    landmark. The cost in principle: an adjunct on a distinct lesion one step away or on no chain, or distinct only by
    size, passage, distances or specimens, that names no act as its whole, is asked even when it is a separate act.
  - Pins: tests/test_interpretation_r3_adjuncts.py DistinctLesions:
    - test_d76_finding_8_an_oozing_registered_as_its_own_lesion_beside_a_rectosigmoid_polypectomy_is_asked (two
      target-word forms) and test_d76_finding_8_the_ileum_variant_is_asked;
    - test_d76_finding_9a_a_visible_vessel_distinct_by_size_alone_is_asked (no site; site words naming no landmark) and
      test_d76_finding_9b_an_oozing_distinct_by_its_passage_alone_is_asked (two L2 descriptions);
    - controls: test_d76_control_distinct_lesions_at_places_apart_stay_their_own_acts (D41's ascending-colon
      diverticulum registered as L2: READY) and test_d76_control_a_part_of_naming_a_biopsy_still_sets_it_apart (READY).
    Each pin asserts that the distinctness is real (Context.distinct gives landmarks, sizes or passage).
  - Mutation proof (each mutant in its own private copy, each applied once and confirmed, sha256 before and after):
    - m1, the arm returning `not context.distinct(...)` again: the 7 D76 subtests fail and no control does;
    - m11, a HARD distinctness (landmarks, distances, specimens) still setting it apart: the 3 finding-8 subtests fail
      and the size and passage pins pass, so each sub-arm is pinned on its own.

- **D77 A junction is no full step on the tract's chains (2026-11-10; the round-3 refutation, finding 10; amends D58's
  adjacency).** D58 gave every junction landmark on the chains a full step: the rectosigmoid, the splenic and hepatic
  flexures, the gastroesophageal junction and the pylorus. So the two segments meeting at a junction were two steps
  apart and set an adjunct apart. The stomach chain also put the fundus between the cardia and the body, which border
  each other along the lesser curve. Each of these was READY (45382, or 43255 beside 43251), with the clip naming no
  lesion and no part_of:
  - a polyp in the distal ascending colon with the clip on its site in the proximal transverse colon (D58's own
    hepatic-flexure pin, written from the other side of the flexure);
  - distal sigmoid with proximal rectum;
  - distal transverse with proximal descending;
  - an EGD's gastric cardia polyp with the clip in the proximal gastric body.
  c2e53f8e READYs all of them.
  - The rule. relations.JUNCTIONS lists the rectosigmoid, the splenic and hepatic flexures, the ileocecal valve, the
    gastroesophageal junction and the pylorus. relations.MUTUALLY_ADJACENT holds the gastric cardia, fundus and body.
    relations.adjacent: two places of one chain are adjacent when no FULL segment (a landmark that is no junction) lies
    strictly between them, or when both are in one mutually adjacent group. Two places are apart only when at least
    one full segment lies strictly between them.
  - What does not change. LOWER_TRACT, UPPER_TRACT, AT_THE_CECUM and TRACT_POSITION are as they were, so D58's chain pin
    holds. The ileocecal valve keeps the cecum's position. As the junction of the cecum and the terminal ileum, it never
    lies strictly between two places apart from that position, so listing it changes no pair. A step of its own after
    the cecum would set it apart from the ascending colon, which D58 reads as adjacent: the one direction D77 must not
    take.
  - Measured over every pair of schema.LANDMARKS: D77 sets apart no pair D58 did not. Exactly six pairs move from apart
    to adjacent: rectum and sigmoid colon, descending and transverse colon, transverse and ascending colon, distal
    esophagus and cardia, antrum and duodenal bulb, and cardia and body.
  - Cost. An adjunct in the neighbouring segment across a junction, with no lesion link and no part_of naming an act,
    is asked even when it is a separate act, for example a transverse-colon diverticulum beside an ascending-colon
    polypectomy. This is the trade D58 accepted for places one step apart. FRESH-2 and the head-to-head: no change, as
    under D76.
  - Pins: Junctions:
    - test_d77_the_junctions_and_the_stomach (the table);
    - test_d77_only_adds_adjacencies (every landmark pair against D58's rule, frozen in the test);
    - test_d77_finding_10_the_colon_pairs_meeting_at_a_flexure_or_junction_are_asked (the finding's three and the
      first one reversed);
    - test_d77_finding_10_the_stomach_pair_is_asked;
    - the control test_d77_control_a_full_segment_between_still_sets_it_apart: a splenic-flexure polyp beside a clip at
      the hepatic flexure, and a cardia polyp beside a clip in the antrum (READY).
    D58's controls pass unchanged: the rectosigmoid beside the descending colon, the sigmoid beside the ascending
    colon, the body beside the pylorus, the transverse-colon ablation beside the cecal EMR, and D55's antrum beside
    the jejunum.
  - Mutation proof:
    - m2, D58's one-step rule: 12 failures across the 5 D77 pins;
    - m7, junctions counted as full steps: 10 failures (all but the stomach's);
    - m6, no mutual adjacency: 3 failures (the stomach pair, the table, the census).
    No control fails.

- **D78 A removal done at several places sets its adjunct apart only when the adjunct is apart from each (2026-11-10;
  the round-3 refutation, finding 11; completes D58).**
  - What was wrong. Context.places read a removal at its one target landmark and its lesion's one verified site.
    Gemini gives a group lesion named at several segments the first-named one: on FRESH-2, 3 of the 7 'diverticulosis
    in the sigmoid and descending colon' lesions got sigmoid_colon. verify.landmark_words verifies that landmark when
    any named place is compatible.
  - The finding's input:
    - "Three sessile polyps, 4 to 6 mm, in the cecum, the ascending colon and the transverse colon were removed with a
      cold snare." Gemini gives one group lesion and one snare, both at the cecum.
    - "Immediate oozing from the transverse colon polypectomy site was controlled with two hemoclips for hemostasis."
      The clip is at the transverse colon, with no lesion and no part_of.
    - The cecum and the transverse colon are apart, so 45382 was READY, although the removal's own verified words name
      the transverse colon. c2e53f8e READYs it.
  - The rule.
    - Context.places(event, every=True) reads, besides the two places it read before:
      - every landmark the words of the event's verified target name (the target's literals);
      - every landmark its verified lesion's own words name (LesionFacts.sites: its description and its site words).
    - The procedural_adjunct arm's place test, _adjunct_places_apart, compares the adjunct's places with EVERY place of
      the removal read that way.
    - Each act must still have a place of its own: the two-place reading, and the caller's `known`. So the literals only
      ADD pairs to the test, and they never set apart a pair that was not set apart before.
  - Scoped deliberately. `every` defaults to False, and only the adjunct arm passes it. The other readers of
    Context.places need EVERY pair to be compatible: the pairing table's target rows, the model's claims, the other
    bundling identities and coverage's C-5 lift. More places there would set more acts apart.
    - Measured with a scratch probe against mutant m14, which reads every removal at all its places for every reader.
      Neither input is caught by the existing suite: under m14 it ran 1035 tests and only this module's two
      narrow-reading assertions failed.
    - The EMR of "A 30 mm laterally spreading tumor spanning the cecum and the ascending colon", with its target and
      site at the ascending colon, beside "A submucosal injection of saline was given in the ascending colon.": 45381 is
      asked (act_target) on a4dcbea72 and on this repair, and READY under m14.
    - The group snare of "Two sessile polyps, 5 and 6 mm, in the cecum and the ascending colon" beside "Cold forceps
      biopsies of the ascending colon polyp were taken.": 45380 is asked on both, and READY under m14.
  - Cost. FRESH-2 and the head-to-head: no change. The cost in principle: a clip at a place a group removal's words
    name (not its chosen landmark) is asked even when it is a separate act in that segment.
  - Pins, in SeveralPlaces:
    - test_d78_finding_11_a_clip_at_one_of_the_removals_places_is_asked. It also pins the other readers' Context.places
      as unchanged.
    - test_d78_finding_11_its_variants_are_asked: the snare naming no place, the lesion naming none, a single lesion,
      and the clip at the hepatic flexure.
    - test_d78_the_places_its_words_name_never_set_apart_a_removal_with_no_place_of_its_own, which pins the only-adds
      guard. The removal has no place of its own, though its words name the transverse colon, and the clip is in the
      cecum: it is asked, as before D78.
    - The control test_d78_control_a_clip_apart_from_every_place_is_its_own_act: a bleeding diverticulum in the sigmoid
      colon is READY.
  - Mutation proof:
    - m3, the arm reading the two-place set: 5 failures (finding 11 and its four variants);
    - m8, Context.places ignoring `every`: 7 failures;
    - m13, the widened places read throughout the arm, the caller's `known` included: the guard pin fails;
    - m14, the blanket reading: the finding pin and the guard pin fail;
    - m10, the inner emptiness test reading the widened places, is equivalent: the caller's `known` already requires
      each act's own place.
  - Recorded, not repaired. The spec widens the removal only, so an adjunct whose OWN words name several places is
    still read at its one landmark. "Immediate oozing from the polypectomy sites in the cecum and the transverse colon
    was controlled with two hemoclips for hemostasis." (landmark cecum), beside a single transverse-colon polypectomy,
    gives 45382 READY on a4dcbea72, on this repair and on c2e53f8e. Reading the adjunct with `every` too would ask it.

- **D79 An attempted removal is a whole its adjunct can belong to (2026-11-10; the round-3 refutation, finding 12;
  completes D30 and D41).**
  - What was wrong. relations._bundling recorded the procedural_adjunct identity beside any current POSITIVE removal,
    but coverage read only a performed whole (current_performed), both in bundling_doubt and in bundled_reason's
    adjunct arm.
  - The finding's input:
    - "Hot snare removal of a 12 mm sessile polyp in the sigmoid colon was attempted and not completed because of poor
      position." beside "Immediate oozing from the snare site was controlled with two hemoclips for hemostasis."
    - The clip was READY (45382 supported), with the relation recorded and never read.
    - With a verified part_of naming the attempted snare it was still READY: _bundling skips a verified step, and
      bundled_reason read no attempted whole.
    - The snare-tip soft coagulation of the margins beside an attempted EMR behaved the same way (45388).
    - c2e53f8e READYs 45382.
  - The rule.
    - coverage.adjunct_whole: a removal whose status is usable and performed or attempted_not_completed, and current
      as current_performed reads it (D62: possibly_current).
    - bundled_reason's adjunct arm reads its wholes through it: the part_of arm, and D30's lesion arm.
    - bundling_doubt returns a procedural_adjunct relation whose whole is one. The other bundling rules still need a
      performed whole.
    - current_performed, possibly_current, _wholes and the other arms are unchanged.
    - The attempted removal's own code keeps its own hold (performed_status; ADJUDICATION C-9).
  - Ownership. bundling_doubt is outside "bundled_reason and one new predicate", but (a) cannot be reached otherwise:
    events.evaluate asks act_target only from bundling_doubt. The change is one added condition.
  - Cost. An ablation that is the definitive treatment of a lesion whose snare removal failed, stated on that lesion or
    as part_of the attempt, is now held as bundled; a reviewer reinstates it. FRESH-2 and the head-to-head: no change.
  - Pins, in AttemptedRemoval:
    - test_d79_finding_12a_a_bleeding_control_beside_an_attempted_snare_is_asked;
    - test_d79_finding_12b_a_part_of_naming_the_attempted_snare_bundles_it;
    - test_d79_the_attempted_snares_verified_lesion_bundles_it_too;
    - test_d79_an_ablation_of_an_attempted_resections_margins: bundled through its part_of, asked with none;
    - the control test_d79_control_a_removal_never_begun_or_of_another_occasion_is_no_whole: a planned removal, one not
      performed, and an attempt in 2024, each with and without a part_of. The clip is READY, and each case first checks
      its own stated status and time.
  - Mutation proof:
    - m4, bundling_doubt reading only a performed whole: 12a and the ablation fail;
    - m5, bundled_reason reading only a performed whole: 12b, the lesion arm and the ablation fail;
    - m9, adjunct_whole reduced to possibly_current: the not-performed control fails;
    - m12, adjunct_whole ignoring the time: the earlier-encounter control fails.
  - Recorded, not repaired. A removal whose status is not usable is no whole, as current_performed reads it. This
    covers performed and attempted alike, when the words are unlocated or the failure marker is missing. The relation is
    recorded, bundling_doubt returns None, and the clip is READY beside the removal's held code. The probe gives 45385
    needs_clarification [performed_status] and 45382 READY, on a4dcbea72 and on this repair. D62's principle (an
    unverified attribute is a doubt, never an absence) would make it a whole for the question. That call belongs to
    current_performed's owner.

- **D76-D79, together.**
  - Files: studio/interpretation/relations.py (Context.places, the chains and adjacent, _adjunct_places_apart, the
    arm's lesion line, the arm's docstring) and studio/interpretation/coverage.py (adjunct_whole, bundled_reason's
    adjunct arm, one condition in bundling_doubt, the bundling docstring line).
  - No existing test's expectation changes. D58's chain table, its adjacent pairs, its two-step controls, its
    assert_places pins and D41's controls pass unchanged.
  - Tests on the working copy:
    - tests.test_interpretation_* with tests.test_pipeline_assess_events and tests.test_readers_dispatch: 1035 OK (1015
      before, plus this module's 20), the replay pins included;
    - the 14 other modules that import the package: 286 OK (3 skipped);
    - the full suite, run as four concurrent serial groups: 7836 tests, 7835 OK (7 skipped) and 1 failure. The failure
      is tests.test_completion_r2_outcome's 30-second bound on the legacy reader (studio.gi.detect.route, which imports
      nothing from studio.interpretation): 34.45 s at a load average near 17. Run alone, it passes on this repair
      (21.8 s) and on a4dcbea72 (22.9 s). An earlier `--parallel 4` run failed the same bound (31.57 s) and then hung,
      because Django's parallel runner could not pickle the failure.
  - Mutation proof m0, a4dcbea72 itself with this module: every finding pin fails. Most fail on the outcome. Those that
    read the new names (JUNCTIONS, `every`, adjunct_whole) fail by error: 12a, the D77 table and the three D78 pins
    that read `every`. The three D76 and D77 controls pass, because they hold before and after.

- **D80 A code of a recognised-only family is held, never READY and never excluded (2026-11-10; the round-3 refutation
  of a4dcbea72, finding 19).** The catalogue recognises moderate sedation and lists it for review without reconciling
  it (gi.sedation is RECOGNISED: "moderate sedation is recognised and listed, not reconciled"), and gi.profiles marks
  the family not supported ("Sedation checks are not implemented in this release; review required."). But 99152 and
  99153 have code profiles, so they took the catalogue route, and the per-code rule matched them to Gemini's sedation
  event. Nothing read CodeLink.supported or CodeLink.support, although CodeLink's docstring and
  test_the_support_the_engine_reads said the engine reads them. So 99152 was READY with no question on "Sedation:
  Moderate sedation was given by me (midazolam 2 mg IV); no independent trained observer was present. Intraservice time
  8 minutes." (under 10 minutes with no observer is not reportable) and on a 3-year-old (a patient under 5 takes
  99151). The installed release c2e53f8e holds both exact inputs with performed_status. That is held turned to READY.
  - The rule.
    - mapping.recognised_only(link) is true for a catalogue-route code whose family the catalogue does not mark
      SUPPORTED (recognised, unsupported, or no entry), or whose gi.profiles profile is not supported. Either one marks
      it (fail-closed). Today that is exactly 99152 and 99153.
    - events.evaluate holds such a code before it reads any event, through events.recognised_only_hold: state
      uncertain, reason recognised_only, the performed_status question wording.performed_question(code), quoting the
      code's own cited passages. E* and read are empty, as for route (d)'s hold.
    - The service.status and events.match checks read: "<family label> is recognised by CPT Studio and listed for
      review, not assessed: no service profile in this release reconciles <code> with the documented acts. What it
      needs documented is not checked: <the catalogue's documentation list>. Held for the reviewer, not excluded."
    - It is never excluded. A sedation stated not done, cited by its own words ("No sedation was given"), was
      excluded by 7.5 at a4dcbea72 and is now held, as c2e53f8e holds it.
    - R1 (out of scope, or no exact evidence) still excludes before the rule, as for every code. Route (b) (46221)
      and route (d) are unchanged.
  - The installed release on the pins' texts (studio.validation.engine.assess, driven as tests/test_harness_engine.py
    drives it, on an archive of c2e53f8e):
    - with the pins' own wording, "was given by me", it holds 99152 with performed_status on all three: 8 minutes with
      no observer, the 3-year-old, and the control (25 minutes, an observer, an adult);
    - with "was performed by me" in the same three texts, it READYs 99152 on all three, the 8-minute sedation and the
      3-year-old included. It also READYs 99153 alone on a 19-minute sedation (99153 needs 23 or more), and 99152 with
      99153 on the 25-minute one;
    - finding 19's fuller document gives the same answers.
    - D80 holds all six texts. This difference is recorded, not matched. The installed release reads sedation through
      performance cues and checks neither the 10-minute floor, the observer, the age band nor 99153's 23 minutes. D80
      checks none of them either, so it never READYs.
  - A held pair changes question. At a4dcbea72, 99152 and 99153 proposed together were each held by competing_codes
    (one sedation event). Now each is held by its own performed_status question (E* is empty, so they no longer
    compete). An add-on with its primary is not a competition, and c2e53f8e never asks competing_codes there either: it
    holds both with performed_status, or READYs both.
  - Cost on FRESH-2 (f2r3-families against f2int3).
    - The summary is unchanged: A 96/6, B 177/15, C 167/19 plus 4 dropped_question and 2 safe_hold.
    - 6 of 486 rows change. All are 99152, all are expected NOT_READY, and all are held before and after:
      - A/note8 r1-r3: the question goes from statement_scope to performed_status (reason statement_scope to
        recognised_only);
      - B/fb16 r1-r3: the reason goes from not_documented to recognised_only; the question was performed_status
        already.
    - 0 of 179 runs and 0 of 179 inventories change. 6 of 179 assessment files change, only in their 99152 proposal.
    - The head-to-head (h2h.json) is identical to a4dcbea72's in every key.
    - The replay pins do not move.
  - Pins: tests/test_interpretation_r3_families.py RecognisedOnly:
    - test_d80_only_the_sedation_codes_are_recognised_only: the predicate over the catalogue; 46221 and the route (d)
      codes; the fail-closed arms (a catalogue level of recognised or unsupported, no entry, a profile not supported);
    - test_d80_finding_19_eight_minutes_with_no_observer_is_held, test_d80_finding_19_a_three_year_old_is_held and
      test_d80_the_control_twenty_five_minutes_an_observer_an_adult_is_held: finding 19's two variants and the control,
      each in both wordings, with 45378 READY beside;
    - test_d80_a_sedation_stated_not_done_is_held_never_excluded;
    - test_d80_the_add_on_alone_and_with_its_primary_are_held;
    - test_d80_the_hold_reads_the_family_not_the_document.
  - Mutation proof. Each mutant was made in its own private copy, applied exactly once and confirmed. Each pin fails
    under the mutants named here:
    - M1, the call site removed (a4dcbea72's behaviour): every behaviour pin fails, 10 failures (99152 and 99153
      READY; the denial excluded, reinstatable).
    - M2, the route check removed: the predicate pin (46221, 99151, 45305, 99223).
    - M3, only the catalogue level read: the predicate pin (profile not supported).
    - M4, only the profile flag read: the predicate pin (recognised, unsupported, no entry).
    - M5, the hold only where the code would otherwise be READY: the never-excluded pin.
    - M9, the detail without "recognised ... not assessed": the five pins that assert it.
  - Residuals, for the owner.
    - The hold's other texts keep the wording of a code whose act is in doubt. None is in this repair's files:
      - the summary sentence (assess._summary_sentence): "CPT Studio could not confirm the moderate sedation as done
        on the date of service.";
      - the rationale (wording.selected_rationale): "Status: not established as performed.";
      - evidence.support (events.support_spans): "Not checked: no documented event supports this code.";
      - the encounter's services.unsupported: "... not established as performed".
    - A sedation code the document supports (25 minutes, an observer, an adult) is now a false hold wherever the
      installed release READYs its performed wording. That is D80's accepted cost: recognised, not assessed.
    - 99151 and 99155-99157 have no profile and stay on route (d), held as unprofiled.
    - The events.py module docstring's R2 line does not yet name D80. This repair's ownership of events.py was one
      new function and its call site.

- **D81 A gi.other procedure on the date of service makes a procedure day (2026-11-10; the round-3 refutation of
  a4dcbea72, finding 20).** combination.procedure_day read only lexicon.PROCEDURAL_FAMILIES (gi.profiles
  procedure=True). So an event of gi.other, such as an office hemorrhoid banding or an anoscopy, never made a procedure
  day. The office note in question had an established office visit and "Rubber band ligation of one internal hemorrhoid
  was performed in the office today." There 99213 asked only setting and patient status, was READY once they were
  answered, and its em.same_day_coverage check said no same-day procedure was documented. The installed release holds
  99213 with separate_em ("Other GI service is documented as performed on the same date; a significant, separately
  identifiable E/M service is not established by this document."). The reason is that engine._same_day_family counts a
  procedure profile OR gi.other, fail-closed: with no code, its global period is unknown. FINAL 7.2 R8 copies that rule,
  and D20 and D21 have the inventory's procedure events feed it.
  - The rule. combination.SAME_DAY_FAMILIES is the procedural families plus gi.other, pinned equal to
    engine._same_day_family over every gi.profiles family. procedure_day reads it. Nothing else changes: the C-3
    date-of-service reading, the done and possible lists, and the undatable events' time question.
  - What the office note now gives. With the member's values, 99213 asks separate_em and carries
    em.same_day_procedure, and em.same_day_coverage is gone. With no member values, it asks setting, patient_status and
    separate_em. A banding given no procedure words is "possibly performed (its performance is not established)",
    because the procedure default belongs to the procedural families alone (contract 5.3). With its words it is
    "documented as performed". separate_em is asked in both cases.
  - Cost on FRESH-2: no row, run, inventory or assessment file changes.
    - Its 26 gi.other events are all placed off the date (22 performed and 3 planned, all verified at another
      encounter) or stated not done (1). So no recording gains a label, a possible family or an undatable event.
    - Where the cost would bite: a gi.other event whose time is not usable is UNDATABLE, so an E/M beside it asks
      event_time (C-3), as it would beside any procedure. That adds a hold and never a READY.
  - Pins: tests/test_interpretation_r3_families.py SameDayOtherGI:
    - test_d81_the_same_day_families_are_the_legacy_rules;
    - test_d81_finding_20_an_office_banding_asks_separate_em, with and without member values;
    - test_d81_finding_20_with_the_banding_words_or_an_anoscopy_examination: procedure and time words, a target at the
      anal canal, and an anoscopy examination alone;
    - controls: test_d81_the_control_an_office_flexible_sigmoidoscopy_already_asks (finding 20's control) and
      test_d81_a_banding_of_another_date_makes_no_procedure_day.
  - Mutation proof (private copies, each applied once and confirmed):
    - M6, gi.other removed from the families: the legacy pin and the 4 behaviour cases fail;
    - M7, gi.unsupported and gi.sedation added: the legacy pin fails;
    - M8, procedure_day's filter reverted with the constant kept: the 4 behaviour cases fail.
    - The two controls pass under every mutant.
  - Residuals, for the owner.
    - The inventory's derived.procedure_day (normalize._derive, normalize.py:808) still reads the procedural families
      only. For the banding it records performed [] and possible [], while the engine holds the visit. Nothing reads
      it for a decision, and changing it changes the inventory record (normalize.py is outside this repair's files).
    - NOT BUILT: an event Gemini labels not_gi (gi.unsupported) never makes a procedure day.
      - The input: the same office note with "Excision of a 1 cm sebaceous cyst on the upper back was performed in the
        office today.", read as E1 with procedure not_gi, kind other, performed and current.
      - 99213 is READY with the member's values, both at a4dcbea72 and after D81. c2e53f8e holds it with separate_em:
        its routing reads a procedure word outside the detected families ("Excision") as gi.other.
      - This is the finding's class (held turned to READY against installed), for a procedure outside GI.
      - Closing it is one more family in SAME_DAY_FAMILIES. On FRESH-2 that changes no row: of its 24 gi.unsupported
        events, 16 lie off the date, 5 are undatable (an earlier abdominal ultrasound in fb14 r1-r3 and an earlier
        cholecystectomy in two documents, each time_marker_missing), and 3 are fb13's current fluoroscopy
        interpretation (r1-r3). No document among them proposes an E/M code.
- **D80 and D81, the suites.** No existing test's expectation changed. The 12 pins are in a new module,
  tests/test_interpretation_r3_families.py.
  - The 27 test_interpretation_* modules (the replay pins among them) with test_pipeline_assess_events and
    test_readers_dispatch went from 1,015 tests on a4dcbea72 to 1,027 on the repair, all passing.
  - test_change_context_events, both guard matrices, test_guard_mutation, test_guard_static, test_overlay_differential,
    test_pipeline_api, test_retry_reading_api and test_pipeline_interpret: 165 tests passed, 3 skipped.
  - test_models_event_inventory (25) and test_peer_heading (9) passed.
  - That is every module that switches on the new chain or builds a new-path record.
  - The full Django suite was started and then stopped unfinished on a loaded host, after about 600 tests with no
    failure marker. The integration run owns it.
  - The patch applied to a fresh archive of a4dcbea72 is byte-identical to the repair tree.

- **D86 A same-event contradiction asks the contradiction (2026-11-10; the owner's head-to-head against the installed
  engine, its three dropped questions; repair workflow wf_b15fa458-ab1, patch "questions").** On three FRESH-2 rows the
  new path held the code and asked act_target ("Which lesion or site was the snare removal ... done on?") where the
  document contradicts itself, and c2e53f8e asks the contradiction (performed_status, conflict:<kind>):
  - C1CL3-001 45385: "No polypectomy was performed in the prior segment." beside the sigmoid snare;
  - W1-u30a-rel-f1-ownpassage-004 and -005 45381: "Lift: submucosal injection x2." / "Submucosal injection: Yes" beside
    a removal "without submucosal injection".
  Each code rested on an UNRESOLVED(target) relation (site_unresolved; identity_unresolved) whose STATEMENT is the
  denial, and FINAL 7.4 h3 asked the fact of the attribute (events.RELATION_FACTS: target -> act_target). Confirmed on
  the recorded answers: all three route through events._h3_unresolved.
  - The rule. In _h3_unresolved, for a CODE, an UNRESOLVED relation whose statement is a denial asks whether that
    statement applies to the act: fact statement_scope, wording.scope_question / scope_reason naming the statement's
    own words and the act, whatever attribute the relation rests on (target, time, performer, technique, status, kind,
    procedure). A denial is a statement whose status is not_performed in ANY state (v4's "This time as well." is
    not_performed with negation_missing), or whose own status words carry a recorded negator (verify's negation_marker
    literal; normalize records it only on a not_performed status, so on every inventory it makes this arm adds nothing to
    the first). A doubt (uncertain), a planned act a claim names and a positive event (Gemini's claim that two acts are
    one) keep the question of their attribute. Only the question changes: status, bucket, READY and the exclusion are
    untouched, and the fingerprint (FINAL 7.11, the events read) does not move.
  - Not applied to focus_question (FINAL 7.8: the service-scope question about an event no code depends on; ``code``
    ''). Built literally (both callers), D86 DROPPED a genuine question on FRESH-2: C2MEM-031 r1's "Was the dilation
    (balloon) at the anastomosis (“was inflated sequentially”) done at this encounter?" (completeness "3 open questions"
    -> "2"). coverage.in_doubt_questions asks one question per (family, fact), and the family's codes (45385, 45390) now
    ask statement_scope. The registry's own reason for that document asks "a targeted question on 45386" for that
    dilation. So the in_doubt event's question stays as at a4dcbea72. C2CL-013's UNRESOLVED(scope) question is
    unchanged (statement_scope before and after).
  - Cost measured (FRESH-2 re-scored as f2r3-questions against f2int3; head-to-head h2h/compare.py against
    c2e53f8e's results-installed-h2h.json):
    - 486 code rows: no 'got', status or bucket changes. 34 rows change their question only: 28 act_target, 5
      performed_status (A/v4 r1-r3, C1CL2-002 r1, C2CL-008 r1; UNRESOLVED(status)) and 1 technique (A/note8 r3 45385) ->
      statement_scope. 0 of 179 inventories and 25 of 179 assessments differ, and every differing path is one of those
      34 proposals' clarification (fact, question, reason), support.detail or service.status / events.match /
      events.relation detail. No encounter clarification, completeness or summary moves.
    - Head-to-head, all 486 rows and runs: exactly 3 change, C1CL3-001 r1 45385 and ownpassage-004 / -005 r1 45381,
      dropped_question -> correct. Run 1, C: 118 correct / 13 false_hold / 3 dropped_question / 2 safe_hold -> 121 / 13
      / 0 / 2. worse_r1 8 -> 5 (exactly those three leave it); better_r1 unchanged (69); A and B unchanged; 7 unstable
      rows, unchanged.
    - **STOP by the letter, for the owner: score_fresh's own verdict.** The FRESH-2 summary's C goes 167 correct / 4
      dropped_question -> 165 / 6. The two new rows are C1CL2-002 r1 45385 and C2CL-008 r1 45385, correct ->
      dropped_question. D86's "whatever attribute" moves their UNRESOLVED(status) question (a contradiction Gemini
      claimed and opened both statuses of) from performed_status, which the expectation lists, to statement_scope.
      score_fresh.verdict has no EQUIVALENT, so it scores statement_scope as not asking performed_status, exactly as it
      already scores C2CL-013 at a4dcbea72. The head-to-head, which applies the owner's adjudication (statement_scope
      asks what performed_status and conflict:<kind> name), keeps both correct. FRESH-1 (fresh-frozen, pristine vs this
      patch): the same two rows and only them (C 161 / 4 -> 159 / 6), 36 rows' questions move, no got or status change,
      no encounter clarification. FRESH-1's head-to-head moves exactly the same three rows to correct. Its one false
      READY at a4dcbea72 is unchanged.
    - The measured alternative, not built: leave the performed_status attributes (status, kind, part_of) out of D86.
      FRESH-2 summary unchanged (C 167 / 4 / 19 / 2), head-to-head identical (the same 3 rows), 29 rows' questions move.
      v4, C1CL2-002 and C2CL-008 then keep "Was the snare removal (…) done on the date of service?", which quotes no
      denial. Mutant 7 below is exactly this alternative.
    - Replay pins: tests/test_interpretation_replay.py passes. D86 reads after normalization, and no MANIFEST pin moves.
  - Pins: tests/test_interpretation_r3_questions.py (14 tests).
    - RecordedRows, on the committed FRESH-2 answers read and assessed as score_fresh.py does:
      - C1CL3-001, ownpassage-004 and -005: the three rows, statement_scope quoting the denial and the act;
      - C1CL2-002: UNRESOLVED(status);
      - v4_this_time_as_well r1: a not_performed statement with no negator;
      - C2CL-013, the control the spec names.
    - SyntheticPairs:
      - the prior-segment denial/act pair;
      - the lift-row pair;
      - a not_performed statement whose words hold no negator;
      - one subtest per attribute: time, performer, technique, status and kind.
    - Boundaries:
      - a doubt keeps act_target and event_time: a clip statement of no stated purpose meets the hemostatic clip of
        45382 by their one Gemini kind and is no candidate of the code, so h3 decides; its denial twin asks
        statement_scope;
      - a positive claim keeps act_target;
      - the negator arm, on a stored record whose status value was replaced by 'planned';
      - the in_doubt dilation's service question keeps event_time beside a 45385 asking statement_scope.
    - One existing expectation moves: tests/test_interpretation_events.py Focused.test_h3_unresolved_time. Its
      denial with an unknown time now asks statement_scope ("Does “No polyp was removed” apply to the snare removal");
      it asked event_time.
    - Suites: tests.test_interpretation_* with test_pipeline_assess_events and test_readers_dispatch went from 1015
      tests to 1029, all passing. Before test_h3_unresolved_time moved, it was the run's one failure. The 14 other
      new-path modules (the four guard modules, test_pipeline_interpret, test_pipeline_api, test_retry_reading_api, the
      two harness pipelines, test_services_second_review, test_change_context_events, test_models_event_inventory,
      test_overlay_differential, test_peer_heading): 327 tests pass, 3 skipped (the legacy guard matrix's c2e53f8e
      baseline tree).
  - Mutation proof: 8 private copies, each differing from the work copy in events.py only. Each edit's anchor
    occurred exactly once and was confirmed applied. The pins' results, per mutant:
    - M1, the change undone (events.py byte-identical to a4dcbea72's): 18 failures. These are every D86 pin and
      test_h3_unresolved_time. The controls pass: C2CL-013, the claim, the doubts' uncertain rows, the planned row with
      no negator.
    - M2, focus_question reached too (the literal reading): 1, the service-question pin.
    - M3, the negator arm removed: 1.
    - M4, a doubt counted as a denial (verify.NEGATIVE): 2, the doubt rows.
    - M5, every statement a denial: 4: the claim, the two doubt rows, the planned row with no negator.
    - M6, the target attribute only: 10.
    - M7, the performed_status attributes left out: 5: C1CL2-002, v4, the no-negator pair, and the status and kind
      subtests.
    - M8, the denial read from the act, not the statement: 2, the two no-negator pins. This mutant survived the first
      pin set, whose denials all carried a negator. The v4 pins were added for it.
  - Recorded residuals and points for the owner.
    - (a) coverage.in_doubt_questions' (family, fact) dedup can still drop a service question beside D86. Probe:
      - the in_doubt event is a rectal biopsy whose status words do not bind ("were obtained" in "Biopsies were taken
        from the rectum."), so it is not done and not listed as not covered;
      - its only relation is UNRESOLVED(scope) against "Biopsies were not taken." (all_of_kind, quantifier_missing);
      - the encounter also holds a 45385 beside the prior-segment denial.
      At a4dcbea72 its service question "Does “were not taken” apply to the forceps biopsy at the rectum (“Biopsies”)?"
      is asked, and completeness says 2 open questions. Under D86, 45385 asks statement_scope and the biopsy's question
      is deduplicated away: 1 open question. FRESH-1 and FRESH-2 hold 0 such cases. Closing it needs the dedup (assess.py
      `asked`, coverage.in_doubt_questions) to compare the question, not the (family, fact) pair. Those files are
      outside this patch.
    - (b) "Whatever attribute" also replaces the ACT's own attribute question where the act's side is the unknown one.
      Probe: C2MEM-031 r1's frozen answer with 45386 proposed on "The balloon was inflated sequentially to 12 mm".
      - The denial "No dilation was carried out" is verified as 2024's.
      - The relation is UNRESOLVED(time) only because the dilation's own time is current_unanchored ("Those were the
        findings at her index colonoscopy.").
      - At a4dcbea72, 45386 asks "Was the dilation (balloon) at the anastomosis (“was inflated sequentially”) done at
        this encounter?"; under D86 it asks "Does “No dilation was carried out” apply to the dilation (balloon) at the
        anastomosis (“was inflated sequentially”)?".
      - compare.py's EQUIVALENT does not read statement_scope as event_time. Built as the spec says.
    - (c) A doubt keeps the misdirected question D86 removes for denials. "It is unclear whether a clip was placed in
      the prior segment." beside "Oozing at the biopsy site was controlled with a clip." asks of 45382 "Which lesion or
      site was the bleeding control (“was controlled with a clip”) done on?". The spec says DENIAL. FRESH-1 and FRESH-2
      hold no UNRESOLVED relation with an uncertain, planned or positive statement: all 241 on FRESH-2 are not_performed.

- **D82 The switch-back's since never reaches across a completed switch-back to its target (2026-11-10; refutation
  round 3, finding 13; amends D65).** D65 took the earliest of every earlier successful app receipt of this revision
  that replaced the same target, with no bound at a completed switch-back (D59's residual had prescribed one). In the
  documented cycle - app R1 replaced OLD (10:02:30); a switch-back completed (10:07) and OLD served alone; OLD's own
  worker wrote e2's record (10:20: an unknown outcome, or a failed request followed by a different one); app R2 replaced
  OLD again (10:30: "To come back to this revision, run app again") - the next switch-back read R1's 10:02:30 and refused
  on e2, a record the target wrote under its own rules. 'outcome' clears only with a member's addendum, and the since
  stayed pinned at R1, so every later record the target wrote while serving alone blocked again. Now replaced_since
  reads only the app receipts written after this revision's newest successful switch-back to that target: the receipt
  the target is read from, and every successful app receipt naming the same target (D65's set, bounded).
  - Receipts are ordered by the stamps their names carry (write_receipt; main's lock runs one phase at a time on one
    receipts directory). A receipt whose order cannot be told is counted (fail-closed).
  - No bound: a switch-back that did not complete (refused at B7, D65's recovery), one to another target, another
    revision's. So D65's case and its pin are unchanged.
  - When the receipt the target is read from is itself older than that switch-back (no successful app has replaced the
    target since: a later app failed, or replaced another revision), the since is the switch-back's own started_at:
    never across it, and every record after it counts.
  - D59's fallback for a receipt that records no time, and the B4 and B7 closes' own since, are unchanged.
  - Measured, BlueGreenWorld through the real install.main: finding 13's sequence, with 'unknown' and with 'outcome':
    refused (exit 1, touched_since 10:02:30) -> completes (exit 0, touched_since 10:30:00, all four touched reads at
    10:30:00). Control: a record written at 10:52, after an app at 10:50, still refuses (touched_since 10:50:00). On
    the 13 real app receipts of /home/claude/cpt-studio-install-20261023 (read-only, docker never called; no
    switch-back receipt exists on this host), the target and the since are unchanged for 13 of 13 revisions.
  - Cost: refusals are relaxed only for records written between a completed switch-back to the target and the next
    successful app that replaced it.
  - Pins, all in ops/test_install_bluegreen.py SwitchBackRound3Tests:
    - test_d82_records_the_target_wrote_while_it_served_after_a_completed_switch_back_never_refuse: finding 13's
      sequence through install.main, both reasons, and the control.
    - test_d82_only_a_completed_switch_back_to_the_same_target_bounds_the_since: a failed switch-back, one to another
      target and another revision's do not bound; a later completed one does.
    - test_d82_a_receipt_older_than_that_switch_back_gives_the_switch_backs_own_start.
  - Mutation, each in a private copy differing from the work copy in one file:
    - no bound (mut-1): the 3 D82 pins fail, and finding 13's refusal is reproduced;
    - install.py as at a4dcbea72 (mut-11): they fail too.
  - Residual: a later app over the target that failed once its switch had finished, and was not run again, does not
    count (D82 counts successful receipts only). The since is then the switch-back's start, so what the target wrote
    between the switch-back and that app is still named. This is fail-closed; see D83, residual 2.

- **D83 After a same-revision re-run, the switch-back returns to the pair an earlier app replaced (2026-11-10;
  refutation round 3, finding 14).** phase_switch_back took its target from the newest successful app receipt only.
  After any same-revision re-run, that receipt names this revision, so switch-back refused "there is nothing to switch
  back to" for good, while OLD's image was present and an earlier receipt named OLD. The re-runs are:
  - a provider-mode switch;
  - an access check run again;
  - the re-run a failed app's receipt asks for once its parked pair is removed.

  This was pre-existing (c2e53f8e gives the identical refusal). But D51 made switch-back the only post-success way back
  to c2e53f8e on live-shaped data: rollback-app's conservative read refuses on the 24 legacy encounters D51 measured.
  Now switch_back_target, when the newest successful receipt replaced this same revision, reads the target from the
  newest app receipt of this revision written since its last successful switch-back (to any target) that names another
  revision whose image is still present. A receipt whose image is gone is passed over. With none, there is still
  nothing to switch back to, and the message keeps its words. The since is read from that receipt: its own started_at
  plus D82's set.
  - Finding 14 (b) needs a receipt that is NOT ok. The first app over OLD installed its pair, its recompute failed, and
    its receipt's recovery was followed. Its receipt is the only one naming OLD.
    - So a not-ok receipt counts here when it records the web it replaced (replaced_web).
    - Only a switch that finished records one: S5's retire_live_web, or a swap's park, followed by a failed recompute,
      a failed removal of the parked pair, or a failed access check.
    - An undo, the S4 keep layout and an S5 failure record none, so after them there is still nothing to switch back
      to. INSTALL.md says that rollback-app is then the way back.
  - Measured, through install.main:
    - (a) refused -> switched back to OLD, touched_since 10:02:30 (R1's start, so R2's window counts);
    - (b) refused -> switched back to OLD, touched_since 10:02:30 (the failed first app's start);
    - a reinstatement written at 10:05 under R1's pair, before the re-run at 10:10, refuses the switch-back
      (touched_since 10:02:30), as it must;
    - the 13 real receipts: unchanged (none records a same-revision re-run).
  - Pins, in SwitchBackRound3Tests:
    - test_d83_a_same_revision_rerun_switches_back_to_the_pair_the_earlier_app_replaced: finding 14 (a);
    - test_d83_a_failed_first_app_recovered_and_run_again_switches_back_to_the_pair_it_replaced: finding 14 (b);
    - test_d83_the_since_is_read_from_the_receipt_the_target_is_read_from;
    - test_d83_the_target_is_the_newest_receipt_since_the_last_switch_back_naming_another_present_revision: a gone
      image, an undo's receipt and another revision's receipt are passed over; the newest qualifying receipt is read;
    - test_d83_a_receipt_before_the_last_switch_back_is_never_read_and_with_none_nothing_is_switched, through the phase
      too: nothing is started or stopped.

    SwitchBackTests' "the same revision" refusal is unchanged.
  - Mutations:
    - no fallback (mut-2): 5 D83 pins fail;
    - successful receipts only (mut-3, the spec's literal word): the (b) pin and the newest-receipt pin fail;
    - the since read from the newest successful receipt (mut-4): (a), (b) and the since pin fail, and the 10:05
      reinstatement goes through;
    - no switch-back bound (mut-5): the bound pin fails;
    - no image check (mut-6): the newest-receipt pin and the bound pin fail.
  - Residuals:
    1. Path P, to the owner. With D82 counting successful receipts only, (b)'s failed first receipt drops out of the
       since once a later successful app names the same target.
       - Input: A0 over OLD (10:02:30) fails at its recompute, and its parked pair is removed. A0' (10:10) re-runs.
         Switch-back SB1 (10:20) is refused at B7: a reinstatement was written on this revision's web during its drain
         (10:21). The parked pair is removed, and app A1 (10:30) replaces OLD.
       - Result: switch-back SB2 (10:40) reads since 10:30 and completes. The standing reinstatement is handed to
         c2e53f8e, D59 finding 11's harm.
       - a4dcbea72 refuses both SB1 and SB2 ("nothing to switch back to").
       - Closing it means also counting, in replaced_since, a not-ok receipt that records the replaced web of the same
         target: the receipts D83 reads targets from. It has been built and measured separately (patch-alt-over-patch.diff:
         ops suite 651/651, the path-P pin included). It changes three expectations: D65's 'failed' row becomes an undo's
         receipt; the D82 older-receipt pin's since moves 10:07 -> 10:30; and the D84 doc phrases.
    2. The D82 residual above (a failed-once-switched app after a completed switch-back) is closed by the same change.
    3. A receipt whose image is gone is passed over, as the spec words it. So the target can be older than the pair
       actually replaced when that image was removed by hand.
       - Input: R1 replaced OLD; Q was installed over R; R2 replaced Q; Q's image was removed; R3 re-ran.
       - Result: switch-back returns to OLD. The since covers Q's tenure (fail-closed on hazards), but the site lands on
         OLD.
    4. Pre-existing: the target comes from the newest successful receipt even when it is older than a completed
       switch-back to its target and a later failed app replaced another revision.
       - Input: R1 replaced OLD; a switch-back completed; Q was installed over OLD; R2 over Q failed once its switch
         finished; the parked pair was removed.
       - Result: switch-back returns to OLD. Its since is that switch-back's start (fail-closed on hazards).

- **D84 INSTALL.md states the switch-back's since and target as they are read (2026-11-10; refutation round 3, finding
  15).** INSTALL.md (Switching back) and the phase_switch_back docstring still stated D59's rule ("the one the same app
  receipt records for its phase (its started_at)"), while D65 read the earliest receipt naming the target. Both now state
  the rules as replaced_since and switch_back_target read them.
  - The since: "the earliest started_at of the app receipt the pair is read from and of every successful app receipt
    of this revision that replaced the same pair - counting only those written after this revision's last successful
    switch-back to that pair". It never reaches across that switch-back. When the receipt is older than it, the time is
    the switch-back's own started_at.
  - The target after a same-revision re-run (D83), including when there is nothing to switch back to.
  - The phases paragraph and the replaced_since and switch_back_services docstrings are updated the same way.
  - Existing test changed: InstallDocTests.test_d59_switching_back_states_its_since_the_approved_reinstatement_and_the_
    rollback_limit. Its since phrase becomes "`switch-back` to that pair (DECISIONS D59, D65 and D82)" plus "Never the
    current containers' creation".
  - Pin: SwitchBackRound3Tests.test_d84_install_md_states_the_since_and_the_target_as_they_are_read. It also checks
    that D59's wording is gone.
  - Mutation: INSTALL.md as at a4dcbea72 (mut-7) fails the D84 pin and the changed D59 pin.

- **D85 A reconciliation note is never read as a retry release (2026-11-10; refutation round 3, finding 16; amends FINAL
  11.3, D52 and D60).** FINAL 11.3 writes the release on the run's reconciled_by, reconciled_at and
  reconciliation_note and queues 'interpret:...:retry:<run>'; that wording is superseded here. released_for_retry read
  reconciled_at plus reconciliation_note == RETRY_RELEASE_NOTE as a release. That
  column also holds an operator's free text, stored unchanged after strip() (operator.py), so a reconciliation note
  reading exactly 'released for one retry' counted as a release. No retry had run, and no 'interpretation.retry' audit
  row existed. Two probes showed the cost:
  - Probe A: the next upload of the same text sent again (1 send, provider 'succeeded').
  - Probe B: a member's retry, after the after-reconcile reading overran, sent again (1 send), where D60 promises 0.

  Now:
  - released_for_retry reads only the system-written 'retry-release:<run>' stage key, on any run carrying the answer.
  - retry_reading keys every release 'retry-release:<run>'. That includes a run nobody had reconciled, which until now
    was keyed 'retry:<run>' and released by the note.
  - On such a run it still writes who and when (RETRY_RELEASE_NOTE) as the record of the act. That record is never
    read.
  - A retry that releases nothing keeps 'retry:<run>' (D60). So does a second ask after a stopped release, where the
    release stands on the first stage's key; before, that ask was the first key plus ':resume:'.

  No other marker is needed: D52's path already releases by this key.
  - Measured on synthetic probes through the real operator and member doors, a4dcbea72 -> the repair:
    - Probe A: 1 send -> 0 (reused), with the note exactly as written and padded with spaces;
    - Probe B: 1 send -> 0 (reused).
    - D52's sequence and D60's measured paths are unchanged (their pins pass).
  - Cost:
    - A release a4dcbea72 wrote for a run nobody had reconciled (the note plus a 'retry:<run>' stage) is no longer a
      release. Such a stage, not yet run, stops at the failed-before door with nothing sent. The next retry releases
      the run under 'retry-release:<run>', keeps the note it finds, and sends once. This fails closed and is pinned.
      Production holds no interpretation run (c2e53f8e has no interpreter).
    - A release now exists only as a Job row, as D52's path already did. No code deletes Job rows, and their foreign
      keys are PROTECT. A release whose stage row were gone would read as no release: it fails closed.
  - Existing tests changed, because the release is now the key:
    - test_pipeline_interpret ReuseTests.test_p2_a_run_released_for_retry_is_never_reused: the release is set up as
      its 'retry-release' stage, not as a note.
    - FailedBeforeAndRetryTests.test_a_failed_reading_is_not_sent_again_until_a_recorded_retry_releases_it: the key
      is 'retry-release:<run>'.
    - FailedBeforeAndRetryTests.test_one_release_is_one_attempt_and_a_retry_that_fails_again_blocks_again: the
      second ask is 'retry:<run>'.
    - test_retry_reading_api MemberRetryTests.test_a_reviewer_retries_a_failed_reading_once_and_it_is_read: the key
      is 'retry-release:<run>', and the module docstring now says so.
  - Pins, in test_retry_reading_api OperatorNoteIsNoReleaseTests:
    - test_d85_probe_a_an_operators_note_reading_released_for_one_retry_leaves_the_stored_answer_reusable (both note
      forms);
    - test_d85_probe_b_a_members_retry_after_the_reading_overran_reads_the_stored_answer_again;
    - test_d85_only_the_system_written_retry_release_stage_is_a_release;
    - test_d85_the_release_of_a_run_nobody_reconciled_is_its_retry_release_stage;
    - test_d85_a_release_written_only_as_the_note_is_none_and_the_next_retry_releases_it: the cost.

    D52's and D60's pins pass unchanged: ReconciledRetryTests (2), and UnreadAnswerRetryTests in both modules (3 and
    2).
  - Mutations:
    - the note read again (mut-8): probe A (2 sends, provider 'succeeded', in both forms), probe B (2 sends), the
      stage pin and the cost pin fail;
    - an unreconciled release keyed 'retry:<run>' again (mut-9): the writer pin and the 3 changed retry tests fail;
    - jobs.py as at a4dcbea72 (mut-10): 9 fail.

    The D52 and D60 pins pass under all three.
  - Residual: two jobs.py module comments still describe D60's split, where only a reconciled run's release is keyed
    'retry-release'. They are the interpret-stage key list (about line 1767) and the comment above RETRY_RELEASE
    (about line 1800). Both lie outside this repair's ownership and are left for integration.

- **Round-3 integration (2026-11-10; commits 62d5bf0dd, the seven patches as built, and 732d172d2, D87-D95).** The
  independent review of each patch reproduced side effects in four of them. They are repaired at integration, where
  they cross the patches' file ownership. The entries above are the builders' own, and D86's and D82's scopes are
  amended by D91 and D95 below.
  - **D87 A possible examination is a doubt, never a fact.** Session.examinations holds the DONE examinations;
    D62's possible ones are Session.possible, and unresolved/event still count them. relations' unresolved sessions
    count verified current examinations again. A session left unresolved only by possible examinations keeps its one
    done examination's C3/C-4 structure. Reviewer inputs, each fixed:
    - 43253 READY on a 'Previously, the linear echoendoscope showed ...' examination's target;
    - conflict:stent never asked beside 'At the original ERCP, ...';
    - 43235 asked its extent instead of base_included beside an aside EGD.
  - **D88 The lower tract comes from every DONE EUS event; a possible one is never lower evidence.** This fixes two
    inputs: a radial EUS naming no place whose done FNA samples a perirectal node (the EGD keeps its item); and a
    possible rectal aside that cancelled D70's doubt, so 43235 was READY beside 43242.
  - **D89 Questions are never displaced.** A merged unresolved item keeps every in_doubt event's question. A code's
    question suppresses a service question only when it is the same question, fact and words.
  - **D90 D76 keeps two lesions not established distinct a doubt.** The injection-plus-clips hemostasis of the
    'polypectomy site' was READY.
  - **D91 D86 reaches the TARGET attribute only.** On every attribute, D86 moved the performed_status questions the
    expectations name (C1CL2-002 and C2CL-008 r1, FRESH-A v4) and a time question the act really lacks.
  - **D92 date_unchecked never fails the deny path's default.**
  - **D93 A reach entry naming no landmark keeps its 'incomplete'.**
  - **D94 The same-day E/M rule counts gi.unsupported.**
  - **D95 The switch-back since counts every app of this revision that served after the last completed switch-back:
    a successful one, or one that parked any role.** This closes path P (a failed first app) and an app undone after
    its switch. D65's narrower reading is superseded, and D59's and D65's since tests move with it.
  - **Measured on 732d172d2.** FRESH-2 with score_fresh, which now applies the statement_scope adjudication: A 96/6,
    B 177/15, C 171/19 plus 2 safe_hold. There are 0 false READY, 0 false exclusion and 0 dropped questions; the
    replay pins are unchanged.
  - **The head-to-head, run 1.** The new path is 214/234 correct (A 34/34, B 59/64, C 121/136); the installed engine
    is 150/234, with 16 false READY and 2 on the wrong facts. The new path is worse than the installed engine on 5
    rows, all holds (fb03 45385; fb12 43242, D40's cost; guard-bolus-005 43247; PAIR-5-W3 45385, D42's cost;
    p20-xexcl-003 45388, a safe hold).
  - **Recorded residuals of round 3:**
    - D67(a) discards an examination's reach while its time is date_unchecked, and the re-judged time does not
      re-attach it: 45380 is asked the extent, and the installed engine holds it too.
    - D67(b) re-judges earlier and future times too, so a member's date can EXCLUDE a held code as historical (the
      document and the installed engine agree). A document date that conflicts with the member's leaves the date
      None, and an excluded code becomes held.
    - Pre-existing: an upper EUS-FNA, an EGD and a rectal EUS all done today leave the EUS session unresolved, and
      43235 is READY beside 43242 (C-4's "any lower examination means no upper EUS").
    - D70's hold reuses base_within's legacy sentence, which states the inclusion as fact.
    - D75's "every family" arm is not built. An act with an absent procedure sits in no session, so a base code
      stays READY beside it in constructed inputs, as at a4dcbea72. The measured alternative (claims-base alt-full)
      moves no FRESH-2 row.
    - Wording: "could not confirm ... done at this encounter" and "(stated in doubt)" are also used for doubts that
      concern only the procedure.
    - D78 is scoped to the adjunct arm (Context.places every=True). The blanket reading made two held codes READY.
    - derived.procedure_day still reads only the procedural families (nothing decides on it), and a procedure Gemini
      leaves 'unknown' (family '') makes no procedure day.
    - Pre-existing: S3's undo lets the previous web show, for a window, a reinstatement written through this
      revision's web.
    - FINAL 11.3 still names the note as the release (D85 amends it; jobs.py's comments are corrected).
- **The integration pins (wf_24489238-cc1, 2026-11-10) and two amendments.** Four agents pinned D87-D94 from the
  reviewers' own inputs, in four new modules tests/test_interpretation_r3_integration_*.py. Every pin passes at
  732d172d2 and fails with its decision undone (5 mutants for D87, 3 to 4 for each of the others). The agents found:
  - **D93, amended.** With the unplaced entry FIRST, the stated reach after it overwrote the kept 'incomplete' and
    43259 stayed READY. The attaching arm now never overwrites an 'incomplete' already attached by another
    completion. Pinned, and mutation-proved.
  - **D94, amended.** An act whose procedure Gemini leaves 'unknown' (family '') is a POSSIBLE same-day procedure,
    labelled 'A procedure CPT Studio could not identify': the office excision read so asks separate_em, as the
    installed release holds it. Pinned and mutation-proved. FRESH-2: 0 rows moved; replay pins unchanged.
  - **A correction to 732d172d2's message:** "coverage still holds every code of that session" overstates it. An
    unresolved session asks the codes that read its examination (extent, class). A code whose own act is verified
    today is decided on that act: the stent placement beside a possible 'At the original ERCP, ...' examination with
    no denial is READY, as with no aside.
  - **Residuals, not repaired:**
    - D89 keeps FINAL 7.8's one service question per (family, fact). Two in_doubt acts of one family that lack the
      same fact give one question, as at 62d5bf0dd and a4dcbea72.
    - D92 restores a4dcbea72's deny path. Gemini's time words that do not locate (say 'On 03/14/2024', on an
      undated EMR line) store nothing, so a member's date cannot re-judge them and the act is READY on the
      document's own undated words. The installed engine reads only the document text and gives the same READY.
    - D87 keeps D62's extent question on a session left unresolved by a possible examination (45385 asks
      conflict:snare and extent): an accepted fail-closed cost.
  - **Final integrated measurement:** engine suites 1217 OK. FRESH-2: A 96/6, B 177/15, C 171/19 plus 2 safe_hold.
    Head-to-head run 1: 214/234 against installed 150/234; worse on 5 rows, all holds.
