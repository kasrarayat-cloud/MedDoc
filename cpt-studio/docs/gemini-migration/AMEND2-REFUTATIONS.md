# AMENDMENT-2 refutation: the judge's decisions

Session 31dfc45d, 2026-11-15. The judge of FINAL-V2 amendment 2 (the interpreter is Claude Fable 5.2, D275). Synthetic
and development material only. Nothing was sent to any provider, no credential file was read, no docker was run, no git
command changed anything, the worktree and the built tree were only read (a `find -newer` after each run shows no file
of the built tree written), and nothing under `acceptance-a1/` or any sealed set was opened.

- The amendment as refuted: `AMENDMENT-2-pre-refutation.md` (a byte copy, sha256 `24a7d701...` at the time of copy).
- The amendment as revised: `AMENDMENT-2.md`; every change carries the tag `[R:<lens>-<id>]` of the finding below that
  made it (every one of the 32 findings has at least one tag).
- The judge's own scripts and outputs: `judge-scripts/model.py` (the cost model, sha256 `cf814230...`) and
  `judge-scripts/repair_check.py` (the revised merged view's direction on the built engine, in-memory monkeypatch only,
  sha256 `1f50c421...`), each with its `.out.txt`.

## Governing texts read first

The owner directive of 2026-11-15 and its session interpretation (rulings file, lines 3373-3425), D275, then FINAL-V2
as AMENDMENT-1 amends it, D183 (funding: no ceiling of the session's own; a per-batch guard of about twice the model),
D202 (a pin moves freely only before the first recording under its label), C5 (ADJUDICATION: a MAX_TOKENS refusal is
never offered a paid repeat; only a new revision or an operator's recorded override sends again), D14 (the key in the
worker only). No decision below departs from them; where a finding's fix would have (T7's reclassification, CONN-2's
60 tok/s deadline), the ruled part is kept and the rest decided.

## Counts

| decision | findings |
|---|---|
| accepted (30) | CONN-1, CONN-3, CONN-4, CONN-5, CONN-6, CONN-7; T1, T2, T3, T4, T5, T6, T8, T9; R1, R2, R3, R4, R5, R6, R7, R8; F-COST-1 to F-COST-8 |
| accepted in part (2) | CONN-2, T7 |
| rejected (0) | - |

Several findings are one defect seen through two or three lenses, decided once and tagged with every id: the long-note
claim bound (T4 = R1 = F-COST-1), partial usage priced as final (CONN-3 = F-COST-3), the shared Anthropic account (R5 =
F-COST-4), and the merged view's common root (T1, T2, T3, T5, T9).

## How the findings were verified

- Every code claim was read at its file and line in the built tree (`trees/step8-195e06e90/cpt-studio`, code identical
  to a9bbc242c); the line numbers below are the tree's.
- The truth lens's demonstrations were re-run read-only on the built engine (`python3 -B -I`): `demo_within.py`
  reproduced T1's release exactly, and its outputs for T2 and T5 were read with their scripts. The judge's
  `repair_check.py` then checked the revised design's direction: with the merged view's options limited to the written
  values, an overfilled examination device is no digital examination and 45378 is supported as under the true reading;
  with `combination._claims_session` reading a contradiction's sides, 43235 is held within the EUS (the T1 case).
- F3all (frozen 2026-11-15T19:18:05Z) and F3long (frozen 19:38:01Z, after the lenses ran) were read after their
  freeze: MANIFEST, SUMMARY, BATCH plans, the probe bodies' Anthropic usage, and the replay health and scores. The
  overfilled-slot scan was re-run by the judge on F2high, F3all and F3long.
- The claude-api reference (cached 2026-11-03) was read for the Anthropic facts the findings rest on: a refusal is
  "surfaced, not retried with the same prompt" and a mid-stream decline is billed (model-migration.md:453, 1397); the
  5-minute cache lifetime runs from the start of the request (prompt-caching.md:148); cache writes cost 1.25 x input
  (5 minutes) and 2 x (1 hour).

## Short documents (the user's request, relayed: "also check with short doc as well and see if it has problem or not")

Checked first-hand on the 8 short development notes (551-1,417 characters) of F2high, F2high-p2 and F3all, their replays
and scores, and against every code path a finding names.

**What the short notes measured.**
- Both passes completed on every short note. F3all: pass 1 79.8-190.6 s with 9,716-22,135 output tokens (at most 17% of
  128,000); pass 2 24.4-94.8 s with 41-108 claims (at most 11% of the 1,000 bound); both passes 110-286 s. That is far
  inside the 1,320 s deadline, the progress panel's slow threshold and every bound.
- The slot rule: with two slot sentences close to 2.1's items 1 and 2, F3all wrote 0 overfilled slots in 10 answers
  (the judge's re-run of the scan; F2high's two slips, A-v2's device and A-v6's organ, are gone, and both notes' 8 rows
  scored correct).
