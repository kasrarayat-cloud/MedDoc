# Blank mapping capacity repair — 2026-09-27

**Prepared locally; disabled by default; no generation, deployment or compatibility claim.**
Worktree `/opt/meddoc-pro/.worktrees/v1-mapping-capacity`, branch `v1/mapping-capacity`,
base `4f4722182330ebf290cd69831f2de15bdda78f33`. This changes only mapping compilation,
wire validation and mapping worker admission. The shared settlement implementation is inherited unchanged.

## Demonstrated sizing defect and bounded repair

The old request admitted 200 fields/1,200 slots while using the global disabled-thinking
8,000-output-token profile. Three separately authorized native `count_tokens` calls measured
prospective minimal old responses as ordinary user text:

| Historical synthetic envelope | Native input-token measurement | Request SHA256 |
|---|---:|---|
| 200 fields, 1,200 paragraph slots | 39,426 | `054cce5bad5e0353bc8884165c5836f1a0b089da1cb52b60bec75e78e17dc639` |
| 200 fields, 1,200 table slots | 62,026 | `3cce9fc23d045b08c4917933a8b4d5967a01a2f01fa662f0b1bc8543268a328f` |
| 100 fields, 128 table slots | 8,370 | `acd03b26364e647638797a0ee85047a5fa9d8626e11cdf164f06b48ae4b8877e` |

Those immutable payloads/attempts/outcomes remain in the prior mapping worktree's
`rebuild/.runtime/mapping-assistance-20260927/output-sizing/`; the original sizing script
and development-only metadata measurements remain beside it. No qualification file was opened.
Across the retained 40 development metadata files, five exceeded 1,200 slots and six exceeded
200 fields. D33 had 1,191 slots/57 fields and D06 808/186: admitted limits were a practical issue.
This work changes neither the corpus denominator nor its failed results.

The v2 wire format groups numeric verdict IDs rather than repeating long stable paths and keys.
One change is `[prior field ID or -1, slot ID, kind code, label reference, start, end,
glyph or -1, then option reference/start/end triples]`. References address complete source
strings in the immutable request, with Unicode code-point offsets. Deterministic expansion
restores the previous stable-source representation for the existing clinician review and writer.

The retained conservative compact envelope includes all 200 field IDs, all 1,200 slot IDs,
100 replacement records and 400 option spans. It is 17,255 bytes. Reference/offset integer widths
are deliberately wider than the catalog normally permits; these synthetic repeated references
measure wire size, not a clinically valid mapping. A separate pure check expands a complete
request-consistent maximum envelope with 100 distinct replacements and 400 owned options.

Exactly **one additional free native count call** was authorized for the compact payload,
made once with explicit `claude-sonnet-5`, `https://api.anthropic.com`, timeout 30 seconds and
zero retries. Before-call and outcome records are retained in the [evidence directory](mapping-capacity-20260927-evidence/).

- Request SHA256: `52225de3bd14756722430db311884433c5b1179ad33b8f4076c95999a9009ac6`.
- Prospective response-text SHA256: `0dd2b02d5daf2db0cceb6f119938009229b88f96c35f87d4cdbf5153fb04fe85`.
- Outcome: **8,659 native input tokens**, completed `2026-09-27T17:57:16.084898+00:00`.

This is an input-token proxy for output-text sizing, not generated-output proof or an exact
upper theorem for every tokenizer sequence. It is below the requested 16,000-token headroom
target for a 20,000-token mapping envelope. No native tokenizer was available locally.
No generation call, paid operation or new spending allowance was used. Earlier calls remain
separate; there is no authority to repeat any consumed or unknown attempt.

## Contract and accounting

- `blank-mapping-v2`: complete, disjoint field/slot verdict groups; strict integers; exact
  references; 100 combined additions/replacements; 400 option spans total, 100 per change.
- Labels/options are copied from owned source spans. Foreign contexts, invented indices,
  duplicate replacement ownership, invalid bounds and incomplete triples refuse the envelope.
  A replacement cannot move to another field's destination or omit a prior counterpart.
  Expanded targets still undergo source hashing, deterministic locator, signature, option and
  overlap validation. Failed replacement candidates preserve the existing field visibly.
- Capacity exhaustion records `incomplete=true`, keeps all source areas in review and adds an
  unresolved item; unassisted confirmation fails. Manual resolution remains assisted. Physical
  parser limits and the 100-answer generation limit are unchanged and disclosed.
