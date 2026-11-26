"""Release 2, Group F (lane D): the Word files release 2 refuses and the ones it codes.

- R2-29: an object or a control keeps a picture in its place, or the file is refused (ContentNotShown): the Word area's
  shape tables B01-B27, C01-C09, E01-E16 and E22, rebuilt here; a preview is a part that is sent.
- R2-30: a removed field in another field's result stays a field whose instruction is QUOTE, byte for byte; its
  fallback refuses a field kept, not HYPERLINK, TOC, QUOTE or STYLEREF, whose stored result holds something a reader
  sees outside the fields in it while a removed field stood in its instruction (the 7.4 corpus's H01 shape), and
  nothing else; a seeded fuzz.
- The Word case of R2-3's pin (refutation round 1): a clean Word file is sent to the coder exactly as release 1 sent it.
- Everything that needs neither a refusal nor a QUOTE gives exactly release 1's package (apart from the deviations
  ZipNameTests and CharacterReferenceTests pin): the reference is release 1's own docx_package.py, vendored as a test
  fixture checked against its git blob id (RELEASE_1_PACKAGE_BLOB, immutable), so the comparisons run wherever the
  tests run - CI's shallow clone and the image included - and are never skipped.
- R2-31: a refused Word upload through the shipped job path - its sentence, its three audit rows with the code and
  counts, nothing counted or sent, retry offered and refused the same way; the two sentences against the customer
  denylist.
- R2-28 step 7 (C8): a round that would read a conversion an earlier round stored runs the package check on the stored
  original first - a stored conversion of a file the check refuses is refused at its next round (an answers round and a
  retry) with no coder and no converter call; a clean one is reused byte-identically, with no converter call; one
  whose package is not release 1's (R2-30's QUOTE, a name or an id release 1 lost: refutation round 2, rounds[1])
  converts afresh, with one; and a check that cannot decide lets the converter decide (rounds[0]).

Synthetic bytes only, every package built here; no LibreOffice, no network, no provider."""
import gzip
import hashlib
import io
import random
import re
import struct
import tempfile
import types
import zipfile
import zlib
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from studio import jobs, models, storage
from studio.fable import BUSY, CONVERT, DOCUMENT, docx_package
from studio.fable import client as fable_client
from studio.fable import document as fable_document
from tests.support import coding as f
from tests.support import rounds as r
from tests.test_fable_document import failing_runner, private_tempdir
from tests.test_request_identity import git_blob_id

Round, Run, AuditEvent = models.CodingRound, models.ProviderRun, models.AuditEvent
ROOT = Path(settings.BASE_DIR)
# release 1's studio/fable/docx_package.py and converter_server.py (9ee0c85be, the live release 816045c72644), as git
# stores them: vendored as test fixtures (tests/fixtures/release-1/), so every comparison with release 1 runs wherever
# the tests run - CI's clone is shallow and the image has no .git (refutation round 1, refuse[0]) - and each fixture is
# checked against its git blob id, so it cannot drift from release 1 unnoticed
RELEASE_1_PACKAGE_BLOB = 'c4aa942edbff920de2126f848ec27045b8ba0a5a'
RELEASE_1_CONVERTER_BLOB = '9a6195defa312b30c4d54d5ee7e6f15356d4b28f'
RELEASE_1_FIXTURES = ROOT / 'tests' / 'fixtures' / 'release-1'
_RELEASE_1 = {}


def release_1_source(name, blob) -> str:
    """Release 1's module ``name`` (tests/fixtures/release-1/<name>.txt), which must be git's blob ``blob``: a fixture
    that is not fails the test that reads it - it is never skipped."""
    data = (RELEASE_1_FIXTURES / f'{name}.txt').read_bytes()
    if git_blob_id(data) != blob:
        raise AssertionError(f'tests/fixtures/release-1/{name}.txt is not release 1\'s blob {blob}')
    return data.decode('utf-8')


def release_1_package():
    """Release 1's docx_package module, from its pinned fixture (imports resolve in this tree's studio package, which
    has the same bounded runner)."""
    if 'module' not in _RELEASE_1:
        module = types.ModuleType('laned_release_1_docx_package')
        module.__package__ = 'studio.fable'
        exec(compile(release_1_source('docx_package.py', RELEASE_1_PACKAGE_BLOB), 'release-1 docx_package.py',
                     'exec'), module.__dict__)
        _RELEASE_1['module'] = module
    return _RELEASE_1['module']


class ReleaseOneCase(SimpleTestCase):
    """A test that compares with release 1's package (release_1_package: never skipped)."""

    def release_1(self):
        return release_1_package()

    def assert_release_1_package(self, data):
        """``data`` gives release 2's package byte for byte as release 1's, and the same removal counts."""
        ours = docx_package._safe_package(data)
        theirs = self.release_1()._safe_package(data)
        self.assertEqual(ours[0], theirs[0])
        self.assertEqual(ours[1], theirs[1])


# --- synthetic Word files (the Word area's shape builders, rebuilt; every text invented) ----------------------------

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
MAIN = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'
DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
NS = (f'xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" xmlns:v="urn:schemas-microsoft-com:vml" '
      'xmlns:o="urn:schemas-microsoft-com:office:office" '
      'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
      'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
      'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" mc:Ignorable="w14"')
DEFAULTS = {'rels': 'application/vnd.openxmlformats-package.relationships+xml', 'xml': 'application/xml',
            'png': 'image/png', 'emf': 'image/x-emf', 'wmf': 'image/x-wmf', 'docx': DOCX,
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'html': 'text/html',
            'txt': 'text/plain', 'bin': 'application/vnd.ms-office.activeX'}
EMF = b'\x01\x00\x00\x00 synthetic EMF preview picture'
WMF = b'\xd7\xcd\xc6\x9a synthetic WMF preview picture'
PNG_BYTES = b'\x89PNG\r\n\x1a\n synthetic PNG preview picture'
XLSX = b'PK\x03\x04 synthetic workbook bytes SECRETBOOK'


def preview_pdf(text):
    """A one-page PDF that draws ``text`` (Helvetica): a preview as Mac Word writes one (D-R2-40, the 7.4 corpus's
    R1-L0e)."""
    stream = f'BT /F1 18 Tf 10 20 Td ({text}) Tj ET'.encode('latin-1')
    objects = [b'<</Type/Catalog/Pages 2 0 R>>', b'<</Type/Pages/Kids[3 0 R]/Count 1>>',
               b'<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 60]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>',
               b'<</Length %d>>stream\n' % len(stream) + stream + b'\nendstream',
               b'<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>']
    out, offsets = bytearray(b'%PDF-1.4\n'), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b'%d 0 obj\n' % number + body + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objects) + 1)
    out += b''.join(b'%010d 00000 n \n' % offset for offset in offsets)
    out += b'trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n' % (len(objects) + 1, xref)
    return bytes(out)


SYNTHETIC_PDF_PREVIEW = preview_pdf('PDFPREVIEW note')


def t(text):
    return f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def p(*inner):
    return f'<w:p>{"".join(inner)}</w:p>'


def rel(rid, kind, target, mode=None):
    kind = kind if kind.startswith('http') else f'{R}/{kind}'
    mode = f' TargetMode="{mode}"' if mode else ''
    return f'<Relationship Id="{rid}" Type="{kind}" Target="{target}"{mode}/>'


def rels(*rows):
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="{PKG}">{"".join(rows)}'
            '</Relationships>')


def override(part, ctype):
    return f'<Override PartName="/{part}" ContentType="{ctype}"/>'


def zipped(entries):
    """A zip of ``entries`` with one fixed timestamp (the bytes are the same whenever it is built)."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        for name, content in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 26, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    return out.getvalue()


def package(body, document_rels=(), parts=(), overrides=(), headers=None, footnotes=None):
    """A .docx of ``body`` (and, when given, headers {'header1.xml': inner} and the inner of footnote 2)."""
    drels, over, extra, section = list(document_rels), [override('word/document.xml', MAIN)], list(parts), ''
    for name, inner in (headers or {}).items():
        rid = 'rIdH' + name.split('.')[0]
        drels.append(rel(rid, 'header', name))
        over.append(override(f'word/{name}',
                             'application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml'))
        extra.append((f'word/{name}', f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:hdr {NS}>{inner}'
                                      '</w:hdr>'))
        section += f'<w:headerReference w:type="default" r:id="{rid}"/>'
    if footnotes is not None:
        drels.append(rel('rIdFn', 'footnotes', 'footnotes.xml'))
        over.append(override('word/footnotes.xml',
                             'application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml'))
        extra.append(('word/footnotes.xml', f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                                            f'<w:footnotes {NS}><w:footnote w:id="2">{footnotes}</w:footnote>'
                                            '</w:footnotes>'))
    entries = [
        ('[Content_Types].xml', f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="{CT}">'
         + ''.join(f'<Default Extension="{key}" ContentType="{value}"/>' for key, value in DEFAULTS.items())
         + ''.join(over) + ''.join(overrides) + '</Types>'),
        ('_rels/.rels', rels(rel('rId1', 'officeDocument', 'word/document.xml'))),
        ('word/document.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                              f'<w:document {NS}><w:body>{body}<w:sectPr>{section}<w:pgSz w:w="12240" w:h="15840"/>'
                              '</w:sectPr></w:body></w:document>')]
    if drels:
        entries.append(('word/_rels/document.xml.rels', rels(*drels)))
    return zipped(entries + extra)


def inner_docx(text='EMBEDDED SYNTHETIC TEXT'):
    return package(p(t(text)))


SHAPETYPE = ('<v:shapetype id="_x0000_t75" coordsize="21600,21600" o:spt="75" o:preferrelative="t" '
             'path="m@4@5l@4@11@9@11@9@5xe" filled="f" stroked="f"><v:stroke joinstyle="miter"/></v:shapetype>')


def vshape(rid='rIdPrev', sid='_x0000_i1025', inner=None, style='width:300pt;height:45pt'):
    inner = inner if inner is not None else f'<v:imagedata r:id="{rid}" o:title=""/>'
    return f'<v:shape id="{sid}" type="#_x0000_t75" style="{style}" o:ole="">{inner}</v:shape>'


def ole(prog='Excel.Sheet.12', rid='rIdOle', sid='_x0000_i1025', aspect='Content', kind='Embed', more=''):
    return (f'<o:OLEObject Type="{kind}" ProgID="{prog}" ShapeID="{sid}" DrawAspect="{aspect}" ObjectID="_1700000001" '
            f'r:id="{rid}"' + (f'>{more}</o:OLEObject>' if more else '/>'))


def drawing(rid='rIdPic', attribute='r:embed'):
    return ('<w:drawing><wp:inline><wp:extent cx="3600000" cy="540000"/><wp:docPr id="1" name="p"/><a:graphic>'
            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr>'
            '<pic:cNvPr id="1" name="p"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill>'
            f'<a:blip {attribute}="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm>'
            '<a:off x="0" y="0"/><a:ext cx="3600000" cy="540000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/>'
            '</a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing>')


def wps_textbox(text):
    return ('<w:drawing><wp:inline><wp:extent cx="3600000" cy="540000"/><wp:docPr id="7" name="tb"/><a:graphic>'
            '<a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"><wps:wsp>'
            '<wps:cNvSpPr/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="3600000" cy="540000"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></wps:spPr><wps:txbx><w:txbxContent>{p(t(text))}'
            '</w:txbxContent></wps:txbx><wps:bodyPr/></wps:wsp></a:graphicData></a:graphic></wp:inline></w:drawing>')


def vml_textbox(text):
    return (f'<v:shape id="tb1" type="#_x0000_t202" style="width:200pt;height:40pt"><v:textbox><w:txbxContent>'
            f'{p(t(text))}</w:txbxContent></v:textbox></v:shape>')


def fc(kind):
    return f'<w:r><w:fldChar w:fldCharType="{kind}"/></w:r>'


def instr(text):
    return f'<w:r><w:instrText xml:space="preserve">{escape(text)}</w:instrText></w:r>'


def field(instruction, result):
    return fc('begin') + instr(instruction) + fc('separate') + t(result) + fc('end')


BEFORE, AFTER = p(t('OWNBEFORE text')), p(t('OWNAFTER text'))
INC = ' INCLUDETEXT "c:\\\\synthetic\\\\SECRET.docx" '
OBJECT_PARTS = (('word/media/image1.emf', EMF), ('word/embeddings/Microsoft_Excel_Worksheet.xlsx', XLSX))
OBJECT_RELS = (rel('rIdPrev', 'image', 'media/image1.emf'),
               rel('rIdOle', 'package', 'embeddings/Microsoft_Excel_Worksheet.xlsx'))
DOCX_PARTS = (('word/media/image1.emf', EMF), ('word/embeddings/Microsoft_Word_Document.docx', inner_docx()))
DOCX_RELS = (rel('rIdPrev', 'image', 'media/image1.emf'),
             rel('rIdOle', 'package', 'embeddings/Microsoft_Word_Document.docx'))
OBJECTS, CONTROLS = 'objects', 'controls'


def in_object(*inner, attributes=' w:dxaOrig="6000" w:dyaOrig="900"'):
    return BEFORE + p('<w:r><w:object' + attributes + '>' + ''.join(inner) + '</w:object></w:r>') + AFTER


def object_shapes():
    """(label, a Word file, None when it is coded or the kind it is refused under): the Word area's B and E tables.
    The outcome of each was measured on LibreOffice 24.2.7 and 7.4 (word-scratch/image-corpus, RESULT-7.4.md): a
    refused shape is one release 1 coded with what its object held missing, or with nothing in its place."""
    embedded = ('word/embeddings/Microsoft_Word_Document.docx', inner_docx())
    bare = '<w:r><w:object w:dxaOrig="6000" w:dyaOrig="900">' + ole('Word.Document.12') + '</w:object></w:r>'
    sized = ('<w:r><w:object w:dxaOrig="6000" w:dyaOrig="900">' + SHAPETYPE + vshape(inner='')
             + ole('Word.Document.12') + '</w:object></w:r>')
    preview = SHAPETYPE + vshape()
    return [
        ('B01 object, EMF preview, xlsx', in_object(preview, ole()), OBJECT_RELS, OBJECT_PARTS, None),
        ('B02 object, WMF preview', in_object(preview, ole()), (rel('rIdPrev', 'image', 'media/image1.wmf'),
                                                               OBJECT_RELS[1]),
         (('word/media/image1.wmf', WMF), OBJECT_PARTS[1]), None),
        ('B03 object, PNG preview', in_object(preview, ole()), (rel('rIdPrev', 'image', 'media/image1.png'),
                                                               OBJECT_RELS[1]),
         (('word/media/image1.png', PNG_BYTES), OBJECT_PARTS[1]), None),
        ('B04 object, no preview, xlsx', in_object(ole()), OBJECT_RELS[1:], OBJECT_PARTS[1:], OBJECTS),
        ('B05 object, no preview, embedded docx', in_object(ole('Word.Document.12')), DOCX_RELS[1:], (embedded,),
         OBJECTS),
        ('B06 object, shapetype only', in_object(SHAPETYPE, ole('Word.Document.12')), DOCX_RELS[1:], (embedded,),
         OBJECTS),
        ('B07 object, shape without imagedata', in_object(SHAPETYPE, vshape(inner=''), ole('Word.Document.12')),
         DOCX_RELS[1:], (embedded,), OBJECTS),
        ('B08 object, imagedata relationship missing', in_object(SHAPETYPE, vshape('rIdGone'), ole('Word.Document.12')),
         DOCX_RELS[1:], (embedded,), OBJECTS),
        ('B09 object, imagedata part missing', in_object(preview, ole('Word.Document.12')), DOCX_RELS, (embedded,),
         OBJECTS),
        ('B10 object, imagedata External', in_object(preview, ole('Word.Document.12')),
         (rel('rIdPrev', 'image', 'file:///nonexistent/x.emf', 'External'), DOCX_RELS[1]), (embedded,), OBJECTS),
        ('B11 object, EMF preview, embedded docx', in_object(preview, ole('Word.Document.12')), DOCX_RELS, DOCX_PARTS,
         None),
        ('B12 object, w:drawing preview, objectEmbed', in_object(
            drawing(), '<w:objectEmbed w:drawAspect="content" r:id="rIdOle" w:progId="Excel.Sheet.12" w:shapeId="1" '
                       'w:fieldCodes=""/>', attributes=''),
         (rel('rIdPic', 'image', 'media/image1.emf'), OBJECT_RELS[1]), OBJECT_PARTS, None),
        ('B13 object, w:drawing text box, objectEmbed', in_object(
            wps_textbox('WPSTOKEN'), '<w:objectEmbed w:drawAspect="content" r:id="rIdOle" w:progId="Excel.Sheet.12" '
                                     'w:shapeId="1" w:fieldCodes=""/>', attributes=''),
         OBJECT_RELS[1:], OBJECT_PARTS[1:], OBJECTS),
        ('B14 object, preview inside mc:AlternateContent', in_object(
            '<mc:AlternateContent><mc:Choice Requires="wps">' + drawing() + '</mc:Choice><mc:Fallback>' + SHAPETYPE
            + vshape('rIdPic') + '</mc:Fallback></mc:AlternateContent>', ole(), attributes=''),
         (rel('rIdPic', 'image', 'media/image1.emf'), OBJECT_RELS[1]), OBJECT_PARTS, OBJECTS),
        ('B15 object shown as an icon', in_object(preview, ole('Package', aspect='Icon')),
         (rel('rIdPrev', 'image', 'media/image1.emf'), DOCX_RELS[1]), DOCX_PARTS, None),
        ('B16 OLEObject in a w:pict, EMF preview', BEFORE + p('<w:r><w:pict>' + preview + ole() + '</w:pict></w:r>')
         + AFTER, OBJECT_RELS, OBJECT_PARTS, None),
        ('B17 OLEObject in a w:pict, no preview', BEFORE + p('<w:r><w:pict>' + ole('Word.Document.12')
                                                            + '</w:pict></w:r>') + AFTER,
         DOCX_RELS[1:], (embedded,), OBJECTS),
        ('B18 objectEmbed directly in a run', BEFORE + p('<w:r><w:objectEmbed w:drawAspect="content" r:id="rIdOle" '
                                                         'w:progId="Word.Document.12" w:shapeId="1" w:fieldCodes=""/>'
                                                         '</w:r>') + AFTER,
         DOCX_RELS[1:], (embedded,), OBJECTS),
        ('B19 object: VML text box beside the picture', in_object(preview, vml_textbox('VMLTOKEN'), ole(),
                                                                  attributes=''),
         OBJECT_RELS, OBJECT_PARTS, OBJECTS),
        ('B20 object: drawing preview and a VML text box', in_object(drawing(), vml_textbox('VMLTOKEN'), ole(),
                                                                     attributes=''),
         (rel('rIdPic', 'image', 'media/image1.emf'), OBJECT_RELS[1]), OBJECT_PARTS, OBJECTS),
        ('B21 linked object, EMF preview', in_object(preview, ole(kind='Link', more='<o:LinkType>EnhancedMetaFile'
                                                                                   '</o:LinkType><o:LockedField>false'
                                                                                   '</o:LockedField>')),
         (OBJECT_RELS[0], rel('rIdOle', 'oleObject', 'file:///nonexistent/book.xlsx', 'External')), OBJECT_PARTS[:1],
         None),
        ('B22 object: text run content (w:t) inside w:object', in_object(preview, '<w:t>STRAYTEXT</w:t>', ole(),
                                                                         attributes=''),
         OBJECT_RELS, OBJECT_PARTS, OBJECTS),
        ('B23 object in the header, no preview', None, None, None, OBJECTS),
        ('B24 empty w:object', BEFORE + p('<w:r><w:object w:dxaOrig="1440" w:dyaOrig="900"/></w:r>') + AFTER, (), (),
         None),
        ('B25 object, v:rect with imagedata', in_object(
            '<v:rect id="_x0000_i1025" style="width:300pt;height:45pt" o:ole="" filled="f" stroked="f"><v:imagedata '
            'r:id="rIdPrev" o:title=""/></v:rect>', ole(), attributes=''), OBJECT_RELS, OBJECT_PARTS, None),
        ('B26 object, imagedata in a v:group', in_object(
            SHAPETYPE + '<v:group id="g1" style="width:300pt;height:45pt" coordsize="3000,450">'
            + vshape(style='width:3000;height:450') + '</v:group>', ole(), attributes=''), OBJECT_RELS, OBJECT_PARTS,
         None),
        ('B27 object, v:fill picture only', in_object(SHAPETYPE, vshape(inner='<v:fill r:id="rIdPrev" o:title="" '
                                                                               'type="frame"/>'),
                                                      ole('Word.Document.12'), attributes=''),
         DOCX_RELS, DOCX_PARTS, OBJECTS),
        ('E01 bare object mid-paragraph', BEFORE + p(t('AAA '), bare, t(' BBB')) + AFTER, DOCX_RELS[1:], (embedded,),
         OBJECTS),
        ('E02 bare object in a table cell', BEFORE + '<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="4000"/></w:tblGrid>'
                                                     '<w:tr><w:tc><w:tcPr/>' + p(t('CELL1 '), bare) + '</w:tc></w:tr>'
                                                     '</w:tbl>' + AFTER, DOCX_RELS[1:], (embedded,), OBJECTS),
        ('E03 object whose shape holds a text box', in_object(vml_textbox('VMLTOKEN'), ole('Word.Document.12'),
                                                              attributes=''),
         DOCX_RELS[1:], (embedded,), OBJECTS),
        ('E04 field from one cell to the next', BEFORE + '<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="4000"/>'
                                                         '<w:gridCol w:w="4000"/></w:tblGrid><w:tr><w:tc><w:tcPr/>'
         + p(t('CELL1 '), fc('begin'), instr(INC), t('TAIL1')) + '</w:tc><w:tc><w:tcPr/>'
         + p(t('HEAD2 '), fc('separate'), t('FIELDRESULT'), fc('end')) + '</w:tc></w:tr></w:tbl>' + AFTER, (), (),
         None),
        ('E05 field begun in a text box, ended in the body', BEFORE + p(
            '<w:r><w:pict><v:shape id="tb1" type="#_x0000_t202" style="width:300pt;height:60pt"><v:textbox>'
            '<w:txbxContent>' + p(t('BOX1 '), fc('begin'), instr(INC)) + p(t('BOX2')) + '</w:txbxContent></v:textbox>'
            '</v:shape></w:pict></w:r>', t('INBODY ')) + p(t('BODY2 '), fc('end'), t(' TAIL')) + AFTER, (), (), None),
        ('E06 field begun in one footnote, ended in another', None, None, None, None),
        ('E07 header relationship with TargetMode="internal"', None, None, None, None),
        ('E08 bare object in a tracked deletion',
         BEFORE + p('<w:del w:id="1" w:author="S" w:date="2026-11-25T00:00:00Z">' + bare + '</w:del>', t('LIVE'))
         + AFTER, DOCX_RELS[1:], (embedded,), OBJECTS),
        ('E09 object in mc:Choice, pict in Fallback', BEFORE + p(
            '<w:r><mc:AlternateContent><mc:Choice Requires="w14"><w:object>' + preview + ole('Word.Document.12')
            + '</w:object></mc:Choice><mc:Fallback><w:pict>' + preview + '</w:pict></mc:Fallback>'
            '</mc:AlternateContent></w:r>') + AFTER, DOCX_RELS, DOCX_PARTS, None),
        ('E10 sized object without imagedata, mid-paragraph', BEFORE + p(t('AAA '), sized, t(' BBB')) + AFTER,
         DOCX_RELS[1:], (embedded,), OBJECTS),
        ('E11 object, imagedata with r:href beside r:id', in_object(
            SHAPETYPE, vshape(inner='<v:imagedata r:id="rIdPrev" r:href="rIdHref" o:title=""/>'),
            ole('Word.Document.12'), attributes=''),
         DOCX_RELS + (rel('rIdHref', 'image', 'file:///nonexistent/y.emf', 'External'),), DOCX_PARTS, None),
        ('E12 object, zero-byte preview part', in_object(preview, ole('Word.Document.12'), attributes=''), DOCX_RELS,
         (('word/media/image1.emf', b''), DOCX_PARTS[1]), OBJECTS),
        ('E13 object, o:relid on imagedata', in_object(SHAPETYPE, vshape(inner='<v:imagedata o:relid="rIdPrev" '
                                                                               'o:title=""/>'),
                                                       ole('Word.Document.12'), attributes=''),
         DOCX_RELS, DOCX_PARTS, None),
        ('E14 object, r:pict on imagedata', in_object(SHAPETYPE, vshape(inner='<v:imagedata r:pict="rIdPrev" '
                                                                              'o:title=""/>'),
                                                      ole('Word.Document.12'), attributes=''),
         DOCX_RELS, DOCX_PARTS, OBJECTS),
        ('E15 text in an unknown child of w:object', in_object(preview, '<w:p>' + t('CHILDTEXT') + '</w:p>',
                                                               ole('Word.Document.12'), attributes=''),
         DOCX_RELS, DOCX_PARTS, OBJECTS),
        ('E16 v:textpath (WordArt) as the object shape', in_object(
            '<v:shape id="wa" type="#_x0000_t136" style="width:200pt;height:40pt">'
            '<v:textpath style="font-family:Arial" string="WORDARTTOKEN"/></v:shape>', ole('Word.Document.12'),
            attributes=''), DOCX_RELS[1:], (embedded,), OBJECTS),
        ('E22 embedded video-like: w:object with w:movie', in_object(preview, '<w:movie r:id="rIdOle"/>',
                                                                     attributes=''),
         DOCX_RELS, DOCX_PARTS, None),
    ]


def object_packages():
    """(label, bytes, expected kind or None) of object_shapes(), with the shapes that need a story of their own."""
    embedded = ('word/embeddings/Microsoft_Word_Document.docx', inner_docx())
    out = []
    for label, body, document_rels, parts, expected in object_shapes():
        if label.startswith('B23'):
            data = package(BEFORE + AFTER, parts=(embedded, ('word/_rels/header1.xml.rels', rels(DOCX_RELS[1]))),
                           headers={'header1.xml': p(t('HEADEROWN '), '<w:r><w:object>' + ole('Word.Document.12')
                                                     + '</w:object></w:r>')})
        elif label.startswith('E06'):
            data = package(p(t('OWNBEFORE'), '<w:r><w:footnoteReference w:id="2"/></w:r>') + AFTER,
                           footnotes=p(t(' FOOTA '), fc('begin'), instr(INC)) + '</w:footnote><w:footnote w:id="3">'
                           + p(t(' FOOTB '), fc('end'), t('FOOTC')))
        elif label.startswith('E07'):
            normal = package(BEFORE + AFTER, headers={'header1.xml': p(t('HEADEROWN'))})
            with zipfile.ZipFile(io.BytesIO(normal)) as archive:
                entries = [(name, archive.read(name)) for name in archive.namelist()]
            lowered = b'Target="header1.xml" TargetMode="internal"'
            data = zipped([(name, content.replace(b'Target="header1.xml"', lowered)
                            if name.endswith('document.xml.rels') else content) for name, content in entries])
        else:
            data = package(body, document_rels, parts)
        out.append((label, data, expected))
    return out


def control_packages():
    """(label, bytes, expected kind or None): the Word area's C table - ActiveX controls, binary and property bags."""
    ax_rels = (rel('rIdCtl', 'control', 'activeX/activeX1.xml'),)
    ax_over = (override('word/activeX/activeX1.xml', 'application/vnd.ms-office.activeX+xml'),)
    ctl = '<w:control r:id="rIdCtl" w:name="TextBox1" w:shapeid="_x0000_i1026"/>'
    binary = (('word/activeX/activeX1.xml', '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<ax:ocx '
               'ax:classid="{8BD21D10-EC42-11CE-9E0D-00AA006002F3}" ax:persistence="persistStreamInit" r:id="rId1" '
               f'xmlns:ax="http://schemas.microsoft.com/office/2006/activeX" xmlns:r="{R}"/>'),
              ('word/activeX/_rels/activeX1.xml.rels', rels(rel(
                  'rId1', 'http://schemas.microsoft.com/office/2006/relationships/activeXControlBinary',
                  'activeX1.bin'))),
              ('word/activeX/activeX1.bin', b'\x10\x1d\xd2\x8b synthetic control value CTLVALUE'))

    def bag(classid, value, name='Value'):
        return (('word/activeX/activeX1.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<ax:ocx '
                 f'xmlns:ax="http://schemas.microsoft.com/office/2006/activeX" xmlns:r="{R}" ax:classid="{classid}" '
                 f'ax:persistence="persistPropertyBag"><ax:ocxPr ax:name="{name}" ax:value="{value}"/></ax:ocx>'),)
    preview_rels = (rel('rIdPrev', 'image', 'media/image1.wmf'),)
    preview_parts = (('word/media/image1.wmf', WMF),)
    shape = vshape(sid='_x0000_i1026')
    empty_shape = vshape(sid='_x0000_i1026', inner='')
    shapes = [
        ('C01 text box control, binary, WMF preview', in_object(SHAPETYPE, shape, ctl), ax_rels + preview_rels,
         binary + preview_parts, None),
        ('C02 text box control, binary, shape without imagedata', in_object(SHAPETYPE, empty_shape, ctl), ax_rels,
         binary, CONTROLS),
        ('C03 text box control, binary, no shape', in_object(ctl), ax_rels, binary, CONTROLS),
        ('C04 control in a w:pict, WMF preview',
         BEFORE + p('<w:r><w:pict>' + SHAPETYPE + shape + ctl + '</w:pict></w:r>') + AFTER, ax_rels + preview_rels,
         binary + preview_parts, None),
        ('C05 control in a w:pict, no preview', BEFORE + p('<w:r><w:pict>' + SHAPETYPE + empty_shape + ctl
                                                          + '</w:pict></w:r>') + AFTER, ax_rels, binary, CONTROLS),
        ('C06 HTML:Text control, property bag, WMF preview', in_object(SHAPETYPE, shape, ctl), ax_rels + preview_rels,
         bag('{5512D11A-5CC6-11CF-8D67-00AA00BDCE1D}', 'CTLVALUE bag') + preview_parts, None),
        ('C07 text box control, property bag, no preview', in_object(SHAPETYPE, empty_shape, ctl), ax_rels,
         bag('{8BD21D10-EC42-11CE-9E0D-00AA006002F3}', 'CTLVALUE bag'), CONTROLS),
        ('C08 check box control, property bag, no preview', in_object(SHAPETYPE, empty_shape, ctl), ax_rels,
         bag('{8BD21D40-EC42-11CE-9E0D-00AA006002F3}', 'CTLVALUE consent', 'Caption'), CONTROLS),
        ('C09 control directly in a run', BEFORE + p('<w:r>' + ctl + '</w:r>') + AFTER, ax_rels, binary, CONTROLS),
    ]
    return [(label, package(body, document_rels, parts, ax_over), expected)
            for label, body, document_rels, parts, expected in shapes]


