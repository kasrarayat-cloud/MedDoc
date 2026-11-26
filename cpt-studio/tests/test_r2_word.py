"""Release 2, Group F (lane D): the Word files release 2 refuses and the ones it codes.

- R2-29: an object or a control keeps a picture in its place, or the file is refused (ContentNotShown): the Word area's
  shape tables B01-B27, C01-C09, E01-E16 and E22, rebuilt here; a preview is a part that is sent.
- R2-30: a removed field in another field's result stays a field whose instruction is QUOTE, byte for byte; its
  fallback refuses a field kept, not HYPERLINK, TOC, QUOTE or STYLEREF, whose stored result holds something a reader
  sees outside the fields in it while a removed field stood in its instruction (the 7.4 corpus's H01 shape), and
  nothing else; a seeded fuzz.
- The Word case of R2-3's pin (refutation round 1): a clean Word file is sent to the coder exactly as release 1 sent it,
  but for the coder's effort, which R2-33 made "high" (release 1's was "max"): the pin is release 1's tree at "high".
- The canonical package gate (refutation round 3, D-R2-46): a package not in the one form a Word package takes - its
  zip, its relationships parts and targets, its content types, a preview's id - is refused before E2 reads a part, told
  as an inserted document (CanonicalPackageTests); the files measured from Word and the real tools pass it unchanged.
- Everything that needs neither a refusal nor a QUOTE gives exactly release 1's package (apart from the deviation
  CharacterReferenceTests pins): the reference is release 1's own docx_package.py, vendored as a test
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
import json
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

from studio import customer, jobs, models, storage
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

    def assert_not_canonical(self, data, form=''):
        """``data`` is refused by the canonical package gate (D-R2-46) - told as an inserted document, one count, its
        reason naming the form it breaks (``form``, when given) - fresh and before a stored conversion of it is read
        again (C8: the check decides, no converter is asked)."""
        with self.assertRaises(docx_package.PackageNotCanonical) as caught:
            docx_package._safe_package(data)
        self.assertEqual((caught.exception.code, caught.exception.counts),
                         (docx_package.INSERTED_DOCUMENT, GATE_COUNTS))
        self.assertIn(form, str(caught.exception))
        with self.assertRaises(docx_package.ConversionRefused) as checked:
            docx_package.check_in_child(data)
        self.assertEqual((checked.exception.code, checked.exception.counts), (docx_package.INSERTED_DOCUMENT,
                                                                              GATE_COUNTS))


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
# refused by the canonical package gate (D-R2-46) before E2 reads a part: told as an inserted document, one count
GATE = 'gate'
GATE_COUNTS = {'documents': 1, 'objects': 0, 'controls': 0, 'fields': 0}


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
         GATE),  # an Internal target that names no part (the gate, D-R2-46)
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
        ('E07 header relationship with TargetMode="internal"', None, None, None, GATE),  # a TargetMode Word never
        # writes, which lane D drops as External and LibreOffice reads as Internal (the gate, D-R2-46)
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
                if expected == GATE:  # not in the one form a Word package takes: refused before E2 reads a part
                    self.assert_not_canonical(data)
                    self.release_1()._safe_package(data)  # the positive control: release 1 coded it
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
        self.assertEqual(sum(expected is None for _, _, expected in packages), 18)
        self.assertEqual([label[:3] for label, _, expected in packages if expected == GATE], ['B09', 'E07'])
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
        # the canonical package gate (D-R2-46) refuses these before E2 reads a part, whatever the object holds: each
        # spells a relationship, its target or a zip name in a form Word never writes, which lane D, LibreOffice and
        # the doctor's Word could read as three parts (refutation rounds 1 to 3 found one such reading per repair)
        not_canonical = {
            'its part missing': preview_object('media/image1.emf', part_name=None),
            # loss[5] (round 1): LibreOffice opens a preview by its exact name only, Word also finds these
            'a percent-encoded name that is present': preview_object('media/image%201.emf',
                                                                     part_name='word/media/image 1.emf'),
            'a name present only without case': preview_object('media/IMAGE1.EMF'),
            'a drawing whose a:blip embeds a percent-encoded name that is present': package(
                drawn, (rel('rIdPic', 'image', 'media/image%201.emf'), DOCX_RELS[1]),
                (('word/media/image 1.emf', EMF), DOCX_PARTS[1])),
            'a drawing whose a:blip embeds ./media/image1.emf': package(
                drawn, (rel('rIdPic', 'image', './media/image1.emf'), DOCX_RELS[1]), DOCX_PARTS),
            # loss[1] (round 2): an id written twice, whatever its first row - one row per id is the one form (the
            # last four were kept before the gate, the first row LibreOffice reads naming the picture)
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
        }
        # loss[0] and refuse[0] (round 2), loss[0] (round 3): a '.' segment, a fragment, a '..' under a root or past it,
        # an empty segment - the last three were kept before the gate (LibreOffice opened them), and round 3 found the
        # rebuild dropping the part they name as an orphan
        for target in ('./media/image1.emf', 'media/./image1.emf', '/./word/media/image1.emf',
                       '/word/./media/image1.emf', '/word/../word/media/image1.emf', 'media/image1.emf#frag',
                       'media/image1.emf#', '../../word/media/image1.emf', 'media//image1.emf',
                       '//word/media/image1.emf'):
            not_canonical[f'a target written {target!r}'] = preview_object(target)
        not_canonical['a target written \'media//../image1.emf\', the part word/image1.emf'] = preview_object(
            'media//../image1.emf', part_name='word/image1.emf')
        # a '.' or '..' in a zip entry's own name is no name in the one form either
        not_canonical['a target written \'./media/image1.emf\', a zip entry word/./media/image1.emf'] = preview_object(
            './media/image1.emf', part_name='word/./media/image1.emf')
        not_canonical['a target written \'/word/../word/media/image1.emf\', a zip entry so named'] = preview_object(
            '/word/../word/media/image1.emf', part_name='word/../word/media/image1.emf')
        for label, data in not_canonical.items():
            with self.subTest(f'refused by the gate: {label}'):
                self.assert_not_canonical(data)
        # in the one form, and no picture in the object's place: R2-29 refuses them (inserted_object)
        refused = {
            'its relationship missing': package(in_object(SHAPETYPE, vshape('rIdGone'), ole('Word.Document.12')),
                                                DOCX_RELS[1:], DOCX_PARTS[1:]),
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
        }
        for label, data in refused.items():
            with self.subTest(f'refused: {label}'):
                with self.assertRaises(docx_package.ContentNotShown) as caught:
                    docx_package._safe_package(data)
                self.assertEqual((caught.exception.code, caught.exception.counts['objects']),
                                 (docx_package.INSERTED_OBJECT, 1))
        kept = {
            'a name present as written': preview_object('media/image1.emf'),
            'o:relid': preview_object('media/image1.emf', inner='<v:imagedata o:relid="rIdPrev"/>'),
            'a drawing whose a:blip embeds a name present as written': package(
                drawn, (rel('rIdPic', 'image', 'media/image1.emf'), DOCX_RELS[1]), DOCX_PARTS),
            # D-R2-40 (the lead's 7.4 run on 3ad91321e, R1-L0e): a PDF preview, as Mac Word writes it, is drawn
            'a PDF preview (R1-L0e)': preview_object('media/image1.pdf', part_name='word/media/image1.pdf',
                                                     content=SYNTHETIC_PDF_PREVIEW),
            # D-R2-45 (the lead's 7.4 run on 464b60de5): an EMZ and a WMZ, which inflate to an EMF and a WMF, are drawn
            'an EMZ preview': preview_object('media/image1.emz', part_name='word/media/image1.emz',
                                             content=gzip.compress(EMF, mtime=0)),
            'a WMZ preview': preview_object('media/image1.wmz', part_name='word/media/image1.wmz',
                                            content=gzip.compress(WMF, mtime=0)),
        }
        # the target in the one form, rooted or led by a '..' that stays inside the package
        for target in ('/word/media/image1.emf', '../word/media/image1.emf'):
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
            'inside an altChunk that holds nothing (a w:pict)': (with_embedding(
                '<w:pict>' + SHAPETYPE + empty_shape + ole('Word.Document.12', sid='_x0000_i1031')
                + '<w:altChunk>' + imagedata + '</w:altChunk></w:pict>'), OBJECTS),
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
        # since the canonical package gate (D-R2-46): a target with a '.' segment is no target in the one form - the
        # file is refused before E2 reads a part, told as an inserted document, fresh and through check_in_child
        self.assert_not_canonical(refused, 'an internal target')
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
            'an empty text part': package(BEFORE + alt + AFTER, (rel('rIdChunk', 'aFChunk', 'empty.txt'),),
                                          (('word/empty.txt', b''),)),
            'an empty part with an Override': package(BEFORE + alt + AFTER, (rel('rIdChunk', 'aFChunk', 'empty.txt'),),
                                                      (('word/empty.txt', b''),),
                                                      (override('word/empty.txt', 'text/plain'),)),
        }
        for label, data in shapes.items():
            with self.subTest(label):
                removed = docx_package._safe_package(data)[1]
                self.assertEqual(removed, {'fields': 0, 'objects': 0, 'controls': 0, 'chunks': 1})
                self.assert_release_1_package(data)
        # since the canonical package gate (D-R2-46), a relationship whose Internal target names no part - or names it
        # in a form Word never writes - is refused before E2 reads a part, whatever the import holds: Word never writes
        # one, and each of these was a repair that taught lane D one more reading (C9's 'missing part' now needs none)
        for label, target in (('a part that is missing', 'afchunk1.docx'),
                              ('a missing part named with a query', 'missing.docx?v=1'),  # round 1, loss[4]
                              ('a missing part named by a file URI', 'file:///word/missing.docx'),
                              ('a missing part named x:afchunk1.docx', 'x:afchunk1.docx'),  # round 2, loss[3]
                              ('a missing part named past the root', '../../word/missing.docx')):  # D-R2-40
            data = package(BEFORE + alt + AFTER, (rel('rIdChunk', 'aFChunk', target),))
            with self.subTest(f'refused by the gate: {label}'):
                self.assertEqual(self.release_1()._safe_package(data)[1]['chunks'], 1)  # release 1 removed it
                self.assert_not_canonical(data, 'an internal target')
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

    def test_a_picture_named_without_the_flag_is_refused_by_the_gate(self):
        # round 1 kept such a picture by its UTF-8 name, a deviation from release 1's bytes; since the canonical package
        # gate (D-R2-46) a zip name outside the one form's ASCII alphabet - flagged or not - is refused, so zipfile,
        # LibreOffice and Word read every accepted name alike and no package renames a part
        data = flagless_picture_word()
        self.assertNotIn(b'word/media/photo_\xc3\x9f.png', entry_names(self.release_1()._safe_package(data)[0]))
        self.assert_not_canonical(data, 'a zip entry')
        flagged = package(BEFORE + p('<w:r>' + drawing('rIdPic') + '</w:r>') + AFTER,
                          (rel('rIdPic', 'image', 'media/photo_\u00df.png'),),
                          (('word/media/photo_\u00df.png', PNG_BYTES),))
        self.assertEqual(entry_names(flagged).get(b'word/media/photo_\xc3\x9f.png'), True)  # stored with the flag
        self.assert_not_canonical(flagged, 'a zip entry')

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
        for label, data in (('a field naming the stored name', same), ('no field', self.picture())):
            with self.subTest(label):
                self.assertEqual(docx_package._safe_package(data)[1], {'fields': 0, 'objects': 0, 'controls': 0,
                                                                       'chunks': 0})
                self.assert_release_1_package(data)
                self.assertIs(docx_package.check_in_child(data), False)
        with self.subTest('a flagless UTF-8 name, a field naming it so'):  # coded before the canonical package gate:
            self.assert_not_canonical(flagless_same, 'a zip entry')  # a name outside the one form's alphabet


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
        # 'rId 5' - is found by the parse the guard runs for an id holding white space. Since the canonical package
        # gate (D-R2-46) a relationship id holding white space is no id in the one form, and such a file is refused
        # before E2 reads a part; the guard's white-space clause stays, a second line behind the gate (the parse
        # itself is pinned on bytes in the next test)
        removed = p(fc('begin'), instr(INC), '<w:r>' + drawing('rId 5') + '</w:r>', fc('separate'),
                    t('Kept result words.'), fc('end'))
        data = package(BEFORE + removed + p('<w:r>' + drawing('rId\t5') + '</w:r>') + AFTER,
                       (rel('rId 5', 'image', 'media/image1.png'),), (('word/media/image1.png', PNG_BYTES),))
        self.assert_not_canonical(data, 'a relationship id')
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


# --- the canonical package gate (refutation round 3, D-R2-46) -------------------------------------------------------

def with_entry(data, name, content, *, rename=None):
    """``data`` (a zip) with its entry ``name`` holding ``content`` (added last when absent; None: dropped) and, with
    ``rename``, named so instead - every other entry as it was, in its order."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = [(entry, archive.read(entry)) for entry in archive.namelist()]
    if name not in dict(entries):
        entries.append((name, content))
    return zipped([((rename or entry) if entry == name else entry, content if entry == name else old)
                   for entry, old in entries if not (entry == name and content is None)])


