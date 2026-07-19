#!/usr/bin/env bash
set -euo pipefail

# Post-contract deployment guard for the only supported application rollback:
# current final-schema code running in rollback-compat-v2 mode. This script
# never changes database rollout state. Operators must pause, drain, and revoke
# through the reviewed control path before invoking it.

readonly EXPECTED_EPOCH="template-twin-final-schema-v2"
readonly BRIDGE_MODE="rollback-compat-v2"
readonly PRE_STACK_APP_ID="sha256:95f57158e3fe56acc832793be3f5da972cc1fdc6c3b85166f8387b3a103f1f90"
readonly PRE_STACK_WORKER_ID="sha256:412dd3157475fd60a77d417a6db6880343d58755aaf76f044be035fba4acf44e"

app_image=""
worker_image=""
release_sha=""
compose_file="docker-compose.yml"
execute_swap="false"

usage() {
  printf '%s\n' \
    "Usage: $0 --app-image <ref> --worker-image <ref> --release-sha <40-hex> [--compose-file <path>] [--execute]" \
    "" \
    "Without --execute this performs a read-only verification. --execute" \
    "recreates only transcribe-md and transcribe-md-worker after every guard passes."
}

while (($# > 0)); do
  case "$1" in
    --app-image)
      app_image="${2:-}"
      shift 2
      ;;
    --worker-image)
      worker_image="${2:-}"
      shift 2
      ;;
    --release-sha)
      release_sha="${2:-}"
      shift 2
      ;;
    --compose-file)
      compose_file="${2:-}"
      shift 2
      ;;
    --execute)
      execute_swap="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 64
      ;;
  esac
done

if [[ -z "$app_image" || -z "$worker_image" || ! "$release_sha" =~ ^[a-f0-9]{40}$ ]]; then
  usage >&2
  exit 64
fi
for immutable_ref in "$app_image" "$worker_image"; do
  if [[ ! "$immutable_ref" =~ ^sha256:[a-f0-9]{64}$ && ! "$immutable_ref" =~ @sha256:[a-f0-9]{64}$ ]]; then
    printf 'runtime-swap: image references must be immutable sha256 IDs or repository digests\n' >&2
    exit 64
  fi
done
if [[ ! -f "$compose_file" ]]; then
  printf 'runtime-swap: compose file not found\n' >&2
  exit 66
fi
for required_command in docker; do
  if ! command -v "$required_command" >/dev/null 2>&1; then
    printf 'runtime-swap: required command unavailable: %s\n' "$required_command" >&2
    exit 69
  fi
done

compose=(docker compose -f "$compose_file")

image_id() {
  docker image inspect --format '{{.Id}}' "$1"
}

image_label() {
  docker image inspect --format "{{ index .Config.Labels \"$2\" }}" "$1"
}

verify_image() {
  local ref="$1"
  local component="$2"
  local resolved_id epoch revision actual_component
  resolved_id="$(image_id "$ref")"
  case "$resolved_id" in
    "$PRE_STACK_APP_ID"|"$PRE_STACK_WORKER_ID")
      printf 'runtime-swap: rejected exact pre-stack image id %s\n' "$resolved_id" >&2
      return 1
      ;;
  esac
  epoch="$(image_label "$ref" com.quillmd.runtime-protocol-epoch)"
  revision="$(image_label "$ref" org.opencontainers.image.revision)"
  actual_component="$(image_label "$ref" com.quillmd.runtime-component)"
  if [[ "$epoch" != "$EXPECTED_EPOCH" ]]; then
    printf 'runtime-swap: %s image lacks the required protocol epoch\n' "$component" >&2
    return 1
  fi
  if [[ "$revision" != "$release_sha" ]]; then
    printf 'runtime-swap: %s image revision does not match the accepted release SHA\n' "$component" >&2
    return 1
  fi
  if [[ "$actual_component" != "$component" ]]; then
    printf 'runtime-swap: image component mismatch for %s\n' "$component" >&2
    return 1
  fi
  printf '%s' "$resolved_id"
}

app_id="$(verify_image "$app_image" transcribe-md-app)"
worker_id="$(verify_image "$worker_image" transcribe-md-worker)"
if [[ "$app_id" == "$worker_id" ]]; then
  printf 'runtime-swap: app and worker unexpectedly resolve to one image\n' >&2
  exit 65
fi

psql_value() {
  "${compose[@]}" exec -T postgres \
    psql -X -v ON_ERROR_STOP=1 \
      -U "${POSTGRES_USER:-meddoc}" \
      -d "${POSTGRES_DB:-meddoc}" \
      -Atqc "$1"
}

lineage_phase="$(psql_value \
  "SELECT \"phase\" FROM \"template_twin_lineage_migration_progress\" WHERE \"operationKey\"='note_templates_lineage_v1';")"
if [[ "$lineage_phase" != "CONTRACTED" ]]; then
  printf 'runtime-swap: final lineage schema is not CONTRACTED\n' >&2
  exit 65
fi

global_enabled="$(psql_value \
  "SELECT CASE WHEN \"enabled\" THEN 'true' ELSE 'false' END FROM \"template_twin_rollout_controls\" WHERE \"id\"='global';")"
