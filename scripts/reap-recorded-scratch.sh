#!/usr/bin/env bash
# ============================================================================
# REAP RECORDED SCRATCH — shred ONLY what your ledger recorded, unchanged.
#
#   bash scripts/reap-recorded-scratch.sh [--retained <manifest>]... [--dry-run] <dir>/<name>.ledger [<recorded path>...]
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
# directory argument, or any path the ledger does not hold, is REFUSED.
#
# It REFUSES TO START (exit 2) when any ledger line is not bound to the recorder
# (its HMAC under <ledger>.key does not verify, or it is out of sequence), when
# any --retained manifest line is not exactly one of the recognised forms, and
# when any other *.ledger in the same directory cannot be read (retain is global
# across that directory, so an unreadable sibling is CANNOT TELL).
#
# For each entry it refuses unless ALL hold at the moment of shredding (details
# and honest limits in scripts/lib/scratch_ledger.py):
#   * same realpath under /tmp/claude-<your uid>/, no symlink component anywhere,
#     the leaf not a link (every directory opened O_NOFOLLOW from / down);
#   * same device + inode + size + sha256 as recorded — never a sibling, never a
#     replacement;
#   * owned by you, link count 1 (never a shared hard link);
#   * not recorded --retain in ANY *.ledger of the directory, by path or by
#     (device, inode, sha256); not listed, aliased or contained by any --retained
#     manifest. A manifest line is EXACTLY a bare absolute path in normal form, or
#     a sha256sum line ("<64 hex>  /path" or "<64 hex> */path"); "#" comment lines
#     and empty lines are skipped; a trailing blank, a trailing comment, a size
#     column, `ls -l` output, or a path that reaches nothing refuses the run;
#   * not inside a .git directory or a bare repository, not tracked by git, and
#     not where git cannot answer (any exit but 0/1 is CANNOT TELL);
#   * not open or mapped by a live process, and no live process except this
#     reaper's own caller chain works in its directory (/proc/*/fd, maps, cwd);
#   * after those scans, still one link, same size/mtime/ctime, and the path
#     walked again from / still reaches it; its directory is writable.
# It overwrites through the VERIFIED inode (a read-only file of yours is made
# owner-writable through that descriptor first, and put back if the shred
# fails), checks shred's exit status and that the content reads as zeros, BEFORE
# unlinking — never after.
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