class ObjectAndControlTests(ReleaseOneCase):
    """R2-29: a removal keeps a picture in its place, or the file is refused - a picture being a v:imagedata (r:id or
    o:relid) or an a:blip (r:embed) whose relationship names a part that is sent and not empty."""

    def assert_outcomes(self, packages):
        compared = 0
        for label, data, expected in packages:
            with self.subTest(label):
                if expected is None:  # coded, edited exactly as release 1 edits it
                    docx_package._safe_package(data)
                    self.assert_release_1_package(data)
                    compared += 1
                    continue
                with self.assertRaises(docx_package.ContentNotShown) as caught:
                    docx_package._safe_package(data)
                counts = {'documents': 0, 'objects': 0, 'controls': 0, 'fields': 0, expected: 1}
                self.assertEqual((caught.exception.code, caught.exception.counts),
                                 (docx_package.INSERTED_OBJECT, counts))
                self.release_1()._safe_package(data)  # the positive control: release 1 coded it
        return compared

    def test_an_object_keeps_its_preview_or_the_file_is_refused(self):
        packages = object_packages()
        self.assertEqual(len(packages), 44)
        self.assertEqual(sum(expected is None for _, _, expected in packages), 19)
        self.assert_outcomes(packages)

    def test_a_control_keeps_its_preview_or_the_file_is_refused(self):
        packages = control_packages()
        self.assertEqual([expected for _, _, expected in packages],
                         [None, CONTROLS, CONTROLS, None, CONTROLS, None, CONTROLS, CONTROLS, CONTROLS])
        self.assert_outcomes(packages)

    def test_a_preview_is_a_part_that_is_sent(self):
        def preview_object(target, *, mode=None, part_name='word/media/image1.emf', content=EMF, inner=None, rows=None,
                           extra=()):
            parts = (DOCX_PARTS[1],) if part_name is None else ((part_name, content), DOCX_PARTS[1])
            return package(in_object(SHAPETYPE, vshape(inner=inner), ole('Word.Document.12')),
                           (*(rows or (rel('rIdPrev', 'image', target, mode),)), DOCX_RELS[1]), parts + tuple(extra))
        drawn = in_object(drawing(), '<w:objectEmbed r:id="rIdOle" w:progId="Word.Document.12"/>', attributes='')
        refused = {
            'its relationship missing': package(in_object(SHAPETYPE, vshape('rIdGone'), ole('Word.Document.12')),
                                                DOCX_RELS[1:], DOCX_PARTS[1:]),
            'its part missing': preview_object('media/image1.emf', part_name=None),
            'External': preview_object('file:///synthetic/preview.emf', mode='External', part_name=None),
            'External, though a part of that name is present': preview_object('media/image1.emf', mode='External'),
            'absent (no imagedata)': preview_object('media/image1.emf', inner=''),
            'zero bytes': preview_object('media/image1.emf', content=b''),
            'named by r:pict (not a picture id)': preview_object('media/image1.emf', inner='<v:imagedata '
                                                                                         'r:pict="rIdPrev"/>'),
            'a drawing whose a:blip links (r:link) the picture': package(
                in_object(drawing(attribute='r:link'), '<w:objectEmbed r:id="rIdOle" w:progId="Word.Document.12"/>',
                          attributes=''), (rel('rIdPic', 'image', 'media/image1.emf'), DOCX_RELS[1]), DOCX_PARTS),
            # refutation round 1, loss[0]: a part that is not empty but no picture leaves nothing in the object's place
            'one byte': preview_object('media/image1.emf', content=b'\x00'),
            'bytes in no picture format': preview_object('media/image1.emf', content=b'plain words, no picture'),
            'the embedded document itself': preview_object('media/image1.emf', inner='<v:imagedata r:id="rIdOle"/>'),
            # loss[5]: LibreOffice opens a preview by its exact name only (Word also finds these; LibreOffice draws
            # nothing)
            'a percent-encoded name that is present': preview_object('media/image%201.emf',
                                                                     part_name='word/media/image 1.emf'),
            'a name present only without case': preview_object('media/IMAGE1.EMF'),
            'a drawing whose a:blip embeds a percent-encoded name that is present': package(
                drawn, (rel('rIdPic', 'image', 'media/image%201.emf'), DOCX_RELS[1]),
                (('word/media/image 1.emf', EMF), DOCX_PARTS[1])),
            # refutation round 2, loss[0] and refuse[0]: LibreOffice opens a picture's target as a string - no '.'
            # segment, fragment or '..' under a root resolved - so these name no part it opens, and it draws nothing
            'a drawing whose a:blip embeds ./media/image1.emf': package(
                drawn, (rel('rIdPic', 'image', './media/image1.emf'), DOCX_RELS[1]), DOCX_PARTS),
            # loss[5]: words that begin as a signature's first bytes are no picture; nor is a BMP LibreOffice does not
            # detect (a 108-byte header with its reserved bytes set: not drawn on 24.2.7)
            'words that begin BM': preview_object('media/image1.emf', content=b'BMI 31.4 kg/m2, words, no picture'),
            'words that begin GIF8': preview_object('media/image1.emf', content=b'GIF8 lesions noted, words'),
            'a BMP whose 108-byte header has its reserved bytes set': preview_object(
                'media/image1.emf', content=b'BM' + bytes(4) + b'AB\x00\x00' + bytes(4) + b'l\x00\x00\x00'
                + bytes(104)),
            # D-R2-45: PICT and SVG stay refused on purpose - 7.4 draws them, but neither has a signature as strong as
            # the accepted ones (a broken one could be coded with nothing in its place)
            'a PICT preview': preview_object('media/image1.pct', part_name='word/media/image1.pct',
                                             content=bytes(2) + bytes(8) + b'\x00\x11\x02\xff\x0c\x00 synthetic PICT'),
            'an SVG preview': preview_object('media/image1.svg', part_name='word/media/image1.svg',
                                             content=b'<svg xmlns="http://www.w3.org/2000/svg"><text>SVG</text></svg>'),
            # D-R2-45 (refutation round 3, refuse[0]): a gzip counts only when it inflates to an EMF or WMF signature
            'a gzip of words named .emz': preview_object('media/image1.emz', part_name='word/media/image1.emz',
                                                         content=gzip.compress(b'plain words, no picture', mtime=0)),
            'a gzip of a PNG named .emz': preview_object('media/image1.emz', part_name='word/media/image1.emz',
                                                         content=gzip.compress(PNG_BYTES, mtime=0)),
            'a gzip cut inside its header': preview_object('media/image1.emz', part_name='word/media/image1.emz',
                                                           content=gzip.compress(EMF, mtime=0)[:6]),
            'a gzip whose deflate stream is corrupt': preview_object(
                'media/image1.emz', part_name='word/media/image1.emz',
                content=gzip.compress(EMF, mtime=0)[:10] + b'\xff' * 24),
            # loss[1]: LibreOffice reads an id's first row that has an Id, a Type and a Target; a later row with a
            # picture is never opened
            'an id written twice, its first row naming a missing part': preview_object('', rows=(
                rel('rIdPrev', 'image', 'media/missing.emf'), rel('rIdPrev', 'image', 'media/image1.emf'))),
            'an id written twice, its first row naming a part that is no picture': preview_object('', rows=(
                rel('rIdPrev', 'image', 'media/words.emf'), rel('rIdPrev', 'image', 'media/image1.emf')),
                extra=(('word/media/words.emf', b'plain words, no picture'),)),
            'an id written twice, its first row naming an empty part': preview_object('', rows=(
                rel('rIdPrev', 'image', 'media/empty.emf'), rel('rIdPrev', 'image', 'media/image1.emf')),
                extra=(('word/media/empty.emf', b''),)),
            'a relationship with no Type': preview_object('', rows=(
                '<Relationship Id="rIdPrev" Target="media/image1.emf"/>',)),
        }
        for target in ('./media/image1.emf', 'media/./image1.emf', '/./word/media/image1.emf',
                       '/word/./media/image1.emf', '/word/../word/media/image1.emf', 'media/image1.emf#frag',
                       'media/image1.emf#'):
            refused[f'a target written {target!r}'] = preview_object(target)
        refused['a target written \'media//../image1.emf\', the part word/image1.emf'] = preview_object(
            'media//../image1.emf', part_name='word/image1.emf')
        # a '.' or '..' left names no part even where a zip entry is so named: lane D cannot tell whether LibreOffice's
        # storage would resolve it (fail closed)
        refused['a target written \'./media/image1.emf\', a zip entry word/./media/image1.emf'] = preview_object(
            './media/image1.emf', part_name='word/./media/image1.emf')
        refused['a target written \'/word/../word/media/image1.emf\', a zip entry so named'] = preview_object(
            '/word/../word/media/image1.emf', part_name='word/../word/media/image1.emf')
        for label, data in refused.items():
            with self.subTest(f'refused: {label}'):
                with self.assertRaises(docx_package.ContentNotShown) as caught:
                    docx_package._safe_package(data)
                self.assertEqual(caught.exception.counts['objects'], 1)
        kept = {
            'a name present as written': preview_object('media/image1.emf'),
            'o:relid': preview_object('media/image1.emf', inner='<v:imagedata o:relid="rIdPrev"/>'),
            'a drawing whose a:blip embeds a name present as written': package(
                drawn, (rel('rIdPic', 'image', 'media/image1.emf'), DOCX_RELS[1]), DOCX_PARTS),
            # refutation round 2, loss[1]: the first row LibreOffice reads names the picture (an External row is
            # dropped from the package; a row with no Type or no Target is one LibreOffice does not read)
            'an id written twice, the picture first': preview_object('', rows=(
                rel('rIdPrev', 'image', 'media/image1.emf'), rel('rIdPrev', 'image', 'media/missing.emf'))),
            'an id written twice, an External row first': preview_object('', rows=(
                rel('rIdPrev', 'image', 'file:///synthetic/x.emf', 'External'),
                rel('rIdPrev', 'image', 'media/image1.emf'))),
            'an id written twice, its first row with no Type': preview_object('', rows=(
                '<Relationship Id="rIdPrev" Target="media/missing.emf"/>',
                rel('rIdPrev', 'image', 'media/image1.emf'))),
            'an id written twice, its first row with an empty Target': preview_object('', rows=(
                rel('rIdPrev', 'image', ''), rel('rIdPrev', 'image', 'media/image1.emf'))),
            # D-R2-40 (the lead's 7.4 run on 3ad91321e, R1-L0e): a PDF preview, as Mac Word writes it, is drawn
            'a PDF preview (R1-L0e)': preview_object('media/image1.pdf', part_name='word/media/image1.pdf',
                                                     content=SYNTHETIC_PDF_PREVIEW),
            # D-R2-45 (the lead's 7.4 run on 464b60de5): an EMZ and a WMZ, which inflate to an EMF and a WMF, are drawn
            'an EMZ preview': preview_object('media/image1.emz', part_name='word/media/image1.emz',
                                             content=gzip.compress(EMF, mtime=0)),
            'a WMZ preview': preview_object('media/image1.wmz', part_name='word/media/image1.wmz',
                                            content=gzip.compress(WMF, mtime=0)),
        }
        # loss[0] and refuse[0]: the names LibreOffice does open - rooted, a '..' to the root, an empty segment
        for target in ('/word/media/image1.emf', '../word/media/image1.emf', '../../word/media/image1.emf',
                       'media//image1.emf', '//word/media/image1.emf'):
            kept[f'a target written {target!r}'] = preview_object(target)
        # each picture format a preview is (loss[0]): EMF, placeable WMF, standard WMF in memory and on disk, PNG, JPEG,
        # GIF, BMP (a 40-byte header; refutation round 2, loss[5]), TIFF in both byte orders, and PDF (D-R2-40)
        for signature in (b'\x01\x00\x00\x00', b'\xd7\xcd\xc6\x9a', b'\x01\x00\x09\x00', b'\x02\x00\x09\x00',
                          b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff\xe0', b'GIF87a', b'GIF89a',
                          b'BM' + bytes(12) + b'(\x00\x00\x00', b'II*\x00', b'MM\x00*', b'%PDF-1.4'):
            kept[f'a picture that begins {signature!r}'] = preview_object(
                'media/image1.emf', content=signature + b' synthetic picture bytes')
        # loss[5]: BMPs LibreOffice draws on 24.2.7 - a 108-byte header with its reserved bytes zero, a 40-byte one with
        # them set
        kept['a BMP whose 108-byte header has its reserved bytes zero'] = preview_object(
            'media/image1.emf', content=b'BM' + bytes(12) + b'l\x00\x00\x00' + bytes(104))
        kept['a BMP whose 40-byte header has its reserved bytes set'] = preview_object(
            'media/image1.emf', content=b'BM' + bytes(4) + b'AB\x00\x00' + bytes(4) + b'(\x00\x00\x00' + bytes(36))
        for label, data in kept.items():
            with self.subTest(f'kept: {label}'):
                package_bytes, removed = docx_package._safe_package(data)
                self.assertEqual(removed['objects'], 1)
                self.assert_release_1_package(data)

    def test_a_picture_inside_what_a_removal_takes_stands_in_nothing(self):
        # refutation round 3, loss[4]: a picture counts for an object or a control only when it survives the removal -
        # one inside the w:control, the w:movie or the o:OLEObject a removal takes, or in the v:shapetype the drawing
        # branch drops, left nothing in the object's place (the control's caption lost); Word's own forms keep theirs
        imagedata = '<v:imagedata r:id="rIdPrev" o:title=""/>'
        empty_shape = vshape(sid='_x0000_i1031', inner='')
        full_shape = vshape(sid='_x0000_i1031')
        control = '<w:control r:id="rIdCtl" w:name="CheckBox1" w:shapeid="_x0000_i1031">{}</w:control>'
        empty_control = control.format('')
        bag = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<ax:ocx '
               f'xmlns:ax="http://schemas.microsoft.com/office/2006/activeX" xmlns:r="{R}" '
               'ax:classid="{8BD21D40-EC42-11CE-9E0D-00AA006002F3}" ax:persistence="persistPropertyBag">'
               '<ax:ocxPr ax:name="Caption" ax:value="CTLCAPTION consent given"/></ax:ocx>')
        no_picture_drawing = drawing('rIdNoSuch')

        def with_control(holder):
            return package(BEFORE + p('<w:r>' + holder + '</w:r>') + AFTER,
                           (rel('rIdCtl', 'control', 'activeX/activeX1.xml'),
                            rel('rIdPrev', 'image', 'media/image1.emf')),
                           (('word/activeX/activeX1.xml', bag), ('word/media/image1.emf', EMF)),
                           (override('word/activeX/activeX1.xml', 'application/vnd.ms-office.activeX+xml'),))

        def with_embedding(holder):
            return package(BEFORE + p('<w:r>' + holder + '</w:r>') + AFTER, DOCX_RELS, DOCX_PARTS)
        shapetype_with_picture = SHAPETYPE.replace('</v:shapetype>', imagedata + '</v:shapetype>')
        refused = {
            'inside the control (a w:object)': (with_control(
                '<w:object w:dxaOrig="6300" w:dyaOrig="960">' + SHAPETYPE + empty_shape + control.format(imagedata)
                + '</w:object>'), CONTROLS),
            'inside the control (a w:pict)': (with_control(
                '<w:pict>' + SHAPETYPE + empty_shape + control.format(imagedata) + '</w:pict>'), CONTROLS),
            'inside a w:movie beside an empty control': (with_control(
                '<w:object w:dxaOrig="6300" w:dyaOrig="960">' + SHAPETYPE + empty_shape + empty_control + '<w:movie>'
                + imagedata + '</w:movie></w:object>'), CONTROLS),
            'inside the o:OLEObject': (with_embedding(
                '<w:object w:dxaOrig="6300" w:dyaOrig="960">' + SHAPETYPE + empty_shape
                + ole('Word.Document.12', sid='_x0000_i1031', more=imagedata) + '</w:object>'), OBJECTS),
            'in the v:shapetype the drawing branch drops': (with_control(
                '<w:object w:dxaOrig="6300" w:dyaOrig="960">' + no_picture_drawing + shapetype_with_picture
                + empty_control + '</w:object>'), CONTROLS),
        }
        for label, (data, kind) in refused.items():
            with self.subTest(f'refused: {label}'):
                with self.assertRaises(docx_package.ContentNotShown) as caught:
                    docx_package._safe_package(data)
                self.assertEqual(caught.exception.counts[kind], 1)
                self.release_1()._safe_package(data)  # the bad shape: release 1 coded it
        kept = {
            'Word\'s form: the picture in the v:shape, the control empty': with_control(
                '<w:object w:dxaOrig="6300" w:dyaOrig="960">' + SHAPETYPE + full_shape + empty_control
                + '</w:object>'),
            'the OLE form: the picture in the v:shape': with_embedding(
                '<w:object w:dxaOrig="6300" w:dyaOrig="960">' + SHAPETYPE + full_shape
                + ole('Word.Document.12', sid='_x0000_i1031') + '</w:object>'),
            'the VML branch, the picture in the v:shapetype (kept with it)': with_control(
                '<w:object w:dxaOrig="6300" w:dyaOrig="960">' + shapetype_with_picture + empty_shape + empty_control
                + '</w:object>'),
        }
        for label, data in kept.items():
            with self.subTest(f'kept: {label}'):
                docx_package._safe_package(data)
                self.assert_release_1_package(data)

    def test_a_control_whose_preview_target_holds_a_dot_segment_is_refused_and_so_is_its_stored_conversion(self):
        # refutation round 2, refuse[0]: a check box control (C08's) whose WMF preview is named './media/image1.wmf' -
        # LibreOffice draws nothing, and the base shows the control's value - is refused, fresh and before a stored
        # conversion is read again (C8); named 'media/image1.wmf' (the control) it is coded with release 1's package
        def check_box(target):
            ctl = '<w:control r:id="rIdCtl" w:name="CheckBox1" w:shapeid="_x0000_i1026"/>'
            bag = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<ax:ocx '
                   f'xmlns:ax="http://schemas.microsoft.com/office/2006/activeX" xmlns:r="{R}" '
                   'ax:classid="{8BD21D40-EC42-11CE-9E0D-00AA006002F3}" ax:persistence="persistPropertyBag">'
                   '<ax:ocxPr ax:name="Caption" ax:value="CTLVALUE consent"/></ax:ocx>')
            return package(in_object(SHAPETYPE, vshape(sid='_x0000_i1026'), ctl),
                           (rel('rIdCtl', 'control', 'activeX/activeX1.xml'), rel('rIdPrev', 'image', target)),
                           (('word/activeX/activeX1.xml', bag), ('word/media/image1.wmf', WMF)),
                           (override('word/activeX/activeX1.xml', 'application/vnd.ms-office.activeX+xml'),))
        refused = check_box('./media/image1.wmf')
        with self.assertRaises(docx_package.ContentNotShown) as caught:
            docx_package._safe_package(refused)
        self.assertEqual((caught.exception.code, caught.exception.counts),
                         (docx_package.INSERTED_OBJECT, {'documents': 0, 'objects': 0, 'controls': 1, 'fields': 0}))
        with self.assertRaises(docx_package.ConversionRefused) as checked:
            docx_package.check_in_child(refused)
        self.assertEqual(checked.exception.code, docx_package.INSERTED_OBJECT)
        self.release_1()._safe_package(refused)  # the bad shape: release 1 coded it
        self.assertEqual(docx_package._safe_package(check_box('media/image1.wmf'))[1]['controls'], 1)
        self.assert_release_1_package(check_box('media/image1.wmf'))


