"""Strict rendered-text alignment for the pinned, unrotated PDF profile.

Widths below come from the PDF font's explicit widths and text positioning
operators. They are not measured from DOCX fonts or inferred from tab stops.
Unsupported painting/text state refuses this contract instead of guessing.
"""
import math
import io
import struct
from pypdf._font import Font
from reportlab.pdfbase.ttfonts import TTFontFile

CONTRACT = 'word-tab-containment-v2'
PRECISION = .051
MAX_OPERATIONS = 200000
MAX_GLYPHS = 200000
VECTOR = '\ufffc'


def finite(values):
    values = list(map(float, values))
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Non-finite drawing geometry')
    return values


def glyph_map(outline):
    """The pinned subset profile has one explicit Mac Roman byte cmap."""
    table = outline.get_table('cmap')
    if len(table) < 18 or struct.unpack('>HHHHI', table[:12]) != (0,1,1,0,12):
        raise ValueError('Ambiguous embedded byte cmap')
    form, length, language = struct.unpack('>HHH', table[12:18])
    data = table[12:12+length]
    if len(data) != length or language != 0: raise ValueError('Incomplete embedded cmap')
    if form == 0 and length == 262: return dict(enumerate(data[6:]))
    if form == 6 and length >= 10:
        first,count = struct.unpack('>HH',data[6:10])
        if first+count>256 or length != 10+count*2: raise ValueError('Invalid embedded cmap extent')
        return {first+i:value for i,value in enumerate(struct.unpack('>'+str(count)+'H',data[10:]))}
    raise ValueError('Unsupported embedded byte cmap')


