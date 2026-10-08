#!/usr/bin/env bash
# Reproducible fresh-application gates. No production service or old data access.
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$repo_root"
gate=${1:-all}
quillmd_ci_python=${QUILLMD_CI_PYTHON:-python3}
if [[ "$quillmd_ci_python" == */* && "$quillmd_ci_python" != /* ]]; then
  quillmd_ci_python="$repo_root/$quillmd_ci_python"
fi

if [[ "$gate" == python || "$gate" == all ]]; then
  : "${QUILLMD_SECRET_KEY:?Supply a synthetic CI secret}"
  : "${QUILLMD_DB_PASSWORD:?Supply the isolated CI database password}"
  # Django reports success when zero tests are discovered; require the core suite.
  [[ -f rebuild/core/tests.py || -d rebuild/core/tests ]] || {
    echo 'Fresh application tests are missing.' >&2
    exit 1
  }
  (
    cd rebuild
    "$quillmd_ci_python" manage.py check
    "$quillmd_ci_python" manage.py makemigrations --check --dry-run
    "$quillmd_ci_python" manage.py test core.tests --verbosity 2
    # ⚠️ This list is EXPLICIT, not discovered: a new documents/test_*.py that is not named
    # here never runs in CI and is inert. Add the module in the same change as the test.
    "$quillmd_ci_python" -m unittest documents.tests documents.test_tab_form documents.test_sdk_sandbox documents.test_sdk_service documents.test_layout documents.test_unmapped_areas documents.test_multicolumn_and_mixed documents.test_preparation documents.test_preparation_constraints -v
    "$quillmd_ci_python" -m unittest discover -s ops -p 'test_*.py' -v
  )
fi

if [[ "$gate" == marketing || "$gate" == all ]]; then
  npm run build -w marketing
  npm audit --omit=dev --audit-level=high
fi

if [[ "$gate" != python && "$gate" != marketing && "$gate" != all ]]; then
  echo 'Usage: bash scripts/ci/verify-fresh.sh [python|marketing|all]' >&2
  exit 2
fi
