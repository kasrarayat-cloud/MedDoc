// ============================================================================
// primock57-run.ts — PriMock57 batch eval against the QuillMD pipeline
// ----------------------------------------------------------------------------
// Validates the production transcribe + SOAP pipeline against the
// PriMock57 corpus from Babylon Health (github.com/babylonhealth/primock57).
//
// 57 mock primary-care consultations × 2 speaker audio files +
// per-utterance TextGrid transcripts + reference clinical notes. Free,
// no DUA, simulated patients = zero PHI concerns.
//
// Usage:
//   cd apps/transcribe-md && npm run eval:primock57 -- --count 5
//
// Hard ceiling: --count 10 unless --i-know-what-i-am-doing is passed
// (each case is ~$0.50–1 with Deepgram + Anthropic; 57 cases ≈ $30–60
// — don't accidentally burn it on the first run).
//
// ─── Design choices, recorded for future readers ───────────────────────
//
// Invocation path: **direct AI-client calls** (option A from the brief).
// Reasons:
//   - Production layer wrappers (L1/L3/L4/L5/L6) all read from MinIO +
//     Prisma + emit audit rows + wrap in modelClient telemetry. Running
//     them in-place needs a synthetic visit row + MinIO upload + cleanup
//     per case, which is friction without eval value (PriMock57 evaluates
//     transcript accuracy + SOAP quality — not MinIO round-trip).
//   - Calling Deepgram + Anthropic directly with the production prompts
//     gives identical model behavior + faster iteration on the eval
//     script itself. The L4 system prompt is mirrored inline below
//     (kept in sync with `04-generate-soap.ts:96-150`).
//
// Layer scope: **L1 (transcribe) + L4 (SOAP)** — not the full chain.
// Reasons:
//   - These two are the layers PriMock57's reference data lets us score
//     against (TextGrid utterances + clinical note).
//   - L2 (speaker roles) is replaced by Deepgram's built-in diarization
//     output, which is what L2 ultimately produces anyway.
//   - L3 (entities) feeds L4 in production; running L4 from raw transcript
//     gives a slightly weaker baseline but isolates the SOAP step's
//     transcript→note transformation, which is what's being evaluated.
//   - L5 (critique) + L6 (polish) are quality-amplifiers, not core
//     content generators — skipping keeps the eval to the load-bearing
//     pair and cuts cost ~3×.
//
// Comparison metrics:
//   - **WER (Word Error Rate)** for L1 — standard ASR metric; computed
//     as word-level Levenshtein / reference length, on light-normalized
//     text (lowercase, strip punctuation + filler tokens).
//   - **LLM-as-judge** for L4 — Claude Sonnet 4.6 scoring 1–10 on
//     completeness + clinical accuracy + relevance. Picked over ROUGE
//     because SOAP notes are too structured for ROUGE to be informative
//     (different valid phrasings score low; LLM judge can recognize
//     equivalent clinical content).
//
// Output: `docs/eval-runs/primock57-<UTC>.md` with summary + per-case
// rows. Each row carries reference vs generated for spot-check.
// ============================================================================

import { config as dotenvConfig } from 'dotenv';
import { spawn } from 'node:child_process';
import { readFile, writeFile, mkdir, unlink } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { randomUUID } from 'node:crypto';

// Load .env from the repo root (where `docker-compose.yml` + the
// production .env live). The script is run from apps/transcribe-md/
// but the secrets file is two levels up.
dotenvConfig({ path: path.resolve(process.cwd(), '../../.env') });

import {
  claudeSonnet46CostCents,
  claudeOpus47CostCents,
  deepgramBatchCostCents,
} from '@meddoc/ai';

// ─── Config ────────────────────────────────────────────────────────────

const DATASET_ROOT = path.resolve(
  process.cwd(),
  '../../.local/datasets/primock57',
);
const OUTPUT_DIR = path.resolve(
  process.cwd(),
  '../../docs/eval-runs',
);

const SOAP_MODEL = 'claude-opus-4-7'; // L4 production model
const JUDGE_MODEL = 'claude-sonnet-4-6'; // LLM-as-judge

const DEEPGRAM_URL = 'https://api.deepgram.com/v1/listen';
const ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages';

const HARD_CEILING_DEFAULT = 10;

// ─── CLI ────────────────────────────────────────────────────────────────

interface CliArgs {
  count: number;
  seed: number;
  override: boolean;
}

