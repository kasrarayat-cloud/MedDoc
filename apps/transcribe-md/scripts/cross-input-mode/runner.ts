/* eslint-disable */
// ============================================================================
// Cross-input-mode audit runner (2026-05-13).
// ----------------------------------------------------------------------------
// For each scenario × {text_notes, voice_dictation, audio_upload}, creates
// a visit row, uploads the appropriate input artifact (text or audio),
// enqueues the pipeline, polls until terminal status. Final results
// land in /tmp/cross-input-mode-results.json for the analyzer.
//
// SAFETY: this runner spends real Anthropic + Deepgram budget. Each
// visit is ~$0.40-0.50. 72 visits = ~$30-35. Confirm credit balance is
// healthy before invoking.
//
// Idempotency:
//   - The scenarios + audio fixtures are stable across runs (audio is
//     cached by `synthesize.py` in /opt/meddoc-pro/.local/cross-input-
//     mode-audio/).
//   - The visit rows are CREATED FRESH per invocation. To avoid
//     billing churn, run this ONCE per intended audit cycle. Subsequent
//     iterations should use the analyzer + an `--include` flag on a
//     subset of failed visits rather than re-running all 72.
//   - All visits are soft-deleted at the end of the run.
//
// Usage:
//   cd /opt/meddoc-pro
//   # 1. Write the scenarios manifest the TTS synthesizer reads:
//   tsx apps/transcribe-md/scripts/cross-input-mode/runner.ts --emit-manifest
//   # 2. Synthesize audio (idempotent — skips existing):
//   python3 apps/transcribe-md/scripts/cross-input-mode/synthesize.py \\
//     --manifest /tmp/cross-input-mode-manifest.json
//   # 3. Run the full pipeline cycle:
//   tsx apps/transcribe-md/scripts/cross-input-mode/runner.ts --run
//   # 4. Analyze:
//   python3 apps/transcribe-md/scripts/cross-input-mode/analyze.py
// ============================================================================

import { prisma } from '@meddoc/db';
import { assertNonProdDatabase } from '@meddoc/db/guard';
import { putAudioStream } from '../../src/lib/minio';
import { enqueueProcessVisit } from '../../src/lib/queue';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { SCENARIOS, INPUT_MODES, type Scenario, type InputMode } from './scenarios';

// Test patient + user — reuses the Kasra solo-practice fixture that
// the prior deep-audit harnesses landed against.
const USER_ID = 'cmo5ye2nm000c01s3ofudqzi6';
const PRACTICE_ID = 'cmo5ye2nf000b01s3q0xlkaxb';
const TEST_PATIENT_NAME = 'CrossInputMode Audit Patient';

const AUDIO_DIR = '/opt/meddoc-pro/.local/cross-input-mode-audio';
const MANIFEST_PATH = '/tmp/cross-input-mode-manifest.json';
const RESULTS_PATH = '/tmp/cross-input-mode-results.json';

interface VisitRecord {
  scenarioTag: string;
  specialty: string;
  specialtyLabel: string;
  scenarioTitle: string;
  mode: InputMode;
  visitId: string;
}

/** Build the manifest that synthesize.py consumes. */
function emitManifest(): void {
  const manifest: Record<string, { text: string; voice: string }> = {};
  for (const s of SCENARIOS) {
    manifest[s.tag] = { text: s.script, voice: 'onyx' };
  }
  writeFileSync(MANIFEST_PATH, JSON.stringify(manifest, null, 2));
  console.log(`[runner] wrote manifest with ${Object.keys(manifest).length} scenarios → ${MANIFEST_PATH}`);
  const totalChars = SCENARIOS.reduce((acc, s) => acc + s.script.length, 0);
  console.log(`[runner] total script chars: ${totalChars} (TTS cost ~$${(totalChars / 1_000_000 * 15).toFixed(2)})`);
}

async function findOrCreatePatient() {
  let p = await prisma.transcribeMdPatient.findFirst({
    where: { practiceId: PRACTICE_ID, name: TEST_PATIENT_NAME, deletedAt: null },
    select: { id: true },
  });
  if (!p) {
    p = await prisma.transcribeMdPatient.create({
      data: { practiceId: PRACTICE_ID, name: TEST_PATIENT_NAME },
      select: { id: true },
    });
  }
  return p.id;
}

