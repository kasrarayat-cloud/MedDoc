#!/usr/bin/env bash
# ============================================================================
# prune-rollback-tags.sh — retire OLD deploy rollback tags, BY NAME.
#
# Ruling #137 (2026-08-21). RELAY item F23.
#
# WHY THIS EXISTS. Preflight's Check 2 used to prescribe `docker image prune
# -af` when images-reclaimable crossed 5 GB. `prune -a` removes every image no
# CONTAINER references — TAGGED ONES INCLUDED — and this host holds ~150
# `meddoc-pro-*:pre-…` tags, the documented rollback path for every past deploy
# (DEPLOYMENT_RUNBOOK.md §3.1-3.2 names some of them by tag). A rollback tag is
# the same class as a volume one layer up: the only artifact that makes a bad
# deploy reversible, and unrebuildable from `main` once the tree has moved.
#
# THE KEEP SET IS A UNION, NOT AN INTERSECTION (ruling #137):
#     · the last 10 DEPLOYS' pre-* tags,   PLUS
#     · any tag whose deploy date is <= 14 days old.
# Everything else is deletable. The owner's reasoning, recorded because it is
# what sets the numbers: "a rollback target older than two weeks of schema
# drift is a false promise anyway — rolling back across migrations 104->106
# without a plan is not a button."
#
# NON-NEGOTIABLE SHAPE (ruling #137, RELAY F23):
#   1. DRY-RUN BY DEFAULT.  Deleting requires --delete.
#   2. The KEEP-LIST is PRINTED BEFORE any deletion, never after and never
#      only the delete-list — a reader has to be able to see what SURVIVES.
#   3. Deletion is BY NAME.  Never `-a`, never a bare `--filter`, never
#      `prune` in any form. That is the entire reason this file exists.
#
# ---------------------------------------------------------------------------
# ⚠️ THE TAG POPULATION HAS THREE SHAPES, NOT ONE. MEASURED 2026-08-21, AND
#    THE FIRST DRAFT OF THIS SCRIPT GOT IT WRONG.
#
# A regex of `^pre-<sha>-<date>$` — F9's automatic form — classified 104 of the
# host's 152 rollback tags as UNPARSEABLE and therefore kept them forever. The
# script would have passed its own tests and reclaimed nothing.
#
#     pre-d7cc0246-20260821    F9's automatic form (sha, then date)
#     pre-footer-20260815      the pre-F9 MANUAL habit (label, then date)
#     pre-20260802-attest      the manual habit with the fields REVERSED
#
# So the date is found by SCANNING for a token that is a real calendar date,
# not by position. A tag with NO valid date token is unparseable and KEPT; a
# tag with TWO is AMBIGUOUS and KEPT. We never delete what we cannot classify.
#
# ⚠️ AND AGE IS READ FROM THAT EMBEDDED DATE, NEVER FROM THE IMAGE'S CreatedAt.
# A pre-* tag names the image that was RUNNING BEFORE the deploy — i.e. the
# PREVIOUS deploy's build. Measured:
#
#     meddoc-pro-transcribe-md:pre-7c42d2d7-20260820   created 2026-08-19 05:06
#
# The tag was cut on the 20th; its image was built on the 19th. Ageing by
# CreatedAt would age every tag by one deploy interval, silently. CreatedAt is
# used for ORDERING ONLY, to break ties inside a single day — a running image
# only ever gets newer, so within one date the newer CreatedAt is the later
# deploy.
# ---------------------------------------------------------------------------
#
# ⚠️ SCOPED TO meddoc-pro-* REPOSITORIES. Co-tenants share this host and are
# untouchable; another project's `pre-*` tag is none of our business.
#
# ⚠️ HONEST LIMIT, STATED SO THE GRANT IS NOT READ WIDER THAN IT IS.
# `docker rmi` is DENIED to the unattended loop in `.claude/settings.json`;
# `bash scripts/ops/prune-rollback-tags.sh` is granted. So this file is a hole
# in its own deny by construction — the same shape `merge-pr.sh` carries
# against `gh pr merge`. That is deliberate and conservative: the hole is
# exactly one keep-set, printed before it acts, and nothing else.
#
# USAGE
#   bash scripts/ops/prune-rollback-tags.sh              # dry run (default)
#   bash scripts/ops/prune-rollback-tags.sh --delete     # actually delete
#   bash scripts/ops/prune-rollback-tags.sh --debug      # add the group counts
#
# EXIT CODES
#   0  reported (dry run), or every deletion succeeded
#   1  at least one deletion FAILED
#   2  CANNOT TELL — the inventory could not be read, the instrument is blind,
#      the partition did not reconcile, or an argument was not understood.
#      NOTHING IS DELETED ON A 2, EVER.
#
# OVERRIDES — for the gate at
# apps/transcribe-md/src/lib/__tests__/gate-f23-prune-rollback-tags.test.ts and
# for auditing a captured inventory by hand. Each prints a loud banner when
# used, because an override that is quiet is an override nobody audits.
#
#   --inventory <file>   read the inventory from a file, not `docker images`
#   --now YYYYMMDD       pin "today" for the 14-day arm
#   --in-use <file>      image ids/tags to treat as container-backed
#
# The same three exist as `PRUNE_ROLLBACK_TAGS_{INVENTORY,NOW,INUSE}` env vars;
# the FLAG wins when both are given.
# ============================================================================
set -uo pipefail

