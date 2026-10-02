# Independent closure and adjacent refutation — 90297ea9

Frozen source `90297ea971528b0b90f68a0e770ea89088672761`; Word reader SHA256 `ffcba8b32e52aa7f0702c776ab4c7d0fae86e18f2e733a24f1dc1980e5bb97e4`, batch module `0c50c911a75faa8e73e37caa2fc79e399ae3aae8fb4ef55085854af68ec079ef`. No implementation file was changed by this reviewer. All packages remained in memory; no DB, network/provider, HTTP, sandbox subprocess, native Word or external account was used.

## Closed original cases

The unchanged `probe.py` completed all33 cases with zero mismatches against this source. First `01-results.json` is unchanged; new results are `02-closure-90297.json`. Because the script is unchanged, its historical `frozen_head` label remains952c7e21; the recorded source hashes and this separately verified freeze identify the new replay correctly.

This independently closes the retained F-B5 false/invalid placeholder cases and F-B6 missing-separator case in the stated component scope. Genuine placeholders, replacements, copied anchors and original F-B3/F-B4 controls continue to behave as expected.

## F-B7 — additional content body erased by first-child reading

`rebuild/documents/word_v3.py:3764` and`:3822` use `.find(w:sdtContent)` in the constrained dropdown/scalar readers. They verify presence but do not require that the content body is unique.

Concrete input: an inspected103-field synthetic package contains scalar/date or dropdown Priority A with two direct `w:sdtContent` children. The first is empty; the second contains `w:t="1"`. A is blank/reviewed and Priority B is explicitly answered1. The qualified uniqueness rule permits1/2/3.

Observed on both control kinds: **ACCEPTED**, effective A`[]`, B`["1"]`; the actual output XML retains A's second content value1 and B's written1. The reader has accepted an ambiguous/malformed control as a known empty value. The package is malformed; there is no claim about desktop Word's rendering or schema acceptance, and no claim that every surrounding application admission gate accepts it. This is a demonstrated failure of the constrained-reader unknown-state contract.

## Other adjacent evidence

`adjacent.py` completed38 probes:35 matched their declared expectation,2 are F-B7 above. The remaining observation is two legacy `separate` elements inside the same run being accepted despite the exact-one-separator claim: the check counts runs containing separators, not separators. Both exported values were still read as1 and2, so this is **not promoted to another demonstrated wrong-value finding**.

The adjacent controls cover all genuine true placeholder encodings, invalid and duplicate flags, false flags on unknown values, explicit replacements after invalid flags, and text embedded in each legacy begin/separate/end marker run. Files `adjacent.py`, `03-adjacent-90297.json` and this report are separate from the original retained evidence. Root and author received the finding before any source repair.

## Bounded F-B7 property-body sibling

At root's request, a final two-case probe checked the corresponding `.find(w:sdtPr)` in `constrained_placeholder` at`:3740`. A native scalar/dropdown A has two property bodies: the first marks the content as a placeholder, the second explicitly sets `w:showingPlcHdr w:val="0"`. Content is1; A is blank/reviewed and B is explicitly1.

Both cases are **ACCEPTED**, A`[]`, B`["1"]`, retaining A1/B1 in output XML. This is the same F-B7 class: first-child selection turns conflicting malformed control structure into a known empty value. Exact files are `duplicate-properties.py` and `04-duplicate-properties-90297.json`. No native rendering or surrounding application-admission claim follows. The review remains bounded to the constrained reader, with no proposed general parser rewrite.

Frozen review is complete:33 unchanged original cases match,35 of38 initial adjacent cases match,4 concrete F-B7 control variants fail across the two adjacent probes, and the single same-run separator observation remains a narrower claim mismatch only. All source hashes still match the freeze.
