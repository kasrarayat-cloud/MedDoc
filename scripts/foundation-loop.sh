#!/usr/bin/env bash
# ============================================================================
# FOUNDATION — the unattended runner.
# ----------------------------------------------------------------------------
# Runs `claude` headless with docs/foundation/MASTER.md as the prompt, once per
# session, appending each session's FULL output to
# docs/foundation/logs/<date>-runNN.log. Those logs ARE the war-room reports —
# there is no second place the session reports to.
#
# ⚠️ IT CONTINUES ONLY ON `CONTINUE`. Every other marker halts, and so does an
# ABSENT or AMBIGUOUS one. The default is to stop: a runner that keeps going
# when it cannot read the answer is worse than one that stops too often.
#
# ── FOUR INDEPENDENT KILL SWITCHES, ALL CHECKED BEFORE A SESSION STARTS ─────
#
#   1. STOP FILE      docs/foundation/STOP exists → halt.
#                     `touch docs/foundation/STOP` from anywhere kills the loop
#                     before the next session begins. It is checked FIRST, so a
#                     human always wins the race against the next launch.
#   2. TOTAL BUDGET   default 24 sessions per RUN (MAX_SESSIONS=6 is now only a
#                     BATCH size — on CONTINUE-at-cap the runner relights itself
#                     with a fresh launch stamp). The blast radius is still
#                     bounded, just at the night rather than the batch: whatever
#                     goes wrong goes wrong at most 24 times before a human sees.
#                     ⚠️ Relighting happens ONLY on CONTINUE-at-cap. Every other
#                     exit — marker, session error, no-progress, log collision,
#                     STOP file — ends the whole run. A relight can never
#                     resurrect a run that something deliberately stopped.
#   3. MARKER         anything but CONTINUE halts, with the marker as the reason.
#   4. NO-PROGRESS    RELAY.md unchanged across two consecutive sessions → halt
#                     with NO-PROGRESS. This is the one that catches a session
#                     doing lots of work and landing nothing — the failure mode
#                     the marker cannot see, because a session that spins can
#                     still honestly believe it should continue.
#
# ⚠️ WHY RELAY.md IS THE PROGRESS SIGNAL AND NOT, SAY, THE GIT LOG.
# The ledger is the contract between sessions. An item that lands without a
# ledger row has not finished, by this programme's own rules — so "RELAY.md did
# not change" and "no item completed" are the same statement. A git-log check
# would count commits, and a spinning session commits plenty.
#
# ⚠️ AND IT IS MEASURED ON `origin/main`, NOT ON THIS WORKING TREE — F20.
# A session works in its own `git worktree` and lands its row through a merged
# PR. It never writes the shared tree's copy of RELAY.md, which advances only
# via the launch-time ff-sync BELOW — i.e. before the session runs. Hashing that
# file therefore sampled something the judged session could not affect, and
# collapsed "no item finished" into "no sync happened".
#
# It FIRED FALSELY on 2026-08-19 and ended a productive run: sessions 03 and 04
# both launched with the tree at `febfdcfd`, session 04 then merged #740, #741
# and #742 — all carrying ledger rows — and halted on NO-PROGRESS 37 minutes
# later, 14 commits ahead of the file being read. Full mechanism in
# `scripts/lib/ledger-progress.sh`.
#
# ── WHAT THE LOOP INHERITS ─────────────────────────────────────────────────
# Every guardrail in MASTER.md, unchanged: deploy-prod.sh is the only path to
# production; co-tenants are untouchable; Stripe stays TEST MODE; owner-boundary
# items HALT the loop rather than being worked around; production is read-only by
# default. The loop grants no capability the guardrails do not already permit —
# it only removes the human keystroke between sessions.
#
# Usage:
#   bash scripts/foundation-loop.sh              # 6 sessions max
#   MAX_SESSIONS=2 bash scripts/foundation-loop.sh
#   touch docs/foundation/STOP                   # halt before the next session
#
# In tmux (how it is meant to run — survives a dropped terminal):
#   tmux new -d -s foundation 'bash scripts/foundation-loop.sh'
#   tmux attach -t foundation
# ============================================================================
set -uo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# F20 — the progress signal. Sourced AFTER the cd, so its relative path resolves
# from the repo root like every other path in this file.
# shellcheck source=scripts/lib/ledger-progress.sh
. scripts/lib/ledger-progress.sh

