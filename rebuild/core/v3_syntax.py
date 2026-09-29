"""Bounded, local sentence syntax. This establishes no clinical or destination fact.

No source text is cached globally or sent over a network. Only the pinned parser is
retained between calls. Callers must still apply all source and clinical guards.
"""
import hashlib
import importlib.metadata
import json
import re
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
def _verbs():
    """The already pinned model's finite verb lexicon, never a downloaded list."""
    if _parser() is None: return frozenset()
    package = importlib.metadata.distribution(MODEL)
    path = Path(package.locate_file(f'{MODEL}/{MODEL}-{MODEL_VERSION}/lemmatizer/lookups/lookups.bin'))
    raw = path.read_bytes()
    manifest = json.loads(Path(__file__).with_name('v3_syntax_model.json').read_text())
    if hashlib.sha256(raw).hexdigest() != manifest['lemmatizer/lookups/lookups.bin']: return frozenset()
    from spacy.lookups import Lookups
    return frozenset(Lookups().from_bytes(raw).get_table('lemma_index')['verb'])


def _bare_patient_clause(text, subject_span):
    """Resolve the parser's noun-compound ambiguity for one explicit finite verb.

    The source must be exactly an already-established patient actor and one
    regularly inflected verb, with no object, qualifier, quote or second clause.
    The pinned lexicon rules out noun fragments such as medications/diabetes.
    Source bytes, offsets and all clinical/context checks remain unchanged.
    """
    match = re.fullmatch(r'(?:(?:The|the)\s+)?(?P<actor>[Pp]atient)\s+(?P<verb>[a-z]+)\.', text)
    if match is None or subject_span != match.span('actor'): return False
    word = match['verb']; candidates = {word[:-1]} if word.endswith('s') else set()
    if word.endswith('es'): candidates.add(word[:-2])
    if word.endswith('ies'): candidates.add(word[:-3] + 'y')
    def inflect(base):
        if base.endswith('y') and len(base) > 1 and base[-2] not in 'aeiou': return base[:-1] + 'ies'
        return base + ('es' if base.endswith(('s', 'x', 'z', 'ch', 'sh', 'o')) else 's')
    return any(base in _verbs() and inflect(base) == word for base in candidates)


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


def _present(head):
    """A clause head in the present tense by the pinned parser's morphology: it, or an auxiliary under it, carries
    Tense=Pres ('sees', 'is starting', 'has stopped'), and no modal is among them."""
    tokens = [head] + [child for child in head.children if child.dep_ in ('aux', 'auxpass')]
    return any('Pres' in token.morph.get('Tense') for token in tokens) and not any(token.tag_ == 'MD' for token in tokens)


def _admissible_adverbials(doc, root):
    """Token indices inside adverbial clauses the caller may accept (G-E, 2026-09-29): an `advcl` attached to the root
    whose own subject, when it has one, is a THING (a noun or proper noun that names no person; never a personal or
    demonstrative pronoun), with no modal anywhere inside it. The caller has already refused every unit carrying a
    scope reframer or pointer (`INHERITED_SCOPE`), so 'if'/'would'/'could'/'might' clauses never reach this.
    ⚠️ R1-9 (repair, 2026-09-29): BOTH clauses must be in the present tense by the parser's morphology. A past clause
    bounded by another ('The patient attended the clinic every week until the order expired.', '... before the order
    lapsed.') describes a state that ENDED, and a present clause bounded by a past one is not proven current either."""
    from .v3_actors import names_person
    allowed = set()
    if not _present(root):
        return allowed
    for head in root.children:
        if head.dep_ != 'advcl':
            continue
        inner = list(head.subtree)
        if any(token.tag_ == 'MD' for token in inner) or not _present(head):
            continue
        subjects = [token for token in inner if token.dep_ in ('nsubj', 'nsubjpass')]
        if any(token.pos_ not in ('NOUN', 'PROPN') or names_person(token) for token in subjects):
            continue
        allowed.update(token.i for token in inner)
    return allowed


@lru_cache(maxsize=1)
def _reader():
    """The same verified bytes as `_parser`, with the model's own rule lemmatizer kept (its lookups file is in the
    manifest). Used only by the actor reader (`v3_actors`) and the readers built on its reading; `_parser` and every
    existing caller are unchanged. The entity recognizer stays excluded: measured on this model it tags drugs PERSON
    ('Lisinopril 10 mg daily.', 'Apixaban was discontinued ...', 'Morphine was given.', a label's 'Urine') and misses
    names ('Ahmed', 'Priya', 'Wei'), so it cannot say who a sentence is about (repair, 2026-09-29)."""
    if _parser() is None:
        return None
    try:
        import spacy
        package = importlib.metadata.distribution(MODEL)
        directory = Path(package.locate_file(f'{MODEL}/{MODEL}-{MODEL_VERSION}'))
        return spacy.load(directory, exclude=['ner'])
    except (ImportError, OSError, ValueError, KeyError, importlib.metadata.PackageNotFoundError):
        return None


