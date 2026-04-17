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
import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';
import { SoapNoteSchema, type SoapNote } from '@meddoc/types';
import { SCRIBE_EVAL_CASES, type ScribeEvalCase } from '../tests/evals/scribe-transcripts';

const THRESHOLD = 0.8;

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
  // the transcript. We normalize whitespace for a friendlier comparison.
  const normalized = transcriptRaw.replace(/\s+/g, ' ').toLowerCase();
  const hallucinations = soap.assessment.filter((a) => {
    const quote = a.evidence_quote.replace(/\s+/g, ' ').toLowerCase().trim();
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
    }, threshold=${THRESHOLD * 100}%${c.reset}\n`
  );

  if (!process.env.ANTHROPIC_API_KEY?.trim()) {
    console.error(`${c.red}ANTHROPIC_API_KEY is not set. Aborting.${c.reset}`);
    process.exit(1);
  }

  const basePrompt = await loadSoapPrompt();
  const start = Date.now();

  let pass = 0;
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
  }

  const accuracy = pass / SCRIBE_EVAL_CASES.length;
  const totalMs = Date.now() - start;
  console.log(
    `\n${c.bold}Summary${c.reset}  passed ${pass}/${SCRIBE_EVAL_CASES.length}  accuracy ${(accuracy * 100).toFixed(1)}%  runtime ${(totalMs / 1000).toFixed(1)}s`
  );

  if (accuracy < THRESHOLD) {
    console.log(
      `${c.red}${c.bold}FAIL${c.reset} — below ${THRESHOLD * 100}% threshold.`
    );
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
