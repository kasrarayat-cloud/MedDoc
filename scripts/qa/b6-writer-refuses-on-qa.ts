// ============================================================================
// B6 — DEMONSTRATE THAT THE BILLING WRITER REFUSES ON THE LIVE QA STACK
// ----------------------------------------------------------------------------
// RELAY B6's gate: "the writer REFUSES ON THE LIVE QA STACK, demonstrated, not
// asserted (F4)." A unit test asserting `expect(...).toThrow()` against a
// string literal is an assertion about a function. This points the real writer
// at the real QA database and watches it decline.
//
// ⚠️ IT TAKES THE URL FROM THE RUNNING QA CONTAINER, NOT FROM A LITERAL.
// A hardcoded connection string would prove the guard rejects a string somebody
// typed. The whole failure class this programme keeps hitting is a config that
// READS safe and is not — `${VAR:-default}` inheriting production's value from
// the shared .env — so the only evidence worth having comes from the live
// process environment. `check-qa-mock-posture.sh` reads the containers for
// exactly this reason.
//
// ⚠️ AND IT RUNS THE POSITIVE CONTROL FIRST. A writer that throws for ANY
// reason would satisfy "it refused" — a missing import, a typo, an unreachable
// database. So the run first proves the guard ACCEPTS the production database
// name, then proves it refuses the QA one. One arm alone is an all-clear that
// cannot discriminate.
//
// READ-ONLY with respect to both databases: the only call that could write is
// the one being demonstrated to refuse, and it refuses before touching Prisma.
//
// Usage: npx tsx scripts/qa/b6-writer-refuses-on-qa.ts
// Exit:  0 = refused on QA and accepted for prod · 1 = FINDING · 2 = cannot tell
// ============================================================================

import { execFileSync } from 'node:child_process';

const QA_CONTAINER = 'meddoc-qa-transcribe-md-1';

function liveQaDatabaseUrl(): string | null {
  try {
    const out = execFileSync(
      'docker',
      ['exec', QA_CONTAINER, 'printenv', 'DATABASE_URL'],
      { encoding: 'utf8' },
    ).trim();
    return out || null;
  } catch {
    return null;
  }
}

/** Never print a connection string — it carries a password. Say only what the
 *  guard actually keys on. */
function describeSafely(url: string): string {
  try {
    const u = new URL(url);
    return `host=${u.hostname} database=${decodeURIComponent(u.pathname.replace(/^\//, ''))}`;
  } catch {
    return '(unparseable)';
  }
}

async function main(): Promise<number> {
  const qaUrl = liveQaDatabaseUrl();
  if (!qaUrl) {
    console.log(`🟡 ${QA_CONTAINER} is not running or has no DATABASE_URL — cannot tell.`);
    return 2;
  }
  console.log(`live QA target, read from the container: ${describeSafely(qaUrl)}`);

  const { assertProdDatabase } = await import('@meddoc/db/guard');

  // ── POSITIVE CONTROL ─────────────────────────────────────────────────────
  // The guard must ACCEPT production. Without this, "it threw" proves nothing.
  let controlOk = false;
  try {
    const t = assertProdDatabase('postgresql://u:p@postgres:5432/meddoc');
    controlOk = t.database === 'meddoc';
    console.log(`   ✔ positive control: the guard ACCEPTS database=meddoc`);
  } catch (err) {
    console.log(`   ✖ positive control FAILED — the guard rejects production too:`);
    console.log(`     ${err instanceof Error ? err.message.split('\n')[0] : err}`);
  }
  if (!controlOk) {
    console.log('\n🟡 the instrument does not discriminate — no verdict.');
    return 2;
  }

  // ── THE DEMONSTRATION ────────────────────────────────────────────────────
  // Point the writer at the live QA database and call it for real.
  process.env.DATABASE_URL = qaUrl;
  const { commitVisitCharge } = await import('@meddoc/ai');

  try {
    await commitVisitCharge({
      practiceId: 'clinic_main',
      visitId: 'b6-refusal-demo',
      rows: [
        {
          id: 'b6-demo-evt',
          provider: 'anthropic',
          modelName: 'claude-sonnet-5',
          unitsSource: 'vendor',
          createdAt: new Date('2026-08-10T00:00:00Z'),
          audioSeconds: null,
          inputTokens: 1_000_000,
          outputTokens: null,
          cacheReadInputTokens: null,
          cacheCreationInputTokens: null,
        },
      ],
    });
    console.log('\n🔴 THE WRITER DID NOT REFUSE. It ran against the QA database.');
    console.log('   F4 is not met. A charge written to a QA practice cannot be');
    console.log('   deleted — ledger_entries is append-only by trigger.');
    return 1;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    // ⚠️ A REFUSAL IS EVIDENCE ONLY WHEN YOU KNOW WHAT REFUSED. Any throw would
    // end up here — an unreachable database, a missing export, a typo. Match
    // the guard's own words, not merely the fact of an exception.
    const isTheGuard = msg.includes('[db-guard] FAIL-CLOSED') && msg.includes('BILLING WRITER');
    if (!isTheGuard) {
      console.log('\n🟡 it threw, but NOT from the prod-only guard — cannot tell:');
      console.log(`   ${msg.split('\n')[0]}`);
      return 2;
    }
    console.log('\n   ✔ the writer REFUSED, and the guard is what refused:');
    for (const line of msg.split('\n').slice(0, 3)) console.log(`     ${line}`);
    console.log('\n🟢 F4 met — the billing writer refuses on the live QA stack.');
    return 0;
  }
}

main().then(
  (code) => process.exit(code),
  (err) => {
    console.error('🟡 harness error — cannot tell:', err);
    process.exit(2);
  },
);
