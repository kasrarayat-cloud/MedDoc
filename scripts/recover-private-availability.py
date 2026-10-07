#!/usr/bin/env python3
"""Prospectively qualified availability recovery; default reads no installed state."""
from pathlib import Path
import json
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rebuild'))
from ops.private_availability_recovery import main, safe_failure_label

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'complete': False, 'provider_calls': 0, 'authentication_submissions': 0,
                          'failure_kind': type(error).__name__, 'refusal_label': safe_failure_label(error),
                          'automatic_retries': False}))
        raise SystemExit(2) from None