class ImportHoldingNothingTests(ReleaseOneCase):
    """C9: a w:altChunk that holds nothing - the critic's shapes - is removed as release 1 removes it, so the package is
    release 1's, byte for byte (read from git); an External one and a w:subDoc are refused on purpose."""

    def test_an_import_that_holds_nothing_gives_release_1s_package(self):
        alt = '<w:altChunk r:id="rIdChunk"/>'
        shapes = {
            'no r:id': package(BEFORE + '<w:altChunk/>' + AFTER),
            'an r:id that names no relationship': package(BEFORE + '<w:altChunk r:id="rIdNone"/>' + AFTER),
            'a part that is missing': package(BEFORE + alt + AFTER, (rel('rIdChunk', 'aFChunk', 'afchunk1.docx'),)),
            'an empty text part': package(BEFORE + alt + AFTER, (rel('rIdChunk', 'aFChunk', 'empty.txt'),),
                                          (('word/empty.txt', b''),)),
            'an empty part with an Override': package(BEFORE + alt + AFTER, (rel('rIdChunk', 'aFChunk', 'empty.txt'),),
                                                      (('word/empty.txt', b''),),
                                                      (override('word/empty.txt', 'text/plain'),)),
            # refutation round 1, loss[4]: a name read by its URI path that names no part holds nothing either
            'a missing part named with a query': package(BEFORE + alt + AFTER,
                                                         (rel('rIdChunk', 'aFChunk', 'missing.docx?v=1'),)),
            'a missing part named by a file URI': package(BEFORE + alt + AFTER,
                                                          (rel('rIdChunk', 'aFChunk', 'file:///word/missing.docx'),)),
            # refutation round 2, loss[3]: a rootless path under a scheme that names no part, as LibreOffice opens it
            'a missing part named x:afchunk1.docx': package(BEFORE + alt + AFTER,
                                                            (rel('rIdChunk', 'aFChunk', 'x:afchunk1.docx'),)),
            # D-R2-40: a '..' past the root, dropped as the doctor's Word drops it, still names no part
            'a missing part named past the root': package(BEFORE + alt + AFTER,
                                                          (rel('rIdChunk', 'aFChunk', '../../word/missing.docx'),)),
        }
        for label, data in shapes.items():
            with self.subTest(label):
                removed = docx_package._safe_package(data)[1]
                self.assertEqual(removed, {'fields': 0, 'objects': 0, 'controls': 0, 'chunks': 1})
                self.assert_release_1_package(data)
        for label, data in (('External', package(BEFORE + alt + AFTER, (rel('rIdChunk', 'aFChunk',
                                                                            'file:///synthetic/x.docx',
                                                                            'External'),))),
                            ('a w:subDoc, External', package(BEFORE + '<w:p><w:subDoc r:id="rIdSub"/></w:p>' + AFTER,
                                                             (rel('rIdSub', 'subDocument', 'file:///synthetic/c.docx',
                                                                  'External'),)))):
            with self.subTest(f'refused on purpose: {label}'), self.assertRaises(docx_package.ContentNotShown):
                docx_package._safe_package(data)


# --- refutation round 1, loss[2]: a zip entry name stored as UTF-8 without the UTF-8 flag ---------------------------

def flagless(data, placeholder, name):
    """``data`` (a zip zipfile wrote) with its entry name ``placeholder`` (ASCII) stored as ``name``'s UTF-8 bytes of
    the same length, the UTF-8 flag left clear - as a writer that stores UTF-8 names without it does."""
    raw = name.encode('utf-8')
    assert len(raw) == len(placeholder) and data.count(placeholder) == 2  # its local header and central directory
    return data.replace(placeholder, raw)


def with_unicode_path(data, stored, unicode_name):
    """``data`` rewritten with its entry ``stored`` (an ASCII name) carrying a Unicode Path extra field (0x7075) that
    names it ``unicode_name``, the UTF-8 flag clear: zipfile reads the entry by that name."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(out, 'w') as rebuilt:
        for info in source.infolist():
            fresh = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            fresh.compress_type = zipfile.ZIP_DEFLATED
            if info.filename == stored:
                name = unicode_name.encode('utf-8')
                fresh.extra = struct.pack('<HHBL', 0x7075, 5 + len(name), 1, zlib.crc32(stored.encode())) + name
            rebuilt.writestr(fresh, source.read(info))
    return out.getvalue()


def unicode_path_field(name, crc, *, version=1, raw=None):
    """A Unicode Path extra field (0x7075) naming an entry ``name`` (or the bytes ``raw``), with ``crc`` and
    ``version``."""
    raw = name.encode('utf-8') if raw is None else raw
    return struct.pack('<HHBL', 0x7075, 5 + len(raw), version, crc) + raw


def central_extras(data, extras):
    """``data`` (a zip with no comment) with the central directory record of each entry ``extras`` names carrying that
    extra field block in place of its own; nothing else moves, the central directory being the zip's last part."""
    end = data.rindex(b'PK\x05\x06')
    count, _size, offset = struct.unpack_from('<HII', data, end + 10)
    records, at = [], offset
    for _ in range(count):
        name_length, extra_length, comment_length = struct.unpack_from('<HHH', data, at + 28)
        head, name = bytearray(data[at:at + 46]), data[at + 46:at + 46 + name_length]
        extra = data[at + 46 + name_length:at + 46 + name_length + extra_length]
        comment = data[at + 46 + name_length + extra_length:at + 46 + name_length + extra_length + comment_length]
        if name.decode('utf-8', 'replace') in extras:
            extra = extras[name.decode('utf-8', 'replace')]
            struct.pack_into('<H', head, 30, len(extra))
        records.append(bytes(head) + name + extra + comment)
        at += 46 + name_length + extra_length + comment_length
    tail = bytearray(data[end:])
    struct.pack_into('<I', tail, 12, sum(len(record) for record in records))
    return data[:offset] + b''.join(records) + bytes(tail)


def with_unicode_paths(data, names, *, crc=None, version=1, raw=None, where=('local', 'central')):
    """``data`` rewritten with a Unicode Path field on each entry ``names`` maps (its stored name: the name its field
    gives) - its CRC the stored name's unless ``crc`` - in its local header, its central directory record or both."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(out, 'w') as rebuilt:
        for info in source.infolist():
            fresh = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            fresh.compress_type = zipfile.ZIP_DEFLATED
            if info.filename in names and 'local' in where:
                fresh.extra = unicode_path_field(names[info.filename], zlib.crc32(info.filename.encode('utf-8'))
                                                 if crc is None else crc, version=version, raw=raw)
            rebuilt.writestr(fresh, source.read(info))
    built = out.getvalue()
    if where == ('local', 'central'):
        return built
    return central_extras(built, {name: b'' if 'local' in where else unicode_path_field(
        target, zlib.crc32(name.encode('utf-8')) if crc is None else crc, version=version, raw=raw)
        for name, target in names.items()})


def with_local_extra(data, name, extra):
    """``data`` rewritten with the extra field block ``extra`` in the local header of its entry ``name`` alone."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(out, 'w') as rebuilt:
        for info in source.infolist():
            fresh = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            fresh.compress_type = zipfile.ZIP_DEFLATED
            if info.filename == name:
                fresh.extra = extra
            rebuilt.writestr(fresh, source.read(info))
    return central_extras(out.getvalue(), {name: b''})