def geometry(page):
    """Read a bounded horizontal PDF profile; retain actual glyph advances."""
    if page.get('/Rotate', 0): raise ValueError('Rotated containment page')
    fonts, records, paths, stack = {}, [], [], []
    state = {'fill': (0., 0., 0.), 'stroke': (0., 0., 0.), 'width': 1., 'cap': 0, 'join': 0, 'dashed': False}
    x = y = size = 0.; font = outline = None; widths = mapping = {}; active = False; path = []
    contents = page.get_contents()
    operations = [] if contents is None else contents.operations
    if len(operations) > MAX_OPERATIONS: raise ValueError('PDF operation limit')
    resources = page.get('/Resources', {})
    def emit(value):
        nonlocal x
        if not active or font is None or size <= 0: raise ValueError('Missing text state')
        raw = value.original_bytes if hasattr(value, 'original_bytes') else bytes(value)
        for code in raw:
            key = chr(code)
            char = font.character_map.get(key)
            width = widths.get(code)
            if not isinstance(char, str) or not 1 <= len(char) <= 8 or width is None:
                raise ValueError('Unmapped or combined PDF glyph')
            advance = float(width) * size / 1000
            if not math.isfinite(advance) or advance < 0: raise ValueError('Invalid glyph advance')
            glyph = mapping.get(code)
            if glyph is None or not 0 <= glyph < len(outline.glyphPos)-1: raise ValueError('Missing embedded glyph identity')
            start, end = outline.glyphPos[glyph:glyph+2]
            ink = None
            if end > start:
                if end-start < 10: raise ValueError('Incomplete embedded glyph bounds')
                _, left, bottom, right, top = struct.unpack('>hhhhh', outline.get_table('glyf')[start:start+10])
                ink = [x+left*size/outline.unitsPerEm, y+bottom*size/outline.unitsPerEm,
                       x+right*size/outline.unitsPerEm, y+top*size/outline.unitsPerEm]
            # A ligature has one actual advance. Every mapped character retains
            # that whole extent; it cannot acquire an invented fractional width.
            # 'order' is the painting order: a path records how many glyphs preceded it.
            for character in char:
                records.append({'text': character, 'left': x, 'right': x + advance, 'y': y,
                                'ink': ink, 'paint': state['fill'], 'type': 'glyph', 'order': len(records)})
            x += advance
            if len(records) > MAX_GLYPHS: raise ValueError('PDF glyph limit')
    for args, op in operations:
        if op == b'q': stack.append(state.copy())
        elif op == b'Q':
            if not stack: raise ValueError('Unbalanced graphics state')
            state = stack.pop()
        elif op in (b'rg', b'RG'):
            rgb = tuple(finite(args))
            if len(rgb) != 3 or any(c < 0 or c > 1 for c in rgb): raise ValueError('Invalid RGB')
            state['fill' if op == b'rg' else 'stroke'] = rgb
        elif op == b'w': state['width'], = finite(args)
        elif op in (b'J', b'j'):
            value, = finite(args)
            if value not in (0., 1., 2.): raise ValueError('Unsupported stroke cap or join')
            state['cap' if op == b'J' else 'join'] = int(value)
        elif op == b'd':
            if len(args) != 2: raise ValueError('Invalid dash pattern')
            lengths, phase = finite(args[0]), float(args[1])
            if not math.isfinite(phase) or phase < 0 or any(v < 0 for v in lengths) or (lengths and not sum(lengths)):
                raise ValueError('Invalid dash pattern')
            state['dashed'] = bool(lengths)
        elif op == b'BT':
            if active: raise ValueError('Nested text object')
            active = True; x = y = 0.
        elif op == b'ET':
            if not active: raise ValueError('Unbalanced text object')
            active = False
        elif op == b'Td':
            dx, dy = finite(args); x += dx; y += dy
        elif op == b'Tm':
            a, b, c, d, x, y = finite(args)
            if (a, b, c, d) != (1., 0., 0., 1.): raise ValueError('Transformed PDF text')
        elif op == b'Tf':
            name, value = args; size, = finite([value])
            if name not in fonts:
                resource = resources['/Font'][name].get_object()
                descriptor = resource.get('/FontDescriptor', {})
                if (str(resource.get('/Subtype')) != '/TrueType' or '/Widths' not in resource or '/ToUnicode' not in resource
                        or resource.get('/Encoding') is not None or not int(descriptor.get('/Flags',0)) & 4
                        or '/FontFile2' not in descriptor):
                    raise ValueError('No explicit embedded symbolic TrueType glyph identity')
                data = descriptor['/FontFile2'].get_data()
                if len(data) > 8*1024*1024: raise ValueError('Embedded font bound')
                face = TTFontFile(io.BytesIO(data))
                first = int(resource.get('/FirstChar',0))
                widths = {first+i:float(value) for i,value in enumerate(resource['/Widths'])}
                fonts[name] = (Font.from_font_resource(resource), face, widths, glyph_map(face))
            font, outline, widths, mapping = fonts[name]
        elif op == b'Tj': emit(args[0])
        elif op == b'TJ':
            for value in args[0]:
                if isinstance(value, (int, float)): x -= float(value) * size / 1000
                else: emit(value)
        elif op == b're': path.append(('rect', finite(args)))
        elif op in (b'm', b'l'): path.append((op.decode(), finite(args)))
        elif op in (b'S', b'f', b'f*'):
            paths.append({'path': path, 'operation': op.decode(), 'state': state.copy(), 'order': len(records)})
            path = []
        elif op == b'W*':
            # Only the renderer's full-page rectangular clip is understood.
            if len(path) != 1 or path[0][0] != 'rect': raise ValueError('Nonrectangular clip')
            left, bottom, width, height = path[0][1]
            pleft, pbottom, pright, ptop = finite(page.cropbox)
            if max(abs(left-pleft), abs(bottom-pbottom), abs(left+width-pright), abs(bottom+height-ptop)) > PRECISION:
                raise ValueError('Partial-page clipping')
        elif op == b'n': path = []
        else:
            raise ValueError('Unsupported containment drawing operator')
    if active or stack or path: raise ValueError('Incomplete drawing state')
    for item in paths:
        points = []
        for kind, values in item['path']:
            if kind == 'rect':
                px,py,pw,ph = values; points += [(px,py),(px+pw,py+ph)]
            else: points.append(values)
        if not points: raise ValueError('Empty painted path')
        xpad = ypad = 0.
        if item['operation'] == 'S':
            half = item['state']['width']/2
            if half <= 0: raise ValueError('Unmeasured zero or negative stroke width')
            kinds = [kind for kind, values in item['path']]
            if kinds == ['rect']:
                xpad = ypad = half  # all supported rectangular joins stay within these bounds
            elif kinds == ['m', 'l']:
                (x0,y0),(x1,y1) = points
                dx,dy = abs(x1-x0),abs(y1-y0); length = math.hypot(dx,dy)
                if not length: raise ValueError('Degenerate stroked segment')
                cap = item['state']['cap']
                if cap == 0: xpad,ypad = half*dy/length,half*dx/length
                elif cap == 1: xpad = ypad = half
                else: xpad = ypad = half*(dx+dy)/length
            else:
                raise ValueError('Unsupported joined stroke geometry')
        item['bounds'] = [min(p[0] for p in points)-xpad,min(p[1] for p in points)-ypad,
                          max(p[0] for p in points)+xpad,max(p[1] for p in points)+ypad]
    baselines = sorted({r['y'] for r in records})
    rectangles = []
    for index, item in enumerate(paths):
        if item['operation'] != 'S' or len(item['path']) != 1 or item['path'][0][0] != 'rect': continue
        left, bottom, width, height = item['path'][0][1]
        if width <= 0 or height <= 0 or abs(width-height) > PRECISION: continue
        possible = [v for v in baselines if bottom < v < bottom+height]
        if len(possible) > 1:
            # Another line's baseline also lies within the box (text in a neighbouring cell set on a slightly
            # different baseline): the box belongs to the one line that prints ink beside it, if only one does.
            possible = [v for v in possible if any(r['y'] == v and r['ink'] is not None and r['ink'][0] <= left + 2 * width
                                                   and r['ink'][2] >= left - width for r in records)]
        if len(possible) != 1: continue
        diagonals = []
        for next_item in paths[index+1:index+3]:
            p = next_item['path']
            if next_item['operation'] != 'S' or len(p) != 2 or [k for k,v in p] != ['m','l']: break
            ends = [v for k,v in p]
            if not all(left-PRECISION <= px <= left+width+PRECISION and bottom-PRECISION <= py <= bottom+height+PRECISION for px,py in ends): break
            diagonals.append(ends)
        checked = False
        if diagonals:
            expected = [[[left,bottom+height],[left+width,bottom]], [[left+width,bottom+height],[left,bottom]]]
            if len(diagonals) != 2 or any(abs(a-b)>PRECISION for actual,wanted in zip(diagonals,expected) for p,q in zip(actual,wanted) for a,b in zip(p,q)):
                raise ValueError('Ambiguous native checkbox marks')
            checked = True
        owned = paths[index:index+1+len(diagonals)]
        if any(stroke['state']['stroke'] != (0.,0.,0.) or stroke['state']['width'] <= 0 or
               stroke['state']['dashed'] for stroke in owned):
            raise ValueError('Unqualified native checkbox stroke paint')
        ink = [min(stroke['bounds'][0] for stroke in owned), min(stroke['bounds'][1] for stroke in owned),
               max(stroke['bounds'][2] for stroke in owned), max(stroke['bounds'][3] for stroke in owned)]
        rectangles.append({'text': VECTOR, 'left': left, 'right': left+width, 'y': possible[0],
                           'bottom': bottom, 'top': bottom+height, 'paint': item['state']['stroke'],
                           'ink': ink,
                           'own_paths':list(range(index,index+1+len(diagonals))),
                           'type': 'ff_checkbox', 'checked': checked})
    lines = []
    for baseline in reversed(baselines):
        glyphs = [r for r in records if r['y'] == baseline]
        glyphs += [r for r in rectangles if r['y'] == baseline]
        glyphs.sort(key=lambda r:(r['left'],r['right']))
        lines.append({'y': baseline, 'records': glyphs, 'paths':paths, 'crop':finite(page.cropbox),
                      'text': ''.join(r['text'] for r in glyphs)})
    return lines


