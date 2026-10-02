"""The outside-host heartbeat pings only when both surfaces are live AND the doctor surface is ready.

The production script is run as it stands, with a fake `curl` first on PATH that answers each loopback URL with a chosen
status and records the ping instead of making it. No network, no credential: the check URL is a synthetic hc-ping.com
address in a temporary credentials directory.
"""
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'deploy/production/quillmd-production-heartbeat.sh'
FAKE_CURL = '''#!/usr/bin/env bash
# Records every call; answers loopback health URLs from $FAKE_CODES ("path=code ..."); records the ping.
echo "$*" >> "$FAKE_LOG"
url="${@: -1}"
case "$url" in
  http://127.0.0.1:*) path="/${url#http://127.0.0.1:*/}"; port="${url#http://127.0.0.1:}"; port="${port%%/*}"
    for pair in $FAKE_CODES; do
      if [ "${pair%%=*}" = "${port}${path}" ]; then printf '%s' "${pair#*=}"; exit 0; fi
    done
    printf '000'; exit 7 ;;
  https://hc-ping.com/*) echo PING >> "$FAKE_LOG"; exit 0 ;;
esac
exit 2
'''


class HeartbeatReadinessGate(unittest.TestCase):
    def run_script(self, codes):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bin').mkdir(); curl = root / 'bin' / 'curl'
            curl.write_text(FAKE_CURL); curl.chmod(curl.stat().st_mode | stat.S_IXUSR)
            (root / 'credentials').mkdir(); (root / 'credentials' / 'heartbeat-url').write_text('https://hc-ping.com/synthetic-check\n')
            log = root / 'calls.log'; log.write_text('')
            env = {'PATH': f'{root / "bin"}:/usr/bin:/bin', 'CREDENTIALS_DIRECTORY': str(root / 'credentials'),
                   'FAKE_LOG': str(log), 'FAKE_CODES': ' '.join(f'{k}={v}' for k, v in codes.items())}
            result = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60)
            return result, log.read_text()

    def test_a_ready_deployment_is_pinged(self):
        result, calls = self.run_script({'9140/health/': 200, '9141/health/': 200, '9140/health/ready/': 200})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PING', calls.splitlines())
        self.assertIn('/health/ready/', calls)
        self.assertIn('Host: app.quillmd.com', calls)

    def test_a_live_but_not_ready_deployment_sends_no_ping(self):
        for code in (503, 404, '000'):
            with self.subTest(ready=code):
                result, calls = self.run_script({'9140/health/': 200, '9141/health/': 200, '9140/health/ready/': code})
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('PING', calls.splitlines())
                self.assertIn(f'/health/ready/ answered {code}; not ready; no ping sent', result.stderr)

    def test_a_dead_surface_still_sends_no_ping(self):
        result, calls = self.run_script({'9140/health/': 200, '9141/health/': 502, '9140/health/ready/': 200})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('PING', calls.splitlines())
        self.assertNotIn('/health/ready/', calls)  # liveness first: readiness is not asked of a dead host


if __name__ == '__main__':
    unittest.main()