- Accuracy (`devsets/score-F3all`): 27 rows, 22 correct, 4 unnecessary holds, 1 wrong READY as scored. The wrong READY
  is the A-v5 45380 scoring artifact (verified first-hand in the BRIEF); B-fb10 45330's hold is the replay tool's missing
  word runs (5.3). The judge replayed F3all's fb10 with the pipeline's word runs (`verify/replay-F3all-fb10-wordruns`,
  the probe tree read-only, the session venv, no tree file written): 45330 READY and 45331 EXCLUDED, as on F2high-p2.
  With section 6's scorer rule and 5.3's word runs, READY recall is 7 of 10, with no wrong READY and no wrong exclusion. The three holds left are v3 45386 (COLFULL, by design), fb05 45380 (`act_target`, by design; T8) and
  fb10 99214 (member values missing from the devset: a measurement input gap).
- Cost per short note, both passes, at 1.7's rates: $0.59-1.44 when pass 1 reads the cached instruction, $1.03-1.87 as
  production pays it (every pass 1 writing the cache), $0.94-1.79 with no cache marker.

**What the amendment as written did to short documents.** It gave them real problems, each verified below and each
repaired in the revision:
- the slot rule as designed: an untrue "not documented" for a documented colonoscopy (T2); K4 switched off on an
  A-v6-shaped note (T3); "stated to be incomplete" for a complete enteroscopy (T5); a constructed false READY (T1);
- a declined short note re-sent, paid, after a release (CONN-1), and its member told "Nothing was sent" (T6);
- a short note cut at its output limit told it is too long, with advice it cannot follow (T7);
- an error-first stream held as a substituted model (CONN-4), a failed reading that could never be retried (CONN-5), a
  mid-stream cut that keeps no evidence (CONN-6), and up to 24 minutes stuck after a crash (CONN-7);
- a production cost 23-43% above the "with caching as measured" figure the owner would be given (F-COST-5);
- the replay, version and install defects R2-R8, which hit every document, short or long, and fb05's hold, which 5.2's
  repair could not release (T8).

Not short-document problems: the long-note claim bound (T4/R1/F-COST-1: short notes carry 41-108 claims), the deadline
cut (CONN-2: short streams run 110-286 s), and CONN-3's main shape (it needs a long partial stream; its error-event
variant applies to any document and is repaired with it).

**After the revision.** No short-document problem was found beyond the stated residuals: the three unnecessary holds
(G-NOISE, weighed on D3's counts); the cost and latency of a short note (about $1.0-1.9 and 2-5 minutes as production
pays); a re-upload of a declined document, which is a new member act that may be declined and billed again (1.5); and a
short note cut at its output limit, which C5 leaves to an operator's override.

## The findings

Each entry gives the claim, what the judge verified, the decision, and where the amendment changed.

### CONN-1 (critical): a declined request is re-sent, paid, by the first Resume after the release. ACCEPTED

- **Verified.**
  - `jobs.py:2489-2503` `_interpretation_failed_before` skips every effect but failed and too_long ("never a hold,
    which an operator's release ends").
  - `jobs.py:5646-5668` `retry_target` releases only FAILED and TOO_LONG runs.
  - `holds.py:287-305` `release` ends every standing hold at once.
  - `holds.py:201-226` `record`: a new sent run creates a new hold of its own.
  - `stage_interpret` (2886-2955) door order: `_settled_answer`, then `_retained_interpretation` (needs ANSWERED, so a
    decline is never reused), the unknown block, the failed-before door (skips the hold), `_settled_path`, then
    `_send_gates` (standing holds only).
  - So after a release, Resume or Retry (key `retry:`) sends the byte-identical request; it is declined and billed
    again, and pauses everyone again.
  - The reference says to surface a refusal and not retry with the same prompt (model-migration.md:453). The installed
    walk's `duplicateSends` would also report such a resend as a duplicate paid request.
- **Decided.** D275's installation-wide hold for a decline stays ("a refusal is a hold"). A *request-bound* hold is a
  decline, or a hold an `error` event set after `message_start`. For such a run, on both passes:
  - the failed-before door returns it for its identical request;
  - `retry_target` releases it only for an operator's recorded override (`retry_reading(override=True)`, the path C5
    gives a cut-off answer);
  - members get RETRY_DECLINED;
  - the release report names each held run, its encounter and its request.

  Every other hold (account, version or model) releases as today. The residual is stated: a re-upload is a new
  encounter and a new member act.
- **Changed.** 1.5 (the table, "Why each hold", "Never a paid resend", the new "Request-bound holds" paragraph, the
  holds.py bullet), 1.9 door 4, 9 (wording), 10 (F1, F6), 11.1, and the owner questions (item 3, recorded).

### CONN-2 (medium, plausible): the 1,320 s deadline turns a truthful TOO_LONG into UNKNOWN, and every reconcile pays again. ACCEPTED IN PART