def luminance(rgb):
    channels = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb]
    return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2]


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + .05) / (low + .05)


MIN_CONTRAST = 4.5  # WCAG AA for ordinary text


def beneath(index, path, record):
    """A filled area painted before this ink, in a colour the ink stands out from, hides nothing."""
    if path['operation'] not in ('f', 'f*'):
        return False
    if record['type'] == 'ff_checkbox':
        painted_before = index < min(record['own_paths'])
    else:
        painted_before = path['order'] <= record['order']
    return painted_before and contrast(path['state']['fill'], record['paint']) >= MIN_CONTRAST


def match_block(line, segments, leader, cursor):
    """Match every visible character/control of one complete source paragraph from `cursor`.
    Returns (end, spans), or None when the records there are not exactly this paragraph."""
    records, spans = line['records'], []
    for ordinal, segment in enumerate(segments):
        if ordinal and leader:
            while cursor < len(records) and records[cursor]['text'] == '.': cursor += 1
        found = []
        for item in segment:
            for char in item['text']:
                if cursor >= len(records): return None
                record = records[cursor]; cursor += 1
                if record['text'] != char: return None
                if item['kind'] == 'ff_checkbox':
                    if record['type'] != 'ff_checkbox' or record['checked'] != item['checked']: return None
                elif record['type'] != 'glyph': return None
                if record['paint'] == (1.,1.,1.): return None
                ink = record['ink']
                if ink is not None:
                    crop = line['crop']
                    if not crop[0] <= ink[0] <= ink[2] <= crop[2] or not crop[1] <= ink[1] <= ink[3] <= crop[3]:
                        return None
                    for i,path in enumerate(line['paths']):
                        if i in record.get('own_paths',[]): continue
                        box = path['bounds']
                        if max(box[0],ink[0]) < min(box[2],ink[2]) and max(box[1],ink[1]) < min(box[3],ink[3]):
                            if beneath(i, path, record): continue  # e.g. cell shading painted under the text
                            return None  # A painted overlay, stroke or low-contrast background is outside this proof.
                found.append(record)
        if found:
            ink = [r['ink'] for r in found if r['ink'] is not None]
            if not ink:
                if ordinal != 0 or any(not r['text'].isspace() for r in found): return None
                spans.append(None)
            else:
                spans.append({'left':min(r[0] for r in ink), 'right':max(r[2] for r in ink), 'y':line['y']})
        else: spans.append(None)
    return cursor, spans


