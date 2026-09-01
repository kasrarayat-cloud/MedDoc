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

# ⚠️ A CALLER'S OWN `-f` WINS, AND THAT IS NOT A HOLE — IT IS THE QA STACK.
# `docker-compose.qa.yml` is a real, sanctioned target (project `meddoc-qa`,
# 127.0.0.1:9020, synthetic DB). Hardcoding the prod file would make QA
# unreachable through the only granted door, which is how a guard gets bypassed
# rather than obeyed. The cd still happens either way, so the relative binds
# resolve against the shared tree whichever compose file is chosen — the hazard
# this script exists for is closed in BOTH cases.
# ── WHICH STACK IS BEING ADDRESSED, AND WHAT MAY BE DONE TO IT ──────────────
#
# ⚠️ THIS SECTION EXISTS BECAUSE THE FIRST VERSION OF THIS SCRIPT RE-OPENED
# EVERY DENY IT WAS SUPPOSED TO SIT BESIDE, AND AN ADVERSARIAL PASS FOUND IT.
#
# `.claude/settings.json` DENIES `docker compose down|stop|rm|exec|up|run|
# build|restart` — its own comment calls the first two load-bearing: "the prod
# stack, and co-tenants". This script is granted as `bash scripts/dc.sh:*`,
# which no deny pattern matches, and it forwarded ANY argv straight through.
# So `bash scripts/dc.sh down` would have stopped production and its co-tenants
# through a granted command — an act that was REFUSED before this script
# existed. The wrapper presented as a narrowing and was a widening.
#
#     A DENY MATCHES THE AGENT, NOT THE SCRIPT — so a wrapper that bypasses a
#     guard must RE-IMPLEMENT it, not merely be careful about something else.
#     `merge-pr.sh` re-implements the in-flight check it bypasses. This script
#     implemented a DIRECTORY guard and silently opened a SUBCOMMAND one.
#
# THE RULE: against the PRODUCTION compose file, this wrapper is at least as
# strict as the deny list — plus `kill`, which is `stop` under another name and
# which the deny list does not enumerate. The QA stack (`-f docker-compose.qa.yml`,
# project `meddoc-qa`, synthetic DB) stays fully usable, because that is the
# whole reason the wrapper takes a subcommand at all.
REFUSED_ON_PROD="down stop kill rm exec up run build restart"

# The target: the caller's own -f wins, exactly as before.
TARGET="$COMPOSE"
CALLER_FILE=""
prev=""
for arg in "$@"; do
  case "$prev" in
    -f|--file) CALLER_FILE="$arg" ;;
  esac
  case "$arg" in
    --file=*) CALLER_FILE="${arg#--file=}" ;;
  esac
  prev="$arg"
done
[ -n "$CALLER_FILE" ] && TARGET="$CALLER_FILE"

# ⚠️ COMPARE RESOLVED PATHS, NOT SPELLINGS. `-f /opt/meddoc-pro/docker-compose.yml
# down` names the production stack as surely as the default does, and a string
# compare against the default would wave it through.
TARGET_REAL="$(readlink -f "$TARGET" 2>/dev/null || echo "$TARGET")"
COMPOSE_REAL="$(readlink -f "$COMPOSE" 2>/dev/null || echo "$COMPOSE")"

# The subcommand: the first bare token, skipping global flags and their values.
SUB=""
skip_next=0
for arg in "$@"; do
  if [ "$skip_next" = 1 ]; then skip_next=0; continue; fi
  case "$arg" in
    -f|--file|-p|--project-name|--project-directory|--profile|--env-file|--ansi|--parallel)
      skip_next=1; continue ;;
    -*) continue ;;
    *) SUB="$arg"; break ;;
  esac
done

if [ "$TARGET_REAL" = "$COMPOSE_REAL" ]; then
  # ⚠️ FAIL-CLOSED ON CANNOT-TELL, same posture as the directory check above: an
  # argv this script cannot parse is not a reason to run it against production.
  if [ -z "$SUB" ]; then
    echo "🔴 dc: cannot identify a subcommand in the arguments. Refusing —"
    echo "   cannot tell, and the target is the PRODUCTION stack."
    exit 1
  fi
  for refused in $REFUSED_ON_PROD; do
    if [ "$SUB" = "$refused" ]; then
      echo "🔴 dc: \`docker compose $SUB\` against the PRODUCTION stack is REFUSED."
      echo "   $COMPOSE_REAL is prod and its co-tenants. This wrapper does not"
      echo "   grant what .claude/settings.json denies."
      echo "   The QA stack is the sanctioned target:"
      echo "     bash scripts/dc.sh -f docker-compose.qa.yml $SUB …"
      exit 1
    fi
  done
fi

if [ -n "$CALLER_FILE" ]; then
  echo "   dc: caller supplied its own compose file — honouring it, from $SHARED."
  exec docker compose "$@"
fi
exec docker compose -f "$COMPOSE" "$@"
