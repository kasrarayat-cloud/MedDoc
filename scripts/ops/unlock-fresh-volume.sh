#!/usr/bin/env bash
# ============================================================================
# Unlock the QuillMD fresh encrypted volume with the recovery passphrase.
#
# Needed only when the slot-0 key file is not on the host (the owner keeps it
# off the disk for protection against disk-level access), or after key loss.
# Run interactively by an operator in the docker group:
#
#   bash scripts/ops/unlock-fresh-volume.sh
#
# The passphrase is read from the terminal without echo, passed on stdin to the
# host's cryptsetup through systemd-run (never on a command line, never in a
# file), then the database and the three private services are started.
# ============================================================================
set -euo pipefail
[ -t 0 ] || { echo "unlock-fresh-volume: run interactively; the passphrase must be typed, not piped" >&2; exit 2; }
image=$(docker image inspect python:3-slim --format '{{.Id}}' 2>/dev/null) || { echo "unlock-fresh-volume: local helper image python:3-slim missing" >&2; exit 1; }
IFS= read -rs -p "QuillMD recovery passphrase: " phrase
echo
[ -n "$phrase" ] || { echo "unlock-fresh-volume: empty passphrase" >&2; exit 2; }
printf '%s\n' "$phrase" | docker run --rm -i --pull=never --network=none --pid=host \
  --security-opt apparmor=unconfined --mount type=bind,src=/,dst=/host,readonly "$image" python -B -c '
import os,subprocess,sys
line=sys.stdin.readline()
os.chroot("/host");os.chdir("/")
def host(*cmd,stdin=None):
    return subprocess.run(["systemd-run","--wait","--pipe","--collect","--quiet","--property=Type=oneshot",*cmd],input=stdin,capture_output=True,text=True,timeout=300)
r=host("/usr/local/bin/quillmd-fresh-volume","unlock",stdin=line)
del line
if r.returncode!=0:
    print("unlock-fresh-volume: unlock refused: "+r.stderr.strip()[-300:],file=sys.stderr);sys.exit(1)
for unit in ("quillmd-fresh-volume.service","quillmd-fresh-database.service","quillmd-fresh-doctor.service","quillmd-fresh-admin.service","quillmd-fresh-worker.service"):
    s=subprocess.run(["systemctl","start",unit],capture_output=True,text=True)
    if s.returncode!=0:
        print("unlock-fresh-volume: could not start "+unit,file=sys.stderr);sys.exit(1)
print("unlock-fresh-volume: volume open; database and private services started")
'
unset phrase
