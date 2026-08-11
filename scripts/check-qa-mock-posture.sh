#!/usr/bin/env bash
# ============================================================================
# Is the QA stack actually incapable of reaching a vendor — AND is it running
# only the fixture flags it declares?
# ----------------------------------------------------------------------------
# IT CHECKS THE RUNNING CONTAINERS, NOT THE COMPOSE FILE, and that distinction
# is the entire reason it exists. On 2026-07-28 docker-compose.qa.yml said
# `MOCK_AI_CALLS: "${MOCK_AI_CALLS:-true}"` and
# `ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY:-mock-key-qa}"` — both of which READ
# as safe. Neither was. `:-` applies only when a variable is UNSET, and
# /opt/meddoc-pro/.env sets both because PRODUCTION needs them. Compose reads
# that same .env. So the "isolated" stack ran with MOCK_AI_CALLS=false, a live
# `sk-ant-api03-…` and a live Deepgram key, and made 298 real Anthropic calls
# plus real Deepgram requests — burning the same balance production depends on,
# for weeks, while the file's own header promised it could not.
#
# TWO INDEPENDENT CONDITIONS, because either alone is a single point of failure:
#
#   1. MOCK_AI_CALLS=true    — no code path tries to call out
#   2. dummy credentials     — and if one does anyway, it fails auth
#
# Condition 2 is what survives a code regression. A new layer, a retry helper or
# a one-off script that forgets the flag is a normal mistake; it should cost an
# auth error, not a vendor bill and a synthetic transcript leaving the box.
#
# ⚠️ A CHECK THAT CRIES WOLF IS HOW THE REAL SIGNAL GETS IGNORED.
#
# This script spent an unknown period reporting "🔴 REAL CALLS ARE POSSIBLE"
# about a stack that was STOPPED. The guard used `docker inspect`, which
# succeeds for a stopped container — it tests EXISTENCE, not running state — so
# every container sailed past it, `docker exec` returned empty for every
# variable, and an empty `MOCK_AI_CALLS` was reported as a live vendor risk.
# Measured 2026-08-07, QA `Exited (143)` since a reboot. It also let the script
# contradict itself inside one run: "This stack can reach a real vendor"
# followed immediately by "The stack cannot reach a vendor".
#
# The cost of that is not a wasted minute. It is that the next person to see a
# 🔴 here assumes the stack is merely off — and this is the check that caught
# 298 real Anthropic calls. A red that is usually meaningless is worse than no
# red at all.
#
# So: a STOPPED stack is "calls impossible — PASS, with a stated note about what
# was NOT verified". RED is reserved for a RUNNING stack that can reach a
# vendor. The two arms below reach their own verdicts and never share a message.
#
# READ-ONLY. Never mutates anything.
#
# Usage:  bash scripts/check-qa-mock-posture.sh
# TWO ARMS:
#   1. vendor reachability — MOCK_AI_CALLS plus dummy credentials
#   2. the FLAG MANIFEST — the MOCK_*/fixture flags actually present in the
#      running containers, compared as a SET against a declared manifest
#
# Exit:   0 = clean · 1 = LIVE CREDENTIALS, MOCK OFF, OR AN UNDECLARED FLAG
#         2 = stack not running / nothing compared
#
# Invoke with `bash scripts/...` — this repo sets core.fileMode=false, so the
# executable bit is not tracked and `./scripts/...` gives "Permission denied".
# ============================================================================
set -uo pipefail

