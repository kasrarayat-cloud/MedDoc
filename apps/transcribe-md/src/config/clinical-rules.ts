// Clinical-rules version surfaced on expanded RxWarningCard details
// (e.g. "Transcript 14:22 · clinical rules v2.1"). Sourced from env so
// the worker and the UI can be version-bumped in lock-step without a
// code change. Falls back to the shipped default when unset.

export const CLINICAL_RULES_VERSION: string =
  process.env.NEXT_PUBLIC_CLINICAL_RULES_VERSION ?? 'v2.1';
