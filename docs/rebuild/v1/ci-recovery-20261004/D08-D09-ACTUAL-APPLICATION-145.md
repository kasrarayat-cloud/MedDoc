# D08/D09 actual application and archived render continuation

The actual original-corpus packet used immutable `1459595edd4551dc4eb9427ccc89da9bda87604f`, unchanged D08/D09 originals, fixed ground truth, answer profiles, scorers and thresholds. Both are previously exposed development cases with documented internal/offline replay rights; their provider upload remains denied. No provider call, installed change, clinical usefulness claim or new independence claim follows.

The two route methods completed in 33.401 seconds with real child exit 0. The driver and supervisor correctly exited **1** at 75.399 seconds: the fixed whole-document gate passed zero of the two in its initial adjudication. Original failures remain unchanged. Source and harness manifests match before/after. Normal and test QA databases are absent by direct catalog readback; renderer and runner PIDs are absent, renderer exited −2 and the socket is removed. No D10 repetition or cleanup occurred.

| Original | First-pass mapping | Empty profile | Ordinary / long profiles |
| --- | --- | --- | --- |
| D08 | 29/41 correct, 2 missed, 10 wrong, 5 extra; strict false | Finalized/downloaded, but raw document XML changed | Both save routes returned 400; no export |
| D09 | 47/47 correct, zero missed/wrong/extra; strict true | Finalized/downloaded; byte-identical original | Both finalized/downloaded; mechanical checks pass |

D08's retained refusal states that “SDU” is a checkbox and accepts only checked or empty. The fixed GT names an ICU/SDU choice group; the automatic map splits SDU into a checkbox. The profile and scorer were not normalized to make this pass. Word owns the cardinality diagnosis.

The empty D08 export adds exactly seven explicit zero `w:checked` elements where the original legacy checkboxes already have default zero. The actual caller sends False for each reviewed ordinary checkbox. A pure unchanged-source reproduction of these seven False writes produces exactly the archived route export; a truly empty answer dictionary returns the original bytes. Removing only those seven inserted zero nodes makes the complete canonical XML identical. Only `word/document.xml` differs raw. The cause is `documents/word_v3.py:set_ff_checkbox`, which inserts an explicit checked state even when effective state is already false. No service/layout source was changed; Word owns the separate repair. Original DOCX and export remain retained.

The first D09 render checker failed because the owned literal helper copy omitted its expected sibling retained dependency directory. Both original and export PDFs had already rendered. The separate prospectively sealed replay invokes the identical helper/scorer against **the same archived PDFs**, using existing PDFium 4.30.0 bytes; it creates no new render or database. Both checker children exit 0: ordinary original/export pages 3/3; long 3/7. Zero fixed overlap or missing-answer problems, and all sixteen supplemental full-answer probes are visible in both profiles. Eighty-three input/scorer/dependency files remain hash-identical. D09 now has complete affected mapping/mechanical/render continuation evidence; the original gate exit 1 and missing-dependency failures are preserved.

The earlier v1 adapter attempt also remains retained: Django rejected a Class object as a test label before any document method or database creation. The distinct v2 replay uses the existing registered-module/string-label adapter without changing document criteria.

Protected packet: `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/dev-d08d09-1459595e-20261004/replay-v2`. The receipt binds original failures, exports, checker replay, source equality and teardown. These affected outcomes do not meet or replace the fixed 54/60 and 18/20 release gates. Manual mapping corrections are zero; fixed manual writer profiles are not useful generation or native Microsoft Word acceptance.
