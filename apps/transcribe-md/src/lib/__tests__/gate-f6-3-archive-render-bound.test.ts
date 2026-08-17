// ============================================================================
// F6.3 — THE ARCHIVE RENDER LOOP IS BOUNDED. Asserted three ways.
// ----------------------------------------------------------------------------
// The defect: both archive routes looped `renderVisitPdf` once per SIGNED
// visit against a single strictly-serializing Gotenberg sidecar shared with
// every doctor's interactive preview and download, with NO bound. Both routes
// carried `export const maxDuration = 300` and comments calling it a cap;
// `next.config.ts` sets `output: 'standalone'`, so that directive is INERT here
// and the cap did not exist.
//
// This file gates three separate claims, because they fail independently:
//
//   A. THE BOUND WORKS          — it charges, refuses, yields, and cancels.
//   B. THE BOUND IS NOT A TRAP  — it does not truncate any archive that
//                                 exists on production today.
//   C. THE BOUND IS WIRED       — every LOOPED caller of `renderVisitPdf`
//                                 actually goes through it, by census.
//
// ⚠️ (B) IS THE ARM PEOPLE SKIP, AND IT IS THE ONE THAT PROTECTS DOCTORS.
// A guard proved only in the RED direction is half-proved. A budget tightened
// until it engages would "pass" every arm in section A while silently
// shortening somebody's medical record — so section B pins the happy path
// against the MEASURED production population and reddens if a future edit
// tightens the default into real archives.
//
// ⚠️ AND (C) IS A CENSUS, NOT A SPOT-CHECK. Asserting that the two routes I
// edited use the budget proves nothing about a THIRD archive route added next
// month. The census names the complete set of production callers and their
// classification; a new caller reddens and forces a human to classify it,
// which is the only shape that does not go stale by hand.
// ============================================================================

import { execSync } from 'node:child_process';

import { describe, expect, it } from 'vitest';

import {
  ARCHIVE_PDF_BUDGET_MS,
  ARCHIVE_PDF_YIELD_MS,
  createArchivePdfBudget,
  skippedNote,
} from '../archive-pdf-budget';

const APP_ROOT = `${__dirname}/../../..`;

/** A deterministic clock. A budget proved with real timers is a 60-second
 *  test, and a 60-second test is one nobody runs. */
function fakeClock(startAt = 1_000_000) {
  let t = startAt;
  return {
    now: () => t,
    advance: (ms: number) => {
      t += ms;
    },
  };
}

/** A render that costs `ms` of the fake clock and succeeds. */
function costing(clock: ReturnType<typeof fakeClock>, ms: number) {
  return async () => {
    clock.advance(ms);
    return 'pdf-bytes';
  };
}

