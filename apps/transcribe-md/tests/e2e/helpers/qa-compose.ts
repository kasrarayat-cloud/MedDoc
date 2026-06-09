// ============================================================================
// Shared resolution of the isolated meddoc-qa stack's docker compose invocation.
// ----------------------------------------------------------------------------
// Used by every e2e helper that needs out-of-band access to the qa stack
// (cleanup → Postgres, seedVisitStates → Postgres, reset-token capture → app
// logs).
//
// The compose file is referenced RELATIVE to the Playwright process CWD, which
// is `apps/transcribe-md` both locally (`cd apps/transcribe-md && playwright
// test`) and in CI (`working-directory: apps/transcribe-md` in e2e.yml). An
// absolute `/opt/meddoc-pro/...` path only exists on the VPS, NOT on the CI
// runner — using it there makes the shell-out fail (cleanup was silently a
// no-op in CI for exactly this reason). The qa compose pins `name: meddoc-qa`,
// so the project resolves the same regardless of CWD once the `-f` path is
// correct.
//
// Overridable via E2E_QA_COMPOSE for other isolated environments.
// ============================================================================

export const QA_COMPOSE =
  process.env.E2E_QA_COMPOSE ?? 'docker compose -f ../../docker-compose.qa.yml';

/** Default qa database name. The fail-closed @meddoc/db/guard refuses anything
 *  that isn't positively a non-prod (qa/test-marked) database. */
export const QA_DB = process.env.E2E_QA_DB ?? 'meddoc_qa_test';