def entry_names(data) -> dict:
    """{each entry's name as its bytes are stored: whether its UTF-8 flag is set}."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {info.orig_filename.encode('utf-8' if info.flag_bits & 0x800 else 'cp437'): bool(info.flag_bits & 0x800)
                for info in archive.infolist()}


class ZipNameTests(ReleaseOneCase):
    """Refutation round 1, loss[2]: a zip entry name stored as UTF-8 without the UTF-8 flag is read as LibreOffice reads
    it - UTF-8, where that is valid - so an import that holds content is refused rather than removed as holding nothing,
    and a picture keeps its name (release 1 read such a name as cp437 and the rebuild renamed the part: the picture was
    lost). A name zipfile takes from a Unicode Path extra field is left as zipfile reads it - and since refutation round
    2 (loss[6] (b)) a file whose field names an entry otherwise than its stored name is refused (UnicodePathTests)."""

    def importing(self, entry_name):
        return package(BEFORE + '<w:altChunk r:id="rIdChunk"/>' + AFTER,
                       (rel('rIdChunk', 'aFChunk', 'afchunk_\u00e4.docx'),), ((entry_name, inner_docx('IMPORTED')),))

    def test_an_import_named_without_the_flag_is_refused(self):
        data = flagless(self.importing('word/afchunk_XX.docx'), b'word/afchunk_XX.docx', 'word/afchunk_\u00e4.docx')
        self.assertEqual(entry_names(data)[b'word/afchunk_\xc3\xa4.docx'], False)
        self.assertEqual(self.release_1()._safe_package(data)[1]['chunks'], 1)  # the bad shape: release 1 removed it
        for label, shape in (('without the flag', data), ('with it (the control)',
                                                          self.importing('word/afchunk_\u00e4.docx'))):
            with self.subTest(label):
                with self.assertRaises(docx_package.ContentNotShown) as caught:
                    docx_package._safe_package(shape)
                self.assertEqual((caught.exception.code, caught.exception.counts), (docx_package.INSERTED_DOCUMENT,
                                                                                    IMPORTED_COUNTS))
                with self.assertRaises(docx_package.ConversionRefused) as checked:  # C8: a stored conversion of it
                    docx_package.check_in_child(shape)
                self.assertEqual(checked.exception.code, docx_package.INSERTED_DOCUMENT)

    def test_a_picture_named_without_the_flag_keeps_its_name(self):
        data = flagless_picture_word()
        out, removed = docx_package._safe_package(data)
        self.assertEqual(removed, {'fields': 0, 'objects': 0, 'controls': 0, 'chunks': 0})
        names = entry_names(out)
        self.assertEqual(names.get(b'word/media/photo_\xc3\x9f.png'), True)  # its bytes kept, the flag now set
        with zipfile.ZipFile(io.BytesIO(out)) as archive:
            self.assertEqual(archive.read('word/media/photo_\u00df.png'), PNG_BYTES)
        # release 1 renamed it (read as cp437, written as UTF-8): the deviation from its bytes is this name alone
        self.assertNotIn(b'word/media/photo_\xc3\x9f.png', entry_names(self.release_1()._safe_package(data)[0]))
        self.assertEqual(docx_package._safe_package(out)[0], out)  # read again, nothing changes

    def test_a_unicode_path_name_is_left_as_zipfile_reads_it(self):
        # zipfile names the entry from the extra field: a name cp437 cannot write ('O' with a double acute) is not read
        # again, so the check refuses the file rather than failing (for the rename itself since round 2's loss[6] (b))
        data = with_unicode_path(package(BEFORE + '<w:altChunk r:id="rIdChunk"/>' + AFTER,
                                         (rel('rIdChunk', 'aFChunk', 'afchunk_\u0150.docx'),),
                                         (('word/afchunk_O.docx', inner_docx('IMPORTED')),)),
                                 'word/afchunk_O.docx', 'word/afchunk_\u0150.docx')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertIn('word/afchunk_\u0150.docx', archive.namelist())
        with self.assertRaises(docx_package.ContentNotShown):
            docx_package._safe_package(data)
        with self.assertRaises(docx_package.ConversionRefused):
            docx_package.check_in_child(data)

    def test_an_import_named_by_a_stored_name_a_reader_may_read_is_refused(self):
        # refutation round 2, loss[6]: the entry stored as 'word/afchunk1.docx' carries a Unicode Path field naming it
        # 'word/afchunk2.docx', which zipfile reads; a reader that ignores the field opens the stored name the import
        # names (since loss[6] (b) such a file is refused for the rename itself). And a name stored as UTF-8 without
        # the flag, read as cp437 - as zipfile, release 1 and a reader of the code page do (D-R2-40's principle: a
        # spelling the doctor's Word may resolve)
        unicode_path = with_unicode_path(package(BEFORE + '<w:altChunk r:id="rIdChunk"/>' + AFTER,
                                                 (rel('rIdChunk', 'aFChunk', 'afchunk1.docx'),),
                                                 (('word/afchunk1.docx', inner_docx('IMPORTED')),)),
                                         'word/afchunk1.docx', 'word/afchunk2.docx')
        with zipfile.ZipFile(io.BytesIO(unicode_path)) as archive:
            self.assertEqual([info.orig_filename for info in archive.infolist() if 'afchunk' in info.filename],
                             ['word/afchunk1.docx'])
            self.assertIn('word/afchunk2.docx', archive.namelist())
        code_page = flagless(package(BEFORE + '<w:altChunk r:id="rIdChunk"/>' + AFTER,
                                     (rel('rIdChunk', 'aFChunk', 'afchunk_\u251c\u00f1.docx'),),
                                     (('word/afchunk_XX.docx', inner_docx('IMPORTED')),)),
                             b'word/afchunk_XX.docx', 'word/afchunk_\u00e4.docx')
        for label, data in (('a Unicode Path name', unicode_path), ('a cp437 reading', code_page)):
            with self.subTest(label):
                self.assertEqual(self.release_1()._safe_package(data)[1]['chunks'], 1)  # release 1 removed it
                with self.assertRaises(docx_package.ContentNotShown) as caught:
                    docx_package._safe_package(data)
                self.assertEqual((caught.exception.code, caught.exception.counts),
                                 (docx_package.INSERTED_DOCUMENT, IMPORTED_COUNTS))
                with self.assertRaises(docx_package.ConversionRefused) as checked:  # C8: a stored conversion of it
                    docx_package.check_in_child(data)
                self.assertEqual(checked.exception.code, docx_package.INSERTED_DOCUMENT)


class UnicodePathTests(ReleaseOneCase):
    """Refutation round 2, loss[6] (b), the lead's decision: a package any of whose entries carries a Unicode Path extra
    field (0x7075) naming it otherwise than its stored name read as UTF-8 - whatever the field's CRC and version, in
    its central directory record or its local header - is refused as an inserted document, fresh and before a stored
    conversion is read again. zipfile applies such a field only where its CRC matches, LibreOffice 24.2.7 reads it
    without, so lane D could check one part while LibreOffice opens another. A field that names the entry as its stored
    name does renames nothing."""

    def assert_refused(self, data, documents):
        counts = {'documents': documents, 'objects': 0, 'controls': 0, 'fields': 0}
        with self.assertRaises(docx_package.ContentNotShown) as caught:
            docx_package._safe_package(data)
        self.assertEqual((caught.exception.code, caught.exception.counts), (docx_package.INSERTED_DOCUMENT, counts))
        with self.assertRaises(docx_package.ConversionRefused) as checked:  # C8: a stored conversion of it
            docx_package.check_in_child(data)
        self.assertEqual((checked.exception.code, checked.exception.counts), (docx_package.INSERTED_DOCUMENT, counts))

    @staticmethod
    def picture():
        return package(BEFORE + p('<w:r>' + drawing('rIdPic') + '</w:r>') + AFTER,
                       (rel('rIdPic', 'image', 'media/image1.png'),), (('word/media/image1.png', PNG_BYTES),))

    def test_two_entries_whose_fields_swap_their_names_are_refused(self):
        decoy = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                 f'<w:document {NS}><w:body>{p(t("DECOYTOKEN other words"))}</w:body></w:document>')
        data = with_unicode_paths(package(p(t('SWAPTOKEN the real note')), parts=(('word/decoyxx.xml', decoy),)),
                                  {'word/document.xml': 'word/decoyxx.xml', 'word/decoyxx.xml': 'word/document.xml'})
        with zipfile.ZipFile(io.BytesIO(self.release_1()._safe_package(data)[0])) as archive:  # the bad shape:
            self.assertIn(b'DECOYTOKEN', archive.read('word/document.xml'))  # release 1 coded the decoy
        self.assert_refused(data, 2)

    def test_an_entry_a_field_renames_is_refused_whatever_the_fields_crc_version_or_header(self):
        renamed = {'word/media/image1.png': 'word/media/image2.png'}
        cut = struct.pack('<HH', 0x7075, 3) + b'\x01\x00\x00'  # too short to hold its version and CRC
        for label, data in (
                ('its CRC the stored name\'s (zipfile renames the part)', with_unicode_paths(self.picture(), renamed)),
                ('its CRC another (zipfile keeps the stored name)', with_unicode_paths(self.picture(), renamed, crc=0)),
                ('version 2', with_unicode_paths(self.picture(), renamed, version=2)),
                ('in the local header only', with_unicode_paths(self.picture(), renamed, where=('local',))),
                ('in the central directory only', with_unicode_paths(self.picture(), renamed, where=('central',))),
                ('a name that is not UTF-8', with_unicode_paths(self.picture(), renamed, crc=0,
                                                                raw=b'word/media/\xff.png')),
                ('too short, in the local header', with_local_extra(self.picture(), 'word/media/image1.png', cut))):
            with self.subTest(label):
                self.release_1()._safe_package(data)  # the bad shape: release 1 coded it
                self.assert_refused(data, 1)

    def test_a_field_that_names_an_entry_as_its_stored_name_does_renames_nothing(self):
        # the controls: a field naming the stored name; a name stored as UTF-8 without the flag, its field naming it as
        # that UTF-8 reads (zipfile applies it, in release 1 too); no field - each coded with release 1's package, and
        # its stored conversion reused
        same = with_unicode_paths(self.picture(), {'word/media/image1.png': 'word/media/image1.png'})
        final = 'word/media/photo_\u00df.png'
        flagless_same = flagless(with_unicode_paths(
            package(BEFORE + p('<w:r>' + drawing('rIdPic') + '</w:r>') + AFTER,
                    (rel('rIdPic', 'image', 'media/photo_\u00df.png'),), (('word/media/photo_XX.png', PNG_BYTES),)),
            {'word/media/photo_XX.png': final}, crc=zlib.crc32(final.encode('utf-8'))),
            b'word/media/photo_XX.png', final)
        with zipfile.ZipFile(io.BytesIO(flagless_same)) as archive:
            self.assertIn(final, archive.namelist())  # zipfile took the field's name
        for label, data in (('a field naming the stored name', same), ('a flagless UTF-8 name, a field naming it so',
                                                                        flagless_same), ('no field', self.picture())):
            with self.subTest(label):
                self.assertEqual(docx_package._safe_package(data)[1], {'fields': 0, 'objects': 0, 'controls': 0,
                                                                       'chunks': 0})
                self.assert_release_1_package(data)
                self.assertIs(docx_package.check_in_child(data), False)


def character_reference_word(kept_id, *, in_object=False, named=True):
    """A removed field naming rIdPic (unless not ``named``) beside a kept picture - or an object's preview - whose id
    a kept attribute writes as ``kept_id`` (refutation round 1, loss[6]; the 7.4 corpus's R1-L6 shapes)."""
    removed = p(fc('begin'), instr(INC), '<w:r>' + drawing('rIdPic') + '</w:r>' if named else '', fc('separate'),
                t('Kept result words.'), fc('end'))
    picture_rel, picture_part = rel('rIdPic', 'image', 'media/image1.png'), ('word/media/image1.png', PNG_BYTES)
    if in_object:
        shown = p('<w:r><w:object w:dxaOrig="6000" w:dyaOrig="900">' + SHAPETYPE + vshape(rid=kept_id)
                  + ole('Package') + '</w:object></w:r>')
        return package(BEFORE + removed + shown + AFTER,
                       (picture_rel, rel('rIdOle', 'package', 'embeddings/o.bin')),
                       (picture_part, ('word/embeddings/o.bin', b'\xd0\xcf synthetic object')))
    return package(BEFORE + removed + p('<w:r>' + drawing(kept_id) + '</w:r>') + AFTER, (picture_rel,),
                   (picture_part,))


def flagless_picture_word():
    """A picture whose zip name is stored as UTF-8 without the UTF-8 flag (refutation round 1, loss[2]; R1-L2b)."""
    built = package(BEFORE + p('<w:r>' + drawing('rIdPic') + '</w:r>') + AFTER,
                    (rel('rIdPic', 'image', 'media/photo_\u00df.png'),), (('word/media/photo_XX.png', PNG_BYTES),))
    return flagless(built, b'word/media/photo_XX.png', 'word/media/photo_\u00df.png')


class CharacterReferenceTests(ReleaseOneCase):
    """Refutation round 1, loss[6]: a relationship that removed content named is kept while a kept attribute still
    holds its id - also when that attribute writes the id with a character reference, as expat reads it - so the picture
    it shows stays. Release 1 searched the bytes alone, dropped the relationship and lost the picture."""

    def shape(self, kept_id, *, in_object=False, named=True):
        return character_reference_word(kept_id, in_object=in_object, named=named)

    def test_a_picture_named_with_a_character_reference_keeps_its_relationship(self):
        for label, data in (('decimal', self.shape('&#114;IdPic')), ('hexadecimal', self.shape('&#x72;IdPic')),
                            ('an object\'s preview, decimal', self.shape('&#114;IdPic', in_object=True))):
            with self.subTest(label):
                out, removed = docx_package._safe_package(data)
                self.assertEqual(removed['fields'], 1)
                with zipfile.ZipFile(io.BytesIO(out)) as archive:
                    self.assertIn('Id="rIdPic"', archive.read('word/_rels/document.xml.rels').decode('utf-8'))
                    self.assertEqual(archive.read('word/media/image1.png'), PNG_BYTES)
                with zipfile.ZipFile(io.BytesIO(self.release_1()._safe_package(data)[0])) as archive:
                    self.assertNotIn('word/media/image1.png', archive.namelist())  # the bad shape: release 1 lost it

    def test_an_id_a_kept_attribute_writes_with_white_space_expat_normalizes_keeps_its_relationship(self):
        # refutation round 3, rounds[2]: the id 'rId 5', which a kept attribute writes 'rId<TAB>5' - expat reads it
        # 'rId 5' - is found by the parse the guard runs for an id holding white space
        removed = p(fc('begin'), instr(INC), '<w:r>' + drawing('rId 5') + '</w:r>', fc('separate'),
                    t('Kept result words.'), fc('end'))
        data = package(BEFORE + removed + p('<w:r>' + drawing('rId\t5') + '</w:r>') + AFTER,
                       (rel('rId 5', 'image', 'media/image1.png'),), (('word/media/image1.png', PNG_BYTES),))
        out, removed_counts = docx_package._safe_package(data)
        self.assertEqual(removed_counts['fields'], 1)
        with zipfile.ZipFile(io.BytesIO(out)) as archive:
            self.assertIn('Id="rId 5"', archive.read('word/_rels/document.xml.rels').decode('utf-8'))
            self.assertEqual(archive.read('word/media/image1.png'), PNG_BYTES)
        with zipfile.ZipFile(io.BytesIO(self.release_1()._safe_package(data)[0])) as archive:
            self.assertNotIn('word/media/image1.png', archive.namelist())  # the bad shape: release 1 lost it

    def test_the_parse_runs_only_where_an_attribute_can_spell_an_id_otherwise(self):
        # refutation round 3, rounds[2]: a clean file holding an object - its removed OLEObject's id named nowhere else,
        # no reference in any attribute - makes no parse in _still_named (a Python call per element: a large part went
        # past PACKAGE_SECONDS); a reference or a white-space id does
        parses, real = [], docx_package._still_named

        def counted(data, values):
            with mock.patch.object(docx_package.expat, 'ParserCreate', wraps=docx_package.expat.ParserCreate) as create:
                result = real(data, values)
            parses.append(create.call_count)
            return result
        clean = dict((label, data) for label, data, _ in object_packages())['B01 object, EMF preview, xlsx']
        with mock.patch.object(docx_package, '_still_named', counted):
            self.assertEqual(docx_package._safe_package(clean)[1]['objects'], 1)
        self.assertEqual(parses, [0])
        for label, data, values, found in (
                ('no reference, no white space', b'<a x="rId1"/>', {'rId2'}, set()),
                ('a reference in a value', b'<a x="&#114;Id2"/>', {'rId2'}, {'rId2'}),
                ('a white-space id', b'<a x="rId\t5"/>', {'rId 5'}, {'rId 5'})):
            with self.subTest(label), mock.patch.object(docx_package.expat, 'ParserCreate',
                                                        wraps=docx_package.expat.ParserCreate) as create:
                self.assertEqual(real(data, values), (found, found))
                self.assertEqual(create.call_count, 0 if label.startswith('no') else 1)

    def test_written_literally_or_not_named_by_what_goes_the_package_is_release_1s(self):
        for label, data in (('literal', self.shape('rIdPic')),
                            ('the removed field names nothing', self.shape('&#114;IdPic', named=False)),
                            ('an object\'s preview, literal', self.shape('rIdPic', in_object=True))):
            with self.subTest(label):
                self.assert_release_1_package(data)


# --- R2-30: a removed field inside another field's result stays a field ----------------------------------------------

QUOTE_BEGIN = '<w:r><w:fldChar w:fldCharType="begin"/><w:instrText xml:space="preserve"> QUOTE </w:instrText></w:r>'
NOTE_REFERENCE = '<w:r><w:footnoteReference w:id="2"/></w:r>'  # refutation round 2, loss[4]: it brings the note


def document_part(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read('word/document.xml').decode('utf-8')


def shells_in(data) -> int:
    """How many QUOTE shells (complex or simple) the main part of a package holds."""
    xml = document_part(data)
    return xml.count('> QUOTE </') + xml.count('" QUOTE "')


class FieldShellTests(ReleaseOneCase):
    """R2-30 (D-R2-36): where the field being removed lies in another field's result and in no field's instruction,
    and is not INCLUDEPICTURE, it stays a field whose instruction is ' QUOTE ': a complex field's begin mark gains the
    instruction and what stood between begin and separate goes; a simple field's instr reads ' QUOTE '. Byte for byte;
    every other removal is release 1's."""

    def edited(self, inner_before, inner_after, *, outer=' IF 1 = 1 "yes" "no" ', paragraphs=None):
        """The main part of a package with ``inner_before`` in an outer field's result, as E2 leaves it, against the
        part with ``inner_after`` in its place (the expectation, written out)."""
        def body(inner):
            return paragraphs(inner) if paragraphs else (BEFORE + p(fc('begin'), instr(outer), fc('separate'),
                                                                    t('OUT1 '), inner, t(' OUT2'), fc('end')) + AFTER)
        data = package(body(inner_before))
        out, removed = docx_package._safe_package(data)
        self.assertEqual(document_part(out), document_part(package(body(inner_after))))
        self.assertNotIn('SECRET', document_part(out))
        ElementTree.fromstring(document_part(out).encode('utf-8'))
        self.assertEqual(docx_package._safe_package(out)[0], out)  # a shell is a kept field: a second pass keeps it
        # the positive control: release 1 unwrapped it
        self.assertNotEqual(self.release_1()._safe_package(data)[0], out)
        return removed

    def test_a_removed_field_inside_another_fields_result_stays_a_field(self):
        complex_inner = fc('begin') + instr(INC) + fc('separate') + t('INNER RESULT') + fc('end')
        shelled = QUOTE_BEGIN + fc('separate') + t('INNER RESULT') + fc('end')
        with self.subTest('complex in complex'):
            self.assertEqual(self.edited(complex_inner, shelled)['fields'], 1)
        simple_inner = '<w:fldSimple w:instr=\' INCLUDETEXT "c:\\\\SECRET.docx" \'>' + t('INNER') + '</w:fldSimple>'
        simple_shell = '<w:fldSimple w:instr=" QUOTE ">' + t('INNER') + '</w:fldSimple>'

        def in_simple(inner):
            return (BEFORE + p('<w:fldSimple w:instr=" IF 1 = 1 ">', t('OUT1 '), inner, t(' OUT2'), '</w:fldSimple>')
                    + AFTER)
        with self.subTest('simple in simple'):
            self.assertEqual(self.edited(simple_inner, simple_shell, paragraphs=in_simple)['fields'], 1)
        with self.subTest('complex in simple'):
            self.assertEqual(self.edited(complex_inner, shelled, paragraphs=in_simple)['fields'], 1)
        with self.subTest('simple in complex, its w:fldData going with its instruction'):
            with_data = ('<w:fldSimple w:instr=" LINK Excel.Sheet.12 SECRET "><w:fldData xml:space="preserve">U0VDUkVU'
                         '</w:fldData>' + t('INNER') + '</w:fldSimple>')
            self.edited(with_data, simple_shell)
        with self.subTest('marks sharing a run'):
            shared = ('<w:r><w:fldChar w:fldCharType="begin"/>' + instr(INC)[len('<w:r>'):-len('</w:r>')]
                      + '<w:fldChar w:fldCharType="separate"/></w:r>' + t('INNER') + fc('end'))
            self.edited(shared, '<w:r><w:fldChar w:fldCharType="begin"/><w:instrText xml:space="preserve"> QUOTE '
                                '</w:instrText><w:fldChar w:fldCharType="separate"/></w:r>' + t('INNER') + fc('end'))
        with self.subTest('a begin mark with w:ffData'):
            begin = ('<w:r><w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="Text1"/><w:enabled/></w:ffData>'
                     '</w:fldChar></w:r>')
            self.edited(begin + instr(INC) + fc('separate') + t('TYPED') + fc('end'),
                        begin[:-len('</w:r>')] + '<w:instrText xml:space="preserve"> QUOTE </w:instrText></w:r>'
                        + fc('separate') + t('TYPED') + fc('end'))

    def test_an_instruction_over_two_paragraphs_keeps_both_paragraphs_and_their_properties(self):
        def paragraphs(inner):
            return BEFORE + inner + AFTER
        before = (p(fc('begin'), instr(' IF 1 = 1 "a" "b" '), fc('separate'), t('OUT1 '), fc('begin'),
                    instr(' INCLUDETEXT "c:\\\\'))
                  + p('<w:pPr><w:jc w:val="center"/></w:pPr>', '<w:r><w:rPr><w:b/></w:rPr><w:instrText>SECRET.docx" '
                      '</w:instrText></w:r>', '<w:r><w:rPr><w:i/></w:rPr><w:fldChar w:fldCharType="separate"/></w:r>',
                      t('INNER'), fc('end'), fc('end')))
        after = (p(fc('begin'), instr(' IF 1 = 1 "a" "b" '), fc('separate'), t('OUT1 '), QUOTE_BEGIN)
                 + p('<w:pPr><w:jc w:val="center"/></w:pPr>', '<w:r><w:rPr><w:i/></w:rPr><w:fldChar '
                     'w:fldCharType="separate"/></w:r>', t('INNER'), fc('end'), fc('end')))
        self.assertEqual(self.edited(before, after, paragraphs=paragraphs)['fields'], 1)

    def test_the_default_namespace_and_another_prefix_are_shelled_in_their_own_form(self):
        inner = fc('begin') + instr(INC) + fc('separate') + t('INNER') + fc('end')
        expected = QUOTE_BEGIN + fc('separate') + t('INNER') + fc('end')

        def bare(inner_xml, form):
            """A package whose main part writes its WordprocessingML elements in ``form``: with no prefix under a
            default namespace (its attributes keep w:), or with the prefix ns0."""
            xml = p(fc('begin'), instr(' REF Bm \\h '), fc('separate'), inner_xml, fc('end'))
            if form == 'default':
                xml, root = xml.replace('<w:', '<').replace('</w:', '</'), f'<document xmlns="{W}" xmlns:w="{W}">'
                part = f'{root}<body>{xml}</body></document>'
            else:
                xml = xml.replace('<w:', '<ns0:').replace('</w:', '</ns0:')
                part = f'<ns0:document xmlns:ns0="{W}" xmlns:w="{W}"><ns0:body>{xml}</ns0:body></ns0:document>'
            return zipped([('[Content_Types].xml', f'<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="{CT}">'
                            f'<Default Extension="rels" ContentType="{DEFAULTS["rels"]}"/><Default Extension="xml" '
                            f'ContentType="application/xml"/>{override("word/document.xml", MAIN)}</Types>'),
                           ('_rels/.rels', rels(rel('rId1', 'officeDocument', 'word/document.xml'))),
                           ('word/document.xml', part)])
        for form, tag in (('default', 'instrText'), ('ns0', 'ns0:instrText')):
            with self.subTest(form):
                out, removed = docx_package._safe_package(bare(inner, form))
                self.assertEqual(document_part(out), document_part(bare(expected, form)))
                self.assertIn(f'<{tag} xml:space="preserve"> QUOTE </{tag}>', document_part(out))
                self.assertNotIn('SECRET', document_part(out))
                self.assertEqual(removed['fields'], 1)

    def test_includepicture_and_a_field_in_an_instruction_are_unwrapped_exactly_as_release_1(self):
        picture = (fc('begin') + instr(' INCLUDEPICTURE "file:///synthetic/SECRET.png" \\* MERGEFORMATINET ')
                   + fc('separate') + '<w:r><w:pict>' + SHAPETYPE + vshape() + '</w:pict></w:r>' + fc('end'))
        longer = picture.replace('INCLUDEPICTURE', 'INCLUDEPICTURES')  # not INCLUDEPICTURE: it is shelled
        cases = {
            'INCLUDEPICTURE in an IF result': package(BEFORE + p(fc('begin'), instr(' IF 1 = 1 "a" "b" '),
                                                                 fc('separate'), picture, fc('end')) + AFTER,
                                                      (rel('rIdPrev', 'image', 'media/image1.emf'),),
                                                      (('word/media/image1.emf', EMF),)),
            'a removed field in an instruction whose outer result holds a field': package(BEFORE + p(
                fc('begin'), instr(' IF 1 = 1 "'), field(INC, 'INCLUDED'), instr('" "" '), fc('separate'),
                field(' QUOTE "x" ', 'INCLUDED'), fc('end')) + AFTER),
            'a removed field with no result in an IF result': package(BEFORE + p(
                fc('begin'), instr(' IF 1 = 1 "a" "b" '), fc('separate'), fc('begin'), instr(INC), fc('end'),
                fc('end')) + AFTER),
            'an empty simple field in an IF result': package(BEFORE + p(
                fc('begin'), instr(' IF 1 = 1 "a" "b" '), fc('separate'), '<w:fldSimple w:instr=\' INCLUDETEXT x \'/>',
                fc('end')) + AFTER),
            # refutation round 2, loss[4]: a note's reference outside the INCLUDEPICTURE is the IF's own (a picture
            # alone stays unwrapped); in an instruction a reference is read past, so 'LI' + reference + 'NK' is LINK
            'INCLUDEPICTURE a picture alone, a note\'s reference beside it in the IF result': package(BEFORE + p(
                fc('begin'), instr(' IF 1 = 1 "a" "b" '), fc('separate'), picture, NOTE_REFERENCE, fc('end')) + AFTER,
                (rel('rIdPrev', 'image', 'media/image1.emf'),), (('word/media/image1.emf', EMF),)),
            'a note\'s reference in a removed field\'s instruction': package(BEFORE + p(
                fc('begin'), instr(' LI'), NOTE_REFERENCE, instr('NK Excel.Sheet.12 "c:\\\\SECRET.xlsx" '),
                fc('separate'), t('LINKED'), fc('end')) + AFTER),
            'INCLUDE, a note\'s reference and PICTURE - INCLUDEPICTURE, a picture alone - in an IF result': package(
                BEFORE + p(fc('begin'), instr(' IF 1 = 1 "a" "b" '), fc('separate'), fc('begin'), instr(' INCLUDE'),
                           NOTE_REFERENCE, instr('PICTURE "file:///synthetic/SECRET.png" '), fc('separate'),
                           '<w:r><w:pict>' + SHAPETYPE + vshape() + '</w:pict></w:r>', fc('end'), fc('end')) + AFTER,
                (rel('rIdPrev', 'image', 'media/image1.emf'),), (('word/media/image1.emf', EMF),)),
        }
        for label, data in cases.items():
            with self.subTest(label):
                out = docx_package._safe_package(data)[0]
                self.assertEqual(shells_in(out), 0)
                self.assert_release_1_package(data)
        shelled = package(BEFORE + p(fc('begin'), instr(' IF 1 = 1 "a" "b" '), fc('separate'), longer, fc('end'))
                          + AFTER, (rel('rIdPrev', 'image', 'media/image1.emf'),), (('word/media/image1.emf', EMF),))
        self.assertEqual(shells_in(docx_package._safe_package(shelled)[0]), 1)  # the control: a longer word is not it
        # refutation round 1, loss[1]: an INCLUDEPICTURE whose stored result shows text or a symbol is no picture alone
        # - unwrapped in an IF's result, its words were lost (release 1) - so it stays a field, shelled
        symbol = '<w:r><w:sym w:font="Wingdings" w:char="F0E0"/></w:r>'
        for label, inner, shell in (
                ('a simple one in a simple IF', '<w:fldSimple w:instr=\' INCLUDEPICTURE "x" \'>' + t('PIC')
                 + '</w:fldSimple>', '<w:fldSimple w:instr=" QUOTE ">' + t('PIC') + '</w:fldSimple>'),
                ('a complex one with a caption beside its picture, in a complex IF', picture.replace(
                    fc('separate') + '<w:r><w:pict>', fc('separate') + t('CAPTION') + '<w:r><w:pict>'), None),
                ('a complex one whose result is a symbol', fc('begin') + instr(' INCLUDEPICTURE "SECRET.png" ')
                 + fc('separate') + symbol + fc('end'), None),
                # refutation round 2, loss[4]: a note's reference brings the note's words, a non-breaking hyphen shows;
                # unwrapped into the IF's result, LibreOffice dropped them with it
                ('a picture and a footnote reference', picture.replace(
                    '</w:pict></w:r>' + fc('end'), '</w:pict></w:r>' + NOTE_REFERENCE + fc('end')), None),
                ('a picture and an endnote reference', picture.replace(
                    '</w:pict></w:r>' + fc('end'), '</w:pict></w:r><w:r><w:endnoteReference w:id="2"/></w:r>'
                    + fc('end')), None),
                ('a footnote reference alone', fc('begin') + instr(' INCLUDEPICTURE "SECRET.png" ') + fc('separate')
                 + NOTE_REFERENCE + fc('end'), None),
                ('a simple one holding a picture and a footnote reference, in a simple IF',
                 '<w:fldSimple w:instr=\' INCLUDEPICTURE "x" \'><w:r><w:pict>' + SHAPETYPE + vshape()
                 + '</w:pict></w:r>' + NOTE_REFERENCE + '</w:fldSimple>',
                 '<w:fldSimple w:instr=" QUOTE "><w:r><w:pict>' + SHAPETYPE + vshape() + '</w:pict></w:r>'
                 + NOTE_REFERENCE + '</w:fldSimple>'),
                ('a picture and a non-breaking hyphen', picture.replace(
                    '</w:pict></w:r>' + fc('end'), '</w:pict></w:r><w:r><w:noBreakHyphen/></w:r>' + fc('end')), None)):
            with self.subTest(f'INCLUDEPICTURE with text: {label}'):
                outer = (p('<w:fldSimple w:instr=" IF 1 = 1 ">', inner, '</w:fldSimple>') if shell is not None
                         else p(fc('begin'), instr(' IF 1 = 1 "a" "b" '), fc('separate'), inner, fc('end')))
                data = package(BEFORE + outer + AFTER, (rel('rIdPrev', 'image', 'media/image1.emf'),),
                               (('word/media/image1.emf', EMF),))
                out = docx_package._safe_package(data)[0]
                self.assertEqual(shells_in(out), 1)
                self.assertNotIn('SECRET', document_part(out))
                self.assertNotEqual(self.release_1()._safe_package(data)[0], out)  # release 1 unwrapped it
                if shell is not None:
                    self.assertIn(shell, document_part(out))


def nested_in_instruction(before, after, result, *, nested_result=None, nested=None):
    """A Word file whose one outer field holds a removed field (INCLUDETEXT) in its instruction - ``before`` it, the
    nested field, ``after`` it - and ``result`` as its stored result (the 7.4 corpus's H shapes)."""
    nested = nested if nested is not None else (fc('begin') + instr(INC) + fc('separate')
                                                + (nested_result or t('INCLUDED TEXT')) + fc('end'))
    return package(BEFORE + p(fc('begin'), instr(before), nested, instr(after), fc('separate'), result, fc('end'))
                   + AFTER)


def fallback_shapes():
    """(label, a Word file, the fields its refusal counts or 0 when it is coded): R2-30's fallback, set from the 7.4
    corpus - shapes 156 and 160 (H01) lose their plain stored result on 7.4 with or without the QUOTE, and H02-H04, I01
    and I02, whose stored result is a field alone, keep every word - and the variants the specification names (outer
    REF, DOCPROPERTY, DATE, ASK and PAGE with a plain result), which the lead's 7.4 corpus run measures. A stored result
    of text beside a field is refused: 7.4 drops the plain text of such a result (G10's IF shows its field alone), and
    without the removed field in the instruction nothing else shows it - Word's flattened result of an included text
    that holds a field."""
    plain = t('INCLUDED TEXT')
    if_before, if_after = ' IF 1 = 1 "', '" "" '
    return [
        ('H01 IF "{INCLUDETEXT}", result plain (w:t in the instruction)',
         nested_in_instruction(if_before, if_after, plain), 1),
        ('H01 IF "{INCLUDETEXT}", result plain (w:instrText in the instruction)',
         nested_in_instruction(if_before, if_after, plain, nested_result=instr('INCLUDED TEXT')), 1),
        ('outer REF, plain result', nested_in_instruction(' REF ', ' \\h ', t('REF RESULT')), 1),
        ('outer DOCPROPERTY, plain result', nested_in_instruction(' DOCPROPERTY ', ' ', t('PROPERTY RESULT')), 1),
        ('outer DATE, plain result', nested_in_instruction(' DATE \\@ "', '" ', t('DATE RESULT')), 1),
        ('outer ASK, plain result', nested_in_instruction(' ASK Bm "', '" ', t('ASK RESULT')), 1),
        ('outer PAGE, plain result', nested_in_instruction(' PAGE ', ' \\* MERGEFORMAT ', t('7')), 1),
        ('outer unknown type, plain result', nested_in_instruction(' SOMETHINGNEW "', '" ', t('UNKNOWN RESULT')), 1),
        ('outer IF, a picture as its plain result', nested_in_instruction(
            if_before, if_after, '<w:r><w:pict>' + SHAPETYPE + vshape() + '</w:pict></w:r>'), 1),
        ('outer IF, a removed simple field in its instruction', nested_in_instruction(
            if_before, if_after, plain, nested='<w:fldSimple w:instr=\' INCLUDETEXT "SECRET" \'>' + t('INCLUDED')
                                               + '</w:fldSimple>'), 1),
        ('outer IF, its stored result text beside a field', nested_in_instruction(
            if_before, if_after, t('INCLUDED ') + field(' PAGE ', '3') + t(' TEXT')), 1),
        ('outer IF, its stored result a field, then text', nested_in_instruction(
            if_before, if_after, field(' PAGE ', '3') + t(' INCLUDED TEXT')), 1),
        # refutation round 1, refuse[1]: a w:fldSimple in the result is a field of it, as a complex one is
        ('outer IF, its stored result text beside a simple field', nested_in_instruction(
            if_before, if_after, t('INCLUDED ') + '<w:fldSimple w:instr=" PAGE ">' + t('3') + '</w:fldSimple>'), 1),
        # refutation round 2 (loss[4]'s marks, failing closed): a note's reference or a non-breaking hyphen as the
        # plain result is something a reader sees - not measured on 7.4, which drops such a result's text
        ('outer IF, its plain result a footnote reference', nested_in_instruction(if_before, if_after,
                                                                                 NOTE_REFERENCE), 1),
        ('outer IF, its plain result a non-breaking hyphen', nested_in_instruction(
            if_before, if_after, '<w:r><w:noBreakHyphen/></w:r>'), 1),
        ('two outer fields, one in the other\'s instruction, each a plain result', package(BEFORE + p(
            fc('begin'), instr(' IF 1 = 1 "'), fc('begin'), instr(' QUOTE "'), field(INC, 'INCLUDED'), instr('" '),
            fc('separate'), t('QUOTED'), fc('end'), instr('" "" '), fc('separate'), t('IF RESULT'), fc('end'))
            + AFTER), 1),  # the IF; the QUOTE is exempt
        # coded: the stored result is fields alone, which LibreOffice shows (the QUOTE keeps a removed one)
        ('H02 IF "{INCLUDETEXT}", result nested field', nested_in_instruction(if_before, if_after,
                                                                               field(INC, 'INCLUDED TEXT')), 0),
        ('H03 IF with MERGEFIELD condition and INCLUDETEXT branch', package(BEFORE + p(
            fc('begin'), instr(' IF '), field(' MERGEFIELD Sex ', 'F'), instr(' = "F" "'), field(INC, 'INCLUDED TEXT'),
            instr('" "" '), fc('separate'), field(INC, 'INCLUDED TEXT'), fc('end')) + AFTER), 0),
        ('H04 as H02 with a multi-paragraph result', package(BEFORE + p(
            fc('begin'), instr(' IF 1 = 1 "'), field(INC, 'INCLUDED TEXT'), instr('" "" '), fc('separate'),
            fc('begin'), instr(INC), fc('separate'), t('INCLUDED ONE')) + p(t('INCLUDED TWO'))
            + p(t('INCLUDED THREE'), fc('end'), fc('end')) + AFTER), 0),
        ('I02 IF MERGEFIELD = "F" "{INCLUDETEXT}", the result a field that differs from the branch', package(
            BEFORE + p(fc('begin'), instr(' IF '), field(' MERGEFIELD Sex ', 'F'), instr(' = "F" "'),
                       field(INC, 'BRANCH TEXT'), instr('" "" '), fc('separate'), field(INC, 'SHOWN IN WORD'),
                       fc('end')) + AFTER), 0),
        ('outer IF, its result a kept field', nested_in_instruction(if_before, if_after, field(' QUOTE "x" ', 'Q')), 0),
        # refutation round 1, refuse[1]: the same results written as w:fldSimple fields are fields alone too
        ('outer IF, its result a kept simple field', nested_in_instruction(
            if_before, if_after, '<w:fldSimple w:instr=\' QUOTE "x" \'>' + t('Q') + '</w:fldSimple>'), 0),
        ('H02 with its result a simple field', nested_in_instruction(
            if_before, if_after, '<w:fldSimple w:instr=\' INCLUDETEXT "SECRET" \'>' + t('INCLUDED TEXT')
            + '</w:fldSimple>'), 0),
        ('outer IF, its result a simple field holding a picture', nested_in_instruction(
            if_before, if_after, '<w:fldSimple w:instr=\' QUOTE "x" \'><w:r><w:pict>' + SHAPETYPE + vshape()
            + '</w:pict></w:r></w:fldSimple>'), 0),
        ('outer IF, its result a kept field holding a footnote reference', nested_in_instruction(
            if_before, if_after, fc('begin') + instr(' QUOTE "x" ') + fc('separate') + NOTE_REFERENCE + fc('end')), 0),
        ('outer IF, its result a simple field holding a symbol', nested_in_instruction(
            if_before, if_after, '<w:fldSimple w:instr=\' QUOTE "x" \'><w:r><w:sym w:font="Wingdings" w:char="F0E0"/>'
            '</w:r></w:fldSimple>'), 0),
        # coded: HYPERLINK, TOC, QUOTE and STYLEREF keep their stored result (QUOTE and STYLEREF: the lead's 7.4 run on
        # lane D's corpus inputs H7f and H7g, refutation round 1)
        ('outer HYPERLINK, plain result', nested_in_instruction(' HYPERLINK "', '" ', t('LINK TEXT')), 0),
        ('outer TOC, plain result', nested_in_instruction(' TOC \\o "', '" ', t('Heading one')), 0),
        ('outer QUOTE, plain result', nested_in_instruction(' QUOTE "', '" ', t('QUOTED')), 0),
        ('outer STYLEREF, plain result', nested_in_instruction(' STYLEREF "', '" ', t('STYLE RESULT')), 0),
        # refutation round 2 (loss[4]): a mark in an instruction is read past, so the type it splits stays one word -
        # 'HYPER', a footnote reference, 'LINK' is HYPERLINK, exempt, as LibreOffice reads it
        ('outer HYPERLINK whose type a footnote reference splits, plain result', nested_in_instruction(
            ' HYPER', '" ', t('LINK TEXT'), nested=NOTE_REFERENCE + instr('LINK "') + field(INC, 'INCLUDED TEXT')), 0),
        # coded: no stored result, or one with nothing in it a reader sees
        ('outer IF, no separate', package(BEFORE + p(fc('begin'), instr(if_before), field(INC, 'INCLUDED'),
                                                     instr(if_after), fc('end')) + AFTER), 0),
        ('outer IF, an empty result', nested_in_instruction(if_before, if_after, ''), 0),
        ('outer IF, a result of white space', nested_in_instruction(if_before, if_after, t('   ')), 0),
        # coded: INCLUDEPICTURE is excluded; and a type the removed field's result completes is a removed one
        ('outer IF, INCLUDEPICTURE in its instruction', nested_in_instruction(
            if_before, if_after, plain, nested=field(' INCLUDEPICTURE "file:///synthetic/SECRET.png" ', 'PIC')), 0),
        ('LI and a removed field\'s NK: LINK, itself removed', package(BEFORE + p(
            fc('begin'), instr(' LI'), field(INC, 'NK'), instr(' "c:\\\\SECRET.xlsx" '), fc('separate'), t('OUTER'),
            fc('end')) + AFTER), 0),
        ('outer IF, a kept field in its instruction (nothing removed)', package(BEFORE + p(
            fc('begin'), instr(' IF '), field(' MERGEFIELD Sex ', 'F'), instr(' = "F" "She" "He" '), fc('separate'),
            t('She'), fc('end')) + AFTER), 0),
    ]


class FieldFallbackTests(ReleaseOneCase):
    """R2-30's fallback (D-R2-36): a field kept, not HYPERLINK, TOC, QUOTE or STYLEREF, with a removed field (not
    INCLUDEPICTURE) in its instruction and a stored result that holds something a reader sees outside the fields in it,
    is refused like R2-29, under its own count ('fields', told as an inserted document: the lead's decision, refutation
    round 1); every other file is coded as before."""

    def test_a_removed_field_in_an_instruction_with_a_plain_stored_result_is_refused(self):
        shapes = fallback_shapes()
        self.assertEqual(sum(1 for *_, fields in shapes if fields), 16)
        for label, data, fields in shapes:
            with self.subTest(label):
                if fields:
                    with self.assertRaises(docx_package.ContentNotShown) as caught:
                        docx_package._safe_package(data)
                    self.assertEqual((caught.exception.code, caught.exception.counts),
                                     (docx_package.INSERTED_DOCUMENT, {'documents': 0, 'objects': 0, 'controls': 0,
                                                                     'fields': fields}))
                    self.release_1()._safe_package(data)  # the positive control: release 1 coded it
                    continue
                out, removed = docx_package._safe_package(data)
                self.assertNotIn('SECRET', document_part(out))
                if not shells_in(out):
                    self.assert_release_1_package(data)

    def test_the_fallback_is_decided_once_every_type_is_final(self):
        # a field whose type a removed field's result completes is read again (release 1): the reading that removes
        # nothing more inside an instruction decides, so 'LI' + 'NK' - LINK, removed - is never refused, and its count
        # comes from that reading alone
        reads = []
        real = docx_package._PartReader.read

        def counted(reader):
            reads.append(reader)
            return real(reader)
        completing = dict((label, data) for label, data, _ in fallback_shapes())[
            'LI and a removed field\'s NK: LINK, itself removed']
        refused = fallback_shapes()[0][1]
        with mock.patch.object(docx_package._PartReader, 'read', counted):
            docx_package._safe_package(completing)
            self.assertEqual([len(reader.candidates) for reader in reads], [1, 0])  # carried, then removed
            self.assertEqual([reader.lost['fields'] for reader in reads], [0, 0])
            reads.clear()
            with self.assertRaises(docx_package.ContentNotShown):
                docx_package._safe_package(refused)
            self.assertEqual([(len(reader.carried), reader.lost['fields']) for reader in reads], [(0, 0), (1, 1)])


# --- R2-30's fuzz: well-formed, no removed instruction left, every visible word, release 1's bytes without a QUOTE ---

FUZZ_REMOVED = ['INCLUDETEXT "SECRET"', 'LINK Excel "SECRET"', 'DDEAUTO cmd "SECRET"', 'INCLUDEPICTURE "SECRET" \\d',
                'DATABASE \\d "SECRET"', 'INCLUDE "SECRET"', 'IMPORT "SECRET"', 'DDE x "SECRET"']
FUZZ_KEPT = ['PAGE', 'IF 1 = 1 "a" "b"', 'REF Bm \\h', 'HYPERLINK "x"', 'QUOTE "y"', '= 1 + 1', 'TOC \\o',
             'MERGEFIELD Name', 'DATE', 'SEQ t']
FUZZ_RUN_PROPERTIES = ['', '<w:rPr><w:b/></w:rPr>', '<w:rPr><w:rFonts w:ascii="Arial"/><w:sz w:val="20"/></w:rPr>']
FUZZ_OBJECT = '<w:object w:dxaOrig="6000" w:dyaOrig="900">' + SHAPETYPE + vshape() + ole() + '</w:object>'


class FuzzDocument:
    """One random paragraph of runs (word-scratch/fuzz2.py's generator, rebuilt): visible tokens, objects with a
    preview, fields of removed and kept types, complex (marks sharing runs, split instructions, a begin mark with
    w:ffData, nested fields in instructions, results over paragraphs) and simple, nested to a depth."""

    def __init__(self, rng):
        self.rng, self.number, self.visible = rng, 0, []

    def token(self, visible):
        self.number += 1
        word = f'T{self.number}x'
        if visible:
            self.visible.append(word)
        return word

    def atoms(self, depth, visible, simple):
        rng, out = self.rng, []
        for _ in range(rng.randint(1, 3)):
            pick = rng.random()
            if pick < 0.35 or depth <= 0:
                out.append(('r', f'<w:t xml:space="preserve">{self.token(visible)}</w:t>'))
            elif pick < 0.42:
                out.append(('r', FUZZ_OBJECT))
            else:
                kind = rng.choice(FUZZ_REMOVED if rng.random() < 0.6 else FUZZ_KEPT)
                if rng.random() < 0.25:
                    inner = self.runs(self.atoms(depth - 1, visible, True))
                    instruction = escape(' ' + kind + ' ', {'"': '&quot;'})
                    out.append(('s', f'<w:fldSimple w:instr="{instruction}">{inner}</w:fldSimple>'))
                    continue
                out.append(('r', '<w:fldChar w:fldCharType="begin"/>' if rng.random() < 0.8 else
                            '<w:fldChar w:fldCharType="begin"><w:ffData><w:name w:val="n"/></w:ffData></w:fldChar>'))
                cut = rng.randint(1, len(kind) - 1) if rng.random() < 0.4 else len(kind)
                out.append(('r', f'<w:instrText xml:space="preserve"> {escape(kind[:cut])}</w:instrText>'))
                if kind[cut:]:
                    out.append(('r', f'<w:instrText xml:space="preserve">{escape(kind[cut:])} </w:instrText>'))
                if rng.random() < 0.3:
                    out += self.atoms(depth - 1, False, simple)
                    out.append(('r', '<w:instrText xml:space="preserve"> tail </w:instrText>'))
                if rng.random() < 0.9:
                    out.append(('r', '<w:fldChar w:fldCharType="separate"/>'))
                    out += self.atoms(depth - 1, visible, simple)
                    if not simple and rng.random() < 0.2:
                        out.append(('s', '</w:p><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'))
                        out.append(('r', f'<w:t>{self.token(visible)}</w:t>'))
                out.append(('r', '<w:fldChar w:fldCharType="end"/>'))
        return out

    def runs(self, atoms):
        rng, out, current = self.rng, [], []

        def flush():
            if current:
                out.append('<w:r>' + rng.choice(FUZZ_RUN_PROPERTIES) + ''.join(current) + '</w:r>')
                current.clear()
        for kind, xml in atoms:
            if kind == 's':
                flush()
                out.append(xml)
            else:
                current.append(xml)
                if rng.random() < 0.6:
                    flush()
        flush()
        return ''.join(out)


class FieldFuzzTests(ReleaseOneCase):
    SEEDS = range(2000)

    def test_a_seeded_fuzz_over_two_thousand_documents(self):
        release_1 = release_1_package()
        tally = {'accepted': 0, 'refused': 0, 'skipped': 0, 'shells': 0, 'identical': 0, 'as release 1': 0}
        fuzz_rels = (rel('rIdPrev', 'image', 'media/image1.emf'), rel('rIdOle', 'package', 'embeddings/x.xlsx'))
        fuzz_parts = (('word/media/image1.emf', EMF), ('word/embeddings/x.xlsx', XLSX))
        for seed in self.SEEDS:
            rng = random.Random(seed)
            made = FuzzDocument(rng)
            xml = made.runs(made.atoms(rng.randint(1, 4), True, False))
            try:
                ElementTree.fromstring(f'<w:document {NS}><w:body><w:p>{xml}</w:p></w:body></w:document>')
            except ElementTree.ParseError:
                tally['skipped'] += 1
                continue
            data = package(p(xml) + p(t('END')), fuzz_rels, fuzz_parts)
            try:
                theirs = release_1._safe_package(data)[0]
            except release_1.PackageRefused:
                theirs = None
            try:
                out, _ = docx_package._safe_package(data)
            except docx_package.ContentNotShown:
                tally['refused'] += 1
                continue
            except docx_package.PackageRefused:
                # refused for another reason only where release 1 refused it too
                self.assertIsNone(theirs, seed)
                continue
            tally['accepted'] += 1
            part = document_part(out)
            self.assertNotIn(b'SECRET', out, seed)
            root = ElementTree.fromstring(part.encode('utf-8'))
            made_shells = shells_in(out)
            tally['shells'] += made_shells
            if made_shells == 0:
                self.assertEqual(out, theirs, seed)
                tally['identical'] += 1
            want = set(made.visible)
            seen = [node.text for node in root.iter(f'{{{W}}}t') if node.text in want]
            if seen != made.visible:  # a token a field of release 1's own makes invisible stays so
                self.assertIsNotNone(theirs, seed)
                theirs_root = ElementTree.fromstring(document_part(theirs).encode('utf-8'))
                self.assertEqual(seen, [node.text for node in theirs_root.iter(f'{{{W}}}t') if node.text in want],
                                 seed)
                tally['as release 1'] += 1
        # not vacuous: shells were made, packages compared, files refused, nearly every document read
        self.assertGreater(tally['accepted'], 1000)
        self.assertGreater(tally['shells'], 100)
        self.assertGreater(tally['refused'], 10)
        self.assertLess(tally['skipped'], 100)
        self.assertGreater(tally['identical'], 300)


# --- R2-28 step 7 (C8): the check a stored conversion is read again after --------------------------------------------

CLEAN_WORD = package(BEFORE + p(field(' PAGE ', '1')) + AFTER)
IMPORTING_WORD = package(BEFORE + '<w:altChunk r:id="rIdChunk"/>' + AFTER,
                         (rel('rIdChunk', 'aFChunk', 'afchunk1.docx'),),
                         (('word/afchunk1.docx', inner_docx('IMPORTED SYNTHETIC TEXT')),))
BARE_OBJECT_WORD = package(in_object(ole('Word.Document.12')), DOCX_RELS[1:], DOCX_PARTS[1:])
SHELLED_WORD = package(BEFORE + p(fc('begin'), instr(' IF 1 = 1 "a" "b" '), fc('separate'), field(INC, 'INNER'),
                                  fc('end')) + AFTER)
NOT_A_PACKAGE = b'PK\x03\x04 synthetic bytes that are no zip'
UNREADABLE_PART_WORD = package(p(field(INC, 'X')) + '<w:p><w:r></w:p>')  # refused once its parts are read
# refutation round 2, rounds[0]: an import beside two pictures whose UTF-8 names, stored without the flag, differ only
# in case - release 1 reads them as cp437, two names, and codes the file without the import; release 2's check refuses
# the zip for a part named twice, so it cannot decide (CHECK_UNDECIDED), and the converter refuses it with the general
# sentence
COLLIDING_NAMES_WORD = flagless(flagless(
    package(BEFORE + '<w:altChunk r:id="rIdChunk"/>' + AFTER, (rel('rIdChunk', 'aFChunk', 'afchunk1.docx'),),
            (('word/afchunk1.docx', inner_docx('IMPORTED SYNTHETIC TEXT')), ('word/media/aXX.png', PNG_BYTES),
             ('word/media/aYY.png', PNG_BYTES))),
    b'word/media/aXX.png', 'word/media/a\u00c9.png'), b'word/media/aYY.png', 'word/media/a\u00e9.png')
IMPORTED_COUNTS = {'documents': 1, 'objects': 0, 'controls': 0, 'fields': 0}
OBJECT_COUNTS = {'documents': 0, 'objects': 1, 'controls': 0, 'fields': 0}


class StoredCheckTests(SimpleTestCase):
    """docx_package.check_in_child and its worker side, fable_document.needs_fresh_conversion: release 2's package check
    of a stored original, in the bounded child under a conversion's limits, converting nothing."""

    def setUp(self):
        private_tempdir(self)

    def test_what_the_check_makes_of_each_kind_of_file(self):
        self.assertIs(docx_package.check_in_child(CLEAN_WORD), False)  # reused
        self.assertIs(docx_package.check_in_child(SHELLED_WORD), True)  # R2-30's QUOTE applies: converted afresh
        self.assertIs(docx_package.check_in_child(NOT_A_PACKAGE), False)  # no Word package: no conversion came of it
        # refused for another reason once it opened as a zip: the check cannot decide, and the converter decides, as for
        # any file (refutation round 2, rounds[0]: told apart from R2-30's edit)
        for data in (UNREADABLE_PART_WORD, COLLIDING_NAMES_WORD):
            self.assertEqual(docx_package.check_in_child(data), docx_package.CHECK_UNDECIDED)
        self.assertEqual(release_1_package()._safe_package(COLLIDING_NAMES_WORD)[1]['chunks'], 1)  # release 1 coded it
        for data, code, counts in ((IMPORTING_WORD, docx_package.INSERTED_DOCUMENT, IMPORTED_COUNTS),
                                   (BARE_OBJECT_WORD, docx_package.INSERTED_OBJECT, OBJECT_COUNTS)):
            with self.subTest(code=code), self.assertRaises(docx_package.ConversionRefused) as caught:
                docx_package.check_in_child(data)
            self.assertEqual((str(caught.exception), caught.exception.code, caught.exception.counts),
                             (docx_package.CONTENT_NOT_SHOWN, code, counts))

    def test_it_runs_in_the_bounded_child_under_a_conversions_limits_and_converts_nothing(self):
        with mock.patch.object(docx_package.bounded, 'run_bounded', wraps=docx_package.bounded.run_bounded) as child, \
                mock.patch.object(docx_package, 'soffice_convert', side_effect=AssertionError('converted')):
            self.assertFalse(docx_package.check_in_child(CLEAN_WORD))
        child.assert_called_once_with(docx_package._check_package, CLEAN_WORD, seconds=docx_package.CONVERT_SECONDS,
                                      memory_bytes=docx_package.CONVERT_MEMORY_BYTES)
        with mock.patch.object(docx_package, 'PACKAGE_SECONDS', -1), self.assertRaises(docx_package.ConversionBusy):
            docx_package.check_in_child(CLEAN_WORD)
        with self.assertRaises(docx_package.ConversionFailed):  # a child that passes a limit gives no answer
            docx_package.check_in_child(CLEAN_WORD, seconds=0)

    def test_the_worker_side_refuses_as_a_conversion_would_and_otherwise_converts_afresh(self):
        for data, code, counts in ((IMPORTING_WORD, docx_package.INSERTED_DOCUMENT, IMPORTED_COUNTS),
                                   (BARE_OBJECT_WORD, docx_package.INSERTED_OBJECT, OBJECT_COUNTS)):
            with self.subTest(code=code), self.assertRaises(fable_document.DocumentError) as caught:
                fable_document.needs_fresh_conversion(data)
            error = caught.exception
            self.assertEqual((error.failure_kind, error.text, error.code, error.counts, error.recorded()),
                             (CONVERT, fable_document.REFUSED_PACKAGE_TEXT[code], code, counts,
                              {'refused': code, 'inserted': counts}))
            with self.assertRaises(fable_document.DocumentError) as fresh:  # a fresh conversion ends the same way
                fable_document.convert_docx(data, runner=failing_runner)
            self.assertEqual((fresh.exception.text, fresh.exception.recorded()), (error.text, error.recorded()))
        self.assertIs(fable_document.needs_fresh_conversion(CLEAN_WORD), False)
        self.assertIs(fable_document.needs_fresh_conversion(SHELLED_WORD), True)
        for failure in (docx_package.ConversionBusy('synthetic'), docx_package.ConversionFailed('synthetic')):
            with self.subTest(failure=type(failure).__name__), \
                    mock.patch.object(docx_package, 'check_in_child', side_effect=failure):
                # undecided: converted afresh - and, for a round's own view, the converter decides first (rounds[0])
                self.assertEqual(fable_document.needs_fresh_conversion(CLEAN_WORD), docx_package.CHECK_UNDECIDED)

    def test_a_package_release_1_builds_otherwise_converts_afresh(self):
        # refutation round 2, rounds[1]: the check is False only where release 2's package is release 1's - a picture
        # whose id a kept attribute writes with a character reference keeps its relationship and part, and a name
        # stored without the UTF-8 flag keeps its UTF-8 reading, where release 1 lost the picture; their stored
        # conversions (release 1's) are not read again
        release_1 = release_1_package()
        for label, data in (('a picture id by a decimal reference', character_reference_word('&#114;IdPic')),
                            ('a picture id by a hexadecimal reference', character_reference_word('&#x72;IdPic')),
                            ('an object preview\'s id by a decimal reference',
                             character_reference_word('&#114;IdPic', in_object=True)),
                            ('a picture named without the UTF-8 flag', flagless_picture_word())):
            with self.subTest(f'converted afresh: {label}'):
                self.assertIs(docx_package.check_in_child(data), True)
                self.assertNotEqual(docx_package._safe_package(data)[0], release_1._safe_package(data)[0])
        for label, data in (('literal', character_reference_word('rIdPic')),
                            ('the removed field names nothing', character_reference_word('&#114;IdPic', named=False)),
                            ('an object preview\'s id, literal', character_reference_word('rIdPic', in_object=True))):
            with self.subTest(f'release 1\'s package, reused: {label}'):
                self.assertIs(docx_package.check_in_child(data), False)
                self.assertEqual(docx_package._safe_package(data)[0], release_1._safe_package(data)[0])


# --- R2-31 and C8 through the shipped job path -----------------------------------------------------------------------

STORED_PDF = b'%PDF-1.7\n% the synthetic conversion release 1 stored for this revision\n%%EOF\n'
FRESH_PDF = b'%PDF-1.7\n% a synthetic fresh conversion\n%%EOF\n'


@override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=False)
class RefusedWordUploadTests(r.CustomerCase, TestCase):
    """R2-31: a Word upload release 2 refuses fails its round, kind convert, with the sentence of its code; nothing is
    counted or sent; its audit trail is three rows - encounter.created, coding.round_queued and coding.round_failed
    with the code and counts -; the page shows the sentence and offers a retry, which fails the same way."""

    def setUp(self):
        super().setUp()
        private_tempdir(self)

    def upload(self, data):
        client = self.client_for(self.reviewer)
        answer = client.post('/api/encounters', {
            'file': SimpleUploadedFile('synthetic-note.docx', data, content_type=DOCX), 'title': 'Synthetic Word note',
            'service_date': '2026-11-05', 'insurance': 'medicare', 'synthetic_attestation': 'yes'})
        self.assertEqual(answer.status_code, 201, answer.content)
        return models.Encounter.objects.get(pk=answer.json()['id']), client

    def events(self, enc):
        return [(event.event, event.data) for event in AuditEvent.objects.filter(encounter=enc).order_by('created_at',
                                                                                                         'pk')]

    def assert_refused(self, data, code, counts):
        enc, client = self.upload(data)
        coder = self.use(f.FakeCoder())  # it fails the test if anything is sent
        with self.assertLogs('studio.jobs', 'INFO') as logged:
            self.run_next()
        round_ = jobs.latest_round(enc)
        # the worker's line names the code, one fixed word, which the installer's kept log keeps (R2-31)
        self.assertIn(f'INFO:studio.jobs:round {round_.pk}: the document was not sent ({code})', logged.output)
        sentence = fable_document.REFUSED_PACKAGE_TEXT[code]
        self.assertEqual((round_.state, round_.failure_kind, round_.error), (Round.FAILED, CONVERT, sentence))
        self.assertEqual((coder.counts, coder.calls), ([], []))
        self.assertFalse(Run.objects.filter(encounter=enc).exists())
        failed = {'round': str(round_.pk), 'failure_kind': CONVERT, 'refused': code, 'inserted': counts}
        events = self.events(enc)
        self.assertEqual([name for name, _ in events], ['encounter.created', 'coding.round_queued',
                                                        'coding.round_failed'])
        self.assertEqual(events[2][1], failed)
        progress = client.get(f'/api/encounters/{enc.pk}').json()['progress']
        self.assertEqual((progress['phase'], progress['error'], progress['can_retry']),
                         ('failed', {'text': sentence}, True))
        retried = client.post(f'/api/encounters/{enc.pk}/retry', data='{}', content_type='application/json')
        self.assertEqual(retried.status_code, 201, retried.content)
        self.run_next()
        again = jobs.latest_round(enc)
        self.assertEqual((again.number, again.trigger, again.state, again.failure_kind, again.error),
                         (2, Round.RETRY, Round.FAILED, CONVERT, sentence))
        self.assertEqual((coder.counts, coder.calls), ([], []))
        self.assertFalse(Run.objects.filter(encounter=enc).exists())
        events = self.events(enc)
        self.assertEqual([name for name, _ in events][3:], ['coding.round_queued', 'coding.round_failed'])
        self.assertEqual(events[4][1], {**failed, 'round': str(again.pk)})
        for _, data_ in events:  # codes and counts only: never a word of the file, its name or its title
            self.assertNotIn('synthetic', str(data_).casefold())
            self.assertNotIn('IMPORTED', str(data_))

    def test_a_word_upload_with_an_imported_document_is_refused_with_its_sentence_and_record(self):
        self.assert_refused(IMPORTING_WORD, docx_package.INSERTED_DOCUMENT, IMPORTED_COUNTS)

    def test_a_word_upload_with_a_bare_object_is_refused_with_its_sentence_and_record(self):
        self.assert_refused(BARE_OBJECT_WORD, docx_package.INSERTED_OBJECT, OBJECT_COUNTS)

    def test_the_two_sentences_carry_nothing_the_customer_denylist_forbids(self):
        scan = r.scan_customer()
        for code, sentence in fable_document.REFUSED_PACKAGE_TEXT.items():
            with self.subTest(code=code):
                self.assertEqual(scan.scan_text(sentence, scan.scan_context(), 'json'), [])
                self.assertEqual(scan.scan_text(code, scan.scan_context(), 'json'), [])
        self.assertEqual(set(fable_document.REFUSED_PACKAGE_TEXT), set(docx_package.REFUSAL_CODES))


@override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=False)
class StoredConversionTests(r.CustomerCase, TestCase):
    """C8: a later round of a revision (an answers round, a retry) that would read the conversion an earlier round
    stored - here one release 1 stored before the install - runs the package check on the stored original first."""

    def setUp(self):
        super().setUp()
        private_tempdir(self)

    def stored(self, data):
        """A Word document whose round 1 release 1 coded, its conversion stored in the practice's own folder."""
        enc = f.encounter(self.ws, self.reviewer, service_date='2026-11-02', insurance='medicare',
                          title='Synthetic Word note')
        rev = f.upload(enc, self.reviewer, data=data, filename='synthetic-note.docx', media_type=DOCX)
        first = r.write_round(enc)
        name, digest, _ = storage.store_original(self.ws.pk, STORED_PDF, 'converted.pdf')
        Round.objects.filter(pk=first.pk).update(view_pdf_storage_name=name, view_pdf_sha256=digest)
        return enc, rev, name, digest

    def next_round(self, enc, rev, trigger, coder, converted=None):
        """The round of ``trigger`` run through the shipped stage, the converter a stand-in that fails the test unless
        ``converted`` is given (what it then answers), and the check spied on."""
        if trigger == Round.RETRY:
            jobs.retry(enc, self.reviewer)
        else:
            jobs.start_round(enc, rev, trigger, self.reviewer)
        self.use(coder)
        effect = {'return_value': converted} if converted else {'side_effect': AssertionError('no conversion here')}
        with mock.patch.object(fable_document, 'convert_docx', **effect) as convert, \
                mock.patch.object(docx_package, 'check_in_child', wraps=docx_package.check_in_child) as check:
            self.run_next()
        return jobs.latest_round(enc), convert, check

    def answering(self):
        return f.FakeCoder(reader=f.succeeded(r.reader_message(r.READER)),
                           checker=f.succeeded(r.checker_message(r.CHECKER)))

    def sent(self, coder):
        return {request.stored['messages'][0]['content'][0]['source']['data']['$original_sha256']
                for _, request in coder.calls}

    def test_a_stored_conversion_of_a_file_the_check_refuses_is_refused_at_its_next_round(self):
        for data, code, counts in ((IMPORTING_WORD, docx_package.INSERTED_DOCUMENT, IMPORTED_COUNTS),
                                   (BARE_OBJECT_WORD, docx_package.INSERTED_OBJECT, OBJECT_COUNTS)):
            with self.subTest(code=code):
                enc, rev, _, _ = self.stored(data)
                before = AuditEvent.objects.filter(encounter=enc).count()
                for trigger, number in ((Round.ANSWERS, 2), (Round.RETRY, 3)):
                    coder = f.FakeCoder()  # it fails the test if anything is sent
                    round_, convert, check = self.next_round(enc, rev, trigger, coder)
                    self.assertEqual((round_.number, round_.trigger, round_.state, round_.failure_kind, round_.error),
                                     (number, trigger, Round.FAILED, CONVERT,
                                      fable_document.REFUSED_PACKAGE_TEXT[code]))
                    self.assertEqual((coder.counts, coder.calls), ([], []))  # nothing counted, nothing sent
                    convert.assert_not_called()  # no converter call, no conversion
                    check.assert_called_once_with(data)  # the stored original, checked
                    self.assertFalse(Run.objects.filter(encounter=enc).exists())
                    self.assertIsNone(round_.view_pdf_storage_name)
                    added = list(AuditEvent.objects.filter(encounter=enc).order_by('created_at', 'pk')
                                 .values_list('event', 'data'))[before:]
                    self.assertEqual([event for event, _ in added], ['coding.round_queued', 'coding.round_failed'])
                    self.assertEqual(added[1][1], {'round': str(round_.pk), 'failure_kind': CONVERT, 'refused': code,
                                                   'inserted': counts})
                    before += 2

    def test_a_clean_stored_conversion_is_reused_byte_identically_with_no_converter_call(self):
        enc, rev, name, digest = self.stored(CLEAN_WORD)
        coder = self.answering()
        round_, convert, check = self.next_round(enc, rev, Round.ANSWERS, coder)
        self.assertEqual(round_.state, Round.DONE)
        convert.assert_not_called()
        check.assert_called_once_with(CLEAN_WORD)
        self.assertEqual((round_.view_pdf_storage_name, round_.view_pdf_sha256), (name, digest))  # the same file
        self.assertEqual(self.sent(coder), {digest})  # both sends carried the stored PDF
        self.assertEqual(len(coder.calls), 2)

    def test_a_stored_conversion_whose_original_holds_r2_30s_shape_converts_afresh(self):
        enc, rev, name, digest = self.stored(SHELLED_WORD)
        coder = self.answering()
        round_, convert, check = self.next_round(enc, rev, Round.ANSWERS, coder, converted=FRESH_PDF)
        self.assertEqual(round_.state, Round.DONE)
        convert.assert_called_once_with(SHELLED_WORD)  # one converter call, so the QUOTE applies
        fresh = hashlib.sha256(FRESH_PDF).hexdigest()
        self.assertEqual(round_.view_pdf_sha256, fresh)
        self.assertNotEqual(round_.view_pdf_storage_name, name)
        self.assertEqual(self.sent(coder), {fresh})

    def test_a_stored_original_that_is_no_word_package_is_reused_as_release_1_reused_it(self):
        # no conversion of such a file was ever made by either release's checks (refused before any part is read):
        # nothing release 2 added applies to it, so its stored view is read again as before
        enc, rev, name, digest = self.stored(NOT_A_PACKAGE)
        coder = self.answering()
        round_, convert, check = self.next_round(enc, rev, Round.ANSWERS, coder)
        self.assertEqual((round_.state, round_.view_pdf_sha256), (Round.DONE, digest))
        convert.assert_not_called()
        check.assert_called_once_with(NOT_A_PACKAGE)

    def test_a_stored_conversion_of_a_zip_refused_before_its_parts_are_read_converts_afresh(self):
        # refutation round 1, protocol[2]: a zip the check refuses before reading its parts - here a part past
        # MAX_PART_BYTES once inflated, beside an import - is no exception: the round converts afresh and the converter
        # refuses the file as a fresh conversion of it would, so the stored PDF (one made before release 1's limits) is
        # never read again. Only a file that is no zip at all, of which no conversion was ever made, is reused.
        big = package(BEFORE + '<w:altChunk r:id="rIdChunk"/>' + AFTER, (rel('rIdChunk', 'aFChunk', 'afchunk1.docx'),),
                      (('word/afchunk1.docx', inner_docx('IMPORTED SYNTHETIC TEXT')),
                       ('word/media/large.bin', b'\0' * (docx_package.MAX_PART_BYTES + 1))))
        enc, rev, _, _ = self.stored(big)
        jobs.start_round(enc, rev, Round.ANSWERS, self.reviewer)
        coder = f.FakeCoder()  # it fails the test if anything is sent
        self.use(coder)
        real = fable_document.convert_docx
        with mock.patch.object(fable_document, 'convert_docx',
                               side_effect=lambda d, **kw: real(d, runner=failing_runner, **kw)) as convert, \
                mock.patch.object(docx_package, 'check_in_child', wraps=docx_package.check_in_child) as check, \
                override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=False):
            self.run_next()
        round_ = jobs.latest_round(enc)
        self.assertEqual((round_.state, round_.failure_kind, round_.error),
                         (Round.FAILED, CONVERT, fable_document.CONVERT_TEXT))
        check.assert_called_once_with(big)
        convert.assert_called_once_with(big)
        self.assertEqual((coder.counts, coder.calls), ([], []))
        self.assertIsNone(round_.view_pdf_storage_name)

    def test_a_stored_original_refused_once_its_parts_are_read_converts_afresh(self):
        # the converter then gives its refusal, as for any fresh conversion (here a stand-in converts it)
        enc, rev, name, digest = self.stored(UNREADABLE_PART_WORD)
        round_, convert, check = self.next_round(enc, rev, Round.ANSWERS, self.answering(), converted=FRESH_PDF)
        convert.assert_called_once_with(UNREADABLE_PART_WORD)
        self.assertEqual(round_.view_pdf_sha256, hashlib.sha256(FRESH_PDF).hexdigest())


    def test_a_fresh_conversion_that_cannot_be_stored_beside_an_earlier_view_fails_the_round_storage(self):
        # refutation round 1, view[2]: C8 converts afresh where an earlier round stored a view; when this round's own
        # conversion cannot be stored, the viewer would show that earlier, other conversion beside this round's codes -
        # so the round fails 'storage' before anything is sent, and a retry codes it again
        enc, rev, name, digest = self.stored(SHELLED_WORD)
        coder = f.FakeCoder()  # it fails the test if anything is sent
        unwritable = OSError('synthetic: the folder cannot be written')
        with mock.patch.object(jobs, 'store_original', side_effect=unwritable), self.assertLogs('studio.jobs', 'ERROR'):
            round_, convert, _ = self.next_round(enc, rev, Round.ANSWERS, coder, converted=FRESH_PDF)
        convert.assert_called_once_with(SHELLED_WORD)
        self.assertEqual((round_.state, round_.failure_kind), (Round.FAILED, jobs.STORAGE))
        self.assertEqual((coder.counts, coder.calls), ([], []))
        self.assertIsNone(round_.view_pdf_storage_name)
        self.assertEqual(self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()['codes'], [])

    def test_a_fresh_conversion_past_the_stores_limit_beside_an_earlier_view_fails_as_one_too_large(self):
        # refutation round 2, rounds[4]: store_original refuses a conversion over MAX_UPLOAD_BYTES at every round while
        # prepare keeps one up to MAX_PDF_BYTES, so 'storage' (which a retry would meet again, for ever) is not the
        # failure: beside an earlier view the round fails DOCUMENT with the Word file's sentence, nothing sent - an
        # answers round and a retry alike (the real store_original)
        enc, rev, _, _ = self.stored(SHELLED_WORD)
        prefix = b'%PDF-1.7\n% a synthetic conversion past the store\'s limit\n'
        large = prefix + b'0' * (settings.MAX_UPLOAD_BYTES + 1 - len(prefix))
        self.assertLess(len(large), docx_package.MAX_PDF_BYTES)
        for trigger, number in ((Round.ANSWERS, 2), (Round.RETRY, 3)):
            with self.subTest(trigger=trigger):
                coder = f.FakeCoder()  # it fails the test if anything is sent
                with self.assertLogs('studio.jobs', 'ERROR'):
                    round_, convert, _ = self.next_round(enc, rev, trigger, coder, converted=large)
                convert.assert_called_once_with(SHELLED_WORD)
                self.assertEqual((round_.number, round_.state, round_.failure_kind, round_.error),
                                 (number, Round.FAILED, DOCUMENT, fable_document.REFUSED_TEXT['docx']))
                self.assertEqual((coder.counts, coder.calls), ([], []))
                self.assertIsNone(round_.view_pdf_storage_name)

    def test_a_stored_conversion_of_a_package_release_1_built_otherwise_converts_afresh(self):
        # refutation round 2, rounds[1]: release 1's stored conversion of a file whose release-2 package keeps a picture
        # release 1's lost (an id a character reference writes - R1-L6a; a name stored without the UTF-8 flag - R1-L2b)
        # is not read again: the next round converts afresh, with one converter call, and both reads carry the fresh PDF
        for label, data in (('a picture id by a decimal reference', character_reference_word('&#114;IdPic')),
                            ('a picture named without the UTF-8 flag', flagless_picture_word())):
            with self.subTest(label):
                enc, rev, name, _ = self.stored(data)
                coder = self.answering()
                round_, convert, check = self.next_round(enc, rev, Round.ANSWERS, coder, converted=FRESH_PDF)
                self.assertEqual(round_.state, Round.DONE)
                check.assert_called_once_with(data)
                convert.assert_called_once_with(data)
                fresh = hashlib.sha256(FRESH_PDF).hexdigest()
                self.assertEqual((round_.view_pdf_sha256, self.sent(coder)), (fresh, {fresh}))
                self.assertNotEqual(round_.view_pdf_storage_name, name)


