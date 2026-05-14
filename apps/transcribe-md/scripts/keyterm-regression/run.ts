// ============================================================================
// keyterm-regression/run.ts — Issues #202+#206 PR-3 regression runner
// ----------------------------------------------------------------------------
// For each scenario, exercise the production keyterm composition path:
//   1. Build per-visit keyterms via `buildKeytermsForVisit({ specialty,
//      safetyFloor: CONFUSED_DRUG_NAMES_FLAT })` — the exact call shape
//      used by L1 + L1b post-PR-2.
//   2. Read the cached TTS MP3 produced by synthesize.ts.
//   3. Call `deepgramBatchTranscribe` directly with the audio + built
//      keyterms (skips MinIO + worker queue + Prisma; pure Deepgram-side
//      check). Options match L1b dictation mode (diarize: false,
//      utterances: false).
//   4. Inspect transcript: did the primary appear? Did any confusedWith
//      alternative appear? Score per-scenario.
//
// Output: console summary + Markdown baseline report at
//   /opt/meddoc-pro/docs/keyterm-regression-baseline/baseline-{ISO}.md
//
// Strict serial: one Deepgram call at a time. Per the PR-3 hard
// constraint inherited from PR-2's commit message.
//
// Cost: ~$0.10-0.15 in Deepgram batch (31 fixtures × ~12s each ×
// $0.0145/min nova-3-medical). Plus the ~$0.10 already spent on TTS
// in synthesize.ts. Sub-$1 total.
//
// Usage:
//   cd /opt/meddoc-pro/apps/transcribe-md
//   # 1. Synthesize audio (idempotent, run once):
//   npx tsx scripts/keyterm-regression/synthesize.ts
//   # 2. Run the regression:
//   npx tsx scripts/keyterm-regression/run.ts
// ============================================================================

// boot must be first — it loads /opt/meddoc-pro/.env so the
// @meddoc/db Prisma client picks up DATABASE_URL before its module-
// level initializer runs.
import './_boot';

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';

import { deepgramBatchTranscribe } from '@meddoc/ai';
import { CONFUSED_DRUG_NAMES_FLAT } from '@/lib/confused-drug-names';
import { buildKeytermsForVisit } from '@/lib/deepgram-keyterm-builder';

import { KEYTERM_REGRESSION_SCENARIOS } from './scenarios';
import type { KeytermRegressionScenario } from './scenarios';

const AUDIO_DIR = '/opt/meddoc-pro/.local/keyterm-regression-audio';
const REPORT_DIR = '/opt/meddoc-pro/docs/keyterm-regression-baseline';

interface ScenarioResult {
  scenario: KeytermRegressionScenario;
  keytermLayers: { core: number; specialty: number; safetyFloor: number; patientContext: number };
  estimatedTokens: number;
  budgetEnforced: boolean;
  durationSec: number;
  transcript: string;
  primaryOccurrences: number;
  confusedOccurrences: Record<string, number>;
  passed: boolean;
  failReason?: string;
  costCents: number;
}

function countOccurrences(haystack: string, needle: string): number {
  if (needle.length === 0) return 0;
  const h = haystack.toLowerCase();
  const n = needle.toLowerCase();
  let count = 0;
  let from = 0;
  for (;;) {
    const idx = h.indexOf(n, from);
    if (idx === -1) break;
    // Word-boundary check: char before + after must be non-alphanumeric
    // (or out-of-string). Stops "Implanon" matching inside "Implanonol"
    // or "Heparin" matching inside "Hespanrinate".
    const before = idx === 0 ? '' : h[idx - 1];
    const afterIdx = idx + n.length;
    const after = afterIdx >= h.length ? '' : h[afterIdx];
    const isWordChar = (c: string) => /[a-z0-9]/.test(c);
    if (!isWordChar(before) && !isWordChar(after)) count++;
    from = idx + n.length;
  }
  return count;
}

