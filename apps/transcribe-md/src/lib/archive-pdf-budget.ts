// ============================================================================
// THE ARCHIVE RENDER BOUND — F6.3.
// ----------------------------------------------------------------------------
// The two archive routes (`GET /api/settings/export-data`, `GET
// /api/patients/[id]/export`) loop `renderVisitPdf` once per SIGNED visit.
// Every one of those renders crosses to the SAME Gotenberg sidecar that serves
// every doctor's interactive preview and PDF download — one instance,
// `cpus: '1.5'`, which serializes strictly (measured: a 0.42s staircase across
// 4 concurrent conversions).
//
// ⚠️ BEFORE THIS MODULE, NOTHING BOUNDED THAT LOOP. Both routes declared
// `export const maxDuration = 300` and both comments described it as a cap.
// **It is inert here**: `maxDuration` is a SERVERLESS directive and
// `next.config.ts` sets `output: 'standalone'`, so the app is a plain
// `node server.js` with no platform to honour it. The cap did not exist and
// the comments said it did — the `DEPLOYMENT_RUNBOOK.md` §5.6 shape, a stated
// invariant nothing asserts.
//
// THE SYMPTOM THAT MADE IT A HAZARD RATHER THAN A TIDY-UP: a doctor's PDF
// download 503s with *"the renderer is unavailable (timeout)"* — `convert.ts`'s
// 12s `CONVERT_TIMEOUT_MS` firing — while the renderer is not unavailable at
// all. It is merely queued behind somebody else's ZIP. The message is false
// about the system, and the doctor cannot act on it.
//
// ⚠️ WHAT THIS MODULE DOES **NOT** DO, SAID PLAINLY SO THE NAME IS NOT READ
// WIDER THAN THE MECHANISM:
//   · It does NOT make the sidecar FAIR. Two archives running at once still
//     occupy it twice over; there is no cross-request admission control here
//     and no priority for interactive renders. That is a separate item.
//   · It does NOT speed anything up. It makes an archive politer and bounded,
//     which costs the archive wall-clock it was previously taking from
//     everyone else.
//
// THE TWO ARMS, AND THEY BOUND DIFFERENT THINGS:
//
//   1. **YIELD** cures the COMMON case and drops nothing. A gap between our
//      submissions is precisely the window in which a strictly-serializing
//      sidecar can serve somebody else's interactive request. Without it, a
//      27-visit archive is 27 back-to-back conversions and an interactive
//      caller waits for all of them.
//   2. **BUDGET** bounds the WORST case. Wall-clock ceiling on the whole
//      render phase; past it, remaining visits are NAMED as unrendered rather
//      than silently absent.
//
// ⚠️ THERE IS DELIBERATELY NO COUNT CAP, and the reason is worth keeping.
// A `take(N)` reads like the obvious bound and buys nothing the budget does
// not already buy: the hazard is measured in sidecar-SECONDS, not in rows, so
// a count cap adds a second way to truncate a doctor's archive while bounding
// nothing the clock does not. One truncation mechanism, not two.
//
// ⚠️ THE BUDGET CHARGES TIME SPENT **INSIDE THE RENDER**, NOT WALL-CLOCK SINCE
// THE ARCHIVE STARTED — AND THE DIFFERENCE IS A DEFECT THIS MODULE SHIPPED
// WITH FOR ONE DRAFT. The archive loop also loads each visit and downloads its
// audio; a doctor with large recordings can spend minutes there without ever
// touching the sidecar. An elapsed-since-start budget would have been consumed
// by those DOWNLOADS and then skipped every remaining PDF — truncating an
// archive to protect a sidecar that was idle the whole time. The quantity the
// hazard is measured in is sidecar-seconds, so that is the quantity the budget
// counts. Found by the refutation pass over this file's own diff.
//
// ⚠️ A FAILED RENDER IS CHARGED TOO, DELIBERATELY. A `convert.ts` timeout costs
// the sidecar its full 12s `CONVERT_TIMEOUT_MS` whether or not a PDF comes
// back. Charging only successes would let a wedged sidecar be hammered
// 18 × 12s by a single archive — the exact starvation this bounds. Charging
// failures means five timeouts exhaust the budget and the archive stops asking.
// ============================================================================

