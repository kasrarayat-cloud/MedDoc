"""Release 2, R2-31: the worker's kept log keeps why a Word file was refused.

The worker logs a document it did not send as 'round <id>: the document was not sent (<word>)', and the installer's
kept copy of its log (install.ids_only_lines, KEPT_LOG_FORMATS['worker']) keeps that line only when the bracket holds
one fixed word. Release 1's worker put the refusal's detail there - a sentence, which the kept copy drops - so the
reason never reached it; release 2's worker puts a refused Word file's code there first (studio/jobs.py), which it
keeps. The pattern is the installer's own, read from this tree, never copied.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r2word -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402

R2WORD_ROUND = '0f8fad5b-d9cb-469f-a165-70867728950e'
R2WORD_CODES = ('inserted_document', 'inserted_object')  # studio.fable.docx_package.REFUSAL_CODES


def r2word_stamped(lines):
    """``lines`` as `docker logs --timestamps` prints them, one second apart."""
    return '\n'.join(f'2026-11-26T10:00:{second:02d}.123456789Z {line}' for second, line in enumerate(lines)).encode()


class RefusedWordLogTests(unittest.TestCase):
    def test_the_code_of_a_refused_word_file_is_kept_with_the_round_s_id(self):
        lines = [f'round {R2WORD_ROUND}: the document was not sent ({code})' for code in R2WORD_CODES]
        kept, dropped = install.ids_only_lines('worker', r2word_stamped(lines))
        self.assertEqual([line.split(' ', 1)[1] for line in kept], lines)
        self.assertEqual(dropped, 0)

    def test_the_detail_release_1_logged_there_is_dropped(self):
        # the positive control: what the line held before R2-31 never reached the kept copy
        lines = [f'round {R2WORD_ROUND}: the document was not sent (the Word package was refused: it holds inserted '
                 'content that could not be shown in the PDF)',
                 f'round {R2WORD_ROUND}: the document was not sent (the converter refused the Word package)']
        kept, dropped = install.ids_only_lines('worker', r2word_stamped(lines))
        self.assertEqual((kept, dropped), ([], 2))

    def test_the_codes_are_the_package_s_own(self):
        source = (Path(__file__).resolve().parents[1] / 'studio' / 'fable' / 'docx_package.py').read_text(
            encoding='utf-8')
        self.assertIn(f"INSERTED_DOCUMENT, INSERTED_OBJECT = '{R2WORD_CODES[0]}', '{R2WORD_CODES[1]}'", source)


if __name__ == '__main__':
    unittest.main()