async function runScenario(s: KeytermRegressionScenario, idx: number, total: number): Promise<ScenarioResult> {
  const label = `[${String(idx + 1).padStart(2, '0')}/${total}] ${s.tag}`;
  process.stdout.write(`${label} … `);

  const built = buildKeytermsForVisit({
    specialty: s.specialty,
    safetyFloor: CONFUSED_DRUG_NAMES_FLAT,
  });

  const audioPath = join(AUDIO_DIR, `${s.tag}.mp3`);
  let audio: Buffer;
  try {
    audio = await readFile(audioPath);
  } catch (err) {
    console.log(`SKIP (no audio: ${(err as Error).message})`);
    return {
      scenario: s,
      keytermLayers: built.metadata.layers,
      estimatedTokens: built.metadata.estimatedTokens,
      budgetEnforced: built.metadata.budgetEnforced,
      durationSec: 0,
      transcript: '',
      primaryOccurrences: 0,
      confusedOccurrences: Object.fromEntries(s.confusedWith.map((c) => [c, 0])),
      passed: false,
      failReason: 'no cached audio (run synthesize.ts first)',
      costCents: 0,
    };
  }

  const t0 = Date.now();
  const result = await deepgramBatchTranscribe({
    audio,
    mimeType: 'audio/mpeg',
    keyterms: built.keyterms,
    options: { diarize: false, utterances: false },
    purpose: 'transcribe_batch',
    practiceId: 'keyterm-regression-script',
  });
  const wallMs = Date.now() - t0;

  const transcript = result.transcript ?? '';
  const primaryOccurrences = countOccurrences(transcript, s.primary);
  const confusedOccurrences: Record<string, number> = Object.fromEntries(
    s.confusedWith.map((c) => [c, countOccurrences(transcript, c)]),
  );

  // Pricing: nova-3-medical batch is $0.0145/min as of 2026-05.
  const costCents = (result.durationSec / 60) * 1.45;

  // Pass condition: primary appears at least once. We don't gate on
  // confusedWith absence because:
  //   1. Some dictation scripts mention the alternative deliberately
  //      (e.g. "Coumadin" + "Cardura" co-mentioned for the warfarin
  //      audit). The script is the ground truth.
  //   2. A clinician COULD legitimately say the alternative.
  //   3. We track confusedWith occurrences in the report so the
  //      reviewer can spot substitution patterns; we just don't make
  //      it a hard fail at this layer.
  const passed = primaryOccurrences > 0;
  const failReason = passed ? undefined : `primary "${s.primary}" not found in transcript`;

  console.log(
    `${passed ? 'PASS' : 'FAIL'} (` +
    `primary=${primaryOccurrences} ` +
    `dur=${result.durationSec}s wall=${(wallMs / 1000).toFixed(1)}s ` +
    `tok=${built.metadata.estimatedTokens} ` +
    `cost=$${(costCents / 100).toFixed(3)}` +
    `)${failReason ? ' — ' + failReason : ''}`,
  );

  return {
    scenario: s,
    keytermLayers: built.metadata.layers,
    estimatedTokens: built.metadata.estimatedTokens,
    budgetEnforced: built.metadata.budgetEnforced,
    durationSec: result.durationSec,
    transcript,
    primaryOccurrences,
    confusedOccurrences,
    passed,
    failReason,
    costCents,
  };
}

