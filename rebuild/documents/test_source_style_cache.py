"""Immutable source style readings retain ambiguity, visibility and document isolation."""
from io import BytesIO
import unittest
from zipfile import ZipFile

from docx import Document

from . import word_v3 as w


UNIQUE = 'The style ancestry is not uniquely defined.'
CYCLE = 'The style ancestry is cyclic or unavailable.'


def style(name, kind='paragraph', *, default=None, base=None, props=''):
    attrs = f'w:type="{kind}" w:styleId="{name}"'
    if default is not None:
        attrs += f' w:default="{default}"'
    ancestor = '' if base is None else f'<w:basedOn w:val="{base}"/>'
    return f'<w:style {attrs}>{ancestor}{props}</w:style>'


def source(styles='', *, body=None, defaults='', missing_styles=False):
    doc = Document(); doc.add_paragraph('Ordinary source:  ')
    stream = BytesIO(); doc.save(stream)
    output = BytesIO()
    with ZipFile(BytesIO(stream.getvalue())) as original, ZipFile(output, 'w') as rebuilt:
        for info in original.infolist():
            if info.filename == 'word/styles.xml':
                if missing_styles:
                    continue
                data = f'<w:styles xmlns:w="{w.NS["w"]}">{defaults}{styles}</w:styles>'.encode()
            elif info.filename == 'word/document.xml' and body is not None:
                data = f'<w:document xmlns:w="{w.NS["w"]}"><w:body>{body}</w:body></w:document>'.encode()
            else:
                data = original.read(info.filename)
            rebuilt.writestr(info, data)
    return output.getvalue()


def detector(data):
    return w.Detector(w.open_package(data))


def paragraph(d):
    return next(s for s in d.index.slots if s.part == 'word/document.xml' and s.kind == 'p')


