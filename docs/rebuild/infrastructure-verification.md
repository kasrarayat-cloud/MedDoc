# Fresh infrastructure verification — 2026-09-17

Prepared in the fresh worktree; no live Caddy reload or compose recreation was
performed by this agent.

- Root compose has exactly five services: PostgreSQL, Redis, MinIO, Caddy and
  marketing. A parsed comparison against the prior committed compose confirms
  each retained service is identical except Caddy's removal of the two old app
  dependencies. Volume and network declarations compare equal.
- `docker compose --env-file /dev/null -f docker-compose.yml config --quiet`
  passes. Its expected missing-KMS warning comes from deliberately avoiding
  loading the production secret file during syntax validation.
- The actual installed Caddy adapter accepts the prepared worktree config.
  Its resulting JSON includes `marketing:3010` and no old application upstream.
  Marketing's host block, global trust configuration and TLS remain preserved.
  App/admin maintenance returns 503; retired pro returns 410.
- Fourteen old QA compose files and old app E2E/accessibility/nightly workflows
  are removed. Fresh CI defines separate `Fresh application tests` and
  `Marketing build` jobs. Existing `secrets-scan.yml` remains unchanged.
- `bash -n scripts/ci/verify-fresh.sh`, workflow YAML parsing, and
  `git diff --check` pass. An unknown gate name returns failure (exit 2).
- Marketing build already passed after workspace cleanup. The added production
  dependency audit reports **zero vulnerabilities**.
- Python lockfile dependency audit reports **no known vulnerabilities**.
- The full new Django suite is owned/run by the lead while it completes the
  fresh application. This report does not claim a successful CI run or a
  completed browser accessibility/E2E suite.

This supersedes the preparation report's observation that root compose/CI still
reference the old application. GitHub branch protection still requires a
separate deliberate update to the new real check names; no GitHub settings
were changed by this agent.
