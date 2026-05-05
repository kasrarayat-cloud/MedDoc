# QA Interaction Auditor

A permanent agent that walks the QuillMD UI clicking every interactive
element and verifying each click produces the state change it appears
to. Designed to catch the class of bugs where the front-end **looks
finished but isn't actually wired** — feature stubs that pass typecheck,
pass code review, and silently fail in production because the wire-up
was deferred to a "later PR" that never landed.

## What this agent catches

Three real production bugs from this week, all of which are this
agent's exact target:

1. **Bug A — Orphan event dispatcher.** "Confirm sign" button dispatched
   `qm:request-sign`. No listener anywhere. Button looked fine in code
   review for weeks.
2. **Bug B — Pretend-success fallback.** BumpModal's `onApplyAdditions`
   prop wasn't passed at the render site. Component fell through to a
   `return { ok: true }` standalone-build fallback. Doctor's edits never
   hit the database. Modal closed. Toast fired. Doctor moved on.
3. **Bug C — Parser/renderer mismatch.** L6 polish wrote a refusal
   banner with non-canonical headings. UI parser regex matched only
   `Subjective/Objective/Assessment/Plan` headings — returned 4 empty
   bodies — renderer emitted "section is empty" four times instead of
   the banner.

Pure backend testing wouldn't have caught any of these. Browser-driven
verification + DB diff verification is the only path.

## How Kasra invokes this

Speak any of these phrases to Lead:

- "Run the QA agent" / "Run the QA sweep" / "Run the interaction sweep"
- "Audit the [page name] for UX bugs"
- "Find no-op buttons / silent failures / stub features on [page]"
- "Check whether [button name] actually works"
- "Walk through the [workflow name] looking for bugs"
- "Run the interaction auditor"

That's it. Lead does the rest:

1. Reads `SKILL.md` + the four `skills/*.md` files into context.
2. Confirms the test user (`qa-auditor@quillmd.test`) is seeded —
   surfaces the seed command if not.
3. Runs static analysis (greps for stub-comment markers + orphan
   dispatchers + missing render-site props).
4. Runs `scripts/sweep-visit-page.mjs` against the target page (or skips
   if the request is "static analysis only").
5. Pipes findings into the report template from
   `skills/reporting-format.md`.
6. Surfaces the report. **Never** auto-fixes.

## What this agent will NOT do

- Auto-fix bugs. It reports findings with a recommended-fix scope; you
  ship the fix.
- Touch real PHI. Test user only; read-only DB queries only.
- Skip the static-analysis pass. Every run starts with greps even when
  the browser walk is the visible output. The grep catches latent bugs
  the browser walk would miss because they're on pages no test user
  touches.
- Install fresh tooling. Playwright is reused from
  `/opt/meddoc-pro/node_modules/playwright`.
- Diagnose outside its scope. AI pipeline / security / database
  schema findings are flagged for the appropriate specialist agent
  per `skills/reporting-format.md`.

## File layout

```
.claude/agents/qa-interaction-auditor/
├── SKILL.md                      # Agent contract — Lead reads this
├── README.md                     # This file
├── skills/
│   ├── bug-patterns.md           # Pattern A/B/C taxonomy + verbatim examples
│   ├── quillmd-workflows.md      # The sign-and-send workflow + element file:line cites
│   ├── verification-tools.md     # Playwright + Caddy log + DB snapshot snippets
│   └── reporting-format.md       # Bug template + severity rubric + escalation routing
├── fixtures/
│   ├── test-user.md              # qa-auditor@quillmd.test seeding instructions
│   └── sample-recordings/
│       └── README.md             # Non-PHI audio fixtures (synthesized at run-time)
└── scripts/
    ├── sweep-visit-page.mjs      # Playwright walk — emits NDJSON
    ├── diff-db-state.sh          # DB snapshot/diff via docker exec + psql
    └── check-network-mutations.mjs # Caddy access-log inspector
```

## First-run setup

The agent self-checks all of these and surfaces missing pieces:

1. **Test user.** Run the seed in `fixtures/test-user.md` once.
   `QA_AUDITOR_PASSWORD` lives in your shell, never in git.
2. **Playwright.** Already installed at
   `/opt/meddoc-pro/node_modules/playwright`. Chromium is cached at
   `~/.cache/ms-playwright/chromium-1217`. Don't `npm install`.
3. **Containers.** `meddoc-pro-postgres-1`, `meddoc-pro-caddy-1`, and
   `meddoc-pro-transcribe-md-1` must be healthy. Pre-flight check
   surfaces this.

After setup, every run re-checks these, so this list is the one-time
bootstrap.

## When to add a new workflow

Append a section to `skills/quillmd-workflows.md` with:

- URL + entry file
- Each interactive element (`file:line`, prop wiring)
- DB writes expected
- Audit-action enum values expected

The first run on the new workflow reads the section and auto-generates
the walk plan. If the section is missing, the agent falls back to
runtime DOM enumeration (less precise; verbatim cites from the file
are better).

## Versioning

Tagged at `agent-qa-interaction-auditor-v1`. Subsequent revisions get
a new tag (`v2`, `v3`, …); skill files use semver-y descriptive commit
messages so the change history reads like documentation.

## Out of scope

- `apps/meddoc-pro` (per memory #9).
- Backend-only logic (use the AI pipeline auditor or the Round 3 audit
  suite if relevant).
- Visual regression / pixel diffs.
- E2E flows that require real PHI.

If you're not sure whether a question is in scope, ask Lead — the
worst case is "this needs a different agent" and Lead routes the
request appropriately.
