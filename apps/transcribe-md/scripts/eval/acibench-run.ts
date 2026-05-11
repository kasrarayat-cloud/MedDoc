// ============================================================================
// acibench-run.ts — ACI-Bench batch eval against the QuillMD pipeline
// ----------------------------------------------------------------------------
// Validates the production L4 (SOAP generation) layer against the
// ACI-Bench corpus (Yim et al., Nature Sci Data 2023; Microsoft/Nuance).
//
//   github.com/wyim/aci-bench  — 207 US doctor-patient dialogues +
//   reference clinical notes. Free, no DUA. Text only — no audio.
//
// This is the US-text complement to the PriMock57 audio eval. Together
// they answer two distinct questions:
//
//   - PriMock57 (UK + audio): does the full L1 + L4 chain work?
//   - ACI-Bench (US + text):  does L4 alone work on US clinical
//                              dialogue without going through Deepgram?
//
// ─── Design choices ───────────────────────────────────────────────────
//
// Subset scope: **the "aci" subset only**. ACI-Bench ships three
// subsets per split (aci / virtassist / virtscribe). The virtassist
// and virtscribe subsets contain Dragon Copilot trigger phrases
// ("hey dragon", "dax" mentions) that are artifacts of Microsoft's
// in-product capture and not representative of ambient-scribe use
// cases. Verified zero dax/dragon mentions in the aci subset (test1
// split: 22 aci-suffixed encounters out of the 40 total).
//
// Invocation path: **direct Anthropic call**, same prompt as production
// L4 (mirrored from `04-generate-soap.ts:96-150`). No Deepgram (input
// is already text). No L2/L3 (skip the entity-extraction enrichment
// to keep the eval surface comparable to the PriMock57 eval).
//
// Comparison metric: **v2 LLM-as-judge** — Sonnet 4.6 scoring 1-10
// on completeness + accuracy + relevance, with accuracy measured
// against the DIALOGUE as source of truth (the reference clinical
// note is auxiliary signal only — same methodology contract as the
// PriMock57 v2 judge documented at PR #198).
// ============================================================================

import { config as dotenvConfig } from 'dotenv';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

dotenvConfig({ path: path.resolve(process.cwd(), '../../.env') });

import { claudeSonnet46CostCents, claudeOpus47CostCents } from '@meddoc/ai';

// ─── Config ────────────────────────────────────────────────────────────

const DATASET_ROOT = path.resolve(
  process.cwd(),
  '../../.local/datasets/acibench/data',
);
const OUTPUT_DIR = path.resolve(
  process.cwd(),
  '../../docs/eval-runs',
);

const SOAP_MODEL = 'claude-opus-4-7';
const JUDGE_MODEL = 'claude-sonnet-4-6';
const ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages';
const HARD_CEILING_DEFAULT = 10;

const SPLIT_FILES: Record<string, string> = {
  test1: 'challenge_data_json/clinicalnlp_taskB_test1_full.json',
  test2: 'challenge_data_json/clinicalnlp_taskC_test2_full.json',
  test3: 'challenge_data_json/clef_taskC_test3_full.json',
  train: 'challenge_data_json/train_full.json',
  valid: 'challenge_data_json/valid_full.json',
};

// ─── CLI ────────────────────────────────────────────────────────────────

interface CliArgs {
  split: keyof typeof SPLIT_FILES;
  count: number | null; // null = run all aci cases in the split
  seed: number;
  override: boolean;
}

function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = {
    split: 'test1',
    count: null,
    seed: 42,
    override: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--split') {
      const v = argv[++i] ?? '';
      if (!(v in SPLIT_FILES)) {
        throw new Error(
          `--split must be one of ${Object.keys(SPLIT_FILES).join(', ')}; got "${v}"`,
        );
      }
      args.split = v as keyof typeof SPLIT_FILES;
    } else if (k === '--count') args.count = parseInt(argv[++i] ?? '0', 10);
    else if (k === '--seed') args.seed = parseInt(argv[++i] ?? '42', 10);
    else if (k === '--confirm-budget') args.override = true;
  }
  return args;
}

// ─── Dataset discovery ─────────────────────────────────────────────────

