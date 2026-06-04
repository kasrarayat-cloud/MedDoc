// ============================================================================
// db-guard.test.ts — proves the fail-closed DB guard (QA report F1).
// ----------------------------------------------------------------------------
// The guard must REFUSE every prod-ish / unconfirmable target and proceed
// ONLY for a positively-marked qa/test database. Also exercises the
// `@meddoc/db/guard` subpath export (no Prisma instantiation).
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  assertNonProdDatabase,
  assertNonProdDbName,
  checkNonProdDb,
} from '@meddoc/db/guard';

const PROD = 'postgresql://meddoc:secret@localhost:5432/meddoc?schema=public';
const PROD_CONTAINER = 'postgresql://meddoc:secret@postgres:5432/meddoc?schema=public';
const PROD_HOST = 'postgresql://meddoc:secret@5.231.107.93:5432/meddoc_qa_test';
const QA = 'postgresql://meddoc:qa_test_pw@postgres:5432/meddoc_qa_test?schema=public';

describe('db-guard — fail-closed (F1)', () => {
  it('REFUSES the production database name (localhost)', () => {
    expect(() => assertNonProdDatabase(PROD)).toThrow(/FAIL-CLOSED/);
  });

  it('REFUSES the production database name (compose host "postgres")', () => {
    expect(() => assertNonProdDatabase(PROD_CONTAINER)).toThrow(/production database name/);
  });

  it('REFUSES the production VPS host even with a qa-marked db name', () => {
    expect(() => assertNonProdDatabase(PROD_HOST)).toThrow(/production VPS/);
  });

  it('REFUSES an unset DATABASE_URL (fail-closed)', () => {
    expect(() => assertNonProdDatabase(undefined)).toThrow(/DATABASE_URL is not set/);
    expect(() => assertNonProdDatabase('')).toThrow(/DATABASE_URL is not set/);
  });

  it('REFUSES an unparseable URL', () => {
    expect(() => assertNonProdDatabase('not-a-url')).toThrow(/parseable/);
  });

  it('REFUSES a marker-less db name (cannot confirm non-prod)', () => {
    expect(() => assertNonProdDatabase('postgresql://u:p@db:5432/production')).toThrow(/lacks a qa\/test\/e2e\/ci marker/);
    expect(() => assertNonProdDatabase('postgresql://u:p@db:5432/meddoc_live')).toThrow(/FAIL-CLOSED/);
  });

  it('PROCEEDS for a positively-marked qa database', () => {
    expect(() => assertNonProdDatabase(QA)).not.toThrow();
    const t = assertNonProdDatabase(QA);
    expect(t.database).toBe('meddoc_qa_test');
  });

  it('accepts other explicit qa/test/e2e/ci markers', () => {
    for (const db of ['qa', 'test', 'meddoc_e2e', 'ci_db', 'transcribe-qa', 'meddoc_test']) {
      expect(checkNonProdDb(db).ok, db).toBe(true);
    }
  });

  it('rejects look-alikes that are not whole-word markers', () => {
    for (const db of ['meddoc', 'meddocqa', 'testimony_db', 'latest']) {
      expect(checkNonProdDb(db).ok, db).toBe(false);
    }
  });

  describe('assertNonProdDbName (psql cleanup path)', () => {
    it('REFUSES the prod db name', () => {
      expect(() => assertNonProdDbName('meddoc')).toThrow(/production database name/);
    });
    it('PROCEEDS for the qa db name', () => {
      expect(() => assertNonProdDbName('meddoc_qa_test')).not.toThrow();
    });
  });
});
