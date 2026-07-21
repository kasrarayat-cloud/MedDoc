#!/usr/bin/env bash

set -euo pipefail
set +x

readonly SAFE_FAILURE="TEMPLATE_TWIN_SYNTHETIC_CI_ORCHESTRATION_FAILED"
readonly SAFE_SUCCESS="TEMPLATE_TWIN_SYNTHETIC_CI_ORCHESTRATION_OK"
readonly EXPECTED_APP_MEMORY_BYTES="805306368"
readonly SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIRECTORY/.." && pwd -P)"
readonly COMPOSE_FILE="$REPOSITORY_ROOT/docker-compose.qa.yml"

fail() {
  printf '%s\n' "$SAFE_FAILURE" >&2
  exit 1
}

require_environment() {
  local name="$1"
  [[ -n "${!name:-}" && "${!name}" != *$'\n'* && "${!name}" != *$'\r'* ]] || fail
}

assert_no_ambient_runtime_overrides() {
  local name
  # Shell variables take precedence over Compose --env-file values. Refuse an
  # inherited authority or authentication/provider override before validating
  # or acting on this synthetic lifecycle. The two protected path/profile
  # capabilities exported by PREPARE are intentionally not in this list.
  for name in \
    QA_TEMPLATE_TWIN_RUNTIME_ENV_VERSION \
    QA_TEMPLATE_TWIN_KILL_SWITCH \
    QA_TEMPLATE_TWIN_RUNTIME_MODE \
    QA_TEMPLATE_TWIN_RELEASE_IDENTITY_SHA256 \
    QA_TEMPLATE_TWIN_RELEASE_COMMIT_SHA \
    QA_TEMPLATE_TWIN_APP_IMAGE_DIGEST \
    QA_TEMPLATE_TWIN_WORKER_IMAGE_DIGEST \
    QA_TEMPLATE_TWIN_MIGRATOR_IMAGE_DIGEST \
    QA_TEMPLATE_TWIN_APP_INSTANCE_ID \
    QA_TEMPLATE_TWIN_WORKER_INSTANCE_ID \
    QA_TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION \
    QA_TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION \
    AUTH_USE_MOCK \
    MOCK_AI_CALLS \
    MOCK_TEMPLATE_TWIN_E2E \
    TEMPLATE_TWIN_STAGING_QA_ENABLED \
    TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT \
    TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION \
    COMPOSE_PROJECT_NAME \
    COMPOSE_FILE \
    COMPOSE_PROFILES \
    COMPOSE_ENV_FILES \
    DOCKER_HOST \
    DOCKER_CONTEXT \
    DOCKER_TLS_VERIFY \
    DOCKER_CERT_PATH \
    DOCKER_CONFIG \
    OPENAI_API_KEY \
    ANTHROPIC_API_KEY \
    DEEPGRAM_API_KEY; do
    [[ -z "${!name+x}" ]] || fail
  done
}

assert_local_docker_authority() {
  local context endpoint
  context="$(docker context show 2>/dev/null)" || fail
  [[ "$context" == "default" ]] || fail
  endpoint="$(docker context inspect default \
    --format '{{.Endpoints.docker.Host}}' 2>/dev/null)" || fail
  [[ "$endpoint" == "unix:///var/run/docker.sock" ]] || fail
}

