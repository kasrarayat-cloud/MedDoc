#!/usr/bin/env bash
# ============================================================================
# Assert that every migration in the repo is actually applied to the database.
# ----------------------------------------------------------------------------
# WHY THIS EXISTS — 2026-07-28. A deploy ran `docker compose run --rm db-migrate`,
# which exited 0 and printed:
#
#     79 migrations found in prisma/migrations
#     No pending migrations to apply.
#
# The repo had EIGHTY. `db-migrate` builds from the app Dockerfile, and that
# deploy rebuilt `transcribe-md` and `transcribe-md-worker` but not `db-migrate`
# — so it ran from an image that physically did not contain the new migration
# directory. A clean exit code, a reassuring message, and nothing done.
#
# The rebuild is now unconditional (see deploy-prod.sh), but a procedure that
# depends on remembering a step is a procedure that will be forgotten. This is
# the backstop that FAILS instead: it compares what the repo has against what the
# database actually recorded, and knows nothing about how migrate was invoked.
#
# WHAT COUNTS AS A MIGRATION: a directory containing `migration.sql`. NOT a
# name pattern. The first version of this script matched `^[0-9]{14}_` and so
# silently skipped `0000_init` — a real migration directory with a short,
# non-conforming name — then reported it as an unexplained extra row in the
# database. A guard that quietly ignores part of what it is guarding is worse
# than no guard, because it reads as coverage.
#
# THE ASSERTION IS DIRECTIONAL, and that is deliberate. It asserts that every
# migration in the repo IS applied. It does NOT assert count equality: an extra
# applied row is a since-removed or renamed migration, which is reported for
# information. A repo migration that is NOT applied is the actual defect, and it
# is the only thing that fails this script.
#
# READ-ONLY. Never mutates anything.
#
# Usage:  bash scripts/assert-migrations-applied.sh [container] [db]
# Exit:   0 = all repo migrations applied · 1 = SOME UNAPPLIED · 2 = cannot check
#
# Invoke with `bash scripts/...` — this repo sets core.fileMode=false, so the
# executable bit is not tracked and `./scripts/...` gives "Permission denied".
# ============================================================================
set -uo pipefail

CONTAINER="${1:-meddoc-pro-postgres-1}"
DB="${2:-meddoc}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRATIONS_DIR="$REPO_DIR/packages/db/prisma/migrations"

if [ ! -d "$MIGRATIONS_DIR" ]; then
  echo "⚠️  cannot check — $MIGRATIONS_DIR not found (wrong host?)"
  exit 2
fi
if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "⚠️  cannot check — container '$CONTAINER' not present (off-host?)"
  exit 2
fi

# A migration is a directory holding a migration.sql. Name-agnostic on purpose
# — see the header for the bug that taught this.
repo_migrations() {
  find "$MIGRATIONS_DIR" -mindepth 2 -maxdepth 2 -name 'migration.sql' -printf '%h\n' 2>/dev/null \
    | xargs -r -n1 basename | sort
}

# Only rows that genuinely landed: a started-but-unfinished or rolled-back row is
# NOT an applied migration, and counting it would hide exactly the failure this
# script exists to catch.
applied_migrations() {
  docker exec -i "$CONTAINER" psql -U meddoc -d "$DB" -t -A -c \
    "SELECT migration_name FROM _prisma_migrations WHERE finished_at IS NOT NULL AND rolled_back_at IS NULL;" 2>/dev/null \
    | sed 's/[[:space:]]*$//' | grep -v '^$' | sort
}

APPLIED_RAW="$(applied_migrations)"
if [ -z "$APPLIED_RAW" ]; then
  echo "⚠️  cannot check — no answer from $CONTAINER/$DB"
  exit 2
fi

REPO_COUNT=$(repo_migrations | wc -l | tr -d '[:space:]')
APPLIED_COUNT=$(printf '%s\n' "$APPLIED_RAW" | wc -l | tr -d '[:space:]')
UNAPPLIED="$(comm -23 <(repo_migrations) <(printf '%s\n' "$APPLIED_RAW"))"
EXTRA="$(comm -13 <(repo_migrations) <(printf '%s\n' "$APPLIED_RAW"))"

if [ -n "$EXTRA" ]; then
  echo "ℹ️  applied but not in the repo (baseline or since-removed) — not a failure:"
  printf '%s\n' "$EXTRA" | sed 's/^/     /'
fi

if [ -z "$UNAPPLIED" ]; then
  echo "🟢 every repo migration is applied — $REPO_COUNT in repo, $APPLIED_COUNT rows recorded"
  exit 0
fi

echo "🔴 UNAPPLIED MIGRATIONS — $(printf '%s\n' "$UNAPPLIED" | wc -l | tr -d '[:space:]') in the repo never reached the database:"
printf '%s\n' "$UNAPPLIED" | sed 's/^/     /'
echo
echo "Most likely cause: db-migrate ran from a STALE IMAGE that predates them."
echo "'No pending migrations to apply' from a stale image is indistinguishable"
echo "from success. Rebuild it and re-run:"
echo "    docker compose build db-migrate && docker compose run --rm db-migrate"
exit 1