describe('F6.3 (A) — the budget charges RENDER time, not elapsed time', () => {
  it('⚠️ time spent OUTSIDE the render is not charged', async () => {
    // THE DEFECT THIS ARM EXISTS FOR, and it shipped in the first draft of the
    // module. The archive loop also loads each visit and downloads its audio.
    // An elapsed-since-start budget is consumed by those DOWNLOADS and then
    // skips every remaining PDF — truncating an archive to protect a sidecar
    // that was idle the whole time. The hazard is measured in sidecar-seconds,
    // so the budget must count sidecar-seconds.
    const clock = fakeClock();
    const budget = createArchivePdfBudget({
      budgetMs: 10_000,
      yieldMs: 0,
      now: clock.now,
    });

    clock.advance(3_600_000); // an hour of audio downloads
    expect(budget.spentMs).toBe(0);

    // ⚠️ AND THE CONSEQUENCE, WHICH IS THE HALF THAT ACTUALLY CATCHES IT.
    // `spentMs === 0` alone stays true under an elapsed-based budget — the
    // defect shows up in the REFUSAL, not the counter. After an hour of
    // downloads the sidecar is untouched, so the next PDF must still render.
    const outcome = await budget.render(costing(clock, 400));
    expect(
      outcome.status,
      'the budget refused a render after an hour of AUDIO DOWNLOADS, during ' +
        'which the sidecar was idle. It is measuring elapsed time instead of ' +
        'sidecar time, and it will truncate the archives of exactly the ' +
        'doctors with the most recordings.',
    ).toBe('rendered');
  });

  it('charges each render exactly what it cost', async () => {
    const clock = fakeClock();
    const budget = createArchivePdfBudget({
      budgetMs: 10_000,
      yieldMs: 0,
      now: clock.now,
    });

    await budget.render(costing(clock, 400));
    expect(budget.spentMs).toBe(400);
    await budget.render(costing(clock, 600));
    expect(budget.spentMs).toBe(1_000);
  });

  it('⚠️ charges a FAILED render too', async () => {
    // A `convert.ts` timeout costs the sidecar its full 12s whether or not a
    // PDF comes back. Charging only successes would let a wedged sidecar be
    // hammered 18 x 12s by one archive — the exact starvation this bounds.
    const clock = fakeClock();
    const budget = createArchivePdfBudget({
      budgetMs: 30_000,
      yieldMs: 0,
      now: clock.now,
    });

    const outcome = await budget.render(async () => {
      clock.advance(12_000);
      throw new Error('renderer unavailable (timeout)');
    });

    expect(outcome.status).toBe('failed');
    expect(budget.spentMs).toBe(12_000);
    expect(budget.failed).toBe(1);
  });

  it('a wedged sidecar exhausts the budget instead of being hammered', async () => {
    const clock = fakeClock();
    const budget = createArchivePdfBudget({
      budgetMs: 60_000,
      yieldMs: 0,
      now: clock.now,
    });

    const statuses: string[] = [];
    for (let i = 0; i < 18; i += 1) {
      const o = await budget.render(async () => {
        clock.advance(12_000); // every render times out
        throw new Error('timeout');
      });
      statuses.push(o.status);
    }

    expect(budget.failed).toBe(5); // 5 x 12s = the 60s budget
    expect(statuses.filter((s) => s === 'skipped').length).toBe(13);
  });
});

describe('F6.3 (A) — the bound admits and refuses', () => {
  it('admits renders while under budget', async () => {
    const clock = fakeClock();
    const budget = createArchivePdfBudget({
      budgetMs: 10_000,
      yieldMs: 0,
      now: clock.now,
    });

    expect((await budget.render(costing(clock, 400))).status).toBe('rendered');
    expect((await budget.render(costing(clock, 400))).status).toBe('rendered');
    expect(budget.rendered).toBe(2);
    expect(budget.skipped).toBe(0);
  });

  it('refuses with budget_exhausted once the ceiling is reached, and STAYS refused', async () => {
    const clock = fakeClock();
    const budget = createArchivePdfBudget({
      budgetMs: 10_000,
      yieldMs: 0,
      now: clock.now,
    });

    await budget.render(costing(clock, 10_000));

    for (const _ of [1, 2]) {
      const o = await budget.render(costing(clock, 400));
      expect(o.status).toBe('skipped');
      expect(o.status === 'skipped' && o.reason).toBe('budget_exhausted');
    }
    // A bound that engages once and then forgets would let the rest of the
    // loop through, which is the whole hazard.
    expect(budget.rendered).toBe(1);
    expect(budget.skipped).toBe(2);
  });

  it('the ceiling is >=, not > — the boundary tick refuses', async () => {
    const clock = fakeClock();
    const budget = createArchivePdfBudget({
      budgetMs: 5_000,
      yieldMs: 0,
      now: clock.now,
    });
    expect((await budget.render(costing(clock, 4_999))).status).toBe('rendered');
    expect((await budget.render(costing(clock, 1))).status).toBe('rendered');
    // spent is now exactly 5_000 — the next one must refuse.
    expect(budget.spentMs).toBe(5_000);
    expect((await budget.render(costing(clock, 1))).status).toBe('skipped');
  });

  it('every render lands in exactly one bucket — the counters reconcile', async () => {
    // The bucket-total discipline: anything that fits no counter is the
    // finding. Without this, a path that returns early without counting would
    // be invisible to every arm above.
    const clock = fakeClock();
    const budget = createArchivePdfBudget({
      budgetMs: 3_000,
      yieldMs: 0,
      now: clock.now,
    });

    let calls = 0;
    for (let i = 0; i < 10; i += 1) {
      await budget.render(async () => {
        clock.advance(500);
        if (i === 2) throw new Error('boom');
        return 'ok';
      });
      calls += 1;
    }

    expect(budget.rendered + budget.skipped + budget.failed).toBe(calls);
    expect(budget.rendered).toBeGreaterThan(0);
    expect(budget.skipped).toBeGreaterThan(0);
    expect(budget.failed).toBe(1);
  });

  it('a skipped render never runs the function', async () => {
    const clock = fakeClock();
    const budget = createArchivePdfBudget({
      budgetMs: 1_000,
      yieldMs: 0,
      now: clock.now,
    });
    await budget.render(costing(clock, 1_000));

    let ran = false;
    await budget.render(async () => {
      ran = true;
      return 'x';
    });
    expect(
      ran,
      'a refused render still touched the sidecar — the bound bounds nothing',
    ).toBe(false);
  });
});

