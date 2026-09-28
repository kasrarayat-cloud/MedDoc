# Original checkbox identity through answer insertion

## Source and concrete failure

Frozen source `2e0dc20e62832208f23c4b29ab07ae4da104898d`, branch
`v1-word-workflows`, engine SHA256
`49c519fc8c7e2ca3600b1a36842c9ae2abcaa5ce6d22793f302bb39a1d109a02`.
This follows independently closed nested ownership source `cf481504` and changes
only the writer/readback and its tests. No new write-in detector eligibility is
included yet. Independent finished-diff refutation is pending.

Preparing disjoint checkbox/write-in support exposed a pre-existing writer defect.
The constructed exact source is:

```
Choices? ☐ Before: _____ ☐ After
```

With source-bound checkbox references, a separate nonoverlapping blank span,
requested Before and After selections, and answer `literal ☐ symbol retained`,
the former writer returned:

```
Choices? ☒ Before: literal ☒ symbol retained ☐ After
```

It changed the answer text and left the original After unchecked. Its ordinal
readback nevertheless returned `[true, true]`. Root independently reproduced the
physical XML defect. This proof uses explicitly constructed source mappings; it
is not evidence that the old automatic importer already exposed that combined
span/checkbox mapping through upload. The actual automatic write-in path remains
the next implementation slice.

The first probe's import error is retained (`probe.log`); the corrected six-case
probe and all original/filled DOCX artifacts remain separately preserved. Native
and legacy control references were stable in those same before/after controls.

## Repair and boundaries

1. Validate existing source mappings and collect original glyph operations.
2. Apply each requested original glyph state before any text insertion. These
   one-character changes preserve source text offsets. Conflicting requested
   states for the same source box refuse.
3. Isolate and retain the actual original glyph leaf nodes. Ordinary disjoint
   span edits may split neighboring runs or insert checkbox-looking characters;
   those new characters cannot take over a retained identity.
4. Refuse if an operation removes an original retained leaf or moves it away from
   its original paragraph/document part.
5. Derive final XML paths from the retained identities after all edits, serialize,
   then read those exact leaves from the written package. Compare their actual
   states with the clinician's requested options. This physical readback is a
   mandatory argument to export verification; an ordinal-only fallback is absent.

The existing native/legacy control writers retain their structural references.
Missing answers do not request new checkbox state edits. Existing protected
signing checks remain before mutation, and the floating-initials refusal now
accounts for the separately collected glyph operations as well as other writes.
Original templates, stored mappings, finalized exports and recorded hashes are
not migrated or rewritten.

`option_states` remains an original-layout ordinal reader. It cannot relocalize
old mappings in a filled paragraph containing newly inserted box characters.
Its `[true, false]` result on the correctly repaired complex output is retained
and explicitly **not** used as export-verification authority. The final writer
uses the source-derived physical leaves described above. Re-uploading a populated
document as a new blank template is not part of this proof.

## Finite evidence

Private runtime: `rebuild/.runtime/word-writein-proof-20260928/`.
Text-only evidence and complete private-file hashes:
`word-glyph-identity-evidence-20260928/`.

| Evidence | Outcome |
| --- | --- |
| `probe.log` | Initial import failure, retained as instrument failure. |
| `probe-corrected.log`, `result.json` | Six constructed source controls; glyph-before/after case demonstrates physical corruption and false-green readback. |
| `01-glyph-source-red.log` | Two failing concrete glyph cases, one positive trailing-only control. |
| `02-glyph-source-after.log` | First physical-identity regression test passed. |
| `03-glyph-focused.log` | Four methods passed, covering mixed controls, long text, missing states, stale references, removed boxes and corrupted serialization. |
| `04-glyph-affected.log` | 121 affected Word/signing/question-box and authenticated synthetic workflow tests: 120 passed, one refused safely with the wrong diagnostic code. Preserved, not reported as a passing suite. |
| `07-final-glyph-focused.log` | Four methods passed after making physical readback mandatory. |
| `08-final-glyph-and-original-workflow.log` | Original D03 authenticated missing/ordinary workflow and four new methods passed; old broken-writer test still failed on missing field name in the refusal message. Entire six-test run therefore failed. |
| `09-final-glyph-readback.log` | Final five affected/readback methods passed, 2.005 seconds; old diagnostic code and field-specific message restored by the mandatory serialized verifier. |
| `11-final-original-export-equivalence.json` | Both final-source exports exactly equal the successful actual original workflow captures. |
| `12-render-equivalence.json` | Changed D03 ordinary export remains four pages; page 2 PNG is byte-identical to the previously reviewed output. |

