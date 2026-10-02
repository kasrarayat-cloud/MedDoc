# Declaration — V1 standing synthetic API testing on claude-sonnet-5-5, October 2, 2026 (campaign 3 of the day)

A later campaign under the same standing authority, on the relations contract v4 (`bfa92cbe`, integrated as
`fdcc7db2` after its refutation found nothing in the wire: `docs/rebuild/v1/standing-campaign/relations-v4-refutation-20261002.md`)
and the runner's generation pacing (`52901096`, integrated as `f55d6434`). Campaign 4 (`20261002-quillmd-v1-standing-api-testing-2.md`)
measured the notes on contract v3 and stopped its transcription stage when the colonoscopy transcript's Generate was
refused by the application's per-user rate limit (30 Generate requests per user per 600 s) after 30 generations in
about seven minutes. This campaign measures again on v4: the 14 frozen notes cases on both requests, and voice-first on
both synthetic recordings with smart formatting on and each transcript generated under field relations. The spoken
section heading release and the other-question heading hold were NOT integrated (confirmed findings), so a dictated
heading still couples its block exactly as in campaign 4. Campaigns 1-4 and their evidence are unchanged.

## Authority

```
campaign: quillmd-v1-standing-api-testing-20261002-3
authority_id: quillmd-v1-private-api-testing-standing-20260930
authority_record: docs/rebuild/v1/QuillMD-V1-Standing-API-Testing-Authority-20260930.json
authority_record_sha256: 9178279297a173697f8becc89d0ab24f510b87231c3d692934e8d60fce41652c
authorization: owner 2026-09-30 standing authority quillmd-v1-private-api-testing-standing-20260930 with no owner monetary ceiling
owner_words: also add thsi propmt like if they need to sue real test with api they can have no limitation also tel lthem to switch to sonnet 5.5 to the brand new one pelase also tel lthem to finish all the  stuuf like Custom word and everything else then give me a results i need that custo mword get focus and at least weve seen some advance things am i right or no?
declaration_use: live
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
rates: input 2 output 10 cached 0.20 (USD per million tokens)
thinking: between_tools
effort: medium
inference_geo: unset
pricing_version model_check: configured-v1:d15bca4a92a0869453c9fd5fd98d1a38321f21ae0d5f6f2b06b4a01332758ff2
pricing_version mapping: configured-v1:d15bca4a92a0869453c9fd5fd98d1a38321f21ae0d5f6f2b06b4a01332758ff2
pricing_version ordinary_notes: configured-v1:d15bca4a92a0869453c9fd5fd98d1a38321f21ae0d5f6f2b06b4a01332758ff2
pricing_version ordinary_notes_field_relations: configured-v1:f714798b73422cc8efe10325a2d9fedb2014bdd771f193df87c117d24aec89e8
pricing_version voice_notes_field_relations: configured-v1:f714798b73422cc8efe10325a2d9fedb2014bdd771f193df87c117d24aec89e8
```


`voice_notes_field_relations` is the version a transcript's generation is quoted under with field relations on, computed
under the transcription stage's settings and the declared voice rate (here equal to the notes stage's relations version,
the rate being the same; both are relations contract v4's). The pricing versions are the application's own (`core.generation.configuration()` under each stage's settings, with
`QUILLMD_DEEPGRAM_RATE_PER_MINUTE=0.0043` and no discount), so they bind the whole request profile: a different
profile is a different version and the runner refuses it. The first attempt pins these terms for the campaign; an
edited declaration never changes what is admitted or how anything is costed. No fallback to any other model.

