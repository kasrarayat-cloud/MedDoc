// ============================================================================
// Eval runner — Doc Editor intent parser (Pass 1)
// ----------------------------------------------------------------------------
// Runs every case in tests/evals/doc-editor-phrasings.ts against the real
// OpenAI API (gpt-4o-mini via parseEditIntent). Prints per-case pass/fail
// with diff, plus an overall accuracy number.
//
// Usage: npm run eval:doc-editor
// Requires: OPENAI_API_KEY in .env
//
// Cost: ~30 cases × ~500 input tokens × $0.15/M = ~$0.002 per run.
// Latency: ~5-15s depending on concurrency.
//
// Exits non-zero if accuracy < THRESHOLD so this can gate a release if wired
// into a nightly workflow. Tuning the threshold: start at 0.85, raise as
// the prompt matures. A persistent single-case failure is a signal to
// either (a) add the phrasing to the intent-parser prompt's examples, or
// (b) remove the case if the expected output was wrong.
// ============================================================================

import 'dotenv/config';

import { EVAL_CASES, SAMPLE_DOC, type EvalCase } from '../tests/evals/doc-editor-phrasings';
import { parseEditIntent, type EditIntent } from '../src/lib/ai-service';

const THRESHOLD = 0.85; // fail the run if accuracy drops below 85%
const CONCURRENCY = 5;   // OpenAI tier-1 RPM easily handles this

// ----------------------------------------------------------------------------
// Terminal colors — no dependency, just ANSI
// ----------------------------------------------------------------------------
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

// ----------------------------------------------------------------------------
// Case comparison — what counts as a pass
// ----------------------------------------------------------------------------
type Verdict =
  | { status: 'pass' }
  | { status: 'fail'; reasons: string[] }
  | { status: 'error'; error: string };

function compareIntent(expected: EvalCase['expected'], actual: EditIntent): Verdict {
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

  if (expected.fill_fields) {
    for (const want of expected.fill_fields) {
      const got = actual.fill_fields.find(
        (f) => f.field.toUpperCase() === want.field.toUpperCase()
      );
      if (!got) {
        reasons.push(`fill_fields: missing expected field ${want.field}`);
      } else if (want.value !== undefined && got.value !== want.value) {
        reasons.push(
          `fill_fields[${want.field}]: expected value ${JSON.stringify(want.value)}, got ${JSON.stringify(got.value)}`
        );
      }
    }
  }

  return reasons.length === 0 ? { status: 'pass' } : { status: 'fail', reasons };
}

// ----------------------------------------------------------------------------
// Runner — parallel with concurrency cap
// ----------------------------------------------------------------------------
interface Result {
  caseId: string;
  description: string;
  verdict: Verdict;
  actual?: EditIntent;
  latencyMs: number;
}

async function runCase(evalCase: EvalCase): Promise<Result> {
  const start = Date.now();
  try {
    const { intent } = await parseEditIntent(
      evalCase.document ?? SAMPLE_DOC,
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

async function runAll(cases: EvalCase[]): Promise<Result[]> {
  const results: Result[] = new Array(cases.length);
  let nextIdx = 0;

  const workers = Array.from({ length: CONCURRENCY }, async () => {
    while (true) {
      const idx = nextIdx++;
      if (idx >= cases.length) return;
      results[idx] = await runCase(cases[idx]);
      // One dot per completed case for progress feedback
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

// ----------------------------------------------------------------------------
// Reporting
// ----------------------------------------------------------------------------
function printResult(r: Result, evalCase: EvalCase) {
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
      fill_fields: r.actual.fill_fields,
    })}`);
    console.log(`  ${c.dim}parser reasoning:${c.reset} ${r.actual.reasoning}`);
  }
}

async function main() {
  console.log(`${c.bold}${c.cyan}Doc Editor — intent parser eval suite${c.reset}`);
  console.log(`${c.dim}${EVAL_CASES.length} cases, concurrency=${CONCURRENCY}, threshold=${THRESHOLD * 100}%${c.reset}\n`);

  if (!process.env.OPENAI_API_KEY?.trim()) {
    console.error(`${c.red}OPENAI_API_KEY is not set. Aborting.${c.reset}`);
    process.exit(1);
  }

  const totalStart = Date.now();
  const results = await runAll(EVAL_CASES);
  const totalMs = Date.now() - totalStart;

  // Print per-case details
  for (let i = 0; i < results.length; i++) {
    printResult(results[i], EVAL_CASES[i]);
  }

  // Summary
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
