# Pinned WM Word adapter protocol — v2

`WordHost <absolute-private-workspace>` emits one JSON object to stdout. The
managed gate runs before either input file is read. It is not safe to invoke
WordHost directly: `documents/sdk_sandbox.py` first verifies a pinned,
self-contained runtime and applies Landlock/seccomp before .NET creates threads.
The managed gate then synchronizes exec denial across existing threads.

Only the accepted original SHA256
`c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b`
is supported. This is a versioned template adapter, not a general Word engine.
All edits use Aspose.Words.FOSS 26.3.0 APIs. The original is never rewritten.

## Files and trust

- `input.docx`: immutable original, maximum 10 MiB, hash checked before SDK load.
- `request.json`: maximum 2 MiB, duplicate keys rejected, maximum JSON depth 32.
- `output.docx`: fill success only, exclusive creation, maximum 30 MiB.

The authenticated Python parent constructs the workspace and every request.
Browser/model input must never supply `trusted_context`, reviewer identity,
source revision, trusted finalization time, or a substituted mapping digest.
The adapter rechecks evidence and choices as a second boundary. Requests and
outputs may contain synthetic clinical content and stay private, untracked.
Evidence offsets use **Unicode code points**, matching Python string offsets.

## Inspect

Request: `{"operation":"inspect"}`.

Response contains `format:"docx"`, `backend:"wm-iov-foss-v2"`,
`source_sha256`, `mapping_digest`, `fields`, `review_requirements`, and warnings.
The mapping digest hashes the adapter's canonical mapping serialization; clients
store the returned digest rather than attempting to reproduce .NET JSON bytes.

Each field is `{key,label,kind,locator,options}`. All 90 keys are stable:

- 28 `sdt_<original-id>` controls; `kind:"choice"`; locator part and SDT ID.
- `date_of_service`, `patient_id`, `patient_name`, `date_of_birth`; text fields.
- `measurement_<row>_<column>`, rows 1–13 and 15–27, columns 1 and 2; measurement
  fields with explicit `locator.unit` of `mm` or `ms`. Tributary labels include
  the original row number so three separate rows never share source labels.
- `location_<row>` for rows 11,12,13,25,26,27; text fields.

Each requirement is `{key,label,kind,body_paragraph,text,text_sha256,control_keys}`.
Keys are `claim_9`, `claim_11`, `claim_19`, `claim_23`, `claim_27`, `claim_30`,
`claim_31`, `claim_32`, `claim_34`, `claim_35`, `claim_36`, `claim_39`, `claim_45`,
`claim_46`. Paragraphs 11/46 are `identity`, 45 is `signature`, the rest
`assertion`. Every requirement label begins `Prewritten statement: ` to avoid
colliding with answer labels. Word paragraph/page delimiters are excluded from
metadata text, while document page breaks remain intact.

## Resolve and fill

Both require `mapping_digest` and exactly the 90 canonical `answers` keys.
An answer is:

```json
{"text":"3.2 mm","status":"supported","reviewed_by":"authenticated-user-id","revision":7,"evidence":[{"quote":"Right GSV at the SFJ: diameter (mm): 3.2 mm","start":0,"end":47}]}
```

The example offset must be calculated from the actual source, not copied.
`status:"missing"` requires an empty text. The reviewed blank is retained. Dropdown display placeholders are cleared through
SDK run APIs while every control container, ID and original option remains. The
clinical-indication separators are adjusted around populated choices. Missing
values never become zero or an assumed normal finding, and an explicitly
documented field cannot be marked missing.
Nonempty values require `supported`; choices must exactly match an original
option. Measurements require an explicit mapped unit; the SDK inserts only the
numeric portion into the original unit column. No answer is truncated; values
above 20,000 UTF-16 code units are refused.

`operation:"resolve"` requires authenticated `trusted_context` so actual clinician
identity can be displayed during review. It materializes selected statement
variants after choices, returns original/resolved hashes plus `conflicts` and
`export_ready:false`, and creates no export. This operation does not certify
clinical support. A statement's required controls must be documented; explicitly
allowed empty controls must remain missing. Unsupported variant/control
combinations are exposed as conflicts and refuse finalization.

`operation:"fill"` additionally requires:

```json
{
  "trusted_context": {
    "reviewer_id":"authenticated-user-id", "revision":7,
    "notes":"immutable current source text", "signer_name":"trusted full clinician name",
    "finalized_at":"2026-09-17T12:34:56Z"
  },
  "reviewed_requirements": {
    "claim_9": {"text_sha256":"resolved claim hash","reviewed_by":"authenticated-user-id","revision":7,"evidence":[]}
  }
}
```

All 14 requirement decisions are required. An assertion needs complete exact
source support in addition to review. The shown empty evidence cannot support
an assertion. Every selected field needs a complete matching labelled line or
its exact value span, with the same full label; arbitrary suffixes of negated
or another anatomical row's evidence are rejected. Reviewer/revision must
match the trusted context. Interpreting/signing identities are replaced from the actual authenticated
clinician; a changed signer invalidates the previously reviewed text hash. Timestamp comes only from trusted
finalization context.

