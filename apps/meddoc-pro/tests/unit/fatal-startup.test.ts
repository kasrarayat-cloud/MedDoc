import { describe, expect, it, vi } from "vitest";

import { terminateForFatalStartupConfiguration } from "../../src/lib/fatal-startup";

describe("MedDoc Pro fatal production startup boundary", () => {
  it("invokes process exit with a fixed credential-free sentinel", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const exitProcess = vi.fn((code: number): never => {
      expect(code).toBe(1);
      throw new Error("synthetic-process-exit");
    });

    expect(() =>
      terminateForFatalStartupConfiguration(
        new Error("postgresql://user:secret@db/private-clinical-value"),
        exitProcess,
      ),
    ).toThrow("synthetic-process-exit");
    expect(exitProcess).toHaveBeenCalledWith(1);
    expect(consoleSpy).toHaveBeenCalledWith(
      "[startup] fatal runtime configuration rejected; terminating",
      { code: "QUILLMD_FATAL_STARTUP_CONFIGURATION_REJECTED" },
    );
    const rendered = JSON.stringify(consoleSpy.mock.calls);
    expect(rendered).toContain(
      "[startup] fatal runtime configuration rejected; terminating",
    );
    expect(rendered).not.toContain("postgresql://");
    expect(rendered).not.toContain("secret");
    expect(rendered).not.toContain("private-clinical-value");
    expect(rendered).not.toContain("errorType");
    expect(rendered).not.toContain("Error");
    consoleSpy.mockRestore();
  });
});
