#!/usr/bin/env bash
# Start the private QA environment on 789c0372 (the presenter's demo environment) (doctor 127.0.0.1:9160, admin 127.0.0.1:9161, one job worker),
# exactly as the 98aebf7b environment was started (int/browser, profile v1 = fixture AI, Sonnet 5.5 configuration, automatic Word selection, field relations on,
# HTTPS off, Word runtime from word-runtime.json). Loopback only. Database quillmd_qa_int_sol_789c0372 on the QA
# PostgreSQL 127.0.0.1:55731 (never the live 55438). Never touches 127.0.0.1:9130/9131.
# Records the gunicorn master PIDs (their own --pid files) and the REAL worker PID (found by owner + cwd + cmdline,
# not the setsid parent's $!) in state/{doctor,admin,worker}.pid. Stop with ./stop.sh.
set -u
D=/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/demo-789c0372
SRC=$D/src/rebuild
PY=/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python
L="python3 -B $D/qa_launch.py"
P=v1
if ss -ltn | grep -qE '127\.0\.0\.1:(9160|9161)\b'; then echo 'REFUSED: 9160 or 9161 is already listening'; exit 1; fi
for name in doctor admin worker; do
  if [ -f "$D/state/$name.pid" ] && [ -d "/proc/$(tr -dc '0-9' < "$D/state/$name.pid")" ]; then
    echo "REFUSED: state/$name.pid names a running process; run ./stop.sh first"; exit 1
  fi
done
umask 077
$L --profile $P --surface doctor -- $PY -B -m gunicorn quillmd.wsgi:application --bind 127.0.0.1:9160 \
   --workers 2 --timeout 120 --daemon --pid $D/state/doctor.pid --error-logfile $D/state/doctor.log --capture-output || exit 1
$L --profile $P --surface admin  -- $PY -B -m gunicorn quillmd.wsgi:application --bind 127.0.0.1:9161 \
   --workers 1 --timeout 120 --daemon --pid $D/state/admin.pid --error-logfile $D/state/admin.log --capture-output || exit 1
setsid $L --profile $P -- $PY -B manage.py worker > $D/state/worker.log 2>&1 < /dev/null &
echo $! > $D/state/worker.setsid-parent.pid
worker=''
for i in $(seq 1 30); do
  sleep 1
  for p in /proc/[0-9]*; do
    pid=${p#/proc/}
    [ "$(stat -c %u "$p" 2>/dev/null)" = "$(id -u)" ] || continue
    [ "$(readlink "$p/cwd" 2>/dev/null)" = "$SRC" ] || continue
    cmd=$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null) || continue
    [[ "$cmd" == "$PY -B manage.py worker "* ]] || continue
    worker="$worker $pid"
  done
  worker=$(echo $worker)
  [ -n "$worker" ] && break
done
case "$worker" in
  ''|*' '*) echo "worker PID not found uniquely: '$worker' (see state/worker.log)"; exit 1 ;;
esac
echo "$worker" > $D/state/worker.pid
for i in $(seq 1 30); do
  curl -fsS --max-time 2 http://127.0.0.1:9160/health/ > /dev/null 2>&1 && curl -fsS --max-time 2 http://127.0.0.1:9161/health/ > /dev/null 2>&1 && break
  sleep 1
done
echo "doctor $(cat $D/state/doctor.pid)  admin $(cat $D/state/admin.pid)  worker $(cat $D/state/worker.pid)"
curl -fsS --max-time 5 http://127.0.0.1:9160/health/; echo
curl -fsS --max-time 5 http://127.0.0.1:9161/health/; echo
ss -ltnp | grep -E '127\.0\.0\.1:(9160|9161)\b'
