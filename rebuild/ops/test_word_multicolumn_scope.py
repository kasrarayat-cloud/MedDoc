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
DECLARATION_SHA256 = 'd7c80b92c5098c924bb7cbc4f650f214c8a7be02e3ac9df6efa658a5194d1418'
MARKER = '<!-- declared-source-scope -->'

#: The baseline this candidate is rebased onto: the source revision Tab 2 published as healthy
#: after recovering its activation. Pinned, because "current main" is not a fact a test can cite.
BASELINE = '875ee6e2a0836c37fcb293c228664186c1106291'

#: Exact, because a count that tracks the file cannot detect an accidental edit to the file.
DECLARED_COUNT = 13

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
    """The fenced list under the marker. A parse that finds nothing raises rather than returning {}."""
    text = declaration_text() if text is None else text
    require(MARKER in text, 'The declaration carries no declared-source-scope marker.')
    after = text.split(MARKER, 1)[1].splitlines()
    fences = [i for i, line in enumerate(after) if line.startswith('```')]
    require(len(fences) >= 2, 'The declared-source-scope block is not fenced on both sides.')
    paths = {line.strip() for line in after[fences[0] + 1:fences[1]] if line.strip()}
    require(paths, 'The declared-source-scope block is empty.')
    return paths


def validate_declared(paths):
    """Every refusal here applies to the DECLARED set, so declaring a path is not a way past it."""
    require(paths, 'The declaration names no file at all.')
    require(REQUIRED <= paths, 'The declaration omits a file this candidate cannot ship without.')
    require(all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                and str(PurePosixPath(name)) == name for name in paths),
            'Noncanonical declared path.')
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


def locate_candidate(declared):
    """Find the tip whose own change is EXACTLY the declared set.

    Two tips, because the checkout differs by surface: a pull-request run tests a merge of the
    base into the candidate, so the candidate is `HEAD^2`; a local branch IS the candidate.
    The comparison is equality, so a tip carrying more or less than the declaration does not
    match — that is what makes this a check rather than a subset filter.
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
        if set(names.split()) == declared:
            return tip, set(names.split())
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

    def test_omitting_any_load_bearing_file_refuses(self):
        good = declared_paths()
        for missing in sorted(REQUIRED):
            with self.subTest(path=missing), self.assertRaises(RuntimeError):
                validate_declared(good - {missing})

    def test_the_declaration_matches_this_candidates_real_change(self):
        declared = declared_paths()
        tip, changed = locate_candidate(declared)
        if tip is None:
            self.skipTest('No tip in this checkout changes exactly the declared set; the '
                          'declaration describes a candidate, and this checkout is not it.')
        self.assertEqual(changed, declared)
        validate_declared(changed)

    def test_that_match_is_equality_and_not_a_subset_filter(self):
        """Without this, a declaration naming half the change would still 'match'."""
        declared = declared_paths()
        if locate_candidate(declared)[0] is None:
            self.skipTest('The candidate is not present in this checkout.')
        for wrong in (declared - {'rebuild/documents/engine.py'},
                      declared | {'rebuild/core/harmless.py'}):
            with self.subTest(size=len(wrong)):
                self.assertIsNone(locate_candidate(wrong)[0])


if __name__ == '__main__':
    unittest.main()