def printed(records):
    return ''.join(r['text'] for r in records if not r['text'].isspace())


def beside(line, neighbours):
    """The sides of the row whose printed text this whole line could be: it prints ink and nothing but one
    contiguous piece of that side's neighbouring text. Its position is checked against the match."""
    if not any(r['ink'] is not None for r in line['records']):
        return ()
    text = printed(line['records'])
    return tuple(side for side in ('left', 'right') if neighbours[side] and text in neighbours[side])


def match_line(line, segments, leader=False, neighbours=None):
    """Match every visible character/control in the complete source paragraph.

    The whole rendered line is the paragraph, except text the same table row prints in its other cells:
    a comment written beside an answered row shares its baselines. Such text is accepted only on the side
    of the row's cells that prints it, only as one contiguous piece of what those cells print, and only
    with its ink clear of the paragraph's own ink. Returns (spans, records) or None; two readings raise."""
    records = line['records']
    left_text, right_text = (neighbours or {}).get('left', ''), (neighbours or {}).get('right', '')
    starts = [0] if not left_text else range(len(records))
    readings = []
    for start in starts:
        found = match_block(line, segments, leader, start)
        if found is None:
            continue
        end, spans = found
        before, after = records[:start], records[end:]
        if after and not right_text:  # (with no left text the paragraph starts the line)
            continue
        if printed(before) not in left_text or printed(after) not in right_text:
            continue
        own = [r['ink'] for r in records[start:end] if r['ink'] is not None]
        if own and (any(r['ink'] is not None and r['ink'][2] >= min(i[0] for i in own) for r in before)
                    or any(r['ink'] is not None and r['ink'][0] <= max(i[2] for i in own) for r in after)):
            continue
        readings.append((spans, records[start:end]))
    if len(readings) > 1: raise ValueError('A rendered line prints the source paragraph more than once')
    return readings[0] if readings else None


UNPRINTED_KEY = str.maketrans('', '', '.\u00b7\u2026_-\u2013' + VECTOR)


