# Install record: CPT Studio 6f306af1b030 (the completion repair) at cpt.quillmd.com, the four retained encounters re-assessed, and the fresh acceptance walk (2026-11-07)

This release answers the owner's completion directive of 2026-11-06, recorded verbatim in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md. The work was done in session a12d8fb3.

The act was declared before it ran, in docs/foundation/mutations/20261107-cpt-studio-completion-install.md:
- committed as c2130f369f7c at 2026-11-07T01:49:43Z;
- landed by PR #1481 as a7d2b51751a2.

It installs PR #1480's merge commit, 6f306af1b03049b7adf289bb22918b2dcb765819.

**The completion target is not met, and this record does not call it met.** The install matched its declaration in
every row and sent nothing. The acceptance walk then ran on the live site with Corti, Astra and Fable:
- **the blind set c2 passed one document of three;**
- **c1 passed one of three.**

Each failure is a hold, never a false READY:
- four are clearly documented codes that a reviewer cannot approve while reviewer confirmation stays off (D7);
- two are defects of the walk's own instrument and of the customer API's addendum response.

All are recorded under "What the walk found" below, with their causes in the shared readers. They are the next repair
round's work: under the two-cycle rule, two of them call for a changed approach, not another patch.

## The install, phase by phase

Every phase ran through scripts/run-ruled-mutation.sh from a clean, detached checkout of a7d2b51751a2
(/opt/meddoc-pro/.worktrees/cpt-completion-act-20261107). Before any phase:
- the declared byte-identity check passed;
- the migrations and models list was exactly 0013 and models.py;
- every phase's start time falls after the declaration's commit;
- each receipt was read before the next phase began.

The receipts are in /home/claude/cpt-studio-install-20261023.

| phase | ran (UTC) | receipt | result against the declaration |
|---|---|---|---|
| preflight | 02:12:59 to 02:13:10 | preflight-20261107T021305508386Z.json | ok; tree "descendant-without-runtime-change"; nginx -t clean apart from two warnings in other sites' vhosts; ports 9150 active, 9151 idle |
| image | 02:13:34 to 02:13:45 | image-20261107T021341515624Z.json | `cpt-studio:6f306af1b030` = `sha256:f9edaaf90e07`. Every Dockerfile step CACHED, so apt and pip did not run. The package list is identical to `cpt-studio:fd8040d71e44`'s: 166 packages, sha256 prefix 500b6abda58b9a3e. pypdf 6.21.2; uid 10150; the labels and CPT_STUDIO_RELEASE_SHA name 6f306af1 |
| (pre-app dump) | 02:14:14 | pre-app-6f306af1b030-20261107T021414Z.dump | read-only, through the database container's own pg_dump; mode 0600; 39 TABLE DATA entries. The baseline read again then equalled the declared one |
| app | 02:14:27 to 02:17:23 | app-20261107T021718036631Z.json | Migrate applied 0013 and nothing else. Blue/green, 9150 to 9151. 301 availability samples, every one HTTP 200; releases_seen fd8040d7 then 6f306af1. states_recomputed {"encounters": 61, "changed": {}}. Astra and Fable live. The old pair drained (130 s, 0 connections) and was removed; no leftover container. Every count as before apart from studio_migrations 12 to 13 and the two new columns (no stored answer with a question, no clarification bound). The worker's beat names 6f306af1 |
| verify | 02:17:57 to 02:18:03 | verify-20261107T021800582259Z.json | 6f306af1 served under normal certificate verification, each security header once. Co-tenants and app.quillmd.com unchanged. The vhost differs from preflight only in its proxy_pass port: the file with 9150 written back hashes to the preflight's 259b895d |
| reassess (dry run) | 02:18:42 to 02:19:08 | reassess-20261107T021904876708Z.json | 0 jobs. Each of the four plans names exactly the declared final assessment, Astra's and Fable's runs and peer runs |
| reassess | 02:19:50 to 02:20:16 | reassess-20261107T022013348927Z.json | 4 jobs, one per encounter, all succeeded by 02:20:11, made from the retained answers |

**Nothing was sent by the install or the reassessment.**
- Provider runs stayed at 135, sent runs at 124, exchanges at 97, tool calls at 67, and credits_sum at 3.164168.
- No provider run was created after the app phase started.

