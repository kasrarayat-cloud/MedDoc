// ============================================================================
// Scribe WebSocket load test (M7 D5)
// ----------------------------------------------------------------------------
// Spins up N (default 10) concurrent WS clients against the scribe-ws
// sidecar, drives each for ~30s with silent opus frames, collects
// per-stream metrics, and writes a structured JSON report + a markdown
// summary. Goal: baseline numbers for the live path before real
// patient traffic.
//
// Requirements:
//   - scribe-ws running (default loopback :3003 in dev)
//   - SCRIBE_LOAD_TEST_COOKIE env — a valid session cookie string
//     (copy from a logged-in browser's devtools → Application → Cookies)
//   - SCRIBE_LOAD_TEST_VISIT_IDS env — comma-separated list of LIVE
//     ScribeVisit ids the session is authorised to open, >= streams
//
// Usage:
//   export SCRIBE_LOAD_TEST_COOKIE='authjs.session-token=...'
//   export SCRIBE_LOAD_TEST_VISIT_IDS='cviz1,cviz2,…'
//   npx tsx apps/scribe/scripts/load-test-ws.ts --streams 10 --duration 30
//
// Output:
//   /tmp/load-test-results-<ISO>.json     — per-stream metrics
//   stdout                                — compact markdown summary
// ============================================================================

import 'dotenv/config';
import fs from 'node:fs';
import path from 'node:path';
import WebSocket from 'ws';

interface Args {
  streams: number;
  durationSec: number;
  host: string;
  port: number;
  cookie: string;
  visitIds: string[];
}

interface StreamResult {
  streamIndex: number;
  visitId: string;
  acceptLatencyMs: number | null;
  framesSent: number;
  framesReceived: number;
  interimCount: number;
  finalCount: number;
  disconnects: number;
  errors: string[];
  ended: 'completed' | 'errored' | 'timeout';
  elapsedMs: number;
}

