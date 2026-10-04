# Long paired answers preserve printed separator tabs

The retained D02 native-long export changed five ordinary separator tabs into
line breaks. Those runs belong to the original printed form, outside the answer
destinations. The writer now places the needed line break within an answered
run, preserving each separator and a missing neighboring answer. A long second
answer with an empty first answer starts within its own run.

Three affected methods pass with actual exit 0, no timeout, provider call or
expected database use. The source diff remained unchanged during the run.
Receipt: `root-tab-separator-repair-20261004T060804Z/result.json`; test log SHA256:
`92e4222bdb5974927e045921627210d45c8d3e4f1b7db6c934a8ecf699a26dde`.
Independent finished-diff refutation also passes32 public inspect→fill cases: every subset of2/3/4 paired fields, mixed empty/short/long values, newline/tab/CRLF, neighboring checkbox/internal link and all untargeted parts. Forged/reordered original mappings refuse. Actual exit0; no DB, renderer, provider or socket call. Result SHA256: `3b2388e0f5efbf422e613881695c01e9fedb9589d104776f07534b8a0ac29810`. Actual whole-document replay remains required. This is not a Word acceptance gate.

Separately, the original two-answer PDF omission claim is refuted at the text
probe layer. The original blank document was rendered to `document.pdf`; the
export was rendered to `instrumented.pdf`, SHA256
`27b2816f22ee26a5f9c55f4aba877802fd61c6cb7928a3247d79826dcbe6f83b`.
Both complete 409-character answers span pages. The retained original footer
interrupts contiguous extracted text. Excluding only that original footer
recovers all 24 complete planned answers without adding answer text.
Adjudication SHA256:
`bf2508af309acf0d03de1bddf59fae31c8d7298513b58c4f9d8b844bb780da52`.
Original checker failures and denominators remain unchanged. Visual clipping,
full document fidelity and native Microsoft Word inspection remain unverified.

The same known archive-comment loss was then reproduced in the legacy WM
output pagination postprocessor: its changed export retained all non-document
entries but lost the original package comment. The separate two-line repair
copies that original comment into the changed export. Two affected methods
pass, with empty, text and binary comments plus byte-identical second-pass
output; actual exit0 in0.330 seconds and unchanged source. Original wrong
output remains retained at `root-layout-archive-comment-original/result.json`.
The correction changes no table/limb layout behavior.

- Corrected receipt: `root-layout-comment-affected-20261004T062856Z/result.json`.
- Log SHA256: `b6183a7bb1d6524a3f0e18874c4bb2419feb0f18399ae191ee5ccbd2df6a910e`.

Independent refutation confirms all five archive-comment shapes including the ZIP maximum65535bytes, identical parent table/layout XML, untouched raw parts and byte-identical second pass. Actual exit0; evidence SHA256 `329477f625b095e0f8877fdfba22828b5b5b066b337bfb2b5bacfb628db2dcc6`.
