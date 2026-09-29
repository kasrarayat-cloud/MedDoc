#!/usr/bin/env bash
# ============================================================================
# REAP RECORDED SCRATCH — shred ONLY what your ledger recorded, unchanged.
#
#   bash scripts/reap-recorded-scratch.sh [--retained <manifest>]... [--dry-run] <ledger> [<recorded path>...]
#
#   0 = every selected entry shredded (or already absent, or kept by retain)
#   1 = one or more REFUSED or FAILED       2 = refused to start
# ----------------------------------------------------------------------------
# THE DOOR SUBAGENTS USE. `reap-session-scratch.sh` answers "is this path inside
# the sandbox?" — true of every agent's scratch at once, which is how a whole-tree
# sweep on 2026-09-29 destroyed 30 files other agents owned and then 6,537 more.
# This door answers "did I record this file, and is it still exactly that file?"
#
# With no path arguments it reaps every entry of the ledger; with paths, only
# those, each of which must be IN the ledger. It NEVER walks a directory: a
# directory argument, or any path the ledger does not hold, is REFUSED. For each
# entry it refuses unless ALL hold at the moment of shredding (details and honest
# limits in scripts/lib/scratch_ledger.py):
#   * same realpath under /tmp/claude-<your uid>/, no symlink component anywhere,
#     the leaf not a link (every directory opened O_NOFOLLOW from / down);
#   * same device + inode + size + sha256 as recorded — never a sibling, never a
#     replacement;
#   * owned by you, link count 1 (never a shared hard link);
#   * not recorded --retain; not listed, aliased or contained by any --retained
#     manifest (one absolute path per line; sha256sum and `ls`-style lines work);
#   * not tracked by git (the reap-session-scratch.sh refusal, kept);
#   * not open, mapped, or holding a live process's working directory
#     (/proc/*/fd, /proc/*/maps, /proc/*/cwd readable to you).
# It overwrites through the VERIFIED file descriptor, checks shred's exit status
# and that the content reads as zeros, BEFORE unlinking — never after.
#
# Every decision is appended to <ledger>.reap-log, beside the ledger OUTSIDE the
# sandbox. The reaper never deletes, truncates or rewrites the ledger or the log.
# `--dry-run` takes every decision and logs it as WOULD-SHRED without shredding.
# ============================================================================
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || here=""
if [ -z "$here" ] || [ ! -r "$here/lib/scratch_ledger.py" ]; then
  echo "🔴 reap-recorded-scratch: CANNOT TELL — scripts/lib/scratch_ledger.py is missing; refusing." >&2
  exit 2
fi
command -v python3 >/dev/null 2>&1 || { echo "🔴 reap-recorded-scratch: no python3 on PATH; refusing." >&2; exit 2; }
exec python3 -B -I "$here/lib/scratch_ledger.py" reap "$@"