function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = { count: 5, seed: 42, override: false };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--count') args.count = parseInt(argv[++i] ?? '0', 10);
    else if (k === '--seed') args.seed = parseInt(argv[++i] ?? '42', 10);
    else if (k === '--i-know-what-i-am-doing') args.override = true;
  }
  if (!Number.isFinite(args.count) || args.count < 1) {
    throw new Error('--count must be a positive integer');
  }
  if (args.count > HARD_CEILING_DEFAULT && !args.override) {
    throw new Error(
      `Refusing to run > ${HARD_CEILING_DEFAULT} cases without --i-know-what-i-am-doing. ` +
        `(Estimated cost: ~$${(args.count * 0.75).toFixed(0)}–$${(args.count * 1.5).toFixed(0)} for ${args.count} cases.)`,
    );
  }
  return args;
}

// ─── Dataset discovery ─────────────────────────────────────────────────

interface Case {
  id: string; // "day1_consultation01"
  audioDoctor: string;
  audioPatient: string;
  transcriptDoctor: string;
  transcriptPatient: string;
  noteJsonPath: string;
}

async function discoverCases(seed: number, count: number): Promise<Case[]> {
  const audioDir = path.join(DATASET_ROOT, 'audio');
  if (!existsSync(audioDir)) {
    throw new Error(`Dataset not found at ${DATASET_ROOT}. Clone first.`);
  }
  const { readdirSync } = await import('node:fs');
  const doctorFiles = readdirSync(audioDir).filter((f) =>
    f.endsWith('_doctor.wav'),
  );
  // Deterministic by seed: sort lexicographically, then take first N.
  // Seed currently unused beyond ordering — leave the arg for future
  // shuffled-subset runs.
  void seed;
  doctorFiles.sort();
  const picked = doctorFiles.slice(0, count);
  const cases: Case[] = picked.map((f) => {
    const id = f.replace('_doctor.wav', '');
    return {
      id,
      audioDoctor: path.join(audioDir, f),
      audioPatient: path.join(audioDir, f.replace('_doctor', '_patient')),
      transcriptDoctor: path.join(
        DATASET_ROOT,
        'transcripts',
        f.replace('.wav', '.TextGrid'),
      ),
      transcriptPatient: path.join(
        DATASET_ROOT,
        'transcripts',
        f.replace('_doctor.wav', '_patient.TextGrid'),
      ),
      noteJsonPath: path.join(
        DATASET_ROOT,
        'notes',
        f.replace('_doctor.wav', '.json'),
      ),
    };
  });
  for (const c of cases) {
    if (!existsSync(c.audioPatient)) {
      throw new Error(`Missing patient file: ${c.audioPatient}`);
    }
    if (!existsSync(c.noteJsonPath)) {
      throw new Error(`Missing note: ${c.noteJsonPath}`);
    }
  }
  return cases;
}

// ─── Audio mixing ──────────────────────────────────────────────────────

