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
