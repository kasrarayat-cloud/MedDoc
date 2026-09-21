"""This candidate's OWN source-scope declaration, and its own instrument.

Tab 2's admin-console guard (`scripts/activate-admin-console.py`) is pinned to the range it
actually installed and its allowlist is exhaustive for THAT range. Its own test says what a
later candidate owes:

    "A later, unrelated candidate must bring its own declaration; this allowlist stays
     exhaustive."  -- ops/test_admin_console_activation.py

So this file reads nothing of theirs, widens nothing of theirs, and refuses the same protected
classes on its own account. A reviewed declaration is not a side door: it may name ordinary
source, and it may never name a migration, a public asset, an operations helper, a service unit
or a workflow. Those need their own act, with their own comparison.

The list itself lives in the DECLARATION, not here, because the declaration is the artifact a
human reviews. This module pins that file by content and checks that its claims are true.
"""
import hashlib
import subprocess
import unittest
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]

SELF = 'rebuild/ops/test_word_multicolumn_scope.py'
DECLARATION = 'docs/foundation/mutations/20260921-quillmd-word-multicolumn-mixed.md'
DECLARATION_SHA256 = '9c74be38c02bd5b8439863715af2dab9dc8e6ddd6bab94b3409adad9bf3018f7'
MARKER = '<!-- declared-source-scope -->'

#: The baseline this candidate is rebased onto: the source revision Tab 2 published as healthy
#: after recovering its activation. Pinned, because "current main" is not a fact a test can cite.
BASELINE = '875ee6e2a0836c37fcb293c228664186c1106291'

#: Exact, because a count that tracks the file cannot detect an accidental edit to the file.
DECLARED_COUNT = 15

#: ⚠️ THE ONLY PLACES A DECLARED PATH MAY LIVE. This was a BLACKLIST that named
#: `rebuild/ops/` — and this repository keeps `scripts/activate-admin-console.py` (the very
#: guard this declaration promises not to touch), `scripts/merge-pr.sh`,
#: `scripts/run-ruled-mutation.sh`, `scripts/hooks/pre-push` and a second `scripts/ops/`
#: directory outside that prefix. All seven were ACCEPTED into the declared set. Measured.
#: A whitelist cannot be outflanked by a directory nobody thought of.
CI_SCRIPT = 'scripts/ci/verify-fresh.sh'
ALLOWED_ROOTS = ('rebuild/core/', 'rebuild/documents/')

#: Files this candidate cannot ship without. engine/tab_form carry the import and the export;
#: generation/tab_review/views carry the clinical-path repairs the review gate found.
REQUIRED = {
    DECLARATION, SELF,
    'rebuild/documents/engine.py',
    'rebuild/documents/tab_form.py',
    'rebuild/core/generation.py',
    'rebuild/core/tab_review.py',
    'rebuild/core/views.py',
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def declaration_text():
    return (ROOT / DECLARATION).read_text()


def declared_paths(text=None):
    """The fenced list DIRECTLY under the marker.

    ⚠️ IT USED TO SCAN FORWARD FOR THE FIRST LINE STARTING WITH A FENCE, and that reads the
    wrong block. Indent the reviewed list inside a markdown list item and its fence no longer
    starts at column 0, so the parser walked past it to a later ```bash block and returned
    `{'bash scripts/ci/verify-fresh.sh python'}` — never seeing the migration the reviewed list
    actually named. Raising on EMPTY is not enough: the dangerous parse returns a WRONG set,
    and a wrong set feeds straight into the comparison.
    """
    text = declaration_text() if text is None else text
    require(MARKER in text, 'The declaration carries no declared-source-scope marker.')
    after = text.split(MARKER, 1)[1].splitlines()
    index = 0
    while index < len(after) and not after[index].strip():
        index += 1
    require(index < len(after) and after[index].startswith('```'),
            'The declared-source-scope block must open, unindented, directly after the marker.')
    index += 1
    body = []
    while index < len(after) and not after[index].startswith('```'):
        body.append(after[index])
        index += 1
    require(index < len(after), 'The declared-source-scope block is not closed.')
    paths = {line.strip() for line in body if line.strip()}
    require(paths, 'The declared-source-scope block is empty.')
    require(all(' ' not in name and not name.startswith(('.', '/', '-')) for name in paths),
            'The declared-source-scope block holds something that is not a repository path.')
    return paths


def validate_declared(paths):
    """Every refusal here applies to the DECLARED set, so declaring a path is not a way past it."""
    require(paths, 'The declaration names no file at all.')
    require(REQUIRED <= paths, 'The declaration omits a file this candidate cannot ship without.')
    require(all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                and str(PurePosixPath(name)) == name for name in paths),
            'Noncanonical declared path.')
    require(all(name in (DECLARATION, SELF, CI_SCRIPT) or name.startswith(ALLOWED_ROOTS)
                for name in paths),
            'A declared path lies outside this candidate\'s roots; it needs its own act.')
    require(not any(name.startswith('rebuild/core/migrations/') for name in paths),
            'This candidate declares no migration; a schema change needs its own reviewed act.')
    require(not any(name.startswith('rebuild/static/') for name in paths),
            'This candidate moves no public asset.')
    require(not any(name.startswith('rebuild/ops/') and name != SELF for name in paths),
            'No operations helper may change under this candidate.')
    require(not any(name.startswith('deploy/') or name.startswith('rebuild/deploy/')
                    or name.startswith('.github/') for name in paths),
            'No service policy or workflow change is declared by this candidate.')


