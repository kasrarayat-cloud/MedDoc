# Custom agents — `.claude/agents/`

QuillMD-specific agents that Lead can invoke. Each agent is a
directory with a `SKILL.md` (skill registration), a `README.md`
(operator-facing overview), and a `skills/` dir of methodology +
domain-knowledge documents.

| Agent | Status | Purpose | Trigger phrase |
|---|---|---|---|
| [`qa-interaction-auditor`](./qa-interaction-auditor/) | **active** (v3.3) | Walks the QuillMD UI clicking every interactive element + verifies each click produces the state change it appears to. Catches feature stubs, orphan event dispatchers, "pretend success" fallbacks, and parser/renderer mismatches. | "Run the QA agent / QA sweep / interaction sweep" |
| [`ai-pipeline-auditor`](./ai-pipeline-auditor/) | **DORMANT (designed, not activated)** | Audits the AI pipeline (transcribe → SOAP → coding → Rx → referral) for cost / quality / coverage / model-assignment drift. Read-only against `transcribe_visits` + `ai_calls` + `audit_logs` + eval results. | "Run the AI pipeline audit" (post-activation) |
| [`hipaa-compliance-auditor`](./hipaa-compliance-auditor/) | **DORMANT (designed, staged activation)** | Audits HIPAA compliance posture: §164.308 (admin) + §164.310 (physical attestation) + §164.312 (technical — access control, audit controls, integrity, auth, transmission). Read-only against `audit_logs` + users + sessions + filesystem + container env. **Does NOT read PHI content; counts bucketed; visit IDs short-hashed in reports.** Per-phase activation gating — most phases run today; phases 2+3 wait for pilot data. | "Run the HIPAA compliance audit" (post-activation) |

## Activation gates

Some agents have data-readiness gates that prevent activation
until the underlying signal exists:

- **`ai-pipeline-auditor`** — gated on `≥20 real visits across
  ≥3 distinct doctors` in `transcribe_visits` with
  `status=READY`. Below this threshold the agent's findings would
  be stylistic rather than behavioral. See
  [`ai-pipeline-auditor/skills/activation-criteria.md`](./ai-pipeline-auditor/skills/activation-criteria.md)
  for the full activation runbook + pre-pilot polish backlog.
- **`hipaa-compliance-auditor`** — staged activation. Most
  phases (0/1/4/5/6/7/8/9) can run today; phases 2 + 3 (audit
  controls + integrity) wait for the same pilot-data threshold
  as `ai-pipeline-auditor`. Initial activation enables the
  today-runnable phases; mid-pilot activation enables phases 2
  + 3. See
  [`hipaa-compliance-auditor/skills/activation-criteria.md`](./hipaa-compliance-auditor/skills/activation-criteria.md)
  for the staged runbook + 12-item pre-activation polish
  backlog.

A DORMANT agent ships as a design artifact (directory + skills
docs) but **does NOT have a `SKILL.md`** — its absence keeps
Lead's skill system from listing the agent as invocable. Adding
`SKILL.md` is the explicit activation step; the operator
(Kasra) does that consciously after the gate is met.

## Adding a new agent

1. Create a directory under `.claude/agents/<agent-name>/`.
2. Author `README.md` (operator-facing overview).
3. Author `skills/*.md` per the agent's domain (methodology,
   data sources, finding classes / output format,
   activation-criteria if dormant).
4. Add `scripts/.gitkeep` + `fixtures/.gitkeep` to preserve
   empty dirs (or actual files if shipping active).
5. Add a row to this table.
6. **If shipping active**: also author `SKILL.md` with the
   `name:` + `description:` frontmatter Lead's skill system
   reads. Pick a trigger phrase that doesn't collide with any
   existing skill.
7. **If shipping dormant**: leave `SKILL.md` out. Document the
   activation gate in `skills/activation-criteria.md`.

## Why a custom-agent dir at all?

QuillMD has domain-specific quality dimensions that don't fit
the generic agents (general-purpose, Explore, Plan, etc.) Lead
ships with. The qa-interaction-auditor catches a class of bugs
(orphan dispatchers, pretend-success fallbacks) that wouldn't
register as findings to a generic UI-test agent. Same for
ai-pipeline-auditor — the per-layer cost/quality/coverage
matrix is pipeline-specific.

Agents under this directory are **versioned with the codebase**.
A change to the audited surface lands in the same PR that
updates the agent's site-map.md / methodology.md / finding-
classes.md so the agent never goes stale silently.
