// ============================================================================
// Real-model eval — capture helpers.
// ----------------------------------------------------------------------------
// Reads the committed generated note (soapFinal / rxDrafts / transcriptText)
// straight from the qa DB (the source of truth — not DOM-scraped) via the same
// guarded psql channel as helpers/rxSafety.ts, and writes a paired artifact
// (source transcript + model output) per encounter for the judge to score.
// Everything here is synthetic (no PHI). Fail-closed to the qa DB.
// ============================================================================

import { execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

import { assertNonProdDbName } from '@meddoc/db/guard';

import { QA_COMPOSE as COMPOSE, QA_DB as DB } from '../helpers/qa-compose';

// Playwright transpiles specs to CJS, so avoid import.meta. The eval always
// runs from apps/transcribe-md → derive the artifact dir from cwd.
const ARTIFACT_DIR = path.resolve(process.cwd(), 'tests/e2e/real-model-eval/artifacts');

function psql(sql: string): string {
  const bin = process.env.PSQL_BIN;
  if (bin) {
    return execSync(`${bin} -A -t -f -`, { input: sql, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
  }
  assertNonProdDbName(DB);
  return execSync(`${COMPOSE} exec -T postgres psql -U meddoc -d ${DB} -A -t -f -`, {
    input: sql,
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
  }).trim();
}

function lit(v: string): string {
  return `'${v.replace(/'/g, "''")}'`;
}

export interface CapturedVisit {
  status: string;
  soapFinal: string | null;
  transcriptText: string | null;
  rxDrafts: unknown;
  noteTemplateId: string | null;
}

/** Read the committed generated note + Rx + transcript for a visit. */
export function captureVisit(visitId: string): CapturedVisit {
  const out = psql(
    `SELECT json_build_object(` +
      `'status', status, 'soapFinal', "soapFinal", 'transcriptText', "transcriptText", ` +
      `'rxDrafts', "rxDrafts", 'noteTemplateId', "noteTemplateId")::text ` +
      `FROM transcribe_visits WHERE id = ${lit(visitId)};`,
  );
  if (!out) throw new Error(`captureVisit: no visit row for ${visitId}`);
  return JSON.parse(out) as CapturedVisit;
}

/** The AiCall model(s) actually used for a visit (proves which model generated it). */
export function visitModels(visitId: string): string[] {
  const out = psql(
    `SELECT DISTINCT model FROM ai_calls WHERE "visitId" = ${lit(visitId)} ORDER BY model;`,
  );
  return out ? out.split('\n').filter((l) => l.length > 0) : [];
}

/** Write a paired artifact (source transcript + model output) for the judge. */
export function writeArtifact(
  label: string,
  encounterId: string,
  payload: Record<string, unknown>,
): string {
  const dir = path.join(ARTIFACT_DIR, label);
  mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${encounterId}.json`);
  writeFileSync(file, JSON.stringify(payload, null, 2), 'utf8');
  return file;
}
