#!/usr/bin/env bash
# ============================================================================
# tests/audit/phi-read-audit.test.sh — Round 3 PR-C
# ============================================================================
# Static regression guard for HIPAA §164.312(b) PHI-read audit coverage
# (audit finding A05-P0-004). Asserts logAudit() calls landed in the
# files that PR-C added them to, so a future refactor cannot silently
# delete them.
#
# This is intentionally a grep-based static check, NOT a runtime test.
# The runtime expectation is "every PHI-read endpoint emits an audit
# row"; this test verifies "every PHI-read endpoint contains the call
# site that emits the row". The two together are sufficient: if the
# call site is present and logAudit() works (covered by separate
# integration tests), the row is written.
#
# Run: bash tests/audit/phi-read-audit.test.sh
# Exit: 0 on all-pass, 1 on first failure.
# ============================================================================

set -euo pipefail

cd "$(dirname "$0")/../.."

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
pass() { printf 'PASS: %s\n' "$*"; }

# Format: <relative-path>|<expected-action>
EXPECTED=(
  'apps/transcribe-md/src/app/api/visits/[id]/route.ts|VIEWED_VISIT'
  'apps/transcribe-md/src/app/api/visits/[id]/dictation/audio/route.ts|VIEWED_VISIT_AUDIO'
  'apps/transcribe-md/src/app/api/patients/route.ts|VIEWED_PATIENT_LIST'
  'apps/transcribe-md/src/app/api/patients/[id]/route.ts|VIEWED_PATIENT_FILE'
  'apps/transcribe-md/src/app/api/patients/fuzzy-match/route.ts|VIEWED_PATIENT_LIST'
  'apps/transcribe-md/src/app/visits/page.tsx|VIEWED_VISIT_LIST'
  'apps/transcribe-md/src/app/visits/[id]/page.tsx|VIEWED_VISIT'
  'apps/transcribe-md/src/app/patients/page.tsx|VIEWED_PATIENT_LIST'
  'apps/transcribe-md/src/app/patients/[id]/page.tsx|VIEWED_PATIENT_FILE'
)

for entry in "${EXPECTED[@]}"; do
  path="${entry%%|*}"
  action="${entry##*|}"

  if [[ ! -f "$path" ]]; then
    fail "expected file missing: $path"
  fi

  # logAudit import present
  if ! grep -qE "^\s*import.*logAudit.*from.*lib/audit" "$path"; then
    fail "$path: missing 'import { logAudit } from .../lib/audit'"
  fi

  # logAudit call with the expected action present
  # We accept either `await logAudit({` or `void logAudit({`. The call
  # site can span multiple lines; the action property may sit on a
  # later line, so use a one-shot grep with -z to span newlines.
  if ! awk -v ACTION="$action" '
        /(await|void)\s+logAudit\(\s*{/ { in_call = 1 }
        in_call && $0 ~ "action: '\''" ACTION "'\''"  { found = 1 }
        in_call && /\)/ { in_call = 0 }
        END { exit (found ? 0 : 1) }
      ' "$path"; then
    fail "$path: logAudit() call with action='$action' not found"
  fi

  pass "$path → action='$action'"
done

# Schema-level invariant: enum values must exist in schema.prisma. The
# migration `20260505010200_*` is what actually adds them at the DB layer,
# but schema.prisma is the source of truth and Prisma client generation
# reads from it.
SCHEMA="packages/db/prisma/schema.prisma"
for action in VIEWED_VISIT VIEWED_VISIT_LIST VIEWED_VISIT_AUDIO; do
  if ! grep -q "  ${action}$" "$SCHEMA"; then
    fail "$SCHEMA: enum value $action missing"
  fi
  pass "$SCHEMA: enum value $action present"
done

# AuditAction TS union (consumed at call sites for type-safety) must
# also include the new actions; otherwise TS compilation fails.
TYPES_FILE="apps/transcribe-md/src/lib/audit.ts"
for action in VIEWED_VISIT VIEWED_VISIT_LIST VIEWED_VISIT_AUDIO VIEWED_PATIENT_LIST VIEWED_PATIENT_FILE; do
  if ! grep -qE "\|\s*'${action}'" "$TYPES_FILE"; then
    fail "$TYPES_FILE: TS union missing '${action}'"
  fi
  pass "$TYPES_FILE: TS union has '${action}'"
done

echo
echo "All PHI-read audit-coverage assertions passed."