describe('F6.3 (A) — cancellation stops the loop', () => {
  it('an already-aborted signal refuses immediately, before any render', async () => {
    const controller = new AbortController();
    controller.abort();
    const budget = createArchivePdfBudget({
      signal: controller.signal,
      yieldMs: 0,
    });

    const o = await budget.render(async () => 'x');
    expect(o.status).toBe('skipped');
    expect(o.status === 'skipped' && o.reason).toBe('client_disconnected');
    expect(budget.rendered).toBe(0);
  });

  it('⚠️ an abort DURING the yield is caught — the re-check arm', async () => {
    // The arm an obvious implementation would not have written. The yield is
    // the longest await in the loop, so it is exactly where a disconnect
    // lands; checking the signal only on entry would hand one more render to a
    // client that is already gone, per archive.
    const controller = new AbortController();
    const clock = fakeClock();

    const budget = createArchivePdfBudget({
      signal: controller.signal,
      budgetMs: 60_000,
      yieldMs: 250,
      now: clock.now,
      sleep: async () => {
        controller.abort(); // the client vanishes mid-yield
      },
    });

    expect((await budget.render(costing(clock, 400))).status).toBe('rendered');
    const o = await budget.render(costing(clock, 400));
    expect(o.status).toBe('skipped');
    expect(o.status === 'skipped' && o.reason).toBe('client_disconnected');
    expect(budget.rendered).toBe(1);
  });
});

describe('F6.3 (A) — the yield is between renders, not before the first', () => {
  it('does not sleep before the first render, and does before every later one', async () => {
    const sleeps: number[] = [];
    const clock = fakeClock();
    const budget = createArchivePdfBudget({
      budgetMs: 60_000,
      yieldMs: 250,
      now: clock.now,
      sleep: async (ms) => {
        sleeps.push(ms);
      },
    });

    await budget.render(costing(clock, 400));
    expect(
      sleeps,
      'the first render has nothing to yield to — an unconditional sleep here ' +
        'is pure latency on every archive, including single-visit ones',
    ).toEqual([]);

    await budget.render(costing(clock, 400));
    await budget.render(costing(clock, 400));
    expect(sleeps).toEqual([250, 250]);
  });

  it('the yield is NOT charged to the budget — it is the opposite of occupancy', async () => {
    const clock = fakeClock();
    const budget = createArchivePdfBudget({
      budgetMs: 60_000,
      yieldMs: 250,
      now: clock.now,
      sleep: async (ms) => clock.advance(ms),
    });

    await budget.render(costing(clock, 400));
    await budget.render(costing(clock, 400));
    expect(budget.spentMs).toBe(800);
  });
});