async function mixAudio(doctorPath: string, patientPath: string): Promise<string> {
  const out = path.join(tmpdir(), `primock-mix-${randomUUID()}.wav`);
  await new Promise<void>((resolve, reject) => {
    const proc = spawn(
      'ffmpeg',
      [
        '-y',
        '-i', doctorPath,
        '-i', patientPath,
        '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=longest:normalize=0',
        '-ac', '1',
        out,
      ],
      { stdio: ['ignore', 'pipe', 'pipe'] },
    );
    let stderr = '';
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg exited ${code}: ${stderr.slice(-500)}`));
    });
    proc.on('error', reject);
  });
  return out;
}

// ─── TextGrid parser ───────────────────────────────────────────────────

interface Utterance {
  start: number;
  end: number;
  speaker: 'Doctor' | 'Patient';
  text: string;
}

async function parseTextGrid(filePath: string, speaker: 'Doctor' | 'Patient'): Promise<Utterance[]> {
  const raw = await readFile(filePath, 'utf-8');
  const intervalRe =
    /intervals \[\d+\]:\s+xmin = ([\d.]+)\s+xmax = ([\d.]+)\s+text = "([^"]*)"/g;
  const out: Utterance[] = [];
  let m: RegExpExecArray | null;
  while ((m = intervalRe.exec(raw)) !== null) {
    const start = parseFloat(m[1]);
    const end = parseFloat(m[2]);
    const text = m[3].trim();
    if (text.length === 0) continue;
    out.push({ start, end, speaker, text });
  }
  return out;
}

function buildCombinedTranscript(doctor: Utterance[], patient: Utterance[]): string {
  const merged = [...doctor, ...patient].sort((a, b) => a.start - b.start);
  return merged
    .map((u) => `${u.speaker}: ${stripTextGridTags(u.text)}`)
    .join('\n');
}

function stripTextGridTags(text: string): string {
  // Remove <UNSURE>...</UNSURE> wrapping (keep contents)
  let t = text.replace(/<UNSURE>(.*?)<\/UNSURE>/g, '$1');
  // Remove <UNIN/> (uninterpretable speech marker)
  t = t.replace(/<UNIN\/>/g, '');
  // Collapse multi-space
  t = t.replace(/\s+/g, ' ').trim();
  return t;
}

// ─── Deepgram call ─────────────────────────────────────────────────────

interface DeepgramResult {
  transcript: string;
  durationSec: number;
  utterances: Array<{ start: number; end: number; speaker: number; text: string }>;
  latencyMs: number;
}

async function callDeepgram(audioPath: string): Promise<DeepgramResult> {
  const audio = await readFile(audioPath);
  const apiKey = process.env.DEEPGRAM_API_KEY;
  if (!apiKey) throw new Error('DEEPGRAM_API_KEY not set');
  const url = `${DEEPGRAM_URL}?model=nova-3-medical&diarize=true&utterances=true&punctuate=true&smart_format=true&language=en`;
  const t0 = Date.now();
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Token ${apiKey}`,
      'Content-Type': 'audio/wav',
      'Content-Length': String(audio.length),
    },
    body: new Uint8Array(audio),
  });
  const latencyMs = Date.now() - t0;
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Deepgram ${res.status}: ${body.slice(0, 500)}`);
  }
  const json = (await res.json()) as DeepgramAPIResponse;
  const channel0 = json.results?.channels?.[0];
  const alt = channel0?.alternatives?.[0];
  if (!alt) throw new Error('Deepgram: missing alternatives');
  const transcript = alt.transcript ?? '';
  const utterances =
    (json.results?.utterances ?? []).map((u) => ({
      start: u.start,
      end: u.end,
      speaker: typeof u.speaker === 'number' ? u.speaker : 0,
      text: u.transcript,
    })) ?? [];
  const durationSec = json.metadata?.duration ?? 0;
  return { transcript, durationSec, utterances, latencyMs };
}

interface DeepgramAPIResponse {
  metadata?: { duration?: number };
  results?: {
    channels?: Array<{ alternatives?: Array<{ transcript?: string }> }>;
    utterances?: Array<{ start: number; end: number; speaker?: number; transcript: string }>;
  };
}

// ─── Build role-labeled transcript from Deepgram diarization ───────────

function buildRoleLabeledTranscript(
  utterances: DeepgramResult['utterances'],
): string {
  // First-pass heuristic: in PriMock57, the doctor leads questioning
  // (first speaker to talk substantively). Deepgram assigns speaker
  // numbers but doesn't know who's doctor vs patient. We pick the
  // speaker who utters the most words as the doctor (rough but
  // consistent for these consultations).
  const wordCount = new Map<number, number>();
  for (const u of utterances) {
    wordCount.set(
      u.speaker,
      (wordCount.get(u.speaker) ?? 0) + u.text.split(/\s+/).length,
    );
  }
  const sortedSpeakers = [...wordCount.entries()].sort((a, b) => b[1] - a[1]);
  const doctorId = sortedSpeakers[0]?.[0] ?? 0;

  return utterances
    .map((u) => {
      const role = u.speaker === doctorId ? 'Doctor' : 'Patient';
      return `${role}: ${u.text.trim()}`;
    })
    .join('\n');
}

// ─── Anthropic call (SOAP generation) ──────────────────────────────────

interface SoapResult {
  soap: string;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
}

async function callAnthropicSoap(roleLabeledTranscript: string): Promise<SoapResult> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY not set');

  // Mirrors `apps/transcribe-md/src/worker/layers/04-generate-soap.ts:96-150`.
  // Eval-specific simplifications: no specialty guidance, no entities
  // input, no audio-quality alert, no prompt-injection delimiter wrapping
  // (which is a safety feature, not a quality feature — its absence
  // doesn't change SOAP quality on the PriMock57 corpus).
  const system = [
    'You are a senior clinician writing a SOAP note from a clinical',
    'visit. Use ONLY the role-labeled transcript as evidence. Write in',
    'a professional medical tone.',
    '',
    'Structure the note with these markdown headings exactly:',
    '',
    '## Subjective',
    '**Chief Complaint:** …',
    '**HPI:** narrative paragraph incorporating onset, duration,',
    '  quality, severity, location, timing, context, modifying factors,',
    '  associated symptoms.',
    '**PMH:** bullet list or "[not documented]" if silent.',
    '**Medications:** bullet list with dose/route/frequency where stated.',
    '**Allergies:** bullet list with reactions where stated.',
    '**Family History:** brief list or "[not documented]".',
    '**Social History:** smoking / alcohol / drugs / occupation if',
    '  mentioned; omit unmentioned lines.',
    '**ROS:** by system when documented; else the single line',
    '  "ROS not formally documented in this encounter."',
    '',
    '## Objective',
    'Physical exam findings grouped by system. Include vitals if',
    'mentioned. Include test results mentioned. If no formal exam was',
    'discussed, write exactly: "Formal exam not documented in this',
    'encounter."',
    '',
    '## Assessment',
    'Primary clinical consideration with supporting reasoning.',
    'Differentials if the doctor discussed them. Severity/staging if',
    'applicable. Use [not documented] rather than inventing.',
    '',
    '## Plan',
    'Numbered list: diagnostics ordered, medications changed/started,',
    'follow-up, referrals, patient education. Each item should be',
    'actionable.',
    '',
    'Critical rules:',
    '- Do NOT invent clinical findings. If a claim lacks transcript',
    '  evidence, either omit it or explicitly mark it "[not documented]".',
    '- When information came exclusively from the patient, prefix with',
    '  "Per patient, …" so the source is clear on downstream review.',
    '- Never add test results, medication doses, or vital-sign numbers',
    '  that were not stated.',
    '- Output ONLY the SOAP note markdown. No preamble, no postscript.',
  ].join('\n');

  const user = [
    'Role-labeled transcript:',
    '',
    roleLabeledTranscript,
  ].join('\n');

  const t0 = Date.now();
  const res = await fetch(ANTHROPIC_URL, {
    method: 'POST',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model: SOAP_MODEL,
      max_tokens: 4096,
      // Opus 4.7 rejects `temperature` (deprecated server-side); rely
      // on default. Sonnet path still accepts it.
      system,
      messages: [{ role: 'user', content: user }],
    }),
  });
  const latencyMs = Date.now() - t0;
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Anthropic ${res.status}: ${body.slice(0, 500)}`);
  }
  const json = (await res.json()) as AnthropicResponse;
  const text = (json.content ?? []).find((b) => b.type === 'text')?.text ?? '';
  return {
    soap: text,
    inputTokens: json.usage?.input_tokens ?? 0,
    outputTokens: json.usage?.output_tokens ?? 0,
    latencyMs,
  };
}