enabled_practices="$(psql_value \
  "SELECT count(*) FROM \"practices\" WHERE \"templateTwinEnabled\";")"
active_twin_templates="$(psql_value \
  "SELECT count(*) FROM \"note_templates\" WHERE \"templateKind\"='template_twin_docx' AND \"status\"='active';")"
unsettled_twin_provider_work="$(psql_value \
  "SELECT count(*) FROM \"visit_automation_provider_executions\" e JOIN \"transcribe_visits\" v ON v.\"id\"=e.\"visitId\" JOIN \"note_templates\" n ON n.\"id\"=v.\"noteTemplateId\" WHERE n.\"templateKind\"='template_twin_docx' AND e.\"status\"::text IN ('RESERVED','IN_FLIGHT','UNKNOWN_OUTCOME');")"
unsettled_twin_visits="$(psql_value \
  "SELECT count(*) FROM \"transcribe_visits\" v JOIN \"note_templates\" n ON n.\"id\"=v.\"noteTemplateId\" WHERE n.\"templateKind\"='template_twin_docx' AND v.\"status\"::text IN ('QUEUED','TRANSCRIBING','EXTRACTING','DRAFTING','CRITIQUING','POLISHING','AUTOMATING');")"
unsettled_twin_runs="$(psql_value \
  "SELECT count(*) FROM \"template_twin_synthetic_qa_runs\" WHERE \"status\" IN ('PENDING_ENQUEUE','ENQUEUED','RETRY_ENQUEUED','PROCESSING');")"

if [[ "$global_enabled" != "false" || "$enabled_practices" != "0" ]]; then
  printf 'runtime-swap: persisted Template Twin rollout has not been fully revoked\n' >&2
  exit 65
fi
if [[ "$active_twin_templates" != "0" ]]; then
  printf 'runtime-swap: active Template Twin versions must be deactivated before bridge swap\n' >&2
  exit 65
fi
if [[ "$unsettled_twin_provider_work" != "0" ]]; then
  printf 'runtime-swap: unsettled Template Twin provider work blocks bridge swap\n' >&2
  exit 65
fi
if [[ "$unsettled_twin_visits" != "0" || "$unsettled_twin_runs" != "0" ]]; then
  printf 'runtime-swap: unsettled Template Twin visits or synthetic runs block bridge swap\n' >&2
  exit 65
fi

queue_active="$("${compose[@]}" exec -T redis redis-cli --raw LLEN bull:transcribe-md:active)"
cleanup_queue_active="$("${compose[@]}" exec -T redis redis-cli --raw LLEN bull:transcribe-md-cleanup:active)"
if [[ "$queue_active" != "0" || "$cleanup_queue_active" != "0" ]]; then
  printf 'runtime-swap: visit or maintenance worker queue is not drained\n' >&2
  exit 65
fi

# Resolve the references a second time immediately before any state change.
if [[ "$(image_id "$app_image")" != "$app_id" || "$(image_id "$worker_image")" != "$worker_id" ]]; then
  printf 'runtime-swap: an image reference changed during verification\n' >&2
  exit 65
fi

printf 'runtime-swap: PASS epoch=%s release=%s app=%s worker=%s mode=%s\n' \
  "$EXPECTED_EPOCH" "$release_sha" "$app_id" "$worker_id" "$BRIDGE_MODE"

if [[ "$execute_swap" != "true" ]]; then
  printf 'runtime-swap: read-only verification complete; no containers changed\n'
  exit 0
fi

export QUILLMD_RELEASE_SHA="$release_sha"
# Compose receives the exact verified local image IDs, not even the immutable
# repository aliases, removing a tag/reference resolution race during recreate.
export TRANSCRIBE_MD_IMAGE="$app_id"
export TRANSCRIBE_MD_WORKER_IMAGE="$worker_id"
export TEMPLATE_TWIN_RUNTIME_MODE="$BRIDGE_MODE"
export TEMPLATE_TWIN_KILL_SWITCH="true"

"${compose[@]}" stop transcribe-md-worker
"${compose[@]}" up -d --no-build --no-deps --force-recreate \
  transcribe-md transcribe-md-worker

app_container="$("${compose[@]}" ps -q transcribe-md)"
worker_container="$("${compose[@]}" ps -q transcribe-md-worker)"
if [[ -z "$app_container" || -z "$worker_container" ]]; then
  printf 'runtime-swap: recreated container identity is unavailable\n' >&2
  exit 70
fi
if [[ "$(docker inspect --format '{{.Image}}' "$app_container")" != "$app_id" ]]; then
  printf 'runtime-swap: running app image does not match verified image\n' >&2
  exit 70
fi
if [[ "$(docker inspect --format '{{.Image}}' "$worker_container")" != "$worker_id" ]]; then
  printf 'runtime-swap: running worker image does not match verified image\n' >&2
  exit 70
fi

for _attempt in $(seq 1 30); do
  app_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$app_container")"
  worker_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$worker_container")"
  if [[ "$app_health" == "healthy" && "$worker_health" == "healthy" ]]; then
    printf 'runtime-swap: bridge app and worker are healthy\n'
    exit 0
  fi
  sleep 2
done

printf 'runtime-swap: bridge containers did not become healthy; keep rollout revoked and follow rollback runbook\n' >&2
exit 70