async function createVisitForScenario(
  scenario: Scenario,
  mode: InputMode,
  patientId: string,
): Promise<string> {
  const data: any = {
    userId: USER_ID,
    patientId,
    patientName: TEST_PATIENT_NAME,
    specialty: scenario.specialty,
    chiefComplaint: scenario.title.slice(0, 120),
    inputMode: mode,
    interpreterMode: false,
    status: 'QUEUED',
  };
  if (mode === 'text_notes') {
    data.rawTextInput = scenario.script;
  }
  const v = await prisma.transcribeVisit.create({
    data,
    select: { id: true },
  });
  return v.id;
}

async function uploadAudioForVisit(scenario: Scenario, mode: InputMode, visitId: string): Promise<void> {
  const audioPath = `${AUDIO_DIR}/${scenario.tag}.mp3`;
  if (!existsSync(audioPath)) {
    throw new Error(`Audio fixture missing for ${scenario.tag} at ${audioPath}. Run synthesize.py first.`);
  }
  const buf = readFileSync(audioPath);
  const ts = Date.now();
  if (mode === 'audio_upload') {
    const audioKey = `${USER_ID}/${visitId}/upload-${ts}.mp3`;
    await putAudioStream(audioKey, buf, buf.byteLength, 'audio/mpeg');
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: {
        audioKey,
        audioMimeType: 'audio/mpeg',
        audioSizeBytes: buf.byteLength,
        audioUploadedAt: new Date(),
      },
    });
  } else if (mode === 'voice_dictation') {
    const audioKey = `${USER_ID}/${visitId}/dictation-${ts}.mp3`;
    await putAudioStream(audioKey, buf, buf.byteLength, 'audio/mpeg');
    await prisma.transcribeVisit.update({
      where: { id: visitId },
      data: { dictationAudioKey: audioKey },
    });
  }
}

async function runAll(includeTags?: Set<string>): Promise<void> {
  const patientId = await findOrCreatePatient();
  console.log(`[runner] test patient ${patientId}`);

  const targetScenarios = includeTags
    ? SCENARIOS.filter((s) => includeTags.has(s.tag))
    : SCENARIOS;
  if (includeTags) {
    const missing = [...includeTags].filter(
      (t) => !targetScenarios.find((s) => s.tag === t),
    );
    if (missing.length > 0) {
      throw new Error(`--include refers to unknown tags: ${missing.join(', ')}`);
    }
    console.log(
      `[runner] include filter: ${targetScenarios.length}/${SCENARIOS.length} scenarios — ${targetScenarios.map((s) => s.tag).join(', ')}`,
    );
  }

  // Pre-check: confirm all audio fixtures exist.
  for (const s of targetScenarios) {
    const p = `${AUDIO_DIR}/${s.tag}.mp3`;
    if (!existsSync(p)) {
      throw new Error(`Audio fixture missing for ${s.tag}. Run synthesize.py first (or rebuild missing fixtures).`);
    }
  }

  // Create + enqueue all visits. We use the canonical
  // `enqueueProcessVisit` so the per-minute idempotent jobId + the
  // prior-job-cleanup logic (PR #228) match what the production code
  // path uses — keeps the harness inside the production envelope.
  const records: VisitRecord[] = [];
  for (const s of targetScenarios) {
    for (const mode of INPUT_MODES) {
      const visitId = await createVisitForScenario(s, mode, patientId);
      if (mode !== 'text_notes') {
        await uploadAudioForVisit(s, mode, visitId);
      }
      await enqueueProcessVisit(visitId, USER_ID);
      records.push({
        scenarioTag: s.tag,
        specialty: s.specialty,
        specialtyLabel: s.specialtyLabel,
        scenarioTitle: s.title,
        mode,
        visitId,
      });
      console.log(`[runner] created ${s.tag} ${mode} → ${visitId}`);
    }
  }
  console.log(`\n[runner] enqueued ${records.length} visits across ${SCENARIOS.length} scenarios × ${INPUT_MODES.length} modes. Polling…\n`);

  // Poll until terminal.
  const targets = records.map((r) => r.visitId);
  const deadline = Date.now() + 6 * 60 * 60 * 1000; // 6h hard cap
  const done = new Set<string>();
  let lastReport = 0;
  while (Date.now() < deadline && done.size < targets.length) {
    await new Promise((r) => setTimeout(r, 30_000));
    const rows = await prisma.transcribeVisit.findMany({
      where: { id: { in: targets } },
      select: { id: true, status: true },
    });
    for (const r of rows) {
      // Real terminal states on TranscribeVisitStatus: READY, SIGNED,
      // FAILED. DRAFT lives only on DocumentStatus — not applicable here.
      if (['READY', 'SIGNED', 'FAILED'].includes(r.status as string) && !done.has(r.id)) {
        done.add(r.id);
      }
    }
    if (Date.now() - lastReport > 60_000) {
      const counts: Record<string, number> = {};
      for (const r of rows) counts[r.status as string] = (counts[r.status as string] || 0) + 1;
      console.log(`[runner] status: ${JSON.stringify(counts)} | done=${done.size}/${targets.length}`);
      lastReport = Date.now();
    }
  }
  console.log(`\n[runner] polling complete: ${done.size}/${targets.length} terminal`);

  // Pull full results.
  const results: any[] = [];
  for (const rec of records) {
    const v: any = await prisma.transcribeVisit.findUnique({
      where: { id: rec.visitId },
      select: {
        id: true,
        status: true,
        inputMode: true,
        interpreterMode: true,
        specialty: true,
        chiefComplaint: true,
        transcriptText: true,
        soapNote: true,
        soapFinal: true,
        icdCodes: true,
        cptCodes: true,
        rxDrafts: true,
        speakerMap: true,
        confidenceScores: true,
        failureCategory: true,
        reviewReason: true,
        audioDurationSec: true,
        processingCostCents: true,
      },
    });
    results.push({ ...rec, ...v });
  }
  writeFileSync(RESULTS_PATH, JSON.stringify(results, null, 2));
  console.log(`[runner] wrote ${results.length} results → ${RESULTS_PATH}`);

  // Soft-delete all visits.
  await prisma.transcribeVisit.updateMany({
    where: { id: { in: targets } },
    data: { deletedAt: new Date() },
  });
  console.log(`[runner] ${targets.length} visits soft-deleted`);

  const totalCost = results.reduce(
    (sum, r) => sum + (r.processingCostCents ?? 0),
    0,
  );
  console.log(`\n[runner] === run complete: total pipeline cost $${(totalCost / 100).toFixed(2)}`);
}

