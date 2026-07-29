# LAUNCH READINESS — Pilot

*Rewritten 2026-07-28 against live production. The previous revision was compiled
2026-04-26 and had drifted three months: it named a `main` HEAD from April, 23
users where there are now 195, and a container table predating the Gotenberg
sidecar. It is preserved in `git log -- LAUNCH_READINESS.md`.*

This document is the canonical pre-pilot snapshot. Every row below was verified
by running the check, not by reading a prior report. Where something could not
be verified, it says so.

---

## THE TABLE — everything between current `main` and pilot

Excluded by instruction, tracked elsewhere: **the Anthropic BAA countersign** and
**the report-template design pass**.

### 🟢 Green — verified this pass

| # | Item | How it was verified |
|---|---|---|
| 1 | **Critical-Rx typed override** — fail-closed | Live prod audit rows: `RX_DRUG_NOT_IN_VERIFIED_DATABASE` ×24, `RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY` ×5, `RX_DRUG_PAIR_INTERACTION` ×1, and `RX_OVERRIDE_RECORDED` ×2 — the warnings fire and the typed override is recorded when used |
| 2 | **E/M confirm at its rehomed chip** — fail-closed | `EM_OVERRIDE_APPLIED` ×5, `EM_LEVEL_CHANGED` ×6, and critically **`EM_SIGN_BLOCKED_UNACKNOWLEDGED_CHANGE` ×2** — the server-side refusal in `POST /sign` has actually stopped a signature in production, not just in a test |
| 3 | **Verifier audit-only** | `ANCHOR_FLAGS_RECORDED` ×7, most recent today. Recording, not gating — which is the intended posture |
| 4 | **`VIEWED_VISIT`** | ×205, most recent today |
| 5 | **Imaging E/M invariant** (standing check) | `bash scripts/check-imaging-em-artifacts.sh` → exit 0: *"0 of 13 imaging visits carry office E/M state"* |
| 6 | **Gate-flag coverage** (standing check) | `gate-flag-coverage.test.ts` 3/3 — every gated surface's flag is present in the CI image that exercises it |
| 7 | **Specialty fixture matrix** | `review-document.spec.ts` parameterises over `REVIEW_DOC_CLASSES` and asserts the E/M surface is ABSENT for imaging and present for office visits, plus a DB precondition that refuses to run if imaging visits carry office E/M state |
| 8 | **Unit + typecheck** | 2592 passed / 4 skipped across 213 files; `tsc --noEmit` clean |
| 9 | **Containers** | All **10** prod containers healthy — see §A |
| 10 | **Co-tenant isolation** | `quillmd.com` 200 · `pro.quillmd.com` 200 · `app.quillmd.com` 307 (auth redirect) · `admin.quillmd.com` 404 (allowlist) · `staging.quillmd.com` 200 |
| 11 | **`/_preview/` no longer public** | `https://app.quillmd.com/_preview/` → 404. This was an open finding from the 2026-07-24 full-app audit; re-checked and it is closed |
| 12 | **TLS renewal now reloads nginx** | **Fixed this pass.** The 2026-07-24 audit had diagnosed it exactly; it needed root, not analysis — see below |
| 13 | **Backup running** | `postgres-backup` container healthy |
| 14 | **Encryption at rest — BOTH stores** | Postgres → `/mnt/pgdata-encrypted`; MinIO → `/mnt/miniodata-encrypted/data`. **Verified against the KERNEL** (`findmnt` on the live container's resolved volume path), by `scripts/check-{minio,pg}-encrypted-mount.sh`. The weaker phrasing this row used to carry — "verified by container mount" — was itself insufficient and is the reason row 14 was **wrong for about four hours on 2026-07-29**: `docker inspect .Source` returns the same `/var/lib/docker/volumes/…/_data` string whether the path is a bind onto dm-crypt or a plain directory on `/dev/sda2`. See runbook §5.7.1 |
| 15 | **MinIO fails CLOSED if the volume is missing** | `device:` binds `…/data`, which exists only on the encrypted filesystem, and docker's local driver will not create a missing `driver_opts` device — so an unmounted volume stops MinIO instead of silently reverting it to plaintext. Negative-controlled 2026-07-29 |

### 🔴 Red — open, with what it would take

| # | Item | Severity | The actual state |
|---|---|---|---|
| R1 | **Deepgram BAA** | **pilot-blocking** | ☐ NOT YET. Deepgram is the PRIMARY ASR and receives raw patient audio. `docs/BAA_CHECKLIST.md` is explicit: *"Do not route real patient data through a processor whose BAA column is not COUNTERSIGNED."* Request form at deepgram.com/security/hipaa |
| R2 | **Resend BAA** | **pilot-blocking** | ☐ NOT YET. Visit-export email carries PHI — patient name in the subject and the signed SOAP note as a PDF attachment (`lib/email.ts`). Auth emails are link-only and would be fine; the export path is not |
| R3 | **VPS host BAA (Zap Hosting)** | **pilot-blocking** | ☐ VERIFY. Every row of PHI persists on this host. If Zap will not sign, the alternative is migration to a HIPAA-eligible host — which is a project, not a task, and needs to start before it is urgent |
| R4 | **Backblaze B2 BAA** | high | ☐ NOT YET. Offsite backup target. Blobs are encrypted client-side before they leave, which mitigates but does not remove the obligation |
| R5 | ~~**Open signup has no captcha**~~ → **the waitlist form has no captcha** | **was high; now low — the row was STALE, reconciled 2026-07-29** | **There is no open signup any more.** It went invite-only in `4455a7ce` (2026-07-28) and that is live in production, not merely on `main`: `app.quillmd.com/signup` serves an invite-code field and the copy *"QuillMD is invite-only during the pilot."* The account-creation surface this row was written about **no longer exists**, so "high" was describing a system that had already changed underneath it. What is left is the **waitlist form** (`/waitlist`, 200): same 5/hour/IP budget, still no captcha — but `joinWaitlistAction` writes exactly one `waitlist_entries` row and creates **no User, no Practice, no session, no auth token, no product grant**. There is nothing there to sign in with, which is what makes an open endpoint acceptable where open signup was not. **Low**, and the honest residue is spam rows in one table. ⚠️ **Two things this reconciliation does NOT close** — (1) the **residue**: 195 accounts / 23 ever logged in / 43 email-verified is *unchanged*, because closing the door does not empty the room; the population query is still polluted and §F still applies. (2) **Signup is currently closed to everyone, including a pilot doctor**: `invite_codes` has **0 rows** and `SIGNUP_INVITE_CODES` is **unset in the running app container**, so no valid code exists from either source. Minting one is a prerequisite of onboarding, not a step during it |
| R6 | **`h8-h3-pilot-followup`** — disk encryption | high, **narrowed 2026-07-29, then CORRECTED the same day** | **Encryption at rest is now genuinely complete for both PHI stores: Postgres ✅ (`/mnt/pgdata-encrypted`) and MinIO ✅ (`/mnt/miniodata-encrypted/data`, 20 GiB LUKS).** ⚠️ **This row claimed exactly that several hours before it was true.** The MinIO migration was declared complete while `miniodata-encrypted.service` had only ever been `enabled`, never *started* — and a mountpoint directory exists whether or not anything is mounted on it, so the bind fell through to `/dev/sda2` and MinIO wrote to the plain root filesystem with every layer reporting success. Re-migrated with a sha256 manifest matched 33/33, made **fail-closed**, and now asserted by a standing check that reads the kernel rather than the config. What remains under this finding is the *managed-volume* migration, not the encryption itself. Runbook §5.7.1 |
| R8 | **MinIO backup regime (encrypted) — define pre-pilot** | medium, open | Postgres has a daily dump with rotation; **MinIO has no backup regime at all.** The one that existed was a plaintext tarball of the object store sitting on the unencrypted root filesystem — a replica contradicting the posture it predated — and it was shredded 2026-07-29 once the migration was sha-proven and the fail-closed guard plus standing check protected the live state. Whatever replaces it must land encrypted and off-host, which folds into R4/R7. **Define before a pilot doctor records anything**, because the first real audio is the point at which "no backup" stops being an acceptable position |
| R7 | **`h16-offsite-backup`** — backups co-located with the database | high, open | *"Single-failure-domain: backups co-located with database."* The daily dump lands on the same host as the Postgres it dumps, so the one event a backup exists for — losing the host — loses both. `infra/backup-offsite-sync.sh` targets Backblaze B2, which is R4's unsigned BAA: **R4 and R7 are the same blocker seen from two directions**, and closing R7 requires closing R4 first |
| R9 | **No fresh end-to-end clinical smoke on a real doctor account** | — | And there will not be one. Production verification is structural by standing policy; the full clinical walk belongs on the QA stack. Named here so the gap is explicit rather than implied |

*(This row was a second `R8` until 2026-07-29 — two different findings carried the
same id, which is how one of them gets closed by a note about the other. It is
`R9` now; nothing else referenced either number.)*

### 🟡 Amber — known, accepted, do not "fix"

| Item | Why it is amber, not red |
|---|---|
| **`NEXT_PUBLIC_REVIEW_DOC_VIEW=false` costs the E/M override** | Recorded constraint (AGENTS.md, runbook §3.2). The gate does NOT weaken — confirm-before-sign and the server-side refusal are flag-independent. One capability is lost. Prefer the image rollback `:pre-emrehome-20260728` when the concern is the E/M surface |
| **AI documentation disclosure — AMBER** | Enabled-with-disclosure, closed 2026-06-12. The doctor-facing paragraph is in §C below and must appear in pilot consent/onboarding |
| **Template Twin is PARKED** | Deliberate. `MAPPINGS_NOT_READY` is a design gate, not a defect — 79 of 80 fields on a real customer form need physician confirmation. Never weaken it to shrink the wall. Trigger to un-park: a pilot doctor explicitly needs their native form bytes back |
| **nginx duplicate `server_name` warnings** | `app.` / `pro.` / `admin.quillmd.com` are each declared twice on `[::]:443`; nginx ignores the duplicate and serves correctly (verified by status code on all five hosts). Cosmetic, but worth tidying before someone edits the wrong block |
| **10 legacy objects carry no SSE-S3 — ACCEPTED 2026-07-29, do not rewrite** | Two encryption layers, and only one of them has a gap. **LUKS covers all ten unconditionally**; SSE-S3 encrypts new PUTs only, so objects predating it stay plaintext *at the object layer* inside an encrypted volume. Verified per-object against live prod, not from a prior report: the **patient-audio bucket has 0 objects**; all ten are in `transcribe-md-template-artifacts` — 5 byte-identical blank PDF canvases (orphans of deleted templates), 2 byte-identical blank twin sources, and **3 filled twin outputs**. The three filled ones are non-PHI **by ownership, not by being blank**: all five twin objects belong to practice `cmrzqiafm0000pd87qtubsj56` = *"QuillMD Smoke Test Practice (synthetic)"*, `smoke-doctor@smoke.quillmd.invalid`. Resolve by practice row, never by trusting a `synthetic_` filename. Not rewritten because a read-then-PUT sweep is a real mutation bought for a second layer over blank forms and synthetic smoke output. **Reverses on exactly one finding: an object with `NONE` owned by a real doctor's practice.** Both buckets now auto-encrypt, so this is a closed tail. Runbook §5.7.3 |

---

## The TLS fix, in full

**The 2026-07-24 audit diagnosed this exactly right.** Quoting it, because a
later reader deserves to know the analysis was not the gap:

> TLS renewal is scheduled and healthy, but `/etc/letsencrypt/renewal-hooks/deploy/`
> is **empty** and `certbot.service` has no `--deploy-hook`, so nginx (a host
> service holding the cert in memory since Jul 22) will never pick up a renewed
> cert. … Fix is a 2-line root script + `certbot renew --dry-run`. **Needs root;
> I have no sudo.** Same gap on `staging.quillmd.com`.

It stayed open for four days because it needed root, not because anyone
misunderstood it. The condensed version that travelled around afterwards — "TLS
expires 2026-09-01, no auto-renew" — is what was imprecise, and it is misleading
in the direction that wastes time: it sends the next person to build a renewal
timer that has been running all along.

The real shape, restated so the short version stops propagating:

`certbot.timer` **is** active and ran 16 hours before this pass; a dry-run renewal
of `quillmd.com` succeeds. Renewal was never broken. Host nginx reads
`/etc/letsencrypt/live/quillmd.com/fullchain.pem` once at start and holds it in
memory, so **a renewed file on disk that nginx never re-reads is not a renewed
certificate** — the site would have begun serving an expired cert on 2026-09-01
while every renewal check reported success.

**Done:** `renewal-hooks/deploy/reload-nginx.sh` runs `nginx -t && systemctl
reload nginx`. Verified by executing the hook for real — a graceful reload, no
downtime — and re-checking all five hosts, which returned identical status codes.
The hook is global, so it also closes the staging gap the audit named.

Two traps for whoever tests this next:

- `certbot renew --dry-run` does **not** execute deploy hooks. Run the hook
  script directly to prove it works.
- Running certbot through the documented root path
  (`docker run --pid=host -v /:/host`) **without `--network host`** fails on DNS
  resolution and looks exactly like a renewal failure. It is not one.

---

## A. Production state

**`main` HEAD:** `4e1ed721` (merge of #442). Deployed image predates it — see §D.

**Containers** — 10, all healthy (42h uptime, except app + worker at 2h):

| Container | Role |
|---|---|
| `meddoc-pro-transcribe-md-1` | the live app |
| `meddoc-pro-transcribe-md-worker-1` | L1–L7e pipeline worker |
| `meddoc-pro-meddoc-pro-1` | legacy app (decommissioned surface) |
| `meddoc-pro-caddy-1` | behind host nginx on `127.0.0.1:8443` |
| `meddoc-pro-postgres-1` | PHI store |
| `meddoc-pro-postgres-backup-1` | daily dump, 7/4/6 rotation |
| `meddoc-pro-gotenberg-1` | DOCX → PDF sidecar |
| `meddoc-pro-marketing-1` | quillmd.com |
| `meddoc-pro-minio-1` | audio + generated-file object store |
| `meddoc-pro-redis-1` | BullMQ broker |

**Ingress:** host nginx owns 80/443. **Never Caddy.**

**Live counts:**

| | |
|---|---|
| users | 195 (**23 have ever logged in** — see R5) |
| practices | 196 |
| transcribe_visits | 24 (16 SIGNED) |
| note_templates | 6 |
| audit_logs | 9,020 |
| imaging visits | 13, **0 carrying office E/M state** |

**Disk:** 296G total / 200G used / 84G free (71%).

**HIPAA findings:** 14 resolved, **2 open, both high** — `h8-h3-pilot-followup` (R6)
and `h16-offsite-backup` (R7). Named, not just counted.

---

## B. What shipped in the 2026-07-28 arc

| PR | What |
|---|---|
| #419 | Review = read-only paper |
| #420 | E/M level rehomed to the gate-stack chip, required reason |
| #439 | Review-doc E2E pack parameterised across specialty classes |
| #440 | Purged 5 pre-fix `emScoredCode` rows from prod; added the standing check |
| #441 | Export imaging guard at the projection layer |
| #442 | Named the Twin certify failure; retired the dead surfaces |
| #443 | Parked Template Twin; re-triaged the Q1 fix-pack |
| #444 | **N1** — a dictated CPT code reaches the note |
| #445 | **§07.1** — L6 polish can see the visit |
| #446 | **§02.9** — ROS polarity as data, not prose |

The Q1 remainder is parked with a written trigger — the pilot roster confirming
the specialty — in `docs/backlog/q1-fixpack-retriage-20260728.md`, which is now
the single source of truth for that backlog.

---

## C. AI documentation disclosure (doctor-facing)

*State AMBER — enabled with disclosure. Product decision recorded in
`docs/qa-reports/hallucination-reconciliation-20260611T072219Z.md`.*

**Give pilot doctors this paragraph verbatim:**

> QuillMD drafts your note from the visit transcript using AI, with a verification
> layer in between: every sentence must quote the transcript it came from, and an
> automated checker verifies each claim against its quote — anything it cannot
> verify is kept OUT of the note and shown to you separately as "Suggested by AI —
> not stated in this visit," for you to add or dismiss explicitly. In our
> pre-registered testing on 30 recorded consultations, this reduced unsupported
> clinical statements from 28 per 30 visits to 2–4 per 30 across test runs; in the
> final test of the configuration running today it was 4 per 30, all low-severity
> wording issues (for example a symptom described as "significant" when the patient
> didn't use that word), not invented medications, doses, or diagnoses. The system
> is designed to surface what it isn't sure of rather than hide it, but it is not
> perfect: every note is a draft until you review and sign it, and adopting a
> suggestion is recorded as your own attestation.

---

## D. Deploy and rollback

Full procedure: `docs/DEPLOYMENT_RUNBOOK.md`. Rollback tags §3.1; the E/M flag
constraint §3.2.

| Tag | Rolls back to |
|---|---|
| `:pre-readonlypaper-20260728` | before the review page became read-only paper |
| `:pre-emrehome-20260728` | before the E/M level returned to the gate stack |

**Never rebuild `:latest` to stage a rollback** — tag a separate image and point
a compose override at it.

`packages/shared` must be in `Dockerfile.worker` — the worker imports
`emAppliesToSpecialty` from it.

---

## E. Guardrails

**≤ 5 doctors for week 1.** One operator, and five is a number one person can
reach individually when something goes wrong.

**Daily checklist:**

1. `docker ps` — all containers healthy
2. `/admin` → audit volume proportional to active doctors
3. `/admin/threats` → Active empty, or every entry investigated within the hour
4. `/admin/usage` → 24h spend within the per-doctor envelope
5. `/admin/hipaa` → no NEW high/critical beyond R6/R7
6. `bash scripts/check-imaging-em-artifacts.sh` → exit 0
7. Newest backup file carries today's date

---

## F. Verdict

**NO-GO on BAAs. Everything else is green or explicitly accepted.**

The code side is ready: four fail-closed gates verified live — one of them with a
production row proving it has actually refused a signature — both standing checks
green, the specialty fixture matrix in CI, 2592 unit tests and a clean typecheck.

What stands between here and a real patient is **R1–R3**, and none of them is an
engineering task. Routing a real doctor's audio through Deepgram, or a real
patient's note through Resend, before those are countersigned is the one thing
this document exists to prevent.

R5 is not pilot-blocking, and as of 2026-07-29 it is **half closed**: the open
signup it described is gone — invite-only shipped 2026-07-28 and is live — so the
surface no longer grows. *"It will only grow"* was true when written and is not
true now. What has **not** changed is the residue: 195 accounts of which 23 have
ever logged in. Closing the door did not empty the room, and those rows still
poison every population query. Carry that into the pilot deliberately or clear
it, but do not read "R5 narrowed" as "R5 handled".

And note the corollary before onboarding day: **signup is currently closed to
everyone**, because no invite code exists in either source. Mint one first.

## Document history

- **Phase 9** (2026-04-26): initial document, GO verdict.
- **Phase 13 / 14** (2026-04-26): non-root containers; E2E residual tracking.
- **2026-07-28**: full rewrite against live production. Prior revision had drifted
  three months. Added the verified four-gate table, both standing checks, the
  red/green pilot table, and the TLS deploy-hook fix. Verdict changed to NO-GO on
  BAAs — not a regression, a correction: the BAAs were unsigned in April too, and
  the April document did not say so.
- **2026-07-29**: two recorded rulings, and one stale row caught. **R5 was
  describing a system that had already changed** — open signup went invite-only
  the day before this row was last touched, so a `high` finding was being carried
  against a surface that no longer existed; narrowed to the waitlist form, `low`,
  with the unchanged residue and the closed-to-everyone corollary called out
  separately. **The 10 legacy no-SSE-S3 objects were accepted**, with the
  ownership evidence that makes "non-PHI" a fact rather than an assumption
  (runbook §5.7.3). Fixed a duplicated `R8` id. *The lesson worth keeping is R5's:
  a readiness row is a claim about a live system, and it goes stale the moment
  the system moves — verify the row before you carry its severity.*
