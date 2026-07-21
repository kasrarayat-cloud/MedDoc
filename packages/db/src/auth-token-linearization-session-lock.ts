import type { Pool, PoolClient } from "pg";

export const AUTH_TOKEN_OPERATOR_SESSION_LOCK_KEY =
  "quillmd_auth_token_linearization_online_v1";

export interface AuthTokenOperatorSessionLock {
  release(): Promise<void>;
}

async function acquireOnConnection(
  connection: PoolClient,
  releaseConnection: boolean,
): Promise<AuthTokenOperatorSessionLock> {
  let held = false;
  let result: { rows: Array<{ acquired: boolean }> };
  try {
    result = await connection.query<{ acquired: boolean }>(
      `SELECT pg_try_advisory_lock(hashtextextended($1, 0)) AS "acquired"`,
      [AUTH_TOKEN_OPERATOR_SESSION_LOCK_KEY],
    );
  } catch {
    // The server may have acquired the session lock before the transport
    // failed. A borrowed connection must be destroyed instead of returned to
    // its pool. A retained operator connection is closed by its owner.
    if (releaseConnection) connection.release(true);
    throw new Error("AUTH_TOKEN_LINEARIZATION_LOCK_ACQUIRE_FAILED");
  }
  if (result.rows[0]?.acquired === false) {
    if (releaseConnection) connection.release();
    throw new Error("AUTH_TOKEN_LINEARIZATION_OPERATOR_BUSY");
  }
  if (result.rows[0]?.acquired !== true) {
    if (releaseConnection) connection.release(true);
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
      // returned to the pool where a session-scoped lock could survive. The
      // retained-client caller owns its final connection destruction.
      if (releaseConnection) {
        connection.release(releaseError ? true : undefined);
      }
      if (releaseError) throw releaseError;
    },
  };
}

/** Bind the advisory lock to the already target-proved mutation session. */
export async function acquireAuthTokenOperatorSessionLockOnClient(
  connection: PoolClient,
): Promise<AuthTokenOperatorSessionLock> {
  return acquireOnConnection(connection, false);
}

/** Compatibility wrapper for callers that deliberately borrow a session. */
export async function acquireAuthTokenOperatorSessionLock(
  pool: Pool,
): Promise<AuthTokenOperatorSessionLock> {
  const connection = await pool.connect();
  return acquireOnConnection(connection, true);
}
