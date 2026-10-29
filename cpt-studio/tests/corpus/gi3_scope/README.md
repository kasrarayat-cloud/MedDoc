# Today's visit versus future follow-up (synthetic) — a regression corpus, not an accuracy measure

**What it measures.** Whether a document documents today's office visit, read only from the document's own markers (a
visit title in its head naming no other occurrence, a heading naming today's visit, a visit statement outside plan and
history, a chief complaint, reason or MDM heading, MDM, or the visit's own time), and whether a future occurrence named
in the plan (a return visit, labs, imaging, a repeat procedure) is ever read as doubt about it (interpretations 43 and
44 of the CPT Studio GI ruling record). At 51b2185f8 the known cases h2-07 and h2-08 were not routed as office visits,
and their E/M codes were held with the plan's follow-up quoted as the reason today's visit was uncertain.
`tests/test_repairs_gi3_scope.py` (`ScopeCorpusTests`) reads every case here.

**Where it comes from.** `variants.json` holds the 87 source-reviewed variants of the gi3 scope investigation (session
7c8d38da, 2026-10-29) over 63 texts: clinic notes with today's visit and a future follow-up, each with two citation
sets; the known cases h2-07 and h2-08 (author's text and the text the live service read), h2-01, and the controls h2-06
and ho-04; Word-table headers; history controls; planned-only documents (a scheduling letter, appointment reminders, a
pre-visit plan, a recall letter, a referral, a "Scheduled visit" title, a pre-charted note); procedure reports that name
a follow-up visit or a repeat; visit statements naming a future service; and probes of procedure, sedation and
interpretation times and of titles on procedure reports. Layouts: plain, the live service's (blank lines dropped), PDF
line wraps, OCR-like and Word tables (" | "). Every text is fictional and opens with the synthetic banner.

**Each case** holds its text, a synthetic provider selection whose evidence passages are exact substrings of it
(`cited`), the source-reviewed expectation (`expected`), its one-line review (`review`), and the verdict inputs the
review fixed (`verdict`): the facts the source leaves undocumented (a question about them is right), the visit's
documented minutes, whether a procedure was done the same day (a separate-E/M question is then right), the procedures
done today, and a date of service the source states twice (a conflict to ask). No reading of any revision is stored
here: the expectations come from the source, never from a reader.

**Known limits** (`known_limits.json`): the cases that read wrong by their source at the commit that added this corpus,
each with its exact output and its reason - the dates repair's (h2-08's charge-block date; a "follow-up" title that
opens a plan section over the header), notes with no marker (held, never excluded), planned-only documents read as a
visit (held, never ready), a procedure day's time read as E/M time (held, never ready), and the extent lens's office
flexible sigmoidoscopy. A known limit that comes to read right fails the test and is removed deliberately; a new wrong
case is a regression.

It measures only the phrasings written into it.
