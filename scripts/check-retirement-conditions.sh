#!/usr/bin/env bash
# ============================================================================
# F30 — RETIREMENT CONDITIONS ARE TESTED, NOT REMEMBERED. READ-ONLY.
#   0 = nothing is due   1 = a FINDING (something is DUE, or an entry is
#                            UNREGISTERED)   2 = can't tell
# ----------------------------------------------------------------------------
# WHAT THIS IS FOR
#
# `INBOX.md` is printed into EVERY session's log at launch. An entry that has
# met its own retirement condition and is still being delivered is not merely
# untidy — canon records two distinct costs, and the second is the expensive
# one:
#
#   · an expired TASK wastes a session (session 04 of run04 spent its whole
#     run establishing that work already done was already done, landed nothing,
#     and the loop then sat dark);
#   · an expired PERMISSION is worse, because a session that OBEYS it does the
#     forbidden thing correctly. The F10 carry-forward clause licenses writing
#     a §2.5 declaration into the SHARED TREE — the deploy surface.
#
# ⚠️ THE ARGUMENT FOR MECHANISING IT IS THAT FOUR SEPARATE SESSIONS FOUND STALE
# ENTRIES **BY HAND**, each while waiting on a gate, and each time the finding
# was filed and the entry stayed. A retirement condition nobody executes is the
# EXEMPTION-DECAY class: canon already says the cure for a decaying exemption is
# to write its retiring condition as a testable event — and this is the other
# half of that sentence. **A testable event that nothing tests is still prose.**
#
# ── REPORT-ONLY, DELIBERATELY ───────────────────────────────────────────────
# It prints a list and changes NOTHING. A sweep that auto-deleted entries on a
# heuristic would eventually delete a live one, and a wrong deletion is a worse
# failure than a stale entry. The loop also never writes `INBOX.md` at all.
#
# ── ⚠️ IT PARTITIONS **ENTRIES**, NEVER GREPPED LINES — AND THAT IS THE WHOLE
#    DESIGN, NOT AN IMPLEMENTATION DETAIL ─────────────────────────────────────
# The obvious build is `grep -c "retires when"`. It is wrong in BOTH directions
# on today's file, measured:
#
#   OVER-counts  three lines inside the very entry that PROPOSED this sweep are
#                prose ABOUT retirement clauses — `**"retires when"** clauses
#                and TESTS each one`, and a quotation of another entry's clause.
#                A legend is not a row.
#   UNDER-counts the F10 pointer's clause reads *"The exception retires WITH
#                F10"*. Not "retires when". It is the single entry F23's session
#                called "the one that matters", and a token sweep drops it.
#
# That is canon's COUNTING TOKENS INSTEAD OF CLASSIFYING ROWS, and it would have
# been committed by the sweep written to cure exactly that family. So the unit
# here is the ENTRY — anchored on the `### <ISO8601> — <title>` heading the
# launcher itself counts — and every entry lands in exactly one named bucket.
#
# ── THE REGISTRY, AND WHY A HAND-KEPT LIST IS SAFE **HERE** ─────────────────
# Deciding what an English clause MEANS is a human judgement. Executing it is
# not. So the judgement is recorded ONCE, in this file, reviewable in a PR — and
# the execution runs every session.
#
# ⚠️ Canon says hand-kept lists go stale. The defence is SET-EQUALITY, the same
# ratchet F24 closed on: the registry's keys and the file's entry timestamps
# must be EQUAL. An entry with no registry row is a FINDING (exit 1), and a
# registry row naming an entry that no longer exists is a FINDING. Neither
# direction can rot quietly, which is the property a bare list lacks.
#
# ── HONEST LIMITS, NAMED SO THIS IS NOT READ WIDER THAN IT IS ───────────────
#   · IT SCANS `INBOX.md` ONLY. The filing item named `RELAY.md` too. RELAY is
#     ~29k lines and its clauses sit mostly inside CLOSED historical rows, so
#     covering it needs its own registry and its own judgement pass; doing it by
#     token-grep would re-commit the exact defect described above. **Named
#     residue, not a silent cap** — a named gap beats a green that cannot fail.
#   · `relay_closed:<ID>` APPROXIMATES "the item is closed" by looking for a
#     `#+ (✅|🟢) <ID> —` heading across the ledger's live head AND its archives
#     under `docs/foundation/relay/` (see the watched-set note below). It is a
#     predicate over the ledger's own vocabulary, not over the code. Verified to DISCRIMINATE on
#     today's file: F10 2, F23 3, F24 1, and **F12 0 while F12-g is open** —
#     sub-items (`F12-a`) do not match their parent.
#   · A `human:` row is a REFUSAL to guess, not a pass. Those entries are
#     printed every run so they stay visible.
#   · It says nothing about whether an entry SHOULD have been written.
#
# ── ⚠️ HOW TO RUN IT, AND THE GRANT THAT IS NOT YET SHIPPED ────────────────
# `.claude/settings.json` names permitted scripts one by one and is PROTECTED
# from the layer it governs, so the unattended session that wrote this file
# could not ship its own grant — the same structural gap already recorded for
# `check-em-note-shape-artifacts.sh`. Canon's *"an entry that names an
# instrument verifies that instrument's grant in the same commit"* is
# unreachable from this side, and saying so is the honest half.
#
#   OWNER ACTION, one line:
#       "Bash(bash scripts/check-retirement-conditions.sh:*)"
#   then add it to MASTER.md STEP 0.5's standing-check list — NOT before, or
#   the loop meets a rule whose instrument is refused, which is the backfire
#   canon names.
#
#   GRANTED FALLBACK until then — this sweep runs on EVERY PR through its own
#   gate, which drives this script with `execFileSync`:
#       cd apps/transcribe-md
#       npx vitest run src/lib/__tests__/gate-f30-retirement-conditions.test.ts
#
# ⚠️ Do NOT tunnel this file through `node -e` or `python3 -c` to get around
# the refusal. That is the sanctioned-hatch-becomes-the-undisciplined-door
# failure, and the gate above is a real, reviewable route that already works.
# ============================================================================
set -uo pipefail

