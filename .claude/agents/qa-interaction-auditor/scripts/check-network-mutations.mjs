#!/usr/bin/env node
// ============================================================================
// check-network-mutations.mjs
// ----------------------------------------------------------------------------
// Reads recent Caddy access-log lines from `docker logs` and emits a
// structured JSON list of HTTP mutations (POST/PATCH/PUT/DELETE) that
// hit the QuillMD app within the requested time window.
//
// The QA Interaction Auditor uses this BEFORE and AFTER a click to
// answer one question:
//
//     "Did this click actually fire a mutation? If yes, where + what
//      status?"
//
// A click that fires NO mutation is the canonical orphan-dispatcher
// signal (Pattern A from skills/bug-patterns.md). A click that fires
// a 2xx mutation but doesn't change the DB is a pretend-success
// fallback (Pattern B).
//
// Usage:
//   node check-network-mutations.mjs [--since 30s] [--container meddoc-pro-caddy-1]
//
// Output: JSON array on stdout, one mutation per element. Errors to
// stderr; exits 0 even with no mutations found (empty array is the
// healthy "click fired no mutation" signal).
// ============================================================================

import { execSync } from 'node:child_process';
import { argv, exit, stderr, stdout } from 'node:process';

function parseArgs(args) {
  const opts = {
    since: '30s',
    container: process.env.CADDY_CONTAINER ?? 'meddoc-pro-caddy-1',
    pretty: false,
  };
  for (let i = 2; i < args.length; i += 1) {
    const a = args[i];
    if (a === '--since') {
      opts.since = args[i + 1];
      i += 1;
    } else if (a === '--container') {
      opts.container = args[i + 1];
      i += 1;
    } else if (a === '--pretty') {
      opts.pretty = true;
    } else if (a === '--help' || a === '-h') {
      stderr.write(
        'check-network-mutations.mjs [--since <duration>] [--container <name>] [--pretty]\n'
      );
      exit(2);
    } else {
      stderr.write(`Unknown arg: ${a}\n`);
      exit(2);
    }
  }
  return opts;
}

export function recentMutations({ since = '30s', container = 'meddoc-pro-caddy-1' } = {}) {
  let raw;
  try {
    raw = execSync(`docker logs ${container} --since "${since}" 2>&1`, {
      encoding: 'utf-8',
      maxBuffer: 32 * 1024 * 1024,
    });
  } catch (err) {
    stderr.write(`docker logs failed: ${err.message}\n`);
    return [];
  }

  const mutations = [];
  for (const line of raw.split('\n')) {
    if (!line.includes('"method":')) continue;
    // Caddy default JSON log is: <ts> <level> <msg> {json}
    // We want just the JSON object.
    const braceIdx = line.indexOf('{');
    if (braceIdx === -1) continue;

    let parsed;
    try {
      parsed = JSON.parse(line.slice(braceIdx));
    } catch {
      // Non-JSON log line; skip (Caddy debug lines, container stdout banners, etc.).
      continue;
    }

    const method = parsed?.request?.method;
    if (!['POST', 'PATCH', 'PUT', 'DELETE'].includes(method)) continue;

    const host = parsed?.request?.host ?? null;
    const uri = parsed?.request?.uri ?? null;
    const status = parsed?.status ?? null;
    const duration = typeof parsed?.duration === 'number' ? parsed.duration : null;

    // Skip _next/static asset POSTs, webhook receivers, anything we
    // know isn't an app-action mutation. This prevents false positives
    // when the page is mid-loading.
    if (uri && (uri.startsWith('/_next/') || uri.startsWith('/static/'))) continue;

    mutations.push({
      ts: parsed?.ts ?? null,
      method,
      host,
      uri,
      status,
      durationMs: duration === null ? null : Math.round(duration * 1000),
      // Preserve user-agent so the agent can confirm the mutation
      // came from the browser walk and not from another tab / cron job.
      userAgent: parsed?.request?.headers?.['User-Agent']?.[0] ?? null,
    });
  }

  return mutations.sort((a, b) => {
    if (a.ts === null) return 1;
    if (b.ts === null) return -1;
    return a.ts - b.ts;
  });
}

// CLI entry — only runs when invoked directly.
if (import.meta.url === `file://${argv[1]}` || argv[1]?.endsWith('check-network-mutations.mjs')) {
  const opts = parseArgs(argv);
  const out = recentMutations(opts);
  stdout.write(opts.pretty ? `${JSON.stringify(out, null, 2)}\n` : `${JSON.stringify(out)}\n`);
  exit(0);
}
