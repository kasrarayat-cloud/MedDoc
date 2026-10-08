#!/usr/bin/env python3
"""Inert-by-default entry for the separately reviewed native Word milestone."""
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'rebuild'))
from ops.word_milestone_delivery import main,Refusal

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        label=str(error) if isinstance(error,Refusal) else 'word_delivery_dependency_refusal'
        label=label if re.fullmatch('word_delivery_[a-z0-9_]+',label) else 'word_delivery_dependency_refusal'
        print(json.dumps({'complete':False,'reason':label,'failure_kind':type(error).__name__,
            'provider_calls':0,'automatic_retries':False,'arbitrary_error_text_exported':False},sort_keys=True))
        raise SystemExit(2) from None
