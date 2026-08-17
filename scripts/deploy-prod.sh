#!/usr/bin/env bash
# ============================================================================
# Rolling deploy of the transcribe-md app + worker to production.
# ----------------------------------------------------------------------------
# This exists because the runbook's prose version failed silently on 2026-07-28.
# The three things it encodes, each bought with a real incident:
#
#   1. db-migrate is ALWAYS rebuilt, alongside the app services.
#      `docker compose run --rm db-migrate` runs whatever image was last built.
#      A deploy that rebuilt only the app services ran migrate from a stale
#      image, which printed "79 migrations found / No pending migrations to
#      apply" and exited 0 — while the repo had eighty. Nothing was applied and
#      nothing said so.
#
#   2. The migration state is ASSERTED after migrating, not assumed.
#      Rebuilding is a step someone can forget. The assertion cannot be
#      forgotten, because it aborts the deploy. It compares the repo against
#      the database and knows nothing about how migrate was invoked.
#
#   3. The full log is written to a FILE, never piped through `tail`.
#      The first attempt was run as `deploy.sh | tail -50`, which discarded the
#      backup and migration output — the two lines that would have shown the
#      no-op. The record of a deploy must outlive the terminal.
#
# Ingress note: host nginx owns 80/443. Nothing here touches Caddy or nginx.
#
# ⚠️ 4. THE TREE THIS RUNS IN IS A DEPLOY SURFACE, NOT A WORKSPACE.
#      This script deploys `git rev-parse HEAD` OF THE TREE IT RUNS IN, and
#      names its §2.5 declaration after that SHA. Run it from a checkout parked
#      on somebody's feature branch and it ships THAT branch, under a
#      declaration naming the wrong commit — which is worse than no declaration,
#      because it looks like evidence.
#
#      ⚠️ AND YOU CANNOT SIDESTEP IT BY DEPLOYING FROM A WORKTREE. The prod
#      compose carries RELATIVE bind mounts — `./Caddyfile`,
#      `./infra/postgres-backup/postscript.sh`,
#      `./infra/backup-offsite-sync.sh` — so `docker compose up` from another
#      directory re-points the INGRESS CONFIG BIND at that directory. Reap the
#      worktree afterwards and the bind dangles. Verified 2026-08-14: the live
#      caddy container binds `/opt/meddoc-pro/Caddyfile` by absolute path.
#
#      So: `/opt/meddoc-pro` stays on `main` and clean. ALL feature work happens
#      in an isolated `git worktree`. Two sessions sharing one working tree is a
#      CLASS, not an incident — it produced two near-misses on 2026-08-14 in a
#      single night, and both resolved only because somebody happened to look.
#
# Usage:  bash scripts/deploy-prod.sh [--skip-backup]
# Exit:   0 = deployed · non-zero = aborted (nothing recreated)
# ============================================================================
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="docs/deploy-logs"
mkdir -p "$LOG_DIR" backups
LOG="$LOG_DIR/deploy-$TS.log"

# Everything from here is teed to the log. `tee` (not a pipe into tail) so the
# operator still sees it live AND the record survives.
exec > >(tee -a "$LOG") 2>&1

echo "=== deploy $TS ==="
echo "commit: $(git log --oneline -1)"
echo "branch: $(git branch --show-current)"
echo "log:    $LOG"
echo

# ============================================================================
# STEP 0 — THE DECLARATION GATE. §2.5, ENFORCED.
# ----------------------------------------------------------------------------
# ⚠️ A STATED INVARIANT IS A WISH UNTIL SOMETHING ASSERTS IT, and §2.5 was a
# wish: "declare the expected delta before the deploy runs" lived in the runbook
# and in a human's discipline. That was survivable while a person typed this
# command. It is not survivable now that an unattended loop can.
#
# So the deploy REFUSES without a declaration for THIS commit, and prints it into
# the transcript. The point is not the file — it is the ORDER. A post-deploy
# check written afterwards is unfalsifiable: every number has a story available
# to it, and a migration supplies a ready-made excuse for any movement ("the
# migration touched that table"). A declaration that exists BEFORE the evidence
# has exactly one correct answer.
#
# The post-deploy comparison reads THE SAME FILE, so the thing being judged
# against cannot be rewritten to fit what happened.
#
# Convention:  docs/foundation/deploys/<UTC-date>-<short-sha>.md
# ============================================================================
DEPLOY_SHA="$(git rev-parse --short HEAD)"
DECL_DIR="docs/foundation/deploys"

