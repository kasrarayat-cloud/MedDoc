# Supported renderer binding for the prepared DEV33 application run

The first five packets on `481b65adb8ffa97053b694f0de3ba4dbaac72d0a`
remain immutable in
`operations/dev33-final-481b65ad-20261004T113626Z`. Every packet's actual
outer/driver exit was 1; all independent source, database, recorded PID,
socket and container teardown checks passed. No provider request occurred.

| Packet | Originals | Application exit | Original retained outcome |
|---|---|---:|---|
| P01 | D01, D02 | 1 | D01 native reader aborted after export at an original-row index after the output table split; D02 strict 19/24, with fixed and manual profiles separate. |
| P02 | D03, D04, D05 | 0 | Strict maps 49/88, 16/27 and 6/6 with two extras respectively; fixed review/readback failures retained. |
| P03 | D07, D08, D09 | 0 | Strict maps 23/28, 39/41 and 47/47; only D09 completed all fixed profiles successfully. |
| P04 | D10 | 0 | 78/198 destinations correct, 120 missed and four extras; source-bound coverage review returned 400. |
| P05 | D11 | 0 | 548/559 destinations correct, 11 missed and two extras; ordinary/long answer review refused. |

These ten original results are a partial run. They are not the final 33-original
run, the 54/60 gate or an unseen holdout. No favorable retry replaces them.
P06–P17 were not launched after the configuration cause was established.
The raw original configuration proof is
`layout-uid-original-environment-cause.json`, SHA256
`ee0aac0a7e4853cbcc7526cdad1cf2551c93073a7a9bf10af4e3f1b21c50a90a`.

The prepared harness supplied `QUILLMD_LAYOUT_SOCKET` but omitted
`QUILLMD_LAYOUT_SERVICE_UID`. The normal protected QA wrapper scrubs its
environment and supplies neither UID nor socket; the source defaults UID to
empty. `documents/layout_transport.py` refuses before connecting when UID is
empty. Running a renderer alone therefore did not make the renderer available
to this harness. D10's 52 retained coverage issues included 45 tab-column
withdrawals, and its source-bound review was refused. Product/safety guards
remain intact.

The minimal correction uses the existing started server. The driver records
its actual PID, `/proc` start ticks and owner UID; a bounded local Unix-socket
probe authenticates the OS peer PID and UID against that record and the socket
owner. It sends no document. The server's existing incomplete-frame refusal
handles probe EOF without rendering. A changed process identity, owner, peer
PID or socket refuses. The driver then writes the immutable plan once, before
launching the normal protected QA application wrapper. The inner harness
uses that plan's UID and socket, verifies the recorded process again and
retains the actually applied settings in each original's
`layout-inner-settings.json`. Empty or foreign settings remain refused.

The version is `dev33-supported-layout-peer-v2`.
`word-dev33-supported-layout-plan-prepared-20261004.json` has SHA256
`e109770ddec753bf537c046a2473dbb3270c200b70983ecffde5c9c9cacba49a`.
It retains every value from the original preparation, whose SHA remains
`e1ca082b8c7ddff09a054cf9f581ef6bbbbb4c35b693380b1bc698ef90822d39`,
and adds only an original-plan reference, version, supported driver-copy
identities and peer-helper hash. The new peer helper SHA is
`05c157aacd0c717ca9835bc8b8482f8c100101e7be3f6a3aa46d49cd145e8a23`.
The mixed ledger and supervisor require this version/helper, exact new driver
bytes/locations and a fresh prospective source/resource seal. Old literals
remain recoverable in S2 and in its byte-exact copied supervisor; old driver
copies, checker, scorer, profile, ground truth and all failure evidence remain
unchanged.

Prepared corrected copies are under
`operations/dev33-supported-layout-prepared-20261004-v2`; its exact four-file
driver/harness diff SHA is
`2c31b53f4558a6009d146f968a607e62984011d0dfb20ff7691c3365a1af7087`.
The first unexecuted preparation is retained separately. The checker is
byte-identical. AST controls preserve every top-level scorer/profile/readback
function in both inner harnesses; the change binds the supported environment
and records it. It does not normalize any score or alter a clinical answer.

Eighty-nine affected pure methods passed, actual exit 0 in 0.918388 seconds,
with unchanged source bytes and zero actual QA/socket/renderer/provider
operations. Protected evidence:
`operations/dev33-layout-peer-finished-20261004/{tests.log,result.json}`;
raw log SHA256
`1098d11b57dca6139053276575874a4bb725896d12a5ccabf99ce37c359aa31e`.
This is prepared harness evidence, not a successful corpus/application run.
Execution waits for independent verification, a new coherent source S and its
exact prospective seal and resource handoff. All 17 packets must then run
serially on that same source. Seven held DEV originals remain within the 60
overall denominator and the 20 historical holdout members remain unevaluated.