class SourceStyleCache(unittest.TestCase):
    def test_complete_chain_returns_fresh_lists_and_preserves_source_bytes(self):
        original = source(style('C', base='B') + style('B', base='A') + style('A'))
        d = detector(original)
        for attempt in range(3):
            chain, problem = d.question_box_style_chain('C', 'paragraph')
            self.assertEqual(problem, '')
            self.assertEqual([s.get(w.q('w:styleId')) for s in chain], ['C', 'B', 'A'])
            chain.clear()
        self.assertEqual(d.package.data, original)
        with ZipFile(BytesIO(original)) as z:
            self.assertEqual(d.package.zip.read('word/styles.xml'), z.read('word/styles.xml'))

    def test_duplicate_matching_id_refuses_and_other_type_is_separate(self):
        for styles, kind, expected in (
                (style('A') + style('A'), 'paragraph', UNIQUE),
                (style('A') + style('A', 'character'), 'paragraph', ''),
                (style('A') + style('A', 'character'), 'character', ''),
                (style('A', 'character'), 'paragraph', UNIQUE)):
            with self.subTest(styles=styles, kind=kind):
                d = detector(source(styles))
                for repeat in range(2):
                    chain, problem = d.question_box_style_chain('A', kind)
                    self.assertEqual(problem, expected)
                    self.assertEqual(len(chain), 1 if not expected else 0)

    def test_missing_id_missing_part_and_empty_ancestry_keep_exact_refusals(self):
        for original, name, expected in (
                (source(style('A')), 'B', UNIQUE),
                (source(style('A')), '', UNIQUE),
                (source(style('A')), None, UNIQUE),
                (source(style('A', base='')), 'A', UNIQUE),
                (source(style('A', base='missing')), 'A', UNIQUE),
                (source(missing_styles=True), 'A', CYCLE)):
            with self.subTest(name=name, expected=expected):
                d = detector(original)
                self.assertEqual(d.question_box_style_chain(name, 'paragraph'), ([], expected))
                self.assertEqual(d.question_box_style_chain(name, 'paragraph'), ([], expected))

    def test_cycles_and_depth_limit_are_unchanged_after_warming_other_keys(self):
        d = detector(source(style('A', base='B') + style('B', base='A')))
        for name in ('A', 'B', 'A'):
            self.assertEqual(d.question_box_style_chain(name, 'paragraph'), ([], CYCLE))
        nodes = ''.join(style(f'S{i}', base=f'S{i + 1}' if i < 32 else None) for i in range(33))
        d = detector(source(nodes))
        chain, problem = d.question_box_style_chain('S1', 'paragraph')
        self.assertEqual((len(chain), problem), (32, ''))
        self.assertEqual(d.question_box_style_chain('S0', 'paragraph'), ([], CYCLE))
        self.assertEqual(d.question_box_style_chain('S0', 'paragraph'), ([], CYCLE))

    def test_duplicate_and_missing_default_ids_never_become_unique(self):
        for styles, properties in (
                (style('A', default='1') + style('B', default='true'), None),
                (style('A', default='1') + style('A', default='1'), None),
                ('<w:style w:type="paragraph" w:default="1"/>', ([], (0, 0)))):
            with self.subTest(styles=styles):
                d = detector(source(styles))
                for repeat in range(2):
                    self.assertFalse(d.tab_source_visible(paragraph(d)))
                    # A missing implicit ID historically has empty layout props;
                    # the independent visibility proof still refuses it.
                    self.assertEqual(d.tab_column_properties(paragraph(d)), properties)

    def test_default_values_and_explicit_style_replacement_stay_literal(self):
        for flag in ('1', 'true', 'on', '0', 'false', 'off', 'TRUE', 'unknown'):
            with self.subTest(flag=flag):
                d = detector(source(style('Hidden', default=flag,
                                          props='<w:rPr><w:vanish/></w:rPr>')))
                self.assertEqual(d.tab_source_visible(paragraph(d)), flag not in ('1', 'true', 'on'))
        body = '<w:p><w:pPr><w:pStyle w:val="Visible"/></w:pPr><w:r><w:t>Source</w:t></w:r></w:p>'
        d = detector(source(style('Hidden', default='1', props='<w:rPr><w:vanish/></w:rPr>')
                            + style('Visible'), body=body))
        self.assertTrue(d.tab_source_visible(paragraph(d)))

    def test_hidden_ancestry_and_doc_defaults_still_refuse(self):
        for marker in ('vanish', 'webHidden', 'specVanish'):
            for value, visible in (('', False), (' w:val="1"', False), (' w:val="true"', False),
                                   (' w:val="0"', True), (' w:val="false"', True), (' w:val="off"', True)):
                with self.subTest(marker=marker, value=value):
                    mark = f'<w:rPr><w:{marker}{value}/></w:rPr>'
                    d = detector(source(style('Parent', props=mark) + style('Child', default='1', base='Parent')))
                    for repeat in range(2):
                        self.assertEqual(d.tab_source_visible(paragraph(d)), visible)
                    d = detector(source(defaults=f'<w:docDefaults>{mark}</w:docDefaults>'))
                    self.assertEqual(d.tab_source_visible(paragraph(d)), visible)

    def test_character_and_table_defaults_and_unknown_references_still_control_visibility(self):
        body = '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Source</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
        for kind in ('character', 'table'):
            with self.subTest(kind=kind):
                d = detector(source(style('Hidden', kind, default='1', props='<w:rPr><w:vanish/></w:rPr>'), body=body))
                self.assertFalse(d.tab_source_visible(paragraph(d)))
        for ref in ('<w:pStyle w:val="Missing"/>', '<w:pStyle/>',
                    '<w:pStyle w:val="A"/><w:pStyle w:val="A"/>'):
            with self.subTest(ref=ref):
                body = f'<w:p><w:pPr>{ref}</w:pPr><w:r><w:t>Source</w:t></w:r></w:p>'
                d = detector(source(style('A'), body=body))
                self.assertFalse(d.tab_source_visible(paragraph(d)))

    def test_physical_visibility_is_not_cached_across_changed_slots(self):
        d = detector(source(style('A', default='1')))
        p = paragraph(d)
        self.assertTrue(d.tab_source_visible(p))
        # Only the style catalogue is immutable. Physical reads remain fresh.
        mark = w.etree.Element(w.q('w:vanish'))
        p.el.append(mark)
        self.assertFalse(d.tab_source_visible(p))
        p.el.remove(mark)
        self.assertTrue(d.tab_source_visible(p))

    def test_separate_documents_and_detectors_do_not_share_ancestry_or_defaults(self):
        a = detector(source(style('A', default='1')))
        b = detector(source(style('A', default='1', base='A')))
        c = detector(source(style('A', 'character', default='1', props='<w:rPr><w:vanish/></w:rPr>')))
        for repeat in range(3):
            self.assertTrue(a.tab_source_visible(paragraph(a)))
            self.assertEqual(b.question_box_style_chain('A', 'paragraph'), ([], CYCLE))
            self.assertFalse(c.tab_source_visible(paragraph(c)))


if __name__ == '__main__':
    unittest.main()