KEEP_DEPLOYS=10
KEEP_DAYS=14
REPO_PREFIX='meddoc-pro-'
TAB=$'\t'
# ⚠️ THE INTERNAL RECORD SEPARATOR IS NOT A TAB, AND THAT IS DELIBERATE.
# TAB is IFS **whitespace**, so `IFS=$'\t' read a b c` COLLAPSES consecutive
# tabs and drops empty fields — every field after an empty one shifts left. A
# `docker images` row with a blank ID therefore silently lost its last field,
# the deploy suffix came back empty, and the tag vanished from BOTH the keep
# list and the delete list while the reconciliation still added up (an
# unclassified row counts as "not deleted", which is safe and invisible).
# `\x1f` is not IFS whitespace, so empty fields survive.
SEP=$'\x1f'

DO_DELETE=0
DEBUG=0
OPT_INVENTORY=''
OPT_NOW=''
OPT_INUSE=''
while [ $# -gt 0 ]; do
  case "$1" in
    --delete) DO_DELETE=1 ;;
    --dry-run) DO_DELETE=0 ;;
    --debug) DEBUG=1 ;;
    --inventory) OPT_INVENTORY="${2:-}"; shift ;;
    --now) OPT_NOW="${2:-}"; shift ;;
    --in-use) OPT_INUSE="${2:-}"; shift ;;
    -h|--help) sed -n '1,100p' "$0"; exit 0 ;;
    *) echo "🔴 unknown argument: $1"; echo "   usage: $0 [--delete]"; exit 2 ;;
  esac
  shift
done

# ⚠️ THE OVERRIDES ARE FLAGS **AND** ENV VARS, AND THE FLAGS ARE THE POINT.
# The unattended FOUNDATION loop cannot set an environment variable on a
# command — `VAR=1 cmd` is not a granted form — so an env-only hook is one the
# only actor who runs this script can never exercise by hand. A hook nobody can
# reach is indistinguishable from one that does not exist. The env forms remain
# for the vitest gate, which spawns with an env of its own.
INVENTORY_FILE="${OPT_INVENTORY:-${PRUNE_ROLLBACK_TAGS_INVENTORY:-}}"
NOW_OVERRIDE="${OPT_NOW:-${PRUNE_ROLLBACK_TAGS_NOW:-}}"
INUSE_FILE="${OPT_INUSE:-${PRUNE_ROLLBACK_TAGS_INUSE:-}}"

say() { printf '%s\n' "$*"; }
nlines() { printf '%s' "$1" | grep -c . || true; }

