"""Real blank originals for synthetic legacy workflow/financial controls.

The parser supplies every physical destination. This does not qualify model
semantics, Word layout families or real patient processing.
"""
from copy import deepcopy
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import hashlib
import json
import os
import tempfile

from docx import Document
from documents import inspect_template


@lru_cache(maxsize=1)
def original_bytes():
    document = Document()
    document.add_heading('Synthetic workflow original', level=1)
    cells = document.add_table(rows=1, cols=2).rows[0].cells
    cells[0].text = 'Symptoms'
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


@lru_cache(maxsize=1)
def _inspection():
    with tempfile.TemporaryDirectory(prefix='quillmd-synthetic-original-') as directory:
        path = Path(directory) / 'original.docx'
        path.write_bytes(original_bytes())
        result = inspect_template(path, engine='legacy')
    assert result['sha256'] == hashlib.sha256(original_bytes()).hexdigest()
    assert len(result['fields']) == 1 and result['fields'][0]['label'] == 'Symptoms'
    assert not result['import_manifest']['coverage'].get('block_generation')
    if os.environ.get('QUILLMD_WORD_ARTIFACTS'):
        root = Path(os.environ['QUILLMD_WORD_ARTIFACTS']) / 'synthetic-financial-original' / result['sha256']
        root.mkdir(mode=0o700, parents=True, exist_ok=False)
        persist(root / 'original.docx')
        with (root / 'inspection.json').open('x') as stream:
            json.dump(result, stream, indent=2)
    return result


def inspection():
    # Never share mutable inspector output between scopes or fixture subclasses.
    return deepcopy(_inspection())


def persist(path, payload=None):
    payload = original_bytes() if payload is None else payload
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != payload:
            raise AssertionError('The synthetic original changed; it must not be overwritten.')
    else:
        with path.open('xb') as stream:
            stream.write(payload)
    return path
