# §2.5 DECLARATION — ruling #307, the `meddoc-pro` compose service is removed

**Written and committed BEFORE the act.** Branch
`fix/307-retire-meddoc-pro-service`. **Config only — no migration, no code.**

## WHAT MUST CHANGE

| # | quantity | before | after |
|---|---|---|---|
| 1 | services in `docker-compose.yml` | **11** | **10** |
| 2 | `meddoc-pro` service defined | yes | **no** |
| 3 | `caddy.depends_on` | `[meddoc-pro, marketing, transcribe-md]` | `[marketing, transcribe-md]` |

## WHAT MUST **NOT** CHANGE — and row 4 is the one that matters

| # | quantity | expected |
|---|---|---|
| 4 | **`pro.quillmd.com`** | **still 410** ⚠️ |
| 5 | `quillmd.com` / `www` | 200 / 200 |
| 6 | `app.quillmd.com` | 307 |
| 7 | `admin.quillmd.com` | 404 |
| 8 | running containers | **9 healthy** — the meddoc-pro container is already `Exited (143)`, so nothing stops |
| 9 | `apps/meddoc-pro/` in git | **unchanged** — this deletes NO code |
| 10 | visits, patients, signatures, ledger rows | **unchanged** |

**Baseline captured before the act** (`scripts/check-cotenants.sh`, exit 0):

    quillmd.com 200 · www 200 · app 307 · admin 404 · pro 410
    — 4 distinct codes, so the probe discriminates

⚠️ **A CHANGE AWAY FROM 410 IS THE FINDING, NOT THE 410 ITSELF** — #265(d).
`check-cotenants.sh` is the expectation table; this declaration does not restate
it, it cites it.

## WHY

The container has been down five weeks and the host answers 410 — but the
service stayed **defined**, one `docker compose up` from reviving **four
unlocked `users` writers** whose missing practice lock was measured to deadlock
the locked doors, the locked side losing and its write silently gone.

> *"Nobody starts it"* and *"nobody CAN start it"* are different properties.

## WHAT THIS DOES NOT DO

**It deletes no code.** `apps/meddoc-pro/` is untouched. DELETE-MEDDOC-PRO
removes it, and only after the console port lands — that app holds **the only
worked provisioning design in the repository** (the recon) and **one of B7's
three ruled promo doors**, the reactivation grant (DMP-c). The four unlocked
doors stay **pinned** by `gate-289-derived-door-list` until then.

## ROLLBACK

`git revert` this commit and `docker compose up -d meddoc-pro`. The image and the
app both still exist. Nothing is destroyed by this change.

## WHAT WOULD MAKE ME SAY THIS FAILED

- `pro.quillmd.com` answering anything other than **410**
- any of rows 5–8 moving
- a file under `apps/meddoc-pro/` changing