The 121-test regression run crossed only the keyword/docstring tightening recorded
in `06-verification-contract-change.txt`; some sandbox workers load source afresh.
It is useful regression evidence, not an exact final-source full-suite citation.
The final changed checks and final-source exact export equivalence are separately
recorded. Required CI on the integrated candidate remains the release citation.

The serializer negative control deliberately corrupts the original After mark and
checks the inserted symbol, recreating the old misleading ordinal arrangement.
The new verifier refuses the export. Direct XML assertions independently check
literal answer text and printed Before/After positions; native checked flags and
visible content, and legacy checked states, are separately checked. These are
synthetic local controls, not provider or native Microsoft Word checks.

## Actual original workflow and render

Authorized blank original D03 SHA256 remains
`29dfcdd8a5daef213e30e03e5062fa9193a31a53651c880acc498006c1d506ff`.
The actual authenticated fixture reuses the complete original template, mapping
review, mocked worker, clinician correction, finalization and export download.
As in the preceding ownership report, ordinary option completion is clinician
assisted; no automatic clinical interpretation or document success is claimed.

- Missing export SHA256:
  `fdfca49601684ebac5183e4c54fed81442b1e00d29835dfa1c2f3a1516eb887a`.
- Corrected ordinary export SHA256:
  `33cdae91b521a07fa8f886d78629268a1ad5e2070a56fd72dcb154f594dfd2cf`.
- Affected rendered page PNG SHA256:
  `8ba6128c771e759573ef8a9d4c1f92edf3236eb1f1ebf42ab95e19d67d19c6a2`.

The latest changed export was rendered once using the same cached pinned,
network-disabled and resource-limited LibreOffice route. Its affected page equals
the preceding image byte for byte, so the prior visual comparison is reused on
that exact boundary. PDF and PNG locations are recorded in `12` evidence. Native
Word and whole-document qualification remain unperformed.

D03 still fails overall. This repair prevents a concrete corruption before adding
the common checkbox-plus-write-in path. Separate population, source context,
missing/ordinary/long workflow evidence and independent refutation are still
required for that next slice. No corpus denominator, first-pass result, authority,
receipt or account setting changed. No live provider request or deployment occurred.

## Independent namespace-alias counterexample and correction

Root's independent pass preserved 36 varied physical-XML controls that passed on
`2e0dc20e`. It also found an ordinary valid namespace layout that the new verifier
refused: a local `x:r`/`x:t` alias for the Word namespace, with only `w` declared at
the root. The retained leaf's XPath used the local alias, while lookup bound only
root namespaces. The original document and exact reviewer probe/result are retained
as `local-prefix-original.docx` and `13` evidence. This was a compatibility defect,
not grounds to exclude ordinary DOCX namespace aliases.

Repaired source `a23fc97b64405721d55979e7bfb53d2285032d81`, engine SHA256
`e48f3e616246e5c3a3f4518975f5dc9a1f782a2ef9bb75ca65c208e5d779eb10`,
uses a path of full Clark tags and same-tag child indices derived from each retained
node after edits. Readback therefore depends on element identity and namespace URI,
not prefix spelling or declaration scope. No XPath prefix lookup remains.

The new local-alias control failed before repair (`14`) and passes afterward.
All six focused/readback methods passed in `15`, 1.980 seconds. Replaying the exact
reviewer's original bytes and saved mappings now produces:

```
☒ First: literal ☐ text ☒ Last
```

`16-local-prefix-repaired.json` records exact source/export hashes and confirms
that the actual original D03 workflow export remains byte-identical. Its existing
render evidence is therefore reused without another render. Source is frozen for
root's unchanged bounded independent replay. No additional importer eligibility,
corpus run or provider request was introduced.
