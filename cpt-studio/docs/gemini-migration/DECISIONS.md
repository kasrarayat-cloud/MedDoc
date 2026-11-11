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
- **S17 refutation round 4 (wf_02819328-bf3, 2026-11-10/11; 7 lenses over a4dcbea72..437b708bb, with a
  plausibility rule and an explicit severity scale): 27 findings, 25 confirmed (8 critical, 5 high, 9 medium, 3
  low).** The full suite on 437b708bb passed.
  - Critical: #0 a digital rectal examination or a rectal medication filed under the EUS heading made the EUS lower
    and 43235 READY; #7 a removal of unknown time stopped holding its biopsy; #10 an EUS examination whose kind is
    unverified was skipped by C-4; #13 an in-office banding Gemini files under the visit was invisible to the same-day
    E/M rule; #14 'earlier in the day' read OFF the date; #22 an ERCP stent exchange gave 43275 and 43274 both READY;
    #24 enteroscopy codes had no class check; #25 a balloon sweep that retrieved nothing made 43264 READY.
  - High: #1, #3, #8, #11, #23.
  - Medium: #4, #5, #12, #15, #16, #18, #19, #21, #26.
  - Low: #2, #6, #20.
  - #9 and #17 were not confirmed.
  - The stopping rule is not met. Repair workflow wf_e3e33bee-05a builds D96-D110 as seven patches (eus-lower,
    currency-pairing, questions, ercp, enteroscopy, em-same-day, ops), each with a reviewer. In parallel, four auditors
    compare the installed engine's rules with the new path family by family (colonoscopy and sigmoidoscopy, EGD, EUS,
    and the cross-family modifiers and review rules), so that the remaining parity gaps are enumerated rather than
    found one refutation round at a time.
  - Recorded, not repaired:
    - #5: a true denial of another site's dilation asks statement_scope for both site codes, where the installed
      engine asks conflict:dilation. Both hold, and both ask the contradiction.
    - #18 and #19: false refusals of the switch-back after an undone app or across another target's switch-back.
      Fail-closed; a refusal never hands a record to the previous revision.
- **D96 C-4 reads the lower tract only from today's done endoscopic EUS examinations and done EUS acts of the EUS's own
  kinds whose procedure is usable, and an act's verified target words place it too (2026-11-11; the round-4
  refutation, findings 0, 2 and 12; amends D88).** D88 read every done EUS event with a usable kind as lower-tract
  evidence, and read an act only at its verified landmark.
  - Finding 0 (critical). A digital rectal examination filed under the EUS heading made the EUS session lower. It used
    the attested C2MEM-029 r1 E9 form: kind examination 'digital rectal examination', technique manual, target the
    rectum, the frame defaults, procedure 'eus' from 'EGD AND ENDOSCOPIC ULTRASOUND (EUS) REPORT'.
    - C-4 switched off, and 43235 was READY beside 43242 (complete_pending_review; the read-time overlay agreed).
    - With no proposal, the EGD's own no_proposal item invited a second review to add 43235.
    - The same happened with today's EUS only possible ('After the EGD, ...'): the DRE cancelled D70's doubt.
    - It also happened with a rectal medication read as an EUS event of kind 'other' ('Rectal indomethacin 100 mg was
      administered before the procedure.').
    - c2e53f8e and 62d5bf0dd hold 43235 base_included on every text. D69 had excluded the digital examination, and D88
      dropped that filter without recording it.
  - Finding 2 (low, off-contract). A done rectal act whose family is in doubt did the same: 'Random biopsies were taken
    from the rectum.' under 'Colonoscopy: ...', given 'eus' with no words (procedure_unsettled, D75). c2e53f8e holds
    43235 base_included.
  - Finding 12 (medium). D88's own sentence, with the FNA's target at the verified landmark 'lymph_node' ('a perirectal
    lymph node in the rectum'), was read nowhere lower, because 'lymph_node' maps to the region 'node'. That target is
    on contract and was attested live in the S17 walk (gi-09).
    - The EGD became the radial EUS's endoscopic portion, and its own no_proposal item and second-review mark were
      dropped.
    - 43235 alone was held base_included on a false premise.
    - c2e53f8e lists both items and gives 43235 READY.
  - The rule. coverage.lower_evidence gives the events C-4's _lower_eus reads, in two parts:
    - (a) the EUS session's done examinations, as done_examinations gives them: never a digital or manual examination
      (FINAL 5.6 E13);
    - (b) coverage.eus_act: a done EUS act of one of EUS_ACTS, whose kind is usable and whose own procedure is usable as
      'eus'. EUS_ACTS is the catalogue's gi.eus acts besides the examination (fna, injection, drainage) and is pinned
      equal to the catalogue.
    - Never lower evidence: a kind-'other' event, a forceps biopsy, an act whose family is in doubt, or a possible
      examination (D88, kept).
    - coverage.eus_places gives where an event is placed. For an act, that is its verified target landmark plus every
      landmark its own verified target's words name (verify.landmark_words over those words, EB1's landmark literal).
    - An examination's place is still its verified landmark and its usable reach. The words of an unverified target are
      never read.
  - Pins, in tests/test_interpretation_r4_eus_lower.py:
    - test_d96_the_eus_acts_are_the_catalogues_gi_eus_acts_besides_the_examination.
    - DigitalExaminationAndOtherKindsAreNoLowerEvidence:
      - test_d96_a_digital_rectal_examination_or_a_rectal_medication_never_frees_43235_beside_43242: finding 0's DRE
        (labelled line, plain line, procedure words left empty) and the indomethacin variant. 43235 is held with C-4's
        question, at assess time and in the overlay, and 43242 is READY. The control holds the same way.
      - test_d96_with_no_proposal_the_digital_examination_leaves_the_items_of_the_control.
      - test_d96_the_digital_examination_never_cancels_d70s_doubt.
      - test_d96_controls_the_dre_elsewhere_and_c3: the finding's boundaries.
    - AnActWhoseFamilyIsInDoubtIsNoLowerEvidence:
      - test_d96_a_rectal_act_whose_procedure_is_unsettled_never_frees_43235_beside_43242: finding 2's biopsies, with and
        without 45380, and the same shape of an EUS kind (a submucosal injection).
      - test_d96_controls_the_contracts_answers_and_a_settled_eus_act: with the injection's procedure stated 'EUS', the
        act is lower evidence and 43235 is READY.
    - AnActsTargetWordsPlaceItLower:
      - test_d96_a_lymph_node_target_whose_words_name_the_rectum_leaves_the_egd_its_own_item: finding 12, at the
        landmark and through lesion L1. Both no_proposal items are kept, included_by is {}, and 43235 alone is READY with
        no base check.
      - test_d96_target_words_naming_no_lower_landmark_are_read_as_before:
        - 'a perirectal lymph node' names no lower place, so 43235 stays held. That is the legacy residual 'p2
          reports2-0c'.
        - Two unverified targets, which are landmark_conflict, are not read.
        - An examination's words are not read.

- **D97 An EUS examination whose kind is not usable is a possible upper EUS (2026-11-11; the round-4 refutation,
  finding 10; amends D70).** C-4 skipped an EUS examination whose kind words do not locate: 'EUS' or 'endoscopic
  ultrasound' cited from the act line, or the attested slip of words joined across two sentences (FRESH-1
  aside-of-twins-002/-021/-023, on EGD examinations).
    - done_examinations and D62's possible examinations both need a usable kind, so the EUS session had no examination.
    - The EGD was part of nothing, and 43235 was READY beside 43242, and beside 43259. The overlay agreed.
    - c2e53f8e holds 43235 base_included and gives 43242 READY.
  - The rule. coverage.unsettled_eus_examinations gives the C-4 doubts D97 adds. Each is an EUS-family event whose kind
    is not usable, and:
    - is an examination by its catalogue kind or by its unusable kind's value;
    - is stated performed or begun;
    - is possibly current (D62);
    - is no digital examination.
  - How C-4 reads them. They join D62's possible EUS examinations among the doubts D70 reads.
    - Unless such an examination is itself placed lower, it raises D70's doubt: the EGD gets possibly_part_of 'gi.eus',
      and combination.base_within holds 43235 base_included.
    - The EGD keeps its own items and second-review mark (D70).
    - It is never the session and never lower evidence. Session.possible, unresolved and event are unchanged: only C-4
      reads it.
  - Pins, in AnExaminationWhoseKindIsNotUsableIsAPossibleUpperEus:
    - test_d97_an_eus_examination_with_unlocated_kind_words_holds_43235_beside_43242: three kind-word forms, beside 43242
      and beside 43259, and 43235 alone. The overlay keeps it held.
    - test_d97_the_egd_keeps_its_own_item_and_second_review_mark.
    - test_d97_controls_located_kind_words_a_lower_place_and_a_plan:
      - located words: C-4 includes the EGD as before, and 43242 is READY;
      - an unusable-kind examination of the rectal wall: no doubt, and 43235 is READY;
      - a planned one: no doubt.

