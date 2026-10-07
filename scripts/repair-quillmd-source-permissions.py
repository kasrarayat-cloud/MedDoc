#!/usr/bin/env python3
"""Default-noop, separately reviewed QuillMD public source mode repair."""
from pathlib import Path
import json
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rebuild'))
from ops.repair_source_permissions import main, safe_failure_label

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'complete': False, 'refusal_label': safe_failure_label(error),
                          'service_actions': 0, 'provider_calls': 0, 'automatic_retries': False}))
        raise SystemExit(2) from None
