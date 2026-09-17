#!/usr/bin/env bash
# Build the locked SDK in an isolated CI workspace; no shared application state.
set -euo pipefail
quillmd_repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
quillmd_python=${QUILLMD_CI_PYTHON:-python3}
quillmd_dotnet=$(command -v dotnet)
cd "$quillmd_repo"
"$quillmd_python" rebuild/documents/sdk_word/build_word.py \
  --dotnet "$quillmd_dotnet" \
  --cache "$quillmd_repo/rebuild/.runtime/nuget-cache" \
  --output "$quillmd_repo/rebuild/.runtime/word-ci"
"$quillmd_python" - <<'PY'
import hashlib, os
from pathlib import Path
root = Path.cwd() / 'rebuild/.runtime/word-ci'
values = {'QUILLMD_WORD_RUNTIME': str(root/'runtime'),
          'QUILLMD_WORD_MANIFEST': str(root/'runtime-manifest.json'),
          'QUILLMD_WORD_MANIFEST_SHA256': hashlib.sha256((root/'runtime-manifest.json').read_bytes()).hexdigest(),
          'QUILLMD_WORD_QUALIFICATION': '1', 'QUILLMD_REQUIRE_WORD_TESTS': '1'}
with Path(os.environ['GITHUB_ENV']).open('a') as stream:
    for name, value in values.items():
        stream.write(name + '=' + value + '\n')
print('CI uses pinned Word artifact; kernel isolation remains mandatory.')
PY
