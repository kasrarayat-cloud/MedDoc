// ============================================================================
// Tiny structured-log wrapper (T-M16.4 M9)
// ----------------------------------------------------------------------------
// Writes one JSON object per line to stdout. Humans grepping Docker
// logs still see readable output because the common fields (ts, level,
// scope, message) stay in a predictable order; log aggregators
// (Loki / Datadog / Vector) get cleanly-parseable events without any
// custom decoder.
//
// Scope is reserved for forward migration — NOT a full pino-style
// replacement. Most existing console.* calls stay as-is; this helper
// covers the high-volume lifecycle + milestone logs that a future log
// pipeline would want indexed. See commit notes for the exact call
// sites migrated in T-M16.4.
//
// NOTE: beforeSend in Sentry's init already scrubs via redactPhi on
// anything it captures from console output. This wrapper does NOT
// re-redact — callers pass only known-safe fields into `data`. If a
// value might carry PHI, redactPhi it before passing.
// ============================================================================

type Level = 'debug' | 'info' | 'warn' | 'error';

interface LogPayload {
  ts: string;
  level: Level;
  scope: string;
  message: string;
  [k: string]: unknown;
}

function emit(
  level: Level,
  scope: string,
  message: string,
  data?: Record<string, unknown>
): void {
  const payload: LogPayload = {
    ts: new Date().toISOString(),
    level,
    scope,
    message,
    ...data,
  };
  const serialized = JSON.stringify(payload);
  // Preserve stderr-vs-stdout routing — Docker + systemd treat them
  // differently, and Sentry's console integration keys on level.
  if (level === 'error') console.error(serialized);
  else if (level === 'warn') console.warn(serialized);
  else if (level === 'info') console.info(serialized);
  else console.log(serialized);
}

export const log = {
  debug: (scope: string, message: string, data?: Record<string, unknown>) =>
    emit('debug', scope, message, data),
  info: (scope: string, message: string, data?: Record<string, unknown>) =>
    emit('info', scope, message, data),
  warn: (scope: string, message: string, data?: Record<string, unknown>) =>
    emit('warn', scope, message, data),
  error: (scope: string, message: string, data?: Record<string, unknown>) =>
    emit('error', scope, message, data),
};
