"""Bounded PDF layout witness. Import parsers, then close the filesystem/network sandbox."""
import hashlib
import json
import math
from pathlib import Path
import sys

from pypdf import PdfReader
from pypdf.generic import IndirectObject, NameObject, StreamObject

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sandbox import isolate

MAX_PAGES = 64
MAX_OBJECTS = 100000
PRECISION_POINTS = .051  # One twip plus PDF floating-point representation tolerance.


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def resource_value(value, seen=None, counter=None):
    seen = set() if seen is None else seen
    counter = [0] if counter is None else counter
    counter[0] += 1
    if counter[0] > MAX_OBJECTS:
        raise ValueError('PDF resource graph limit')
    if isinstance(value, IndirectObject):
        identity = (value.idnum, value.generation)
        if identity in seen:
            raise ValueError('Cyclic drawing resource')
        return resource_value(value.get_object(), seen | {identity}, counter)
    if isinstance(value, dict):
        result = {str(k): resource_value(v, seen, counter) for k, v in value.items()
                  if k not in ('/Length', '/Filter', '/DecodeParms') or not isinstance(value, StreamObject)}
        if isinstance(value, StreamObject):
            result['decoded_stream_sha256'] = hashlib.sha256(value.get_data()).hexdigest()
        return result
    if isinstance(value, (list, tuple)):
        return [resource_value(v, seen, counter) for v in value]
    if isinstance(value, bytes):
        return {'bytes_sha256': hashlib.sha256(value).hexdigest()}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    try:
        number = float(value)
        if not math.isfinite(number): raise ValueError('Non-finite PDF value')
        return number
    except (TypeError, ValueError):
        if type(value).__name__ == 'NullObject': return None
        raise ValueError('Unsupported drawing resource value') from None


def destinations(reader):
    result = {}
    pages = {page.indirect_reference.idnum: index for index, page in enumerate(reader.pages)}
    def add(name, value):
        name = str(name)[1:] if isinstance(name, NameObject) else str(name)
        if name in result: raise ValueError('Duplicate PDF destination')
        value = value.get_object()
        if isinstance(value, dict): value = value['/D'].get_object()
        if len(value) != 5 or str(value[1]) != '/XYZ' or not isinstance(value[0], IndirectObject):
            raise ValueError('Unsupported PDF destination')
        point = {'page': pages[value[0].idnum], 'x': float(value[2]), 'y': float(value[3])}
        if not all(math.isfinite(point[k]) for k in ('x', 'y')): raise ValueError('Non-finite destination')
        result[name] = point
    visited = set()
    def walk(tree):
        if isinstance(tree, IndirectObject):
            identity = (tree.idnum, tree.generation)
            if identity in visited: raise ValueError('Repeated destination tree')
            visited.add(identity)
        if len(visited) > MAX_OBJECTS: raise ValueError('Destination graph limit')
        tree = tree.get_object()
        if '/Names' in tree:
            names = tree['/Names']
            if len(names) % 2: raise ValueError('Incomplete destination pair')
            for i in range(0, len(names), 2): add(names[i], names[i + 1])
        for child in tree.get('/Kids', []): walk(child)
    root = reader.trailer['/Root']
    if '/Dests' in root:
        for name, value in root['/Dests'].items(): add(name, value)
    if '/Names' in root and '/Dests' in root['/Names']: walk(root['/Names']['/Dests'])
    return result


