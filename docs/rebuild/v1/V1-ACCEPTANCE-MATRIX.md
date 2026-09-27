# V1 release acceptance matrix (synthetic inputs only)

One finite matrix, run against the merged V1 candidate branch. Each row names what proves it. No paid campaign
beyond the existing eligible authorization; rows that need provider spend or an owner session are marked and
stay unrun until authorized. Results are filled in only from executed commands, never from expectations.

Legend: PASS · FAIL · NOT RUN (with reason) · BLOCKED. Branch evidence names its tested revision; it is
not an installed or combined-candidate result. Reuse unchanged checks; run changed/missing checks only.

| # | area | check | proof | result |
|---|---|---|---|---|
| 1 | build | `manage.py check`, `makemigrations --check` | CI script (python gate) | local integration complete; final candidate CI pending |
| 2 | build | full core suite | `manage.py test core.tests` | local integration complete; final candidate CI pending |
| 3 | build | document suites incl. `test_word_v3` | explicit unittest list | local integration complete; final candidate CI pending |
| 4 | build | ops discovery suite | `unittest discover -s ops` | local integration complete; final candidate CI pending |
| 5 | access | invite-only: `/register/` 404 in invite mode; clinic invitation accept and recovery links without clinical content | blockers-stream tests | branch fixture evidence; combined candidate pending |
| 6 | access | MFA required for every account in real mode; staff Reset MFA | blockers-stream tests | local integration complete; final candidate CI pending |
| 7 | access | real mode refuses to start with sandbox Stripe; live mode refuses the preview gate | R1/R2 repair tests | pending |
| 8 | access | per-client rate limits behind the trusted proxy | blockers-stream tests | local integration complete; final candidate CI pending |
| 9 | isolation | department scoping on routes, files, exports | existing isolation tests | local integration complete; final candidate CI pending |
| 10 | notes | typed notes, revision checks | existing tests | local integration complete; final candidate CI pending |
| 11 | voice | synthetic audio → transcript review → notes (fixture provider) | existing tests / input-workflow browser test | local integration complete; final candidate CI pending |
| 12 | generation | refusal / max_tokens / incomplete output never adopted; charge reversed | Sonnet 5 stream tests | local integration complete; final candidate CI pending |
| 13 | generation | no generation over reviewed answers (server-side) | review-guards tests | PASS on branch: 1,224 core/11 skips plus final79 focused; locally integrated, final combination pending |
| 14 | generation | ordinary unlabelled notes on a custom form produce answers, not blanket conflicts | — | **BUILT, BLOCKED (B-G1 usefulness/semantic qualification; necessary WM path integrated; ordinary source-context repair in progress)** |
| 15 | Word | holdout automatic success ≥ 18/20 | `word-holdout-first-pass-1.md` | **FAIL: historical engine proxy 0/20; full workflow unqualified** |
| 16 | Word | every export mechanically faithful (untouched parts byte-identical, text kept, answers visible, no new overprinting) on the 40 dev + 20 holdout forms | frozen harness | Historical proxy31/40 dev ·18/20 holdout; incomplete checkbox checks, not complete workflow/native acceptance |
| 17 | Word | mapping review: add / remove / kind / label corrections recorded as manual; confirmation gate | Word-integration tests | pending |
| 18 | Word | choice/checkbox answers filled only from explicit options; everything else held | Word-integration tests | pending |
| 19 | Word | signature/initials never filled | `test_word_v3` | PASS (engine) |
| 20 | Word | a content control wrapping other controls is never overwritten (H08 class) | `test_word_v3` (mutation-proved) | PASS (engine) |
| 21 | review | WM statement decisions survive an employee save; finalized record not re-reviewed; `&` blocker | review-guards tests | PASS on branch: 1,224 core/11 skips plus final79 focused; locally integrated, final combination pending |
| 22 | finalize/export | hash-checked export in the original format | existing tests | local integration complete; final candidate CI pending |
| 23 | money | hold before request, charge ≤ hold, 1.5× preserved, audit_billing passes | existing + Sonnet 5 settlement tests | local integration complete; final candidate CI pending |
| 24 | money | live Stripe payment credited once (≤ $5) | owner-run | BLOCKED (B-S2) |
| 25 | model | Sonnet 5 served and echoed, stop/end_turn, tokens within bound, latency | bounded live check | BLOCKED (spend approval) |
| 26 | admin | console on the TLS proxy (admin host), MFA-gated | blockers-stream test | local integration complete; final candidate CI pending |
| 27 | ops | alert escalation within an open incident re-notifies; persistent incident reminds | alert-escalation tests | PASS: ops1,018/2 known skips; sole surviving mutation closed; locally integrated; delivery separate |
| 28 | ops | production launcher proves the metadata service is denied | UDP probe test + BPF container probe | PASS (branch) |
| 29 | ops | backups with verified restore on the production host | — | BLOCKED (B-H1) |
| 30 | public | public app/admin stay in maintenance; synthetic-only enforced on the current VPS | `check-cotenants.sh` (app 503, admin 503) | PASS at recovery (2026-09-27); installed dedac162 remains synthetic-only |

## Required evidence not represented by a fixture-suite pass

| # | area | check | proof / current result |
|---|---|---|---|
| 31 | native Word | final qualified original/export pairs and actual controls | NOT RUN: no connected Word session; both remote devices offline at Sep27 continuation |
| 32 | model access / sizing | native exact model metadata and new tokenizer count | PASS for metadata and eight free counts only; output-text counts are input-token proxies; generation/served worker remains row25 |
| 33 | corpus independence | 60 independently authored authorized templates, ≥10 sources | INSUFFICIENT:60 hashes/26 sources but44 declared lineages; preserve frozen set/results, validate provenance separately |
| 34 | WM ordinary narrative | necessary draft path on selected V1 code/adapter, source/row/side/correction → review/export | Locally integrated:273 focused checks; cleared-answer repair80targeted checks; historical benchmark byte-identical; exactSonnet5 quality still pending. No labelled-only substitution |
| 35 | actual incident delivery | receipt, delivery and recipient acknowledgement; escalation/reminder/outside-host failure | BLOCKED: actual production target/access; no uncertain email or single-use test replay |
| 36 | independent security | actual target/candidate and serious-finding retest | BLOCKED: target and external review |
| 37 | custody and host recovery | independent credentials/keys, whole-host rebuild, retention/deletion procedure, sustainable backup admission | BLOCKED on target/custody/legal inputs; package prepared |
| 38 | current local restore | latest synthetic encrypted backup, isolated DB/file verification | PASS Sep27 16:44:36 tables/226,187 rows/64 files all hashes match, no provider actions, owned container removed; not production/offsite/custody proof |

No row closes the automatic Word gate by manually remapping, refusing difficult files, changing the denominator
or holding every answer. The unchanged first-pass failures remain failures. No launch date is inferred from
these branch checks. Final qualification consumes only an eligible frozen candidate and explicitly bounded
authority; no additional paid campaign is implicit.

## Continuation integration evidence (2026-09-27)

The original corpus and first-pass scores above are unchanged. Required WM185f1ae2 and mapping37491d49
were locally merged as ebcddc2a and35ce0d1c. Mapping has380affected,21finalUI and4constructor controls;
the root independently reproduced and closed the stranded pre-submit wallet hold. Five synthetic rendered
pages cover original/ordinary/missing/long answers (1/1/1/2pages), not native Word or corpus success.
After integration,37mapping/WM/settlement checks passed;49independent pure metering controls passed.
Flags remain off and nothing was installed. The final candidate suites will be cited separately after
remaining source-context and production-status changes finish. No aggregate launch percentage is inferred.