# ⚠️ F28: resolve the root from THIS SCRIPT'S OWN LOCATION, never the caller's.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || {
  echo "🟡 check-retirement-conditions: cannot resolve this script's own root — can't tell"; exit 2; }
cd "$ROOT" || {
  echo "🟡 check-retirement-conditions: cannot enter $ROOT — can't tell"; exit 2; }

INBOX="docs/foundation/INBOX.md"
LEDGER="docs/foundation/RELAY.md"
LEDGER_DIR="docs/foundation/relay"

[ -r "$INBOX" ]  || { echo "🟡 $INBOX is not readable — can't tell";  exit 2; }
[ -r "$LEDGER" ] || { echo "🟡 $LEDGER is not readable — can't tell"; exit 2; }

# ── ⚠️ THE WATCHED SET IS THE LIVE HEAD **PLUS** THE ARCHIVES ───────────────
# The 2026-08-26 split moved every CLOSED arc out of `RELAY.md` and into
# `docs/foundation/relay/`. A closure heading is BY DEFINITION in a closed arc,
# so after the split the live head carries almost none of them — and this
# script's whole `relay_closed:` predicate is a search for closure headings.
#
# Read against the head alone the sweep did not err loudly, which is the part
# worth remembering: its vocabulary control went to 0, it fail-closed at exit 2,
# and the DUE list quietly went 4 -> 2. F10's and F23's MET conditions became
# invisible — the exact "an expired entry is still delivered to every session"
# harm this sweep was built to price.
#
# The set degrades correctly in BOTH directions: where the archive directory
# does not exist (any pre-split tree, and any other checkout of this repo) the
# set is exactly `$LEDGER` and behaviour is byte-identical to before.
declare -a LEDGER_SET=("$LEDGER")
if [ -d "$LEDGER_DIR" ]; then
  while IFS= read -r _f; do
    [ -r "$_f" ] && LEDGER_SET+=("$_f")
  done < <(find "$LEDGER_DIR" -maxdepth 1 -type f -name '*.md' | sort)
fi
LEDGER_LABEL="$LEDGER"
[ "${#LEDGER_SET[@]}" -gt 1 ] && LEDGER_LABEL="the ledger (head + $(( ${#LEDGER_SET[@]} - 1 )) archive files)"