# --- refutation round 1, view[0] and loss[3]: a resumed Word round that recorded its own view reads, records and shows
# one PDF (refutation round 2, rounds[2]: a round that stored no view has none to read back, and converts afresh) ----

RESUME_PAGE = b'%PDF-1.6\n1 0 obj <</Type/Page>> endobj\n% the same page streams in both conversions\n'
RESUME_PDF_A = RESUME_PAGE + b'/CreationDate(D:20261126002410Z)\n/ID [<55583B0FAFF25547>]\n%%EOF\n'
RESUME_PDF_B = RESUME_PAGE + b'/CreationDate(D:20261126002412Z)\n/ID [<00D3679272100CE7>]\n%%EOF\n'


def pdf_sha(data):
    return hashlib.sha256(data).hexdigest()


def stored_files():
    """{every file under the originals folder: its sha256}."""
    return {path: pdf_sha(path.read_bytes()) for path in Path(settings.ORIGINALS_DIR).rglob('*') if path.is_file()}


@override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=False)
class ResumedWordRoundTests(r.CustomerCase, TestCase):
    """Refutation round 1, view[0] and loss[3]: a round that recorded a conversion as its own view - stopped and
    resumed, or requeued, its reads paid or not, begun on release 1's worker or on release 2's - reads that conversion
    back: its reader, its checker, its view and the page served are one PDF, and the file the reader read is kept. A
    file the check refuses still ends a resumed round, and a later round of an R2-30 revision still converts afresh
    (C8). When the check cannot decide, the converter decides first, and the round reads its own view back only once the
    converter has accepted the file (refutation round 2, rounds[0]). Two conversions of one file differ in their bytes
    (the PDF's creation time and id), as here."""

    def setUp(self):
        super().setUp()
        private_tempdir(self)

    def word(self, data):
        enc = f.encounter(self.ws, self.reviewer, service_date='2026-11-02', insurance='medicare',
                          title='Synthetic Word note')
        rev = f.upload(enc, self.reviewer, data=data, filename='synthetic-note.docx', media_type=DOCX)
        return enc, rev, jobs.start_round(enc, rev, Round.UPLOAD, self.reviewer)

    @staticmethod
    def carried(run):
        return run.request_body['messages'][0]['content'][0]['source']['data']['$original_sha256']

    @staticmethod
    def answering():
        return f.FakeCoder(reader=f.succeeded(r.reader_message(r.READER)),
                           checker=f.succeeded(r.checker_message(r.CHECKER)))

    def stopping(self, enc, *, after='reader'):
        """A coder whose reader (or checker) answers and then the encounter is stopped."""
        reader, checker = f.succeeded(r.reader_message(r.READER)), f.succeeded(r.checker_message(r.CHECKER))

        def answer_then_stop(answer):
            def answered(request):
                jobs.stop_encounter(enc, self.reviewer)
                return answer
            return answered
        if after == 'reader':
            return f.FakeCoder(reader=answer_then_stop(reader), checker=checker)
        return f.FakeCoder(reader=reader, checker=answer_then_stop(checker))

    def assert_one_pdf(self, enc, round_, pdf, name, converted, *, conversions=None):
        """The round DONE on ``pdf`` alone - its reads, its view, the page served - kept under ``name``, after
        ``converted`` conversions (one for RESUME_PDF_A, none for a stored one, unless ``conversions`` says)."""
        round_.refresh_from_db()
        reader = Run.objects.get(purpose=jobs.READER, scope__round=str(round_.pk))
        checker = Run.objects.get(purpose=jobs.CHECKER, scope__round=str(round_.pk))
        served = self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}/original?view=1').content
        self.assertEqual(round_.state, Round.DONE)
        self.assertEqual(converted, conversions if conversions is not None else 1 if pdf is RESUME_PDF_A else 0)
        self.assertEqual({self.carried(reader), self.carried(checker), round_.view_pdf_sha256, pdf_sha(served)},
                         {pdf_sha(pdf)})
        self.assertEqual(round_.view_pdf_storage_name, name)  # the file the reader read is the one kept

    def stopped_then_resumed(self, data, check=None):
        """(enc, the round, the converter's mock, the round's first view's name, the files its resumed pass stored)."""
        with mock.patch.object(fable_document, 'convert_docx', side_effect=[RESUME_PDF_A, RESUME_PDF_B]) as convert:
            enc, _, round_ = self.word(data)
            self.use(self.stopping(enc))
            self.run_next()
            round_.refresh_from_db()
            first = round_.view_pdf_storage_name
            self.assertEqual((round_.state, round_.view_pdf_sha256), (Round.CANCELLED, pdf_sha(RESUME_PDF_A)))
            jobs.resume(enc, self.reviewer)
            before = stored_files()
            if check is None:
                self.run_next()
            else:
                with mock.patch.object(docx_package, 'check_in_child', side_effect=check):
                    self.run_next()
        added = {path: digest for path, digest in stored_files().items() if path not in before}
        return enc, round_, convert, first, added

    def begun_on_release_1(self, data, paid):
        """A Word revision release 1 coded - round 1, its conversion stored as STORED_PDF - and an answers round begun
        on release 1's worker, which has no check: it reuses that conversion, records it as its own view, and then
        stops - requeued at its reader's slot with nothing sent ('nothing'), stopped after its reader ('the reader',
        resumed here), or requeued after both reads, before they were combined ('both reads'). (enc, rev, the round,
        the stored view's name, its sha256, how many runs the round holds)."""
        enc = f.encounter(self.ws, self.reviewer, service_date='2026-11-02', insurance='medicare',
                          title='Synthetic Word note')
        rev = f.upload(enc, self.reviewer, data=data, filename='synthetic-note.docx', media_type=DOCX)
        first = r.write_round(enc)
        name, digest, _ = storage.store_original(self.ws.pk, STORED_PDF, 'converted.pdf')
        Round.objects.filter(pk=first.pk).update(view_pdf_storage_name=name, view_pdf_sha256=digest)
        round_ = jobs.start_round(enc, rev, Round.ANSWERS, self.reviewer)
        halt = mock.patch.object(jobs.fable_result, 'combine', wraps=jobs.fable_result.combine)
        if paid == 'nothing':
            self.use(f.FakeCoder())  # it fails the test if anything is sent
            halt = mock.patch.object(jobs, '_take_slot', side_effect=jobs.Requeue('synthetic: every slot is in use'))
        elif paid == 'the reader':
            self.use(self.stopping(enc))
        else:
            self.use(self.answering())
            halt = mock.patch.object(jobs.fable_result, 'combine',
                                     side_effect=jobs.Requeue('synthetic: requeued before combining'))
        with mock.patch.object(fable_document, 'needs_fresh_conversion', return_value=False), \
                mock.patch.object(fable_document, 'convert_docx', side_effect=AssertionError('release 1 reused it')), \
                halt, mock.patch.object(jobs, 'REQUEUE_SECONDS', 0):
            self.run_next()  # release 1's worker: no check
        round_.refresh_from_db()
        self.assertEqual((round_.state, round_.view_pdf_sha256),
                         (Round.CANCELLED if paid == 'the reader' else Round.QUEUED, digest))
        runs = Run.objects.filter(scope__round=str(round_.pk)).count()
        self.assertEqual(runs, {'nothing': 0, 'the reader': 1, 'both reads': 2}[paid])
        if paid == 'the reader':
            jobs.resume(enc, self.reviewer)
        return enc, rev, round_, name, digest, runs

    def test_a_stopped_and_resumed_round_of_r2_30s_shape_reads_its_own_conversion(self):
        enc, round_, convert, first, _ = self.stopped_then_resumed(SHELLED_WORD)
        self.assert_one_pdf(enc, round_, RESUME_PDF_A, first, convert.call_count)

    def requeued_at(self, slot, data=SHELLED_WORD):
        """A round of ``data`` requeued at its ``slot``-th provider slot (1: the reader's, before anything was sent; 2:
        the checker's), then run again: (enc, the round, the converter's mock, its first view's name)."""
        real_take, taken = jobs._take_slot, []

        def no_slot():
            taken.append(1)
            if len(taken) == slot:
                raise jobs.Requeue('every provider slot is in use')
            return real_take()
        enc, _, round_ = self.word(data)
        self.use(self.answering())
        with mock.patch.object(fable_document, 'convert_docx', side_effect=[RESUME_PDF_A, RESUME_PDF_B]) as convert, \
                mock.patch.object(jobs, '_take_slot', side_effect=no_slot), \
                mock.patch.object(jobs, 'REQUEUE_SECONDS', 0):
            self.run_next()
            round_.refresh_from_db()
            first = round_.view_pdf_storage_name
            self.assertEqual((round_.state, round_.view_pdf_sha256), (Round.QUEUED, pdf_sha(RESUME_PDF_A)))
            self.assertEqual(Run.objects.filter(scope__round=str(round_.pk)).count(), slot - 1)
            self.run_next()
        return enc, round_, convert, first

    def test_a_round_requeued_between_its_reads_reads_its_own_conversion(self):
        enc, round_, convert, first = self.requeued_at(2)
        self.assert_one_pdf(enc, round_, RESUME_PDF_A, first, convert.call_count)

    def test_a_round_requeued_at_its_readers_slot_reads_its_own_conversion(self):
        # refutation round 2, rounds[3]: the rule's unpaid half - requeued before anything was sent, its own view
        # recorded and no read paid - reads that view back too
        enc, round_, convert, first = self.requeued_at(1)
        self.assert_one_pdf(enc, round_, RESUME_PDF_A, first, convert.call_count)

    def test_a_resumed_clean_round_whose_check_cannot_decide_reads_its_own_conversion(self):
        # refutation round 2, rounds[0]: the converter decides first - a second conversion - and, once it has accepted
        # the file, the round reads its own view back; the PDF made to decide is neither read nor stored
        for failure in (docx_package.ConversionBusy('synthetic: out of time'),
                        docx_package.ConversionFailed('synthetic: the child failed')):
            with self.subTest(failure=type(failure).__name__):
                enc, round_, convert, first, added = self.stopped_then_resumed(CLEAN_WORD, check=failure)
                self.assertEqual([call.args for call in convert.call_args_list], [(CLEAN_WORD,), (CLEAN_WORD,)])
                self.assert_one_pdf(enc, round_, RESUME_PDF_A, first, convert.call_count, conversions=2)
                self.assertEqual(added, {})  # the second conversion was not stored
                self.assertFalse(Round.objects.filter(view_pdf_sha256=pdf_sha(RESUME_PDF_B)).exists())

    def test_a_file_the_check_refuses_still_ends_a_resumed_round(self):
        # its first pass converted as release 1's converter did, before the converter's phase: the resume is refused
        enc, round_, convert, _, _ = self.stopped_then_resumed(IMPORTING_WORD)
        round_.refresh_from_db()
        self.assertEqual((round_.state, round_.failure_kind, round_.error),
                         (Round.FAILED, CONVERT, fable_document.REFUSED_PACKAGE_TEXT[docx_package.INSERTED_DOCUMENT]))
        self.assertEqual(convert.call_count, 1)
        self.assertFalse(Run.objects.filter(purpose=jobs.CHECKER, scope__round=str(round_.pk)).exists())
        # refutation round 2, rounds[3]: begun on release 1's worker and requeued before anything was sent, then run on
        # release 2's - the check refuses the file, with no converter call and nothing sent
        for data, code in ((IMPORTING_WORD, docx_package.INSERTED_DOCUMENT),
                           (BARE_OBJECT_WORD, docx_package.INSERTED_OBJECT)):
            with self.subTest(code=code):
                enc, _, round_, _, _, _ = self.begun_on_release_1(data, 'nothing')
                with mock.patch.object(fable_document, 'convert_docx',
                                       side_effect=AssertionError('no conversion')) as convert:
                    self.run_next()
                round_.refresh_from_db()
                self.assertEqual((round_.state, round_.failure_kind, round_.error),
                                 (Round.FAILED, CONVERT, fable_document.REFUSED_PACKAGE_TEXT[code]))
                convert.assert_not_called()
                self.assertFalse(Run.objects.filter(scope__round=str(round_.pk)).exists())

    def test_an_own_view_whose_check_cannot_decide_is_read_again_only_once_the_converter_accepts_the_file(self):
        # refutation round 2, rounds[0]: a round begun on release 1's worker recorded release 1's conversion - which
        # left the import or the object out - as its own view, and stopped: requeued with nothing sent, or after its
        # reader. On release 2's worker its check cannot decide (out of time; a failed child; a refusal that is not
        # ContentNotShown - two pictures whose names differ only in case): the converter decides, refuses the file, and
        # the round ends with the converter's sentence, nothing more sent and its own view never read again
        real = fable_document.convert_docx
        cases = [(data, code, paid, failure)
                 for data, code in ((IMPORTING_WORD, docx_package.INSERTED_DOCUMENT),
                                    (BARE_OBJECT_WORD, docx_package.INSERTED_OBJECT))
                 for paid in ('nothing', 'the reader')
                 for failure in (docx_package.ConversionBusy('synthetic: out of time'),
                                 docx_package.ConversionFailed('synthetic: the child failed'))]
        cases += [(COLLIDING_NAMES_WORD, None, paid, None) for paid in ('nothing', 'the reader')]
        for data, code, paid, failure in cases:
            with self.subTest(code=code, paid=paid, check=type(failure).__name__ if failure else 'the real check'):
                enc, _, round_, _, _, runs = self.begun_on_release_1(data, paid)
                check = {'side_effect': failure} if failure else {'wraps': docx_package.check_in_child}
                with mock.patch.object(docx_package, 'check_in_child', **check) as checked, \
                        mock.patch.object(fable_document, 'convert_docx',
                                          side_effect=lambda d, **kw: real(d, runner=failing_runner, **kw)) as convert:
                    self.run_next()
                round_.refresh_from_db()
                text = fable_document.REFUSED_PACKAGE_TEXT[code] if code else fable_document.CONVERT_TEXT
                self.assertEqual((round_.state, round_.failure_kind, round_.error), (Round.FAILED, CONVERT, text))
                checked.assert_called_once_with(data)
                convert.assert_called_once_with(data)  # the converter decided
                self.assertEqual(Run.objects.filter(scope__round=str(round_.pk)).count(), runs)  # nothing more sent

    def test_an_own_view_whose_check_cannot_decide_is_never_read_again_while_the_converter_is_busy(self):
        # refutation round 3, rounds[0]: the BUSY half - a busy converter (the service unreachable, or required with no
        # socket) has not accepted the file: the round fails BUSY, nothing more is sent, and its own view (release 1's
        # conversion, without the import or the object) is never read again
        cases = [(data, paid, failure)
                 for data in (IMPORTING_WORD, BARE_OBJECT_WORD)
                 for paid in ('nothing', 'the reader')
                 for failure in (docx_package.ConversionBusy('synthetic: out of time'),
                                 docx_package.ConversionFailed('synthetic: the child failed'))]
        cases += [(COLLIDING_NAMES_WORD, paid, None) for paid in ('nothing', 'the reader')]
        for data, paid, failure in cases:
            for converter in ('the service, unreachable', 'required, no socket'):
                with self.subTest(paid=paid, check=type(failure).__name__ if failure else 'the real check',
                                  converter=converter):
                    enc, _, round_, _, _, runs = self.begun_on_release_1(data, paid)
                    self.use(self.answering())  # a regression shows as DONE, not as a coder's complaint
                    check = {'side_effect': failure} if failure else {'wraps': docx_package.check_in_child}
                    nowhere = str(Path(tempfile.gettempdir()) / 'nothing-listens-here.sock')
                    busy = (override_settings(CONVERTER_SOCKET=nowhere) if converter.startswith('the service')
                            else override_settings(CONVERTER_SOCKET='', CONVERTER_REQUIRED=True))
                    with mock.patch.object(docx_package, 'check_in_child', **check), busy, \
                            mock.patch.object(fable_document, 'convert_docx',
                                              wraps=fable_document.convert_docx) as convert:
                        self.run_next()
                    round_.refresh_from_db()
                    self.assertEqual((round_.state, round_.failure_kind, round_.error),
                                     (Round.FAILED, BUSY, fable_document.BUSY_TEXT))
                    convert.assert_called_once_with(data)
                    self.assertEqual(Run.objects.filter(scope__round=str(round_.pk)).count(), runs)

    def test_an_own_view_the_converter_accepted_is_not_decided_again_at_each_pass(self):
        # refutation round 3, rounds[3]: while the check cannot decide, an own-view round requeued at its reader's slot
        # asks the converter once - its acceptance is remembered for the round in this worker process - and not at
        # every pass (each a full conversion thrown away): the view's conversion, then one decision, and no third
        real_take, taken = jobs._take_slot, []

        def busy_slots():
            taken.append(1)
            if len(taken) <= 4:
                raise jobs.Requeue('every provider slot is in use')
            return real_take()
        enc, _, round_ = self.word(CLEAN_WORD)
        self.use(self.answering())
        with mock.patch.object(fable_document, 'convert_docx', side_effect=[RESUME_PDF_A, RESUME_PDF_B]) as convert, \
                mock.patch.object(jobs, '_take_slot', side_effect=busy_slots), \
                mock.patch.object(jobs, 'REQUEUE_SECONDS', 0), \
                mock.patch.object(docx_package, 'check_in_child',
                                  side_effect=docx_package.ConversionBusy('synthetic: out of time')):
            self.run_next()
            round_.refresh_from_db()
            first = round_.view_pdf_storage_name
            for _ in range(4):
                self.run_next()
        self.assertEqual(len(taken), 6)  # four requeues, then the reader's and the checker's slots
        self.assert_one_pdf(enc, round_, RESUME_PDF_A, first, convert.call_count, conversions=2)

    def test_a_later_round_of_an_r2_30_revision_still_converts_afresh(self):
        enc, rev, _ = self.word(SHELLED_WORD)
        self.use(self.answering())
        with mock.patch.object(fable_document, 'convert_docx', side_effect=[RESUME_PDF_A, RESUME_PDF_B]) as convert:
            self.run_next()
            later = jobs.start_round(enc, rev, Round.ANSWERS, self.reviewer)
            self.run_next()
        later.refresh_from_db()
        self.assertEqual((later.state, convert.call_count, later.view_pdf_sha256),
                         (Round.DONE, 2, pdf_sha(RESUME_PDF_B)))

    def test_a_round_begun_on_release_1s_worker_and_resumed_after_the_switch_stays_on_its_pdf(self):
        # loss[3]: release 1's worker reused the stored conversion (it has no check) and recorded it as the round's own
        # view - then nothing was sent (a requeue at the reader's slot: refutation round 2, rounds[3]), or it read its
        # reader alone and stopped, or both reads and was requeued before they were combined. Resumed on release 2's
        # worker, the round reads that same PDF back, with no converter call; only the next round converts afresh, so
        # R2-30's edit applies
        for paid in ('nothing', 'the reader', 'both reads'):
            with self.subTest(paid=paid):
                enc, rev, round_, name, _, _ = self.begun_on_release_1(SHELLED_WORD, paid)
                if paid == 'nothing':
                    self.use(self.answering())
                with mock.patch.object(fable_document, 'convert_docx', side_effect=AssertionError('no conversion')):
                    self.run_next()
                self.assert_one_pdf(enc, round_, STORED_PDF, name, 0)
                self.use(self.answering())
                later = jobs.start_round(enc, rev, Round.ANSWERS, self.reviewer)
                with mock.patch.object(fable_document, 'convert_docx', return_value=RESUME_PDF_B) as convert:
                    self.run_next()
                later.refresh_from_db()
                convert.assert_called_once_with(SHELLED_WORD)
                self.assertEqual((later.state, later.view_pdf_sha256), (Round.DONE, pdf_sha(RESUME_PDF_B)))

