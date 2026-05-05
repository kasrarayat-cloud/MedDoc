# Round 3 — Pre-pilot deep audit · Executive summary

**Date:** 2026-05-04 (commenced) → 2026-05-05 (synthesis)
**Branch:** `chore/round-3-deep-audit-2026-05-04` (off main, off latest tag `phase-6.2-pre-activation-fixes`)
**Scope:** apps/transcribe-md, apps/marketing, packages/*, infra/, scripts/, .github/workflows/, root configs, docs/.
**Out of scope:** apps/meddoc-pro (DECOMMISSIONED) — surfaced only where shared infra leaks across the boundary.
**Method:** 12 parallel sub-agent audits, one per domain. No sampling.

---

## Headline numbers

| Severity | Count | Definition |
|---|---|---|
| **P0** | **21** | Security breach / data loss / compliance violation. **Blocks pilot.** |
| **P1** | **47** | Significant risk / major bug. **Blocks public launch.** |
| **P2** | **44** | Notable, not blocking. Fix soon. |
| **P3** | **26** | Polish. Backlog. |
| **Total** | **138** | 12 domains, no domain skipped. |

Per-agent breakdown:

| Agent | Domain | P0 | P1 | P2 | P3 | Total |
|---|---|---|---|---|---|---|
| 01 | Credential & secret hygiene | **3** | 3 | 3 | 1 | 10 |
| 02 | Auth & session security | **2** | 4 | 3 | 2 | 11 |
| 03 | Authorization & tenant isolation | 0 | 0 | 2 | 2 | 4 |
| 04 | Input validation & injection | 0 | 2 | 3 | 1 | 6 |
| 05 | PHI & HIPAA technical safeguards | **4** | 5 | 2 | 1 | 12 |
| 06 | AI safety & clinical correctness | **4** | 6 | 3 | 2 | 15 |
| 07 | Infrastructure & operational security | **3** | 7 | 5 | 3 | 18 |
| 08 | Dependency & supply chain | 0 | 2 | 4 | 3 | 9 |
| 09 | Data integrity & races | **3** | 4 | 4 | 2 | 13 |
| 10 | UX, A11y, mobile | 0 | 4 | 6 | 5 | 15 |
| 11 | Error handling & observability | 0 | 6 | 5 | 3 | 14 |
| 12 | Docs & runbook completeness | **2** | 4 | 4 | 1 | 11 |
| **Σ** | | **21** | **47** | **44** | **26** | **138** |

---

## Top 5 highest-risk findings (pilot-blockers)

1. **A05-P0-004 — PHI-READ endpoints emit zero audit rows.** Every `GET /api/visits/[id]`, `GET /api/patients/[id]`, every PHI list, every SSR PHI page reads PHI without writing AuditLog. HIPAA §164.312(b) minimum-control failure. The schema *mandates* this in a leading comment; the code violates it.
2. **A09-P0-002 — `audit_logs` is application-mutable.** No `REVOKE … ON audit_logs FROM meddoc` anywhere in `packages/db/`, `infra/`, or `scripts/`. The same Postgres role that reads PHI can DELETE/UPDATE the HIPAA tamper-evidence layer. §164.312(c) integrity safeguard absent.
3. **A06-P0-002 — No ICD-10/CPT allowlist.** Both schemas validate regex shape only. `Z99.999` and `99999` pass. Hallucinated codes flow through to claims = False Claims Act exposure for the practice. Same primitive defect for E&M codes and modifiers. Fix template exists in-repo (`em-coding/llm-mdm.ts` LLM+deterministic-floor pattern).
4. **A07-P0-001 + A07-P0-002 + A07-P0-003 — Host hardening absent.** `PermitRootLogin yes`, no `AllowUsers`, no fail2ban, UFW disabled, public 9010/9020/8000/18789-90 listeners, AND a `/root/ai-deal-hunter/uvicorn` running as root on the same VPS as PHI. One credential compromise on any of those surfaces = total host loss + PHI breach.
5. **A01-P0-001 + A01-P0-002 + A01-P0-003 + A02-P0-002 — Secrets are exposed at rest.** Live ANTHROPIC + OPENAI + DEEPGRAM + RESEND + AUTH_SECRET + DB_PASSWORD baked into shipped Docker images via `COPY . .` + `.dockerignore` whitelist gap. The OpenAI key documented in `LAUNCH_CHECKLIST.md §6` as "leaked, must rotate" is still live in 5 on-disk files + 2 images. `.env` files mode 0777/0755 readable by every UNIX account on the VPS. AUTH_SECRET exposure permits forging JWE session cookies for any user including SUPER_ADMIN.

---

## Cross-domain themes

### Theme A — Defense-in-depth at rest is patchy
Crosses Agents 01, 02, 05, 07. LUKS protects Postgres only; MinIO bucket has no SSE, daily Postgres `*.sql.gz` backups sit plaintext on the unencrypted root disk, swap is not LUKS-on-swap, `.env` files have liberal modes, Docker images ship `.env` inside layers, AUTH_SECRET sits world-readable. Six findings tighten this; the pattern repeats because there is no single "encryption-at-rest checklist" doc.

### Theme B — AI pipeline has zero deterministic backstops on clinical safety
Crosses Agents 04, 06. Twenty-seven distinct patient-harm-exposing properties are enforced by Claude prompt obedience alone — empty-audio→empty-SOAP, ICD-10 plausibility, drug-drug interactions, peds mg/kg dosing, allergy matching, suicidal-ideation screening, source-of-claim preservation. The em-coding LLM-judge + deterministic-fallback + Redis-cache pattern (`packages/ai/.../llm-mdm.ts`) is the in-repo blueprint for retrofitting these. Until it is, "no fabrication" is one model-drift away from a clinical incident.

### Theme C — HIPAA technical-safeguard pattern enforcement is inconsistent
Crosses Agents 05, 09, 12. Writes-side audit logging is comprehensive; reads-side has zero coverage. Audit table integrity is not enforced at the DB role layer. BAAs claim signed publicly but checklist says zero signed. No incident-response runbook for the §164.408 60-day notification clock the marketing site commits to. Pattern: when a control was added (writes audit), it was added thoroughly; when one is missing (reads audit, role REVOKE, IR runbook), it is missing entirely. No "HIPAA-control matrix" doc tracks coverage.

### Theme D — Operational hardening lags compose hygiene
Crosses Agents 07, 08, 11. Compose-level (cap_drop, non-root, ulimits) and image-level (multi-stage, non-root USER) hygiene is excellent. Host-level (sshd_config, UFW, fail2ban, swap encryption, base-image SHA pinning, Sentry source maps, Redis AOF, worker healthcheck) lags. Same engineer wrote both layers — the difference appears to be that compose was refactored deliberately while the host was set up once and not revisited.

### Theme E — Round-2 fix verification was procedural, not behavioural
Crosses Agents 04, 10. Round-2 P2-001 (Zod bounds) flagged; Agent 04 finds password fields still without `.max()`. Round-2 axe-color-contrast "cleared"; Agent 10 finds the rule was globally suppressed in `a11y.spec.ts:113-119` rather than fixed (~480 call sites still fail). Pattern: prior-audit acceptance was test-passes-based, not source-fix-based. Recommend Round-3 fixes get a paired follow-up that specifically inverts each suppression and confirms the code change.

### Theme F — Documentation says "we did X" while code/infra says "we partially did X"
Crosses Agents 05, 06, 12. Public HIPAA page asserts BAAs signed (none signed). Marketing claims peds dosing supported (no pharmacology backstop, no weight capture). Marketing claims Whisper fallback (single-provider Deepgram + retry-against-itself). Marketing claims 8th-grade summaries (FK measured but not enforced). Each is a small fact-check gap that compounds into a misrepresentation pattern. Recommend a one-pass "every public claim → code reference" cross-check before pilot launch.

---

## Recommended fix sequence (follow-up PRs)

This audit ships **no fixes** — it is audit-only. Below is the recommended PR sequence for triage. Order is "value × independence" — each PR is independently mergeable; later PRs do not strictly depend on earlier ones, but the listed order minimises rework.

| # | Title | Domain | Severity | Estimated effort |
|---|---|---|---|---|
| **PR-A** | secrets: rotate OpenAI key + tighten `.dockerignore` + chmod 600 .env files + rebuild images | A01, A02 (P0s) | P0 | 2-4h |
| **PR-B** | infra: SSH `PermitRootLogin no` + `AllowUsers` + UFW enable + fail2ban + evict ai-deal-hunter | A07 (3 P0s) | P0 | 4-8h |
| **PR-C** | hipaa-tech: PHI-read audit emits + audit_logs REVOKE migration + MinIO SSE + backup encryption fingerprint check | A05 (P0-001..004), A09 (P0-002) | P0 | 1-2 days |
| **PR-D** | ai-safety: empty-transcript guard + ICD-10/CPT allowlist + pharmacology backstop + weight capture | A06 (P0-001..004) | P0 | 2-4 days |
| **PR-E** | data-integrity: Rx warning dedupe (`@@unique([visitId, warningId])`) + SOAP optimistic concurrency | A09 (P0-001, P0-003) | P0 | 1 day |
| **PR-F** | auth: disable `EMAIL_AUTO_CONFIRM_DOMAINS` in prod env + signup anti-enumeration + NextAuth GA pin | A02 (P0-001, P1-001, P1-004) | P0 | 4-8h |
| **PR-G** | docs/compliance: retract or back the BAA-signed claim + author IR runbook + author DR runbook | A12 (P0-001, P0-002, P1-001) | P0 | 2-4 days (incl. legal review of public copy) |
| **PR-H** | observability: Sentry source-maps build + Redis AOF + worker healthcheck + marketing Sentry/health/error.tsx | A11 (P1-001..006) | P1 | 1 day |
| **PR-I** | a11y: lift `--color-linear-text-3` token + add `id="main"` skip-link target + remove `tabIndex={-1}` from transcript audio | A10 (P1-001..004) | P1 | 4-8h |
| **PR-J** | input-validation: prompt-injection delimiters in worker layers + audio magic-byte sniff | A04 (P1-001, P1-002) | P1 | 4-8h |
| **PR-K** | supply-chain: NextAuth exact pin + Docker base-image SHA pinning + Dependabot YAML + audit-ci allowlist | A08 (P1-001, P1-002, P2-001) | P1 | 2-4h |
| **PR-L** | clinical-resilience: Whisper fallback + BullMQ DLQ + bull-board admin route | A11 (P1-004, P1-006), A06 (P1-007) | P1 | 1 day |

**P0 subset (must close before pilot):** PR-A through PR-G. Estimated 7-12 dev-days for a single experienced engineer.
**P1 subset (must close before public launch):** PR-H through PR-L. Estimated 4-7 additional dev-days.

P2/P3 findings are itemised in the per-agent SUMMARY.md files and should land in subsequent batched-cleanup PRs (analogous to PRs #97 and #98 from Round 2).

---

## Resource state during audit

- **Phase 0 verdict:** 🟢 GO — full parallel mode (12 simultaneous sub-agents).
- **Pre-flight:** 11 GiB total / 9.8 GiB available / load 0.60 / 8 cores / 9 of 9 containers healthy / no OOM in 24 h / Caddy smoke 200/307 expected.
- **Auto-fix applied:** `docker image prune -af --filter until=168h` freed 339.7 MB.
- **Memory note (resolved-and-stale):** stored memory recorded a hypervisor-side regression to 5.6 GB on 2026-05-04. At preflight time, post-reboot allocation had recovered to 11 GB total. **During the audit, total RAM regressed again from 11 GB → 5.5 GB** (the same balloon-re-inflation pattern, even though `lsmod` confirmed the driver is unloaded — likely a host-side reallocation, not a guest-driver event). Available RAM stayed > 3 GB throughout; no OOM, no audit-quality impact. Memory file should be updated post-merge.
- **Disk:** 25% used / 213 GiB free, no pressure.
- **Parallelism:** all 12 agents ran simultaneously to completion. Total wall-clock ~16 minutes; single-agent durations 7-15 min each. No agent failed or partial-completed.

---

## Findings index

Each finding is a separate file under `docs/round-3-deep-audit-2026-05-04/findings/agent-NN/{P0..P3}-NNN-<slug>.md`.

A flat severity-sorted index lives at `docs/round-3-deep-audit-2026-05-04/INDEX.md` (next to this file).

Each agent's per-domain SUMMARY.md sits at `docs/round-3-deep-audit-2026-05-04/findings/agent-NN/SUMMARY.md`.

---

## Process notes

- **No sampling.** Every relevant file in each domain was read. 63/63 API routes, 262/262 Zod usages, all 4 Sentry configs, the full git history (654 commits / 41 branches / 19 tags), all 4 Dockerfiles, both compose files, every infra script, every cron, all 1,157 deps, all PHI emit/read points, all 27 model-trust touchpoints, ~140 docs.
- **No fixes.** This PR is audit-only. Fixes ship in the follow-up PRs above.
- **No production-code modifications.** Only writes are under `docs/round-3-deep-audit-2026-05-04/` and an entry in `docs/POST_MERGE_TODO.md §24`.
- **Verification of prior fixes.** Round-1 PDF/DOCX metadata fix (P1-001) confirmed held in both formats. Round-2 axe-color-contrast "clearance" debunked (rule globally suppressed, not fixed). Round-2 Zod-bounds (P2-001) partially held; password fields still unbounded.
