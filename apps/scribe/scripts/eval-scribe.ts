// ============================================================================
// Eval runner — Scribe SOAP pipeline
// ----------------------------------------------------------------------------
// For each golden transcript in tests/evals/scribe-transcripts.ts:
//   1. Build the same system prompt the real pipeline uses
//   2. Call Claude Sonnet 4.6 directly via @meddoc/ai
//   3. Score pass/fail:
//        - Zod schema passes
//        - Every assessment.evidence_quote is a substring of the transcript
//          (hallucination detector per M2 plan §D9)
//        - At least one expected ICD-10 candidate appears
//        - Subjective / plan keys the case listed are populated
//
// Skips Whisper + Pass-1 cleanup — transcripts are pre-diarized so we
// score SOAP generation quality in isolation.
//
// Usage: `npm run eval:scribe`
// Cost:  ~$0.05 at 3 cases via Claude Sonnet 4.6. Needs ANTHROPIC_API_KEY.
// ============================================================================

import 'dotenv/config';
import fs from 'node:fs/promises';
import path from 'node:path';
import { z } from 'zod';
import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';
import { SoapNoteSchema, type SoapNote } from '@meddoc/types';
import { SCRIBE_EVAL_CASES, type ScribeEvalCase } from '../tests/evals/scribe-transcripts';

const THRESHOLD = 0.8;
/** Minimum mean judge score per case when --judge is active. */
const JUDGE_THRESHOLD = 3.5;

/**
 * Normalise whitespace + strip speaker-turn prefixes before substring
 * matching. Both Whisper-style "UNKNOWN:" and Deepgram "speaker_N:"
 * labels get removed, along with the CLINICIAN/PATIENT/OTHER tokens.
 * This lets a valid evidence quote that happens to span two turn
 * boundaries match against the transcript body text. Added M5 after a
 * multi-turn quote legitimately landed in an assessment item.
 */
function normalizeForHallucination(text: string): string {
  return text
    .replace(/\s+/g, ' ')
    .replace(/\b(clinician|patient|other|unknown|speaker_\d+):\s*/gi, ' ')
    .replace(/\s+/g, ' ')
    .toLowerCase()
    .trim();
}

const CLI_ARGS = new Set(process.argv.slice(2));
const JUDGE_ENABLED = CLI_ARGS.has('--judge');

// ---------------------------------------------------------------------------
// LLM-as-judge (M4 D7 — opt-in via --judge)
// ---------------------------------------------------------------------------

const JudgeScoreSchema = z.object({
  score: z.number().min(1).max(5),
  criteria: z.object({
    hallucination: z.number().min(1).max(5),
    completeness: z.number().min(1).max(5),
    clarity: z.number().min(1).max(5),
    specialty_appropriateness: z.number().min(1).max(5),
  }),
  notes: z.string(),
});
type JudgeScore = z.infer<typeof JudgeScoreSchema>;

async function loadJudgePrompt(): Promise<string> {
  return fs.readFile(
    path.resolve(__dirname, '..', 'src', 'server', 'prompts', 'llm-judge.md'),
    'utf8'
  );
}

async function judgeSoap(args: {
  transcript: string;
  soap: SoapNote;
  basePrompt: string;
}): Promise<JudgeScore> {
  const judgeModel = process.env.MODEL_FOR_JUDGE?.trim() || 'claude-sonnet-4-6';
  return modelClient.complete({
    provider: 'anthropic',
    model: judgeModel,
    system: args.basePrompt,
    user:
      `OUTPUT_TYPE: SOAP\n\nTRANSCRIPT:\n${args.transcript}\n\n` +
      `OUTPUT:\n${JSON.stringify(args.soap, null, 2)}`,
    schema: JudgeScoreSchema,
    purpose: 'judge',
    practiceId: 'clinic_main',
    maxTokens: 1024,
  });
}

const c = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
};

async function loadSoapPrompt(): Promise<string> {
  return fs.readFile(
    path.resolve(__dirname, '..', 'src', 'server', 'prompts', 'generate-soap.md'),
    'utf8'
  );
}

interface Score {
  schemaOk: boolean;
  hallucinationOk: boolean;
  icd10Ok: boolean;
  subjectiveOk: boolean;
  planOk: boolean;
  reasons: string[];
  soap?: SoapNote;
}

