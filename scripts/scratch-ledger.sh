#!/usr/bin/env bash
# ============================================================================
# SCRATCH LEDGER — record, AT CREATION, the disposable files YOU made.
#
#   bash scripts/scratch-ledger.sh record --agent <your id> [--retain] <ledger> <file>...
#
#   0 = every file recorded   1 = one or more REFUSED   2 = refused to start
# ----------------------------------------------------------------------------
# ⚠️ THE ONLY FACT THAT MAKES A FILE YOURS TO DESTROY IS THAT YOU MADE IT, AND
# THE ONLY MOMENT THAT FACT IS KNOWABLE IS WHEN YOU MAKE IT. Everything under
# /tmp/claude-<uid>/ has the same owner, so "inside the sandbox" answers "may I
# shred this?" for every agent at once. On 2026-09-29 that cost 30 files other
# agents owned, then 6,537 more (see scripts/lib/scratch_ledger.py's header).
#
# So: when you create a disposable file, record it. At close-out, reap ONLY the
# ledger — `bash scripts/reap-recorded-scratch.sh <ledger>` — which shreds
# nothing that was not recorded and nothing that changed since.
#
# Each record is one appended JSON line: realpath, device, inode, size, sha256,
# owner uid, birth/change/modify times, when it was recorded, your agent id, and
# `retain` if the file is evidence (retain is never lifted; the reaper keeps it).
#
# ⚠️ THE LEDGER LIVES OUTSIDE THE SANDBOX, IN A PRIVATE DIRECTORY — a ledger a
# sweep can reach is a ledger a sweep can destroy, which is what happened to the
# cleanup's own logs. Suggested: ${XDG_STATE_HOME:-$HOME/.local/state}/scratch-ledger/<agent>.ledger
# The directory is created 0700 if absent and REFUSED if it exists with any
# group/other bit; the ledger is 0600, yours, one link, never a symlink, and is
# only ever appended to.
#
# ⚠️ AND IT REFUSES TO BE FED BY A SWEEP. More than 16 files in one call, or a
# find/xargs ancestor, is refused unless SCRATCH_LEDGER_BULK_DECLARATION says why
# (scripts/lib/sweep-guard.sh — the same check reap-session-scratch.sh uses).
# `--retain` calls are exempt: a retain record can only PREVENT destruction.
# Files outside the sandbox, directories, symlinks (anywhere on the path), hard
# links, and files you do not own are refused.
# ============================================================================
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || here=""
if [ -z "$here" ] || [ ! -r "$here/lib/scratch_ledger.py" ]; then
  echo "🔴 scratch-ledger: CANNOT TELL — scripts/lib/scratch_ledger.py is missing; refusing." >&2
  exit 2
fi
case "${1:-}" in
  record) ;;
  *) echo "usage: bash scripts/scratch-ledger.sh record --agent <id> [--retain] <ledger> <file>..." >&2
     exit 2 ;;
esac
command -v python3 >/dev/null 2>&1 || { echo "🔴 scratch-ledger: no python3 on PATH; refusing." >&2; exit 2; }
exec python3 -B -I "$here/lib/scratch_ledger.py" "$@"