# Return the single valid YYYYMMDD token in a tag, or an empty string when
# there is none or more than one. Deliberately silent about which — the caller
# treats both as "cannot classify", and both end in the KEEP bucket.
date_token() {
  local tag="$1" tok d found=''
  local n=0
  for tok in ${tag//-/ }; do
    case "$tok" in
      [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;;
      *) continue ;;
    esac
    if d=$(date -u -d "${tok:0:4}-${tok:4:2}-${tok:6:2}" +%Y%m%d 2>/dev/null) && [ "$d" = "$tok" ]; then
      found="$tok"; n=$((n + 1))
    fi
  done
  [ "$n" -eq 1 ] && printf '%s' "$found"
}

# ---------------------------------------------------------------------------
# THE INVENTORY, AND ITS POSITIVE CONTROL.
#
# A broken `docker images` and a host with no rollback tags produce the SAME
# empty output. So the total image count is read FIRST: if docker cannot name a
# single image of any kind, the instrument is blind and we exit 2 rather than
# reporting a zero. If it names images and none of them are rollback tags, that
# is a real zero and we say so.
# ---------------------------------------------------------------------------
INVENTORY_SRC='docker images'
if [ -n "${INVENTORY_FILE:-}" ]; then
  say "⚠️  INVENTORY OVERRIDE ACTIVE — reading ${INVENTORY_FILE}"
  say "    instead of \`docker images\`. This is a TEST HOOK."
  if [ ! -r "${INVENTORY_FILE}" ]; then
    say "🔴 CANNOT TELL — the override file is not readable."
    exit 2
  fi
  RAW=$(cat "${INVENTORY_FILE}")
  INVENTORY_SRC="file:${INVENTORY_FILE}"
else
  if ! RAW=$(docker images --format "{{.Repository}}:{{.Tag}}${TAB}{{.ID}}${TAB}{{.CreatedAt}}" 2>&1); then
    say "🔴 CANNOT TELL — \`docker images\` failed:"
    say "$RAW"
    exit 2
  fi
fi

TOTAL_IMAGES=$(nlines "$RAW")
if [ "$TOTAL_IMAGES" -eq 0 ]; then
  say "🔴 CANNOT TELL — the inventory named ZERO images of ANY kind."
  say "   A blind instrument and a clean host produce the same empty output."
  say "   source: $INVENTORY_SRC"
  exit 2
fi

NOW_DATE="${PRUNE_ROLLBACK_TAGS_NOW:-$(date -u +%Y%m%d)}"
if [ -n "${NOW_OVERRIDE:-}" ]; then
  say "⚠️  CLOCK OVERRIDE ACTIVE — treating today as ${NOW_DATE}. TEST HOOK."
fi
if ! CUTOFF=$(date -u -d "${NOW_DATE:0:4}-${NOW_DATE:4:2}-${NOW_DATE:6:2} - ${KEEP_DAYS} days" +%Y%m%d 2>/dev/null); then
  say "🔴 CANNOT TELL — could not compute the ${KEEP_DAYS}-day cutoff from '${NOW_DATE}'."
  exit 2
fi

if [ -n "${INUSE_FILE:-}" ]; then
  say "⚠️  IN-USE OVERRIDE ACTIVE — reading ${INUSE_FILE}. TEST HOOK."
  IN_USE=$(cat "${INUSE_FILE}" 2>/dev/null || true)
else
  IN_USE=$(docker ps -a --format '{{.Image}}' 2>/dev/null || true)
  IN_USE="${IN_USE}
$(docker ps -aq 2>/dev/null | xargs -r docker inspect --format '{{.Image}}' 2>/dev/null || true)"
fi

# ---------------------------------------------------------------------------
# PARTITION. Every rollback tag lands in exactly ONE named bucket, and the
# totals reconcile by COUNTING at the end — never by subtracting one bucket
# from another. A reconciliation that is computed rather than observed cannot
# detect the case it exists for.
#
#   foreign     a pre-* tag on a repository that is not ours
#   unclassed   ours, but no single valid date token — KEPT
#   candidate   ours, dated — goes on to the keep/delete decision
# ---------------------------------------------------------------------------
CANDIDATES=''      # <suffix> \t <repo:tag> \t <id> \t <created>
GROUPROWS=''       # <date>   \t <created>  \t <suffix>
UNCLASSED=''
FOREIGN=0
OURS_TOTAL=0

# ⚠️ SPLIT BY HAND, NOT BY `IFS=$'\t' read` — see the SEP comment at the top.
# A blank field must stay blank rather than shifting its successors left.
while IFS= read -r ln; do
  [ -z "${ln:-}" ] && continue
  reftag="${ln%%"$TAB"*}"
  rest="${ln#*"$TAB"}"
  id="${rest%%"$TAB"*}"
  created="${rest#*"$TAB"}"
  [ "$rest" = "$ln" ] && { id=''; created=''; }
  [ -z "${reftag:-}" ] && continue
  tag="${reftag##*:}"
  repo="${reftag%:*}"
  case "$tag" in pre-*) ;; *) continue ;; esac
  case "$repo" in
    "${REPO_PREFIX}"*) ;;
    *) FOREIGN=$((FOREIGN + 1)); continue ;;
  esac
  OURS_TOTAL=$((OURS_TOTAL + 1))
  d=$(date_token "$tag")
  if [ -z "$d" ]; then
    UNCLASSED="${UNCLASSED}${reftag}"$'\n'
    continue
  fi
  CANDIDATES="${CANDIDATES}${tag}${SEP}${reftag}${SEP}${id}${SEP}${created}"$'\n'
  GROUPROWS="${GROUPROWS}${d}${SEP}${created}${SEP}${tag}"$'\n'
