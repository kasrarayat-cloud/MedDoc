"""Build the exact MIT Word helper; emit immutable runtime and input proof.

No SDK installation, package update, cloud provisioning or application deployment.
The caller supplies an already verified SDK 8.0.425. Locked restore verifies every
NuGet content hash; runtime 8.0.31 and linux-x64 are explicit.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

SDK_VERSION = '8.0.425'
RUNTIME_VERSION = '8.0.31'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dotnet', required=True, type=Path)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    repository = source.parents[2]
    sdk = args.dotnet.resolve(strict=True)
    output = args.output.absolute()
    if output.exists() or '.runtime' not in output.parts:
        raise SystemExit('Use a new private .runtime build directory.')
    os.umask(0o077)
    output.mkdir(parents=True, mode=0o700)
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TZ': 'UTC',
                   'DOTNET_CLI_HOME': str(output/'cli-home'),
                   'DOTNET_CLI_TELEMETRY_OPTOUT': '1', 'DOTNET_NOLOGO': '1',
                   'DOTNET_GENERATE_ASPNET_CERTIFICATE': 'false',
                   'DOTNET_MULTILEVEL_LOOKUP': '0', 'NUGET_PACKAGES': str(args.cache.resolve())}
    version = subprocess.check_output([str(sdk), '--version'], cwd=source, env=environment, text=True).strip()
    if version != SDK_VERSION:
        raise SystemExit('The exact pinned .NET SDK is required.')
    inputs = sorted(p for p in source.rglob('*') if p.is_file()
                    and (p.suffix in ('.cs', '.csproj') or p.name in ('packages.lock.json', 'global.json', 'build_word.py'))
                    and not {'obj', 'bin'} & set(p.relative_to(source).parts))
    before = {str(p.relative_to(repository)): digest(p) for p in inputs}
    properties = ['-p:RestoreLockedMode=true', '-p:UseArtifactsOutput=true',
                  '-p:ArtifactsPath='+str(output/'artifacts'), '-p:RuntimeFrameworkVersion='+RUNTIME_VERSION,
                  '-p:Deterministic=true', '-p:ContinuousIntegrationBuild=true',
                  '-p:EnableSourceControlManagerQueries=false', '-p:EnableSourceLink=false',
                  '-p:IncludeSourceRevisionInInformationalVersion=false',
                  '-p:SourceRevisionId=', '-p:RepositoryCommit=',
                  '-p:PathMap='+str(output)+'=/_/quillmd-build%2C'+str(repository)+'=/_/quillmd']
    project = str(source/'WordHost/WordHost.csproj')
    subprocess.run([str(sdk), 'restore', project, '--locked-mode', '--runtime', 'linux-x64', *properties],
                   cwd=source, env=environment, check=True, timeout=180)
    subprocess.run([str(sdk), 'publish', project, '--configuration', 'Release', '--runtime', 'linux-x64',
                    '--self-contained', 'true', '--no-restore', '--output', str(output/'runtime'), *properties],
                   cwd=source, env=environment, check=True, timeout=180)
    if before != {str(p.relative_to(repository)): digest(p) for p in inputs}:
        raise SystemExit('Build inputs changed during compilation; artifact is not installable.')
    assembly_metadata = list((output/'artifacts/obj').rglob('*.AssemblyInfo.cs'))
    if len(assembly_metadata) != 2 or any('AssemblyInformationalVersionAttribute("1.0.0")' not in p.read_text() for p in assembly_metadata):
        raise SystemExit('Unexpected ambient revision metadata in generated assembly information.')
    if list((output/'artifacts/obj').rglob('*.sourcelink.json')):
        raise SystemExit('Ambient SourceLink output is not allowed; input hashes are the provenance authority.')
    runtime = output/'runtime'
    files = {}
    for path in sorted(runtime.rglob('*')):
        if path.is_symlink():
            raise SystemExit('Published runtime must not contain symlinks.')
        if path.is_dir():
            path.chmod(0o700)
        elif path.is_file():
            path.chmod(0o700 if path.name == 'WordHost' else 0o600)
            files[str(path.relative_to(runtime))] = digest(path)
    runtime.chmod(0o700)
    configuration = json.loads((runtime/'WordHost.runtimeconfig.json').read_text())
    frameworks = configuration['runtimeOptions']['includedFrameworks']
    if any(f['version'] != RUNTIME_VERSION for f in frameworks):
        raise SystemExit('Published runtime version differs from the declared pin.')
    manifest = output/'runtime-manifest.json'
    manifest.write_text(json.dumps({'format': 1, 'runtime': 'dotnet8-self-contained-linux-x64',
                                   'executable': 'WordHost', 'files': files}, sort_keys=True, separators=(',', ':')))
    proof = {'format': 1, 'sdk_version': version, 'runtime_version': RUNTIME_VERSION,
             'runtime_identifier': 'linux-x64', 'build_inputs': before,
             'restored_locked': True, 'self_contained': True, 'runtime_executable': 'WordHost',
             'runtime_manifest_sha256': digest(manifest), 'sdk_executable_sha256': digest(sdk),
             'dependencies': {'Aspose.Words.FOSS': '26.3.0'}, 'license': 'MIT',
             'ambient_scm_metadata': False, 'source_revision_id': '', 'repository_commit': ''}
    (output/'build-proof.json').write_text(json.dumps(proof, sort_keys=True, indent=2))
    print(json.dumps({'runtime': str(runtime), 'manifest': str(manifest),
                      'manifest_sha256': digest(manifest), 'build_proof': str(output/'build-proof.json')}))


if __name__ == '__main__':
    main()