describe('F6.3 (B) — the default bound does NOT truncate a real archive', () => {
  // ⚠️ THE POPULATION IS MEASURED, NOT ASSUMED. Read off production
  // 2026-08-17: the largest single archive is 18 signed visits (the per-user
  // maximum). The per-patient maximum is 7. The 27 figure in the ledger is the
  // TOTAL signed rows in the whole database and is not any one archive's loop
  // length — recorded because that conflation is what the constant would
  // otherwise have been sized against.
  const LARGEST_ARCHIVE_ON_PROD = 18;

  /** Per-conversion sidecar cost.
   *
   * ⚠️ **INHERITED, NOT RE-MEASURED HERE — and the distinction is load-bearing
   * for exactly one claim.** The 0.42s staircase was measured on 2026-08-16
   * and recorded in `RELAY.md`; this session did not reproduce it. A faithful
   * reproduction needs a REAL visit render, and the cheap substitutes — a DOCX
   * synthesized in a container, a trivial fixture — would have produced a
   * measured-LOOKING number for a document nobody exports.
   *
   * **What depends on it:** the headroom arm below, and therefore the claim
   * that an 18-visit archive fits. If the true cost is above ~3.3s per render,
   * an 18-visit archive WOULD be truncated by the default budget.
   *
   * **What does NOT depend on it:** the safety property. Whatever a render
   * costs, one archive can never occupy the sidecar for more than
   * `ARCHIVE_PDF_BUDGET_MS`. That bound is absolute and needs no estimate.
   *
   * **What would falsify it:** a production archive emitting
   * `signed.pdf.UNAVAILABLE.txt` with reason `budget_exhausted`. That is the
   * observable, it is NAMED rather than silent, and it means this constant is
   * wrong — re-measure before widening the budget. */
  const MEASURED_RENDER_MS = 420;

  it(`admits all ${LARGEST_ARCHIVE_ON_PROD} visits of the largest archive on production`, async () => {
    const clock = fakeClock();
    const budget = createArchivePdfBudget({
      now: clock.now,
      sleep: async (ms) => clock.advance(ms),
    });

    const statuses: string[] = [];
    for (let i = 0; i < LARGEST_ARCHIVE_ON_PROD; i += 1) {
      statuses.push((await budget.render(costing(clock, MEASURED_RENDER_MS))).status);
    }

    expect(
      statuses.filter((s) => s !== 'rendered'),
      'the DEFAULT budget truncated an archive the size of the largest one on ' +
        'production. Either ARCHIVE_PDF_BUDGET_MS was tightened or the ' +
        'per-render cost grew — either way a doctor is now silently getting ' +
        'fewer PDFs than they asked for. Re-measure before changing this.',
    ).toEqual([]);
    expect(budget.rendered).toBe(LARGEST_ARCHIVE_ON_PROD);
  });

  it('keeps a healthy multiple of headroom over that archive', () => {
    const admits = Math.floor(ARCHIVE_PDF_BUDGET_MS / MEASURED_RENDER_MS);
    expect(
      admits,
      `the default budget admits ~${admits} visits against a largest-known ` +
        `archive of ${LARGEST_ARCHIVE_ON_PROD}. Under 3x headroom means the ` +
        'next few signed visits start hitting the ceiling.',
    ).toBeGreaterThan(LARGEST_ARCHIVE_ON_PROD * 3);
  });

  it('the constants are what this file was reasoned against', () => {
    // Pins the two numbers every assertion above depends on. Changing either
    // is legitimate; changing it without re-reading this file is not.
    expect(ARCHIVE_PDF_BUDGET_MS).toBe(60_000);
    expect(ARCHIVE_PDF_YIELD_MS).toBe(250);
  });
});

