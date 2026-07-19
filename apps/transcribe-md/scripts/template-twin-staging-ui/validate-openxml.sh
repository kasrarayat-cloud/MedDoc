#!/usr/bin/env bash
set -euo pipefail

: "${TEMPLATE_TWIN_STAGING_ARTIFACT_DIR:?required}"
: "${QA_SOURCE_COMMIT:?required}"
: "${QA_GENERATED_AT:?required}"

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
ARTIFACT_ROOT="$(realpath "$TEMPLATE_TWIN_STAGING_ARTIFACT_DIR")"
SHORT="${QA_SOURCE_COMMIT:0:12}"
DOTNET_IMAGE="mcr.microsoft.com/dotnet/sdk@sha256:aabe48e2f28d3a10bed9cfb7beb8afc7ad4234578c0fdb11f03413b69941faea"
SOURCE_DOCX="$ARTIFACT_ROOT/template-twin-staging-source.docx"
OUTPUT_DOCX="$ARTIFACT_ROOT/template-twin-staging-output.docx"
RESULT_ROOT="$ARTIFACT_ROOT/openxml"
BUILD_ROOT="/tmp/template-twin-staging-openxml-$SHORT"

[[ "$QA_SOURCE_COMMIT" =~ ^[a-f0-9]{40}$ ]]
[[ "$(git rev-parse HEAD)" == "$QA_SOURCE_COMMIT" ]]
[[ -f "$SOURCE_DOCX" && -f "$OUTPUT_DOCX" ]]
rm -rf "$BUILD_ROOT"
trap 'rm -rf "$BUILD_ROOT"' EXIT
mkdir -p "$BUILD_ROOT" "$RESULT_ROOT"
cp "$PROJECT_ROOT/apps/transcribe-md/scripts/template-twin-human-gate/openxml-validator/"{OpenXmlValidator.csproj,Program.cs,packages.lock.json} "$BUILD_ROOT/"

docker run --rm --network bridge --read-only --cap-drop ALL \
  --security-opt no-new-privileges --user "$(id -u):$(id -g)" \
  --memory 1g --cpus 2 --pids-limit 256 \
  --tmpfs /tmp:rw,noexec,nosuid,size=256m -e HOME=/tmp \
  -v "$BUILD_ROOT:/src:rw" -w /src "$DOTNET_IMAGE" \
  sh -c 'dotnet restore --locked-mode && dotnet publish --no-restore -c Release -o /src/publish'

for target in Office2013 Microsoft365; do
  output="staging-ui-${target}.json"
  docker run --rm --network none --read-only --cap-drop ALL \
    --security-opt no-new-privileges --user "$(id -u):$(id -g)" \
    --memory 768m --cpus 2 --pids-limit 128 \
    --tmpfs /tmp:rw,noexec,nosuid,size=128m -e HOME=/tmp \
    -e "OPENXML_TARGET=$target" -e "QA_SOURCE_COMMIT=$QA_SOURCE_COMMIT" \
    -e "QA_GENERATED_AT=$QA_GENERATED_AT" \
    -v "$BUILD_ROOT/publish:/validator:ro" \
    -v "$ARTIFACT_ROOT:/documents:ro" -v "$RESULT_ROOT:/out:rw" \
    -w /out --entrypoint dotnet "$DOTNET_IMAGE" \
    /validator/OpenXmlValidator.dll "/out/$output" \
    /documents/template-twin-staging-source.docx \
    /documents/template-twin-staging-output.docx
  jq -e --arg commit "$QA_SOURCE_COMMIT" '
    .sourceCommit == $commit and
    .tool == "DocumentFormat.OpenXml.OpenXmlValidator" and
    .sdkVersion == "3.5.1.0" and
    all(.results[]; .opened and .valid and .errorCount == 0 and (.errors | length == 0))
  ' "$RESULT_ROOT/$output" >/dev/null
done

sha256sum "$RESULT_ROOT"/*.json | LC_ALL=C sort > "$RESULT_ROOT/SHA256SUMS.txt"
