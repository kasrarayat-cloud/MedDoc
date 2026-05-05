# Agent 12 — Documentation & Runbook Completeness · Summary

## Severity counts
**P0: 2 · P1: 4 · P2: 4 · P3: 1 · Total: 11**

## Top 3 findings
1. **A12-P0-001** — Public Privacy + HIPAA pages assert "All subprocessors that touch PHI have signed BAAs"; `BAA_CHECKLIST.md` shows ZERO signed (Anthropic, OpenAI, Deepgram, Resend all `☐ NOT YET`). Misrepresentation to prospective Covered Entities.
2. **A12-P0-002** — No incident-response or breach-notification runbook. HIPAA §164.404 / §164.410 / §164.408 unactionable. `apps/marketing/src/app/hipaa/page.tsx:172-179` publicly commits to 60-day notification with no internal procedure. `docs/incidents/` referenced in ROTATION_RUNBOOK does not exist.
3. **A12-P1-001** — No consolidated DR runbook. Only 2 of 6 audit scenarios documented (VPS lost + B2 compromised, in `phase-6.2-backup-strategy.md`); MinIO recovery, Redis loss, DNS hijack absent. §164.308(a)(7)(ii)(B/C) unaddressed. RTO/RPO stated for one scenario only.

## Coverage
~140 .md in scope (excluding decommissioned `apps/meddoc-pro/*`); 17 read deeply, 25+ skimmed. All critical (README, AGENTS.md, CLAUDE.md, POST_MERGE_TODO, all runbooks, BAA_CHECKLIST, HIPAA_COMPLIANCE, KNOWN_ISSUES, LAUNCH_CHECKLIST/READINESS, PILOT_STATUS, KASRA_HANDOFF, AUDIT_T-M18, marketing legal pages, WORKER.md) — read. Skipped: `docs/A11Y_TESTING.md`, prior-audit detail, 20+ `preflight-reports/`, design-direction inventories.

## Gap matrix

| Doc | Status |
|---|---|
| Disaster recovery | MISSING (P1-001) |
| Incident response / breach notification | MISSING (P0-002) |
| Threat model | MISSING (P1-004) |
| BAA list (we ← subprocessors) | EXISTS, FALSE-CLAIMED on public pages (P0-001) |
| BAA template (we → CE) | MISSING (P2-003) |
| Onboarding doc | MISSING — CLAUDE.md is 11 bytes (P1-003) |
| Architecture diagram | MISSING (P2-001) |
| Phase 6.2 runbook gaps | (1) MinIO offsite-activation procedure not in runbook; (2) MinIO restore drill not in runbook — POST_MERGE_TODO §22 acknowledges + defers (P1-002) |
| ADRs | MISSING — 13+ implicit decisions identified (P1-004) |
| Changelog / OpenAPI / DPA / SOC 2 | MISSING (P2-003) |

## Phase 6.2 — the 2 runbook gaps explicitly
**Gap 1**: `docs/RUNBOOK_OFFSITE_BACKUP.md` is 100% Postgres; MinIO activation has no runbook section parallel to its §A-§G shape — only the 3-line manual sync test in POST_MERGE_TODO §22 step 7. **Gap 2**: MinIO restore drill has no procedure anywhere — `scripts/restore-drill.sh` covers Postgres only; POST_MERGE_TODO §22 line 1350 explicitly defers ("Document as a runbook addendum when first MinIO restore is exercised"). Both gaps must close before flipping the `phase-6.2-live` tag (POST_MERGE_TODO §22 step 11).

## Positives
1. `POST_MERGE_TODO.md` is exceptional — 23 sections, every milestone has PR + SHA + tag + verification + lessons-added (Phase 5.1.1 + Phase 6.1 entries are post-mortem-grade).
2. `RUNBOOK_OFFSITE_BACKUP.md` is a textbook runbook for the Postgres half — §A-§G shape (one-time setup → first-run → restore → key custody → rotation → ops notes → resolution checklist) is the right template; A12-P1-002 fix replicates it for MinIO.
3. `ROTATION_RUNBOOK.md` covers every secret with the right "provision → cut over → drain → revoke" idiom; emergency/leak procedure correctly inverted.
4. `KNOWN_ISSUES.md` "trigger / impact / mitigation / escalation" format is the right pattern for living caveats — KI-1, KI-3, KI-4 work for both resolved and open.
5. `apps/transcribe-md/WORKER.md` pipeline table (lines 18-25) is a tight architecture artifact; structure is good.

## Cross-domain hooks
- **Agent 03** has a finding on multi-tenant cascade — flag for cross-ref into onboarding.
- **Agent 05** (compliance/HIPAA): A12-P0-002 + A12-P1-004 are the biggest HIPAA-shaped doc gaps.
- **Agent 01/07** (security/infra): A12-P0-001 (BAA over-statement) is partly an infra issue (env vars enable PHI flows pre-BAA).
- **Agent 09** (DB): A12-P0-002 forensics path depends on stable `audit_logs` schema — joint review with any schema-evolution finding.
- **Phase 6.2 activation**: any infra agent flipping `phase-6.2-live` must consume A12-P1-002 first.
- **README staleness (P2-002)**: docs-CI check proposed there catches future "8 containers" / old-IP / pre-Phase-6.1 path regressions.