# ----------------------------------------------------------------------------
# THE REGISTRY — one row per INBOX entry. `<timestamp>|<predicate>|<note>`
#
# predicate kinds:
#   retired                    the entry's own heading declares it retired
#   none                       a one-shot notice; it states no condition
#   human:<why>                real condition, NOT machine-checkable from here
#   relay_closed:<ID>          RELAY carries a ✅/🟢 closure heading for <ID>
#   merged:<branch>:<path>     branch gone from origin AND <path> on origin/main
#   file_exists:<path>         <path> exists in this tree
#
# ⚠️ EVERY ROW'S NOTE IS PRINTED, AND IT SAYS `STATED` OR `INFERRED`.
# `STATED` quotes the entry's own retirement clause. `INFERRED` means the entry
# states NO clause and the condition below is this registry's READING of it —
# which is a judgement somebody must be able to disagree with. Hiding that
# distinction would let an inferred condition retire a live entry while looking
# like the entry's own words.
# ----------------------------------------------------------------------------
REGISTRY=(
"2026-08-13T20:38:44Z|none|STATED none — a standing reconciliation FACT for B9 (the 176th grant). It must OUTLIVE the queue; it is not a task"
"2026-08-14T20:09:13Z|retired|STATED — already struck through by the owner 2026-08-20"
"2026-08-15T04:18:34Z|none|STATED none — one-shot handoff notice"
"2026-08-16T08:10:00Z|none|STATED none — one-shot; it exists to retire a clause in ANOTHER entry"
"2026-08-16T19:30:00Z|relay_closed:F10|STATED 'The exception retires WITH F10' — the clause a 'retires when' token sweep drops"
"2026-08-17T12:00:00Z|relay_closed:F12|INFERRED — the entry is a POINTER to ruling #123 and states no clause; read as retiring when F12 closes"
"2026-08-18T07:00:00Z|merged:feat/twin-auto-certification:apps/transcribe-md/src/lib/template-twin/auto-certify.ts|STATED 'This entry retires when that branch merges'"
"2026-08-20T01:45:00Z|retired|STATED — already struck through 2026-08-20"
"2026-08-20T15:30:00Z|human:needs a PRODUCTION DB READ (has the owner's template CERTIFIED) and the loop has no granted database route|STATED 'retires when the owner's template certifies'"
"2026-08-20T16:40:00Z|file_exists:scripts/check-retirement-conditions.sh|STATED 'retires when the sweep prints its first list' — this script IS that sweep"
"2026-08-20T23:00:00Z|human:a judgement about whether a second actor EXTENDED rather than duplicated a claim|STATED 'when a claim line appears on a ruled fix direction and the second actor extends it'"
"2026-08-20T23:10:00Z|human:behavioural — needs a reflux cell to fill from a fact whose quote does not name the vessel|STATED 'Retires when a reflux cell fills…'"
"2026-08-21T09:00:00Z|human:needs a PRODUCTION DB READ (has a SECOND template shape certified end to end)|STATED 'when a second SHAPE certifies end-to-end'"
"2026-08-21T12:20:00Z|relay_closed:F23|INFERRED — states no clause, but its point 2 reads 'The script does not exist yet — F23 builds it', which became FALSE when F23 landed. A false PRESENT-TENSE fact, delivered to every session"
"2026-08-24T15:25:10Z|none|STATED none — one-shot union notice for a single named PR"
"2026-09-04T22:05:00Z|file_exists:scripts/check-worktree-resolution.sh|STATED 're-run after the harness fix' — the notice retires once every affected lane has re-run its packages/* measurements. The probe existing is the CONDITION being pointed at, not the retirement itself: the lanes must still re-run. Retire by hand once Design/Admin and Data/Audit confirm, and not before"
)

# ── read the entries the LAUNCHER counts: `### <ISO8601> — <title>` ──────────
mapfile -t HEADINGS < <(grep -E '^### [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z' "$INBOX")

# ⚠️ NON-VACUITY FIRST. A regex that silently matched nothing would make every
# bucket below empty and the partition would reconcile perfectly at zero.
# NEVER normalise an impossible value into a plausible one.
if [ "${#HEADINGS[@]}" -lt 5 ]; then
  echo "🟡 only ${#HEADINGS[@]} INBOX entries parsed — the matcher is not reading this file. Can't tell."
  exit 2
fi
if ! printf '%s\n' "${HEADINGS[@]}" | grep -q '2026-08-20T16:40:00Z'; then
  echo "🟡 positive control FAILED — the known entry 2026-08-20T16:40:00Z was not parsed. Can't tell."
  exit 2
fi

echo "retirement-condition sweep — $INBOX"
echo "   · parsed ${#HEADINGS[@]} entries · positive control: known member 2026-08-20T16:40:00Z found"
# ⚠️ INSTRUMENTATION, ADDED 2026-08-31 — NO VERDICT LOGIC DEPENDS ON IT.
#
# `gate-f30` went RED twice in CI on one unchanged tree, naming a DIFFERENT
# orphan each time (2026-08-20T15:30:00Z, then 2026-08-16T19:30:00Z) — and both
# entries are present. A CI-shaped shallow clone of the exact merge ref parses
# 15/15 with no orphan; 25 consecutive local runs are clean; a static sweep of
# the suite finds NO writer to this file, no chdir, and no shell redirect into
# it. So the failure is real, non-deterministic, and unexplained.
#
# Every hypothesis died for want of ONE fact: what the sweep actually READ in
# CI. The census below is that fact. It prints the timestamps this run parsed,
# in order, so a future red carries its own evidence instead of requiring the
# reader to reconstruct it — the difference between "an entry is missing" and
# "the registry has rotted" is exactly what these two lines settle.
echo "   · census(${#HEADINGS[@]}): $(printf '%s\n' "${HEADINGS[@]}" | sed -E 's/^### ([0-9T:-]+Z).*/\1/' | tr '\n' ' ')"
echo "   · registry(${#REGISTRY[@]}): $(printf '%s\n' "${REGISTRY[@]}" | cut -d'|' -f1 | tr '\n' ' ')"