interface Case {
  id: string;         // e.g. "D2N106-aci"
  dialogue: string;   // [doctor] / [patient] -labelled lines
  referenceNote: string;
}

function discoverCases(args: CliArgs): Case[] {
  const datasetPath = path.join(DATASET_ROOT, SPLIT_FILES[args.split]);
  if (!existsSync(datasetPath)) {
    throw new Error(
      `Dataset not found at ${datasetPath}. Clone https://github.com/wyim/aci-bench into .local/datasets/acibench first.`,
    );
  }
  const raw = readFileSync(datasetPath, 'utf-8');
  const rows = JSON.parse(raw).data as Array<{
    file: string;
    src: string;
    tgt: string;
  }>;
  // Filter to aci subset only (drop virtassist + virtscribe).
  const aciRows = rows.filter((r) => r.file.endsWith('-aci'));
  // Deterministic ordering by encounter id; --seed reserved for future
  // shuffled-subset runs but not used today.
  void args.seed;
  aciRows.sort((a, b) => a.file.localeCompare(b.file));
  const picked =
    args.count !== null ? aciRows.slice(0, args.count) : aciRows;
  return picked.map((r) => ({
    id: r.file,
    dialogue: r.src,
    referenceNote: r.tgt,
  }));
}

// ─── Anthropic SOAP call ───────────────────────────────────────────────

interface SoapResult {
  soap: string;
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
}

async function callAnthropicSoap(dialogue: string): Promise<SoapResult> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY not set');

  // Mirror of apps/transcribe-md/src/worker/layers/04-generate-soap.ts
  // post-PR-#203 (with the narrow hallucination rules). Eval-specific
  // simplifications: no specialty guidance, no entities, no audio-
  // quality alert, no prompt-injection delimiter wrapping.
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
    "- Don't add diagnostic qualifiers (acute, chronic, undiagnosed,",
    "  severe, mild, sudden, gradual) unless the transcript uses them",
    '  explicitly. "Migraines" stays "migraines" — not "undiagnosed',
    '  migraines." Onset is "sudden" only if the patient said sudden.',
    "- Don't infer maternal/paternal side or a specific relative when",
    "  the transcript only mentions a relative type. \"My grandmother\"",
    '  stays "grandmother" — not "maternal grandmother" unless stated.',
    "- When a dose, frequency, or strength is ambiguous in the",
    "  transcript, write what was actually said and append",
    "  '[clarify with patient]' rather than picking the most likely",
    "  value. Don't silently resolve \"two tablets... one tablet twice",
    '  a day" to a single interpretation.',
    '- Output ONLY the SOAP note markdown. No preamble, no postscript.',
  ].join('\n');

  const user = ['Role-labeled transcript:', '', dialogue].join('\n');

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
      // Opus 4.7 rejects `temperature` server-side; rely on default.
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

// ─── LLM-as-judge ──────────────────────────────────────────────────────
// Same v2 methodology as primock57-run.ts: dialogue is source of truth,
// reference note is auxiliary signal only. Methodology contract
// documented at docs/eval-runs/primock57-20260510T222316Z.md (PR #198).

interface JudgeResult {
  completeness: number;
  accuracy: number;
  relevance: number;
  mean: number;
  rationale: string;
  hallucinations: string[];
  inputTokens: number;
  outputTokens: number;
  latencyMs: number;
}

/** Extract the first balanced `{...}` JSON object from a string that
 *  may contain chain-of-thought prose before/after. */
function extractFirstJsonObject(s: string): string {
  const start = s.indexOf('{');
  if (start === -1) return s;
  let depth = 0;
  let inString = false;
  let escape = false;
  for (let i = start; i < s.length; i++) {
    const ch = s[i];
    if (escape) { escape = false; continue; }
    if (ch === '\\') { escape = true; continue; }
    if (ch === '"') { inString = !inString; continue; }
    if (inString) continue;
    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return s.slice(start, i + 1);
    }
  }
  return s.slice(start);
}

