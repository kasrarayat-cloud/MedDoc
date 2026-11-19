# FINAL-V2 amendment 1, second refutation: judged

**What this is.** The judge's record for the bounded second refutation of FINAL-V2 amendment 1's revision, written
2026-11-12. Two lenses reported 16 findings on the revised `AMENDMENT-1.md`: binding, races, duplicates and holds
(`refute2-binding.md`, R2B-1 to R2B-8) and truth, exports, the screen and confidentiality (`refute2-truth.md`, RT1 to
RT8). Each finding's premises and wrong outcome were checked against the code before it was decided. The owner's words
(`gemini-migration/owner-autorecheck-20261112-verbatim.md`) governed every judgement. Where the amendment disagreed with
them, the amendment was wrong.

## Inputs

| input | sha256 |
|---|---|
| `AMENDMENT-1.md` as refuted, at the start of this judgement | `2f0699485de0bd85f945c38c3d1296d3caf620f785a6d0959547a096a3edcf1a` |
| `r2/AMENDMENT-1-r1.md`, its copy made first (163,794 bytes, 2026-11-12T11:45:32Z) | `2f0699485de0bd85f945c38c3d1296d3caf620f785a6d0959547a096a3edcf1a` (equal) |
| `AMENDMENT-1.md` as revised by this judgement (194,741 bytes) | `3ba391192e6b7f763d5185e2a7c69d42daacd08604d48e1ffad8834b0adf07b8` |
| `r2/refute2-binding.md` | `5787381c350d615e921c9f53001d464155f11fc0f6ef1b9404b513c589846479` |
| `r2/refute2-truth.md` | `33afdc00105e66eee8363379c4633824504b3c24d751560fff7dc219dc9bc053` |
| `owner-autorecheck-20261112-verbatim.md` | `65cb0be8ceb1aaf20acb3095f84860a140692f95e0263cfc24102daf5f961c13` |
| `AMEND-REFUTATIONS.md` (the first judgement) | `8cbed069c5c7713fe681fa1c8ca6606916b6feef0b2a22bd7b100e452d35e2b0` |
| `refute-races.md`, `refute-truth.md`, `refute-legacy.md` | `71a81e98…`, `471f6d59…`, `824c8fd0…` |
| `AMENDMENT-1-pre-refutation.md` | `fd8167ac6a1b9a13172a63d94b8c7c514d25098da0882c7931a4aabb9448895d` |

The code: branch `feat/cpt-studio-gemini-interpreter-20261109` at `c0d6d52a7f7066d77382fe9576a8e1a4de5b2eab` (the worktree
`/opt/meddoc-pro/.worktrees/cpt-gemini-20261109`, read only; its HEAD read with `git rev-parse HEAD`). The files read:

- `studio/jobs.py`, `review.py`, `answers.py`, `api.py` and `progress.py`;
- `customer_api.py` (`FORBIDDEN`, `code_rows`), `models.py`, `providers/corti.py` and `providers/base.py`;
- `participants/anthropic_fable.py` (header and status handling);
- `interpretation/assess.py` (participant admission, `disagreements`, `_fingerprint`), and `static/studio/app.js`
  (`emptyResults`, `tallyText`);
