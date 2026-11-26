"""Release 2, Group F (lane D): the Word files release 2 refuses and the ones it codes.

- R2-29: an object or a control keeps a picture in its place, or the file is refused (ContentNotShown): the Word area's
  shape tables B01-B27, C01-C09, E01-E16 and E22, rebuilt here; a preview is a part that is sent.
- R2-30: a removed field in another field's result stays a field whose instruction is QUOTE, byte for byte; its
  fallback refuses a field kept, not HYPERLINK or TOC, whose stored result holds what a reader sees and no field while a
  removed field stood in its instruction (the 7.4 corpus's H01 shape), and nothing else; a seeded fuzz.
- Everything that needs neither a refusal nor a QUOTE gives exactly release 1's package: the reference is release 1's
  own docx_package.py, read from the repository by its git blob id (RELEASE_1_PACKAGE_BLOB, immutable); where there is
  no git (the image has no .git) those comparisons say so and are skipped, and every other check still runs.
- R2-31: a refused Word upload through the shipped job path - its sentence, its three audit rows with the code and
  counts, nothing counted or sent, retry offered and refused the same way; the two sentences against the customer
  denylist.
- R2-28 step 7 (C8): a round that would read a conversion an earlier round stored runs the package check on the stored
  original first - a stored conversion of a file the check refuses is refused at its next round (an answers round and a
  retry) with no coder and no converter call; a clean one is reused byte-identically, with no converter call; one
  R2-30's QUOTE applies to converts afresh, with one.

Synthetic bytes only, every package built here; no LibreOffice, no network, no provider."""
import hashlib
import io
import random
import re
import subprocess
import types
import zipfile
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from studio import jobs, models, storage
from studio.fable import CONVERT, docx_package
from studio.fable import document as fable_document
from tests.support import coding as f
from tests.support import rounds as r
from tests.test_fable_document import failing_runner, private_tempdir
from tests.test_request_identity import git_blob_id

Round, Run, AuditEvent = models.CodingRound, models.ProviderRun, models.AuditEvent
ROOT = Path(settings.BASE_DIR)
# release 1's studio/fable/docx_package.py (9ee0c85be, the live release 816045c72644), as git stores it
RELEASE_1_PACKAGE_BLOB = 'c4aa942edbff920de2126f848ec27045b8ba0a5a'
_RELEASE_1 = {}


def release_1_package():
    """Release 1's docx_package module, loaded from the repository's object store by its blob id (imports resolve in
    this tree's studio package, which has the same bounded runner), or None where there is no git checkout."""
    if 'module' not in _RELEASE_1:
        try:
            done = subprocess.run(['git', '-C', str(ROOT), 'cat-file', 'blob', RELEASE_1_PACKAGE_BLOB],
                                  capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            done = None
        if done is None or done.returncode or git_blob_id(done.stdout) != RELEASE_1_PACKAGE_BLOB:
            _RELEASE_1['module'] = None
        else:
            module = types.ModuleType('laned_release_1_docx_package')
            module.__package__ = 'studio.fable'
            exec(compile(done.stdout.decode('utf-8'), 'release-1 docx_package.py', 'exec'), module.__dict__)
            _RELEASE_1['module'] = module
    return _RELEASE_1['module']


class ReleaseOneCase(SimpleTestCase):
    """A test that compares with release 1's package: skipped, with its reason, where there is no git checkout."""

    def release_1(self):
        module = release_1_package()
        if module is None:
            self.skipTest('no git checkout here (the image has no .git): release 1\'s package is read from git')
        return module

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
                    if release_1_package() is not None:
                        self.assert_release_1_package(data)
                        compared += 1
                    continue
                with self.assertRaises(docx_package.ContentNotShown) as caught:
                    docx_package._safe_package(data)
                counts = {'documents': 0, 'objects': 0, 'controls': 0, 'fields': 0, expected: 1}
                self.assertEqual((caught.exception.code, caught.exception.counts),
                                 (docx_package.INSERTED_OBJECT, counts))
                if release_1_package() is not None:  # the positive control: release 1 coded it
                    self.release_1()._safe_package(data)
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
        def preview_object(target, *, mode=None, part_name='word/media/image1.emf', content=EMF, inner=None):
            parts = (DOCX_PARTS[1],) if part_name is None else ((part_name, content), DOCX_PARTS[1])
            return package(in_object(SHAPETYPE, vshape(inner=inner), ole('Word.Document.12')),
                           (rel('rIdPrev', 'image', target, mode), DOCX_RELS[1]), parts)
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
        }
        for label, data in refused.items():
            with self.subTest(f'refused: {label}'):
                with self.assertRaises(docx_package.ContentNotShown) as caught:
                    docx_package._safe_package(data)
                self.assertEqual(caught.exception.counts['objects'], 1)
        kept = {
            'a percent-encoded name that is present': preview_object('media/image%201.emf',
                                                                     part_name='word/media/image 1.emf'),
            'a name present as written': preview_object('media/image1.emf'),
            'o:relid': preview_object('media/image1.emf', inner='<v:imagedata o:relid="rIdPrev"/>'),
            'a drawing whose a:blip embeds a percent-encoded name that is present': package(
                drawn, (rel('rIdPic', 'image', 'media/image%201.emf'), DOCX_RELS[1]),
                (('word/media/image 1.emf', EMF), DOCX_PARTS[1])),
        }
        for label, data in kept.items():
            with self.subTest(f'kept: {label}'):
                package_bytes, removed = docx_package._safe_package(data)
                self.assertEqual(removed['objects'], 1)
                if release_1_package() is not None:
                    self.assert_release_1_package(data)


