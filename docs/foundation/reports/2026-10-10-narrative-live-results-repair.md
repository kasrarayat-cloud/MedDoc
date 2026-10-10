# Actual custom narrative failure and automatic results

Owner authority and prospective installation scope are recorded in
`../rulings/2026-10-10-quillmd-narrative-live-results.md` and
`../mutations/20261010-quillmd-narrative-live-results.md`.

## Confirmed served failure

The active, verified account `kasra.rayat@gmail.com` is a clinician in X-ray,
Synthetic North Clinic. Its actual document
`34ea5784-e03c-40a0-9d15-0ce4209c5e15` uses the approved eight-cell “Test”
mapping `b93fd1ec-3d18-4d22-8bbf-0c1fc8f38083`, version 1. Generation
`65dd651b-9c1a-4ce6-b69d-5dd0535f88b2` failed on the saved ordinary narrative.

Read-only native inspection verified the original blank form digest
`da91079f071cbc49fbf5f5b45a5933e09c8bab768bcf5de038bfd32a363fbe34`
and retained response digest
`412c744d1cb98399ed3b87980650db922905bc1cc92d38a92c30a1ee312529f3`.
Rehydrating the retained Anthropic response and running the installed validator
without a provider call reproduced the exact error:

> Evidence must preserve a complete source line or complete labelled answer.

The response selected complete sentences from a paragraph. The legacy contract
accepted only the entire source line or an entire explicitly labelled value.
The mapping and retained response were intact. The attempt retains calculated
provider cost USD 0.010206 and sponsored account charge USD 0; calculated cost
is not independently confirmed provider billing.

## Prospective repair

New ordinary custom-form jobs use prompt version
`extractive-v7-custom-sentence-evidence`, with complete offered source-unit IDs
and exact character offsets. The validator rejects unknown/duplicate units,
partial quotation substitutions and schema violations. Missing information,
conflicts, scope/heading governance and explicit clinician decisions remain.
No answer is automatically reviewed. Qualified Word and underlined-tab forms
retain their established contracts. Queued v4/v5/v6 provider requests remain
byte-identical; retained jobs are neither relabelled nor re-adopted.

Authenticated, tenant-scoped status GETs return display state and governed
answer previews. The browser submits once, observes queued/running/terminal
states, reconciles interrupted responses with GET, and refreshes the review
area while retaining local notes and review edits. Failed/cancelled generation
replays reuse the persisted attempt for that saved source revision. An explicit
source save advances the revision and permits a new request.

## Validation and operational evidence

The finished clinical diff received independent refutation. A finite-verb
allowlist rejected legitimate “presented with” and “demonstrates” prose; the
custom contract now grounds complete offered units without that tab-specific
heuristic. Tab behavior remains unchanged. Independent comparisons found all
12 legacy provider request combinations equal (both providers, v4/v5/v6,
ordinary custom/tab). A stale document header badge was also corrected.

Focused Chromium fixtures passed 11 progress/result cases and 8 existing input
regressions without provider calls. PostgreSQL tests exercise tenant isolation,
read-only observation, persisted failed-attempt replay, source revision retry,
financial record preservation and existing review/export governance. Legacy
workflow fixtures explicitly pin their retained v6 contract; prospective v7
has separate real Word review/export coverage.

These checks do not constitute installation or public-browser completion.
Exact CI, code-only native preservation, encrypted backup, installed release,
public browser outcome and downloaded Word verification must be read from the
corresponding protected receipts under
`rebuild/.runtime/narrative-live-results-20261010/`.

Public-browser verification uses `doctor@synthetic.quillmd.invalid`, the
existing dedicated synthetic doctor in the same X-ray workspace, with normal
public HTTPS sign-in and no old cookies. It uses the actual approved mappings,
the exact owner's narrative, the exact earlier successful labelled SOAP
source, and the unchanged original failed document. The controlled new failure
is a stale-revision refusal, not an induced provider failure. Live transitions
to failed are additionally covered by isolated browser tests. This does not
claim a fresh Gmail sign-in: its password is not retained, and this repair
does not reset it or fabricate a session.
