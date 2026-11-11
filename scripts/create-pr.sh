#!/usr/bin/env bash
# ============================================================================
# THE ONLY DOOR FOR `gh pr create`. IT REFUSES BEFORE IT CREATES.
# ----------------------------------------------------------------------------
# 0 = created (and verified) · 1 = REFUSED, or the create failed · 2 = can't tell
#
# ── WHY THIS EXISTS ────────────────────────────────────────────────────────
# Canon 48: GitHub's linked-issue parser has NO CONCEPT OF NEGATION — or of
# tense, or of narration. A body that says a body DENYING that it fixes a numbered issue, or one NARRATING that GitHub
# itself closed a numbered pull request, carries a closing keyword next to an
# issue number, and the parser does not read English.
#
# ⚠️ THE GUARD EXISTED AND WAS RUN POST-HOC, TWICE, BY THE SAME SESSION.
# Both times the grep was piped after `gh pr create` had already run — so it
# reported on a PR that was already open. The first instance named a PR that was
# already closed; the second was narrative. Neither did harm, and neither was
# prevented: the check was performed correctly and could not have stopped
# anything, because it ran second.
#
# **A rule that depends on remembering has a failure rate** (canon 93). This is
# that rule made mechanical: the scan runs BEFORE the create, and a match is a
# REFUSAL rather than a warning printed next to a URL.
#
# ── AND PROSE IS NEVER A SHELL ARGUMENT ────────────────────────────────────
# `--body` is refused outright. A body reaches this script as a FILE or not at
# all, because backticks in prose are command substitutions waiting for a shell
# and prose is exactly where backticks live.
# ============================================================================
set -uo pipefail

BASE=""; HEAD=""; TITLE=""; BODY_FILE=""; DRAFT=""; CHECK_ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="${2:-}"; shift 2 ;;
    --head) HEAD="${2:-}"; shift 2 ;;
    --title) TITLE="${2:-}"; shift 2 ;;
    --body-file) BODY_FILE="${2:-}"; shift 2 ;;
    --draft) DRAFT="--draft"; shift ;;
    --check) CHECK_ONLY="1"; shift ;;
    --body)
      echo "🔴 REFUSED — --body is not accepted. PROSE IS NEVER A SHELL ARGUMENT."
      echo "   Write the body to a file and pass --body-file. Backticks in prose are"
      echo "   command substitutions waiting for a shell, and prose is where they live."
      exit 1 ;;
    *) echo "🟡 CANNOT TELL — unknown argument '$1'"; exit 2 ;;
  esac
done

for pair in "BASE:--base" "HEAD:--head" "TITLE:--title" "BODY_FILE:--body-file"; do
  var="${pair%%:*}"; flag="${pair##*:}"
  if [ -z "${!var}" ]; then echo "🟡 CANNOT TELL — $flag is required"; exit 2; fi
done
[ -r "$BODY_FILE" ] || { echo "🟡 CANNOT TELL — cannot read body file '$BODY_FILE'"; exit 2; }

# ── THE GUARD, AND IT RUNS FIRST ───────────────────────────────────────────
# GitHub's closing syntax: keyword, optional colon, whitespace, then #N or
# owner/repo#N or a full issue URL. Matched case-insensitively, because the
# parser is.
KEYWORDS='close[sd]?|closes|fix|fixes|fixed|resolve[sd]?'
PATTERN="(${KEYWORDS})[[:space:]]*:?[[:space:]]+([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)?#[0-9]+"
URLPATTERN="(${KEYWORDS})[[:space:]]*:?[[:space:]]+https://github\.com/[^ ]+/issues/[0-9]+"

MATCHES="$(grep -inE "$PATTERN|$URLPATTERN" "$BODY_FILE" 2>/dev/null)"
GREP_RC=$?
if [ "$GREP_RC" -gt 1 ]; then
  echo "🟡 CANNOT TELL — the guard's own grep failed (rc=$GREP_RC). Refusing rather than guessing."
  exit 2
fi

# ⚠️ POSITIVE CONTROL: the pattern must match a string we KNOW is an offender.
# A guard whose regex silently stopped matching reports a clean body forever.
if ! printf 'closes #1\n' | grep -qiE "$PATTERN"; then
  echo "🟡 CANNOT TELL — the guard's own pattern does not match a known offender."
  echo "   The regex is broken; a clean result from it would mean nothing."
  exit 2
fi

if [ -n "$MATCHES" ]; then
  if [ -z "${DECLARE_INTENTIONAL_CLOSE:-}" ]; then
    cat <<MSG
🔴 REFUSED — the body carries a GitHub CLOSING KEYWORD next to an issue number.

$(printf '%s\n' "$MATCHES" | sed 's/^/   /')

  GitHub's parser has no concept of negation, tense or narration. "it does not
  A denial and a past-tense narration both read to it as an instruction.

  Either rephrase (put the number in a different clause, or prefix it with "PR"),
  or, if the close is INTENDED, declare it:

    DECLARE_INTENTIONAL_CLOSE="the issue named really is closed by this, because ..." \\
      bash scripts/create-pr.sh ...
MSG
    exit 1
  fi
  DECL="$DECLARE_INTENTIONAL_CLOSE"
  case "$DECL" in
    1|true|yes|TRUE|YES|y|Y)
      echo "🔴 REFUSED — DECLARE_INTENTIONAL_CLOSE must be a REASON, not a token."
      exit 1 ;;
  esac
  if [ "${#DECL}" -lt 20 ]; then
    echo "🔴 REFUSED — the declaration is ${#DECL} characters. An audit trail's 'why' is somebody's words or nothing."
    exit 1
  fi
  echo "═══════════════════════════════════════════════════════════════════"
  echo "DECLARED INTENTIONAL CLOSE — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '%s\n' "$MATCHES" | sed 's/^/  matched : /'
  echo "  reason  : $DECL"
  echo "═══════════════════════════════════════════════════════════════════"
fi

echo "🟢 guard: no undeclared closing keyword in $BODY_FILE"
if [ -n "$CHECK_ONLY" ]; then exit 0; fi

command -v gh >/dev/null 2>&1 || { echo "🟡 CANNOT TELL — no gh on PATH"; exit 2; }

URL="$(gh pr create --base "$BASE" --head "$HEAD" --title "$TITLE" --body-file "$BODY_FILE" $DRAFT 2>&1 | tail -1)"
case "$URL" in
  https://github.com/*/pull/*) ;;
  *) echo "🔴 create did not return a PR url: $URL"; exit 1 ;;
esac
NUM="${URL##*/}"

# ⚠️ THE EXIT CODE IS NOT THE EVIDENCE — canon 22. Ask the system that owns it.
STATE="$(gh pr view "$NUM" --json state --jq .state 2>/dev/null)"
if [ "$STATE" != "OPEN" ]; then
  echo "🔴 created but the PR does not read OPEN (state=$STATE) — $URL"
  exit 1
fi
LINKED="$(gh api graphql -f query="{repository(owner:\"$(gh repo view --json owner --jq .owner.login)\",name:\"$(gh repo view --json name --jq .name)\"){pullRequest(number:$NUM){closingIssuesReferences(first:5){nodes{number}}}}}" --jq '.data.repository.pullRequest.closingIssuesReferences.nodes|length' 2>/dev/null)"
case "$LINKED" in
  ''|0) : ;;
  *) echo "⚠️  WARNING — GitHub linked $LINKED issue(s) for closing on $URL. Check them." ;;
esac
echo "🟢 created and verified OPEN: $URL"
exit 0