def git(*command):
    done = subprocess.run(['git', *command], cwd=ROOT, capture_output=True, text=True, timeout=60)
    return done.stdout.strip() if done.returncode == 0 else None


def locate_candidate():
    """Find the tip that CARRIES this candidate, without asking whether it matches.

    ⚠️ IT USED TO LOCATE BY EQUALITY WITH THE DECLARED SET, AND THAT MADE THE WHOLE MODULE
    VACUOUS. A stale declaration simply matched no tip, so the comparison SKIPPED and the suite
    printed OK — which is exactly what happened the first time the declaration went out of date,
    one commit after this file was written. "Not the candidate" and "the candidate, declared
    wrongly" are different facts and must not share an answer.

    The declaration file itself is the anchor: nothing else in the repository adds it, so a tip
    whose change contains it IS this candidate, and its diff must then match EXACTLY.

    Two tips, because the checkout differs by surface: a pull-request run tests a merge of the
    base into the candidate, so the candidate is `HEAD^2`; a local branch IS the candidate.
    """
    for tip in ('HEAD^2', 'HEAD'):
        resolved = git('rev-parse', '--verify', tip + '^{commit}')
        if not resolved:
            continue
        base = git('merge-base', BASELINE, resolved)
        if not base:
            continue
        names = git('diff', '--name-only', base, resolved)
        if names is None:
            continue
        changed = set(names.split())
        # ⚠️ THE WORKING TREE COUNTS TOO. A commit-only view is blind to an undeclared file
        # that is merely uncommitted — which is every file, right up until the moment it is
        # committed and the gate has already been read as green.
        # Two commands that emit BARE paths. Slicing `git status --porcelain` by a fixed
        # offset is what produced `ebuild/core/generation.py` here, one character short and
        # looking exactly like a real finding.
        for command in (('diff', '--name-only', 'HEAD'),
                        ('ls-files', '--others', '--exclude-standard')):
            pending = git(*command)
            if pending:
                changed |= set(pending.split())
        if DECLARATION in changed:
            return tip, changed
    return None, None


class DeclarationIdentity(unittest.TestCase):
    def test_the_declaration_is_pinned_to_its_actual_bytes(self):
        self.assertEqual(hashlib.sha256((ROOT / DECLARATION).read_bytes()).hexdigest(),
                         DECLARATION_SHA256)

    def test_the_parse_finds_the_reviewed_list_and_not_an_empty_one(self):
        paths = declared_paths()
        self.assertEqual(len(paths), DECLARED_COUNT)
        self.assertLessEqual(REQUIRED, paths)

    def test_a_declaration_without_the_marker_or_the_fence_refuses_rather_than_reading_empty(self):
        """A silent {} here would make every check below pass vacuously."""
        for broken in (declaration_text().replace(MARKER, ''),
                       declaration_text().replace('```', '', 1),
                       declaration_text().split(MARKER)[0] + MARKER + '\n\n```text\n```\n'):
            with self.subTest(), self.assertRaises(RuntimeError):
                declared_paths(broken)

    def test_an_indented_list_or_a_later_code_block_is_not_read_as_the_scope(self):
        """⚠️ RAISING ON EMPTY IS NOT ENOUGH — the dangerous parse returns a WRONG set.

        Indent the reviewed list inside a markdown list item and its fence no longer starts at
        column 0, so a forward scan walks past it to the next ```bash block. Measured: the
        parser returned `{'bash scripts/ci/verify-fresh.sh python'}` and never saw the migration
        the reviewed list actually named — then fed that straight into the comparison.
        """
        head = declaration_text().split(MARKER)[0]
        indented = (head + MARKER + '\n\n- reviewed list:\n\n  ```text\n'
                    '  rebuild/core/migrations/0019_side_door.py\n  ```\n\n'
                    '```bash\nbash scripts/ci/verify-fresh.sh python\n```\n')
        with self.assertRaises(RuntimeError):
            declared_paths(indented)
        unclosed = head + MARKER + '\n\n```text\nrebuild/core/generation.py\n'
        with self.assertRaises(RuntimeError):
            declared_paths(unclosed)
        prose = head + MARKER + '\n\n```text\nsee the table above\n```\n'
        with self.assertRaises(RuntimeError):
            declared_paths(prose)
        # Positive control: the real declaration still parses.
        self.assertEqual(len(declared_paths()), DECLARED_COUNT)

    def test_every_declared_path_exists_in_this_checkout(self):
        for name in sorted(declared_paths()):
            with self.subTest(path=name):
                self.assertTrue((ROOT / name).is_file(), name)


