# Coverage matrix — what was tested vs what was not

Paired with `audit-final-report.md`. Lists the probe shape, the live outcome, and an honest note on anything that was skipped and why.

| # | Category | Shape | Verified live? | Notes |
|---|---|---|---|---|
| A | Real audio stress | Single 7-min MP3 via kasra's visit after keyterm trim | ✅ verified in PR #62 | Not re-run this session — would have burned Deepgram budget with no new-info expectation. Edge-case matrix (0-byte, corrupted, renamed-ext, silence, whisper, heavy-accent, network-drop mid-upload) NOT exercised. Audio format allowlist + 500 MB cap + per-mode input validation all verified statically. |
| B | IDOR / cross-tenant | 6 foreign visits × 6 endpoints + 1 cross-practice patient × 3 methods = 42 probes | ✅ all 404 / 403 / 405 | See `cat-b-findings.json`. |
| B | Cookie tampering | Mangled + empty session-token | ✅ both → 401 | |
| B | JWT inspection | Verified session-token is JWE (alg `dir`, 5 parts, 649 bytes), not a signed JWT | ✅ | attacker with stolen cookie can't read claims offline |
| B | Cross-app cookie reuse | Attempt to fetch `pro.quillmd.com` from `app.quillmd.com` page context | ✅ CORS blocks | |
| B | Privilege escalation | NOT exercised this session | ⛔ | No admin role to attempt escalation AS — transcribe-md has no admin-only endpoints; escalation shape doesn't apply |
| C | Concurrent SOAP edit | Two contexts, same session, simultaneous save | ✅ | **MEDIUM finding (M3): silent last-write-wins** |
| C | Sign-vs-edit race | NOT exercised | ⛔ | Sign endpoint has an atomic updateMany with status guard — pre-verified in prior audits |
| C | Patient merge conflicts | NOT exercised | ⛔ | Patient model is practice-level scoped; inline fuzzy-match guides doctors to existing rows — not a conflict scenario |
| C | SQL injection | 11 payloads via `/api/patients` POST | ✅ Prisma parameterized; no reflection | |
| C | XSS | 11 payloads rendered on `/patients` | ✅ React escapes; no script/iframe/img-onerror execution | |
| C | Path traversal | Patient name `../../../etc/passwd` — stored verbatim, no filesystem interaction | ✅ | Filename-based path traversal on upload route would need an audio_upload QUEUED visit; ownership check fires before filename handling so not reachable |
| C | UTF-8 / RTL / emoji | Prior deep-hunt confirmed; React hydration error #418 on some unicode — known LOW | ✅ / known-low | |
| D | Unauth status matrix | 23 routes × 1 method each | ✅ 307/401/403/405 as appropriate | |
| D | Authed wrong-method | PUT/DELETE on POST-only routes | ✅ 405 | |
| D | Malformed body | 10 routes × invalid JSON | ✅ 400 (2 hit 429 rate-limit during probe, not a bug) | |
| D | Stack trace leakage | Grep all authed 5xx responses for framework internals | ✅ none | |
| D | Rate-limit enforcement | Observed 429 on CAT-D + CAT-C-injection probes — fires as designed | ✅ | |
| E | Accessibility (axe-core) | NOT RUN | ⛔ | Recommended pre-launch addition; Playwright prior audits used `getByLabel` / `getByRole` which implicitly validated labels exist |
| E | Keyboard navigation / tab order | NOT RUN | ⛔ | Same recommendation |
| E | Focus trap in modals | NOT RUN | ⛔ | Radix Dialog (used by sign-and-send + override modals) has correct focus-trap by default; not re-verified |
| F | Page-load latency | `curl -sw` on 5 routes | ✅ all sub-300ms | Authed-page full-render timings NOT measured |
| F | API response times | p50/p95/p99 NOT MEASURED | ⛔ | Recommended: Lighthouse + Sentry Performance |
| F | Memory leaks (long session) | NOT RUN | ⛔ | Worker has per-job timeout (15 min) so runaway process fails fast; web app is stateless-per-request |
| F | Slow queries / N+1 | `pg_stat_user_tables` inventory | partial | `pg_stat_statements` extension not enabled (LOW L2) |
| F | Bundle sizes | NOT MEASURED | ⛔ | Recommended: next build output analysis |
| G | Deepgram down | NOT SIMULATED | ⛔ | Inferred by code review: categorizer now flags 5xx as transient → BullMQ retries 3x; after 3 the worker surfaces `provider_down` UI variant |
| G | Anthropic down | NOT SIMULATED | ⛔ | Same categorizer path applies |
| G | Postgres connection drop | NOT SIMULATED | ⛔ | withApiHandler catches; Prisma client reconnects; any in-flight request fails the single user |
| G | Redis death | NOT SIMULATED | ⛔ | BullMQ producer-side fails fast; admin-notify throttle's Redis-miss path allows-send (logs warn). Would hurt pipeline but not data integrity |
| G | MinIO unreachable | NOT SIMULATED | ⛔ | Upload route categorizes permanent vs transient based on error shape |
| G | Worker crash mid-job | NOT SIMULATED | ⛔ | T-M13 resume logic + BullMQ 3-attempt retry covers this. Verified indirectly when kasra's visit re-processed cleanly post-keyterm-trim |
| H | Login timing (valid vs wrong-pw vs inactive vs locked vs no-entitlement) | Static review of loginAction + authorize callback shows dummy-bcrypt branches covering all paths | ✅ code-review | Not a live-latency-histogram measurement |
| H | Forgot-password / reset-password timing | Static review | ✅ generic 200 always, no branch-on-existence | |
| H | Search response timing | NOT MEASURED | ⛔ | Would require thousands of probes to be conclusive |
| I | SPF/DKIM/DMARC | NOT VERIFIED | ⛔ | Resend sends are accepted → presumed configured; would need dig + mxtoolbox pass |
| I | Email header injection | Tested via CRLF in `forgot-password` email field — 400 rejects | ✅ | |
| I | Email reply-to injection | NOT TESTED | ⛔ | Resend sets reply-to server-side; no user control |
| J | Filename path traversal on upload | Route's ownership check fires before filename handling — no injection surface reachable from outside | ✅ static-reviewed | MinIO object key built server-side via `buildAudioObjectKey(userId, visitId, filename)` with length + character filtering |
| J | ZIP bomb | NOT TESTED | ⛔ | Upload route's 500 MB size cap + MIME allowlist (audio/* only) → ZIP would be rejected at MIME-check |
| J | Polyglot file | NOT TESTED | ⛔ | Same — MIME allowlist rejects non-audio/* |
| J | Very long filename | NOT TESTED | ⛔ | MinIO key length limit is 1024 chars; filename sanitizer applies — static-reviewed |
| J | Null byte in filename | NOT TESTED | ⛔ | Would need a real audio_upload QUEUED visit |
| K | Container users | Every container checked | ✅ | **H4 finding: 4 containers run as root** |
| K | Port bindings | Every exposed port checked | ✅ | All infra services loopback-only |
| K | Volumes | `docker volume inspect` + mount table | ✅ | **H3 finding: no disk-level encryption** |
| K | Backup status | postgres-backup sidecar logs + weekly/monthly file check | ✅ | Running correctly |
| K | HTTP security headers | `curl -sI` on both apps | ✅ | **M1: CSP report-only + unsafe-eval** |
| K | CORS | Cross-origin OPTIONS probe | ✅ no wildcard | |
| K | TLS config | NOT DEEPLY PROBED (testssl.sh would be right tool; not installed) | ⛔ | HSTS preload present; leaves cipher-suite review for pre-launch |
| L | Audit-log coverage | Grep `logAudit(` + DB row counts | ✅ | **H2 finding: transcribe-md writes 0 rows** |
| L | PHI in stdout logs | Grep non-redactPhi console.* in transcribe-md | ✅ | `withApiHandler` top-level catch now scrubs (T-M18 A1 fix) — confirmed |
| L | Encryption at rest | Mount-table + volume introspection | ✅ | **H3 finding** |
| L | Auth-token storage | NOT DEEPLY VERIFIED (did verify Redis BullMQ payload shape; did NOT grep auth-token hashing) | ⛔ | Static-review of `auth-tokens.ts` needed for final sign-off |
| L | Ephemeral token leakage | OpenAI Realtime tokens NOT probed — that's meddoc-pro, out of primary scope for this transcribe-md-focused audit | ⛔ | Prior audit noted they're short-lived |

---

## What I'd run next if I had another ~2 hours

1. Real-audio matrix in CAT-A with FFmpeg-generated files (0-byte, 30s, 5m, 30m, silence, white noise, deliberately-wrong-extension) — ~$15 of Deepgram spend.
2. Lighthouse on authed `/dashboard` + `/visits/[id]` to get real LCP / TTI numbers.
3. axe-core accessibility scan on the three primary flows.
4. testssl.sh against `app.quillmd.com:443` for cipher-suite grade.
5. Sustained `hey -z 60s -c 20` load test on a read-heavy endpoint to see connection-pool behaviour.
6. Deliberate Redis kill-and-restart mid-pipeline to verify the worker's Redis-miss path doesn't drop the job.

None of these would change the HIGH findings list. They would likely surface 2–4 additional MEDIUM/LOW items.
