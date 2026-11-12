# CPT harness, Stage 1: the actual starting point (2026-11-01)

The evidence for checklist items 1.1 to 1.4 of `CPT-HARNESS-CHECKLIST.md`. Every code citation is `cpt-studio/<path>:<line>`
at `c7f812258`, whose `cpt-studio/` tree is byte-identical to the live revision `80df1831d168`
(`git diff --quiet 80df1831d168 HEAD -- cpt-studio/` exits 0). Live facts come from read-only queries (a `BEGIN READ
ONLY` transaction) and `docker inspect`, run 2026-11-01 between 21:15Z and 21:35Z. No credential file was opened and no
provider request was sent.

The map was drafted by four read-only code readers and is engineering analysis, not clinical review. The integration
owner re-checked the claims this file relies on against the code before recording them.

## 1. What is installed (item 1.1)

| fact | value | how it was read |
|---|---|---|
| served revision | `80df1831d168c4ee83d83c37bac9860690986cf3` | image label `org.opencontainers.image.revision` on `cpt-studio-web` and `cpt-studio-worker` |
| image | `sha256:88544c7cd33fc6d0ad9ae2ebd0c90e40edcdb2a2b5226de526440cb96b282a10` (web and worker) | `docker inspect` |
| started | web 2026-10-31T12:55:27Z, worker 2026-10-31T12:55:30Z; web healthy | `docker inspect` |
| shared checkout | `/opt/meddoc-pro` on `main`, no tracked change | `.git/HEAD`; `git status --porcelain --untracked-files=no` read through `--git-dir` |
| harness work | worktree `/opt/meddoc-pro/.worktrees/harness-checklist` | — |

Work in flight when the directive arrived:
- **Round-4 interpretation repairs.** Branch `fix/cpt-studio-gi4-interpretation-20261101`; Wave 1 repair cycle 2 is being
  integrated.
- **Ordinary-reviewer acceptance tool.** `1e23e80b6`, being merged with it.
- **CPT Studio pypdf 6.21.4 move.** Deferred (interpretation 68).
- **Rebuild.** P1 is installed (`c8b54991`). The rebuild is a different application and not part of this harness.

## 2. The document-to-code workflow (item 1.2)

**Stages.** Upload (web) → extract → analyze → predict → assess. A reviewer can additionally ask for `review2` → assess
(`studio/jobs.py:1`, `studio/jobs.py:1022-1023`). One worker container runs one job at a time, oldest first
(`studio/jobs.py:1028-1046`, `studio/jobs.py:1140-1154`). There is no automatic retry (`Job.max_attempts` is never read,
`studio/models.py:379`).

| step | what it does | evidence |
|---|---|---|
| upload | `.pdf`, `.docx` and `.txt` (checked by extension and by signature), or paste up to 400,000 characters. Requires a synthetic attestation; an optional member-entered date is kept as metadata. The original is written once, mode 0600, re-read and sha256-verified; every later read re-verifies it | `studio/api.py:153-185`, `studio/storage.py:16-79`, `studio/intake.py:32-52` |
| extract | Runs in an isolated child process with resource limits, a minimal environment, no Django and a process-group kill at the deadline. Word, native PDF (with forms and annotations) and OCR at 300 dpi. Records page tiling and messages once per revision | `studio/jobs.py:345-386`, `studio/ingest/extract.py:41-391` |
| analyze | Reads the context (date of service, setting, billing context, patient status: value, origin, evidence) and routing (document kind; per family: status, mentions, facts) in a bounded child | `studio/jobs.py:389-407`, `studio/gi/context.py:1-11`, `studio/gi/detect.py:1-33` |
| predict | Sends to Corti: the whole revision text, plus `Date of service: YYYY-MM-DD` when the context's date is settled | `studio/providers/corti.py:49-70`, `studio/jobs.py:545-599` |
| assess | A bounded child re-routes and reads the documented-service inventory from the text alone. It validates each code Corti SELECTED (exact evidence, family, status from the documented service, required facts, E/M rules, CMS fee-schedule presence, MUE units, endoscopic base) and reconciles the inventory against the proposals | `studio/jobs.py:671-706`, `studio/validation/engine.py:127-248` |
| clarification | Questions about the date, member conflicts, service documentation and individual proposals. Answered by a context edit or an addendum (a new revision) | `studio/validation/engine.py:470-503`, `studio/api.py:218-288` |
| review | An owner or reviewer approves, rejects, reinstates, confirms or revokes. Approval needs READY status, exact evidence and the attestation text for the reviewer's kind (human or agent). Decisions are append-only, and a new revision invalidates them | `studio/review.py:37-45`, `studio/review.py:182-321` |
| reports | Draft or reviewed, TXT or CSV, built from persisted rows only. Stored immutably with sha256. A reviewed report needs readiness | `studio/reports.py:1-8`, `studio/reports.py:1029-1048` |

