/**
 * Immutable byte identity for the reviewed synthetic staging fixture.
 *
 * Keep this module dependency-free: admission and signing guards import it in
 * server paths that must not load the fixture builder or provider transcript.
 */
export const TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 =
  "9c917a831e661d5fdcf92a6e13cbc542adda9fb86a2292cf34689fc333c375d4" as const;

export const TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES = 4_686 as const;
