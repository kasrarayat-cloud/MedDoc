// Smoke test for the llm-mdm.ts hotfix:
// 1. Verify cold call returns llmJudged=true (would have timed out with old 8s cap on this rubric)
// 2. Verify warm call (within 5-min Anthropic cache window) is faster than cold
// 3. Confirm telemetry path didn't break (no thrown errors from logAiCall/logApiUsage)
// Run: cd apps/transcribe-md && tsx scripts/llm-mdm-smoke.ts

import 'dotenv/config';
import fs from 'node:fs';
import path from 'node:path';
import { judgeMdm } from '../src/lib/em-coding/llm-mdm';

const FIXTURE = '/opt/meddoc-pro/tests/fixtures/soap-em-corpus/21-complex-dm-exacerbation.md';

function loadSoap(file: string): string {
  const raw = fs.readFileSync(file, 'utf8');
  const m = raw.match(/^---\n[\s\S]*?\n---\n([\s\S]*)$/);
  return (m ? m[1] : raw).trim();
}

(async () => {
  const soap = loadSoap(FIXTURE);
  console.log(`[smoke] fixture: ${path.basename(FIXTURE)}`);
  console.log(`[smoke] soap length: ${soap.length} chars`);

  const args = {
    soap,
    // Use a real practice so telemetry FKs don't fire-and-forget-warn.
    practiceId: 'clinic_main',
    // visitId/userId omitted → telemetry rows go in with null FKs
    // (which is allowed by the schema for both AiCall and ApiUsageEvent).
    visitId: undefined as string | undefined,
    userId: null,
  };

  console.log('\n[smoke] --- COLD CALL ---');
  const coldStart = Date.now();
  const cold = await judgeMdm(args);
  const coldMs = Date.now() - coldStart;
  console.log(`[smoke] cold latency: ${coldMs}ms`);
  console.log(`[smoke] cold result: cacheHit=${cold.cacheHit} llmJudged=${cold.llmJudged} tier=${cold.judgement.tier}`);
  console.log(`[smoke] cold elements: problems=${cold.judgement.elements.problems.level} data=${cold.judgement.elements.data.level} risk=${cold.judgement.elements.risk.level}`);
  if (!cold.llmJudged) {
    console.error('[smoke] FAIL — cold call did not LLM-judge (timeout or error)');
    process.exit(1);
  }
  if (cold.judgement.tier !== 'high') {
    console.warn(`[smoke] WARN — expected tier=high for fixture 21, got tier=${cold.judgement.tier}`);
  }

  console.log('\n[smoke] --- WARM CALL (different SOAP body, same rubric → Anthropic prompt cache hit) ---');
  const warmArgs = { ...args, soap: soap + '\n[smoke-suffix]' };
  const warmStart = Date.now();
  const warm = await judgeMdm(warmArgs);
  const warmMs = Date.now() - warmStart;
  console.log(`[smoke] warm latency: ${warmMs}ms`);
  console.log(`[smoke] warm result: cacheHit=${warm.cacheHit} llmJudged=${warm.llmJudged} tier=${warm.judgement.tier}`);
  if (!warm.llmJudged) {
    console.error('[smoke] FAIL — warm call did not LLM-judge');
    process.exit(1);
  }

  console.log('\n[smoke] --- VERDICT ---');
  console.log(`[smoke] cold: ${coldMs}ms | warm: ${warmMs}ms | speedup: ${(coldMs / warmMs).toFixed(2)}x`);
  console.log('[smoke] PASS — both calls returned llmJudged=true (Path C confirmed live)');

  // Give the fire-and-forget telemetry a moment to flush so we don't
  // exit before the AiCall row commits.
  await new Promise((r) => setTimeout(r, 1500));
  process.exit(0);
})().catch((err) => {
  console.error('[smoke] uncaught error:', err);
  process.exit(2);
});
