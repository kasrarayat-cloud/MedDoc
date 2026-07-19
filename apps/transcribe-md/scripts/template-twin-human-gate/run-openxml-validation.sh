#!/usr/bin/env bash
set -euo pipefail

: "${TEMPLATE_TWIN_HUMAN_GATE_ROOT:?required}"
: "${QA_SOURCE_COMMIT:?required}"
: "${QA_GENERATED_AT:?required}"

ROOT="$TEMPLATE_TWIN_HUMAN_GATE_ROOT"
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
SHORT="${QA_SOURCE_COMMIT:0:12}"
DOTNET_IMAGE="mcr.microsoft.com/dotnet/sdk@sha256:aabe48e2f28d3a10bed9cfb7beb8afc7ad4234578c0fdb11f03413b69941faea"
[[ "$ROOT" == "/tmp/template-twin-human-gate-$SHORT" ]]
[[ "$QA_SOURCE_COMMIT" =~ ^[a-f0-9]{40}$ ]]
[[ "$(git rev-parse HEAD)" == "$QA_SOURCE_COMMIT" ]]

BUILD_ROOT="$ROOT/openxml-build"
RESULT_ROOT="$ROOT/office-evidence/openxml"
rm -rf "$BUILD_ROOT"
rm -rf "$RESULT_ROOT"
mkdir -p "$BUILD_ROOT" "$RESULT_ROOT"
cp "$PROJECT_ROOT/apps/transcribe-md/scripts/template-twin-human-gate/openxml-validator/"{OpenXmlValidator.csproj,Program.cs,packages.lock.json} "$BUILD_ROOT/"

docker run --rm --network bridge --read-only --cap-drop ALL --security-opt no-new-privileges \
  --user "$(id -u):$(id -g)" --memory 2g --cpus 2 --pids-limit 256 \
  --tmpfs /tmp:rw,noexec,nosuid,size=1g -e DOTNET_CLI_HOME=/tmp/dotnet-cli -e NUGET_PACKAGES=/tmp/nuget \
  -v "$BUILD_ROOT:/src:rw" -w /src "$DOTNET_IMAGE" \
  sh -c 'dotnet restore --locked-mode && dotnet publish --no-restore -c Release -r linux-x64 --self-contained true -p:PublishSingleFile=true -p:DebugType=None -p:DebugSymbols=false -o /src/publish-linux && dotnet publish --no-restore -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:DebugType=None -p:DebugSymbols=false -o /src/publish-windows'
# The desktop package validates the bytes Word actually saved. The Windows
# build is self-contained so reviewer machines need no separately managed SDK.
[[ -s "$BUILD_ROOT/publish-windows/OpenXmlValidator.exe" ]]

mapfile -t DOCUMENTS < <(find "$ROOT/corpus" -mindepth 2 -maxdepth 2 -type f \( -name '*.source.docx' -o -name '*.output.docx' \) -print | LC_ALL=C sort)
[[ "${#DOCUMENTS[@]}" -ge 2 ]]
CONTAINER_DOCUMENTS=()
for file in "${DOCUMENTS[@]}"; do CONTAINER_DOCUMENTS+=("${file/$ROOT\/corpus/\/corpus}"); done

for target in Office2013 Microsoft365; do
  output="pre-delivery-${target}.json"
  docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
    --user "$(id -u):$(id -g)" --memory 768m --cpus 2 --pids-limit 128 \
    --tmpfs /tmp:rw,noexec,nosuid,size=128m \
    -e "OPENXML_TARGET=$target" -e "QA_SOURCE_COMMIT=$QA_SOURCE_COMMIT" -e "QA_GENERATED_AT=$QA_GENERATED_AT" \
    -v "$BUILD_ROOT/publish-linux:/validator:ro" -v "$ROOT/corpus:/corpus:ro" -v "$RESULT_ROOT:/out:rw" \
    -w /out --entrypoint /validator/OpenXmlValidator "$DOTNET_IMAGE" "/out/$output" "${CONTAINER_DOCUMENTS[@]}"
  jq -e --arg commit "$QA_SOURCE_COMMIT" '
    .sourceCommit == $commit and
    .tool == "DocumentFormat.OpenXml.OpenXmlValidator" and
    .sdkVersion == "3.5.1.0" and
    all(.results[]; .opened and .valid and .errorCount == 0 and (.errors | length == 0))
  ' "$RESULT_ROOT/$output" >/dev/null
done

sha256sum "$RESULT_ROOT"/*.json | LC_ALL=C sort > "$RESULT_ROOT/SHA256SUMS.txt"
jq -n --arg sourceCommit "$QA_SOURCE_COMMIT" --arg generatedAtIso "$QA_GENERATED_AT" --argjson documentCount "${#DOCUMENTS[@]}" \
  '{contractVersion:"template-twin-human-gate-openxml-evidence/1.0.0",sourceCommit:$sourceCommit,generatedAtIso:$generatedAtIso,syntheticOnly:true,documentCount:$documentCount,Office2013:"passed",Microsoft365:"passed"}' \
  > "$RESULT_ROOT/summary.json"
