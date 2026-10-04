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
This is an affected regression result, awaiting independent finished-diff
refutation and actual whole-document replay. It is not a Word acceptance gate.

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
