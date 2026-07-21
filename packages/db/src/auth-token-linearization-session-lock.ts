import type { Pool } from "pg";

export const AUTH_TOKEN_OPERATOR_SESSION_LOCK_KEY =
  "quillmd_auth_token_linearization_online_v1";

export async function acquireAuthTokenOperatorSessionLock(pool: Pool): Promise<{
  release(): Promise<void>;
}> {
  const connection = await pool.connect();
  let held = false;
  let result: { rows: Array<{ acquired: boolean }> };
  try {
    result = await connection.query<{ acquired: boolean }>(
      `SELECT pg_try_advisory_lock(hashtextextended($1, 0)) AS "acquired"`,
      [AUTH_TOKEN_OPERATOR_SESSION_LOCK_KEY],
    );
  } catch {
    // The server may have acquired the session lock before the transport
    // failed. Destroy the uncertain session instead of returning it to pool.
    connection.release(true);
    throw new Error("AUTH_TOKEN_LINEARIZATION_LOCK_ACQUIRE_FAILED");
  }
  if (result.rows[0]?.acquired === false) {
    connection.release();
    throw new Error("AUTH_TOKEN_LINEARIZATION_OPERATOR_BUSY");
  }
  if (result.rows[0]?.acquired !== true) {
    connection.release(true);
    throw new Error("AUTH_TOKEN_LINEARIZATION_LOCK_ACQUIRE_FAILED");
  }
  held = true;

  return {
    release: async () => {
      if (!held) return;
      held = false;
      let releaseError: Error | undefined;
      try {
        const result = await connection.query<{ released: boolean }>(
          `SELECT pg_advisory_unlock(hashtextextended($1, 0)) AS "released"`,
          [AUTH_TOKEN_OPERATOR_SESSION_LOCK_KEY],
        );
        if (result.rows[0]?.released !== true) {
          releaseError = new Error(
            "AUTH_TOKEN_LINEARIZATION_LOCK_RELEASE_FAILED",
          );
        }
      } catch {
        releaseError = new Error(
          "AUTH_TOKEN_LINEARIZATION_LOCK_RELEASE_FAILED",
        );
      }
      // A connection whose unlock result is uncertain must be destroyed, not
      // returned to the pool where a session-scoped lock could survive.
      connection.release(releaseError ? true : undefined);
      if (releaseError) throw releaseError;
    },
  };
}