Rates as read on 2026-10-01. Anthropic (https://platform.claude.com/docs/en/about-claude/pricing): Claude Sonnet 5.5
$2 input, $10 output and $0.20 cache reads per million tokens, the same as Claude Sonnet 5. Deepgram
(https://deepgram.com/pricing): the page lists pre-recorded Nova-3 Monolingual pay-as-you-go at $0.0043/min and no
separate Nova-3 Medical line; the project's cost definition (docs/rebuild/cost-definition.md, 2026-09-17) prices
nova-3-medical at that same $0.0043/min public rate, which is declared here. Provider-billed amounts are reported
separately from these calculated costs.

## Transcription, fixed before any send

```
transcription_provider: deepgram
transcription_model: nova-3-medical
transcription_rate_per_minute: 0.0043
transcription_mip_opt_out: true
transcription_smart_format: true
transcription_notes_contract: field_relations
pricing_version transcription: configured-v1:d15bca4a92a0869453c9fd5fd98d1a38321f21ae0d5f6f2b06b4a01332758ff2
```

Each transcription request is the product's own: `POST https://api.deepgram.com/v1/listen` with exactly
`model=nova-3-medical`, `smart_format=true` and `mip_opt_out=true` (the recording is never offered to the
provider's model improvement), carrying the submission the product prepared from an allowlisted synthetic recording.
The transcription pricing version is the application's under the transcription stage's settings (the notes stage's
v3 settings, the opt-out on) and the rate above, which the application uses for the quote, the hold and the
settlement. A transport guard admits that one request per transcription send and nothing else; the Deepgram key
reaches only a transcription run's request process, and its environment holds the key only around that request.

## Bounds (the non-monetary controls that stay in force)

```
concurrency: 1
automatic_retries: none
max_sends_per_run: 10
max_output_tokens_per_request: 20000
request_deadline_seconds: 180
stage: model_check sends 1 requires none
stage: notes_comparison sends 28 requires model_check_passed
stage: transcription sends 4 requires model_check_passed
```

One runner at a time (the ledger lock), one request at a time, a running job in the QA database refuses. A run makes at
most `max_sends_per_run` sends (fewer with `--max-sends`); a stage never makes more than its declared count, which is
exactly its plan's size; a send (stage and send id) is attempted at most once in this campaign — measuring a send
again after a repair is a later campaign under the same authority, with its own declaration file
(`<date>-quillmd-v1-standing-api-testing-<n>.md`), whose id fixes its root and QA database. The SDK runs with no
retries and a sent request is never sent again: a lost or late response is an unknown outcome, reconciled before any
new send. Every request's output limit is checked on the job's profile and again on the outgoing body by the request
capture. A send that has not returned within the deadline is abandoned as unknown.

Generations are paced to the application's own per-user rate limit (`core.views.GENERATION_RATE_LIMIT` Generate
requests per `GENERATION_RATE_WINDOW_SECONDS`): before a send that leads to a Generate — for a recording, before
its Deepgram request — the runner reads the limit's window and waits, sending nothing and reading the Stop file
every second, until one more Generate is admitted; the wait is recorded on the attempt. A Generate the application
still refuses stops the stage with the page's message, nothing sent.

## Where it runs

```
root: /opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261002-3
qa_database: quillmd_qa_standing_20261002_3
credential_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/credential/anthropic-api-key
transcription_credential_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/credential/deepgram-api-key
qa_database_password_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password
restricted_inputs_ledger: /opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/metadata/053-original-dev40-exact-rights-ledger.json
restricted_inputs_ledger_sha256: 5abaabb031c6e1552944dab1bc3e7fbd3ae5876436c840ffe1ee6312281851d7
```

A new campaign with its own root, ledger, run records, evidence and QA database; never the historical root
`v1-sonnet5-campaign`, its ledger or its database. Only the owner-delivered credential files are read (the protected QA
credential route; each one line, mode 0600, owned by the runner's account, one name, no link anywhere on its path;
the Deepgram file only for a transcription run, before anything is sent), in a scrubbed request process with the SDK's
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

```
transcription_input: soap-ankle-speech 3121862714193bb2f36c09a688dc7b3f293504163014680cae3c610dc21ea2d7
transcription_input: colonoscopy-speech dfd22dfd4facec937dabd3fbaddd4670807fa5b018d86a4df9f425eb9f83e97c
```

The recordings sent for transcription are synthesized speech, not a human microphone recording: machine speech of
synthetic scripts written for this project, on the runner's own allowlist (`standing_qa.TRANSCRIPTION_AUDIO`), each
pinned by sha256 and size and read only when its bytes match. This list may only narrow that allowlist. The product's
stored upload must hash to the same sha256 before the send is admitted, and every transcription attempt records it.

## Plans

- `model_check`: the fixed three-question form and three-line synthetic note, end to end (views, worker, review,
  finalization, verified export, billing audit).
- `notes_comparison`: the 14 frozen notes cases that have a default send, each once on the default request and once on
  the field-relations request (28 requests), scored by the frozen replay.
- `transcription`: per recording, two sends in one run (4 requests for the two recordings). First its transcription:
  the frozen synthetic form r1-11 uploaded and confirmed, a voice-first encounter, the recording through the real voice
  view (one QA-worker transcription job), the transcript reviewed and saved unedited as the notes through the real notes
  view. Then the generation on that encounter (a separate Messages request, under the field-relations contract —
  switched on around that send only — and priced at `voice_notes_field_relations`): review, finalization and the verified,
  authenticated export, every adopted answer checked against the saved notes. Each transcription records its request
  id, the processed duration, the provider cost at the declared rate, the settlement, the model and every artifact.
- Not declared here: synthetic D30/D31-structure notes (no frozen provider-safe input set exists yet). It needs its own
  declaration once it exists.

Before the first paid request the runner requires a model-access preflight: one free request to the models endpoint
for `claude-sonnet-5-5`, recording the returned id and display information. It is access evidence only, never
generation proof.

## Stop conditions

Any stop reason other than `end_turn`; a timeout, an unknown outcome or a reconciliation; a served model other than
`claude-sonnet-5-5`; `inference_geo: us` metered while unset; output at or above 70% of the request's output limit; a
validator, export or billing-audit failure; unsafe output (an answer adopted without source support, or a wrong side,
denial or destination) on a path that stops; a leaked credential or an unscannable evidence tree. For transcription
also: a request other than the declared one, or not the submission the product prepared; a receipt naming another
model; a processed duration whose provider charge at the declared rate exceeds the send's maximum, or a settlement
that differs from it; an empty transcript, a disclosed incomplete or unknown coverage, or a stored transcript that is
not the provider's; a reviewed transcript that could not be saved unedited as the notes. A safety failure stops
the affected stage until an offline diagnosis and repair are committed and the stage is reopened; the failed evidence
is retained and every verdict stays as recorded.

## Retained evidence (no secrets)

Exact request bodies, raw responses as received, usage, served model id, stop reason, each request's calculated cost
bound and computed cost, the settlement and wallet records, failures, the run records, the preflight records and a
provenance manifest per attempt; the validator's decision and any clinician review change are kept apart from the raw
model output. For transcription: the recording and its provenance, the request record without its credential header
and the exact submitted bytes, the response as received, the product's stored transcript and the notes it became.