# --- refutation round 1, refuse[0]: what the coder is sent for a clean Word file, pinned to release 1 ----------------
# tests/test_request_identity.py pins it for text, paste and PDF (R2-3); this is the Word case. The shapes are stored
# zip entries (no zlib in any byte), coded through the shipped job path with a coder that records every request and the
# in-process conversion, whose runner (laned_pin_pdf, the LibreOffice stand-in) answers a PDF naming the sha256 of the
# package safe_package made - so a changed package changes the request.
PIN_W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
PIN_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PIN_PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
PIN_CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
PIN_NS = (f'xmlns:w="{PIN_W}" xmlns:r="{PIN_R}" xmlns:v="urn:schemas-microsoft-com:vml" '
          'xmlns:o="urn:schemas-microsoft-com:office:office"')
PIN_EMF = b'\x01\x00\x00\x00 synthetic EMF preview picture'
PIN_XLSX = b'PK\x03\x04 synthetic workbook bytes'


def laned_pin_pdf(package, work):
    """The LibreOffice stand-in of the request pin: a PDF naming the sha256 of the package it was given (module level:
    it runs in the bounded child)."""
    return b'%PDF-1.4\n% package ' + hashlib.sha256(package).hexdigest().encode() + b'\n%%EOF\n'


def pin_word(body, rels=(), parts=()):
    rows = ''.join(f'<Relationship Id="{rid}" Type="{PIN_R}/{kind}" Target="{target}"/>' for rid, kind, target in rels)
    entries = [
        ('[Content_Types].xml', f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="{PIN_CT}">'
                                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
                                'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                                '<Default Extension="emf" ContentType="image/x-emf"/><Default Extension="xlsx" '
                                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"/>'
                                '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
                                'officedocument.wordprocessingml.document.main+xml"/></Types>'),
        ('_rels/.rels', f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="{PIN_PKG}">'
                        f'<Relationship Id="rId1" Type="{PIN_R}/officeDocument" Target="word/document.xml"/>'
                        '</Relationships>'),
        ('word/document.xml', f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {PIN_NS}>'
                              f'<w:body>{body}</w:body></w:document>'),
        ('word/_rels/document.xml.rels', f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                                         f'<Relationships xmlns="{PIN_PKG}">{rows}</Relationships>'),
        *parts]
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        for name, content in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 26, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED  # no zlib in the bytes: the same wherever the suite runs
            info.create_system = 3
            archive.writestr(info, content)
    return out.getvalue()


