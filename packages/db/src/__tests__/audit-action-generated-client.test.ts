import { AuditAction } from "@prisma/client";
import { describe, expect, it } from "vitest";

describe("generated Prisma Template Twin audit actions", () => {
  it("exposes the quarantine malware and metadata events used by admission", () => {
    expect(AuditAction.TEMPLATE_TWIN_MALWARE_SCANNED).toBe(
      "TEMPLATE_TWIN_MALWARE_SCANNED",
    );
    expect(AuditAction.TEMPLATE_TWIN_METADATA_MINIMIZED).toBe(
      "TEMPLATE_TWIN_METADATA_MINIMIZED",
    );
  });
});
