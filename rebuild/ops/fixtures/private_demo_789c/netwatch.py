"""Record every TCP/UDP socket held by a process tree while it runs (read-only observer; signals nothing).

    python3 -B netwatch.py <root pid> <out.json>
Samples `ss -tunapH` every 0.2 s until <root pid> exits, keeps the sockets whose users:(...) name a pid in the tree
(descendants re-read on each sample), and writes the distinct (proto, local, peer) tuples plus any peer that is NOT
127.0.0.1:9160/9161 loopback, any non-loopback peer, and any DNS (port 53) peer.
"""
import json
import os
import re
import subprocess
import sys
import time

root, out = int(sys.argv[1]), sys.argv[2]


def tree():
    kids = {}
    for name in os.listdir('/proc'):
        if name.isdigit():
            try:
                fields = open(f'/proc/{name}/stat').read().rsplit(')', 1)[1].split()
                kids.setdefault(int(fields[1]), []).append(int(name))
            except OSError:
                pass
    seen, todo = set(), [root]
    while todo:
        pid = todo.pop()
        if pid not in seen:
            seen.add(pid)
            todo.extend(kids.get(pid, []))
    return seen


seen, samples, started = {}, 0, time.time()
while os.path.exists(f'/proc/{root}'):
    pids = tree()
    lines = subprocess.run(['ss', '-tunapH'], capture_output=True, text=True).stdout.splitlines()
    for line in lines:
        owners = {int(p) for p in re.findall(r'pid=(\d+)', line)}
        if owners & pids:
            parts = line.split()
            proto, state, local, peer = parts[0], parts[1], parts[4], parts[5]
            seen.setdefault((proto, local, peer), state)
    samples += 1
    time.sleep(0.2)
peers = sorted({p for (_, _, p) in seen})
loop_ok = re.compile(r'^(127\.0\.0\.1|\[::1\]|\[::ffff:127\.0\.0\.1\]):(9160|9161)$')
def host(p):
    return p.rsplit(':', 1)[0]
result = {
    'root_pid': root, 'samples': samples, 'seconds': round(time.time() - started, 1),
    'sockets': [{'proto': k[0], 'local': k[1], 'peer': k[2], 'state': v} for k, v in sorted(seen.items())],
    'peers_other_than_qa_ports': [p for p in peers if not loop_ok.match(p) and p not in ('*:*', '0.0.0.0:*', '[::]:*')],
    'non_loopback_peers': [p for p in peers if host(p) not in ('127.0.0.1', '[::1]', '[::ffff:127.0.0.1]', '*', '0.0.0.0', '[::]')],
    'dns_peers': [p for p in peers if p.endswith(':53')],
}
with open(out, 'w') as stream:
    json.dump(result, stream, indent=1)