MAX_SESSIONS="${MAX_SESSIONS:-6}"
# ⚠️ THE CAP IS A BATCH SIZE; **TOTAL_BUDGET** IS THE NIGHT'S REAL BOUND.
# On CONTINUE-at-cap the runner relights itself with a fresh launch stamp rather
# than stopping, up to TOTAL_BUDGET sessions. The cap therefore no longer ends
# the run — it only decides how often the log rolls over. Every other kill switch
# is unchanged and still ends everything.
TOTAL_BUDGET="${TOTAL_BUDGET:-24}"
PROMPT_FILE="docs/foundation/MASTER.md"
STOP_FILE="docs/foundation/STOP"
INBOX_FILE="docs/foundation/INBOX.md"
LEDGER="docs/foundation/RELAY.md"
LOG_DIR="docs/foundation/logs"
# ⚠️ DATE AND LAUNCH ARE COMPUTED PER BATCH, NOT ONCE — AN OVERNIGHT RUN CROSSES
# MIDNIGHT. Computed once at start, every log written after 00:00Z would carry
# the PREVIOUS day's date: the filenames would still be unique (the launch stamp
# differs) and still be WRONG, which is the worse failure — a wrong label is
# read, an absent one is noticed.
# ⚠️ A LOG FILENAME MUST IDENTIFY A LAUNCH, NOT JUST A DAY.
# The first version named logs `<date>-runNN.log`. The counter resets to 01 on
# every launch, so a SECOND launch on the same day reopened run01.log and
# APPENDED to it — two different launches' sessions interleaved in one file,
# each distinguishable only by reading the `started :` banners. That happened on
# 2026-08-08: run01.log holds a 15:42 session and an 18:23 session, and the
# filename says nothing about either.
#
# The launch timestamp fixes it without breaking what runNN MEANS. Scanning for
# the next free runNN would also avoid the collision, but it makes the counter
# monotonic forever and erases where one launch ends and the next begins —
# "session 3" would stop meaning "the third session of this run".

mkdir -p "$LOG_DIR"

if [ ! -f "$PROMPT_FILE" ]; then
  echo "🔴 $PROMPT_FILE is missing — refusing to run a loop with no brief."
  exit 2
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "🔴 the claude CLI is not on PATH."
  exit 2
fi

# ⚠️ A STALE STOP FILE MUST NOT SILENTLY DISABLE THE LOOP. If one is left over
# from a previous halt, say so loudly and refuse — rather than exiting 0 in a way
# that reads like "the queue is finished".
# ⚠️ THE INTERPRETER IS ASSERTED BEFORE THE FIRST SESSION, NOT DISCOVERED BY IT.
# On 2026-08-20T01:36Z the `claude` CLI auto-updated to 2.1.237, whose linux
# native package was never published, and every session died on launch with
# "claude native binary not installed". The loop went dark mid-run and nothing
# said why — tmux was fine, the tree was fine, and the thing that was broken is
# the one component no liveness signal looks at.
#
# A named refusal here costs one line and turns a silent dark loop into a
# sentence that names the repair.
if ! bash scripts/check-claude-cli.sh; then
  echo "🔴 REFUSING TO LAUNCH — the claude CLI cannot run (see above)."
  echo "   Every session would die on startup and the loop would go dark"
  echo "   without saying why. Fix the CLI, then relight."
  exit 1
fi

if [ -f "$STOP_FILE" ]; then
  echo "🔴 $STOP_FILE exists — the loop is disabled."
  echo "   It was created $(date -u -r "$STOP_FILE" +%Y-%m-%dT%H:%M:%SZ). Contents:"
  sed 's/^/     /' "$STOP_FILE"
  echo "   Remove it to re-enable: rm $STOP_FILE"
  exit 2
