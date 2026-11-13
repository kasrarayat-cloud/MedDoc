"""The contract of design v2 (docs/gemini-migration/FINAL-V2.md, adopted as DECISIONS D178): what Gemini is asked, and
how its two answers are read, checked, claimed and settled into one EventInventory row (FINAL-V2 1-3).

It is the only package of the new path that touches document text, and only as FINAL-V2 5.6 allows: segmentation by
character classes (segment), quote location (geometry, fold), the transcription check of a date Gemini gave against its
own words (date_literals, read by consistency's L1 alone) and revision binding. Its modules, by the step of 8.1 that
owns each: types and jsonschema (0b); segment (1a); extract_schema and extract_read (1b); geometry, fold and
date_literals (1c); extract_prompt (2a); consistency (2b); claims, appraise_schema, appraise_prompt and appraise_read
(2c); settle and checks (3a).

It executes no v1 code: no module here imports one of the 17 retired v1 modules (5.0), and what it copies from them
(jsonschema's generator, fold, the date parsers) is proved equal to v1's by test. The static rules of FINAL-V2 5.7
measure 4 hold here: NoWordLists over every module; WordsNeverDecide over settle, claims and consistency;
SingleCharacterGeometry over segment and geometry.

This module holds no code and imports nothing, so importing the package loads nothing else.
"""