### Production clinical reviewers versus engineering agents

- **Corti** is the only model that reads an uploaded document in production. It returns selected, candidate and
  alternative CPT codes with evidence spans. Nothing it returns is approved automatically.
- **Local readers** are deterministic code, not models: extraction, context, routing, the inventory, validation,
  reconciliation and the CMS lookup. `requirements.in` lists no model library.
- **Human reviewers** are the owner and the doctor's demonstration reviewer.
- **The review-agent account** (`actor_kind=agent`) is driven by `ops/verify_browser.cjs`. Its decisions are scripted
  from a manifest; it is not a model reading the document. Its decisions are labelled "agent" in the UI, the API and both
  reports.
- **Astra and Fable are absent.** There is no adapter, setting or credential handling for either
  (`studio/providers/__init__.py:18-53`). The only occurrence of "astra" is a test that refuses it as an unknown
  provider (`tests/test_providers.py:1032-1034`).
- **Engineering agents** (refutation lenses, skeptics, repair and integration agents) reviewed code and measured readers
  on constructed synthetic text. They have no runtime component and do not satisfy the directive.

## 3. Provider access (item 1.3)

### Corti (live; the only participant today)

**Endpoint and authentication.**
- OAuth2 client credentials at `https://auth.{us|eu}.corti.app/realms/{tenant}/protocol/openid-connect/token`.
- Then `POST https://api.{us|eu}.corti.app/v2/tools/coding/` with `Tenant-Name` (`studio/providers/corti.py:38-39`,
  `:140-180`).
- The environment (us or eu) and the tenant are in the credentials file, which was not opened. **Neither is recorded on
  a run.**

**Model identifier.** None is sent or returned. The retained response's top-level keys are `codes`, `candidates` and
`usageInfo`. CPT Studio records its own adapter label, `corti-coding-v2@cptstudio-1`.

**Live evidence** (read-only, `studio_providerrun`):

| purpose | state | sent | runs | with `X-Request-Id` | first | last |
|---|---|---|---|---|---|---|
| primary | succeeded | yes | 45 | 45 | 2026-10-26 | 2026-10-31T13:02:54Z |
| primary | succeeded (reused, nothing sent) | no | 4 | 4 | 2026-10-29 | 2026-10-31T12:57:10Z |
| primary | not_sent | no | 1 | 0 | 2026-10-29 | 2026-10-29 |
| second_review | succeeded | yes | 1 | 1 | 2026-10-28 | 2026-10-28 |

- Usage basis: `provider_reported_credits_not_usd`, or reuse with no new usage.
- Authorization reference on every sent run: `docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`.

**What this does not cover.** It is not a fresh capability check. A fresh check is planned through the harness's
per-participant access check, which records the endpoint actually used.

### Astra (owner-confirmed 2026-11-01: OpenAI GPT-6 Astra, `gpt-6-astra`, `POST https://api.openai.com/v1/responses`, Bearer)

- **No CPT Studio credential exists.**
- **QuillMD has never called OpenAI.** Its `core_aistagereceipt` and `core_providerreceipt` hold no OpenAI row.
- **QuillMD's possible key is not reachable.** QuillMD reads `OPENAI_API_KEY` from its process environment, loaded from
  `rebuild/.env` (`rebuild/deploy/quillmd-fresh-*.service`). That file is never read by this session, so whether a key
  is set there is unknown, and it is not reused.
- **Status: BLOCKED** on one credential (see the consolidated request in the checklist).

### Fable (owner-confirmed 2026-11-01: Anthropic Claude Fable 5.1, `claude-fable-5-1`, `POST https://api.anthropic.com/v1/messages`)

- **The owner's authorized Anthropic account is in production use by QuillMD.** It has 371 succeeded
  `claude-sonnet-5-5` stage calls, the last on 2026-10-23, and 20 `claude-sonnet-4-6` receipts.
- **That key exists on this host only inside `rebuild/.env`.** Extracting it would mean reading another service's
  environment, which the owner's instruction and this programme's standing rule both forbid.
- **Status: BLOCKED** on one credential, a dedicated key in the same account (see the consolidated request).

### Egress

