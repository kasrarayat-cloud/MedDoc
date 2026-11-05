# Install record: CPT Studio e6d451f0 (the GI core and multi-agent harness repair) at cpt.quillmd.com, 88d9db32 re-assessed, and the fresh acceptance walk (2026-11-05)

Owner directive of 2026-11-05 (verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md). Declaration
docs/foundation/mutations/20261105-cpt-studio-harness-repair-install.md: committed alone as 964a4728 at
2026-11-05T18:46:06Z, landed as 5c787efe (PR #1475). Session a12d8fb3.

## Installed

**e6d451f03d86f11e8454c46e14cda6337bdbef23**, PR #1473's merge commit. It carries PR #1472 (the GI core and harness
repair) and refutation rounds 4 to 7 over it.
- Image `cpt-studio:e6d451f03d86` = `sha256:a0b077a1792d`. The rollback image is `cpt-studio:b0dc3446c64c`, kept.
- It replaced b0dc3446c64c840cd01e9f37b8de3bad7aa954d4.
- Every phase ran through scripts/run-ruled-mutation.sh from a clean, detached checkout of 5c787efe. Each start time
  falls after the declaration's commit, and each receipt was read before the next phase.

| phase | at (UTC) | receipt (in /home/claude/cpt-studio-install-20261023) | against the declaration |
|---|---|---|---|
| preflight | 19:13:51 | preflight-20261105T191357040782Z.json | ok: baseline recorded, no blocking problem; web ports 9150 active, 9151 idle; both participant sources present; `nginx -t` passes |
| image | 19:14:20 | image-20261105T191427991267Z.json | built from cache, every step CACHED including apt and pip (the precheck had built the same cpt-studio tree, 81327159); after the phase: the dpkg list (166 packages) is identical to cpt-studio:b0dc3446c64c's; pypdf 6.21.2; CPT_STUDIO_RELEASE_SHA, the revision label and uid 10150 as declared |
| before app | 19:14:58 | pre-app-e6d451f03d86-20261105T191458Z.dump (0600) | read-only pg_dump, 39 TABLE DATA entries. jobs_active 0, no run reserved, sending or unreconciled, last audit event 07:43:47Z |
| app | 19:15:08 | app-20261105T191802411110Z.json | blue/green 9150 to 9151. 305 availability samples, all 200; releases_seen b0dc3446 then e6d451f0; drain 130.8 s; migrate applied nothing; states_recomputed {"encounters": 55, "changed": {}}; 0 unrunnable stages; no access check; participant credentials parsed (astra, fable). After app: every count equals the pre-app reading, the worker beat names e6d451f0, 0 provider runs since the act began, no previous or next container left |
| verify | 19:18:34 | verify-20261105T191834323824Z.json | e6d451f03d86 verified under normal certificate checks with its security headers; co-tenants and app.quillmd.com unchanged |
| reassess (dry run) | 19:18:46 | reassess-20261105T191857950580Z.json | the declared plan exactly: final assessment 0e7c965b; Astra's run f4167034 with peer run 3fc81ee9; Fable's run 437e6278 with peer run d6a8101c; 0 jobs queued |
| reassess | 19:19:24 | reassess-20261105T191936531375Z.json | one assess job, made by the running worker from the retained answers and succeeded. Tables: assessment +1, proposal +26, clarification +1, job +1, routingrun +1, auditevent +2, and no other table moved. Provider runs 107, sent 97, exchanges 63, tool calls 40 and credits all unchanged |

**88d9db32 after the reassessment, as predicted.** It reads `needs_clarification` (customer: awaiting a detail), on
engine cpt-studio-validation@7.
- **Ready:**
  - 45380 and 43239, Corti's;
  - 43249, 45390 and 45385, the codes Corti omitted that Astra and Fable proposed, admitted under P-ADMIT through
    Corti's own validation path.
- **Held:** 45381, with one open question, the tattoo conflict. That is the live revision's reading: directive item 3's
  tattoo-versus-resection reading was dropped in refutation round 6.
- **Listed:** the decompression, as an act no upper-endoscopy code accounts for.
- The prior assessment (0e7c965b) and the encounter's decisions are kept beside the new current assessment.
- **Served, read through the public site with GET only (as review-agent):**
  - the same six codes and statuses;
  - ops/scan_customer.py passes on 88d9db32: the contract, the original document, 7 operator URLs each 404 to the
    customer, and no provider, model, usage, id, hash or trace text in any body, header, download or bundle;
  - the sign-out is proved.

## The fresh acceptance walk (ordinary use, 19:22:13 to 19:27:36Z)

ops/verify_browser.cjs ran from the act's checkout, through the agent account review-agent with ops-agent beside it,
with --allow-live-provider and --expect-harness. Its three documents and their expectations were written and sealed
(mode 0400) at 09:49:56Z and 09:50:29Z, before any code read them, and the manifest was built from the sealed files
(sha256 prefixes checked). Every approval below is an **agent-executed synthetic review**, labelled as such in the
product and in every download. **No human clinical review is claimed.**

