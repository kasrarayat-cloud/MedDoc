# CPT Studio

A standalone, login-protected, **synthetic-only** CPT coding workspace for
`cpt.quillmd.com`. A member uploads an original clinical document (PDF, DOCX
or pasted text); the service extracts the text (OCR for scanned PDFs), routes
the documented services to internal Gastroenterology profiles, asks the
initial proposal adapter (Corti) for CPT proposals, checks them against the
reference data that is actually installed, and records the reviewer's
decisions and reports against the exact source revision.

- Owner directive: `docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`
- Architecture contract: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Frontend JSON contract: [`API.md`](API.md)
- Install: [`ops/INSTALL.md`](ops/INSTALL.md)

## What it does not do

- Process real patient information (every upload carries an explicit synthetic
  attestation; `SYNTHETIC_ONLY` is a constant).
- Show CPT descriptors or claim CPT code-set validity: no CPT edition is
  licensed, so descriptors are withheld and membership is reported as not
  verified.
- Run NCCI procedure-to-procedure edits: CMS serves them only behind an AMA
  point-and-click agreement, which is an owner decision.
- Claim accuracy. Accuracy is measured only with `evaluate_cases` against
  independently adjudicated cases withheld from development.

## Develop

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export CPT_STUDIO_SECRET_KEY=dev-only CPT_STUDIO_DB_PASSWORD=... CPT_STUDIO_DB_PORT=55452 \
       CPT_STUDIO_STATE_DIR=$PWD/.runtime CPT_STUDIO_TEST_DB_SUFFIX=$USER
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test tests --noinput
```

Pipeline worker: `manage.py run_worker` (`--once` drains the queue and exits).
Accounts and the GI workspace: `manage.py provision` (passwords from files).
Reference data: `manage.py import_reference` (CMS PFS RVU and practitioner MUE,
sha256-pinned; descriptors are never imported).
