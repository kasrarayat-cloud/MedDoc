# HIPAA Compliance Auditor

> **Status: SHADOW MODE** (active, advisory-only) as of merge of
> `agent/auditors-shadow-mode`. The agent runs on demand against
> the live system read-only; findings route to
> `docs/agent-shadow-runs/hipaa-compliance/<UTC>.md` (advisory)
> instead of the production report path. Phases 0/1/4/5/6/7/8/9
> produce real signal today; phases 2 + 3 emit `NO_DATA` markers
> until the pilot threshold (≥20 visits across ≥3 doctors) is
> met. Findings do NOT block any merge, deploy, or operator
> action — but `BLOCKING_*`-class findings should still be
> escalated to compliance counsel. Trigger phrase: **"Run the
> HIPAA compliance shadow audit"**. See `SKILL.md` and
> `skills/activation-criteria.md`.

An agent that audits QuillMD's **HIPAA compliance
posture** continuously: §164.308 (administrative safeguards —
workforce training, contingency plan, vendor BAAs), §164.310
(physical — facility, workstation, encryption-at-rest config
attestation), §164.312 (technical — access control, audit
controls, integrity, transmission security). Read-only against
the production system + `audit_logs` + filesystem + container
env.

## Why a separate agent (not part of the other two)

QuillMD already has two agents:

- **`qa-interaction-auditor`** (active v3.3) — walks UI
  surfaces; catches click-class bugs (orphan dispatchers,
  pretend-success, parser/renderer mismatches). The §164.312(b)
  audit-row gaps in F-09/F-10/F-11 were caught by this agent.
- **`ai-pipeline-auditor`** (designed, dormant) — audits the
  AI pipeline for cost/quality/coverage/model-assignment drift.

Neither catches **compliance posture drift** — is encryption
still on? Are audit rows still being written across the full
action enum? Are vendor BAAs still in date? Are SUPER_ADMIN
accounts still limited to the expected list? Are sessions
properly scoped? Compliance lives at a different layer than UI
behavior or AI quality, so a separate agent is the right shape.

The three agents form a triad:

| Agent | Catches | Trigger |
|---|---|---|
| qa-interaction-auditor | UI behavior bugs | "Run the QA agent" |
| ai-pipeline-auditor | AI pipeline drift | "Run the AI pipeline audit" (post-activation) |
| hipaa-compliance-auditor | Compliance posture drift | "Run the HIPAA compliance audit" (post-activation) |

## What it audits (high level — see `skills/` for detail)

10 audit phases, each mapping to a HIPAA citation or
operational hardening axis:

