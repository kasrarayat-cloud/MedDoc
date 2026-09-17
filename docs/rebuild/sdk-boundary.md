# Word SDK process boundary

Prepared and privately exercised 2026-09-17. This is a separate boundary for the
qualified Aspose.Words FOSS .NET helper. The existing Python DOCX/PDF sandbox is
unchanged. The first successful SDK probe is **not** a claim that the complete
doctor workflow or all Word forms have passed qualification.

## Two enforced stages

`rebuild/documents/sdk_sandbox.py` runs as a fresh, single-threaded child. It
verifies the complete self-contained publish tree against a separately pinned
SHA256 manifest, sets resource limits, installs Landlock and seccomp, and then
`exec`s the fixed published `WordHost` or synthetic `ProbeHost` entry point.
All CLR threads are created after this native boundary and inherit it. A process
that already has another thread is refused before isolation begins.

Filesystem grants are limited to:

- The private job workspace, read/write/create/delete, without execution.
- The pinned self-contained publish tree, read/execute only.
- Native system library directories, read only, and the exact ELF interpreter
  with execute permission.
- Explicit ordinary runtime metadata files: loader cache, OS/time metadata,
  process status/stat/maps/cgroup, global memory metadata, CPU online/possible
  and the two root cgroup memory-limit files. There is no whole `/proc`, `/etc`,
  home, application-source or full .NET SDK grant.

The clean CLR environment disables diagnostics and startup hooks, uses invariant
globalization, bounds the managed heap and processor count, and excludes every
application/provider/payment credential and inherited loader override.

The first seccomp stage blocks networking, fork/vfork, cross-process inspection,
signals to other processes, SysV/message-queue IPC, namespace/mount changes,
kernel-key/BPF/io_uring interfaces and related escape surfaces. `clone3` returns
`ENOSYS` so libc can use `clone` for legitimate threads. The latter is accepted
only with `CLONE_THREAD`, `CLONE_VM` and `CLONE_SIGHAND` together, with an exact
allowlist of ordinary pthread bookkeeping flags. Exit signals, namespace flags,
unknown flags and process-creation combinations are denied. Own-thread signals
needed by the CLR are permitted; foreign thread-group IDs are refused.