def verify(workspace):
    manifest = json.loads((workspace / 'manifest.json').read_text())
    original = PdfReader(workspace / 'document.pdf', strict=True)
    marked = PdfReader(workspace / 'instrumented.pdf', strict=True)
    if not 0 < len(original.pages) <= MAX_PAGES or len(original.pages) != len(marked.pages):
        raise ValueError('Different or excessive page count')
    page_records = []
    for a, b in zip(original.pages, marked.pages):
        def page_record(page):
            contents = page.get_contents()
            return {'content_sha256': hashlib.sha256(contents.get_data() if contents is not None else b'').hexdigest(),
                    'resources_sha256': hashlib.sha256(canonical(resource_value(page.get('/Resources', {})))).hexdigest(),
                    'media': list(map(float, page.mediabox)), 'crop': list(map(float, page.cropbox)),
                    'rotation': int(page.get('/Rotate', 0)),
                    'text_sha256': hashlib.sha256(page.extract_text().encode()).hexdigest()}
        left, right = page_record(a), page_record(b)
        if left != right: raise ValueError('Instrumentation changed page graphics, resources, text or geometry')
        page_records.append(left)
    original_destinations, actual = destinations(original), destinations(marked)
    expected = {a['name'] for a in manifest['anchors']}
    if len(expected) != len(manifest['anchors']) or expected & original_destinations.keys():
        raise ValueError('Source anchor identity collision')
    if actual.keys() != original_destinations.keys() | expected:
        raise ValueError('Missing or unexpected PDF source anchors')
    for point in actual.values():
        page = marked.pages[point['page']]
        left, bottom, right, top = map(float, page.cropbox)
        if not left <= point['x'] <= right or not bottom <= point['y'] <= top:
            raise ValueError('Source anchor is outside the visible page')
    if any(actual[name] != value for name, value in original_destinations.items()):
        raise ValueError('Existing destination changed')
    groups = {}
    for anchor in manifest['anchors']:
        key = (anchor['candidate'], anchor['ordinal'])
        side = (anchor['role'], anchor['edge'])
        if side in groups.setdefault(key, {}): raise ValueError('Duplicate source span')
        groups[key][side] = actual[anchor['name']]
    measurements, per_candidate = [], {}
    for (candidate, ordinal), group in groups.items():
        if set(group) != {('header', 'start'), ('header', 'end'), ('row', 'start'), ('row', 'end')}:
            raise ValueError('Partial source span')
        h0, h1, r0, r1 = [group[k] for k in [('header', 'start'), ('header', 'end'), ('row', 'start'), ('row', 'end')]]
        same_page = len({p['page'] for p in (h0, h1, r0, r1)}) == 1
        same_line = abs(h0['y'] - h1['y']) <= PRECISION_POINTS and abs(r0['y'] - r1['y']) <= PRECISION_POINTS
        delta = abs((h0['x'] + h1['x']) / 2 - (r0['x'] + r1['x']) / 2)
        ordered = h0['x'] < h1['x'] and r0['x'] < r1['x'] and h0['y'] > r0['y']
        passed = same_page and same_line and ordered and delta <= PRECISION_POINTS
        row = {'candidate': candidate, 'ordinal': ordinal, 'header': [h0, h1], 'row': [r0, r1],
               'center_delta_points': delta, 'passed': passed}
        measurements.append(row); per_candidate.setdefault(candidate, []).append(row)
    for candidate in manifest['candidates']:
        rows = sorted(per_candidate.get(candidate['id'], []), key=lambda row: row['ordinal'])
        if [row['ordinal'] for row in rows] != list(range(len(candidate['source']['options']))):
            raise ValueError('Incomplete candidate coverage')
        for left, right in zip(rows, rows[1:]):
            if any(left[role][1]['x'] >= right[role][0]['x'] for role in ('header', 'row')):
                raise ValueError('Overlapping source columns')
    return {'passed': bool(measurements) and all(row['passed'] for row in measurements),
            'page_records': page_records, 'measurements': measurements,
            'complete_unique_anchors': len(expected), 'precision_points': PRECISION_POINTS,
            'pdf_sha256': {name: hashlib.sha256((workspace / name).read_bytes()).hexdigest()
                           for name in ('document.pdf', 'instrumented.pdf')}}


if __name__ == '__main__':
    workspace = Path(sys.argv[1]).resolve()
    try:
        isolate(workspace)
        result = verify(workspace)
        print(json.dumps(result, allow_nan=False))
    except Exception:
        print(json.dumps({'passed': False, 'error': 'Layout verification is incomplete or the rendered source differs.'}))