/**
 * Ceiling on the CUMULATIVE time one archive may spend inside `renderVisitPdf`
 * — i.e. on the sidecar-seconds it is allowed to consume. Not elapsed time; see
 * the header.
 *
 * ⚠️ SIZED AGAINST THE MEASURED PRODUCTION POPULATION, NOT GUESSED. On
 * 2026-08-17 the largest single archive on production is **18** signed visits
 * (the per-user maximum; the per-patient maximum is 7, and 27 is the total
 * signed rows in the whole database — a figure the ledger had conflated with
 * one archive's loop length). At the measured 0.42s per conversion, 60s admits
 * roughly 140 visits.
 *
 * **So this must not truncate any archive that exists today, by a factor of
 * about eight** — and the gate asserts exactly that, so a future edit that
 * tightens this into real archives goes red instead of quietly shortening
 * somebody's record.
 */
export const ARCHIVE_PDF_BUDGET_MS = 60_000;

/**
 * Pause between consecutive renders inside one archive.
 *
 * Small enough to be invisible against an archive that is already streaming
 * audio blobs, large enough to be a real serving window for a sidecar whose
 * measured per-conversion cost is 0.42s.
 */
export const ARCHIVE_PDF_YIELD_MS = 250;

/** Why a signed visit's PDF was not rendered. Both are NAMED in the archive. */
export type ArchivePdfSkip = 'budget_exhausted' | 'client_disconnected';

/**
 * The three things that can happen to one visit's PDF. The caller must handle
 * all three; `skipped` and `failed` carry DIFFERENT doctor-facing notes,
 * because one says the render was never attempted and the other says it was
 * attempted and did not come back.
 */
export type ArchivePdfOutcome<T> =
  | { status: 'rendered'; value: T }
  | { status: 'skipped'; reason: ArchivePdfSkip }
  | { status: 'failed'; error: unknown };

export interface ArchivePdfBudget {
  /**
   * Wrap one `renderVisitPdf`.
   *
   * ⚠️ THE RENDER IS WRAPPED RATHER THAN GATED BY A SEPARATE `claim()`, AND
   * THAT IS THE POINT. A check-then-render pair leaves the caller responsible
   * for reporting how long the render took, and a caller that forgets charges
   * the budget nothing — a bound that silently stops bounding. Wrapping makes
   * the accounting unforgettable, and puts the yield, the cancellation check
   * and the charge in one place instead of three call sites.
   *
   * Never throws: a throwing render becomes `{ status: 'failed' }` so the
   * caller cannot accidentally skip the accounting via an exception path.
   */
  render<T>(fn: () => Promise<T>): Promise<ArchivePdfOutcome<T>>;
  /** Renders that completed. */
  readonly rendered: number;
  /** Renders refused before being attempted. */
  readonly skipped: number;
  /** Renders attempted that threw. */
  readonly failed: number;
  /** Sidecar-milliseconds charged so far. */
  readonly spentMs: number;
}

export interface ArchivePdfBudgetOptions {
  /** The request's signal. When the client disconnects, rendering stops. */
  signal?: AbortSignal;
  budgetMs?: number;
  yieldMs?: number;
  /** Injected for tests — a budget proved with real timers is a slow test. */
  now?: () => number;
  sleep?: (ms: number) => Promise<void>;
}

const realSleep = (ms: number) =>
  new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * Create a per-archive render bound.
 *
 * One per request. The clock starts here, so it is created where the render
 * loop begins rather than at module scope — a shared budget would let one
 * doctor's archive exhaust another's.
 */