done <<< "$RAW"

UNCLASSED_N=$(nlines "$UNCLASSED")
CAND_ROWS=$(nlines "$CANDIDATES")

say ""
say "prune-rollback-tags — ruling #137"
say "  source            : $INVENTORY_SRC"
say "  images seen       : $TOTAL_IMAGES  (positive control: non-zero, so the inventory traverses)"
say "  ${REPO_PREFIX}* pre-* : $OURS_TOTAL  = $CAND_ROWS dated + $UNCLASSED_N unclassifiable"
say "  today             : $NOW_DATE"
say "  keep set          : last $KEEP_DEPLOYS deploys  UNION  deploy date >= $CUTOFF (<= $KEEP_DAYS days)"
if [ "$FOREIGN" -gt 0 ]; then
  say "  co-tenant pre-*   : $FOREIGN — NOT OURS, never considered"
fi

if [ "$CAND_ROWS" -eq 0 ]; then
  say ""
  say "🟢 nothing to do — no dated ${REPO_PREFIX}* rollback tag to consider."
  if [ "$UNCLASSED_N" -gt 0 ]; then
    say "⚠️  $UNCLASSED_N unclassifiable pre-* tag(s) KEPT:"
    printf '%s' "$UNCLASSED" | sed 's/^/      /'
  fi
  exit 0
fi

# Deploy groups, newest first. Dedupe to one row per deploy keeping that
# deploy's newest image, then order by: embedded date DESC, newest CreatedAt
# DESC (deploy order inside one day), tag DESC for determinism.
# ⚠️ THIS VARIABLE IS **NOT** CALLED `GROUPS`, AND THAT IS DELIBERATE.
# `GROUPS` is a bash SPECIAL ARRAY holding the invoking user's group ids.
# `GROUPS=$(…)` is silently IGNORED — no error, no non-zero status — and
# `"$GROUPS"` then expands to the primary gid. The first draft of this script
# did exactly that: every deploy grouping collapsed to the single string
# `1000`, the keep-list printed zero rows, the delete-list printed zero rows,
# and the run reported a cheerful green `0 tag(s) would be removed`.
# An assignment that succeeds and does not land, in the shape canon already
# names for `chmod +x` and `.replace()`.
DEPLOY_ORDER=$(printf '%s' "$GROUPROWS" \
  | sort -t"$SEP" -k3,3 -k2,2r \
  | awk -F"$SEP" '!seen[$3]++' \
  | sort -t"$SEP" -k1,1r -k2,2r -k3,3r)
GROUP_COUNT=$(nlines "$DEPLOY_ORDER")
if [ "$DEBUG" = "1" ]; then
  say "DEBUG rows=$(nlines "$GROUPROWS") groups=$GROUP_COUNT"
fi

KEEP_ROWS=''
DELETE_SUFFIXES=''
KEEP_GROUPS=0
rank=0
SKIPPED_GROUPS=0
while IFS="$SEP" read -r gdate gcreated gsuffix; do
  if [ -z "${gsuffix:-}" ]; then
    [ -n "${gdate:-}${gcreated:-}" ] && SKIPPED_GROUPS=$((SKIPPED_GROUPS + 1))
    continue
  fi
  rank=$((rank + 1))
  why=''
  [ "$rank" -le "$KEEP_DEPLOYS" ] && why='recent-10'
  if [ ! "$gdate" \< "$CUTOFF" ]; then
    if [ -n "$why" ]; then why="recent-10 + <=${KEEP_DAYS}d"; else why="<=${KEEP_DAYS}d"; fi
  fi
  if [ -n "$why" ]; then
    KEEP_GROUPS=$((KEEP_GROUPS + 1))
    KEEP_ROWS="${KEEP_ROWS}${gsuffix}${SEP}#${rank}${SEP}${gdate}${SEP}${why}"$'\n'
  else
    DELETE_SUFFIXES="${DELETE_SUFFIXES}${gsuffix}"$'\n'
  fi