async function callJudgeSoap(
  dialogue: string,
  referenceNote: string,
  generatedSoap: string,
): Promise<JudgeResult> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY not set');

  const system = [
    'You are a clinical-documentation reviewer evaluating an AI-generated',
    'SOAP note against a clinical consultation. You have two reference',
    'artifacts:',
    '',
    '  1. The full role-labeled DIALOGUE of the consultation. This is',
    '     your SOURCE OF TRUTH. Every fact in the generated SOAP must',
    '     be traceable to the dialogue.',
    '  2. The REFERENCE NOTE written by the consulting clinician. This',
    '     is the clinician\'s own summary; it may itself be incomplete',
    '     or imperfect relative to the dialogue. Use it as a hint to',
    '     clinical priorities, NOT as ground truth.',
    '',
    'Score the generated note on three dimensions, 1–10 each:',
    '',
    '  - completeness (vs reference): Does the generated note cover the',
    '    same clinical facts the reference captures (CC, key HPI, PMH,',
    '    Plan)? Missing facts that the reference captured → lower score.',
    '    Generated note containing MORE faithful detail than the',
    '    reference is NOT a penalty — that\'s a completeness win.',
    '',
    '  - accuracy (vs dialogue): Are the facts in the generated note',
    '    supported by the DIALOGUE? **A fact is a hallucination IF AND',
    '    ONLY IF the dialogue does not support it.** A fact that',
    '    appears in the dialogue but NOT in the reference note is NOT',
    '    a hallucination — it is the model being more faithful than the',
    '    clinician\'s summary. Drug doses, frequencies, denials, ADLs,',
    '    counts: trace each to the dialogue before calling it wrong.',
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
    '  "hallucinations": ["specific fact 1 not supported by dialogue", "specific fact 2"],',
    '  "rationale": "short 2-3 sentence summary citing 1-2 specific gaps or strengths, with dialogue-line citations where possible"',
    '}',
    '',
    'The "hallucinations" array MUST be empty when accuracy is 10.',
    'Only list a hallucination if you can confirm the fact is absent',
    'from the dialogue (not just absent from the reference note).',
  ].join('\n');

  const user = [
    '## DIALOGUE (source of truth)',
    dialogue,
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
      max_tokens: 1024,
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
  const fenceStripped = text.replace(/```(?:json)?\s*|\s*```/g, '').trim();
  const jsonObject = extractFirstJsonObject(fenceStripped);
  let parsed: {
    completeness: number;
    accuracy: number;
    relevance: number;
    rationale: string;
    hallucinations?: string[];
  };
  try {
    parsed = JSON.parse(jsonObject);
  } catch (e) {
    throw new Error(
      `Judge JSON parse fail: ${(e as Error).message}; raw: ${text.slice(0, 300)}`,
    );
  }
  const mean = (parsed.completeness + parsed.accuracy + parsed.relevance) / 3;
  return {
    completeness: parsed.completeness,
    accuracy: parsed.accuracy,
    relevance: parsed.relevance,
    mean,
    rationale: parsed.rationale,
    hallucinations: Array.isArray(parsed.hallucinations)
      ? parsed.hallucinations
      : [],
    inputTokens: json.usage?.input_tokens ?? 0,
    outputTokens: json.usage?.output_tokens ?? 0,
    latencyMs,
  };
}

// ─── Per-case eval ──────────────────────────────────────────────────────

interface CaseResult {
  id: string;
  status: 'success' | 'error';
  errorMessage?: string;
  dialogue?: string;
  referenceNote?: string;
  // SOAP
  soapLatencyMs?: number;
  soapInputTokens?: number;
  soapOutputTokens?: number;
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
  try {
    result.dialogue = c.dialogue;
    result.referenceNote = c.referenceNote;

    const soapRes = await callAnthropicSoap(c.dialogue);
    result.soapLatencyMs = soapRes.latencyMs;
    result.soapInputTokens = soapRes.inputTokens;
    result.soapOutputTokens = soapRes.outputTokens;
    result.generatedSoap = soapRes.soap;

    const judge = await callJudgeSoap(
      c.dialogue,
      c.referenceNote,
      soapRes.soap,
    );
    result.judgeMean = judge.mean;
    result.judgeCompleteness = judge.completeness;
    result.judgeAccuracy = judge.accuracy;
    result.judgeRelevance = judge.relevance;
    result.judgeRationale = judge.rationale;
    result.judgeHallucinations = judge.hallucinations;
    result.judgeLatencyMs = judge.latencyMs;
    result.judgeInputTokens = judge.inputTokens;
    result.judgeOutputTokens = judge.outputTokens;

    const soapCents = claudeOpus47CostCents(
      soapRes.inputTokens,
      soapRes.outputTokens,
    );
    const judgeCents = claudeSonnet46CostCents(
      judge.inputTokens,
      judge.outputTokens,
    );
    result.totalCostCents = soapCents + judgeCents;
    result.totalLatencyMs = Date.now() - t0;
    return result;
  } catch (err) {
    result.status = 'error';
    result.errorMessage = err instanceof Error ? err.message : String(err);
    result.totalLatencyMs = Date.now() - t0;
    return result;
  }
}

