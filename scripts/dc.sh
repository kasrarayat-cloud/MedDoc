#!/usr/bin/env bash
# ============================================================================
# `docker compose`, REFUSED OUTSIDE THE SHARED TREE.
#   0 = the compose command ran   1 = REFUSED (nothing ran)
#
#   bash scripts/dc.sh ps
#   bash scripts/dc.sh exec -T postgres psql -U meddoc -d meddoc -c '…'
# ----------------------------------------------------------------------------
# WHY THIS IS A SCRIPT AND NOT A SENTENCE IN A RULEBOOK.
#
# `docker-compose.yml` carries RELATIVE bind mounts — `./Caddyfile`,
# `./infra/postgres-backup/postscript.sh`, `./infra/backup-offsite-sync.sh`.
# Run `docker compose` from anywhere else and those resolve against THAT
# directory: `up` re-points the live ingress config at a path that may not
# exist, and reaping the worktree afterwards leaves the bind dangling. The
# running caddy container binds `/opt/meddoc-pro/Caddyfile` by ABSOLUTE path,
# which is the only reason a wrong-directory `up` has not already broken it.
#
# ⚠️ THE HAZARD WAS WRITTEN DOWN AND STILL BIT THREE TIMES IN ONE SESSION —
# each time from a worktree, each time caught only by a stray warning in the
# output ("env file /opt/meddoc-pro/.cdev/.env not found"). Twice it was a
# read-only `exec` and cost nothing; the third would eventually be an `up`.
#
#     A RULE THAT DOES NOT CHANGE WHAT HAPPENS BECOMES MECHANISM.
#
# This is that mechanism, and it is the same move `pre-push` and `merge-pr.sh`
# already made for their own repeatedly-written rules.
#
# ⚠️ FAIL-CLOSED ON CANNOT-TELL. If the shared tree is missing, or the compose
# file is not where it should be, this REFUSES rather than guessing — a broken
# instrument and a correct directory must not produce the same success.
# ============================================================================
set -uo pipefail

SHARED="/opt/meddoc-pro"
COMPOSE="$SHARED/docker-compose.yml"

[ -d "$SHARED" ] || { echo "🔴 dc: $SHARED does not exist. Refusing — cannot tell."; exit 1; }
[ -r "$COMPOSE" ] || { echo "🔴 dc: $COMPOSE missing or unreadable. Refusing — cannot tell."; exit 1; }

HERE="$(pwd -P)"
if [ "$HERE" != "$SHARED" ]; then
  echo "⚠️  dc: cwd is $HERE, not the shared tree."
  echo "   Relative bind mounts in docker-compose.yml would resolve against the"
  echo "   WRONG directory. Running from $SHARED instead."
fi

# ⚠️ BOTH: cd AND an explicit -f. The cd fixes the relative binds; the -f means
# a future cwd change cannot silently pick up a different compose file. Belt and
# braces, because this hazard has already survived being written down.
cd "$SHARED" || { echo "🔴 dc: cannot cd to $SHARED. Refusing."; exit 1; }
exec docker compose -f "$COMPOSE" "$@"