- **D96-D97, what was edited, and the measurement.**
  - Edited: studio/interpretation/coverage.py only.
    - New helpers beside _lower_eus: EUS_ACTS, eus_act, lower_evidence, unsettled_eus_examinations, eus_places.
    - _lower_eus now reads eus_places.
    - sessions()' C-4 block: `evidence` replaces D88's done_events, and `doubts` = D62's possible EUS examinations plus
      D97's.
    - Nothing else is touched: done_examinations, Session, the D62 list, event_coding and combination are unchanged. No
      existing test's expectation changed.
  - The module docstring is untouched. It says "no text is read ... no pattern is matched", and that sentence is now
    inexact: eus_places reads the act's own target words for a landmark literal, with the same function over the same
    words that normalize stores as the target's literals. The integration should amend it.
  - Cost on FRESH-2. f2r4-eus-lower was compared against f2r3intc, the scoring of 437b708bb.
    - The summary is unchanged: A 96/6, B 177/15, C 171/19 plus 2 safe_hold.
    - 0 of 486 rows and 0 of 179 runs differ, and all 358 inventories and assessments are byte-identical.
    - There are 0 false READY, 0 false exclusion and 0 dropped questions. The replay pins did not move.
  - The head-to-head (h2h.json) is identical to h2h-r3final.json in every leaf.
    - Run 1: 214/234 (A 34/34, B 59/64, C 121/136). The installed engine scores 150/234.
    - Worse 5, better 69, unstable 7, facts moved 0.
  - Census of the frozen answers. FRESH-1 and FRESH-2 were each normalized by the work tree.
    - Each corpus has 179 answers. 6 carry EUS events (fb12 and fb14, three runs each), giving 12 EUS events: 6
      examinations and 6 FNAs.
    - Members of every class D96 and D97 read: 0. That is 0 manual or unusable-kind EUS examinations, 0 done EUS
      examinations with an unusable procedure, 0 done non-EUS-kind EUS acts, and 0 done EUS-kind acts with an unusable
      procedure.
    - 3 EUS acts (fb12's FNA of the pancreas) are eus_act, and none of them is placed lower by its words.
    - 0 lower EUS sessions.
  - Suites:
    - the new module: 12 tests;
    - every tests.test_interpretation_* module, with test_pipeline_assess_events, test_readers_dispatch and
      test_overlay_differential: 1142 OK (437b708bb: 1130, plus the 12);
    - the 13 other modules that import the interpretation package (test_change_context_events, test_guard_matrix_legacy,
      test_guard_matrix_new_path, test_guard_mutation, test_guard_static, test_models_event_inventory,
      test_peer_heading, test_pipeline_api, test_pipeline_interpret, test_repairs_7c8_p1reports,
      test_repairs_7c8_p1sends, test_repairs_ec5_reportruns, test_retry_reading_api): 289 OK, 3 skipped, the same as
      437b708bb;
    - one earlier run of those modules failed test_guard_mutation's recompile-identity check on coverage.sessions. The
      cause was editing sessions() while that run was in flight, and the re-run on the unedited copy passes;
    - alternative A1 (residual 1): 1143 OK, that is these 1142 plus its own pin.
  - Mutation proof. Each mutant was built in its own copy of the work tree, and each replacement was asserted to occur
    once. Each was confirmed applied by its marker and a sha256 change, with the work copy's sha256 unchanged
    (a81722b00d29).
    - M0, the whole change undone (437b708bb's coverage.py): 11 of 12 tests fail or error. The DRE-boundary controls
      hold on 437b708bb too.
    - M1, the lower reader admitting the digital examination: the 3 DRE tests fail, on their DRE subtests only.
    - M2, an EUS act of any non-examination kind: the indomethacin subtests fail.
    - M3, an act's procedure not read: finding 2's injection subtests fail. The biopsy subtests still pass, because the
      kind arm holds them.
    - M4, the words arm removed: the finding-12 pin fails.
    - M5, D97 undone: both D97 pins fail.
    - M6, D97 ignoring the "placed lower" exception: the rectal control fails.
    - M7, D97 ignoring status and time: the planned control fails.
    - M8, the words arm reading an examination: its control fails.
    - M9, the words arm reading an unverified target: the pancreas-at-'...in the rectum' control fails. It survived the
      first pin set and was killed by adding that control.
    - M10, D88's lower reader restored whole: the 5 behaviour tests fail.
  - Residuals, for the owner. Each is measured on 437b708bb, the build and c2e53f8e (jobs._assess_child, empty and
    harness reference).
    - (1) DISAGREEMENT: the words arm as specified also reads a lower place named beside an act's own organ landmark.
      - Input: 'EGD: ...' / 'EUS: a linear echoendoscope was then introduced and advanced to the duodenum.' / 'A 3 cm
        pancreatic tail mass abutting the splenic flexure was sampled with a 22-gauge needle.' The FNA's target is the
        pancreas, verified, with words 'pancreatic tail mass abutting the splenic flexure'.
      - 437b708bb holds 43235 base_included beside 43242. The build gives READY (complete_pending_review).
      - c2e53f8e gives READY too, because it reads 'splenic flexure' in the EUS's documentation, but the expected
        outcome is NOT_READY.
      - Alternative A1 (alt-A1.diff, measured): read the words only where the verified landmark places the act in no
        region of its own (region '' or 'node'). It holds this input, keeps finding 12's repair, and passes all 13 pins
        plus the r3 EUS and D88/D93 modules. Its pin fails on the patch as specified.
    - (2) D96(b)'s kind list leaves out the forceps biopsy (the catalogue reads it under READ_UNDER, not as an EUS act).
      - Input: 'Radial EUS was then performed; forceps biopsies of the rectal mass were taken.' beside the EGD.
      - The build reads the EGD as the EUS's endoscopic portion. It drops the EGD's no_proposal item and mark, and
        holds 43235 alone base_included.
      - 437b708bb and c2e53f8e both give READY and keep both items.
      - This is finding 12's medium harm, reintroduced for this kind. It adds a hold and drops no READY.
    - (3) (a) reads no procedure, so a done examination whose family is in doubt is still lower evidence.
      - Input: finding 2's document with its colonoscopy EXAMINATION ('Colonoscopy: the colonoscope was advanced to the
        cecum.', reach cecum) given 'eus' with no words.
      - The EUS session is lower and unresolved, and 43235 is READY beside 43242, both at 437b708bb and in the build.
      - c2e53f8e holds it base_included.
      - This is pre-existing. It is D87's "a doubt is never a fact" left unapplied to examinations.
    - (4) C-4 reads the upper EUS from examinations only.
      - Input: an EGD and 'EUS-guided fine-needle aspiration of the pancreatic head mass was performed with a 22-gauge
        needle.', with no EUS examination event.
      - 43235 is READY beside 43242, both at 437b708bb and in the build. c2e53f8e holds it base_included.
      - This is pre-existing, with 0 FRESH members.
    - (5) 'injection' is an EUS act kind.
      - Input: a rectal medication Gemini labels 'injection' under the EUS heading (off contract).
      - It still frees 43235, at 437b708bb and in the build. c2e53f8e holds it.
    - (6) D97 is C-4's alone. The unusable-kind examination is still no session examination, so the EUS codes beside it
      read none: 43242 asks the extent, as at 437b708bb. c2e53f8e gives 43242 READY, so this is a fail-closed false hold.

- **D98 An explicit unknown time is possibly current (2026-11-11; the round-4 refutation of 437b708bb, finding 7;
  completes D62 and D68; repair "currency-pairing").** coverage.possibly_current and relations._possibly_current read
  only a current_encounter time as possibly current. So a time Gemini gave as 'unknown' was an ABSENCE for the rules
  that hold OTHER codes by an event: the removal a part is bundled into, the removal's procedural adjunct, a session's
  possible examinations (C-4, D70) and D74's claims. FINAL C6 says an explicit unknown is absent: it never supports a
  code and gives UNRESOLVED in pairing, never a match and never a non-match. FINAL risk 4 says an unknown time "holds,
  never READYs", and D68's rule as written ("only an earlier or future time is not current") already covers it.
  - The finding's input: the attested FRESH-2 answer W1-u30a-rel-f4-unread-before-017 r1, verbatim (the snare E2's time
    'unknown' worded 'Once', its performer 'unknown', Gemini's two open questions), with one added line, 'During this
    procedure, cold forceps biopsies of the polyp were taken.', and one on-contract event for it (E3: a cold forceps
    biopsy of Gemini's own L1, 'During this procedure', the documenting team).
    - 437b708bb: 45380 READY (supported, no question) while 45385 is held asking event_time. Coverage counted the snare
      as doubted, but the bundling reader read it as absent.
    - Now: 45380 is held ([performed_status], support bundled, biopsy_of_removed_lesion). 45385 keeps its own
      event_time question.
    - Installed c2e53f8e (run first-hand): 45380 held [performed_status] as part of the removal, 45385 READY.
  - The rule. Both functions: only an earlier_encounter or future time, verified or not, is not current. A time Gemini
    gave as 'unknown' is possibly current, as a current_encounter time already is whatever its reasons (D62, D68).
    Nothing else reads these functions differently: an unknown time is still absent for the act's OWN code (events.done
    and supports read verify.usable), and coverage.doubted already counted it as a doubt.
  - The same reader, the finding's siblings, each whole's time 'unknown' (worded 'Once', and with no words):
    - A lift injection beside 'Once, the lesion was removed by endoscopic mucosal resection in three pieces.': 45381
      READY -> held (bundled).
    - An EGD to D2 beside 'Once, the linear echoendoscope was introduced ...' and an FNA: 43235 READY -> held
      (base_included). The gi.eus session's possible examination is E2, so the EGD is possibly its portion (D70).
    - A lithotripsy 'Once, a 15 mm stone ... was fragmented ...' beside the balloon extraction: 43264 READY -> held
      [competing_codes], beside 43265 held [event_time, competing_codes] (D74).
    - relations' half: hemoclips for hemostasis beside 'Once, a 6 mm sessile polyp ... was removed with a cold snare.':
      the procedural_adjunct bundling identity is now recorded, and 45382 goes READY -> held [act_target] (D41).
    - The installed release holds all four on these texts.
  - Cost measured.
    - FRESH-2 (f2r4-currency-pairing against 437b708bb's f2r3intc; a re-score of a pristine copy,
      f2r4-currency-pairing-pristine, reproduces f2r3intc exactly):
      - 0 of 486 rows, 0 of 179 runs and 0 of 358 assessment and inventory files differ;
      - A 96/6, B 177/15, C 171/19 plus 2 safe_hold. There are 0 false READY, 0 false exclusions, 0 dropped questions
        and 0 READY on wrong facts.
    - The head-to-head (h2h/compare.py) is identical to h2h-r3final.json, every key: run 1 214/234, worse on the same 5
      rows, all holds.
    - FRESH-1 (fresh-frozen, pristine against this repair): 0 of 486 rows and 0 runs change. Two assessment files
      differ, and only in completeness.event_coding.sessions:
      - C2MEM-023 r1: gi.colonoscopy possible [E9] -> [E9, E13], unresolved false -> true;
      - W1S-112 r1: gi.egd possible [E5] -> [E5, E6], unresolved false -> true.
      E13 and E6 are examinations Gemini gives an 'unknown' time and an opened other_clinician performer ("All of the
      above was done by her previous gastroenterologist." / "Done by her previous gastroenterologist."). Their codes
      were already held (event_performer and extent; procedure and extent; extent), so no verdict moves.
    - The census over the 358 frozen FRESH-1 and FRESH-2 answers finds six positive acts with an 'unknown' time:
      - the attested snare, alone, with no part beside it;
      - the two examinations above;
      - a biopsy and a dilation by the previous gastroenterologist in C2MEM-023 r1, which are no wholes;
      - an 'other' act in PAR-006 r2, of no family.
  - The accepted fail-closed cost, recorded: an examination whose time Gemini gives as 'unknown' leaves today's session
    unresolved beside today's examination. This includes another clinician's earlier examination, because a session's
    possible examinations read no performer (D62). The codes that read the session's examination are then asked (extent,
    class), never READY on it. This is D62's and D68's cost, widened to unknown times. On FRESH-1 it reaches the two
    sessions above and no verdict.
  - Pins (tests/test_interpretation_r4_currency_pairing.py):
    - test_d98_the_attested_unknown_time_snare_keeps_the_biopsy_of_its_polyp_held: the committed recording, its
      request and body sha256 checked against the manifest. Three subtests: as recorded, the unknown time with no words,
      and Gemini's open questions removed;
    - test_d98_control_a_current_time_holds_it_and_an_earlier_one_releases_it: the reference. An earlier_encounter
      time still releases the biopsy;
    - test_d98_an_unknown_time_is_possibly_current_and_only_an_earlier_or_future_one_is_not: both readers, over every
      state normalize gives each value;
    - test_d98_the_lift_injection_stays_bundled_into_an_unknown_time_emr;
    - test_d98_the_egd_stays_held_beside_an_unknown_time_upper_eus;
    - test_d98_a_lithotripsy_left_unknown_still_claims_the_stone_clearance;
    - test_d98_a_bleeding_control_beside_an_unknown_time_polypectomy_is_asked: relations' half.

- **D99 A current time no date has checked yet pairs as current (2026-11-11; the round-4 refutation of 437b708bb,
  finding 8; completes D67).** On a document whose date no check establishes (not_stated, 'several', or opened by
  Gemini's own question), D67(a) leaves a current_encounter time worded with a day ('On 11/09/2026') unverified with
  date_unchecked. relations.time_row read that as UNKNOWN, and assess re-judges the times but reuses the stored
  relations (D67's recorded residual). So a same-day denial beside the act was UNRESOLVED(time) instead of a
  CONTRADICTION: h1 never fired, and the services.conflicts check said there was no conflict. A pending date check is
  not a doubt about the encounter.
  - The finding's input. An undated colonoscopy note (date_of_service not_stated):
    - 'The colonoscope was advanced to the cecum.';
    - 'On 11/09/2026, a 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.' (E2, current_encounter
      worded 'On 11/09/2026');
    - 'Impression: No polypectomy was performed.' (E3: removal, not_performed, all_of_kind);
    - the member enters 2026-11-09.
    Outputs:
    - 437b708bb: the stored relation is unresolved(time). 45385 is held asking only event_time, services.conflicts is
      pass, and completeness reads ['1 open question'].
    - Now: the stored relation is contradiction(status, same_act). 45385 is held asking [conflict:snare],
      services.conflicts is warn, and completeness reads ['1 conflict in the record', '1 open question']. The
      document's own date gives exactly the same.
    - Installed c2e53f8e: [conflict:snare] with conflicts warn, on a text with a report header so that its routing finds
      the colonoscopy. On the bare text it asks [conflict:snare, extent].
    - Same result on 'several' dates (one line and two lines) settled by the member's date, on the date line opened by
      Gemini's question and settled by the member, on the words 'On November 9, 2026', and through the production chain
      (the member's date at upload, and saved afterwards by jobs.change_context).
  - The rule. In time_row, a current_encounter time whose ONLY failure is date_unchecked pairs as current: state
    unverified, its reasons exactly ['date_unchecked'], and not opened by an open question. It is SAME against a current
    time, and DIFFERENT (another_time) against an earlier or future one. Every other unusable time stays UNKNOWN: with
    another reason beside it (current_unanchored, other_occasion), opened, date_mismatch, an earlier or future time
    date_unchecked, unknown, or discarded. The act's own code still reads its time through verify.usable (supports, h4),
    so it is held until a date decides it. The difference is never HARD: exclusion_basis reads only a usable time, and a
    date no date has checked is no literal (C-11).
  - Applied to the time ROW only, deliberately not to relations.Context's examination Counter. The Counter is also a
    time's currency deciding pairs (all_of_kind -> session_unresolved), but counting a date_unchecked examination
    there would ADD doubts (D87: it counts VERIFIED current examinations). The case: an undated note whose aside
    'On 03/14/2024, a colonoscopy to the cecum was performed.' Gemini calls current, beside the snare and 'Impression:
    No polypectomy was performed.' Counted, the aside would make the denial's pair session_unresolved and ask
    'procedure', where the document's own date (date_mismatch) asks conflict:snare. A doubt never takes another doubt's
    question (D89). Pinned, and the mutant M10 below carries D99 into the Counter.
  - The one direction that is not a hold, and it is the dated document's. Beside a denial Gemini places at an earlier
    encounter ('Previously, no polyp was removed.', verified by its marker), the unchecked day is another time
    (INDEPENDENT, another_time), as with the document's own date. So with the member's 2026-11-09, 45385 goes held
    (event_time) -> READY:
    - the document-date path is READY at 437b708bb and now, and the act with no denial is READY there too (D67's
      control);
    - the installed release is READY on both paths (with a report header);
    - with no date it stays held (event_time); with the member's 2026-11-10 it stays held (event_time), where the
      installed release EXCLUDES it as historical.
    The measured alternative, not built: read the pending check as SAME only, never as another time (mutant M11). It
    keeps D99 hold-only, and this READY stays a hold that 437b708bb's stale relation made. Both readings measure the
    same on FRESH-1 and FRESH-2 (below).
  - Cost measured: FRESH-2, the head-to-head and FRESH-1 as D98 states them. No row, relation or inventory moves
    through D99. The census of current_encounter times carrying date_unchecked, over the 358 frozen answers:
    - FRESH-2 has three, all in aside-of-twins-019 r1 ('several' dates, opened by Gemini's own question). Each carries
      current_unanchored beside it and is opened, so it stays UNKNOWN;
    - FRESH-1 has one with date_unchecked alone, the same document's EGD examination E1 ('2026-09-30'). No statement
      pairs with it, and its inventory is byte-identical.
  - Pins:
    - test_d99_a_current_time_whose_only_failure_is_date_unchecked_pairs_as_current: the row, both sides;
    - test_d99_every_other_unverified_time_stays_unknown: the control, 9 subtests;
    - test_d99_the_same_day_denial_is_a_contradiction_on_the_undated_note: the stored relation, the five variants;
    - test_d99_the_members_date_asks_the_contradiction: the five variants, with the conflicts check and completeness;
    - test_d99_control_the_documents_own_date_asks_the_contradiction;
    - test_d99_with_no_date_or_another_date_the_snare_stays_held;
    - test_d99_an_earlier_denial_sets_the_act_apart_as_the_dated_document_does: the READY direction, both dates;
    - test_d99_control_a_date_unchecked_examination_never_unresolves_the_pairing: the Counter's scope;
    - test_d99_control_the_acts_own_code_is_still_held_by_its_unchecked_time: unchanged, D67's control;
    - D99Chain.test_d99_the_members_date_at_upload_and_saved_afterwards_asks_the_contradiction: the production chain,
      the legacy entry points failing if called.
  - Recorded residual: the pairing is still made once, at normalize, with no date. D99 reads the pending check as the
    day it will most often be, and assess does not re-relate when the effective date says otherwise. On the finding's
    note with the denial:
    - Member's date 2026-11-10 (the snare's 11/09 is then another day's): 45385 asks [conflict:snare] and
      services.conflicts says warn. 437b708bb asked [event_time] with pass, and the installed release asks
      [performed_status] with pass.
    - No date at all: 45385 asks [conflict:snare] (warn), and the encounter's date question stands beside it.
      437b708bb asked [event_time], and the installed release asks [performed_status] (pass).
    - The code is held in every case, never READY and never excluded. The question is the conflict's where the time
      question is the genuine one: run_registry.verdict would score it dropped_question against an expectation naming
      performed_status or event_time. FRESH-1 and FRESH-2 hold no such case.
    - The repair belongs in assess (assess.py, which reuses stored.relations): relate again over the re-judged reading.
      With that, a member's equal date verifies the time and pairs it, and a differing one leaves it UNKNOWN. D99 would
      then matter only with no date. Outside this repair's files.

- **D100 A digital rectal examination is no session for the pairing table (2026-11-11; the round-4 refutation of
  437b708bb, finding 1; completes D87; FINAL 5.6 E13).** relations.Context's examination Counter makes the pairing
  table's unresolved sessions (all_of_kind -> session_unresolved; and events.broad). It counted every current positive
  examination, so a digital rectal examination that Gemini lists as the colonoscopy's examination made the session
  unresolved for the pairing. That examination has its device verified as manual, the attested C2MEM-029 r1 E9 form.
  Meanwhile coverage.sessions, done_examinations (D69) and events.supports read it as no session (E13), as D87's own
  Session.examinations does.
  - The finding's input. A dated note:
    - 'The colonoscope was advanced to the cecum.';
    - 'Cold forceps biopsies were taken from the transverse colon.';
    - 'No biopsies were taken.' (all_of_kind);
    - 'Digital rectal examination showed normal sphincter tone, no palpable mass, and no gross blood.' (E4: examination,
      device manual 'Digital', target rectum, time and performer the frame defaults).
    Outputs:
    - 437b708bb: unresolved_sessions {gi.colonoscopy}, while coverage's session is E1, resolved. The relation is
      unresolved(procedure, session_unresolved), and 45380 asks [procedure]: 'In which procedure was the forceps biopsy
      ... done?'. The conflicts check is pass.
    - Now: unresolved_sessions {}, contradiction(status, same_act). 45380 asks [conflict:biopsy], the conflicts check
      is warn, and completeness reads '1 conflict in the record'. The same holds with the DRE line first.
    - The snare analogue, 'No polyp was removed.': 45385 asks [conflict:snare] (was [procedure]).
    - Installed c2e53f8e (run first-hand): 45380 asks [conflict:biopsy, extent] on the bare text and [conflict:biopsy]
      with a report header, with or without the DRE line.
  - The rule. The Counter counts only examinations events.endoscopic_examination accepts: never one of an endoscopic
    family whose device is VERIFIED as manual. It is events' own rule, imported inside Context.__init__ because events
    imports relations, so the pairing table, coverage.sessions, done_examinations and events.supports read one rule.
    Kept (D87, C-8): two verified current ENDOSCOPIC examinations still make the pairing's session unresolved. A second
    colonoscope counts, and so does a digital examination whose device Gemini does not state or does not verify (E13
    names that device only).
  - Cost measured: FRESH-2 as D98 states it. C2MEM-029 r1 is the one recording with such an examination event (E9).
    Its pairing sessions go {gi.colonoscopy} -> {}, and its stored relations and assessment stay byte-identical. No
    all_of_kind denial meets an act of its kind there. events.broad(E13 'No colonic stent was placed.') becomes True,
    and no code's kept spans meet it.
  - Pins:
    - test_d100_a_digital_rectal_examination_never_unresolves_the_pairing: the DRE line last and first;
    - test_d100_the_snare_analogue_asks_the_contradiction;
    - test_d100_control_without_the_dre_line;
    - test_d100_control_a_second_endoscopic_examination_still_unresolves_the_pairing: the DRE with no device stated,
      the DRE whose manual device is not verified, and a second colonoscope.

- **D98-D100, the suites and the mutation proof.**
  - Edited: coverage.possibly_current; and in relations, _possibly_current, time_row and the examination Counter in
    Context.__init__. No existing test's expectation changed.
  - The pins: the new module tests/test_interpretation_r4_currency_pairing.py, 21 tests. It is synthetic, apart from
    one committed FRESH-2 recording read verbatim, and nothing is sent.
  - Suites. The engine suites (tests.test_interpretation_*, test_pipeline_assess_events and test_readers_dispatch)
    together with the 14 other new-path modules ran 1419 tests at 437b708bb and 1440 here (1419 plus the 21 pins). All
    pass, with 3 skipped: the legacy guard matrix's c2e53f8e baseline tree. The 14 other modules are
    test_change_context_events, the four guard modules, test_models_event_inventory, test_overlay_differential,
    test_peer_heading, test_pipeline_api, test_pipeline_interpret, the three test_repairs_* report and send modules, and
    test_retry_reading_api. The two harness pipelines and test_services_second_review: 128 tests, passing at both
    commits. The replay pins (tests.test_interpretation_replay) pass, and no fixture was regenerated. INVENTORY_VERSION
    stays gemini-inventory@1, as through D27-D95: nothing is recorded in the product yet.
  - Mutation proof. Each mutant is a private copy of the work tree differing only in the edited function. Each anchor
    occurred exactly once and was confirmed applied, by its marker and sha256. The counts are the pins' failing tests
    and subtests:
    - M0, all three undone (437b708bb's code with these pins): 31. Every D98, D99 and D100 behaviour pin fails, and the
      controls pass.
    - M1, D98 undone in coverage: 13 (the attested input, the four siblings, the unit pin).
    - M2, D98 undone in relations: 7. The behavioural failure is the bleeding control, 45382 READY. The attested input
      and the unit pin fail through their direct assertion of relations._possibly_current, and the attested 45380 stays
      held through coverage's half.
    - M3, D99 undone: 15 (every D99 behaviour pin, the chain among them).
    - M4, D100 undone: 3.
    - M5, D99 read with date_unchecked among other reasons: 2.
    - M6, D99 read on an opened time: 1.
    - M7, D99 read on an earlier or future value: 2.
    - M8, D100 read on an unverified manual device: 1. It survived the first pin set, and the control's
      unverified-device subtest was added for it.
    - M9, D98 widened to every time: 21.
    - M10, D99 carried into the Counter: 2.
    - M11, D99 as SAME only (the hold-only alternative): 4.

- **D101 h3 reads every UNRESOLVED relation of the act (2026-11-11; the round-4 refutation of 437b708bb, finding 3;
  repair "questions").** events._h3_unresolved returned on the act's FIRST stored UNRESOLVED relation, so a same-event
  contradiction stored after another relation was never asked and its sentence appeared nowhere in the assessment.
  Finding 3's input: the sigmoid cold snare 45385 cites, "These were the findings at her index colonoscopy: no
  polypectomy was performed." (UNRESOLVED(time): its time words are the framing sentence, current_unanchored) and then
  C1CL3-001's "No polypectomy was performed in the prior segment." (UNRESOLVED(target, site_unresolved)). 437b708bb
  asked the snare's own, verified, time; with "Neither the EMR electrosurgical snare nor cautery was used to treat this
  polyp." (UNRESOLVED(technique), device_missing) first, its own verified technique. Listed the other way round, both
  asked statement_scope. Against C1CL3-001's expectation the framed-first order scored dropped_question; c2e53f8e asks
  conflict:snare in every order.
  - The rule. For a code, _h3_unresolved reads every UNRESOLVED relation of the act. A same-event contradiction
    (_h3_asks_contradiction: a denial's relation on the target or the scope, or D102's) is the code's question in any
    stored order: the first one resting on the TARGET (D86's own arm: where the pairing table rests on the target, every
    row before it - procedure, time, performer, technique - read the same), else the first one stored. With none, the
    first relation stored asks its attribute's fact, as before. The question's events and passages are the chosen
    relation's, so the prior-segment sentence is shown (question_events E2, E4). focus_question (FINAL 7.8, ``code``
    '') still reads the first relation only (D86's boundary).
  - Why the target first, which the spec does not state: D102 makes the framed denial's own time relation a
    contradiction too, so "the first contradiction stored" would ask about the framed denial and the prior-segment
    sentence would still be shown nowhere in the finding's own order. The spec's example ("the C1CL3-001 contradiction
    listed after an aside's time relation is asked") needs the target one. Mutant 2 below is "the first contradiction
    stored".

- **D102 D91's narrowing is by which side is unknown (2026-11-11; finding 4).** D91 kept D86 on the target attribute
  only, so a denial whose OWN time, performer, device or session is the unknown side made the code ask the act's own
  VERIFIED attribute, with a reason that is not true. Finding 4's S2w: "During withdrawal, no polypectomy was performed
  in the sigmoid colon." ('During withdrawal' is no present-encounter frame, so the denial's time is unverified) beside
  the verified sigmoid snare: 45385 asked "Was the snare removal ... done at this encounter?" with "CPT Studio could not
  confirm from the document when the snare removal ... was done". Recorded: FRESH-2 A/note8 r3 45385 asked "Which
  technique was used for the snare removal (cold snare) ...?" beside its verified cold snare (the denial's hot snare
  unverified). S3 (two done examinations and "No polypectomy was performed.", session_unresolved) asked "In which
  procedure ...?". c2e53f8e asks conflict:snare on all three.
  - The rule. A relation from a denial on the procedure, the time, the performer or the technique is a contradiction
    (statement_scope) when the ACT's own value of that attribute is usable: the unknown side is then the statement's.
    When the act's own value is unusable, the relation keeps that attribute's question (D91, and D86 residual (b)'s
    direction: the act's own unanchored time, unknown performer or unverified device - pinned). A status, kind or part_of
    relation keeps performed_status (D91: C1CL2-002, C2CL-008, v4). The target and scope arms are D86's and D91's,
    unchanged.

- **D103 The statement_scope question quotes the statement whole (2026-11-11; finding 6).** The question and its reason
  quoted only the statement's status words ("required no therapy", "not treated", "not examined endoscopically"), so a
  statement about other findings read as a denial of the act: FRESH-2 C2MEM-031 r2 45385 asked 'Does “required no
  therapy” apply to the snare removal ...?' of "Nonbleeding rectal vascular ectasia, mild sigmoid diverticulosis, and
  small internal hemorrhoids were incidental findings and required no therapy."
  - The rule. h3's statement_scope question and reason (both arms: a code's, and focus_question's for a scope relation)
    quote _h3_whole_statement: the text of the place, among the statement's own passages (its status's first), that
    holds its status words - the sentence, clause or line Gemini cited. Without located status words: the first located
    place of its status's passages, else statement_text as before. Quoted uncut (wording.scope_question and
    scope_reason take ``whole``; a passage is bounded to 600 characters by the read): 129 of 227 denial places on FRESH-2
    are longer than the 120 characters a question used to be cut at, and the cut fell on the denial's own words ("...
    were incidental findin…"). ``whole`` defaults to False, so ADJUDICATION C-10's question (events._exclusion) is
    unchanged.

- **Finding 5, RECORDED, not repaired.** D86's target arm (kept by D91 and D102) asks 43249 and 43245 one statement_scope
  question beside "No dilation of the esophagus was performed." (site_overlap; an anastomosis is never disjoint), where
  a4dcbea72 asked D29's act_target. Both codes stay held (never READY, never excluded); the question is the
  contradiction c2e53f8e asks as conflict:dilation, now quoting the denial whole. Pinned as recorded.

- **D101-D103, what was edited.** studio/interpretation/events.py: _h3_unresolved, and three helpers only it calls
  (_h3_denial, D86's denial test moved out of the loop unchanged; _h3_asks_contradiction; _h3_whole_statement) with
  the attribute tuple _H3_STATEMENT_SIDE. studio/interpretation/wording.py: scope_question and scope_reason take
  ``whole``. RELATION_FACTS is unchanged. Only the question changes: status, bucket, READY, the exclusion, the events
  read (the fingerprint) and every inventory are untouched.
- **Cost measured.**
  - FRESH-2 (score_fresh over fresh2-frozen; 437b708bb re-scored as f2r4-questions-pristine, equal to f2r3intc in every
    row, inventory and assessment; the patch as f2r4-questions): A 96/6, B 177/15, C 171/19 plus 2 safe_hold, before and after. 0 false READY, 0
    false exclusion, 0 dropped questions, 0 ready_wrong_facts. Of 486 code rows exactly one field moves: A/note8 r3
    45385's asked, technique -> statement_scope (D102; expected READY, a false hold before and after). No got, verdict,
    status, bucket, exclusion or failing check moves. 0 of 179 inventories and 19 of 179 assessments differ: 31
    proposals' questions (1 fact, D102; 30 wording only, D103), with their support.detail and service.status,
    events.match and events.relation details. No encounter clarification, completeness or summary moves. D101 moves no
    recorded row on FRESH-1 or FRESH-2 (no question_events change anywhere).
  - FRESH-1 (fresh-frozen, 437b708bb against the patch): A 97/5, B 174/18, C 165/24 plus 1 false READY and 2 safe_hold,
    before and after (the false READY is the one D86 recorded, unchanged). No row field moves; 30 proposals' questions
    and one service question (C2MEM-031 r3) change wording only; completeness unchanged.
  - Head-to-head (h2h/compare.py on f2r4-questions against c2e53f8e's results): identical to h2h-r3final.json in every
    key. Run 1: 214/234 (A 34/34, B 59/64, C 121/136); worse_r1 the same 5 holds; better_r1 69; 7 unstable rows; the
    facts check moves 0 rows. No row changes.
  - Replay pins (tests/test_interpretation_replay.py) pass: h3 reads after normalization.
- **Pins: tests/test_interpretation_r4_questions.py (20 tests),** from the findings' own inputs.
  - D101EveryRelation (8): the prior-segment denial after the framed denial's time relation, and after the device
    denial, is the question (question_events E2, E4; the sentence shown); the same question in all four sentence orders;
    a doubt's time relation stored first (D86's clip boundary shape) does not take the denial's question, and alone keeps
    event_time; a target denial stored after the act's OWN unknown device is the question, and without it the act keeps
    technique; two contradictions resting on no target ask the first stored (both orders); with no contradiction (the
    snare's own time unanchored) the first relation keeps event_time; focus_question still reads the first relation
    (event_time, E2, E3).
  - D102TheStatementsSide (6): S2w (the reason is no longer "could not confirm ... when"); note8 r3's shape (the
    denial's device unverified); S3 (statement_scope, and the session's extent question stays); the denial's performer
    unknown; the act's own unknown time, performer and device keep event_time, event_performer and technique; a status
    or kind relation keeps performed_status.
  - D103TheStatementWhole (5): the 146-character incidental-findings sentence quoted whole and uncut; finding 6's S5
    ("The terminal ileum was not examined."); FRESH-2 fb07 r1 recorded (43235: 'Does “The Roux limb was therefore not
    examined endoscopically.” apply to the upper endoscopy'; 43245 still READY); status words not located quote the
    status passage; the C-10 default keeps its cut.
  - Finding5Recorded (1): 43249 and 43245 both held, statement_scope quoting the denial whole.
- **Existing expectations moved** (each by the spec's own change; no other test changed):
  - tests/test_interpretation_events.py Focused.test_h3_unresolved_time: event_time -> statement_scope (D102: the
    denial's time is the unknown one); its question now quotes "No polyp was removed." (D103).
  - Focused.test_h3_unresolved_scope_asks_whether_the_statement_applies: the quote is "No polyp was removed." (D103).
  - tests/test_interpretation_r3_questions.py RecordedRows: C1CL3-001 quotes "No polypectomy was performed in the prior
    segment."; ownpassage-004 and -005 quote "A 22 mm polyp in the ascending colon was removed piecemeal with a cold
    snare in four pieces, without submucosal injection." (LIFT_SENTENCE); C2CL-013 quotes "The intervention was not
    repeated at this examination." (D103). Their facts, question_events and shown passages are unchanged.
  - SyntheticPairs.test_d86_a_denial_of_a_segment_its_words_do_not_name_asks_whether_it_applies_to_the_snare and
    test_d86_an_injection_denial_beside_a_lift_row_asks_the_contradiction: the whole sentence is quoted (D103).
  - SyntheticPairs.test_d91_only_a_target_relation_asks_the_denial_every_other_attribute_keeps_its_question: the time
    and performer subtests (an unknown time or performer on the DENIAL, beside the snare's verified one) ask
    statement_scope (D102); technique (the act's own device not stated), status and kind are unchanged.
  - Boundaries.test_d86_a_doubt_keeps_the_question_of_its_attribute: the denial twin of the time row (its time unknown,
    the clip's verified) asks statement_scope (D102); both doubt rows keep their attribute's question.
  - tests/test_interpretation_r3_integration_d89_d91.py SNARE_SCOPE and BIOPSY_SCOPE quote the statements whole (D103);
    D89's two pins keep their substance (both questions asked; only the same question suppresses).
- **Suites.** tests.test_interpretation_* with test_pipeline_assess_events and test_readers_dispatch: 1128 tests at
  437b708bb -> 1148, all passing. Before the expectations above moved, they were the run's 13 failures and its only
  ones. The 14 other new-path modules (the four guard modules, test_pipeline_interpret, test_pipeline_api,
  test_retry_reading_api, the two harness pipelines, test_services_second_review, test_change_context_events,
  test_models_event_inventory, test_overlay_differential, test_peer_heading): 332 tests pass, 3 skipped (the legacy
  guard matrix's c2e53f8e baseline tree), as at 437b708bb (332, 3 skipped).
- **Mutation proof:** 10 private copies, each differing from the patch in one anchored edit (the anchor occurred exactly
  once; the marker and a changed sha256 confirmed it applied; the patch copy's sha was unchanged). The pin modules
  (r4_questions, r3_questions, r3_integration_d89_d91, interpretation_events; 114 tests), per mutant:
  - M1, D101 undone (only the first stored relation read): 6 failures - the framed-first, device-first, both
    target-first order subtests, the doubt-first and the act-device-first pins.
  - M2, the first contradiction stored (no target preference): 4 - the framed-first and device-first pins and their two
    order subtests.
  - M3, D102 undone (D91's target-or-scope rule): 10 - the four D102 pins, the tie pin (2), D91's time and performer
    subtests, the doubt boundary's denial twin, test_h3_unresolved_time.
  - M4, D102 by attribute whichever side is unknown: 7 - the act-side pin (3 subtests), the no-contradiction and
    act-device pins, D91's 2024-denial pin, D91's technique subtest.
  - M5, D102 reaching status, kind and part_of: 9 - the status-or-kind pin (2), D91's C1CL2-002 and C2CL-008 pins, D86's
    C1CL2-002, v4 and no-negator pins, D91's status and kind subtests.
  - M6, D103 undone (status words, cut as before): 30.
  - M7, the whole statement cut at the old 120 / 140: 4 - the incidental-findings pin and the three lift-row pins (the
    sentence is 122 characters).
  - M8, D103's fallback undone (unlocated status words quote statement_text): 1.
  - M9, D101/D102 reaching focus_question: 1, the service-question pin (D86's own service pin passes under it: its
    relation rests on the act's unknown time).
  - M10, every scope question quoted whole (C-10's too): 1, the C-10 pin.
- **Recorded residuals and points for the owner.**
  - (a) D103 reaches h3's question only. events._exclusion's statement_scope question (C-7's broad statement, C-10's
    partial cover) still quotes the statement's status words: 29 rows on FRESH-2, e.g. B/fb06 r2 45385 'Does “not
    removed” apply to the snare removal this code accounts for?', C/W1S-222 r1 45385 'Does “removed” apply ...'.
    Outside this repair's ownership.
  - (b) The quote is the passage Gemini cited, never cut to a sentence. A hard-wrapped document's passage is a line:
    FRESH-2 C2MEM-023 r1 45390 'Does “flat 4 mm, nonbleeding vascular ectasia in the proximal rectum was photographed
    but not treated; there was no” apply ...' (45385 likewise ends "... was performed on"). A passage of two sentences
    is quoted with both: FRESH-1 A/note8 r2 45385, 45386, 45388, 45390 quote "5. Mid-descending-colon 9 mm sessile
    polyp, completely removed by cold-snare technique. Nonbleeding rectal vascular ectasia, ... required no therapy." (0
    such quotes on FRESH-2; 4 on FRESH-1). A sentence cut was not built: any boundary rule drops meaning somewhere - "No
    polypectomy was performed by Dr. Smith at the outside hospital." cut at "Dr." loses the other facility, and
    "History: No polypectomy was performed at the 2024 colonoscopy. None was performed today either." cut to its status
    words' sentence ("None was performed today either.") loses the act it denies. The whole passage always holds the
    status words' sentence.
  - (c) D101 is per act. FINAL 7.4's candidate loop (_focused) asks the first candidate with any UNRESOLVED relation:
    45385 citing a sigmoid snare whose own time is unanchored ("During withdrawal, a 6 mm sessile polyp ... was removed
    with a cold snare.") and a rectal snare beside "No polypectomy was performed in the distal segment." (target the
    rectum, words unverified) asks the sigmoid snare's event_time (E2, E5); the rectal snare's contradiction is not
    asked. Outside _h3_unresolved.
  - (d) D101's tie: two contradictions on no target (each on the statement's own unknown side) ask the first stored, so
    the sentence quoted follows the document's order (statement_scope either way). Pinned.
  - (e) One question per code: a contradiction wins over the act's own unknown on the same act. A snare whose own device
    is unverified, beside "No hot snare was used for the 6 mm sessile polyp." (technique, the act's side) and the
    prior-segment denial, asks statement_scope; the technique question is not asked (at 437b708bb the sentence order
    decided which). c2e53f8e asks conflict:snare on finding 3's texts in every order. 0 recorded instances on FRESH-1
    and FRESH-2. Pinned.
  - (f) D102's condition is the act's own value USABLE, as the spec states it. It therefore also reaches a technique
    relation where both devices are verified and the act's is wider: "A 6 mm sessile polyp in the sigmoid colon was
    removed with a snare." beside "No cold snare was used for the 6 mm sessile polyp." asked "Which technique was used
    ...?" (a true reason: a snare, not which) and now asks statement_scope; c2e53f8e asks conflict:snare (and extent, on
    that heading-less text). Not pinned.
  - (g) focus_question (D86's boundary, kept by the spec) still has finding 3's and 4's defects in the service question.
    45378 alone on finding 3's text: the uncited snare (not_covered) asks the service question "Was the snare removal
    (cold snare) ... done at this encounter?" with "CPT Studio could not confirm from the document when ... was done",
    though its time is verified, and the prior-segment denial is not asked. c2e53f8e asks the service question
    conflict:snare ("The record conflicts on the snare removal in the colonoscopy: which statement is correct for this
    encounter?") on the same texts, with or without a procedure heading. D89 since compares a code's question with a
    service question by its words, but keeps one service question per (family, fact) among service questions, so
    lifting the boundary has a cost of its own: the owner's call.
  - (h) Parity (report only): the new path's services.conflicts check (assess._conflicts) reads CONTRADICTION relations
    only. Beside a code held by statement_scope (finding 3's and 4's inputs) it passes, "No act is stated both as done
    and as not done for the same service and site.", where c2e53f8e warns "Kept with both sides, never resolved
    silently: snare removal in the colonoscopy: physician performed vs physician negated.".

- **D104 A defining act stated uncertain is a doubt the narrowed code claims for (2026-11-11; the round-4 refutation
  of 437b708bb, finding 11; widens D74).** D74 gave a code D27 narrows the claims of its covers' other kinds when its
  family has a defining act stated POSITIVE (verify.POSITIVE) and possibly current. A lithotripsy stated 'uncertain'
  ("It is unclear from the record whether the 15 mm stone in the common bile duct was fragmented with mechanical
  lithotripsy.", status words "It is unclear"; "... may have been required.") is neither, so assess._claims(43265) was
  () and 43264 for the balloon extraction of the fragments went READY beside a held 43265, with no competing_codes. The
  installed release, configured as in production (Astra and Fable read), holds both with competing_codes on both
  wordings. coverage.doubted, FINAL 7.4 h2 and the engine's own "doubt" reason already read 'uncertain' as a doubt.
  - The rule. In assess._claims the defining act's status value may be positive OR 'uncertain' (it may have been done),
    still in any verification state and possibly current (coverage.possibly_current). A denied, planned or earlier one
    claims nothing, as before. The claimed kinds, E*, support['acts'] and combination.competition are unchanged.
  - Pins: tests/test_interpretation_r4_ercp.py D104UncertainDefiningAct, three tests: finding 11's three P3 wordings
    (status words "It is unclear", "It is unclear from the record whether" with no scope words, "may have been
    required"), each with no participant and with Astra and Fable read and proposing nothing (6 subtests: 43264 held
    competing_codes only, 43265 held with its own doubt question and competing_codes, E* unchanged); _claims(43265) ==
    ('E4',) on the three wordings and () for a denied, a planned and an earlier-encounter uncertain lithotripsy; the
    controls (43264 proposed alone stays READY, as installed; a denied lithotripsy leaves 43264 READY and 43265 held not
    documented).
  - Mutations: mut-1h (the gate back to verify.POSITIVE) fails 9 subtests of the first two pins, and the controls
    pass. mut-14h (the gate reading any status) fails the denied and planned subtests and the denied control.
  - Cost: FRESH-1 and FRESH-2 hold no defining act stated uncertain (census below), so no row moves.

- **D105 A stent removal and a stent placement in one duct are a possible stent exchange (2026-11-11; the round-4
  refutation, finding 22).** "The existing biliary stent was removed with a snare." and "A 10 Fr x 9 cm plastic biliary
  stent was placed into the common bile duct.", read to the contract as stent_removal and stent, made 43275 and 43274
  both READY, and 43276 on "Procedure: ERCP with biliary stent exchange." was held "not documented". A stent removed and
  replaced in the same duct at one session is one exchange (43276), not a removal and a placement. Nothing read the two
  acts together: coverage.bundled_reason (D45) folds only a sphincterotomy or a dilation into a stent act, and
  combination.competition compares E* sets, which do not intersect. The installed release never READYs 43275 there
  (its reader has no stent_removal kind) and READYs 43274.
  - The rule (studio/interpretation/ercp.py, exchange_pairs and exchange_hold). An ERCP session with a positive stent
    removal and a positive stent placement whose ducts nothing sets apart is a possible exchange. Each side is of the ERCP
    family, stated positive (verify.POSITIVE) and possibly current (D62), each read as a value in any verification state
    (D74's reading; D87: a doubt is a question), and not verified as another performer's act. Two ducts both verified and
    different (coverage.duct_side: the bile duct and the pancreatic duct) keep the acts separate. A duct verified on
    neither act, or the ampulla, never sets them apart (D45's reading).
    - A READY 43275 whose own stent removal is a side, and a READY 43274 whose own placement is a side, are held with ONE
      question naming the exchange (performed_status): "Were the stent removal (snare) at the bile duct (“was removed
      with a snare”) and the stent placement at the common bile duct (“was placed”) one stent exchange (43276), or
      separate services (a stent removal, 43275, and a stent placement, 43274)?". The question's events are the removal
      and the placement, and the decision reads both, so coverage counts both as read.
    - 43276, READY or held "not documented", is held with that question while the session has a pair. It is never "not
      documented" there.
    - A code held for another reason keeps its own question (D89; the removal's unanchored time keeps 43275's event_time
      question). An exclusion stands. Reason 'possible_exchange' (a new Evaluation.reason value; none is a closed list).
  - Where it runs: ercp.ruled is events.evaluate's ONE call site, its first statement. For a code D105 or D106 reads,
    it has the per-code rule evaluate the code once, re-entered with the hook stood down by a context variable, and
    applies the rules to that evaluation. For any other code it returns None and the rule goes on as before. So every
    reader of the per-code rule reads one evaluation: the assessment, its participants and second review, and
    overlay.counted_codes, which re-makes "the evaluation the engine made". A hook in assess alone would have made the
    review overlay's coverage differ from the engine's.
    - A decorator on evaluate was built first and refused. tests.test_guard_mutation's F3 plant recompiles
      events.evaluate from events.py's own source, and a wrapper defined in ercp.py is no FunctionDef there (3 errors).
      The in-function call site keeps evaluate the function events.py defines, and the plant applies and goes red, as
      before.
  - A literal choice, for the owner: 43276 READY on its own stent_exchange event beside such a pair (the refuter's
    three-event shape, where all three codes were READY) is held too ("43276, when proposed, is held with that
    question"). On a single exchange restated as three events that is a false hold of the right code. The other reading,
    hold 43276 only where it was "not documented", would leave 43276 READY beside two held rivals.
  - Pins: D105PossibleStentExchange, six tests:
    - finding 22's document with 43275+43274, +43276, and each code alone, with and without the participants (10
      subtests);
    - finding 22's second document ('Impression: Biliary stent exchange.'): 43275, 43274 and 43276 held, 43260 keeps
      base_included;
    - the three-event shape;
    - the controls: the ducts verified apart, either way round, keep 43275 and 43274 READY and 43276 not documented;
    - a duct not stated, and a placement at the ampulla, are a pair;
    - the removal's time unanchored: 43275 keeps event_time, 43274 and 43276 are held. A removal verified at an earlier
      encounter, or denied, is no side: 43274 READY.
  - Mutations: mut-2h (the rule off) fails 15 subtests over 5 tests. mut-5h (the call site removed) fails every D105
    and D106 behaviour pin. mut-6h (ducts never set apart) fails the ducts-apart control. mut-7h (READY only, no
    not-documented arm) fails the 43276 subtests, the second document and the doubted-removal test. mut-8h (a side's time
    verified only) fails the doubted-removal test.
  - Cost: FRESH-1 and FRESH-2 hold no ERCP stent removal, placement or exchange event, so no row moves. Against the
    installed release, 43274 READY -> held on an exchange document (finding 22's, its second document, h2-10's shape)
    is a new hold where c2e53f8e READYs 43274, on a document where 43274 is the wrong code for the exchange.
  - Recorded, not built (the spec names a stent REMOVAL that is positive):
    - a removal Gemini files as foreign_body ("The migrated biliary stent was removed with a snare.") pairs with nothing,
      so 43275 and 43274 stay READY (c2e53f8e: 43275 held, 43274 READY);
    - a removal stated 'uncertain' ("It is unclear whether the existing biliary stent was removed.") is no side, so
      43274 stays READY (c2e53f8e READY too). D104's reading would count it;
    - a removal begun and not completed is a side (POSITIVE), so a stent placed beside an old stent that could not be
      removed holds 43274 with the exchange question: fail-closed, possibly a false hold.

- **D106 A stone removal that retrieved nothing does not support 43264 (2026-11-11; the round-4 refutation, finding
  25).** "The bile duct was swept several times with an extraction balloon; no stones or sludge were retrieved.", read
  as a performed stone_extraction (KINDS has no sweep; the extraction_balloon technique verifies on "extraction
  balloon"), made 43264 READY. CPT reports a removal of calculi or debris, and not a balloon passed through a duct
  that yields none. The installed release EXCLUDES 43264 (act_denied, its reader reads "no stones or sludge w..." as a
  negated stone_extraction), and holds it when Corti cites only the first clause.
  - The rule (ercp.nothing_retrieved, retrieval_hold). A supporting stone_extraction of 43264's one requirement group
    whose own sentence states that nothing was retrieved does not support 43264. "Its own sentence" is a sentence of its
    own located passages (kind, status, target) that holds one of its own words, or the whole of a passage none of
    whose sentences does (a restatement). "States" means: a negator (lexicon.NEGATORS, or n't) over STONE_WORDS (stone,
    stones, calculus, calculi, debris, sludge), at most three words between and no clause break, AND a retrieval or
    extraction word in the sentence (retrieve, extract, remove, deliver, recover and yield, with their forms).
    - With no other supporting act, 43264 is held with the performed_status question naming that sentence: "Was any
      stone, calculus, debris or sludge removed with the stone removal (extraction balloon) at the bile duct (“...; no
      stones or sludge were retrieved.”)?". Reason 'nothing_retrieved'. Never READY. The installed release's EXCLUSION
      is not ported: the hold is the fail-closed answer (D5; EB1 forbids an exclusion read from a passage's words).
    - With another supporting act (a basket extraction that did retrieve stones), 43264 stays READY on that act alone.
      The sweep leaves E* and stays in the decision's read events, so it is still covered.
  - An interpretation, stated: an exceptive or partial word between the negator and the stone word (further, other,
    additional, more, residual, remaining, retained, all, every, each, both, only) is not "nothing retrieved". ADJUDICATION
    C-7 reads "no further / no other / no additional" as about acts BEYOND those reported, never pairing with positive
    acts. So "Two stones were extracted ...; a final sweep retrieved no further stones." keeps 43264 READY, and so does
    "Not all stones could be extracted.". Pinned (test_d106_the_negation_read_in_the_acts_own_sentence), mutation-proved
    (mut-9h).
  - A tension with EB1, for the owner. The rule reads words of the act's own PASSAGE that are not the words of any
    attribute it verifies: the negation is in no attribute's words, since Gemini gave the act performed. EB1 says "a
    check never scans the rest of a passage". It never makes READY or excludes, only holds, and the passage read is the
    act's own sentence, never a neighbour. EB4 says a passage word list is never the repair.
  - Pins: D106NothingRetrieved, three tests:
    - finding 25's reading with Corti citing the whole sentence or its first clause, with and without the participants
      (4 subtests: 43264 held, question and reason naming the statement, E* empty; 43262 READY);
    - the sentence reader over 5 stating and 6 non-stating sentences, plus the recorded cost below;
    - the controls: "two small stones were retrieved" and an exceptive "no further stones" keep 43264 READY, and beside
      a basket extraction 43264 stays READY on E5 alone with E4 read and covered.
  - Mutations: mut-3h (the rule off) fails the finding test (4 subtests) and the basket control. mut-9h (no exceptive
    words) fails the exceptive control and 3 non-stating sentences. mut-10h (E* not narrowed) fails the basket control.
    mut-5h (no call site) fails the behaviour pins.
  - Cost: FRESH-1 and FRESH-2 hold 48 ERCP stone_extraction events and none states nothing retrieved, so no row moves.
    The pinned cost of reading the whole sentence: "The bile duct was swept with an extraction balloon; no stones were
    seen; sludge was retrieved." is read as nothing retrieved, so 43264 is held, never READY and never excluded.
  - Recorded, not built: three on-contract wordings where 43264 stays READY and c2e53f8e holds or excludes it.
    - "...; nothing was retrieved." has no negator over a stone word (c2e53f8e: held).
    - "The bile duct was swept several times with a balloon; no stones were found." has no retrieval or extraction word
      (c2e53f8e: held).
    - Gemini's passage for the sweep is only its first clause ("The bile duct was swept several times with an
      extraction balloon"), so the negation is in no passage of the act (c2e53f8e: EXCLUDED).

- **D107 An ERCP whose access act was begun and not completed carries D61's signals (2026-11-11; the round-4
  refutation, finding 26; completes D61 and D71).** On finding 26's ERCP the examination is performed ("was advanced"),
  the biliary cannulation is attempted_not_completed ("Multiple attempts at biliary cannulation were unsuccessful.")
  and the sphincterotomy and stent are denied. 43260 was READY with neither the service.incomplete warn nor the 52/53
  consideration. _incomplete_session read only a done examination's completion or status, and the cannulation is a
  bundled act. The installed release reads a failed cannulation as an incomplete ERCP and gives 43260 both, with or
  without "The procedure was terminated;".
  - The rule. assess._incomplete_session, after D61's verified completion and D71's attempted examination, reads
    ercp.access_not_completed. For the ERCP family that is the status words of its first cannulation done at this
    encounter (events.done: usable status, current time and documenting-team performer) whose status is a usable
    attempted_not_completed (its failure marker verified). Every code of the session, whatever its own state, carries
    the warn worded from those words (wording.incomplete_check, ADJUDICATION R-4: "Documented as incomplete: “were
    unsuccessful”. Kept for review: ...") and the installed release's consideration. An excluded code carries neither.
    Status never changes. "The examination stated terminated" is D61's and D71's arm, which is read first and quotes the
    examination's own words.
  - The session's DEFINING access act. A pancreatic duct's cannulation begun and not completed, beside the bile duct's
    cannulation achieved (both ducts verified), gives nothing. This is the installed release's pancreatic avoidance
    (detect._pancreatic_avoidance, "a deliberate choice, not a failed ERCP"), measured on c2e53f8e as READY with neither
    signal. A biliary attempt that failed before the biliary access was achieved gives both, as c2e53f8e does.
  - Pins: D107AccessNotCompleted, four tests:
    - finding 26's text and the variant without "The procedure was terminated;", with and without the participants (4
      subtests): 43260 READY with both signals in the cannulation's words; 43262 and 43274 excluded with neither; a held
      43261 and the base 43260 it holds carry both;
    - the examination stated begun and not completed, or its completion 'incomplete', quotes "The procedure was
      terminated", once, on 43260 and on a held 43261 whose signals come from the session alone;
    - the controls: a cannulation achieved, a failed cannulation at an earlier encounter, and any other family give
      nothing;
    - the pancreatic avoidance and the biliary attempt before the access.
  - Mutations: mut-4h (the arm removed) fails the finding test's 4 subtests and the biliary-attempt subtest. mut-11h
    (any attempted cannulation, whatever its time) fails the earlier-encounter control. mut-12h (no pancreatic
    avoidance) fails the pancreatic subtest. mut-13h (the cannulation read before the examination's own words) fails
    both subtests of the examination test.
  - Cost: FRESH-1 and FRESH-2 hold 6 ERCP cannulations, all performed, so no row moves.
  - Recorded, not built:
    - finding 26's EGD sibling ("The gastroscope was advanced to the gastric antrum; the pylorus could not be traversed
      ...", reach gastric_antrum, completion not stated, 43239 READY) is not the ERCP and stays without the signals,
      where c2e53f8e gives both;
    - D61's completion is still read verified only (D73 relies on it).

- **D104-D107, what was edited, and the measurement.**
  - Files: studio/interpretation/assess.py, _claims (D104) and _incomplete_session (D107, a local import of ercp)
    only. studio/interpretation/ercp.py, new. studio/interpretation/events.py, an import line and the one call
    site, the three lines that open evaluate's body. tests/test_interpretation_r4_ercp.py, new, 16 tests. No existing test changed.
  - Suites on the final work copy:
    - tests.test_interpretation_* (all 37 modules, the new one included), test_pipeline_assess_events,
      test_readers_dispatch, test_overlay_differential and test_guard_static: 1161 OK. 437b708bb ran 1130 on the same
      modules without the new module and test_guard_static, and test_guard_static passes there too (15).
    - The 45 other test modules that import the new path, test_guard_mutation and the guard matrices among them: 983 OK,
      3 skipped. With the refused decorator, test_guard_mutation's F3 errored 3 times, and nothing else failed.
  - FRESH-2 re-scored as fresh2-score/f2r4-ercp, against 437b708bb scored the same way (f2r4-ercp-pristine, identical
    to f2r3intc): A 96/6, B 177/15, C 171/19 plus 2 safe_hold, unchanged. 0 of 486 rows, 0 of 179 assessments
    (JSON-equal) and 0 of 179 inventories differ.
  - Head-to-head: identical to h2h-r3final.json (JSON-equal). Run 1 is 214/234 (A 34/34, B 59/64, C 121/136), worse 5,
    better 69, unstable 7, facts moved 0.
  - Census of the stored inventories (FRESH-2 f2r3intc and FRESH-1 f1final, 358):
    - 0 defining acts stated uncertain;
    - 0 ERCP stent removal, placement or exchange events, so 0 pairs;
    - 48 ERCP stone_extraction events, 0 stating nothing retrieved;
    - 6 ERCP cannulations, all performed, so 0 access acts begun and not completed.
    The committed fixtures hold none of these kinds. The replay pins do not move.
  - Each of the 14 mutants was built in its own copy of the final work tree (mut-1h ... mut-14h). Each replacement was
    asserted to occur once and confirmed by its marker and a sha256 change, with the work copy's sha256 unchanged.
    Every mutant fails at least one pin, by assertion and never by error.

- **D108 An enteroscopy code is READY only when its class fits its session's verified reach and route (2026-11-11; the
  round-4 refutation of 437b708bb, finding 24).** Every small-bowel enteroscopy code was READY on any verified reach.
  assess._reach applies a reach class to the colonoscopy alone (D38), mapping.examination_class knows only the EUS
  classes, the catalogue gives 44360-44386 no class, and the enteroscopy profile only needs some extent to be present.
  So on finding 24's own documents the new path made these READY with no question:
  - 44377 ("including ileum") on "The double-balloon enteroscope was advanced orally to the mid jejunum." with the
    biopsy of an ulcer there;
  - 44361 ("not including ileum") on the same report reaching the proximal ileum;
  - 44382 (ileoscopy through a stoma) and 44386 (a pouch's biopsy) on the oral report to the mid jejunum;
  - 44369 and 44361, alone and together, on "PUSH ENTEROSCOPY REPORT ... The enteroscope was advanced to the second
    portion of the duodenum." (and the bulb), an upper endoscopy's reach, and on that report with a verified
    "The examination was incomplete because of looping." (only service.incomplete and the 52/53 consideration).
  The installed release c2e53f8e holds every one of these exact inputs: engine.assess, as tests/test_harness_engine.py
  drives it, and jobs._assess_child agree on all 22 rows (performed_status and extent, or extent alone for 44369). That
  was held turned to READY, against the document and against the installed release.
  - The rule: a NEW module, studio/interpretation/classes.py, and ONE call in assess._proposal beside
    _examination_class, in its shape (the enteroscopy codes have no EUS class, so the call fills the same exam_class
    slot). The engine therefore treats both alike: a warn check, the extent question, and a reinstatement wait on an
    excluded code.
    - The classes follow the code ranges their CPT descriptors name. Every catalogue code of gi.enteroscopy is in
      exactly one; this is pinned.
      - 44360-44373 (JEJUNAL): a verified reach at the jejunum.
      - 44376-44379 (ILEAL): a verified reach at the ileum, terminal ileum or neo-terminal ileum.
      - 44380-44384 (STOMA): the encounter's verified stoma (mapping.has_stoma, D43's reading) and an ileal reach.
      - 44385-44386 (POUCH): the encounter's verified pouch (an altered-anatomy pouch entry, read as has_stoma reads a
        stoma) and a reach in the pouch or the ileum.
    - Every other reach fits no class: the bulb, the second portion, the duodenum or ampulla, the small bowel named
      only as such, an anastomosis, the upper tract and the colon. (The second-portion landmark also takes the "third
      portion" words.)
    - As D43 reads the full EUS class, ILEAL (the class that needs the deeper reach) never fits an examination whose
      completion is 'incomplete' in ANY state (D56) or whose status is attempted_not_completed (D72). JEJUNAL, like
      the limited class, reads its reach only.
    - The hold:
      - facts.examination_class (the EUS check's id; label "Small-bowel enteroscopy examination class"), warn;
      - one question, fact extent, in D43's form:
        - the class question ("The documented enteroscopy (“mid jejunum”) reached the jejunum. Was a small-bowel
          enteroscopy past the second portion of the duodenum that reaches the ileum performed on the date of
          service?") where the reach fits another class, or fits the code's own class with only the route
          unverified;
        - its incomplete form where only the incompleteness keeps the code's own class from fitting;
        - R6's own extent question ("Small-bowel enteroscopy: confirm the furthest extent reached.", copied and
          pinned equal to checks.FACT_QUESTIONS) where the reach fits no class at all.
      - Never READY and never an exclusion. An unverified reach, or a session with no single current examination
        (D62/D87), is left to R6, which asks the missing extent: one question, never a second.
    - It reads only the inventory's verified structure: the reach's landmark, the examination's completion and
      status, and the encounter's anatomy. There is no word list, and no passage is read (EB1).
  - The new path after D108, on the same inputs:
    - every finding variant is held with the extent question and the class check;
    - 44361 and 44369 on the push enteroscopy to the proximal jejunum (the finding's control) stay READY, as do
      44361 on the mid-jejunum report and 44377 on the ileal one. The installed release holds these controls only
      incidentally: it reads no enteroscopy reach without a "Procedure:" line.
    - The 52/53 consideration and service.incomplete of D61 are kept on the incomplete D2 report.
  - Cost on FRESH-2 (f2r4-enteroscopy against f2r3intc):
    - the summary is unchanged: A 96/6, B 177/15, C 171/19 plus 2 safe_hold;
    - 0 of 486 rows change in any field. The corpus has no enteroscopy document. Its 6 enteroscopy-code rows are the
      decoys A/v6 44381 r1-r3 and B/fb07 44360 r1-r3, all expected NOT_READY. Both are held before and after, on
      performed_status and extent, because no enteroscopy session exists;
    - the head-to-head (h2h.json) is identical to h2h-r3final.json in every key: run 1 214/234 against installed
      150/234, worse on the same 5 rows (all holds), better on 69;
    - 0 new false READY, false exclusion, dropped question or ready-on-wrong-facts;
    - the replay pins pass unchanged.
  - Cost measured on probes: a reach beyond the second portion that the schema's landmarks cannot name.
    - "The enteroscope was advanced to the fourth portion of the duodenum.", read as 'duodenum' (verified): 44361 was
      READY at 437b708bb, correctly, and is held after D108.
    - c2e53f8e READYs it when the document carries "Procedure: Push enteroscopy.".
    - "Third portion" words verify as second_portion_duodenum and are held the same way.
    - LANDMARKS has no third or fourth portion and no ligament of Treitz, so "beyond the second portion" is
      verifiable only as the jejunum. This fails closed, as the design asks: a reach at the second portion fits no
      enteroscopy code.
  - Pins: tests/test_interpretation_r4_enteroscopy.py, 18 tests.
    - FindingInputs:
      - test_d108_44377_on_the_double_balloon_enteroscopy_to_the_mid_jejunum_is_held_with_the_class_question;
      - test_d108_44377_and_44361_proposed_together_for_the_one_biopsy_compete_and_the_misfit_asks_its_class;
      - test_d108_44361_on_a_reach_into_the_proximal_ileum_is_held_with_the_class_question;
      - test_d108_the_stoma_and_pouch_codes_on_an_oral_enteroscopy_are_held;
      - test_d108_a_push_enteroscopy_stopped_at_the_second_portion_or_the_bulb_fits_no_enteroscopy_code;
      - test_d108_a_reach_named_only_as_the_small_bowel_fits_no_class;
      - test_d108_the_push_enteroscopy_stated_incomplete_at_the_second_portion_is_held_and_keeps_d61s_signals.
    - ClassesThatFit (READY controls):
      - test_d108_a_jejunal_reach_fits_44360_to_44373;
      - test_d108_an_ileal_reach_fits_44376_to_44379;
      - test_d108_an_ileoscopy_through_the_encounters_verified_stoma_fits_44380_to_44384;
      - test_d108_a_pouch_examination_with_the_encounters_verified_pouch_fits_44385_and_44386.
    - RouteAndCompletion:
      - test_d108_a_stoma_or_pouch_code_needs_the_encounters_verified_route: none, or its words not located;
      - test_d108_an_examination_stated_incomplete_never_fits_the_ileal_class: verified, words not located, opened,
        attempted_not_completed;
      - test_d108_the_jejunal_class_reads_its_reach_only.
    - LeftToTheOtherRules:
      - test_d108_an_unverified_reach_is_r6s_extent_question_alone;
      - test_d108_an_excluded_code_stays_excluded_and_waits_on_its_class;
      - test_d108_every_catalogue_enteroscopy_code_has_exactly_one_class_and_no_other_code_has_one;
      - test_d108_the_extent_question_is_r6s_and_no_sentence_names_a_vendor.
  - Mutation proof: 22 mutants, each made in its own private copy of the final tree, applied exactly once and
    confirmed. The working copy's tree sha256 is the same before and after. Every mutant fails at least one pin, and
    every pin fails under at least one mutant.
    - M1, the call removed (437b708bb's behaviour): the 10 pins on the finding's inputs, the route, the
      incompleteness and the reinstatement wait fail.
    - M2-M4 and M13 widen a reach set: the second portion and bulb, the jejunum for ILEAL, the ileum for JEJUNAL, the
      small bowel.
    - M5, M9 and M10 drop the route or its verification.
    - M6-M8 and M16 turn the completion arm off or widen it: incompleteness ignored, only a verified 'incomplete',
      the status not read, JEJUNAL needing a complete examination.
    - M11, M12, M15 and M20 change the question's form: always the extent question, always the class question, never
      the incomplete form, R6's words drifting.
    - M14: the stoma and pouch codes have no class.
    - M17: the class reads a reach R6 did not verify.
    - M18, M19, M21 and M22 empty JEJUNAL, ILEAL, STOMA or POUCH: the READY controls fail.
  - Existing tests: no expectation changed.
    - The test_interpretation_* modules (the replay pins among them), with test_pipeline_assess_events and
      test_readers_dispatch, went from 1,128 tests at 437b708bb to 1,146 on the repair, all passing.
    - The modules that switch on the new chain passed: test_change_context_events, both guard matrices,
      test_guard_mutation, test_guard_static, test_overlay_differential, test_pipeline_api, test_retry_reading_api,
      test_pipeline_interpret, test_models_event_inventory and test_peer_heading. That is 204 tests, 3 skipped.
    - The full Django suite passed: 7,951 tests, 7 skipped, in 4,209 s. It ran before a wrap of comment and docstring
      lines in the new pin module, which changed no logic; the module was re-run afterwards (18 OK).
  - Residuals, for the owner.
    - The route is read from the encounter's anatomy (D43's reading), not from the examination. Not built:
      - The input: "The patient has an end ileostomy after a total colectomy." / "The double-balloon enteroscope was
        advanced orally to the proximal ileum." / a biopsy there, with 44382 proposed.
      - 44382 is READY at 437b708bb and after D108; c2e53f8e asks the extent.
      - The schema gives the examination no route attribute. Reading the examination's own words for a stoma is a
        word read.
    - A stoma's or a pouch's TYPE is not read. A colostomy, a bariatric gastrojejunal "stoma" or a gastric pouch is a
      verified route for the stoma or pouch class beside an ileal reach, or a reach at the pouch. Not attested.
    - The retrograde route is not read: a retrograde enteroscopy through the colon into the ileum fits 44376-44379.
    - The jejunal class reads its reach only. If Gemini took an incomplete examination's reach from its intended
      target rather than its furthest point, a verified jejunal reach would still fit. The prompt asks for the
      furthest point, and this is not attested.
    - assess.py's module docstring does not name D108; this repair's ownership of assess.py was the call alone. The
      class check shares the EUS class check's id, with its own label.
    - Parity, report only: c2e53f8e gives an act to a family by its site's region (services.FAMILY_REGIONS,
      _family_for_act_in). The input: an EGD to the second portion, then a push enteroscopy to the proximal jejunum,
      and "Two gastric antral angioectasias were treated with argon plasma coagulation.".
      - c2e53f8e gives the gastric act to the EGD. It holds 44369 (performed_status, act_missing) and 43235
        (base_included), and READYs 43270.
      - The new path follows Gemini's own procedure for the act. Read as the enteroscopy's, 44369 and 43235 are READY
        and 43270 is held. Read as the EGD's, it matches c2e53f8e.

- **D109 The same-day E/M rule reads an act by its kind, places an act "earlier in the day" on the date of service, and
  counts a non-GI or unidentified act only as an act of this encounter (2026-11-11; the round-4 refutation of
  437b708bb, findings 13, 23, 14, 15 and 16; amends D81 and D94; repair key em-same-day).** Three defects of
  combination.procedure_day and facts.day_of, each measured against c2e53f8e (studio.validation.engine.assess, driven
  as tests/test_harness_engine.py drives it) on byte-identical texts.
  - **By kind (findings 13 and 23).** An in-office band ligation, or an anoscopy, that Gemini files under the visit
    (procedure office_em: the prompt's "the heading or line that introduces the part of the document the act is in",
    and an office note's only heading is the visit's) had family gi.office_em. That family is outside
    SAME_DAY_FAMILIES, and the family test ran before any usability check. So the act made no procedure day, even when
    its procedure was unverified (procedure_unsettled), and 99213 was READY: "No same-day procedure is documented".
    c2e53f8e holds 99213 with separate_em: "Other GI service is documented as performed on the same date". The same
    held for em_other and sedation.
    - The rule. combination.SAME_DAY_KINDS is computed from the catalogue: every kind a procedural family's entry
      lists (acts, bundled and unsupported acts), the examination kinds and the umbrellas. That is every schema kind
      except em_visit, em_prolonged, moderate_sedation and other. An act of such a kind, filed under a family outside
      SAME_DAY_FAMILIES (gi.office_em, gi.em_other, gi.sedation), is a same-day procedure. Its label is OTHER_GI's,
      "Other GI service", the installed routing's reading. It counts as C-3 counts an event: its time is
      current_encounter in any state, or its own words place it on the date (facts.day_of ON). It is done only with its
      kind usable as well, since the kind is what makes it a procedure; otherwise it is possible. An examination whose
      device is verified manual (a digital rectal examination, E13) is not an endoscopic examination and never counts.
    - Reading of the spec. "A positive current event" is read as procedure_day reads every other event: a positive or
      uncertain status (D62 and D75: a doubt is never an absence), and "current" as C-3 defines a counted event. The
      undatable, non-current history mention filed under the visit is NOT counted, so an indication's banding asks
      nothing. That keeps finding 16's dead end (an event_time question whose only answers exclude the E/M) away from
      the kind arm. Recorded residual below (time 'unknown').
    - SAME_DAY_FAMILIES is unchanged, so D81's legacy pin stands.
  - **Same-date frames (finding 14).** facts.day_of read a verified earlier_encounter time worded "earlier in the
    day", "Earlier that day" or "Earlier in the morning" as OFF the date: an endoscopy at its own encounter earlier
    on the same date. 99213 was READY ("Stated but not as done today: upper endoscopy"); c2e53f8e holds it with
    separate_em. Pre-existing since S08 (SAME_DAY_WORDS).
    - The rule. lexicon.SAME_DAY_FRAMES (the spec's markers and their siblings: earlier or later today, in the day,
      that day, the same day, this or that morning, afternoon or evening, in the morning, afternoon or evening, on the
      same date, on the date of service) are read WHOLE, as D54 reads CURRENT_FRAMES. The time's own words, folded,
      edges stripped and split at commas, semicolons and a standalone "and", must be made of frames and nothing else.
      Then the act is ON the date whatever time Gemini gives. Never a bare "that day", "that morning" or "in the
      morning". facts._frame_parts writes D54's split without a pattern, and a pin holds it equal to
      lexicon._FRAME_EDGES and _FRAME_JOINS. SAME_DAY_WORDS is unchanged and still read anywhere in the words, so the
      frames only add.
  - **D94 narrowed (findings 15 and 16).** D94 counted every gi.unsupported act and every act of no family ('') by
    date of service.
    - fb13's attested shape (not_gi, current_encounter with no words, other_clinician "radiology service") for "CT
      images obtained today were interpreted separately by the radiology service." made 99213 ask separate_em.
    - fb14's attested shape (an abdominal ultrasound named in the indication, earlier_encounter worded "Indication:",
      time_marker_missing) asked 99213's event_time, whose only answers exclude it.
    - c2e53f8e is READY on both.
    - The rule. combination.CURRENT_ONLY_FAMILIES = {gi.unsupported, ''}. Such an act counts only when its time is
      current_encounter (any state) and its performer is not verified to another clinician or facility. D94's office
      excision and its unidentified act still ask separate_em (their pins pass unchanged).
  - **What the findings' inputs now give.** Each READY at 437b708bb becomes held with separate_em, as c2e53f8e holds
    it:
    - finding 13: the headed note with the anoscopy and the banding; the banding alone; no procedure words; em_other;
      sedation; the anoscopy alone;
    - finding 23: D81's note with the banding filed office_em by its own words "office", the visit's "Office visit"
      or a heading;
    - finding 14: the EGD, banding and flexible sigmoidoscopy "earlier in the day", "Earlier in the morning" and
      "Earlier that day".

    Each hold at 437b708bb becomes READY, as c2e53f8e reads it:
    - finding 15: the CT and fb13's fluoroscopy line, with no time words or "today", procedure not_gi or unknown;
    - finding 16: fb14 r1, r2 and r3, "Reason for visit:", the "followed by" cholecystectomy, the unknown polypectomy.
  - **Effects besides.**
    - An unverified current time worded by frames (current_encounter "earlier in the day", unverified by D35's
      "earlier") was UNDATABLE, and the E/M asked event_time. It is now ON, a possible same-day procedure, and the E/M
      asks separate_em. The code stays held, and the question is the one the E/M rule needs: the date is established.
    - With no E/M code proposed, an act filed under the visit (or an act "earlier in the day") now makes a procedure
      day. So the visit's "has no supported proposal" item is not pushed: the legacy rule for every same-day
      procedure. D81's other_gi banding already behaved so, and c2e53f8e does the same: "1 documented service has no
      supported proposal and is not listed as unresolved: office / outpatient visit beside a procedure ...".
    - The routing stand-in reads such a family performed (it read historical), as the installed routing does.
    - The narrowing gives the visit's item back beside a radiology read.
  - **Cost on FRESH-2: none.**
    - Re-scored on the repair (fresh2-score/f2r4-em-same-day): A 96/6, B 177/15, C 171/19 plus 2 safe_hold, equal to
      f2r3intc. All 486 rows, 179 runs and 358 assessment and inventory files are identical. The replay pins pass.
    - Head-to-head run 1: 214/234 against installed 150/234, identical to h2h-r3final.json in every section. It is
      worse on the same 5 rows, all holds.
    - Census of 370 distinct recorded answers (FRESH-1, FRESH-2, tests/fixtures/interpretation; 2,982 events):
      - 0 events of the kind arm: office_em appears only on em_visit (28), sedation on moderate_sedation (32) and
        other (4).
      - 74 time words made only of frames; every one also holds a SAME_DAY_WORD ("today").
      - 138 not_gi or unknown events: the 4 current ones are fb13's radiology reads (FRESH-2 r1-r3, FRESH-1 r2),
        each other_clinician "radiology service", the words the finding-15 pin verifies; the other 134 are earlier,
        future or undated.
  - **Pins.** tests/test_interpretation_r4_em_same_day.py, 16 tests:
    - D109ProceduralKindWhateverItsFamily:
      - test_d109_the_procedural_kinds_are_every_act_a_procedural_family_lists;
      - test_d109_finding_13_the_headed_office_note_asks_separate_em;
      - test_d109_finding_13_its_variants;
      - test_d109_finding_23_d81s_office_banding_filed_under_the_visit;
      - test_d109_an_act_read_by_its_kind_is_done_only_with_its_kind_usable;
      - test_d109_an_act_filed_under_the_visit_earlier_in_the_day_counts;
      - test_d109_controls_what_the_kind_never_reads (a DRE, moderate sedation, kind other, 2024, an indication's
        banding).
    - D109SameDateFrames:
      - test_d109_finding_14_an_act_earlier_in_the_day_is_on_the_date;
      - test_d109_the_egd_earlier_in_the_day_is_documented_as_performed;
      - test_d109_a_current_time_worded_earlier_in_the_day_is_on_the_date;
      - test_d109_the_frames_are_read_whole_as_d54_reads_them;
      - test_d109_the_frame_split_is_d54s;
      - test_d109_controls_another_date_stays_off.
    - D109CurrentOnlyFamilies:
      - test_d109_finding_15_a_study_read_by_the_radiology_service_makes_no_procedure_day;
      - test_d109_finding_16_a_study_named_in_the_indication_asks_nothing;
      - test_d109_an_act_of_this_encounter_still_counts.
    - At 437b708bb the module gives 33 failures and 17 errors; every control passes there.
  - **Mutation proof.** Each mutant was in its own copy, applied once and confirmed by sha and marker, and re-run on
    the final tree:
    - M1, no act read by its kind: 12 fail;
    - M2, no frames: 12 fail;
    - M3, D94 not narrowed: 10 fail;
    - M4, the performer arm dropped: 4 fail (finding 15);
    - M5, the time arm dropped: 6 fail (finding 16);
    - M6, the kind arm counting every undatable act: the indication-banding control fails;
    - M7, a DRE counts: its control fails;
    - M8, frames matched anywhere: 2 fail;
    - M13, frames matched anywhere, punctuation as space: 3 fail, including "earlier in the day, before her visit";
    - M9, the family's own label: 12 fail;
    - M10, no edge strip: the split pin fails, 5 subtests;
    - M11, the kind not read for done: 1 fails;
    - M12, the listed acts only: the kinds pin fails.
    - The controls pass under every decision mutant.
  - **Suites.** No existing test's expectation changed.
    - The test_interpretation_* modules (36 at 437b708bb, 37 with the new one) with test_pipeline_assess_events and
      test_readers_dispatch: 1,128 tests at 437b708bb, 1,144 on the repair, all passing.
    - test_change_context_events, both guard matrices, test_guard_mutation, test_guard_static,
      test_overlay_differential, test_pipeline_api, test_pipeline_interpret, test_retry_reading_api,
      test_models_event_inventory, test_peer_heading, test_repairs_ec5_reportruns, test_repairs_7c8_p1reports,
      test_repairs_7c8_p1sends and test_repairs_r3_integration_guards: 292 tests, OK, 3 skipped.
    - The patch applied to a fresh archive of 437b708bb is byte-identical to the repair tree.
  - **For the owner: the literal narrowing turns one constructed shape from held to READY.**
    - The input: D81's office lines with "Earlier today, excision of a 1 cm sebaceous cyst on the upper back was
      performed in the office.", read as not_gi (or unknown), earlier_encounter "Earlier today" (verified, ON the date).
    - 437b708bb and c2e53f8e hold 99213 with separate_em; the repair is READY, because the time is not
      current_encounter.
    - "Earlier in the day" gives the same READY, where c2e53f8e holds (437b708bb was READY there too).
    - Not attested: no recorded not_gi or unknown act carries same-date words.
    - The alternative is one condition: count such an act when its time is current_encounter OR day_of is ON (C-3's
      own counting rule, the kind arm's), still never another's verified read. It is
      repair4/em-same-day/alt-patch.diff, applied on top of patch.diff, with its pin
      test_d109_alt_an_act_its_own_words_place_on_the_date_still_counts, mutation-proved: 4 subtests fail under the
      literal rule.
    - It measures: all pins and the D80, D81 and D94 pins pass; FRESH-2 has 0 rows changed; the head-to-head is
      identical.
    - Its cost: "CT abdomen obtained earlier today ..." with performer unknown holds 99213 where c2e53f8e is READY.
      With the read verified to the radiology service it is READY.
  - **Recorded residuals.**
    - An act of kind 'other' filed under the visit (the D94 excision read office_em, kind other) makes no procedure
      day. 99213 is READY at 437b708bb and on the repair; c2e53f8e holds it. 'other' is outside the spec's procedural
      kinds.
    - A procedural act filed under the visit whose time is 'unknown' ("Rubber band ligation of one internal hemorrhoid
      was performed.", office_em) is READY at 437b708bb and on the repair; c2e53f8e holds it. The kind arm counts only
      C-3's events.
      - Counting every undatable act (M6's reading) would ask event_time there.
      - It would also ask event_time on the indication's banding, where c2e53f8e is READY.
    - Finding 15's other variants still hold where c2e53f8e is READY: an ECG obtained in clinic today, labs drawn in
      clinic today, performer unknown or the team. The narrowing reads time and performer only, never what the act is;
      that is D94's class (the office excision).
    - services.inventory and completeness still omit an act filed under the visit: coverage reads a session's
      catalogue acts, and gi.office_em lists em_visit only. The E/M's check now names it ("Other GI service").
      derived.procedure_day and the routing stand-in still list it under gi.office_em. None of these is in this
      repair's files.
    - Whole frames: "earlier in the day, before her visit" stays OFF (READY beside it), as the spec's "matched as
      whole frames like D54's" requires.
    - "Earlier that day" and "later that day" read the day they refer to as the date of service.

- **D110 Every app receipt of this revision after the bound counts toward the switch-back's since, whatever it
  replaced and however it ended (2026-11-11; refutation round 4, findings 21 and 20; amends D95 and D84).**
  replaced_since now counts every `app` receipt of this revision written after its last completed switch-back to the
  target (D82's bound). D95's served test is removed: a receipt that was successful, or one that parked a role
  (`_parked_anything`, 'replaced' non-empty). The bound, the target (D83), the order by stamp and D59's fallback are
  unchanged.
  - **Finding 21.** In an outage state, `app` is a swap: the HTTPS stage proxies to 9150 and no running web answers
    it.
    - The swap parks OLD's pair and starts this revision's web on 9150, in front of traffic. Its worker never becomes
      ready, so the undo restores OLD's pair.
    - The undo's close names e1 for a reason OLD's worker acts on, so OLD's worker is held. The receipt says "Install
      this revision again". It records hazards, stages_closed and states_put_back, and no 'replaced'.
    - D95 therefore dropped that window. A2 (blue/green over OLD, 10:30) gave the since. e1's record (10:03:30, in
      A1's window) was not touched, so the switch-back completed and B8 started OLD's worker while e1's hazard stood.
    - The installed release c2e53f8e refuses the same input. a4dcbea72 behaved as D95 does.
  - **Why not narrower.** A receipt cannot always say whether its phase put this revision's pair in front of traffic.
    - A swap's undo records only its close, and a swap that re-raises its first failure carries that failure's
      details.
    - "Could not then be closed / put back" carries none, and a KeyboardInterrupt writes a receipt with no details at
      all.
    - A refusal at the switch's start (switch problems, baseline drift) comes after migrate has run this revision's
      migrations.
    - The verifier's counterfactual (count a receipt that carries 'stages_closed') closes finding 21's exact shape and
      no other. mut-8 below measures it.
  - **Finding 20.** INSTALL.md (Switching back) and the replaced_since and phase_switch_back docstrings stated D82's
    rule, and the D84 pin enforced it. They now state the since as D95 and D110 read it:
    - every `app` receipt of this revision written after the last successful `switch-back` to that pair, whatever it
      replaced and however it ended (the kinds of receipt are listed);
    - an earlier time only refuses more;
    - a receipt whose order cannot be told is counted;
    - the pair's own status quo after that switch-back lasts until this revision's next `app` began;
    - a switch-back that did not complete, one to another revision and another revision's are no bound;
    - when the receipt the pair is read from is older than that switch-back, the time is that switch-back's own start.
  - **Measured.** All through the real install.main in BlueGreenWorld, using a probe in private copies of 437b708bb
    (D95) and of the work tree (D110). c2e53f8e was run through its own harness.

    | Input | D95 | D110 | c2e53f8e |
    | --- | --- | --- | --- |
    | Finding 21, swap undone, e1 'conflict', 'unknown' or 'outcome' | exit 0, since 10:30, OLD's worker started while e1 stands | exit 1, since 10:02:30, nothing started or stopped | exit 1 |
    | Finding 18, undone at S3 (nginx -t, and HTTPS after the reload), OLD's 'unknown' or 'outcome' at 10:20 | exit 1, 10:02:30 | exit 1, 10:02:30 (unchanged) | not run |
    | Finding 19, three revisions | exit 1, 10:02:30 | exit 1, 10:02:30 (unchanged) | not run |
    | No first app, OLD's 'unknown' at 10:20 | exit 0, 10:30 | exit 0, 10:30 | exit 1 |
    | A1 failed at S1 (replaced={}), then the same | exit 0, 10:30 | **exit 1, 10:02:30** | exit 1 |
    | A1 refused before S1 (baseline drift), then the same | exit 0, 10:30 | **exit 1, 10:02:30** | exit 1 |

    - The real host's receipts were read only; docker was never called and nothing was written. /home/claude/cpt-studio-install-20261023
      holds 13 app receipts, all ok, one per revision, and no switch-back. The target and the since are unchanged for
      13 of 13 revisions (12 targets, and 1 "names no previous web").
    - The change is monotone. The counted set only grows and every branch takes a minimum, so since(D110) <= since(D95)
      on every receipt set. The since is read only by the touched filter (the refusal) and by the receipt's
      touched_since, so D110 only adds refusals.
  - **Cost: false refusals, fail-closed.** Nothing is handed over.
    - After an app of this revision that failed or was refused before its pair served, the since reaches that app's
      start: an S1 failure; a refusal before S1 (switch problems, baseline drift, credential checks); an interrupted
      app.
    - So a record the target wrote while it served alone before this revision's next app refuses the switch-back while
      it stands: 'unknown' until it is reconciled, 'outcome' until a member's addendum (D82).
    - The baseline-drift refusal is routine, because app.quillmd.com's release changes on every deploy of that
      co-tenant. So this cost is likelier than finding 18's path.
    - c2e53f8e refuses every such input too, because it reads undo_hazards whole.
    - A completed rollback-app is no bound either: only a completed switch-back to the target is.
  - **Existing tests changed, where D110 moves them.**
    - SwitchBackSinceTests.test_d65_...: the not-ok receipt with replaced={} (10:01:15) now moves the since from
      10:02:30 to 10:01:15. An assertion of 10:02:30 was added with another revision's receipt alone, so that check
      still discriminates.
    - SwitchBackSinceTests.test_d59_a_receipt_that_records_no_time_...: the earlier not-ok receipt (09:00) now counts,
      so 10:01:00 becomes 09:00:00. It is now put after the other-revision and other-phase receipts, asserted, then
      removed, so the rest of the fallback keeps its expectations (10:00:40.25, 10:00:30, 10:00:10 and 10:00:00
      unchanged). Its comments are updated.
    - SwitchBackRound3Tests.test_d84_install_md_...: it checks the new since phrases, and asserts that D82's two
      phrases are absent.
    - InstallDocTests.test_d59_switching_back_...: its citation becomes "`switch-back` to that pair, whatever it
      replaced and however it ended (DECISIONS D59, D65, D82, D95 and D110)".
    - These pass unchanged: D95's two sequences, D82's three pins, D83's five pins, and D59's two through-main tests.
  - **Pins**, in ops/test_install_bluegreen.py D110SinceCountsEveryAppReceiptTests:
    - test_d110_finding_21_a_swap_undone_after_its_web_served_counts_while_its_record_stands: finding 21's sequence
      through install.main, for 'conflict', 'unknown' and 'outcome'. A1 parked both roles, ran this revision's web on
      9150, and its receipt has no 'replaced'. The switch-back refuses (exit 1, touched_since 10:02:30, nothing
      started or stopped) while e1 stands, and completes once it is cleared.
    - test_d110_every_app_receipt_of_this_revision_after_the_bound_counts_whatever_it_records: receipts written by
      hand. These count: a swap's undo, an interrupted app (no details), a refusal before anything changed, an S1
      failure, and one with details None and no time. These do not: one written before the completed switch-back,
      another revision's, and another phase's.
    - test_d110_cost_an_app_that_failed_at_s1_counts_so_a_record_the_target_wrote_meanwhile_refuses: the recorded
      cost, through install.main (finding 18's control).
    - test_d110_finding_20_the_docstrings_state_the_since_as_it_is_read.
  - **Mutations.** Each is a private copy that differs from the work tree in one file, with "mutation applied: True"
    printed before the run. Each run covers the 24 tests of the five since and doc classes.
    - mut-6, install.py as at 437b708bb: 12 failures (finding 21 x3, every receipt x5, the cost, the docstrings, D59's
      fallback, D65). The finding-21 switch-back exits 0.
    - mut-7, D95's filter and `_parked_anything` restored, docstrings kept: 11 failures.
    - mut-8, D95 plus the counterfactual ('stages_closed' counts): 7 failures.
      - The finding-21 pin passes.
      - The every-receipt pin fails for the interrupted, refused, S1 and no-details receipts. The cost pin, D59 and
        D65 fail too.
      - So "whatever it records" is pinned beyond finding 21's shape.
    - mut-9, INSTALL.md as at 437b708bb: the D84 pin and the D59 doc pin fail.
    - mut-10, the two docstrings as at 437b708bb: the docstring pin fails.
  - **Suites.** ops 656/656 (652 + 4); ops/verification 43/43; the 16 Django modules that load install.py 323/323.
  - **Residuals:**
    1. Findings 18 and 19 are accepted fail-closed false refusals (the owner's ruling: a refusal never hands a record
       to the previous revision). D110 leaves them unchanged, as measured, and adds the S1 and pre-S1 cost above, which
       is of the same class.
    2. An installer killed outright writes no receipt, so no receipt counts its window. This was checked: no hand-over
       follows on the documented recoveries.
       - Keeping the new pair means a same-revision re-run. The switch-back then either finds no target since its last
         switch-back (D83), or reads an earlier receipt whose since already covers the window.
       - Going back runs rollback-app, whose conservative read refuses on any hazard.
    3. Text outside this repair's ownership:
       - switch_back_services' docstring cites "(replaced_since, D59 and D82 ...)". It states no rule, so it is not
         wrong, but its citation is short of D95 and D110.
       - SwitchBackRound3Tests' class docstring still describes D82's successful-only rule.

- **Round-4 integration (2026-11-11; d353e64df, the seven patches as built) and the family parity audit.**
  - The seven patches applied unchanged. The combined engine and guard suites pass (1354 tests), and so does the ops
    suite. FRESH-2 and the head-to-head are unchanged, because no recorded document has these shapes.
  - The patches' independent reviews found problems that are open at d353e64df:
    - em-same-day: D94's narrowing drops an act that its own words place on the date, or whose time is unknown
      (a wrong READY), and its anaphoric frames ('earlier that day') name another day.
    - enteroscopy: with a verified stoma or pouch and an ileal reach, both the oral and the stoma or pouch codes are
      READY.
    - Smaller problems in eus-lower, questions, ercp and currency-pairing.
  - The parity audit compared 142 installed rules in four families and found 17 gaps: colonoscopy and
    sigmoidoscopy 2, EGD 8, EUS 4, modifiers and review 3; 1 critical, 7 high, 4 medium, 5 low.
  - Round 5 (wf_5d0c6806-f7d) repairs them as D111-D129 in nine patches: em, enteroscopy-route, egd, eus2, colon,
    questions2, ercp2, currency2 and second-review.
  - Recorded, not repaired: egd gaps E (a gastric tattoo proposed as 43243) and F (a stated stop contradicting the
    stated reach), eus gap 3 (43237 on an esophagus-only EUS), and the ops review's documentation nits (repaired at
    integration).
- **D111 Every act the same-day rule reads has its date read by one currency rule (2026-11-11; the review of D109,
  em-same-day problems 0, 1 and 2; amends D109 and D94; repair key em).** D109 read "current" two ways. An act of
  gi.unsupported or of no family (Gemini's procedure 'unknown': CURRENT_ONLY_FAMILIES) counted only when Gemini gave
  its time as current_encounter, and the kind arm, which counts an act whose own words place it on the date, could never
  reach such an act, because the CURRENT_ONLY branch took family '' and gi.unsupported first. Three wrong READYs, each
  measured against c2e53f8e (engine.assess as tests/test_harness_engine.py drives it) on byte-identical texts:
  - problem 0: D81's office lines with "Earlier today, excision of a 1 cm sebaceous cyst on the upper back was performed
    in the office." (kind other) or "Earlier today, rubber band ligation of one internal hemorrhoid was performed in the
    office.", time earlier_encounter worded "Earlier today" (verified, ON the date), procedure not_gi or unknown.
    d353e64df READY; c2e53f8e and 437b708bb held, separate_em.
  - problem 1: the same excision or banding with Gemini's time 'unknown'. d353e64df READY with no question; c2e53f8e
    held (separate_em); 437b708bb event_time (READY only for the banding filed under the visit, D109's residual).
  - problem 2: "Earlier in the day, rubber band ligation ..." with procedure unknown, ON by D109's frames. d353e64df
    and 437b708bb READY; c2e53f8e held.
  - The rule (combination.procedure_day). The acts it reads are unchanged: a procedure family or gi.other (D81), every
    act of gi.unsupported or of no family (D94), and an act of a procedural kind filed under any other family (D109),
    which now includes gi.unsupported and family '' acts (the spec's "the kind arm applies to family '' and
    gi.unsupported acts too"). An act of gi.unsupported or no family whose performer is verified to another clinician
    or facility is never read (D109, finding 15). Every act's date is read by facts.day_of, never by Gemini's time value
    alone:
    - ON (a usable current time, or its own words or literals place it on the date, an earlier_encounter time worded
      "Earlier today" included) counts, done or possible as before;
    - OFF never counts;
    - UNDATABLE is listed, so the E/M asks event_time (C-3). This covers a time 'unknown', a current time that does not
      verify, and an open time.
    - Exception: an act outside the procedure families and gi.other (read by its kind, gi.unsupported or no family)
      whose time Gemini gives as earlier_encounter or future with no marker. That is a history mention (finding 16's
      ultrasound named in the indication, D109's indication banding), and it never counts, as at D109.
  - An act of a procedural kind of gi.unsupported or of no family is read by its kind: labelled "Other GI service" (as
    c2e53f8e words it: "Other GI service is documented as performed on the same date") and done only with its kind
    usable. An act of kind 'other' keeps D94's arm and label (the excision: "Service outside the GI profiles", "A
    procedure CPT Studio could not identify"; D94's pin unchanged).
  - Built where the spec is not literal (a disagreement, recorded):
    - The spec says "an earlier or future time that day_of reads OFF never counts (finding 16's history mention)". But
      day_of reads finding 16's mention UNDATABLE, not OFF: its earlier_encounter time is unverified
      (time_marker_missing). A literally uniform rule has two readings, and both break a stated constraint:
      - list it, which holds finding 16 again with event_time, where the spec keeps it READY;
      - skip every UNDATABLE earlier or future act, which takes C-3's question away from the procedure families and
        gi.other (D81: "a hold, never a READY").
      Input for the second: 'Indication: rectal bleeding after rubber band ligation of an internal hemorrhoid.' (other_gi,
      earlier_encounter 'Indication:', unverified). d353e64df and 437b708bb ask event_time; the skip reading is READY.
      c2e53f8e is READY here too, but an unverified earlier time of a GI procedure can equally be an act of today
      ("Polypectomy was performed" given earlier with no marker), so dropping the question is not "only adds holds".
      Built: the exception applies outside the procedure families and gi.other only. Both sides are pinned and
      mutation-proved (M3, M13).
    - The kind arm's exclusion of a manual examination (E13) is not extended to the D94 arm, which reads an act of
      gi.unsupported or of no family of any kind. A digital rectal examination of no family is still read (as at
      d353e64df when current), so with time 'unknown' it now asks event_time, as 437b708bb does. c2e53f8e is READY.
      This is a recorded cost, not repaired, because extending the exclusion would remove a hold.
  - What the inputs give now: every input of problems 0-2 (the excision and the banding, "Earlier today" and "Earlier in
    the day", procedure not_gi or unknown; the unknown-time excision and banding, not_gi, unknown or filed under the
    visit) asks separate_em or event_time, never READY. Findings 15 and 16 stay READY, the 'unknown' polypectomy (now
    read by its kind) included.

- **D112 The same-date frames are anchored to today (2026-11-11; the review of D109, problem 3; amends D109).**
  lexicon.SAME_DAY_FRAMES held anaphoric frames. Problem 3's input:
  - V1 "Office visit: established patient seen today for follow-up of melena."
  - P1 "On 10/30/2026 she was seen in the emergency department of another hospital for melena."
  - P2 "Earlier that day she had undergone an upper endoscopy at that hospital, which showed a clean-based duodenal
    ulcer." Gemini gives an EGD examination, earlier_encounter worded "Earlier that day" (verified), performer
    other_facility.

  At d353e64df day_of read it ON, so 99213 asked separate_em ("Upper GI endoscopy ... is documented as performed on the
  same date") and, with no E/M proposed, the visit's "has no supported proposal" item was dropped. c2e53f8e and
  437b708bb give 99213 READY with the item listed.
  - The rule. Removed: "earlier that day", "later that day", "earlier that same day", "later that same day", "earlier
    that morning", "earlier that afternoon", "later that morning", "later that afternoon", "later that evening" and
    "that same day". Each names whatever day the sentence before it names. Kept:
    - every frame anchored to today ("today", "earlier today", "this morning", "earlier this afternoon", "tonight");
    - "earlier/later in the day" and "earlier/later in the morning/afternoon/evening" (finding 14's B4-B6; the spec's
      "earlier in the day" and "later in the day");
    - "on the date of service";
    - the "same day" and "same date" phrasings that facts.SAME_DAY_WORDS already reads anywhere.

    The spec's parenthetical list ("earlier today" ... "later in the day") is read as examples of today-anchored
    frames, not as the whole list. Read as the whole list, finding 14's B6 ("Earlier in the morning I performed a
    flexible sigmoidoscopy ...", which c2e53f8e holds) would be OFF and 99213 READY. Mutant M14 shows it.
  - Problem 3's input is OFF again (verified by its "earlier"). 99213 is READY and the visit item is listed, as at
    437b708bb.
  - **THE SPEC'S COST, AGAINST c2e53f8e, ON A CONSTRUCTED INPUT: finding 14's G2 goes from held to READY.**
    - The input: "Earlier that day, I performed a flexible sigmoidoscopy, which showed internal hemorrhoids.", an
      office note with no other day named, earlier_encounter by "I".
    - d353e64df held 99213 with separate_em, and so does c2e53f8e ("Flexible sigmoidoscopy ...").
    - The repair is READY: "Earlier that day" is no frame, and its "earlier" marker verifies the earlier_encounter time,
      so the act is OFF.
    - This is the shape D112 removes, and it was G2 in D109's own pin. That pin's expectation is changed (below) and
      the new READY is pinned in the r5 module so it is visible.
    - No structural rule can tell G2 from problem 3 within EB1. The only difference is the sentence before, which a
      check may never read.
    - Not attested: FRESH-1 and FRESH-2 record no anaphoric time words (census below).
  - Other effects:
    - "Later that morning" or "Later that afternoon" (earlier_encounter with no "earlier" marker, so unverified) is
      UNDATABLE again. For a procedure family it asks event_time, as at 437b708bb; c2e53f8e is READY.
    - The routing stand-in reads such an act by its own time again.
  - Residual, outside this repair's ownership. "Earlier that same day" and "the same day" stay ON through
    facts.SAME_DAY_WORDS ("same day", read anywhere in the words since S08). So problem 3 worded "Earlier that same
    day" still asks separate_em, as it did at 437b708bb; c2e53f8e is READY.
  - Stale docstring, outside this repair's ownership: facts._same_day_frame still gives "earlier that day" as an
    example of a frame.

- **D113 The separately identifiable statement is today's visit's (2026-11-11; the family parity audit of d353e64df,
  modifiers-review gap 0; gap 2 recorded, not repaired).** combination.separate_statement read the code's own visit
  events, then ANY visit event, with no time or performer filter. Gap 0's input:
  - the document: "Office visit: established patient seen today for dyspepsia." / total time / an EGD to the second
    portion of the duodenum / its antrum biopsy / "At her office visit on 10/01/2026, a significant, separately
    identifiable E/M service was provided.";
  - E3, that earlier visit: em_visit, earlier_encounter "on 10/01/2026" (verified), separately_identifiable stated;
  - today's E0: not_stated;
  - Corti proposes 99213 and 43239.

  d353e64df made 99213 READY and quoted the 10/01/2026 visit as this one's. So did variant C6, where today's visit
  verifiably denies it. c2e53f8e holds both with separate_em.
  - The rule. The statement is the words of the first usable 'stated' value among:
    - the code's own visit events;
    - else another visit event of this encounter: its time a usable current_encounter, its performer not verified to
      another clinician or facility.

    Never another encounter's visit: the installed reader refuses a statement about another encounter. A 'stated'
    value whose own words carry a negator (lexicon.negation, the reader a denial is verified by) is no statement, and a
    denial never releases.
  - Built where the spec is not literal (recorded). "A statement whose own words are negated never releases" is built
    as no release; it does not silence another statement.
    - The silencing reading was built first: any usable denial among today's visits meant None. It was measured on
      FRESH-2 B/fb10 r1-r3, a real two-visit note: "The GERD evaluation and management is a significant, separately
      identifiable E/M service." (stated) and "The rectal bleeding assessment is part of the procedure and is not a
      separate E/M service." (denied).
    - An E/M code's events are every visit of its session, so the denial silenced the GERD statement. separate_em was
      added to 99204 and 99214 in all three runs, 6 rows, with the registry expecting 99214 READY.
    - So it is not built. fb10's shape is pinned as a control, and the silencing variant is mutant M9.
    - The cost, on a constructed input: E0 states it and an addendum visit of today denies it. That is READY, as at
      d353e64df; c2e53f8e holds it.
  - Gap 2 is RECORDED, NOT REPAIRED, because it cannot be reached inside this ownership.
    - The input: "Modifier 25 requires that a significant, separately identifiable E/M service is documented.", with
      E0 given 'stated' and the words "a significant, separately identifiable E/M service is documented".
    - Those words do verify in their own passage: they are located, and they are in the attribute's cited passage. So
      "a stated value whose words do not verify in its own passage is no statement" is already what verify.usable
      enforces, and it does not catch this input.
    - What makes gap 2 wrong is the clause the words leave out ("requires that"). Under EB1 a check reads only the cited
      words, and those words, read alone, state it.
    - The repair belongs in the prompt or in verify.separate_words (a marker requirement for 'stated'), both outside
      this repair's files. EB4 rules out a word-list patch for an off-contract answer.
    - The result is unchanged: 99213 READY at d353e64df and on the repair, held at c2e53f8e. Severity low,
      off-contract.
  - Cost, on a constructed input: an addendum of today by Dr. Lena Park, verified as another clinician (the documenting
    endoscopist is named), stated. It now asks separate_em, as the spec requires ("performer not verified other").
    d353e64df and c2e53f8e are READY.

- **D111-D113, what was edited.**
  - studio/interpretation/combination.py: procedure_day (the currency rule and the kind arm), the comments on
    CURRENT_ONLY_FAMILIES and SAME_DAY_KINDS (both values unchanged), and separate_statement. SAME_DAY_FAMILIES is
    unchanged, so D81's legacy pin stands.
  - studio/interpretation/facts.py: day_of's docstring only. Its logic is unchanged, since 'unknown' was already
    UNDATABLE.
  - studio/interpretation/lexicon.py: SAME_DAY_FRAMES and its comment.
  - tests/test_interpretation_r5_em.py: NEW, 16 tests.
  - tests/test_interpretation_r4_em_same_day.py: two expectations changed, both D112's.
    - FINDING_14 loses its G2 row, so test_d109_finding_14_an_act_earlier_in_the_day_is_on_the_date covers B4-B6. G2's
      new READY is pinned in r5.
    - test_d109_the_frames_are_read_whole_as_d54_reads_them: 'Earlier that day' is now facts.OFF (it was facts.ON).
    - The two docstrings that name it are updated.
    - No other existing test changed.
- **Pins.** tests/test_interpretation_r5_em.py, 16 tests.
  - D111OneCurrencyRule:
    - test_d111_problem_0_an_act_its_own_words_place_on_the_date_makes_a_procedure_day (4 subtests);
    - test_d111_problem_2_earlier_in_the_day_whatever_the_procedure (4);
    - test_d111_problem_1_an_unknown_time_asks_event_time (5, with the question's exact text);
    - test_d111_the_kind_arm_reads_an_unidentified_or_non_gi_act_too (3);
    - test_d111_findings_15_and_16_stay_ready (7, control: a CT "earlier today", ON, read by the radiology service, and
      the 'unknown' polypectomy included);
    - test_d111_an_act_of_a_procedure_family_keeps_c3s_question (control).
  - D112TodayAnchoredFrames:
    - test_d112_problem_3_the_outside_egd_earlier_that_day_is_off_the_date (also the visit item, no code proposed);
    - test_d112_the_anaphoric_frames_are_no_frames (the tuple and 4 subtests);
    - test_d112_finding_14s_g2_earlier_that_day_is_read_by_its_marker (the recorded cost);
    - test_d112_controls_today_anchored_frames_stay_on (5, control).
  - D113TodaysVisitStatement:
    - test_d113_gap_0_another_encounters_statement_never_releases (also without member values);
    - test_d113_gap_0_todays_denial_beside_another_encounters_statement (C6);
    - test_d113_a_statement_whose_own_words_are_negated_never_releases;
    - test_d113_fb10_a_denial_never_silences_another_of_todays_statements (control: fb10's shape and the gap-0
      document both ways);
    - test_d113_a_visit_by_another_clinician_or_of_an_unverified_time_never_releases (2);
    - test_d113_controls_todays_statement_still_releases (C4, two addenda, C2, C3).
  - At d353e64df the module gives 23 failures across 11 tests. The five control tests pass there.
- **Mutation proof.** Each mutant is in its own copy of the work tree, with the anchor asserted once, the sha before and
  after, and "mutation applied: True" printed. Each copy is run over the r5, r4 em, r3 families and D94 modules:
  - M1, D109's literal rule (an act of gi.unsupported or no family ON only with a current_encounter time): 8 fail
    (problems 0 and 2).
  - M2, an 'unknown' time outside the procedure families not listed: 5 fail (problem 1).
  - M3, the history-mention exception dropped: 10 fail (finding 16 in r4 and r5, D109's indication banding).
  - M4, the verified-other exception dropped: 7 fail (finding 15 in r4 and r5).
  - M5, the kind arm off for gi.unsupported and '': 6 fail.
  - M6, the anaphoric frames restored: 4 fail.
  - M7, any visit event read: 4 fail (gap 0 C1, C6, the verified-other and the unverified-time addenda).
  - M8, the negator check dropped: 1 fails.
  - M10, the performer filter dropped: 1 fails. M11, the time's usability dropped: 1 fails.
  - Control mutants:
    - M9, a denial silences every other statement: the fb10 control fails.
    - M12, the code's own visit events only: 2 fail.
    - M13, the history-mention exception extended to the procedure families: 3 fail (the by-family control and "Later
      that morning/afternoon").
    - M14, the spec's parenthetical read as the whole list (seven frames only): 5 fail. The failures are the D112
      control's and finding 14's B6, "Earlier in the morning", which c2e53f8e holds; the r4 frame-split pin (every
      SAME_DAY_WORD a frame); and the r5 frame-tuple pin.
- **Suites** (t.sh on Postgres 55461, a new suffix per run).
  - Every tests.test_interpretation_* module (43, the new one included), tests.test_pipeline_assess_events,
    tests.test_readers_dispatch, tests.test_guard_static and tests.test_guard_mutation: 1,272 tests, OK. The same set
    on d353e64df: 1,256 tests, OK.
  - test_change_context_events, both guard matrices, test_overlay_differential, test_pipeline_api,
    test_pipeline_interpret, test_retry_reading_api, test_models_event_inventory, test_peer_heading,
    test_repairs_ec5_reportruns, test_repairs_7c8_p1reports, test_repairs_7c8_p1sends and
    test_repairs_r3_integration_guards: 267 tests, OK, 3 skipped.
  - The replay pins pass. No fixture was regenerated. No ops file changed.
- **Cost measured.**
  - FRESH-2, re-scored on the repair (fresh2-score/f2r5-em) and on a d353e64df copy (f2r5-em-base): A 96/6, B 177/15,
    C 171/19 plus 2 safe_hold, both. Row by row, 0 of 486 rows, 0 of 179 runs and 0 of 358 assessment and inventory
    files differ.
    - Against f2r3intc, one row differs: A/note8 r3 45385, asked technique -> statement_scope. That is D102's, already
      in d353e64df, and not this repair's.
  - FRESH-1 (f1r5-em against f1r5-em-base, corpora A, B and C): 0 of 486 rows and 0 of 358 files differ.
  - Head-to-head (repair5/em/h2h.json): identical to h2h-r3final.json in all 7 sections. Run 1 is 214/234 for the new
    path (A 34/34, B 59/64, C 121/136) against the installed engine's 150/234; worse 5, better 69.
  - No new false_ready, false_exclusion, dropped_question or ready_wrong_facts.
  - Census of the 358 recorded FRESH-1 and FRESH-2 inventories, read by both trees:
    - procedure_day or separate_statement moves on 1 inventory: FRESH-1 C/PAR-006 r2's E12 (no family, kind other,
      time unknown, its performer an open question) is now listed undatable. The document proposes no E/M code, so no
      row moves.
    - 0 anaphoric time words.
    - The separately identifiable values are fb10's 6 stated and 6 denied, all on today's visits. None is on another
      encounter's visit, and none is a negated 'stated' value.
    - No act outside the procedure families has an earlier time ON the date.
  - The four engines on the constructed inputs: repair5/em/out/table4.txt (c2e53f8e, 437b708bb, d353e64df, the repair),
    raw outputs in repair5/em/out/{installed,newpath-437b,newpath-base,newpath-work}.json.
- **Recorded residuals and costs** (constructed; each is a hold, never a READY, unless it says otherwise):
  - A history mention whose time Gemini leaves 'unknown' now asks the E/M's event_time where c2e53f8e is READY. The
    question's only answers exclude the E/M (finding 16's dead end). Inputs:
    - "Indication: Dilated common bile duct on abdominal ultrasound; ..." (not_gi), as at 437b708bb;
    - "Indication: rectal bleeding after rubber band ligation ..." filed office_em;
    - a digital rectal examination of no family, as at 437b708bb.

    The spec accepts this cost: "a time 'unknown' (undatable) is listed UNDATABLE".
  - G2 is READY where c2e53f8e holds (D112, above).
  - "Earlier that same day" stays ON (SAME_DAY_WORDS, above).
  - Gap 2 is open (above).
  - E0 states it and an addendum of today denies it: READY, as at d353e64df; c2e53f8e holds (above).
  - A stated addendum by another clinician, verified, now asks separate_em where c2e53f8e is READY (above).
  - D109's residuals remain unchanged: finding 15's ECG and labs held, an act of kind 'other' filed under the visit not
    read, and services.inventory omitting an act filed under the visit.

- **D121 An EUS told only through its act is an upper EUS for C-4 (2026-11-11; the round-4 parity audit, EUS gap 1;
  amends C-4, D70, D96).** C-4 read the upper EUS from the EUS session's done examinations only.
  - The gap (high). An EUS that Gemini's answer tells only through its act - an FNA, an injection or a drainage, with no
    EUS examination event - left the EGD part of nothing. The audit's input (battery 4, g2b_noexam): 'UPPER ENDOSCOPY
    REPORT' / 'The gastroscope was advanced to the second portion of the duodenum; ...' / 'EUS-FNA of a 22 mm
    hypoechoic mass in the pancreatic body was performed with a 22-gauge needle.'
    - d353e64df: 43235 READY beside 43242, beside 43238, beside 43253 (an act-only celiac plexus block) and beside 43240
      (an act-only pseudocyst drainage); 43235 alone READY too. With no proposal, the EGD's own no_proposal item and
      second-review mark were listed.
    - c2e53f8e: 43235 held base_included in every case: "Is 43235 reported separately from 43242 for this
      examination?", and alone "... from the endoscopic ultrasound ...". services._included marks the EGD included in
      the EUS service its act makes, so with no proposal only the EUS's item is listed. On the drainage input it also
      lists an EGD 'not_covered' act, because its reader reads the lumen-apposing stent as an EGD stent.
  - The rule (coverage.sessions, C-4 block). With no done EUS examination, today's done EUS acts are the session C-4
    reads (eus_act: an EUS kind, with its kind and procedure usable). So session_events is the done examinations, else
    those acts.
    - Placed nowhere lower, the session is an upper EUS, and the EGD is its endoscopic portion (part_of 'gi.eus').
    - Beside a possible EUS examination (D62's, or D97's unusable kind), the acts are a doubt, never the fact:
      possibly_part_of, which D70 and D97 already give. The D97 pins (an unusable-kind examination beside a settled FNA)
      keep the EGD's own item.
    - D87 and D62 on D121's own input: some EUS-kind acts are possible upper EUSes (upper_doubts), never the session:
      - an act whose own kind or procedure is not usable (the FNA filed under 'eus' with no words:
        procedure_unsettled);
      - an act only POSSIBLY of this encounter (coverage.possible_eus_acts: 'After the EGD, EUS-FNA of ...', its time
        unanchored).
    - In both, the EGD keeps its items and 43235 is held through D70's doubt. d353e64df gives READY (both inputs);
      c2e53f8e holds it base_included.
    - Beside the possible FNA, the question names "the endoscopic ultrasound", not 43242. The EUS session has no done
      event, so 43242 is matched to no session.
    - An act-only EUS placed in the rectum is lower: the EGD stays a service of its own and 43235 is READY. This is
      unchanged, and the same on all three engines.
  - Pins (tests/test_interpretation_r5_eus.py, AnEusToldOnlyByItsActIsAnUpperEus):
    - test_d121_43235_beside_the_eus_code_of_its_act_is_held_base_included: the FNA beside 43242 and 43238, the celiac
      block beside 43253, and the drainage beside 43240. Each is held with base_within_hold's own check and question,
      the read-time overlay keeps it held, included_by names the code, and 43235 alone is held.
    - test_d121_with_no_proposal_the_egd_asks_no_code_of_its_own: the EUS's item alone, as on c2e53f8e.
    - test_d121_controls_an_examination_event_and_a_rectal_act: the audit's g2b_withexam control.
    - test_d121_an_act_whose_family_is_in_doubt_is_a_possible_upper_eus.
    - test_d121_an_act_only_possibly_of_this_encounter_is_a_possible_upper_eus: this repair's own sibling probe. The
      first build left it READY, and c2e53f8e holds it.
  - Residual. An act-only EUS whose act is placed nowhere (a target CPT Studio cannot place, or one not verified) is upper
    by default, so the EGD's own no_proposal item is dropped when no EUS code is counted. This is the spec ("whose acts
    are not placed lower"), and it is c2e53f8e's reading when no lower site is named.
    - If the act's unverified words name the rectum, c2e53f8e (which reads the passage) keeps the item; the new path
      cannot (EB1). 43235 is held either way.
    - This is the class D96 recorded for examinations (the 'p2 reports2-0c' residual).

- **D123 An act verified at an organ is at that organ; a done act filed under the EUS that is not the EUS's own is a
  doubt (2026-11-11; the round-4 review of D96, problems 0, 1 and 2; amends D96).**
  - Problem 0 (high, repaired by the round-4 alternative A1, as the review measured it). D96's words arm read a colon
    landmark that an UPPER act's verified target words name beside its own organ landmark.
    - The review's input: 'EGD: ...' / 'EUS: a linear echoendoscope was then advanced to the stomach and the duodenum.' /
      'Transgastric drainage of a 10 cm pancreatic pseudocyst abutting the transverse colon was performed with a
      lumen-apposing metal stent.' The drainage is verified at the pancreas, with the words 'pancreatic pseudocyst
      abutting the transverse colon'.
    - d353e64df: eus_places [pancreas, pancreas, transverse_colon], so the EUS was lower. 43235 was READY beside 43240
      and alone (complete_pending_review); with no proposal, the EGD's item was listed.
    - 437b708bb and c2e53f8e hold 43235 base_included.
    - The same held on the review's two rewordings ('... was drained transgastrically ...', 'walled-off necrosis in the
      pancreatic tail abutting the splenic flexure') and on an FNA ('a 28 mm hypoechoic mass in the pancreatic tail
      adjacent to the splenic flexure').
    - The same arm cancelled D70's doubt ('After the EGD, ...' with that FNA): 43235 READY at d353e64df, held at
      437b708bb.
    - The rule: eus_places reads an act's target words only where its verified landmark places it in no organ of its
      own (UNPLACED_REGIONS: no region, or a lymph node). Finding 12's repair stands: at 'lymph_node', 'a perirectal
      lymph node in the rectum' is still lower.
    - Recorded difference from c2e53f8e. On the FNA wordings, c2e53f8e READYs 43235: its word scan reads 'splenic
      flexure' in the EUS's passages. The new path holds 43235, the review's expected outcome (NOT_READY).
    - With no proposal, the new path drops the EGD's own item, because the EUS is upper and the EGD is its endoscopic
      portion. This restores 437b708bb.
  - Problems 1 and 2 (decided and repaired as one rule). coverage.doubted_eus_acts gives today's DONE acts filed under
    the EUS that are no EUS act (eus_act):
    - an act of an EUS kind whose kind or procedure is not usable. Problem 2: D88's pinned sentence 'Radial EUS was then
      performed; a perirectal lymph node in the rectum was sampled ...', with its FNA's procedure 'eus' given no words;
    - an act of a kind that is no EUS act. Problem 1: 'Radial EUS was then performed; forceps biopsies of the rectal
      mass were taken.'
    - Not acts here: an examination (the digital rectal examination, E13) and an event of no catalogue kind (D96 finding
      0's rectal medication read as 'other').
    - The rule. Such an act is still no lower evidence (D96 kept).
      - Placed lower where no done EUS event places the EUS (_placed_eus: a place of a region that is neither lower nor
        unplaced), it makes C-4's upper reading a doubt (possibly_lower). The EGD gets possibly_part_of, not part_of.
      - So the EGD keeps its own no_proposal item and second-review mark, and 43235 is held base_included through
        D70's doubt.
    - Problem 1, "lower evidence or not": NEITHER. Following c2e53f8e on the problem's input means matching both of its
      outcomes: it keeps both items (included_by {}) AND holds 43235 (performed_status, extent).
      - Read as lower evidence, the act would turn 43235 alone READY.
      - Read as no evidence, as at d353e64df, the act drops the EGD's item.
      - The doubt matches c2e53f8e on both outcomes.
    - Problem 2, "never drop the EGD's own item for it": the same rule. d353e64df dropped the item (included_by
      {gi.egd: []}). It is listed now (gi.egd no_proposal, second_review True), as on 437b708bb and c2e53f8e.
    - Where the EUS's own done events place it in the upper tract, C-4 reads it as before: the EGD is part of the EUS.
      - D96 finding 2: an EUS examination reaching the duodenum beside the colonoscopy's unsettled rectal biopsies. Its
        pin holds that structure.
      - A settled 'EUS' forceps biopsy of the rectal mass beside an EUS reaching the duodenum is held the same way on
        c2e53f8e: 43235 base_included, the EUS's item alone.
  - Pins (AnActVerifiedAtAnOrganIsAtThatOrgan, ADoubtedLowerActIsADoubtNeverAFact):
    - test_d123_words_naming_a_colon_landmark_beside_the_pancreas_never_free_43235: four wordings, beside the code and
      alone;
    - test_d123_the_same_words_never_cancel_d70s_doubt;
    - test_d123_controls_words_are_still_read_at_a_node;
    - test_d123_the_egd_keeps_its_own_item_and_second_review_mark;
    - test_d123_43235_stays_held_never_ready;
    - test_d123_controls_a_settled_act_and_an_eus_placed_upper;
    - test_d123_no_kind_and_no_examination_are_doubted_acts.
  - Not repaired, recorded:
    - Problem 3 (design note). eus_places runs verify.landmark_words over target words inside coverage, so the module
      docstring's "no pattern is matched" is inexact, as round 4 noted. The docstring is outside this repair's functions.
    - Problem 4. D96's settled_eus_act control (test_interpretation_r4_eus_lower.py:272-276) pins as correct a 43235
      READY that c2e53f8e holds base_included. It is unchanged; moving its expectation is not this spec's.
    - Problem 5. A DRE whose technique Gemini leaves not_stated is a done EUS examination, so it is lower evidence. This
      is unchanged: the recorded "any lower examination means no upper EUS" residual.
    - Problem 6 (pin strength). Now covered: the problem-0 pins assert outcomes on upper acts whose words name a lower
      landmark.
    - Problems 1 and 2 beside a lower-tract EUS code (B1 with 45341 'Radial EUS', C1 with 45342). 43235 is READY on
      d353e64df and on the build alike, because 45341 and 45342 include no EGD (base_within holds only beside a code that
      includes it). c2e53f8e holds 43235 on its own reader's performed_status and extent. This is pre-existing.

- **D120 43240's defining act has a target requirement - a pancreatic fluid collection (2026-11-11; the round-4 parity
  audit, EUS gap 0). BUILT AS SPECIFIED IN mapping.py, AND NOT READ: no function this repair owns reads it, so no outcome
  changes.**
  - The gap (high). D27 makes 'drainage' 43240's defining kind, and nothing reads the drainage's target.
    - The audit's input (g1_gallbladder_43240): 'EUS-guided transmural drainage of the gallbladder was performed from the
      duodenal bulb with a 15 mm lumen-apposing metal stent.', with the drainage's target verified at the gallbladder.
    - d353e64df and the build: 43240 READY (the overlay agrees), coding complete_pending_review. The same holds for a
      common bile duct, a left hepatic duct and a liver abscess.
    - c2e53f8e: held [performed_status, target], with no item.
  - What is built: mapping.DEFINING_TARGETS {'43240': PANCREATIC_FLUID_COLLECTION} and mapping.defining_target(code,
    event, lesion).
    - A drainage meets the requirement only where one of two sets of words names a pancreatic fluid collection: its
      usable target's own words, or the words of the lesion its target is verified to be. The names are pseudocyst,
      walled-off necrosis, WON, a pancreatic or peripancreatic fluid collection, PFC, a necrotic collection, and
      pancreatic necrosis.
    - No verified place of it may lie in DEFINING_TARGET_APART: the biliary region and the liver.
    - It is an inclusion list for SUPPORT, so it fails closed: words that name none of these never support. It reads the
      attribute's own words only, never a passage (EB1). For every other code it gives True.
  - Why it is not wired. The engine's candidate and support rule lives in events.py (is_candidate, supports,
    _without_support, _exclusion), which this repair does not own.
    - Route (a) reads an event's catalogue kind and family only.
    - The one code-keyed target hook, D29's DILATION_SITES, words its hold as a dilation (wording.another_site), and
      wording.SITE_WORDS would raise KeyError on a new class.
    - That hook also keeps the act in the code's read set, so coverage could never list it.
    - So within the spec's files there is no way to hold 43240 on that input, nor to list the act.
  - Alternative (optional, outside the ownership): alt-D120.diff, which applies on top of patch.diff.
    - events.defining_fit is read in supports, in _without_support's candidates and in _exclusion. An act that misses
      the requirement is no candidate: it supports nothing, decides no exclusion, and is listed by coverage.
    - events.group_label names the requirement (mapping.DEFINING_TARGET_NAMES), so the hold reads "records no drainage
      of a pancreatic fluid collection documented as done".
    - On the four inputs, 43240 is held [performed_status, target] - exactly c2e53f8e's questions. The drainage is
      listed not_covered (second_review True), and coding is incomplete.
    - The pseudocyst, the walled-off necrosis and the lesion arm stay READY. That is D27's recorded difference from
      c2e53f8e, which holds every 43240.
    - A cited 'No drainage of the gallbladder was performed.' no longer EXCLUDES 43240; it is held. d353e64df and
      c2e53f8e both exclude it.
    - It changes one existing expectation, test_interpretation_r3_integration_d87's 43240 arm. A drainage naming no
      place now fails the requirement, so 43240 is held not_documented [performed_status, target] instead of supported
      [target]. Both are holds, and the target question is unchanged.

- **D122 An examination-only EUS code beside an EUS-guided act no EUS code accounts for (2026-11-11; the round-4 parity
  audit, EUS gap 2). NOT BUILDABLE IN combination._base; NOTHING CHANGED.**
  - The gap (high). The audit's input (g4_eusge_stent_43259): 'Procedure: EUS-guided gastroenterostomy.' / 'The linear
    echoendoscope was advanced to the second portion of the duodenum.' / ... / 'From the gastric body, a 20 mm
    lumen-apposing metal stent was deployed into a distended jejunal loop.' Its E2 is of kind stent, target the jejunum.
    - d353e64df and the build: 43259 READY (the overlay agrees), no item, complete_pending_review. The same holds with
      E2 read as 'other', from the stomach with 43237, and for an RFA read as 'ablation'.
    - c2e53f8e: held [performed_status, target].
  - Why. base_included holds a base code only from the STORED event coding's 'reportable' and 'doubted' entries, which
    is what lets the read-time overlay re-derive it.
    - coverage.event_coding fills those entries through reportable_kind, which reads the gi.eus entry's acts only
      (eus_exam, fna, injection, drainage). A stent or an ablation is never among them.
    - _base(code) sees the code alone, so no change to it can hold 43259 beside the stent.
    - Listing the act needs coverage.reconcile, whose `if kind not in entry.acts: continue` skips it.
    - All three are outside the ownership.
  - Alternative (optional): alt-D122.diff, which applies on top of patch.diff. It is in coverage.py.
    - EUS_UNPROFILED is every act kind but the EUS's own, the never-reported ones and the READ_UNDER forceps biopsy.
      eus_unprofiled_act is one of those kinds, or 'other' with a usable device.
    - reportable_kind reads eus_unprofiled_act; _entry labels an 'other' act by its event label; and reconcile lists the
      act.
    - On the four inputs, 43259 and 43237 are held with the base question ("Is 43259 reported separately from stent
      placement for this examination?"). The act is listed 'unsupported' ("no code profile of this service accounts for
      it"), which is the reason reconcile gives an act no code of the family covers, not 'not_covered'.
    - D96's rectal medication read as 'other' (no device) leaves 43259 READY.
  - The two alternatives combined: alt-D120-D122.diff. The single diffs conflict only on the pin module's import line.

- **D120-D123, what was edited, and the measurement.**
  - Edited:
    - studio/interpretation/coverage.py, C-4 only: new helpers possible_eus_acts, doubted_eus_acts, UNPLACED_REGIONS and
      _placed_eus; eus_places' words arm; eus_act's docstring; sessions()' C-4 block (acts, session_events, doubted,
      possibly_lower, upper_doubts).
    - studio/interpretation/mapping.py: the D120 block after DEFINING.
    - combination.py is untouched (D122).
    - tests/test_interpretation_r5_eus.py is NEW, with 16 tests. No existing test changed.
    - The module docstrings are untouched.
  - Suites (t.sh, Postgres 127.0.0.1:55461):
    - every tests.test_interpretation_* module (42, plus the new one), test_pipeline_assess_events,
      test_readers_dispatch, test_guard_static, test_guard_mutation and test_overlay_differential: 1274 OK. d353e64df
      gives 1258, plus the 16.
    - the 11 other modules that import the package (test_change_context_events, test_guard_matrix_legacy,
      test_guard_matrix_new_path, test_models_event_inventory, test_peer_heading, test_pipeline_api,
      test_pipeline_interpret, test_repairs_7c8_p1reports, test_repairs_7c8_p1sends, test_repairs_ec5_reportruns,
      test_retry_reading_api): 264 OK, 3 skipped, the same as d353e64df.
    - the new module on d353e64df: 44 failures and 18 errors.
  - Mutation proof: 17 mutants. Each was built in its own copy, with its replacement asserted once and its application
    confirmed by a marker and a sha256 change. The work tree's sha256 was unchanged. Every one is killed, and every pin
    fails under at least one:
    - M1 (D121 undone): 17 failures.
    - M2 (the doubted-act upper doubt undone): 2.
    - M13 (the possible-act upper doubt undone): 3.
    - M3 (the words arm unrestricted): 18.
    - M4 (problems 1 and 2 undone): 4.
    - M5 (the placed-upper condition removed): 3, including D96 finding 2's pin.
    - M6 (an event of no kind admitted): 1.
    - M7 (an act-only session beside a possible examination read as the fact): 12, including the D88, D96 and D97
      pins.
    - M8 to M12 (each part of defining_target): 1, 1, 1, 4 and 2.
    - M14 (the requirement disabled for 43240): 7.
    - M15 (a doubted lower act read as lower evidence, which would make 43235 READY): 10, including the never-READY
      guard and D96 finding 2's pin.
    - M16 (the words arm no longer read at a lymph node): 9, including D96 finding 12's pin.
    - M17 (an act-only session read as upper even when placed lower): 19, including the D69, D88 and D96 pins.
  - The alternatives' pins (3 for alt-D120 and 2 for alt-D122) fail on patch.diff alone:
    - 19 failures for alt-D120: 13, plus the 6 subtests of its changed D87 expectation;
    - 12 failures and 1 error for alt-D122.
  - The alternatives' 9 part-mutants are all killed.
  - The combined alternative (alt-D120-D122.diff on patch.diff) passes the same label set: 1279 OK, which is the 1274
    plus its 5 pins, with the D87 expectation it changes.
  - FRESH-2 (f2r5-eus2): A 96/6, B 177/15, C 171/19 plus 2 safe_hold.
    - Against the d353e64df scorings (f2r5-colon-base, f2r5-questions2-pristine, f2r5-ercp2-pristine): 0 of 486 rows, 0
      of 179 runs, and 358 of 358 per-run files byte-identical.
    - Against f2r3intc: one row, A note8 r3 45385 asked [technique] -> [statement_scope]. It is already in d353e64df and
      is not this patch's.
    - FRESH-1 (f1r5-eus2) against f1r5-questions2-pristine: 0 of 486.
    - Each alternative, singly and combined: 0 of 486, with 358 of 358 files identical.
    - The scorer reads the given tree. Positive control: a planted event-coding key appeared in all 179 assessments.
  - The head-to-head is identical to h2h-r3final.json in all 459 leaves, for the patch and for each alternative.
    - Run 1: 214/234 (A 34/34, B 59/64, C 121/136).
    - c2e53f8e: 16 false_ready and 2 ready_wrong_facts. Worse 5, better 69, unstable 7, facts moved 0.
    - No new false_ready, false_exclusion, dropped_question or ready_wrong_facts.
  - Census, the build's helpers over FRESH-1 and FRESH-2:
    - 179 inventories in each, 6 with EUS events (6 examinations and 6 FNAs), 3 with both an EGD and an EUS. Those are
      fb12, whose EGD is part of the EUS through its own verified part_of (C3), so C-4 decides nothing there.
    - 0 drainages, 0 act-only EUS sessions, 0 possible EUS acts, 0 doubted EUS acts, 0 upper acts whose words name a
      lower landmark, 0 unprofiled EUS acts, and 0 of 67 EGD sessions whose C-4 structure differs from d353e64df.
    - So the corpus measures none of these classes: the cost is 0 rows because the classes have no members.

- **D126 The one statement_scope question asks every same-event contradiction of the act, the act's same-site denial
  first; it quotes each denial's whole sentence across a hard wrap; a doubt's keeps D86's wording; and a technique
  relation whose two devices are verified keeps its technique question (2026-11-11; the review of round 4's
  "questions" patch, problems 0, 1, 3 and 4; amends D101, D102 and D103; repair "questions2").** Only the question
  changes: status, bucket, READY, the exclusion and every inventory are untouched (measured below).
  - **(0) Problem 0 (low-medium).** D101's tie-break ("the first contradiction resting on the target, else the first
    stored", which the spec did not set) hid a same-site contradiction D102 asks.
    - Input: the sigmoid cold snare 45385 cites, S2w ("During withdrawal, no polypectomy was performed in the sigmoid
      colon.", its own time unanchored: UNRESOLVED(time)) and C1CL3-001's "No polypectomy was performed in the prior
      segment." (UNRESOLVED(target, site_unresolved)), in either order.
    - d353e64df asked statement_scope about the prior-segment sentence only. S2w appeared nowhere in the assessment:
      not in the question, its question_events or its source. 437b708bb had at least shown it in the withdrawal-first
      order. c2e53f8e asks conflict:snare in both orders, with or without a procedure heading, and its conflicts
      check warns.
    - The rule. The code's ONE question (FINAL 7.4) asks EVERY same-event contradiction of the act (D101's
      _h3_asks_contradiction, as D126 (4) narrows it), in a stated precedence. It is events._h3_rank, a stable sort
      over the stored order:
      - first, the act's SAME-SITE denials: the pairing table's own target row (relations.target_row, read from the
        stored attributes) reads the statement as the act's own target. Its place contains the act's, it names the
        act's verified lesion, or it covers every act of its kind in the act's session. What is unknown is then its
        own procedure, time, performer, device or kind;
      - then the TARGET denials (D86): whether the place or lesion is the act's is what is unknown;
      - then the others: a scope the statement leaves unresolved, a session the table cannot resolve, a denial whose
        own site is unknown too.
    - The question reads 'Does “A” or “B” apply to the <act> (“<its words>”)?' ('“A”, “B” or “C”' for three). The
      reason reads 'The document states “A” and “B”; CPT Studio could not confirm from the document whether those
      statements apply to the <act>.'
    - The question's events and passages are every contradiction's, in that order, and a sentence two events share
      is quoted once. So no contradiction is hidden or dropped, and the precedence decides the order and the relation
      recorded (the first).
    - One contradiction asks exactly as before. focus_question (code '', FINAL 7.8) still reads the first relation
      stored (D86's boundary).
    - Why every statement is quoted, not only the precedence's first. The spec asks for both: the same-site denial
      first, and never dropping the target denial's statement_scope question. With one question per code, quoting
      only the first would drop the target denial from the question whenever a same-site denial leads. That is
      finding 3's own shape: the framed historical denial is a same-site denial (all_of_kind), so it leads before the
      prior-segment denial. The lead-only alternative is mutant M3, measured below.
  - **(1) Problem 1 (low).** D103 quoted the one place that holds the status words. In a hard-wrapped document that
    place is one line, for example FRESH-2 C2MEM-023 r1 45385: 'Does “No biopsy, snare resection, ablation, or balloon
    dilation was performed on” apply ...'.
    - The rule. events._h3_whole_statement quotes the places, among the statement's own passages, that hold its status
      words (or D103's fallback) together with its target's and its scope's own words (events._h3_place).
    - Each place is quoted once, in document order:
      - a place within another adds nothing;
      - a place that overlaps or touches another adds the rest of its own text;
      - a place at most a line break away (_H3_WRAP = 2 characters) follows after a space;
      - a place further away follows after " … ".
    - So C2MEM-023 r1 45385 now quotes "No biopsy, snare resection, ablation, or balloon dilation was performed on this
      splenic-flexure lesion during the present encounter."
    - Census of the frozen answers (denials whose status, target and scope words lie in more than one place):
      - FRESH-2 has 9. Seven are one line break apart. Two are 4,371 characters apart: A/note8 r3 E24 (its scope words
        "this lesion") and C2MEM-031 r1 E25 (its target words "this lesion") are in the findings, and their status
        words are in the impression.
      - FRESH-1 has 16, all one line break apart.
  - **(3) Problem 3 (info): decided and pinned.** D103 is about denials. A statement_scope question whose statement is
    no denial keeps D86's pre-D103 wording, on both arms (the code's and focus_question's service arm): statement_text,
    cut at 120 characters in the question and 140 in the reason. Such a question comes from a doubt's unresolved scope,
    or from a planned act a claim names.
    - A denial's statement_scope question is quoted whole on both arms, as D103 built it.
    - The review's FRESH-1 C2MEM-031 r3 service question comes from a denial (E17, "were not taken"), so it stays
      whole (see residual 1).
  - **(4) Problem 4 (info).** On the technique, D102's "the act's own value is usable" now also requires the
    STATEMENT's own device to be unusable.
    - Both devices verified and still UNKNOWN to the table is no doubt on the statement's side. That covers the act's
      device wider than the statement's, and two 'other' devices. The doubt is which device the act used, so the
      relation keeps its technique question (C-16).
    - Input: "A 6 mm sessile polyp in the sigmoid colon was removed with a snare." beside "No cold snare was used for
      the 6 mm sessile polyp.". It now asks "Which technique was used for the snare removal ...?" with the true reason.
    - d353e64df asked statement_scope. c2e53f8e asks conflict:snare, plus extent without a heading (see residual 3).
    - The statement's own device unverified (note8 r3's shape) still asks the contradiction (D102).
  - **Edited.**
    - studio/interpretation/events.py:
      - _h3_asks_contradiction: the technique arm.
      - new helpers that only h3 calls: _h3_rank (with the constants _H3_SAME_SITE, _H3_TARGET and _H3_OTHER) and
        _h3_place (with the constant _H3_WRAP);
      - _h3_whole_statement: the joined places;
      - _h3_unresolved: every contradiction in the precedence, the denial and doubt wording arms, and the carried
        events and passages.
      - RELATION_FACTS, _h3_denial, _relation_question and focus_question are unchanged.
    - studio/interpretation/wording.py: scope_question and scope_reason take ``also``, the other statements quoted in
      order. The defaults are unchanged, so ADJUDICATION C-10's question (events._exclusion) keeps its cut and its
      single statement.
  - **Cost measured.**
    - **FRESH-2.** fresh2-score/f2r5-questions2 against f2r5-questions2-pristine (d353e64df re-scored; its summary
      equals the base).
      - Summary: A 96/6, B 177/15, C 171/19 plus 2 safe_hold, before and after. There are 0 false READY, 0 false
        exclusions, 0 dropped questions and 0 ready_wrong_facts.
      - 0 of 486 rows change in any field (got, verdict, status, bucket, asked, exclusion, failing checks).
      - 0 of 179 inventories and 5 of 179 assessments differ. No service question, completeness or summary changes.
      - 10 proposals change their question and reason, with their support detail, question_events and source and the
        service.status, events.match and events.relation details:
        - (0), now asking every contradiction: A/note8 r1 45382 (+E24, E26) and 45388 (+E24); r2 45380 (+E33), 45381
          (+E33), 45382 (+E34, E33) and 45388 (+E33); r3 45382 (+E36, E38); C2MEM-023 r1 45385 (+E24).
        - (1): C2MEM-023 r1 45385 (E14 joined across the wrap); C2MEM-031 r1 45385 and 45390 ("In view of this
          morphology and the anticipated need for expert en bloc assessment, this lesion was left in situ. … 4.
          Distinct 17 mm non-granular splenic-flexure lesion ..."). Their verdicts are unchanged: six correct
          NOT_READY holds and four false holds, before and after.
        - (3) and (4): 0 proposals. The census finds 0 technique relations from a denial with both devices verified,
          on FRESH-1 and FRESH-2.
      - statement_scope questions by the number of statements quoted: 62 single before; after, 54 single, 5 with two
        and 3 with three. The longest is 488 characters (C2MEM-031 r1 45390; 373 before).
    - **FRESH-1.** fresh-score/f1r5-questions2-work against f1r5-questions2-pristine.
      - Summary: A 97/5, B 174/18, C 165/24 plus 1 false READY and 2 safe_hold, before and after. The false READY is the
        one D86 recorded.
      - 0 rows change. 5 assessments and 15 proposals change: 11 questions, and 4 in question_events only (A/note8 r2
        45385, 45386, 45388 and 45390, whose second statement is the same passage as the first, so it is quoted once).
      - 0 service questions change. statement_scope questions: 61 single before; after, 50 single, 5 with two, 4 with
        three and 2 with four. The longest is 794 characters (C/N8-CF2 r1 45380).
    - **Head-to-head** (h2h/compare.py on f2r5-questions2): identical to h2h-r3final.json in every leaf (0 leaf
      differences).
      - Run 1: 214/234 (A 34/34, B 59/64, C 121/136).
      - worse_r1 5 (the same holds), better_r1 69, 7 unstable rows, and the facts check moves 0 rows.
    - **The lead-only alternative** (mutant M3: only the first statement quoted, every contradiction's events and
      passages carried), scored as f2r5-questions2-altT1.
      - The summary is unchanged, and the same 10 proposals change.
      - The 7 note8 proposals keep d353e64df's text and change in question_events and source only.
    - **Replay pins** (tests/test_interpretation_replay.py) pass, and no MANIFEST pin moves.
  - **Installed release c2e53f8e** on every pin input, through studio.validation.engine.assess as
    tests/test_harness_engine.py drives it (its REFERENCE lookup, service date 2026-11-09), with and without
    'Procedure: Colonoscopy':
    - Every (0) input asks conflict:snare in every order, with extent beside it on most texts without a heading, and
      services.conflicts warns.
    - (1): the flexure shape asks conflict:snare. The wrapped prior-segment denial, the denial whose target is stated
      sentences away, and the biopsy beside the wrapped denial are READY with a heading and performed_status plus
      extent without one. The new path holds all three with statement_scope, as d353e64df did; only the quote changes.
    - (3): the clip doubt asks performed_status (plus extent). Uncited, it asks no service question.
    - (4): both devices verified asks conflict:snare (plus extent). The EMR-snare denial with its device unverified is
      READY with a heading (performed_status plus extent without).
  - **Pins: tests/test_interpretation_r5_questions.py, 15 tests from the problems' inputs** (synthetic, the shared S08
    builders).
    - D126EveryContradiction (6):
      - S2w beside the prior-segment denial in either order: both asked, S2w first, question_events [E2, S2w, prior],
        both sentences shown; each alone asks as before;
      - the precedence: a statement about other findings (scope), the prior-segment denial (target) and S2w, stored in
        that order, are asked as S2w, prior, other findings;
      - finding 3's framed and device denials beside the prior-segment denial in all four orders: the same-site denial
        first, and the prior-segment denial always asked and shown;
      - two target denials are both asked, in the stored order;
      - two same-site denials are both asked, in the stored order (D101's tie);
      - two denials Gemini reads from one sentence: the sentence is quoted once, and both events are the question's.
    - D126TheWholeSentence (5):
      - C2MEM-023 r1's shape and a wrapped prior-segment denial, each quoted as its one sentence;
      - the service question beside a denial whose scope words are on the next line (focus_question);
      - RECORDED (residual 1): the recorded C2MEM-031 r3 E17's shape, its scope words unlocated and its target absent,
        keeps the status words' one line, as at d353e64df;
      - places apart joined with " … " (C2MEM-031 r1 E25's shape);
      - _h3_whole_statement over stored places: within, across, touching and wrap.
    - D126ADoubtsScopeQuestion (2): a doubt's scope question keeps D86's cut wording on the code's arm (45382 beside a
      clip doubt) and on the service arm; a denial in its place is quoted whole on the service arm.
    - D126BothDevicesVerified (2):
      - the review's input asks technique, and the statement's own device unverified still asks the contradiction;
      - beside the prior-segment denial, the contradiction is the one question (recorded: one question per code).
  - **Existing expectations moved** (tests/test_interpretation_r4_questions.py only, each by D126 (0)):
    - D101EveryRelation.test_d101_the_prior_segment_denial_after_a_framed_denials_time_relation_is_the_question:
      asks FRAMED or PRIOR, with question_events [E2, E3, E4].
    - test_d101_the_prior_segment_denial_after_a_device_denial_is_the_question: asks DEVICE or PRIOR, with
      question_events [E2, E3, E4].
    - test_d101_the_question_is_the_same_in_every_sentence_order: the same-site denial first and PRIOR second, in all
      four orders.
    - test_d101_two_contradictions_resting_on_no_target_ask_the_first_stored: both are asked, the first stored first.
    - Also a new helper, Held.assert_scope_all, and one sentence appended to the module docstring. Every other
      assertion of these tests is unchanged: PRIOR is shown, and the relations are as stored.
  - **Suites.**
    - The 43 tests.test_interpretation_* modules plus test_pipeline_assess_events, test_readers_dispatch,
      test_guard_static and test_guard_mutation: 1256 OK at d353e64df, 1271 OK on the patch (+15).
    - The pin modules (r5_questions, r4_questions, r3_questions, r3_integration_d89_d91, interpretation_events and
      interpretation_replay): 134 OK.
    - The 15 other modules on the new path (test_change_context_events, test_guard_matrix_legacy,
      test_guard_matrix_new_path, test_models_event_inventory, test_pipeline_api, test_peer_heading,
      test_overlay_differential, test_repairs_7c8_p1reports, test_repairs_ec5_reportruns, test_repairs_7c8_p1sends,
      test_pipeline_interpret, test_retry_reading_api, test_harness_pipeline, test_harness2_pipeline and
      test_services_second_review): 394 OK, 3 skipped, as at d353e64df (394 OK, 3 skipped).
    - The patch applies with patch -p1 to a fresh archive of d353e64df (dry run and real), and the result is
      byte-identical to the work tree.
  - **Mutation proof.** M0 is d353e64df's events.py and wording.py with the new and moved tests kept. M1 to M13 are
    private copies of the work tree, each with one anchored edit: the anchor occurred once, "mutation applied: True"
    was confirmed by the marker and a sha256 change, and the work copy's sha256 was unchanged. Failures on the 134 pin
    tests:
    - M0, the change undone: 30. Every new pin fails except the two recorded ones (the one-question pin, which M12
      kills, and the unlocated-scope pin, which M11 kills), and so do the 8 moved subtests.
    - M1, D101's target-first single relation: 20.
    - M2, every contradiction in the stored order (no precedence): 6, the prior-first orders and the precedence pin.
    - M3, only the lead statement quoted: 19.
    - M4, only the lead's events and passages carried: 16.
    - M5, quotes not deduplicated: 1.
    - M6, same-site by attribute alone (no target row): 1, the precedence pin.
    - M7, the status place alone (D103): 7.
    - M8, a space instead of the ellipsis: 1.
    - M9, no merge of places within, overlapping or touching: 3.
    - M10, every statement_scope quoted whole (d353e64df's (3)): 2.
    - M11, a denial's service question in D86's wording: 5, including D89's two pins and the recorded unlocated-scope
      pin.
    - M12, D102's technique arm as at d353e64df: 2.
    - M13, a technique relation never a contradiction: 11, including D102's own pin.
  - **Recorded residuals and points for the owner.**
    1. (1) as specified is short of the review's own inputs in two shapes. Each is still one wrapped line:
       - A statement whose target and scope words are not located. FRESH-1 C2MEM-031 r3's service question, the
         review's second input: E17's target is absent and its scope is listed_targets with words_unlocated. Its scope
         passages are P50 and P51, the next line, but no words hold a place, so the quote stays "... they were not taken
         from any".
       - A statement whose words all lie in one wrapped line: FRESH-2 C2MEM-023 r1 E24 ("flat 4 mm, nonbleeding
         vascular ectasia in the proximal rectum was photographed but not treated; there was no"), now also asked by
         (0), and FRESH-1 C2MEM-031 r3 E23 and E35.
       - Reading an attribute's own passages a line break away when its words are unlocated would complete the first
         shape (P51 is 1 character after P50). The second needs a sentence boundary from passages that are not the
         statement's own. Neither is built.
    2. (0) makes questions longer: up to 4 statements and 794 characters (FRESH-1 N8-CF2 r1 45380). Member rows show
       the fixed prompt and at most two of CPT Studio's located passages (validation.questions.PER_SOURCE), so a third
       statement's sentence reaches the member only through the engine's question text and the reports. The lead-only
       alternative (M3) is measured above and is the owner's call.
    3. (4) moves away from the installed release's question on its own input: c2e53f8e asks conflict:snare, d353e64df
       statement_scope and D126 technique. Against an expectation in the installed fact vocabulary (conflict:snare or
       performed_status), technique would score dropped_question, because statement_scope counts as the
       contradiction and technique does not. There are 0 members on FRESH-1, FRESH-2 and the head-to-head, and the
       spec's reason stands: denying the cold snare does not deny the snare removal.
    4. One question per code: beside a contradiction, (4)'s technique question is not asked, the class of D101
       residual (e). This is pinned.
    5. A D102 time contradiction whose own time words are another sentence quotes its status sentence only. The shape
       is C2MEM-031 r1 E12: "No colonic stent was placed." / "Those were the findings at her index colonoscopy.". The
       statement's unknown time is shown nowhere, because relations._passages carries the act's time passages, not the
       statement's. (1) reads status, target and scope words, as specified. No statement_scope question on FRESH-1 or
       FRESH-2 rests on a time relation at all.
    6. events._exclusion's C-7 and C-10 statement_scope question (D103's residual (a)) is unchanged, as is
       focus_question's first-relation boundary (D86, D101 residual (g)).

- **Round 5, partly built (2026-11-11; wf_5d0c6806-f7d).** The account's WEEKLY usage limit stopped the workflow:
  "resets Nov 16, 10am (UTC)".
  - Built: em (D111-D113), eus2 (D120-D123) and questions2 (D126). The independent reviews of all three failed on
    the limit, so all three are UNREVIEWED.
  - Built and reviewed, NOT integrated: second-review (D129). Its reviewer found three high problems: a READY on an
    act other than the one the code was added for; the item resolved while the added code is held; and an addition
    wider than c2e53f8e's _open_items_covered rule. The patch is parked in gemini-migration/round5/second-review/.
  - Not built (the limit): colon (D124-D125), ercp2 (D127), enteroscopy-route (D114), egd (D115-D119) and currency2
    (D128). Their specs are in gemini-migration/round5/round5-workflow.js.
  - Integrated at this commit, unreviewed: em, eus2 and questions2. Engine and guard suites 1401 OK. FRESH-2
    verdicts unchanged; one row changes its question (A/note8 r3 45385, false_hold, technique -> statement_scope).
    The head-to-head is unchanged (214/234; worse on 5 rows, all holds).
  - Before ANY merge: the reviews of these three patches, the rebuilt second-review, the five unbuilt repairs and
    refutation round 5 must all run, as AGENTS.md's mandatory adversarial pass requires.

- **D114 An ileal reach beside a stoma or pouch fits a class only through the examination's own route; an enteroscopy
  act in the upper tract beside a done EGD is the EGD session's (2026-11-11; the round-4 review of D108, problems 0, 2
  and 4, and its parity note 1; amends D108).**
  - Problems 0 and 2 (critical-class by finding 24's grading). D108 read the stoma and pouch classes' route from the
    ENCOUNTER's anatomy (D43's has_stoma). The anatomy says a stoma or a pouch exists; it never says the examination went
    through it. So with a verified stoma or pouch and an ileal reach, the oral class and the stoma or pouch class were
    both READY when each was proposed alone, and one of them is wrong on every such document.
    - The review's input (the author's own READY control, tests/test_interpretation_r4_enteroscopy.py ileoscopy(), and the
      review's stoma_ileoscopy): 'The patient has an end ileostomy after a total proctocolectomy for Crohn disease.' /
      'The enteroscope was advanced through the ileostomy into the neo-terminal ileum for 25 cm.' / 'Biopsies of the
      neo-terminal ileum were taken with cold forceps.'. 1caaf0609: 44377 READY beside the correct 44382, READY too.
    - The pouch input (pouch_prepouch): 'The endoscope was advanced through the anus into the J-pouch and through the
      pouch inlet into the pre-pouch ileum for 15 cm.', a verified J-pouch. 1caaf0609: 44377 READY.
    - The twins whose Procedure line names an enteroscopy, and the 'distal ileum' reaches: 44377 READY.
  - Problem 4 (the disclosed residual, extended). An ORAL double-balloon enteroscopy to the proximal ileum ('The
    double-balloon enteroscope was advanced orally to the proximal ileum.') beside an end ileostomy made 44382 READY,
    and beside an ileal J-pouch made 44386 READY.
  - The installed release c2e53f8e holds every one of these inputs: extent, with performed_status on the ileoscopy and
    pouchoscopy documents (engine.assess as tests/test_harness_engine.py drives it, and jobs._assess_child: the two
    drivers agree on all 128 probe rows).
  - The rule (classes.py; no other file):
    - When the encounter has a verified stoma or pouch (classes.routes: D43's has_stoma, and a usable altered pouch
      entry), an ileal reach (the ileum, the terminal or neo-terminal ileum) fits:
      - ILEAL (44376-44379) only when the examination's route is verified oral;
      - STOMA (44380-44384) only when it is verified through the stoma (and the anatomy's stoma, as D108);
      - POUCH (44385-44386) only when it is verified through the pouch (and the anatomy's pouch, as D108).
      A route not verified fits none of them: every such code is held, never READY and never excluded.
    - The route is verified (examination_route) when the usable words of the examination's own statement - its
      procedure, kind, technique and status words (ROUTE_STATED) - name exactly one route of ROUTE_WORDS, and no other
      route is named in ANY of its own located words (ROUTE_READ: its reach, completion, target, time, performer, scope
      and purpose words too).
      - ROUTE_WORDS, matched in lexicon.fold's form and word-bounded (lexicon.found): oral - 'orally', 'oral',
        'peroral', 'perorally', 'per oral', 'per os', 'transoral', 'transorally', 'through the mouth', 'via the mouth',
        'by mouth', 'antegrade', 'antegradely', 'anterograde', 'anterogradely'; the stoma - 'ileostomy', 'ileostomies',
        'stoma', 'stomas', 'stomal', 'ostomy', 'ostomies'; the pouch - 'pouch', 'pouches', 'pouchoscopy', 'reservoir'.
      - EB1: only the words Gemini cited for the examination's own attributes, located in their own passages, are
        read; no passage is scanned. Unlocated words are not stored, so they name nothing.
      - Why the reach words never VERIFY a route: they name the point reached, and a stoma or pouch named there is a
        place ("the pre-pouch ileum", "the distal ileum, 20 cm proximal to the ileostomy"). They still DOUBT another
        route (D87): a route named anywhere else in the examination's words leaves the route not verified.
    - Without a verified stoma or pouch the classes read as D108 built them, and a reach at the pouch itself is the
      pouch class's whatever the words (D114 reads the route for an ileal reach only).
    - The hold, fact extent (classes.class_hold):
      - ROUTE_FORM, where the reach, the anatomy and the incompleteness fit the code's own class and only the route is
        not verified: 'The documented enteroscopy (“neo-terminal ileum”) reached the neo terminal ileum; CPT Studio
        could not confirm from the document whether it was passed through the mouth or through the documented stoma.
        Was a small-bowel enteroscopy past the second portion of the duodenum that reaches the ileum performed on the
        date of service?'. An examination also stated incomplete adds ' and is stated to be incomplete' to the same one
        question (both doubts in it; with the oral route verified, D108's incomplete form).
      - D108's CLASS_FORM where the route is verified as another class's, the route named: '... reached the ileum
        through the mouth (“was advanced orally”). Was an examination of the ileum through a stoma performed on the date
        of service?'.
      - D108's other arms unchanged. "Another class fits" still reads the reach and the anatomy only, so 44361 on an
        unrouted ileal reach beside a stoma keeps D108's class question, never R6's extent question.
  - Parity note 1 (the review's report-only rule gap). c2e53f8e gives an act to the family whose regions hold its site
    (services.FAMILY_REGIONS: 'gi.enteroscopy' the small bowel alone; 'gi.egd' the esophagus, the stomach and the
    duodenum; _family_for_act_in). The new path followed Gemini's procedure for the act.
    - The note's input: 'EGD AND PUSH ENTEROSCOPY REPORT' / 'Procedure: EGD and push enteroscopy.' / 'EGD: The
      gastroscope was advanced to the second portion of the duodenum.' / 'Push enteroscopy: The enteroscope was then
      advanced to the proximal jejunum.' / 'Two gastric antral angioectasias were treated with argon plasma
      coagulation.', the APC filed under the push enteroscopy.
    - 1caaf0609: 44369 READY; 43235 READY alone and beside 44369; 43270 held (performed_status); 44360 held
      (base_included). c2e53f8e: 44369 held (performed_status), 43235 held (base_included), 43270 READY, 44360 READY.
    - The rule:
      - coverage.coding_family (NEW) and its ONE call, where sessions() groups the events by family: an ACT Gemini files
        under the enteroscopy whose VERIFIED target (mapping.target_landmark) lies in an EGD region (EGD_REGIONS, the
        installed FAMILY_REGIONS['gi.egd'], pinned equal to it by a test-only import) is the EGD session's when the
        encounter has a DONE EGD examination (done_examinations). An examination never moves, and an act whose place is
        not verified keeps Gemini's family. So event_coding lists the act in the EGD session (43235 base_included), and
        coverage lists it there.
      - classes.act_elsewhere / elsewhere_hold: an enteroscopy code each of whose supporting acts (events.supports), for
        one of its requirement groups, its own session does not hold - the grouping the call made - is held:
        service.act_elsewhere (the installed release's id and label), warn; fact performed_status: 'The documented
        ablation (“Two gastric antral angioectasias”) is at the gastric antrum, which the upper endoscopy of this
        encounter examines. Was ablation performed in the small-bowel enteroscopy on the date of service?'. Never READY,
        never excluded.
      - The enteroscopy's diagnostic code (44360, 44376, 44380, 44385: a code that accounts for the examination
        itself) is held beside such a moved act when it is reportable or doubted (coverage.reportable / doubted - what
        held it base_included in its own session at 1caaf0609): service.act_elsewhere, warn; fact procedure,
        wording.procedure_question: 'In which procedure was the ablation (“Two gastric antral angioectasias”) done?'.
        Without this arm the move would turn 44360 from held (base_included) to READY, which c2e53f8e does but the spec
        does not ask; Gemini's own reading of the act as the enteroscopy's stays a doubt (D87). A denial at the stomach
        holds nothing (as at 1caaf0609).
      - D89 (questions are never displaced): a code held by its class AND by its act's region asks both in one question,
        the class question first (its check carries both reasons). The input: the note's document with the push
        enteroscopy 'advanced to the third portion of the duodenum' (the second portion's landmark). 1caaf0609 asked 44369
        R6's extent question; it still does, followed by the act's.
    - The new path after D114 on the note's input: 44369 held (service.act_elsewhere), 43235 held base_included alone and
      beside 44369, 44360 held (its base_included question becomes the act's procedure question; beside 44369 it asks
      both), 43270 held as before (performed_status; see "not built").
  - Pins: tests/test_interpretation_r5_enteroscopy_route.py, 23 tests.
    - RouteOfTheExamination:
      - test_d114_44377_on_an_ileoscopy_through_the_ileostomy_is_held (problem 0; the route question, and the class
        question with the route named when the words name the ileostomy);
      - test_d114_44382_on_the_ileoscopy_is_ready_only_through_its_verified_stoma_route (READY with 'Ileoscopy through
        the ileostomy' as procedure words, or 'was advanced through the ileostomy' as status words; held otherwise);
      - test_d114_44377_on_a_pouchoscopy_into_the_pre_pouch_ileum_is_held (problem 0's pouch input; 44386 READY through
        'Pouchoscopy'; both held with no route words);
      - test_d114_the_oral_dbe_in_an_ileostomy_patient_holds_44382_and_readies_44377_only_orally (problem 4);
      - test_d114_the_oral_dbe_in_a_j_pouch_patient_holds_44386_and_readies_44377_only_orally (problem 4's pouch
        analogue);
      - test_d114_the_specs_oral_words_verify_the_oral_route ('peroral', 'antegrade', 'per os', 'through the mouth');
      - test_d114_a_route_named_two_ways_is_not_verified ('orally' beside 'pre-pouch ileum'; beside '20 cm proximal to
        the ileostomy');
      - test_d114_reach_words_never_verify_a_route;
      - test_d114_words_of_an_unusable_attribute_never_verify_a_route (procedure words opened by Gemini's own question);
      - test_d114_an_incomplete_examination_asks_one_route_question_naming_both.
    - ScopeOfTheRoute:
      - test_d114_without_a_stoma_or_pouch_the_oral_classes_read_as_d108_built_them (the spec's control: 44377 READY on
        a verified ileal reach; c2e53f8e holds it, extent and performed_status, as it holds D108's controls);
      - test_d114_a_reach_at_the_pouch_is_the_pouchs_whatever_the_words (44386 READY, as D108; c2e53f8e holds it);
      - test_d114_the_jejunal_class_reads_its_reach_only_beside_a_stoma;
      - test_d114_the_route_words_are_the_specs_and_no_sentence_names_a_vendor.
    - RegionOfTheAct:
      - test_d114_the_gastric_apc_filed_under_the_enteroscopy_is_the_egd_sessions;
      - test_d114_44369_is_held_on_the_gastric_apc_and_43235_base_included_beside_it;
      - test_d114_the_esophagus_and_the_duodenum_are_the_egds_regions_too;
      - test_d114_a_small_bowel_act_stays_the_enteroscopys (control: 44369 and 43235 READY);
      - test_d114_an_act_whose_place_is_not_verified_keeps_geminis_family;
      - test_d114_without_a_done_egd_the_act_keeps_its_family (no EGD; a planned EGD);
      - test_d114_a_code_held_by_its_class_and_by_its_acts_region_asks_both_in_one_question;
      - test_d114_the_enteroscopys_base_code_stays_held_beside_its_moved_act (alone, beside 43235, beside 44369; the
        denial and the jejunal controls);
      - test_d114_an_examination_and_an_egds_own_act_never_move.
  - One existing expectation changed, as the spec requires:
    test_d108_an_ileoscopy_through_the_encounters_verified_stoma_fits_44380_to_44384 (test_interpretation_r4_enteroscopy).
    Its answer's examination words ('ILEOSCOPY', 'enteroscope', 'was advanced') name no route, so 44382 is now held with
    the route question; the READY control with the route named is the new module's. Its name is kept for traceability.
  - Mutation proof: 22 mutants, each made in its own copy of the final tree (hard-linked, the mutated file written as a
    new inode), applied exactly once and confirmed by its marker; each copy differs from the work tree in that file
    alone (sha256), and the work tree's manifest is the same before and after. Every mutant fails at least one pin, and
    every new pin and the changed one fails under at least one mutant.
    - M1 the call in sessions() removed; M2 the act_elsewhere hold removed; M3 the target read unverified; M4 no done EGD
      needed; M5 the small bowel among EGD_REGIONS; M6 an examination moved too.
    - M7 the route never decides; M8 a route named elsewhere no doubt; M9 the reach words verify a route; M10 an
      unusable attribute's words verify; M11 the route read for a pouch reach; M12 no oral words; M13 the route question
      never chosen; M14 the route question drops the incompleteness; M15 the class question no longer names the route;
      M16 "another class fits" reads the route (44361 falls to R6's question); M17 the stoma and pouch routes swapped; M18
      the route read with no stoma or pouch.
    - M19 the act's region hold displaces the class hold; M20 the class hold displaces the region hold.
    - M21 the diagnostic code's arm removed (44360 READY beside its moved act); M22 that arm held beside any moved event,
      a denial too.
  - Suites (t.sh, Postgres 127.0.0.1:55461, a new suffix each run):
    - the 46 tests.test_interpretation_* modules (45 at 1caaf0609, the replay pins among them), with
      test_pipeline_assess_events, test_readers_dispatch, test_guard_static and test_guard_mutation: 1,303 tests at
      1caaf0609, OK; 1,326 on the repair, OK (1,303 + the 23 new; the changed D108 pin passes);
    - the modules that switch on the new chain (test_change_context_events, both guard matrices,
      test_overlay_differential, test_peer_heading, test_pipeline_api, test_pipeline_interpret,
      test_retry_reading_api, test_models_event_inventory, test_repairs_7c8_p1reports, test_repairs_7c8_p1sends,
      test_repairs_ec5_reportruns): 266 tests, OK, 3 skipped, on the repair.
  - Cost on FRESH-2 (f2r5b-enteroscopy-route against f2r5int): none.
    - The summary is unchanged: A 96/6, B 177/15, C 171/19 plus 2 safe_hold.
    - 0 of 486 rows change in any field, and all 360 scored files are byte-identical (diff -rq; every file rewritten
      after the scoring began). FRESH-2 has no enteroscopy session and no act filed under one.
    - The head-to-head (h2h.json) is identical to h2h-r5int.json in every key: run 1 214/234, worse on the same 5 rows
      (all holds), better on 69, facts moved 0, 7 unstable, 126 rows run three times.
    - 0 new false READY, false exclusion, dropped question or ready-on-wrong-facts. The replay pins pass unchanged.
  - Cost on the 128 probe rows (tools/cases.py; pristine 1caaf0609, the build, c2e53f8e by both drivers, which agree on
    all 128): 0 held turned READY, 0 excluded; 66 rows change (status, facts, checks or wording), each from READY to
    held, by an added question or by a question's wording, except three where 44360's question changes fact
    (base_included to procedure, above). The holds of a code c2e53f8e also holds but that may be correct:
    - 44382 on the author's ileoscopy control and 44377 on an oral examination whose words name no route (the route
      not verified): the spec's fail-closed rule;
    - 44377 on 'The double-balloon enteroscope was advanced orally to the pre-pouch ileum.' with 'orally' verified: the
      J-pouch named in the reach words is a doubt.
  - Not built, recorded:
    - 43270 is not made READY on the note's input. A code's support reads the act's OWN family (events.is_candidate,
      events.py: event['family'] != link.family), outside this repair's ownership; the call in sessions() changes the
      sessions, event_coding and coverage only. c2e53f8e READYs 43270 there; the new path holds it (performed_status), as
      at 1caaf0609.
    - Without a verified stoma or pouch, a route through a stoma named in the examination's own words is not read (the
      spec: D108 as built). 'Procedure: Ileoscopy through the ileostomy.' with no anatomy entry: 44377 READY (1caaf0609
      READY; c2e53f8e holds).
    - The spec's rule (a route word NAMED in the statement's words) cannot tell a route from a place inside those words.
      Status words 'was advanced to the distal ileum, 20 cm proximal to the ileostomy' verify the stoma route: 44382
      READY (1caaf0609 READY; c2e53f8e holds extent). Closing it needs route phrases or a route attribute in the schema
      (a new INTERPRETATION_VERSION).
    - A stoma's type is still not read (D108's residual), now through the words too: 'was advanced through the colostomy
      stoma into the terminal ileum' beside an 'end colostomy' entry names 'stoma': 44382 READY (1caaf0609 READY;
      c2e53f8e holds).
    - The jejunal class reads its reach only (the spec reads the route for an ileal reach): an ileoscopy 'through the
      ileostomy' to the proximal jejunum: 44361 READY (1caaf0609 READY; c2e53f8e holds).
    - The retrograde route is not read without a stoma or pouch (D108's residual): 44377 READY on the retrograde DBE.
    - The region rule needs a DONE EGD (the spec). Beside an EGD that is only possibly this encounter's (D62: its time
      words 'At the index visit'), the gastric act stays the enteroscopy's: 44369 READY (1caaf0609 READY; c2e53f8e holds
      performed_status). D87's reading would make the act's family a doubt.
    - An EGD Gemini makes the push enteroscopy's endoscopic portion (part_of) is still a done EGD session: the gastric act
      moves to it and 44369 is held there too (a hold; c2e53f8e reads no part_of).
    - The region rule moves only enteroscopy acts into a done EGD. An EGD act in the small bowel beside a done
      enteroscopy, and an enteroscopy act at the colon or the ampulla, keep Gemini's family.
    - A code held by both its class and its act's region carries one check, the class check, with both reasons; the
      service.act_elsewhere id appears only where the region holds it alone.
    - By construction (not probed): a DOUBTED enteroscopy act that moves to the EGD lists its in_doubt item, and asks its
      service question, in the EGD session (coverage.reconcile reads session.events), not the enteroscopy's.
    - An act code with one supporting act in its own session and another moved (a jejunal and a gastric APC, both filed
      under the enteroscopy) is READY on its own act, as before, whichever passage it cites; its events.match check
      still lists both acts (support reads Gemini's family). c2e53f8e READYs 44369 citing the jejunal APC and holds it
      (performed_status) citing the gastric one; the new path READYs it citing either.
    - The route words are an engine list in classes.py (read at assess time over the stored located words), not one of
      lexicon.py's binding lists versioned by INVENTORY_VERSION; ENGINE_VERSION is unchanged, as for D108.
    - "OUTSIDE the small bowel (the stomach, the esophagus)": EGD_REGIONS follows the installed FAMILY_REGIONS and
      includes the duodenum, whose region mapping.REGION_OF keeps apart from the small bowel's. 'Two duodenal bulb
      angioectasias were treated with argon plasma coagulation.' moves to the EGD and holds 44369 (pinned); c2e53f8e
      holds it too and READYs 43270.

- **D115 A hemostatic clip or injection whose own words state no bleeding is a bleeding control in doubt (2026-11-11;
  the round-4 family parity audit, EGD gap D, critical; amends FINAL 7.7's clip rule as mapping.catalogue_kind reads it;
  repair key egd).** catalogue_kind read any clip or injection whose purpose 'hemostasis' is verified as a bleeding
  control. The purpose is verified when its words bind (normalize.py:602), so the adjective alone made a control of
  bleeding.
  - The gap's input (audit case D1): 'The gastroscope was advanced to the second portion of the duodenum.' / 'A 12 mm
    clean-based ulcer was seen in the gastric antrum.' / 'Two hemostatic clips were placed across the ulcer.' Gemini: E2
    clip, performed, technique 'hemostatic clips', target L1, purpose hemostasis worded 'hemostatic' (the attested note8
    and C2MEM purpose shape). 43255 cites the clip sentence.
    - 1caaf0609: 43255 READY on "bleeding control (clip) of the 12 mm clean-based ulcer".
    - c2e53f8e (harness configured, as production runs it): 43255 held [performed_status], "The documented upper
      endoscopy leaves the bleeding control in doubt (...). Was a bleeding control performed on the date of service?"
      (HEMOSTATIC_ADJECTIVE, refutation multi-3).
  - The rule (mapping.catalogue_kind's bleeding-control arm, mapping.hemostasis_in_doubt, mapping.bleeding_stated). A
    clip or an injection with a usable hemostasis purpose and a usable 'performed' status is a bleeding control only
    when one of its OWN words (kind, status, target, device, purpose) states bleeding or names the hemostasis as the act:
    - BLEEDING_STATED: bleeding (bleed, bled, rebleeding), oozing, hemorrhage, spurting, a visible vessel, an adherent
      clot, stigmata of recent bleeding or hemorrhage, and the noun hemostasis ("for hemostasis", "to achieve
      hemostasis"; the installed rule reads any bleeding-control word but the adjective as the act);
    - not counted when a negator stands anywhere before it in the same words (lexicon.NEGATORS, non, absent, absence,
      free, negative, a contraction in n't: "no active bleeding, oozing or visible vessel", "the non-bleeding ulcer",
      "without stigmata of recent bleeding");
    - not counted in words that hold a prevention, risk, hedge, condition or other-occasion word (NOT_BLEEDING_NOW: "to
      prevent delayed bleeding", "to ensure hemostasis", "if bleeding recurs", "a previously bleeding ulcer").
    - Otherwise its catalogue kind is mapping.POSSIBLE_BLEEDING_CONTROL: a bleeding control in DOUBT. No code profile
      covers it, so no code is matched by it. The bleeding-control codes (43255, 43227, 44366, 44378, 44391, 45334, 45382)
      are held [performed_status], never READY. The injection codes (43236, 43243) take no act that may be a control of
      bleeding: held, as at 1caaf0609.
    - A statement that is not a usable 'performed' (a denial, a plan, a doubt, an attempt, status words that do not bind)
      keeps the bleeding control, so its own rule holds or excludes as before. FRESH's "No hemostatic cautery, hemostatic
      clipping, injection for bleeding, or band ligation was performed" still denies a control of bleeding (55 such
      denials, 27 in FRESH-2 and 28 in FRESH-1, unchanged).
  - Never an absence (D62, D87; coverage.doubted, coverage._bleeding_control_in_doubt). The doubted act is a doubted
    reportable act of its session in a family whose catalogue acts hold the bleeding control:
    - the base code beside it stays held (1caaf0609 held it beside the bleeding control it read). On D1 with 43235:
      held, "Is 43235 reported separately from possible bleeding control (stated in doubt) for this examination?";
      c2e53f8e is READY there;
    - it is listed in doubt (in_doubt, completeness incomplete), and its own unusable attributes are asked at service
      scope (an unanchored time: event_time, which 1caaf0609 asked on 43255 itself);
    - except where, read as the bleeding control, it would be a removal's procedural adjunct (bundled_reason: D30's
      verified part_of or the removal's lesion, D79's attempted whole). "Two hemostatic clips were placed on the
      polypectomy site of the polyp." is then not listed and adds no base hold, as 1caaf0609 bundled it; 43255 stays
      held.
  - Pins (tests/test_interpretation_r5_egd.py, D115BleedingControlInDoubt, 12 tests): gap D's D1 (43255 held, its
    citation shown, the overlay held, listed in doubt); D1 beside 43235; the hemostatic injection with 43255, 43236,
    43243 and 43235; the own-words controls (an oozing vessel, the noun, "to control the bleeding": READY, as on both
    engines); prevention, non-bleeding and without-stigmata (held); every family (45382, 45334, 43227, 44366 held with
    performed_status, their base held); the statement-status table; the words table; the adjunct; the unanchored time;
    and the recorded cost below.
  - Installed outputs on the pin inputs (c2e53f8e, both drivers): equal on D1, prevention, without-stigmata, the four
    families, the injection's 43255, the adjunct, the unanchored time (43255 held [performed_status]) and the own-words
    controls. c2e53f8e READYs 43255 on "Two hemostatic clips were placed across the non-bleeding ulcer." (its
    BLEEDING_PRESENT matches "bleeding ulcer"); this repair holds it. On the injection c2e53f8e holds 43236 and 43243 with competing_codes (harness) or READYs them (no participant);
    this repair holds both, as 1caaf0609 does.
  - Built where the spec is not literal (recorded, a disagreement):
    1. "in its own sentence or for its lesion": catalogue_kind(event) is called with the event alone (map_events and
       relations.Context, outside this ownership), and an event carries neither its passages' text nor its lesion's
       record. So it reads the event's own attribute WORDS (EB1), never the sentence beyond them and never the lesion.
       Gap D's D3 ('A 12 mm ulcer with an oozing visible vessel was seen in the gastric antrum.' / 'Two hemostatic clips
       were placed across the ulcer.', target words 'the ulcer') is held [performed_status], as c2e53f8e holds it, where
       the spec and the audit expect READY (pinned as the recorded cost). Reading the lesion needs the bleeding test
       where the reading is - events.supports or a catalogue_kind given the draft - outside this ownership.
    2. "held with performed_status naming the statement": 43255 is held through the not-documented route (no event is
       a candidate): "Confirm whether 43255 is supported by what was done on the date of service.", its source the code's
       own cited spans (the clip sentence when it cites it, pinned). The fact is the installed one; the installed's
       sentence ("leaves the bleeding control in doubt (...)") needs a doubt hold for a candidate that does not support -
       events.py, outside this ownership.
  - Residuals:
    1. The in_doubt item's fixed wording (coverage.reconcile, outside this ownership) reads "CPT Studio could not confirm
       from the document that it was done at this encounter"; what is in doubt is whether it controls bleeding.
    2. A denial that concerns only the bleeding control ("No bleeding control was needed.") no longer pairs with a clip
       in doubt (their catalogue kinds differ and their raw kinds differ). 43255 is then held not documented, never
       READY. With 43255 citing only such a denial it could be excluded by it, as for any act that is no bleeding
       control; with the clip sentence cited it is held (C-10).
    3. Inventories normalized before this change keep 'bleeding_control' (catalogue_kind is stored by map_events). The new
       path is not installed, so none exists in production.
    4. A word list decides the READY side: a missing word leaves the act in doubt (a hold), never READY. Missing words are
       false holds by construction (for example "Forrest Ib", "a clot", "fresh blood").
    5. 43255 is matched by no event, so a question 1caaf0609 asked of it BECAUSE the bleeding control supported it is
       not its question any more: a Gemini open question on the session (D31) or a removal's procedural-adjunct identity
       (D41). Probed on D1 with Gemini's open question {about: performer, events: [E1]}: 1caaf0609 asks 43255
       [event_performer, extent], this repair [performed_status, extent], and no service question. With 43235 proposed
       too, 43235 asks event_performer, so the question is lost only when 43255 is the session's one code. The act's
       own unusable attributes are still asked at service scope (the unanchored-time pin). 43255 is held either way, never
       READY. Keeping those questions needs a doubted candidate in the per-code rule (events.py, outside this
       ownership). 0 FRESH members.

- **D116 An EGD stent removal or exchange is a reportable act of its session (2026-11-11; the round-4 family parity
  audit, EGD gap A; repair key egd).** coverage.reportable_kind required the kind in the family's catalogue acts, and only
  the ERCP's lists stent_removal and stent_exchange.
  - The gap's input (A1): '...advanced to the second portion of the duodenum.' / 'The fully covered esophageal stent was
    removed by its retrieval loop without difficulty.' Gemini: E2 stent_removal, performed, target esophagus; 43235 alone.
    A3: '...was exchanged for a new 18 mm fully covered esophageal stent across the stricture.' as stent_exchange.
    - 1caaf0609: 43235 READY, coding complete_pending_review.
    - c2e53f8e: 43235 held [base_included] ("includes stent placement"), stent not_covered.
  - The rule (coverage.reportable_kind, STENT_ACTS): a stent removal or exchange is a reportable kind of its session in
    every family whose catalogue acts hold the stent placement - the EGD, the enteroscopy, the colonoscopy, the
    sigmoidoscopy (the ERCP lists them itself; the EUS holds no stent act). Reportable when done, doubted when in doubt,
    so base_included holds the base code beside it ("stent removal", "stent exchange", "(stated in doubt)"), at assess
    time and in the overlay.
  - Pins (D116StentRemovalAndExchange, 4 tests): A1, A3, the removal in doubt ("was possibly removed"), the colonoscopy's
    45378 and the families table. c2e53f8e: equal on A1, A3 and the colonoscopy; it READYs 43235 on the doubted removal
    (this repair holds it).
  - Not built (a disagreement): "the act is listed not covered when no code covers it". coverage.reconcile skips every
    kind outside the family's catalogue acts (`if kind not in entry.acts: continue`), outside this ownership. On A5 (the
    removal beside 'Biopsies of the gastric antrum were taken with cold forceps.', 43239 alone) 43239 is READY and coding
    is complete_pending_review; c2e53f8e lists 'stent' not_covered. On A1 and A3 coding is incomplete through the base
    question. The one-line change (`kind not in entry.acts and not reportable_kind(event)`) would list it as 'unsupported'
    (no EGD code profile covers a stent removal), with no second-review mark.

- **D117 A removal of unstated method is a doubted act of its session (2026-11-11; the round-4 family parity audit, EGD gap
  B; repair key egd).** The 'removal' umbrella was in NOT_ACT_KINDS, so it was neither reportable nor doubted and
  coverage.reconcile skipped it.
  - The gap's input (B1): 'A 7 mm sessile polyp was seen in the gastric body.' / 'A polypectomy of the gastric body polyp
    was performed.' Gemini: E2 removal (words 'polypectomy'), performed, target L1 (attested: fb08, v4, fb09). 43235
    alone; B4 adds a biopsy and proposes 43239 alone.
    - 1caaf0609: 43235 READY with coding complete; on B4, 43239 READY with coding complete (the polypectomy invisible).
    - c2e53f8e: 43235 held [base_included] ("includes snare removal"), snare not_covered; on B4 43239 READY, coding
      incomplete.
  - The rule (coverage.doubted, _removal_in_doubt): a 'removal' umbrella stated positive or uncertain, not verified at
    another time or by another performer, in a family whose catalogue acts hold a removal method (the EGD, the
    enteroscopy, the colonoscopy, the sigmoidoscopy), is doubted. The base code is held ("removal (stated in doubt)"),
    the act is listed in doubt, and its method is asked at service scope (act_method, focus_question's h5) unless a
    proposal of the family already asks it. A removal at another encounter ("... removed at her colonoscopy in January
    2024") is no doubt: 45378 READY, as on both engines.
  - Pins (D117RemovalOfUnstatedMethod, 7 tests): B1, B4, B3 ('The gastric body polyp was removed.'), control B2 (43251
    beside it asks act_method and holds 43235, no second item), the colonoscopy's 45378, the history control, and the
    families-and-frame table shared with D115. c2e53f8e: equal on B1 and the colonoscopy (held); it READYs 43235 on B3
    (no snare word), where this repair holds it - the method of a removal is never the diagnostic code's.
  - Residual: two removals of unstated method in one session are one in_doubt item and one act_method service question
    (in_doubt_questions asks once per family and fact, D89); each removal's own method code asks its own.

- **D118 Two dilation codes of different techniques for one stricture compete (2026-11-11; the round-4 family parity
  audit, EGD gap C; amends D40, D55; repair key egd).** combination.competition compares the codes' claims, and the
  technique filter (R4) gives a balloon code and a guide-wire code disjoint E* on one stricture.
  - The gap's input (C1): 'A benign-appearing peptic stricture was seen in the distal esophagus at 37 cm.' / 'The
    stricture was dilated with a through-the-scope balloon to 15 mm.' / 'The stricture was then dilated with a Savary
    dilator passed over a guidewire to 17 mm.' Gemini: E2 balloon and E3 wire_bougie on L1; 43249 and 43248.
    - 1caaf0609: both READY.
    - c2e53f8e with the harness configured (production): both held [competing_codes]; with no participant both READY.
  - The rule (assess._claims, _stricture_claims, _one_stricture, _technique_doubts). A code whose profile names a
    technique also claims every current performed act of its family and kinds done on ONE stricture with another of its
    own acts, whatever its technique:
    - its own acts are its supporting events, else (as D74 reads a doubted defining act) its own technique's acts in
      doubt: positive or uncertain, possibly current, not another performer's, a device of its class or not verified as
      a class, and not verified outside its D29 site class;
    - one stricture: one verified lesion, or two identity does not establish as distinct; otherwise unless every verified
      place of one is disjoint from every verified place of the other; a place unread competes (the installed
      _same_claim's order, erring toward one);
    - an act is never paired with itself, so a technique code held for its site claims nothing from the one dilation a
      code of any technique supports (FRESH-2 fb07: 43245 READY, 43249 held for its site, unchanged).
    - Each code keeps its own E* (support.acts); only the competition reads the claims. The overlay releases the hold
      once the other code is rejected (support.competes).
  - Pins (D118DilationsOfOneStricture, 10 tests): C1 (both held, each other's rival, overlay held); the release on
    rejection; the Savary dilation whose site is unread (both held, 43248 with act_target and competing_codes, as
    c2e53f8e holds both); and the controls: two places verifiably apart (both READY); two strictures verified distinct
    by their distances (both READY); 43245 with 43249 on one pyloric dilation and on two (43245 READY, 43249 held for
    its site); fb07's anastomotic shape (D34; the same); a Savary dilation at another encounter (fb02's shape: 43249
    READY, 43248 held technique); two balloon dilations with 43248 (43249 READY, 43248 held technique).
  - Installed outputs (harness configured): equal on C1, the unread Savary site and the two places apart; with two
    balloon dilations 43249 is READY on both (c2e53f8e holds 43248 [performed_status], this repair [technique]); with the
    Savary dilation at another encounter c2e53f8e excludes 43248, this repair holds it [technique] as 1caaf0609 does.
    c2e53f8e also holds both codes on the two distinct strictures (its reader leaves them one site) and holds 43245 with
    competing_codes beside the wrong-site 43249 (one or two pyloric dilations, fb07's shape). This repair keeps 1caaf0609
    there, by the installed rule's own structure (lesion records compared whole, a code verified at another site claims
    nothing); recorded, not repaired, and FRESH-2 fb07's 43245 is expected READY.

- **D119 A PEG filed under the feeding tube is an act of the EGD done with it too (2026-11-11; the round-4 family parity
  audit, EGD gap H; repair key egd).** coverage.sessions groups events by Gemini's procedure family, and base_included
  read only the EGD's own session.
  - The gap's input (H2): 'UPPER ENDOSCOPY WITH PEG PLACEMENT' / '...advanced to the second portion of the duodenum.' /
    'A 20 Fr pull-type PEG tube was placed under endoscopic guidance without difficulty.' Gemini: E2 peg, performed,
    procedure feeding_tube worded 'PEG' from the heading; 43235 alone.
    - 1caaf0609: 43235 READY. c2e53f8e: 43235 held [base_included, performed_status] ("includes gastrostomy (PEG)
      placement").
  - The rule (combination.base_included, _acts_beside): an EGD base code matched to a done EGD session reads, as (b) and
    (c), the reportable and doubted PEG entries of the encounter's feeding-tube session. The PEG kind only (a tube
    replacement or placement under the feeding tube is not read), and the EGD's codes only. The overlay applies it at
    read time over the same record.
  - Pins (D119PegUnderTheFeedingTube, 6 tests): H2 (held, "gastrostomy (PEG) placement", the PEG still the feeding-tube
    session's), H1 (43235 held beside 43246), a doubted PEG ("(stated in doubt)"), control H3 (the PEG under the EGD),
    a PEG in 2023 (no hold), and the kind-and-family unit table. c2e53f8e: equal on H2, H1, H3 and the doubted PEG; it
    also holds 43235 beside the 2023 PEG, where this repair is READY as 1caaf0609 is.
  - Not built (a disagreement): "43246 is supported by it (not 'not documented')". A code's candidates are events of its
    own family (events.is_candidate, events.py), outside this ownership. On H1 (43246 citing the PEG line beside 43235)
    43246 stays held [performed_status], "CPT Studio's reading of the document records no gastrostomy (PEG) placement
    documented as done"; c2e53f8e holds it [performed_status] too, so this is no regression against it.
  - Residual: the feeding-tube session keeps its own no_proposal item; c2e53f8e lists 'peg' not_covered under the EGD.

- **D115-D119, what was edited, and the measurement.**
  - Edited (patch.diff on 1caaf0609):
    - studio/interpretation/mapping.py: catalogue_kind's bleeding-control arm and its D115 block (POSSIBLE_BLEEDING_CONTROL,
      BLEEDING_STATED, BLEEDING_NEGATORS, NOT_BLEEDING_NOW, HEMOSTASIS_WORDS, bleeding_stated, hemostasis_in_doubt) and
      `import re`;
    - studio/interpretation/coverage.py: reportable_kind (D116, STENT_ACTS) and doubted (D115, D117; helpers _stated_here,
      _removal_in_doubt, _bleeding_control_in_doubt);
    - studio/interpretation/combination.py: base_included (D119; _acts_beside);
    - studio/interpretation/assess.py: _claims (D118; _one_stricture, _technique_doubts, _stricture_claims);
    - tests/test_interpretation_r5_egd.py is NEW, with 38 tests. No existing test changed.
  - Suites (t.sh, Postgres 127.0.0.1:55461; every tests.test_interpretation_* module, test_pipeline_assess_events,
    test_readers_dispatch, test_guard_static, test_guard_mutation and the 12 other modules that import the new path - 61
    modules): 1569 OK, 3 skipped on 1caaf0609; with the new module on this patch 1607 OK, 3 skipped (1569 plus its
    38). tests.test_interpretation_replay passes: no replay fixture was regenerated.
  - Mutation proof: 25 mutants, each in its own copy re-synced from the work tree, its replacement asserted once and its
    application confirmed by a marker; the unmutated module ran first (38 OK); the work tree's sha256 was unchanged.
    Every one is killed:
    - D115: M01 (the arm undone) 10 failing tests; M02 (the doubted arm undone) 4; M03 (the adjunct exception) 1; M04
      (negation) 2; M05 (the prevention words) 2; M06 (the status condition) 1; M07 (purpose words only) 1; M08 (the
      family condition) 1.
    - D116: M09 (undone) 4; M10 (the stent-family condition) 1.
    - D117: M11 (undone) 5; M12 (the family condition) 1; M13 and M14 (the time and performer frame) 2 and 1.
    - D118: M15 (undone) 3; M16 (the doubts undone) 1; M17 (one stricture always) 2; M18 (distinct lesions ignored) 1;
      M19 (the D29 exclusion undone) 1; M20 (an act paired with itself) 1; M21 (another class admitted as one's own) 1;
      M22 (an act at another encounter admitted) 1.
    - D119: M23 (undone) 3; M24 (every feeding-tube kind) 1; M25 (every family's base) 1.
    - A first draft filtered D118's claims to acts of another technique; its removal survived (no input separates them:
      a same-class act on one stricture is either supported or claimed by no rival), so the filter was dropped.
  - The new module on 1caaf0609: 25 of its 38 tests fail (35 failing and 36 erroring subtests); the 13 that pass there
    are the controls (unchanged behaviour).
  - FRESH-2 (f2r5b-egd): A 96/6, B 177/15, C 171/19 plus 2 safe_hold. Against f2r5int: 0 of 486 rows, and 179 of 179
    assessments and 179 of 179 inventories byte-identical. Positive control: a planted event-coding key appeared in all
    21 FRESH-2 A assessments (f2r5b-egd-posctl) and nothing else moved, so the scorer read this tree.
  - FRESH-1 (f1r5b-egd): A 97/5, B 174/18, C 165/24 plus 1 false_ready and 2 safe_hold, the false_ready pre-existing.
    Against f1r5b-currency2-pristine and f1r5b-em2-base: 0 of 486 rows, 358 of 358 per-run files byte-identical.
  - The head-to-head (h2h.json) is identical to h2h-r5int.json: run 1 214/234 (A 34/34, B 59/64, C 121/136); worse 5,
    better 69; facts moved 0. No new false_ready, false_exclusion, dropped_question or ready_wrong_facts.
  - Census (tools/census.py) over FRESH-2 and FRESH-1 inventories: 0 performed hemostatic clips or injections (55
    denials, 27 and 28, unchanged), 0 positive stent removals or exchanges, 0 positive current removal umbrellas (every recorded
    one is verified at another encounter), 0 feeding-tube PEGs, and one EGD with dilations of two device classes (fb02 r3,
    whose wire-guided dilation is verified on June 4, 2026: no claim). So the corpus measures none of these classes:
    the cost is 0 rows because the classes have no members.
  - The audit's own 30 cases (repair4/audit-egd/cases): 8 outcomes change, each READY to held: A1, A3, B1, B3, C1, D1,
    D3, H2; each equals c2e53f8e (harness) except B3 (c2e53f8e READY) and D3 (the recorded cost).

- **D124 An act documented only in another role's entry holds its code (2026-11-11; the round-4 family parity audit,
  colon-sig gap 0; owner directive 2026-11-06, item 2: other-provider acts stay distinct from completed current
  services; repair key colon).**
  - The gap (high). No rule on the new path read where an act is documented. On the contract's frame defaults
    (performer documenting_team, time current_encounter, no words) an act told only in a nursing note or under a
    pathology report heading is done, and supports its code. The audit's inputs, each a structured colonoscopy report
    ('Colonoscopy report (fictional)' / 'Place of service: ...' / 'Procedure: Colonoscopy' / 'The colonoscope was
    advanced to the cecum and the examination was completed.'):
    - T02: 'Nursing note' / 'Nurse: A 6 mm polyp in the sigmoid colon was removed with a cold snare and retrieved.',
      45385 citing the nurse's line.
    - U05: 'Nursing note' / 'Nurse: Cold forceps biopsies of the sigmoid colon polyp were obtained and sent to
      pathology.', 45380.
    - T03: 'Pathology report' / 'Sigmoid colon polyp, cold forceps biopsy: tubular adenoma.', 45380.
    - 1caaf0609: READY on all three, no question, coding complete_pending_review.
    - c2e53f8e (engine.assess as tests/test_harness_engine.py drives it, same texts and codes): held [performed_status].
      T02 and U05 with engine._another_roles_hold's question, "The snare removal is documented only in the nursing
      entry (“Nurse: ...”). Was it performed in this colonoscopy on the date of service?"; T03 act_missing ("CPT
      Studio could not find a forceps biopsy in the documented colonoscopy. ...").
  - The rule (events.another_role_hold, called once in evaluate, after the bundling holds and before the performed and
    incomplete returns). A code the per-code rule would support is held when EVERY act it accounts for (its supporting
    events but the examination, which is the session: C-1) is told only in another role's entry. An act is so told when
    every located place of its KIND and STATUS passages lies in one:
    - the passage begins with a role label, as a whole label: a name and its colon ('Nurse:', 'RN:', 'Pathology:',
      'Anesthesia:', 'CRNA:'), or an entry phrase followed by its end, a colon, a bracket or a dash ('Nursing note',
      'Nursing procedure record', 'Pathology report', 'Anesthesia record', 'Radiology report');
    - or, read from the document's lines: the line it stands on opens with such a label; or the line is a role's
      heading line (a heading name alone, 'NURSING', 'Pathology:'; or an entry phrase with at most a bracketed note, a
      date or time after a colon or dash, a closing colon); or it lies in the lines after such a heading line and
      before the next heading. The next heading is services.GENERIC_HEADING's shape (c2e53f8e): a line of at most 61
      characters opening with a capital or a digit, of letters, digits and / & , ( ) ' - only, at most a closing colon.
      A blank line does not end an entry. An act's own line is content, never the next heading.
    - never a line the physician's own label opens ('Endoscopist: ...', 'Physician addendum: ...').
    - Never a label or heading: 'Nursing staff: ...', 'Nurse: Jo Rowe, RN' and 'RN: Jo Rowe' as staff fields (they
      label their own line only and head nothing: services.ROLE_HEADINGS' refutation r1 missed-1), 'Nurse present
      throughout the procedure.', FRESH's own 'Anesthesia, equipment, and quality measures', 'Recovery instructions and
      management plan' and '- Pathology from jars 1-3 will be sent ...'.
    - An act with any statement passage outside such entries leaves the code as it is (U06: the physician's own line,
      alone or restated by the nurse; and a code over the physician's own biopsy beside the nurse's), and so does a
      code that accounts for no act (a base code, an examination-only EUS code: c2e53f8e's match lists no act either).
    - The hold: Evaluation reason 'another_role' (events.ANOTHER_ROLE, c2e53f8e's reason), state uncertain, E* empty
      and the acts in ``read``, so coverage still counts them as the code's (they are listed nowhere as uncovered, as
      the installed release's held match keeps its acts). ONE question, performed_status, worded as c2e53f8e words it -
      the entry's role and the act's first passage in it, quoted at 120 characters; the detail is "The colonoscopy is
      documented as performed with ... But the snare removal it accounts for is documented only in the nursing entry
      (...), not by the physician performing the colonoscopy. Held for the reviewer, not excluded." Never an exclusion.
  - Three readings beyond the spec's words, each only ADDING holds against its literal reading:
    1. The act's kind and status passages, not OWN's (kind, status AND target). The target's passages can be where the
       physician describes the LESION: 'Findings: A 6 mm sessile polyp in the sigmoid colon.' / 'Nursing note' /
       'Nurse: The polyp was removed with a cold snare and retrieved.' with the snare's target passage the findings
       line. Read as OWN, that place is outside the entry and 45385 is READY (mutant M5); c2e53f8e holds it with its
       another-role question. Kind and status are a subset of OWN, so the rule holds wherever the literal one does.
    2. "The passage begins with a role label" includes the line it stands on: Gemini may cite the clause after the
       label (prompt.py: "a sentence, a clause or a line"). 'A 6 mm polyp ... retrieved.' cited from 'Nurse: A 6 mm
       polyp ... retrieved.' with no heading above: READY without it (mutant M16); c2e53f8e holds it.
    3. The examination is not an act (C-1). A base code's supporting event is its session, and c2e53f8e lists no act
       for a base code, so it never holds one this way either.
  - The text, and the one statement outside the spec's ownership. evaluate receives no text, and the inventory holds
    only text_sha256, so "read the text the assess call receives" cannot be built inside events.py alone: T03's
    'Pathology report' is no passage of any event, and its biopsy line carries no label. assess.assess hands the revision
    text to the reading it builds (``reading.text = text``, one statement beside the Reading's construction; the spec
    gives assess.py only the service-question call). Without it (mutant M8) T03, the blank-line and the nursing-lines
    inputs are READY again. A reading without the text - overlay.counted_codes, a unit test's Reading - reads the
    passages' own labels only: T02 is still held there, T03 supported. The overlay reads only E* and ``read`` from it,
    the same event set either way (pinned).
  - No pattern. The first build compiled regular expressions in events.py, and tests.test_interpretation_assess.Imports
    failed: the six engine modules import no ``re`` ("no pattern here can be a denied pattern's twin"). The labels are
    compared as case-folded strings (curly apostrophes straight, whitespace runs one space), re-typed from
    services.ROLE_HEADINGS and ROLE_LABEL (c2e53f8e) - never imported, never called (the guard tests pass). The helpers
    are nested in the one new function; its tables (ANOTHER_ROLE and the _ROLE_* constants) sit beside it.
  - This is no evidence binding (ADJUDICATION EB1): no value of Gemini's is read or changed - the act stays performed,
    current and the documenting team's - and it only turns a supported code into a hold. It does read the document's
    lines around an act, which EB1 forbids a binding check to do, so it is recorded as the owner-designed exception it
    is: it can hold, never release or exclude.
  - Pins (tests/test_interpretation_r5_colon.py; c2e53f8e's outputs on every input are in each docstring):
    - AnActToldOnlyInAnotherRolesEntryIsHeld: test_d124_a_snare_told_only_in_a_nursing_note_is_held (T02),
      test_d124_a_biopsy_told_only_in_a_nursing_note_is_held (U05),
      test_d124_a_biopsy_told_only_under_a_pathology_report_heading_is_held (T03),
      test_d124_the_label_opening_the_line_of_a_cited_clause,
      test_d124_a_lesion_the_physician_describes_does_not_release_the_nurses_removal, test_d124_beside_its_base_code.
      Each asserts the question word for word, the support reason, the read-time overlay (still held) and that the act
      is listed nowhere as uncovered. c2e53f8e holds all six [performed_status]: its question is identical word for
      word on T02, U05, the lesion input and beside the base code (and on the blank-line and nursing-lines inputs
      below), quotes the whole line on the clause input, and is act_missing's on T03.
    - TheEntryIsWhatItsLabelsAndHeadingsSay: test_d124_controls_the_physicians_own_line_states_the_act (U06, both
      forms), test_d124_controls_one_act_of_the_physicians_beside_one_of_the_nurses,
      test_d124_controls_an_unknown_performer_keeps_its_own_question (U07),
      test_d124_the_next_heading_ends_the_entry_and_a_blank_line_does_not (four cases),
      test_d124_a_staff_field_or_a_section_naming_a_role_is_no_entry (eight lines),
      test_d124_a_reading_without_the_text_reads_the_passages_own_labels. c2e53f8e gives the same outcomes, with two
      differences that are not D124's: on U07 it asks its another-role question where the build asks event_performer
      (C6: an unknown performer is never a match, so D124 is never reached; held on both), and under 'Recovery
      instructions and management plan' it holds the physician's snare for its own reading of that section
      ("a passage it cites about this service reads as uncertain").
- **D125 A documented endoscopic session that states no extent asks it at service scope (2026-11-11; the round-4
  family parity audit, colon-sig gap 1 and egd gap I; the round-4 enteroscopy review's parity note 2; repair key
  colon).**
  - The gap (medium, low). c2e53f8e's reconcile.documentation_clarifications (reconcile.py:960-967, through
    engine._service_questions) asks "How far was the instrument advanced (the landmark reached)?" of a documented
    gi.egd, gi.colonoscopy, gi.flex_sig or gi.enteroscopy service with no extent and an unknown completion, unless a
    proposal of the family already asks the extent, and counts it among the open questions. The new path asked service
    questions only for in_doubt items (FINAL 7.8). The inputs:
    - T04: 'Colonoscopy was performed with good preparation.' / the cold snare of a sigmoid polyp, no reach entry, no
      code. T05: the same for a flexible sigmoidoscopy. T06: T04 with 'No biopsies were taken.' and 45380 citing it
      (excluded on both engines).
    - egd I2: 'UPPER ENDOSCOPY REPORT' / 'The gastroscope was introduced through the mouth under direct vision.' /
      antral biopsies, no reach, no code.
    - The enteroscopy note: 'PUSH ENTEROSCOPY REPORT' / 'Procedure: Push enteroscopy.' / 'The enteroscope was
      introduced and the small bowel was examined.' / jejunal biopsies, with only 43239 proposed.
    - 1caaf0609: no question anywhere; T04's reasons ['1 documented service or act without a supported proposal'].
      c2e53f8e: the service question on every one, T04's reasons [..., '1 open question'].
  - The rule (coverage.service_extent_questions; assess adds its questions after in_doubt_questions'). For each
    documented session (session.done: the sessions the reconciliation reads) of those four families whose catalogue
    entry is supported and has the extent question:
    - when no done examination of the session (coverage.done_examinations) has a USABLE reach naming a place or a
      USABLE completion stated complete or incomplete;
    - and no proposal of the family asks the extent (``asked``, the D89 triples assess already builds, read as
      (family, fact): any of the family's extent questions, the R6 one or D28's and D108's class questions; an excluded
      proposal asks none);
    - one question per family: the catalogue's own question (catalogue.ENDOSCOPIC_QUESTIONS), scope service, fact
      extent, counted among the open questions. Never a hold; no code's status changes.
  - Two readings beyond the spec's words:
    1. "No stated reach" is no USABLE reach. An unverified or opened reach is a doubt, never a fact (D87), and
       establishes no extent: T04's text with a reach Gemini takes from the snare's sentence (D36 reach_inferred), or
       a reach to the cecum whose words its passage does not hold (words_unlocated), is asked. The literal reading
       drops it (mutant M10); c2e53f8e asks it on that text. So is a session told only by its acts, which no reach
       entry can name, and one whose reach only an examination D62 reads as possibly current states.
    2. The reason follows P10 (CPT Studio's reading, never a statement about the document): "CPT Studio's reading of
       the documented colonoscopy does not establish how far the instrument was advanced or whether the examination was
       completed." c2e53f8e: "The documented colonoscopy does not state ...". The question is identical.
  - Pins (TheServiceAsksItsExtent): test_d125_a_colonoscopy_with_no_reach_and_no_proposal (T04, reasons pinned),
    test_d125_a_flexible_sigmoidoscopy_with_no_reach_and_no_proposal (T05), test_d125_its_only_proposal_excluded (T06),
    test_d125_an_upper_endoscopy_with_no_reach_and_no_proposal (I2), test_d125_an_enteroscopy_beside_an_upper_endoscopy_code
    (43239 still [performed_status, extent]; c2e53f8e [extent]), test_d125_controls_a_proposal_of_the_family_asks_it_itself
    (S05, I3, 44361), test_d125_controls_a_stated_reach_or_an_undocumented_session,
    test_d125_controls_a_stated_incomplete_completion (D93's landmark-less 'incomplete' is stated),
    test_d125_an_unverified_reach_establishes_no_extent, test_d125_once_per_family. c2e53f8e gives every outcome but
    the planned control's (below).
- **D124-D125, what was edited, the proofs and the measurement.**
  - Edited (patch.diff removes no line):
    - studio/interpretation/events.py: ``another_role_hold`` and its tables, new; its one call in evaluate (three
      lines). Nothing else.
    - studio/interpretation/coverage.py: ``service_extent_questions``, new, after in_doubt_questions.
    - studio/interpretation/assess.py: the call adding its questions beside in_doubt_questions', and the one
      statement handing the text to the reading (outside the spec's ownership, above).
    - tests/test_interpretation_r5_colon.py, NEW: 22 tests. No existing test changed.
  - Suites (t.sh, Postgres 127.0.0.1:55461): every tests.test_interpretation_* module (45 and the new one),
    test_pipeline_assess_events, test_readers_dispatch, test_guard_static, test_guard_mutation and
    test_overlay_differential: 1327 OK (1caaf0609: 1305, plus the 22). The other 11 modules that import the package:
    264 OK, 3 skipped. No replay test failed.
  - On 1caaf0609 the new module gives 30 failures and 1 error in its 15 behaviour pins; its 7 controls pass.
  - Mutation proof: 18 mutants, one reused copy (mut-1); each replacement asserted to occur once, applied (marker and
    sha256 change) and restored (sha256 equal to work's); work's sha256s unchanged. Every one is killed: M1 (the call
    removed) 15 failures; M2 (no label read) 3; M3 (no heading read) 4; M4 (no heading ends an entry) 1; M5 (OWN's
    target passages too) 2; M6 (the physician's label not read) 1; M7 (one act in an entry suffices) 1; M8 (the text
    not handed over) 6; M9 (the service call removed) 16; M10 (a reach counted when merely given) 4; M11 (no proposal
    suppresses it) 3; M12 (one question per examination) 1; M13 (no documented-session gate) 1; M14 (a completion never
    counts) 1; M15 (a heading name followed by anything heads an entry) 7; M16 (the line's own label not read) 2; M17
    (one place in an entry suffices) 1; M18 (a reach never counts) 1. Every pin but U07's control fails under at least
    one; U07's cannot, by construction: its code is held before D124 is reached.
  - FRESH-2 (f2r5b-colon): A 96/6, B 177/15, C 171/19 plus 2 safe_hold.
    - Against f2r5int (1caaf0609): 0 of 486 rows, 179 of 179 inventories identical, 177 of 179 assessments identical.
    - The two others gain the service extent question [gi.colonoscopy], and one open question: C/PAR-008 r1 and
      C/W1-u31a-reg-p7-codes-025 r1, both 'ENDOSCOPY NOTE - EGD AND COLONOSCOPY, SAME SESSION' with only an EGD code
      (43239) or an ERCP code (43264) proposed. Both state no colonoscopy reach ('The colonoscope was inserted and
      advanced under direct vision.'), and c2e53f8e's head-to-head run asks 'extent' on both (results-installed-h2h.json:
      its colonoscopy service performed, extent '', completion unknown). They are parity, not cost - and the
      scorer's positive control: only this tree asks that question.
    - D124's census: 0 members among the 452 done acts of the 179 FRESH-2 inventories (0 of 479 in FRESH-1's). Its
      positive control - the same instrument with the line above one done act rewritten at equal length as 'Nursing
      note' - finds that act (A/note8 r1 E10), and does not without the plant. The class has no members in the corpus,
      so its cost is 0 rows.
  - FRESH-1 (f1r5b-colon) against f1r5b-currency2-pristine and f1r5b-em2-base (1caaf0609): 0 of 486 rows; the same two
    assessments gain the same question.
  - Head-to-head: identical to h2h-r5int.json in all 459 leaves. Run 1 214/234 (A 34/34, B 59/64, C 121/136); worse 5,
    better 69, unstable 7, facts moved 0. No new false_ready, false_exclusion, dropped_question or ready_wrong_facts.
  - Time: assess over the 179 FRESH-2 inventories, 0.469 s on 1caaf0609 and 0.485 s here (mean 2.6 and 2.7 ms).
    another_role_hold's worst case - one act on the last line of a 19,457-character, 247-line document with no heading
    above it, every line scanned (INTERPRET_MAX_CHARS is 20,000) - 2.8 ms a call.
  - Applies on 1caaf0609 (dry run and a real apply, byte-identical to the work tree), and on top of the five round-5b
    patches in progress (egd, enteroscopy-route, ercp2, currency2, em2) with offsets only.
  - Residuals, recorded, not built:
    1. D125, an examination only in doubt: 'It is unclear whether the colonoscopy was performed.' (no done event).
       c2e53f8e asks the extent of its 'uncertain' service; the build asks nothing - no documented session, and
       coverage counts it 'not established as performed'. Asking the extent presupposes the procedure was done. The
       owner's call.
    2. D125, a completion stated with no landmark: 'Colonoscopy was performed and the examination was completed.' The
       contract carries no completion-only reach (prompt.py: "Leave out an examination whose reach the document does
       not state"; normalize keeps a landmark-less completion only when it is 'incomplete', D93), so the build asks
       where c2e53f8e, reading completion 'complete', does not. A question, never a hold.
    3. D125, a colonoscopy stated only as planned under 'Procedure: Colonoscopy': c2e53f8e reads the heading as a
       documented colonoscopy, lists it no_proposal and asks the extent; the build reads no documented session (no
       done event) and asks nothing. The extent of a procedure not yet done is no genuine question (pinned).
    4. D124, a line shaped as a heading inside an entry ('Vital signs stable', no period) ends it, as c2e53f8e's
       GENERIC_HEADING does, so an act below it in a nursing note is not held (as at 1caaf0609).
    5. D124, a role named only in a sentence ('The nurse removed the polyp.') is no label and holds nothing. That is
       the performer's attribute, Gemini's to state.
    6. D124, support['acts'] is empty for the hold, as for every hold but conflict and bundled (assess._support), so
       the record shows the act through the question's passages and events only.
    7. A role-only act no code covers is listed not_covered; c2e53f8e's reconcile skips other roles' acts. Unchanged
       here: more items, never fewer.
    8. D124, a bare 'Anesthesia:' or 'Pathology:' heading line (the spec's labels, alone on their line; c2e53f8e's
       anesthesia and pathology headings need 'record', 'note', 'report', 'result' or 'addendum') opens an entry that a
       field line does not end: 'Anesthesia:' / 'Monitored anesthesia care by the anesthesia team.' / 'Procedure: The
       colonoscope was advanced to the cecum; a 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
       holds 45385 with the anesthesia-entry question. A hold, never a READY; c2e53f8e holds it too, for its own reading
       ("a passage it cites about this service reads as uncertain"). FRESH-1 and FRESH-2 have no such line.
    9. Pre-existing differences seen on the pins' inputs, not D124's or D125's: on the push enteroscopy c2e53f8e holds
       43239 [extent] only and the build [performed_status, extent]; U07 and the 'Recovery instructions ...' line
       above.

- **D127 The ERCP rules read what their review found them missing (2026-11-11; the review of D104-D107, ercp problems
  0-4; the family parity audit's ERCP notes 1 and 2; amends D105, D106 and D107; repair key ercp2).** Five defects of
  the round-4 ERCP rules, each measured against c2e53f8e (jobs._assess_child, as the head-to-head assesses) on the
  pins' own texts and citations, with no participant and with Astra and Fable read and proposing nothing:
  - problem 0: finding 25's document with a period where the semicolon was ("The bile duct was swept several times
    with an extraction balloon. No stones or sludge were retrieved.", one passage) made 43264 READY, Corti citing both
    sentences or the first (c2e53f8e: EXCLUDED, act_denied, and HELD performed_status). So did the denial on its own
    line, as a passage of Gemini's no attribute of the sweep cites, or as no passage at all with Corti citing both
    lines (c2e53f8e: HELD). D106's builder's disagreement 1 (the parity audit's note 2) left three more READY: "...;
    nothing was retrieved." (no stone word; c2e53f8e HELD, act_missing), "...with a balloon; no stones were found." (no
    retrieval word; c2e53f8e HELD on the builder's document - a family-level doubt that also held its control "two
    small stones were retrieved" - and READY on a clean one), and Gemini's passage only the sentence's first clause
    with Corti citing the sentence (c2e53f8e EXCLUDED).
  - problem 1: an exchange Gemini files as stent_exchange (the Procedure line's kind words, the placement's status and
    target) beside the stent_removal it includes made 43275 and 43276 both READY; the mirror (stent_exchange on the
    removal's sentence, beside a stent placement) made 43274 and 43276 both READY. c2e53f8e holds 43275 and 43276
    act_missing and READYs 43274.
  - problem 2: the review's surviving mutant - read every sentence of the act's passages - passed all 16 D104-D107
    pins.
  - problem 3 (a cost D106 introduced): a complete clearance worded with "no stones" was held nothing_retrieved -
    "Multiple stones were extracted from the bile duct with an extraction balloon until no stones remained.", "...and
    several small stones were removed; no stones remained on the final cholangiogram." (c2e53f8e READY on both).
  - problem 4: D107's warn quoted the failure-marker words alone ("were unsuccessful"); c2e53f8e quotes the statement
    of the failure.
  - parity note 1: a cannulation stated achieved and one begun and not completed ("Deep biliary cannulation was achieved
    with a sphincterotome." / "Initial attempts at biliary cannulation were unsuccessful.") made 43260 READY, with
    D107's warn and 52/53; c2e53f8e holds it [cannulation] (detect._cannulation: "both documented is a conflict for a
    reviewer, never a pick"), with the warn and 52/53.
  - The rules (studio/interpretation/ercp.py; one arm of assess._inventory_fact).
    - (0) D106 reads an act's STATEMENT: each own sentence (D106's: a sentence of its own located passages that holds
      one of its kind, status or target words, or a passage none of whose sentences does, read whole), the sentences of
      the code's own exact evidence (the kept spans, already verified exact) that overlap one of its own passages and
      hold one of its words (Gemini's passage may be a clause of the sentence), and - when the own sentence states no
      yield - the sentence that immediately follows it: one that begins within CONTINUES_WITHIN (2) characters of the
      own sentence's end, in the same passage, in a located passage or in a kept span, and holds no other event's own
      words ("names no other act"). The following sentence is read for a denial only. A negator that is itself what was
      retrieved ('nothing', 'none'; not exceptive: "nothing else" is) denies beside a retrieval word in its own clause;
      'find', 'finds' and 'found' join the retrieval words as the context a negation over stones needs. ruled now
      passes the code's kept spans to retrieval_hold, so overlay.counted_codes (which re-evaluates from the stored exact
      evidence) reads the same.
    - (2) Only those: another act's sentence in the act's own passage, before or after the act's own, is never read; a
      following sentence that holds another event's words does not continue the act.
    - (3) A denial is of a RETRIEVAL when its clause holds a retrieval word after the negator, or the two words before it
      hold one ("no stones or sludge were retrieved", "retrieved no stones", "without retrieval of any stones", "nothing
      was retrieved"), else of the stones' PRESENCE ("no stones remained", "no stones were seen", "no stones were
      found"). A sentence states the act's YIELD when a clause of it that holds the act's own words and no other event's
      holds a stone word no negator governs and a past-form yield verb (retrieved, extracted, removed, delivered,
      recovered, yielded) no negator precedes and that does not follow "to" or "be". A presence denial in a sentence
      that states the act's yield is a clearance: it denies nothing. A retrieval denial in the act's own sentence holds
      whatever the sentence states beside it, as before. Unless the presence denial sits in a clause that holds another
      event's words: a sentence of two acts is D106's own sentence read whole, and keeps its hold. An own sentence that
      states the yield is the act's own word on it, so the sentence after it is not read.
    - (1) exchange_pairs pairs, after D105's (removal, placement), every positive stent removal with a positive stent
      exchange, and every exchange with a positive stent placement, ducts read as D105 reads them (both verified and
      different keep them apart). A READY 43275 whose removal is a side, a READY 43274 whose placement is a side, and
      43276 (D105's literal choice, READY or not documented) are held with one question: "Was the stent removal (snare)
      at the bile duct (“was removed with a snare”) part of the stent exchange at the common bile duct (“was placed”),
      one stent exchange (43276), or a separate stent removal (43275)?" (the placement's form names 43274). A session
      with all three events keeps D105's question, its pair first. Reason possible_exchange, as D105.
    - (4) access_not_completed returns the sentence of the access act's own passages that holds its verified
      failure-marker words (statement_sentence), the words themselves where no own sentence holds them.
    - (5) cannulation_conflict: an ERCP cannulation with status value performed and one attempted_not_completed, each in
      any verification state (D87: a doubted outcome is a question), possibly current (D62) and not verified as another
      performer's, of ducts nothing sets apart (D45's reading: D107's pancreatic avoidance is no conflict). The
      cannulation arm of assess._inventory_fact makes it Fact('cannulation', None, 'conflict', the two statements,
      'Conflicting documented values: bile duct cannulated, bile duct not achieved.'), so every ERCP code (the profile
      requires the cannulation) asks "ERCP: confirm whether, and which, duct was cannulated." with the reason "The
      document gives conflicting values for the cannulation outcome: “Deep biliary cannulation was achieved with a
      sphincterotome.”, “Initial attempts at biliary cannulation were unsuccessful.”." - c2e53f8e's question and its
      facts.required wording ("Conflicting values documented: cannulation outcome."); an excluded code waits for it.
      D107's signals are unchanged.
  - What the inputs give now (each pinned): every problem-0 shape, the five disagreement-1 wordings and their
    two-sentence variants hold 43264 nothing_retrieved, the question quoting the statement; the exchange filed with its
    removal holds 43275 and 43276, the mirror holds 43274 and 43276; the review's two clearances, "no stones were seen on
    the final cholangiogram" after a stated removal, and "Two stones were extracted ... No stones remained." across a
    period are READY on the extraction; D107 quotes "Multiple attempts at biliary cannulation were unsuccessful."; the
    parity note's two documents hold 43260 [cannulation] (with 43262 too: base_included and cannulation, cannulation),
    with the warn and 52/53.
  - The one release, and where it stops. The clearance turns held codes READY only where the act's own clause states its
    yield and a denial of the stones' presence follows: on every probe that release lands c2e53f8e READYs the code too
    (the review's two inputs and the cholangiogram one). Kept held, each pinned: a stated extraction beside a denied
    retrieval ("A stone was extracted with a basket and the duct was then swept ...; no stones were retrieved.":
    c2e53f8e conflict:stone_extraction); "until no stones remained" with no yield; "no stones were seen" with no yield
    (c2e53f8e READY: as 1caaf0609); "no stones were retrieved and none remained" (EXCLUDED there); an intent ("were to
    be extracted"); a yield in a clause none of the act's words are in ("Stones were extracted at the index ERCP in
    2024; today the duct was swept ... and no stones were seen."); a retrieval denied four words after the stones; two
    acts in one sentence, the basket's yield beside the sweep's denial (c2e53f8e conflict:stone_extraction) or in a
    clause both share (c2e53f8e READY) - fail-closed false holds of the right code; and D106's recorded cost "...; no
    stones were seen; sludge was retrieved." (c2e53f8e READY), whose yield's clause holds none of the sweep's words.
  - Built where the spec is not literal (disagreements, recorded):
    - (4) "matches the installed release's wording on problem 4's input" cannot be met on finding 26's own text.
      c2e53f8e quotes “The procedure was terminated” (cue “incomplete: The procedure was terminated”, documented
      service); on the refuter's reading those words are the first clause of the denials' passage and the words of no
      attribute. Quoting them would read passage words of no attribute through a "terminated" word list (EB1, EB4).
      Built: the failure's own sentence, which is exactly the words c2e53f8e quotes on the variant without "The
      procedure was terminated;", and on every other failed-cannulation probe (4 of 4); the "(cue …, documented
      service)" provenance is the legacy reader's and is not copied. When Gemini gives the examination the terminated
      words (status or completion), D61 and D71 quote them first, as before. Input left: finding 26's text, 43260
      READY with “Multiple attempts at biliary cannulation were unsuccessful.” where c2e53f8e has “The procedure was
      terminated”.
    - (4) R-4 words the warn "from the event's verified failure-marker words"; the sentence that holds them is quoted,
      not the words alone. For the owner.
    - (0) EB1 ("a check never scans the rest of a passage, a neighbouring sentence ...") is departed from further than
      D106 did: the rule now reads the next sentence and the proposer's exact evidence. It only holds, never READYs
      or excludes; the clearance it gained reads only the act's own sentence. For the owner, with D106's own note.
    - (0) "no stones were found" (disagreement 1(b)) is built as specified although c2e53f8e READYs it on a clean
      document; holding it adds a hold only.
    - (1) D105's literal choice is extended to the new pairs: 43276 READY on its own stent_exchange beside the removal it
      includes is held - a false hold of the right code; the other reading would leave 43276 READY beside a held
      rival.
  - Recorded, not built (the spec names none of these; each a READY or a missing signal, never introduced):
    - the denial in no passage and no evidence (Gemini's passage the first clause and Corti citing it; the next line no
      passage and Corti citing the first): READY, c2e53f8e HELD - nothing in the inventory holds the words (EB4);
    - "...; stones and sludge were not retrieved." (a negator after the stone word): READY, c2e53f8e HELD
      (performed_status);
    - "...; the sweeps were negative for stones and sludge." and "...with a balloon; no stones were seen." (no retrieval
      or find word): READY, c2e53f8e READY too;
    - a following sentence that names an act Gemini filed no event for is read as the continuation ("The bile duct was
      swept with an extraction balloon. The pancreatic duct was then swept with a balloon; no stones were retrieved."
      with no event for the pancreatic sweep): HELD, c2e53f8e HELD (pinned as the cost);
    - a biliary cannulation that failed beside the PANCREATIC duct's achieved (two ducts set apart, no conflict): READY
      with D107's signals; c2e53f8e HELD [cannulation];
    - a failed cannulation whose failure words do not bind (status unverified): held [cannulation] by the conflict, but
      D107 (a usable status only) gives no warn and no 52/53, where c2e53f8e gives both;
    - finding 26's text plus "Deep biliary cannulation was then achieved with a precut sphincterotome.": HELD
      [cannulation] where c2e53f8e is READY (it reads "was then achieved" as no success); a hold only;
    - the exchange filed beside its placement holds 43274 where c2e53f8e READYs it - D105's recorded cost, in the new
      pair;
    - D105's removal filed as foreign_body still pairs with nothing (unchanged).
- **D127, what was edited.**
  - studio/interpretation/ercp.py: the module docstring; D105's exchange_pairs, exchange_question and exchange_hold's
    pair filter; D106's reader - FIND_WORDS, OBJECT_NEGATORS, YIELD_VERBS, NOT_NOTHING's "else", CONTINUES_WITHIN, and
    _clauses, _governed, _negated, _denial, _yields, states_nothing_retrieved, _trimmed, _own_words, _holds, _kept,
    nothing_retrieved (it takes the kept spans and returns the statement's places) and retrieval_hold (kept, and the
    statement quoted); ruled passes kept; D107's statement_sentence and access_not_completed; cannulation_conflict, new.
  - studio/interpretation/assess.py: _inventory_fact's cannulation arm only (a local import of ercp and the conflict's
    Fact before the first-cannulation loop, which is unchanged).
  - tests/test_interpretation_r5_ercp.py: NEW, 16 tests.
  - tests/test_interpretation_r4_ercp.py: four expectations changed, and the comments and one docstring that name them.
    D104-D107's original module, run on the new code, fails exactly these (7 subtests in 4 tests):
    - test_d106_the_negation_read_in_the_acts_own_sentence: the recorded-cost sentence read alone is now False (it
      states a yield); in the sweep's own reading the cost stands (pinned in r5);
    - test_d107_finding_26_a_failed_cannulation_gives_every_code_of_the_ercp_both_signals: the warn's words are the
      failure's sentence (FAILURE);
    - test_d107_controls_a_cannulation_achieved_or_of_another_occasion_gives_nothing: access_not_completed returns the
      sentence;
    - test_d107_the_defining_access_act_a_pancreatic_failure_beside_the_biliary_access_achieved: the 'biliary, before'
      shape is the conflict - held [cannulation], with both signals in the sentence's words; the pancreatic shape is
      unchanged.
- **Pins.** tests/test_interpretation_r5_ercp.py, 16 tests.
  - D127NextSentence: test_d127_problem_0_finding_25_with_a_period_the_next_sentence_continues_the_sweep (4 subtests);
    test_d127_problem_0_the_denial_on_its_own_line (6); test_d127_disagreement_1_the_wordings_the_installed_release_
    holds_or_excludes (10, and the sentence reader on 4 sentences).
  - D127OwnSentence: test_d127_problem_2_another_acts_sentence_in_the_acts_own_passage_is_never_read (2: the other act
    filed, and not filed beside a basket extraction); test_d127_problem_2_the_next_sentence_names_another_act_and_does_
    not_continue (and its recorded cost).
  - D127Clearance: test_d127_problem_3_a_complete_clearance_supports_43264 (6, across a period, and 3 sentences);
    test_d127_problem_3_controls_a_denied_retrieval_or_no_yield_still_holds (8, 2 sentences, 2 two-act sentences).
  - D127ExchangeFiled: the exchange beside its removal (6) and beside its placement (6), with each code alone;
    a held code keeps its question and three events keep D105's; the controls (the exchange alone, a pancreatic
    removal, a removal denied, a removal at an earlier ERCP).
  - D127IncompleteWording: test_d127_problem_4_the_warn_quotes_the_sentence_that_states_the_failure (4).
  - D127CannulationConflict: the parity note's first document (2, and with 43262), its second (finding 26 with the
    access achieved, the excluded codes' waits), ducts nothing sets apart and a doubted failure (3), the controls (4:
    the pancreatic failure, an earlier ERCP, two achieved, the biliary failure beside the pancreatic access).
  - Every pin's input was run through c2e53f8e (74 assessments); the outcomes are quoted in each docstring.
  - On 1caaf0609's code the module gives 40 failures and 13 errors (the new functions and nothing_retrieved's new
    return) across 15 of its 16 tests; the exchange controls pass there, as a control should.
- **Mutation proof.** One copy of the final work tree, each of 24 mutants applied in turn (the anchor asserted to occur
  once, "mutation applied" and the sha256 change printed), run over the r5 and r4 ERCP modules, then restored and its
  sha256 checked equal to the work tree's; the copy equals the work tree after the run. Every mutant fails at least one
  pin, by assertion, with 0 errors (failing tests in the r5 and r4 modules):
  - m01 the following sentence never read: 4 (problem 0's two, disagreement 1, problem 2's cost);
  - m02 the evidence never extends the own sentence: 1 (disagreement 1(c)); m03 the continuation never from the
    evidence: 1 (the line that is no passage); m20 ruled passes no kept spans: 2;
  - m04 "nothing" no denial: 2; m05 no find words: 1;
  - m06 every sentence of the act's passages read (the review's surviving mutant): 2; m07 a following sentence of
    another act continues: 1;
  - m08 no clearance: 2 (r5's clearances and r4's recorded-cost sentence); m09 a yield releases a denied retrieval: 1;
    m10 "were to be extracted" a yield: 1; m11 "were not removed" a yield: 1; m12 another event's clause the act's
    yield: 1; m21 a clause without the act's words the act's yield: 1; m22 the retrieval word read only three words
    past the stones: 1; m23 a two-act sentence released: 1;
  - m13 no exchange-event pairs: 3; m24 ducts verified apart still pair: 2 (the r5 exchange controls and D105's own);
  - m14 the bare failure-marker words: 6 (r4's three changed D107 pins, r5's wording and two conflict pins);
  - m15 no conflict: 4; m16 ducts never apart: 2; m17 any time: 1; m18 verified statuses only: 1; m19 the assess call
    site removed: 4.
- **Tests.** t.sh on port 55461, a new suffix every run.
  - tests.test_interpretation_* (46 modules, the new one included), test_pipeline_assess_events, test_readers_dispatch,
    test_guard_static, test_guard_mutation and test_overlay_differential: 1321 OK. 1caaf0609, the same modules without
    the new one: 1305 OK. So 1321 = 1305 + 16.
  - The 49 other modules that import the new path (the round-4 builder's 45 and four more, test_guard_matrix_new_path,
    test_guard_matrix_legacy and the pipeline and repairs modules among them): 1070 OK, 3 skipped; 1caaf0609 the same,
    1070 OK, 3 skipped.
  - Replay pins: the committed answers (tests/fixtures/interpretation, 161 read as test_interpretation_replay reads
    them) hold 24 ERCP stone_extraction events and 3 ERCP cannulations, all performed, and no stent kind - more than
    the round-4 entry's "none of these kinds" suggests. Read through the new rules, as through 1caaf0609's: 0 retrieve
    nothing, 0 pairs, 0 access acts begun and not completed, 0 conflicts. The replay modules pin the reading's
    structure, never a code, and pass unchanged; no fixture was regenerated.
- **Measurement.**
  - FRESH-2 re-scored as fresh2-score/f2r5b-ercp2: A 96/6, B 177/15, C 171/19 plus 2 safe_hold, as f2r5int. rows.jsonl
    is byte-identical to f2r5int's (0 of 486 rows), and 0 of 179 assessments and 0 of 179 inventories differ.
  - Head-to-head (h2h.json): JSON-equal to h2h-r5int.json. Run 1 214/234 (A 34/34, B 59/64, C 121/136), worse 5,
    better 69, unstable 7, facts moved 0. No new false_ready, false_exclusion, dropped_question or ready_wrong_facts.
  - Census of the stored inventories (FRESH-2 f2r5int and FRESH-1 f1final, 358), the new reader without evidence spans:
    48 ERCP stone_extraction events, none read as retrieving nothing; 0 stent removal, placement or exchange events, so
    0 pairs; 6 cannulations, all performed, so 0 access acts begun and not completed and 0 conflicts. That is why no
    corpus row moves.
  - Probes (synthetic, 71 cases, each with and without the participants, on 1caaf0609, the work tree and c2e53f8e): 70
    rows change. Every change is READY to held, a question added, or the warn's quoted words - but for the clearance's
    6 rows (3 inputs, each in both settings), which go from held to READY and so lose D106's nothing_retrieved
    question, c2e53f8e READY on each. No exclusion; no other question dropped.

- **D128 A current time no date has checked yet pairs as current beside a denial only on the denial's own side, and
  never sets a pair apart (2026-11-11; the review of D99, currency-pairing problems 0, 1 and 2; narrows D99; repair key
  currency2).** D99 read a "pending check" - a current_encounter time whose ONLY failure is date_unchecked (D67(a): a
  day literal no service date could check yet), unopened - as current on both sides of relations.time_row. The pairing
  is made once, at normalize, before any date can decide the day; assess re-judges the times (D67(b)) but reuses the
  stored relations (D67's residual). So the relation D99 stored was right for the one date that equals the pending day,
  and could be wrong for every other.
  - Problem 0 (CONFIRMED by the review). The undated note 'The colonoscope was advanced to the cecum.' / 'On 06/02/2025,
    a 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.' (E2, current_encounter worded 'On
    06/02/2025') / 'Impression: No polypectomy was performed.' (E3: removal, not_performed, all_of_kind), and the
    member's 2026-11-09. Each run first-hand on byte-identical texts (the installed release with a 'PROCEDURE:
    Colonoscopy' header so that its routing finds the colonoscopy; jobs._assess_child as h2h/run_registry.py builds
    it):
    - 1caaf0609: stored contradiction(status, same_act); 45385 asks [conflict:snare], conflicts warn, completeness '1
      conflict in the record' - the snare is another day's. The same on 'On 11/09/2026' with the member's 2026-11-10 or
      2026-11-08, on 'several' dates ('Date of service: 11/08/2026 or 11/09/2026.') settled on 2026-11-08, and with no
      date at all.
    - Installed c2e53f8e: [performed_status], conflicts pass, on each (bare: [extent, performed_status]); with the
      member's EQUAL date (11/09 and 2026-11-09): [conflict:snare], warn.
    - 437b708bb: [event_time] on each.
  - Problem 1 (PLAUSIBLE, constructed). The same dated snare beside 'As previously noted, no polypectomy was performed.'
    (E3: earlier_encounter worded 'As previously noted', verified only by the C1 marker 'previously'). 1caaf0609 stores
    independent(time, another_time) and makes 45385 READY with the member's 2026-11-09; installed asks [conflict:snare]
    (warn). Beside round 4's 'Previously, no polyp was removed.': 1caaf0609 READY; installed READY with 2026-11-09 and
    EXCLUDED (historical) with 2026-11-10. 437b708bb held both (event_time).
  - Problem 2. The examination Counter in relations.Context.__init__ (the pairing's unresolved sessions) never read
    D99 (round 4's deliberate deviation); the spec asks to apply it there consistently or record why not.
  - The rule (time_row). Two usable times pair as before. A pending check pairs as the SAME time against a current time
    or another pending check, except:
    - beside a DENIAL (status not_performed), only the denial's own pending check pairs, and only against an act whose
      time is verified current. The ACT's pending check beside a denial is UNKNOWN (time_unresolved), as before D99,
      and so are two pending checks. The act's time is its own code's question until a date decides it: with the
      member's date equal to its day the re-judged time is usable, so the denial's UNRESOLVED(time) relation asks the
      contradiction as the statement's scope (D102), quoting the impression whole (D103): "Does “Impression: No
      polypectomy was performed.” apply to the snare removal (cold snare) of the 6 mm sessile polyp in the sigmoid
      colon (“was removed with a cold snare”)?"; with another date or none it asks the act's time (event_time);
    - a pending check is never DIFFERENT, beside any statement: against a usable earlier or future time it is UNKNOWN
      (problem 1: a day no date has checked is no literal, C-11, and no fact).
    The denial's own pending check stays paired because the act's time is then verified, so no question of its code is
    displaced, and the installed release asks [conflict:snare] (warn) on that text - 'A 6 mm sessile polyp ... removed
    with a cold snare.' beside 'On 11/09/2026, no polypectomy was performed.' - with no date, 2026-11-09 and 2026-11-10,
    and on the document dated 11/10/2026. Beside a doubt (uncertain), a planned act a claim names, and the other act of
    a claim between two acts, D99's reading stands unchanged (below). The act's own code reads its time through
    verify.usable (supports, h4), unchanged.
  - Why a doubt keeps D99 (built after a measured failure of this repair's first build, recorded). The first build
    applied the act-side rule to EVERY statement (mutant M3 below). A DOUBT relation keeps every code of its kinds from
    an exclusion (events._doubted, FINAL 7.5 (4): a DOUBT from a statement covering the code's kinds), and the first
    build turned it into UNRESOLVED(time). The input, recorded by an earlier, interrupted build of this same repair
    (scratchpad repair5/currency2) and run first-hand here:
    - 'EGD: the gastroscope was advanced to the duodenum.' / 'EGD: On 11/09/2026, a 5 mm polyp in the gastric body was
      removed with a cold snare.' (a pending check) / 'EGD: It is unclear whether the gastric body polyp was removed.'
      (removal, uncertain) / 'Colonoscopy: The colonoscope was advanced to the cecum.' / 'Colonoscopy: No polyp was
      removed.' (all_of_kind), which 45385 cites; Corti also proposes 43251;
    - 1caaf0609 and this repair: doubt(status, in_doubt); 45385 held [performed_status] with no date, 2026-11-09 and
      2026-11-10, and on the document dated 11/09/2026; 43251 held [performed_status, extent];
    - the first build: 45385 EXCLUDED with every date on the undated note (the dated document held it) - a held code
      excluded, which no repair here may do;
    - installed: 45385 EXCLUDED on every one of these texts, 43251 READY with 2026-11-09 - FINAL 7.5 (4)'s own
      difference from it, which this repair does not reopen.
    For a claim between two acts the narrowing would only have changed the question ([performed_status] to
    [event_time], stale with the member's equal date); it is not built there either.
  - (2), recorded with pins rather than built: the Counter is unchanged. D128 keeps D99's reading only where it can only
    hold, and counting a pending examination can release: it makes every all_of_kind pair of the family
    session_unresolved before any date (the pairing's unresolved sessions count VERIFIED current examinations, D87).
    Two measured reasons, each mutation-proved by M5 (D99 carried into the Counter):
    - a contradiction's question: the undated note's 'On 11/09/2026, the colonoscope was reinserted to the cecum.' (E4,
      an examination Gemini calls current) beside the snare and the impression's denial. Not counted, the pair is the
      contradiction and 45385 asks [conflict:snare, extent] with no date, 2026-11-09 and 2026-11-10; installed asks
      [conflict:snare] (warn) on all three, and the document's own 11/10/2026 asks the contradiction. Counted: the denial
      is asked as its scope with every date, the second colonoscope another day's or not;
    - a doubt's exclusion guard: an EGD with 'EGD: On 11/09/2026, the gastroscope was reinserted to the duodenum.', a
      snare and the all_of_kind doubt 'EGD: It is unclear whether any polyp was removed.', beside the colonoscopy's
      'No polyp was removed.' that 45385 cites. Not counted: DOUBT, and 45385 held [performed_status] with every date,
      as with the document's own 11/10/2026. Counted: session_unresolved, the guard goes, and 45385 is EXCLUDED with
      every date, 2026-11-10 included. Installed excludes 45385 on all of these texts.
    The Counter's comment records it; its code is unchanged.
  - Built where the spec is not literal (recorded). The spec's example - "a date_unchecked time pairs as
    UNRESOLVED(time) when the denial is itself undated, and as CONTRADICTION only when the other side's time is
    verified current" - is built as two sides of a denial: the first clause is the ACT's pending check (beside a denial
    with no date of its own), the second the DENIAL's. Read with both clauses on the act's side, it contradicts itself
    on problem 0's own input: 'Impression: No polypectomy was performed.' has no date (clause 1: UNRESOLVED) and its
    default time is verified current (clause 2: CONTRADICTION). No fix inside time_row can ask [conflict:snare] with the
    member's equal date and [event_time] with another, because the stored relation is one for every date: built
    UNRESOLVED(time), which asks statement_scope with the equal date; the scoring adjudication of 2026-11-10
    (score_fresh.verdict, h2h/compare.py EQUIVALENT) reads statement_scope as asking an expectation's conflict:<kind> or
    performed_status. And the example names denials only: beside a doubt the narrowing is not built (above).
  - Cost, on constructed inputs (nothing in FRESH-1 or FRESH-2 reaches it; census below). Held in every case, never
    READY, never excluded:
    - finding 8's own input with the member's equal date (round 4's D99 pins, moved below): 45385 asks [statement_scope]
      where D99 asked [conflict:snare]; the conflicts check is pass instead of warn and completeness drops '1 conflict
      in the record'. Installed: [conflict:snare] (warn). The document's own 11/09/2026 still asks [conflict:snare];
    - 'Previously, no polyp was removed.' with the member's 2026-11-09: held [statement_scope] where installed is READY
      (437b708bb held it, event_time). The hold direction;
    - two pending checks beside a denial ('On 11/09/2026' on the snare and on the denial): [event_time] with no date and
      with 2026-11-10, [statement_scope] with 2026-11-09, where D99 asked [conflict:snare] (warn) with every date.
      Installed: [performed_status], [performed_status], [conflict:snare] (warn);
    - a pending denial beside an act Gemini dates earlier ('Previously, a 6 mm sessile polyp ... removed with a cold
      snare.'): stored independent(time) -> unresolved(time); 45385 asks [statement_scope] either way (the exclusion
      arm, 7.5); installed [performed_status].
  - Measured (host_score.sh on the final work copy; nothing sent): see "D128, the measurement" below.
  - Pins (tests/test_interpretation_r5_currency.py, NEW, 20 tests; synthetic, nothing sent):
    - D128TimeRow: test_d128_a_statements_pending_check_pairs_against_a_verified_current_act (9 subtests);
      test_d128_beside_a_denial_an_acts_pending_check_never_pairs_and_no_pending_check_sets_a_pair_apart (11);
      test_d128_beside_a_doubt_a_planned_act_or_a_claim_d99_stands (12); test_d128_control_every_other_unverified_
      statement_time_stays_unknown (D99's control with a denial's and a doubt's status on either side, 18);
      test_d128_control_two_usable_times_pair_as_before.
    - D128MemberDates (problem 0's inputs): test_d128_another_day_asks_the_acts_time_and_never_a_conflict (the review's
      06/02/2025 with 2026-11-09; 11/09 with 2026-11-10 and 2026-11-08; 'several' settled on 2026-11-08);
      test_d128_with_no_date_the_act_is_asked_its_time; test_d128_the_members_equal_date_asks_the_contradiction_as_the_
      statements_scope (round 4's five undated variants); test_d128_control_the_documents_own_date_decides_at_normalize.
    - D128EarlierDenial (problem 1's input): test_d128_an_earlier_denial_verified_by_its_marker_never_sets_the_pending_
      act_apart ('As previously noted' and 'Previously', three dates each);
      test_d128_control_the_documents_own_date_still_sets_it_apart.
    - D128StatementSide: test_d128_a_statements_pending_check_beside_a_verified_current_act_is_the_contradiction (three
      dates); test_d128_two_pending_checks_never_pair; test_d128_a_pending_denial_never_sets_an_earlier_act_apart.
    - D128PositiveClaim: test_d128_a_claim_between_two_acts_keeps_d99s_reading (the claim on either event, three dates).
    - D128DoubtKept: test_d128_a_doubt_beside_a_pending_act_still_keeps_its_kinds_from_an_exclusion (the undated note,
      the doubt worded 'On 11/09/2026' too, the dated document).
    - D128Counter (problem 2): test_d128_a_pending_examination_is_no_second_examination_of_the_pairings_session;
      test_d128_control_the_documents_own_date_counts_a_verified_second_examination;
      test_d128_a_pending_examination_never_takes_a_doubts_exclusion_guard.
    - D128Chain.test_d128_both_member_dates_through_the_chain: the production chain, the legacy entry points failing if
      called - the member's 2026-11-10 at upload asks [event_time], 2026-11-09 saved afterwards (jobs.change_context)
      asks [statement_scope], the conflicts check pass on both.
  - Round 4's pins whose expectations D128 moves (tests/test_interpretation_r4_currency_pairing.py; a constant
    UNRESOLVED_TIME added):
    - D99TimeRow.test_d99_a_current_time_whose_only_failure_is_date_unchecked_pairs_as_current: (earlier, unchecked)
      DIFFERENT another_time -> UNKNOWN (its other three SAME rows read sides with no status, no denial, and stand);
    - D99UndatedDenial.test_d99_the_same_day_denial_is_a_contradiction_on_the_undated_note: stored contradiction ->
      unresolved(time);
    - D99UndatedDenial.test_d99_the_members_date_asks_the_contradiction: [conflict:snare], warn, '1 conflict in the
      record' -> [statement_scope], pass;
    - D99UndatedDenial.test_d99_an_earlier_denial_sets_the_act_apart_as_the_dated_document_does: on the undated note
      independent -> unresolved(time), and the member's equal date READY -> held [statement_scope]; the document's own
      date unchanged (READY);
    - D99Chain.test_d99_the_members_date_at_upload_and_saved_afterwards_asks_the_contradiction (its
      assert_contradiction_asked): contradiction, [conflict:snare], warn -> unresolved(time), [statement_scope], pass.
    The other 16 round-4 tests are unchanged.
  - Mutation proof: 8 mutants in one reusable copy (mut-1), each anchor asserted once, each application proved by its
    marker and a sha256 change, each restoration proved by sha256 before the next. Counts are failing tests and
    subtests over the r5 and r4 modules (41 tests); every one an assertion failure, none an error; every behaviour pin
    fails under at least one, and the four controls (the dated paths and two usable times) under none, as references:
    - M0, D128 undone (time_row as at 1caaf0609): 39;
    - M1, beside a denial the act's pending check pairs again: 27;
    - M2, a pending check set apart by a usable earlier or future time: 12;
    - M3, the denial arm applied to every statement (this repair's first build): 16 - D128DoubtKept (its DOUBT gone;
      45385 EXCLUDED with every date in the M3 probe log), the claim and doubt pins, and round 4's D99TimeRow SAME
      rows;
    - M4, beside a denial nothing pairs (the denial's own pending check no longer pairs): 4;
    - M5, D99 carried into the Counter: 4 (both D128Counter behaviour pins, and two subtests of round 4's aside
      control);
    - M6, a denial's pending check pairs against the act's pending check too: 3;
    - M7, a pending check is any date_unchecked time, opened or with other reasons: 9 (round 4's control now reaches
      the arm too: its sides have no status, no denial).
  - Recorded residuals:
    - The pairing is still made once, at normalize. With the member's equal date the denial's contradiction is asked as
      statement_scope and the conflicts check says pass (installed and the document-date twin: [conflict:snare], warn).
      The repair belongs in assess (assess.py reuses stored.relations): relate again over the re-judged reading.
    - A denial's own pending check stays a CONTRADICTION whatever the date: with the member's 2026-11-10 the denial
      'On 11/09/2026, ...' is another day's, and the conflicts check reports a conflict the document's own 11/10/2026
      would not (that twin asks statement_scope, pass). Installed asks [conflict:snare] (warn) on both. The code's own
      time is not in question; held.
    - Beside a doubt, a planned act a claim names and a claim's other act, D99's reading still decides before the date,
      as at 1caaf0609: the DOUBT or the claim's "no difference" stands when the member's date makes the act another
      day's (the code is held by it; the uncertain statement asks its own performed_status anyway).
    - The normalize-time and assess-time Counters can disagree: the assess-time Context (Reading.context) reads the
      re-judged times, so with the member's 2026-11-09 the pending second colonoscope IS counted at assess (coverage
      asks the extent; events.broad and D126's ranking read the session as unresolved) while the stored pairing read one
      examination. Held either way.
    - Outside D128, pre-existing (D87, unchanged): with the document's own 11/09/2026 the second gastroscope of the
      doubt-guard input is verified, the doubt's pair is session_unresolved, and 45385 is EXCLUDED by the colonoscopy's
      denial (as installed excludes it); the undated note and the document's own 11/10/2026 hold it.
    - Outside D128, pre-existing (the standard table's DIFFERENT, unchanged since 437b708bb): on the DATED twin,
      'As previously noted, no polypectomy was performed.' (earlier_encounter, verified by 'previously') sets the snare
      apart and 45385 is READY, where installed asks [conflict:snare] (warn). Not attested: none of the 74 earlier- or
      future-dated statements in FRESH-1 and FRESH-2 is worded with a discourse phrase (the round-4 review's census).
      A repair (a marker-only earlier or future time never setting a pair apart) is in time_row's reach but outside the
      spec, which names D99's direction only; it would only add holds.
    - Stale prose, outside this repair's ownership: the round-4 module's docstring still describes D99 unnarrowed (each
      moved test says D128 moved it), and relations' module docstring table never described D99 or D128.

- **D128, what was edited, the suites and the measurement.**
  - studio/interpretation/relations.py: time_row (its docstring and the D99 arm), and a comment in the examination
    Counter of Context.__init__ (its code unchanged). Nothing else in the module, its docstring included.
  - tests/test_interpretation_r5_currency.py: NEW, 20 tests.
  - tests/test_interpretation_r4_currency_pairing.py: the five expectations above, and the constant UNRESOLVED_TIME.
  - Suites (t.sh, Postgres 127.0.0.1:55461, a new suffix every run), 65 labels: the 46 tests.test_interpretation_*
    modules (the new one included), test_pipeline_assess_events, test_readers_dispatch, test_guard_static,
    test_guard_mutation, test_guard_matrix_legacy, test_guard_matrix_new_path, test_change_context_events,
    test_models_event_inventory, test_overlay_differential, test_peer_heading, test_pipeline_api,
    test_pipeline_interpret, test_repairs_7c8_p1reports, test_repairs_7c8_p1sends, test_repairs_ec5_reportruns,
    test_retry_reading_api, test_harness_pipeline, test_harness2_pipeline and test_services_second_review - every test
    module that imports studio.interpretation. 1caaf0609: 1697 OK, 3 skipped (the legacy guard matrix's three
    skipTest sites, its c2e53f8e baseline tree). The final work copy: 1717 OK, 3 skipped - the 1697 plus the 20 pins.
    Before the pins and the moved expectations (the first build), the only failures were the round-4 subtests whose
    expectations D128 moves. The replay pins (tests.test_interpretation_replay) pass; no fixture was regenerated.
    INVENTORY_VERSION is unchanged.
  - Measured on the final work copy (host_score.sh; nothing sent; the first build was measured too, with the same
    zeros):
    - FRESH-2 (f2r5b-currency2): A 96/6, B 177/15, C 171/19 plus 2 safe_hold, as f2r5int. Against f2r5int: 0 of 486
      rows, 0 of 179 runs and 0 of 358 per-recording files (assessments and inventories) differ.
    - The scorer reads the given tree. Positive control: a plant (every time row UNKNOWN) in a copy of the final tree,
      corpus A only (f2r5b-currency2-plantA, a control, not a measurement): 8 of 102 rows and 21 of 42 files differ.
    - The head-to-head (h2h/compare.py) is identical to h2h-r5int.json in all 7 keys: run 1 214/234 (A 34/34, B 59/64,
      C 121/136); installed 150/234 with 16 false_ready and 2 ready_wrong_facts; worse 5, better 69, unstable 7, facts
      moved 0. No new false_ready, false_exclusion, dropped_question or ready_wrong_facts.
    - FRESH-1 (f1r5b-currency2-pristine against f1r5b-currency2-work): 0 of 486 rows, 0 of 179 runs, 0 of 358 files;
      A 97/5, B 174/18, C 165/24 plus 1 false_ready and 2 safe_hold on both (that false_ready pre-exists).
    - Census of pending checks over the 358 frozen answers: FRESH-2 has 3 times carrying date_unchecked and none
      pending (each also carries current_unanchored and is opened by Gemini's question, all in aside-of-twins-019 r1,
      as D99 recorded); FRESH-1 has one pending time, a positive event in no relation (aside-of-twins-019 r1's EGD
      examination E1, '2026-09-30'). The corpora hold no member of the classes D128 changes: the cost is 0 rows
      because the classes are empty, which is why the constructed pins carry the proof.

- **D130 An act of kind 'other' filed under the visit whose own status words state it was performed is a possible
  same-day procedure; the routine pre-procedure visit's performed_status question is recorded, not repaired
  (2026-11-11; the round-4 em-same-day repair's parity notes (a) and (e), measured on 437b708bb; amends D109's residual
  "an act of kind 'other' filed under the visit makes no procedure day"; repair key em2).** Each input below was
  measured on byte-identical texts against c2e53f8e (studio.validation.engine.assess with gi_context.extract_context,
  merge_user_values and detect.route on 2026-11-09, as tests/test_harness_engine.py drives it), 1caaf0609 and the
  repair, Corti proposing 99213 citing the visit line, member values office and established unless it says otherwise.
  - **Note (a), the source.** The families review's office document (D94's CYST_TEXT: "Office visit: established
    patient seen today for rectal bleeding." / "Total time on the date of the encounter: 25 minutes." / "Excision of a
    1 cm sebaceous cyst on the upper back was performed in the office today." / "Plan: fiber; recheck in 6 weeks."),
    and finding 20's office lines (the same with "Anoscopy showed grade 2 internal hemorrhoids.", which no event reads).
    Gemini files the excision under the visit: E1 kind other "Excision of a 1 cm sebaceous cyst", status performed "was
    performed", procedure office_em by its own word "office" (or the visit line's "Office visit", or em_other with no
    words), the current encounter and the documenting team by the frame defaults.
    - c2e53f8e: 99213 held, separate_em, "Other GI service is documented as performed on the same date; a significant,
      separately identifiable E/M service is not established by this document." Its routing reads the excision as
      gi.other performed (detect's procedure-word routing).
    - 1caaf0609: READY, em.same_day_coverage not_verified. The act's family is gi.office_em, and no arm of
      combination.procedure_day read it: not D81's families, not D94's gi.unsupported or no family, and not D109's
      procedural kinds, since 'other' is none.
  - **The rule (combination.procedure_day and its module-level helpers).** A fourth arm, by STATEMENT: an act of kind
    'other' whose family is one the visit's procedure gives (VISIT_FAMILIES = the families of lexicon.EM_PROCEDURES:
    gi.office_em and gi.em_other) counts when combination._stated_procedure holds:
    - its status words hold a DONE_STATEMENTS phrase: "was performed", "were performed", "was done", "were done" or
      "underwent". These are read whole and word-bounded (lexicon.holds) in the status attribute's own words only (EB1);
    - and none of the NAMING_WORDS (the kind's and the target's words, which name the act) names a NOT_PROCEDURES class:
      - test: test, tests, testing, ECG, EKG, electrocardiogram;
      - order: order, orders, ordered;
      - interpretation: interpretation, interpretations, interpreted;
      - lab: lab, labs, laboratory, laboratories, bloodwork, blood work;
      - imaging: imaging, image, images, CT, MRI, MRCP, ultrasound, sonogram, sonography, x-ray, x-rays, xray,
        radiograph, radiographs, fluoroscopy, scan, scans;
      - counseling: counseling, counselling, counseled, counselled.

    Such an act counts only when facts.day_of places it ON the date of service (the spec's "placed on the date"). OFF
    and UNDATABLE are not counted and not listed. It passes the same status gate as every arm (positive or uncertain).
    It is labelled "Other GI service" (OTHER_GI's label, as the installed routing reads it) and is ONLY EVER POSSIBLE:
    "Other GI service is possibly performed on the same date (its performance is not established)". Its kind names no
    procedure, so the words alone never make it a fact (D87). The other three arms are untouched: by_statement is
    disjoint from them (VISIT_FAMILIES lie outside SAME_DAY_FAMILIES and CURRENT_ONLY_FAMILIES, and 'other' is no
    SAME_DAY_KIND). The rule only ever adds a possible label, so it can make nothing READY that was held.
  - **Built where the spec is not literal (recorded, each pinned and mutation-proved):**
    - The plural "were performed" and "were done" are read as the spec's own phrases in the plural (mutant M12). Input:
      "Excisions of two sebaceous cysts on the upper back were performed in the office today." With the spec's three
      phrases only, 99213 is READY; c2e53f8e holds it.
    - "Performed" is read as procedure_day's shared status gate (positive or uncertain; D62 and D75: a doubt is never an
      absence). An uncertain excision with "was performed" is possible, as c2e53f8e holds the same text (mutant M13).
    - "Names a test ..." is read in the words that name the act, the kind's and the target's, never the status words.
      Those state its status, and a status-word read is a second use of an attribute's words that EB1 does not give.
      Input: "Excision of a 1 cm sebaceous cyst on the upper back was performed in order to relieve pain today.",
      status words "was performed in order to relieve pain". Reading the status words too, its "order" excluded the
      act and 99213 was READY; c2e53f8e holds it. Now it is held (mutant M14).
    - The class words are my closed lists: the spec names the classes, not their words. A test, lab or imaging study
      named by another word ("FIT", "FibroScan", "hydrogen breath study") is counted as possible. That is a hold, the
      safe direction.
    - No negator is read in the status words. "was performed without complication" holds lexicon's negator "without",
      and reading negators would lift that hold. Cost: an answer off the contract (status performed with the words "No
      excision was performed") is held where c2e53f8e is READY.
  - **What the inputs give now** (c2e53f8e / 1caaf0609 / the repair):
    - Note (a)'s input, both documents, every filing (office words, visit words, em_other, a verified "today"): held
      separate_em / READY / held separate_em. With no member values: separate_em / setting, patient_status / setting,
      patient_status, separate_em.
    - "was done", "underwent", "were performed", "was performed without complication", "was performed in order to
      relieve pain", "Earlier today, excision ..." and "Earlier in the day, excision ..." (earlier_encounter, ON):
      held / READY / held, each separate_em. So is "Excision of a labial cyst was performed ..." (word-bounded: a labial
      cyst is no lab).
    - Never counted, READY on all three: "A 12-lead ECG was performed in clinic today."; "A hydrogen breath test was
      performed ..."; "An order for a colonoscopy was done today."; "Interpretation of the outside CT images was
      performed today."; "Labs were done ..."; "An abdominal ultrasound was performed ..."; "A CT of the abdomen was
      done today."; "Counseling on a high-fiber diet was done today."; "Moderate sedation was performed today." (kind
      moderate_sedation: no statement arm); the excision "in 2024" (OFF); the excision planned "at the next visit";
      D109's control "Counseling was provided.".
  - **Effects besides.**
    - With no E/M proposed, the visit's "has no supported proposal" item moves to not_listed: "office / outpatient visit
      beside a procedure done or possibly done the same day". This is coverage.reconcile's rule for every procedure day,
      and c2e53f8e lists no visit item beside the excision. The encounter stays incomplete. For the same reason, a
      second review's E/M code finds no marked visit item to be added through (assess._second_review reads the same
      reconcile), as on every procedure day; no input here has a second review.
    - Beside an act C-3 cannot date, 99213 asks separate_em, no longer that act's event_time. This is assess's existing
      order: a procedure day asks separate_em, and only without one does an undatable act ask event_time. Input: note
      (a)'s document plus P4 "Rubber band ligation of one internal hemorrhoid was performed." (band_ligation filed
      office_em, time 'unknown'). The three engines give separate_em / event_time / separate_em. The same order already
      holds at 1caaf0609 for every possible label: D111's banding of no family "today" beside that undatable banding
      asks separate_em there. The banding stays listed undatable. Without the excision it still asks event_time
      (c2e53f8e: separate_em).
    - A procedure day closes assess's reinstatement gate (gate = reinstatable and visits and not procedure_day): an E/M
      beside an excluded procedural code asks separate_em directly instead of carrying same_day_if_reinstated. This is
      generic to procedure_day; no input here has an excluded procedural code.
  - **Note (e), RECORDED, NOT REPAIRED (outside this repair's ownership).**
    - Input: "Date of service: 11/09/2026." / "Procedure: Colonoscopy" / "The colonoscope was advanced to the cecum and
      the examination was completed." / "History and physical: routine pre-procedure assessment; no separate E/M service
      was provided.". Corti proposes 45378 (citing "The colonoscope was advanced to the cecum") and 99213 (citing the
      history and physical line).
    - c2e53f8e: 99213 held with performed_status, em_basis and separate_em in every reading. services.EM_ROUTINE negates
      the documented visit.
    - 1caaf0609 and the repair, by Gemini's reading:
      - the visit performed (em_visit "pre-procedure assessment", status words "routine pre-procedure assessment"):
        em_basis, separate_em;
      - the visit not performed ("no separate E/M service was provided"): statement_scope, em_basis, separate_em;
      - no visit event: performed_status, em_basis, separate_em.

      99213 is held and 45378 is READY in every case.
    - Why not here: the question is the visit code's own. It belongs to its supporting em_visit event (events.evaluate)
      and to assess's fact questions. procedure_day returns only the date-of-service lists (labels, possible,
      undatable), which assess turns into separate_em or event_time, so nothing it returns can carry a performed_status
      question for 99213. It belongs in events.evaluate or assess, reading the visit event's own status words, or in the
      prompt. The pin holds the three readings as they are, so the residual stays visible.
  - **Cost measured.**
    - FRESH-2, re-scored on the final work copy (fresh2-score/f2r5b-em2): A 96/6, B 177/15, C 171/19 plus 2 safe_hold,
      equal to f2r5int. Row by row, 0 of 486 rows, 0 of 179 runs (runs.jsonl byte-identical) and 0 of 358 assessment
      and inventory files differ. The summary JSON is byte-identical.
    - FRESH-1, on the repair (fresh-score/f1r5b-em2) and on 1caaf0609 (f1r5b-em2-base): A 97/5, B 174/18, C 165/24 plus
      1 false_ready and 2 safe_hold on both. The false_ready is 1caaf0609's own. 0 of 486 rows, 0 runs and 0 of 358
      files differ.
    - Head-to-head (repair5b/em2/h2h.json): byte-identical to h2h-r5int.json in all 7 sections. Run 1 is 214/234 (A
      34/34, B 59/64, C 121/136) against the installed engine's 150/234. It is worse on the same 5 rows, all holds:
      fb03 45385, fb12 43242, p20-xexcl-003 45388 (safe_hold), guard-bolus-005 43247 and PAIR-5-W3 45385. Better: 69.
    - No new false_ready, false_exclusion, dropped_question or ready_wrong_facts: not a STOP. No replay test fails,
      and no fixture was regenerated.
    - Census: the rule has no member in any recording.
      - 358 stored FRESH-1 and FRESH-2 inventories, read by both trees: procedure_day differs on 0.
      - Acts filed under the visit families: gi.office_em on em_visit only (14 in each corpus).
      - Kind 'other' acts (FRESH-2 / FRESH-1): gi.unsupported 23/25, gi.other 18/5, gi.colonoscopy 6/4, gi.sedation 2/2
        (monitored anesthesia care: filed as sedation, and no done statement in their status words), and no family
        0/2. None is filed under the visit.
      - 976 distinct recorded events in fresh-frozen, fresh2-frozen and tests/fixtures/interpretation: under the visit,
        office_em on em_visit only (12); 0 of kind 'other'.
  - **Pins.** tests/test_interpretation_r5_em2.py (NEW), 16 tests:
    - D130KindOtherFiledUnderTheVisit:
      - test_d130_note_a_the_office_excision_filed_under_the_visit_asks_separate_em (both documents; no member values);
      - test_d130_however_gemini_files_it_under_the_visit (3);
      - test_d130_its_own_status_words_state_it_performed_on_the_date (7);
      - test_d130_it_is_only_ever_possible (2);
      - test_d130_with_no_e_m_proposed_the_visit_item_is_not_pushed;
      - test_d130_beside_an_undatable_act_the_e_m_asks_separate_em.
    - D130WhatTheStatementNeverCounts:
      - test_d130_a_test_an_order_an_interpretation_a_lab_imaging_or_counseling_never_counts (9, control);
      - test_d130_words_that_cannot_tell_are_not_counted (4, control, and the recorded cost);
      - test_d130_only_on_the_date_of_service (3, control, and the residual);
      - test_d130_only_under_the_visit (control, and the residual; D94's arm unchanged);
      - test_d130_the_recorded_costs_are_holds (4 holds, and the paracentesis READY).
    - D130TheStatementReader:
      - test_d130_the_done_statements_are_read_in_the_status_words_only;
      - test_d130_the_never_counted_classes_are_read_in_the_kind_and_target_words;
      - test_d130_the_words_are_word_bounded;
      - test_d130_the_visit_families_are_office_em_and_em_other.
    - D130RoutineVisitRecorded: test_d130_note_e_the_routine_visit_is_held_in_every_reading (3, the recorded residual).
    - At 1caaf0609 the module gives 21 failures and 23 errors across 11 tests. The 5 control tests pass there. No
      existing test changed.
  - **Mutation proof.** Each mutant is a fresh copy of the final work tree, checked equal to it before the one mutation.
    The anchor was asserted once, the sha256 printed before and after, and "mutation applied: True" read back. Each copy
    ran the r5_em2, r5_em, r4_em_same_day, r3_families, r3_integration_d90_d92_d94 and combination modules (92 tests).
    The 76 tests outside the new module pass under every mutant.
    - M0, the whole change undone: 21 failures and 23 errors.
    - M1, no statement arm: 21 fail.
    - M2, no never-counted classes: 10 fail.
    - M3, the statement arm under D111's one currency rule (UNDATABLE listed): 1 fails, the time-'unknown' residual.
    - M4, done when every attribute is usable: 16 fail.
    - M5, the done statements read in the kind and target words too: 1 fails.
    - M6, sedation filed under the visit too: 2 fail.
    - M7, the visit family's own label: 20 fail.
    - M8, the classes read in the kind words only: 1 fails.
    - M9, the classes matched inside words: 5 fail.
    - M10, a bare "performed" or "done": 5 fail.
    - M11, moderate sedation read by its statement: 1 fails.
    - M12, no plural: 3 fail.
    - M13, status "performed" only: 1 fails.
    - M14, the classes read in the status words too: 2 fail.
    - The note (e) record changes with no D130 decision, so no D130 mutant touches it. Its liveness is shown
      instead by M15, visit_basis always giving a basis: all 3 of its subtests fail.
  - **Suites** (t.sh on Postgres 55461, a new suffix per run):
    - every tests.test_interpretation_* module (46 with the new one), tests.test_pipeline_assess_events,
      tests.test_readers_dispatch, tests.test_guard_static and tests.test_guard_mutation: 1,319 tests, OK. The same set
      on 1caaf0609 (45 modules): 1,303 tests, OK.
    - test_change_context_events, both guard matrices, test_overlay_differential, test_pipeline_api,
      test_pipeline_interpret, test_retry_reading_api, test_models_event_inventory, test_peer_heading,
      test_repairs_ec5_reportruns, test_repairs_7c8_p1reports, test_repairs_7c8_p1sends and
      test_repairs_r3_integration_guards: 267 tests, OK, 3 skipped.
    - The patch applied to a fresh archive of 1caaf0609 (patch -p1, no .orig or .rej) is byte-identical to the work
      tree. No ops file changed.
  - **Edited.** studio/interpretation/combination.py: procedure_day (the statement arm, its label, never done, ON only)
    and its docstring, plus the module-level helpers VISIT_FAMILIES, DONE_STATEMENTS, NAMING_WORDS, NOT_PROCEDURES,
    _own_words and _stated_procedure. No import changed.
  - **Recorded residuals and costs** (constructed; a hold unless it says otherwise):
    - The spec's "placed on the date": the excision filed under the visit with Gemini's time 'unknown' ("Excision of a
      1 cm sebaceous cyst on the upper back was performed in the office.") is READY, as at 1caaf0609; c2e53f8e holds it,
      separate_em.
      - The alternative is D111's one currency rule for this arm: drop "or (by_statement and day != facts.ON)", mutant
        M3. It asks event_time there ("Was the act (“was performed”) done at this encounter?").
      - It moves nothing else probed and has no recorded member.
      - Not built, because the spec says "placed on the date".
    - The spec's filing "office_em or em_other": the same excision filed as sedation is READY, as at 1caaf0609;
      c2e53f8e holds it.
    - When its words cannot tell: "was excised", "I performed ..." and "was completed" are READY, as at 1caaf0609.
      c2e53f8e holds each, reading "completed" and "I performed" as done and "excised" as gi.other uncertain.
    - "Names imaging": "Ultrasound-guided paracentesis was performed ..." and "Endoscopic ultrasound was performed ..."
      are never counted, READY as at 1caaf0609. c2e53f8e holds both; it routes the second as gi.eus.
    - Held where c2e53f8e is READY: "Removal of a perianal skin tag was performed ..." ("removal" is no procedure word
      of detect's, but the act is a procedure), "A history and physical was performed today.", "Medication
      reconciliation was performed today." and the off-contract "No excision was performed today.". The classes the
      spec names do not cover the visit, its history and physical, or a reconciliation. The installed reader's
      _NOT_A_PROCEDURE list (visit, evaluation, history, review, assessment, education, ...) would; adding it removes
      only holds this rule adds. With no E/M proposed, each moves the visit item to not_listed where c2e53f8e lists it.
    - Note (e), above.
    - D109's residuals are unchanged: services.inventory and derived.procedure_day still omit an act filed under the
      visit, and the routing stand-in lists it under gi.office_em.
  - **Housekeeping.** t.sh left runs/state-em2* and runs/tmp-em2* under gemini-migration/runs, and the measurement
    wrote fresh2-score/f2r5b-em2, fresh-score/f1r5b-em2 and fresh-score/f1r5b-em2-base (with their summary JSON).
    rm -rf is denied, so they remain. All data is synthetic, nothing was sent, no docker was used, and the worktree
    was never edited (HEAD is still 1caaf0609).
  - **Evidence.**
    - The three engines on the probe inputs: repair5b/em2/out/table.txt, raw outputs in
      out/{installed,np-base,np-work}.json.
    - The pins' own inputs: out/pin-table.txt, raw in out/pin-installed.json and out/pin-replay-{base,work}.json. These
      texts were recorded by running the pin module, and the installed side was also run through t.sh in the c2e53f8e
      archive, with identical output.
    - Mutants: out/mut-<n>.log and out/mutation-summary.txt. Census: out/census-*.json.

- **Round 5b integration (2026-11-11; wf_488a1307-ad1, integrated as built).** After the owner reset the usage limit,
  six repairs were built on 1caaf0609, each with an independent reviewer: colon (D124-D125), ercp2 (D127),
  enteroscopy-route (D114), egd (D115-D119), currency2 (D128) and em2 (D130). The three patches committed unreviewed
  at 1caaf0609 (em D111-D113, eus2 D120-D123, questions2 D126) were reviewed independently against d353e64df.
  - The six patches applied in sequence with git apply and no conflict. Engine and guard suites: 1704 tests OK.
  - FRESH-2 (f2r5b-int): A 96/6, B 177/15, C 171/19 plus 2 safe_hold. rows.jsonl is byte-identical to f2r5int's.
    Two assessments gain D125's service extent question (C/PAR-008 r1 and C/W1-u31a-reg-p7-codes-025 r1, both
    EGD-and-colonoscopy notes with no colonoscopy reach); c2e53f8e asks extent on both. The head-to-head is equal to
    h2h-r5int.json in every key (run 1 214/234; worse on 5 rows, all holds).
  - The reviews found, on constructed on-contract inputs, a wrong READY against the document AND c2e53f8e in these
    places. Each is a regression under the owner's registry rule, so round 5c repairs them before refutation round
    5. Only ercp2's was INTRODUCED by its patch; the others were present before it, or are left open by a repair
    that set out to close them:
    - em: SAME_DAY_WORDS never matched a word followed by punctuation ('Earlier today, excision ...'), present
      since D109. D112's removal of the anaphoric frames releases 'Earlier that morning, I performed a flexible
      sigmoidoscopy ...' (G2), where d353e64df and c2e53f8e hold the E/M.
    - eus2: an EUS told only through an EUS-guided act of a kind outside EUS_ACTS (a biopsy, RFA, stent or coil);
      D120 (43240's defining target) and D122 (a diagnostic EUS beside an unlisted EUS-guided act) are recorded but
      read by nothing.
    - colon: D124 misses role headings that carry trailing words ('Pathology Report: Final', 'Nursing note -
      recovery').
    - ercp2 (introduced): D127's clearance release reads a purpose clause, a device subject or a doubt as a yield.
      'The bile duct was swept with an extraction balloon to ensure all stones had been removed; no stones
      remained.' turns 43264 from held to READY.
    - enteroscopy-route: a Roux-en-Y gastric pouch is read as the small-intestinal pouch (44386 READY); an anatomy
      mention ('in a patient with an end ileostomy') is read as the route (44382 READY on an oral enteroscopy).
    - egd: a bleeding_control act named only 'Hemostatic' (43255 READY).
    - em2: an act read by its statement that is undatable is dropped; a class word in the target words sets the
      act apart.
  - High or medium problems repaired in 5c:
    - questions2: the TARGET denial falls out of the member's details row, and D126's (4) asks technique where
      d353e64df asked statement_scope.
    - currency2: a denial's unresolved relation is displaced by a doubt on the same act.
    - egd: a doubted clip takes another act's service question, and the stent removal is never listed.
    - enteroscopy-route: duodenal acts beyond the EGD's reach are moved to the EGD.
  - Saved: gemini-migration/round5b/ (every report and review, each patch and DECISIONS entry, and the workflow).
