#!/usr/bin/env bash
# ============================================================================
# Does the QA WORKER carry the runtime feature-flag universe it is supposed to?
# ----------------------------------------------------------------------------
# ⚠️ THIS EXISTS BECAUSE EVERY STANDING CHECK WAS GREEN WHILE THE QA WORKER RAN
# WITH ALL ELEVEN PRODUCTION FEATURE FLAGS OFF. Measured 2026-08-24:
#
#     prod worker: templateNativeDocxEnabled() = true    | 11 NEXT_PUBLIC_*
#     QA   worker: templateNativeDocxEnabled() = false   |  0 NEXT_PUBLIC_*
#
# Both run `npx tsx src/worker.ts` — identical shape, so the env is the only
# difference, and there is no build-time inlining to hide behind.
#
# CONSEQUENCE: `worker/template-twin-fill-step.ts:76` returned
# `{status:'skipped', reason:'flag_off'}` for EVERY QA visit. The per-visit twin
# fill could not run on QA at all, `template_twin_fill_manifests` sat at 0, and
# ruling #144's acceptance walk was UNPERFORMABLE on the stack reserved for it.
#
# ⚠️ AND THE MECHANISM IS A SIDE EFFECT OF A CONTROL THAT IS CORRECT.
# Production delivers each flag TWICE — `build.args` (inlined into the frontend)
# and `env_file: .env` (the worker's runtime env). `docker-compose.qa.yml`
# declares them under `build.args` ONLY and has ZERO env_file declarations,
# deliberately, because inheriting the shared .env is what once put 298 real
# Anthropic calls through this stack. The severance is right; the flags rode
# .env to the worker, so the worker silently lost all of them.
#
# ⚠️ WHY THIS IS NOT `check-qa-mock-posture.sh`, AND MUST NOT BE FOLDED INTO IT.
# That check's FLAG_PATTERN is `^(MOCK_*|NOTE_FORMAT_E2E|E2E_*|*_E2E)=` — mock
# and fixture flags. Its green is TRUE and covers none of the product flags;
# its name is honest about its scope. Widening it would make its NAME narrower
# than what it MEASURES, which is the exact anti-pattern canon names. Two
# checks, two questions.
#
# ⚠️ SCOPE IS THE WORKER, DELIBERATELY. The QA APP container is a Next BUILD:
# its NEXT_PUBLIC_* are inlined at image-build time and are legitimately ABSENT
# from its runtime env (verified — build args reach the bundle; a surviving
# runtime read would mean they had NOT been inlined). Demanding a runtime env
# there would be demanding something harmless. The worker reads at runtime, so
# the worker is where runtime absence is a defect.
#
# READ-ONLY. Runs `printenv` inside a container. Writes nothing, mutates
# nothing, never touches a clinical route or any database.
#
# Usage:  bash scripts/check-qa-worker-flag-universe.sh
# Exit:   0 = the worker's runtime flag universe matches the declared manifest
#         1 = DIVERGED — missing, wrong-valued, or undeclared  (the finding)
#         2 = cannot tell (no docker, container down, probe cannot discriminate)
# ============================================================================
set -uo pipefail

CONTAINER="${QA_WORKER_CONTAINER:-meddoc-qa-transcribe-md-worker-1}"

# VAR|expected|why — the "why" is load-bearing. A bare name/value pair decays
# into nobody remembering whether the value was intended or inherited.
# Keep every entry on ONE line: the parser cuts on `|`, and a wrapped reason
# would be read as a further field.
DECLARED=(
  "NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX|true|gates the whole twin fork, incl. template-twin-fill-step.ts:76. OFF here made ruling #144's acceptance walk unperformable"
  "NEXT_PUBLIC_TEMPLATE_NATIVE_PDF|true|the pdf-native feature; imports twin storage"
  "NEXT_PUBLIC_ULTRASOUND_SPECIALTY|true|emAppliesToVisit reads it. OFF here silently changes which visits suppress office E/M"
  "NEXT_PUBLIC_REVIEW_DOC_VIEW|true|the read-only paper and its E/M override gate stack"
  "NEXT_PUBLIC_UX_SIMPLIFY|true|upload -> one confirm card; signed visit -> one document"
  "NEXT_PUBLIC_VISIT_DOC_PAGE|true|the document-first visit route"
  "NEXT_PUBLIC_CHAT_EDITOR|true|the chat editor write path"
  "NEXT_PUBLIC_DOC_PREVIEW|true|the real-document preview"
  "NEXT_PUBLIC_SETTINGS_SIMPLE_ROW|true|folds the UPLOAD half of NativeTemplateManager; the CONFIRM half stays reachable"
  "NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL|http://localhost:9020|QA's OWN url, matching build.args. NEVER production's — copying prod verbatim points this stack at app.quillmd.com"
  "NEXT_PUBLIC_MARKETING_URL|http://localhost:9010|QA's OWN url, matching build.args"
)

# ---------------------------------------------------------------------------
# ARM 0 — CAN WE MEASURE AT ALL? A broken probe and a clean system produce the
# same output, so nothing below is believed until this passes. Note the failure
# direction this guards: if `printenv` returns nothing, EVERY declared flag
# reads missing and the script would report a spectacular RED. That is alarm
# rather than false calm — still wrong, and it is `2`, never `1`.
# ---------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "⚠️  no docker on this host — cannot tell"
  exit 2
