import type { Pool } from "pg";

export const LINEAGE_OPERATOR_SESSION_LOCK_KEY =
  "template_twin_note_templates_lineage_operator_session_v1";

export interface LineageOperatorSessionLock {
  release(): Promise<void>;
}

/**
 * Hold a PostgreSQL session advisory lock across standalone
 * CREATE/DROP INDEX CONCURRENTLY and VALIDATE statements. A transaction lock
 * cannot span those autocommit statements. We fail immediately instead of
 * allowing two GUARDING/INDEXING/VALIDATING operators to overlap.
 */
export async function acquireLineageOperatorSessionLock(
  pool: Pool,
): Promise<LineageOperatorSessionLock> {
  const connection = await pool.connect();
  let held = false;
  try {
    const result = await connection.query<{ acquired: boolean }>(
      `SELECT pg_try_advisory_lock(hashtextextended($1, 0)) AS "acquired"`,
      [LINEAGE_OPERATOR_SESSION_LOCK_KEY],
    );
    held = result.rows[0]?.acquired === true;
    if (!held) throw new Error("LINEAGE_MIGRATION_OPERATOR_BUSY");
  } catch (error) {
    connection.release();
    throw error;
  }

  return {
    release: async () => {
      if (!held) return;
      held = false;
      try {
        const result = await connection.query<{ released: boolean }>(
          `SELECT pg_advisory_unlock(hashtextextended($1, 0)) AS "released"`,
          [LINEAGE_OPERATOR_SESSION_LOCK_KEY],
        );
        if (result.rows[0]?.released !== true) {
          throw new Error("LINEAGE_MIGRATION_OPERATOR_LOCK_RELEASE_FAILED");
        }
      } finally {
        connection.release();
      }
    },
  };
}