function parseArgs(): Args {
  const argv = process.argv.slice(2);
  const flag = (name: string, fallback: string): string => {
    const i = argv.indexOf(`--${name}`);
    return i >= 0 && i + 1 < argv.length ? argv[i + 1] : fallback;
  };
  const streams = Number(flag('streams', '10'));
  const durationSec = Number(flag('duration', '30'));
  const host = flag('host', '127.0.0.1');
  const port = Number(flag('port', '3003'));

  const cookie = process.env.SCRIBE_LOAD_TEST_COOKIE?.trim();
  if (!cookie) {
    throw new Error(
      'SCRIBE_LOAD_TEST_COOKIE is required. Copy your session cookie from devtools and export it.'
    );
  }
  const visitIds = (process.env.SCRIBE_LOAD_TEST_VISIT_IDS ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  if (visitIds.length < streams) {
    throw new Error(
      `SCRIBE_LOAD_TEST_VISIT_IDS must list at least ${streams} LIVE-mode visit ids you own.`
    );
  }
  return { streams, durationSec, host, port, cookie, visitIds };
}

// Synthetic 250ms "audio" frame — just silent bytes sized like a real
// opus payload. Deepgram rejects non-audio but scribe-ws forwards blindly;
// this test is about WS lifecycle + back-pressure, not transcription
// quality.
function syntheticFrame(): Buffer {
  const bytes = Buffer.alloc(2048);
  return bytes;
}

async function runOneStream(args: {
  streamIndex: number;
  url: string;
  cookie: string;
  durationSec: number;
}): Promise<StreamResult> {
  const result: StreamResult = {
    streamIndex: args.streamIndex,
    visitId: args.url.split('/').pop() ?? '',
    acceptLatencyMs: null,
    framesSent: 0,
    framesReceived: 0,
    interimCount: 0,
    finalCount: 0,
    disconnects: 0,
    errors: [],
    ended: 'errored',
    elapsedMs: 0,
  };

  return new Promise((resolve) => {
    const openStarted = Date.now();
    const streamStart = Date.now();
    const ws = new WebSocket(args.url, {
      headers: { Cookie: args.cookie },
    });

    const deadline = setTimeout(() => {
      result.ended = result.ended === 'errored' ? 'timeout' : result.ended;
      try { ws.close(); } catch { /* ignored */ }
    }, (args.durationSec + 5) * 1000);

    let frameTimer: NodeJS.Timeout | undefined;

    ws.on('open', () => {
      result.acceptLatencyMs = Date.now() - openStarted;
      // Send a frame every 250ms for the duration window.
      const endAt = Date.now() + args.durationSec * 1000;
      frameTimer = setInterval(() => {
        if (Date.now() >= endAt) {
          if (frameTimer) clearInterval(frameTimer);
          try {
            ws.send(JSON.stringify({ type: 'end' }));
          } catch (err) {
            result.errors.push(
              `end send: ${err instanceof Error ? err.message : String(err)}`
            );
          }
          return;
        }
        try {
          ws.send(syntheticFrame(), { binary: true });
          result.framesSent += 1;
        } catch (err) {
          result.errors.push(
            `frame send: ${err instanceof Error ? err.message : String(err)}`
          );
        }
      }, 250);
    });

    ws.on('message', (data) => {
      result.framesReceived += 1;
      try {
        const msg = JSON.parse(String(data)) as { type?: string };
        if (msg.type === 'interim') result.interimCount += 1;
        if (msg.type === 'final') result.finalCount += 1;
      } catch {
        // non-JSON frames (binary) counted above via framesReceived
      }
    });

    ws.on('error', (err) => {
      result.errors.push(err.message);
    });

    ws.on('close', () => {
      result.disconnects += 1;
      result.ended = result.errors.length > 0 ? 'errored' : 'completed';
      result.elapsedMs = Date.now() - streamStart;
      if (frameTimer) clearInterval(frameTimer);
      clearTimeout(deadline);
      resolve(result);
    });
  });
}

async function main(): Promise<void> {
  const args = parseArgs();
  console.log(
    `[load-test] ${args.streams} streams × ${args.durationSec}s → ws://${args.host}:${args.port}`
  );
  const tasks: Array<Promise<StreamResult>> = [];
  for (let i = 0; i < args.streams; i++) {
    const visitId = args.visitIds[i];
    const url = `ws://${args.host}:${args.port}/api/ws/visit/${visitId}`;
    tasks.push(
      runOneStream({
        streamIndex: i,
        url,
        cookie: args.cookie,
        durationSec: args.durationSec,
      })
    );
  }
  const results = await Promise.all(tasks);

  const summary = {
    ranAt: new Date().toISOString(),
    streams: args.streams,
    durationSec: args.durationSec,
    totals: {
      accepted: results.filter((r) => r.acceptLatencyMs !== null).length,
      completed: results.filter((r) => r.ended === 'completed').length,
      errored: results.filter((r) => r.ended === 'errored').length,
      timeout: results.filter((r) => r.ended === 'timeout').length,
      framesSent: results.reduce((s, r) => s + r.framesSent, 0),
      framesReceived: results.reduce((s, r) => s + r.framesReceived, 0),
      interimCount: results.reduce((s, r) => s + r.interimCount, 0),
      finalCount: results.reduce((s, r) => s + r.finalCount, 0),
    },
    acceptLatencyMs: {
      p50: pct(
        results.map((r) => r.acceptLatencyMs).filter((n): n is number => typeof n === 'number'),
        50
      ),
      p95: pct(
        results.map((r) => r.acceptLatencyMs).filter((n): n is number => typeof n === 'number'),
        95
      ),
    },
    perStream: results,
  };

  const outPath = path.join(
    '/tmp',
    `load-test-results-${summary.ranAt.replace(/[:.]/g, '-')}.json`
  );
  fs.writeFileSync(outPath, JSON.stringify(summary, null, 2));

  console.log('');
  console.log(`## Load test summary — ${summary.ranAt}`);
  console.log('');
  console.log(`| Metric | Value |`);
  console.log(`|---|---|`);
  console.log(`| Streams | ${summary.streams} |`);
  console.log(`| Accepted | ${summary.totals.accepted}/${summary.streams} |`);
  console.log(`| Completed cleanly | ${summary.totals.completed} |`);
  console.log(`| Errored | ${summary.totals.errored} |`);
  console.log(`| Timed out | ${summary.totals.timeout} |`);
  console.log(`| Total frames sent | ${summary.totals.framesSent} |`);
  console.log(`| Total frames received | ${summary.totals.framesReceived} |`);
  console.log(`| Interim messages | ${summary.totals.interimCount} |`);
  console.log(`| Final messages | ${summary.totals.finalCount} |`);
  console.log(`| Accept p50 (ms) | ${summary.acceptLatencyMs.p50 ?? 'n/a'} |`);
  console.log(`| Accept p95 (ms) | ${summary.acceptLatencyMs.p95 ?? 'n/a'} |`);
  console.log('');
  console.log(`Full per-stream report: ${outPath}`);
}

function pct(values: number[], p: number): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.floor((sorted.length * p) / 100));
  return sorted[idx];
}

main().catch((err) => {
  console.error('[load-test] fatal:', err instanceof Error ? err.message : err);
  process.exit(1);
});
