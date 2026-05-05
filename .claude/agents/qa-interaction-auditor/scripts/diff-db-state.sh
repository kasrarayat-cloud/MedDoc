#!/usr/bin/env bash
# ============================================================================
# diff-db-state.sh — Snapshot a visit's mutable DB state for click-diffing.
# ----------------------------------------------------------------------------
# Used by the QA Interaction Auditor agent to capture the visit's
# columns + audit-log rows BEFORE and AFTER an interactive element is
# clicked, so the agent can classify the click outcome (real write vs.
# pretend success vs. orphan dispatcher).
#
# Usage:
#   diff-db-state.sh snapshot <visit-id> <label>     -> writes /tmp/qa-<label>-<vid>.json
#   diff-db-state.sh diff <visit-id> <label-a> <label-b>  -> diffs A vs B
#   diff-db-state.sh audit <visit-id> <since-iso>    -> dumps audit_logs since timestamp
#
# Idempotent + read-only (only reads from postgres; writes to /tmp).
# ============================================================================

set -euo pipefail

CONTAINER="${POSTGRES_CONTAINER:-meddoc-pro-postgres-1}"
DB_USER="${POSTGRES_USER:-meddoc}"
DB_NAME="${POSTGRES_DB:-meddoc}"

usage() {
  cat <<'EOF' >&2
diff-db-state.sh — snapshot/diff visit state for QA agent

Subcommands:
  snapshot <visit-id> <label>
      Snapshot all mutable columns of the visit + count audit rows.
      Writes /tmp/qa-<label>-<visit-id>.json. <label> is typically
      "before-click" or "after-click".

  diff <visit-id> <label-a> <label-b>
      Diff two earlier snapshots. Outputs unified-style JSON diff to
      stdout. Returns exit 0 if no changes, 1 if changes found.

  audit <visit-id> <since-iso>
      Dump audit_logs rows for this visit since <since-iso>
      (ISO 8601). One JSON object per line.

Env overrides:
  POSTGRES_CONTAINER (default: meddoc-pro-postgres-1)
  POSTGRES_USER      (default: meddoc)
  POSTGRES_DB        (default: meddoc)
EOF
  exit 2
}

snapshot() {
  local visit_id="$1"
  local label="$2"
  local out="/tmp/qa-${label}-${visit_id}.json"

  docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tA <<SQL > "$out"
SELECT row_to_json(t) FROM (
  SELECT
    id,
    status::text AS status,
    "needsReview",
    "reviewReason",
    "audioKey",
    "audioMimeType",
    "audioSizeBytes",
    LENGTH(COALESCE("soapDraft", '')) AS soap_draft_len,
    LENGTH(COALESCE("soapFinal", '')) AS soap_final_len,
    "icdCodes"::text AS icd_codes_json,
    "cptCodes"::text AS cpt_codes_json,
    "rxDrafts"::text AS rx_drafts_json,
    "signedAt"::text AS signed_at,
    "processingStartedAt"::text AS processing_started_at,
    "processingFinishedAt"::text AS processing_finished_at,
    "updatedAt"::text AS updated_at,
    (
      SELECT COUNT(*)
      FROM audit_logs
      WHERE "targetId" = transcribe_visits.id
    ) AS audit_row_count
  FROM transcribe_visits
  WHERE id = '$visit_id'
) t;
SQL

  if [ ! -s "$out" ]; then
    echo "ERROR: visit $visit_id not found" >&2
    rm -f "$out"
    exit 3
  fi

  echo "$out"
}

diff_snapshots() {
  local visit_id="$1"
  local label_a="$2"
  local label_b="$3"
  local file_a="/tmp/qa-${label_a}-${visit_id}.json"
  local file_b="/tmp/qa-${label_b}-${visit_id}.json"

  for f in "$file_a" "$file_b"; do
    if [ ! -f "$f" ]; then
      echo "ERROR: snapshot missing: $f" >&2
      exit 4
    fi
  done

  if cmp -s "$file_a" "$file_b"; then
    echo '{"changed":false}'
    exit 0
  fi

  # Build a structured diff using jq. Each row is a single JSON object;
  # iterate keys + report mismatches.
  jq -n \
    --slurpfile a "$file_a" \
    --slurpfile b "$file_b" \
    '
      ($a[0]) as $A
    | ($b[0]) as $B
    | ([$A | keys[]] + [$B | keys[]] | unique) as $allKeys
    | {
        changed: true,
        diffs: ($allKeys | map(
          . as $k
          | if ($A[$k] // null) == ($B[$k] // null) then empty
            else { key: $k, before: ($A[$k] // null), after: ($B[$k] // null) }
            end
        ))
      }
    '
  exit 1
}

audit() {
  local visit_id="$1"
  local since_iso="$2"

  docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tA <<SQL
SELECT row_to_json(t) FROM (
  SELECT
    id,
    "createdAt"::text AS created_at,
    action::text AS action,
    "actorUserId" AS actor_user_id,
    "targetId" AS target_id,
    "targetType" AS target_type,
    metadata::text AS metadata_json
  FROM audit_logs
  WHERE "targetId" = '$visit_id'
    AND "createdAt" > '$since_iso'::timestamptz
  ORDER BY "createdAt" ASC
) t;
SQL
}

case "${1:-}" in
  snapshot)
    [ "$#" -eq 3 ] || usage
    snapshot "$2" "$3"
    ;;
  diff)
    [ "$#" -eq 4 ] || usage
    diff_snapshots "$2" "$3" "$4"
    ;;
  audit)
    [ "$#" -eq 3 ] || usage
    audit "$2" "$3"
    ;;
  *)
    usage
    ;;
esac