# ⚠️ THE GATE IS SOURCED, NOT CARRIED. `scripts/lib/declaration.sh` is shared
# with `scripts/run-ruled-mutation.sh`; a second copy would drift from the first.
# Its absence is fail-closed — a deploy that silently skipped its own gate is
# worse than one that refuses.
DECL_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" 2>/dev/null && pwd)/declaration.sh"
if [ ! -r "$DECL_LIB" ]; then
  echo "🔴 REFUSING TO DEPLOY — $DECL_LIB is missing or unreadable."
  echo "   Production is untouched."
  exit 1
fi
# shellcheck source=lib/declaration.sh
. "$DECL_LIB"

# ⚠️ THE PATH IS RESOLVED, NOT DERIVED — F10, ruling #121. It used to be
# `$DECL_DIR/$(date -u +%Y%m%d)-${DEPLOY_SHA}.md`, which bound the declaration's
# NAME to the deploying tree's HEAD. `main` moves between a feature merge and its
# deploy in this programme's normal cadence, and the commit that would CARRY the
# declaration is itself what moves HEAD — so the naming had no fixed point.
# `declaration_resolve` takes the exact match when it exists and otherwise
# accepts an ANCESTOR whose runtime diff to HEAD is provably empty. Full
# reasoning, and why this satisfies #121's three criteria, is in the library.
declaration_resolve "$DECL_DIR" || {
  echo "   Nothing has been built, migrated or recreated. Production is untouched."
  exit 1
}
DECL="$DECLARATION_PATH"

# ⚠️ MODE IS `present` ON THE EXACT MATCH, AND THAT ASYMMETRY IS DELIBERATE. A
# ruled MUTATION must have its declaration COMMITTED before it runs, because
# nothing can undo an append-only row and the commit timestamp is the only
# durable proof of order. A deploy is answerable by a rollback, and requiring a
# commit here would refuse every deploy whose author lands the declaration in the
# same PR — a real habit. So the deploy records provenance loudly and does not
# refuse on it. Strictness proportional to reversibility; ruling #96(b)'s logic.
#
# ⚠️ A CARRY-FORWARD IS RESOLVED AT `strict`, WHICH IS STRICTLY STRONGER. #121's
# criterion (1) says the gate must not weaken; this is the direction it moves.
declaration_gate "$DECL" "$DECLARATION_MODE" "deploy declaration" || {
  echo "   Nothing has been built, migrated or recreated. Production is untouched."
  exit 1
}

# ============================================================================
# STEP 0b — THE ROLLBACK TAG. F9, AND IT IS FAIL-CLOSED.
# ----------------------------------------------------------------------------
# ⚠️ THE SAME ARGUMENT AS STEP 0, ONE STEP LATER. Runbook §3.1 has said since
# 2026-08-02 that tagging the outgoing images is a MANUAL pre-step, and that
# forgetting it leaves nothing to roll back to. It was forgotten TWICE on
# 2026-08-16 — F3 at 04:02Z and F4 at 11:35Z — the second time by a session that
# then asserted in its own §2.5 declaration that the tags HAD been cut. Both
# images were recovered by hand from dangling images; the ~8h window in which a
# rollback would have needed a REBUILD is the cost that was actually paid.
#
# A PRE-STEP THAT LIVES ONLY IN PROSE IS A PRE-STEP THAT GETS SKIPPED. So it is
# mechanism now, and it runs BEFORE the backup — nothing has been built,
# migrated or recreated when it refuses.
#
# The runbook's manual block is now the FALLBACK, not the mechanism.
# ============================================================================
TAG_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" 2>/dev/null && pwd)/rollback-tag.sh"
if [ ! -r "$TAG_LIB" ]; then
  echo "🔴 REFUSING TO DEPLOY — $TAG_LIB is missing or unreadable."
  echo "   A deploy that silently skipped its own rollback tag is exactly the"
  echo "   state F9 exists to make impossible. Production is untouched."
  exit 1