// ─── Report ─────────────────────────────────────────────────────────────

function dollars(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const idx = Math.max(
    0,
    Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length)),
  );
  return sorted[idx];
}

// PriMock57 locked baseline for the comparison section.
// Numbers come from docs/eval-runs/primock57-20260510T223531Z.md
// (PR #200) and the 5-case follow-up post-narrow-rules (PR #203).
const PRIMOCK57_BASELINE = {
  meanSoapScore: 8.68,
  hallucinationsMeanPerCase: 1.43,
  hallucinationsCasesPct: 53 / 54,
  meanCostUsd: 0.30,
  sampleSize: 54,
  meanLatencySec: 26.6,
  note: 'PR #200 full-57 baseline. Pipeline includes Deepgram L1 + Anthropic Opus 4.7 L4 + Sonnet 4.6 judge.',
};

async function writeReport(
  results: CaseResult[],
  args: CliArgs,
  utcTimestamp: string,
): Promise<string> {
  const successes = results.filter((r) => r.status === 'success');
  const failures = results.filter((r) => r.status === 'error');
  const judges = successes
    .map((r) => r.judgeMean!)
    .filter((v) => Number.isFinite(v))
    .sort((a, b) => a - b);
  const latencies = successes.map((r) => r.totalLatencyMs!).sort((a, b) => a - b);
  const totalCents = successes.reduce(
    (sum, r) => sum + (r.totalCostCents ?? 0),
    0,
  );

  const meanJudge =
    judges.length === 0 ? 0 : judges.reduce((s, w) => s + w, 0) / judges.length;
  const judgeNaNCount = successes.filter(
    (r) => !Number.isFinite(r.judgeMean ?? NaN),
  ).length;
  const totalHallucinations = successes.reduce(
    (sum, r) => sum + (r.judgeHallucinations?.length ?? 0),
    0,
  );
  const casesWithHallucinations = successes.filter(
    (r) => (r.judgeHallucinations?.length ?? 0) > 0,
  ).length;
  const meanHallucinationsPerCase =
    successes.length === 0 ? 0 : totalHallucinations / successes.length;
  const meanCostUsd =
    successes.length === 0
      ? 0
      : totalCents / 100 / successes.length;

  const lines: string[] = [];
  lines.push(`# ACI-Bench batch eval — ${utcTimestamp}`);
  lines.push('');
  lines.push(`**Dataset:** github.com/wyim/aci-bench (Yim et al., Nature Sci Data 2023).`);
  lines.push(`**Split:** ${args.split} — ACI subset only (virtassist + virtscribe excluded; see header comment).`);
  lines.push(`**Cases run:** ${results.length}${args.count !== null ? ` (--count ${args.count} applied)` : ' (full ACI subset of split)'}`);
  lines.push(`**Pipeline path:** Anthropic Opus 4.7 SOAP only — no L1 (input is text), no L2/L3/L5/L6/L7. L4 prompt mirrors \`apps/transcribe-md/src/worker/layers/04-generate-soap.ts\` post-PR-#203 (with the narrow hallucination rules).`);
  lines.push(`**Judge:** Anthropic Sonnet 4.6, v2 methodology (PR #198). Source of truth is the DIALOGUE; reference note is auxiliary.`);
  lines.push('');
  lines.push('## Summary');
  lines.push('');
  lines.push('| Metric | Value |');
  lines.push('|---|---|');
  lines.push(`| Cases attempted | ${results.length} |`);
  lines.push(`| Cases succeeded | ${successes.length} |`);
  lines.push(`| Cases failed | ${failures.length} |`);
  lines.push(`| Mean SOAP score | **${meanJudge.toFixed(2)} / 10** (n=${judges.length}${judgeNaNCount > 0 ? `; ${judgeNaNCount} judge-parse failures excluded` : ''}) |`);
  lines.push(`| Cases with hallucinations | ${casesWithHallucinations} / ${successes.length} |`);
  lines.push(`| Total hallucinations flagged | ${totalHallucinations} |`);
  lines.push(`| Mean hallucinations / case | ${meanHallucinationsPerCase.toFixed(2)} |`);
  lines.push(`| p50 end-to-end latency | ${Math.round(percentile(latencies, 50) / 1000)}s |`);
  lines.push(`| p95 end-to-end latency | ${Math.round(percentile(latencies, 95) / 1000)}s |`);
  lines.push(`| Total cost | ${dollars(totalCents)} |`);
  lines.push(`| Mean cost / case | ${dollars(totalCents / Math.max(1, successes.length))} |`);
  lines.push('');

  // ── Comparison to PriMock57 ───────────────────────────────────────
  lines.push('## Comparison to PriMock57 baseline');
  lines.push('');
  lines.push(`PriMock57 = UK mock primary-care **audio** corpus (full L1 + L4 chain).`);
  lines.push(`ACI-Bench = US **text** dialogue corpus (L4 only).`);
  lines.push(`Cost-per-case diverges by design (no Deepgram on this side).`);
  lines.push('');
  const dScore = meanJudge - PRIMOCK57_BASELINE.meanSoapScore;
  const dHallu = meanHallucinationsPerCase - PRIMOCK57_BASELINE.hallucinationsMeanPerCase;
  const dCost = meanCostUsd - PRIMOCK57_BASELINE.meanCostUsd;
  lines.push('| Metric | PriMock57 (n=54) | ACI-Bench (n=' + successes.length + ') | Δ |');
  lines.push('|---|---|---|---|');
  lines.push(`| Mean SOAP score | ${PRIMOCK57_BASELINE.meanSoapScore.toFixed(2)} | ${meanJudge.toFixed(2)} | ${formatDelta(dScore, 2)} |`);
  lines.push(`| Hallucinations / case | ${PRIMOCK57_BASELINE.hallucinationsMeanPerCase.toFixed(2)} | ${meanHallucinationsPerCase.toFixed(2)} | ${formatDelta(dHallu, 2)} |`);
  lines.push(`| Mean cost / case | $${PRIMOCK57_BASELINE.meanCostUsd.toFixed(2)} | $${meanCostUsd.toFixed(2)} | ${formatDelta(dCost, 2, '$')} |`);
  lines.push('');
  const interpretation = interpretDelta(dScore);
  lines.push(`**Plain reading:** ${interpretation}`);
  lines.push('');
  lines.push(`> n=${successes.length} on ACI-Bench is the full ACI subset of the test1 split. The 22-case sample is enough to surface large deltas but won't catch sub-0.3-point differences with confidence. Treat Δ < 0.3 as "no signal yet."`);
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
  lines.push('| Case | SOAP score | Hallucinations | Latency | Cost |');
  lines.push('|---|---|---|---|---|');
  for (const r of results) {
    if (r.status !== 'success') {
      lines.push(`| ${r.id} | — | — | — | error |`);
      continue;
    }
    const score = Number.isFinite(r.judgeMean ?? NaN)
      ? r.judgeMean!.toFixed(1)
      : 'NaN';
    lines.push(
      `| ${r.id} | ${score} | ${r.judgeHallucinations?.length ?? 0} | ${Math.round(r.totalLatencyMs! / 1000)}s | ${dollars(r.totalCostCents!)} |`,
    );
  }
  lines.push('');

  lines.push('## Spot-check (reference vs generated)');
  lines.push('');
  for (const r of successes.slice(0, Math.min(5, successes.length))) {
    lines.push(`### ${r.id}`);
    lines.push('');
    const score = Number.isFinite(r.judgeMean ?? NaN)
      ? r.judgeMean!.toFixed(1)
      : 'NaN';
    lines.push(`**Judge:** ${score}/10 (completeness ${r.judgeCompleteness}, accuracy ${r.judgeAccuracy}, relevance ${r.judgeRelevance})`);
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

  const filename = `acibench-${args.split}-${utcTimestamp}.md`;
  const outPath = path.join(OUTPUT_DIR, filename);
  await mkdir(OUTPUT_DIR, { recursive: true });
  await writeFile(outPath, lines.join('\n'), 'utf-8');
  return outPath;
}

function formatDelta(d: number, digits: number, prefix = ''): string {
  const sign = d > 0 ? '+' : d < 0 ? '' : '±';
  return `${sign}${prefix}${d.toFixed(digits)}`;
}

function interpretDelta(dScore: number): string {
  if (Math.abs(dScore) < 0.3) {
    return `Δ < 0.3 — sub-threshold; treat as comparable to the PriMock57 baseline. Strong evidence the L4 prompt generalizes US ↔ UK well at the SOAP-quality level.`;
  }
  if (dScore >= 0.3 && dScore < 1.5) {
    return `Δ ${dScore.toFixed(2)} — ACI-Bench scores meaningfully higher than PriMock57. Likely explanation: dialogue input bypasses ASR noise that PriMock57 suffers from (~17% WER); L4 sees clean text and produces tighter SOAPs.`;
  }
  if (dScore <= -0.3 && dScore > -1.5) {
    return `Δ ${dScore.toFixed(2)} — ACI-Bench scores lower than PriMock57. Worth investigating whether US clinical vocabulary, dialogue density, or note-style expectations are pushing L4 off.`;
  }
  if (Math.abs(dScore) >= 1.5) {
    return `Δ ${dScore.toFixed(2)} — LARGE DELTA. ${dScore > 0 ? 'Likely too good to be true' : 'Likely a methodology bug'}; double-check the eval before drawing conclusions.`;
  }
  return `Δ ${dScore.toFixed(2)}`;
}

// ─── Main ───────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const utcTimestamp = new Date()
    .toISOString()
    .replace(/[-:]/g, '')
    .replace(/\.\d+Z$/, 'Z');

  console.log(
    `[acibench] split=${args.split} count=${args.count ?? 'all-aci'} seed=${args.seed} timestamp=${utcTimestamp}`,
  );
  const cases = discoverCases(args);
  console.log(`[acibench] resolved ${cases.length} aci-subset cases`);

  if (cases.length > HARD_CEILING_DEFAULT && !args.override) {
    const low = (cases.length * 0.05).toFixed(0);
    const high = (cases.length * 0.20).toFixed(0);
    console.error(
      `[acibench] refusing to run > ${HARD_CEILING_DEFAULT} cases without --confirm-budget. ` +
        `Estimated cost: ~$${low}–$${high} for ${cases.length} cases.`,
    );
    process.exit(2);
  }

  const results: CaseResult[] = [];
  for (let i = 0; i < cases.length; i++) {
    const c = cases[i];
    process.stdout.write(`[acibench] [${i + 1}/${cases.length}] ${c.id} ... `);
    const r = await evalCase(c);
    if (r.status === 'success') {
      const score = Number.isFinite(r.judgeMean ?? NaN)
        ? r.judgeMean!.toFixed(1)
        : 'NaN';
      console.log(
        `judge=${score} hallu=${r.judgeHallucinations?.length ?? 0} cost=${dollars(r.totalCostCents!)} (${Math.round(r.totalLatencyMs! / 1000)}s)`,
      );
    } else {
      console.log(`ERROR: ${r.errorMessage}`);
    }
    results.push(r);
  }

  const out = await writeReport(results, args, utcTimestamp);
  console.log(`[acibench] report: ${out}`);
}

main().catch((err) => {
  console.error('[acibench] fatal:', err);
  process.exit(1);
});

void readFile; // keep import — unused at the moment, reserved for future
