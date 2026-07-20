import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const dispatcher = readFileSync(
  resolve(process.cwd(), "src/auth-email-dispatcher.ts"),
  "utf8",
);
const delivery = readFileSync(
  resolve(process.cwd(), "src/lib/auth-email-delivery.ts"),
  "utf8",
);

describe("authentication email dispatcher source contract", () => {
  it("claims only immediate serial capacity and wires progress to liveness", () => {
    expect(dispatcher).toMatch(/limit:\s*1,/u);
    expect(dispatcher).toContain("onProgress: writeHeartbeat");
    expect(dispatcher).toMatch(
      /const result = await drainAuthEmailOutbox\([\s\S]*?\}\);\s*\/\/ Keep the empty-queue case explicit:[\s\S]*?await writeHeartbeat\(\);/u,
    );
    expect(dispatcher).toContain(
      'const HEARTBEAT_PATH = "/tmp/auth-email-dispatcher-heartbeat"',
    );
    expect(dispatcher).toContain("await assertDispatcherDatabasePrincipal()");
    expect(dispatcher).toContain(
      'const PRODUCTION_APP_URL = "https://app.quillmd.com"',
    );
  });

  it("keeps provider execution single-shot, bounded, and idempotent", () => {
    expect(delivery).toContain("const PROVIDER_TIMEOUT_MS = 30_000");
    expect(delivery).toContain("idempotencyKey: `auth-email-${requestId}`");
    expect(delivery).toContain("await withProviderTimeout(");
    expect(delivery).toContain("providerReceiptHash(providerId)");
    expect(delivery).toContain('errorCode: "AUTH_EMAIL_PROVIDER_AMBIGUOUS"');
    expect(delivery).not.toMatch(/console\.|process\.(?:stdout|stderr)/u);
  });

  it("never includes recipient or bearer identifiers in dispatcher logs", () => {
    expect(dispatcher).not.toMatch(
      /\b(?:recipientEmail|requestId|claimToken|tokenId|rawToken)\b/u,
    );
    expect(dispatcher).not.toContain("error.message");
    expect(dispatcher).not.toContain("String(error)");
    expect(dispatcher).toContain('code: "AUTH_EMAIL_DISPATCH_FAILED"');
    expect(dispatcher).toContain(
      'code: "AUTH_EMAIL_PROVIDER_OUTCOME_AMBIGUOUS"',
    );
  });
});
