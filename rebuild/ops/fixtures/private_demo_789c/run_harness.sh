#!/usr/bin/env bash
# run_harness.sh <label> <node|python args...> : run one harness step from the private src copy with a FRESH environment
# (env -i), base URL pinned to the QA doctor 127.0.0.1:9160, Chromium proxy env pointed at a dead loopback port (127.0.0.1:9,
# nothing listens) with loopback bypassed, and netwatch.py recording every socket of the process tree. Log -> evidence/<label>.log
set -u
D=/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/demo-789c0372
SRC=/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/demo-789c0372/src/rebuild
MODS=/opt/meddoc-pro/.worktrees/private-os-isolation/rebuild/.runtime/browser-deps/node_modules
label=$1; shift
ss -ltn | grep -qE '127\.0\.0\.1:9\b' && { echo 'guard port 127.0.0.1:9 is listening; refusing'; exit 90; }
cd "$SRC" || exit 91
{ echo "start $(date -u +%FT%TZ)"; echo "cmd: $*"; } > "$D/evidence/$label.log"
env -i PATH=/usr/bin:/bin HOME="$D/home" TMPDIR="${HARNESS_TMPDIR:-$D/t}" LANG=C.UTF-8 TZ=UTC \
    PLAYWRIGHT_BROWSERS_PATH=/home/claude/.cache/ms-playwright PLAYWRIGHT_MODULE_DIR="$MODS" \
    QUILLMD_BROWSER_BASE_URL=http://127.0.0.1:9160 ${EXTRA_ENV:-} \
    http_proxy=http://127.0.0.1:9 https_proxy=http://127.0.0.1:9 all_proxy=http://127.0.0.1:9 \
    HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 ALL_PROXY=http://127.0.0.1:9 \
    no_proxy=127.0.0.1,localhost,::1 NO_PROXY=127.0.0.1,localhost,::1 \
    "$@" >> "$D/evidence/$label.log" 2>&1 &
child=$!
python3 -B "$D/netwatch.py" "$child" "$D/evidence/$label.netwatch.json" &
watcher=$!
wait "$child"; rc=$?
wait "$watcher"
echo "exit=$rc end $(date -u +%FT%TZ)" >> "$D/evidence/$label.log"
cat "$D/evidence/$label.log"
python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print('netwatch samples',d['samples'],'non-loopback',d['non_loopback_peers'],'other-than-qa',d['peers_other_than_qa_ports'],'dns',d['dns_peers'])" "$D/evidence/$label.netwatch.json"
exit $rc
