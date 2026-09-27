# V1 release acceptance matrix (synthetic inputs only)

One finite matrix, run against the merged V1 candidate branch. Each row names what proves it. No paid campaign
beyond the existing eligible authorization; rows that need provider spend or an owner session are marked and
stay unrun until authorized. Results are filled in only from executed commands, never from expectations.

Legend: PASS · FAIL · NOT RUN (with reason) · BLOCKED (external).

| # | area | check | proof | result |
|---|---|---|---|---|
| 1 | build | `manage.py check`, `makemigrations --check` | CI script (python gate) | pending merge |
| 2 | build | full core suite | `manage.py test core.tests` | pending merge |
| 3 | build | document suites incl. `test_word_v3` | explicit unittest list | pending merge |
| 4 | build | ops discovery suite | `unittest discover -s ops` | pending merge |
| 5 | access | invite-only: `/register/` 404 in invite mode; clinic invitation accept | blockers-stream tests | pending merge |
| 6 | access | MFA required for every account in real mode; staff Reset MFA | blockers-stream tests | pending merge |
| 7 | access | real mode refuses to start with sandbox Stripe; live mode refuses the preview gate | R1/R2 repair tests | pending |
| 8 | access | per-client rate limits behind the trusted proxy | blockers-stream tests | pending merge |
| 9 | isolation | department scoping on routes, files, exports | existing isolation tests | pending merge |
| 10 | notes | typed notes, revision checks | existing tests | pending merge |
| 11 | voice | synthetic audio → transcript review → notes (fixture provider) | existing tests / input-workflow browser test | pending merge |
| 12 | generation | refusal / max_tokens / incomplete output never adopted; charge reversed | Sonnet 5 stream tests | pending merge |
| 13 | generation | no generation over reviewed answers (server-side) | review-guards tests | pending |
| 14 | generation | ordinary unlabelled notes on a custom form produce answers, not blanket conflicts | — | **BLOCKED (B-G1 not built)** |
| 15 | Word | holdout automatic success ≥ 18/20 | `word-holdout-first-pass-1.md` | **FAIL (0/20)** |
| 16 | Word | every export mechanically faithful (untouched parts byte-identical, text kept, answers visible, no new overprinting) on the 40 dev + 20 holdout forms | frozen harness | 31/40 dev · 18/20 holdout (fill/render problems listed per document) |
| 17 | Word | mapping review: add / remove / kind / label corrections recorded as manual; confirmation gate | Word-integration tests | pending |
| 18 | Word | choice/checkbox answers filled only from explicit options; everything else held | Word-integration tests | pending |
| 19 | Word | signature/initials never filled | `test_word_v3` | PASS (engine) |
| 20 | Word | a content control wrapping other controls is never overwritten (H08 class) | `test_word_v3` (mutation-proved) | PASS (engine) |
| 21 | review | WM statement decisions survive an employee save; finalized record not re-reviewed; `&` blocker | review-guards tests | pending |
| 22 | finalize/export | hash-checked export in the original format | existing tests | pending merge |
| 23 | money | hold before request, charge ≤ hold, 1.5× preserved, audit_billing passes | existing + Sonnet 5 settlement tests | pending merge |
| 24 | money | live Stripe payment credited once (≤ $5) | owner-run | BLOCKED (B-S2) |
| 25 | model | Sonnet 5 served and echoed, stop/end_turn, tokens within bound, latency | bounded live check | BLOCKED (spend approval) |
| 26 | admin | console on the TLS proxy (admin host), MFA-gated | blockers-stream test | pending merge |
| 27 | ops | alert escalation within an open incident re-notifies; persistent incident reminds | alert-escalation tests | pending |
| 28 | ops | production launcher proves the metadata service is denied | UDP probe test + BPF container probe | PASS (branch) |
| 29 | ops | backups with verified restore on the production host | — | BLOCKED (B-H1) |
| 30 | public | public app/admin stay in maintenance; synthetic-only enforced on the current VPS | `check-cotenants.sh` (app 503, admin 503) | PASS (2026-09-27 05:50Z) |
