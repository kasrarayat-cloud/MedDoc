// Compatibility export for tooling that still resolves the project-root
// convention. Next 16 resolves src/instrumentation.ts because this app uses
// src/app; keep one implementation so Sentry and the runtime guard cannot
// drift.
export { register } from './src/instrumentation';
