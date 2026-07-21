/**
 * Trusted plain-Node worker replacement for Next's compile-time
 * `server-only` marker. Only tsconfig.worker.json maps the marker here; the
 * ordinary Next graph keeps the real poison pill so client imports still fail.
 */
export {};
