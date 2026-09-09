# §2.5 DECLARATION — ruling #307, the `meddoc-pro` compose service is removed

**Written and committed BEFORE the act.** Branch
`fix/307-retire-meddoc-pro-service`. **Config only — no migration, no code.**

> ⚠️ **REVISED 2026-09-09 AFTER AN ADVERSARIAL PASS UPHELD SIX FINDINGS AGAINST
> THE FIRST DRAFT.** The first draft claimed *"nobody CAN start it"* and
> nominated a row that **cannot move in response to this change** as the one
> that matters. Both are corrected below, and the superseded wording is quoted
> rather than quietly replaced — the correction is the point.

## WHAT MUST CHANGE

| # | quantity | before | after |
|---|---|---|---|
| 1 | services in `docker-compose.yml` | **11** | **10** |
| 2 | `meddoc-pro` service defined | yes | **no** |
| 3 | `caddy.depends_on` | `[meddoc-pro, marketing, transcribe-md]` | `[marketing, transcribe-md]` |
| 4 | `Caddyfile` `pro.quillmd.com` handler | `reverse_proxy meddoc-pro:3000` | **`respond … 410`** |
| 5 | `apps/meddoc-pro` `dev`/`build`/`start` scripts | run the CRM | **refuse, exit 1** |

⚠️ **ROW 4 CHANGES THE DEPLOY'S SHAPE AND IS CALLED OUT HERE FOR THAT REASON.**
`Caddyfile` is a bind mount, so this is no longer a compose-file-only change:
**`caddy` must be recreated (or reloaded) for row 4 to take effect**, and rows
9–11 below are what says whether that went well.

## WHAT MUST **NOT** CHANGE

| # | quantity | expected | can this row detect a revived CRM? |
|---|---|---|---|
| 6 | **`meddoc-pro-meddoc-pro-1` `State.Status`** | **still `exited`** | ⚠️ **YES — THIS IS THE ROW THAT MATTERS** |
| 7 | running containers in project `meddoc-pro` | **9 healthy** | **yes** — a started CRM makes it 10 |
| 8 | `pro.quillmd.com` | still 410 | ⚠️ **NO — see below** |
| 9 | `quillmd.com` / `www` | 200 / 200 | no (but detects a broken `caddy` recreate) |
| 10 | `app.quillmd.com` | 307 | no (same) |
| 11 | `admin.quillmd.com` | 404 | no (same) |
| 12 | `apps/meddoc-pro/` in git | source **unchanged** apart from row 5 | no |
| 13 | visits, patients, signatures, ledger rows | **unchanged** | no |

⚠️ **ROW 8 IS A HOST-NGINX INVARIANT AND IS **NOT** A DETECTOR FOR THIS CHANGE —
THE FIRST DRAFT SAID IT WAS.** It read *"WHAT MUST NOT CHANGE — and row 4 is the
one that matters"*, and listed the 410 first under what would make this look
failed. **Measured, and this is why that was wrong:**

- `https://pro.quillmd.com/` → `HTTP/2 410`, `server: nginx/1.24.0 (Ubuntu)`;
- `/etc/nginx/sites-available/quillmd:82-97` is a dedicated
  `server { server_name pro.quillmd.com; location / { return 410 …; } }` with
  **no `proxy_pass`** — nothing behind nginx is consulted for this hostname;
- Caddy's own answer for that SNI, probed directly at `127.0.0.1:8443`, was
  **502** — i.e. the 502 the row warns about already existed *behind* a green row.

So the 410 is **unconditional and upstream-independent**: it reads the same
whether the container is exited, running, defined in compose or absent from it.
`docker start meddoc-pro-meddoc-pro-1` would leave row 8 **green** while the
retired CRM served on `127.0.0.1:3001` and wrote to the production clinical
database. **A row that is green by construction cannot be the discriminating
evidence, and calling it that is worse than omitting it** — it buys confidence
the measurement never earned.

Row 8 stays in the table because it is a real watch on a **different** layer:
it fires if the nginx 410 block is tidied away and the hostname falls through to
a co-tenant (`sites-enabled/dealhunter` declares `server_name 5.231.107.93 _;`
and sorts first in the glob). That is an ingress event, not a container event.

⚠️ **AND `scripts/check-cotenants.sh` INHERITED THE SAME MISATTRIBUTION** — its
reason field said *"Caddy answers Gone"*, which was false: nginx answered Gone
and Caddy answered 502. That string is corrected in this change, and row 4 above
now makes it true of the tree as well as of the edge.

**Baseline captured before the act** (`scripts/check-cotenants.sh`, exit 0):

    quillmd.com 200 · www 200 · app 307 · admin 404 · pro 410
    — 4 distinct codes, so the probe discriminates

## WHY

The container has been down five weeks and the host answers 410 — but the
service stayed **defined**, one `docker compose up` from reviving **four
unlocked `users` writers** whose missing practice lock was measured to deadlock
the locked doors, the locked side losing and its write silently gone.

> *"Nobody starts it"* and *"nobody CAN start it"* are different properties.

## ⚠️ WHAT THIS DOES **NOT** CLOSE — the residual doors, named

**THE FIRST DRAFT'S COMPOSE COMMENT SAID *"This removes the second gap."* IT DOES
NOT.** It removes one verb. These doors survive it, all measured:

