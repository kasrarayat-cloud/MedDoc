# Preserve answer-cell guidance without erasing existing constrained values

Prepared structural repair; no provider, activation, deployment or paid calls.
The original D31 development witness showed that a `cell_replace` mapping with
`all=True` deleted substantive grey instructions about third-party information
and patient comments. The source, first export and first failure remain under
runtime `document-relations/D31-guidance-loss-first.*`.

New mappings use `cell_append` and retain every original paragraph. Their
`source_instructions` carries complete source text plus part, cell path and
whole-cell fingerprint. Export validates the exact metadata against the original
before appending the complete answer in black. The metadata supports up to
20,000 Unicode characters; 20,001 refuses without shortening. Historical
`cell_replace/all=True` maps retain their exact stored shape and now preserve
source paragraphs when exporting; existing files and maps are not rewritten.

A second first failure was independently reproduced on the handed-off repair:
a grey or blue `1` followed by appended `2` was read as only `2`; `Yes` followed
by appended `No` was read as only `No`. All eight cases affected both new and
historical mappings. Their complete input mappings and outputs remain in
runtime `document-relations/handoff/preserved-value-first.json`.

Both constrained scalar and option readers now return unknown for these append
areas, whether an answer is supplied or omitted. Colour does not prove the
original text is an instruction or that an existing value may be disregarded.
The structural append reader can verify what was newly written, but cannot
establish the complete clinical value of the cell. Global rules therefore
refuse these unknown states. Ordinary unconstrained guidance preservation still
works. New/legacy constraints are not bypassed by changing a test label.

Explicit `For RC:`, `For the RC:`, `For QA:` and named `Completed by` roles end
the preceding patient-author scope. Patient examples and ordinary mentions do
not acquire or reset authorship without the recognized structural boundary.
Attestation source metadata also follows the new append target. Additional
instruction interpretation remains a separate clinical requirement; D31's
conditional guidance is not qualified by the left-hand question alone.

Validation on the finished source:

- 158 affected Word, question-box, relation, hyperlink, role and guidance methods
  passed in 80.176 seconds.
- 24 actual sandbox constraint-reader methods passed in 56.963 seconds, including
  the retained-value counterexamples and unchanged native/plain positive controls.
- The complete 20,000-character instruction survived inspect, JSON persistence,
  sandbox export and exact original text read-back; the 20,001 boundary refused.
- A mapping produced by the actual `a8f636ea` engine was persisted through JSON
  and exported by this repair without any mapping mutation; all original
  paragraphs and the full new answer remain. Its constrained value is unknown.

Integration needs the same instruction annotation in `layout_source.prepare`
(the D10 component is absent from this branch): within its `annotate_printed`
loop, for `cell_append`, assign
`field['source_instructions'] = w.cell_instruction_source(detector.index, field)`
before `source_policy.annotate`. The shared helper is the same one used by
ordinary inspection. That combined route requires a focused integration check.

Independent finished-diff refutation remains required before closure. Evidence
is synthetic or the authorized original D31 development form; filled documents
remain runtime-only and are not tracked.
