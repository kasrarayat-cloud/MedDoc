import { describe, expect, it, vi } from "vitest";

import { acquireAuthTokenOperatorSessionLock } from "./auth-token-linearization-session-lock";
import type { Pool } from "pg";

describe("auth-token online operator session lock", () => {
  it("destroys a connection after an uncertain acquire result", async () => {
    const release = vi.fn();
    const pool = {
      connect: vi.fn().mockResolvedValue({
        query: vi.fn().mockRejectedValue(new Error("synthetic transport loss")),
        release,
      }),
    } as unknown as Pool;

    await expect(acquireAuthTokenOperatorSessionLock(pool)).rejects.toThrow(
      "AUTH_TOKEN_LINEARIZATION_LOCK_ACQUIRE_FAILED",
    );
    expect(release).toHaveBeenCalledWith(true);
  });

  it("returns a known-busy connection normally", async () => {
    const release = vi.fn();
    const pool = {
      connect: vi.fn().mockResolvedValue({
        query: vi.fn().mockResolvedValue({ rows: [{ acquired: false }] }),
        release,
      }),
    } as unknown as Pool;

    await expect(acquireAuthTokenOperatorSessionLock(pool)).rejects.toThrow(
      "AUTH_TOKEN_LINEARIZATION_OPERATOR_BUSY",
    );
    expect(release).toHaveBeenCalledWith();
  });

  it("destroys a connection whose unlock outcome is uncertain", async () => {
    const release = vi.fn();
    const query = vi
      .fn()
      .mockResolvedValueOnce({ rows: [{ acquired: true }] })
      .mockRejectedValueOnce(new Error("synthetic unlock failure"));
    const pool = {
      connect: vi.fn().mockResolvedValue({ query, release }),
    } as unknown as Pool;

    const lock = await acquireAuthTokenOperatorSessionLock(pool);
    await expect(lock.release()).rejects.toThrow(
      "AUTH_TOKEN_LINEARIZATION_LOCK_RELEASE_FAILED",
    );
    expect(release).toHaveBeenCalledWith(true);
  });

  it("returns a definitely unlocked connection normally", async () => {
    const release = vi.fn();
    const query = vi
      .fn()
      .mockResolvedValueOnce({ rows: [{ acquired: true }] })
      .mockResolvedValueOnce({ rows: [{ released: true }] });
    const pool = {
      connect: vi.fn().mockResolvedValue({ query, release }),
    } as unknown as Pool;

    const lock = await acquireAuthTokenOperatorSessionLock(pool);
    await lock.release();
    expect(release).toHaveBeenCalledWith(undefined);
  });
});
