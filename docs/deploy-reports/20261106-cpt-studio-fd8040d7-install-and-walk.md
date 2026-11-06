# Install record: CPT Studio fd8040d71e44 (harness repair 3) at cpt.quillmd.com, 88d9db32 and 39f0ac49 re-assessed, and the fresh acceptance walk (2026-11-06)

This release answers the owner's second message of 2026-11-05, recorded verbatim in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md. The work was done in session a12d8fb3.

The act was declared before it ran, in docs/foundation/mutations/20261106-cpt-studio-harness-repair3-install.md:
- committed as f40e03ba3eea at 2026-11-06T04:38:16Z;
- landed by PR #1478 as f867ee719146.

It installs PR #1477's merge commit, fd8040d71e448c31ca6762e92ed9714e57aef4e5.

**The GI release is not complete, and this record does not call it complete.** The harness ran with all three
participants on two fresh documents. What CPT Studio then did with their answers still fails the owner's central
requirement for one class of act. On the fresh PDF, Astra and Fable each proposed 43247 (an EGD with removal of a
foreign body) for the food-bolus removal, quoting the document exactly. Corti omitted it. CPT Studio listed 43247 as
not done on the date of service and gave the reviewer no way to approve it. The owner's 39f0ac49 reads the same way.
See "What did not reach review" below.

## The install, phase by phase

Every phase ran through scripts/run-ruled-mutation.sh from a clean, detached checkout of f867ee719146
(/opt/meddoc-pro/.worktrees/cpt-install-h3-20261106). Before any phase:
- the declared byte-identity check passed;
- every phase's start time falls after the declaration's commit;
- each receipt was read before the next phase began.

The receipts are in /home/claude/cpt-studio-install-20261023.

| phase | ran (UTC) | receipt | result against the declaration |
|---|---|---|---|
| preflight | 05:12:40 to 05:12:45 | preflight-20261106T051245410845Z.json | ok; nothing blocking. Co-tenants and app.quillmd.com recorded |
| image | 05:13:13 to 05:13:20 | image-20261106T051320572668Z.json | `cpt-studio:fd8040d71e44` = `sha256:ffa72382e88e`. Every Dockerfile step CACHED, so apt and pip did not run (the precheck had built the same tree). The package list is identical to `cpt-studio:e6d451f03d86`'s: 166 packages, sha256 prefix 500b6abda58b9a3e. pypdf 6.21.2; uid 10150; the labels name fd8040d71e44 |
| (pre-app dump) | 05:13:57 | pre-app-fd8040d71e44-20261106T051357Z.dump | read-only, through the database container's own pg_dump; mode 0600; 39 TABLE DATA entries |
| app | 05:14:12 to 05:17:03 | app-20261106T051703349105Z.json | Blue/green, 9151 to 9150. 299 availability samples, every one HTTP 200; releases_seen e6d451f03d86 then fd8040d71e44. states_recomputed {"encounters": 59, "changed": {}}. Astra and Fable both live. No leftover *-previous or *-next container. Every count as before, with no provider run created. The worker's beat names fd8040d71e44 |
| verify | 05:17:40 to 05:17:43 | verify-20261106T051743415104Z.json | fd8040d71e44 verified as installed. Co-tenants and app.quillmd.com unchanged. Each security header once. No container appeared elsewhere |
| reassess (dry run) | 05:18:02 to 05:18:18 | reassess-20261106T051818214867Z.json | 0 jobs appeared. The plans name exactly the declared final assessments and runs: 88d9db32 4657b3cd, with Astra f4167034/3fc81ee9 and Fable 437e6278/d6a8101c; 39f0ac49 e0c1c149, with Astra a873ac6a/6b3e413f and Fable cc217632/6053cb63 |
| reassess | 05:18:31 to 05:18:47 | reassess-20261106T051847304868Z.json | 2 jobs appeared, one per encounter. The running worker made both from the retained answers |

**Nothing was sent by the install or the reassessment.**
- Provider runs stayed at 124, sent runs at 113, exchanges at 83 and tool calls at 57.
- No run has a created_at after the app phase's start.
- credits_sum is unchanged.

**The read-only baseline differs in exactly the declared rows.** It was read before the declaration (04:37:46Z) and
after the reassessment (05:19:14Z). The differences:
- assessments 94 to 96, proposals 1,209 to 1,248, clarifications 142 to 148, audit_events 692 to 696, jobs 333 to 335
  (assess succeeded 94 to 96);