describe('F6.3 — the skip is NAMED, and names the right cause', () => {
  it('discriminates on the reason', () => {
    expect(skippedNote('v1', 'budget_exhausted')).not.toBe(
      skippedNote('v1', 'client_disconnected'),
    );
  });

  it('⚠️ never blames the renderer — that is a DIFFERENT note', () => {
    // `unavailableNote` (visit-pdf.ts) explains a render that was ATTEMPTED
    // AND FAILED. These explain a render that was never attempted. Telling a
    // doctor the renderer failed when it was never asked is a confident false
    // statement about the cause — the wrong-field failure, which is worse than
    // an absent field.
    for (const reason of ['budget_exhausted', 'client_disconnected'] as const) {
      const text = skippedNote('v1', reason);
      expect(text).not.toMatch(/renderer (was )?unavailable/i);
      expect(text).not.toMatch(/did not return/i);
    }
  });

  it('points at the visit record and says the visit is unaffected', () => {
    for (const reason of ['budget_exhausted', 'client_disconnected'] as const) {
      const text = skippedNote('abc123', reason);
      expect(text).toContain('visits/abc123.json');
      expect(text).toMatch(/unaffected/);
    }
  });
});

// ---------------------------------------------------------------------------
// (C) THE CENSUS. Same instrument and the same controls as
// `gate-f3-one-pdf-builder.test.ts` — a traversal that silently walks nothing
// reports the identical clean zero as a codebase with nothing to find.
// ---------------------------------------------------------------------------

