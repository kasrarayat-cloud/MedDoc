#!/usr/bin/env python3
"""Fixed inert CLI; no installed reads precede the source qualification gate."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rebuild'))
from ops.owner_acceptance_v3 import failure_summary, main

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps(failure_summary(error)), flush=True)
        raise SystemExit(2)