def printed_key(text):
    """The printed characters of a text as a coarse key: no spaces, leader-like punctuation or native
    control, and one box state. Coarser than the match, so a search over it can only find more places."""
    return ''.join(text.split()).translate(UNPRINTED_KEY).replace('\u2612', '\u2610')


def painting_stream(lines):
    """The complete immutable projection of this call's parsed painting order."""
    stream = tuple((number, r['order'], char) for number, page_lines in enumerate(lines)
                   for r in sorted((r for line in page_lines for r in line['records'] if r['type'] == 'glyph'),
                                   key=lambda r: r['order'])
                   for char in printed_key(r['text']))
    return stream, ''.join(char for _, _, char in stream)


def _rendered_elsewhere(stream, text, page, own, sequence):
    """Whether the source sequence's printed characters are painted, in order and as one run, anywhere
    other than the matched lines. The renderer paints a place's paragraphs as one run; a place that
    prints the same text but not as whole lines (a neighbour on its baselines, a wrapped paragraph) is
    still found here, whatever characters the source holds that never print."""
    key = printed_key(''.join(item['text'] for paragraph in sequence for segment in paragraph['segments']
                              for item in segment))
    if not key:
        return True
    at = text.find(key)
    while at >= 0:
        if not all(number == page and order in own for number, order, _ in stream[at:at + len(key)]):
            return True
        at = text.find(key, at + 1)
    return False


def rendered_elsewhere(lines, page, own, sequence):
    # Standalone callers always compile their own current complete source.
    return _rendered_elsewhere(*painting_stream(lines), page, own, sequence)


def _measure(lines, candidate, source_run_check):
    """Measure one candidate's complete printed sequence; absent, ambiguous or incomplete raises."""
    model = candidate['rendered_source']
    matches = []
    sequence = model.get('sequence') or [{'segments': model['header'], 'dot_leaders': False},
                                        {'segments': model['row'], 'dot_leaders': model['row_dot_leaders']}]
    if not 2 <= len(sequence) <= 100: raise ValueError('Incomplete or excessive printed source sequence')
    # Every paragraph is one whole rendered line, in order, with no other line between. Only text the
    # same table row prints in its other cells may share those lines (see match_line), or print a line of
    # its own between them, beside the sequence on that cell's side (see beside).
    # The column header is the paragraph whose segments align with the answer row's.
    header_at = model.get('header_index', 0)
    if type(header_at) is not int or not 0 <= header_at < len(sequence) - 1:
        raise ValueError('Invalid printed column header position')
    neighbours = model.get('neighbours', {'left': '', 'right': ''})
    if not isinstance(neighbours, dict) or set(neighbours) != {'left', 'right'} \
            or not all(isinstance(v, str) for v in neighbours.values()):
        raise ValueError('Invalid neighbouring row text')
    # The source prints this sequence exactly once (counted by the preparer over every displayed
    # paragraph). A second place printing the same text could supply the only matching lines while
    # the candidate's own rendering fails to match, so it is ambiguous whatever the PDF shows.
    if type(model.get('source_occurrences')) is not int or model['source_occurrences'] != 1:
        raise ValueError('The printed source sequence is not unique in the document')
    for page_index, page in enumerate(lines):
        for index in range(len(page)):
            found, between, at = [], [], index
            for offset, paragraph in enumerate(sequence):
                reading = None
                while at < len(page):
                    reading = match_line(page[at], paragraph['segments'], paragraph['dot_leaders'], neighbours)
                    if reading is not None or not offset:
                        break
                    # A line printing only the row's neighbouring text (a wrapped comment line on the baseline
                    # of a blank spacer paragraph) may lie between two of the sequence's lines.
                    sides = beside(page[at], neighbours)
                    if not sides:
                        break
                    between.append((page[at], sides)); at += 1
                if reading is None:
                    break
                found.append(reading); at += 1
            else:
                ink = [r['ink'] for _, records in found for r in records if r['ink'] is not None]
                low, high = min(i[0] for i in ink), max(i[2] for i in ink)
                if all(any(all(r['ink'] is None or (r['ink'][0] > high if side == 'right' else r['ink'][2] < low)
                               for r in line['records']) for side in sides) for line, sides in between):
                    matches.append((page_index, index, found))
    if len(matches) != 1: raise ValueError('Missing or ambiguous complete source paragraph pair')
    page, index, found = matches[0]
    headers, rows = found[header_at][0], found[-1][0]
    # The matched lines are the candidate's own paragraphs only if they were painted as one run: no
    # other printed character was painted between their first and last glyph (lines from different
    # places that merely sit on adjacent baselines are painted with other text between them).
    own = {r['order'] for _, records in found for r in records if r['type'] == 'glyph'}
    if own and any(min(own) < r['order'] < max(own) and r['order'] not in own and not r['text'].isspace()
                   for line in lines[page] for r in line['records'] if r['type'] == 'glyph'):
        raise ValueError('The matched lines are not one contiguous rendering of the source sequence')
    # The source count is taken over source characters, some of which never print. A place the
    # renderer paints with the same text is a second place, whatever the source count says.
    if source_run_check(page, own, sequence):
        raise ValueError('The printed source sequence is rendered more than once')
    headers, rows = headers[1:], rows[1:]
    if len(headers) != len(candidate['source']['options']) or len(rows) != len(headers) or any(r is None for r in headers+rows):
        raise ValueError('Incomplete visible option set')
    if any(a['right'] >= b['left'] for a,b in zip(headers,headers[1:])):
        raise ValueError('Overlapping printed header spans')
    if any(a['right'] >= b['left'] for a,b in zip(rows,rows[1:])):
        raise ValueError('Overlapping visible answer segments')
    # A header word owns the row segment printed under it: the segment's centre lies within the word's
    # printed span and the whole segment lies within the word's column, which ends halfway across the
    # gap to each neighbouring word. A centred '1 ☐' wider than a short word ('No') is owned by it;
    # nothing that reaches halfway to another word, or is centred beside its word, is.
    columns = [((headers[i - 1]['right'] + h['left']) / 2 if i else -math.inf,
                (h['right'] + headers[i + 1]['left']) / 2 if i + 1 < len(headers) else math.inf)
               for i, h in enumerate(headers)]
    measurements = []
    for ordinal,(header,row) in enumerate(zip(headers,rows)):
        centre = (row['left'] + row['right']) / 2
        owners = [i for i,(h,(low,high)) in enumerate(zip(headers, columns))
                  if h['left'] <= centre <= h['right'] and low <= row['left'] < row['right'] <= high]
        measurements.append({'candidate':candidate['id'],'ordinal':ordinal,'page':page,'header':header,'row':row,
                             'unique_owners':owners,'passed':owners==[ordinal]})
    return measurements


