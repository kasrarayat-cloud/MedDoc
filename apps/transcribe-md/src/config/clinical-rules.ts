// Clinical-rules version. Surfaced on the expanded Rx warning card until owner
// ruling #109 deleted that surface; the version itself is still stamped on the
// extracted warnings, which the ruling left untouched.
// (e.g. "Transcript 14:22 · clinical rules v2.1"). Sourced from env so
// the worker and the UI can be version-bumped in lock-step without a
// code change. Falls back to the shipped default when unset.

export const CLINICAL_RULES_VERSION: string =
  process.env.NEXT_PUBLIC_CLINICAL_RULES_VERSION ?? 'v2.1';