done <<< "$DEPLOY_ORDER"

# ---------------------------------------------------------------------------
# ⚠️ THE KEEP-LIST IS PRINTED FIRST. Ruling #137 clause 2.
# ---------------------------------------------------------------------------
say ""
say "──────── KEEP — $KEEP_GROUPS of $GROUP_COUNT deploys SURVIVE ────────"
printf '%s' "$KEEP_ROWS" | awk -F"$SEP" '{ printf "  ✔ %-30s rank %-5s date %s   (%s)\n", $1, $2, $3, $4 }'
if [ "$UNCLASSED_N" -gt 0 ]; then
  say "  ✔ …plus $UNCLASSED_N unclassifiable pre-* tag(s) — KEPT, because a tag whose"
  say "    deploy date we cannot read is never a tag we delete:"
  printf '%s' "$UNCLASSED" | sed 's/^/      /'
fi

DEL_GROUPS=$(nlines "$DELETE_SUFFIXES")

# ⚠️ THE GROUP-LEVEL RECONCILIATION IS WHAT CAUGHT THE SEPARATOR BUG, AND IT
# IS THE STRICTER OF THE TWO. The per-tag one further down counts anything not
# on the delete list as kept, so a row that fell out of the partition entirely
# still "reconciles" — safe, and invisible. This one cannot be satisfied by a
# dropped row: keep + delete must equal the deploys we counted.
if [ $((KEEP_GROUPS + DEL_GROUPS)) -ne "$GROUP_COUNT" ] || [ "$SKIPPED_GROUPS" -ne 0 ]; then
  say ""
  say "🔴 CANNOT TELL — $GROUP_COUNT deploys went in and $((KEEP_GROUPS + DEL_GROUPS)) came out"
  say "   ($KEEP_GROUPS kept + $DEL_GROUPS deletable, $SKIPPED_GROUPS unreadable)."
  say "   Nothing is deleted when the partition does not account for every deploy."
  exit 2
fi

say ""
say "──────── DELETABLE — $DEL_GROUPS of $GROUP_COUNT deploys ────────"
[ "$DEL_GROUPS" -eq 0 ] && say "  (none)"

# Expand deploy groups back to individual image tags, holding back any whose
# image backs a container. `docker rmi` on a container-backed image is a
# foot-gun; refusing it here is cheaper than explaining it afterwards.
DELETE_REFS=''
HELD=0
if [ "$DEL_GROUPS" -gt 0 ]; then
  while IFS= read -r suffix; do
    [ -z "${suffix:-}" ] && continue
    while IFS="$SEP" read -r s reftag id created; do
      [ "$s" = "$suffix" ] || continue
      # ⚠️ THE EMPTINESS GUARD IS LOAD-BEARING. `grep -qF -- ""` matches EVERY
      # line, so a malformed inventory row with a blank image id would mark the
      # whole delete-list as container-backed and report a cheerful zero. The
      # id match is a substring one on purpose: `docker images` gives a 12-char
      # short id and `docker inspect` gives `sha256:<64hex>` containing it.
      # ⚠️ BASH-NATIVE, NOT `printf | grep -q` — THE F30 CLASS, AND THESE TWO
      # ARE THE DANGEROUS DIRECTION. `grep -q` exits 0 the instant it matches
      # and CLOSES the pipe; `printf` then dies of SIGPIPE (141); `set -o
      # pipefail` (line 93) promotes the pipeline's status to that 141 — so a
      # MATCH is reported as a MISS.
      #
      # ⚠️ HERE A FALSE MISS LEAVES `held=0` ON AN IMAGE A CONTAINER IS USING,
      # so the tag is printed as `✗` and joins DELETE_REFS. That is a rollback
      # tag deleted while in use — the artifact ruling #137 exists to protect,
      # and unrebuildable from `main` once the tree has moved.
      #
      # The id match stays a SUBSTRING one on purpose (`docker images` gives a
      # 12-char short id, `docker inspect` gives `sha256:<64hex>` containing
      # it), and the emptiness guard stays load-bearing: `*""*` matches
      # everything, exactly as `grep -qF -- ""` did.
      held=0
      if [ -n "${id:-}" ] && [[ "$IN_USE" == *"$id"* ]]; then held=1; fi
      # Line-exact, as `-x` was: the needle is wrapped in newlines on both sides.
      if [[ $'\n'"$IN_USE"$'\n' == *$'\n'"$reftag"$'\n'* ]]; then held=1; fi
      if [ "$held" = "1" ]; then
        say "  ⏸ $reftag — HELD, a container references this image"
        HELD=$((HELD + 1))
        continue
      fi
      say "  ✗ $reftag   ($created)"
      DELETE_REFS="${DELETE_REFS}${reftag}"$'\n'
    done <<< "$CANDIDATES"
  done <<< "$DELETE_SUFFIXES"
