import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "../../../..");
const ENTRYPOINT = path.join(
  ROOT,
  "scripts/quillmd-next-runtime-entrypoint.mjs",
);

describe("immutable Next production runtime entrypoint", () => {
  it("rejects the build-only phase before starting a server child", () => {
    const result = spawnSync(
      process.execPath,
      [ENTRYPOINT, process.execPath, "-e", "process.stdout.write('started')"],
      {
        encoding: "utf8",
        env: {
          ...process.env,
          NEXT_PHASE: "phase-production-build",
          SYNTHETIC_SENSITIVE_VALUE: "must-not-be-rendered",
        },
      },
    );

    expect(result.status).toBe(78);
    expect(result.stdout).toBe("");
    expect(result.stderr).toContain("QUILLMD_RUNTIME_ENTRYPOINT_REJECTED");
    expect(result.stderr).not.toContain("must-not-be-rendered");
  });

  it("starts the exact child when no build-only phase is retained", () => {
    const result = spawnSync(
      process.execPath,
      [ENTRYPOINT, process.execPath, "-e", "process.stdout.write('started')"],
      {
        encoding: "utf8",
        env: { ...process.env, NEXT_PHASE: "phase-production-server" },
      },
    );

    expect(result.status).toBe(0);
    expect(result.stdout).toBe("started");
    expect(result.stderr).toBe("");
  });

  it("is the immutable command in both app images and package start paths", () => {
    for (const relative of [
      "apps/transcribe-md/Dockerfile",
      "apps/meddoc-pro/Dockerfile",
      "apps/transcribe-md/package.json",
      "apps/meddoc-pro/package.json",
    ]) {
      expect(readFileSync(path.join(ROOT, relative), "utf8")).toContain(
        "quillmd-next-runtime-entrypoint.mjs",
      );
    }
  });
});
