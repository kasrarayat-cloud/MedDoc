import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ getToken: vi.fn() }));

vi.mock("next-auth/jwt", () => ({ getToken: mocks.getToken }));
vi.mock("@meddoc/auth", () => ({
  authConfig: { secret: "synthetic-test-secret" },
}));

import { readSignedSessionAuthority } from "../signed-session-authority";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getToken.mockResolvedValue({
    id: "user-synthetic",
    sub: "user-synthetic",
    sessionId: "session-synthetic",
  });
});

describe("signed session authority", () => {
  it("does not consult the decoder when no session cookie exists", async () => {
    await expect(
      readSignedSessionAuthority(new Headers({ cookie: "other=value" })),
    ).resolves.toEqual({
      cookiePresent: false,
      sessionId: null,
      userId: null,
    });
    expect(mocks.getToken).not.toHaveBeenCalled();
  });

  it("decodes a chunked signed cookie without database-backed auth", async () => {
    const headers = new Headers({
      cookie: "authjs.session-token.0=part-one; authjs.session-token.1=part-two",
    });

    await expect(readSignedSessionAuthority(headers)).resolves.toEqual({
      cookiePresent: true,
      sessionId: "session-synthetic",
      userId: "user-synthetic",
    });
    expect(mocks.getToken).toHaveBeenCalledWith(
      expect.objectContaining({
        req: { headers },
        cookieName: "authjs.session-token",
        secureCookie: false,
        secret: "synthetic-test-secret",
      }),
    );
  });

  it("fails closed when signed user identifiers disagree", async () => {
    mocks.getToken.mockResolvedValue({
      id: "user-one",
      sub: "user-two",
      sessionId: "session-synthetic",
    });

    await expect(
      readSignedSessionAuthority(
        new Headers({ cookie: "authjs.session-token=synthetic" }),
      ),
    ).resolves.toEqual({
      cookiePresent: true,
      sessionId: "session-synthetic",
      userId: null,
    });
  });

  it("retains cookie presence when signature decoding fails", async () => {
    mocks.getToken.mockResolvedValue(null);

    await expect(
      readSignedSessionAuthority(
        new Headers({ cookie: "authjs.session-token=synthetic" }),
      ),
    ).resolves.toEqual({
      cookiePresent: true,
      sessionId: null,
      userId: null,
    });
  });
});