def with_document_rels(*rows, data=None):
    """A Word file whose document part's relationships part holds ``rows`` (as written) and nothing else."""
    return with_entry(data or package(BEFORE + AFTER), 'word/_rels/document.xml.rels', rels(*rows))


def renamed_bytes(data, placeholder, raw):
    """``data`` with the stored name ``placeholder`` (local header and central directory) replaced by the bytes ``raw``
    of the same length - a name zipfile would not write."""
    assert len(raw) == len(placeholder) and data.count(placeholder) == 2
    return data.replace(placeholder, raw)


def with_local_header(data, name, change):
    """``data`` with the 30-byte local header of its entry ``name`` passed through ``change`` (its central directory
    record left as it is): a header zipfile does not compare with the record, which a streaming reader reads."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        at = archive.getinfo(name).header_offset
    changed = change(data[at:at + 30])
    assert len(changed) == 30 and changed != data[at:at + 30]
    return data[:at] + changed + data[at + 30:]


def word_forms():
    """(label, a Word file in the forms Word and the real tools measured write): every one passes the gate unchanged.
    Measured (canon-gate/out/survey-real.jsonl) on the committed templates - 'WM IOV Template.docx', the colonoscopy
    template and the E2E fixtures - LibreOffice 24.2.7 re-saves, pandoc 3.1.3 and python-docx 1.2.0 files."""
    word = package(BEFORE + p('<w:r>' + drawing('rId8') + '</w:r>') + AFTER,
                   (rel('rId1', 'styles', 'styles.xml'), rel('rId2', 'customXml', '../customXml/item1.xml'),
                    rel('rId8', 'image', 'media/image1.jpeg'), rel('rIdHeader', 'header', 'header1.xml'),
                    rel('R4f8a2c1e9b7d3a60', 'hyperlink', 'https://example.invalid/a?b=1&amp;c=2#x y', 'External'),
                    rel('rId9', 'glossaryDocument', 'glossary/document.xml')),
                   (('word/styles.xml', f'<w:styles {NS}/>'), ('word/media/image1.jpeg', b'\xff\xd8\xff\xe0 synthetic'),
                    ('word/header1.xml', f'<w:hdr {NS}>{p(t("HEADER words"))}</w:hdr>'),
                    ('word/_rels/header1.xml.rels', rels(rel('rId1', 'image', 'media/image1.jpeg'))),
                    ('word/glossary/document.xml', f'<w:glossaryDocument {NS}/>'),
                    ('word/glossary/_rels/document.xml.rels', rels(rel('rId1', 'styles', 'styles.xml'))),
                    ('word/glossary/styles.xml', f'<w:styles {NS}/>'),
                    ('customXml/item1.xml', '<b:Sources xmlns:b="urn:x-synthetic"/>'),
                    ('customXml/itemProps1.xml', '<ds:datastoreItem xmlns:ds="urn:x-synthetic"/>'),
                    ('customXml/_rels/item1.xml.rels', rels(rel('rId1', 'customXmlProps', 'itemProps1.xml'))),
                    ('docProps/core.xml', '<cp:coreProperties xmlns:cp="urn:x-synthetic"/>'),
                    ('docProps/thumbnail.jpeg', b'\xff\xd8\xff\xe0 synthetic thumbnail')),
                   (override('word/styles.xml', 'application/xml'),))
    word = with_entry(word, '_rels/.rels', rels(
        rel('rId1', 'officeDocument', 'word/document.xml'),
        rel('rId2', 'http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties',
            'docProps/core.xml'),
        rel('rId3', 'http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail',
            'docProps/thumbnail.jpeg')))
    rooted = with_entry(word, '_rels/.rels', rels(rel('rId1', 'officeDocument', '/word/document.xml')))
    out = io.BytesIO()  # a folder's entry for each folder (as JSZip writes), and parts stored, not deflated
    with zipfile.ZipFile(io.BytesIO(word)) as source, zipfile.ZipFile(out, 'w') as rebuilt:
        for folder in ('_rels/', 'word/', 'word/_rels/'):
            rebuilt.writestr(zipfile.ZipInfo(folder, date_time=(2026, 11, 26, 0, 0, 0)), b'')
        for info in source.infolist():
            rebuilt.writestr(zipfile.ZipInfo(info.filename, date_time=info.date_time), source.read(info))
    return [('Word\'s own forms: relative, \'..\' to customXml, a glossary, named and hexadecimal ids', word),
            ('the main part named by a rooted target (System.IO.Packaging writes it)', rooted),
            ('folder entries and stored parts (a JSZip-made package)', out.getvalue()),
            ('Word\'s growth-hint field (0xA220) in a local header', with_local_extra(
                word, 'word/document.xml', struct.pack('<HHH', 0xA220, 2, 0)))]


def picture_in_object(imagedata, *, rows=None, parts=()):
    """An object (the E table's form) whose VML preview is ``imagedata``, its picture media/image1.emf (an EMF)."""
    return package(in_object(SHAPETYPE, vshape(inner=imagedata), ole('Word.Document.12')),
                   rows or DOCX_RELS, DOCX_PARTS + tuple(parts))


class CanonicalPackageTests(ReleaseOneCase):
    """The canonical package gate (refutation round 3, D-R2-46): a Word package is accepted only in the one form a Word
    package takes - every structural reference with exactly one reading, the same for lane D, LibreOffice and Word -
    and refused otherwise before E2 reads a part, whatever it holds (PackageNotCanonical: ContentNotShown, told as an
    inserted document, one count). Rounds 1 to 3 each taught lane D one more of LibreOffice's readings and each found
    the next spelling in the repair; these pin the form instead."""

    def test_a_package_in_the_forms_word_and_the_real_tools_write_passes_unchanged(self):
        for label, data in word_forms():
            with self.subTest(label):
                docx_package._safe_package(data)
                self.assert_release_1_package(data)
                self.assertIs(docx_package.check_in_child(data), False)

    def test_release_1s_own_refusals_run_first_with_their_reasons(self):
        # D-R2-46 (refute-d4, diff[0]): a package release 1 refuses keeps release 1's reason, and the general sentence,
        # when its zip is not in the one form either - a Word file zipped again inside its folder holds no inserted
        # document
        plain = package(BEFORE + p(t('SYNTHETIC')) + AFTER)

        def rebuilt(rename=lambda name: name, comment=b'', extra=()):
            out = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(plain)) as source, zipfile.ZipFile(out, 'w') as zipped:
                for info in source.infolist():
                    zipped.writestr(zipfile.ZipInfo(rename(info.filename), date_time=info.date_time), source.read(info))
                for name, data in extra:
                    zipped.writestr(zipfile.ZipInfo(name), data)
                zipped.comment = comment
            return out.getvalue()
        cases = [(rebuilt(lambda name: f'Visit note/{name}'),
                  'it is not a Word package (no content types or package relationships)'),
                 (rebuilt(extra=(('word/media/a b.png', PNG_BYTES), ('word/media/A B.png', PNG_BYTES))),
                  'a part is named twice'),
                 (rebuilt(comment=b'synthetic', extra=(('mimetype', b'application/vnd.oasis.opendocument.text'),)),
                  'it is an OpenDocument package, not a Word file')]
        for data, reason in cases:
            with self.subTest(reason):
                with self.assertRaises(docx_package.PackageRefused) as caught:
                    docx_package._safe_package(data)
                self.assertNotIsInstance(caught.exception, docx_package.ContentNotShown)
                self.assertEqual(str(caught.exception), reason)
                self.assertEqual(docx_package.check_in_child(data), docx_package.CHECK_UNDECIDED)

    def test_a_zip_archive_not_in_the_one_form_is_refused(self):
        plain = package(BEFORE + p('<w:r>' + drawing('rIdPic') + '</w:r>') + AFTER,
                        (rel('rIdPic', 'image', 'media/aXX.png'),), (('word/media/aXX.png', PNG_BYTES),))
        commented = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(plain)) as source, zipfile.ZipFile(commented, 'w') as rebuilt:
            for info in source.infolist():
                rebuilt.writestr(info, source.read(info))
            rebuilt.comment = b'synthetic comment'
        compressed = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(plain)) as source, zipfile.ZipFile(compressed, 'w') as rebuilt:
            for info in source.infolist():
                fresh = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                fresh.compress_type = zipfile.ZIP_BZIP2 if info.filename.endswith('.png') else zipfile.ZIP_DEFLATED
                rebuilt.writestr(fresh, source.read(info))
        cases = [('bytes before its first local header', b'synthetic prefix ' + plain, 'its zip archive'),
                 ('bytes after its end record', plain + b'\x00', 'its zip archive'),
                 ('an archive comment', commented.getvalue(), 'its zip archive'),
                 ('a part compressed as Word does not read it (bzip2)', compressed.getvalue(), 'compressed'),
                 ('a folder entry that holds bytes', with_entry(plain, 'word/media/', b'synthetic'), 'a folder entry')]
        for label, raw in (('a space', b'word/media/a X.png'), ('a percent sign', b'word/media/a%X.png'),
                           ('a colon', b'word/media/a:X.png'), ('a backslash', b'word/media\\aXX.png'),
                           ('a NUL', b'word/media/a\x00X.png'), ('a \'.\' segment', b'word/./media/a.png'),
                           ('an empty segment', b'word//media/aX.png'), ('a leading \'/\'', b'/ord/media/aXX.png'),
                           ('a byte outside ASCII, stored without the flag', b'word/media/a\xc3\xa9.png'),
                           ('a tilde', b'word/media/a~X.png')):
            cases.append((f'a zip name with {label}', renamed_bytes(plain, b'word/media/aXX.png', raw), 'a zip entry'))
        for label, change in (('another method', lambda head: head[:8] + b'\x0c\x00' + head[10:]),  # bzip2
                              ('other flags', lambda head: head[:6] + b'\x08\x00' + head[8:]),
                              ('another CRC', lambda head: head[:14] + bytes(4) + head[18:]),
                              ('other sizes', lambda head: head[:18] + struct.pack('<II', 1, 1) + head[26:])):
            cases.append((f'a local header with {label} than its directory record',
                          with_local_header(plain, 'word/media/aXX.png', change), 'local header'))
        cases.append(('a zip name outside ASCII, stored with the UTF-8 flag',
                      with_entry(plain, 'word/media/aXX.png', PNG_BYTES, rename='word/media/a\u00e9.png'),
                      'a zip entry'))
        for label, data, form in cases:
            with self.subTest(label):
                self.assert_not_canonical(data, form)
        self.assert_release_1_package(plain)  # the control

    def test_a_relationships_part_not_in_the_one_form_is_refused(self):
        image = rel('rIdPic', 'image', 'media/image1.png')
        body = BEFORE + p('<w:r>' + drawing('rIdPic') + '</w:r>') + AFTER
        plain = package(body, (image,), (('word/media/image1.png', PNG_BYTES),))
        opc = f'"{PKG}"'
        forms = {
            # refutation round 3, loss[3]: a row LibreOffice reads by its name as written, outside the OPC namespace
            'a row in another namespace': image.replace('<Relationship ', '<Relationship xmlns="urn:x-synthetic" '),
            'a row in no namespace': image.replace('<Relationship ', '<Relationship xmlns="" '),
            'a row with an attribute OPC does not define': image.replace('/>', ' Foo="1"/>'),
            'a row with an xml:base': image.replace('/>', ' xml:base="media/"/>'),
            'a row with no Type': '<Relationship Id="rIdPic" Target="media/image1.png"/>',
            'a row with an empty Type': image.replace(f'Type="{R}/image"', 'Type=""'),
            'a row with no Target': f'<Relationship Id="rIdPic" Type="{R}/image"/>',
            'a row with no Id': image.replace('Id="rIdPic" ', ''),
            'a row holding an element': image.replace('/>', '><Extra/></Relationship>'),
            'an id twice': image + rel('rIdPic', 'image', 'media/image1.png'),
            # a part a reader finds by its Type, twice: LibreOffice could show one footnotes part, Word the other
            'two footnotes parts': image + rel('rIdFn1', 'footnotes', 'media/image1.png')
            + rel('rIdFn2', 'footnotes', 'media/image1.png'),
            'two styles parts': image + rel('rIdSt1', 'styles', 'media/image1.png')
            + rel('rIdSt2', 'styles', 'media/image1.png'),
            'an id with a space': image.replace('rIdPic', 'rId Pic'),
            'an id led by a digit': image.replace('rIdPic', '1rIdPic'),
            'a TargetMode in another case': image.replace('/>', ' TargetMode="internal"/>'),
            'an empty TargetMode': image.replace('/>', ' TargetMode=""/>'),
            'a TargetMode of another word': image.replace('/>', ' TargetMode="Package"/>'),
        }
        cases = [(label, with_document_rels(row, data=plain), 'relationship') for label, row in forms.items()]
        root = rels(image)
        for label, written in (
                ('a prefixed root in the OPC namespace', root.replace(f'<Relationships xmlns={opc}>',
                                                                      f'<p:Relationships xmlns:p={opc}>')
                 .replace('<Relationship ', '<p:Relationship ').replace('</Relationships>', '</p:Relationships>')),
                ('a root declaring another prefix', root.replace(f'xmlns={opc}', f'xmlns={opc} xmlns:x="urn:x"')),
                ('a root with an xml:base', root.replace(f'xmlns={opc}', f'xmlns={opc} xml:base="/word/"'))):
            cases.append((label, with_entry(plain, 'word/_rels/document.xml.rels', written), 'relationships part'))
        for label, name in (('named in another case', 'word/_rels/Document.xml.rels'),
                            ('its folder in another case', 'word/_RELS/document.xml.rels'),
                            ('its suffix in another case', 'word/_rels/document.xml.RELS')):
            cases.append((f'a relationships part {label}',
                          with_entry(plain, 'word/_rels/document.xml.rels', rels(image), rename=name),
                          'not named for a part'))
        cases.append(('a relationships part for a relationships part',
                      with_entry(plain, 'word/_rels/_rels/document.xml.rels.rels', rels(image)),
                      'describes a part that has none'))
        cases.append(('a relationships part for the content types (no zip name in the one form)',
                      with_entry(plain, '_rels/[Content_Types].xml.rels', rels()), 'a zip entry'))
        cases.append(('a relationships part for a part the package does not hold',
                      with_entry(plain, 'word/_rels/gone.xml.rels', rels()), 'not named for a part'))
        cases.append(('a part in a relationships folder that is no relationships part',
                      with_entry(plain, 'word/_rels/notes.xml', b'<notes/>'), 'not named for a part'))
        for label, data, form in cases:
            with self.subTest(label):
                self.assert_not_canonical(data, form)
        self.assert_release_1_package(plain)  # the control
        two_headers = with_document_rels(image, rel('rIdH1', 'header', 'media/image1.png'),
                                         rel('rIdH2', 'header', 'media/image1.png'), data=plain)
        self.assert_release_1_package(two_headers)  # a Type a part may have many of (as 'WM IOV Template.docx' has)

    def test_an_internal_target_not_in_the_one_form_is_refused(self):
        parts = (('word/media/image1.png', PNG_BYTES), ('word/a/afchunk1.docx', inner_docx('CHUNKTOKEN')),
                 ('a/afchunk1.docx', inner_docx('CHUNKTOKEN')))
        plain = package(BEFORE + AFTER, (rel('rIdX', 'image', 'media/image1.png'),), parts)
        targets = [
            # refutation round 3, loss[2]: a scheme, an authority or white space before a '..', read by RFC 3986
            '//host/a//../afchunk1.docx', '//host/word/a//../afchunk1.docx', 'x:/a//../afchunk1.docx',
            'file:///word/a//../afchunk1.docx', ' a/afchunk1.docx', 'a/afchunk1.docx ',
            # refutation round 3, loss[0]: names oox opens and normpath does not
            '//word/media/image1.png', '../../word/media/image1.png', 'media//../media/image1.png',
            # rounds 1 and 2: dot segments, '..' past the root or under it, escapes, queries, fragments, case, schemes
            './media/image1.png', 'media/./image1.png', 'media/../media/image1.png', '/word/../word/media/image1.png',
            '../../../a/afchunk1.docx', 'media/image1%2Epng', 'media%2Fimage1.png', 'media\\image1.png',
            'media/image1.png?v=1', 'media/image1.png#f', 'media/IMAGE1.PNG', 'MEDIA/image1.png', 'x:media/image1.png',
            'file:media/image1.png', 'https://example.invalid/media/image1.png', '', '/', 'media/', '.', '..',
            # an Internal target that names no part
            'media/missing.png', '../a/missing.docx']
        cases = [(f'{target!r}', with_document_rels(rel('rIdX', 'image', target), data=plain)) for target in targets]
        for label, data in cases:
            with self.subTest(label):
                self.assert_not_canonical(data, 'an internal target')
        for target in ('media/image1.png', '/word/media/image1.png', 'a/afchunk1.docx', '../a/afchunk1.docx',
                       '/a/afchunk1.docx'):  # the one form: coded with release 1's bytes
            with self.subTest(f'the one form: {target!r}'):
                self.assert_release_1_package(with_document_rels(rel('rIdX', 'image', target), data=plain))

    def test_every_target_in_the_one_form_is_read_alike_by_each_of_lane_ds_readings(self):
        # the gate's premise, pinned: a target in the one form names the same part for release 1's reading
        # (_part_name), LibreOffice's picture reading (_opened_name), its import reading (_uri_path_name) and RFC 3986
        # (_word_name, the doctor's Word) - so no reading of one can differ from another
        segments = ('a', 'word', 'media', 'image1.png', 'x-y_z.9', '..a', 'b..')
        read = 0
        for folder in ('', 'word', 'word/glossary', 'customXml/a'):
            depth = len(folder.split('/')) if folder else 0
            for ups in range(depth + 1):
                for length in (1, 2, 3):
                    for names in zip(*(segments[i:] + segments[:i] for i in range(length))):
                        for target in ('../' * ups + '/'.join(names), *(('/' + '/'.join(names),) if not ups else ())):
                            part = docx_package._canonical_part(folder, target)
                            self.assertIsNotNone(part, target)
                            readings = (docx_package._part_name(folder, target),
                                        docx_package._opened_name(folder, target),
                                        docx_package._uri_path_name(folder, target),
                                        docx_package._word_name(folder, target))
                            self.assertEqual(set(readings), {part}, (folder, target, readings))
                            read += 1
        self.assertGreater(read, 250)

    def test_the_content_types_not_in_the_one_form_are_refused(self):
        plain = package(BEFORE + AFTER, parts=(('word/styles.xml', f'<w:styles {NS}/>'),),
                        overrides=(override('word/styles.xml', 'application/xml'),))
        with zipfile.ZipFile(io.BytesIO(plain)) as archive:
            types = archive.read('[Content_Types].xml').decode('utf-8')
        main = override('word/document.xml', MAIN)
        ct = f'"{CT}"'
        forms = {
            'a prefixed root': types.replace(f'<Types xmlns={ct}>', f'<c:Types xmlns:c={ct}>').replace(
                '<Default ', '<c:Default ').replace('<Override ', '<c:Override ').replace('</Types>', '</c:Types>'),
            'a root declaring another prefix': types.replace(f'xmlns={ct}', f'xmlns={ct} xmlns:x="urn:x"'),
            # a second type for the main part that a reader matching names as written takes, lane D does not
            'an Override in another namespace': types.replace('</Types>', override(
                'word/document.xml', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml')
                .replace('<Override ', '<Override xmlns="urn:x" ') + '</Types>'),
            'an Override with another attribute': types.replace(main, main.replace('/>', ' Foo="1"/>')),
            'an Override naming a part only by case': types.replace(
                override('word/styles.xml', 'application/xml'), override('word/STYLES.xml', 'application/xml')),
            'an Override not in the one form': types.replace('/word/styles.xml', '/word//styles.xml'),
            'a part overridden twice': types.replace('</Types>', main + '</Types>'),
            'a part overridden twice, without case': types.replace('</Types>', override('WORD/document.xml', MAIN)
                                                                   + '</Types>'),
            'an extension given twice': types.replace('</Types>', '<Default Extension="XML" ContentType="'
                                                      'application/xml"/></Types>'),
            'an empty extension': types.replace('</Types>', '<Default Extension="" ContentType="text/plain"/></Types>'),
            'a child that is neither': types.replace('</Types>', '<Other/></Types>'),
            'a child holding an element': types.replace(main, main.replace('/>', '><Extra/></Override>')),
            # LibreOffice detects the main part's type by its Default with case, lane D without: so it has its own
            'the main part typed by its Default alone': types.replace(main, '').replace(
                'Extension="xml" ContentType="application/xml"', f'Extension="xml" ContentType="{MAIN}"'),
        }
        for label, written in forms.items():
            with self.subTest(label):
                self.assertNotEqual(written, types)
                self.assert_not_canonical(with_entry(plain, '[Content_Types].xml', written), 'content type')
        self.assert_release_1_package(plain)  # the control
        # an Override that names no part has one reading - every reader passes over it, as release 1's own package
        # leaves one when it drops a part - so it is no ambiguity, and the file is coded
        stale = with_entry(plain, '[Content_Types].xml', types.replace(
            '</Types>', override('word/activeX/activeX1.xml', 'application/vnd.ms-office.activeX+xml') + '</Types>'))
        self.assert_release_1_package(stale)

    def test_an_override_naming_a_part_through_a_dot_dot_segment_is_refused(self):
        # lane D, on the gate's G11 (round 3): an Override that names no part is passed over by every reader only when
        # its PartName is in the one form - one whose '..' stands after its first segment reaches the main part for a
        # reader that resolves it, with another type, so it is refused as the gate's rule says ('..' only leads a
        # relative target); G11's mutant coded each of these (LibreOffice 24.2.7 showed the text: laneD_g11_lo24.out)
        plain = package(BEFORE + AFTER)
        with zipfile.ZipFile(io.BytesIO(plain)) as archive:
            types = archive.read('[Content_Types].xml').decode('utf-8')
        for part in ('word/../word/document.xml', 'a/../word/document.xml', 'word/media/../../word/document.xml'):
            with self.subTest(part):
                written = types.replace('</Types>', override(part, 'text/plain') + '</Types>')
                self.assert_not_canonical(with_entry(plain, '[Content_Types].xml', written), 'content type')
        self.assert_release_1_package(plain)  # the control

    def test_a_preview_naming_more_than_one_relationship_id_is_refused(self):
        strict = 'xmlns:rs="http://purl.oclc.org/ooxml/officeDocument/relationships"'
        refused = {
            # refutation round 3, loss[1]: LibreOffice reads o:relid when present, else the first r:id; Word its own
            'r:id and o:relid, each naming a picture': picture_in_object(
                '<v:imagedata r:id="rIdPrev" o:relid="rIdOther" o:title=""/>',
                rows=DOCX_RELS + (rel('rIdOther', 'image', 'media/image1.emf'),)),
            'o:relid first': picture_in_object('<v:imagedata o:relid="rIdPrev" r:id="rIdPrev"/>'),
            'r:id and the strict r:id': picture_in_object(f'<v:imagedata {strict} r:id="rIdPrev" rs:id="rIdPrev"/>'),
            'r:id and r:pict': picture_in_object('<v:imagedata r:id="rIdPrev" r:pict="rIdPrev"/>'),
            'a:blip with r:embed and the strict r:embed': package(
                in_object(drawing(attribute=f'{strict} rs:embed="rIdPic" r:embed'),
                          '<w:objectEmbed r:id="rIdOle" w:progId="Word.Document.12"/>', attributes=''),
                (rel('rIdPic', 'image', 'media/image1.emf'), DOCX_RELS[1]), DOCX_PARTS),
            'in a w:pict holding a control': package(
                BEFORE + p('<w:r><w:pict>' + SHAPETYPE + vshape(inner='<v:imagedata r:id="rIdPrev" o:relid="rIdPrev"/>',
                                                                sid='_x0000_i1026')
                           + '<w:control r:id="rIdCtl" w:name="CheckBox1" w:shapeid="_x0000_i1026"/></w:pict></w:r>')
                + AFTER, (DOCX_RELS[0], rel('rIdCtl', 'control', 'activeX/activeX1.xml')),
                (DOCX_PARTS[0], ('word/activeX/activeX1.xml', '<ax:ocx xmlns:ax="urn:x-synthetic"/>'))),
        }
        for label, data in refused.items():
            with self.subTest(f'refused: {label}'):
                self.assert_not_canonical(data, 'more than one relationship id')
        kept = {
            'r:id alone': picture_in_object('<v:imagedata r:id="rIdPrev" o:title=""/>'),
            'o:relid alone': picture_in_object('<v:imagedata o:relid="rIdPrev" o:title=""/>'),
            'the strict r:id alone': picture_in_object(f'<v:imagedata {strict} rs:id="rIdPrev"/>'),
            'r:id beside r:href (a hyperlink, no picture id)': picture_in_object(
                '<v:imagedata r:id="rIdPrev" r:href="rIdHref"/>',
                rows=DOCX_RELS + (rel('rIdHref', 'hyperlink', 'https://example.invalid/', 'External'),)),
            'a:blip with r:embed and r:link (one picture id)': package(
                in_object(drawing(attribute='r:link="rIdLink" r:embed'),
                          '<w:objectEmbed r:id="rIdOle" w:progId="Word.Document.12"/>', attributes=''),
                (rel('rIdPic', 'image', 'media/image1.emf'), rel('rIdLink', 'image', 'file:///synthetic/x.emf',
                                                                 'External'), DOCX_RELS[1]), DOCX_PARTS),
        }
        for label, data in kept.items():
            with self.subTest(f'kept: {label}'):
                self.assertEqual(docx_package._safe_package(data)[1]['objects'], 1)
                self.assert_release_1_package(data)

    def test_a_document_swap_through_the_package_relationships_is_refused(self):
        # refutation round 3, loss[5]: LibreOffice opens the first officeDocument row it reads by its name as written,
        # lane D (and Word) the one row of the OPC namespace - one part checked, another converted
        with zipfile.ZipFile(io.BytesIO(self.release_1()._safe_package(DOCUMENT_SWAP_WORD)[0])) as archive:
            self.assertIn(b'SWAPTOKEN', archive.read('word/document.xml'))  # release 1 checked the real note
        with zipfile.ZipFile(io.BytesIO(DOCUMENT_SWAP_WORD)) as archive:
            types = archive.read('[Content_Types].xml').decode('utf-8')
        untyped = types.replace(override('word/decoy.xml', MAIN), '')
        self.assertNotEqual(untyped, types)
        foreign = f'<Relationship xmlns="urn:x-synthetic-other" Id="rIdX" Type="{R}/officeDocument" ' \
                  'Target="word/decoy.xml"/>'
        for label, data in (('a row in another namespace first', DOCUMENT_SWAP_WORD),
                            ('a row in no namespace first', with_entry(DOCUMENT_SWAP_WORD, '_rels/.rels', rels(
                                foreign.replace('urn:x-synthetic-other', ''),
                                rel('rId1', 'officeDocument', 'word/document.xml')))),
                            ('the decoy typed as no Word document (its Override gone)',
                             with_entry(DOCUMENT_SWAP_WORD, '[Content_Types].xml', untyped)),
                            ('a row in another namespace after the real one', with_entry(
                                DOCUMENT_SWAP_WORD, '_rels/.rels', rels(
                                    rel('rId1', 'officeDocument', 'word/document.xml'), foreign)))):
            with self.subTest(label):
                self.assert_not_canonical(data, 'relationship')

    def test_the_five_round_3_readings_are_refused_and_their_one_form_coded(self):
        # refutation round 3's class, each finding's input in the verifier's form: lane D read the package otherwise
        # than LibreOffice, and coded it with content silently missing; the gate refuses each, before any reading
        external_sibling = rel('rIdExt', 'image', 'media/image1.emf', 'External')
        import_body = BEFORE + '<w:altChunk r:id="rIdChunk"/>' + AFTER
        chunk = inner_docx('CHUNKTOKEN imported words')
        refused = {
            'loss[0]: a preview //word/... beside an External row naming its part': picture_in_object(
                '<v:imagedata r:id="rIdPrev" o:title=""/>', rows=(rel('rIdPrev', 'image', '//word/media/image1.emf'),
                                                               external_sibling, DOCX_RELS[1])),
            'loss[0]: a preview ../../word/... beside it': picture_in_object(
                '<v:imagedata r:id="rIdPrev" o:title=""/>',
                rows=(rel('rIdPrev', 'image', '../../word/media/image1.emf'), external_sibling, DOCX_RELS[1])),
            'loss[0]: a preview media//../... beside it': picture_in_object(
                '<v:imagedata r:id="rIdPrev" o:title=""/>', rows=(rel('rIdPrev', 'image', 'media//../image1.emf'),
                                                               external_sibling, DOCX_RELS[1])),
            'loss[1]: r:id the picture, o:relid a part that is missing': picture_in_object(
                '<v:imagedata r:id="rIdPrev" o:relid="rIdMiss" o:title=""/>',
                rows=DOCX_RELS + (rel('rIdMiss', 'image', 'media/missing.emf'),)),
            'loss[2]: //host/a//../afchunk1.docx, the part a/afchunk1.docx': package(
                import_body, (rel('rIdChunk', 'aFChunk', '//host/a//../afchunk1.docx'),),
                (('a/afchunk1.docx', chunk),)),
            'loss[2]: file:///word/a//../afchunk1.docx': package(
                import_body, (rel('rIdChunk', 'aFChunk', 'file:///word/a//../afchunk1.docx'),),
                (('word/a/afchunk1.docx', chunk),)),
            'loss[3]: the import\'s row in another namespace': with_document_rels(
                rel('rIdChunk', 'aFChunk', 'afchunk1.docx').replace('<Relationship ',
                                                                    '<Relationship xmlns="urn:x-other" '),
                data=package(import_body, (rel('rIdChunk', 'aFChunk', 'afchunk1.docx'),),
                             (('word/afchunk1.docx', chunk),))),
            'loss[5]: the document swap': DOCUMENT_SWAP_WORD,
        }
        for label, data in refused.items():
            with self.subTest(f'refused: {label}'):
                self.release_1()._safe_package(data)  # the bad shape: release 1 coded it
                self.assert_not_canonical(data)
        # the one form of each: a preview named media/image1.emf (beside the External row) is kept with release 1's
        # bytes; an import named afchunk1.docx is refused for what it holds (R2-28), not by the gate
        coded = picture_in_object('<v:imagedata r:id="rIdPrev" o:title=""/>',
                                  rows=(DOCX_RELS[0], external_sibling, DOCX_RELS[1]))
        self.assertEqual(docx_package._safe_package(coded)[1]['objects'], 1)
        self.assert_release_1_package(coded)
        with self.assertRaises(docx_package.ContentNotShown) as caught:
            docx_package._safe_package(package(import_body, (rel('rIdChunk', 'aFChunk', 'afchunk1.docx'),),
                                               (('word/afchunk1.docx', chunk),)))
        self.assertNotIsInstance(caught.exception, docx_package.PackageNotCanonical)
        self.assertEqual(str(caught.exception), docx_package.CONTENT_NOT_SHOWN)


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
# refutation round 3, loss[5]: a document swap through the package relationships - LibreOffice opens the first
# officeDocument row it reads by its name as written (one outside the OPC namespace), lane D the OPC row; release 1
# codes it, release 2's canonical package gate refuses it (D-R2-46)
DOCUMENT_SWAP_WORD = with_entry(
    package(p(t('SWAPTOKEN the real note')),
            parts=(('word/decoy.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                                      f'<w:document {NS}><w:body>{p(t("DECOYTOKEN other words"))}</w:body>'
                                      '</w:document>'),),
            overrides=(override('word/decoy.xml', MAIN),)),
    '_rels/.rels', rels(f'<Relationship xmlns="urn:x-synthetic-other" Id="rIdX" Type="{R}/officeDocument" '
                        'Target="word/decoy.xml"/>', rel('rId1', 'officeDocument', 'word/document.xml')))


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
        # (a picture named without the UTF-8 flag converted afresh too, until the canonical package gate refused it:
        # ZipNameTests)
        for label, data in (('a picture id by a decimal reference', character_reference_word('&#114;IdPic')),
                            ('a picture id by a hexadecimal reference', character_reference_word('&#x72;IdPic')),
                            ('an object preview\'s id by a decimal reference',
                             character_reference_word('&#114;IdPic', in_object=True))):
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

    def test_a_word_upload_the_canonical_package_gate_refuses_is_refused_with_its_sentence_and_record(self):
        # D-R2-46: told as an inserted document (D-R2-43's swap is), one count - the package - and the same record
        self.assert_refused(DOCUMENT_SWAP_WORD, docx_package.INSERTED_DOCUMENT, GATE_COUNTS)

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
                                   (BARE_OBJECT_WORD, docx_package.INSERTED_OBJECT, OBJECT_COUNTS),
                                   # the canonical package gate (D-R2-46): release 1 coded and stored it, renaming the
                                   # picture; release 2 refuses it at its next round, as a fresh conversion
                                   (flagless_picture_word(), docx_package.INSERTED_DOCUMENT, GATE_COUNTS),
                                   (DOCUMENT_SWAP_WORD, docx_package.INSERTED_DOCUMENT, GATE_COUNTS)):
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
        # (R1-L2b's flagless name is refused by the canonical package gate since D-R2-46: the test above)
        for label, data in (('a picture id by a decimal reference', character_reference_word('&#114;IdPic')),):
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

    # --- integrated refutation round 1, I1-1 (bypass-0, failclosed-0): release 1's stored conversion of a file a later
    # round refuses is never shown or downloaded to the doctor again - the page reads as for a file refused at its first
    # round - while the record keeps it: the bundle's converted/ file and the operator's console

    def doctors_page(self, member, enc, tag):
        """What the doctor's page is given of ``enc``: the detail's document block, the view with and without the kept
        ``tag``, the default download and the Word file by name - and the member.inline rows those reads added."""
        base = f'/api/encounters/{enc.pk}'
        inline = models.AccessRecord.objects.filter(view='member.inline').count()
        document = member.get(base).json()['document']
        kept = member.get(f'{base}/original?view=1', HTTP_IF_NONE_MATCH=tag)
        fresh = member.get(f'{base}/original?view=1')
        download = member.get(f'{base}/original')
        word = member.get(f'{base}/original?format=original')
        added = models.AccessRecord.objects.filter(view='member.inline').count() - inline
        return document, kept, fresh, download, word, added

    def assert_refused_as_at_first_round(self, member, enc, data, tag, when):
        document, kept, fresh, download, word, added = self.doctors_page(member, enc, tag)
        self.assertEqual((document['view_url'], document['view_media_type'], document['converted'], document['view_round']),
                         (None, None, False, None), when)
        self.assertEqual((kept.status_code, fresh.status_code), (404, 404), f'{when}: no view, a kept tag included')
        self.assertNotIn(b'%PDF', kept.content + fresh.content, when)
        self.assertEqual(added, 0, f'{when}: nothing shown, from page memory or afresh')
        self.assertEqual((download.status_code, download['Content-Type']), (409, 'application/json'),
                         f'{when}: no PDF download')
        self.assertEqual(download.json(), {'error': customer.ORIGINAL_ONLY, 'details': {
            'original_url': f'/api/encounters/{enc.pk}/original?format=original'}}, when)
        self.assertEqual((word.status_code, word.content), (200, data), f'{when}: the Word file stays downloadable')

    def test_a_file_a_later_round_refuses_is_shown_and_downloaded_as_one_refused_at_its_first_round(self):
        from tests.support import operator as ops
        from tests.test_frontend import PLAIN_STATIC
        from tests.test_operator_console import open_content
        from tests.test_read_audit import member_client

        for index, (data, code) in enumerate(((IMPORTING_WORD, docx_package.INSERTED_DOCUMENT),
                                               (BARE_OBJECT_WORD, docx_package.INSERTED_OBJECT),
                                               (DOCUMENT_SWAP_WORD, docx_package.INSERTED_DOCUMENT))):
            with self.subTest(index=index, code=code):
                enc, rev, _, digest = self.stored(data)
                member = member_client(self.reviewer)
                base = f'/api/encounters/{enc.pk}'
                # before: round 1's conversion is the view, and the page keeps it under its tag
                first = member.get(f'{base}/original?view=1')
                self.assertEqual((first.status_code, first.content), (200, STORED_PDF))
                tag = first['ETag']
                self.assertEqual(member.get(f'{base}/original?view=1', HTTP_IF_NONE_MATCH=tag).status_code, 304)
                self.assertEqual(member.get(base).json()['document']['converted'], True)
                round_, _, _ = self.next_round(enc, rev, Round.ANSWERS, f.FakeCoder())
                self.assertEqual((round_.state, round_.failure_kind, round_.error),
                                 (Round.FAILED, CONVERT, fable_document.REFUSED_PACKAGE_TEXT[code]))
                self.assert_refused_as_at_first_round(member, enc, data, tag, 'refused')
                # a retry, queued and not yet run, shows no view either: the refusal stands until a round stores its own
                jobs.retry(enc, self.reviewer)
                self.assertEqual(jobs.latest_round(enc).state, Round.QUEUED)
                self.assert_refused_as_at_first_round(member, enc, data, tag, 'retry queued')
                self.use(f.FakeCoder())
                with mock.patch.object(fable_document, 'convert_docx', side_effect=AssertionError('no conversion')):
                    self.run_next()
                self.assertEqual(jobs.latest_round(enc).failure_kind, CONVERT)
                self.assert_refused_as_at_first_round(member, enc, data, tag, 'retry refused')
                # the record keeps what round 1 read: the bundle's converted/ file (its record.json is the page as shown)
                bundle = member.get(f'{base}/bundle')
                self.assertEqual(bundle.status_code, 200)
                with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
                    self.assertEqual(archive.read('converted/synthetic-note.pdf'), STORED_PDF)
                    self.assertEqual(archive.read('original/synthetic-note.docx'), data)
                    shown = json.loads(archive.read('record.json'))['document']['document']
                self.assertEqual((shown['view_url'], shown['converted']), (None, False))
                # and the operator's console: its link to the converted PDF, and that PDF as the record's download
                console = ops.admin_client(r.f.user(f'platform-operator-{index}'))
                open_content(console, enc)
                with override_settings(STORAGES=PLAIN_STATIC):  # R2-26: the console names its fonts by the static tag
                    page = console.get(f'/ops/encounters/{enc.pk}').content.decode()
                self.assertIn('The converted PDF the coding review read', page)
                answer = console.get(f'/ops/encounters/{enc.pk}/original')
                self.assertEqual((answer.status_code, answer.content), (200, STORED_PDF))
                self.assertEqual(answer['X-Content-SHA256'], digest)
                self.assertEqual(models.AccessRecord.objects.filter(view='ops.original').latest('created_at').filters,
                                 {'format': 'converted_pdf'})

    def test_a_round_refused_beside_the_view_it_recorded_shows_none_and_a_later_round_that_stores_one_shows_it(self):
        from tests.test_read_audit import member_client

        enc, _, _, _ = self.stored(IMPORTING_WORD)
        member = member_client(self.reviewer)
        # a resumed round refused at its check fails CONVERT beside the view it recorded on its first pass
        Round.objects.filter(encounter=enc, number=1).update(state=Round.FAILED, failure_kind=CONVERT,
                                                             error=fable_document.REFUSED_PACKAGE_TEXT[
                                                                 docx_package.INSERTED_DOCUMENT])
        document = member.get(f'/api/encounters/{enc.pk}').json()['document']
        self.assertEqual((document['view_url'], document['converted']), (None, False))
        self.assertEqual(member.get(f'/api/encounters/{enc.pk}/original?view=1').status_code, 404)
        # a failure of another kind is not the file's: it masks nothing (the view stands, as in release 1)
        Round.objects.filter(encounter=enc, number=1).update(failure_kind=BUSY)
        self.assertEqual(member.get(f'/api/encounters/{enc.pk}/original?view=1').content, STORED_PDF)
        Round.objects.filter(encounter=enc, number=1).update(failure_kind=CONVERT)
        # a later round that stores a view of its own is shown again
        later = r.write_round(enc)
        name, digest, _ = storage.store_original(self.ws.pk, FRESH_PDF, 'converted.pdf')
        Round.objects.filter(pk=later.pk).update(view_pdf_storage_name=name, view_pdf_sha256=digest)
        document = member.get(f'/api/encounters/{enc.pk}').json()['document']
        self.assertEqual((document['view_url'], document['converted']),
                         (f'/api/encounters/{enc.pk}/original?view=1', True))
        self.assertEqual(member.get(f'/api/encounters/{enc.pk}/original?view=1').content, FRESH_PDF)
        self.assertEqual(member.get(f'/api/encounters/{enc.pk}/original').content, FRESH_PDF)

    # --- integrated refutation round 1, I1-12 (viewer-0): the document block names the round whose conversion the view
    # serves (view_round), so a page kept open across a later round that converts the file again redraws its viewer whole
    # and asks for the view with its kept copy's tag - answered 200 with the new bytes, or 304 for the same file

    def test_the_document_names_the_round_whose_conversion_its_view_serves(self):
        from tests.test_read_audit import member_client

        member = member_client(self.reviewer)
        # a later round converts the file again (C8, R2-30's shape): view_round moves to it, and the kept copy, asked with
        # round 1's tag, is answered 200 with the new conversion under another tag
        enc, rev, _, _ = self.stored(SHELLED_WORD)
        base = f'/api/encounters/{enc.pk}'
        first = member.get(f'{base}/original?view=1')
        self.assertEqual((first.status_code, first.content), (200, STORED_PDF))
        self.assertEqual(member.get(base).json()['document']['view_round'], 1)
        with self.assertNumQueries(2):  # its first file and shown_view, read once: no statement added
            self.assertEqual(customer.document_json(enc)['view_round'], 1)
        round_, convert, _ = self.next_round(enc, rev, Round.ANSWERS, self.answering(), converted=FRESH_PDF)
        self.assertEqual((round_.number, round_.state), (2, Round.DONE))
        convert.assert_called_once_with(SHELLED_WORD)
        document = member.get(base).json()['document']
        self.assertEqual((document['view_url'], document['converted'], document['view_round']),
                         (f'{base}/original?view=1', True, 2))
        kept = member.get(f'{base}/original?view=1', HTTP_IF_NONE_MATCH=first['ETag'])
        self.assertEqual((kept.status_code, kept.content), (200, FRESH_PDF))
        self.assertNotEqual(kept['ETag'], first['ETag'])
        # a later round that reads the same stored file again moves view_round too: the kept copy is answered 304
        clean, clean_rev, name, digest = self.stored(CLEAN_WORD)
        clean_base = f'/api/encounters/{clean.pk}'
        held = member.get(f'{clean_base}/original?view=1')
        self.assertEqual(member.get(clean_base).json()['document']['view_round'], 1)
        round_, convert, _ = self.next_round(clean, clean_rev, Round.ANSWERS, self.answering())
        convert.assert_not_called()
        self.assertEqual((round_.number, round_.view_pdf_storage_name, round_.view_pdf_sha256), (2, name, digest))
        self.assertEqual(member.get(clean_base).json()['document']['view_round'], 2)
        again = member.get(f'{clean_base}/original?view=1', HTTP_IF_NONE_MATCH=held['ETag'])
        self.assertEqual((again.status_code, again.content), (304, b''))
        # a file a later round refused names none (I1-1); a first round still converting names none until it stores one
        refused, refused_rev, _, _ = self.stored(IMPORTING_WORD)
        round_, _, _ = self.next_round(refused, refused_rev, Round.ANSWERS, f.FakeCoder())
        self.assertEqual((round_.number, round_.state, round_.failure_kind), (2, Round.FAILED, CONVERT))
        self.assertEqual((customer.document_json(refused)['view_round'], customer.document_json(refused)['converted']),
                         (None, False))
        busy = f.encounter(self.ws, self.reviewer, title='Synthetic Word note')
        f.upload(busy, self.reviewer, data=CLEAN_WORD, filename='synthetic-note.docx', media_type=DOCX)
        jobs.start_round(busy, busy.current_revision, Round.UPLOAD, self.reviewer)
        self.assertEqual(customer.document_json(busy)['view_round'], None)


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

