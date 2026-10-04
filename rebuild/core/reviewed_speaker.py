"""Complete headed clinician reports under an immutable transcript review.

The speaker remains the clinician. The full report or directive, including its
complete complement, remains the answer; no patient predicate is synthesized.
"""


def frames(reading, docs, proof):
    from . import generation as g, v3_actors as a
    units = reading['units']
    fields = {key: matches[0] for key, matches in reading['named'].items()
              if len(matches) == 1 and matches[0].get('kind') in ('text', 'long_text')
              and not matches[0].get('write_protected')}
    headings = {key: [i for i, u in enumerate(units)
                     if u['quote'].casefold() == f['label'].strip().rstrip(':').casefold() + '.']
                for key, f in fields.items()}
    bodies = {positions[0] + 1: key for key, positions in headings.items()
              if len(positions) == 1 and positions[0] + 1 < len(units)}
    result = {}
    for index, (unit, doc) in enumerate(zip(units, docs)):
        if index not in bodies or not proof['start'] <= unit['start'] < unit['end'] <= proof['end']:
            continue
        info = reading['actors'][unit['id']]
        if (not info.get('readable') or info.get('other_floor')
                or reading['resolved'][unit['id']].get('self_other')
                or info.get('past_time') or info.get('habitual') or info.get('dependent')
                or info.get('bounded') or info.get('bare_cessation') or info.get('ceased_keys')):
            continue
        words = [t for t in doc if not t.is_punct and not t.is_space]
        if (len(list(doc.sents)) != 1
                or any(t.pos_ in ('PRON', 'PROPN') or a.names_person(t)
                       or t.text in ('"', '“', '”', '‘', '’') for t in doc)
                or any(t.tag_ == 'MD' for t in doc)):
            continue
        verbs = [t for t in doc if t.pos_ == 'VERB' and 'Fin' in t.morph.get('VerbForm')]
        if len(verbs) == 1:
            verb = verbs[0]
            subjects = [t for t in verb.children if t.dep_ == 'nsubj']
            if (len(subjects) != 1 or not a.names_carer(subjects[0])
                    or a._lemma(verb) not in ('document', 'direct') or verb.tag_ != 'VBZ' or a._negates(verb)):
                continue
            action = a._lemma(verb)
            subject = subjects[0]
            subject_words = list(subject.subtree)
            if (any(t != subject and not (t.dep_ == 'det' and a._fold(t.text) == 'the') for t in subject_words)
                    or not any(t.dep_ == 'det' and a._fold(t.text) == 'the' for t in subject.children)
                    or any(t not in subject_words and not (t.dep_ == 'advmod' and t.head == verb)
                           for t in words if t.i < verb.i)):
                continue
        elif (not verbs and len(words) > 3 and a._fold(words[0].text) == 'the'
                and a._fold(words[1].text) in a.CARE_NOUNS
                and a._fold(words[2].text) in ('documents', 'directs')):
            # The pinned parser reads "The clinician documents a possible ..."
            # as ADJ + plural NOUN, despite its unambiguous present-tense speech
            # frame. Verify that exact subject/inflected-verb surface and the
            # original closed complement below; never rephrase the source.
            verb = words[2]
            action = a._fold(verb.text)[:-1]
        else:
            continue
        if action == 'direct' and bodies[index] not in g.PLAN_FIELDS:
            continue
        # Read the original complete complement. Re-parsing a clipped value
        # mis-tags "rest" as a name and changes the grammatical noun "strain";
        # the original dependency graph supplies their actual object roles.
        complement = [t for t in words if t.i > verb.i]
        heads = [t for t in complement if t.dep_ == 'ROOT' or t.dep_ == 'dobj' and t.head == verb]
        if (not heads or any(t.pos_ != 'NOUN' for t in heads)
                or any(t.pos_ in ('PRON', 'PROPN') or a.names_person(t) or a.names_carer(t)
                       for t in complement)):
            continue
        if action == 'document':
            if any(t.pos_ not in ('NOUN', 'ADJ', 'DET', 'NUM', 'CCONJ')
                   or t.dep_ not in ('ROOT', 'dobj', 'amod', 'compound', 'det', 'nummod', 'conj', 'cc')
                   for t in complement):
                continue
        else:
            if any(t.dep_ not in ('ROOT', 'dobj', 'amod', 'compound', 'det', 'nummod', 'conj', 'cc',
                                 'prep', 'pobj', 'acl', 'advmod', 'npadvmod')
                   or t.pos_ not in ('NOUN', 'ADJ', 'DET', 'NUM', 'CCONJ', 'ADP', 'ADV', 'VERB')
                   for t in complement):
                continue
            if any(t.pos_ == 'VERB' and not (
                    t.tag_ == 'VBN' and t.dep_ == 'acl'
                    or t.tag_ == 'VB' and t.dep_ == 'compound' and t.head.pos_ == 'NOUN'
                    and any(c.text == '-' for c in t.head.children)) for t in complement):
                continue
            # A FOR recipient is not the patient merely because the clinician
            # speaks. Retain bounded durations and a material modifier of an
            # existing reduced passive; never infer a recipient from a noun.
            time_words = set(a.SOLE_LEXICON['time'].split())
            bad_preposition = False
            for preposition in (t for t in complement if t.dep_ == 'prep'):
                objects = [t for t in preposition.children if t.dep_ == 'pobj']
                if len(objects) != 1:
                    bad_preposition = True
                    break
                obj = objects[0]
                inside = list(obj.subtree)
                duration = bool(a._lemma(obj) in time_words
                    and all(t == obj or t.pos_ in ('NUM', 'DET') for t in inside)
                    and (any(t.pos_ == 'NUM' for t in inside)
                         or a._lemma(preposition) == 'at' and a._lemma(obj) == 'time'))
                material = bool(a._lemma(preposition) == 'in' and preposition.head.tag_ == 'VBN'
                    and preposition.head.dep_ == 'acl' and obj.pos_ == 'NOUN'
                    and all(t.pos_ in ('NOUN', 'ADJ', 'DET') for t in inside))
                if not (a._lemma(preposition) in ('for', 'in', 'at') and duration or material):
                    bad_preposition = True
                    break
            if bad_preposition:
                continue
        if (any(a._fold(t.text) != 'and' for t in complement if t.dep_ == 'cc')
                or any(g.SELF_CORRECTION.search(s) or g.INHERITED_SCOPE.search(s)
                       for s in g.safety_readings(unit['quote']))):
            continue
        result[unit['id']] = bodies[index]
    return result