def pin_t(text):
    return f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'


def pin_fc(kind):
    return f'<w:r><w:fldChar w:fldCharType="{kind}"/></w:r>'


def pin_instr(text):
    return f'<w:r><w:instrText xml:space="preserve">{text}</w:instrText></w:r>'


def pin_field(instruction, result_xml):
    return pin_fc('begin') + pin_instr(instruction) + pin_fc('separate') + result_xml + pin_fc('end')


PIN_TEXT = '<w:p>' + pin_t('SYNTHETIC PROCEDURE NOTE. Colonoscopy to the cecum; one 6 mm sigmoid polyp, cold snare.') \
    + '</w:p>'
PIN_SHAPETYPE = ('<v:shapetype id="_x0000_t75" coordsize="21600,21600" o:spt="75" path="m@4@5l@4@11@9@11@9@5xe">'
                 '<v:stroke joinstyle="miter"/></v:shapetype>')
PIN_SHAPE = ('<v:shape id="_x0000_i1025" type="#_x0000_t75" style="width:72pt;height:36pt" o:ole="">'
             '<v:imagedata r:id="rIdPrev" o:title=""/></v:shape>')
PIN_OLE = ('<o:OLEObject Type="Embed" ProgID="Excel.Sheet.12" ShapeID="_x0000_i1025" DrawAspect="Content" '
           'r:id="rIdOle"/>')