CONTAINERS="meddoc-qa-transcribe-md-1 meddoc-qa-transcribe-md-worker-1"
# Every vendor credential the codebase reads. Keep in step with the compose file
# — a key that is unset today is one .env line away from being real.
#
# ⚠️ `STRIPE_SECRET_KEY` IS HERE BEFORE ANY CODE READS IT, AND THAT IS THE POINT.
# SPEC §2.4 and RELAY B6 both require it to join this list "in the same change
# that introduces it". B6 introduces the billing writer; B7 introduces the
# Stripe caller. Waiting for the caller would mean the first commit that can
# spend money is also the first commit this check watches — and the whole reason
# this script exists is that a `${VAR:-default}` in docker-compose.qa.yml
# inherits the PRODUCTION value from the shared .env, silently, for weeks.
#
# There is no Stripe entry in docker-compose.qa.yml today (verified: zero
# matches for `stripe` across every compose file), so this arm reports the key
# UNSET rather than dummy. That is the correct reading and it is stronger than a
# dummy: nothing to leak because nothing is there. It becomes load-bearing the
# moment B7 adds the variable, which is exactly when nobody will be thinking
# about this file.
#
# ⚠️ AND THE GUARDRAIL IS ABSOLUTE: Stripe is TEST MODE ONLY on this programme.
# A live `sk_live_…` reaching any container is not a configuration slip, it is
# the hard-halt item at the top of the FOUNDATION master prompt.
KEYS="ANTHROPIC_API_KEY DEEPGRAM_API_KEY OPENAI_API_KEY RESEND_API_KEY STRIPE_SECRET_KEY"

fail=0
checked=0
stopped=0
absent=0

for c in $CONTAINERS; do
  # ⚠️ `docker inspect` SUCCEEDS FOR A STOPPED CONTAINER — it tests EXISTENCE,
  # not running state. That was this script's own bug: on 2026-08-07 the QA
  # stack was `Exited (143)` since a reboot, every container sailed past this
  # guard, `docker exec` then returned empty for every variable, and empty
  # MOCK_AI_CALLS printed as "🔴 REAL CALLS ARE POSSIBLE" — about containers
  # that were not running and could call nobody.
  if ! docker ps --format '{{.Names}}' | grep -qx "$c"; then
    if docker inspect "$c" >/dev/null 2>&1; then
      echo "⚪ $c is STOPPED — it cannot reach a vendor (see the verdict below)"
      stopped=$((stopped + 1))
    else
      echo "⚪ $c does not exist on this host"
      absent=$((absent + 1))
    fi
    continue
  fi
  checked=$((checked + 1))

  mock=$(docker exec "$c" printenv MOCK_AI_CALLS 2>/dev/null || echo "")
  if [ "$mock" = "true" ]; then
    echo "🟢 $c: MOCK_AI_CALLS=true"
  else
    echo "🔴 $c: MOCK_AI_CALLS=${mock:-(unset)} — REAL CALLS ARE POSSIBLE"
    fail=1
  fi

  for k in $KEYS; do
    val=$(docker exec "$c" printenv "$k" 2>/dev/null || echo "")
    if [ -z "$val" ]; then
      # Unset is acceptable — nothing to leak — but say so, because it means
      # this container is relying on absence rather than on a dummy.
      echo "   ⚪ $k unset"
    elif printf '%s' "$val" | grep -qiE '^(qa-)?(dummy|mock|test|ci-dummy)'; then
      echo "   🟢 $k is a dummy"
    else
      # Print a SHORT prefix only. Enough to recognise the vendor, never enough
      # to use — this output goes in reports.
      echo "   🔴 $k LOOKS REAL (${val:0:8}…) — a mock regression could spend it"
      fail=1
    fi
  done
done

if [ "$checked" = "0" ]; then
  echo
  if [ "$stopped" != "0" ]; then
    # ⚠️ A STOPPED STACK IS A PASS FOR THIS ARM, AND SAYING SO IS THE WHOLE
    # POINT. The question is "can this stack reach a vendor?" — for a stopped
    # container the answer is a definitive NO, not "cannot tell". Reporting RED
    # here is how the check taught people to ignore it.
    echo "🟢 QA cannot reach a vendor — the stack is STOPPED ($stopped container(s))."
    echo "   ⚪ NOTE: this is a pass about CAPABILITY, not about configuration."
    echo "      The flag manifest could not be compared, so nothing here says the"
    echo "      stack will come up correctly. Re-run after starting it, BEFORE"
    echo "      trusting any pack run against it:"
    echo "        docker compose -f docker-compose.qa.yml up -d --force-recreate \\"
    echo "          --no-deps transcribe-md transcribe-md-worker"
    exit 0
  fi
  echo "🟡 no QA containers exist on this host — no verdict."
  exit 2