function renderReport(results: readonly ScenarioResult[]): string {
  const ts = new Date().toISOString();
  const passed = results.filter((r) => r.passed).length;
  const failed = results.length - passed;
  const totalCost = results.reduce((s, r) => s + r.costCents, 0);
  const audioRan = results.filter((r) => r.durationSec > 0).length;

  let md = '';
  md += `# Keyterm regression baseline — Issues #202 + #206 PR-3\n\n`;
  md += `**Generated:** ${ts}  \n`;
  md += `**Scenarios:** ${results.length}  \n`;
  md += `**Passed:** ${passed} / ${results.length}  \n`;
  md += `**Failed:** ${failed}  \n`;
  md += `**Audio scenarios actually run (rest skipped due to missing cache):** ${audioRan}  \n`;
  md += `**Total Deepgram cost:** $${(totalCost / 100).toFixed(3)} (nova-3-medical @ $0.0145/min)  \n`;
  md += '\n';
  md += '## Method\n\n';
  md += '- Each scenario synthesizes a ~150-250 char doctor-dictation script via OpenAI tts-1 ("onyx" voice).\n';
  md += '- Audio is read from `.local/keyterm-regression-audio/{tag}.mp3` (idempotent cache).\n';
  md += '- `buildKeytermsForVisit({ specialty, safetyFloor: CONFUSED_DRUG_NAMES_FLAT })` composes per-scenario keyterms.\n';
  md += '- `deepgramBatchTranscribe` with `diarize: false, utterances: false` (dictation mode).\n';
  md += '- Pass = primary medication name appears in the transcript at least once (word-boundary, case-insensitive).\n';
  md += '- `confusedWith` occurrences are tracked but not gated — co-mention is allowed.\n';
  md += '\n';
  md += '## Per-scenario results\n\n';
  md += '| Tag | Primary | Pass | Primary hits | Confused hits | Tokens | Audio dur | Cost ¢ |\n';
  md += '|---|---|---|---|---|---|---|---|\n';
  for (const r of results) {
    const confusedSummary =
      Object.entries(r.confusedOccurrences)
        .filter(([, n]) => n > 0)
        .map(([k, n]) => `${k}=${n}`)
        .join(', ') || '—';
    md += `| ${r.scenario.tag} | ${r.scenario.primary} | ${r.passed ? '✓' : '✗'} | ${r.primaryOccurrences} | ${confusedSummary} | ${r.estimatedTokens} | ${r.durationSec}s | ${r.costCents.toFixed(2)} |\n`;
  }
  md += '\n';
  md += '## Failures — detail\n\n';
  const fails = results.filter((r) => !r.passed);
  if (fails.length === 0) {
    md += 'None.\n\n';
  } else {
    for (const r of fails) {
      md += `### ${r.scenario.tag} — ${r.scenario.primary}\n\n`;
      md += `- **Specialty:** \`${r.scenario.specialty}\`\n`;
      md += `- **Fail reason:** ${r.failReason ?? 'unknown'}\n`;
      md += `- **Script:** ${r.scenario.dictation}\n`;
      md += `- **Transcript:** ${r.transcript || '(empty)'}\n`;
      md += `- **Confused hits:** ${
        Object.entries(r.confusedOccurrences)
          .filter(([, n]) => n > 0)
          .map(([k, n]) => `${k} (${n})`)
          .join(', ') || 'none'
      }\n`;
      md += '\n';
    }
  }
  md += '## Keyterm-budget invariant\n\n';
  const anyBudgetEnforced = results.some((r) => r.budgetEnforced);
  md += `**Builder \`budgetEnforced\` ever triggered:** ${anyBudgetEnforced ? 'YES — investigate' : 'NO ✓ (specialty bundles ride untrimmed)'}\n\n`;
  md += '---\n\n';
  md += '_Closes PR-3 milestone of Issues #202 + #206. Cited from PR-4 audit doc._\n';
  return md;
}

async function main(): Promise<void> {
  console.log(`Keyterm regression — ${KEYTERM_REGRESSION_SCENARIOS.length} scenarios, strict serial`);
  console.log('');
  const results: ScenarioResult[] = [];
  for (let i = 0; i < KEYTERM_REGRESSION_SCENARIOS.length; i++) {
    const r = await runScenario(KEYTERM_REGRESSION_SCENARIOS[i], i, KEYTERM_REGRESSION_SCENARIOS.length);
    results.push(r);
  }
  console.log('');
  const passed = results.filter((r) => r.passed).length;
  console.log(`SUMMARY: ${passed}/${results.length} passed`);

  await mkdir(REPORT_DIR, { recursive: true });
  const reportPath = join(REPORT_DIR, `baseline-${new Date().toISOString().replace(/[:.]/g, '-')}.md`);
  await writeFile(reportPath, renderReport(results));
  console.log(`Report: ${reportPath}`);
}

main().catch((err) => {
  console.error('FAIL:', err);
  process.exit(1);
});
