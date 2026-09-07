# THE 53-CONTROL CONSULTATION FORM — ITS DERIVATION, AS ITS PROVENANCE

**Ruling #209, 2026-09-07.** *"The reconstruction IS the regeneration — the same
deterministic rule over the same source bytes. No re-upload. Re-run the five
additive proofs on it and record the derivation as its provenance; it is the
form that certifies."*

This is that record. The rule is executable at
`apps/transcribe-md/scripts/regenerate-consult-form.ts`.

## THE TWO PINNED SIDES

| | |
|---|---|
| **source bytes** | `sha256 6f04f29e33835e62b956e32bed349f6a0ce4a259a763027187d9d58492f70076` — the owner's BLANK 35-control GI consultation form |
| **the rule** | the six sentences of the GI-ROS paragraph; the ten exam value runs; the telehealth consent line; the total-time blank |

**35 + 6 + 10 + 1 + 1 = 53.**

⚠️ **THE ARITHMETIC PINS WHAT IS EXCLUDED, NOT ONLY WHAT IS INCLUDED.** The
second *"Review of Systems"* sentence — *"A thorough 14-point review of systems
was performed and remarkable findings were documented in the HPI."* — is
deliberately NOT a control. Including it gives **54**, and the ruled total is
**53**. That is the check that stops the rule drifting, and it is proof P5.

## THE FIVE ADDITIVE PROOFS

⚠️ **DERIVED, NOT QUOTED — stated so it is not read as more than it is.** #191
records that *"all five additive proofs held"* and does not enumerate them, and
no other file in the record does either. (The five proofs in
`docs/foundation/relay/README.md` belong to the LEDGER SPLITTER and are a
different subject entirely.) The five below are what a purely **additive**
regeneration must prove — it adds 18 controls to a 35-control document and must
disturb nothing else. **If the original five are recovered and differ, this
document is the defect.**

| | proof | what it catches |
|---|---|---|
| **P1** | source identity — the sha256 is the owner's blank form | the rule applied to a different document, producing 53 controls that mean nothing |
| **P2** | the ruled arithmetic — 18 added, 53 total | a clause silently merged or split |
| **P3** | nothing disturbed — all 35 original ids present, `w:sdt` tags balanced | an "additive" change that renumbered or dropped an existing control; it would pass P2 |
| **P4** | prose unchanged — every clause sentence still present verbatim | a control that REWROTE the doctor's words instead of wrapping them; it would also count 53 |
| **P5** | the exclusion pinned — the 14-point ROS sentence is still static prose | the rule drifting to 54 |

**All five held.** The script exits non-zero and writes nothing on any failure.

## THE ARTIFACT

| | |
|---|---|
| `word/document.xml` sha256 | `ecb817039a035e975cf73605f4e5ba68a88362a5a27f02d204e6e11903cf241d` |
| package sha256 | `5367fd075472cc2c6a1de768c5224e7522691ccad3d2c7aafc47071752920642` |
| compiled | `fields=53  scaffolded=53  scaffoldText=53  unsupported=0` |
| `structureSha256` | `f1bb9365b71b407bd0bc6a09661f005d55504e392cde1487233945f0aeb02163` |
| `compilerVersion` | `template-docx-compiler/1.0.0` |

`fields=53 scaffolded=53 unsupported=0` **reproduces the measurement
`note-template-docx/compiler.ts:344` records of the lost original**, which is
the independent corroboration that the rule is the right one.

Of the 53, **17 carry real clinical prose** — the six ROS clauses, the ten exam
clauses and the telehealth line. The remaining 36 are underscore furniture, and
the 18th added control is the total-time blank.

## ⚠️ THE FORM IS PRODUCED ONCE, AND THE REASON IS NOT CONVENIENCE

**`fieldId` is salted with the WHOLE-PACKAGE sha256.**
`note-template-docx/compiler.ts:836` derives it as
`stableId('ttf_', 24, state.sourceSha256, partName, nodePath, kind)`.

**MEASURED:** two runs produced a **byte-identical `word/document.xml`**
(`ecb81703…` every time) and compiled to **different** `structureSha256`
(`6b58f00f…` and `32c421f3…`), because JSZip is not a reproducible-archive
writer — three attempts to pin it left 2, then 2, then 14 bytes moving, all of
them DOS-time fields in zip headers.

> **So the FORM is deterministic and its COMPILED IDENTITY is
> package-dependent.**

⚠️ **AND CERTIFICATION IS KEYED TO `fieldId`.** The 2026-09-03 transfer rested
on *"match on fieldId: 35 — the ids themselves are identical"*, which held only
because the same BYTES were re-uploaded. A form regenerated a second time would
mint a **new identity** and no longer match its own certification.

**Therefore: this artifact, at package sha `5367fd07…`, is the one that gets
uploaded and certified.** Re-running the script to obtain "the same" form is the
one thing this provenance exists to prevent.

## WHAT THIS DOES NOT CLAIM

The clause boundaries within the GI-ROS paragraph are the ruled six sentences,
and the exam clauses are the ten authored lines. **#209 settles that these are
the rule.** What is recorded here is that the rule was applied to the right
bytes and that the result has the properties the ruling and #191 both name.