fi

# ============================================================================
# ARM 2 — THE FLAG MANIFEST
# ----------------------------------------------------------------------------
# The arm above answers ONE question: can this stack reach a vendor? It was
# green throughout the incident below, correctly, and could not have caught it.
#
# ⚠️ REFERENCE CASE, 2026-08-06. The default `chromium` E2E pack came back 6
# failed, all reporting "clicked Review & sign but the gate flow never presented
# the attestation". Nothing was wrong with the code. `MOCK_RX_WARNINGS=true` was
# still set ON THE WORKER, left from an earlier flag-gated run — the worker emits
# the Rx drafts, so every visit it processed carried a critical Warfarin
# interaction and the gate opened at Gate 1 instead of the attestation.
#
# The app container was clean. Only the worker was contaminated, because a
# rebuild had recreated `transcribe-md` and left `transcribe-md-worker` up for
# two days. ⚠️ **A PARTIAL `up -d` SPLITS THE STACK'S CONFIGURATION** — the flags
# come from the shell at up-time, so recreating one service and not the other is
# enough to leave half the stack on a previous invocation's env.
#
# STANDING RULE: recreate BOTH for any flag-bearing stack change.
#
# What this arm asserts: the set of MOCK_*/fixture flags present in the RUNNING
# containers equals the DECLARED manifest below. An undeclared flag is a red,
# with the container named — because a leftover fixture flag does not break
# anything visibly, it silently changes WHAT THE PACK IS TESTING, which is the
# "packs certifying a configuration that is not production" class.
#
# ⚠️ IT COMPARES SETS, NOT A DENYLIST. Listing known-bad flags would pass every
# flag nobody had thought of yet — the same defect as a gate watching the wrong
# universe. Anything matching the pattern and not on the manifest is a finding.
# ============================================================================

# The flags a CLEAN QA stack is expected to carry, as `NAME=value`.
# Adding a line here is a declaration: it belongs in a diff where someone can ask
# whether that flag should be on for every pack, not just the one that needed it.
EXPECTED_FLAGS="MOCK_AI_CALLS=true"

# Flags that legitimately vary per PACK and are set on the RUNNER, never baked
# into a long-lived container. Present here = leftover, by definition.
#   MOCK_RX_WARNINGS       — rx-safety project only
#   MOCK_TEMPLATE_PHI_FLAG — phi-reject project only
#   NOTE_FORMAT_E2E        — a Playwright-step env var; must not be in a container
FLAG_PATTERN='^(MOCK_[A-Z0-9_]*|NOTE_FORMAT_E2E|E2E_[A-Z0-9_]*|.*_E2E)='

manifest_fail=0
manifest_checked=0
manifest_broken=0
# Remember which arm failed. A manifest mismatch is NOT vendor reachability, and
# saying so would be a false claim in a report — the same defect as a check whose
# message is wider than its evidence.
vendor_broken=$fail

