#!/usr/bin/env bash
set -euo pipefail

# Post-contract deployment guard for the only supported application rollback:
# current final-schema code running in rollback-compat-v2 mode. The database
# remains on the final schema. Operators must pause, drain, and revoke through
# the reviewed control path before invoking this script.

readonly EXPECTED_EPOCH="template-twin-final-schema-v2"
readonly BRIDGE_MODE="rollback-compat-v2"
readonly ROLLBACK_STATE_VERSION="six-runtime-v1"
readonly PRE_STACK_APP_ID="sha256:95f57158e3fe56acc832793be3f5da972cc1fdc6c3b85166f8387b3a103f1f90"
readonly PRE_STACK_WORKER_ID="sha256:412dd3157475fd60a77d417a6db6880343d58755aaf76f044be035fba4acf44e"

readonly RUNTIME_SERVICES=(
  transcribe-md
  template-twin-admin-app
  template-twin-admin-control
  transcribe-md-worker
  template-twin-audit-dispatcher
  auth-email-dispatcher
)
declare -Ar SERVICE_ARTIFACT=(
  [transcribe-md]="app"
  [template-twin-admin-app]="app"
  [template-twin-admin-control]="app"
  [transcribe-md-worker]="worker"
  [template-twin-audit-dispatcher]="worker"
  [auth-email-dispatcher]="worker"
)
declare -Ar SERVICE_ROLE=(
  [transcribe-md]="physician-app"
  [template-twin-admin-app]="template-twin-admin-app"
  [template-twin-admin-control]="template-twin-admin-control"
  [transcribe-md-worker]=""
  [template-twin-audit-dispatcher]="template-twin-audit-dispatcher"
  [auth-email-dispatcher]="auth-email-dispatcher"
)
declare -A pre_containers=()

app_image=""
worker_image=""
release_sha=""
compose_file="docker-compose.yml"
state_dir=""
execute_swap="false"
state_tmp=""
state_overlay=""
swap_started="false"

cleanup() {
  local status=$?
  if [[ -n "$state_tmp" && -f "$state_tmp" ]]; then
    rm -f -- "$state_tmp"
  fi
  if [[ "$status" -ne 0 && "$swap_started" == "true" ]]; then
    printf '%s\n' \
      "runtime-swap: six-service transition did not complete; persisted rollout remains revoked and every recreated process is pinned to the active kill switch" \
      "runtime-swap: do not use mutable Compose defaults; recover only with the recorded immutable rollback overlay" >&2
  fi
}
trap cleanup EXIT

usage() {
  printf '%s\n' \
    "Usage: $0 --app-image <ref> --worker-image <ref> --release-sha <40-hex> [--compose-file <path>] [--state-dir <absolute-existing-dir>] [--execute]" \
    "" \
    "Without --execute this performs read-only verification. --execute requires" \
    "an operator-owned state directory outside the release checkout, persists a" \
    "content-addressed read-only Compose overlay, and recreates the exact six" \
    "long-lived app/worker-artifact services. The DB migrator is never invoked."
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
    --state-dir)
      state_dir="${2:-}"
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
if [[ ! -f "$compose_file" || -L "$compose_file" ]]; then
  printf 'runtime-swap: compose file must be a regular non-symlink file\n' >&2
  exit 66
fi
for required_command in docker node sha256sum mktemp stat; do
  if ! command -v "$required_command" >/dev/null 2>&1; then
    printf 'runtime-swap: required command unavailable: %s\n' "$required_command" >&2
    exit 69
  fi
done

compose_dir="$(cd -- "$(dirname -- "$compose_file")" && pwd -P)"
compose_file="$compose_dir/$(basename -- "$compose_file")"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
census_script="$script_dir/template-twin-runtime-census.mjs"
if [[ ! -f "$census_script" || -L "$census_script" ]]; then
  printf 'runtime-swap: reviewed runtime census helper is unavailable\n' >&2
  exit 66
fi

