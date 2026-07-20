import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

const mocks = vi.hoisted(() => ({
  send: vi.fn(),
  logApiUsage: vi.fn(),
  buildResendUsage: vi.fn(() => ({ provider: "resend" })),
}));

vi.mock("resend", () => ({
  Resend: class {
    emails = { send: mocks.send };
  },
}));

vi.mock("@meddoc/ai", () => ({
  logApiUsage: mocks.logApiUsage,
  buildResendUsage: mocks.buildResendUsage,
}));

import {
  sendAccountDeletedConfirmation,
  sendAccountExistsEmail,
  sendEmailChangedNotification,
  sendEmailChangeRequestEmail,
  sendEmailVerification,
  sendPasswordResetEmail,
} from "@/lib/email";

const HOSTILE_NAME = `Synthetic <img src=x onerror="boom"> & '`;
const HOSTILE_URL = `https://app.quillmd.com/auth?token=a&next="><script>alert(1)</script>&quote='`;

let previousApiKey: string | undefined;

beforeAll(() => {
  previousApiKey = process.env.RESEND_API_KEY;
  process.env.RESEND_API_KEY = "synthetic-test-key";
});

afterAll(() => {
  if (previousApiKey === undefined) delete process.env.RESEND_API_KEY;
  else process.env.RESEND_API_KEY = previousApiKey;
});

beforeEach(() => {
  vi.clearAllMocks();
  mocks.send.mockResolvedValue({
    data: { id: "synthetic-delivery" },
    error: null,
  });
});

function lastHtml(): string {
  const message = mocks.send.mock.calls.at(-1)?.[0] as
    | { html?: unknown }
    | undefined;
  expect(message?.html).toEqual(expect.any(String));
  return String(message?.html);
}

function expectHostileNameEscaped(html: string): void {
  expect(html).not.toContain("<img");
  expect(html).toContain(
    "Synthetic &lt;img src=x onerror=&quot;boom&quot;&gt; &amp; &#39;",
  );
}

function expectHostileUrlEscaped(html: string): void {
  expect(html).not.toContain("<script>alert(1)</script>");
  expect(html).toContain(
    `href="https://app.quillmd.com/auth?token=a&amp;next=&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;&amp;quote=&#39;"`,
  );
}

describe("transactional email HTML escaping", () => {
  it.each([
    [
      "password reset",
      () =>
        sendPasswordResetEmail({
          toEmail: "doctor@synthetic.invalid",
          resetUrl: HOSTILE_URL,
          userName: HOSTILE_NAME,
        }),
    ],
    [
      "email verification",
      () =>
        sendEmailVerification({
          toEmail: "doctor@synthetic.invalid",
          verifyUrl: HOSTILE_URL,
          userName: HOSTILE_NAME,
        }),
    ],
    [
      "account exists",
      () =>
        sendAccountExistsEmail({
          toEmail: "doctor@synthetic.invalid",
          signInUrl: HOSTILE_URL,
          userName: HOSTILE_NAME,
        }),
    ],
    [
      "email change request",
      () =>
        sendEmailChangeRequestEmail({
          toEmail: "doctor@synthetic.invalid",
          confirmUrl: HOSTILE_URL,
          userName: HOSTILE_NAME,
        }),
    ],
  ])("escapes names and link attributes in %s HTML", async (_label, send) => {
    await send();
    const html = lastHtml();

    expectHostileNameEscaped(html);
    expectHostileUrlEscaped(html);
  });

  it("escapes the greeting and replacement address in email-change notices", async () => {
    await sendEmailChangedNotification({
      toEmail: "doctor@synthetic.invalid",
      newEmail: `<script>changed&"'</script>`,
      userName: HOSTILE_NAME,
    });
    const html = lastHtml();

    expectHostileNameEscaped(html);
    expect(html).not.toContain("<script>changed");
    expect(html).toContain(
      "&lt;script&gt;changed&amp;&quot;&#39;&lt;/script&gt;",
    );
  });

  it("escapes the greeting in account-deletion confirmations", async () => {
    await sendAccountDeletedConfirmation({
      toEmail: "doctor@synthetic.invalid",
      userName: HOSTILE_NAME,
    });

    expectHostileNameEscaped(lastHtml());
  });
});