The initial `exec` into the pinned CLR entry point is necessary. Before opening
the request or document, the managed host invokes `SdkSeccompGate` through the
mandatory `IDocumentSandbox` interface. It verifies native no-new-privileges and
seccomp status, actual outside-file denial and `EPERM` for socket creation, then
loads the second filter with **TSYNC** to deny `execve` and `execveat` in every
existing CLR thread. A missing native stage, failed synchronization or absent
library refuses processing; no environment flag can substitute for this gate.
The [libseccomp API](https://raw.githubusercontent.com/seccomp/libseccomp/main/include/seccomp.h.in)
defines the thread synchronization control used here.

## Runtime ownership and publication

Production uses a reviewed installation under the application's `.word-sdk`
directory. The manifest and every published object must be operator/root-owned,
not owned or writable by the application, free of symlinks and hardlinks, and
match the complete manifest exactly. Writable ancestors are refused so an
application cannot replace an otherwise read-only artifact. The manifest lives
outside the hashed publish tree; its SHA256 comes from protected application
configuration. A self-contained runtime is required; the full development SDK
and NuGet cache are never granted to the document process.

Operator fixture builds can use `--qualification`, but only when the launcher
receives `QUILLMD_WORD_QUALIFICATION=1` and does not receive the managed-service
flag. The parent refuses this mode when `QUILLMD_ENV_MANAGED=1`. This exception
permits the operator to own its local build artifacts; full-byte pinning,
Landlock, seccomp and the mandatory managed gate still execute. It does not
relax the document's filesystem or syscall policy. `ProbeHost` additionally
requires an existing synthetic outside canary whose bytes the trusted launcher
positively verifies before applying isolation.

The first publish attempt was correctly refused before CLR execution because
the build emitted a group-writable publish directory (`0775`) and native library
(`0764`). Only the completed private qualification artifact was normalized to
`0700` directories/entry point and `0600` files. No system library, host security
setting, production app runtime or prior Python boundary was modified.

## Actual private evidence

The self-contained .NET8 `ProbeHost`, using Aspose.Words FOSS 26.3.0, passed:

- Outside-canary read denial on the main thread, a CLR thread created before the
  managed gate, and a thread created afterward. Those threads themselves were
  successfully created; their forbidden reads were denied.
- Raw `execve` denial with `EPERM` on all three thread cases, proving the second
  filter covers pre-existing CLR threads.
- Socket and process creation denial.
- Opening the accepted blank WM IOV document, selecting all 28 dropdowns,
  saving and reopening the result with 28 controls retained.

The private result at
`rebuild/.runtime/wm-sandbox-20260917T191823Z/result.json` in the continuation
worktree records **all nine checks passing**, empty stderr and exit zero. This
run also carried the final `512 MiB` native data limit:

| Measurement | Observed value |
| --- | --- |
| End-to-end startup, isolation and SDK round trip | 2.007 seconds |
| Sampled peak resident memory | 87,572 KiB, about 85.5 MiB |
| Peak virtual address space | 3,860,968 KiB, about 3.68 GiB |
| Sampled peak thread count | 6 |

The earlier run without the additional native-data limit also passed in 2.231
seconds with 87,888 KiB peak RSS. Its evidence is retained separately. Both
measurements cover one small accepted blank and its synthetic dropdown fill,
not worst-case documents or concurrent doctor traffic.

Seven focused Python tests pass, including **eleven real kernel assertions** in
a disposable process: secret/passwd/socket/fork/foreign-signal/IPC denial,
`clone3` fallback behavior, inherited thread denial, positive own-thread signals
and workspace writes, and a `600 MiB` private native allocation failing with
`ENOMEM`. Other checks reject altered runtime manifests/files, extra objects,
symlinks, app-owned production artifacts, managed qualification flags and a
native stage started too late to cover all threads.

## Resource limits and remaining coverage

The qualified profile uses 20 CPU seconds, 32 MiB output-file size, 96 file
descriptors, 8 MiB stack, no core dumps, a 256 MiB managed heap, a 512 MiB native
data limit and an **8 GiB virtual-address limit**. The latter is deliberate:
the actual CLR reserves about 3.68 GiB while using under 90 MiB resident memory.
Blindly reusing the Python parser's 512 MiB address-space cap would reject this
runtime before document handling. The trusted parent imposes a wall timeout.

These limits are not a claim of a complete per-process RSS ceiling. The existing
service cgroup remains the hard aggregate memory/task backstop: doctor/admin
`768 MiB`, worker `1024 MiB`, each `TasksMax=64`. The trusted parent now takes
one application-wide `flock` on the private `proofs/word-processor.lock` before
spawning WordHost. The regular0600 file and private0700 parent must belong to
the application identity; links are refused. A second request waits at most
eight seconds and receives a retryable busy refusal. The child inherits no lock
descriptor. An actual two-process test demonstrated refusal while held and
successful acquisition after release; this is a serialization proof, not a
worst-case memory-load measurement. The single helper shares its service budget
with the parent process. Large-input and concurrency qualification must
measure the actual parent workflow before increasing exposure; cgroup exhaustion
can affect the service, not just one parser. A distinct per-job cgroup has not
been demonstrated.

The reviewed v2 adapter has separately passed an actual90-check synthetic gate,
including long answers and clinical alternatives. Independent clinical refutation
found and then reproduced repairs for cross-side assertion evidence, normalized
source-label compatibility and extraction alongside required assertion labels.
The final build6 artifact also passed12 independent checks, including actual
core-review-to-SDK export, refusal of the original cross-side exploit, and stale
source/mapping/revision/answer binding. Private evidence is under
`rebuild/.runtime/wm-v2-independent-refutation-build6/` in the continuation worktree.
These checks do not substitute for actual doctor/admin upload-to-export
verification after installation or the scoped independent security assessment.
Scanned forms/OCR and arbitrary Word layouts are outside this boundary's
document-compatibility claim. Public maintenance and synthetic-only processing
remain in force.
