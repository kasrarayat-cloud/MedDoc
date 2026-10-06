#!/usr/bin/env bash
# Stop the private QA environment on 789c0372 (the presenter's demo environment) (doctor 127.0.0.1:9160, admin 127.0.0.1:9161, job worker).
# Kills ONLY by the recorded PIDs (state/{doctor,admin,worker}.pid), and only after confirming each PID is still the
# process that was started: owner uid = ours, cwd = the private src copy (demo/env-789c0372/src/rebuild), and the expected command
# line (gunicorn bind + its own --pid file; 'manage.py worker'). Never pkill -f. Never touches 9130/9131 or port 55438.
# Waits for the signalled PIDs themselves to exit (a freed port is not an exited process), up to 60 s.
# Does NOT drop the database quillmd_qa_int_sol_789c0372; that is a separate decision:
#   python3 -B $D/qa_launch.py -- <venv python> -B $D/create_qa_database.py --drop-confirm quillmd_qa_int_sol_789c0372
#   ./stop.sh --check   verifies the identities and signals nothing.
set -u
CHECK=0; [ "${1:-}" = --check ] && CHECK=1
D=/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/demo-789c0372
SRC=$D/src/rebuild
status=0
signalled=()
for name in doctor admin worker; do
  pidfile=$D/state/$name.pid
  if [ ! -f "$pidfile" ]; then echo "$name: no pid file ($pidfile)"; status=1; continue; fi
  pid=$(tr -dc '0-9' < "$pidfile")
  if [ -z "$pid" ] || [ ! -d "/proc/$pid" ]; then echo "$name: pid '$pid' not running"; continue; fi
  cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || true)
  cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
  owner=$(stat -c '%u' "/proc/$pid")
  case "$name" in
    doctor) want="--bind 127.0.0.1:9160 --workers 2 --timeout 120 --daemon --pid $D/state/doctor.pid" ;;
    admin)  want="--bind 127.0.0.1:9161 --workers 1 --timeout 120 --daemon --pid $D/state/admin.pid" ;;
    worker) want='manage.py worker' ;;
  esac
  if [ "$owner" != "$(id -u)" ] || [ "$cwd" != "$SRC" ] || [[ "$cmd" != *"$want"* ]]; then
    echo "$name: pid $pid is not the recorded QA process (owner=$owner cwd=$cwd); REFUSING to signal it"
    status=1; continue
  fi
  if [ "$CHECK" = 1 ]; then echo "$name: pid $pid verified (owner, cwd, cmdline); --check sends nothing"; continue; fi
  kill -TERM "$pid" && echo "$name: sent TERM to $pid" && signalled+=("$pid")
done
[ "$CHECK" = 1 ] && exit $status
# gunicorn masters stop their workers; the job worker finishes its current job first (core/management/commands/worker.py).
for i in $(seq 1 60); do
  alive=0
  for pid in "${signalled[@]}"; do [ -d "/proc/$pid" ] && alive=1; done
  if [ "$alive" = 0 ] && ! ss -ltn | grep -qE '127\.0\.0\.1:(9160|9161)\b'; then break; fi
  sleep 1
done
for pid in "${signalled[@]}"; do [ -d "/proc/$pid" ] && { echo "pid $pid still alive after 60 s"; status=1; }; done
if ss -ltnp | grep -E '127\.0\.0\.1:(9160|9161)\b'; then echo 'still listening'; status=1; else echo 'stopped: 9160/9161 free'; fi
exit $status
