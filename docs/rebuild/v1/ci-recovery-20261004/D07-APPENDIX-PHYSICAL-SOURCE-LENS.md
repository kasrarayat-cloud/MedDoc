# D07 appendix physical-source lens — 2026-10-04

The original D07 has six full appendix captions that each match exactly one physical selection question. No ambiguity was found in these six original caption-to-question relationships. The current existing classifier nevertheless recognizes none of their complete positive commands: all six fields remain `choice`. A repair needs both exact physical-source binding and qualified selection grammar; binding alone does not close the six wrong kinds.

This is independent read-only source/destination evidence, not verification of a new appendix implementation. The original remains SHA256 `f43d08e3b4361ea7161572917a8839beea7f79ba2497a14dca7493ddf6e67cc3`. The fixed GT remains `27f3a8d356c15311f815cd8943bfae26cefd073fe92512ded0c6a4be6aab91e6`. The recorded prior **16/28 correct, 6 missed, 6 wrong, 4 extras** stays historical; this lens does not regrade it or change the 60/20 denominator.

## Exact original relationships

All source and target slots below are in `word/document.xml`. The full source paragraphs, raw subtree hashes, exact control lists and complete current inspected fields are retained in the adjacent receipt/protected evidence.

| Fixed destination | Appendix source | Complete printed caption | Physical question owner | Printed positive selection command |
| --- | --- | --- | --- | --- |
| A11 | `b/p[22]` | How researcher determined intervention was delivered | `b/tbl[1]/tr[1]/tc[0]/tbl[0]/tr[0]/tc[1]/p[0]` | Select more than one source if relevant. |
| A20 | `b/p[28]` | Recipient(s) | `b/tbl[1]/tr[1]/tc[0]/tbl[1]/tr[2]/tc[0]/p[0]` | Conditional extensive participation from both recipients → select both; one primary recipient → select that one. |
| A21 | `b/p[29]` | Format | `b/tbl[1]/tr[1]/tc[0]/tbl[1]/tr[3]/tc[0]/p[0]` | Conditional multiple/changed formats → select both formats. |
| A22 | `b/p[30]` | Modality | `b/tbl[1]/tr[1]/tc[0]/tbl[1]/tr[4]/tc[0]/p[0]` | Conditional multiple/changed modalities → select all relevant modalities. |
| A23 | `b/p[31]` | In-person location | `b/tbl[1]/tr[1]/tc[0]/tbl[1]/tr[5]/tc[0]/p[0]` | Conditional multiple/changed locations → select all relevant locations. |
| A24 | `b/p[32]` | Reason not delivered | `b/tbl[1]/tr[1]/tc[0]/tbl[1]/tr[6]/tc[0]/p[0]` | If known, select a reason or reasons; unknown instruction remains part of the same source. |

The independent comparison removes only a printed leading question number, terminal colon/question mark, case and repeated whitespace. It keeps the entire caption, including `Recipient(s)` and the `In-person` hyphen. The physical owner is the complete question header before its native control group, not an ancestor table's aggregated text or an arbitrary noun elsewhere.

Exact frozen `b98b98fc893acf2b17004945e0e1721fd2b0da97` Word source SHA256 is `5cd57ce0b01faa6037485f0f14433714a6b0b2550168acb2d09edba6d70e8511`. Its `many_evidence` (`documents/word_v3.py:1406`) returns `(False, '', '', False)` for every full paragraph above, and `one_only` returns false. `Detector.cardinality` at line 2208 currently takes local physical source and excludes unowned positive instructions; `MANY_COMMAND` at line 1146 does not express these plain complete positive commands. These are two independent missing qualifications, not permission to treat every mention of “more than one” as multi-choice.

## Minimum scope and safety controls

The original provides strong negative controls. At `b/p[27]`, Provider type says that if more than one provider was involved, the user should select the code for the **most-involved provider**. It remains one selected provider. At `b/p[21]`, Delivered describes separately choosing Yes, No or Unknown under different conditions; several `Select` verbs do not grant several simultaneous selections.

Nine finite control records and three supplemental XML counterexamples are retained. They demonstrate the boundaries a future implementation must keep:

- A cloned visible Format group creates two distinct physical question owners with the exact same normalized caption. A global caption match cannot choose one of them.
- A hidden Format instruction cannot grant visible selection capacity.
- A unique Format question plus both a Select-both instruction and a separate Select-one-only instruction is still a conflict. Unique destination identity alone is insufficient; all competing source commands must be captured.
- `Format of delivery` does not match `Format`; neighboring Format and Modality groups remain distinct. No stem, prefix or global instruction transfer is justified.
- Recorder Signature is a human destination, not a complete native selection question; appendix wording cannot release signing or other-person authored destinations.

These are physical controls and required outcomes, **not nine passed production feature tests**. The conditional one/both branches of the original Recipient(s) paragraph must remain intact. Numeric lower/upper-bound or exact-count rules remain held under the existing contract; this evidence supplies no globally permissive count rule. Any new source evidence must remain bound to the immutable original, full source paragraph/physical question and reviewed destination through export, and be recompiled against the original rather than accepted from a forged saved field.

## Six other recorded omissions remain separate

| Fixed destination | Actual printed destination | Independent fact |
| --- | --- | --- |
| A13 / A15 | Required nested table `tbl[0]/tr[1]/tc[0]` and `tc[1]`, `p[1]/ff[0]` | Separate legacy “Or Unknown” boxes beside Start and End date, each one native checkbox. |
| A17 | Optional nested `tbl[1]/tr[0]/tc[0]/p[0]` | Same paragraph as Number of completed sessions. Plain spaces before printed **minutes**, zero tab/ptab/checkbox. The unit is only minutes; fixed source/GT has Min=1, max=999. |
| A26 / A27 | `b/p[1]` | Recorder Signature and Date share a paragraph, with ten plain tabs between the two captions. Signature remains an explicit human act; the date must use its own exact physical destination. |
| A28 | `word/footer2.xml#hf/p[0]` and `word/footer1.xml#hf/p[0]` | Initials in the first-page and latent continuation footers; each paragraph contains two positioned tabs. The instructions footer has no Initials. |

An appendix-cardinality repair cannot close these physical destination omissions. No signature/initials, date, number or medical interpretation was supplied by this lens.

## Actual execution and retained refusal

The bounded pure child exited 0 in 1.773 seconds; script elapsed time is 1.581 seconds. Source and original bytes are unchanged, with no database, renderer or provider call and no Word-source edit. Current inspector result SHA256 is `c07307ceac7ae0cd4127e83d43d61e4a97a2f2f23d919cd2059bb67d857bd1a9`. Own result SHA256 is `0b02974dcd122bb78a5e918395b5be0a93774c96c27ee9ea1dfb4548522fbcfa`.

The first binding instrument correctly refused with exit 1 at 0.165 seconds: the retained earlier mapping's Word source hash `11d146…` differs from actual frozen b98 source `5cd57c…`. Its original traceback and prospective manifest remain retained. The distinct replay records a fresh current inspector result and keeps the older 16/28 score separately; it does not relabel the old evidence. An earlier unqualified system-Python read failed before original XML parsing because lxml was unavailable; the qualified existing interpreter was used thereafter.

Protected evidence: `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/d07-appendix-physical-lens-20261004/replay-02`. No new automatic mapping success, first-generation usefulness, native Word or whole-document acceptance claim follows from this lens.