interface AnthropicResponse {
  content?: Array<{ type: string; text?: string }>;
  usage?: { input_tokens?: number; output_tokens?: number };
}

// ─── LLM-as-judge for SOAP scoring ─────────────────────────────────────

interface JudgeResult {
  completeness: number; // 1-10
  accuracy: number;     // 1-10
  relevance: number;    // 1-10
  mean: number;
  rationale: string;
  hallucinations: string[];
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
}

async function callJudgeSoap(
  referenceTranscript: string,
  referenceNote: string,
  generatedSoap: string,
): Promise<JudgeResult> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY not set');

  // ── Methodology note (post-2026-05-10 correction) ──────────────────
  // The first iteration of this judge scored against the reference
  // note only. Inspection of PR #197's flagged "hallucinations"
  // (e.g. case-01 "paracetamol 2 tablets QID", "did not measure
  // temperature", "continued to attend work") revealed they were ALL
  // present verbatim in the source transcript — they were absent only
  // from the clinician's *summarized* reference note. The judge was
  // penalizing the model for being MORE FAITHFUL to the transcript
  // than the clinician's own abbreviated summary.
  //
  // Corrected methodology: the **TRANSCRIPT is the source of truth**.
  // The reference note is auxiliary signal showing what the
  // clinician thought was clinically important to capture. A
  // generated SOAP detail is a hallucination IF AND ONLY IF the
  // transcript does not support it. Generated details that appear in
  // transcript but not in reference are NOT hallucinations — they
  // are completeness wins.
  const system = [
    'You are a clinical-documentation reviewer evaluating an AI-generated',
    'SOAP note against a clinical consultation. You have two reference',
    'artifacts:',
    '',
    '  1. The full role-labeled TRANSCRIPT of the consultation. This is',
    '     your SOURCE OF TRUTH. Every fact in the generated SOAP must be',
    '     traceable to the transcript.',
    '  2. The REFERENCE NOTE written by the consulting clinician. This',
    '     is the clinician\'s own abbreviated summary; it may itself be',
    '     incomplete or imperfect relative to the transcript. Use it as',
    '     a hint to what the clinician thought was important, NOT as',
    '     ground truth.',
    '',
    'Score the generated note on three dimensions, 1–10 each:',
    '',
    '  - completeness (vs reference): Does the generated note cover the',
    '    same clinical facts the reference captures (CC, key HPI, PMH,',
    '    Plan)? Missing facts that the reference captured → lower score.',
    '    Generated note containing MORE faithful detail than the',
    '    reference is NOT a penalty — that\'s a completeness win.',
    '',
    '  - accuracy (vs transcript): Are the facts in the generated note',
    '    supported by the TRANSCRIPT? **A fact is a hallucination IF',
    '    AND ONLY IF the transcript does not support it.** A fact that',
    '    appears in the transcript but NOT in the reference note is NOT',
    '    a hallucination — it is the model being more faithful than the',
    '    clinician\'s summary. Drug doses, frequencies, denials, ADLs,',
    '    counts: trace each to the transcript before calling it wrong.',
    '',
    '  - relevance: Does the generated note prioritize the clinically',
    '    important content (chief complaint, red flags, plan) over',
    '    boilerplate? Filler-heavy → lower score.',
    '',
    'Respond with VALID JSON ONLY, no markdown fences, this exact shape:',
    '',
    '{',
    '  "completeness": 8,',
    '  "accuracy": 9,',
    '  "relevance": 7,',
    '  "hallucinations": ["specific fact 1 not supported by transcript", "specific fact 2"],',
    '  "rationale": "short 2-3 sentence summary citing 1-2 specific gaps or strengths, with transcript-line citations where possible"',
    '}',
    '',
    'The "hallucinations" array MUST be empty when accuracy is 10.',
    'Only list a hallucination if you can confirm the fact is absent',
    'from the transcript (not just absent from the reference note).',
  ].join('\n');

  const user = [
    '## TRANSCRIPT (source of truth)',
    referenceTranscript,
    '',
    '## REFERENCE NOTE (clinician summary — auxiliary signal only)',
    referenceNote,
    '',
    '## GENERATED SOAP NOTE (to evaluate)',
    generatedSoap,
  ].join('\n');

  const t0 = Date.now();
  const res = await fetch(ANTHROPIC_URL, {
    method: 'POST',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model: JUDGE_MODEL,
      max_tokens: 512,
      temperature: 0,
      system,
      messages: [{ role: 'user', content: user }],
    }),
  });
  const latencyMs = Date.now() - t0;
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Judge ${res.status}: ${body.slice(0, 500)}`);
  }
  const json = (await res.json()) as AnthropicResponse;
  const text = (json.content ?? []).find((b) => b.type === 'text')?.text ?? '';
  // Strip possible fences just in case
  const stripped = text.replace(/```(?:json)?\s*|\s*```/g, '').trim();
  let parsed: {
    completeness: number;
    accuracy: number;
    relevance: number;
    rationale: string;
    hallucinations?: string[];
  };
  try {
    parsed = JSON.parse(stripped);
  } catch (e) {
    throw new Error(`Judge JSON parse fail: ${(e as Error).message}; raw: ${text.slice(0, 300)}`);
  }
  const mean = (parsed.completeness + parsed.accuracy + parsed.relevance) / 3;
  return {
    completeness: parsed.completeness,
    accuracy: parsed.accuracy,
    relevance: parsed.relevance,
    mean,
    rationale: parsed.rationale,
    hallucinations: Array.isArray(parsed.hallucinations) ? parsed.hallucinations : [],
    inputTokens: json.usage?.input_tokens ?? 0,
    outputTokens: json.usage?.output_tokens ?? 0,
    latencyMs,
  };
}

// ─── WER ────────────────────────────────────────────────────────────────
//
// Two normalizations are emitted side-by-side so future readers can
// compare against either internal trends or the published PriMock57
// paper's baselines (Moramarco et al., ACL 2022).
//
//   - normalizeForWer (our internal): light normalization — lowercase,
//     strip ASCII punctuation, collapse whitespace. KEEPS numbers,
//     hyphenated words, and apostrophes. Stricter than PriMock57's
//     alphabetic-only filter; reports a slightly HIGHER WER on
//     average because token mismatches like "3" vs "three" and
//     "follow-up" vs "follow up" count as errors.
//
//   - normalizeForWerPrimock57Aligned: matches the published
//     paper's preprocessing exactly — alphabetic-only with apostrophe
//     preserved, hyphen → space. Lower WER on average; the metric to
//     cite when comparing against the paper's tables.
//
// PriMock57's reference: `.local/datasets/primock57/scripts/utils.py`
// `preprocess_text()` (committed by the dataset authors).

/** Our internal normalization — preserves more tokens to surface
 *  cosmetic ASR drift (digits, hyphens). Stricter than PriMock57-
 *  aligned and produces a slightly higher WER on the same audio. */
function normalizeForWer(s: string): string[] {
  return s
    .toLowerCase()
    .replace(/[.,!?;:"()[\]{}<>]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .split(' ')
    .filter((w) => w.length > 0);
}

/** Matches `preprocess_text` in PriMock57's `scripts/utils.py`:
 *  lowercase → hyphen-to-space → strip non-`[a-z \']` → collapse
 *  whitespace. Use this when comparing WER against the paper's
 *  published baselines (Moramarco et al., 2022). */
function normalizeForWerPrimock57Aligned(s: string): string[] {
  return s
    .toLowerCase()
    .replace(/-/g, ' ')
    .replace(/[^a-z \']+/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .split(' ')
    .filter((w) => w.length > 0);
}

/** Word-level Levenshtein over already-tokenised arrays. Identical
 *  algorithm to NIST's sclite (insertion/deletion/substitution all
 *  cost 1; final WER = edits / reference word count). */
function werFromTokens(ref: string[], hyp: string[]): { wer: number; refWords: number } {
  if (ref.length === 0) return { wer: 0, refWords: 0 };
  const m = ref.length;
  const n = hyp.length;
  let prev = new Uint32Array(n + 1);
  let curr = new Uint32Array(n + 1);
  for (let j = 0; j <= n; j++) prev[j] = j;
  for (let i = 1; i <= m; i++) {
    curr[0] = i;
    for (let j = 1; j <= n; j++) {
      const cost = ref[i - 1] === hyp[j - 1] ? 0 : 1;
      curr[j] = Math.min(
        prev[j] + 1,
        curr[j - 1] + 1,
        prev[j - 1] + cost,
      );
    }
    [prev, curr] = [curr, prev];
  }
  return { wer: prev[n] / ref.length, refWords: ref.length };
}

function computeWer(reference: string, hypothesis: string): {
  wer: number;
  werPaper: number;
  refWords: number;
  refWordsPaper: number;
} {
  const internal = werFromTokens(
    normalizeForWer(reference),
    normalizeForWer(hypothesis),
  );
  const paper = werFromTokens(
    normalizeForWerPrimock57Aligned(reference),
    normalizeForWerPrimock57Aligned(hypothesis),
  );
  return {
    wer: internal.wer,
    werPaper: paper.wer,
    refWords: internal.refWords,
    refWordsPaper: paper.refWords,
  };
}

// ─── Per-case eval ──────────────────────────────────────────────────────

interface CaseResult {
  id: string;
  status: 'success' | 'error';
  errorMessage?: string;
  audioDurationSec?: number;
  // L1
  l1LatencyMs?: number;
  l1Transcript?: string;
  // Reference
  referenceTranscript?: string;
  referenceNote?: string;
  // WER — internal (preserves digits/hyphens, slightly stricter)
  wer?: number;
  refWords?: number;
  // WER — aligned with PriMock57 paper's preprocess_text (alpha-only)
  werPaper?: number;
  refWordsPaper?: number;
  // L4
  l4LatencyMs?: number;
  l4InputTokens?: number;
  l4OutputTokens?: number;
  generatedSoap?: string;
  // Judge
  judgeMean?: number;
  judgeCompleteness?: number;
  judgeAccuracy?: number;
  judgeRelevance?: number;
  judgeRationale?: string;
  judgeHallucinations?: string[];
  judgeLatencyMs?: number;
  judgeInputTokens?: number;
  judgeOutputTokens?: number;
  // Aggregate
  totalLatencyMs?: number;
  totalCostCents?: number;
}

async function evalCase(c: Case): Promise<CaseResult> {
  const result: CaseResult = { id: c.id, status: 'success' };
  const t0 = Date.now();
  let mixedPath: string | null = null;
  try {
    // 1. Mix audio
    mixedPath = await mixAudio(c.audioDoctor, c.audioPatient);

    // 2. Deepgram
    const dg = await callDeepgram(mixedPath);
    result.audioDurationSec = dg.durationSec;
    result.l1LatencyMs = dg.latencyMs;
    result.l1Transcript = dg.transcript;
    const roleLabeled = buildRoleLabeledTranscript(dg.utterances);

    // 3. Reference transcript from TextGrid
    const [tgDoctor, tgPatient] = await Promise.all([
      parseTextGrid(c.transcriptDoctor, 'Doctor'),
      parseTextGrid(c.transcriptPatient, 'Patient'),
    ]);
    const refTranscript = buildCombinedTranscript(tgDoctor, tgPatient);
    result.referenceTranscript = refTranscript;

    // 4. WER (compare plain transcript text, role labels stripped)
    const refTextOnly = refTranscript.replace(/^(Doctor|Patient): /gm, '');
    const werResult = computeWer(refTextOnly, dg.transcript);
    result.wer = werResult.wer;
    result.refWords = werResult.refWords;
    result.werPaper = werResult.werPaper;
    result.refWordsPaper = werResult.refWordsPaper;

    // 5. Reference note
    const noteRaw = await readFile(c.noteJsonPath, 'utf-8');
    const noteJson = JSON.parse(noteRaw) as { note: string };
    result.referenceNote = noteJson.note;

    // 6. SOAP generation
    const soapRes = await callAnthropicSoap(roleLabeled);
    result.l4LatencyMs = soapRes.latencyMs;
    result.l4InputTokens = soapRes.inputTokens;
    result.l4OutputTokens = soapRes.outputTokens;
    result.generatedSoap = soapRes.soap;

    // 7. Judge — now scores against the transcript (source of truth)
    //    with the reference note as auxiliary signal. See callJudgeSoap.
    const judge = await callJudgeSoap(refTranscript, noteJson.note, soapRes.soap);
    result.judgeMean = judge.mean;
    result.judgeCompleteness = judge.completeness;
    result.judgeAccuracy = judge.accuracy;
    result.judgeRelevance = judge.relevance;
    result.judgeRationale = judge.rationale;
    result.judgeHallucinations = judge.hallucinations;
    result.judgeLatencyMs = judge.latencyMs;
    result.judgeInputTokens = judge.inputTokens;
    result.judgeOutputTokens = judge.outputTokens;

    // 8. Costs
    const dgCents = deepgramBatchCostCents(dg.durationSec);
    const soapCents = claudeOpus47CostCents(soapRes.inputTokens, soapRes.outputTokens);
    const judgeCents = claudeSonnet46CostCents(judge.inputTokens, judge.outputTokens);
    result.totalCostCents = dgCents + soapCents + judgeCents;
    result.totalLatencyMs = Date.now() - t0;

    return result;
  } catch (err) {
    result.status = 'error';
    result.errorMessage = err instanceof Error ? err.message : String(err);
    result.totalLatencyMs = Date.now() - t0;
    return result;
  } finally {
    if (mixedPath) {
      try { await unlink(mixedPath); } catch { /* ignore */ }
    }
  }
}

// ─── Report writer ──────────────────────────────────────────────────────

function pct(n: number, digits = 1): string {
  return `${(n * 100).toFixed(digits)}%`;
}

function dollars(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const idx = Math.max(0, Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length)));
  return sorted[idx];
}

async function writeReport(
  results: CaseResult[],
  args: CliArgs,
  utcTimestamp: string,
): Promise<string> {
  const successes = results.filter((r) => r.status === 'success');
  const failures = results.filter((r) => r.status === 'error');
  const wers = successes.map((r) => r.wer!).sort((a, b) => a - b);
  const judges = successes.map((r) => r.judgeMean!).sort((a, b) => a - b);
  const latencies = successes.map((r) => r.totalLatencyMs!).sort((a, b) => a - b);
  const totalCents = successes.reduce((sum, r) => sum + (r.totalCostCents ?? 0), 0);

  const meanWer =
    wers.length === 0 ? 0 : wers.reduce((s, w) => s + w, 0) / wers.length;
  const meanJudge =
    judges.length === 0 ? 0 : judges.reduce((s, w) => s + w, 0) / judges.length;
  const totalAudioSec = successes.reduce(
    (s, r) => s + (r.audioDurationSec ?? 0),
    0,
  );

  const lines: string[] = [];
  lines.push(`# PriMock57 batch eval — ${utcTimestamp}`);
  lines.push('');
  lines.push(`**Dataset:** github.com/babylonhealth/primock57 — 57 mock consultations.`);
  lines.push(`**Cases run:** ${args.count} (seed: ${args.seed})`);
  lines.push(`**Pipeline path:** direct Deepgram (nova-3-medical) + Anthropic Opus 4.7 (SOAP). L4 prompt mirrors \`apps/transcribe-md/src/worker/layers/04-generate-soap.ts:96-150\`.`);
  lines.push(`**Judge:** Anthropic Sonnet 4.6, 1–10 scoring on completeness + accuracy + relevance. **Methodology v2 (post-2026-05-10 correction):** scores accuracy against the TRANSCRIPT (source of truth), not the reference note. Reference is auxiliary signal only.`);
  lines.push('');

  const totalHallucinations = successes.reduce(
    (sum, r) => sum + (r.judgeHallucinations?.length ?? 0),
    0,
  );
  const casesWithHallucinations = successes.filter(
    (r) => (r.judgeHallucinations?.length ?? 0) > 0,
  ).length;

  lines.push('## Summary');
  lines.push('');
  lines.push('| Metric | Value |');
  lines.push('|---|---|');
  lines.push(`| Cases attempted | ${results.length} |`);
  lines.push(`| Cases succeeded | ${successes.length} |`);
  lines.push(`| Cases failed | ${failures.length} |`);
  lines.push(`| Total audio | ${(totalAudioSec / 60).toFixed(1)} min |`);
  lines.push(`| Mean WER (internal — preserves digits/hyphens) | ${pct(meanWer)} (n=${wers.length}) |`);

  const persPaper = successes.map((r) => r.werPaper!).filter((v) => v != null).sort((a, b) => a - b);
  const meanWerPaper =
    persPaper.length === 0 ? 0 : persPaper.reduce((s, w) => s + w, 0) / persPaper.length;
  lines.push(`| Mean WER (PriMock57-aligned — alpha-only + hyphen→space) | ${pct(meanWerPaper)} (n=${persPaper.length}) |`);
  lines.push(`| Mean SOAP score | ${meanJudge.toFixed(2)} / 10 (n=${judges.length}) |`);
  lines.push(`| Cases with hallucinations | ${casesWithHallucinations} / ${successes.length} |`);
  lines.push(`| Total hallucinations flagged | ${totalHallucinations} |`);
  lines.push(`| p50 end-to-end latency | ${Math.round(percentile(latencies, 50) / 1000)}s |`);
  lines.push(`| p95 end-to-end latency | ${Math.round(percentile(latencies, 95) / 1000)}s |`);
  lines.push(`| Total cost | ${dollars(totalCents)} |`);
  lines.push(`| Mean cost / case | ${dollars(totalCents / Math.max(1, successes.length))} |`);
  lines.push('');

  if (failures.length > 0) {
    lines.push('## ⚠ Failures');
    lines.push('');
    for (const f of failures) {
      lines.push(`### ${f.id}`);
      lines.push('');
      lines.push('```');
      lines.push(f.errorMessage ?? '(no message)');
      lines.push('```');
      lines.push('');
    }
  }

  lines.push('## Per-case results');
  lines.push('');
  lines.push('| Case | WER | SOAP score | Latency | Cost |');
  lines.push('|---|---|---|---|---|');
  for (const r of results) {
    if (r.status !== 'success') {
      lines.push(`| ${r.id} | — | — | — | error |`);
      continue;
    }
    lines.push(
      `| ${r.id} | ${pct(r.wer!)} | ${r.judgeMean!.toFixed(1)} | ${Math.round(r.totalLatencyMs! / 1000)}s | ${dollars(r.totalCostCents!)} |`,
    );
  }
  lines.push('');

  lines.push('## Spot-check (reference vs generated)');
  lines.push('');
  for (const r of successes.slice(0, Math.min(5, successes.length))) {
    lines.push(`### ${r.id}`);
    lines.push('');
    lines.push(`**WER:** ${pct(r.wer!)} · **Judge:** ${r.judgeMean!.toFixed(1)}/10 (completeness ${r.judgeCompleteness}, accuracy ${r.judgeAccuracy}, relevance ${r.judgeRelevance})`);
    lines.push('');
    lines.push(`**Judge rationale:** ${r.judgeRationale}`);
    if ((r.judgeHallucinations?.length ?? 0) > 0) {
      lines.push('');
      lines.push(`**Hallucinations flagged (${r.judgeHallucinations!.length}):**`);
      for (const h of r.judgeHallucinations!) lines.push(`- ${h}`);
    }
    lines.push('');
    lines.push('<details><summary>Reference note</summary>');
    lines.push('');
    lines.push('```');
    lines.push(r.referenceNote ?? '');
    lines.push('```');
    lines.push('');
    lines.push('</details>');
    lines.push('');
    lines.push('<details><summary>Generated SOAP</summary>');
    lines.push('');
    lines.push(r.generatedSoap ?? '');
    lines.push('');
    lines.push('</details>');
    lines.push('');
  }

  const filename = `primock57-${utcTimestamp}.md`;
  const outPath = path.join(OUTPUT_DIR, filename);
  await mkdir(OUTPUT_DIR, { recursive: true });
  await writeFile(outPath, lines.join('\n'), 'utf-8');
  return outPath;
}

// ─── Main ───────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const utcTimestamp = new Date()
    .toISOString()
    .replace(/[-:]/g, '')
    .replace(/\.\d+Z$/, 'Z');

  console.log(`[primock57] count=${args.count} seed=${args.seed} timestamp=${utcTimestamp}`);
  const cases = await discoverCases(args.seed, args.count);
  console.log(`[primock57] resolved ${cases.length} cases:`);
  for (const c of cases) console.log(`  - ${c.id}`);

  const results: CaseResult[] = [];
  for (let i = 0; i < cases.length; i++) {
    const c = cases[i];
    process.stdout.write(`[primock57] [${i + 1}/${cases.length}] ${c.id} ... `);
    const r = await evalCase(c);
    if (r.status === 'success') {
      console.log(
        `wer=${pct(r.wer!)} judge=${r.judgeMean!.toFixed(1)} cost=${dollars(r.totalCostCents!)} (${Math.round(r.totalLatencyMs! / 1000)}s)`,
      );
    } else {
      console.log(`ERROR: ${r.errorMessage}`);
    }
    results.push(r);
  }

  const out = await writeReport(results, args, utcTimestamp);
  console.log(`[primock57] report: ${out}`);
}

main().catch((err) => {
  console.error('[primock57] fatal:', err);
  process.exit(1);
});
