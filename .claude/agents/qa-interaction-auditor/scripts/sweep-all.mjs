#!/usr/bin/env node
// ============================================================================
// sweep-all.mjs — full-site QA orchestrator
// ----------------------------------------------------------------------------
// Runs every per-page walker SEQUENTIALLY (memory #17 — VPS is shared,
// no parallelism on browser launches), aggregates the NDJSON output
// from each child, and writes a unified report to docs/qa-reports/
// <UTC-timestamp>.md per skills/reporting-format.md.
//
// Trigger: "Run the full site QA sweep" (Lead spawns this). The flagship
// sweep-visit-page.mjs is run last because it does a full element walk
// that can take 2-3 minutes; everything else is page-load smoke + per-
// page assertions, ~5-15 seconds each.
//
// Pre-flight: aborts when available RAM <4Gi (memory #17 threshold).
// ============================================================================

import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCRIPT_DIR = __dirname;
const REPO_ROOT = resolve(__dirname, '..', '..', '..', '..');

// ──────────────────────────────────────────────────────────────────────
// Walker registry — keep in sync with skills/site-map.md
// ──────────────────────────────────────────────────────────────────────
const WALKERS = [
  // Public app pages first (no login overhead).
  { name: 'login', file: 'sweep-login.mjs', auth: false },
  { name: 'signup', file: 'sweep-signup.mjs', auth: false },
  { name: 'forgot-password', file: 'sweep-forgot-password.mjs', auth: false },
  { name: 'reset-password', file: 'sweep-reset-password.mjs', auth: false },
  { name: 'check-email', file: 'sweep-check-email.mjs', auth: false },
  // Marketing site (no login).
  { name: 'marketing-home', file: 'sweep-marketing-home.mjs', auth: false },
  { name: 'marketing-about', file: 'sweep-marketing-about.mjs', auth: false },
  { name: 'marketing-pricing', file: 'sweep-marketing-pricing.mjs', auth: false },
  { name: 'marketing-demo', file: 'sweep-marketing-demo.mjs', auth: false },
  { name: 'marketing-signup', file: 'sweep-marketing-signup.mjs', auth: false },
  { name: 'marketing-security', file: 'sweep-marketing-security.mjs', auth: false },
  { name: 'marketing-hipaa', file: 'sweep-marketing-hipaa.mjs', auth: false },
  { name: 'marketing-privacy', file: 'sweep-marketing-privacy.mjs', auth: false },
  { name: 'marketing-contact', file: 'sweep-marketing-contact.mjs', auth: false },
  { name: 'marketing-terms', file: 'sweep-marketing-terms.mjs', auth: false },
  // Authenticated pages — login required, hits the seeded QA user.
  { name: 'dashboard', file: 'sweep-dashboard.mjs', auth: true },
  { name: 'visits-list', file: 'sweep-visits-list.mjs', auth: true },
  { name: 'new-visit', file: 'sweep-new-visit.mjs', auth: true },
  { name: 'patients-list', file: 'sweep-patients-list.mjs', auth: true },
  { name: 'patient-detail', file: 'sweep-patient-detail.mjs', auth: true },
  { name: 'settings', file: 'sweep-settings.mjs', auth: true },
  { name: 'visit-record', file: 'sweep-visit-record.mjs', auth: true },
  { name: 'dev-rx-warnings', file: 'sweep-dev-rx-warnings.mjs', auth: true },
  // SUPER_ADMIN-gated routes (DOCTOR will hit 404 — that's the test).
  { name: 'admin-dashboard', file: 'sweep-admin-dashboard.mjs', auth: true },
  { name: 'admin-users', file: 'sweep-admin-users.mjs', auth: true },
  { name: 'admin-usage', file: 'sweep-admin-usage.mjs', auth: true },
  { name: 'admin-hipaa', file: 'sweep-admin-hipaa.mjs', auth: true },
  { name: 'admin-threats', file: 'sweep-admin-threats.mjs', auth: true },
  // Flagship walker last — longest run + most expensive (SQL fixture +
  // full element walk). When this fails the rest of the report is
  // already in-hand.
  { name: 'visit-page', file: 'sweep-visit-page.mjs', auth: true, deep: true },
];

// ──────────────────────────────────────────────────────────────────────
// Pre-flight (memory #17)
// ──────────────────────────────────────────────────────────────────────
function preflight() {
  try {
    const free = execSync(`free -m`, { encoding: 'utf-8' });
    const m = free.match(/Mem:\s+(\d+)\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)/);
    if (!m) {
      console.error('Could not parse free -m output; refusing to proceed.');
      process.exit(2);
    }
    const totalMb = parseInt(m[1], 10);
    const availableMb = parseInt(m[2], 10);
    return { totalMb, availableMb };
  } catch (err) {
    console.error('Preflight: free -m failed:', err.message);
    process.exit(2);
  }
}