| Phase | Citation | What it inspects |
|---|---|---|
| 0 | n/a | Schema sanity — does the auditor's data still exist where it expects? |
| 1 | §164.312(a) | Access control — session scoping, inactive accounts, SUPER_ADMIN list, role-change audit |
| 2 | §164.312(b) | Audit controls — every enum action emitted in last 30d; PHI-read paths emit `VIEWED_X`; timestamp monotonicity; 6-year retention |
| 3 | §164.312(c) | Integrity — schema constraints; transcript immutability post-sign; SOAP version monotonicity |
| 4 | §164.312(d) | Authentication — MFA on admin accounts; password-reset audit pairs; session-cleanup job liveness |
| 5 | §164.312(e) | Transmission security — HTTPS-redirect; HSTS; TLS 1.2+; WSS-only sidecars |
| 6 | §164.310 | Physical safeguards (config attestation only — agent isn't on hardware) |
| 7 | §164.308 | Administrative — vendor BAAs in date; restore-drill freshness; workforce training |
| 8 | n/a (operational hardening) | Encryption posture — MinIO SSE-S3, postgres LUKS, backup encryption |
| 9 | n/a | Reporting — aggregate by severity + section; emit operator summary |

Full methodology + per-phase queries at `skills/methodology.md`.

## Activation gate (different from the other two — per-phase)

Most agent designs are all-or-nothing. This agent is staged:

| Phases | Gate | Why |
|---|---|---|
| 0, 5, 6, 7, 8, 9 | **None — runs today** | Schema sanity, transmission security, encryption, BAAs, encryption posture, reporting all read structural facts that exist regardless of pilot data |
| 1, 4 | **≥3 active accounts** (currently met) | Access control + auth phases need at least a few users to detect cross-tenant patterns |
| 2, 3 | **≥20 visits across ≥3 doctors** (same as ai-pipeline-auditor) | Audit-controls + integrity phases need real pipeline data to baseline against |

Initial activation enables phases 0 + 5–9 + 1 + 4 (most of the
agent's value); phases 2 + 3 enable when pilot data lands.
That partial-coverage report is itself useful — it's the
fastest path from "we have nothing" to "we have a recurring
compliance signal."

## Run cadence (when active)

**Nightly via cron** — only agent of the three with a
recurring schedule. The other two are operator-triggered
(qa-agent on demand, ai-pipeline-auditor when investigating).

A nightly compliance audit is the right shape because BAA
reviewers ask for "show me your audit cadence" + a recurring
signal lets the operator catch drift between the time it
appears and the time it'd otherwise be discovered (in a
quarterly review or — worse — during an actual breach
investigation).

## Trigger phrase (when active)

**"Run the HIPAA compliance audit"** — mirroring the other
agents' convention.

Output: NDJSON stream + aggregated markdown report at
`docs/compliance-audit-reports/<UTC-timestamp>.md`. Reports
retain forever (compliance trace).

## Directory layout

```
.claude/agents/hipaa-compliance-auditor/
├── README.md                      ← you are here
├── skills/
│   ├── methodology.md             ← 10-phase audit walkthrough
│   ├── finding-classes.md         ← P1/P2/P3 keyed to §164.x rules
│   ├── data-sources.md            ← what tables / files / configs the auditor reads
│   └── activation-criteria.md     ← per-phase gating + staged activation runbook
├── scripts/
│   └── .gitkeep                   ← empty pre-activation
└── fixtures/
    └── .gitkeep                   ← empty pre-activation
```

Mirrors `ai-pipeline-auditor/` (which mirrors
`qa-interaction-auditor/`). Three agents on the same
skeleton.

## What this agent does NOT do

- **Read free-text PHI.** Stricter than ai-pipeline-auditor.
  Reads NO content fields. Even row counts (which are
  PHI-adjacent — knowing "practice A has 47 visits" is
  metadata) get **bucketed** (1–10, 11–100, 101–1000, 1000+)
  before appearing in reports. Visit IDs in findings get
  short-hashed (last 6 chars only) so reports themselves
  carry no identifiers.
- **Make breach-notification decisions.** Some §164.312 gaps
  may be reportable to OCR (Office for Civil Rights) under
  45 CFR §164.404. The auditor **flags candidate findings**
  with an `ocr_reportable_candidate: true` field; the
  operator + counsel make the call. The auditor never
  declares a breach.
- **Touch hardware.** The auditor isn't on the VPS. Phase 6
  (physical safeguards) reads config attesting hardware
  posture (LUKS device path, MinIO encryption flag, backup
  destination), not the hardware itself.
- **Block any operation.** Read-only. Findings flow to a
  report; the operator decides remediation.
- **Touch `apps/meddoc-pro`.** Out of scope per memory #9.
- **Make HIPAA-section claims that aren't supported by 45 CFR
  Part 164.** Each phase that cites a rule (§164.312(a) etc.)
  is grounded in that rule's actual text. Phases 0/8/9 are
  labeled "operational hardening" rather than "HIPAA
  compliance" — they're useful but they're not the auditor's
  rule-citation surface.

## Reading order (for the activator)

If you're picking this up to activate, read in this order:

1. `skills/activation-criteria.md` — which phases can run
   today vs. need data?
2. `skills/data-sources.md` — what does each phase read?
3. `skills/methodology.md` — how does each phase compute its
   findings?
4. `skills/finding-classes.md` — what does the agent emit
   per finding, with §164.x citation?

Then implement the per-phase scripts under `scripts/` and
add a `SKILL.md` per `activation-criteria.md`'s staged
runbook.

## Honest framing

- This agent ships **before** any audit script exists. The
  value is the methodology + the citation map + the per-phase
  gating.
- Activation is staged because not all phases need pilot
  data. Most of the agent (phases 0, 1, 4, 5, 6, 7, 8, 9)
  can run on day one.
- HIPAA compliance is **fundamentally an attestation
  practice**: you assert controls + maintain evidence. The
  auditor produces evidence on a recurring cadence; the
  attestation is still the operator's responsibility.
