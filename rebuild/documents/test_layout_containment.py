"""Concrete PDF ink/identity counterexamples for the separately versioned rule."""
import copy
import io
from pathlib import Path
import unittest

from pypdf import PdfReader
from pypdf.generic import DecodedStreamObject, NameObject
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from .layout_geometry import containment, geometry, VECTOR


class LayoutContainment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pdfmetrics.registerFont(TTFont('LayoutProofFixture', str(Path(reportlab.__file__).parent/'fonts/Vera.ttf')))
        buffer = io.BytesIO(); canvas = Canvas(buffer,pagesize=(400,400)); canvas.setFont('LayoutProofFixture',11)
        canvas.drawString(10,10,'NormalAbnormalFinding1 2');canvas.save()
        cls.fixture = buffer.getvalue()
        cls.candidate = {'id':'row','source':{'options':['Normal','Abnormal']},'rendered_source':{
            'header':[[],[{'kind':'glyph','text':'Normal'}],[{'kind':'glyph','text':'Abnormal'}]],
            'row':[[{'kind':'glyph','text':'Finding'}],
                   [{'kind':'glyph','text':'1 '},{'kind':'ff_checkbox','text':VECTOR,'checked':False}],
                   [{'kind':'glyph','text':'2 '},{'kind':'ff_checkbox','text':VECTOR,'checked':False}]],
            'row_dot_leaders':False}}

    def pages(self,shift=0,wide=10,second=200,duplicate=False,extra=b'',checked=False):
        reader=PdfReader(io.BytesIO(self.fixture));page=reader.pages[0]
        font=next(name for name,ref in page['/Resources']['/Font'].items() if ref.get_object().get('/Subtype')=='/TrueType')
        def text(value,x,y):return f'q 0 0 0 rg BT {x} {y} Td {font} 11 Tf <{value.encode().hex()}> Tj ET Q\n'.encode()
        stream=b'.1 w\n'
        for dy in ([0,100] if duplicate else [0]):
            stream+=text('Normal',100,300-dy)+text('Abnormal',second,300-dy)+text('Finding',20,270-dy)
            stream+=text('1 ',110+shift,270-dy)+f'0 0 0 RG {120+shift} {268-dy} {wide} {wide} re S\n'.encode()
            if checked:stream+=f'{120+shift} {278-dy} m {130+shift} {268-dy} l S {130+shift} {278-dy} m {120+shift} {268-dy} l S\n'.encode()
            stream+=text('2 ',210,270-dy)+f'220 {268-dy} 10 10 re S\n'.encode()
        content=DecodedStreamObject();content.set_data(stream+extra);page[NameObject('/Contents')]=content
        return reader.pages

    def result(self,**kwargs):return containment(self.pages(**kwargs),[self.candidate])

    def test_unique_printed_labels_and_native_boxes_pass(self):
        result=self.result();self.assertTrue(result['passed']);self.assertEqual(len(result['measurements']),2)
        candidate=copy.deepcopy(self.candidate);candidate['rendered_source']['row'][1][-1]['checked']=True
        self.assertTrue(containment(self.pages(checked=True),[candidate])['passed'])

    def test_wrong_column_and_crossing_adjacent_boundary_refuse(self):
        self.assertFalse(self.result(shift=80)['passed'])
        proof=self.result()['measurements'][0]
        shift=proof['header']['left']-proof['row']['left']-.001
        self.assertFalse(self.result(shift=shift)['passed'])

    def test_overwide_overlapping_and_ambiguous_printed_pairs_refuse(self):
        for kwargs in ({'wide':80},{'second':120},{'duplicate':True}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.result(**kwargs)

    def test_unknown_checkbox_mark_state_and_overlay_refuse(self):
        for kwargs in ({'checked':True},{'extra':b'120 278 m 130 268 l S'},
                       {'extra':b'1 1 1 rg 100 260 50 20 re f'},
                       {'extra':b'1 0 0 1 10 0 cm'}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.result(**kwargs)

    def test_full_source_meaning_must_match_and_cannot_borrow_another_label(self):
        candidate=copy.deepcopy(self.candidate);candidate['rendered_source']['row'][0][0]['text']='Different question'
        with self.assertRaises(ValueError):containment(self.pages(),[candidate])

    def test_every_owned_checkbox_stroke_has_visible_solid_ink(self):
        candidate=copy.deepcopy(self.candidate);candidate['rendered_source']['row'][1][-1]['checked']=True
        for paint in (b'1 1 1 RG ', b'1 0 0 RG ', b'0 w ', b'[0 20] 0 d ', b'[1 20] 0 d '):
            with self.subTest(paint=paint):
                pages=self.pages(checked=True); page=pages[0]
                needle=b'120 278 m 130 268 l S 130 278 m 120 268 l S'
                content=DecodedStreamObject();content.set_data(page.get_contents().get_data().replace(needle,b'q '+paint+needle+b' Q'))
                page[NameObject('/Contents')]=content
                with self.assertRaises(ValueError):containment(pages,[candidate])

    def test_control_only_segment_measures_every_owned_stroke(self):
        candidate=copy.deepcopy(self.candidate);candidate['rendered_source']['row'][1][-1]['checked']=True
        for segment in candidate['rendered_source']['row'][1:]:segment.pop(0)
        for paint,expected in ((b'',True),(b'40 w ',False),(b'2 J 30 w ',False)):
            with self.subTest(paint=paint):
                pages=self.pages(checked=True); page=pages[0]
                needle=b'120 278 m 130 268 l S 130 278 m 120 268 l S'
                stream=page.get_contents().get_data().replace(b'<3120> Tj',b'<> Tj').replace(b'<3220> Tj',b'<> Tj')
                content=DecodedStreamObject();content.set_data(stream.replace(needle,b'q '+paint+needle+b' Q'))
                page[NameObject('/Contents')]=content
                result=containment(pages,[candidate]);self.assertEqual(result['passed'],expected)
                lines=geometry(page)
                line=next(line for line in lines if any(r['type']=='ff_checkbox' and r['checked'] for r in line['records']))
                box=next(r for r in line['records'] if r['type']=='ff_checkbox' and r['checked'])
                owned=[line['paths'][i]['bounds'] for i in box['own_paths']]
                self.assertEqual(box['ink'],[min(b[0] for b in owned),min(b[1] for b in owned),
                                            max(b[2] for b in owned),max(b[3] for b in owned)])

    def test_embedded_ink_bounds_are_used_instead_of_advances(self):
        lines=geometry(self.pages()[0]);normal=next(line for line in lines if line['text']=='NormalAbnormal')
        glyph=normal['records'][0]
        self.assertNotEqual(glyph['left'],glyph['ink'][0])
        self.assertGreater(glyph['ink'][2],glyph['ink'][0])