class DeclaredSourceScope(unittest.TestCase):
    def test_the_reviewed_declaration_is_accepted(self):
        validate_declared(declared_paths())

    def test_each_protected_class_refuses_even_though_the_declaration_is_reviewed(self):
        good = declared_paths()
        for extra in ('rebuild/core/migrations/0019_other.py',
                      'rebuild/static/app.js',
                      'rebuild/ops/private_storage.py',
                      'rebuild/deploy/quillmd-fresh-worker.service',
                      'deploy/quillmd-fresh-admin.service',
                      '.github/workflows/test.yml',
                      'docs/../outside.md',
                      '/absolute'):
            with self.subTest(path=extra), self.assertRaises(RuntimeError):
                validate_declared(good | {extra})
        # Positive control: the harness is not simply refusing everything.
        validate_declared(good | {'rebuild/core/harmless.py'})

    def test_a_path_outside_this_candidates_roots_refuses(self):
        """⚠️ THIS WAS A BLACKLIST AND ALL SEVEN OF THESE WERE ACCEPTED.

        The refusal named `rebuild/ops/`, and this repository keeps its activation scripts, its
        merge wrapper, its mutation runner, its push hook and a SECOND ops directory under
        `scripts/`. A declaration could therefore name the very guard whose prose it promises
        not to touch.
        """
        good = declared_paths()
        for outside in ('scripts/activate-admin-console.py',
                        'scripts/merge-pr.sh',
                        'scripts/run-ruled-mutation.sh',
                        'scripts/hooks/pre-push',
                        'scripts/ops/unlock-fresh-volume.sh',
                        'scripts/ci/other.sh',
                        'rebuild/quillmd/settings.py',
                        'docs/rebuild/anything.md',
                        'Caddyfile'):
            with self.subTest(path=outside), self.assertRaises(RuntimeError):
                validate_declared(good | {outside})
        # Positive control: the three named files and the two roots are still accepted.
        validate_declared(good | {'rebuild/core/harmless.py', 'rebuild/documents/harmless.py'})

    def test_omitting_any_load_bearing_file_refuses(self):
        good = declared_paths()
        for missing in sorted(REQUIRED):
            with self.subTest(path=missing), self.assertRaises(RuntimeError):
                validate_declared(good - {missing})

    def test_the_candidate_is_actually_found_in_this_checkout(self):
        """THE ANTI-VACUOUS CONTROL. If the comparison below ever skips, this fails instead.

        A skip is the honest answer on a checkout that does not carry this candidate — and it
        is the WRONG answer on one that does. Only this test can tell the two apart, so it is
        the one that must be read when the module reports OK.
        """
        tip, changed = locate_candidate()
        if tip is None:
            self.skipTest('No tip in this checkout adds the declaration; this is not the candidate.')
        self.assertTrue(changed, 'the candidate was located but its change set is empty')

    def test_the_declaration_matches_this_candidates_real_change_exactly(self):
        declared = declared_paths()
        tip, changed = locate_candidate()
        if tip is None:
            self.skipTest('No tip in this checkout adds the declaration; this is not the candidate.')
        # Both directions, named separately, because the failure message IS the repair
        # instruction: one says the declaration is missing a file, the other that it names one
        # this candidate does not touch.
        self.assertEqual(sorted(changed - declared), [],
                         'changed by this candidate and NOT named in the declaration')
        self.assertEqual(sorted(declared - changed), [],
                         'named in the declaration and NOT changed by this candidate')
        validate_declared(changed)


if __name__ == '__main__':
    unittest.main()