# ── instrument controls for the predicates that consult something external ───
NET_OK=0
if git ls-remote --heads origin main 2>/dev/null | grep -q 'refs/heads/main'; then NET_OK=1; fi
# ⚠️ A SECOND, SEPARATE CONTROL — and it is not implied by the first.
# `merged:` asks TWO questions: is the branch gone (network), and is the file on
# `origin/main` (a LOCAL ref). A CI checkout is routinely shallow or
# single-branch, so `origin/main` may not resolve even with the network up. With
# no control, `git cat-file -e origin/main:<path>` failing for THAT reason is
# indistinguishable from the file genuinely being absent — two states collapsed
# into one, which is this house's most-repeated defect, and it would report a
# met condition as NOT MET without ever saying it could not tell.
REF_OK=0
if git rev-parse --verify --quiet origin/main >/dev/null 2>&1; then REF_OK=1; fi
LEDGER_OK=0
if grep -qE '^#+ (✅|🟢) F[0-9]+ —' "${LEDGER_SET[@]}"; then LEDGER_OK=1; fi
echo "   · controls: origin reachable=$NET_OK · origin/main resolvable=$REF_OK · ledger closure-vocabulary present=$LEDGER_OK ($LEDGER_LABEL)"
echo

declare -a B_DUE=() B_NOTDUE=() B_HUMAN=() B_NONE=() B_RETIRED=() B_UNREG=() B_CANT=()

registry_for() {
  local ts="$1" row
  for row in "${REGISTRY[@]}"; do
    case "$row" in "$ts|"*) printf '%s' "${row#*|}"; return 0 ;; esac
  done
  return 1
}