if [[ "$execute_swap" == "true" ]]; then
  if [[ -z "$state_dir" || "$state_dir" != /* || ! -d "$state_dir" || -L "$state_dir" ]]; then
    printf 'runtime-swap: --execute requires an absolute existing non-symlink state directory\n' >&2
    exit 64
  fi
  state_dir="$(cd -- "$state_dir" && pwd -P)"
  case "$state_dir/" in
    "$compose_dir/"*)
      printf 'runtime-swap: rollback state must be stored outside the mutable release checkout\n' >&2
      exit 64
      ;;
  esac
  if [[ ! -w "$state_dir" ]]; then
    printf 'runtime-swap: rollback state directory is not writable by the deployment authority\n' >&2
    exit 73
  fi
  state_mode="$(stat -c '%a' "$state_dir")"
  if [[ ! "$state_mode" =~ ^[0-7]{3,4}$ ]] || (( (8#$state_mode) & 0022 )); then
    printf 'runtime-swap: rollback state directory must not be group- or world-writable\n' >&2
    exit 73
  fi
fi

compose=(docker compose -f "$compose_file")

verify_compose_census() {
  "${compose[@]}" config --no-interpolate --no-env-resolution --format json |
    node "$census_script"
}

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
  if [[ ! "$resolved_id" =~ ^sha256:[a-f0-9]{64}$ ]]; then
    printf 'runtime-swap: %s image did not resolve to an immutable local image ID\n' "$component" >&2
    return 1
  fi
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

single_service_container() {
  local service="$1"
  local output
  local -a ids=()
  output="$("${compose[@]}" ps --all -q "$service")"
  while IFS= read -r id; do
    [[ -n "$id" ]] && ids+=("$id")
  done <<< "$output"
  if [[ "${#ids[@]}" -ne 1 ]]; then
    printf 'runtime-swap: %s must resolve to exactly one existing container\n' "$service" >&2
    return 1
  fi
  printf '%s' "${ids[0]}"
}

container_env_exact() {
  local container="$1"
  local expected="$2"
  local result
  if [[ ! "$expected" =~ ^[A-Za-z0-9_:.=@/+,-]+$ ]]; then
    printf 'runtime-swap: internal environment assertion is invalid\n' >&2
    return 1
  fi
  result="$(docker inspect --format "{{range .Config.Env}}{{if eq . \"$expected\"}}MATCH{{end}}{{end}}" "$container")"
  [[ "$result" == "MATCH" ]]
}

verify_current_runtime_census() {
  local service artifact role container current_image component epoch revision
  for service in "${RUNTIME_SERVICES[@]}"; do
    artifact="${SERVICE_ARTIFACT[$service]}"
    role="${SERVICE_ROLE[$service]}"
    container="$(single_service_container "$service")"
    pre_containers["$service"]="$container"
    if [[ "$(docker inspect --format '{{.State.Status}}' "$container")" != "running" ]]; then
      printf 'runtime-swap: %s is not running before the guarded transition\n' "$service" >&2
      return 1
    fi
    # Compose's own service identity must be exact. The newly introduced
    # rollback labels are required on the recreated containers below, not on
    # the pre-swap deployment: requiring them here would make the first safe
    # transition from an earlier final-schema image circular. Artifact labels
    # on the current image and the static Compose census still fail closed.
    if [[ "$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.service" }}' "$container")" != "$service" ]]; then
      printf 'runtime-swap: %s live Compose service identity is invalid\n' "$service" >&2
      return 1
    fi
    current_image="$(docker inspect --format '{{.Image}}' "$container")"
    case "$current_image" in
      "$PRE_STACK_APP_ID"|"$PRE_STACK_WORKER_ID")
        printf 'runtime-swap: %s is running an explicitly rejected pre-stack image\n' "$service" >&2
        return 1
        ;;
    esac
    component="transcribe-md-$artifact"
    epoch="$(image_label "$current_image" com.quillmd.runtime-protocol-epoch)"
    revision="$(image_label "$current_image" org.opencontainers.image.revision)"
    if [[ "$epoch" != "$EXPECTED_EPOCH" ||
          "$(image_label "$current_image" com.quillmd.runtime-component)" != "$component" ||
          ! "$revision" =~ ^[a-f0-9]{40}$ ]]; then
      printf 'runtime-swap: %s current image is outside the final-schema protocol\n' "$service" >&2
      return 1
    fi
    if ! container_env_exact "$container" "QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH=$EXPECTED_EPOCH" ||
       ! container_env_exact "$container" "TEMPLATE_TWIN_KILL_SWITCH=true"; then
      printf 'runtime-swap: %s current protocol or kill-switch state is unsafe\n' "$service" >&2
      return 1
    fi
    if ! container_env_exact "$container" "TEMPLATE_TWIN_RUNTIME_MODE=standard" &&
       ! container_env_exact "$container" "TEMPLATE_TWIN_RUNTIME_MODE=$BRIDGE_MODE"; then
      printf 'runtime-swap: %s current runtime mode is invalid\n' "$service" >&2
      return 1
    fi
    if [[ -n "$role" ]] && ! container_env_exact "$container" "QUILLMD_SERVICE_ROLE=$role"; then
      printf 'runtime-swap: %s current service role is invalid\n' "$service" >&2
      return 1
    fi
  done
}

psql_value() {
  "${compose[@]}" exec -T postgres \
    psql -X -v ON_ERROR_STOP=1 \
      -U "${POSTGRES_USER:-meddoc}" \
      -d "${POSTGRES_DB:-meddoc}" \
      -Atqc "$1"
}

verify_revoked_and_drained() {
  local lineage_phase global_enabled enabled_practices active_twin_templates
  local unsettled_twin_provider_work unsettled_twin_visits unsettled_twin_runs
  local queue_active cleanup_queue_active
  lineage_phase="$(psql_value \
    "SELECT \"phase\" FROM \"template_twin_lineage_migration_progress\" WHERE \"operationKey\"='note_templates_lineage_v1';")"
  if [[ "$lineage_phase" != "CONTRACTED" ]]; then
    printf 'runtime-swap: final lineage schema is not CONTRACTED\n' >&2
    return 1
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
    return 1
  fi
  if [[ "$active_twin_templates" != "0" ]]; then
    printf 'runtime-swap: active Template Twin versions must be deactivated before bridge swap\n' >&2
    return 1
  fi
  if [[ "$unsettled_twin_provider_work" != "0" ]]; then
    printf 'runtime-swap: unsettled Template Twin provider work blocks bridge swap\n' >&2
    return 1
  fi
  if [[ "$unsettled_twin_visits" != "0" || "$unsettled_twin_runs" != "0" ]]; then
    printf 'runtime-swap: unsettled Template Twin visits or synthetic runs block bridge swap\n' >&2
    return 1
  fi

  queue_active="$("${compose[@]}" exec -T redis redis-cli --raw LLEN bull:transcribe-md:active)"
  cleanup_queue_active="$("${compose[@]}" exec -T redis redis-cli --raw LLEN bull:transcribe-md-cleanup:active)"
  if [[ "$queue_active" != "0" || "$cleanup_queue_active" != "0" ]]; then
    printf 'runtime-swap: visit or maintenance worker queue is not drained\n' >&2
    return 1
  fi
}

write_state_overlay() {
  local service artifact image role state_hash final_path
  umask 077
  state_tmp="$(mktemp "$state_dir/.template-twin-rollback.XXXXXX")"
  {
    printf '%s\n' \
      '# Generated by template-twin-runtime-swap.sh; contains no credentials.' \
      '# Content-addressed rollback state. Do not edit or replace in place.' \
      'services:'
    for service in "${RUNTIME_SERVICES[@]}"; do
      artifact="${SERVICE_ARTIFACT[$service]}"
      role="${SERVICE_ROLE[$service]}"
      if [[ "$artifact" == "app" ]]; then
        image="$app_id"
      else
        image="$worker_id"
      fi
      printf '  %s:\n' "$service"
      printf '    image: "%s"\n' "$image"
      printf '%s\n' '    pull_policy: never'
      printf '%s\n' \
        '    labels:' \
        '      com.quillmd.rollback-runtime-managed: "true"'
      printf '      com.quillmd.rollback-runtime-artifact: "%s"\n' "$artifact"
      printf '      com.quillmd.rollback-state-version: "%s"\n' "$ROLLBACK_STATE_VERSION"
      printf '      com.quillmd.rollback-release-sha: "%s"\n' "$release_sha"
      printf '%s\n' '    environment:'
      if [[ -n "$role" ]]; then
        printf '      QUILLMD_SERVICE_ROLE: "%s"\n' "$role"
      fi
      printf '      QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH: "%s"\n' "$EXPECTED_EPOCH"
      printf '      TEMPLATE_TWIN_RUNTIME_MODE: "%s"\n' "$BRIDGE_MODE"
      printf '%s\n' '      TEMPLATE_TWIN_KILL_SWITCH: "true"'
      printf '      TEMPLATE_TWIN_RELEASE_COMMIT_SHA: "%s"\n' "$release_sha"
      printf '      TEMPLATE_TWIN_APP_IMAGE_DIGEST: "%s"\n' "$app_id"
      printf '      TEMPLATE_TWIN_WORKER_IMAGE_DIGEST: "%s"\n' "$worker_id"
      # Standard-mode envelopes are instance/image bound and must never flow
      # into a bridge recreate. An active kill switch makes NOT_CONFIGURED the
      # intended fail-closed attestation result for every rollback process.
      printf '%s\n' \
        '      TEMPLATE_TWIN_RUNTIME_ATTESTATION: ""' \
        '      TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION: ""' \
        '      TEMPLATE_TWIN_ADMIN_APP_RUNTIME_ATTESTATION: ""' \
        '      TEMPLATE_TWIN_ADMIN_CONTROL_RUNTIME_ATTESTATION: ""' \
        '      TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION: ""'
    done
  } > "$state_tmp"

  if grep -Eq '(DATABASE_URL|PASSWORD|AUTH_SECRET|API_KEY|ACCESS_TOKEN|REFRESH_TOKEN)[:=]' "$state_tmp"; then
    printf 'runtime-swap: generated rollback overlay unexpectedly contains a credential field\n' >&2
    return 1
  fi
  read -r state_hash _ < <(sha256sum "$state_tmp")
  final_path="$state_dir/template-twin-rollback-${release_sha}-${state_hash}.override.yml"
  if [[ -e "$final_path" ]]; then
    if [[ -L "$final_path" || ! -f "$final_path" || ! -O "$final_path" ||
          "$(stat -c '%a' "$final_path")" != "444" ||
          "$(sha256sum "$final_path" | cut -d ' ' -f 1)" != "$state_hash" ]] ||
       ! cmp -s "$state_tmp" "$final_path"; then
      printf 'runtime-swap: existing rollback state path is not the exact immutable overlay\n' >&2
      return 1
    fi
    rm -f -- "$state_tmp"
    state_tmp=""
  else
    if ! ln "$state_tmp" "$final_path"; then
      printf 'runtime-swap: could not atomically persist rollback overlay\n' >&2
      return 1
    fi
    chmod 0444 "$final_path"
    rm -f -- "$state_tmp"
    state_tmp=""
  fi
  state_overlay="$final_path"
  state_overlay_sha256="$state_hash"
}

verify_compose_census
verify_current_runtime_census

app_id="$(verify_image "$app_image" transcribe-md-app)"
worker_id="$(verify_image "$worker_image" transcribe-md-worker)"
if [[ "$app_id" == "$worker_id" ]]; then
  printf 'runtime-swap: app and worker unexpectedly resolve to one image\n' >&2
  exit 65
fi

verify_revoked_and_drained

# Resolve the references a second time immediately before any state change.
if [[ "$(image_id "$app_image")" != "$app_id" || "$(image_id "$worker_image")" != "$worker_id" ]]; then
  printf 'runtime-swap: an image reference changed during verification\n' >&2
  exit 65
fi

printf 'runtime-swap: PASS epoch=%s release=%s app=%s worker=%s mode=%s services=%s migrator=excluded\n' \
  "$EXPECTED_EPOCH" "$release_sha" "$app_id" "$worker_id" "$BRIDGE_MODE" "${#RUNTIME_SERVICES[@]}"

if [[ "$execute_swap" != "true" ]]; then
  printf 'runtime-swap: read-only verification complete; no containers changed\n'
  exit 0
fi

write_state_overlay
printf 'runtime-swap: immutable rollback state ready state_sha256=%s overlay=%s\n' \
  "$state_overlay_sha256" "$state_overlay"
state_compose=(docker compose -f "$compose_file" -f "$state_overlay")
"${state_compose[@]}" config --no-interpolate --no-env-resolution --format json |
  node "$census_script" \
    --expected-app-image "$app_id" \
    --expected-worker-image "$worker_id" \
    --require-bridge

# Stopping all six before recreation prevents a partial Compose failure from
# leaving an old standard-mode process serving alongside the bridge. The live
# pre-census above requires the old processes to have the kill switch active;
# the persisted database rollout is also revoked and is rechecked after start.
for service in "${RUNTIME_SERVICES[@]}"; do
  if [[ "$(single_service_container "$service")" != "${pre_containers[$service]}" ]]; then
    printf 'runtime-swap: %s container identity changed before the guarded transition\n' "$service" >&2
    exit 70
  fi
done
swap_started="true"
"${state_compose[@]}" stop --timeout 45 "${RUNTIME_SERVICES[@]}"
"${state_compose[@]}" up -d --no-build --no-deps --force-recreate \
  "${RUNTIME_SERVICES[@]}"

declare -A post_containers=()
for service in "${RUNTIME_SERVICES[@]}"; do
  container="$(single_service_container "$service")"
  post_containers["$service"]="$container"
  artifact="${SERVICE_ARTIFACT[$service]}"
  role="${SERVICE_ROLE[$service]}"
  if [[ "$artifact" == "app" ]]; then
    expected_image="$app_id"
  else
    expected_image="$worker_id"
  fi
  if [[ "$(docker inspect --format '{{.Image}}' "$container")" != "$expected_image" ]]; then
    printf 'runtime-swap: %s running image does not match the immutable rollback image\n' "$service" >&2
    exit 70
  fi
  if [[ "$(docker inspect --format '{{.State.Status}}' "$container")" != "running" ||
        "$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.service" }}' "$container")" != "$service" ||
        "$(docker inspect --format '{{ index .Config.Labels "com.quillmd.rollback-runtime-managed" }}' "$container")" != "true" ||
        "$(docker inspect --format '{{ index .Config.Labels "com.quillmd.rollback-runtime-artifact" }}' "$container")" != "$artifact" ||
        "$(docker inspect --format '{{ index .Config.Labels "com.quillmd.rollback-state-version" }}' "$container")" != "$ROLLBACK_STATE_VERSION" ||
        "$(docker inspect --format '{{ index .Config.Labels "com.quillmd.rollback-release-sha" }}' "$container")" != "$release_sha" ]]; then
    printf 'runtime-swap: %s running identity or rollback labels are invalid\n' "$service" >&2
    exit 70
  fi
  if ! container_env_exact "$container" "QUILLMD_REQUIRED_RUNTIME_PROTOCOL_EPOCH=$EXPECTED_EPOCH" ||
     ! container_env_exact "$container" "TEMPLATE_TWIN_RUNTIME_MODE=$BRIDGE_MODE" ||
     ! container_env_exact "$container" "TEMPLATE_TWIN_KILL_SWITCH=true" ||
     ! container_env_exact "$container" "TEMPLATE_TWIN_RELEASE_COMMIT_SHA=$release_sha" ||
     ! container_env_exact "$container" "TEMPLATE_TWIN_RUNTIME_ATTESTATION=" ||
     ! container_env_exact "$container" "TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION=" ||
     ! container_env_exact "$container" "TEMPLATE_TWIN_ADMIN_APP_RUNTIME_ATTESTATION=" ||
     ! container_env_exact "$container" "TEMPLATE_TWIN_ADMIN_CONTROL_RUNTIME_ATTESTATION=" ||
     ! container_env_exact "$container" "TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION="; then
    printf 'runtime-swap: %s running protocol, mode, release, or kill-switch state is invalid\n' "$service" >&2
    exit 70
  fi
  if [[ -n "$role" ]] && ! container_env_exact "$container" "QUILLMD_SERVICE_ROLE=$role"; then
    printf 'runtime-swap: %s running service role is invalid\n' "$service" >&2
    exit 70
  fi
done

all_healthy="false"
for _attempt in $(seq 1 30); do
  all_healthy="true"
  for service in "${RUNTIME_SERVICES[@]}"; do
    if [[ "$(single_service_container "$service")" != "${post_containers[$service]}" ]]; then
      printf 'runtime-swap: %s container identity changed during health verification\n' "$service" >&2
      exit 70
    fi
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${post_containers[$service]}")"
    if [[ "$health" == "none" ]]; then
      printf 'runtime-swap: %s has no health contract\n' "$service" >&2
      exit 70
    fi
    if [[ "$health" != "healthy" ]]; then
      all_healthy="false"
    fi
  done
  [[ "$all_healthy" == "true" ]] && break
  sleep 2
done
if [[ "$all_healthy" != "true" ]]; then
  printf 'runtime-swap: one or more rollback services are unhealthy; keep rollout revoked and follow the rollback runbook\n' >&2
  exit 70
fi

verify_revoked_and_drained

printf 'runtime-swap: bridge services healthy count=%s state_sha256=%s overlay=%s\n' \
  "${#RUNTIME_SERVICES[@]}" "$state_overlay_sha256" "$state_overlay"
