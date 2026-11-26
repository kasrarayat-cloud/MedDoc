"""Deterministic synthetic data for the release-2 bench (RELEASE-2-SPEC R2-2). Invented text only, never a patient.

Two halves:
- the BYTES (top level, no Django): text PDFs, scans, a Word file, a text note, each PDF with a solid marker block and a
  12-bit barcode of its number on page 1. ops/test_bench.py builds them twice and requires equal bytes, so nothing here
  may draw on an unseeded source: noise comes from random.Random(seed), never from Pillow's effect_noise (whose C rand()
  is unseeded), and reportlab runs with invariant=1;
- the ROWS (functions that import Django when called): practices of bulk rows from uuid5 ids and seeded choices, and
  the documents with stored originals. They are written only into the bench's throwaway test database
  (bench_run.py refuses any other).

The barcode: 15 squares in a row in page 1's top margin - a start square (always dark), the number's 12 bits, most
significant first, an even-parity square, and a stop square (always dark). A blank or an all-dark canvas never decodes:
blank fails the start square, all dark fails the parity. bench.cjs reads it at fit width, at each square's centre, from
the geometry() this module hands it, so the two never disagree on where a square is.
"""
from __future__ import annotations

import io
import random
import statistics
import uuid
import zipfile

NS = uuid.UUID('7d1a6f7e-5b1c-4d0e-9a55-0f5a2c0c2ba2')
PAGE_W, PAGE_H = 612, 792  # US letter, PDF points, origin bottom-left
MARKER = (540, 740, 24, 24)  # x, y, width, height of the solid block bench.cjs reads to know page 1 is drawn
BITS = 12
SQUARES = BITS + 3  # start, 12 bits, parity, stop
BAR_X0, BAR_PITCH, BAR_SIZE, BAR_Y = 56, 14, 10, 772  # square i spans x0 + pitch*i .. + size, y .. y + size
WORDS = ('colonoscopy cecum reached withdrawal time minutes boston bowel preparation scale polyp sessile ascending '
         'transverse descending sigmoid rectum cold snare polypectomy retrieved biopsy forceps hemostasis clip '
         'erythema mucosa diverticulosis internal hemorrhoids retroflexion terminal ileum intubated sedation '
         'propofol monitored anesthesia care indication screening surveillance history adenoma recommendation '
         'repeat interval pathology follow-up patient tolerated procedure well no immediate complications').split()
QUOTE = 'the synthetic polyp was removed by cold snare and retrieved.'
DOCX_MEDIA = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


# --- the barcode ------------------------------------------------------------------------------------------------------

def barcode_bits(number: int) -> list[int]:
    """The 15 squares for ``number`` (1..4095): 1 = dark."""
    if not isinstance(number, int) or not 0 < number < 2 ** BITS:
        raise ValueError(f'a barcode number is 1..{2 ** BITS - 1}')
    data = [(number >> (BITS - 1 - i)) & 1 for i in range(BITS)]
    return [1, *data, sum(data) % 2, 1]


def decode_bits(bits) -> int | None:
    """The number a row of 15 read squares names, or None when the frame or the parity does not hold."""
    bits = list(bits)
    if len(bits) != SQUARES or any(b not in (0, 1) for b in bits):
        return None
    if bits[0] != 1 or bits[-1] != 1 or sum(bits[1:BITS + 1]) % 2 != bits[BITS + 1]:
        return None
    number = 0
    for b in bits[1:BITS + 1]:
        number = number * 2 + b
    return number or None


def geometry() -> dict:
    """Where bench.cjs reads, as fractions of page 1's canvas (x from the left, y from the top)."""
    mx, my, mw, mh = MARKER
    y = (PAGE_H - (BAR_Y + BAR_SIZE / 2)) / PAGE_H
    return {'marker': [(mx + mw / 2) / PAGE_W, (PAGE_H - (my + mh / 2)) / PAGE_H],
            'squares': [[(BAR_X0 + BAR_PITCH * i + BAR_SIZE / 2) / PAGE_W, y] for i in range(SQUARES)],
            'bits': BITS}


