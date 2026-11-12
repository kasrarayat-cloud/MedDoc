# Harness repair (owner directive 2026-11-05): stage 1, the baseline

Read by session a12d8fb3 on 2026-11-05 between 09:03Z and 09:16Z, before any change. Every number is a read-only
measurement: SELECTs inside a read-only transaction through the database container's own psql, `docker inspect`, and
`curl`. No row was written and no provider request was sent.

## Served revision and configuration

- `https://cpt.quillmd.com/health/` at 09:03:49Z: `{"status": "ok", "data_mode": "synthetic-only", "release":
  "b0dc3446c64c840cd01e9f37b8de3bad7aa954d4", "database": "ok"}`.
- `cpt-studio-web` and `cpt-studio-worker` both run image `sha256:b29413df09c108ad008fdaf61ef4f9d7ffdddde8ccaa1f97fd9f62ebe17e1810`,
  label `org.opencontainers.image.revision` = `b0dc3446c64c…`, started 2026-11-05T04:05:33Z and 04:05:40Z. Both:
  restart `unless-stopped`, read-only root filesystem, user `10150:10150`, network `cpt-studio-net`.
- Configuration (non-secret values only; the secret key, the database password and the credential files' contents
  were not read): `CPT_STUDIO_PROVIDER_MODE=live`, `CPT_STUDIO_ASTRA_MODE=live`, `CPT_STUDIO_FABLE_MODE=live`,
  `CPT_STUDIO_RELEASE_SHA=b0dc3446…`, `CPT_STUDIO_HTTPS=1`, `CPT_STUDIO_TRUST_PROXY=1`,
  `CPT_STUDIO_STATE_DIR=/var/lib/cpt-studio`, `CPT_STUDIO_AUTHORIZATION_REF=docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`,
  the three credential files at `/run/cpt-studio/{corti,openai,anthropic}-credentials.env`, database
  `cpt-studio-db:5432/cptstudio`.
- The last install's receipts (`/home/claude/cpt-studio-install-20261023/app-20261105T040807902688Z.json`,
  `verify-20261105T041012889994Z.json`): blue/green 9151 to 9150, 297 availability samples with none not 200,
  participants `astra: live`, `fable: live`, the rollback image of 24c49a50 kept.
- Code: `origin/main` is `8645fd54ff7664c3436e60c1585ba363d086c325` (#1471). No runtime file differs from the served
  revision: `git diff --name-only b0dc3446..8645fd54` lists 8 files, all records, the checklist, or the walk tool and
  its samples (`ops/verify_browser.cjs`, `ops/verification/`); none under `studio/`, `cpt_studio/`, the Dockerfile or
  the requirements.

## Concurrent writers

At 09:16Z no installer, ruled-act runner, walk or reassessment process ran on the host; the only worktree changed in
the last 24 hours besides the shared tree was this repair's; no CPT Studio pull request was open. The shared tree
`/opt/meddoc-pro` is on `main` (its `.git/HEAD`).

## Preservation baseline (live database, 09:06:50Z)

The full read is `baseline-pre-20261105T090650Z.txt` in the session's evidence directory (88 lines, made by the
read-only `live_baseline.sh` of the previous programme). The counts every later step must preserve:

| table | rows | | table | rows |
|---|---|---|---|---|
| encounters | 55 | | decisions | 30 |
| revisions | 55 | | decision invalidations | 0 |
| source files | 49 | | audit events | 604 |
| contexts | 71 | | reports | 129 |
| routing runs | 64 | | jobs | 300 (0 active) |
| provider runs | 107 (97 sent) | | member answers | 8 |
| assessments | 86 | | provider exchanges | 63 |
| proposals | 1,068 | | tool calls | 40 |
| clarifications | 127 | | reference facts | 34,665 |

- Participant runs: Astra independent 10 and peer review 12, Fable independent 10 and peer review 10, all succeeded.
  Corti credits recorded in total: 2.832088. No run is unknown and unreconciled; none is reserved or sending.
- Encounter states: extraction_failed 1, needs_clarification 28, no_codes 4, ready_for_review 4, reviewed 18.
- Accounts: `demo-reviewer` (human, reviewer), `owner` (human, owner), `review-agent` (agent, reviewer), `ops-agent`
  (agent), `platform-operator` (human); two operator grants, none revoked.
- Reference sources: CMS PFS RVU26D (19,453 rows) and CMS practitioner MUE 2026-Q4 (15,212 rows).
- Migrations: 12, the last `0012_cux_worker_beat`.
- The last audit event: `assessment.created` at 07:43:47Z (the inspected encounter's last re-assessment).

## The inspected encounter, as stored

`88d9db32-65b5-4a55-98ee-b82ce0da8941`: one revision (PDF text layer, 5,783 characters, text sha256 `98afa4270bb9a7c5…`),
state `needs_clarification`, no decision, five assessments (07:38:40Z to 07:43:47Z). Its nine provider runs, in order:
Corti primary not sent (the dateless request, 07:38:40Z) then sent (HTTP 200, 07:39:22Z); Astra and Fable first
readings (HTTP 200, `gpt-6-astra` and `claude-fable-5-1` requested and returned); Astra and Fable peer reviews (HTTP 200);
Corti's bounded second review, requested by the owner at 07:43:31Z and sent at 07:43:32Z (HTTP 200); and the two peer
reviews reused, not sent, for the last assessment. **The second review is consumed. It is not reset, re-sent or
reused under another identity by this repair.** Its retained answer is re-read by the reassessment (stage 9).
