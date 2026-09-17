# WM IOV SDK qualification

The root `Program.cs` executable is a **synthetic qualification tool**, separate
from the production `WordHost` adapter below.
It accepts only the tracked blank WM IOV SHA256, changes documents through the
established Aspose.Words FOSS APIs, and writes only to a fresh private runtime
directory. The application does not call it.

Pinned dependency: **Aspose.Words.FOSS 26.3.0**, MIT. `packages.lock.json` pins
transitive packages and content hashes. `LICENSE.Aspose.Words.FOSS` reproduces
the upstream copyright/license. Source:
https://github.com/aspose-words-foss/Aspose.Words-FOSS-for-.NET

Official provenance and limits:

- https://docs.aspose.org/words/net/getting-started/license/
- https://docs.aspose.org/words/net/getting-started/installation/
- https://api.nuget.org/v3-flatcontainer/aspose.words.foss/26.3.0/aspose.words.foss.nuspec

The FOSS package edits DOCX without an evaluation watermark or license key.
It has no page layout/PDF/image renderer. The separate proprietary Python SDK
was used **only for private watermarked evaluation** and is not an application
dependency. No commercial license or font rights are implied.

## Reproduce

Use an isolated .NET8 SDK and private package/build directories. Run with
`umask 077`; do not replace shared Python dependencies. Example from `rebuild/`:

```sh
dotnet restore documents/sdk_word/Qualification.csproj --locked-mode \
  --packages "$PWD/.runtime/wm-nuget" \
  -p:BaseIntermediateOutputPath="$PWD/.runtime/wm-build/obj/"
dotnet build documents/sdk_word/Qualification.csproj -c Release --no-restore \
  -p:BaseIntermediateOutputPath="$PWD/.runtime/wm-build/obj/" \
  -p:OutputPath="$PWD/.runtime/wm-build/bin/"
python documents/wm_qualification.py \
  --original '../WM IOV Template.docx' \
  --output "$PWD/.runtime/wm-new-qualification" \
  --dotnet /absolute/path/to/private/dotnet \
  --assembly "$PWD/.runtime/wm-build/bin/Qualification.dll"
```

The Python checker uses lxml for read-only assertions; it does not alter OOXML.
Optional `--render-evaluation` requires a separate isolated installation of
`aspose-words==26.9.0` and `pymupdf==1.28.2`. Its output is always evaluation
evidence and must never be returned as a finalized clinical export. This
Ubuntu VPS needed OpenSSL1.1 extracted into a private evaluation directory for
that renderer; no system package, host library or application runtime changed.

See `docs/rebuild/wm-iov-qualification.md` for the clinical/default-text blockers,
actual structural/visual results and the chosen integration sequence.

## Bounded application adapter

`Adapter/` is the shared library; `WordHost/` is the production entry point.
`ProbeHost/` is only an independent synthetic boundary control. All three use
pinned package locks. The original qualification `Program.cs` stays separate.
See [PROTOCOL.md](PROTOCOL.md) and `documents/sdk_sandbox.py` for the required
native/managed security boundary and trust contract.

Build from a private worktree with the already verified isolated SDK/cache:

```bash
python3 rebuild/documents/sdk_word/build_word.py \
  --dotnet "$PWD/rebuild/.runtime/wm-dotnet/dotnet" \
  --cache "$PWD/rebuild/.runtime/wm-nuget" \
  --output "$PWD/rebuild/.runtime/new-word-build"
```

The script requires exactly SDK **8.0.425**, self-contained runtime **8.0.31**
and linux-x64. `global.json` disables SDK roll-forward; the project disables
runtime roll-forward. Restore uses the committed NuGet lock/content hashes.
Generated source and repository paths are normalized independently so clean
builds in different directories produce identical DLL/PDB/runtime manifests.
Ambient Git queries/SourceLink and informational-version revision injection are
disabled; the content-hash proof is authoritative, avoiding a stale Git HEAD in
uncommitted-source builds. Generated metadata is asserted before the proof.
No global package installation or shared Python environment is changed.

The build emits `runtime/`, a separate `runtime-manifest.json`, and
`build-proof.json`. The proof includes SHA256 of every `.cs`, `.csproj`,
`packages.lock.json`, `global.json`, and `build_word.py` input; exact SDK/runtime
versions; locked-restore/self-contained flags; and the manifest hash. Inputs are
hashed before and after compilation. The production installer checks the exact
source population and bytes against the reviewed commit before activation.

Two independent v2 builds in separate synthetic Git repositories with different
HEADs were demonstrated byte-identical to the worktree build across all 192
published files and their source proof. See the private reproducibility evidence
cited in `docs/rebuild/wm-iov-qualification.md`; never infer reproducibility merely
from setting the compiler flag.

Production installation requires root-owned immutable runtime/manifest ancestors:
the application identity cannot replace the SDK binary or pin. The whole SDK is
never a runtime permission grant. Operator qualification mode retains the full
kernel boundary and is refused in managed services.

## CI and meaningful qualification

1. Use the pinned SDK/locks and run `build_word.py` in a new private artifact
   directory. Retain the manifest/source proof together with the build evidence.
2. Run the native sandbox tests and self-contained ProbeHost controls on a Linux
   x86-64 kernel supporting the required Landlock/seccomp features. Unsupported
   isolation must fail closed; never skip the security gate to produce a pass.
3. Run `verify_adapter_v2.py` with the accepted blank, built runtime/manifest pin
   and a new output directory. It covers actual positive, absent, no-prior,
   asymptomatic and long exports plus evidence/variant/security negatives.
4. Run the application's model/API and synthetic browser workflows on the same
   immutable mapping/runtime. Clinical code changes also require independent
   refutation. The old v1 qualifier's positive result was followed by an actual
   side-binding counterexample; v2 regressions and independent retests close it.
5. Keep all generated fixtures/documents/images private and untracked. Preserve
   original hash, controls/options and source evidence. Never use patient data.

`synthetic_fixture.py` constructs synthetic requests from actual canonical SDK
metadata/resolution, with no provider calls or unlabelled source preface.
`render_v2_evaluation.py` optionally uses the separate installed commercial trial
for private watermarked layout evidence only. It is not a runtime dependency,
CI requirement, purchased license, or application PDF export engine. Its font
substitution and native Word acceptance limits remain explicit.

A read-only NuGet advisory query complements the application dependency checks.
SDK8 does not expose `--no-restore` on `dotnet list package`; use the existing
exact restored assets and verify the returned package inventory against locks.
Set a private `DOTNET_CLI_HOME`, `DOTNET_GENERATE_ASPNET_CERTIFICATE=false` and
`DOTNET_CLI_TELEMETRY_OPTOUT=1` even for CLI help/audit commands. Set
`UseArtifactsOutput=true` and `ArtifactsPath` to the matching build's artifacts,
then run `dotnet list WordHost.csproj package --vulnerable --include-transitive
--format json --source https://api.nuget.org/v3/index.json`. A successful empty
finding list alone is insufficient: also list all packages and assert the five
exact locked IDs/versions were the population queried. Preserve query timestamp,
source, inventory and finding counts with the release evidence.