- **Verified.**
  - `participants/http.py:397-407`: when the watch fires, `post` returns `_unknown(DEADLINE_READING)` with no bytes and
    no usage; `_read_capped` (492-501) raises on the deadline.
  - The reconcile queues the after-reconcile stage. `_settle_from_exchange` (2522-2552) needs a SUCCEEDED 200 exchange,
    and UNKNOWN is neither failed nor too_long, so the doors pass and a new attempt is sent.
  - Measured rates are 115.6-131.6 tok/s across F2 and F3 (F3long's long pass 2s ran at 130.9-131.2), and the largest
    measured answer is 79,758 tokens. A cut needs a stream that runs past 1,320 s: 128,000 tokens below about 97 tok/s.
- **Accepted.**
  - The bytes of a deadline cut are kept (with the `complete` hook), and its cost is an unknown cost (unpriced, counted
    at its bound).
  - Sections 1.12 and 3 now state the residual truthfully: such a stream is UNKNOWN, not TOO_LONG.
  - D1-D3 record every send's rate. If the slowest falls below 110 tok/s, the deadline is re-derived before A, at
    128,000 tokens at 80% of that rate plus 40 s, with the JOB, stale, STOP and queue settings following it.
- **Not accepted.**
  - Re-deriving the deadline now at 60 tok/s. That is about 2,170 s plus TTFT, with every threshold following: an
    install could wait about 40 minutes, and a stuck send would hold the single worker for 37. The residual needs an
    answer at least 38% larger than any measured one *and* a throughput 16% below the slowest measured. The measured
    trigger above covers it.
  - The finding's sense that each reconcile is a resend no one asked for. FINAL 6.9's reconcile is the member's
    recorded act for exactly one new attempt. That is unchanged and is now stated.
- **Changed.** 1.3, 1.5 (UNKNOWN row), 1.12 (deadline row), 3 (residuals), 10 (F1), 11.1, 11.2.

### CONN-3 (medium) = F-COST-3: partial usage is priced as final. ACCEPTED

- **Verified.**
  - `report.py:489-497` `estimated_cost` prices any non-empty usage of a sent, non-reused run, and `usage_sums`
    (441-459) counts it as priced.
  - `jobs.py:1201-1202` `_finish_run` copies the usage whatever the outcome.
  - `record_v2.py:645` (`elif exchange.outcome == 'succeeded' or usage:`) estimates from any usage.
  - Today `http._unknown` records no usage. The amendment's hook would have made the first unknown exchange that
    carries `message_start`'s `{44,740 in, 1 out}`, priced at about $0.36 against a bound of about $5.5.
  - The error-event variant (a stream that is complete, SUCCEEDED and classified FAILED) priced the same way.
- **Decided.** `describe` returns a usage only when a `message_delta` arrived. So every cut, early-ended or
  error-ended stream is unpriced in the report and counted at its bound by every harness ledger, and its
  `message_start` usage stays readable in the kept bytes.
- **Changed.** 1.3, 1.4, 1.7, 1.10, 8.3, 10 (F1, T), 11.1.

### CONN-4 (medium, plausible): an error-first 200 stream is read as "model absent" and holds the installation. ACCEPTED

- **Verified.** In the first text, 1.4 rule 3 (`message_start` comes first) and rule 7 (an `error` event ends the
  stream), with `complete()` True for an error-ended stream and 1.6's "absent ... is HOLD model, read before anything
  else", left an error-first stream claimed by two rows with no precedence. The reference documents in-stream overload
  errors.
- **Decided.** The precedence is stated in 1.5:
  1. a `message_start` naming another model or none, a fallback, or a stream that opens with neither `message_start`
     nor `error` is HOLD `model`;
  2. otherwise an `error` event decides by its type, so an error-first overload is FAILED, never HOLD `model`;
  3. otherwise a stream that does not assemble is FAILED;
  4. otherwise `stop_reason` decides.

  Rules 3 and 7 and section 1.6 are aligned with it, and there are tests.
- **Changed.** 1.4 (rules 3 and 7), 1.5, 1.6, 10 (F1), 11.1.

### CONN-5 (medium, plausible): section 9's list leaves `retry_target` on Gemini. ACCEPTED

- **Verified.**
  - By grep, `jobs.py` reads `interpretation.PROVIDER`, `MODEL` or `ADAPTER_VERSION_V2` at lines 1783, 2333-2336,
    2440, 2530, 2976, 5152, 5159, 5245, 5265 and 5655. The first text named four of them.
  - `retry_target` (5655) filters `provider='gemini'` (kept by 1.1), so it returns (None, None) and members get
    RETRY_NOTHING. A Resume is held by the failed-before door.
  - `_read_extraction` (2440) and `_extraction_of` (2976) name `ADAPTER_VERSION_V2` directly, so pass 2 would never
    follow a Fable pass 1.
  - `_loop_label` (1783) would name 'anthropic' in loop errors (against D22).
- **Decided.** The full list goes into section 9, each read via `_reading_*()`, or via `READ_PROVIDERS` with dispatch
  by adapter version when a stored run is settled. A guard test checks that no other line names the three, and F6
  gains Fable retry and resume rows.
- **Changed.** 9, 10 (F6), 11.1.

### CONN-6 (low): the `complete` hook never sees a real mid-stream cut. ACCEPTED

- **Verified.** `http.py:397-407`: an exception inside `_read_capped`'s `iter_content` goes to `_unknown` with no bytes,
  so the hook runs only for a body that ended cleanly. A chunked body cut without its terminating chunk raises
  requests' `ChunkedEncodingError` (the lens's local probe; consistent with urllib3's IncompleteRead). The first text's
  test could therefore be met by a fake session that ends cleanly.
- **Decided.** When the hook is set and the response is a 200, every early stop keeps the chunks read so far: a
  connection error, the deadline or the byte cap. A socket-level test covers this. Corti, Astra and Fable 5.1 pass no
  hook, so their behaviour is byte-identical.
- **Changed.** 1.3, 1.5, 1.10, 10 (F1), 11.1.

### CONN-7 (low): a worker crash during a short note leaves it stuck for up to 24 minutes. ACCEPTED

- **Verified.**
  - `jobs.py:5230-5233` `mark_stale` sweeps only RUNNING jobs older than the cutoff, and `busy` (5466) makes Resume,
    Retry and Reconcile refuse. With 1,440 s per kind, a 70 s-old short-note stage stays busy for about 23 more minutes.
  - `ops/install.py:4164`, the I-worker invariant: "at most one worker runs ... the new one starts only after the old
    one has exited (no stale-stage sweep races a live stage)".
- **Decided.** The worker's first sweep at start settles every RUNNING job whatever its age, since the invariant means
  no live peer exists. The periodic sweep keeps the per-kind threshold. No new column is needed (WorkerBeat holds no
  job binding).
- **Changed.** 1.12 (stale row), 10 (F6), 11.1.

### T1 (critical): the merged view releases a base_within hold (43235 READY beside a same-day EUS). ACCEPTED

- **Verified.**
  - Re-ran `demo_within.py` on the built engine. Under the true reading 43235 is held within X2, and under a 9.4
    weakening it is still held. Under the merged view (value None), `not_done_today(X2)` is True, `base_within` is
    empty, and 43235 is supported by E1 with no held fact.
  - `combination._claims_session` (1405-1412) reads only the claimed value ("never ... a contradiction's side").
  - `demo_within_contradicted.py` shows that the same release already exists for pass 1's own contradicted session.
  - The judge's `repair_check.py` shows the revised direction: with written sides plus `_claims_session` reading the
    sides, 43235 is held (possible whole X2), and the same holds for pass 1's own contradicted session, which releases
    43235 before the repair and holds it after.
  - Reachability: it needs an overfilled session slot and a planned or past examination filed in the done session's own
    session, which the probes have not shown (F3all filed its planned examinations with no session).
- **Decided.**
  - The merged view's options are the written values (4.3.3).
  - Claimed-value readers read a contradiction's sides as claims. This covers pass 1's own contradiction too, so the
    release already in the built tree is repaired in the same change.
  - 9.4's generator gains value-erasing contradictions, and P-MONO runs on them.
  - 4.3.8 keeps S1's whole-answer refusal for any attribute where the build cannot prove the properties.
- **Changed.** 4.2, 4.3.3, 4.3.8, 4.4, 10 (F3), 11.1, 11.3 (G-SCHEMA), E.2.

### T2 (high): an overfilled examination device makes a documented colonoscopy read "not documented". ACCEPTED

- **Verified.**
  - `pairing.digital_examination` (371-382) is `possibly(device, MANUAL) and not silent(device)`. Whole-domain options
    include `manual`, so E1 is never the examination.
  - `demo_digital_words` reproduces the member sentence "records no colonoscopy documented as done on the date of
    service".
  - `scan_devices`: Fable wrote `endoscope` on every examination event.
  - `repair_check.py`: with options = written values, `digital_examination` is False and 45378 is supported by E1 with
    nothing held, the true reading's outcome.
- **Decided.** The options are the written values, never a value pass 1 did not write. Claimed-value readers
  (`digital_examination`, `_digital`) exclude negated written values. The held item asks which device was used.
- **Changed.** 4.3.3, 4.3.7, 10 (F3), 11.1, E.2.

### T3 (high): the merged view switches off K4 (and K2's date arm and K5's documenting arm). ACCEPTED

- **Verified.**
  - `consistency.py:297-308`: `_value` and `_id` return None unless SUPPORTED.
  - `_k4` (591-608) reads the organ by `_value` and hits `continue`.
  - `_k2`'s examination-link and date arms (510-542) use `_id`, `_k5` (618-632) uses `_value` and `_id`, and K3
    (572-588) uses `_id` for the session.
  - A pass-1 contradicted organ also skips K4 today (pre-existing). This was traced in code, not executed: the
    claim-time merged view does not exist yet.
- **Decided.** Every K rule and L1 fires on each value a slot's fact states or offers (its supported value, each side
  of pass 1's contradiction, each written value of an overfilled slot that is not negated) wherever the firing demotes
  another fact. A plant test runs per K rule. Pass 1's own contradictions are repaired too.
- **Changed.** 4.3.3, 4.4, 8.1 (inventory label reason), 10 (F3), 11.1.

### T4 (high) = R1 = F-COST-1: long notes refuse at pass 2's claim bound after pass 1 is paid. ACCEPTED

- **Verified.**
  - F3all MANIFEST: A-note8 has 756 claims and C-C2MEM-023 has 711, both `pass2 not_built` ("more than the 640 one
    request may carry"), after pass 1 answered at 79,758 and 73,224 output tokens ($3.61 and $3.35 by the harness).
  - `claims.py:147` sets `CLAIM_BOUND = 640`, sized for Gemini's 32,768 tokens.
  - F3long (read after its 19:38:01Z freeze) ran under a bound of 1,000. Its `CLAIM_BOUND_SHA256` is
    `3fe08a5c...`, which the judge computed to be the sha256 of `{"claims_per_request": 1000}`.
  - In F3long, both pass 2s answered in one request each: 77,483 and 70,263 output tokens (61% and 55% of 128,000),
    38,113 and 37,844 input tokens, 590.7 s and 536.9 s, established 336/340 and 317/322, controls not rejected 0/303
    and 2/288. Its score was 10 correct and 7 unnecessary holds, with no wrong READY and no wrong exclusion.
  - So section 3's "545 claims ... under the 640 bound" is false, and GI Note #8 would have ended TOO_LONG after a paid
    pass 1.
- **Decided.**
  - `claims.CLAIM_BOUND_V3 = 1000` on this path, with its own pin `CLAIM_BOUND_SHA256_V3` written by F0 before D1. So
    `gemini-appraisal@2`'s first recording is made under it (D202), appraisal@1's 640 is untouched, and any later change
    is appraisal@3.
  - G-SIZE gains a per-claim line (pass-2 output per claim on the long notes at most 108.8, so a set at the bound fits
    85% of 128,000; measured 98.8-102.5). FINAL-V2's pass-2 remedy ("fewer controls on attributes that can only hold")
    is restored, since the compact form changes no claim count.
  - Costs and latency are corrected: a long note costs $6.11-7.10 and takes 18-20 minutes.
  - No class-b question is needed, because GI Note #8 is read in full.
  - The residual (a claim set over 1,000 after a paid pass 1) is stated. The long notes' 0.0365-0.039 claims per
    character put a 20,000-character note at about 730-780 claims.
- **Changed.** E.1, E.3, 1.9, 1.12, 2.4, 3, 7.1, 7.3, 7.4, 8.2, 8.3, 10 (F0, F2, F3), 11.2, 11.3, Appendix.

### T5 (medium): an overfilled completion slot is worded "stated to be incomplete". ACCEPTED

- **Verified.** `classes._claims` (453-457) reads a contradicted fact's options as pass 1's own sides, and
  `_completion` (634-642) sets `stated` from them. `demo_completion_route` reproduces "reached the ileum and is stated
  to be incomplete" for [complete supported, terminated negated].
- **Decided.** The options are the written values. Readers of what pass 1 stated read the options less the negated
  ones, so a denied value is never worded as stated.
- **Changed.** 4.3.3, 4.4, 10 (F3), 11.1, E.2.

### T6 (medium): a declined or refused request tells its member "Nothing was sent". ACCEPTED

- **Verified.**
  - `jobs.py:2779-2789` `_settle_outcome` raises `StageCancelled(PAUSED_MESSAGE)` for the run whose answer set a
    standing hold, and `mark_stale`'s settled path does the same (5199-5202).
  - `holds.py:97`: PAUSED_MESSAGE says "Nothing was sent".
  - This was already untrue for a Gemini hold set by a sent 401. A billed decline makes it plainly untrue.
- **Decided.**
  - The triggering run is worded from itself: DECLINED_MESSAGE (stage FAILED, action `none`) for a request-bound hold,
    and HOLD_SET_MESSAGE (CANCELLED, read as paused) for any other.
  - PAUSED_MESSAGE stays for the runs a standing hold kept unsent.
  - No provider or model is named, and the denylist readers run on the new sentences.
- **Changed.** 1.5, 9 (wording), 10 (F6), 11.1.

### T7 (medium): a short note cut at `max_tokens` is told it is "too long". ACCEPTED IN PART

- **Verified.**
  - `progress.py:131-132` and RETRY_TOO_LONG (`jobs.py:5641-5642`) say "too long ... shorten it or split it".
  - `_reading_situation` (`progress.py:424-425`) maps every TOO_LONG effect to `too_long`.
  - `INTERPRET_CUT_OFF_MESSAGE` (`jobs.py:2192`) asserts that the document is too long.
  - C5 is the ruling.
- **Accepted.**
  - The member sentence for an answer cut at its output limit says that limit was reached, never that the document is
    too long: progress gains the `cut_off` situation and RETRY_CUT_OFF, and the cut-off messages are revised.
  - The size and claim bounds keep the `too_long` sentences.
  - D2 and D3 measure the short-note output tail.
- **Not accepted.** Reclassifying a short note's cut as FAILED with a member retry. C5's ruled effect stands: a cut
  costs about $5.6, and the identical request may well stop there again. An operator's recorded override remains the
  way to re-send.
- **Changed.** 1.5 (table and the new paragraph), 3, 9, 10 (F6), 11.1, 11.2, 11.4.

### T8 (medium): 5.2's repair cannot release B-fb05 45380. ACCEPTED

- **Verified.**
  - `engine/requirements.py:733-734` claims `target.structure` only for drainage and EUS injection.
  - `engine/coverage.py:900-940`: `_same_lesion` and `_apart` read only `target.lesion` and `target.places`.
  - The frozen replay settles E4's structure as unresolved, `unappraised`.
- **Decided.**
  - 2.1 item 3 (TARGETS) is withdrawn, so `INSTRUCTIONS_3` carries four changes and sits closer to F3all's measured
    text.
  - 5.2 is rewritten: the hold is correct by design, with no repair here.
  - A release needs a CLAIMED row, a control and a bundling rule, designed and refuted on its own and weighed on D3's
    counts.
- **Changed.** 2.1, 5.2, 10 (F2).

### T9 (low): the date slot has no domain for the merged view. ACCEPTED

- **Verified.** `extract_schema.py:238`: `events[].date` is a SLOT holding an ISO date with no Enum, and the engine's
  `facts.DOMAINS` gives it `_DATE`, which cannot be enumerated.
- **Decided.** Through T1/T2's change, the merged view's options are the written values, here the written dates, and
  L1 runs on each.
- **Changed.** 4.3.3, 11.1.

### R1 (high): long notes cannot build pass 2 under 640, and raising the bound after D1 moves a pin with no new label. ACCEPTED (with T4)

- **Verified, beyond T4.** `interpretation/__init__.py:98-100`: `CLAIM_BOUND_SHA256` and `HEALTH_THRESHOLDS_SHA256` are
  single names shared with `gemini-appraisal@1`, which has recordings (D1v, D1w). Under D202, changing their objects
  under those names moves a recorded label.
- **Decided.** Separate `_V3` pins (`CLAIM_BOUND_SHA256_V3`, `HEALTH_THRESHOLDS_SHA256_V3`). The bound is written
  before D1, so D2's long notes are never recorded as door-0 refusals that later replay with no recording.
- **Changed.** As T4, plus 8.2 and 8.3.

### R2 (high): the installed walk's verifier still checks for Gemini, and CI holds it there. ACCEPTED

- **Verified.**
  - `ops/verify_browser.cjs:192, 198, 201` hold the constants, checked at 2690-2716; `releasedForRetry` (2503-2511)
    knows only provider `gemini`.
  - `ops/verification/test_verify_browser.cjs:3833, 4377-4379` pin them, with the regex `^NAME = '...'`, to
    `PROVIDER`, `MODEL` and `ENGINE_VERSION_V2`, which keep Gemini's values.
  - No step owned the file.
- **Decided.** F8 owns the walk and its test pins, which read `PROVIDER_V3`, `MODEL_V3` and `ENGINE_VERSION_V3` and
  still accept @2 rows as stored.
- **Changed.** 8.1, 9, 10 (F8), 11.1, 11.4.

### R3 (medium): verify fails whenever the Fable participant is live and the interpreter is not. ACCEPTED

- **Verified.**
  - `ops/install.py:7181-7186` `holds_interpreter_key` compares the bind with `INTERPRETER`'s target and mount, which
    1.11 made the participant's.
  - 7236-7237 flag a bind when the mode is not live.
  - The installer's own advice at 7232-7233 ("--interpreter-mode disabled to keep it paused") would then fail verify.
- **Decided.** Verify expects the shared file when the Fable participant or the interpreter is live, and reports a bind
  only when neither is. D14 is unchanged.
- **Changed.** 1.11, 10 (F8), 11.1.

### R4 (medium): the label moves in 8.1 cannot be built inside the file plan. ACCEPTED

- **Verified.**
  - The tree's names are at `interpretation/__init__.py:49-61`. The first text's 8.1 named `INTERPRETATION_VERSION_V3`,
    `APPRAISAL_VERSION_2` and others with "now" values that the tree does not have.
  - Every non-test reference was found by grep: jobs, review (335/359/394/1289), store (818-819), assess
    (165/180/186/717-718/1587), coverage (231), readers (65/67), overlay (176), report, appraise_read (114), settle
    (229), extract_read (187), extract_prompt (491) and appraise_prompt (268/417). derive and serializers read
    `ROUTING_VERSION_V2`, which is unchanged.
- **Decided.**
  - New names, as 1.1 rules: `INTERPRETATION_VERSION_V3`, `APPRAISAL_VERSION_V3` (`gemini-appraisal@2`),
    `INVENTORY_VERSION_V3`, `ENGINE_VERSION_V3`, `INTERPRETATION_PAIR_V3` and `ADAPTER_VERSION_V3`.
  - Writers write only the new labels, and readers of stored rows accept both families.
  - Every reader and writer is listed with its owning step (assess.py, coverage.py: F3; readers.py, overlay.py,
    review.py: F6; appraise_read.py: F2), and a guard test is added.
- **Changed.** 8.1, 10 (F0, F2, F3, F6).

### R5 (medium) = F-COST-4: development and acceptance spend run on the installed site's live Anthropic account with no reserve. ACCEPTED

- **Verified.**
  - `provider_holds.py:86-103`: a participant's sent 4xx other than 413 sets an installation-wide hold (reason
    `refused` for a 400).
  - AMENDMENT-1 A20 (7.3's table) records that Anthropic answered an exhausted credit balance with HTTP 400.
  - D275 and D183 create no separate key.
  - record_v2's project threshold can keep a site reserve, but D183 forbids a ceiling of the session's own.
- **Decided.** 7.5's package to the owner gains the account's configured limit or balance (stated by the owner, never
  read), the installed site's monthly Anthropic usage and the headroom, with the exposure stated. Whether to keep a
  reserve is the owner's decision, and `none` applies only on the owner's word.
- **Changed.** 1.5 ("Why each hold"), 7.5, 8.3, the owner questions (item 2).

### R6 (low): the D15 rollback check still counts @2 and `gemini` rows. ACCEPTED

- **Verified.** `ops/rollback_check.py:360-391` filters with `V2_ENGINE = 'cpt-studio-events@2'` and
  `provider = 'gemini'`.
- **Decided.** F8 changes both literals: both engine versions, and the provider matched against `READ_PROVIDERS`.
- **Changed.** 8.5, 10 (F8), 11.1.

### R7 (low): pass 2 ships its schema in another key order than the one measured. ACCEPTED

- **Verified.**
  - `providers/base.py:40-42`: `canonical_body` uses `sort_keys=True`, and those are also the bytes sent.
  - `probes-fable/fable_record.py:128` sends `json.dumps(body)` in insertion order.
  - The schema's declared order is claim, verdict, attached, qualifiers, evidence; sorted, it is attached, claim,
    evidence, qualifiers, verdict.
  - The cached reference does not say whether structured outputs follow the order of `properties`.
- **Decided.**
  - The pass-2 evidence is labelled as the declared order's, and D1-D2 measure the shipped canonical order through the
    connector.
  - If G-HEALTH falls because of it, the remedy is property names whose sorted order is the intended order, as
    appraisal@3, never a body that is not canonical.
  - 1.2's "sent exactly this object" is corrected.
- **Changed.** E.1, 1.2, 2.2, 11.2, 11.3 (G-HEALTH).

### R8 (low): the interpreter's API version follows the participant's and appears in no label or record. ACCEPTED

- **Verified.** `participants/anthropic_fable.py:77` sets `API_VERSION = '2026-10-21'`. The first text pinned the
  interpreter's value equal to the participant's, and the header is outside the request body and its sha256.
- **Decided.**
  - The value is part of what `ADAPTER_VERSION_V3` names, pinned beside it and never to the participant's, so a change
    is a new adapter version and the doors stop reusing across it.
  - Each run records the value in `scope.api_version`.
  - replay_v2 refuses a recorded batch of another adapter version.
- **Changed.** 1.1, 1.2, 8.3, 8.4, 10 (F0, T).

### F-COST-1 (high): the long-note cost and latency figures rest on 545 claims. ACCEPTED (with T4)

- **Verified, beyond T4.** The judge priced F3all's and F3long's usage at 1.7's rates:
  - a long note's pass 1 costs $3.00-3.26 on a cache hit and $3.44-3.70 on a write;
  - its pass 2 costs $3.11-3.40;
  - both passes cost $6.11-7.10 and take 566-615 s plus 537-591 s.

  The model was refit: claims = 40.5 + 0.0357 x chars and pass-2 input = 3,240 + 47.3 x claims (`judge-scripts`). The
  lens's own pass-2 input estimate (32,072 tokens) was low against the measured 37,844-38,113. Its conclusion holds.
- **Decided.** Sections 3, 7.1, 7.3 and 7.4 and 1.12's latency are recomputed, and G-SIZE is revised (as T4).
- **Changed.** As T4.

### F-COST-2 (medium): the owner's figure for A has no mechanism. ACCEPTED

- **Verified.**
  - `record_v2.py:570-571` `Batch.gate` stops only once `spent >= cap`, and its docstring says it "can pass the cap by
    at most one send".
  - With `--provider-cap-usd none` and per-batch guards of about 2 x the model, nothing compared A's running total with
    the owner's figure.
  - The owner's class-d figure (D275) is the owner's ceiling, not one of the session's own (D183).
- **Decided.**
  - A is sent only by a tool that enforces the owner's figure as one cap over all of A, checked before every send as
    spend plus that send's worst-case bound. A' gets its own figure.
  - This is a stated property of the acceptance owner's tool (FINAL-V2 9.6), checked by the integration owner before A.
- **Changed.** 7.5, 8.3, 10 (T), 11.4, the owner questions (item 1).

### F-COST-3 (medium): an incomplete stream's partial usage is priced as a whole answer. ACCEPTED (= CONN-3)

- Decided and changed with CONN-3.

### F-COST-4 (medium): A shares the installed site's account with no reserve and no check of its headroom. ACCEPTED (= R5)

- Decided and changed with R5.

### F-COST-5 (low): the caching totals assume every pass 1 hits. ACCEPTED

- **Verified.**
  - prompt-caching.md:148 says the cache lifetime runs from the start of the request and that generation time counts.
  - F3all used a 1-hour TTL (`ephemeral_1h_input_tokens` 44,466; `fable_record.py:112`).
  - F3all's pass-1 starts were 109.7-285.5 s apart for the short notes, and 615.8 s for C2MEM-023 after A-note8.
  - Production pricing of the short notes is $1.03-1.87, against $0.59-1.44 on a hit.
- **Decided.**
  - A production column is added to 7.1, and A's total is shown as a range from all hits to all writes (7.3).
  - The pass-1-first order for A is the acceptance owner's tool's, so the range stands unless that tool sends pass 1
    first.
  - 7.5 hands the production figure to the owner apart.
  - 2.4 no longer weighs caching's $0.35 against the compact form.
- **Changed.** E.1, 2.4, 7.1, 7.2, 7.3, 7.5, Appendix.

### F-COST-6 (low): the reservation "at its worst case" is below the worst case. ACCEPTED

- **Verified.**
  - A pass 1 that writes the cache and runs to 128,000 tokens costs 44,466 x $10/M, plus the uncached input at $8/M,
    plus $5.12: $5.57-5.64, not $5.48.
  - A pass 2 at the bound costs about $5.52.
  - D1's $3 guard is checked as "spent reached the guard", so D1 can reach about $8.6.
- **Decided.** The reservation is computed from the body, with the prefix at the write rate. 7.4 states each guard's
  real maximum (the guard plus one worst-case send) under D183's runaway-stop semantics. The reservation-checked cap is
  reserved for A (the owner's figure).
- **Changed.** 7.4, 8.3, 10 (T), 11.2, Appendix.

### F-COST-7 (low): the Batches row assumes the sequential chain's cache hits. ACCEPTED

- **Verified.** A batch is processed in any order, and its cache hits are best effort; the reference advises the 1-hour
  TTL there. Half of the all-write total is about $330 (347 documents).
- **Decided.** The row shows about $254-330 (347) and $473-613 (645), with hits stated as best effort.
- **Changed.** 7.3.

### F-COST-8 (low): the installer's access check is refused while a reading holds the provider lock. ACCEPTED

- **Verified.**
  - `participant_access_check.py:94-106` `_single_flight` takes `pg_try_advisory_lock` and refuses with "Another
    provider request is in flight".
  - `jobs.py:1578/1654`: `_send` holds that lock for the whole send, now up to 1,320 s.
  - Access checks run after the new worker starts.
- **Decided.** The access check waits for the lock, polling, for up to the send deadline plus 60 s, and the installer's
  timeout covers that wait. F8 owns `participant_access_check.py`.
- **Changed.** 1.11, 10 (F8), 11.1.

## Questions only the owner can decide

1. **A's budget (class d; D275).** The owner sets the figure for A, and for A' if he approves one, from the corrected
   range:
   - 347 documents: about $509 with every pass 1 a cache hit, $629 with no cache marker, and $660 as production pays
     (every pass 1 writes the cache). With long notes cut at 128,000 tokens it can reach $614-765.
   - 645 documents: about $945-1,226, up to $1,142-1,423.
   - The Batches option: about $254-330 for 347 documents. It needs its own transport and reader to be built first.

   Whatever figure he sets binds as a cap, checked before every send.
2. **The Anthropic account's headroom and a site reserve (class d).**
   - The owner states the account's configured monthly limit or prepaid balance; the session cannot read it. It is set
     against the installed site's monthly usage, about $155-195 for D1-D3, and A.
   - The owner decides whether the harness keeps a reserve for the installed site's Fable 5.1 second reader. That
     reader shares the account, and it would stop for every upload if the balance ran out mid-batch.
   - D183 forbids the session to set a ceiling of its own, so without the owner's word the harness runs with no reserve
     and the exposure stands.
3. **Recorded, not asked.** D275's "a refusal is a hold" means one declined document pauses every customer's reading
   until an operator reviews it. This revision keeps that and adds the request-bound block. If the owner prefers a
   decline to hold only its own document, that is a product decision (class a).

## For the integration owner, before the build

- F0 writes `CLAIM_BOUND_SHA256_V3` (`3fe08a5c...`) before D1. Every later bound change is appraisal@3.
- F3's list of readers decides the slot rule attribute by attribute (4.3.8). An attribute whose properties cannot be
  proven keeps the whole-answer refusal. The instruction fix alone took the measured slips to 0 of 10 (F3all).
- The mandatory refutation of the finished diff (FINAL-V2 9.8) should give the revised 4.3.3 its own lens. Its reader
  kinds and the K-rule reading are new code on the clinical generation path, and they also change how pass 1's own
  contradictions are read.