fi

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "⚠️  container $CONTAINER does not exist — is the QA stack up? cannot tell"
  exit 2
fi

ENV_DUMP="$(docker exec "$CONTAINER" printenv 2>/dev/null)"
if [ -z "$ENV_DUMP" ]; then
  echo "⚠️  printenv returned NOTHING from $CONTAINER — the probe is blind, not the stack clean. cannot tell"
  exit 2
fi

TOTAL_VARS="$(printf '%s\n' "$ENV_DUMP" | grep -cE '^[A-Za-z_][A-Za-z0-9_]*=')"
# POSITIVE CONTROL: a var that MUST be there, and is not one of the ones under
# test — so it discriminates the instrument rather than the target. DATABASE_URL
# is set in this service's `environment:` block unconditionally.
if ! printf '%s\n' "$ENV_DUMP" | grep -qE '^DATABASE_URL='; then
  echo "⚠️  positive control FAILED — DATABASE_URL absent from $CONTAINER."
  echo "    The probe cannot see this container's environment. cannot tell"
  exit 2
fi
# NEGATIVE CONTROL: a name that cannot exist. If this "matches", the matcher is
# not discriminating and no zero below means anything.
if printf '%s\n' "$ENV_DUMP" | grep -qE '^NEXT_PUBLIC_THIS_IS_NOT_A_REAL_FLAG_F27='; then
  echo "⚠️  negative control FIRED — the matcher matches things that do not exist. cannot tell"
  exit 2
fi

if [ "${#DECLARED[@]}" -eq 0 ]; then
  echo "⚠️  the declared manifest is EMPTY — a vacuous check cannot pass. cannot tell"
  exit 2
fi

echo "QA worker runtime flag universe — $CONTAINER"
echo "   · positive control: DATABASE_URL present · $TOTAL_VARS env vars readable"
echo "   · negative control: a non-existent flag name does not match"
echo "   · manifest: ${#DECLARED[@]} declared"
echo

# ---------------------------------------------------------------------------
# ARM 1 — every DECLARED flag is present with its declared value.
# ---------------------------------------------------------------------------
fail=0
ok=0
printf '   %-40s %-24s %s\n' "FLAG" "EXPECTED" "OBSERVED"
for row in "${DECLARED[@]}"; do
  name="${row%%|*}"
  rest="${row#*|}"
  want="${rest%%|*}"
  got="$(printf '%s\n' "$ENV_DUMP" | grep -E "^${name}=" | head -n1)"
  got="${got#*=}"
  if [ -z "$got" ]; then
    printf '   🔴 %-37s %-24s %s\n' "$name" "$want" "(UNSET)"
    fail=1
  elif [ "$got" != "$want" ]; then
    printf '   🔴 %-37s %-24s %s\n' "$name" "$want" "$got"
    fail=1
  else
    printf '   🟢 %-37s %-24s %s\n' "$name" "$want" "$got"
    ok=$((ok + 1))
  fi
done

# ---------------------------------------------------------------------------
# ARM 2 — the set comparison runs BOTH WAYS. An UNDECLARED NEXT_PUBLIC_* is a
# finding too: it means production or this stack grew a flag and this manifest
# was not updated, which is precisely how the original divergence survived.
# ---------------------------------------------------------------------------
undeclared=0
while IFS= read -r kv; do
  [ -z "$kv" ] && continue
  n="${kv%%=*}"
  found=0
  for row in "${DECLARED[@]}"; do
    [ "${row%%|*}" = "$n" ] && found=1 && break
  done
  if [ "$found" = "0" ]; then
    echo "   🔴 UNDECLARED: $n is set in the container and not in this manifest"
    undeclared=$((undeclared + 1))
    fail=1
  fi
done <<< "$(printf '%s\n' "$ENV_DUMP" | grep -E '^NEXT_PUBLIC_')"

# ---------------------------------------------------------------------------
# THE PARTITION — every declared row lands in exactly one bucket, and the
# total reconciles against a number computed a different way (the array's own
# length). Arithmetic that does not reconcile is a finding.
# ---------------------------------------------------------------------------
missing_or_wrong=$(( ${#DECLARED[@]} - ok ))
echo
echo "   THE PARTITION — declared rows:"
echo "     matched                 $ok"
echo "     missing or wrong-valued $missing_or_wrong"
echo "                             ---"
echo "                             $(( ok + missing_or_wrong ))  == ${#DECLARED[@]} declared"
echo "   undeclared NEXT_PUBLIC_* present in container: $undeclared"
echo

if [ "$(( ok + missing_or_wrong ))" != "${#DECLARED[@]}" ]; then
  echo "⚠️  the partition does not reconcile — this script is miscounting. cannot tell"
  exit 2
fi

if [ "$fail" != "0" ]; then
  echo "🔴 QA WORKER FLAG UNIVERSE DIVERGED — this stack is NOT production-shaped."
  echo "   A behavioural proof run here is a proof about a system nobody ships."
  echo "   Fix: docker-compose.qa.yml, the worker's \`environment:\` block."
  echo "   ⚠️  LITERALS, never \${VAR:-default} — compose interpolation reads the"
  echo "       shared .env whether or not this file declares an env_file."
  exit 1
fi

echo "🟢 the QA worker carries its declared runtime flag universe —"
echo "   $ok of ${#DECLARED[@]} matched, 0 undeclared, read from the LIVE container."
exit 0
