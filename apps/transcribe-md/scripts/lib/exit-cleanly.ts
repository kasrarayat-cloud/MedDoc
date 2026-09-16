/**
 * exitCleanly / runCli — make a ruled-act CLI EXIT once its work is done, and
 * ANNOUNCE that completion so the door can tell "finished and lingering" from
 * "busy and quiet".
 *
 * 2026-09-15: the RULING C colon-note certify script printed its whole
 * transcript through "[323] DONE" and then hung for 5h24m, held alive by an
 * open pg pool handle, because its success path never called process.exit().
 * The mutation door (scripts/run-ruled-mutation.sh) waited on it in silence.
 *
 * Two fixes, two layers:
 *   · the DOOR now times out with a reason        → scripts/lib/run-watched.sh
 *   · the SCRIPT now exits on its own (this file)  so the timeout is never hit.
 *
 * A bare process.exit() can TRUNCATE a piped/redirected transcript — the last
 * lines are the ones a judge reads — so we flush stdout+stderr first, with a
 * short hard-exit backstop so a stuck flush can never reintroduce the hang.
 *
 * The sentinel: printed as the FIRST thing exitCleanly does. The door only
 * fast-kills a quiet, still-alive process AFTER it has seen this line — proof
 * the script reached its own end rather than being merely slow. Without it the
 * door refuses to kill on silence and lets the wall-clock ceiling decide, so a
 * healthy in-flight irreversible act is never SIGKILLed mid-transaction.
 */

/**
 * ⚠️ ONE RULE, TWO READERS: this literal MUST equal `RUN_WATCHED_SENTINEL_DEFAULT`
 * in scripts/lib/run-watched.sh. The gate asserts both files carry it.
 */
export const RULED_ACT_COMPLETE_SENTINEL = '__RULED_ACT_COMPLETE__';

/** Flush stdout/stderr, then hard-exit `code`. Never returns. */
export function exitCleanly(code: number): never {
  // Announce completion BEFORE exiting, so the door's fast-kill has its proof.
  process.stdout.write(`${RULED_ACT_COMPLETE_SENTINEL} rc=${code}\n`);

  // Backstop: exit even if a flush callback never fires. `unref` so the timer
  // itself does not keep the loop alive in the (normal) fast-flush case.
  const backstop = setTimeout(() => process.exit(code), 2000);
  (backstop as { unref?: () => void }).unref?.();

  let pending = 2;
  const done = (): void => {
    pending -= 1;
    if (pending === 0) {
      clearTimeout(backstop);
      process.exit(code);
    }
  };
  // Empty writes whose callbacks fire once prior buffered output has drained.
  process.stdout.write('', done);
  process.stderr.write('', done);

  // process.exit above ends the process; this satisfies the `never` return.
  return undefined as never;
}

/**
 * Run a ruled-act CLI `main()`: exit 0 on success, 1 on failure — always
 * explicitly, so an open pg pool / minio / redis handle cannot keep the
 * process alive after the work is done.
 */
export function runCli(main: () => Promise<unknown>): void {
  main().then(
    () => exitCleanly(0),
    (err: unknown) => {
      const e = err as { stack?: string; message?: string } | undefined;
      console.error(e?.stack ?? e?.message ?? err);
      exitCleanly(1);
    },
  );
}
