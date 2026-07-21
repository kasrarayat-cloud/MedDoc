type ExitProcess = (code: number) => never;

/**
 * Next standalone may retain its listener after instrumentation rejects. A
 * release-critical startup error therefore terminates explicitly and logs only
 * a fixed sentinel and fixed code, never error metadata or credentials.
 */
export function terminateForFatalStartupConfiguration(
  error: unknown,
  exitProcess: ExitProcess = process.exit,
): never {
  void error;
  console.error("[startup] fatal runtime configuration rejected; terminating", {
    code: "QUILLMD_FATAL_STARTUP_CONFIGURATION_REJECTED",
  });
  return exitProcess(1);
}