for h in "${HEADINGS[@]}"; do
  ts="$(printf '%s' "$h" | sed -E 's/^### ([0-9T:-]+Z).*/\1/')"
  title="$(printf '%s' "$h" | sed -E 's/^### [0-9T:-]+Z (— )?//' | cut -c1-58)"

  if ! spec="$(registry_for "$ts")"; then
    B_UNREG+=("$ts  $title"); continue
  fi
  pred="${spec%%|*}"
  note="${spec#*|}"

  case "$pred" in
    retired)
      # Cross-checked against the FILE, never taken from the registry's word.
      if printf '%s' "$h" | grep -q 'RETIRED'; then B_RETIRED+=("$ts  $title")
      else B_UNREG+=("$ts  $title   ⚠️ registry says RETIRED; the heading does not"); fi
      ;;
    none)
      B_NONE+=("$ts  $title
        └─ $note")
      ;;
    human:*)
      B_HUMAN+=("$ts  $title
        └─ $note
        └─ CANNOT CHECK: ${pred#human:}")
      ;;
    relay_closed:*)
      id="${pred#relay_closed:}"
      if [ "$LEDGER_OK" -ne 1 ]; then B_CANT+=("$ts  $title   (ledger vocabulary control failed)")
      elif grep -qE "^#+ (✅|🟢) ${id} —" "${LEDGER_SET[@]}"; then B_DUE+=("$ts  $title
        └─ $note
        └─ MET: $LEDGER_LABEL carries a closure heading for ${id}")
      else B_NOTDUE+=("$ts  $title
        └─ $note
        └─ NOT MET: no closure heading for ${id} in $LEDGER_LABEL — the item is still open"); fi
      ;;
    merged:*)
      rest="${pred#merged:}"; br="${rest%%:*}"; path="${rest#*:}"
      if [ "$NET_OK" -ne 1 ]; then B_CANT+=("$ts  $title   (origin unreachable — a branch cannot be called GONE)")
      elif [ "$REF_OK" -ne 1 ]; then B_CANT+=("$ts  $title   (origin/main does not resolve here — 'file absent' and 'ref missing' are NOT the same answer)")
      else
        gone=1; git ls-remote --heads origin "$br" 2>/dev/null | grep -q "refs/heads/$br" && gone=0
        landed=0; git cat-file -e "origin/main:$path" 2>/dev/null && landed=1
        if [ "$gone" -eq 1 ] && [ "$landed" -eq 1 ]; then
          B_DUE+=("$ts  $title
        └─ $note
        └─ MET: $br is gone from origin AND $path is on origin/main")
        else
          B_NOTDUE+=("$ts  $title
        └─ $note
        └─ NOT MET: branch-gone=$gone file-on-main=$landed — both are required")
        fi
      fi
      ;;
    file_exists:*)
      p="${pred#file_exists:}"
      if [ -e "$p" ]; then B_DUE+=("$ts  $title
        └─ $note
        └─ MET: $p exists")
      else B_NOTDUE+=("$ts  $title
        └─ $note
        └─ NOT MET: $p does not exist"); fi
      ;;
    *)
      B_CANT+=("$ts  $title   (unknown predicate '$pred')")
      ;;
  esac
done

# ── a registry row naming an entry that is GONE is the other rot direction ───
declare -a ORPHANS=()
for row in "${REGISTRY[@]}"; do
  rts="${row%%|*}"
  # -F: a timestamp is a FIXED string, never a pattern. `grep -q` would also
  # match it appearing anywhere in a heading's title text.
  printf '%s\n' "${HEADINGS[@]}" | grep -qF "### $rts" || ORPHANS+=("$rts")
done

emit() {
  local label="$1"; shift
  [ "$#" -eq 0 ] && return 0
  echo "$label"
  printf '   %s\n' "$@"
  echo
}

emit "✅ DUE FOR RETIREMENT — the condition each entry set for itself is MET:" "${B_DUE[@]}"
emit "⛔ NOT DUE — the condition is demonstrably NOT met (this bucket is the control):" "${B_NOTDUE[@]}"
emit "👤 NEEDS A HUMAN — a real condition this layer cannot check. NOT a pass:" "${B_HUMAN[@]}"
emit "· NO CONDITION — one-shot notices and standing facts:" "${B_NONE[@]}"
emit "· ALREADY RETIRED:" "${B_RETIRED[@]}"
emit "🔴 UNREGISTERED — an entry with no registry row. THE LIST HAS GONE STALE:" "${B_UNREG[@]}"
emit "🟡 CANNOT TELL — an instrument control failed:" "${B_CANT[@]}"
emit "🔴 ORPHANED REGISTRY ROWS — they name entries that no longer exist:" "${ORPHANS[@]}"

total=$(( ${#B_DUE[@]} + ${#B_NOTDUE[@]} + ${#B_HUMAN[@]} + ${#B_NONE[@]} \
        + ${#B_RETIRED[@]} + ${#B_UNREG[@]} + ${#B_CANT[@]} ))

echo "THE PARTITION — every entry lands in exactly one bucket:"
printf '     due %d · not-due %d · needs-human %d · no-condition %d · retired %d · unregistered %d · cannot-tell %d\n' \
  "${#B_DUE[@]}" "${#B_NOTDUE[@]}" "${#B_HUMAN[@]}" "${#B_NONE[@]}" \
  "${#B_RETIRED[@]}" "${#B_UNREG[@]}" "${#B_CANT[@]}"
printf '     %d == %d entries parsed\n\n' "$total" "${#HEADINGS[@]}"

# ARITHMETIC THAT DOES NOT RECONCILE IS A FINDING.
if [ "$total" -ne "${#HEADINGS[@]}" ]; then
  echo "🟡 the partition does NOT reconcile — there is an unnamed bucket. Can't tell."
  exit 2
fi

if [ "${#B_CANT[@]}" -gt 0 ]; then
  echo "🟡 at least one predicate could not be evaluated — can't tell."
  exit 2
fi
if [ "${#B_UNREG[@]}" -gt 0 ] || [ "${#ORPHANS[@]}" -gt 0 ]; then
  echo "🔴 the registry and $INBOX have DIVERGED — register the entries above (or drop the orphans)."
  echo "   This is a finding about the SWEEP, not about the entries."
  exit 1
fi
if [ "${#B_DUE[@]}" -gt 0 ]; then
  echo "🔴 ${#B_DUE[@]} entry(ies) have met their own retirement condition and are STILL being"
  echo "   delivered to every session. Retiring them is a SUPERVISED action — move each to"
  echo "   docs/foundation/inbox-archive/ after confirming delivery. The loop never writes INBOX.md."
  exit 1
fi

echo "🟢 nothing is due — every entry either has no condition, is already retired,"
echo "   or has a condition that is demonstrably not yet met."
exit 0
