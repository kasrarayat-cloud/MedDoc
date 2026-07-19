type ExitProcess = (code: number) => never;

/**
 * Next standalone currently keeps its listener alive after a rejected
 * instrumentation promise. Release-critical configuration errors therefore
 * terminate the Node process explicitly. The log is fixed and never includes
 * the caught error message, which may contain configuration values.
 */
export function terminateForFatalStartupConfiguration(
  error: unknown,
  exitProcess: ExitProcess = process.exit,
): never {
  console.error("[startup] fatal runtime configuration rejected; terminating", {
    errorType: error instanceof Error ? error.name : "UnknownError",
  });
  return exitProcess(1);
}