def _squares(number):
    for i, bit in enumerate(barcode_bits(number)):
        if bit:
            yield BAR_X0 + BAR_PITCH * i, BAR_Y, BAR_SIZE, BAR_SIZE


# --- the bytes --------------------------------------------------------------------------------------------------------

def sentence(rng: random.Random, n: int) -> str:
    return (' '.join(rng.choice(WORDS) for _ in range(n)) + '.').capitalize()


def text_pdf(pages: int, number: int, seed: int, *, marker: bool = True, lines: int = 34, head: tuple = (),
             span: bool = False) -> bytes:
    """A text PDF of ``pages`` pages. Page 1 carries the marker block and the barcode of ``number`` unless ``marker`` is
    False (the control document: a PDF without the marker must never count as drawn). Each page ends with the quoted
    passage the documents' citations name. The walk's documents only: ``head`` adds lines under page 1's title, and
    ``span`` splits page 1's quoted passage across the page break. Without them the bytes are the same as ever."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    rng = random.Random(seed)
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=letter, invariant=1, pageCompression=1)
    for page in range(1, pages + 1):
        c.setFillColorRGB(0, 0, 0)
        if page == 1 and marker:
            c.rect(*MARKER, stroke=0, fill=1)
            for square in _squares(number):
                c.rect(*square, stroke=0, fill=1)
        c.setFont('Helvetica-Bold', 12)
        c.drawString(56, 750, f'SYNTHETIC PROCEDURE NOTE - NOT A REAL PATIENT - page {page} of {pages}')
        c.setFont('Helvetica', 10)
        y = 728
        if page == 1:
            for extra in head:
                c.drawString(56, y, extra)
                y -= 18
        for n in range(lines - (len(head) if page == 1 else 0)):
            c.drawString(56, y, f'{n + 1:02d} ' + sentence(rng, 11)[:105])
            y -= 18
        if span and page == 1 and pages > 1:
            c.drawString(56, y, f'Quoted passage {page}: the synthetic polyp was removed by')
        elif span and page == 2:
            c.drawString(56, 60, 'cold snare and retrieved, and the passage ends on this page.')
            c.drawString(56, y, f'Quoted passage {page}: {QUOTE}')
        else:
            c.drawString(56, y, f'Quoted passage {page}: {QUOTE}')
        c.showPage()
    c.save()
    return out.getvalue()


def _paper_table() -> list[int]:
    """Uniform bytes to paper grey: N(238, 22) clamped to 150..255, as the prototype's effect_noise(22) + 110 was, but
    reproducible (a fixed table over seeded bytes)."""
    normal = statistics.NormalDist(238, 22)
    return [max(150, min(255, round(normal.inv_cdf((v + 0.5) / 256)))) for v in range(256)]


def scan_pdf(pages: int, number: int, seed: int, *, dpi: int = 150, quality: int = 62, ocr: tuple = ()) -> bytes:
    """An image-only PDF (a scan): JPEG pages of noisy paper with bars of ink, the marker block and the barcode drawn
    into page 1's pixels. The walk's scan only: ``ocr`` lines are laid on every page as invisible text (render mode 3),
    the text layer scanning software adds, over word-shaped blocks of ink in the image, so its quotes can be found and
    their marks lie on ink (walk.cjs requires 5% of a mark's pixels to be ink: thin glyphs drawn at 100 dpi did not
    reach it in the viewer); without ``ocr`` the bytes are the same as ever."""
    from PIL import Image, ImageDraw
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    rng = random.Random(seed)
    table = _paper_table()
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=letter, invariant=1)
    w, h = int(8.5 * dpi), int(11 * dpi)

    def box(x, y, bw, bh):  # PDF points (origin bottom-left) to pixel corners
        return [round(w * x / PAGE_W), round(h * (PAGE_H - y - bh) / PAGE_H),
                round(w * (x + bw) / PAGE_W), round(h * (PAGE_H - y) / PAGE_H)]

    for page in range(1, pages + 1):
        img = Image.frombytes('L', (w, h), rng.randbytes(w * h)).point(table)
        d = ImageDraw.Draw(img)
        for n in range(40):
            y = int(h * (0.06 + n * 0.022))
            x = int(w * 0.09)
            while x < w * 0.88:
                ww = rng.randrange(int(w * 0.02), int(w * 0.09))
                d.rectangle([x, y, x + ww, y + int(h * 0.009)], fill=60)
                x += ww + int(w * 0.012)
        if page == 1:
            d.rectangle(box(*MARKER), fill=0)
            for square in _squares(number):
                d.rectangle(box(*square), fill=0)
        if ocr:  # ink under the text layer: a word-shaped block where the layer puts each word (Helvetica 10 pt)
            from reportlab.pdfbase.pdfmetrics import stringWidth
            for i, line in enumerate(ocr):
                y_pt, x_pt = 700 - 12 * i, 56.0
                for word in line.replace('{page}', str(page)).split(' '):
                    end = x_pt + stringWidth(word, 'Helvetica', 10)
                    d.rectangle([round(w * x_pt / PAGE_W), round(h * (PAGE_H - y_pt - 7) / PAGE_H),
                                 round(w * end / PAGE_W), round(h * (PAGE_H - y_pt + 2) / PAGE_H)], fill=30)
                    x_pt += stringWidth(word + ' ', 'Helvetica', 10)
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=quality)
        buf.seek(0)
        c.drawImage(ImageReader(buf), 0, 0, PAGE_W, PAGE_H)
        if ocr:
            text = c.beginText(56, 700)
            text.setTextRenderMode(3)
            text.setFont('Helvetica', 10)
            for line in ocr:
                text.textLine(line.replace('{page}', str(page)))
            c.drawText(text)
        c.showPage()
    c.save()
    return out.getvalue()


def word_docx(number: int, seed: int) -> bytes:
    """A small, valid Word file (the original a Word document's converted PDF stands for). Fixed member order, times and
    compression, so its bytes repeat."""
    rng = random.Random(seed)
    paragraphs = ''.join(f'<w:p><w:r><w:t>{sentence(rng, 10)}</w:t></w:r></w:p>' for _ in range(12))
    parts = {
        '[Content_Types].xml': (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'),
        '_rels/.rels': (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'officeDocument" Target="word/document.xml"/></Relationships>'),
        'word/document.xml': (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            f'<w:p><w:r><w:t>SYNTHETIC PROCEDURE NOTE {number} - NOT A REAL PATIENT</w:t></w:r></w:p>{paragraphs}'
            '</w:body></w:document>'),
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        for name, text in parts.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            z.writestr(info, text.encode('utf-8'), compresslevel=6)
    return out.getvalue()


def text_note(number: int) -> bytes:
    return (f'SYNTHETIC NOTE {number} - NOT A REAL PATIENT\n'.encode() + f'Quoted passage 1: {QUOTE}\n'.encode() * 60)


# The documents with stored originals, in the practice of 100 (spec R2-2: 2-, 4- and 10-page text PDFs, a 3-page 1.67 MB
# scan, a 20-page 11.1 MB scan, a Word file with its converted PDF, a text note), and the bench's two control documents:
# a PDF without the marker (never counts as drawn) and the document the proxy holds (the 20 s note). Each number is the
# barcode on its page 1; the Word document's second conversion carries `renumber`.
RICH = (
    {'label': 'text-2p', 'kind': 'pdf', 'pages': 2, 'number': 101, 'seed': 1},
    {'label': 'text-4p', 'kind': 'pdf', 'pages': 4, 'number': 102, 'seed': 2},
    {'label': 'text-10p', 'kind': 'pdf', 'pages': 10, 'number': 103, 'seed': 3},
    {'label': 'scan-3p', 'kind': 'scan', 'pages': 3, 'number': 104, 'seed': 4},
    {'label': 'scan-20p', 'kind': 'scan', 'pages': 20, 'number': 105, 'seed': 5},
    {'label': 'word-3p', 'kind': 'word', 'pages': 3, 'number': 106, 'seed': 6, 'renumber': 116},
    {'label': 'text-note', 'kind': 'text', 'pages': 1, 'number': 107, 'seed': 7},
    {'label': 'control-nomarker', 'kind': 'pdf', 'pages': 2, 'number': 108, 'seed': 8, 'marker': False},
    {'label': 'control-held', 'kind': 'pdf', 'pages': 2, 'number': 109, 'seed': 9},
)


def rich_files(spec: dict) -> dict:
    """The stored bytes of one RICH document: its original (data, filename, media type) and, for Word, the converted PDF
    its round stores."""
    kind, pages, number, seed = spec['kind'], spec['pages'], spec['number'], spec['seed']
    label = spec['label']
    if kind == 'pdf':
        return {'data': text_pdf(pages, number, seed, marker=spec.get('marker', True)), 'filename': f'{label}.pdf',
                'media_type': 'application/pdf', 'view': None}
    if kind == 'scan':
        return {'data': scan_pdf(pages, number, seed), 'filename': f'{label}.pdf', 'media_type': 'application/pdf',
                'view': None}
    if kind == 'word':
        return {'data': word_docx(number, seed), 'filename': f'{label}.docx', 'media_type': DOCX_MEDIA,
                'view': text_pdf(pages, number, seed)}
    if kind == 'text':
        return {'data': text_note(number), 'filename': f'{label}.txt', 'media_type': 'text/plain', 'view': None}
    raise ValueError(kind)


def all_bytes() -> bytes:
    """Every byte builder's output, concatenated with lengths (what ops/test_bench.py compares across two builds)."""
    out = io.BytesIO()
    for spec in RICH:
        files = rich_files(spec)
        for part in (files['data'], files['view'] or b''):
            out.write(len(part).to_bytes(8, 'big') + part)
    out.write(word_docx(106, 99) + text_pdf(1, 4095, 99))
    return out.getvalue()


# --- the rows (Django; only ever in the bench's throwaway test database) ----------------------------------------------

STATE_MIX = ['ready'] * 30 + ['needs_review'] * 15 + ['awaiting_answer'] * 5 + ['failed'] * 30 + ['no_codes'] * 20 + [
    'reviewed'] * 900  # a live-like mix of today's derived states, as the measure area's prototype used
INSURANCE = ('medicare', 'medicaid', 'commercial', 'unknown')
TITLE = 'Synthetic GI note {i:05d} colonoscopy with biopsy'


def practice(name: str, rows: int, password: str, *, seed: int):
    """A practice of ``rows`` bulk documents (no stored files), one reviewer, with deterministic ids. Bulk rows are
    older than anything added later, 25 minutes apart, so the documents added by add_rich() list first."""
    from django.db import connection
    from django.utils import timezone
    from studio import models
    category, _ = models.Category.objects.get_or_create(
        slug='bench-gi', defaults={'name': 'Gastroenterology', 'profiles_version': 'synthetic@1'})
    ws = models.Workspace.objects.create(id=uuid.uuid5(NS, f'ws:{name}'), name=f'Bench {name}', category=category)
    user = models.User.objects.create_user(id=uuid.uuid5(NS, f'user:{name}'), username=f'bench-{name}',
                                           password=password, display_name=f'Bench {name}')
    models.Membership.objects.create(user=user, workspace=ws, role=models.Membership.REVIEWER)
    rng = random.Random(seed)
    now = timezone.now()
    encs, revs, rounds = [], [], []
    for i in range(rows):
        eid = uuid.uuid5(NS, f'{name}:{i}')
        encs.append(models.Encounter(id=eid, workspace=ws, title=TITLE.format(i=i), created_by=user,
                                     user_values={'service_date': '2026-11-02', 'insurance': rng.choice(INSURANCE)},
                                     state=rng.choice(STATE_MIX)))
        rid = uuid.uuid5(NS, f'{name}:{i}:rev')
        revs.append(models.SourceRevision(id=rid, encounter_id=eid, number=1, kind='upload', synthetic_attested_by=user,
                                          synthetic_attested_at=now, created_by=user))
        rounds.append(models.CodingRound(id=uuid.uuid5(NS, f'{name}:{i}:round'), encounter_id=eid, revision_id=rid,
                                         number=1, trigger='upload', context={}, state='done', codes=[],
                                         finished_at=now))
    models.Encounter.objects.bulk_create(encs, batch_size=2000)
    models.SourceRevision.objects.bulk_create(revs, batch_size=2000)
    models.CodingRound.objects.bulk_create(rounds, batch_size=2000)
    with connection.cursor() as cur:
        cur.execute('UPDATE studio_encounter e SET current_revision_id = r.id FROM studio_sourcerevision r '
                    'WHERE r.encounter_id = e.id AND e.workspace_id = %s', [ws.pk])
        cur.execute("UPDATE studio_encounter e "
                    "SET created_at = now() - interval '1 hour' - (n.k * interval '25 minutes') "
                    'FROM (SELECT id, row_number() OVER (ORDER BY title DESC) k FROM studio_encounter '
                    'WHERE workspace_id = %s) n WHERE n.id = e.id', [ws.pk])
    return ws, user


def _codes(pages: int):
    """9 lines, 31 quotes, the audit's largest GI round's shape (as the measure area's prototype)."""
    codes, citations = [], {}
    for n in range(1, 10):
        line = f'L{n}'
        status = ['ready', 'needs_review', 'not_supported'][n % 3]
        reason = ('The synthetic note documents this service in the findings and the impression, with its '
                  'technique. ') * 3
        check = {'agrees': True, 'verdict': 'agree', 'reason': 'Agreed on the same passages. ' * 4, 'question': None,
                 'correct_code': f'4538{n}', 'correct_units': 1, 'correct_modifiers': [], 'correct_status': status,
                 'evidence': [], 'reviews': 1, 'unmatched': 0, 'unplaced': 0}
        codes.append({'line': line, 'code': f'4538{n}', 'units': 1, 'modifiers': ['59'] if n % 2 else [],
                      'listed_status': status, 'reason': reason, 'question': None, 'evidence': [], 'status': status,
                      'listed_by': 'reader', 'second_check': check})
        citations[line] = [{'text': f'Quoted passage {(k % pages) + 1}: {QUOTE}', 'page': (k % pages) + 1,
                            'source': 'reader'} for k in range(4 if n <= 4 else 3)]
    return codes, citations


def add_rich(ws, user, spec: dict, *, order: int):
    """One RICH document: its stored original, a finished round (and, for Word, the converted PDF the round keeps),
    12 history rows. Returns the encounter."""
    from django.utils import timezone
    from studio import audit, models, storage
    from studio import state as derived
    files = rich_files(spec)
    enc = models.Encounter.objects.create(
        id=uuid.uuid5(NS, f'rich:{ws.pk}:{spec["label"]}'), workspace=ws, title=f'Rich {spec["label"]}',
        created_by=user, user_values={'service_date': '2026-11-02', 'insurance': 'medicare'}, state='ready')
    name, digest, size = storage.store_original(ws.pk, files['data'], files['filename'])
    src = models.SourceFile.objects.create(encounter=enc, original_name=files['filename'],
                                           media_type=files['media_type'], size=size, sha256=digest,
                                           storage_name=name, uploaded_by=user)
    rev = models.SourceRevision.objects.create(encounter=enc, number=1, kind='upload', source_file=src,
                                               synthetic_attested_by=user, synthetic_attested_at=timezone.now(),
                                               created_by=user)
    enc.current_revision = rev
    enc.save(update_fields=['current_revision'])
    codes, citations = _codes(spec['pages'])
    extra = {}
    if files['view'] is not None:
        vname, vdigest, _ = storage.store_original(ws.pk, files['view'], 'converted.pdf')
        extra = {'view_pdf_storage_name': vname, 'view_pdf_sha256': vdigest}
    now = timezone.now()
    models.CodingRound.objects.create(encounter=enc, revision=rev, number=1, trigger='upload', context={}, state='done',
                                      codes=codes, questions=[], problems=['The note is not signed.'],
                                      citations=citations, started_at=now, finished_at=now, **extra)
    audit.record(ws, 'encounter.created', encounter=enc, actor=user, kind='upload')
    for n in range(11):
        audit.record(ws, 'decision.recorded', encounter=enc, actor=user, round='x', code=f'4538{n % 9 + 1}',
                     line=f'L{n % 9 + 1}', action='approve')
    derived.refresh(enc)
    # newest first in the list, in RICH's order (the bulk rows are an hour and more older)
    models.Encounter.objects.filter(pk=enc.pk).update(created_at=now - timezone.timedelta(seconds=order))
    return enc


def reconvert(enc, spec: dict):
    """A newer round of a Word document with another conversion (barcode ``renumber``): the correctness part's 'a
    re-open shows the new barcode and never the old bytes'."""
    from django.utils import timezone
    from studio import models, storage
    last = models.CodingRound.objects.filter(encounter=enc).order_by('-number').first()
    view = text_pdf(spec['pages'], spec['renumber'], spec['seed'])
    vname, vdigest, _ = storage.store_original(enc.workspace_id, view, 'converted.pdf')
    now = timezone.now()
    return models.CodingRound.objects.create(
        encounter=enc, revision=last.revision, number=last.number + 1, trigger='retry', context={}, state='done',
        codes=last.codes, questions=[], problems=last.problems, citations=last.citations, started_at=now,
        finished_at=now, view_pdf_storage_name=vname, view_pdf_sha256=vdigest)


# --- the practices a round (or a rehearsal on a test instance) needs -----------------------------------------------

SIZES = {'n50': 50, 'n100': 100, 'n101': 101, 'n1500': 1500, 'n5000': 5000, 'n18000': 18000}
RICH_IN = 'n100'  # the practice whose 100 documents include the RICH ones


def seed(names, password) -> dict:
    """The practices ``names`` (SIZES' keys), each with one reviewer; the practice of 100 holds the RICH documents among
    its 100. Ids are uuid5 of fixed names, so a test instance seeded with this function holds the same ids as a
    round."""
    out = {}
    for name in sorted(names, key=lambda n: SIZES[n]):
        rich = len(RICH) if name == RICH_IN else 0
        ws, user = practice(name, SIZES[name] - rich, password, seed=SIZES[name])
        out[name] = {'ws': ws, 'user': user, 'username': user.username, 'rows': SIZES[name], 'docs': []}
        if rich:
            for order, spec in enumerate(RICH):
                enc = add_rich(ws, user, spec, order=order)
                files = rich_files(spec)
                out[name]['docs'].append({'id': str(enc.pk), 'label': spec['label'], 'kind': spec['kind'],
                                          'number': spec['number'], 'renumber': spec.get('renumber'),
                                          'pages': spec['pages'], 'bytes': len(files['view'] or files['data']),
                                          'original_bytes': len(files['data']), 'marker': spec.get('marker', True)})
    if out:
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute('ANALYZE')
    return out


def docs_json(seeded: dict, client, marker: str) -> dict:
    """What bench.cjs reads (--docs): the barcode geometry, the RICH documents, the users and sizes, the client header
    the measured tree's page sends, and the search marker."""
    return {'geometry': geometry(), 'docs': seeded.get(RICH_IN, {}).get('docs', []), 'client': list(client),
            'marker': marker, 'users': {name: d['username'] for name, d in seeded.items()},
            'rows': {name: d['rows'] for name, d in seeded.items()}}


def rehearsal_seed(password: str, client, marker: str = 'zqxbenchmarkerword') -> dict:
    """The rehearsal (section 9.1): seed a test instance's own database (run inside its Django, synthetic data only)
    with the practices the open, list and office parts use, and return the docs.json those parts read."""
    return docs_json(seed(('n100', 'n101', 'n1500', 'n5000', 'n18000'), password), client, marker)