A successful fill returns `format`, `backend`, `source_sha256`,
`output_sha256`, `field_count`, and `review_requirement_count`. Errors return
`{error,code}` with exit status 2 and no sensitive path/SDK diagnostics.

## Versioned statement variants

Each immutable requirement adds `variants` and `default_variant`. Each variant is
`{id,label,text_template,required_control_keys,empty_control_keys}`. Resolve/fill
accept `claim_variants:{claim_key:variant_id}`; fill requires all 14 explicit IDs.
No freeform replacement text is accepted. A resolved requirement adds
`original_text`, `original_text_sha256`, `selected_variant`, and `changed` while
its `text`/`text_sha256` describe the actual completed statement. All successful
responses include the original source SHA256.

| Paragraphs | Allowed variants |
| --- | --- |
| 9 | `original`, `exam_choice` |
| 11/46 | `trusted` actual clinician identity |
| 19 | `original`, `technique_only`, `not_documented` |
| 23/27 | `original`, `none`, `not_documented` |
| 30/34 | `selected`, `not_documented`, `not_assessed` |
| 31/35 | `selected`, `not_documented`, `not_assessed` |
| 32/36 | `negative`, `positive`, `not_documented`, `not_assessed` |
| 39 | `original` |
| 45 | `trusted` finalization timestamp |

Template tokens are only canonical `{sdt_<id>}` answers, `{signer_name}`, and
qualified right/left connector tokens. `{right_reflux_connector}` and its left
counterpart are one space for the `is absent.` option, otherwise ` is `.
`{right_treatment_connector}` and its left counterpart are empty before the
original recurrence option's leading comma, otherwise one space. The Python
review helper can independently substitute these immutable templates to verify
resolved text, without editing Word or accepting arbitrary statement text.

Changing a prewritten finding/identity is visible through the original/resolved
review and bound to current answers, source revision, mapping and clinician.
Every clinical assertion requires its own **complete labelled source evidence**;
a bare sentence is insufficient because the right/left template sentences can
be identical. All citations and all nonempty explicit values under that exact
label must agree. Full label matching tolerates case and surrounding whitespace,
while retaining side, anatomical row and internal colons. Identity/signature
requirements reject note evidence and use only trusted parent metadata.

Positive reflux chooses a documented positive finding instead of the original
fixed negative. Absent-vein grammar uses the qualified connector. No-prior-
treatment variants require their four dependent choices to be missing, clear
only their display runs, and preserve the original controls/options/paragraph.
No-symptom forms show the documented `Asymptomatic` option with unused symptom
controls blank and no dangling commas. No unsupported normal finding is inferred.
The SDK rejects positive reflux versus a negative/unknown reviewed statement,
contradictory same-vein absence, prior-treatment indication versus bilateral
none, and non-assessed statements versus documented side measurements. It also
rejects a global negative when a recorded reflux duration exceeds the original
template's explicit 500 ms criterion; this is a template-specific consistency
check, not a general clinical decision engine.

## Scope and evidence

Only the exact accepted blank and this versioned mapping are supported. Fifteen
unclassified blank paragraphs remain untouched; no general narrative location
is invented. The original upload stays unchanged. Clinical statements use SDK
literal-run editing, with unchanged styled prefixes and page breaks preserved;
no custom Word engine or raw OOXML mutation is used.

No commercial renderer is used in application exports. SDK serialization
normalizes Word revision/drawing edit IDs, compatibility declarations and empty
crop metadata; ZIP/XML byte identity is not promised. Qualification separately
checks questions, controls/options, styles, media, geometry and completed layout.

`verify_adapter_v2.py` invokes the actual kernel boundary for completed positive,
absent, no-prior-treatment, asymptomatic and long cases plus negative controls.
`synthetic_fixture.py` builds metadata-driven synthetic fixtures using an actual
isolated resolver and only complete known source labels. The old v1 verifier
is historical evidence: independent refutation found and repaired a side-
binding defect after its original pass. It is not the v2 release gate.

`render_v2_evaluation.py` uses an existing separate proprietary trial only for
private watermarked evaluation evidence, never application output. Repeated
trial footer lines are excluded explicitly when checking a long answer across
pages. Font substitution and lack of native Word certification remain recorded.

`--qualification` only allows operator-owned fixture artifacts; it does not relax
kernel controls and managed services refuse it. Production uses root-owned
pinned immutable runtime/manifest ancestors. `build_word.py` requires the exact
verified SDK 8.0.425, runtime 8.0.31, locked NuGet restore and deterministic path
mapping. Ambient Git/SourceLink revision metadata is disabled; exact source
bytes and installer comparison provide provenance. It emits a separate manifest and build proof with SHA256 of every build
source/lock/project/global.json/build script. The installer compares those bytes
to the exact reviewed commit before enabling the private service.
