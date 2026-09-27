#!/usr/bin/env python3
"""Verify and install a production release artifact: `git archive` of ONE reviewed commit.

deploy/production/build-release.sh produces `quillmd-<sha>.tar.gz` with
`git archive --format=tar --prefix=quillmd-<sha>/ <sha> | gzip -n`. git writes the commit id into the
tar's global pax header (`comment`), so the artifact names its own commit independently of its file
name. Verification requires, before anything is extracted:

- the artifact's sha256 equals the one recorded when it was built;
- the pax commit id equals the release SHA the operator declared;
- every member lives under the single prefix `quillmd-<sha>/`;
- the artifact carries rebuild/ops/production_profile.json and its sha256 equals the profile the
  running bootstrap script read, so the installed release carries exactly the profile values
  (paths, identity, ports, endpoints) that the script validated and planned with.

That last check binds the profile BYTES, not a commit. A bootstrap script from one release WILL
verify and install any other release whose profile file is byte-identical. The commit is bound
only by the release SHA the operator declares (checked against the pax commit id) and the artifact
sha256 recorded when it was built. Running the bootstrap script extracted from that same verified
artifact (docs/rebuild/v1/cutover-plan.md, G3 step 2) is what makes the script and the release one
commit; nothing here checks it.

`install` extracts ONLY the `rebuild/` subtree into a destination that must not exist yet, through
Python's `data` extraction filter: no absolute paths, no `..`, no links leaving the destination, no
device files, no setuid/setgid, no group/other write bits, and ownership of the extracting user
(root on the host). Errors carry fixed labels only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import sys
import tarfile

SHA1 = re.compile(r'[0-9a-f]{40}')
SHA256 = re.compile(r'[0-9a-f]{64}')
PROFILE_MEMBER = 'rebuild/ops/production_profile.json'
MAX_ARTIFACT_BYTES = 512 * 1024 * 1024


class ArtifactError(RuntimeError):
    """Contains only a fixed label."""


def require(condition, label):
    if not condition:
        raise ArtifactError(label)


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _open(artifact):
    try:
        return tarfile.open(artifact, mode='r:gz')
    except (OSError, tarfile.TarError, EOFError):
        raise ArtifactError('artifact_unreadable') from None


def verify(artifact, artifact_sha256, release_sha, profile_sha256):
    require(SHA256.fullmatch(artifact_sha256 or '') is not None and SHA1.fullmatch(release_sha or '') is not None
            and SHA256.fullmatch(profile_sha256 or '') is not None, 'arguments')
    path = Path(artifact)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_ARTIFACT_BYTES, 'artifact_unreadable')
    require(file_sha256(path) == artifact_sha256, 'artifact_sha256')
    prefix = 'quillmd-' + release_sha
    with _open(path) as archive:
        require(archive.pax_headers.get('comment') == release_sha, 'artifact_commit')
        members = archive.getmembers()
        require(members, 'artifact_empty')
        for member in members:
            name = member.name
            require(name == prefix or name.startswith(prefix + '/'), 'artifact_prefix')
            require('..' not in PurePosixPath(name).parts, 'artifact_member')
        try:
            profile = archive.extractfile(prefix + '/' + PROFILE_MEMBER)
        except KeyError:
            raise ArtifactError('artifact_profile') from None
        require(profile is not None, 'artifact_profile')
        require(hashlib.sha256(profile.read()).hexdigest() == profile_sha256, 'artifact_profile')
        application = [m for m in members if m.name.startswith(prefix + '/rebuild/')]
    return {'artifact_sha256': artifact_sha256, 'release_sha': release_sha, 'members': len(members),
            'application_members': len(application), 'profile_sha256': profile_sha256}


def install(artifact, artifact_sha256, release_sha, profile_sha256, destination):
    summary = verify(artifact, artifact_sha256, release_sha, profile_sha256)
    destination = Path(destination)
    require(destination.is_absolute() and not destination.exists() and not destination.is_symlink(), 'destination')
    require(destination.parent.is_dir() and destination.parent.resolve() == destination.parent, 'destination')
    prefix = 'quillmd-' + release_sha + '/'
    # Extract beside the destination and rename only when complete, so a refused member never leaves
    # a half-installed tree at the path the services use.
    partial = destination.with_name('.' + destination.name + '.partial-' + secrets.token_hex(4))
    previous = os.umask(0o022)
    try:
        partial.mkdir(mode=0o755)
        with _open(artifact) as archive:
            selected = []
            for member in archive.getmembers():
                if not member.name.startswith(prefix + 'rebuild/') and member.name != prefix + 'rebuild':
                    continue
                relative = PurePosixPath(member.name[len(prefix):])
                require(not relative.is_absolute() and '..' not in relative.parts, 'artifact_member')
                member.name = str(relative)
                selected.append(member)
            try:
                archive.extractall(partial, members=selected, filter='data')
            except (tarfile.FilterError, OSError):
                raise ArtifactError('artifact_member') from None
        partial.rename(destination)
    finally:
        os.umask(previous)
        if partial.exists():
            shutil.rmtree(partial)
    installed = destination / PROFILE_MEMBER
    require(installed.is_file() and file_sha256(installed) == profile_sha256, 'installed_profile')
    return dict(summary, installed=len(selected), destination=str(destination))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('action', choices=['verify', 'install'])
    parser.add_argument('--artifact', required=True)
    parser.add_argument('--artifact-sha256', required=True)
    parser.add_argument('--release-sha', required=True)
    parser.add_argument('--profile-sha256', required=True)
    parser.add_argument('--destination')
    args = parser.parse_args(argv)
    try:
        if args.action == 'verify':
            result = verify(args.artifact, args.artifact_sha256, args.release_sha, args.profile_sha256)
        else:
            require(args.destination, 'destination')
            result = install(args.artifact, args.artifact_sha256, args.release_sha, args.profile_sha256,
                             args.destination)
    except ArtifactError as exc:
        print(json.dumps({'verified': False, 'refused': str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(dict(result, verified=True), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
