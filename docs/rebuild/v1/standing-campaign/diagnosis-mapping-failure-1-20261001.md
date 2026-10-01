# Diagnosis: standing campaign mapping failure 1 (2026-10-01)

campaign: quillmd-v1-standing-api-testing-20261001
stage: mapping
failed_attempts: 32
repair_commit: 51bbcb9e31a06b7904475f6dec7471a34713cffe

**What stopped the stage.** Attempt 32 (`mapping:f2b-leave-checkboxes-owner`, served `claude-sonnet-5-5`, `end_turn`,
8,860 input / 188 output tokens, 0 thinking tokens, request on the QA worker) returned a schema-valid envelope that
listed slots 9-29 in BOTH the covered and the not-an-answer group, and listed slots 35-42 in the not-an-answer group
of a request that has 35 slots (IDs 0-34). The wire rule refused the whole response ("Mapping slot IDs must form one
disjoint request-bound set."), the job failed, its provider cost was absorbed, nothing was adopted, and the stage
stopped as a contract failure before the remaining seven sends. Attempts 30 (f1) and 31 (f2) completed safely: f1 held
both areas for review, f2 matched the deterministic mapping on all three areas.

**The refusal is correct and stays.** Replayed offline on the candidate, the response is refused by the
request-bound check before any other rule runs. A hold-only alternative (hold each repeated ID `uncertain`, keep the
rest) was written, tested and WITHDRAWN before commit: the same response names eight areas that do not exist, so its
numbering is not aligned with the request, and its other verdicts (for example 'not an answer' on slots 30-31,
"Details of the leave", a real answer area) cannot be trusted. A response that contradicts itself and invents areas is
still refused whole.

**Cause.** Two request-side facts, both measured: (1) native structured output drops numeric bounds (the request's
schema describes `0 <= id < 1200` in prose only), so the decoder could emit an ID the request does not contain;
(2) the application's `between_tools` thinking gives a single-turn request no reasoning at all (0 thinking tokens on
every standing attempt), and the 35-slot envelope was produced without any.

**Repair (request side only, claude-sonnet-5-5 only; validation unchanged).**
- `mapping_wire.request_schema`: each field-group and slot-group item is an integer `enum` of exactly the request's IDs
  (up to 400 per group; above that the generic item stays), so constrained decoding cannot name an absent area.
- `mapping_assistance.request_profile`: the mapping envelope on claude-sonnet-5-5 asks for adaptive thinking
  (`display: omitted`) at medium effort; the 120 s client deadline, the output bound (20,000, thinking included), the
  price bound and every validation are unchanged. Sonnet 5's mapping request is byte-identical to before.

**Refutation r1 (independent, read-only).** A-F1 (MEDIUM): the first version raised the 5.5 mapping deadline to 180 s,
which outlives the worker's graceful stop (systemd `TimeoutStopSec=150`, `generation.WORKER_STOP_SECONDS`) that every
application profile respects with 30 s left for the receipt and settlement; a deploy during a long request would have
left it unreceipted. Reverted to 120 s, with a test that every mapping deadline ends inside the graceful stop (mutation:
180 s fails it for both models). A-N1 (LOW, predates this change): the cost scanner does not watch `profile` inside
`compile_request`, so a cap lowered there through an unreadable call would price the hold below the request; the
mapping unit tests catch that case. Recorded as a residual. Nothing else was found: the enum schema survives
`transform_schema`, response validation is unchanged, the Sonnet 5 request digest is identical, an old-profile quote is
refused unsent and released.
(Whether the provider accepts the enum grammar, and how long adaptive mapping takes against 120 s, is measured live in
campaign 2; a timeout there is an unknown outcome and stops the stage.)

**Why a new campaign, not a reopening.** The first campaign's declaration fixes `thinking: between_tools` for every
request it admits. Mapping requests with adaptive thinking are a different request profile, so they are measured under
their own committed declaration (`20261001-quillmd-v1-standing-api-testing-2.md`), all ten mapping sends again. The
first campaign's mapping stage stays failed; attempt 32 and its evidence are unchanged.