function isCommentLine(hit: string): boolean {
  const text = hit.replace(/^[^:]*:\d+:/, '').replace(/\/\*.*?\*\//g, ' ');
  return /^\s*(\/\/|\*|\/\*)/.test(text) || text.trim() === '';
}

function gitGrep(pattern: string, pathspec: string): string[] {
  try {
    return execSync(`git grep -n -- ${JSON.stringify(pattern)} -- ${pathspec}`, {
      cwd: APP_ROOT,
      encoding: 'utf8',
    })
      .split('\n')
      .filter(Boolean)
      .filter((h) => !isCommentLine(h));
  } catch {
    // `git grep` exits 1 on NO MATCHES — the expected shape for an absence
    // arm. The controls below are what distinguish that from a broken
    // traversal.
    return [];
  }
}

/** Production source only. Tests do not ship, and the DEFINITION site is
 *  excluded because `export async function renderVisitPdf(` contains the call
 *  shape and is not a caller — the substring trap, one line from home. */
const CALLERS_PATHSPEC =
  "'src' ':(exclude)src/**/__tests__/**' ':(exclude)src/lib/visit-pdf.ts'" +
  " ':(exclude)src/lib/archive-pdf-budget.ts'";

describe('F6.3 (C) — the traversal itself works', () => {
  it('POSITIVE CONTROL — finds something that certainly exists', () => {
    const hits = gitGrep('renderVisitPdf', "'src'");
    expect(
      hits.length,
      'the traversal found no reference to renderVisitPdf, which certainly ' +
        'exists. The instrument is broken — do not read the census below.',
    ).toBeGreaterThan(2);
  });

  it('NEGATIVE CONTROL — returns empty for a token that is really absent', () => {
    // Assembled at runtime so no literal of it exists in any tracked file,
    // including this one.
    const absent = 'zzzNoSuchSymbol' + 'AnywhereF63zzz';
    expect(gitGrep(absent, "'src'")).toEqual([]);
  });
});

describe('F6.3 (C) — every LOOPED caller of renderVisitPdf is bounded', () => {
  /** ⚠️ THIS TABLE IS THE SPEC, AND THE CENSUS BELOW IS DIFFED AGAINST IT.
   *  A caller in the code and not here reddens — which is the point.
   *  Classification is a human judgement about whether the call sits inside a
   *  per-visit loop, and it must not be inferred by regex. */
  const EXPECTED_CALLERS: Record<string, 'looped' | 'single'> = {
    'src/app/api/settings/export-data/route.ts': 'looped',
    'src/app/api/patients/[id]/export/route.ts': 'looped',
    // One visit, one render, one response — no loop, so no bound is owed.
    'src/app/api/visits/[id]/export/pdf/route.ts': 'single',
  };

  const callerFiles = Array.from(
    new Set(
      gitGrep('renderVisitPdf(', CALLERS_PATHSPEC).map((h) => h.split(':')[0]),
    ),
  ).sort();

  it('the census matches the classified set exactly — no unclassified caller', () => {
    expect(
      callerFiles,
      'a file calls renderVisitPdf and is not classified in EXPECTED_CALLERS. ' +
        'Decide whether it loops: a looped caller MUST render through a ' +
        'budget, a single caller need not. Do not delete this to go green.',
    ).toEqual(Object.keys(EXPECTED_CALLERS).sort());
  });

  it('non-vacuity — the census is not empty', () => {
    expect(callerFiles.length).toBe(3);
  });

  for (const [file, kind] of Object.entries(EXPECTED_CALLERS)) {
    if (kind !== 'looped') continue;

    it(`${file} creates a render budget`, () => {
      expect(
        gitGrep('createArchivePdfBudget(', `'${file}'`).length,
        `${file} loops renderVisitPdf and never creates a budget — the F6.3 ` +
          'defect, reintroduced.',
      ).toBeGreaterThan(0);
    });

    it(`${file} renders THROUGH the budget`, () => {
      // Creating a budget and rendering around it is the half-landed fix: the
      // import lands, the call site does not, and nothing else notices.
      expect(
        gitGrep('pdfBudget.render(', `'${file}'`).length,
        `${file} creates a budget but never renders through it — a bound ` +
          'that is constructed and never consulted bounds nothing.',
      ).toBeGreaterThan(0);
    });

    it(`${file} does NOT call renderVisitPdf outside the budget`, () => {
      // ⚠️ THE BICONDITIONAL. Every `renderVisitPdf(` in a looped caller must
      // be the one inside `pdfBudget.render(() => …)`. A second, unwrapped
      // call would satisfy every arm above and be exactly the original defect.
      const calls = gitGrep('renderVisitPdf(', `'${file}'`);
      expect(
        calls.length,
        `${file} calls renderVisitPdf ${calls.length} times; exactly one of ` +
          'them may exist, and it must be the one wrapped by the budget.',
      ).toBe(1);
      expect(
        calls[0],
        `${file}'s renderVisitPdf call is not the budget-wrapped one.`,
      ).toMatch(/renderVisitPdf\(exportData\)/);
    });

    it(`${file} NAMES a skipped PDF instead of dropping it`, () => {
      expect(
        gitGrep('skippedNote(', `'${file}'`).length,
        `${file} can skip a render and does not write a note. An absent ` +
          'signed.pdf is indistinguishable from a visit that was never ' +
          'signed — ruling #113/#116.',
      ).toBeGreaterThan(0);
    });

    it(`${file} threads the request signal into the budget`, () => {
      expect(
        gitGrep('signal: req.signal', `'${file}'`).length,
        `${file} builds a budget with no signal, so a cancelled download ` +
          'keeps consuming sidecar slots for a client that is gone.',
      ).toBeGreaterThan(0);
    });
  }
});

describe('F6.3 — the archive READMEs describe the file that can now appear', () => {
  // The routes gained a SECOND reason to emit signed.pdf.UNAVAILABLE.txt. A
  // README that promises signed.pdf and never mentions it leaves a doctor
  // holding a file the archive's own manual does not describe.
  for (const file of [
    'src/app/api/settings/export-data/route.ts',
    'src/app/api/patients/[id]/export/route.ts',
  ]) {
    it(`${file}'s README names signed.pdf.UNAVAILABLE.txt`, () => {
      expect(
        gitGrep('signed.pdf.UNAVAILABLE.txt', `'${file}'`).length,
        `${file} can write signed.pdf.UNAVAILABLE.txt and its README never ` +
          'mentions it.',
      ).toBeGreaterThan(2); // two append paths AND the README line
    });
  }
});
