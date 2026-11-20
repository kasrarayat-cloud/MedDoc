# CPT Studio

A standalone, login-protected, **synthetic-only** CPT coding workspace for `cpt.quillmd.com`. A member uploads an
original clinical document (PDF, DOCX or pasted text) with the practice's date of service and insurance. Claude Fable 5.2
reads the original file twice through the Anthropic API - once as the coding **reader**, once as an independent
**checker** - and the page shows each code with its units, modifiers, status, reason, the second check's verdict and the
quoted passages. The member answers any questions (which starts a new coding round), approves or rejects the codes, and
downloads a draft or an approved export. Every decision is recorded against the exact round it was made on.

Fable's decision is final apart from the human: no code holds, drops, upgrades or downgrades a code it returned
(owner decisions D351-D352).

- Owner directive: `docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`
- Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Customer JSON API: [`API.md`](API.md)
- The customer page's DOM and copy contract: [`CORE-UX-DESIGN.md`](CORE-UX-DESIGN.md)
- Install and rollback: [`ops/INSTALL.md`](ops/INSTALL.md)
- Records of the earlier pipeline (decisions, spend ledger, acceptance-set seals): `docs/gemini-migration/`

## What it does not do

- Process real patient information: every upload carries an explicit synthetic attestation and `SYNTHETIC_ONLY` is a
  constant.
- Show CPT descriptors: no CPT edition is licensed, so the page shows the code, units, modifiers and the coding review's
  reason.
- Resend a paid request automatically: an outcome that may have reached the vendor is recorded unknown, for an operator's
  reconcile or a member's retry.
- Claim accuracy, or approve anything by itself: a human (or a labelled review agent) approves each code.

## Develop

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
export CPT_STUDIO_SECRET_KEY=dev-only CPT_STUDIO_DB_PASSWORD=... CPT_STUDIO_DB_PORT=55452 \
       CPT_STUDIO_STATE_DIR=$PWD/.runtime CPT_STUDIO_TEST_DB_SUFFIX=$USER
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test tests --noinput     # the Django suite (it runs the page's node tests too)
node tests/frontend/app.test.cjs                     # the page's logic on its own
```

`CPT_STUDIO_CODING_MODE` is `disabled` by default (nothing is sent); `replay` reads recorded answers from
`CPT_STUDIO_CODING_REPLAY_DIR`; `live` sends, with the key read from `CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE`, and only for
a synthetic-attested document, with `CPT_STUDIO_AUTHORIZATION_REF` set, at an owner's or reviewer's request.

- Worker: `manage.py run_worker` (`CPT_STUDIO_CONCURRENT_DOCUMENTS` threads, default 4; `--once` drains the queue and
  exits).
- Accounts and the workspace: `manage.py provision` (passwords from files, never argv).
- Reference data: `manage.py import_reference` (CMS PFS RVU and practitioner MUE, sha256-pinned; descriptors are never
  imported) and `manage.py import_passages` (the bundled CMS policy passages).
- Operator access, with a reason file (never argv); an operator with no membership signs in on the usual page and lands
  on `/ops/`:

```bash
python manage.py grant_operator --username <account> --reason-file <file> [--by <your label>]
python manage.py revoke_operator --username <account> --reason-file <file> [--by <your label>]
```