**The read-only baseline differs in exactly the declared rows.** The counts after the reassessment differ from those
before it in:
- routing_runs 71 to 75, assessments 100 to 104, proposals 1,308 to 1,377;
- decision_invalidations 0 to 2, audit_events 744 to 752, jobs 354 to 358;
- encounter states: needs_clarification 29 to 28, ready_for_review 5 to 8, reviewed 22 to 20.

The reassessment moved no other row; the app phase had moved only studio_migrations and its two columns, as above.

**The four retained encounters read exactly as predicted offline:**
- **39f0ac49 (the owner's case): ready_for_review.** 43239, 45380, 45385 and 43247 are READY, with no question. Astra's
  and Fable's bolus removal reaches review and can be approved.
- **d44a77b3: ready_for_review.** 43239, 45385, 45381 and 43247 are READY, with no question.
- **e888f9ce: ready_for_review.** 45385 and 45380 are READY with no incompleteness flag. Its two earlier synthetic
  approvals were invalidated by the fingerprint rule, as declared ("the checks for 45380 changed", "the evidence and
  checks for 45385 changed").
- **88d9db32: ready_for_review.** Its six codes are READY, as before.

The co-tenant check passed before and after. The rollback image `cpt-studio:fd8040d71e44` is kept.

## The fresh acceptance walk (ordinary use, 02:21:52 to 02:39:02Z)

ops/verify_browser.cjs ran from the installed revision's checkout with `--allow-live-provider` and `--expect-harness`.
It used the agent account review-agent, with ops-agent beside it, one document at a time.

**The blind set c2:**
- three documents written by an agent blind to the repair, sealed at 2026-11-06T14:11:22Z;
- read by nobody until this revision was merged and its image precheck and predictions were read;
- its manifest built from its expectations alone at 01:19Z, after the four sha256 values were checked;
- two PDFs and one Word document made by ops/verification/generate.py.

**c1:** written and sealed by this session before the repair's code existed, so it is never the independent
evidence.

**The expectations:** each set's expectations are its author's provisional reading, not a qualified coder's
adjudication.

**Every approval below is an agent-executed synthetic review,** labelled as such in the product and in every download.
**No human clinical review is claimed.**

| doc | delivered | result | reached review | decided (synthetic) | downloads |
|---|---|---|---|---|---|
| c2a | PDF | **fail** | 43248 held (performed_status, extent); 45378 held, then excluded by the member's "Not documented" extent answer | none possible | drafts; approved report withheld (correctly) |
| c2b | PDF | **fail** | 43239 READY; 43247 held (performed_status); routing reads the EGD incomplete | 43239 approved | drafts; approved report withheld (correctly) |
| c2c | Word | pass | 45380, 45385, 45381 READY | all three approved; reviewed | drafts and approved TXT/CSV match the decisions |
| c1a | PDF | pass | 43239, 45385, 45381, 43247 READY | all four approved, the bolus removal included; reviewed | drafts and approved TXT/CSV match the decisions |
| c1b | Word | **fail** | Stop and Resume worked (stop 200, resume 201, Fable's stopped stage resumed); 45380 READY; 45385 held | 45380 approved | drafts; approved report withheld (correctly) |
| c1c | PDF | **fail** (the walk's own check and the scan) | 45338 READY after the member's answer and the physician's addendum (a new revision) | 45338 approved; reviewed | drafts and approved TXT/CSV match the decisions |

**What worked, observed live:**
- PDF and Word upload, and extraction;
- all three participants on every document;
- Stop and Resume;
- a member's answer re-making the assessment with nothing sent;
- an addendum as a new revision;
- decisions persisting across a reload;
- downloads matching the decisions;
- no false READY on any document.

## What the walk found (each cause read from the live records and reproduced offline)

1. **c2a, the labelled procedure paragraphs ("Upper endoscopy: ...", "Colonoscopy: ...") were not released (U2).**
   `structure.decisions` refused both on P1, "not a procedure report", only because the plan says "Clinic visit in
   four weeks" (P1 reads `cues.EM_VISIT` anywhere in the text as office E/M structure). Without that line P2 refuses
   both: the EGD paragraph opens with a frame its allow-list lacks ("After informed consent and a time-out, the
   gastroscope was passed ..."), and the colonoscopy paragraph opens with a positioning sentence. The paragraphs
   therefore read as Indications. The EGD extent question then cites the passage that answers it ("advanced to the
   second portion of the duodenum"), which fails the truthful-questions requirement.
2. **c2a, a Savary dilation over a guidewire was not read as done.** "Savary-Gilliard dilators of 15, 16 and 17 mm
   were then passed over the wire" and the impression's "dilated to 17 mm with Savary-Gilliard bougies" give no
   dilation act, so 43248 (proposed by Corti, Astra and Fable) is held as `act_missing`.
3. **c2b, the extent was read from the first landmark of a coordinated reach sentence.** "The scope was then advanced
   into the stomach, ... and through the pylorus to the second portion of the duodenum" reads as "incomplete: stomach",
   so the EGD is incomplete.
4. **c2b, a bolus removal phrased "the bolus was captured and brought out through the mouth"** (after "A retrieval net
   was passed") gives no removal act, so 43247 (Astra and Fable) is held. On the installed base it was not even a
   proposal: it now reaches review, but cannot be approved.
5. **c1b, a failed act outside the closed attempt form holds a different, successful act's code.** "Hot snare
   polypectomy of a 12 mm pedunculated polyp ... was attempted, but the snare could not be closed around the stalk"
   reads "uncertain" (an unresolved negation). Because a provider cited it for 45385, the documented cold-snare removal
   of the 7 mm polyp is held: "a passage that hedges holds the code". This is the another-act release abandoned in
   cycle 2, meeting the recorded residual "a sub-act's failure outside the closed attempt form".
6. **c2a and c1c, the walk's code-list check was out of date.** A code the engine excludes by a member's answer stays
   listed where its selected code was (customer_api.code_rows, U11, by design). The walk's `expectedCodeRows` predates
   that case, so it reported "the customer lists ... 45378; the operator view implies 43248". The product is right and
   the instrument is wrong.
7. **c1c, the addendum response carried an internal identifier.** POST /api/encounters/{id}/addenda answers
   `{"revision_id": "<uuid>"}`, as API.md documents. The walk's privacy scan flags it, because a revision id is among
   the identifiers a customer surface must never carry, and the page does not use it. It is unchanged since before
   this release; the walk exercised the addendum for the first time.

**Measured against the installed base** (offline, the same documents with each document's own date): findings 1 to 4
read the same or worse on the installed release. None is a regression; each is a defect this repair did not reach.
Findings 1 and 5 sit on mechanisms already refuted in two cycles (the labelled release's allow-lists; the another-act
release), so the next round changes their approach rather than patching them.

## Usage

| | provider runs (all sent) | Corti credits | exchanges / tool calls | other |
|---|---|---|---|---|
| install and reassess | 0 | 0 | 0 / 0 | - |
| walk c2 | 15: Corti 3; Astra 3 + 3 peer; Fable 3 + 3 peer | +0.145872 (3.164168 to 3.310040) | +19 / +13 | 4 synthetic decisions; 1 member answer |
| walk c1 | 19: Corti 4 (the addendum's revision included); Astra 4 + 4 peer; Fable 4 + 3 peer | +0.129748 (to 3.439788) | +24 / +15 | 6 synthetic decisions; 1 member answer, 1 withdrawal; Fable's stopped stage cancelled, then resumed |

No unknown outcome and no reserved or sending run remained after either walk. Astra's and Fable's token usage is
recorded on each run (usage keys as in the baseline).

## Reported separately

- Clinical validation: not performed. Every approval is an agent-executed synthetic review; no human clinical review
  is claimed.
- Content-use permissions (D3 to D5): open, as recorded.
- Limitations: L1 (pypdf 6.21.2's seven advisories, accounted for, not resolved); L2 (NCCI PTP not connected).
- Owner questions: Q1, Q2 and 4.6, unchanged.

## Correction to the completion PR's record (appended)

HARNESS.md "The gates and the install predictions on `443740630`" says the predictions differ from cycles 3 and 4 only
"apart from the code fingerprint in the reassess keys". That part of the key is not a code fingerprint: it is
sha256(tag)[:12], the release tag the reassessment is made for (jobs.reassess_retained). The merge commit's predictions
equal 443740630's in every reading and count. Corrected there in the next code change, which may touch cpt-studio/.
