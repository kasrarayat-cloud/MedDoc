#!/usr/bin/env bash
# ============================================================================
# Is every container actually running the config file the repo says it is?
# ----------------------------------------------------------------------------
# ⚠️ A CHECK THAT CRIES WOLF IS HOW THE REAL SIGNAL GETS IGNORED. This one is
# built to two arms and two verdicts: a container that is not running is
# "cannot tell" (2), never RED. RED is reserved for a container that IS running
# and IS serving something other than what the repo holds.
#
# WHY THIS EXISTS — the 6h15m ingress outage of 2026-08-07.
# `docker-compose.yml` bind-mounts THREE files out of the working tree. A FILE
# bind binds the INODE, not the path. Any editor that writes-then-renames (git
# checkout, most editors, python's write-and-replace) creates a NEW inode, and
# the container keeps the ORPHANED original — forever, silently:
#
#     host shows the edit          container does not
#     `caddy reload`               reports "config is unchanged"
#     `caddy validate`             reports "Valid configuration" — OF THE OLD FILE
#     `docker compose up -d`       declines, no config hash changed
#
# Only `--force-recreate` re-resolves the bind. Nothing else does, and every
# other signal available reads as success.
#
# TWO ARMS, BECAUSE THEY ANSWER DIFFERENT QUESTIONS:
#
#   CONTENT (md5 host vs container)  "is it running what the repo says?"
#                                    → RED. This is the outage, already happened.
#   INODE   (host vs container)      "will the NEXT edit even land?"
#                                    → NOTE. This is PREDICTIVE, and it is the
#                                      half that would have caught the outage
#                                      BEFORE it was one.
#
# The inode arm is deliberately not RED: diverged inodes with matching content
# are a completely healthy running system. Making that red would be the wolf-cry
# this header opens with. It is reported because it is the tripwire — and it
# re-arms itself on every branch switch, so it is normal to see it and worth
# knowing about before you edit.
#
# READ-ONLY. Reads files and container metadata; writes nothing.
#
# Usage:  bash scripts/check-bind-mount-agreement.sh
# Exit:   0 = every running container agrees · 1 = DIVERGED · 2 = cannot tell
# ============================================================================
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The class, enumerated 2026-08-07 by two independent methods that agreed:
# `docker inspect` over every meddoc container (running AND stopped), and the
# compose files. Kept here BY FILE, so a new bind that nobody adds to this list
# is the one thing this check cannot see — see the census arm at the end, which
# exists precisely to make that failure loud instead of silent.
MEMBERS=(
  "meddoc-pro-caddy-1|Caddyfile|/etc/caddy/Caddyfile"
  "meddoc-pro-postgres-backup-1|infra/postgres-backup/postscript.sh|/scripts/postscript.sh"
  "meddoc-pro-postgres-backup-1|infra/backup-offsite-sync.sh|/scripts/backup-offsite-sync.sh"
)

diverged=0; untestable=0; armed=0; checked=0

echo "bind-mounted config — is the container running what the repo holds?"
for m in "${MEMBERS[@]}"; do
  IFS='|' read -r ctr host dest <<<"$m"

  if ! docker ps --format '{{.Names}}' | grep -qx "$ctr"; then
    printf '   🟡 %-44s %s is not running — cannot tell\n' "$host" "$ctr"
    untestable=1; continue
  fi
  if [ ! -f "$host" ]; then
    printf '   🟡 %-44s absent from the working tree — cannot tell\n' "$host"
    untestable=1; continue
  fi

  hm=$(md5sum "$host" 2>/dev/null | awk '{print $1}')
  cm=$(docker exec "$ctr" md5sum "$dest" 2>/dev/null | awk '{print $1}')
  hi=$(stat -c %i "$host" 2>/dev/null)
  ci=$(docker exec "$ctr" stat -c %i "$dest" 2>/dev/null)

  if [ -z "$cm" ]; then
    printf '   🟡 %-44s unreadable inside %s — cannot tell\n' "$host" "$ctr"
    untestable=1; continue
  fi

  checked=$((checked+1))
  if [ "$hm" != "$cm" ]; then
    printf '   🔴 %-44s CONTENT DIVERGED\n' "$host"
    printf '      host md5 %s   container md5 %s\n' "$hm" "$cm"
    printf '      → the container is serving something the repo does not hold.\n'
    printf '      → fix: docker compose up -d --no-deps --force-recreate %s\n' "${ctr#meddoc-pro-}"
    diverged=1
  elif [ "$hi" != "$ci" ]; then
    printf '   ✔ %-44s content agrees  ⚠ inode diverged (%s ≠ %s)\n' "$host" "$hi" "$ci"
    armed=1
  else
    printf '   ✔ %-44s content and inode agree\n' "$host"
  fi
done

# ── CENSUS ARM ────────────────────────────────────────────────────────────
# The list above is hand-kept, and hand-kept lists are wrong eventually. So the
# check also counts the binds that ACTUALLY exist and compares. A new
# working-tree file bind that nobody added here makes this fail loudly rather
# than sit unwatched — the defect this whole file is shaped against.
actual=$(grep -cE '^\s*-\s*\./[^:]+:[^:]+' docker-compose.yml 2>/dev/null || echo 0)
if [ "$actual" -ne "${#MEMBERS[@]}" ]; then
  printf '\n   🔴 CENSUS MISMATCH: docker-compose.yml declares %s working-tree file binds, this check watches %s.\n' \
    "$actual" "${#MEMBERS[@]}"
  printf '      A bind nobody added to MEMBERS is a bind nothing watches. Reconcile before trusting any green above.\n'
  diverged=1
fi

echo
if [ "$diverged" -ne 0 ]; then
  echo "🔴 A CONTAINER IS NOT RUNNING WHAT THE REPO HOLDS."
  exit 1
fi
if [ "$checked" -eq 0 ]; then
  echo "🟡 nothing could be checked — no verdict. (Stack down? Wrong host?)"
  exit 2
fi
if [ "$untestable" -ne 0 ]; then
  echo "🟡 $checked member(s) agree; others could not be checked — partial, so no clean pass."
  exit 2
fi
if [ "$armed" -ne 0 ]; then
  echo "🟢 every bind-mounted config agrees with the repo."
  echo "   ⚠ but at least one inode has diverged: the NEXT edit to that file will"
  echo "     NOT reach its container. Use --force-recreate, not reload, when you"
  echo "     change it. (A branch switch re-arms this; it is not a fault.)"
  exit 0
fi
echo "🟢 every bind-mounted config agrees with the repo, inodes included."
exit 0