| document | delivered as | result | codes READY (served) | agent decisions | sealed expectation |
|---|---|---|---|---|---|
| h2a (193f50c0) | PDF (pdf-text) | **PASS**, 148 hard and 17 soft checks | 45380, 45381, 45385, 43249, 43251, 43239 | approved 45380 (modifier XS), 45381, 45385, 43249, 43239; rejected 43251 (the plan's designated rejection) | all six provisional codes; nothing must-not |
| h2b (7fd652e2) | Word (docx), with a Stop and Resume | FAIL, 2 of 140 hard checks (below) | 45390 (EMR), 45380 | approved both | 45390, 45380 and 99152, 99153 (sedation, not proposed by anyone); 45385, 45381, 45382 and 45378 rightly absent. The EMR's lift injection, its own snare and both prophylactic clips are bundled as part of the EMR |
| h2c (0cd3285f) | Word (docx) | FAIL, 1 of 116 hard checks (below) | 43239; 43248 held for a question | approved 43239 | 43239 and 43248; 43249 (no balloon) rightly absent; the decompression listed as an act no upper-endoscopy code accounts for, as expected |

**What passed on every document:**
- the upload acknowledgement;
- a reload while processing: same encounter, jobs and runs kept, no duplicate request;
- extraction and the service date;
- every participant named with its model: Corti, Astra gpt-6-astra, Fable claude-fable-5-1;
- request and response hashes, usage, reuse and the trace;
- the customer contract and every scan;
- decisions persisted after a reload;
- no must-not code ever approved;
- the draft and approved reports downloaded in the browser.

h2b's Stop and Resume passed as well: nothing was sent while stopped, the same jobs were kept, and no duplicate request
was made. ops/verify_downloads.py checked every downloaded report independently, 276 of 276: codes, order, units,
modifiers and statuses as persisted, every agent approval labelled, every quotation an exact and supported slice, and
nothing a customer must not be shown. ops/scan_customer.py (GET only) passes on all three encounters.

**The three hard failures, each examined.** None of them is a code made READY or approved wrongly.

| check | what happened | cause | whose |
|---|---|---|---|
| h2b `routing.gi.colonoscopy.status`: historical, expected performed | the routing-era reader's family label read "an outside colonoscopy" (the Indication) above the report's own title and "Repeat colonoscopy in 3 months" | the routing reader; identical at main and the previous live revision (reproduced on both). The documented-service reader still read the EMR and biopsy as performed, and both codes were READY | pre-existing, main-equal |
| h2b `provenance.peer_reviews`: no peer review state for Astra or Fable | the walk's planned Stop interrupted Astra's first reading mid-run; after Resume, the harness refused to send the identical request again ("an identical request is never sent again"). Fable's reading was refused (next row), so neither peer review ran | the duplicate-prevention rule treats a Stop that cut a run short like a failed request | a product limitation, recorded: a Stop during a participant's run loses that participant for the revision, reported as partial completion |
| h2c `routing.gi.egd.status`: uncertain, expected performed | the routing-era reader found "no performance evidence in its sentence or section" for the report's title | the routing reader; identical at main and the previous live revision. The same doubt holds 43248 (dilation over a guide wire) for a question, where 43239 was READY | pre-existing, main-equal |

**Fable answered every document, and its reading was never used.**
- Its requests were sent and answered: claude-fable-5-1, with usage recorded.
- All three readings were refused by the reading schema: "not_coded[0] has a field the schema does not allow" (a value
  of 9, 16 and 13 characters).
- The harness reported this as refused, which is partial participation, and substituted nothing, as directive item 5
  requires.
- The participant schema and parser are untouched by this release, and Fable's reading of 88d9db32 earlier was used.
  So this is the model's output varying against a deliberately strict schema.
- Accepting an extra field there is a change to the clinical path that needs its own refutation, and it is not made
  here.

## Usage and cost of the walk (this session's only provider sends; the install and the reassessment sent nothing)

| participant | sent runs | usage (provider-reported) | estimated cost |
|---|---|---|---|
| Corti | 3 (primary) | 0.142716 credits (0.089984, 0.023916, 0.028816) | credits, not USD; no dollar figure |
| Astra, gpt-6-astra | 5: 3 first readings (h2b's stopped mid-run) and 2 peer reviews; plus 1 retry not sent | first readings 10,057 / 9,436 input tokens and 2,656 / 1,459 output tokens; the stopped run 2,065 / 131; peer reviews 3,897 / 310 and 3,076 / 304 | $0.2076 (h2a) and $0.1352 (h2c), the operator view's estimates for the two first readings; the peer reviews and the stopped run carry no estimate |
| Fable, claude-fable-5-1 | 3 first readings | 28,691 / 22,774 / 18,713 input tokens, 5,050 / 4,953 / 3,058 output tokens | $0.5394, $0.4754, $0.3400 |

- **Estimated total:** $1.70 where the view estimates, plus the unestimated Astra peer reviews and stopped run, plus
  Corti's 0.143 credits.
- **Confirmed costs:** none. No provider invoice is read here.
- **Controls kept throughout:** usage records, finite deadlines (1,500 s per document), the participant concurrency
  rules, duplicate prevention (the not-sent retry) and Stop.

## What is not claimed

Functional completion is reported here. Clinical accuracy and content-use permissions are separate verdicts, and none
of them is established by a synthetic walk: the expectations are the author's provisional reading, not a qualified
coder's adjudication.
- NCCI PTP is unconnected: modifiers are considerations only.
- D3 to D5 and decision (m) stay open.
- Directive item 3's tattoo-versus-resection and future-localization readings are not delivered (refutation round 6).
- Moderate sedation (99152/99153, or G0500 for Medicare) is outside CPT Studio's coded scope, and was neither coded nor
  listed.