- encounter_state: needs_clarification 29 to 28, ready_for_review 4 to 5 (88d9db32);
- assessments_by_engine: cpt-studio-validation@8, 2.

No other row moved. That includes decisions, member answers, users, the reference sources and the schema.

**The two retained encounters read exactly as predicted offline:**
- **88d9db32: ready_for_review, with no open question.** Six codes are READY:
  - 45380, 45381 and 43239: Corti's, which Astra and Fable also proposed;
  - 43249, 45390 and 45385: Astra's and Fable's alone.
- **39f0ac49 (the owner's case): reviewed.**
  - Corti's 43239, 45380 and 45385, which Astra and Fable also proposed, are held by six open questions: performed_status
    and extent for each. Its labelled procedure paragraphs inside the Indications are read as the base reads them.
  - Astra's and Fable's 43247 is listed: "the bolus was removed" is not a documented act, because F-ACTS was dropped.
- **For both,** the prior assessments, the decisions and the owner's answers are kept beside the new assessments.

The co-tenant check passed before and after. https://cpt.quillmd.com/health/ serves
fd8040d71e448c31ca6762e92ed9714e57aef4e5. The rollback image `cpt-studio:e6d451f03d86` is kept.

## The fresh acceptance walk (ordinary use, 05:21:59 to 05:26:49Z)

ops/verify_browser.cjs ran from the act's checkout with `--allow-live-provider` and `--expect-harness`. It used the
agent account review-agent, with ops-agent beside it.

The inputs were sealed before any code read them:
- the two document texts and their expectations were written and sealed (mode 0400) at 2026-11-05T22:27:01Z;
- their sha256 prefixes are the ones the declaration names: 5bbbc6b6c5465ca1 (h3a), 30b557b48defa847 (h3b) and
  3cb92ddac087a666 (the expectations), checked again after the walk;
- the manifest was built from the sealed files at walk time;
- ops/verification/generate.py made the delivered files at 05:20:45Z: h3a as a PDF (3,002 bytes, sha256
  8b4f7aea1e0f…) and h3b as a Word document (37,399 bytes, sha256 53c3f00da0ca…).

The expectations are the authoring session's provisional reading. They are not a qualified coder's adjudication. Every
approval below is an **agent-executed synthetic review**, labelled as such in the product and in every download. **No
human clinical review is claimed.**

| document | delivered as | result | served | agent decisions | sealed expectation |
|---|---|---|---|---|---|
| h3a (d44a77b3) | PDF (pdf-text) | FAIL: 2 of 112 hard checks; 15 soft checks pass, 3 warn | 43239, 45385 and 45381 held by six open questions (performed_status and extent for each). Astra's and Fable's 43247 listed and not approvable. Corti's other candidates (45380, 45390, 99204, 99214 and six quality codes) not selected | none: no code was READY. The approved download was withheld, its dialog naming the three codes that need a detail | 43247, 43239, 45385 and 45381. Must not code: 45390 (the transverse lesion was referred for EMR), a second 45385 (the 2023 outside polypectomy), 43235, 45378 and the anesthesia. None of these was READY or approved |
| h3b (e888f9ce) | Word (docx), with a Stop and Resume | FAIL: 1 of 140 hard checks; 17 soft checks pass | 45385 and 45380 READY | approved both | 45380 and 45385. Must not code: a second 45385 (the failed sigmoid hot-snare attempt), 45381, 43249 and 43235 (the 2025 referring-facility procedures), 45378 and the anesthesia. None of these was READY or approved; 45381 appears only as Corti's unselected candidate |

**What passed on both documents:**
- the upload acknowledgement;
- a reload while processing: the same encounter, its jobs and runs kept, and no request sent twice;
- extraction and the service date;
- every participant named with the model that answered: Corti (its API names no model), Astra `gpt-6-astra` and Fable
  `claude-fable-5-1`;
- request and response hashes, usage, reuse and the trace for every sent run (5 on h3a, 6 on h3b);
- a peer review state for Astra and Fable;
- the customer contract and every scan;
- the decisions persisted after a reload;
- no must-not code approved;
- the draft reports and, on h3b, the approved reports downloaded in the browser.

**The first readings were frozen before any peer saw them.** The server's activity on each document reads in this order:
1. Corti's request, then its answer;
2. Astra's first reading, then Fable's first reading;
3. the first assessment;
4. the peer reviews;
5. the final assessment.

On h3a, the first assessment was made at 05:23:54.78Z and the first peer request was sent at 05:23:54.89Z. Each peer
review is its own run.

**Stop and Resume on h3b, verified against the trace.** All 19 Stop and Resume checks pass.
- **The Stop landed mid-exchange.** The server recorded "Processing stopped" at 05:25:03.066Z. Astra's first exchange
  had been sent at 05:25:01.461Z and was still in flight.
- **Nothing more was sent.** That exchange's answer was recorded. Run 48fa965f ends with "Stopped by a workspace member
  while the tool loop ran, after 1 exchange; nothing more was sent". No new run appeared in the 6 s the walk watched
  while stopped.
- **Resume continued the loop without resending.** Resume answered HTTP 201 at 05:25:15.28Z. Run 1f17208c continued
  the loop from its verified record and sent one exchange, with request sha256 7854489f…. The stopped exchange (request
  sha256 0c4067fc…) was not sent again; it appears once as an exchange in the trace. The chain keeps 0c4067fc… as its
  request identity.
- **No participant was lost.** Fable's reading, both peer reviews and the final assessment followed, and the document
  finished ready.

**Downloads, checked independently.** ops/verify_downloads.py checked six files, 166 of 166 checks. The files are h3a's
draft TXT and CSV, and h3b's draft and approved TXT and CSV. The checks cover:
- the bytes against every recorded sha256;
- codes, order, units, modifiers and statuses as persisted;
- every approval labelled agent-executed;
- every quotation an exact slice of the revision text, and a passage CPT Studio holds as support;
- nothing a customer must not be shown.

The report is /home/claude/cpt-studio-harness3-20261105/acceptance/verify-h3/downloads.json.

**The customer surfaces, scanned.** ops/scan_customer.py ran as review-agent, GET only, from 05:31:15 to 05:31:22Z,
and passed on d44a77b3, e888f9ce and 88d9db32:
- 42 requests: 40 GETs, plus the sign-in and sign-out POSTs;
- 27 of 27 checks pass, with 0 hits in any JSON, header, file or bundle;
- for each encounter, the contract and the original document were checked, and every customer report was scanned (six);
- 3 operator URLs each, and the trace, answer 404 to the customer;
- the sign-out is proved.

The operator view's identifiers were supplied for the two walk encounters, from their operator snapshots, but not for
88d9db32. 39f0ac49 was not scanned in this session.

**The three hard failures, each examined.** None is a code wrongly made READY or approved. The routing reader
(studio/gi/detect.py, gi-routing@7) and every module it imports are unchanged between the previous live revision
e6d451f0 and fd8040d7 (git diff). So all three readings are main-equal.

| check | what happened | cause |
|---|---|---|
| h3a `routing.gi.egd.status`: uncertain, expected performed | The routing reader placed "Upper endoscopy" in the Indications section | The document's labelled procedure paragraphs follow its Indications. F-SECTIONS L, which read such labels as their own sections, was dropped in refutation cycle 2. The documented-service reader also reads both services as in doubt, so the three codes are held for performed_status and extent. 39f0ac49 has the same shape |
| h3a `routing.gi.colonoscopy.status`: uncertain, expected performed | The same, for "Colonoscopy" | The same |
| h3b `routing.gi.colonoscopy.status`: incomplete, expected performed | The routing reader took "was unsuccessful", which the document says of the attempted hot-snare polypectomy, as the colonoscopy's own status. It also found no performance evidence for the title "Colonoscopy" | The routing reader. The documented-service reader read the biopsies and the cold-snare polypectomy as done today. The failed attempt produced no second 45385 (F-TIME F), and the 2025 referring-facility procedures produced no READY code (F-TIME P). Both expected codes were READY |

The three soft warnings on h3a:
- the six open questions;
- the review plan's codes not READY;
- a 134 x 41 px "save details" button below the 44 px touch target.

## What did not reach review: Astra's and Fable's 43247

On h3a, Astra and Fable each proposed 43247 in their first readings, quoting the document verbatim: "A retrieval net
was passed through the working channel and the bolus was removed through the mouth in one piece." Corti did not return
43247.

CPT Studio listed it:
- with the reason "Proposed by Astra and Fable (independent participants), but not added as a proposal: the act it
  accounts for is not documented as done on the date of service";
- not reinstatable, with no allowed action.

A reviewer cannot approve it. 43247 is the first code of the sealed expectation.

**Why.** The documented-service reader names a food-bolus act only for the words "food bolus" or "food impaction".
F-ACTS, which read "the bolus was removed" as the act, was refuted in cycles 3 and 4 and dropped under the two-cycle
rule. The owner's 39f0ac49 lists its 43247 for the same reason.

**What that means.** For this class of act, an explicit, source-supported Astra or Fable proposal does not reach human
review. That is the owner's central requirement, and it is not met here. For acts the reader documents, it is met:
88d9db32's 43249, 45390 and 45385, which only Astra and Fable proposed, are READY.

## Astra's and Fable's live contributions

- **h3a:**
  - Astra and Fable each proposed 43247, 43239, 45385 and 45381, which is the sealed provisional expectation exactly.
  - Corti selected 43239, 45385 and 45381, and missed 43247.
  - Both participants' peer reviews ran.
- **h3b:** all three proposed 45385 and 45380 (the expectation). Both peer reviews ran.
- **Fable's new contract.** Both of Fable's first readings were accepted under `anthropic-messages@cptstudio-harness-4`:
  refused false, no problems, no unverified quote. On the previous release all three of Fable's walk readings were
  refused by the reading schema.
- **88d9db32** (reassessed from its retained live answers): Astra's and Fable's 43249, 45390 and 45385 are READY, each
  an act done today.
- **No model approves anything.** The two READY codes on h3b were approved by the labelled agent review.

## Usage and cost of the walk (this session's only provider sends; the install and the reassessment sent nothing)

| participant | sent runs | usage (provider-reported; input / output tokens) | estimated cost |
|---|---|---|---|
| Corti | 2 (primary) | 0.061144 and 0.040320 credits | credits, not USD; no dollar figure |
| Astra, gpt-6-astra | 5: h3a's first reading (2 exchanges) and peer review; h3b's stopped first reading (1 exchange), its continuation (1 exchange) and peer review | 11,466 / 2,595; 7,068 / 884; 1,939 / 83; 6,298 / 1,565; 4,109 / 70 | $0.2217, $0.1149, $0.0092, $0.1238, $0.0446 |
| Fable, claude-fable-5-1 | 4: two first readings and two peer reviews (2 exchanges each) | 26,249 / 5,032; 27,172 / 1,663; 17,258 / 3,203; 16,967 / 1,183 | $0.5141, $0.3549, $0.3327, $0.2288 |

- **Estimated total:** $1.9447 for the participants (Astra $0.5142, Fable $1.4305), plus Corti's 0.101464 credits.
- **Confirmed costs:** none. No provider invoice is read here.
- **Controls kept throughout:**
  - usage records;
  - finite deadlines;
  - the participant concurrency rules;
  - duplicate prevention, which held across the Stop and Resume;
  - Stop itself.

## What is not claimed

Functional progress is reported here. Clinical accuracy, billing readiness and content-use permissions are separate
verdicts, and a synthetic walk establishes none of them. **Complete three-engine operation is not claimed while these
known failures remain:**
- **Astra's and Fable's 43247 for a food-bolus removal does not reach review** (h3a, 39f0ac49). F-ACTS was dropped.
- **Labelled procedure paragraphs** are read as part of the Indications, which holds the codes for questions (h3a,
  39f0ac49). F-SECTIONS L was dropped.
- **The routing reader's colonoscopy status** takes a failed polypectomy as the colonoscopy's own status (h3b). The
  reader is unchanged by this release.
- **Completed marking versus future localization is not delivered.** F-TIME R was dropped.
- **The base's own false READYs** recorded in cpt-studio/HARNESS.md stay open. Among them: "The polyp was left in
  place." under a procedure line naming the polypectomy.
- **Recorded false holds** on the safe side.
- **Two recorded asymmetries:** L4-4, and Corti's own selection on a not-done act staying held.
- **Not walked here:** answering a clarification, and recomputation after one.
- **pypdf 6.21.2's seven denial-of-service advisories** are accounted for in
  docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md, not resolved. No wider-upload readiness is
  claimed.
- **NCCI PTP is not connected:** modifiers are considerations only.
- **D3 to D5 stay open.**
- **Moderate sedation and the anesthesia service** are outside CPT Studio's coded scope.