export function createArchivePdfBudget(
  options: ArchivePdfBudgetOptions = {},
): ArchivePdfBudget {
  const {
    signal,
    budgetMs = ARCHIVE_PDF_BUDGET_MS,
    yieldMs = ARCHIVE_PDF_YIELD_MS,
    now = () => Date.now(),
    sleep = realSleep,
  } = options;

  let rendered = 0;
  let skipped = 0;
  let failed = 0;
  let spentMs = 0;
  let attempts = 0;

  return {
    get rendered() {
      return rendered;
    },
    get skipped() {
      return skipped;
    },
    get failed() {
      return failed;
    },
    get spentMs() {
      return spentMs;
    },
    async render<T>(fn: () => Promise<T>): Promise<ArchivePdfOutcome<T>> {
      // ⚠️ CANCELLATION IS CHECKED FIRST, AND BEFORE THE YIELD.
      // The archive builders are detached (`void (async () => …)()`), so
      // nothing else stops them: a doctor who cancels a download leaves a loop
      // consuming sidecar slots for every remaining visit, on behalf of a
      // client that is gone.
      if (signal?.aborted) {
        skipped += 1;
        return { status: 'skipped', reason: 'client_disconnected' };
      }

      if (spentMs >= budgetMs) {
        skipped += 1;
        return { status: 'skipped', reason: 'budget_exhausted' };
      }

      // Nothing to yield to before the first attempt — the sidecar has not
      // been touched by this archive yet, so a sleep here is pure latency.
      if (attempts > 0 && yieldMs > 0) {
        await sleep(yieldMs);

        // ⚠️ RE-CHECKED AFTER THE SLEEP, AND THIS IS NOT BELT-AND-BRACES.
        // The yield is the longest await in the loop, so it is exactly where a
        // disconnect lands. Proceeding here would hand a render to a client
        // that vanished while we were being polite.
        if (signal?.aborted) {
          skipped += 1;
          return { status: 'skipped', reason: 'client_disconnected' };
        }
      }

      attempts += 1;
      const startedAt = now();
      try {
        const value = await fn();
        rendered += 1;
        return { status: 'rendered', value };
      } catch (error) {
        failed += 1;
        return { status: 'failed', error };
      } finally {
        // Charged in `finally` so the success path, the throw path and any
        // future early return all pay. A charge that lives on one branch is a
        // charge that a later edit walks around.
        spentMs += now() - startedAt;
      }
    },
  };
}

/**
 * The note an archive writes in place of a signed PDF it did not attempt.
 *
 * ⚠️ SEPARATE FROM `unavailableNote` IN `visit-pdf.ts`, DELIBERATELY, AND THE
 * TWO MUST NOT BE MERGED. That one explains a render that was ATTEMPTED AND
 * FAILED; this one explains a render that was never attempted. Telling a
 * doctor the renderer failed when it was never asked is the wrong-field
 * failure `unavailableNote`'s own docstring was written about — a confident
 * false statement about the cause.
 *
 * Both live beside the mechanism that produces them so neither is edited
 * alone, and both READMEs name both files.
 */
export function skippedNote(visitId: string, reason: ArchivePdfSkip): string {
  const shared =
    `The visit's full record is in visits/${visitId}.json in this archive, ` +
    `and the visit in QuillMD itself is unaffected. Nothing about the visit ` +
    `is missing or wrong.\n`;

  if (reason === 'client_disconnected') {
    return (
      `The signed PDF for this visit was not rendered because the download ` +
      `was cancelled before the archive finished building.\n\n` +
      shared +
      `Request the export again to get a complete archive.\n`
    );
  }

  return (
    `The signed PDF for this visit was not rendered: this archive reached the ` +
    `time limit for rendering PDFs before it reached this visit.\n\n` +
    `This is NOT a renderer failure and NOT a problem with the visit. PDF ` +
    `rendering is shared with every other doctor using QuillMD right now, so ` +
    `one archive is not allowed to occupy it without limit.\n\n` +
    shared +
    `You can download this visit's PDF directly from its page in QuillMD, or ` +
    `export a smaller range and the PDFs will be included.\n`
  );
}
