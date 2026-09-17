#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .runtime
chmod 700 .runtime
.venv/bin/python manage.py check
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/gunicorn quillmd.wsgi:application --bind 127.0.0.1:9130 --workers 2 --timeout 120 --daemon --pid .runtime/doctor.pid --error-logfile .runtime/doctor.log --capture-output
QUILLMD_ADMIN_SITE=1 .venv/bin/gunicorn quillmd.wsgi:application --bind 127.0.0.1:9131 --workers 1 --timeout 120 --daemon --pid .runtime/admin.pid --error-logfile .runtime/admin.log --capture-output
.venv/bin/python - <<'PY'
import os,subprocess
from pathlib import Path
pid=Path('.runtime/worker.pid')
if pid.exists():
 try: os.kill(int(pid.read_text()),0); raise SystemExit('Worker already running.')
 except ProcessLookupError: pass
with open('.runtime/worker.log','ab',buffering=0) as log:
 process=subprocess.Popen(['.venv/bin/python','manage.py','worker'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 pid.write_text(str(process.pid))
print('Private worker started.')
PY