assert_github_boundary() {
  local name
  for name in \
    CI GITHUB_ACTIONS GITHUB_REPOSITORY GITHUB_EVENT_NAME GITHUB_RUN_ID \
    GITHUB_RUN_ATTEMPT GITHUB_SHA GITHUB_ENV RUNNER_TEMP QUILLMD_RELEASE_SHA \
    QA_TRANSCRIBE_MD_IMAGE QA_TRANSCRIBE_MD_WORKER_IMAGE QA_DB_MIGRATE_IMAGE \
    QA_DB_RELEASE_CONTROL_PASSWORD QA_DB_RUNTIME_PASSWORD; do
    require_environment "$name"
  done

  [[ "$CI" == "true" ]] || fail
  [[ "$GITHUB_ACTIONS" == "true" ]] || fail
  [[ "$GITHUB_REPOSITORY" == "kasrarayat-cloud/MedDoc" ]] || fail
  [[ "$GITHUB_EVENT_NAME" == "pull_request" || "$GITHUB_EVENT_NAME" == "push" ]] || fail
  [[ "$GITHUB_RUN_ID" =~ ^[1-9][0-9]{0,19}$ ]] || fail
  [[ "$GITHUB_RUN_ATTEMPT" =~ ^[1-9][0-9]{0,19}$ ]] || fail
  [[ "$GITHUB_SHA" =~ ^[a-f0-9]{40}$ ]] || fail
  [[ "$QUILLMD_RELEASE_SHA" =~ ^[a-f0-9]{40}$ ]] || fail
  [[ "$QA_TRANSCRIBE_MD_IMAGE" =~ ^sha256:[a-f0-9]{64}$ ]] || fail
  [[ "$QA_TRANSCRIBE_MD_WORKER_IMAGE" =~ ^sha256:[a-f0-9]{64}$ ]] || fail
  [[ "$QA_DB_MIGRATE_IMAGE" =~ ^sha256:[a-f0-9]{64}$ ]] || fail
  [[ "$QA_TRANSCRIBE_MD_IMAGE" != "$QA_TRANSCRIBE_MD_WORKER_IMAGE" ]] || fail
  [[ "$QA_DB_RELEASE_CONTROL_PASSWORD" =~ ^[A-Za-z0-9_-]{43,128}$ ]] || fail
  [[ "$QA_DB_RUNTIME_PASSWORD" =~ ^[A-Za-z0-9_-]{43,128}$ ]] || fail
  [[ -f "$COMPOSE_FILE" ]] || fail
  [[ "$RUNNER_TEMP" == /* && -d "$RUNNER_TEMP" && ! -L "$RUNNER_TEMP" ]] || fail
  [[ "$GITHUB_ENV" == /* && -f "$GITHUB_ENV" && ! -L "$GITHUB_ENV" ]] || fail
  assert_no_ambient_runtime_overrides
  assert_local_docker_authority
}

runner_temp_root() {
  realpath -- "$RUNNER_TEMP"
}

fixture_root() {
  printf '%s/quillmd-template-twin-ci-orchestrator-%s-%s\n' \
    "$(runner_temp_root)" "$GITHUB_RUN_ID" "$GITHUB_RUN_ATTEMPT"
}

fixture_output_directory() {
  printf '%s/quillmd-template-twin-release-fixture-%s-%s\n' \
    "$(fixture_root)" "$GITHUB_RUN_ID" "$GITHUB_RUN_ATTEMPT"
}

assert_private_directory() {
  local directory="$1"
  local expected_parent
  expected_parent="$(runner_temp_root)"
  [[ "$directory" == "$expected_parent"/* ]] || fail
  [[ -d "$directory" && ! -L "$directory" ]] || fail
  [[ "$(realpath -- "$directory")" == "$directory" ]] || fail
  [[ "$(stat -c '%a' -- "$directory")" == "700" ]] || fail
}

initialize_fixture_root() {
  local root
  root="$(fixture_root)"
  if [[ ! -e "$root" ]]; then
    install -d -m 0700 -- "$root"
  fi
  assert_private_directory "$root"
}

container_github_environment() {
  local root base command_directory target
  root="$(fixture_root)"
  base="$(basename -- "$GITHUB_ENV")"
  [[ "$base" =~ ^set_env_[A-Za-z0-9_-]+$ ]] || fail
  command_directory="$root/_runner_file_commands"
  if [[ ! -e "$command_directory" ]]; then
    install -d -m 0700 -- "$command_directory"
  fi
  assert_private_directory "$command_directory"
  target="$command_directory/$base"
  if [[ -L "$target" || -d "$target" ]]; then
    fail
  fi
  if [[ ! -e "$target" ]]; then
    install -m 0600 /dev/null "$target"
  fi
  [[ -f "$target" && ! -L "$target" ]] || fail
  chmod 0600 -- "$target"
  printf '%s\n' "$target"
}

run_fixture_phase() {
  local phase="$1"
  local root github_environment_target host_github_environment host_runner_temp
  local host_uid host_gid
  case "$phase" in
    prepare|activate|replace|revoke|cleanup) ;;
    *) fail ;;
  esac

  assert_github_boundary
  initialize_fixture_root
  root="$(fixture_root)"
  host_github_environment="$GITHUB_ENV"
  host_runner_temp="$RUNNER_TEMP"
  github_environment_target="$(container_github_environment)"
  host_uid="$(id -u)"
  host_gid="$(id -g)"
  [[ "$host_uid" =~ ^[0-9]+$ && "$host_gid" =~ ^[0-9]+$ ]] || fail

  export TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL=
  TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL="postgresql://meddoc_release_control:${QA_DB_RELEASE_CONTROL_PASSWORD}@127.0.0.1:5432/meddoc_qa_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic"
  export TEMPLATE_TWIN_SYNTHETIC_RUNTIME_DATABASE_URL=
  TEMPLATE_TWIN_SYNTHETIC_RUNTIME_DATABASE_URL="postgresql://meddoc_runtime:${QA_DB_RUNTIME_PASSWORD}@127.0.0.1:5432/meddoc_qa_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic"
  export QUILLMD_SYNTHETIC_CI_RELEASE_FIXTURE="isolated-disposable-template-twin-v1"
  export QUILLMD_SYNTHETIC_CI_RELEASE_PROFILE="synthetic-ci-fixture/not-production"
  export QUILLMD_SYNTHETIC_CI_DATABASE_PROFILE="owner-release-control-runtime/meddoc-qa-test-v1"
  export QUILLMD_SYNTHETIC_CI_REPOSITORY_ROOT="/app"
  export QUILLMD_SYNTHETIC_CI_EXPECTED_SHA="$QUILLMD_RELEASE_SHA"
  export QUILLMD_SYNTHETIC_CI_FIXTURE_PHASE="$phase"
  export RUNNER_TEMP="$root"
  export GITHUB_ENV="$github_environment_target"

  docker compose -f "$COMPOSE_FILE" run --rm -T --no-deps \
    --user "$host_uid:$host_gid" \
    --volume "$root:$root:rw" \
    --volume "$host_github_environment:$github_environment_target:rw" \
    -e CI \
    -e GITHUB_ACTIONS \
    -e GITHUB_REPOSITORY \
    -e GITHUB_EVENT_NAME \
    -e GITHUB_RUN_ID \
    -e GITHUB_RUN_ATTEMPT \
    -e GITHUB_SHA \
    -e GITHUB_ENV \
    -e RUNNER_TEMP \
    -e QUILLMD_RELEASE_SHA \
    -e QUILLMD_SYNTHETIC_CI_RELEASE_FIXTURE \
    -e QUILLMD_SYNTHETIC_CI_RELEASE_PROFILE \
    -e QUILLMD_SYNTHETIC_CI_DATABASE_PROFILE \
    -e QUILLMD_SYNTHETIC_CI_REPOSITORY_ROOT \
    -e QUILLMD_SYNTHETIC_CI_EXPECTED_SHA \
    -e QUILLMD_SYNTHETIC_CI_FIXTURE_PHASE \
    -e QA_TRANSCRIBE_MD_IMAGE \
    -e QA_TRANSCRIBE_MD_WORKER_IMAGE \
    -e QA_DB_MIGRATE_IMAGE \
    -e TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL \
    -e TEMPLATE_TWIN_SYNTHETIC_RUNTIME_DATABASE_URL \
    --entrypoint sh db-migrate -c \
    'cd /app && npm run --silent release-control:synthetic-ci-fixture -w @meddoc/db -- --phase "$QUILLMD_SYNTHETIC_CI_FIXTURE_PHASE"'

  RUNNER_TEMP="$host_runner_temp"
  GITHUB_ENV="$host_github_environment"
  export RUNNER_TEMP GITHUB_ENV
}

assert_runtime_environment_file() {
  local expected_switch="$1"
  local file
  local root
  local metadata owner links bytes
  local switch_line_count
  file="$(runtime_environment_file)"
  root="$(fixture_root)"
  [[ "$expected_switch" == "true" || "$expected_switch" == "false" ]] || fail
  [[ "$file" == "$(fixture_output_directory)/runtime.env" ]] || fail
  [[ "$file" == "$root"/* && -f "$file" && ! -L "$file" ]] || fail
  [[ "$(realpath -- "$file")" == "$file" ]] || fail
  [[ "$(stat -c '%a' -- "$file")" == "600" ]] || fail
  metadata="$(stat -c '%u:%h:%s' -- "$file" 2>/dev/null)" || fail
  IFS=: read -r owner links bytes <<< "$metadata"
  [[ "$owner" == "$(id -u)" && "$links" == "1" ]] || fail
  [[ "$bytes" =~ ^[1-9][0-9]{0,5}$ && "$bytes" -le 32768 ]] || fail
  # Compose receives exactly the reviewed serializer surface. Refuse duplicate,
  # unknown, blank, or CR-bearing assignments before any container recreation.
  awk -F= '
    BEGIN {
      expected["QA_TEMPLATE_TWIN_RUNTIME_ENV_VERSION"] = 1
      expected["QA_TEMPLATE_TWIN_RELEASE_PROFILE"] = 1
      expected["QA_TEMPLATE_TWIN_KILL_SWITCH"] = 1
      expected["QA_TEMPLATE_TWIN_RUNTIME_MODE"] = 1
      expected["QA_TEMPLATE_TWIN_RELEASE_IDENTITY_SHA256"] = 1
      expected["QA_TEMPLATE_TWIN_RELEASE_COMMIT_SHA"] = 1
      expected["QA_TEMPLATE_TWIN_APP_IMAGE_DIGEST"] = 1
      expected["QA_TEMPLATE_TWIN_WORKER_IMAGE_DIGEST"] = 1
      expected["QA_TEMPLATE_TWIN_MIGRATOR_IMAGE_DIGEST"] = 1
      expected["QA_TEMPLATE_TWIN_APP_INSTANCE_ID"] = 1
      expected["QA_TEMPLATE_TWIN_WORKER_INSTANCE_ID"] = 1
      expected["QA_TEMPLATE_TWIN_APP_RUNTIME_ATTESTATION"] = 1
      expected["QA_TEMPLATE_TWIN_WORKER_RUNTIME_ATTESTATION"] = 1
    }
    {
      separator = index($0, "=")
      name = substr($0, 1, separator - 1)
      value = substr($0, separator + 1)
      if (separator < 2 || value == "" || $0 ~ /\r/ ||
          !(name in expected) || seen[name]++ != 0) exit 1
      count += 1
    }
    END { if (count != 13) exit 1 }
  ' "$file" || fail
  grep -Fqx -- \
    "QA_TEMPLATE_TWIN_RUNTIME_ENV_VERSION=template-twin-synthetic-runtime-env-v1" \
    "$file" || fail
  grep -Fqx -- \
    "QA_TEMPLATE_TWIN_RELEASE_PROFILE=synthetic-ci-fixture/not-production" \
    "$file" || fail
  switch_line_count="$(awk \
    '/^QA_TEMPLATE_TWIN_KILL_SWITCH=(true|false)$/ { count += 1 } END { print count + 0 }' \
    "$file")" || fail
  [[ "$switch_line_count" == "1" ]] || fail
  grep -Fqx -- "QA_TEMPLATE_TWIN_KILL_SWITCH=$expected_switch" "$file" || fail
}

runtime_environment_file() {
  if [[ -n "${QA_TEMPLATE_TWIN_RUNTIME_ENV_FILE:-}" ]]; then
    printf '%s\n' "$QA_TEMPLATE_TWIN_RUNTIME_ENV_FILE"
  else
    printf '%s/runtime.env\n' "$(fixture_output_directory)"
  fi
}

runtime_is_healthy() {
  local service container state app_container memory
  for service in transcribe-md transcribe-md-worker; do
    container="$(runtime_container_id "$service")" || return 1
    [[ -n "$container" ]] || return 1
    state="$(docker inspect --format \
      '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} {{.State.OOMKilled}}' \
      "$container" 2>/dev/null)" || return 1
    [[ "$state" == "running healthy false" ]] || return 1
  done
  app_container="$(runtime_container_id transcribe-md)" || return 1
  [[ -n "$app_container" ]] || return 1
  memory="$(docker inspect --format '{{.HostConfig.Memory}}' "$app_container" \
    2>/dev/null)" || return 1
  [[ "$memory" == "$EXPECTED_APP_MEMORY_BYTES" ]]
}

assert_runtime() {
  runtime_is_healthy || fail
  printf '%s\n' "$SAFE_SUCCESS"
}

runtime_profile() {
  case "${TEMPLATE_TWIN_SYNTHETIC_CI_RUNTIME_PROFILE:-}" in
    infrastructure|staging) printf '%s\n' "$TEMPLATE_TWIN_SYNTHETIC_CI_RUNTIME_PROFILE" ;;
    *) fail ;;
  esac
}

assert_transition_profile() {
  local expected="$1"
  local actual
  actual="$(runtime_profile)"
  case "$expected" in
    any)
      [[ "$actual" == "infrastructure" || "$actual" == "staging" ]] || fail
      ;;
    staging)
      [[ "$actual" == "staging" ]] || fail
      ;;
    *) fail ;;
  esac
}

runtime_container_id() {
  local service="$1"
  local container
  case "$service" in
    transcribe-md|transcribe-md-worker) ;;
    *) return 1 ;;
  esac
  container="$(docker compose -f "$COMPOSE_FILE" ps -a -q "$service" \
    2>/dev/null)" || return 1
  if [[ -n "$container" && ! "$container" =~ ^[a-f0-9]{12,64}$ ]]; then
    return 1
  fi
  printf '%s' "$container"
}

unpause_runtime_if_needed() {
  local service="$1"
  local container paused after_paused
  container="$(runtime_container_id "$service")" || fail
  if [[ -z "$container" ]]; then
    return
  fi
  paused="$(docker inspect --format '{{.State.Paused}}' "$container" \
    2>/dev/null)" || fail
  case "$paused" in
    true)
      docker unpause "$container" >/dev/null 2>&1 || fail
      after_paused="$(docker inspect --format '{{.State.Paused}}' "$container" \
        2>/dev/null)" || fail
      [[ "$after_paused" == "false" ]] || fail
      ;;
    false) ;;
    *) fail ;;
  esac
}

recreate_runtime() {
  local expected_switch="$1"
  local profile runtime_environment
  assert_github_boundary
  profile="$(runtime_profile)"
  runtime_environment="$(runtime_environment_file)"
  assert_runtime_environment_file "$expected_switch"
  unpause_runtime_if_needed transcribe-md
  unpause_runtime_if_needed transcribe-md-worker
  if [[ "$profile" == "staging" ]]; then
    AUTH_USE_MOCK=false \
    MOCK_AI_CALLS=true \
    MOCK_TEMPLATE_TWIN_E2E=true \
    TEMPLATE_TWIN_STAGING_QA_ENABLED=true \
    TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT=qa \
    TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION=isolated-disposable-qa-v1 \
      docker compose --env-file "$runtime_environment" \
        -f "$COMPOSE_FILE" up -d --wait --force-recreate \
        transcribe-md transcribe-md-worker
  else
    AUTH_USE_MOCK=false \
    MOCK_AI_CALLS=true \
    MOCK_TEMPLATE_TWIN_E2E=true \
      docker compose --env-file "$runtime_environment" \
        -f "$COMPOSE_FILE" up -d --wait --force-recreate \
        transcribe-md transcribe-md-worker
  fi
  assert_runtime
}

runtime_container_has_closed_switch() {
  local service="$1"
  local container marker
  container="$(runtime_container_id "$service")" || fail
  [[ -n "$container" ]] || return 1
  marker="$(docker inspect --format \
    '{{range .Config.Env}}{{if eq . "TEMPLATE_TWIN_KILL_SWITCH=true"}}closed{{end}}{{end}}' \
    "$container" 2>/dev/null)" || fail
  [[ "$marker" == "closed" ]]
}

ensure_closed_runtime() {
  local runtime_environment app_container worker_container
  if runtime_container_has_closed_switch transcribe-md && \
    runtime_container_has_closed_switch transcribe-md-worker; then
    unpause_runtime_if_needed transcribe-md
    unpause_runtime_if_needed transcribe-md-worker
    if runtime_is_healthy; then
      printf '%s\n' "$SAFE_SUCCESS"
      return
    fi
  fi
  app_container="$(runtime_container_id transcribe-md)" || fail
  worker_container="$(runtime_container_id transcribe-md-worker)" || fail
  if [[ -z "$app_container" && -z "$worker_container" ]]; then
    printf '%s\n' "$SAFE_SUCCESS"
    return
  fi
  runtime_environment="$(runtime_environment_file)"
  assert_runtime_environment_file true
  unpause_runtime_if_needed transcribe-md
  unpause_runtime_if_needed transcribe-md-worker
  AUTH_USE_MOCK=false \
  MOCK_AI_CALLS=true \
  MOCK_TEMPLATE_TWIN_E2E=true \
    docker compose --env-file "$runtime_environment" -f "$COMPOSE_FILE" \
      up -d --wait --force-recreate transcribe-md transcribe-md-worker
  runtime_container_has_closed_switch transcribe-md || fail
  runtime_container_has_closed_switch transcribe-md-worker || fail
  assert_runtime
}

fixture_exists() {
  [[ -d "$(fixture_root)" && ! -L "$(fixture_root)" ]]
}

destroy_fixture_root() {
  local root expected_parent
  assert_github_boundary
  root="$(fixture_root)"
  expected_parent="$(runner_temp_root)"
  if [[ ! -e "$root" ]]; then
    printf '%s\n' "$SAFE_SUCCESS"
    return
  fi
  [[ -d "$root" && ! -L "$root" ]] || fail
  [[ "$(realpath -- "$root")" == "$root" ]] || fail
  [[ "$(dirname -- "$root")" == "$expected_parent" ]] || fail
  [[ "$(basename -- "$root")" == \
    "quillmd-template-twin-ci-orchestrator-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}" ]] || fail
  find "$root" -depth -delete
  [[ ! -e "$root" ]] || fail
  printf '%s\n' "$SAFE_SUCCESS"
}

main() {
  local command="${1:-}"
  [[ "$#" -eq 1 ]] || fail
  case "$command" in
    prepare)
      run_fixture_phase prepare
      ;;
    recreate-disabled)
      recreate_runtime true
      ;;
    activate-cycle)
      assert_transition_profile any
      assert_runtime_environment_file true
      run_fixture_phase activate
      assert_runtime_environment_file false
      recreate_runtime false
      ;;
    replace-disabled)
      assert_transition_profile staging
      run_fixture_phase replace
      assert_runtime_environment_file true
      recreate_runtime true
      ;;
    replace-cycle)
      assert_transition_profile staging
      run_fixture_phase replace
      assert_runtime_environment_file true
      recreate_runtime true
      run_fixture_phase activate
      assert_runtime_environment_file false
      recreate_runtime false
      ;;
    revoke)
      assert_github_boundary
      if fixture_exists; then
        run_fixture_phase revoke
        # Recovery cleanup may intentionally publish only a minimal closed
        # marker after an interrupted PREPARE. If both replicas are already
        # closed, no envelope file is needed; otherwise ensure_closed_runtime
        # requires and validates the complete mode-0600 runtime.env before it
        # recreates either service.
        ensure_closed_runtime
      else
        printf '%s\n' "$SAFE_SUCCESS"
      fi
      ;;
    cleanup)
      assert_github_boundary
      if fixture_exists; then
        run_fixture_phase cleanup
        ensure_closed_runtime
      else
        printf '%s\n' "$SAFE_SUCCESS"
      fi
      ;;
    assert-runtime)
      assert_github_boundary
      assert_runtime
      ;;
    destroy)
      destroy_fixture_root
      ;;
    *) fail ;;
  esac
}

main "$@"
