# §2.5 ROWS — production Postgres stops being published to the host (#281)

**Declared BEFORE the act, per §2.5.** This is a compose change: it alters what
the host can reach, and nothing about the image, the schema, or any row.

## MUST CHANGE

| # | claim | how it is checked |
|---|---|---|
| **C1** | `docker-compose.yml` publishes **no** host port for `postgres` | `gate-prod-postgres-unpublished` parses compose: `services.postgres.ports` is `[]`, and no service maps `5432` by any route |
| **C2** | after the deploy, the host cannot open a TCP connection to `127.0.0.1:5432` | on the host: `timeout 3 bash -c '</dev/tcp/127.0.0.1/5432' ; echo $?` → **non-zero** (it is **0** today) |
| **C3** | the container still serves the app | `docker exec meddoc-pro-postgres-1 pg_isready -U meddoc` → `accepting connections` |

## MUST NOT CHANGE

| # | claim |
|---|---|
| **N1** | **every clinical count.** Visits, patients, signatures, audit rows: identical before and after. This publishes nothing and migrates nothing — a moved count here would mean something nobody asked for |
| **N2** | `deploy-prod.sh` still reads applied migrations. It uses `docker exec meddoc-pro-postgres-1 psql`, which does not traverse the host port |
| **N3** | the nightly backup still runs. `docker compose exec -T postgres pg_dump` — same door |
| **N4** | **`restore-drill.sh` is unaffected.** It binds a host port for its OWN throwaway container, on **5433** |
| **N5** | CI is unaffected. `localhost:5432` in `test.yml` / `a11y.yml` is a GitHub **service container**, not this compose file |
| **N6** | MinIO and Redis keep publishing — `127.0.0.1:9000/9001` and `127.0.0.1:6379`. #281 orders their audit **after** this, and the gate pins the current state so the follow-up is a visible change |

## Why this is a deletion and not a trade

⚠️ **The port bought nothing.** Audited before removal: every host-side consumer
already goes through `docker exec` — `deploy-prod.sh`, `assert-migrations-applied`,
the `check-*` family, `annotate-backfill`, the artifact scanners. One script binds
a host port and it is its own temporary container.

⚠️ **And the comment on the line was true while not being a control.** *"only
accessible from localhost"* — every process on this box is localhost. A diagnostic
probe written against the **QA** database reached **PRODUCTION** through it, and was
stopped by wrong credentials rather than by design.

## The rollback

Restore the two lines under `postgres:`:

```yaml
    ports:
      - "127.0.0.1:5432:5432"
```

then `docker compose up -d postgres`. ⚠️ It re-opens the accident class, so it is
a **loosening** and not a neutral revert — say so if you do it.