fi

# ============================================================================
# STARTUP GUARD — the loop refuses to begin from an ambiguous state.
# ----------------------------------------------------------------------------
# ⚠️ A DIRTY TREE AT LOOP START IS SOMEBODY'S UNFINISHED WORK, and the loop has
# no way to tell a half-applied edit from a deliberate one. MASTER.md tells each
# SESSION to reconstruct a dirty tree — that is right for state a previous
# session left mid-queue. It is wrong for state that was already there when the
# loop was lit, because nothing in the loop's history explains it.
#
# Checked ONCE, before session 1. Between sessions a branch and even a dirty tree
# are normal: a session legitimately ends with a PR open and CI running, and the
# next session's STEP 0 is what resolves it.
# ============================================================================
START_BRANCH="$(git branch --show-current 2>/dev/null)"
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  echo "🔴 REFUSING TO START — the working tree is dirty."
  git status --porcelain | sed 's/^/     /'
  echo
  echo "   The loop cannot tell a half-applied edit from a deliberate one, and it"
  echo "   is about to run sessions that can deploy. Commit, stash or revert first."
  exit 2
fi
if [ "$START_BRANCH" != "main" ]; then
  echo "⚠️  starting on '$START_BRANCH', not main."
  echo "   The queue is executed against main; a feature branch means the loop's"
  echo "   own sessions would commit to it. Continuing, but say so loudly."
  echo
fi

# ⚠️ THE STREAK COUNTERS LIVE OUTSIDE THE BATCH LOOP, DELIBERATELY. The
# no-progress switch watches the whole night, not each batch: resetting it per
# batch would let a stalled loop relight forever, since the switch needs two
# CONSECUTIVE unchanged sessions and a reset makes every batch's first session
# look like a fresh start. The one kill switch that catches "busy but landing
# nothing" must not be the one the relight silently disarms.
noprogress_streak=0
# ⚠️ CANNOT-TELL IS COUNTED SEPARATELY AND NEVER REPORTED AS NO-PROGRESS. A
# failed fetch is evidence about the network, not about the session, and calling
# it "no progress" is precisely the collapse F20 exists to undo. But a switch
# that is silently disarmed by a permanent fault is no switch at all — so a
# cannot-tell that PERSISTS halts under its own name. Three consecutive, the
# same debounce the runs-API waiter uses, because one blind sample is a blip.
cannottell_streak=0
CANNOTTELL_LIMIT=3
overall_halt=""
sessions_used=0
batch=0
# Marker-recovery budget for the WHOLE run, not per batch — a contract broken
# repeatedly is a signal, and resetting it per batch would hide exactly that.
recoveries_used=0
# Sessions that finished with no morning report — a RECORD defect, reported in
# the halt banner and read by the next session's STEP 0. Never a halt on its own.
reports_missing=""

while : ; do
  # ── STOP WINS THE RACE AT THE BATCH BOUNDARY TOO ─────────────────────────
  # Checked here as well as before each session, so a human who creates the file
  # during the last session of a batch is never overtaken by the relight.
  if [ -f "$STOP_FILE" ]; then
    overall_halt="STOP FILE — $STOP_FILE appeared before batch $((batch + 1))"
    break
  fi
  if [ "$sessions_used" -ge "$TOTAL_BUDGET" ]; then
    overall_halt="BUDGET EXHAUSTED — $sessions_used of $TOTAL_BUDGET sessions used"
    break
  fi

  batch=$(( batch + 1 ))
  DATE="$(date -u +%Y%m%d)"
  LAUNCH="$(date -u +%H%M%S)"
  halt_reason=""

  # Never start more sessions than the budget has left.
  batch_size="$MAX_SESSIONS"
  remaining=$(( TOTAL_BUDGET - sessions_used ))
  [ "$batch_size" -gt "$remaining" ] && batch_size="$remaining"

