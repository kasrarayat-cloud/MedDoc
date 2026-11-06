"""The subject of a clause's predicate, read from the text as written (completion repair 2026-11-06; HARNESS.md
"Completion repair (2026-11-06)", builder R2).

A shared primitive. Routing (detect) asks of a statement that something was not done or not completed whose failure it
is: the examination's own ("Cecal intubation was unsuccessful.", "The scope could not be advanced beyond the
stricture."), or a sub-act's or an accessory's ("the polypectomy was unsuccessful", "The snare could not be passed
around the polyp."). The documented-service reader asks the same of its completion statements. Builder A's
bolus-removal binding is written to the same contract (``subject_head``); the integrator unifies the two.

What is read, structurally, from the tokens before the predicate (no tagger, no word list for the grammar itself; the
closed classes below only name what a head IS once the grammar has found it):
- the nearest noun phrase before the predicate is its subject; adverbs right before the predicate ("then",
  "unfortunately") and a comma-delimited or parenthesised aside ("The polypectomy, which was attempted twice, was ...")
  are passed over;
- a prepositional object is climbed to the phrase it modifies ("Hot snare polypectomy of a 14 mm polyp in the sigmoid
  colon was attempted" gives polypectomy, never colon);
- a relative clause inside the subject is passed over ("The snare that was used could not be passed" gives snare); a
  relative pronoun as the subject stands for the noun phrase right before it, and only where that phrase is no
  prepositional object (an attachment the grammar cannot decide is not read);
- an elided subject ("The scope was advanced to the transverse colon and could not be advanced further") is the
  subject of the first predicate of its clause;
- partitive and attempt heads resolve to their complement: "fragments of the bolus" gives bolus, "attempts at cecal
  intubation" gives intubation, "Biopsy attempts" gives biopsy. Both the head and the resolved head are reported;
- a pronoun ("it", "they", "this"), or an attempt with no complement ("the attempt"), stands for an antecedent: the
  subject of the antecedent clause the caller names (the clause before it in its sentence), one level only.

Fail-closed: where any step cannot be read - the window cut inside the subject, a fronted phrase holding it, two noun
phrases run together, an aside that is no aside - the answer is None, and every caller keeps its base reading.

Pure functions, no cache, no reader state. Every scan is bounded: SUBJECT_REACH characters and SUBJECT_TOKENS tokens
before the predicate, RELATIVE_REACH tokens for a relative clause."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Optional

from studio.gi import cues

SUBJECT_REACH = 300  # characters before the predicate read for its subject (bounds the work per predicate)
SUBJECT_TOKENS = 48  # tokens read back at most
RELATIVE_REACH = 12  # tokens a relative clause inside a subject may run before the predicate

_TOKEN = re.compile(r"[A-Za-z][A-Za-z'’/-]*|\d+(?:[.,]\d+)?|[(),;:\[\]]", re.A)
_SPACE = re.compile(r'\s')


def _words(text: str) -> frozenset:
    return frozenset(text.split())


# --- the grammar's closed classes (function words: what stops a noun phrase, what opens an aside) ------------------
PREPOSITIONS = _words('of in at from with on to for into within along near by during after before under over through '
                      'via using across beyond past around toward towards onto upon without about below above between '
                      'among per throughout inside outside behind against like including following involving '
                      'regarding concerning beside besides until up down off despite except')
DETERMINERS = _words('the a an this that these those its their his her our my your each every any some no another '
                     'both either neither such')
AUXILIARIES = _words('was were is are be been being am has have had could would should can will may might must did '
                     'does do shall cannot couldn\'t wasn\'t weren\'t didn\'t')
NEGATORS = _words('not never')
CONJUNCTIONS = _words('and or but nor yet so then')
SUBORDINATORS = _words('while whereas although though because since as if unless when where whereupon once until '
                       'that whether after before however')
RELATIVES = _words('which who whom whose')
PRONOUNS = _words('it this that they these those')  # pronouns that stand for a thing named before
PERSONAL = _words('we i he she you they us them one patient endoscopist physician operator surgeon nurse staff '
                  'assistant team attending fellow anesthesiologist')
ADVERBS = _words('then also still again ultimately unfortunately subsequently finally therefore however thus '
                 'eventually initially originally further nonetheless nevertheless regrettably apparently technically '
                 'later even')
_LY_NOUNS = _words('family anomaly assembly belly jelly ally rally supply')
ASIDE_OPENERS = RELATIVES | PREPOSITIONS | ADVERBS | _words('that as although though while if when despite '
                                                            'including which who')
ATTEMPT_HEADS = _words('attempt attempts try tries effort efforts')
PARTITIVE_HEADS = _words('fragment fragments piece pieces portion portions part parts remnant remnants remainder rest '
                         'most some all several majority half bulk none one two three four five six seven eight nine '
                         'ten')
QUANTITY_WORDS = _words('multiple several many numerous repeated repeat further additional initial first second third '
                        'final subsequent prior previous two three four five six seven eight nine ten few both all '
                        'unsuccessful failed successful')
_COMPLEMENT_PREPOSITIONS = _words('of at for to')  # what an attempt or a part is of

_STOPS = PREPOSITIONS | AUXILIARIES | NEGATORS | CONJUNCTIONS | SUBORDINATORS | RELATIVES
_PUNCTUATION = frozenset(',;:()[]')
_BOUNDARY = frozenset(',;:([')


@dataclass(frozen=True)
class Head:
    start: int
    end: int
    word: str  # lower-cased


@dataclass(frozen=True)
class Subject:
    """The subject of one predicate. ``phrase``: its noun phrase as written, with the phrases attached to it.
    ``head``: the head noun the predicate agrees with. ``resolved``: what a partitive or attempt head resolves to (the
    head itself otherwise; an antecedent's resolved head for a pronoun read through ``antecedent``). ``modifiers``: the
    words before the head inside its own noun phrase. ``attached``: the heads of the phrases attached to it by a
    preposition, outermost first, each with its preposition. ``pronoun``: the head stands for an antecedent (a pronoun,
    or an attempt or a part with no complement); ``antecedent``: the subject it was read through, if any."""
    phrase: tuple[int, int]
    head: Head
    resolved: Head
    modifiers: tuple[Head, ...] = ()
    attached: tuple[tuple[Head, str], ...] = ()
    pronoun: bool = False
    antecedent: Optional['Subject'] = None


@dataclass(frozen=True)
class _Tok:
    start: int
    end: int
    low: str

    @property
    def punct(self) -> bool:
        return self.low in _PUNCTUATION

    @property
    def content(self) -> bool:
        return not self.punct and self.low not in _STOPS


def _tokens(text: str, clause_start: int, predicate_start: int) -> tuple[list[_Tok], bool]:
    """The tokens of [clause_start, predicate_start), at most SUBJECT_REACH characters and SUBJECT_TOKENS tokens back;
    ``cut``: the window does not reach the clause's start (so a subject reaching the window's start is not read)."""
    lo = max(clause_start, predicate_start - SUBJECT_REACH)
    cut = lo > clause_start
    if cut:  # start at a word boundary: a regex reads a cut as the start of a word
        space = _SPACE.search(text, lo, predicate_start)
        if space is None:
            return [], True
        lo = space.end()
    toks = [_Tok(m.start(), m.end(), m.group(0).lower().replace('’', "'"))
            for m in _TOKEN.finditer(text, lo, predicate_start)]
    if len(toks) > SUBJECT_TOKENS:
        toks, cut = toks[-SUBJECT_TOKENS:], True
    return toks, cut


def _adverb(tok: _Tok) -> bool:
    w = tok.low
    return w in ADVERBS or (len(w) > 4 and w.endswith('ly') and w not in _LY_NOUNS)


def _participle(tok: _Tok) -> bool:
    w = tok.low
    return len(w) > 4 and (w.endswith('ed') or w in ('seen', 'found', 'taken', 'given', 'done', 'made', 'left', 'held',
                                                    'shown', 'known', 'drawn', 'withdrawn'))


def _skip_back(toks: list[_Tok], i: int) -> int:
    """The index of the last token before the predicate that may end its subject, past adverbs and asides; -2 when an
    aside cannot be read (a comma with no aside opener, an unmatched parenthesis)."""
    while i >= 0:
        tok = toks[i]
        if tok.punct and tok.low in ')]':
            depth, j = 0, i
            while j >= 0:
                if toks[j].low in ')]':
                    depth += 1
                elif toks[j].low in '([':
                    depth -= 1
                    if depth == 0:
                        break
                j -= 1
            if j < 0:
                return -2
            i = j - 1
            continue
        if tok.low == ',':
            j = i - 1
            while j >= 0 and toks[j].low not in (',', ';', ':', '(', '['):
                j -= 1
            if j < 0 or toks[j].low != ',' or j + 1 >= i:
                return -2  # a comma right before the predicate with no aside to pass over: no subject is read
            opener = toks[j + 1]
            if not (opener.low in ASIDE_OPENERS or _adverb(opener) or _participle(opener)
                    or opener.low.endswith('ing')):
                return -2
            i = j - 1
            continue
        if not tok.punct and _adverb(tok):
            i -= 1
            continue
        return i
    return -1


@dataclass(frozen=True)
class _Phrase:
    start: int  # token index of its first token (a determiner, when it has one)
    head: int  # token index of its head


def _noun_phrase(toks: list[_Tok], i: int) -> Optional[_Phrase]:
    """The noun phrase whose head is token ``i``: content words before it, up to and including a determiner."""
    if i < 0 or not toks[i].content or toks[i].low in DETERMINERS:
        return None
    j = i
    while j - 1 >= 0:
        prev = toks[j - 1]
        if prev.low in DETERMINERS:
            j -= 1
            break
        if not prev.content:
            break
        j -= 1
    return _Phrase(j, i)


def _relative_start(toks: list[_Tok], i: int) -> Optional[int]:
    """The index of a relative pronoun opening a relative clause that runs from it to the predicate ("The snare that
    was used could not be passed"): within RELATIVE_REACH tokens, no clause punctuation between, the pronoun right after
    a content word and followed by a verb (an auxiliary, a negator or a participle) - a 'that' followed by anything else
    is a determiner or a complementizer, never a relative."""
    for r in range(i - 1, max(-1, i - 1 - RELATIVE_REACH), -1):
        tok = toks[r]
        if tok.punct:
            return None
        if tok.low in RELATIVES or tok.low == 'that':
            if r == 0 or not toks[r - 1].content:
                return None
            nxt = toks[r + 1]
            if tok.low == 'that' and not (nxt.low in AUXILIARIES or nxt.low in NEGATORS or _participle(nxt)):
                return None
            return r
    return None


def _first_auxiliary(toks: list[_Tok], end: int) -> Optional[int]:
    return next((k for k in range(0, end) if toks[k].low in AUXILIARIES), None)


def _head(tok: _Tok) -> Head:
    return Head(tok.start, tok.end, tok.low)


def _resolve(toks: list[_Tok], np: _Phrase, chain: list[tuple[Head, str]]) -> tuple[Head, bool]:
    """(resolved head, stands for an antecedent) of a subject phrase: a partitive or an attempt head resolves to the
    phrase its own preposition attaches ("attempts at cecal intubation", "fragments of the bolus"), else to the nearest
    noun before it in its own phrase that is no quantity word ("Biopsy attempts", "repeated cannulation attempts"); with
    neither, it stands for an antecedent ("the attempt", "Multiple attempts")."""
    head = toks[np.head]
    if head.low not in ATTEMPT_HEADS | PARTITIVE_HEADS:
        return _head(head), False
    if chain and chain[-1][1] in _COMPLEMENT_PREPOSITIONS:
        return chain[-1][0], False
    for k in range(np.head - 1, np.start - 1, -1):
        word = toks[k]
        if word.low in DETERMINERS or word.low in QUANTITY_WORDS or not word.content or word.low[:1].isdigit():
            continue
        return _head(word), False
    return _head(head), True


def _walk(toks: list[_Tok], i: int, cut: bool, depth: int = 0) -> Optional[Subject]:
    i = _skip_back(toks, i)
    if i < 0:
        return None
    tok = toks[i]
    if tok.punct:
        return None
    if tok.low in CONJUNCTIONS and depth == 0:
        # an elided subject: the subject of the first predicate of the clause
        k = _first_auxiliary(toks, i)
        if k is None or k == 0:
            return None
        return _walk(toks, k - 1, cut, depth + 1)
    if tok.low in RELATIVES or (tok.low == 'that' and i > 0 and toks[i - 1].content):
        # a relative pronoun as the subject: the noun phrase right before it, never a prepositional object
        j = i - 1
        if j >= 0 and toks[j].low == ',':
            j -= 1
        np = _noun_phrase(toks, j)
        if np is None or (np.start > 0 and toks[np.start - 1].low in PREPOSITIONS):
            return None
        if np.start == 0 and cut:
            return None
        resolved, stands = _resolve(toks, np, [])
        return Subject((toks[np.start].start, toks[np.head].end), _head(toks[np.head]), resolved,
                       tuple(_head(t) for t in toks[np.start:np.head] if t.low not in DETERMINERS), (), stands)
    if tok.low in PRONOUNS:
        return Subject((tok.start, tok.end), _head(tok), _head(tok), pronoun=True)
    if not tok.content:
        return None
    r = _relative_start(toks, i)
    if r is not None:
        i = _skip_back(toks, r - 1)
        if i < 0 or not toks[i].content:
            return None
        tok = toks[i]
    if _participle(tok):
        return None  # a verb, never a noun: an active clause's predicate ends here
    np = _noun_phrase(toks, i)
    if np is None:
        return None
    chain: list[tuple[Head, str]] = []
    while True:
        k = np.start - 1
        if k < 0:
            if cut:
                return None  # the window ends inside the subject: not read
            break
        prep = toks[k].low
        if prep not in PREPOSITIONS:
            break
        j = k - 1
        if j >= 0 and _participle(toks[j]) and j - 1 >= 0 and toks[j - 1].content:
            j -= 1  # a reduced relative: "the polyp seen in the sigmoid colon"
        outer = _noun_phrase(toks, j)
        if outer is None:
            return None  # a fronted phrase holds the subject ("In the sigmoid colon polypectomy was ..."): not read
        chain.append((_head(toks[np.head]), prep))
        np = outer
    k = np.start - 1
    if k >= 0:
        before = toks[k]
        boundary = (before.low in _BOUNDARY or before.low in CONJUNCTIONS or before.low in SUBORDINATORS
                    or toks[np.start].low in DETERMINERS)
        if not boundary:
            return None  # two noun phrases run together: which one is the subject is not read
    resolved, stands = _resolve(toks, np, chain)
    return Subject((toks[np.start].start, toks[np.head].end), _head(toks[np.head]), resolved,
                   tuple(_head(t) for t in toks[np.start:np.head] if t.low not in DETERMINERS),
                   tuple(reversed(chain)), stands)


# The passive auxiliary of a predicate whose matched word is its participle or adjective ("was terminated", "were
# unable to", "was aborted"), read right before that word, with at most one adverb between.
_PASSIVE_LEAD = re.compile(r"\b(?:was|were|is|are|been|being)\s+(?:(?:then|subsequently|eventually|ultimately|finally|"
                           r"therefore|thus|also|again)\s+)?$", re.A | re.I)
_PASSIVE_LEAD_REACH = 40


def predicate_start(text: str, clause_start: int, pos: int) -> int:
    """Where the predicate whose word a reader matched at ``pos`` begins, for its subject: the passive auxiliary right
    before it where there is one ("The procedure [was] terminated", "The scope [was] unable to be advanced"), else
    ``pos`` itself - a match that opens on an auxiliary, a modal or a finite verb ("was unsuccessful", "could not be
    passed", "failed to reach") or an active predicate ("The scope stopped at")."""
    lead = _PASSIVE_LEAD.search(text, max(clause_start, pos - _PASSIVE_LEAD_REACH), pos)
    return lead.start() if lead else pos


def first_predicate(text: str, start: int, end: int) -> Optional[int]:
    """Where the first predicate of the clause [start, end) begins: its first auxiliary or modal ("was attempted",
    "could not be advanced"); None when it has none in its first SUBJECT_TOKENS tokens."""
    toks, _ = _tokens(text, start, min(end, start + SUBJECT_REACH))
    k = _first_auxiliary(toks, len(toks))
    return toks[k].start if k is not None else None


def subject(text: str, clause_start: int, predicate_start: int,
            antecedent: Optional[tuple[int, int]] = None) -> Optional[Subject]:
    """The subject of the predicate starting at ``predicate_start`` in the clause starting at ``clause_start`` (see the
    module's rules), or None when it cannot be read. ``antecedent``: the clause a pronoun or a bare attempt stands for -
    the clause before this one in its sentence; its first predicate's subject is read, one level only, and only a
    subject that is itself no pronoun and no person resolves it."""
    if not (0 <= clause_start <= predicate_start <= len(text)):
        return None
    toks, cut = _tokens(text, clause_start, predicate_start)
    found = _walk(toks, len(toks) - 1, cut)
    if found is None or not found.pronoun or antecedent is None:
        return found
    a0, a1 = antecedent
    if not (0 <= a0 < a1 <= clause_start):
        return found
    predicate = first_predicate(text, a0, a1)
    if predicate is None:
        return found
    toks, cut = _tokens(text, a0, predicate)
    prior = _walk(toks, len(toks) - 1, cut)
    if prior is None or prior.pronoun or prior.resolved.word in PERSONAL:
        return found
    return replace(found, resolved=prior.resolved, antecedent=prior, pronoun=False)


def subject_head(text: str, clause_start: int, predicate_start: int,
                 antecedent: Optional[tuple[int, int]] = None) -> Optional[tuple[int, int, str]]:
    """(start, end, lower-cased word) of the resolved head of the predicate's subject (``subject``), or None. A pronoun
    or a bare attempt that no ``antecedent`` resolves is returned as itself: the caller decides what it stands for."""
    found = subject(text, clause_start, predicate_start, antecedent)
    if found is None:
        return None
    return found.resolved.start, found.resolved.end, found.resolved.word


# --- whose failure: the examination's own, or a sub-act's -----------------------------------------------------------
# Small closed classes of what a subject's head IS. Their failure mode is the safe side: a head in none of them (a
# lesion, a person, a word this list does not know) is no answer, and the caller keeps its base reading.
SCOPES = _words('colonoscope colonoscopes gastroscope gastroscopes endoscope endoscopes scope scopes instrument '
                'instruments enteroscope enteroscopes duodenoscope duodenoscopes sigmoidoscope sigmoidoscopes '
                'echoendoscope echoendoscopes ileoscope colonoscope/gastroscope')
EXAMINATIONS = _words('procedure procedures examination examinations exam exams study studies endoscopy endoscopies '
                      'evaluation')
REACHES = _words('intubation intubations cannulation cannulations insertion insertions advancement advancements '
                 'passage passages traversal traversals reinsertion reintubation entry access reach intubate '
                 'cannulate insert advance traverse')
OBSTRUCTIONS = _words('stricture strictures stenosis narrowing obstruction angulation lumen papilla ampulla duct ducts '
                      'orifice')
SUB_ACTS = _words('polypectomy polypectomies biopsy biopsies dilation dilations dilatation dilatations banding '
                  'ligation ligations injection injections hemostasis resection resections removal removals retrieval '
                  'retrievals extraction extractions clipping coagulation ablation cauterization cautery tattoo '
                  'tattooing marking lithotripsy stenting sampling aspiration brushing '
                  'brushings mucosectomy emr esd dissection apc rfa snaring polypectomy/biopsy remove resect dilate '
                  'clip band inject retrieve extract ligate coagulate ablate')
ACCESSORIES = _words('snare snares net nets basket baskets forceps clip clips hemoclip hemoclips endoclip endoclips '
                     'balloon balloons needle needles band bands stent stents loop loops endoloop endoloops')
GENERIC_ACTS = _words('placement placements deployment application use closure')
EXAMINATION, SUB_ACT = 'examination', 'sub_act'


def _landmark_head(text: str, head: Head) -> bool:
    """Whether a landmark of routing's tables (cues.LOWER_LANDMARKS, cues.UPPER_LANDMARKS) is named AT the head itself
    ("the cecum", "the sigmoid colon", "the second portion of the duodenum"), never only by a modifier ("the sigmoid
    polyp")."""
    lo, hi = max(0, head.start - 40), min(len(text), head.end + 40)
    for _, _, pattern in cues.LOWER_LANDMARKS + cues.UPPER_LANDMARKS:
        for m in pattern.finditer(text, lo, hi):
            if m.start() < head.end and head.start < m.end():
                return True
    return False


def _service_head(text: str, head: Head) -> bool:
    lo, hi = max(0, head.start - 40), head.end
    for _, pattern in cues.SERVICE_PATTERNS:
        for m in pattern.finditer(text, lo, hi):
            if m.start() < head.end and head.start < m.end():
                return True
    return False


def _word_class(text: str, head: Head, words: tuple[Head, ...]) -> Optional[str]:
    w = head.word
    if w in PERSONAL:
        return None
    if w in SCOPES:
        return EXAMINATION
    if w in ACCESSORIES or w in SUB_ACTS:
        return SUB_ACT
    if w in REACHES or w in GENERIC_ACTS:
        if any(o.word in ACCESSORIES or o.word in SUB_ACTS for o in words):
            return SUB_ACT  # "clip placement", "passage of the snare", "insertion of the needle"
        if w in REACHES or any(o.word in SCOPES for o in words):
            return EXAMINATION  # "cecal intubation", "passage of the colonoscope", "biliary cannulation"
        return None
    if w in EXAMINATIONS or _service_head(text, head):
        return EXAMINATION
    if w in OBSTRUCTIONS or _landmark_head(text, head):
        return EXAMINATION
    return None


def failure_of(text: str, found: Optional[Subject]) -> Optional[str]:
    """Whose failure a not-done or not-completed predicate with this subject states: EXAMINATION - the service named
    or referred to ("the procedure"), its scope, its reach or entry ("Cecal intubation"), or a landmark or an obstruction
    it did not reach or pass ("The cecum could not be reached", "the stricture could not be traversed"); SUB_ACT - a
    therapeutic or diagnostic sub-act ("the polypectomy", "Biopsy attempts", "Clip placement") or an accessory ("The
    snare"); None when it cannot be told (an unread or unresolved subject, a pronoun with no antecedent, a person, a
    lesion, any other head), which every caller reads as its base reading."""
    if found is None or found.pronoun:
        return None
    source = found.antecedent if found.antecedent is not None else found
    head = found.resolved
    words = source.modifiers + tuple(h for h, _ in source.attached)
    if head != source.head:  # a partitive or an attempt head: its complement's own phrase is read with it
        words = tuple(o for o in words if o != head)
    return _word_class(text, head, words)