function scoreCase(
  evalCase: ScribeEvalCase,
  transcriptRaw: string,
  soap: SoapNote
): Score {
  const reasons: string[] = [];

  // Hallucination detector: every evidence_quote must appear verbatim in
  // the transcript. Normalize whitespace + strip speaker labels so a
  // legitimate quote across a turn boundary isn't falsely flagged.
  const normalized = normalizeForHallucination(transcriptRaw);
  const hallucinations = soap.assessment.filter((a) => {
    const quote = normalizeForHallucination(a.evidence_quote);
    return quote.length > 0 && !normalized.includes(quote);
  });
  const hallucinationOk = hallucinations.length === 0;
  if (!hallucinationOk) {
    reasons.push(
      `hallucinated evidence (${hallucinations.length}): ${hallucinations
        .map((h) => JSON.stringify(h.evidence_quote.slice(0, 60)))
        .join(', ')}`
    );
  }

  // Expected ICD-10 — at least one of the candidates must match.
  const seen = new Set(soap.assessment.map((a) => a.icd10_candidate));
  const icd10Ok = evalCase.expectedIcd10Candidates.some((code) => seen.has(code));
  if (!icd10Ok) {
    reasons.push(
      `missing expected icd10 (expected one of ${evalCase.expectedIcd10Candidates.join(
        '/'
      )}, got ${[...seen].join('/') || 'none'})`
    );
  }

  const subjectiveOk = evalCase.expectedSubjectiveKeys.every(
    (k) => typeof soap.subjective[k] === 'string' && soap.subjective[k].trim().length > 0
  );
  if (!subjectiveOk) {
    reasons.push(
      `subjective missing one of: ${evalCase.expectedSubjectiveKeys.join(', ')}`
    );
  }
  const planOk = evalCase.expectedPlanKeys.every(
    (k) => typeof soap.plan[k] === 'string' && soap.plan[k].trim().length > 0
  );
  if (!planOk) {
    reasons.push(`plan missing one of: ${evalCase.expectedPlanKeys.join(', ')}`);
  }

  return {
    schemaOk: true, // we validated before calling this
    hallucinationOk,
    icd10Ok,
    subjectiveOk,
    planOk,
    reasons,
    soap,
  };
}

async function runCase(evalCase: ScribeEvalCase, basePrompt: string): Promise<Score> {
  const specialty = await prisma.scribeSpecialtyTemplate.findUnique({
    where: { slug: evalCase.specialtySlug },
  });
  if (!specialty) {
    return {
      schemaOk: false,
      hallucinationOk: false,
      icd10Ok: false,
      subjectiveOk: false,
      planOk: false,
      reasons: [
        `specialty ${evalCase.specialtySlug} not seeded — run npm run seed:specialties first`,
      ],
    };
  }

  const soapModel = process.env.MODEL_FOR_SOAP?.trim() || 'claude-sonnet-4-6';
  try {
    const soap = await modelClient.complete({
      provider: 'anthropic',
      model: soapModel,
      system: `${basePrompt}\n\n---\nSPECIALTY-SPECIFIC GUIDANCE:\n${specialty.systemPrompt}\n\nSPECIALTY SOAP SCHEMA:\n${JSON.stringify(
        specialty.soapSchema,
        null,
        2
      )}\n\nREQUIRED EXAM ELEMENTS:\n${JSON.stringify(specialty.requiredExamElements)}`,
      user: evalCase.transcript,
      schema: SoapNoteSchema,
      purpose: 'eval',
      // AiCall.practiceId has a FK to practices.id — use clinic_main
      // (always seeded) so the logger's DB write succeeds. Rows tagged
      // purpose='eval' are filterable on the admin Metrics page.
      practiceId: 'clinic_main',
    });

    return scoreCase(evalCase, evalCase.transcript, soap);
  } catch (err) {
    return {
      schemaOk: false,
      hallucinationOk: false,
      icd10Ok: false,
      subjectiveOk: false,
      planOk: false,
      reasons: [`pipeline failed: ${err instanceof Error ? err.message : String(err)}`],
    };
  }
}

function passed(s: Score): boolean {
  return s.schemaOk && s.hallucinationOk && s.icd10Ok && s.subjectiveOk && s.planOk;
}