// ──────────────────────────────────────────────────────────────────────
// Walker invocation
// ──────────────────────────────────────────────────────────────────────
function runWalker(walker) {
  return new Promise((resolveFn) => {
    const file = resolve(SCRIPT_DIR, walker.file);
    const env = { ...process.env };
    if (walker.deep && !env.QA_FIXTURE_VISIT_ID) {
      // sweep-visit-page.mjs needs a fixture visit id; the operator
      // can pre-set this. Without it, skip the deep walker rather
      // than crash.
      return resolveFn({
        name: walker.name,
        skipped: true,
        reason: 'QA_FIXTURE_VISIT_ID not set — sweep-visit-page.mjs needs a fixture visit',
      });
    }
    const child = spawn('node', [file], {
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => (stdout += d.toString()));
    child.stderr.on('data', (d) => (stderr += d.toString()));
    child.on('close', (code) => {
      const events = stdout
        .split('\n')
        .filter(Boolean)
        .map((l) => {
          try { return JSON.parse(l); } catch { return null; }
        })
        .filter(Boolean);
      resolveFn({
        name: walker.name,
        exitCode: code,
        events,
        stderrTail: stderr.slice(-1000),
      });
    });
  });
}

// ──────────────────────────────────────────────────────────────────────
// Report writer
// ──────────────────────────────────────────────────────────────────────
function utcTimestamp() {
  return new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
}

function reportPath() {
  const ts = utcTimestamp();
  return resolve(REPO_ROOT, 'docs', 'qa-reports', `${ts}.md`);
}

function buildReport({ runs, preflightInfo, startedAt, finishedAt }) {
  const totalWalkers = runs.length;
  const skipped = runs.filter((r) => r.skipped).length;
  const failed = runs.filter((r) => !r.skipped && r.exitCode !== 0).length;
  const ok = totalWalkers - skipped - failed;

  const lines = [];
  lines.push(`# QA Interaction Audit — full-site sweep — ${startedAt}`);
  lines.push('');
  lines.push(`- Agent: qa-interaction-auditor v2 (full-site coverage)`);
  lines.push(`- Run mode: sweep-all.mjs orchestrator`);
  lines.push(`- Walkers: ${totalWalkers} total — ${ok} ok, ${failed} failed, ${skipped} skipped`);
  lines.push(`- Pre-flight: ${preflightInfo.availableMb} Mi available / ${preflightInfo.totalMb} Mi total`);
  lines.push(`- Started: ${startedAt}`);
  lines.push(`- Finished: ${finishedAt}`);
  lines.push('');
  lines.push('---');
  lines.push('');
  lines.push('## Walker results');
  lines.push('');
  lines.push('| Walker | Status | Page-load | Notes |');
  lines.push('|---|---|---|---|');
  for (const r of runs) {
    if (r.skipped) {
      lines.push(`| ${r.name} | ⏭️  skipped | — | ${r.reason} |`);
      continue;
    }
    const result = r.events.find((e) => e.event === 'walker-result');
    const ok = result?.ok ?? false;
    const icon = r.exitCode === 0 ? (ok ? '✅' : '⚠️') : '❌';
    const note = result?.note ?? result?.loadErr ?? r.stderrTail?.split('\n')[0]?.slice(0, 80) ?? '';
    const dur = result?.durationMs ? `${result.durationMs}ms` : '—';
    lines.push(`| ${r.name} | ${icon} | ${dur} | ${(note ?? '').replace(/\|/g, '\\|').slice(0, 120)} |`);
  }
  lines.push('');
  lines.push('---');
  lines.push('');
  lines.push('## Per-walker raw NDJSON');
  lines.push('');
  for (const r of runs) {
    lines.push(`### ${r.name}`);
    lines.push('');
    lines.push('```');
    if (r.skipped) {
      lines.push(`SKIPPED: ${r.reason}`);
    } else {
      for (const e of r.events) {
        lines.push(JSON.stringify(e));
      }
      if (r.stderrTail) {
        lines.push(`stderr-tail: ${r.stderrTail.replace(/\n/g, ' ').slice(0, 500)}`);
      }
    }
    lines.push('```');
    lines.push('');
  }
  return lines.join('\n');
}

// ──────────────────────────────────────────────────────────────────────
// Main
// ──────────────────────────────────────────────────────────────────────
async function main() {
  const startedAt = new Date().toISOString();
  console.log(`sweep-all started at ${startedAt}`);

  const preflightInfo = preflight();
  console.log(
    `pre-flight: total ${preflightInfo.totalMb}Mi, available ${preflightInfo.availableMb}Mi`
  );
  if (preflightInfo.availableMb < 4096) {
    console.error(
      `BLOCK: only ${preflightInfo.availableMb}Mi available (<4096Mi). Aborting full-site sweep — re-run when RAM frees up.`
    );
    process.exit(1);
  }

  const runs = [];
  for (const w of WALKERS) {
    process.stdout.write(`[${runs.length + 1}/${WALKERS.length}] ${w.name} … `);
    const t0 = Date.now();
    const r = await runWalker(w);
    const dur = Date.now() - t0;
    if (r.skipped) {
      process.stdout.write(`skip (${r.reason})\n`);
    } else {
      const result = r.events.find((e) => e.event === 'walker-result');
      const okStr = r.exitCode === 0 ? (result?.ok ? 'OK' : 'WARN') : 'FAIL';
      process.stdout.write(`${okStr} ${dur}ms\n`);
    }
    runs.push(r);
  }

  const finishedAt = new Date().toISOString();
  const report = buildReport({ runs, preflightInfo, startedAt, finishedAt });
  const path = reportPath();
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, report);
  console.log(`\nreport: ${path}`);

  // Exit non-zero if any walker failed (but skipped is fine).
  const anyFail = runs.some((r) => !r.skipped && r.exitCode !== 0);
  process.exit(anyFail ? 1 : 0);
}

main().catch((err) => {
  console.error('sweep-all fatal:', err);
  process.exit(1);
});
