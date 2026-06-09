// ============================================================================
// E2E helper — out-of-band reads of the Rx clinical-safety state for Batch-4:
// the visit's persisted Rx warnings (TranscribeVisit.rxDrafts) and the
// rx_warning_overrides audit rows that the sign-time gate counts.
// ----------------------------------------------------------------------------
// The source of truth for "is the sign-gate satisfied" is the DB, not the UI:
// the gate at POST /api/visits/[id]/sign filters rxDrafts.warnings for
// severity='critical' and counts rx_warning_overrides rows (severity='critical')
// for the visit. These helpers assert that committed state directly.
//
// Same guarded psql channel as helpers/noteTemplates.ts / seedVisitStates.ts
// (PSQL_BIN in CI; compose exec locally), fail-closed to the qa stack DB.
// ============================================================================

import { execSync } from 'node:child_process';

import { assertNonProdDbName } from '@meddoc/db/guard';

import { QA_COMPOSE as COMPOSE, QA_DB as DB } from './qa-compose';

function psql(sql: string): string {
  const bin = process.env.PSQL_BIN; // CI: full prefix incl. connection string
  if (bin) {
    return execSync(`${bin} -A -t -f -`, {
      input: sql,
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
    }).trim();
  }
  assertNonProdDbName(DB); // fail-closed: never touch a prod DB
  return execSync(`${COMPOSE} exec -T postgres psql -U meddoc -d ${DB} -A -t -f -`, {
    input: sql,
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
  }).trim();
}

function lit(v: string): string {
  return `'${v.replace(/'/g, "''")}'`;
}

/** The visit's lifecycle status (QUEUED…READY|SIGNED|FAILED). */
export function getVisitStatus(visitId: string): string {
  return psql(`SELECT status FROM transcribe_visits WHERE id = ${lit(visitId)};`).trim();
}

/** The severities of the visit's persisted L7c warnings (rxDrafts.warnings[]),
 *  in array order — e.g. ['critical','major','minor', ...]. Lets a spec assert
 *  the warning set (and that exactly one critical was produced). */
export function rxWarningSeverities(visitId: string): string[] {
  const out = psql(
    `SELECT jsonb_array_elements("rxDrafts" -> 'warnings') ->> 'severity' ` +
      `FROM transcribe_visits WHERE id = ${lit(visitId)};`,
  );
  return out ? out.split('\n').filter((l) => l.length > 0) : [];
}

/** Count of rx_warning_overrides rows for the visit at severity='critical' —
 *  exactly what the sign-gate compares against the critical-warning count. */
export function countCriticalOverrides(visitId: string): number {
  return Number(
    psql(
      `SELECT COUNT(*) FROM rx_warning_overrides ` +
        `WHERE "visitId" = ${lit(visitId)} AND severity = 'critical';`,
    ).trim() || '0',
  );
}

/** Insert a fabricated severity='critical' override row DIRECTLY into the DB,
 *  bypassing recordOverride's server-side validation. Simulates the override-
 *  count-inflation attack: a caller minting bogus 'critical' rows whose
 *  `warningId` corresponds to NO real warning on the visit. The hardened sign
 *  gate must not let these clear the critical-warning coverage. `overriddenBy`
 *  is set to the visit's own owner so the row is realistic + the User FK holds.
 *  (fix/rx-override-gate-correlation regression scaffolding.) */
export function seedFabricatedCriticalOverride(
  visitId: string,
  warningId: string,
): void {
  const id = `fab-${visitId}-${warningId}`;
  psql(
    `INSERT INTO rx_warning_overrides ` +
      `(id, "visitId", "rxLineNumber", "warningId", severity, headline, reason, "overriddenBy", "overriddenAt") ` +
      `SELECT ${lit(id)}, ${lit(visitId)}, 1, ${lit(warningId)}, 'critical', ` +
      `'fabricated', 'fabricated inflation row — must not clear the gate', ` +
      `v."userId", NOW() FROM transcribe_visits v WHERE v.id = ${lit(visitId)};`,
  );
}

export interface RxOverrideRow {
  warningId: string;
  /** NB: the OVERRIDE-ROW severity vocabulary is the rail's frozen
   *  'critical' | 'warning' | 'info' (schema.prisma RxWarningOverride.severity),
   *  distinct from rxDrafts.warnings[].severity ('critical' | 'major' | 'minor').
   *  Only 'critical' is common to both — which is all the sign-gate counts. */
  severity: string;
  headline: string;
  reason: string;
}

/** Every rx_warning_overrides row for the visit (the audit trail). Emitted as
 *  one JSON object per row so the free-text `reason`/`headline` columns (which
 *  can contain newlines or pipes) survive the line/column split intact. */
export function getRxOverrides(visitId: string): RxOverrideRow[] {
  const out = psql(
    `SELECT json_build_object(` +
      `'warningId', "warningId", 'severity', severity, 'headline', headline, 'reason', reason)::text ` +
      `FROM rx_warning_overrides WHERE "visitId" = ${lit(visitId)} ORDER BY "overriddenAt" ASC;`,
  );
  if (!out) return [];
  return out
    .split('\n')
    .filter((l) => l.length > 0)
    .map((line) => JSON.parse(line) as RxOverrideRow);
}