for (( n=1; n<=batch_size; n++ )); do
  RUN=$(printf '%02d' "$n")
  # ⚠️ THE BATCH ORDINAL IS PART OF THE NAME, NOT DECORATION. A wall-clock stamp
  # alone is not unique: two batches that both finish inside one second compute
  # the SAME `LAUNCH`, and the collision guard below then turns a legitimate
  # relight into a halt. Found by the stub proof on 2026-08-09 — batch 2 collided
  # with batch 1 and ended the run at 2 of 5 sessions. Real sessions take tens of
  # minutes so it would not have bitten tonight, which is exactly why it had to
  # be caught by a test rather than waited for.
  LOG="$LOG_DIR/${DATE}-${LAUNCH}-b${batch}-run${RUN}.log"

  # ⚠️ AND THE NAME IS ASSERTED, NOT TRUSTED. A filename scheme that silently
  # appends is exactly what this replaced, so the loop refuses to open a log
  # that already exists rather than quietly concatenating two launches again.
  if [ -e "$LOG" ]; then
    halt_reason="LOG COLLISION — $LOG already exists; refusing to append two launches into one file"
    break
  fi

  # ── KILL SWITCH 1 — checked FIRST, so a human always wins the race ────────
  if [ -f "$STOP_FILE" ]; then
    halt_reason="STOP FILE — $STOP_FILE appeared before session $RUN"
    break
  fi

  # F20 — sampled from `origin/main`, so it brackets the session rather than
  # trailing it.
  #
  # ⚠️ NO `|| true` HERE, AND THAT IS LOAD-BEARING. This script runs `set -uo
  # pipefail` WITHOUT `-e`, so a non-zero return does not end the run and needs
  # no rescue. Adding `|| true` would make `$?` the exit status of `true` —
  # ALWAYS 0 — silently disarming the cannot-tell arm and feeding the literal
  # string `CANNOT-TELL:fetch-failed` in as if it were a hash. That reads as
  # permanent progress: the exact inverse of the bug this fix exists for, wearing
  # the fix's own clothes. (Written down because the first draft of this line had
  # it.)
  ledger_before="$(ledger_progress_hash "$LEDGER")"
  ledger_before_rc=$?

  {
    echo "════════════════════════════════════════════════════════════════"
    echo "FOUNDATION session $RUN of $MAX_SESSIONS"
    echo "started : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "commit  : $(git rev-parse --short HEAD 2>/dev/null)"
    echo "branch  : $(git branch --show-current 2>/dev/null)"
    echo "ledger  : ${ledger_before:0:12} (origin/main)"
    echo "════════════════════════════════════════════════════════════════"
  } >> "$LOG"

  # ── INBOX — operational notices, DELIVERED MECHANICALLY ───────────────────
  # ⚠️ PRINTED INTO THE SESSION LOG BEFORE THE SESSION STARTS, so receipt cannot
  # be skipped and needs no new read-discipline from anybody. It exists because
  # there was NO inter-session channel at all: a session is a fresh process with
  # no memory, and anything written after its STEP 0 was invisible to it — a
  # supervised session could not tell a running one that `main` had moved.
  #
  # ⚠️ OPERATIONAL NOTICES ONLY. A ruling never travels this way; `RULINGS.md` is
  # the single source of truth and an inbox that can carry a decision is a second
  # one. The constraint is stated in the file's own header, which is printed with
  # every delivery so it cannot drift out of sight.
  #
  # ⚠️ FAIL-OPEN, DELIBERATELY. Missing, unreadable, or holding no entries: it
  # prints nothing and never blocks a launch. An inbox that could stop the
  # programme would be a worse bug than the problem it solves.
  #
  # ══════════════════════════════════════════════════════════════════════
  # SYNC THE SHARED TREE BEFORE READING THE INBOX. F13.
  # ----------------------------------------------------------------------
  # ⚠️ THE INBOX'S OWN HEADER CLAIMS delivery is "mechanical: receipt cannot be
  # skipped and requires no read-discipline from anybody." That was FALSE, and
  # false in exactly the case it exists for.
  #
  # This runner had NO git sync of any kind, and MASTER.md never instructed one.
  # It printed INBOX.md from the SHARED TREE, which only advanced because
  # sessions happened to `git merge --ff-only` it as an unwritten habit. So an
  # owner notice merged to `main` reached the loop only if some later session
  # chose to sync — which is read-discipline, wearing a mechanism's clothes.
  #
  # MEASURED 2026-08-17: the shared tree sat at 1537ae47 while origin/main was
  # 82f743ca — FOUR merges behind. An owner ruling (#123) and its INBOX pointer
  # for F12 were on main and INVISIBLE to the loop, and the next session would
  # have launched with the stale five entries and a RELAY with no F12 row.
  #
  # ⚠️ FAIL-LOUD, NOT FAIL-CLOSED. A stale tree is bad; a halted loop is worse,
  # and this is a delivery aid rather than a safety gate. So it never refuses:
  # it ff's when it safely can, and when it cannot it SAYS SO with the distance,
  # because "N commits behind" in the log is the thing that gets noticed.
  # ⚠️ AND IT IS `--ff-only`, ON `main`, AND ONLY WHEN CLEAN. A session may have
  # the shared tree checked out to a branch or dirty mid-item; moving it under
  # that session is the shared-tree hazard this house already has a rule for.
  # (plain `git` — the script cd's to the repo root at the top, so there is no
  #  $ROOT to pass; an earlier draft referenced one that does not exist, which
  #  bash would have accepted silently as an empty -C argument.)
  git fetch --quiet origin 2>/dev/null || true
  _branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')
  _dirty=$(git status --porcelain 2>/dev/null | wc -l)
  _behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo '?')
  if [ "$_behind" = "0" ]; then
    :
  elif [ "$_branch" = "main" ] && [ "$_dirty" = "0" ]; then
    if git merge --ff-only origin/main >/dev/null 2>&1; then
      echo "[loop] shared tree fast-forwarded $_behind commit(s) → $(git rev-parse --short HEAD)"
    else
      echo "[loop] ⚠️ shared tree is $_behind commit(s) behind origin/main and the ff FAILED."
      echo "[loop]    The INBOX and MASTER below may be STALE. Sync it by hand."
    fi
  else
    echo "[loop] ⚠️ shared tree is $_behind commit(s) behind origin/main and NOT synced:"
    echo "[loop]    branch=$_branch dirty=$_dirty — refusing to move it under a session."
    echo "[loop]    The INBOX and MASTER below may be STALE."
  fi

  # "Holding no entries" is COUNTED, not assumed — entries are
  # `### <ISO8601> — <title>` headings, so a file carrying only its own header
  # prints nothing, and a prose `### heading` does not trip it.
  if [ -r "$INBOX_FILE" ] && grep -qE '^### [0-9]{4}-[0-9]{2}-[0-9]{2}T' "$INBOX_FILE" 2>/dev/null; then
    {
      echo "──────────────── INBOX — operational notices ────────────────"
      cat "$INBOX_FILE"
      echo "──────────────── end INBOX ────────────────"
      echo
    } >> "$LOG"
    echo "[loop] inbox: $(grep -cE '^### [0-9]{4}' "$INBOX_FILE") entr(y|ies) delivered → $LOG"
  fi

  echo "[loop] session $RUN/$MAX_SESSIONS → $LOG"

  # Headless. The prompt is the committed file, read fresh each session so an
  # edit to MASTER.md takes effect on the next one without restarting the loop.
  # ⚠️ NO `--dangerously-skip-permissions`. The loop runs inside the project's
  # OWN allowlist (.claude/settings.json), which is bounded and reviewable in a
  # diff. That is not merely tidier — it is FAIL-CLOSED: an operation nobody
  # allowed cannot run, so the session reports a blocker and the loop halts,
  # instead of an unattended agent quietly doing something nobody sanctioned.
  # ⚠️ THE SESSION'S OUTPUT GOES TO ITS OWN FILE FIRST, AND THE MARKER IS READ
  # FROM THAT — never from the shared log.
  #
  # The first version of this appended straight to $LOG and then read the log's
  # last line. The loop's OWN bookkeeping line ("[loop] session 01 exited rc=0")
  # landed after the session output, so the runner read its own noise as the
  # marker and halted every run with NO MARKER. A perfectly good STOP-CONDITION
  # was reported as unreadable. Caught by the kill-switch test, not in
  # production — which is the entire reason those tests exist.
  SESSION_OUT="$(mktemp)"
  claude -p "$(cat "$PROMPT_FILE")" > "$SESSION_OUT" 2>&1
  rc=$?
  # Counted here, not on success: a session that errored still SPENT a session,
  # and a budget that only counts the happy path is not a bound on anything.
  sessions_used=$(( sessions_used + 1 ))

  cat "$SESSION_OUT" >> "$LOG"
  echo "" >> "$LOG"
  echo "[loop] session $RUN exited rc=$rc at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"

  # ── REPORT TRIPWIRE ────────────────────────────────────────────────────────
  # ⚠️ A SESSION'S FINAL MESSAGE IS THE ONLY ONE `claude -p` EMITS. A session
  # that writes its morning report and is then WOKEN AGAIN — by its own leftover
  # watcher, say — answers the wake-up, and that short answer becomes the whole
  # log. The work is fine, the marker is fine, the gates are green, and the
  # night is simply not in the record.
  #
  # It has happened TWICE, identically, both from a leftover watcher of the
  # session's own: batch 1 session 01 (2026-08-09, losing its SCRATCH LIST) and
  # batch 2 session 02 (2026-08-10, after landing B4's closing step and its
  # citation). 16 and 17 lines where their siblings run 43 to 82, each ending
  # "the morning report above stands" — where "above" was a turn nobody kept.
  # The first was spotted by the NEXT session and written down; nothing turned
  # it into a check, so it recurred a day later. Hence this.
  #
  # This does NOT halt. A missing report is a record defect, not a reason to
  # stop a run that is otherwise landing work. It is flagged HERE, in the halt
  # banner, and read by the next session's STEP 0 — because an alarm nobody is
  # obliged to read is how three red nights became background.
  report_lines="$(grep -cvE '^[[:space:]]*$' "$SESSION_OUT" 2>/dev/null || echo 0)"
  if ! grep -q 'MORNING REPORT' "$SESSION_OUT" 2>/dev/null; then
    reports_missing="$reports_missing $RUN"
    {
      echo ""
      echo "[loop] ⚠️ REPORT-MISSING — session $RUN produced no morning report"
      echo "       ($report_lines non-empty lines; no 'MORNING REPORT' header)."
      echo "       Its final message was the only one captured. If it was woken"
      echo "       after reporting, the report is GONE — reconstruct from git log,"
      echo "       RELAY.md and the PRs, and name it in the next report."
    } | tee -a "$LOG"
  fi

  if [ "$rc" -ne 0 ]; then
    halt_reason="SESSION ERROR — session $RUN exited rc=$rc"
    break
  fi

  # ── KILL SWITCH 3 — the marker ───────────────────────────────────────────
  # The LAST non-empty line, stripped. Anything but CONTINUE halts; so does an
  # unreadable one, because "I could not tell" must never mean "carry on".
  marker="$(grep -vE '^\s*$' "$SESSION_OUT" | tail -1 | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  echo "[loop] marker: '$marker'" | tee -a "$LOG"

  # ── MARKER RECOVERY — classify the session's OWN OUTPUT, never guess ──────
  # ⚠️ WHY THIS EXISTS. On 2026-08-09 a session did excellent work — STEP 0
  # passed, B1-b step 2 built, the gate mutation-proved four ways — then ended
  # its turn with a prose summary saying it would "wait on the e2e watcher".
  # There is no waiting: a headless session ENDS when its response ends. Its PR
  # sat green and mergeable for SIX HOURS while the loop was dead, because the
  # last line was not a marker. The work was excellent and the run still stopped.
  #
  # The cure is NOT to loosen the contract — an unreadable answer must never mean
  # "carry on". It is to ask a fresh session to READ what the dead one actually
  # produced and classify it. That is evidence, not a guess: the same judgement a
  # human makes reading the log. If it cannot tell, it says STOP-CONDITION and we
  # halt exactly as before.
  #
  # Bounded at 2 per run. A third means the contract is systematically broken,
  # and papering over that with a classifier is how a loop stops being auditable.
  case "$marker" in
    CONTINUE|STOP-CONDITION|"RULING NEEDED"|"OWNER ACTION"|"PHASE CLOSED") : ;;
    *)
      if [ "$recoveries_used" -ge 2 ]; then
        echo "[loop] marker unreadable and recovery budget spent ($recoveries_used) — halting" | tee -a "$LOG"
      else
        recoveries_used=$(( recoveries_used + 1 ))
        echo "[loop] marker unreadable — RECOVERY $recoveries_used/2: classifying the session's own output" | tee -a "$LOG"
        RECOVERED="$(claude -p "$(printf '%s\n\n----- SESSION OUTPUT BEGINS -----\n%s\n----- SESSION OUTPUT ENDS -----\n' \
'A FOUNDATION session just finished but failed to end with its required marker line. Below is its COMPLETE output. Read it and decide which single marker honestly describes what it achieved.

CONTINUE       real progress was made and the next item is ready to start
STOP-CONDITION a blocker survived cure attempts, or the session could not proceed
RULING NEEDED  a ruling-shaped decision it could not make itself
OWNER ACTION   a hard-halt item is next
PHASE CLOSED   the phase is complete end-to-end

Judge ONLY from what the output says. Do not infer beyond it. If you genuinely cannot tell, answer STOP-CONDITION — halting is the safe error.

Reply with EXACTLY ONE of those markers and NOTHING else: no punctuation, no explanation, no code fence.' "$(cat "$SESSION_OUT")")" 2>/dev/null | grep -vE '^\s*$' | tail -1 | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
        case "$RECOVERED" in
          CONTINUE|STOP-CONDITION|"RULING NEEDED"|"OWNER ACTION"|"PHASE CLOSED")
            echo "[loop] RECOVERED marker: '$RECOVERED' (classified from the session's output, not asserted by it)" | tee -a "$LOG"
            marker="$RECOVERED" ;;
          *)
            echo "[loop] recovery FAILED — classifier returned '$RECOVERED'; halting on the original unreadable answer" | tee -a "$LOG" ;;
        esac
      fi ;;
  esac
  rm -f "$SESSION_OUT"

  case "$marker" in
    CONTINUE) : ;;
    STOP-CONDITION|"RULING NEEDED"|"OWNER ACTION"|"PHASE CLOSED")
      halt_reason="MARKER — $marker (session $RUN)"; break ;;
    *)
      halt_reason="NO MARKER — session $RUN ended with '$marker'; refusing to continue on an unreadable answer"
      break ;;
  esac

  # ── KILL SWITCH 4 — no-progress ──────────────────────────────────────────
  # F20 — the CLOSING sample, taken from `origin/main` like the opening one, so
  # the pair brackets the session that is being judged. See the note by
  # `ledger_before` on why there is no `|| true`.
  ledger_after="$(ledger_progress_hash "$LEDGER")"
  ledger_after_rc=$?

  if [ "$ledger_before_rc" -ne 0 ] || [ "$ledger_after_rc" -ne 0 ]; then
    # ⚠️ NOT A NO-PROGRESS HALT. Neither sample says anything about the session.
    # Reported LOUDLY — a switch that goes quiet when it goes blind is the
    # failure this whole item is about.
    cannottell_streak=$((cannottell_streak + 1))
    {
      echo ""
      echo "⚠️ LEDGER PROGRESS: CANNOT TELL (${cannottell_streak}/${CANNOTTELL_LIMIT})."
      echo "   before: $ledger_before"
      echo "   after : $ledger_after"
      echo "   This is NOT scored as no-progress — a failed fetch is evidence"
      echo "   about the network, not about session $RUN. The streak is what"
      echo "   halts, not the single blind sample."
    } >> "$LOG"
    if [ "$cannottell_streak" -ge "$CANNOTTELL_LIMIT" ]; then
      halt_reason="LEDGER-UNREADABLE — $LEDGER could not be read on origin/main for $cannottell_streak consecutive sessions (through $RUN)"
      {
        echo ""
        echo "🔴 LEDGER-UNREADABLE HALT."
        echo "   The progress signal has been unmeasurable for $cannottell_streak sessions."
        echo "   The loop is not being judged at all, so it stops rather than"
        echo "   running on with its one anti-spin switch disarmed."
      } >> "$LOG"
      break
    fi
    # A blind sample cannot anchor a streak in either direction.
    noprogress_streak=0
  elif [ "$ledger_after" = "$ledger_before" ]; then
    # ⚠️ RESET HERE TOO, NOT ONLY ON THE PROGRESS PATH. The limit reads
    # "N CONSECUTIVE", and a reset that lives only in the final `else` would let
    # three cannot-tells scattered across a whole night — each one separated by a
    # perfectly measured session — add up to a halt that never happened
    # consecutively. A counter whose name says "consecutive" and whose code
    # accumulates is this house's own wrong-quantity defect. (First draft had it.)
    cannottell_streak=0
    noprogress_streak=$((noprogress_streak + 1))
    if [ "$noprogress_streak" -ge 2 ]; then
      halt_reason="NO-PROGRESS — $LEDGER unchanged on origin/main across two consecutive sessions (through $RUN)"
      {
        echo ""
        echo "🔴 NO-PROGRESS HALT."
        echo "   The session reported CONTINUE, but $LEDGER on origin/main is"
        echo "   byte-identical from the start of the session to its end, for a"
        echo "   second consecutive run. By this programme's rules an item is not"
        echo "   finished until its ledger row lands, so no item finished."
        echo "   CONTINUE is a claim about PROGRESS, not about effort."
        echo "   ledger (origin/main): $ledger_before"
      } >> "$LOG"
      break
    fi
  else
    noprogress_streak=0
    cannottell_streak=0
  fi
