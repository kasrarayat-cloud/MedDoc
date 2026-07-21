import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const appRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const repositoryRoot = resolve(appRoot, "../..");
const fixture = join(
  appRoot,
  "src/lib/template-twin/__tests__/fixtures/runtime-attestation-worker-import.ts",
);
const tsxCli = join(repositoryRoot, "node_modules/tsx/dist/cli.mjs");

function executeWithConfig(configName: string) {
  return spawnSync(
    process.execPath,
    [tsxCli, "--tsconfig", join(appRoot, configName), fixture],
    {
      cwd: appRoot,
      encoding: "utf8",
      env: {
        CI: "true",
        NODE_ENV: "test",
        NO_COLOR: "1",
        PATH: process.env.PATH,
      },
      timeout: 20_000,
    },
  );
}

describe("Template Twin worker server-only boundary", () => {
  it("admits the trusted worker graph without weakening the ordinary Next boundary", () => {
    const worker = executeWithConfig("tsconfig.worker.json");
    expect(worker.error).toBeUndefined();
    expect(worker.signal).toBeNull();
    expect(worker.status, worker.stderr).toBe(0);
    expect(worker.stdout).toBe("WORKER_SERVER_ONLY_BOUNDARY_PASS\n");

    const ordinary = executeWithConfig("tsconfig.json");
    expect(ordinary.error).toBeUndefined();
    expect(ordinary.signal).toBeNull();
    expect(ordinary.status).not.toBe(0);
    expect(ordinary.stderr).toContain(
      "cannot be imported from a Client Component module",
    );
  });

  it("scopes the replacement to the worker entry point and keeps React export conditions unchanged", () => {
    const ordinaryConfig = JSON.parse(
      readFileSync(join(appRoot, "tsconfig.json"), "utf8"),
    ) as { compilerOptions?: { paths?: Record<string, string[]> } };
    const workerConfig = JSON.parse(
      readFileSync(join(appRoot, "tsconfig.worker.json"), "utf8"),
    ) as { compilerOptions?: { paths?: Record<string, string[]> } };
    const runtimeAttestation = readFileSync(
      join(appRoot, "src/lib/template-twin/runtime-attestation.ts"),
      "utf8",
    );
    const workerShim = readFileSync(
      join(appRoot, "src/worker/server-only-runtime.ts"),
      "utf8",
    );
    const packageJson = JSON.parse(
      readFileSync(join(appRoot, "package.json"), "utf8"),
    ) as { scripts?: Record<string, string> };
    const dockerfile = readFileSync(join(appRoot, "Dockerfile.worker"), "utf8");

    expect(runtimeAttestation.startsWith('import "server-only";\n')).toBe(true);
    expect(workerShim).not.toMatch(/^\s*import\s/mu);
    expect(ordinaryConfig.compilerOptions?.paths).toEqual({
      "@/*": ["./src/*"],
    });
    expect(workerConfig.compilerOptions?.paths).toEqual({
      "@/*": ["./src/*"],
      "server-only": ["./src/worker/server-only-runtime.ts"],
    });
    expect(packageJson.scripts?.worker).toBe(
      "tsx --tsconfig tsconfig.worker.json src/worker.ts",
    );
    expect(dockerfile).toContain(
      "COPY apps/transcribe-md/tsconfig.worker.json ./apps/transcribe-md/tsconfig.worker.json",
    );
    expect(dockerfile).toContain(
      'CMD ["npx", "tsx", "--tsconfig", "tsconfig.worker.json", "src/worker.ts"]',
    );
    expect(`${packageJson.scripts?.worker}\n${dockerfile}`).not.toContain(
      "--conditions=react-server",
    );
  });
});