for c in $CONTAINERS; do
  docker inspect "$c" >/dev/null 2>&1 || continue
  # Read the LIVE process environment, not the compose file and not the image.
  present=$(docker exec "$c" printenv 2>/dev/null | grep -E "$FLAG_PATTERN" | sort)
  manifest_checked=$((manifest_checked + 1))

  while IFS= read -r kv; do
    [ -z "$kv" ] && continue
    name=${kv%%=*}
    value=${kv#*=}
    # An empty value is the flag being explicitly cleared — not a leftover.
    [ -z "$value" ] && continue
    if printf '%s\n' "$EXPECTED_FLAGS" | grep -qxF "$kv"; then
      echo "🟢 $c: $name=$value (declared)"
    else
      echo "🔴 $c: $name=$value is UNDECLARED — a leftover fixture flag silently"
      echo "        changes what every pack on this stack is testing."
      manifest_fail=1
    fi
  done <<EOF
$present
EOF

  # And the other direction: a declared flag that has gone MISSING means the
  # stack is not in the posture the manifest claims. Same asymmetry as the
  # allowlists elsewhere — both directions, or it is a rubber stamp.
  #
  # ⚠️ TO PROVE THIS ARM CAN FIRE, MUTATE THE MANIFEST — NOT THE CONTAINER.
  # `MOCK_AI_CALLS= docker compose up -d` does NOT clear the flag: the compose
  # file says `${MOCK_AI_CALLS:-true}`, and `:-` substitutes on EMPTY as well as
  # unset, so the container comes up with `true` and the mutation is a silent
  # no-op that reads as "the check failed to fire". Add a line to
  # EXPECTED_FLAGS instead and watch it redden. (Same `:-` trap that caused the
  # 2026-07-28 vendor incident this script was written for.)
  while IFS= read -r want; do
    [ -z "$want" ] && continue
    wname=${want%%=*}
    if ! printf '%s\n' "$present" | grep -qxF "$want"; then
      got=$(docker exec "$c" printenv "$wname" 2>/dev/null || echo "")
      # ⚠️ `${got:-(unset)}` ALONE. The earlier form was
      # `${got:+$got}${got:-(unset)}`, which prints the value TWICE for any
      # non-empty value — `:+` yields it, and `:-` also yields it, because the
      # default only fires when the variable is empty. Observed as
      # "MOCK_AI_CALLS is falsefalse". Harmless to the verdict, corrosive to a
      # report nobody can quite trust.
      echo "🔴 $c: $wname is ${got:-(unset)}, manifest expects ${want#*=}"
      manifest_fail=1
    fi
  done <<EOF
$EXPECTED_FLAGS
EOF
done

# ⚠️ POSITIVE CONTROL. A loop that inspected nothing reports zero problems, which
# is indistinguishable from a clean stack.
if [ "$manifest_checked" = "0" ]; then
  echo "⚠️  flag manifest compared 0 containers — reporting 'cannot tell'"
  exit 2
fi

if [ "$manifest_fail" != "0" ]; then
  manifest_broken=1
  fail=1
fi

if [ "$fail" = "0" ]; then
  echo
  echo "🟢 QA posture holds — vendor-severed AND the flag manifest matches, in the live containers"
  exit 0
fi

echo
# ⚠️ SAY WHICH ARM FAILED. The first version printed "this stack can reach a real
# vendor" for a FLAG MANIFEST mismatch, while the vendor arm was green — a
# statement the evidence did not support, in a script whose output goes into
# reports. Two arms, two verdicts, never one message for both.
if [ "$vendor_broken" != "0" ]; then
  echo "🔴 QA MOCK POSTURE BROKEN. This stack can reach a real vendor."
  echo "   Check docker-compose.qa.yml for a \`\${VAR:-default}\` that inherits from"
  echo "   the shared .env — that is how this broke before."
fi
if [ "$manifest_broken" != "0" ]; then
  # ⚠️ THIS ARM MUST NOT ASSERT ANYTHING ABOUT THE OTHER ONE. It used to open
  # with "The stack cannot reach a vendor, but…" — a clause that is only true
  # when the vendor arm PASSED. When both arms fail, the script printed "This
  # stack can reach a real vendor" and "The stack cannot reach a vendor" three
  # lines apart, in the same run. Two arms, two verdicts, and neither speaks
  # for the other.
  echo "🔴 FLAG MANIFEST BROKEN. This stack is NOT running the fixture"
  echo "   configuration it declares — so any pack run against it is certifying"
  echo "   something other than production."
  if [ "$vendor_broken" = "0" ]; then
    echo "   (Vendor reachability is SEVERED — that arm passed. This is a"
    echo "    configuration fault, not an exposure.)"
  fi
fi
echo "   Recreate BOTH services (a partial \`up -d\` is what splits the env):"
echo "     docker compose -f docker-compose.qa.yml up -d --force-recreate \\"
echo "       --no-deps transcribe-md transcribe-md-worker"
exit 1
