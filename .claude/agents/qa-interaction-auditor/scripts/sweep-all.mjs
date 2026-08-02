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
import { mkdirSync, writeFileSync, existsSync, unlinkSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { randomBytes } from 'node:crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCRIPT_DIR = __dirname;
const REPO_ROOT = resolve(__dirname, '..', '..', '..', '..');

// One sweep-run id per orchestrator invocation. All child walkers
// inherit it via QA_SWEEP_RUN_ID env so they share a single cached
// auth-session file in /tmp (v3.1 fix for the v2 rate-limit cascade
// where 28 separate logins tripped /login's rate limiter).
const SWEEP_RUN_ID = randomBytes(6).toString('hex');
const SESSION_FILE = resolve(tmpdir(), `qa-auditor-session-${SWEEP_RUN_ID}.json`);

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
  // ⚠️ `board` needs a Rounds FLAG-ON image. NEXT_PUBLIC_SKIN_ROUNDS is
  // build-time inlined and board/page.tsx fails closed to a 404, so on a
  // flag-OFF build this walker refuses at its premise check rather than
  // walking the 404 and reporting ok:true. See sweep-board.mjs's header.
  { name: 'board', file: 'sweep-board.mjs', auth: true },
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
  { name: 'admin-queues', file: 'sweep-admin-queues.mjs', auth: true },
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
// Auto-resolve the deep-walker fixture from seeded-ids.json so the
// orchestrator no longer skips visit-page. Defaults to the
// bump-eligible scenario; operators can override via env.
function deepWalkerFixtureId() {
  if (process.env.QA_FIXTURE_VISIT_ID) return process.env.QA_FIXTURE_VISIT_ID;
  const seededPath = resolve(
    __dirname,
    '..',
    'fixtures',
    'seeded-ids.json'
  );
  if (!existsSync(seededPath)) return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const seeded = JSON.parse(execSync(`cat ${seededPath}`, { encoding: 'utf-8' }));
    const scenario = process.env.QA_SCENARIO ?? 'bumpEligible';
    const id = seeded.visitIds?.[scenario] ?? null;
    if (!id) return null;

    // FAIL CLOSED (full-app audit 2026-07-24). The seeders run inside the
    // db-migrate container, so they write seeded-ids.json to the CONTAINER
    // filesystem — the host copy is not a bind mount and goes stale silently.
    // On 2026-07-24 the host file still named a userId/patientId from
    // 2026-06-15 and five qa_fix_visit_* ids that no longer existed in the DB
    // (0 rows). Because an id was still *resolvable* from the JSON, the
    // orchestrator did not take its `skipped` branch: the flagship walker
    // launched, walked a not-found page, and reported on it. Verify the id
    // actually exists in the target DB before handing it to the walker.
    const container = process.env.QA_AUDITOR_DB_CONTAINER ?? 'meddoc-qa-postgres-1';
    const dbName = process.env.QA_AUDITOR_DB_NAME ?? 'meddoc_qa_test';
    const dbUser = process.env.QA_AUDITOR_DB_USER ?? 'meddoc';
    try {
      const sql = `SELECT COUNT(*) FROM transcribe_visits WHERE id='${id.replace(/'/g, "''")}';`;
      const n = parseInt(
        execSync(
          `docker exec ${container} psql -U ${dbUser} -d ${dbName} -tA -c ${JSON.stringify(sql)}`,
          { encoding: 'utf-8', stdio: ['ignore', 'pipe', 'pipe'] }
        ).trim(),
        10
      );
      if (!Number.isFinite(n) || n < 1) {
        console.error(
          `[sweep-all] STALE FIXTURES: '${id}' (scenario=${scenario}) is named in ` +
            `${seededPath} but does not exist in ${dbName}. Re-run seed-qa-fixtures.ts. ` +
            `Refusing to walk a non-existent visit.`
        );
        return null;
      }
    } catch (err) {
      console.error(
        `[sweep-all] Could not verify fixture '${id}' against ${dbName}: ` +
          `${err instanceof Error ? err.message : err}. Refusing to walk unverified fixtures.`
      );
      return null;
    }
    return id;
  } catch {
    return null;
  }
}

