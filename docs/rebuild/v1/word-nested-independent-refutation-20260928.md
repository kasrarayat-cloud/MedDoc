# Independent nested-checkbox ownership refutation

## Source and bounded method

Read-only review compared Word source `649f65c2bd32b5b994611de91f9cb24cd6522034`
with frozen `904fa10c9f717582d0e405e0e445292e29003872` (engine SHA256
`02c25c15110a9af367dae24e925f598a2e9aeeb6ffec4afee63357a009fdc235`), then
replayed against focused repair `1bcda7b62624d8293865733e9dbc2b21a7809417`
(engine `b3174ffd4027b4bab7a1741a39a361ce2dc455a26f82a403b68f6c3117d461f9`).
The initial 16 cases were declared before execution; three explicit followups
isolated the demonstrated header and signing-context failures. Network creation
was disabled in the probe processes. No provider, database, native Word, full
suite or unseen qualification content was used. Source trees were not edited.

Synthetic original files, complete mappings, filled exports, exact changed
paragraph paths and source snapshots are preserved in
`rebuild/.runtime/v1-word-corpus/custodian-20260927/word-nested-904-review-20260928/`.
`probe.py`, `followup.py`, both result JSON files and `seal-initial.json` reproduce
the evidence. The only real original inspected was independently annotated DEV
D03, SHA256 `29dfcdd8a5daef213e30e03e5062fa9193a31a53651c880acc498006c1d506ff`.

## Demonstrated failures

### 1. One-option source loss — author finding independently reproduced, closed by 1bc

At `rebuild/documents/word_v3.py:1633` in 904, the nested context override discards
the question appended by the single-checkbox path. Full-width outer cell:
`Which finding concerns the donor? Tick all that apply.`, plain spacer, nested
one-cell `☐ Other` produces checkbox `Other`, context `''`, no warning. This same
parent loss already occurs in base649, so it is not a new original-to-base defect;
904's claimed ownership repair remained incomplete. A subsection `During
exertion:` before that grid instead retains the parent but drops the subsection.

The exact unchanged fixtures replayed on 1bc retain the full parent, and the
subsection case retains `parent > During exertion:`. Both writes address only the
intended box. D03 fields and warnings are exactly equal between 904 and 1bc (43
detected fields). This is selected evidence, not whole-document success.

### 2. Printed grid headers disappear — remains on 1bc

`rebuild/documents/word_v3.py:1541` counts only paragraphs containing boxes.
The subsequent context override at line1633 drops other grid source text.

Input `inner_scope_headers_neutral_parent.docx`: full-width outer cell contains
`Which findings apply? Tick all that apply.`, plain spacer, nested 2×2 table:

| Donor | Recipient |
| --- | --- |
| ☐ Abnormal | ☐ Abnormal |

904 and 1bc emit one `multi_choice` with the complete generic parent as label,
context `''`, options `['Abnormal', 'Abnormal (2)']`, and no warning. Neither
Donor nor Recipient appears in the mapping. Selecting `Abnormal (2)` marks the
Recipient box at `b/tbl[0]/tr[0]/tc[0]/tbl[0]/tr[1]/tc[1]/p[0]`; the field supplies
no recipient attribution for that choice. Source headers remain printed in the
export, so this is lost mapping scope rather than erased document ink.

Base649 already flattens these two columns incorrectly, but returns `Donor` as
both label and context with single `choice`. The new override additionally erases
that retained header and advertises complete parent ownership. A complete grid
accounting proof or visible refusal is required before this relation is safe.

### 3. Governing signing/consent context bypasses the new guard — base-existing

`rebuild/documents/word_v3.py:1554` checks the local source but not the complete
heading context returned at line1548. In `consent_scope_specific.docx`, Heading1
is `Participant consent for optional procedures`; the local parent is `Which
procedures are authorized? Tick all that apply.` with `☐ Blood sampling` and
`☐ Tissue storage`. 904/1bc emit an unprotected `multi_choice`, preserve the consent
heading in context, emit no warning, and accept `['Tissue storage']` to mark that
consent box. `Signed declaration` as Heading1 has the same result. The equivalent
signing term inside the local parent is refused visibly in the positive guard
control.

Base649 also allows these checkbox writes. This is not attributed as a newly
introduced signing defect. It refutes the new route's complete signing/consent
containment claim and its omission is directly adjacent to the added source guard.
The probes demonstrate detector/writer behavior, not a model or generation outcome.

## Other bounded observations and limits

Complete ordinary parents, explicit donor headings, separate subsection/grid
sequences and native checkbox controls retain the tested question and state.
Marked spacers, competing questions, unpaired subsection labels, and mixed
parent/subordinate boxes are visibly refused. Recorded changed paragraphs remain
within the selected checkbox grid; no neighbor text loss was demonstrated.

An inline page break and an intervening empty nested table were also preserved as
probes. They did not independently establish a wrong clinical attribution and are
not promoted to findings. This review does not establish complete D03 coverage,
large-form admission, automatic clinical option semantics, rendered/native Word
compatibility or any qualification denominator. All prior failures and maps stay
unchanged. Findings 2–3 remain open at this checkpoint; author repair is separate.

## Subsequent exact repair closure

Frozen source `cf481504697c5028f3ae84534bd343792ec91009`, engine SHA256
`7d2296ea679c7e804bdb8ea88a7a539c01cb7654527f1b0b65dc87f3ee42c2a6`, closes the
three demonstrated cases/classes above. **The same19 synthetic fixtures pass**
their bounded ownership, refusal, printed-state and exact neighbor-preservation
checks. The two-role grid is now visibly unresolved with both source headers;
governing consent and signing context appears in the refusal; single-option and
subsection context remains complete. No additional cases were introduced during
closure. **NOTHING FOUND within these bounded claims on the final repair.**

The complete D03 mapping and notes remain exactly equal to 904's43-field result.
This preserves the earlier selected-workflow boundary, not a whole-document pass.
All earlier errors, mappings and exports are retained.

The first closure harness attempted nonexistent `Package.read`, an instrument
error. Its script and partial outputs remain. `closure-v2.py` changes only that
byte-reader to `ZipFile.read` and writes a separate directory. Final evidence is
`closure-v2/closure-results.json`; the complete predecessor-linked seal is
`seal-closure.json`. No application source was changed by the reviewer.
