# TEST DECLARATION — used only by rebuild/ops/tests/test_standing_qa.py (declaration_use: test; never sends)

# Declaration — V1 standing synthetic API testing on claude-sonnet-5-5, October 1, 2026

This is the project record of the owner's standing authority for private synthetic QuillMD API testing, written
before any provider request under it. It binds every request of this campaign to that authority. It does not rewrite
the historical staged campaign, it does not cover Stripe, AWS purchases, contracts, subscriptions, messages to anyone,
restricted documents, real patient data or a launch, and it does not waive any technical or clinical safety failure.

## Authority

```
campaign: quillmd-v1-standing-api-testing-20261001
authority_id: quillmd-v1-private-api-testing-standing-20260930
authority_record: docs/rebuild/v1/QuillMD-V1-Standing-API-Testing-Authority-20260930.json
authority_record_sha256: 9178279297a173697f8becc89d0ab24f510b87231c3d692934e8d60fce41652c
authorization: owner 2026-09-30 standing authority quillmd-v1-private-api-testing-standing-20260930 with no owner monetary ceiling
owner_words: also add thsi propmt like if they need to sue real test with api they can have no limitation also tel lthem to switch to sonnet 5.5 to the brand new one pelase also tel lthem to finish all the  stuuf like Custom word and everything else then give me a results i need that custo mword get focus and at least weve seen some advance things am i right or no?
declaration_use: test
```

The owner words are verbatim, typos included, and byte-equal to the committed authority record named above (the
runner compares them, and the record's sha256). Provenance, at its actual strength: the owner's words relayed through
another assistant and delivered by the owner directly into this VPS session's own user turn on 2026-10-01 — stronger
than a peer-session claim, weaker than a captured owner signature. The record's desktop copy is not on this VPS.

## Money

```
mode: standing_unlimited_monetary
monetary_ceiling: none
per_batch_monetary_confirmation: not_required
```

There is no owner-imposed monetary ceiling and none is invented: the runner carries no money limit, and wherever a
limit would stand (its declaration, its admission records, its status) it holds `null`. The runner still computes each
request's maximum and each response's provider cost at the declared rates, for accounting only. Actual provider quota,
rate-limit or payment failures are reported as external conditions, never retried around.

## Model and request, fixed before any send

```
provider: anthropic
model: claude-sonnet-5-5
rates: input 3 output 15 cached 0.30 (USD per million tokens)
thinking: disabled
effort: medium
inference_geo: unset
pricing_version model_check: configured-v1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
pricing_version mapping: configured-v1:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
pricing_version ordinary_notes: configured-v1:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
pricing_version ordinary_notes_field_relations: configured-v1:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
```

The pricing versions are the application's own (`core.generation.configuration()` under each stage's settings, with
`QUILLMD_DEEPGRAM_RATE_PER_MINUTE=0.0043` and no discount), so they bind the whole request profile: a different
profile is a different version and the runner refuses it. The first attempt pins these terms for the campaign; an
edited declaration never changes what is admitted or how anything is costed. No fallback to any other model.

## Bounds (the non-monetary controls that stay in force)

```
concurrency: 1
automatic_retries: none
max_sends_per_run: 10
max_output_tokens_per_request: 20000
request_deadline_seconds: 180
stage: model_check sends 1 requires none
stage: mapping sends 10 requires model_check_passed
stage: notes_comparison sends 28 requires model_check_passed
```

One runner at a time (the ledger lock), one request at a time, a running job in the QA database refuses. A run makes at
most `max_sends_per_run` sends (fewer with `--max-sends`); a stage never makes more than its declared count, which is
exactly its plan's size; a send (stage and send id) is attempted at most once in this campaign — measuring a send
again after a repair is a later campaign under the same authority, with its own declaration file
(`<date>-quillmd-v1-standing-api-testing-<n>.md`), whose id fixes its root and QA database. The SDK runs with no
retries and a sent request is never sent again: a lost or late response is an unknown outcome, reconciled before any
new send. Every request's output limit is checked on the job's profile and again on the outgoing body by the request
capture. A send that has not returned within the deadline is abandoned as unknown.

## Where it runs

```
root: /nonexistent/standing-qa-test-root
qa_database: quillmd_qa_v2_auth_fixture
credential_file: /nonexistent/standing-qa-test-root/credential/anthropic-api-key
qa_database_password_file: /nonexistent/standing-qa-test-root/qa-db/password
restricted_inputs_ledger: /nonexistent/standing-qa-test-root/rights-ledger.json
restricted_inputs_ledger_sha256: 5abaabb031c6e1552944dab1bc3e7fbd3ae5876436c840ffe1ee6312281851d7
```

A new campaign with its own root, ledger, run records, evidence and QA database; never the historical root
`v1-sonnet5-campaign`, its ledger or its database. Only the owner-delivered credential file is read (the protected QA
credential route; one line, mode 0600, owned by the runner's account), in a scrubbed request process with the SDK's
other credential sources absent; `rebuild/.env` is never read by any route. An isolated private QA process: the
candidate's real views and its real worker function on a synthetic database on the QA server 127.0.0.1:55731 — QA-worker
evidence, never installed-worker evidence. The installed release, its tree, services, database (port 55438) and state
are not touched. Every send and the preflight run only through `scripts/run-ruled-mutation.sh` with this declaration.
The Stop file `<root>/STOP` halts every send while it exists. A halt between a mapping form's send and its
encounter's (or a stop before the encounter's attempt) strands that encounter, which needs its form's proposal in the
same run: the remainder is then refused whole and the mapping stage cannot pass in this campaign.

## Inputs

Only synthetic material authored for this project is sent: the fixed model-check case and the frozen synthetic
diagnostics (`docs/rebuild/v1/sonnet5-campaign/diagnostics`, verified against their freeze). Each run records the
input hashes it allows, and the runner refuses any form whose sha256 is one of the development originals the rights
ledger above marks "no provider upload". The development originals are exercised only offline.

## Plans

- `model_check`: the fixed three-question form and three-line synthetic note, end to end (views, worker, review,
  finalization, verified export, billing audit).
- `mapping`: the frozen synthetic forms f1 to f6 (8 mapping requests) and the f6a and f6b encounters (2 generation
  requests), graded by the frozen grader.
- `notes_comparison`: the 14 frozen notes cases that have a default send, each once on the default request and once on
  the field-relations request (28 requests), scored by the frozen replay.
- Not declared here: synthetic D30/D31-structure notes (no frozen provider-safe input set exists yet) and transcription
  (the runner has no transcription stage). Each needs its own declaration once it exists.

Before the first paid request the runner requires a model-access preflight: one free request to the models endpoint
for `claude-sonnet-5-5`, recording the returned id and display information. It is access evidence only, never
generation proof.

## Stop conditions

Any stop reason other than `end_turn`; a timeout, an unknown outcome or a reconciliation; a served model other than
`claude-sonnet-5-5`; `inference_geo: us` metered while unset; output at or above 70% of the request's output limit; a
validator, export or billing-audit failure; unsafe output (an answer adopted without source support, or a wrong side,
denial or destination) on a path that stops; a leaked credential or an unscannable evidence tree. A safety failure stops
the affected stage until an offline diagnosis and repair are committed and the stage is reopened; the failed evidence
is retained and every verdict stays as recorded.

## Retained evidence (no secrets)

Exact request bodies, raw responses as received, usage, served model id, stop reason, each request's calculated cost
bound and computed cost, the settlement and wallet records, failures, the run records, the preflight records and a
provenance manifest per attempt; the validator's decision and any clinician review change are kept apart from the raw
model output.
