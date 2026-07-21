import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cleanup,
  type SyntheticState,
} from "../scripts/synthetic-ci-database-release";

vi.mock("node:child_process", () => {
  const mockedModule = { spawnSync: vi.fn() };
  return { ...mockedModule, default: mockedModule };
});

const spawnSyncMock = vi.mocked(spawnSync);
const token = "0123456789abcdef01234567";

function dockerResult(status: number, stdout = "", stderr = "") {
  return {
    pid: 123,
    output: [null, stdout, stderr],
    stdout,
    stderr,
    status,
    signal: null,
  } as never;
}

describe("synthetic CI database cleanup failure semantics", () => {
  let runnerTemp: string;
  let statePath: string;
  let temporaryDirectory: string;
  let state: SyntheticState;
  let stdoutWrite: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    runnerTemp = mkdtempSync(join(tmpdir(), "quillmd-cleanup-unit-"));
    statePath = join(runnerTemp, "quillmd-synthetic-ci-database-state-v1.json");
    temporaryDirectory = join(runnerTemp, "quillmd-synthetic-ci-" + token);
    mkdirSync(temporaryDirectory, { mode: 0o700 });
    state = {
      version: "quillmd-synthetic-ci-database-state-v1",
      token,
      containerName: "quillmd-synthetic-ci-postgres-" + token,
      volumeName: "quillmd-synthetic-ci-pgdata-" + token,
      imageTag: "quillmd-synthetic-ci-postgres:" + token,
      temporaryDirectory,
      ready: true,
    };
    writeFileSync(statePath, JSON.stringify(state) + "\n", { mode: 0o600 });
    stdoutWrite = vi
      .spyOn(process.stdout, "write")
      .mockImplementation(() => true);
  });

  afterEach(() => {
    stdoutWrite.mockRestore();
    spawnSyncMock.mockReset();
    rmSync(runnerTemp, { recursive: true, force: true });
  });

  function runCleanup(): void {
    cleanup({
      runnerTemp,
      githubEnvironment: join(
        runnerTemp,
        "_runner_file_commands",
        "set_env_unit",
      ),
      statePath,
    });
  }

  function expectRecoveryEvidencePreserved(): void {
    expect(existsSync(statePath)).toBe(true);
    expect(existsSync(temporaryDirectory)).toBe(true);
    expect(stdoutWrite).not.toHaveBeenCalledWith(
      "SYNTHETIC_CI_DATABASE_RELEASE_CLEANUP_PASS\n",
    );
    expect(
      spawnSyncMock.mock.calls.some(([, args]) => {
        const dockerArgs = args as string[];
        return dockerArgs[1] === "rm";
      }),
    ).toBe(false);
  }

  it("fails closed on an exact-name container without the ownership label", () => {
    spawnSyncMock
      .mockReturnValueOnce(dockerResult(0))
      .mockReturnValueOnce(dockerResult(0, state.containerName + "\n"))
      .mockReturnValueOnce(dockerResult(0));

    expect(runCleanup).toThrow(
      "SYNTHETIC_CI_DATABASE_RELEASE_RESOURCE_IDENTITY_MISMATCH",
    );
    expectRecoveryEvidencePreserved();
  });

  it("fails closed when inspection of an exact-name resource fails", () => {
    spawnSyncMock
      .mockReturnValueOnce(dockerResult(0))
      .mockReturnValueOnce(dockerResult(0, state.containerName + "\n"))
      .mockReturnValueOnce(dockerResult(1, "", "synthetic inspect failure"));

    expect(runCleanup).toThrow(
      "SYNTHETIC_CI_DATABASE_RELEASE_RESOURCE_INSPECTION_FAILED",
    );
    expectRecoveryEvidencePreserved();
  });

  it("fails closed when the exact-name resource census itself fails", () => {
    spawnSyncMock.mockReturnValueOnce(
      dockerResult(1, "", "synthetic census failure"),
    );

    expect(runCleanup).toThrow(
      "SYNTHETIC_CI_DATABASE_RELEASE_RESOURCE_LIST_FAILED",
    );
    expectRecoveryEvidencePreserved();
  });

  it("does not remove state when a successful deletion lacks absence proof", () => {
    const expectedLabel = "v1:" + token;
    spawnSyncMock
      .mockReturnValueOnce(dockerResult(0))
      .mockReturnValueOnce(dockerResult(0, state.containerName + "\n"))
      .mockReturnValueOnce(dockerResult(0, expectedLabel + "\n"))
      .mockReturnValueOnce(dockerResult(0))
      .mockReturnValueOnce(dockerResult(0))
      .mockReturnValueOnce(dockerResult(0))
      .mockReturnValueOnce(dockerResult(0))
      .mockReturnValueOnce(dockerResult(0, state.containerName + "\n"));

    expect(runCleanup).toThrow(
      "SYNTHETIC_CI_DATABASE_RELEASE_RESOURCE_CLEANUP_INCOMPLETE",
    );
    expect(existsSync(statePath)).toBe(true);
    expect(existsSync(temporaryDirectory)).toBe(true);
    expect(stdoutWrite).not.toHaveBeenCalledWith(
      "SYNTHETIC_CI_DATABASE_RELEASE_CLEANUP_PASS\n",
    );
  });
});
