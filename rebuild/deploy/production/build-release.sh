#!/usr/bin/env bash
# Build the production release artifact for ONE reviewed commit, from any clone that has it.
#
#   bash rebuild/deploy/production/build-release.sh <40-hex commit> <output directory>
#
# The artifact is `git archive` of the commit (never the working tree), so uncommitted or ignored
# files (environment files, runtime evidence, virtualenvs, scratch) cannot enter it. git records the commit id in the tar's pax
# header, which ops/release_artifact.py checks on the host. gzip -n omits the timestamp, so the same
# commit and git version give the same bytes. Record the printed sha256 in the deploy declaration;
# the host refuses any other.
set -euo pipefail

commit=${1:-}
output=${2:-}
[[ $commit =~ ^[0-9a-f]{40}$ ]] || { echo "build-release: give the full 40-character commit" >&2; exit 2; }
[ -n "$output" ] && [ -d "$output" ] || { echo "build-release: give an existing output directory" >&2; exit 2; }
[ "$(git cat-file -t "$commit" 2>/dev/null)" = commit ] || { echo "build-release: $commit is not a commit here" >&2; exit 1; }

name="quillmd-${commit}.tar.gz"
target="${output%/}/${name}"
[ ! -e "$target" ] || { echo "build-release: $target already exists; refusing to overwrite" >&2; exit 1; }
git archive --format=tar --prefix="quillmd-${commit}/" "$commit" | gzip -n -9 > "$target.partial"
mv -- "$target.partial" "$target"
sha256sum -- "$target"