fi

DEL_REF_COUNT=$(nlines "$DELETE_REFS")

# Reconciliation by COUNTING each bucket independently, then asserting the sum.
KEPT_REFS=''
while IFS="$SEP" read -r s reftag id created; do
  [ -z "${reftag:-}" ] && continue
  # ⚠️ THE SAME F30 CLASS, AND THIS ONE EXPLAINS THE OBSERVED SYMPTOM. A false
  # miss here means a reftag already in DELETE_REFS is not recognised, so it is
  # ALSO added to KEPT_REFS — the tag lands in BOTH buckets,
  # `KEPT_REF_COUNT + DEL_REF_COUNT` exceeds `CAND_ROWS`, and the reconciliation
  # below refuses with "the buckets do not reconcile" and exits 2 BEFORE any
  # removal. `gate-f23`'s red is exactly that: "expected 0 to be greater than 0"
  # on the arm that asserts something was removed.
  [[ $'\n'"$DELETE_REFS"$'\n' == *$'\n'"$reftag"$'\n'* ]] && continue
  KEPT_REFS="${KEPT_REFS}${reftag}"$'\n'
done <<< "$CANDIDATES"
KEPT_REF_COUNT=$(nlines "$KEPT_REFS")

say ""
say "  reconciliation    : $CAND_ROWS dated tags = $KEPT_REF_COUNT kept/held + $DEL_REF_COUNT deletable"
if [ $((KEPT_REF_COUNT + DEL_REF_COUNT)) -ne "$CAND_ROWS" ]; then
  say "🔴 CANNOT TELL — the buckets do not reconcile against the candidate count."
  say "   Nothing is deleted when the partition does not add up."
  exit 2
fi

if [ "$DO_DELETE" -eq 0 ]; then
  say ""
  say "🟢 DRY RUN — nothing was deleted. $DEL_REF_COUNT tag(s) would be removed BY NAME."
  say "   Re-run with --delete to act."
  exit 0
fi

if [ "$DEL_REF_COUNT" -eq 0 ]; then
  say ""
  say "🟢 --delete requested, and there is nothing outside the keep set. Nothing deleted."
  exit 0
fi

say ""
say "──────── DELETING BY NAME ────────"
FAILED=0
DELETED=0
while IFS= read -r reftag; do
  [ -z "${reftag:-}" ] && continue
  if out=$(docker rmi "$reftag" 2>&1); then
    say "  🗑  $reftag"
    DELETED=$((DELETED + 1))
  else
    say "  🔴 FAILED $reftag"
    printf '%s\n' "$out" | sed 's/^/       /'
    FAILED=$((FAILED + 1))
  fi
done <<< "$DELETE_REFS"

say ""
say "  deleted $DELETED, failed $FAILED, held $HELD, kept $KEPT_REF_COUNT"
if [ "$FAILED" -gt 0 ]; then
  say "🔴 $FAILED deletion(s) FAILED — read them above; nothing is retried silently."
  exit 1
fi
say "🟢 $DELETED rollback tag(s) retired BY NAME. The keep set above is intact."
exit 0
