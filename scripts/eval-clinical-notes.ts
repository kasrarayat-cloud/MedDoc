// ============================================================================
// Eval runner — Clinical Notes intent parser (Pass 1)
// ----------------------------------------------------------------------------
// Runs every case in tests/evals/clinical-notes-phrasings.ts against the
// real OpenAI API (gpt-4o-mini via parseEditIntent). Prints per-case pass/
// fail with diff, plus an overall accuracy number.
//
// Companion to scripts/eval-doc-editor.ts — same Pass 1 parser, different
// case set tuned for clinical-note edits (mostly partial_edit, dose changes,
// section rewrites, voice typos).
//
// Usage: npm run eval:clinical-notes
// Cost: ~25 cases × ~500 input tokens × $0.15/M ≈ $0.002 per run.
// ============================================================================

import 'dotenv/config';

import {
  NOTE_EVAL_CASES,
  SAMPLE_NOTE,
  type NoteEvalCase,
} from '../tests/evals/clinical-notes-phrasings';
import { parseEditIntent, type EditIntent } from '../src/lib/ai-service';

const THRESHOLD = 0.85;
const CONCURRENCY = 5;

const c = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
  gray: '\x1b[90m',
};

type Verdict =
  | { status: 'pass' }
  | { status: 'fail'; reasons: string[] }
  | { status: 'error'; error: string };

function compareIntent(expected: NoteEvalCase['expected'], actual: EditIntent): Verdict {
  const reasons: string[] = [];

  if (actual.operation !== expected.operation) {
    reasons.push(`operation: expected ${expected.operation}, got ${actual.operation}`);
  }
  if (expected.target_section !== undefined) {
    if (actual.target_section !== expected.target_section) {
      reasons.push(
        `target_section: expected ${JSON.stringify(expected.target_section)}, got ${JSON.stringify(actual.target_section)}`
      );
    }
  }
  if (expected.replacement_text !== undefined) {
    if (actual.replacement_text !== expected.replacement_text) {
      reasons.push(
        `replacement_text: expected ${JSON.stringify(expected.replacement_text)}, got ${JSON.stringify(actual.replacement_text)}`
      );
    }
  }
  if (actual.confidence !== expected.confidence) {
    reasons.push(`confidence: expected ${expected.confidence}, got ${actual.confidence}`);
  }

  return reasons.length === 0 ? { status: 'pass' } : { status: 'fail', reasons };
}

interface Result {
  caseId: string;
  description: string;
  verdict: Verdict;
  actual?: EditIntent;
  latencyMs: number;
}

async function runCase(evalCase: NoteEvalCase): Promise<Result> {
  const start = Date.now();
  try {
    const { intent } = await parseEditIntent(
      evalCase.note ?? SAMPLE_NOTE,
      evalCase.instruction
    );
    return {
      caseId: evalCase.id,
      description: evalCase.description,
      verdict: compareIntent(evalCase.expected, intent),
      actual: intent,
      latencyMs: Date.now() - start,
    };
  } catch (err) {
    return {
      caseId: evalCase.id,
      description: evalCase.description,
      verdict: {
        status: 'error',
        error: err instanceof Error ? err.message : String(err),
      },
      latencyMs: Date.now() - start,
    };
  }
}

async function runAll(cases: NoteEvalCase[]): Promise<Result[]> {
  const results: Result[] = new Array(cases.length);
  let nextIdx = 0;

  const workers = Array.from({ length: CONCURRENCY }, async () => {
    while (true) {
      const idx = nextIdx++;
      if (idx >= cases.length) return;
      results[idx] = await runCase(cases[idx]);
      process.stdout.write(
        results[idx].verdict.status === 'pass'
          ? `${c.green}.${c.reset}`
          : results[idx].verdict.status === 'fail'
            ? `${c.red}F${c.reset}`
            : `${c.yellow}E${c.reset}`
      );
    }
  });

  await Promise.all(workers);
  process.stdout.write('\n\n');
  return results;
}

function printResult(r: Result, evalCase: NoteEvalCase) {
  if (r.verdict.status === 'pass') {
    console.log(`${c.green}✓${c.reset} ${r.caseId}  ${c.dim}${r.description}${c.reset}  ${c.gray}(${r.latencyMs}ms)${c.reset}`);
    return;
  }
  if (r.verdict.status === 'error') {
    console.log(`${c.yellow}⚠${c.reset} ${r.caseId}  ${c.bold}${r.description}${c.reset}`);
    console.log(`  ${c.yellow}error:${c.reset} ${r.verdict.error}`);
    return;
  }
  console.log(`${c.red}✗${c.reset} ${r.caseId}  ${c.bold}${r.description}${c.reset}`);
  console.log(`  ${c.dim}instruction:${c.reset} ${JSON.stringify(evalCase.instruction)}`);
  for (const reason of r.verdict.reasons) {
    console.log(`  ${c.red}•${c.reset} ${reason}`);
  }
  if (r.actual) {
    console.log(`  ${c.dim}actual intent:${c.reset} ${JSON.stringify({
      operation: r.actual.operation,
      target_section: r.actual.target_section,
      replacement_text: r.actual.replacement_text,
      confidence: r.actual.confidence,
    })}`);
    console.log(`  ${c.dim}parser reasoning:${c.reset} ${r.actual.reasoning}`);
  }
}

async function main() {
  console.log(`${c.bold}${c.cyan}Clinical Notes — intent parser eval suite${c.reset}`);
  console.log(`${c.dim}${NOTE_EVAL_CASES.length} cases, concurrency=${CONCURRENCY}, threshold=${THRESHOLD * 100}%${c.reset}\n`);

  if (!process.env.OPENAI_API_KEY?.trim()) {
    console.error(`${c.red}OPENAI_API_KEY is not set. Aborting.${c.reset}`);
    process.exit(1);
  }

  const totalStart = Date.now();
  const results = await runAll(NOTE_EVAL_CASES);
  const totalMs = Date.now() - totalStart;

  for (let i = 0; i < results.length; i++) {
    printResult(results[i], NOTE_EVAL_CASES[i]);
  }

  const passed = results.filter((r) => r.verdict.status === 'pass').length;
  const failed = results.filter((r) => r.verdict.status === 'fail').length;
  const errored = results.filter((r) => r.verdict.status === 'error').length;
  const accuracy = passed / results.length;

  console.log(`\n${c.bold}Summary${c.reset}`);
  console.log(`  total:    ${results.length}`);
  console.log(`  ${c.green}passed:${c.reset}   ${passed}`);
  console.log(`  ${c.red}failed:${c.reset}   ${failed}`);
  console.log(`  ${c.yellow}errored:${c.reset}  ${errored}`);
  console.log(`  accuracy: ${c.bold}${(accuracy * 100).toFixed(1)}%${c.reset}`);
  console.log(`  runtime:  ${(totalMs / 1000).toFixed(1)}s`);

  if (accuracy < THRESHOLD) {
    console.log(`\n${c.red}${c.bold}FAIL${c.reset} — accuracy ${(accuracy * 100).toFixed(1)}% is below threshold ${(THRESHOLD * 100).toFixed(0)}%.`);
    process.exit(1);
  }
  console.log(`\n${c.green}${c.bold}PASS${c.reset} — accuracy meets the ${(THRESHOLD * 100).toFixed(0)}% threshold.`);
}

main().catch((err) => {
  console.error(`${c.red}Fatal:${c.reset}`, err);
  process.exit(1);
});