def docs(texts):
    """Parse bounded source texts with `_reader`, in order: a list with a Doc per text, or None in its place when that
    text is out of bounds (over `MAX_CHARACTERS` characters or `MAX_TOKENS` tokens); None instead of the list when the
    verified model is missing or the parser fails. Every caller fails closed on a None."""
    texts = list(texts)
    bounded = [index for index, text in enumerate(texts) if isinstance(text, str) and 0 < len(text) <= MAX_CHARACTERS]
    try:
        with _lock:
            reader = _reader()
            if reader is None:
                return None
            parsed = list(reader.pipe((texts[index] for index in bounded), batch_size=32))
    except (ValueError, TypeError, RuntimeError, OSError, KeyError, importlib.metadata.PackageNotFoundError):
        return None
    out = [None] * len(texts)
    for index, doc in zip(bounded, parsed):
        out[index] = doc if len(doc) <= MAX_TOKENS else None
    return out


def _complete(doc, subject_span=None, adverbial=False):
    if len(doc) > MAX_TOKENS or len(list(doc.sents)) != 1:
        return False
    sentence = next(iter(doc.sents))
    root = sentence.root
    if root.pos_ not in ('VERB', 'AUX'):
        return False
    # An adverbial clause is accepted only when the caller asked for it (explicit-patient units and pronouns already
    # resolved to the patient) and only in the admissible shape above. Everything else is exactly as before.
    inside = _admissible_adverbials(doc, root) if adverbial else set()
    # Only a simple declarative clause gets this additional syntax allowance.
    # Quoted/embedded, relative, conditional, passive and infinitival clauses
    # need a separately qualified source relation, not inferred actor/scope.
    if any(token.tag_ == 'MD' or (token.dep_ in ('ccomp', 'xcomp', 'advcl', 'relcl', 'acl', 'parataxis', 'csubj', 'csubjpass', 'auxpass')
                                  and not (token.dep_ == 'advcl' and token.i in inside))
           for token in doc):
        return False
    finite = [token for token in [root, *root.children]
              if (token is root or token.dep_ in ('aux', 'auxpass'))
              and 'Fin' in token.morph.get('VerbForm')]
    subjects = [token for token in root.children if token.dep_ in ('nsubj', 'nsubjpass')]
    if not finite or len(subjects) != 1 or min(t.i for t in subjects) >= min(t.i for t in finite):
        return False
    # A second explicit subject in a coordinated clause is a separate actor;
    # shared-subject coordination retains just this one subject token.
    if sum(token.dep_ in ('nsubj', 'nsubjpass') and token.i not in inside for token in doc) != 1:
        return False
    if any(token.dep_ == 'conj' for token in subjects[0].children):
        return False
    if subject_span is not None:
        subject = subjects[0]
        if (subject.idx, subject.idx + len(subject.text)) != subject_span:
            return False
        # The caller's exact actor phrase permits only its leading determiner.
        # Apposition, compounds or other nominal qualifiers need explicit review.
        if any(token.i != subject.i and not (token.dep_ == 'det' and token.i < subject.i
                   and token.text.casefold() == 'the') for token in subject.subtree):
            return False
    words = [token for token in doc if not token.is_punct and not token.is_space]
    # A dangling conjunction, preposition or determiner is not a complete sentence.
    return bool(words and words[-1].pos_ not in ('CCONJ', 'SCONJ', 'ADP', 'DET', 'AUX', 'PART'))


def complete_ids(units, *, subject_spans=None, adverbial=frozenset()):
    """Syntax proof for at most 64 bounded source units in their original order.

    A missing model, excess unit, long text or parser error yields no new allowance.
    Input strings and offsets remain untouched. The caller passes only sentences
    which lack the existing finite-word proof, never labelled values or options.
    When the caller supplies already established actor spans, syntax must bind
    that exact token to the sole subject; it cannot invent or expand the actor.
    `adverbial`: unit ids for which one admissible adverbial clause is accepted (`_admissible_adverbials`).
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
                if subject_spans is not None and unit['id'] not in subject_spans:
                    continue
                span = None if subject_spans is None else subject_spans[unit['id']]
                if _complete(doc, span, unit['id'] in adverbial) or _bare_patient_clause(unit['quote'], span):
                    result.add(unit['id'])
            return result
    except (ValueError, TypeError, RuntimeError, OSError, KeyError, importlib.metadata.PackageNotFoundError):
        return set()
