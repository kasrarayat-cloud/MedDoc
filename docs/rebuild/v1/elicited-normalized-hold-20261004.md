# E03 normalized hold grading repair — 2026-10-04

On frozen C2 `fc44b4a27366a4ab0514234d374f9f711cb7cfa9`, canonical-5 run 0004/attempt 4 stopped elicited qualification as unsafe. All later sends stopped immediately. The completed provider request was `req_011Cfhu8NNecaB2Sytm7Dmts`, with Sonnet 5.5, 20,000 tokens, between-tools thinking, medium effort and unset request geography. Calculated provider cost was `$0.004734`; receipt and usage agreed, charge was `$0.007101`, and its reservation settled.

E03 is the declared synthetic negative: the **father**, rather than the patient, supplied the relationships statement. The provider selected that source unit, but the application correctly held it: `answers-adopted.json` contains `conflict` and empty text. The normal review records `left_blank` and empty text. Export readback proves the answer stayed blank with no changed document parts or outside-field changes.

The failure is in the stage grader. `app_path_steps.field_outcomes` converts a raw `conflict` to `held`. `generation_send` passes that normalized first result to the elicited judge. The new grader accepted only raw `conflict` or `missing`, so it called the actual blank `held` result `unsupported_accepted`. The one-token runtime repair consumes the existing normalized `held` status. It does not alter the application, provider request, original form, fixture, gold or score denominator.

Four offline controls passed in 0.363 seconds including imports (0.002 seconds in unittest), with no DB/network attempt and unchanged source. They exercise actual raw-to-normalized grading for all three negative fixtures and all eight positive answers; nonempty holds, supported negative answers, absent rows and unrecognized statuses retain rejection. A retained E03 adjudication executes the exact old C2 grader against the captured raw answer and actual normalizer: old grade `unsupported_accepted`, fixed independent grade `held_correct`. All 15 clinical AST/byte pins and four paid-input pins match C2.

The original unsafe classification and failed-stage decision stay unchanged. The independent adjudication is a separate retained record, with every original evidence hash verified. No E03 retry occurs. Before reopening, canonical-5 has four completed attempts costing `$0.027122`, no open or unknown attempt, and a failed elicited stage. E01/E02 measured eight correct supported answers; E03 is the recorded scoring failure just diagnosed.

The existing normal reopening contract requires a committed diagnosis and repair, a new clean runner containing that repair, a changed watched runner file, and unattempted remainder. It defines this failure's scope as every elicited attempt after `open_since=0`, so `failed_attempts` must be **2, 3, 4** even though only run 0004 triggered failure. `standing_qa_elicited.py` is already watched. The only remaining elicited sends are E04/E05; E01/E02/E03 cannot be planned again. N01 remains a separate unattempted stage. No reopening or further provider call is authorized by this report alone.

Protected evidence under `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/hpi-release-20261004/qualification-preparation/`:

- `canonical5-C2-send4-E03.log`, `canonical5-C2-E03-stop-status.json`: actual stopped run and accounting.
- `ops-held-grade-controls-r1.{log}` and `ops-held-grade-controls-r1-result.json`: focused controls.
- `E03-independent-adjudication-r2.{log,json}`: exact captured answer, old/new grader results and immutable evidence hashes.
- `ops-held-grade-source-proof-r1.json`: unchanged clinical inputs and one runtime status change.

Original paid records remain under `/opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261004-5/evidence/004/`, its `ledger/004-{attempt,outcome}.json`, `ledger/stage-elicited_qualification-failed-1.json` and `runs/0004-{run,closed}.json`. Readback instrumentation failures are retained separately and caused no provider retry.
