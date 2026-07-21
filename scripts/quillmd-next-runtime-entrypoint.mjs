#!/usr/bin/env node

import { spawn } from "node:child_process";
import { resolve } from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";

const BUILD_PHASE = "phase-production-build";

export function assertQuillmdNextRuntimeEntrypoint(environment = process.env) {
  if (environment.NEXT_PHASE === BUILD_PHASE) {
    throw new Error("Production server startup rejected a build-only phase.");
  }
}

function fail() {
  process.stderr.write(
    `${JSON.stringify({
      service: "quillmd-next-runtime-entrypoint",
      code: "QUILLMD_RUNTIME_ENTRYPOINT_REJECTED",
    })}\n`,
  );
  process.exitCode = 78;
}

export async function main(argv = process.argv.slice(2)) {
  try {
    assertQuillmdNextRuntimeEntrypoint(process.env);
  } catch {
    fail();
    return;
  }

  const [executable, ...args] = argv;
  if (!executable) {
    fail();
    return;
  }

  const child = spawn(executable, args, {
    env: process.env,
    stdio: "inherit",
  });
  for (const signal of ["SIGINT", "SIGTERM"]) {
    process.once(signal, () => child.kill(signal));
  }
  await new Promise((resolve) => {
    child.once("error", () => resolve({ code: 78, signal: null }));
    child.once("exit", (code, signal) => resolve({ code, signal }));
  }).then(({ code, signal }) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exitCode = code ?? 78;
  });
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  await main();
}