- **From the host,** with no credentials sent: `https://api.anthropic.com/v1/models` answers 401 (reachable, a key is
  required), and `https://www.cms.gov/` answers 200.
- **Containers:** CPT Studio's web and worker sit on a non-internal Docker bridge, `cpt-studio-net`. Nothing in
  `cpt-studio/` restricts egress (`ops/install.py:1255-1263`). Corti's adapter pins its own hosts and refuses redirects
  and proxies.

## 4. Reference sources (item 1.4)

### Loaded live

| key | kind | release | effective | retrieved | rows |
|---|---|---|---|---|---|
| `cms-pfs-rvu26d` | CMS physician fee schedule relative value file (PPRRVU nonQPP member) | RVU26D | 2026-10-01 to 2026-12-31 | 2026-10-16 | 19,453 |
| `cms-mue-practitioner-2026q4` | CMS NCCI practitioner MUE table | 2026-Q4 | 2026-10-01 to 2026-12-31 | 2026-10-23 | 15,212 |

The two sources hold 34,665 code facts in total.

### How they are used

- **Imported indicators:** status, global days, multiple procedure, endoscopic base, PC/TC, and the modifier rows (26,
  TC, 53). The MUE table supplies value, MAI and rationale.
- **Store.** Imports read a local zip pinned by sha256; the URL is recorded, never fetched (`studio/reference/importers.py:93-104`).
- **Checks.** They feed `pfs.presence`, `mue.units` and `pfs.endoscopic_base`. These never change a proposal's status,
  except that global days decides a procedure day (`studio/validation/engine.py:1426-1436`).

### Not connected, reported "not verified" on every proposal (`studio/validation/checks.py:954-962`)

- **AMA CPT code-set membership and descriptors.** No licence is held, and descriptors are never stored or shown.
- **CMS NCCI procedure-to-procedure (PTP) edits.** Recorded in interpretations 1 to 3 as available only behind an AMA
  point-and-click agreement. Accepting it would be a new agreement, which this directive excludes.
- **Not present at all:** the NCCI Policy Manual, CMS manuals, NCCI add-on edits, and payer policies.

### Retrieval

There is none in the directive's sense: no retrieval stage, no retrieved passages and no tool traces. The assess child
has no database access, so lookups are prefetched, and only for Corti's selected codes (`studio/reference/store.py:143-175`,
`studio/jobs.py:687`).

### Use terms

The terms for each candidate source are being checked against the publisher's own download pages before anything is
imported (owner instruction, 2026-11-01).

## 5. What a three-participant harness has to change (from the map)

- **One adapter per installation, chosen by one global mode.** Corti cannot run live with Astra off
  (`studio/providers/__init__.py:25-45`).
- **The normalized output holds codes only** (`studio/types.py:137-144`). It has no place for service facts, missing
  services or clarification needs.
- **Only Corti's codes become proposals.** An assessment links one primary run and one second-review run
  (`studio/models.py:261-264`). Proposals come from Corti's selected codes only (`studio/validation/engine.py:1-8`).
- **No model or endpoint column on a run.** Corti's environment and tenant are not recorded (`studio/models.py:206-252`).
- **The unknown-outcome block is encounter-wide** (`studio/jobs.py:291-292`). A reconcile always re-queues Corti's
  predict (`studio/jobs.py:1243-1245`).
- **Send deadline.** One deadline of 150 s for every send, which equals the worker's stop timeout (`studio/jobs.py:630`,
  `ops/install.py:56`).
- **Installer secrets.** The secrets phase is all-or-nothing over three files (`ops/install.py:581-656`). Mounts, live
  checks and rollback hazards are Corti-only.
- **No administrative view exists.** There is no Django admin and no owner-only page. Provider traces show in the
  Activity tab to every member.
- **Design pins.** The approved design is pinned by the CSS prefix sha256 and by node tests of the progress card,
  provider rows and state cards (`tests/test_frontend.py`, `tests/frontend/app.test.cjs`). `ops/verify_browser.cjs` waits
  for `.progress-card` to disappear.

## Open questions carried forward

1. Corti's environment, tenant and model are not recorded per run. The harness records the endpoint actually used.
2. Whether model participants fit a 150 s send deadline and the 150 s worker stop timeout. To be measured.
3. The licence position on sending a synthetic clinical document to OpenAI and Anthropic and receiving CPT code numbers.
   No CPT data file or descriptor is sent; this is recorded with the research on use terms.
4. `processing_failed` has no review-page card, and the failed stage's error is not shown once idle. Found by the map;
   it is a pre-existing gap.
