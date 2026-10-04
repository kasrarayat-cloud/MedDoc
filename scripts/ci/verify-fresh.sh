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

case "$gate" in
  python|python-core|python-core-1|python-core-2|python-support|marketing|all) ;;
  *) echo 'Usage: bash scripts/ci/verify-fresh.sh [python|python-core|python-core-1|python-core-2|python-support|marketing|all]' >&2; exit 2 ;;
esac

if [[ "$gate" == python || "$gate" == python-core || "$gate" == python-core-1 || "$gate" == python-core-2 || "$gate" == python-support || "$gate" == all ]]; then
  : "${QUILLMD_SECRET_KEY:?Supply a synthetic CI secret}"
  : "${QUILLMD_DB_PASSWORD:?Supply the isolated CI database password}"
  # Django reports success when zero tests are discovered; require the core suite.
  [[ -f rebuild/core/tests.py || -d rebuild/core/tests ]] || {
    echo 'Fresh application tests are missing.' >&2
    exit 1
  }
  (
    cd rebuild
    if [[ "$gate" != python-support ]]; then
      "$quillmd_ci_python" manage.py check
      "$quillmd_ci_python" manage.py makemigrations --check --dry-run
      if [[ "$gate" == python-core-1 || "$gate" == python-core-2 ]]; then
        core_shard=${gate##*-}
        "$quillmd_ci_python" manage.py test core.tests --verbosity 2 \
          --testrunner ops.ci_test_runner.CoreShardRunner --core-shard "$core_shard" \
          --core-shard-manifest ".runtime/core-shard-${core_shard}.json"
      else
        "$quillmd_ci_python" manage.py test core.tests --verbosity 2
      fi
    fi
    if [[ "$gate" != python-core && "$gate" != python-core-1 && "$gate" != python-core-2 ]]; then
    # manage.py configures only its own child process. Standalone document
    # controls also use Django settings, including the auto-import switch.
    export DJANGO_SETTINGS_MODULE=quillmd.settings
    # ⚠️ This list is EXPLICIT, not discovered: a new documents/test_*.py that is not named
    # here never runs in CI and is inert. Add the module in the same change as the test.
    "$quillmd_ci_python" -m unittest documents.tests documents.test_tab_form documents.test_sdk_sandbox documents.test_sdk_service documents.test_layout documents.test_unmapped_areas documents.test_multicolumn_and_mixed documents.test_word_v3 documents.test_signing_areas documents.test_question_boxes documents.test_composite_kind documents.test_hyperlink_destinations documents.test_document_relations documents.test_paragraph_list_boxes documents.test_source_policy documents.test_layout_verification documents.test_layout_containment documents.test_guidance_preservation documents.test_checkbox_history documents.test_structural_columns documents.test_destination_roles documents.test_import_selection documents.test_source_coverage documents.test_destination_regressions documents.test_paragraph_option_recovery documents.test_ruled_paragraph_recovery documents.test_numeric_part_recovery documents.test_temporal_format_pairs documents.test_paired_colon_gaps documents.test_layout_source_nodes documents.test_named_single_scope documents.test_layout_stream_reuse -v
    "$quillmd_ci_python" -m unittest discover -s ops -p 'test_*.py' -v
    fi
  )
fi

if [[ "$gate" == marketing || "$gate" == all ]]; then
  npm run build -w marketing
  npm audit --omit=dev --audit-level=high
fi