async function main() {
  console.log(`${c.bold}${c.cyan}Scribe SOAP eval${c.reset}`);
  console.log(
    `${c.dim}${SCRIBE_EVAL_CASES.length} cases, model=${
      process.env.MODEL_FOR_SOAP?.trim() || 'claude-sonnet-4-6'
    }, threshold=${THRESHOLD * 100}%${
      JUDGE_ENABLED ? `, llm-judge=on (min mean ${JUDGE_THRESHOLD.toFixed(1)}/5)` : ''
    }${c.reset}\n`
  );

  if (!process.env.ANTHROPIC_API_KEY?.trim()) {
    console.error(`${c.red}ANTHROPIC_API_KEY is not set. Aborting.${c.reset}`);
    process.exit(1);
  }

  const basePrompt = await loadSoapPrompt();
  const judgePrompt = JUDGE_ENABLED ? await loadJudgePrompt() : null;
  const start = Date.now();

  let pass = 0;
  let judgePass = 0;
  let judgeRuns = 0;
  const judgeSum = { hallucination: 0, completeness: 0, clarity: 0, specialty_appropriateness: 0, mean: 0 };

  for (const evalCase of SCRIBE_EVAL_CASES) {
    const score = await runCase(evalCase, basePrompt);
    const ok = passed(score);
    if (ok) pass += 1;
    console.log(
      `${ok ? c.green + '✓' : c.red + '✗'} ${evalCase.id}${c.reset}  ${c.dim}${evalCase.description}${c.reset}`
    );
    if (!ok) {
      for (const r of score.reasons) console.log(`    ${c.red}•${c.reset} ${r}`);
    }

    if (JUDGE_ENABLED && score.soap && judgePrompt) {
      try {
        const j = await judgeSoap({
          transcript: evalCase.transcript,
          soap: score.soap,
          basePrompt: judgePrompt,
        });
        judgeRuns += 1;
        judgeSum.hallucination += j.criteria.hallucination;
        judgeSum.completeness += j.criteria.completeness;
        judgeSum.clarity += j.criteria.clarity;
        judgeSum.specialty_appropriateness += j.criteria.specialty_appropriateness;
        judgeSum.mean += j.score;
        const judgeOk = j.score >= JUDGE_THRESHOLD;
        if (judgeOk) judgePass += 1;
        console.log(
          `    ${judgeOk ? c.green + '★' : c.yellow + '☆'} judge ${j.score.toFixed(1)}/5${c.reset}  ${c.dim}H=${j.criteria.hallucination} C=${j.criteria.completeness} Cl=${j.criteria.clarity} Sp=${j.criteria.specialty_appropriateness} — ${j.notes.slice(0, 120)}${c.reset}`
        );
      } catch (err) {
        console.log(
          `    ${c.red}• judge call failed:${c.reset} ${err instanceof Error ? err.message : String(err)}`
        );
      }
    }
  }

  const accuracy = pass / SCRIBE_EVAL_CASES.length;
  const totalMs = Date.now() - start;
  console.log(
    `\n${c.bold}Summary${c.reset}  passed ${pass}/${SCRIBE_EVAL_CASES.length}  accuracy ${(accuracy * 100).toFixed(1)}%  runtime ${(totalMs / 1000).toFixed(1)}s`
  );

  if (JUDGE_ENABLED && judgeRuns > 0) {
    const n = judgeRuns;
    console.log(
      `${c.bold}Judge${c.reset}    mean ${(judgeSum.mean / n).toFixed(2)}/5  ` +
        `H=${(judgeSum.hallucination / n).toFixed(2)} ` +
        `C=${(judgeSum.completeness / n).toFixed(2)} ` +
        `Cl=${(judgeSum.clarity / n).toFixed(2)} ` +
        `Sp=${(judgeSum.specialty_appropriateness / n).toFixed(2)}  ` +
        `passed ${judgePass}/${n} @ ≥${JUDGE_THRESHOLD.toFixed(1)}`
    );
  }

  const judgeFailed = JUDGE_ENABLED && judgeRuns > 0 && judgePass < judgeRuns;
  if (accuracy < THRESHOLD || judgeFailed) {
    const reasons: string[] = [];
    if (accuracy < THRESHOLD) reasons.push(`accuracy below ${THRESHOLD * 100}%`);
    if (judgeFailed) reasons.push(`${judgeRuns - judgePass} case(s) below judge threshold`);
    console.log(`${c.red}${c.bold}FAIL${c.reset} — ${reasons.join(', ')}.`);
    process.exit(1);
  }
  console.log(`${c.green}${c.bold}PASS${c.reset}`);
}

main()
  .catch((err) => {
    console.error(`${c.red}Fatal:${c.reset}`, err);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
