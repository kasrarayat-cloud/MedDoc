# QuillMD semantic facts: independent finished-diff refutation

Date: 2026-10-10; SOAP follow-up controls: 2026-10-11. Reviewer: `diagnose_narrative_validation`, independent of the product module and integration authors. Preflight: lead-agent GO report `preflight-20261010T231028Z.md`.

## Result and scope

**No remaining demonstrated defect was found in the finished source examined below.** The pass initially found concrete defects; the counterexamples were reproduced, repaired or excluded through a supported server gate, and rerun against the finished files. This is a source and isolated-fixture assessment. It does not certify a model's clinical accuracy, provider invoice amounts, production installation, or a served-browser workflow.

The reviewer made no provider requests, native database queries, production mutations, credential reads, service actions or commits. Fixtures contain synthetic statements created for these controls. The lead agent owns installation, live verification and the complete regression suite.

The pass examined concise source-value rendering, compound positive and negative facts, subject/time/unit/scale attribution, governing context, independent checking and bounded repair, stored-proof verification, clinician edits and explicit blanks, approved destinations and versions, provider evidence durability, aggregate accounting, status previews and backup references.

## Finished byte bindings

| File | SHA-256 |
| --- | --- |
| `rebuild/core/semantic_generation.py` | `d2a12f45e8affa36379ee26c792bb662559782ca115ab60a7ccc9d63d5345ba5` |
| `rebuild/core/semantic_review.py` | `ea836655f8ffa1ca977fc202cbdceb55095807478586b717fd1dd85ecc1ca861` |
| `rebuild/core/tests/test_semantic_generation.py` | `d34229348027d54648e17f2e2d5409ecd8a08e353237c4677bb952359352c646` |
| `rebuild/core/management/commands/audit_billing.py` | `4cae0b715b0ca0b80b54b78835828396b562c3657e3da31579961389402aae45` |
| `rebuild/core/ai_stages.py` | `59ef9187c5d01c9efa7829f210d3e4f902048655f1a6687c63758e3dc193c1a4` |
| `rebuild/core/migrations/0026_semantic_stage_receipts.py` | `bfdc362a31440974f630f1e3cb61dc8141b8b7e97a0ffd823baf51f2e1333a33` |

The protected `integration-freeze-v1.json` receipt has SHA-256 `3a235b3dbb97f3033cad415cf90d4c1cf31fc6386b98076272ce8579b771a7a8`. All 18 listed source hashes were independently checked against the worktree: **zero mismatches**. The historical `core/generation.py` and `core/wm_review.py` have no diff from the feature baseline.

## Concrete counterexamples and disposition

The file and line references below identify the finished enforcement points, rather than the superseded faulty line numbers.

