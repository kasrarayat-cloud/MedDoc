# CI continuation — 2026-09-27

Draft PR #1288, source b806ed85b4895304e6ef0c0b5aab8a8affbf9288. GitHub run36351792380 / application job108711760640 exceeded its hard20-minute limit. The exact check annotation confirms timeout; no intervening push, ready event or merge was made by this session.

Before cancellation: **2,043 core tests PASS in1029.308s;204 document tests PASS in68.642s**. The operations completion fixture failed before cancellation. Browser/accessibility, marketing and separate secrets check passed. Actual Word adapter qualification and dependency audit were later steps and are not credited from this cancelled job.

## Demonstrated fixture failure and repair

The completion fixture patches automatic_offsite.now to Sep20, but Budget's default clock was bound to the original function at import. On Sep27 after18:30, the budget correctly refuses the seven-day fixture policy as expired. Root reproduced reason_code=policy_expired locally; production expiry handling is correct.

52f48d72 supplies an explicit clock to a real Budget object in that test and adds a converse execute test proving an expired budget refuses before transport even with a valid outer clock.35 affected tests PASS;4 CI orchestration controls PASS.

The first full operations pass (1155tests/82.390s) retained **2 failures,1 error,2 skips**: three shared-accounting execute tests had the same unbound clock. fc7361cb injects their real Budget fixture clocks as well; assertions and production files are unchanged. **57 focused offsite/shared-accounting/CI tests PASS in1.184s.** Full final CI remains required; a targeted repair is not a retroactive full-suite pass.

## Bounded CI partition

52f48d72 retains every original Python command but runs core and support in independent20-minute jobs with fail-fast disabled. Support contains documents, operations, reviewer SSH access, actual Word adapter qualification and dependency audit. Both partitions build the pinned helper and use isolated synthetic PostgreSQL. The required `Fresh application tests` check is an always-running aggregate that accepts only matrix success: failure, cancellation, skip or empty result fails. Legacy `python` and `all` script modes remain available. No limit was raised and no check skipped to conceal the timeout.

Four offline orchestration controls prove exact command union, stop-on-each-failure, unknown-mode refusal and aggregate acceptance for success/failure/cancelled/skipped/empty. They stub command execution; the next CI run must supply actual execution evidence.

All initial failures and full output are retained by hash in manifest.json. No provider call, production backup, policy renewal, reservation or deployment occurred.


## Exact33759 completed result and schema-test repair

Run36354278599 finished **failure**. Core ran2,047 tests in1035.245s with exactly one failing subtest: the old SDK-schema constraint test expected301-character labels to reject, while the reviewed contract permits1,000 Unicode code points. The required aggregate correctly failed. Support passed20 reviewer-SSH controls,211 document tests,1,155 operations tests and90 named adapter/kernel checks; dependency audit found no known vulnerabilities. Four operations skips remain explicit: two host-worker identity checks cannot run without installed workers; two historical candidate-scope checks refer to an already-merged candidate. Browser15/WM9/input8, marketing andsecrets passed. Complete logs and all first results are retained.

Root reproduced the same schema failure locally (3tests/1failure). Test-only91db0eb7 changes the rejected label to1,001 and adds astral1,001 rejection; it also asserts complete301/1,000 ASCII/astral labels survive unchanged. Empty label and invalid glyph constraints remain. All4 affected tests pass0.062s, including the actual SDK body through MockTransport with network denied. No application code, schema bound, request, reservation or provider call changed. Independent review and next exact-head CI remain pending at this entry;33759 is not relabelled green.
