#!/usr/bin/env python3
"""Qualified operator entry point; imports no installed application settings."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'rebuild'))
from ops.legacy_model_activation import main

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Legacy model configuration refused or stopped; inspect protected evidence. No automatic retry.') from None