fi
# shellcheck source=lib/rollback-tag.sh
. "$TAG_LIB"

ROLLBACK_SLUG="$(rollback_tag_slug "$DECL" "$DEPLOY_SHA")"
rollback_tag_cut "$ROLLBACK_SLUG" "$(date -u +%Y%m%d)" \
  transcribe-md transcribe-md-worker gotenberg || {
  echo "   Nothing has been built, migrated or recreated. Production is untouched."
  exit 1
}

if [ "${1:-}" != "--skip-backup" ]; then
  echo "=== 1. pre-deploy backup ==="
  BACKUP="backups/pre_deploy_${TS}.sql.gz"
  docker compose exec -T postgres pg_dump -U meddoc -d meddoc --no-owner --no-acl | gzip > "$BACKUP"
  ls -lh "$BACKUP"
  echo
fi

echo "=== 2. build db-migrate (UNCONDITIONAL — see the header) ==="
docker compose build db-migrate
echo

echo "=== 3. apply migrations ==="
docker compose run --rm db-migrate
echo

echo "=== 4. ASSERT the migrations actually landed ==="
# The backstop. A stale-image no-op exits 0 with a reassuring message, so the
# exit code of step 3 proves nothing on its own.
if ! bash scripts/assert-migrations-applied.sh; then
  echo
  echo "🔴 ABORTING THE DEPLOY — the database is not where the repo says it should be."
  echo "   Nothing has been rebuilt or recreated; production is untouched."
  exit 1
fi
echo

echo "=== 5. build app + worker (sequential — this VPS cannot parallel-build) ==="
docker compose build transcribe-md-worker
docker compose build transcribe-md
echo

# C2-b: gotenberg is a BUILD service now, not a stock tag. It carries the fonts
# the PDF export embeds, and the on-screen preview is its render of the DOCX —
# without them LibreOffice substitutes Noto Serif and the preview shows a
# different typeface from the downloaded file.
#
# ⚠️ IT MUST BE BUILT **AND RECREATED** HERE. Step 6 only ups the app and the
# worker, so a gotenberg still running the old stock image would keep rendering
# substituted type after a deploy that "succeeded" — the same shape as the
# stale `db-migrate` this script already guards against: a service left behind
# by a deploy that never names it.
echo "=== 5b. build + recreate the converter (fonts live in this image) ==="
docker compose build gotenberg
docker compose up -d gotenberg
echo

echo "=== 6. recreate ==="
docker compose up -d transcribe-md transcribe-md-worker
echo

echo "=== 7. settle, then health ==="
sleep 30
docker compose ps --format '{{.Service}}\t{{.State}}\t{{.Status}}' | grep -E 'transcribe-md|gotenberg'
echo "app /api/health: $(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://app.quillmd.com/api/health)"
echo
echo "=== 8. JUDGE AGAINST THE DECLARATION ==="
# ⚠️ THE SAME FILE, RE-READ. Not a fresh summary written now — the document that
# existed before any of this happened. A difference that is not in it is THE
# FINDING, whatever its explanation sounds like after the fact.
echo "declaration: $DECL"
echo "─────────────────────────────────────────────────────────────────────"
cat "$DECL"
echo "─────────────────────────────────────────────────────────────────────"
echo "⚠️ Compare the post-deploy state above against THIS declaration."
echo "   A movement it does not name is a finding, not an explanation."
echo

echo "=== deploy complete — full log at $LOG ==="
