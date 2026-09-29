#!/usr/bin/env bash
# ============================================================================
# SCRATCH LEDGER — record the disposable files YOU made, once they are written.
#
#   bash scripts/scratch-ledger.sh record --agent <your id> [--retain] <dir>/<name>.ledger <file>...
#
#   0 = every file recorded   1 = one or more REFUSED   2 = refused to start
# ----------------------------------------------------------------------------
# ⚠️ THE ONLY FACT THAT MAKES A FILE YOURS TO DESTROY IS THAT YOU MADE IT, AND
# THE ONLY MOMENT THAT FACT IS KNOWABLE IS WHEN YOU MAKE IT. Everything under
# /tmp/claude-<uid>/ has the same owner, so "inside the sandbox" answers "may I
# shred this?" for every agent at once. On 2026-09-29 that cost 30 files other
# agents owned, then 6,537 more (see scripts/lib/scratch_ledger.py's header).
#
# So: when you make a disposable file, record it in the same step — once its last
# write is done, because the reaper refuses anything whose content changed since.
# A file you write again later (a log, a harness output) is recorded again after
# that write: the latest record for a path is the one reaped. At close-out, reap
# ONLY the ledger — `bash scripts/reap-recorded-scratch.sh <ledger>`.
#
# Each record is one appended JSON line: realpath, device, inode, size, sha256,
# owner uid, birth/change/modify times, when it was recorded, your agent id,
# `retain` if the file is evidence (retain is never lifted; the reaper keeps it),
# its line number, and an HMAC under `<ledger>.key` — a key the first record
# creates beside the ledger (0600). The reaper refuses the WHOLE ledger if any
# line does not verify, so a ledger written by anything but this recorder (a
# tree walk, a hand edit, a line copied from another ledger) reaps nothing.
#
# ⚠️ THE LEDGER LIVES OUTSIDE THE SANDBOX, IN A PRIVATE DIRECTORY, NAMED *.ledger
# — a ledger a sweep can reach is a ledger a sweep can destroy, which is what
# happened to the cleanup's own logs. Suggested: one directory per session,
# one ledger per agent: ${XDG_STATE_HOME:-$HOME/.local/state}/scratch-ledger/<agent>.ledger
# Every *.ledger in that directory is read for retain records at reap time, so
# evidence one agent retains is kept whichever ledger reaps it. The directory is
# created 0700 if absent (only it — never a chain of parents) and REFUSED if it
# exists with any group/other bit; the ledger is 0600, yours, one link, never a
# symlink, and is only ever appended to.
#
# ⚠️ AND IT REFUSES TO BE FED BY A SWEEP. More than 16 undeclared files per
# ledger in any 5 minutes — counted across calls in <ledger>.sweep-window, so
# whatever drives the calls — or a find/xargs ancestor, is refused unless
# SCRATCH_LEDGER_BULK_DECLARATION says why (scripts/lib/sweep-guard.sh — the same
# check reap-session-scratch.sh uses). `--retain` calls are exempt: a retain
# record can only PREVENT destruction. Files outside the sandbox, directories,
# symlinks (anywhere on the path), hard links, and files you do not own are refused.
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