- Mapping-only profile: **20,000 max output tokens; 120-second timeout; disabled thinking;
  medium effort**. Profile/hash are bound into the request and immutable job config. Reservations
  price the actual 20,000-output cap plus the conservative input bound and applicable geography;
  this raises the reserved output component from $0.08 to $0.20 at the configured $10/M list rate.
  It does not increase spending authority. Retail policy and actual-use settlement are unchanged.
- Global generation remains 8,000 disabled/16,000 adaptive tokens; legacy requests/history remain
  untouched. Old queued mapping contracts fail **before the current compiler** as definitely
  unsent, release their holds and require a fresh quote. They are never rewritten/replayed.
- `max_tokens`, wrong model, refusal or invalid output remains receipted, settled and absorbed
  without adoption. A transport-time unknown keeps its original attempt/hold for reconciliation;
  a definite constructor/profile failure releases unsent. There is no automatic retry.

## Finite checks

| Run | Result |
|---|---|
| Existing mapping workflow/accounting tests adapted to compact wire | 22 passed, 47.516s |
| Workflow plus source ownership, Unicode, ID partitions, maximum complete envelope, signature, old-contract release, cap exhaustion, profile/hash and legacy checks | 33 passed, 52.614s |
| Minimum/maximum metadata quote arithmetic; exact byte-limit admission/refusal | 1 passed, 1.656s |
| 101 changes, 101 options in one change, non-boolean exhaustion refusal | 1 passed, 0.001s |

No broad regression suite was repeated. Existing 380-check evidence, synthetic rendered
original/missing/ordinary/long comparisons and native-control limitations remain as recorded
in the original mapping recovery report. The unchanged writer's positive workflow was exercised
again: upload/omitted Plan proposal/review/confirmation/correction/finalization/download, destination
text, missing/long answers and export hash. Unmocked provider construction is denied; explicit
native mocks test requests and billing only. The fixture staticfiles warning is preserved.

Source hashes and logs are retained with the report. Root independently refutes the finished diff
before integration; this report does not substitute for that gate. No services, production records,
locks, installed revisions, agreements or deployment flags were changed.

## Remaining limits and next safe action

Numerical source binding cannot establish the semantic relevance of an allowed source span or
`not_answer` judgment. A model can still misclassify source wording; qualification and clinician
review remain necessary. Actual native structured-output acceptance, timing and clinical mapping
quality on this exact contract/profile remain unmeasured. The measured proxy alone does not
establish provider schema compatibility, Word compatibility or V1 readiness. Both flags stay off.

Next: independently refute this fixed source, integrate the reviewed union, retain all first-pass
corpus evidence, then undertake only specifically authorized eligible native verification. Do not
rerun old campaigns, open reserved qualification content or reuse consumed count authority.

## Independent review finding: native schema transformation

Root identified a shared native request compatibility blocker while refuting this finished diff:
`generation.anthropic_request` passed raw Pydantic JSON Schema to `messages.create`. The compact
schema includes 26 constraint nodes (numeric bounds, array lengths) unsupported by native
structured output. The installed public `anthropic.transform_schema` removes those unsupported
keywords and retains their guidance in descriptions; local strict Pydantic validation stays required.
Our offline impact probe confirms raw/transformed schema hashes and zero remaining unsupported
nodes. Root owns the Sonnet-5-only shared compiler repair on the release branch, including
historical request preservation. **This branch requires that reviewed shared repair before use**;
its current base alone is not a native-compatible candidate. The transformation must precede
request hashing and reservation, as the shared compiler does. No provider call was made to
reproduce a known-invalid request. See `schema-impact.json` in the evidence directory.

Root's finished shared repair was independently refuted with 12 pure/actual-SDK MockTransport
controls (socket denied, dummy database): NOTHING FOUND. The checked `generation.py` SHA256 is
`ce7af2f35124c24edcc0f74daa103fd0bd9b72b6db610225195315830171827d`. Sonnet 5 outgoing schemas
for ordinary, WM, expanded mapping and compact mapping contain no unsupported constraint keywords;
entire prior-model requests and input schema/profile objects remain identical, and strict local
compact validation still rejects invalid bounds. The proof is retained in the evidence directory.
The first standalone reviewer probe stopped before any SDK transport because Django was not set up;
using explicit dummy settings corrected that probe setup, with no application source change.