# --- R2-30: a removed field inside another field's result stays a field ----------------------------------------------

QUOTE_BEGIN = '<w:r><w:fldChar w:fldCharType="begin"/><w:instrText xml:space="preserve"> QUOTE </w:instrText></w:r>'


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
        if release_1_package() is not None:  # the positive control: release 1 unwrapped it
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
            'a simple INCLUDEPICTURE in a simple IF': package(BEFORE + p(
                '<w:fldSimple w:instr=" IF 1 = 1 "><w:fldSimple w:instr=\' INCLUDEPICTURE "x" \'>' + t('PIC')
                + '</w:fldSimple></w:fldSimple>') + AFTER),
            'a removed field in an instruction whose outer result holds a field': package(BEFORE + p(
                fc('begin'), instr(' IF 1 = 1 "'), field(INC, 'INCLUDED'), instr('" "" '), fc('separate'),
                field(' QUOTE "x" ', 'INCLUDED'), fc('end')) + AFTER),
            'a removed field with no result in an IF result': package(BEFORE + p(
                fc('begin'), instr(' IF 1 = 1 "a" "b" '), fc('separate'), fc('begin'), instr(INC), fc('end'),
                fc('end')) + AFTER),
            'an empty simple field in an IF result': package(BEFORE + p(
                fc('begin'), instr(' IF 1 = 1 "a" "b" '), fc('separate'), '<w:fldSimple w:instr=\' INCLUDETEXT x \'/>',
                fc('end')) + AFTER),
        }
        for label, data in cases.items():
            with self.subTest(label):
                out = docx_package._safe_package(data)[0]
                self.assertEqual(shells_in(out), 0)
                self.assert_release_1_package(data)
        shelled = package(BEFORE + p(fc('begin'), instr(' IF 1 = 1 "a" "b" '), fc('separate'), longer, fc('end'))
                          + AFTER, (rel('rIdPrev', 'image', 'media/image1.emf'),), (('word/media/image1.emf', EMF),))
        self.assertEqual(shells_in(docx_package._safe_package(shelled)[0]), 1)  # the control: a longer word is not it


def nested_in_instruction(before, after, result, *, nested_result=None, nested=None):
    """A Word file whose one outer field holds a removed field (INCLUDETEXT) in its instruction - ``before`` it, the
    nested field, ``after`` it - and ``result`` as its stored result (the 7.4 corpus's H shapes)."""
    nested = nested if nested is not None else (fc('begin') + instr(INC) + fc('separate')
                                                + (nested_result or t('INCLUDED TEXT')) + fc('end'))
    return package(BEFORE + p(fc('begin'), instr(before), nested, instr(after), fc('separate'), result, fc('end'))
                   + AFTER)


