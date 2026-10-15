# QuillMD — fresh private application

Django 5.2, PostgreSQL, Django OTP, isolated Python document libraries, Anthropic/OpenAI adapters, Deepgram and Stripe. No legacy application data or compatibility code is used. The marketing site remains the existing Next.js workspace.

## Current preview

Doctor: http://127.0.0.1:9130 · Admin: http://127.0.0.1:9131

Use an SSH tunnel as described in `../docs/rebuild/private-hosting.md`. Both require individual logins; administrators also require TOTP. Synthetic account passwords and the bootstrap administrator TOTP enrollment are stored only in `.runtime/private-access.json` (0600). Do not copy that file into a report, Git, or chat.

**Synthetic data only.** This is private staging, not a cleared patient-data service. No public ingress routes to these listeners.

## Local setup

Python 3.12, Node 22 (browser tests), PostgreSQL 16+, Linux Landlock ABI 3+ and libseccomp are required. Parser sandbox failure refuses parsing. It does not fall back to an unsandboxed parser.

1. Create `.venv` with `python3 -m venv .venv`; install `requirements.txt`.
2. Copy `.env.example` to `.env`, use fresh secrets/database credentials and `chmod 600 .env`.
3. Provide an isolated PostgreSQL database. Never point this application at the old `meddoc` database.
4. Run `.venv/bin/python manage.py migrate`, `collectstatic --noinput`, then `seed_private` for synthetic test accounts. These migrations create only the fresh schema.
5. Run `bash start-private.sh`. Logs, PIDs and private files are in `.runtime`.

The existing VPS has already been initialized. **Do not rerun setup to replace its database or secret.** Follow the checkpoint for its actual ownership and paths.

## Supported workflow

Upload a DOCX with blank answer cells or `{{placeholders}}`, or an AcroForm PDF. Original bytes are retained and hashed. Review a versioned field map; choose a department/patient; enter notes or upload/record voice; explicitly approve generation's maximum charge; inspect source evidence and missing/conflicting answers; edit and individually review fields; finalize; download the filled original format. The original is never overwritten. Finalized encounters and mappings are immutable.

Generation is intentionally conservative: only complete, verbatim documented evidence can populate an answer. Negation, scope, contradictory values or unsafe instructions can require manual review. No autonomous diagnostic findings are generated. Unsupported/scanned PDFs, advanced Word content controls and unrepresentable/overflowing PDF answers are refused explicitly. See `documents/README.md` and the SDK evaluation before broadening formats.

Department memberships govern patients, templates, encounters, searches, files, exports and queued jobs. A same-department X-ray employee can share that department's patient; ultrasound and other organizations are separately scoped. Owners create departments, invite individual accounts and manage memberships.

The Coding tab prepares source-grounded suggestions for saved US outpatient/office encounters, using the official ICD-10-CM Index and Tabular release selected by service date. Historical releases remain available, including FY2027 for services from 1 October 2026. Suggestions require a separate explicit coding approval and do not change the clinical document. CPT is disabled without a licensed dataset, applicable selection criteria and current entitlement. Execution failures remain visible and retain their request evidence. See the [coding workflow](../docs/coding-workflow.md) for current behavior and verification requirements.

## Billing and integrations

Every verified new user, including invitees, receives exactly one personal $10 promotional grant. Promotional credit stays separate from paid funds; an organization's payer policy does not move the individual's grant. Reservations and settlement are transactional. A charge is `1.5 × defined actual billable provider cost`, in decimal precision, never more than the binding limit shown and held before the request (anything above it is absorbed as a platform cost), with provider units/rates and user/department/organization/payer recorded. No automatic top-up is implemented. Read `../docs/rebuild/cost-definition.md` for rounding and cost scope.

Provider receipts are persisted before output file storage. Unknown provider completion or an over-reservation cost enters reconciliation; workers never automatically repeat a possibly billed request. An output validation failure can still carry an actually incurred provider cost. The MFA-protected console exposes receipts, jobs, credits, paid balances, ledger, payments/refunds, reconciliation, account permissions and audit history.

Fixture generation is explicitly labeled and costs $0. The current VPS uses real Anthropic generation and Deepgram transcription with synthetic data. OpenAI exists as an adapter but the available key was rejected. Stripe test checkout/webhook/refund handling is implemented and tested with signed synthetic events; actual Stripe credentials are still required. No live Stripe charging is enabled. Email defaults to a private file outbox.

## Verification

```bash
QUILLMD_AI_MODE=fixture .venv/bin/python manage.py test core.tests --noinput
QUILLMD_AI_MODE=fixture .venv/bin/python -m unittest documents.tests -q
.venv/bin/python -m pip_audit -r requirements.txt
```

The browser gate (`node browser-tests.mjs`) requires seeded synthetic accounts and a running **fixture-mode** server/worker, refuses a live generation surface and writes a JSON report. CI provides a separate temporary database. See `../docs/rebuild/pentest-scope.md` for authorized test boundaries and `../docs/rebuild/CHECKPOINT.md` for results and remaining gates.