| Demonstrated input or operation → incorrect earlier result | Finished disposition |
| --- | --- |
| Select `ankle pain` from `The patient reports left ankle pain.` → supported answer dropped laterality. Select `swelling` from `Examination shows mild swelling over the left lateral ankle.` → answer dropped severity and site. | `semantic_generation.py:125` holds omitted adjacent clinical qualifiers and sites. Complete qualified phrases, including the exact requested narrative, remain supported. |
| Cite both units of `Mother reports diabetes. The patient reports ankle pain.`, annotate the pain with Mother's exact name → supported other-person answer. | `semantic_generation.py:203` holds unsupported cross-statement attribution and explicit patient attribution contradicted by another subject annotation. Same-sentence countercontrol also passes. |
| Select historical pain from `The patient had left ankle pain last year. The patient currently has no ankle pain.`, borrow `currently` from the second unit → supported current pain. | `semantic_generation.py:203` holds timing borrowed from another statement and explicit past time presented as current. |
| Select `3` from `Vein diameter is 3 cm. Another diameter is 4 mm.`, borrow exact `mm` from the other measurement → supported value `3 mm`. | `semantic_generation.py:203` requires the unit to directly qualify the selected numeric value in its own statement. Another-number-in-the-same-sentence countercontrol also passes. No conversion is performed. |
| Select `3` from `Temperature is -3 C.` or `Temperature is .3 C.` → supported positive integer 3. Select a prefix or exponent tail of `1,000`, `1e3`, or `1e-3` → supported unrelated numeric value. | `semantic_generation.py:230` refuses these partial numeric tokens. Complete `-3` and `.3` retain their original values. Grouped and exponent forms are refused rather than converted. |
| A scale reference borrowed a denominator or another measurement's range → wrong scale accepted despite exact individual spans. | `semantic_generation.py:175` binds the selected score and supplied scale to the same explicit source expression. |
| Assign the numeric fact `3` from `Pain is 3 out of 10.` to SOAP Subjective → the display and Word value lost its clinical label and scale. Relabelling that fact as `history` initially bypassed the new hold. | `semantic_generation.py:380` holds bare numeric source values in approved narrative text fields independently of the extractor's fact-kind annotation. A separate exact source phrase `Pain is 3 out of 10` remains supported alongside the typed numeric value 3. Stored proof revalidation also refuses the clipped narrative. |
| An exact complete narrative summary and numeric facts for the same measurement → a false numeric conflict; conversely the same score on conflicting 5- and 10-point scales could be treated as equal. | `semantic_generation.py:410` limits numeric peers to numeric source values and compares value, unit and source scale. The controlled 3/3.0 equivalence stays supported; competing 3/5 and 3/10 retain both contexts and remain held. |
| A negative fact fragment lost its source negative word, or a conjunction inherited the wrong polarity → unsupported absence could be synthesized. | `semantic_generation.py:125` retains actual negative phrases, handles the tested shared predicate, and holds nested or unresolved negation. Rendering synthesizes no negative claim. |
| Invisible-format reframers, family-history context or an unbound correction could disappear from a supported value. | `semantic_generation.py:230` reuses the positioned governing reader and retains exact governing evidence; unresolved context remains held. |
| A checker pass referenced other fact IDs, or a rejected fact reappeared during repair → unsupported proof could pass. | Exact selected-ID binding and the union of rejected facts survive the single bounded assignment repair and recheck. No extractor repair or extra call is permitted. |
| A standalone manual marker or a review tick on concealed invalid text could bypass generated proof; an ordinary empty Save could silently clear retained content. | `semantic_generation.py:605` validates attributed manual history, status and typed values. `semantic_review.py:29` requires a separate explicit blank decision or a nonempty clinician edit, preserving the prior snapshot. |
| Raw provider output was retained but actual request IDs could be lost when usage parsing failed. | `ai_stages.py:198` retains both actual IDs in the raw wrapper and saves them before meter parsing. A uniqueness collision retains the wrapper and requires reconciliation. |
| A newly approved semantic WM numeric field could not pass the existing unit-text guard; the immutable SDK also requires historical labelled evidence. | `semantic_preparation.py:46` and its shared source gate refuse prospective semantic preparation for `wm-iov-foss-v2` before any receipt or provider send. The UI explains the limitation. The qualified historical WM path is unchanged. |

## Executed checks

The reviewer independently ran **59 pure tests, all passing**: 53 source/proof/review generation controls and six aggregate-cost controls. The final run took 0.848 seconds using the isolated Django fixture settings and a plain unittest runner; it did not set up or query a database. `git diff --check` passed after the final report update.

The clinical corpus includes the exact eight-field narrative regression, a labelled SOAP case with a complete narrative pain measurement and a separate typed score, independent role/call boundaries, compound positives/negatives, multiple people, missing and contradictory values, corrected measurements, source scale relations, protected signing destinations, printed dates, strict API quotation/occurrence references, stale persisted proofs, bounded repair, explicit manual edits and explicit blanks. These fixtures demonstrate code behavior with controlled replies; they do not measure provider first-pass quality.

The financial source pass confirmed independent per-stage rounding before summation, one aggregate usage/receipt, no fabricated aggregate provider ID, preservation of earlier known costs when a later outcome is unknown, retained holds and no automatic resend on uncertainty, and stage request/response file references in backup validation. The integration author separately reports database-backed stage, sponsor, collision and WM-gate tests; those executions were not performed by this reviewer.

## Limits retained deliberately

The finite source guards supplement the independent checker and clinician review; they are not a complete clinical language parser. Unsupported cross-statement antecedents, prefix units, uncertain scope, unresolved corrections and unfamiliar numeric notation can require a clinician decision. No source or response is truncated to make validation pass.

Advanced WM forms remain on their qualified labelled-evidence workflow until a separate semantic SDK protocol is qualified. Ordinary prepared Word forms use the separately approved semantic version; prior mappings and documents retain their original behavior.

The three API roles, raw evidence, time boundaries and calculated costs are durable receipts. A mocked passing checker does not establish provider quality, and a calculated provider cost does not establish an invoice-confirmed charge. Served-browser and downloaded-Word evidence must be reported separately by the lead agent.
