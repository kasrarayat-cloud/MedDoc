#!/usr/bin/env bash
# ============================================================================
# THE PING HALF OF PARK-AND-PING — reaches the owner's phone.
# ----------------------------------------------------------------------------
#   bash scripts/notify.sh <class> <one-line message>
#
#   halt       🔴 urgent   the loop stopped and will not resume itself
#   needs-you  🟡 high     owner-class park — a decision only he can make
#   waiting    🟡 default  a WAITING state that may clear on its own
#   ok         🟢 low      a milestone landed
#   heartbeat  ⚪ min      the daily "still alive", so silence is never ambiguous
#
# ⚠️ A NOTIFIER MUST NEVER BLOCK OR CRASH THE THING IT REPORTS ON. Every network
# call is bounded at 5s and every failure is swallowed; this script exits 0 come
# what may. A deploy that dies because its own success message could not be
# delivered is a worse outcome than a missed message, and that trade is not close.
#
# ⚠️ TRANSPORT IS ONE FUNCTION, DELIBERATELY. If the owner says "telegram", only
# `send_transport` changes — every call site, class and wiring stays put.
# ============================================================================
set -uo pipefail

# The topic is an unguessable string and it is the ONLY credential: anyone
# holding it can publish to, and subscribe to, this channel. It lives here rather
# than in an ignored file so a fresh clone is not silently mute — the failure
# mode where a notifier "works" and reaches nobody. The repository is private.
# Override with QUILLMD_NTFY_TOPIC to point a test elsewhere.
TOPIC="${QUILLMD_NTFY_TOPIC:-quillmd-46taoo2esklz}"
NTFY_BASE="${QUILLMD_NTFY_BASE:-https://ntfy.sh}"
TIMEOUT=5

send_transport() {  # $1=title $2=body $3=priority $4=tags
  command -v curl >/dev/null 2>&1 || return 0
  curl -fsS -m "$TIMEOUT" \
    -H "Title: $1" -H "Priority: $3" -H "Tags: $4" \
    -d "$2" "$NTFY_BASE/$TOPIC" >/dev/null 2>&1 || true
  return 0
}

main() {
  local class="${1:-ok}"; shift || true
  local msg="${*:-(no message)}"
  local host; host="$(hostname 2>/dev/null || echo '?')"
  local emoji prio tags
  case "$class" in
    halt)      emoji="🔴"; prio="urgent";  tags="rotating_light" ;;
    needs-you) emoji="🟡"; prio="high";    tags="raising_hand"   ;;
    waiting)   emoji="🟡"; prio="default"; tags="hourglass"      ;;
    ok)        emoji="🟢"; prio="low";     tags="white_check_mark" ;;
    heartbeat) emoji="⚪"; prio="min";     tags="heartbeat"      ;;
    # ⚠️ AN UNKNOWN CLASS IS NOT A LOW-PRIORITY MESSAGE. IT IS A BUG IN THE
    # CALLER, AND IT MUST NOT BE DELIVERED QUIETLY.
    #
    # MEASURED 2026-09-01: a session paged the owner about a live CI outage and
    # passed the EMOJI (`🟡`) instead of the class NAME. It matched nothing, fell
    # to this arm, and went out at LOW priority — which on a phone is silent. The
    # alarm was correct, the routing was correct, and it would simply never have
    # been seen. The session caught it only by reading its own output.
    #
    #     A MISADDRESSED ALARM MUST FAIL LOUD. The failure mode of a notifier is
    #     silence, and silence is exactly what a wrong class bought here.
    #
    # So an unrecognised class is escalated to `needs-you`, not demoted — the
    # sender clearly wanted attention, and the safe error is a message that is
    # too loud rather than one nobody sees. The refusal goes to stderr WITH the
    # valid class list, so the caller learns; the message is still delivered,
    # because dropping somebody's alarm to punish their typo is worse than both.
    *)
      echo "[notify] ⚠️ UNKNOWN CLASS '$class' — sending as needs-you." >&2
      echo "[notify]    valid: halt | needs-you | waiting | ok | heartbeat" >&2
      echo "[notify]    (pass the NAME, not the emoji)" >&2
      class="needs-you"; emoji="🟡"; prio="high"; tags="raising_hand"
      ;;
  esac
  # One line. A phone notification that needs scrolling has already failed.
  send_transport "$emoji QuillMD · $class" "$msg" "$prio" "$tags"
  echo "[notify] $emoji $class: $msg (host $host)" >&2
}

main "$@"
exit 0