def fallback_shapes():
    """(label, a Word file, the fields its refusal counts or 0 when it is coded): R2-30's fallback, set from the 7.4
    corpus - shapes 156 and 160 (H01) lose their stored result on 7.4 with or without the QUOTE, and H02-H04, I01 and
    I02, whose stored result holds a field, keep every word - and the variants the specification names (outer REF,
    DOCPROPERTY, DATE, ASK and PAGE with a plain result), which the lead's 7.4 corpus run measures."""
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
        ('outer QUOTE, plain result', nested_in_instruction(' QUOTE "', '" ', t('QUOTED')), 1),
        ('outer IF, a picture as its plain result', nested_in_instruction(
            if_before, if_after, '<w:r><w:pict>' + SHAPETYPE + vshape() + '</w:pict></w:r>'), 1),
        ('outer IF, a removed simple field in its instruction', nested_in_instruction(
            if_before, if_after, plain, nested='<w:fldSimple w:instr=\' INCLUDETEXT "SECRET" \'>' + t('INCLUDED')
                                               + '</w:fldSimple>'), 1),
        ('two outer fields, one in the other\'s instruction, each a plain result', package(BEFORE + p(
            fc('begin'), instr(' IF 1 = 1 "'), fc('begin'), instr(' QUOTE "'), field(INC, 'INCLUDED'), instr('" '),
            fc('separate'), t('QUOTED'), fc('end'), instr('" "" '), fc('separate'), t('IF RESULT'), fc('end'))
            + AFTER), 2),
        # coded: the stored result holds a field, which LibreOffice shows (the QUOTE keeps a removed one)
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
        # coded: HYPERLINK and TOC keep their stored result
        ('outer HYPERLINK, plain result', nested_in_instruction(' HYPERLINK "', '" ', t('LINK TEXT')), 0),
        ('outer TOC, plain result', nested_in_instruction(' TOC \\o "', '" ', t('Heading one')), 0),
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
    """R2-30's fallback (D-R2-36): a field kept, not HYPERLINK or TOC, with a removed field (not INCLUDEPICTURE) in its
    instruction and a stored result that holds what a reader sees and no field, is refused like R2-29, under its own
    count ('fields', the sentence of an embedded object); every other file is coded as before."""

    def test_a_removed_field_in_an_instruction_with_a_plain_stored_result_is_refused(self):
        shapes = fallback_shapes()
        self.assertEqual(sum(1 for *_, fields in shapes if fields), 11)
        for label, data, fields in shapes:
            with self.subTest(label):
                if fields:
                    with self.assertRaises(docx_package.ContentNotShown) as caught:
                        docx_package._safe_package(data)
                    self.assertEqual((caught.exception.code, caught.exception.counts),
                                     (docx_package.INSERTED_OBJECT, {'documents': 0, 'objects': 0, 'controls': 0,
                                                                     'fields': fields}))
                    if release_1_package() is not None:  # the positive control: release 1 coded it
                        self.release_1()._safe_package(data)
                    continue
                out, removed = docx_package._safe_package(data)
                self.assertNotIn('SECRET', document_part(out))
                if release_1_package() is not None and not shells_in(out):
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
            theirs = None
            if release_1 is not None:
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
                self.assertTrue(release_1 is None or theirs is None, seed)
                continue
            tally['accepted'] += 1
            part = document_part(out)
            self.assertNotIn(b'SECRET', out, seed)
            root = ElementTree.fromstring(part.encode('utf-8'))
            made_shells = shells_in(out)
            tally['shells'] += made_shells
            if made_shells == 0 and release_1 is not None:
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
        if release_1 is not None:
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
IMPORTED_COUNTS = {'documents': 1, 'objects': 0, 'controls': 0, 'fields': 0}
OBJECT_COUNTS = {'documents': 0, 'objects': 1, 'controls': 0, 'fields': 0}


class StoredCheckTests(SimpleTestCase):
    """docx_package.check_in_child and its worker side, fable_document.needs_fresh_conversion: release 2's package check
    of a stored original, in the bounded child under a conversion's limits, converting nothing."""

    def setUp(self):
        private_tempdir(self)

    def test_what_the_check_makes_of_each_kind_of_file(self):
        self.assertFalse(docx_package.check_in_child(CLEAN_WORD))  # reused
        self.assertTrue(docx_package.check_in_child(SHELLED_WORD))  # R2-30's QUOTE applies: converted afresh
        self.assertFalse(docx_package.check_in_child(NOT_A_PACKAGE))  # no Word package: no conversion came of it
        self.assertTrue(docx_package.check_in_child(UNREADABLE_PART_WORD))  # the converter decides, as for any file
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
        self.assertFalse(fable_document.needs_fresh_conversion(CLEAN_WORD))
        self.assertTrue(fable_document.needs_fresh_conversion(SHELLED_WORD))
        for failure in (docx_package.ConversionBusy('synthetic'), docx_package.ConversionFailed('synthetic')):
            with self.subTest(failure=type(failure).__name__), \
                    mock.patch.object(docx_package, 'check_in_child', side_effect=failure):
                self.assertTrue(fable_document.needs_fresh_conversion(CLEAN_WORD))  # undecided: converted afresh


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

    def test_a_stored_original_refused_once_its_parts_are_read_converts_afresh(self):
        # the converter then gives its refusal, as for any fresh conversion (here a stand-in converts it)
        enc, rev, name, digest = self.stored(UNREADABLE_PART_WORD)
        round_, convert, check = self.next_round(enc, rev, Round.ANSWERS, self.answering(), converted=FRESH_PDF)
        convert.assert_called_once_with(UNREADABLE_PART_WORD)
        self.assertEqual(round_.view_pdf_sha256, hashlib.sha256(FRESH_PDF).hexdigest())