function runWalker(walker) {
  return new Promise((resolveFn) => {
    const file = resolve(SCRIPT_DIR, walker.file);
    // Propagate the sweep-run id so all walkers share one
    // /tmp/qa-auditor-session-<id>.json — first auth walker logs in
    // once, the rest reuse the cached storageState.
    const env = { ...process.env, QA_SWEEP_RUN_ID: SWEEP_RUN_ID };

    if (walker.deep) {
      const fixtureId = deepWalkerFixtureId();
      if (!fixtureId) {
        return resolveFn({
          name: walker.name,
          skipped: true,
          reason:
            'No fixture visit id resolvable. Run seed-qa-fixtures.ts or set QA_FIXTURE_VISIT_ID.',
        });
      }
      env.QA_FIXTURE_VISIT_ID = fixtureId;
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
  const orchSkipped = runs.filter((r) => r.skipped).length;
  const selfSkipped = runs.filter((r) =>
    !r.skipped && r.events?.some((e) => e.event === 'walker-skip')
  ).length;
  const skipped = orchSkipped + selfSkipped;
  const failed = runs.filter((r) => !r.skipped && r.exitCode !== 0).length;
  // Walkers whose DB probes errored: they exited 0 and looked green, but their
  // assertions never ran. Counted separately so the headline can never again
  // read "30/30 ok" over a sweep that verified nothing on the data side.
  const dbBroken = runs.filter(
    (r) =>
      !r.skipped &&
      r.exitCode === 0 &&
      r.events?.some((e) => e.event === 'db-probe-error')
  ).length;
  const ok = totalWalkers - skipped - failed - dbBroken;

  const lines = [];
  lines.push(`# QA Interaction Audit — full-site sweep — ${startedAt}`);
  lines.push('');
  lines.push(`- Agent: qa-interaction-auditor v3.1 (storageState + rich fixtures + deepWalk)`);
  lines.push(`- Run mode: sweep-all.mjs orchestrator`);
  lines.push(
    `- Walkers: ${totalWalkers} total — ${ok} ok, ${failed} failed, ${skipped} skipped` +
      (dbBroken ? `, **${dbBroken} DB-probe-broken (assertions did not run)**` : '')
  );
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
    // walker-skip is a self-declared skip emitted by the walker
    // itself (e.g. visit-record skipping when no draft visit exists).
    // Treat it identically to the orchestrator-side skip.
    const selfSkip = r.events.find((e) => e.event === 'walker-skip');
    if (selfSkip) {
      lines.push(`| ${r.name} | ⏭️  skipped | — | ${(selfSkip.reason ?? '').slice(0, 120)} |`);
      continue;
    }
    const result = r.events.find((e) => e.event === 'walker-result');
    // A DB probe that errored proves nothing, so a walker that emitted one
    // cannot be reported as ✅ — its zero-write / side-effect assertions did
    // not actually run. Before 2026-07-24 these were swallowed and the sweep
    // reported 30/30 ok while emitting 14 Postgres errors.
    const dbProbeErrors = r.events.filter((e) => e.event === 'db-probe-error');
    const ok = (result?.ok ?? false) && dbProbeErrors.length === 0;
    const icon = r.exitCode === 0 ? (ok ? '✅' : '⚠️') : '❌';
    const note = dbProbeErrors.length
      ? `DB PROBE FAILED (${dbProbeErrors.length}) — assertions did not run: ${(dbProbeErrors[0].error ?? '').split('\n')[0].slice(0, 90)}`
      : (result?.note ?? result?.loadErr ?? r.stderrTail?.split('\n')[0]?.slice(0, 80) ?? '');
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
  console.log(`sweep-run-id: ${SWEEP_RUN_ID} (session at ${SESSION_FILE})`);

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
      const selfSkip = r.events?.find((e) => e.event === 'walker-skip');
      const result = r.events?.find((e) => e.event === 'walker-result');
      let okStr;
      if (r.exitCode !== 0) okStr = 'FAIL';
      else if (selfSkip) okStr = 'skip';
      else if (result?.ok) okStr = 'OK';
      else okStr = 'WARN';
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

  // Sweep done — best-effort cleanup of the cached session file.
  // Leaving it would leak a logged-in cookie until /tmp is cleared;
  // the file's TTL would also auto-invalidate it, but explicit beats
  // implicit.
  if (existsSync(SESSION_FILE)) {
    try { unlinkSync(SESSION_FILE); } catch { /* ignore */ }
  }

  // Exit non-zero if any walker failed (but skipped is fine).
  const anyFail = runs.some((r) => !r.skipped && r.exitCode !== 0);
  process.exit(anyFail ? 1 : 0);
}

main().catch((err) => {
  console.error('sweep-all fatal:', err);
  process.exit(1);
});