done

  # ── BATCH BOUNDARY — RELIGHT, or carry the halt outward ──────────────────
  # Reaching the cap with no halt_reason means every session in the batch ended
  # on CONTINUE. That is the ONLY condition that relights: every other exit —
  # marker, session error, no-progress, log collision, STOP — propagates and
  # ends the night. The relight cannot resurrect a run that something stopped.
  if [ -n "$halt_reason" ]; then
    overall_halt="$halt_reason"
    break
  fi
  echo "[loop] batch $batch reached the cap on CONTINUE — relighting (${sessions_used}/${TOTAL_BUDGET} sessions used)"
done

[ -z "$overall_halt" ] && overall_halt="BUDGET EXHAUSTED — $sessions_used of $TOTAL_BUDGET sessions used"
halt_reason="$overall_halt"

# ⚠️ THE HALT BANNER GOES IN THE LAST LOG THAT ACTUALLY RAN.
# The first version computed the filename from the loop counter, so halting
# BEFORE session 02 created a `run02.log` containing nothing but a halt banner —
# a report for a session that never happened. These logs are the war-room
# record; a phantom entry in one is worse than a missing one.
FINAL="$(ls -1t "$LOG_DIR"/*.log 2>/dev/null | head -1)"
[ -z "$FINAL" ] && FINAL="$LOG_DIR/${DATE}-halt.log"
{
  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "LOOP HALTED : $halt_reason"
  echo "at          : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  [ -n "$reports_missing" ] && echo "REPORT-MISSING:$reports_missing  ← these sessions' nights are NOT in the record"
  echo "commit      : $(git rev-parse --short HEAD 2>/dev/null)"
  echo "════════════════════════════════════════════════════════════════"
} | tee -a "$FINAL"

echo "[loop] halted: $halt_reason"