| # | door | why the removal does not reach it | closing it needs |
|---|---|---|---|
| a | **`docker start meddoc-pro-meddoc-pro-1`** | `docker start` is a daemon API call against config persisted at CREATE time. **It reads no compose file.** The container object is `Exited (143)`, `Dead=false`, `RestartPolicy=unless-stopped`; its image `sha256:5ed8f372…` is present; its network alias `meddoc-pro` on `meddoc-pro_default` is intact; `127.0.0.1:3001` is free; and its baked `DATABASE_URL` password is **sha-identical to the live app's**, so it authenticates against the production clinical database. | **`docker rm meddoc-pro-meddoc-pro-1`** — an irreversible production deletion. ⚠️ **NOT PERFORMED HERE.** See OWNER QUESTIONS. |
| b | `apps/meddoc-pro/.next/standalone/apps/meddoc-pro/server.js` | a build artifact on disk under a gitignored path. A verifier **booted it** — 200 on `/`, and `/api/health` ran a real Prisma query — with no compose service, no image and no container. | deleting `apps/meddoc-pro/.next/` on the host (reversible by rebuild, but the shared tree is a deploy surface). ⚠️ **NOT PERFORMED HERE.** |
| c | `npm run start\|dev\|build -w meddoc-pro` | the repo's own scripts start the identical app, resolving `apps/meddoc-pro/.env` → the root `.env` for its DSN. | **CLOSED by row 5 of this change.** The refusal has one reader (the workspace `package.json`); the root scripts inherit it by delegation — measured `exit 1` from both spellings. |

⚠️ **AND THE HARNESS'S OWN GUARD RAILS HAVE THE SAME SHAPE AS THE DEFECT.**
`.claude/settings.json` denies twelve **compose** verbs (`up`, `run`, `down`,
`stop`, `rm`, `restart`, `build`, `exec`, …) and denies **neither `docker start`
nor `docker restart`**. The pre-existing guard and the first draft of this
change both watch the compose surface; the container surface is watched by
neither. That is an owner question, not something a session may edit.

## WHAT THIS DOES NOT DO

**It deletes no code.** `apps/meddoc-pro/` is untouched apart from row 5's three
script values. DELETE-MEDDOC-PRO removes it, and only after the console port
lands — that app holds **the only worked provisioning design in the repository**
(the recon) and **one of B7's three ruled promo doors**, the reactivation grant
(DMP-c). The four unlocked doors stay **pinned** by `gate-289-derived-door-list`
until then.

## ⚠️ ACCEPTED CAPABILITY LOSS — AGENTS.md class (b), for the owner to confirm

Row 5 closes `npm run build -w meddoc-pro`, and `apps/meddoc-pro/Dockerfile:60`
runs exactly that. **So the CRM image can no longer be rebuilt from source
without reverting this change.** The existing image
(`meddoc-pro-meddoc-pro:latest`) is untouched and the rollback below still
works, because reverting restores the build script and the service together.
This is a deliberate trade — reading and porting the code is unaffected, only
running it is refused — and it is recorded here rather than left to be
discovered.

## ROLLBACK

⚠️ **THREE REVERSALS, IN ORDER, NOT ONE.** The first draft said *"`git revert`
this commit and `docker compose up -d meddoc-pro`"*, which was true of the
service alone and is no longer the whole story:

1. **Revert the #307 change IN FULL** (it spans several commits: the compose
   service, the `Caddyfile` block and the run scripts). This restores the
   service definition, the `reverse_proxy`, and `npm run build -w meddoc-pro`.
2. Bring the service up by name and confirm healthy.
3. Recreate `caddy` so it picks the restored upstream back up.

The image and the app both still exist, and **no data is destroyed by this
change.** What IS lost until a revert is the ability to build the image from
source — see the capability-loss section above.

`docs/DEPLOYMENT_RUNBOOK.md` §3.5 carries the ordered restore procedure for the
hostname, including the step that must come **last**: the host-nginx 410 block.

## WHAT WOULD MAKE ME SAY THIS FAILED

- `meddoc-pro-meddoc-pro-1` reading anything but `exited` (**row 6 — the one
  that matters**)
- the project's running-container count moving off 9 (row 7)
- any of rows 9–11 moving — which after this change means the `caddy` recreate
  went wrong, since row 4 edits a file `caddy` bind-mounts
- a file under `apps/meddoc-pro/` changing beyond row 5's three script values
- row 13 moving at all

⚠️ **NOT ON THIS LIST, DELIBERATELY: `pro.quillmd.com` answering 410.** It will,
whatever happens here. Listing it would be listing a guaranteed pass as evidence.

## OWNER QUESTIONS

1. **May `meddoc-pro-meddoc-pro-1` be removed?** It is the cheapest surviving
   door (door **a**) and closing it is an irreversible production deletion, so
   it needs `scripts/run-ruled-mutation.sh` with its own committed declaration.
   **This change does not perform it.**
2. **May `docker start` / `docker restart` / `docker create` be added to the
   `.claude/settings.json` deny list?** That file governs the layer a session
   runs in and is not a session's to edit.
3. **`/etc/nginx/sites-enabled/quillmd:79-81` still documents the OLD restore
   order** and names a `--profile retired` invocation for a profile that has
   never existed in this compose file. Correcting it is a production act on host
   config and is **not performed here.**
4. **Confirm the capability loss above** (the CRM image can no longer be rebuilt
   without a revert).
