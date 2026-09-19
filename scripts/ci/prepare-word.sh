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
# Application integration tests must use the ordinary ownership boundary. A
# root-owned child inside the runner-owned checkout is replaceable through its
# ancestors, so install the pinned artifact outside that checkout as well.
quillmd_word_install=$(sudo mktemp -d /usr/local/lib/quillmd-word-ci.XXXXXXXX)
sudo cp -R --no-preserve=ownership "$quillmd_repo/rebuild/.runtime/word-ci/runtime" "$quillmd_word_install/runtime"
sudo cp --no-preserve=ownership "$quillmd_repo/rebuild/.runtime/word-ci/runtime-manifest.json" "$quillmd_word_install/runtime-manifest.json"
sudo chown -R root:root "$quillmd_word_install"
sudo chmod -R a+rX,go-w "$quillmd_word_install"
sudo chmod 755 "$quillmd_word_install"
export QUILLMD_CI_WORD_INSTALL="$quillmd_word_install"
"$quillmd_python" - <<'PY'
import hashlib, os, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'rebuild'))
from documents.sdk_sandbox import verified_runtime
root = Path(os.environ['QUILLMD_CI_WORD_INSTALL'])
values = {'QUILLMD_WORD_RUNTIME': str(root/'runtime'),
          'QUILLMD_WORD_MANIFEST': str(root/'runtime-manifest.json'),
          'QUILLMD_WORD_MANIFEST_SHA256': hashlib.sha256((root/'runtime-manifest.json').read_bytes()).hexdigest(),
          'QUILLMD_WORD_QUALIFICATION': '0', 'QUILLMD_REQUIRE_WORD_TESTS': '1'}
verified_runtime(root/'runtime', root/'runtime-manifest.json',
                 values['QUILLMD_WORD_MANIFEST_SHA256'], qualification=False)
with Path(os.environ['GITHUB_ENV']).open('a') as stream:
    for name, value in values.items():
        stream.write(name + '=' + value + '\n')
print('CI uses an immutable pinned Word artifact; ordinary ownership and kernel isolation are mandatory.')
PY
