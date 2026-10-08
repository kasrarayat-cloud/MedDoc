#!/usr/bin/env python3
"""Default-disabled owner normal443 preparation. No installed-state reads by default."""
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'rebuild'))
from ops.owner_normal_origin import main, Refusal, qualified

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        reason = str(error) if isinstance(error, Refusal) else ''
        reason = reason if re.fullmatch('normal443_[a-z0-9_]+', reason) else 'normal443_dependency_refusal'
        print(json.dumps({'complete':False,'qualification_required':not qualified(),'reason':reason,
                          'failure_kind':type(error).__name__,'automatic_retries':False,
                          'arbitrary_error_text_exported':False},sort_keys=True))
        raise SystemExit(2) from None
