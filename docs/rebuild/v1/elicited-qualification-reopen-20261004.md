# Diagnosis for canonical-5 elicited qualification reopening

reopen_stage: elicited_qualification
failed_attempts: 2, 3, 4
repair_commit: 54d0acdd8ef693cebcd1c94cdc97dcbee4659182

This diagnoses the first elicited-stage failure in `quillmd-v1-standing-api-testing-20261004-5`, whose unchanged declaration has SHA256 `21c3fdbc4610a700fac2505ad5668d5abcb9b59ba2f2bb809cc17058fbbabb99`. All three attempts ran on `fc44b4a27366a4ab0514234d374f9f711cb7cfa9`; attempts 2/3 passed their positive cases and attempt 4 triggered the failed-stage record. The normal reopening contract requires the complete [2,3,4] scope since `open_since=0`.

The application correctly held the E03 father-attributed statement with blank text and exported it blank. The scorer received the normal first-result `held` value but accepted only raw `conflict` or `missing`, falsely recording `unsupported_accepted`. The repair changes that one accepted status to `held`; real normalization controls prove blank holds, while nonempty holds, unsupported negative answers and absent or unknown shapes retain rejection. Full evidence and the separate independent adjudication are linked in [the repair report](elicited-normalized-hold-20261004.md).

Keep every original attempt, outcome, unsafe classification, failed-stage decision, request/response, original form and export unchanged. A new reopening record must name the actual new clean runner containing this repair. Only the never-attempted E04/E05 remain eligible; no E01/E02/E03 retry is intended or permitted by the normal fixed plan. The maximum of five elicited requests leaves exactly two requests. N01 is still a separate unattempted notes-stage send.

This committed diagnosis is a prerequisite for the existing guarded `standing_qa.py reopen --stage elicited_qualification --diagnosis ...` command. It does not itself perform a reopening or grant a provider/QA lease.
