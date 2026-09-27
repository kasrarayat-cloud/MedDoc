"""Bounded, local sentence syntax. This establishes no clinical or destination fact.

No source text is cached globally or sent over a network. Only the pinned parser is
retained between calls. Callers must still apply all source and clinical guards.
"""
import hashlib
import importlib.metadata
import json
from functools import lru_cache
from pathlib import Path
from threading import Lock

MODEL = 'en_core_web_sm'
MODEL_VERSION = '3.8.0'
LIBRARY_VERSION = '3.8.16'
MAX_CHARACTERS = 1000
MAX_TOKENS = 128
MAX_UNITS = 64
_lock = Lock()


@lru_cache(maxsize=1)
def _parser():
    """Load installed, verified bytes only. No download or alternate model path."""
    try:
        if (importlib.metadata.version('spacy') != LIBRARY_VERSION
                or importlib.metadata.version(MODEL) != MODEL_VERSION):
            return None
        import spacy
        package = importlib.metadata.distribution(MODEL)
        directory = Path(package.locate_file(f'{MODEL}/{MODEL}-{MODEL_VERSION}'))
        manifest = json.loads(Path(__file__).with_name('v3_syntax_model.json').read_text())
        for relative, expected in manifest.items():
            if hashlib.sha256((directory / relative).read_bytes()).hexdigest() != expected:
                return None
        # The entity recognizer and lemmatizer are not needed for this syntax check.
        return spacy.load(directory, exclude=['ner', 'lemmatizer'])
    except (ImportError, OSError, ValueError, KeyError, importlib.metadata.PackageNotFoundError):
        return None


def _complete(doc):
    if len(doc) > MAX_TOKENS or len(list(doc.sents)) != 1:
        return False
    sentence = next(iter(doc.sents))
    root = sentence.root
    if root.pos_ not in ('VERB', 'AUX'):
        return False
    # Only a simple declarative clause gets this additional syntax allowance.
    # Quoted/embedded, relative, conditional, passive and infinitival clauses
    # need a separately qualified source relation, not inferred actor/scope.
    if any(token.tag_ == 'MD' or token.dep_ in ('ccomp', 'xcomp', 'advcl', 'relcl', 'acl', 'parataxis', 'csubj', 'csubjpass', 'auxpass')
           for token in doc):
        return False
    finite = [token for token in [root, *root.children]
              if (token is root or token.dep_ in ('aux', 'auxpass'))
              and 'Fin' in token.morph.get('VerbForm')]
    subjects = [token for token in root.children if token.dep_ in ('nsubj', 'nsubjpass')]
    if not finite or len(subjects) != 1 or min(t.i for t in subjects) >= min(t.i for t in finite):
        return False
    if any(token.dep_ == 'conj' for token in subjects[0].children):
        return False
    words = [token for token in doc if not token.is_punct and not token.is_space]
    # A dangling conjunction, preposition or determiner is not a complete sentence.
    return bool(words and words[-1].pos_ not in ('CCONJ', 'SCONJ', 'ADP', 'DET', 'AUX', 'PART'))


def complete_ids(units):
    """Syntax proof for at most 64 bounded source units in their original order.

    A missing model, excess unit, long text or parser error yields no new allowance.
    Input strings and offsets remain untouched. The caller passes only sentences
    which lack the existing finite-word proof, never labelled values or options.
    """
    candidates = [unit for unit in units[:MAX_UNITS]
                  if isinstance(unit.get('quote'), str) and 0 < len(unit['quote']) <= MAX_CHARACTERS]
    if not candidates:
        return set()
    try:
        with _lock:
            parser = _parser()
            if parser is None:
                return set()
            result = set()
            for unit, doc in zip(candidates, parser.pipe((u['quote'] for u in candidates), batch_size=16)):
                if _complete(doc):
                    result.add(unit['id'])
            return result
    except (ValueError, TypeError, RuntimeError):
        return set()