- `HARNESS.md` (11.1, 11.3, 12.10, P-ADMIT), and `docs/gemini-migration/FINAL-V2.md` (1.2's `[S\d+]` rule, 6.5).

## Method

- **Every finding.** The cited code and the revised text were read, and the sequence's premises and its wrong outcome were
  confirmed or refuted. Each finding was then accepted, accepted in part or rejected. A finding outside the revision's
  scope, or with an unsupported premise, was rejected, and the record says which.
- **Every accepted finding.** The narrowest change that closes it was made to `AMENDMENT-1.md`, tagged
  `[R2:<lens>-<id>]`. Refusing, holding or failing truthfully was preferred to a new mechanism, and nothing was made
  approvable or exportable that was not before. New decisions are A19 and A20.
- **Every changed passage was re-read** against the owner's words, the first round's 30 fixes and J1. Three defects in
  this judge's own fixes were found and repaired (J2, J3, J4, below).
- **Checks run.** The new customer strings were matched in the scratchpad against a verbatim copy of
  `customer_api.FORBIDDEN`: 12 strings, 0 hits. The scripted reflow of 8 over-long lines asserted its own count.
- **What was not done.**
  - Nothing was built, run against the application, sent to a provider, installed, or run in docker.
  - No git command changed the worktree.
  - None of these was opened: a sealed set, `acceptance-a1/`, `g1-stage`, `walk-c6`/`walk-c7`, `docs-c6`/`docs-c7`, or
    the acceptance directory.

## Result

| outcome | count | findings |
|---|---|---|
| accepted | 14 | |
| accepted in part | 1 | RT2 |
| rejected | 1 | R2B-8: its premise is unsupported, and what remains is outside the revision's scope |

- **Critical findings:** 4, all acted on. R2B-1, R2B-2 and RT1 were accepted, and RT2 in part.
- **New decisions:**
  - **A19:** a restore applies only to earlier codes that can be current again as they stand.
  - **A20:** one classification of the refusals that set a provider hold, where the hold is recorded, and what a
    hold-setting run is.
- **Amended:** A3, A4, A10, A16, A18.
- **Own-fix defects found and repaired:** 3 (J2, J3, J4).

## Summary

| id | lens | severity | decision | where the amendment changed |
|---|---|---|---|---|
| R2B-1 | binding | critical | accepted (the hint's first option) | A16, A20; 3.5; 7.3 "Where the hold is recorded"; 10 (`provider_holds.py`, `jobs._send`); U20 |
| R2B-2 | binding | critical (lens: PLAUSIBLE) | accepted | A20; 7.3 table (a participant's any 4xx but 413, reason `refused`), "Shape", "What a held stage does" (the cost); 10; pinned behaviours; U20 |
| R2B-3 | binding | high | accepted (the hint's second option); J2 | vocabulary (`earlier`, `update pending`); 4.5; 6.2 step 4 (J2); 10; U11, U22 |
| R2B-4 | binding | high (lens: PLAUSIBLE) | accepted, fix is the hint's alternative (with R2B-5); J3, J4 | A3, A19; 1.3; 1.4 (RESTORE_REFUSED); 2.5; 3.10 item 7; 5.1 (`update.restorable`); 7.1 (J3); 7.5; 9.1; 10; U8 |
| R2B-5 | binding | high | accepted (with R2B-4); J3, J4 | as R2B-4, and A18's sentence |
| R2B-6 | binding | high (lens: PLAUSIBLE) | accepted | 3.7; 7.2 (last paragraph); 10 (`mark_stale`; pinned behaviours); U9 |
| R2B-7 | binding | medium | accepted | A4; 2.3 (coalesced); 3.10 item 5; 10; pinned behaviours; U5 |
| R2B-8 | binding | medium | rejected (premise unsupported; the rest outside scope) | none (R2B-2's change states the hold's cost) |
| RT1 | truth | critical | accepted (wider than the hint) | A10, A16, A20; 7.1 (not-sent and held rows); 7.2 (hold bullet, every-other-outcome bullet, retry paragraph); 7.3 (table, "One classification"); 10; U20 |
| RT2 | truth | critical | accepted in part | A20; 7.3 ("After the release", "Refusals recorded before the install", the stated limit); 9.5; 10; U20 |
| RT3 | truth | high | accepted (the hint's first part) | 5.2; 10 (`progress.py`); U16 |
| RT4 | truth | high | accepted | 5.1 (JSON `outcome`); 6.2 step 4; 10; U11 |
| RT5 | truth | high | accepted | 6.2 step 5; 10; U11 |
| RT6 | truth | medium | accepted | A16; 7.1 header (PROVIDER_PAUSED); 7.2 (last paragraph); 7.3 "What a held stage does"; 10; pinned behaviours; U20 |
| RT7 | truth | medium | accepted | 1.4 (addenda); 10 (`api.py`, `customer_api.py`); U14 |
| RT8 | truth | low | accepted | 5.1 (results section); 10 (`app.js`); U21 |

---

## The findings

### R2B-1 (critical): nothing records the provider hold when the refusing stage ends without recording it

**Claim.** The revision names no writer of the provider hold outside 7.2's list for an update. A worker killed between a
refusal's recorded outcome and its stage's decision leaves the refusal with no hold, so the next encounter's request is
sent and refused again. The same happens to a first processing's refusal and to a superseded predict's.

**Verified.**
- `jobs._send` (1187-1290) calls `provider.send` (1269), then `_finish_run(run, exchange)` (1271), with no enclosing
  transaction: `run_job` (3643) wraps none. The outcome is therefore committed before `stage_predict` decides (its
  `next_assess(run)` is at 1184), and the provider lock is released in `finally` (1288).
- The revised 7.2 reads the hold only inside its list "while an update is pending", and says a first processing's
  `stage_predict` is "unchanged, except that Corti's provider hold is read at its send door".
- The revised 3.7 left `mark_stale` unchanged. It settles a finished predict run by `_after_predict` (3818-3822).
- `_failed_before` (641) is per encounter.
- D53's `_record_unsettled_holds` (3691, called at 2262) closes exactly this class for the interpreter.
- A participant's exchange is committed in a transaction of its own as it ends (`_record_exchange`, 1490); the run's
  outcome follows in `_finish_loop` (1457).

The wrong outcome holds: a request is sent after a payment, quota or authentication refusal, against A16's own claim.

**Decision: accepted.** The fix is the hint's first option: the hold is written with the outcome.
- `jobs._send` records it in the same transaction as the record that carries the status: `_finish_run` for Corti, and
  the exchange record for a participant (`_record_exchange`, or `_finish_loop` for the exchanges it records).
- That holds whatever the stage's state: a first processing, an update, a stage superseded while it sent, or one whose
  worker dies right after.

The hint's second option, a D53-shaped sweep before every send door, was not taken. A sweep over runs classified by
their status would also have set holds from every refusal recorded before the install (RT2's population) at the first
send after the install. With R2B-6, the stale path finds the hold already recorded.

**Revision.**
- A16, and A20's second sentence.
- 3.5: a late finisher's refusal sets the hold.
- 7.3: a new paragraph, "Where the hold is recorded".
- 10: `provider_holds.record` is called by `jobs._send`.
- U20: a kill right after a 402; a 402 in a first processing; a 402 answering a superseded predict.

### R2B-2 (critical; the lens marked it PLAUSIBLE): a payment refusal under another status

**Claim.** A16's table holds a participant only on 401, 402, 403 or 429. Anthropic has answered an exhausted credit
balance with HTTP 400, so Fable's requests repeat after a payment refusal.

**Verified.**
- `participants/anthropic_fable.py` records each exchange's status (399-417, `RawExchange(..., http_status=status)`), and
  `jobs._record_exchanges` stores it.
- A 400 is FAILED under I10: the chain goes on, `_failed_before` holds only the identical request in the same encounter,
  and every other encounter's request is sent.

The premise is the vendor's behaviour and is not measured in the repository. Anthropic's Messages API has answered an
exhausted credit balance with `400 invalid_request_error` ("Your credit balance is too low to access the Anthropic
API…"), and D39 records the same class for Gemini: a spend cap read as a rate limit. A table resting on an unmeasured
status is the assumption D39 retired. The wrong outcome holds under the premise, and it is the owner's "Handle quota and
payment failures without repeated requests".

**Decision: accepted.**
- The fix is fail-closed. A participant exchange answering any 4xx but 413 sets that participant's hold, with the new
  reason `refused` for a status outside 401, 402, 403 and 429. A 413, the request's own size, fails only that request.
- The hint's option of reading the vendor's structured error fields was not taken. Anthropic's `error.type` is
  `invalid_request_error` both for the credit refusal and for a request-specific 400, so telling them apart needs the
  message text, which section 10 rules out.
- The cost is stated in 7.3: a request-specific 4xx then stops that participant's checks on every encounter until an
  operator's release.
- Corti's coding-endpoint statuses were not attacked and are unchanged. The same unmeasured-status caveat applies to
  them (see "For the adoption").

**Revision.** A20; the 7.3 table, "Shape" and "What a held stage does"; 10 (`provider_holds.py`, pinned behaviours);
U20 (a Fable 400 holds, a 413 does not).

### R2B-3 (high): a reconciliation after a completed update reads as "Changes saved—updating codes"

**Claim.** An operator's reconciliation of a participant run after a completed update restarts the chain. Its assess #1
becomes current while the encounter is fresh. `earlier()`'s second branch then returns the context's recorded E, so the
page reads an update pending against the codes from before the previous, completed update.

**Verified.**
- `jobs.reconcile` (4046-4098) restarts the chain on the current context: `_after_predict(..., origin=f'reconcile:{run.pk}')`
  at 4092.
- The chain's assess #1 is persisted while fresh. A17 applies only "while an update is pending", and today's persist
  makes every assessment current (verified in round 1).
- `earlier()`'s second branch then returns `C1.earlier_assessment` = E. `update pending` holds for the whole peer phase,
  so the panel, `update.changes`, `started_at`, UPDATE_DECISION and the stopped text's restore offer all follow.
- The branch predates the revision. The revision, however, re-justified it (4.5: "no longer meets that state under A17;
  it stays for a state an older image wrote"), and the defect lies in how A17's scope interacts with the tagged
  `earlier()` text, so it is in scope.

**Decision: accepted.**
- The fix is the hint's second option. The second branch of `earlier()` and of `earlier_for_new_context` applies only
  when the current assessment is not on the current context. A re-run chain's assess #1 on the current context is then
  processing, as today, and never an update.
- The hint's first option was not taken. Generalizing A17 so that a non-final assessment never displaces a final current
  one would make the last final approvable while its re-run chain runs. Today the re-run's assess #1 is current there and
  nothing is approvable, so that option would widen what is approvable.
- See J2 for this fix's consequence in "what changed".

**Revision.** The vocabulary (`earlier`, `update pending`); 4.5 (the code and a bullet); 6.2 step 4 (J2); 10; U22 (new);
U11.

### R2B-4 (high; the lens marked it PLAUSIBLE): save, reconcile, restore leaves E "being confirmed" with nothing pending

**Claim.** E's Corti read ended unknown and a save started an update, which waits on that unknown outcome. The operator
reconciles it, then a restore lands before the released predict runs. E comes back current with its reconciled unknown
run, reading provider_unknown with nothing pending and no way out.

**Verified.**
- `reconcile` refuses an already reconciled run (4070) and queues `predict:<context>:after-reconcile:<run>` (4094).
- `_run_in_use` leaves a reconciled unknown out (4290).
- `review._state_and_run` reads `run.state in UNSETTLED_RUN_STATES or unknown` as provider_unknown (1779), whether or not
  the run was reconciled.
- 2.5's restore makes E fresh, so the reconciliation's predict is superseded at its start.
- No Resume is offered (the state is not stopped), `retry_update` answers RETRY_UPDATE_NOTHING (the encounter is fresh),
  and `reconcile` returns None. The variant with the reconciliation first holds the same way.

**Decision: accepted.** The fix is A19, the hint's alternative of refusing the restore: a B whose document review is a
reconciled unknown outcome is not restorable.
- In case A, the save is an ordinary change. Its predict sends B's request as the released attempt.
- In case B, the save is refused (J4).

Counting the reconciliation's attempt among A18's member-act stages (the hint's first option) was not taken alone, for
two reasons:
- A Stop lifts A18's refusal, and the reconciliation's predict belongs to the update's context, which is not a target job
  of the restored state. A Stop followed by a restore would strand E the same way.
- The participants' chain a reconciliation starts carries no key mark that A18 could read.

**Revision.** A3 and A19; 1.3; 1.4 (Added, A19); 2.5 (the condition and its paragraph); 3.10 item 7; 5.1
(`update.restorable`); 7.1 ("No restore where A19 refuses one", J3); 7.5; 9.1; 10; U8.

### R2B-5 (high): a details save that replaces a "Not documented" answer revokes it, and a restore brings it back

**Claim.** A details save that gives a value in a row answered "Not documented" revokes that answer in the same save
that starts an update. A restore then makes E current still reading the revoked answer, and STALE_ANSWER_BLOCKER stands
with nothing queued.

**Verified.**
- `answers._save_details`: a value given in a row answered "Not documented" puts that answer in `superseded` (853),
  writes a `MemberAnswerRevocation(SUPERSEDED)` (878-880), then calls `change_context` (882).
- The narrowed refusal refuses only a save that records a `MemberAnswer`, so this save is accepted, both when fresh and
  during a case-B update, whose rows stay drawn.
- `_reads_a_withdrawn_answer` (1314) is what raises STALE_ANSWER_BLOCKER (194, 1347).
- After the restore nothing is queued, and there is no Resume and no Retry. A18's "a restore never brings back codes
  that read an answer whose change was never applied" is false.

**Decision: accepted.** The fix is A19: a B that reads an answer that no longer stands is not restorable. In case A the
save is an ordinary change, whose chain reads the answers that stand and reuses E's Corti request. In case B it is
refused (J4).

The hint's recompute option was not taken. `recompute_after_answers` returns None on a legacy context after the install
(4634-4637), so it closes only a v2 B, and it adds an act on restore. The ordinary change closes both kinds of B in case
A with no new act.

**Revision.** As R2B-4, and A18's sentence.

### R2B-6 (high; the lens marked it PLAUSIBLE): the stale sweep queues the assess after an update's failed, unsent or held predict

**Claim.** `mark_stale` was left unchanged. For a predict whose worker died after the run's outcome was recorded, it
queues the successor whatever the run says. An update's failed, unsent or held document review then replaces the earlier
codes, against A6.

**Verified.** `mark_stale` (3754 onward):
- `finished` is the job's newest finished run (SUCCEEDED, FAILED, UNKNOWN or NOT_SENT, reservations left out).
- Any run whose scope says `held` goes to ASSESS (3813). It was written for the member date conflict, but a run the
  provider hold kept unsent carries `held` too.
- Any other run goes to `_after_predict` (3818-3822), and the job is marked SUCCEEDED.
- Its docstring says "exactly as the stage would have settled it". Under 7.2 that is no longer "queue the successor" for
  a FAILED, not-sent or held run during an update.

The window is the one between the outcome's commit and the stage's decision, which the code's own stale branch exists to
cover. The wrong outcome holds: E is replaced and its approvals are cleared. A held first processing completes with the
provider not run.

**Decision: accepted.** The fix is the hint's.
- 3.7 now settles a predict's finished run exactly as the stage would: by 7.2's exhaustive list during an update, and as
  today otherwise, except that a hold-setting or provider-held run ends the job CANCELLED (paused).
- The `held` branch is narrowed to the member date conflict's hold.

**Revision.** 3.7; 7.2 (last paragraph); 10 (`mark_stale`; pinned behaviours); U9 (kills after a 500, a 402 and a held
run, during an update and in a first processing).

### R2B-7 (medium): coalescing into a queued stage that expires, or into the stale sweep's settled path

**Claim.** A save that coalesces into a QUEUED reading stage rides on that stage's queue deadline. When the stage
expires, or when it is the stale sweep's settled path that cannot settle, the save is never rechecked in the background.

**Verified.**
- `enqueue` sets `deadline_at` once (122).
- `claim_next` cancels a QUEUED job past its deadline as expired (3613).
- `QUEUE_DEADLINE` is 30 minutes (89).
- `_settled_path` "sends nothing, whatever it finds" (1846).

The R6 rule (coalesce only with a QUEUED stage) still loses a save coalesced late into an old stage. The update then
reads stopped by the system and needs a Resume, which is truthful but contrary to 3.10.5's "every stored save is read".

**Decision: accepted.** The fix is the hint's.
- Coalescing is a compare-and-set under the row lock: the save renews the stage's `deadline_at` (`UPDATE ... WHERE state
  = QUEUED`) and coalesces only when that changed the row. Otherwise it queues the owed stage.
- The settled path is never coalesced with.
- There is no lock cycle: `claim_next`'s short transaction holds the job row and never waits on the encounter's lock.

**Revision.** A4; 2.3 (coalesced); 3.10 item 5; 10; pinned behaviours; U5 (d), (e).

### R2B-8 (medium): a participant's hold makes every update finish partial and clear approvals — rejected

**Claim.** While a participant's hold stands, every update completes without that participant's peer review. A code
that only its peer review added, and that the reviewer approved, is no longer proposed, so the approval is cleared by
the hold rather than by the member's change.

**Verified.**
- These premises hold: A16 lets the chain go on without a held participant, so the update completes partial; and a
  participant's 429 holds fail-closed.
- The sequence's central premise does not hold: "Fable's peer review added 45380, and the reviewer approved it; N,
  without Fable's review, does not propose it". A code a participant adds only in peer review is an alternative, never a
  listed, approvable proposal:
  - P-ADMIT (HARNESS.md, "GI core and harness repair (2026-11-05)");
  - the events engine, `interpretation/assess.py:merge` (1441-1479; `PARTICIPANT_PEER_ONLY` at 1462);
  - `_alternative` (1481-1500): "Candidates and alternatives cannot be approved".
- Otherwise a peer review adds only a `participants.disagree` warn, which "never changes the status" (1502-1513), and
  candidates that no release of this version offers (12.10).

What remains of the claim is that an update completes without a participant's check, and that a decision does not
carry where a missing dispute changes a code's checks and so its fingerprint (747-754). That is the I10 behaviour 7.1
already states for any participant failure. It was in the pre-refutation text (its line 856, "with any code only that
check had given shown as removed"), and the revision applies it unchanged to a held participant: outside the revision's
scope. Such an update reads partial truthfully, and "Cleared when the details changed: the code it was made on changed."
is true of a fingerprint change.

**Decision: rejected.** The premise is unsupported, and the rest is outside the scope.
- The lens's fix, pausing every update while a participant's hold stands, would let an advisory participant's fail-closed
  hold stop every encounter's update until an operator acts.
- R2B-2's change states the hold's cost in 7.3.
- Whether updates should pause during a participant's hold instead is a product choice (see "For the adoption").

### RT1 (critical): a token-endpoint refusal other than 401 or 403 is neither held nor explained

**Claim.** The revision classifies Corti's token refusals in four places, and they disagree. A token 429 or 402 is then
either neither held nor explained (re-sent on every save and retried by a member), or, read the other way, a transient
token 5xx holds every encounter.

**Verified.**
- `providers/corti.py:_authenticate` turns every non-200 token answer into `_NotSent('Corti authentication was refused
  (HTTP {status}); …')` (189-190), and `providers/base.not_sent` records no status (49-50).
- In the revised text:
  - the 7.3 table held a token refusal only on 401 or 403;
  - 7.1's held row and 7.2's hold bullet and retry paragraph held "a token refusal";
  - 7.1's not-sent row took in every not-sent path "other than a token refusal" and said "could not be reached".

Both readings give a wrong outcome: requests repeated after a quota or payment refusal (automatically, and by a member's
Retry that A10 forbids), or every encounter paused on a transient 5xx.

**Decision: accepted.** The fix is wider than the hint, which named 401, 402, 403 and 429. There is now one
classification (A20, 7.3's table), and every other passage refers to it.
- Any 4xx from the token endpoint sets the hold. The token request carries only the installation's credentials and is
  the same for every encounter, so no 4xx of it is request-specific. A token 400 (an OAuth `invalid_client` or
  `unauthorized_client`) left out would be retried by a member, re-posting refused credentials.
- A 5xx, a redirect, an unreadable or tokenless answer and a transport failure are the local not-sent class, retried
  without a release.
- 7.1's not-sent sentence is now true for every member of that class: "the coding service could not be used just now,
  and the document was not sent to it".

**Revision.** A10, A16, A20; 7.1 (the not-sent and held rows); 7.2 (the hold bullet, the every-other-outcome bullet and
the retry paragraph); 7.3 (the table, and "One classification"); 10; U20 (token 429, 400 and 500).

### RT2 (critical): refusals recorded before the install

**Claim.**
- (a) Implemented as the named model does it, by the run's status, "a hold-setting run left out" of `_failed_before`
  releases a pre-install refusal, which then re-sends its identical request with no operator act.
- (b) The installed release recorded a token refusal as not sent with no status. The L4 bullet sends such a request
  once.

**Verified.**
- `corti.py:_predict` records a coding 4xx as FAILED, sent, with its status (237-240).
- `_failed_before` holds FAILED and sent runs (641-654).
- `_interpretation_failed_before` leaves hold effects out by classifying the run (1995-2009), and the revision names it
  as the model.
- (a) holds: read by status, a pre-install 401, 402, 403 or 429, which has no hold row, would be left out of the door,
  and a legacy encounter's first edit would re-send E's refused request. Today's door holds it.
- (b) holds as stated.

**Decision: accepted in part.**
- **(a) Accepted.** A hold-setting run is a run a `ProviderHold` row names, never one classified by its status alone.
  A pre-install refusal stays held against its identical request exactly as today.
- **(b) Accepted as a stated and counted limit, not as a door change.** Holding it would need a door that reads the
  installed adapter's own sentence from a pre-install run. The request sent is the token request only: no coding request
  leaves. It is bounded at one per provider before an operator acts, because a refusal again sets the hold through A20's
  recorded status. And it is today's behaviour for any new request after such a refusal. 9.5 counts both classes for the
  owner.

**Revision.** A20; 7.3 ("After the release", "Refusals recorded before the install" with its stated limit); 9.5 (a new
count); 10; U20.

### RT3 (high): progress folds overlapping attempts, so a step the update completed reads "Stopped" or "Did not finish"

**Claim.** Two attempts of the same stage can now overlap in one run:
- (a) a stopped appraise and the `:after-save:` appraise a save queued beside it;
- (b) a late finisher's FAILED predict for an older context and the newer chain's predict.

The fold ranks stopped and failed above done, so the step reads stopped or failed for work the update completed.

**Verified.**
- `progress._fold` (258) uses `FOLD_ORDER = ('stopped', 'failed', 'done')` (255).
- `_runs` (157) joins a job queued while another was active to that job's run.
- `_step_outcome` (222) reads CANCELLED as stopped and FAILED as failed.
- `run_job` (3643) writes no `superseded` into a CANCELLED or FAILED result.
- `stop_encounter` leaves a running job to read its own Stop at `_send`.

Both sequences hold. Neither overlap exists today: a save is refused while busy, and a Resume starts a new run.

**Decision: accepted.**
- The fix is the hint's first part: a step folds only the newest attempt of each stage kind in the run, and keeps every
  attempt's row and times.
- The hint's second part was not taken (leaving out of progress jobs a finished stage `_superseded` would answer now).
  For a context-free stage `_superseded` answers SUPERSEDED_RESTORED whenever the encounter is fresh, which would drop the
  update's reading steps after completion: T2's defect. The newest-attempt rule covers (b) as well.

**Revision.** 5.2; 10 (`progress.py`); U16 (both sequences).

### RT4 (high): "what changed" has no outcome for a kept approval the reviewer then revoked or replaced

**Claim.** An approval the update kept and the reviewer then revoked, or revoked and approved again, on N fits none of
6.2 step 4's three outcomes. The natural fall-through reads it "Cleared when the details changed".

**Verified.**
- `review.current_decisions` (224-232) ends a decision at a REVOKE.
- `_carry_decisions` (1090-1124) writes `carried_from`, and a reviewer's new decision has none.
- Step 4's kept, kept-then-cleared and cleared conditions all fail for D1 → D2, then D3 REVOKE (and D4) on N.
- The fall-through's text, beside the code shown Approved or Ready for review, is false.

**Decision: accepted.** A fourth outcome, `kept_then_changed`: "{action} of {code} was kept by the update, then changed
by a reviewer." The four are stated exhaustive. A chain always ends current, invalidated or replaced, because
`_carry_decisions` carries or invalidates every current decision of the holder.

**Revision.** 5.1 (the JSON `outcome`); 6.2 step 4; 10; U11.

### RT5 (high): the answers line counts an answer given after the update

**Claim.** An answer given after the update to a question N asks is standing and not yet read by N's stored rows. Step 5
counts it, so the page says it was given "before this change" and is "listed under Earlier answers": both false.

**Verified.**
- `_save_details` (780) records an answer on a fresh encounter and queues `recompute_after_answers` (897; 4614).
- `answers.earlier_answers` (968) lists only answers no question asked now takes.

Step 5's predicate counts the new answer while its recompute is queued, stopped or failed.

**Decision: accepted.** Only answers recorded before N's context was recorded are counted (`MemberAnswer.answered_at`
before `N.context.created_at`): rows only, with no clock and no configuration. No answer is recorded while an update is
pending (1.4), so every answer counted was given before the change. The hint's simpler option ("exactly the answers
`answers.earlier_answers` lists") was not taken. That function goes through `answers._states` to `review.answer_states`
(review.py 312), which binds answers against "the questions the overlay asks" through a reader
(`readers.for_assessment(...).views`), and 6.2 reads "never the review overlay, a reader".

**Revision.** 6.2 step 5; 10; U11.

### RT6 (medium): a first processing's Corti hold has no text, and the upload that set it fails while later ones pause

**Claim.** During a first processing the Corti hold has no customer text. The upload whose own request set the hold ends
failed, with no Resume, while every later upload pauses with one.

**Verified.**
- `_settle_interpretation` ends the interpreter's own hold-setting answer CANCELLED: paused and resumable (2141-2166).
- `progress.interpreter_paused` (335-341) carries INTERPRETATION_PAUSED ("Reading documented procedures is paused…"),
  which is false for a Corti hold.
- `progress.ERRORS['provider_failed']` (108-109) reads "…You can upload the document again." (`new_document`).
- `stage_predict` calls `next_assess(run)` after any send (1184).
- The revision's 7.2 leaves a first processing's predict unchanged apart from the hold door, and 7.1 and 3c words no
  first-processing text for the hold.

Both parts hold.

**Decision: accepted.**
- PROVIDER_PAUSED for a first processing (3c words it, naming no provider). It is true both for a document the hold kept
  unsent and for the one that set it.
- The hold-setting predict ends paused and resumable in a first processing too, as the interpreter's own hold-setting
  answer does.

**Revision.** A16; the 7.1 header; 7.2 (last paragraph); 7.3 "What a held stage does"; 10; pinned behaviours; U20.

### RT7 (medium): the addendum refusals blame "this documentation" for a cause in the existing document

**Claim.** The addendum refusals are decided on the combined text, but their sentences blame "this documentation" even
when the existing document is the cause, and they say "the codes shown stay" where none are shown.

**Verified.**
- `api.addenda` computes `combined` from `parent.text` and the block (343).
- `stage_extract` carries the parent's pages to an addendum.
- `jobs._size_bound` is at 1853-1860.
- FINAL-V2 1.2 (its line 173) builds no request for a revision that already holds `[S\d+]`.

All three variants hold: a legacy text with `[S2]`, an addendum during a first processing or after a failed first
reading, and a parent already over the page bound.

**Decision: accepted.**
- The parent's own text is checked first, alone. When the parent alone causes the refusal, the new
  ADDENDUM_DOCUMENT_TOO_LONG or ADDENDUM_DOCUMENT_UNPREPARED answers, naming the document and a way forward.
- Otherwise the addendum's own sentence answers.
- No addendum refusal says "the codes shown stay as they are".

**Revision.** 1.4 (addenda); 10 (`api.py`, `customer_api.py`); U14.

### RT8 (low): "shown below" when the earlier codes listed none

**Claim.** When the earlier assessment listed no code, the results section still says the codes from before the change
are shown below, and the tally reads "Before your change: No codes yet".

**Verified.**
- `app.js:emptyResults` (959-968) and `tallyText` (454-467, "No codes yet").
- `customer_api.code_rows` (631).

With empty `earlier_codes`, the revision's sentence and the tally say something false.

**Decision: accepted.** "No code was suggested before your change." and the tally "Before your change: no code suggested".

**Revision.** 5.1; 10 (`app.js`); U21.

---

## Defects in this judge's own fixes, found while re-reading them

### J2 (from R2B-3's fix): "what changed" listed no decisions after a save during a re-run chain

**What.** R2B-3's restriction makes a save during a chain re-run after the codes were final take that chain's unfinished
assess #1 as its earlier codes (T8's branch: the codes the page shows). 6.2 step 4 then listed that assessment's
decisions, and it has none. Meanwhile the update's final carried or invalidated the last final's decisions, because
`_carry_decisions` acts on `review.decision_holder`. "What changed" would have omitted every kept or cleared approval.

**Repair.** Step 4 lists the decisions the update acted on, read from rows:
- the decisions on assessments created before N's context that a final on N's context carried (`carried_from`) or
  invalidated (`by_context`);
- in case C, the decisions invalidated for N's revision.

Whenever E held the decisions, this equals the first round's "E's decision as it stood". The repair's first wording
chose by `review.is_final(E)`, which reads the participants configured now. That breaks 6.2's rows-only rule and U11's
"changing the participants configured … changes nothing", and it was replaced by the rows-only rule before this record
was written. U11 gains the case.

### J3 (from A19): the texts promised a restore A19 refuses

**What.** A19 makes some saves of the earlier details no restore. 7.1's restore clauses would still have promised one:
- "You can restore the earlier details to use them again.";
- "Resume to finish it, or restore the earlier details.";
- the too-long text's "Restore the earlier details to use them again".

**Repair.** `update.restorable` (5.1) is false for case C and wherever A19 refuses a restore. 7.1 then drops every
restore clause, as for case C. U8 checks that no text offers one.

### J4 (from A19): A19's "ordinary change" was a no-op in case B

**What.** A19 first made every such save an ordinary change. In case B (a legacy revision, or a v2 revision whose
inventory is of an older version, before the update's analyze) the save keeps the context, so B's values on the kept
context make `fresh` true from rows alone. Every stage of the update then ends SUPERSEDED_RESTORED, and the encounter is
left exactly where the restore would have left it: STALE_ANSWER_BLOCKER, or provider_unknown, with nothing queued.

**Repair.** In case B that save is refused with RESTORE_REFUSED, and nothing is written:
- "The codes from before your change cannot be used again as they were, so their details cannot be restored until the
  update has finished." This is true in every update state, and is in 1.3, 1.4, 2.5 and A19.
- Once the update's analyze has made a gemini context, the save is case A and the ordinary change applies.
- One corner remains. When a legacy update ends too long, the update cannot finish and the legacy codes cannot be
  restored. The text then names the only way forward (shorten the document and upload it again). The legacy codes would
  not have been approvable anyway, since STALE_ANSWER_BLOCKER stands.
- U8 gains the case-B fixture.

---

## Re-read against the owner's words and the first round

**Every changed passage was re-read against each of the owner's requirements:**
- **Background recheck after saving:** R2B-7 keeps a coalesced save's recheck in the background.
- **No calls on keystrokes or cosmetic changes:** untouched.
- **Truthful progress:** RT3 and R2B-3 remove false steps and a false "Changes saved—updating codes".
- **No duplicates; results bound to the saved revision:** no fix adds a send or a second chain. A19's ordinary change is
  a newer save, which supersedes as A1 says.
- **Rerun only what changed:** A19's case-A update reruns the chain because the answers changed or an outcome was
  unknown, and reuses every stored answer.
- **Historical approvals and reports preserved; stale codes neither approved nor exported as current:**
  - nothing widens what is approvable or exportable;
  - R2B-3's fix keeps today's semantics for a re-run chain, refusing the wider A17 for that reason;
  - RESTORE_REFUSED refuses rather than restoring stale codes.
- **Updated codes and what changed shown on completion:** RT4, RT5 and J2.
- **Retry for failures; quota and payment handled without repeated requests:** RT1, R2B-1, R2B-2, RT2 and RT6.
- **Legacy and new encounters both:** J4 covers the legacy case.

**Against the first round's 30 fixes and J1:**
- A17, A18, T8, T9, T11, T13, L4, L5, R6, T2, T5, T7, R2/L2 and J1 still hold where this round's changes meet them (the
  checks are in the text above).
- R3/L6's restores are unchanged whenever A19's conditions hold. Their U8 fixtures read no revoked answer and no
  reconciled unknown.
- T13's reply follows A19: a refused restore in case A answers as a change, and in case B as 409.
- T9's "a revoked decision is not listed" is kept by J2's rule.

**Confidentiality:** the 12 new or changed customer strings match nothing in `customer_api.FORBIDDEN`.

## For the adoption

- Record A19 and A20 as DECISIONS entries, and the amended A3, A4, A10, A16 and A18. FINAL-V2 4.12's row now cites A20.
- **Owner-facing items (class b)**, through 9.5's report:
  - the count of provider refusals recorded before the install;
  - the stated limit: a pre-install token refusal is sent once after the install, and a refusal again sets the hold.
- **Builders:**
  - A participant's hold is now fail-closed on any 4xx but 413. A request-specific 4xx stops that participant's checks
    on every encounter until an operator's release. A finer classification needs each vendor's refusals measured (D39's
    lesson).
  - Corti's coding-endpoint statuses (402 and 429 assumed for payment and quota) rest on the same kind of unmeasured
    vendor assumption. This round did not attack them, and the adoption should have them measured.
- **3c** words RESTORE_REFUSED, ADDENDUM_DOCUMENT_TOO_LONG, ADDENDUM_DOCUMENT_UNPREPARED, PROVIDER_PAUSED, the not-sent
  row's sentence, RT8's sentences and the fourth "what changed" outcome. The meanings are given in the amendment.
- **R2B-8's concern, rejected here:** while a participant's hold stands, updates complete without that participant's
  checks. That is the stated cost. Pausing every update during a participant's hold instead would be a product choice
  (class a). If the owner wants it, it is his to make.
