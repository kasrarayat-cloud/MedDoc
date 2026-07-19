/** Client-safe reviewed values for the synthetic staging worksheet. */
export const TEMPLATE_TWIN_STAGING_QA_STATIC_INTENT_REASON =
  "Physician marked this reviewed synthetic fixture field as intentionally static." as const;

/**
 * Reviewed, closed-grammar evidence for the byte-allowlisted staging fixture.
 *
 * Keep this client-safe module free of server/provider imports: it is consumed
 * by the certification workspace. A fixture regression test pins this value to
 * the provider-side transcript so UI drift fails before a browser can offer
 * evidence that the deterministic provider would reject.
 */
export const TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER =
  "Chief concern is synthetic wrist discomfort. Synthetic wrist discomfort began on 2099-07-16 with Moderate severity and context Explicit synthetic detail. Smoking status is Current. Respiratory review confirms synthetic cough. Encounter category is Follow-up. Medication Syntheticmed documented. Plan use synthetic brace. Plan detail is synthetic brace at night. Additional synthetic detail is synthetic follow-up tolerated well." as const;