/** Emit a JSON manifest of every scenario's safety-rule labels for the
 *  analyzer's round-trip parity self-check. The analyzer's regex
 *  parser of scenarios.ts is best-effort; this manifest is the
 *  ground-truth label set. If the parser drops or fabricates a rule
 *  label, analyze.py fails loudly instead of silently mis-counting. */
function emitRuleLabels(): void {
  const labels: Array<{ tag: string; label: string; required: boolean }> = [];
  for (const s of SCENARIOS) {
    for (const rule of s.expect.rxSafetyRules ?? []) {
      labels.push({
        tag: s.tag,
        label: rule.label,
        required: rule.required ?? false,
      });
    }
  }
  const out = '/tmp/cross-input-mode-rule-labels.json';
  writeFileSync(out, JSON.stringify(labels, null, 2));
  console.log(`[runner] wrote ${labels.length} rule labels → ${out}`);
}

async function main() {
  const flag = process.argv[2];
  if (flag === '--emit-manifest') {
    emitManifest();
    return;
  }
  if (flag === '--emit-rule-labels') {
    emitRuleLabels();
    return;
  }
  if (flag === '--run') {
    // Optional --include TAG1,TAG2,... — runs the targeted subset of
    // scenarios across all three modes. Useful for verification re-runs
    // after a targeted fix; avoids the full 72-visit / ~$22 cost.
    const includeIdx = process.argv.indexOf('--include');
    let includeTags: Set<string> | undefined;
    if (includeIdx > 0) {
      const includeArg = process.argv[includeIdx + 1];
      // Guard: `--include` at end of argv with no value would otherwise
      // silently fall through to the full 72-visit batch. Fail loudly
      // so a typo doesn't burn ~$22.
      if (!includeArg || includeArg.startsWith('--')) {
        throw new Error('--include requires a comma-separated tag list (e.g., --include PED1,UC2,DERM1)');
      }
      includeTags = new Set(
        includeArg.split(',').map((s) => s.trim()).filter(Boolean),
      );
      if (includeTags.size === 0) {
        throw new Error('--include received an empty tag list after trim/split');
      }
    }
    // FAIL-CLOSED: never create visits against prod (see packages/db/src/db-guard.ts).
    assertNonProdDatabase();
    await runAll(includeTags);
    return;
  }
  console.error(
    'Usage: runner.ts --emit-manifest | --emit-rule-labels | --run [--include TAG1,TAG2,...]',
  );
  process.exit(1);
}

main()
  .then(() => prisma.$disconnect().then(() => process.exit(0)))
  .catch((e) => {
    console.error(e);
    prisma.$disconnect().finally(() => process.exit(1));
  });
