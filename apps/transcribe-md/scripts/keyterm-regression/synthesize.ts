// ============================================================================
// keyterm-regression/synthesize.ts — TTS audio synthesis (Issues #202+#206 PR-3)
// ----------------------------------------------------------------------------
// Serial synthesis of doctor-dictation audio for each scenario in
// scenarios.ts. Reads OPENAI_API_KEY from /opt/meddoc-pro/.env, uses
// tts-1 with the "onyx" voice (same choice as the cross-input-mode
// runner), writes MP3 to .local/keyterm-regression-audio/{tag}.mp3.
//
// Idempotent: a scenario whose MP3 already exists is skipped. To force
// regeneration, delete the specific file first.
//
// Serial: one OpenAI request at a time. Per the PR-3 strict-serial
// constraint (no parallel TTS spawning) — see the operator note in
// PR-2's commit message (#247) for the why.
//
// Usage:
//   cd /opt/meddoc-pro/apps/transcribe-md
//   npx tsx scripts/keyterm-regression/synthesize.ts
// ============================================================================

import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

import { KEYTERM_REGRESSION_SCENARIOS } from './scenarios';

const OUT_DIR = '/opt/meddoc-pro/.local/keyterm-regression-audio';
const ENV_PATH = '/opt/meddoc-pro/.env';
const VOICE = 'onyx';
const MODEL = 'tts-1';

async function loadApiKey(): Promise<string> {
  const envText = await readFile(ENV_PATH, 'utf8');
  for (const line of envText.split('\n')) {
    if (line.startsWith('OPENAI_API_KEY=')) {
      return line.slice('OPENAI_API_KEY='.length).trim();
    }
  }
  throw new Error('OPENAI_API_KEY missing from ' + ENV_PATH);
}

async function fileExists(path: string): Promise<boolean> {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

async function synth(apiKey: string, text: string, outPath: string): Promise<number> {
  const body = JSON.stringify({
    model: MODEL,
    voice: VOICE,
    input: text,
    response_format: 'mp3',
    speed: 1.0,
  });
  const resp = await fetch('https://api.openai.com/v1/audio/speech', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body,
  });
  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(`OpenAI TTS ${resp.status}: ${errText.slice(0, 200)}`);
  }
  const buf = Buffer.from(await resp.arrayBuffer());
  await writeFile(outPath, buf);
  return buf.length;
}

async function main(): Promise<void> {
  await mkdir(OUT_DIR, { recursive: true });
  const apiKey = await loadApiKey();

  let totalBytes = 0;
  let synthed = 0;
  let skipped = 0;
  let totalChars = 0;

  for (let i = 0; i < KEYTERM_REGRESSION_SCENARIOS.length; i++) {
    const s = KEYTERM_REGRESSION_SCENARIOS[i];
    const idx = `[${String(i + 1).padStart(2, '0')}/${KEYTERM_REGRESSION_SCENARIOS.length}]`;
    const outPath = join(OUT_DIR, `${s.tag}.mp3`);

    if (await fileExists(outPath)) {
      console.log(`${idx} SKIP ${s.tag} (cached)`);
      skipped++;
      continue;
    }

    console.log(`${idx} SYNTH ${s.tag} (${s.dictation.length} chars) → ${s.primary}`);
    const bytes = await synth(apiKey, s.dictation, outPath);
    totalBytes += bytes;
    totalChars += s.dictation.length;
    synthed++;
  }

  console.log();
  console.log('done.');
  console.log(`  scenarios:  ${KEYTERM_REGRESSION_SCENARIOS.length}`);
  console.log(`  synthed:    ${synthed}`);
  console.log(`  cached:     ${skipped}`);
  if (synthed > 0) {
    console.log(`  total mp3:  ${(totalBytes / 1024).toFixed(0)} KB`);
    console.log(`  total text: ${totalChars} chars (~$${((totalChars / 1_000_000) * 15).toFixed(2)} at tts-1 pricing)`);
  }
}

main().catch((err) => {
  console.error('FAIL:', err);
  process.exit(1);
});