PIN_PREVIEW_REL, PIN_PREVIEW_PART = ('rIdPrev', 'image', 'media/image1.emf'), ('word/media/image1.emf', PIN_EMF)
PIN_OBJECT_RELS = (PIN_PREVIEW_REL, ('rIdOle', 'package', 'embeddings/x.xlsx'))
PIN_OBJECT_PARTS = (PIN_PREVIEW_PART, ('word/embeddings/x.xlsx', PIN_XLSX))
PIN_INC = ' INCLUDETEXT "c:\\\\x\\\\y.docx" '
PIN_SHAPES = {
    'plain, a PAGE field': pin_word(PIN_TEXT + '<w:p>' + pin_field(' PAGE ', pin_t('1')) + '</w:p>'),
    'an object with its preview': pin_word(
        PIN_TEXT + '<w:p><w:r><w:object w:dxaOrig="1440" w:dyaOrig="720">' + PIN_SHAPETYPE + PIN_SHAPE + PIN_OLE
        + '</w:object></w:r></w:p>', PIN_OBJECT_RELS, PIN_OBJECT_PARTS),
    'a removed field with its result': pin_word(PIN_TEXT + '<w:p>' + pin_field(PIN_INC, pin_t('INCLUDED RESULT'))
                                                + '</w:p>'),
    'an empty w:object': pin_word(PIN_TEXT + '<w:p><w:r><w:object w:dxaOrig="1440" w:dyaOrig="900"/></w:r></w:p>'),
    'an empty removed w:fldSimple in an IF result': pin_word(
        PIN_TEXT + '<w:p>' + pin_field(' IF 1 = 1 "a" "b" ', "<w:fldSimple w:instr=' INCLUDETEXT x '/>") + '</w:p>'),
    'an object with its preview and a w:movie': pin_word(
        PIN_TEXT + '<w:p><w:r><w:object w:dxaOrig="1440" w:dyaOrig="720">' + PIN_SHAPETYPE + PIN_SHAPE
        + '<w:movie r:id="rIdOle"/></w:object></w:r></w:p>', PIN_OBJECT_RELS, PIN_OBJECT_PARTS),
    'an altChunk that holds nothing': pin_word(PIN_TEXT + '<w:altChunk r:id="rIdGone"/>'),
    'a picture INCLUDEPICTURE in an IF result': pin_word(
        PIN_TEXT + '<w:p>' + pin_field(' IF 1 = 1 "a" "b" ', pin_field(
            ' INCLUDEPICTURE "x.png" ', '<w:r><w:pict>' + PIN_SHAPETYPE + PIN_SHAPE.replace(' o:ole=""', '')
            + '</w:pict></w:r>')) + '</w:p>', (PIN_PREVIEW_REL,), (PIN_PREVIEW_PART,)),
    'a removed field in a HYPERLINK instruction, plain result': pin_word(
        PIN_TEXT + '<w:p>' + pin_fc('begin') + pin_instr(' HYPERLINK "') + pin_field(PIN_INC, pin_t('INC'))
        + pin_instr('" ') + pin_fc('separate') + pin_t('LINK TEXT') + pin_fc('end') + '</w:p>'),
    'a removed field in a QUOTE instruction, plain result': pin_word(
        PIN_TEXT + '<w:p>' + pin_fc('begin') + pin_instr(' QUOTE "') + pin_field(PIN_INC, pin_t('INC'))
        + pin_instr('" ') + pin_fc('separate') + pin_t('QUOTED TEXT') + pin_fc('end') + '</w:p>'),
}


def pin_requests(ws, user, data):
    """One upload of ``data`` coded through the shipped job path: (the package's sha256 as the converter saw it, the
    round's state, every request as (role, request.sha256, sha256 of the exact parameters, attempts))."""
    real = fable_document.convert_docx
    enc = f.encounter(ws, user, service_date='2026-11-02', insurance='medicare', title='Word request case')
    revision = f.upload(enc, user, data=data, filename='n.docx',
                        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    jobs.start_round(enc, revision, models.CodingRound.UPLOAD, user)
    fake = f.FakeCoder(reader=f.succeeded(r.reader_message(r.READER)),
                       checker=f.succeeded(r.checker_message(r.CHECKER)))
    with mock.patch.object(fable_client, 'coder', return_value=fake), \
            mock.patch.object(fable_document, 'convert_docx',
                              side_effect=lambda d, **kw: real(d, runner=laned_pin_pdf, **kw)):
        jobs.run_job(jobs.claim_next())
    round_ = models.CodingRound.objects.get(encounter=enc)
    view = storage.stored_path(round_.view_pdf_storage_name).read_bytes() if round_.view_pdf_storage_name else b''
    package = view.split(b'% package ')[1][:64].decode() if b'% package ' in view else None
    return package, round_.state, tuple(
        (role, request.sha256, hashlib.sha256(fable_client.canonical(request.params)).hexdigest(), request.attempts)
        for role, request in fake.calls)

# Measured on release 1's tree - an export of 9ee0c85be (docx_package.py blob c4aa942e) - with exactly these builders,
# CONVERTER_SOCKET='' and laned_pin_pdf: per shape, the upload's sha256, the package's sha256 as the converter saw it,
# and each request (role, request.sha256, sha256 of the exact parameters, attempts). A failure here is the alarm, never
# a value to re-pin: what the coder is sent for a clean Word file may change only through the coding-path gate (D358).
RELEASE_1_WORD_REQUESTS = {
    'plain, a PAGE field': (
        'd84af93d617847be4ce5cadb6bf4928f2b8b978baa18e0d48190135d5d108502',
        'd84af93d617847be4ce5cadb6bf4928f2b8b978baa18e0d48190135d5d108502',
        (
            ('reader', 'f709a11872af1092c3d2bdd05d1812f668704a13a6ee1122fbbf908686974073',
             '68c703d43e7a01ac70ad99d4e7c3891ec9dfada9886572f6c440cb360c5a44a4', 2),
            ('checker', '7984eb2c9f1346ae50469c590f219d941814a2cef0d0fc12cf8658ffde00226b',
             '28166ac5c600bf9a554dba95b0baf4247e7e0916cdb47c6f8059384219a7fe82', 2),
        )),
    'an object with its preview': (
        'd0c7171d5eae0ef9364030f85829773e45067a5e069e317283e4d8f86f03c4a7',
        '165642bd7b0c837f97ab65a3054c5b9070219f05d70f444d844978c5c4b3f3ff',
        (
            ('reader', 'd9cabd6201c9bb8f620658a00d45d856ae3c8b8da35a1030cf9feedcaa600479',
             '137755718dd66ca5219de868e4674e7851a8fdb886c6b0de6407ccb3884dfc6b', 2),
            ('checker', '0b2f18d2a4242fdb45897101a6f2439e504bd7fb76128dd0710c6ea57003c4ec',
             'cd8fc196d4e5964cec53fc421e60a4fbffd222384c8303a97a0c496b98eea1df', 2),
        )),
    'a removed field with its result': (
        '25137a7f789df0ea6af37ad33cf9ad683c7ddb2d0ba877a7877af70db96bbf43',
        '613e01ffb636b81b7f1edebdcac6c60e453a097cc04dce75e064bf8c6a70c02f',
        (
            ('reader', '01a7ca13a7979444e54998b1d877f37f3053d3b65b21c3b0f3630ca42114e8fc',
             'e109717c963e7109ea5b6e3391b73086cd1ca65b005c2c8bf56e6c05e6ed5aee', 2),
            ('checker', '4253486b77447dbdc28aee03c989ff4593c312690c8b5d952cb341b3e8e8fc49',
             'c3d8c454ab6e2dca8ed087c8e84c106af89094d36f3e53bacf7d54acdb069a71', 2),
        )),
    'an empty w:object': (
        '27c59b326f1103b050508b562fb006702079a2e84034999aed9066dec7dbfccf',
        '32f07c4f214665ec879f1599d33b017f0f5d04d5e5b36b4b818e58194ac0ccf4',
        (
            ('reader', '01dc7df561b2ff2b7b000d61b2ca6597a2bd51ae27a486020106815abd381929',
             'd3e960badb04ed07e3bf21fe5d32778433db789a47360b9f53c35242147a8543', 2),
            ('checker', '9881a03fa672d5edd661739b254454caff698866072a3ef6161da9880b54e493',
             '9cca02dd8a243dc8e366e4eb62b6e25c5f3a97a9df4e1602593b06e36f381229', 2),
        )),
    'an empty removed w:fldSimple in an IF result': (
        '368e6cc9070892c286fed7ada17add47b9fab127dd6f70274a9e3763946e63d6',
        '68220ffe7297ccf93d6c9ba824378283a724739585361e0c87eeb049dfadc708',
        (
            ('reader', 'e9b37c3c1d90b981899903698a2da031389689bbe7c0f970ee415f6dee044c47',
             '32d3060fa79f0d2150e6bf852085a51f91dc2305f074ad61ec89dfcfd2c0e84d', 2),
            ('checker', '674ab65d12ab01a11799ee5f481e050652d65b1b01979ba1f20e07cc20a43dbb',
             '7efcc22bc6ac127d3d17b0a977935cca6011731c6f34f973bfa42c78f5d82265', 2),
        )),
    'an object with its preview and a w:movie': (
        'c5d359bd2527e317f13c58ea5708178fa1663108d99539c882fa56281f09b652',
        '165642bd7b0c837f97ab65a3054c5b9070219f05d70f444d844978c5c4b3f3ff',
        (
            ('reader', '08937266afd8a758c016bda66236375b308cf1533e8d1b3b67a460c7498b1cb0',
             '137755718dd66ca5219de868e4674e7851a8fdb886c6b0de6407ccb3884dfc6b', 2),
            ('checker', 'ab540ec6cd2b3ab7caefe0a9d4585b152278e8056835ecfa103c68ce19a8d387',
             'cd8fc196d4e5964cec53fc421e60a4fbffd222384c8303a97a0c496b98eea1df', 2),
        )),
    'an altChunk that holds nothing': (
        'c7d8cb0ca87e9c1da7eabb414aecfa3c6eb7d6cae5ddd308add238223fdf8fcf',
        '1a7ca20d8f460e0ee40bf098c84ff0cd3d2ff05c240795a829ebc57b11ec4793',
        (
            ('reader', '0761e4bd54a7dbe0fb97ed821a89fead977537a28a3d69f9657e1d91892ff207',
             'c165680749a6f130302dab82d0e6e6e3fed7f8bd8e2c9d9ee7c7bdfcf374929d', 2),
            ('checker', '3679ae9d6361cf6f1b5139a75da91a09e28fd2ade3553fc0b4dd46109792ebec',
             '7c8c38865ffd06dc1f2fc4ce41cd2330c3f84c73fd938bb0279fd9692bcf5c1a', 2),
        )),
    'a picture INCLUDEPICTURE in an IF result': (
        '59beff8ba0f3272b659e9688770c88d8c337172f06190eaf44336066b66c4828',
        'aa4c439652576e60b6c37dd38af74dbbc0948309a297d9e7b01b9ef0a4d53ab9',
        (
            ('reader', '0886fe679f3f8cc5902af5ced4514dda6063e46b5e8f147c29b887a7c25f78ed',
             'b9882167d1e57c2ee227660f35c779b9e46659b2d5671d2e50d564c9d8df73e0', 2),
            ('checker', '1a6d4a08379419c85e679f3fa4faeaaf1d2c718f8ccbd978b6936fae64319773',
             'a8dc9902c92aa69a205bbe6a4647a2188d8daff206d06d0fd546f4d1f48d57cf', 2),
        )),
    'a removed field in a HYPERLINK instruction, plain result': (
        'd80e298b0d73c8fae0a16ef126d550dcdf14f6a3357d9d03e31ed1e20694a2a4',
        '45e0d8196c736dd3578f47a6af006a48187422b233df4581753337ba9f7f9b15',
        (
            ('reader', 'e3e69de51ff0379f2e93d8d0c2e8364a0488292cd4e4af2c6ec0ee8f3fcce005',
             '8754b7f48f07ab0f31eedfa404bbf469f79aeb89aa194529bcb4e962cae342d9', 2),
            ('checker', '93c2679d01ae5ef8301516c095e950fd85fc28603bc385ee32342de19304fa64',
             'e19e673bc57c94c89af657c7983985a4f3a2d867c3865804995ace17f695aae7', 2),
        )),
    'a removed field in a QUOTE instruction, plain result': (
        'a5189f553064ec1ce8cc24d07f4f3d4a0748fc690d6bc87a1b3f25d41510d97c',
        '2f271ef6ad028d35fbdbea5360f75823a26269610f2e9ed7b35cd474429663a9',
        (
            ('reader', '0399dda60d6e4edc624f239e0c078feea9ee71acbce4200d52d8d3a345b6662f',
             '94111e17890d7e49c57772a43e2cd3aa31122e5f83ed0e59a4bacfa3630721b8', 2),
            ('checker', 'dead2940e10127cee732bc249eaa398036b74bb8e5177b8f1e186c57a6924524',
             '4039eae8168d430c0e4fb8fae517fc1621aa601dc1e65d72d0840e1bbaf75c0d', 2),
        )),
}


class CleanWordRequestTests(TestCase):
    """Refutation round 1, refuse[0] (the Word case of R2-3, D358): a Word file that needs no refusal and no QUOTE is
    sent to the coder exactly as release 1 sent it - the package, every request and its parameters - over clean shapes
    that include what release 2 reads and leaves alone: an object with its preview, an empty w:object, an import that
    holds nothing, a picture INCLUDEPICTURE in a field's result, and a removed field in an exempt outer field's
    instruction (HYPERLINK, QUOTE)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._originals = tempfile.TemporaryDirectory()
        cls._override = override_settings(ORIGINALS_DIR=Path(cls._originals.name), CONVERTER_SOCKET='',
                                          CONVERTER_REQUIRED=False)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._originals.cleanup()
        super().tearDownClass()

    def test_each_clean_word_file_is_sent_as_release_1_sent_it(self):
        self.assertEqual(sorted(PIN_SHAPES), sorted(RELEASE_1_WORD_REQUESTS))
        ws = f.workspace('Word requests')
        user = f.member(ws)
        for label, data in PIN_SHAPES.items():
            with self.subTest(label):
                docx_sha256, package_sha256, requests = RELEASE_1_WORD_REQUESTS[label]
                self.assertEqual(hashlib.sha256(data).hexdigest(), docx_sha256)  # the upload measured on release 1
                package, state, sent = pin_requests(ws, user, data)
                self.assertEqual(state, Round.DONE)
                self.assertEqual([role for role, *_ in sent], ['reader', 'checker'])
                self.assertEqual((package, sent), (package_sha256, requests))