# Measured on release 1's tree at the coder's effort "high" (R2-33, D433 and D434; release 1's setting was "max", at
# which lane D first measured them on an export of 9ee0c85be, docx_package.py blob c4aa942e): twice and independently
# (the lead's m1 and m2) on release 1's commit 816045c7 (cpt-studio tree bc0729bb9596) with
# CPT_STUDIO_CODING_EFFORT=high, with exactly these builders, CONVERTER_SOCKET='' and laned_pin_pdf: per shape, the
# upload's sha256, the package's sha256 as the converter saw it, and each request (role, request.sha256, sha256 of the
# exact parameters, attempts). The effort moved every request.sha256 and parameters sha256 and nothing else: the
# uploads, the packages and the attempts are as at "max". A failure here is the alarm, never a value to re-pin: what
# the coder is sent for a clean Word file may change only through the coding-path gate (D358).
RELEASE_1_WORD_REQUESTS = {
    'plain, a PAGE field': (
        'd84af93d617847be4ce5cadb6bf4928f2b8b978baa18e0d48190135d5d108502',
        'd84af93d617847be4ce5cadb6bf4928f2b8b978baa18e0d48190135d5d108502',
        (
            ('reader', '7b5a7edaf8cd646d09cdbb28b6cf8f9111daf830b389c9c4ba6a4c31c8d2d9f2',
             '0b4559423486b087a7c540aff307cdd66f8944ba906f25dc015ee9283f559909', 2),
            ('checker', '6ae3baa72e07529746da968a4f3f62d716948fc38d2d82a8c6e8c6bf83b10586',
             '0619e6d3b483d7c2788433e3fffb1dd6770f0aae48cf3811628eb87e2ea522fd', 2),
        )),
    'an object with its preview': (
        'd0c7171d5eae0ef9364030f85829773e45067a5e069e317283e4d8f86f03c4a7',
        '165642bd7b0c837f97ab65a3054c5b9070219f05d70f444d844978c5c4b3f3ff',
        (
            ('reader', '488fafce876c304ca85cac7212f8fd54eb61cc6a38b369c0c44fb973395ccd25',
             '7ca37765cb8e5767f47e85d920a1053636876008cae82b4d9edbbd3c6b42054c', 2),
            ('checker', '3e1df38df52353eb68c09acd84eb5cca07eef8616386935095af903ff334d797',
             '5c4ab9bb89b0575af8d1993ad3af1e889cd9f7058accef35dff167680e1be830', 2),
        )),
    'a removed field with its result': (
        '25137a7f789df0ea6af37ad33cf9ad683c7ddb2d0ba877a7877af70db96bbf43',
        '613e01ffb636b81b7f1edebdcac6c60e453a097cc04dce75e064bf8c6a70c02f',
        (
            ('reader', 'b1f085b0eb04b05b413bb15fff25b9c3a21960fd45b5c75f44702cefdfa13106',
             '5ef14ebe01cd8048c651b5b7bf285de5409e8887e7403ee72645b410fd409c49', 2),
            ('checker', '56e297d4a2faefb95411e379b613246bed922024e6fd870f34afd291cf48090c',
             '684b03e181de815129161cd49fd3f16ec4bf67cecadfca7a63c68b5a23daafeb', 2),
        )),
    'an empty w:object': (
        '27c59b326f1103b050508b562fb006702079a2e84034999aed9066dec7dbfccf',
        '32f07c4f214665ec879f1599d33b017f0f5d04d5e5b36b4b818e58194ac0ccf4',
        (
            ('reader', '7e29aa355464b975f9eb31abfcf4311fcc70b7d190baabae09b0dc9c9f4bde70',
             'eaeabfd1c897df440837752cb5973b37230517ca2f6e0667a6670a2fbf82d992', 2),
            ('checker', '416f26132dfd16e20cef34f6540c307351c16e149696499e4582cb9ff6ff83b6',
             'a3ac93f2c0be679a59f1eb5fa70ac623e66a1360bc631447e7c7cf98b64441bb', 2),
        )),
    'an empty removed w:fldSimple in an IF result': (
        '368e6cc9070892c286fed7ada17add47b9fab127dd6f70274a9e3763946e63d6',
        '68220ffe7297ccf93d6c9ba824378283a724739585361e0c87eeb049dfadc708',
        (
            ('reader', '975e8a457a006a5511f1dcc2ddbb6462a8f4423eac18206cd4213974cce13ff4',
             '3d55db8375f872e14e9ee0193f93688a048f9ff0af9e9ea3494e6470d07ee30a', 2),
            ('checker', '7ff43b9f49218c3fefaac0db91f9beaa35b841a0befbc8be02811032a52fda84',
             'af75156555ea3340a38634fe27051ce812f170da9cfa84c6c671aabf22b3ad0a', 2),
        )),
    'an object with its preview and a w:movie': (
        'c5d359bd2527e317f13c58ea5708178fa1663108d99539c882fa56281f09b652',
        '165642bd7b0c837f97ab65a3054c5b9070219f05d70f444d844978c5c4b3f3ff',
        (
            ('reader', '2512b6faa611e720eaf459184c560b88d65afec4b1059198fcfed5fde812840d',
             '7ca37765cb8e5767f47e85d920a1053636876008cae82b4d9edbbd3c6b42054c', 2),
            ('checker', '28ae07ff747f1836f261dbda52f4ee6cf259a3aebaa1e2d199528a54e1d5a82a',
             '5c4ab9bb89b0575af8d1993ad3af1e889cd9f7058accef35dff167680e1be830', 2),
        )),
    'an altChunk that holds nothing': (
        'c7d8cb0ca87e9c1da7eabb414aecfa3c6eb7d6cae5ddd308add238223fdf8fcf',
        '1a7ca20d8f460e0ee40bf098c84ff0cd3d2ff05c240795a829ebc57b11ec4793',
        (
            ('reader', '0d14990deab6669168b63b4ae055408e80e916cd24215c3737ab368b5ea499a2',
             'd117db80365d8f84c41e4e76fe5e710a138ce13e9c596573d4282a7e34e058fa', 2),
            ('checker', 'e55c09f4fd58c7fc31bff528243e3ccbe4f918ce1b0b58d0b5fd71206c9efab1',
             '38cb11876980fbd4fc7e4fb90600c0f13123dfd874c7ec7adabf5548b3cfb548', 2),
        )),
    'a picture INCLUDEPICTURE in an IF result': (
        '59beff8ba0f3272b659e9688770c88d8c337172f06190eaf44336066b66c4828',
        'aa4c439652576e60b6c37dd38af74dbbc0948309a297d9e7b01b9ef0a4d53ab9',
        (
            ('reader', '21f99259e39d9ed8196c7f115aef33e4b4be5f1cbe393964eab1e3e80fdb64ee',
             '14848fa616d0d514ca27ccca8920d45e7dc2c0227a2dfe31ce92c69f9ff6c80e', 2),
            ('checker', '8896f5738d62b60ffaba3eebea1446bfdf6f8952de27874f4ee46e92eff5eb0c',
             '0c15743e63ec22edaed89794e8605c519e01f9883189c069b5cd8eab683564e7', 2),
        )),
    'a removed field in a HYPERLINK instruction, plain result': (
        'd80e298b0d73c8fae0a16ef126d550dcdf14f6a3357d9d03e31ed1e20694a2a4',
        '45e0d8196c736dd3578f47a6af006a48187422b233df4581753337ba9f7f9b15',
        (
            ('reader', '3767c6e33b2b4ebb7123f6436ca8042fa314de29f77bf2490bdee2d22ed1c303',
             '311053fb24fc264bf26e7245d319b60ede510421f39e3ce43222ae3d4f79b9c5', 2),
            ('checker', '88435c5567d1b1a7507a2808d818a8b42b33a6f22c478a9ed59d3e549cde3dfb',
             'a1059bdcb71cb7132495bf7847f05c513fcc598410685db8c384a46159d92a46', 2),
        )),
    'a removed field in a QUOTE instruction, plain result': (
        'a5189f553064ec1ce8cc24d07f4f3d4a0748fc690d6bc87a1b3f25d41510d97c',
        '2f271ef6ad028d35fbdbea5360f75823a26269610f2e9ed7b35cd474429663a9',
        (
            ('reader', 'e6a66dfc46bd280b6e6a31bc6d3c13500182e44efb413d9868956bc762426db9',
             'cf8370a8a32c381e7df990f3b3d161074d00dab1cf112e3b3f8a9281e9d0a758', 2),
            ('checker', '55cfbec7d66db4565c6d7d218fbdccd8f4fef69c9b977a31dc023d7873b6eb48',
             'af79df7134274501b72ff13338e430a71dd745ecf9a3b5fa113e362e3583dd43', 2),
        )),
}


class CleanWordRequestTests(TestCase):
    """Refutation round 1, refuse[0] (the Word case of R2-3, D358): a Word file that needs no refusal and no QUOTE is
    sent to the coder exactly as release 1 sent it, at the coder's effort R2-33 set ('high'; release 1's was 'max') -
    the package, every request and its parameters - over clean shapes that include what release 2 reads and leaves
    alone: an object with its preview, an empty w:object, an import that holds nothing, a picture INCLUDEPICTURE in a
    field's result, and a removed field in an exempt outer field's instruction (HYPERLINK, QUOTE)."""

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