def measure(lines, candidate):
    """Public single-candidate reader retains its fresh-source behavior."""
    return _measure(lines, candidate,
                    lambda page, own, sequence: rendered_elsewhere(lines, page, own, sequence))


def holdable(candidate):
    """Only an optional proposal whose source the export leaves byte-identical and unanswered
    can be held on its own. Everything else keeps the all-candidates refusal."""
    return candidate.get('optional') is True and candidate.get('untouched') is True


def containment(pages, candidates):
    lines = [geometry(page) for page in pages]
    # Geometry is compiled from this invocation's exact PDF pages before any
    # candidate is measured. Only this closed-over immutable projection is
    # reused; callers cannot provide a cache or a foreign document's stream.
    stream, text = painting_stream(lines)
    def source_run_check(page, own, sequence):
        return _rendered_elsewhere(stream, text, page, own, sequence)
    measurements, held = [], []
    for candidate in candidates:
        try:
            found = _measure(lines, candidate, source_run_check)
        except ValueError as error:
            if not holdable(candidate): raise
            held.append({'candidate': candidate['id'], 'reason': str(error)})
            continue
        if holdable(candidate) and not all(m['passed'] for m in found):
            held.append({'candidate': candidate['id'], 'reason': 'A visible control is outside its printed column'})
            continue
        measurements.extend(found)
    # A held proposal publishes no destination. It is never counted as a verified one.
    return {'passed':bool(measurements or held) and all(m['passed'] for m in measurements),'measurements':measurements,
            'held':held,
            'ownership_contract':CONTRACT, 'width_source':'PDF embedded glyph bounds, explicit advances, positioning operators and stroked native control paths'}
