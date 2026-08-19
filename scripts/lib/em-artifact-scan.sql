-- ===========================================================================
-- F12-g — THE PROJECTION. READ-ONLY, AND IT IS A PROJECTION AND NOTHING MORE.
-- ---------------------------------------------------------------------------
-- ⚠️ THIS FILE DOES NOT DECIDE ANYTHING. It does not re-implement
-- `emAppliesToVisit`, it does not filter on the verdict, and it must never
-- start to. F12-g's own filing records what an SQL re-implementation costs: one
-- with the specialty axis approximated answered **19** where the shipped
-- predicate answers **15**, and the 19 was carried into a ledger row before it
-- was caught. Every verdict is taken in TypeScript, from the module production
-- runs. This query's whole job is to hand that module its inputs.
--
-- ⚠️ PHI POSTURE — NO NOTE BODY LEAVES THE DATABASE.
-- `noteHeadingLines` emits only lines matching `^[ \t]*#{1,6}[ \t]+`, which is
-- a strict PREFIX of `NOTE_SECTION_HEADING_RE` in note-shape.ts:
--
--     SQL   ^[ \t]*#{1,6}[ \t]+
--     TS    ^[ \t]*#{1,6}[ \t]+(.+?)[ \t]*$
--
-- Any line the shipped regex accepts necessarily matches this one, so the
-- heading list derived downstream is IDENTICAL to the one that would be derived
-- from the whole note — the filter cannot MISS a heading. It can in principle
-- over-select (its condition is weaker), and `assertNoBodyText` in
-- em-artifact-scan.ts asserts that it did not, which is the PHI control as much
-- as the correctness one. Do not relax this pattern without moving that proof.
--
-- ⚠️ `signedSoap` BEFORE `soapFinal` — that is the rule every read path uses to
-- decide which text to render, and `emAppliesToVisit`'s own doc-comment names
-- it. Reading `soapFinal` on a signed visit would classify a document nobody is
-- looking at.
--
-- ⚠️ THE JOIN CARRIES NO STATUS FILTER, DELIBERATELY. `noteTemplateId` is
-- FROZEN on the visit and every production read path joins the template without
-- filtering on `status` — so a RETIRED template goes on classifying signed
-- visits forever. Adding a filter here would measure a system that does not
-- exist. (That frozen-retired-template shape is the mechanism F12-d found on a
-- live signed row.)
--
-- `jsonb_typeof` is selected on both JSONB columns so the SHAPE of the data is
-- a measurement rather than an assumption — a `#>>` path read against a column
-- that turns out not to be an object returns NULL and looks exactly like a
-- clean row.
-- ===========================================================================
select coalesce(json_agg(row_to_json(r)), '[]'::json)::text
from (
  select
    v.id                                       as "visitId",
    v.specialty                                as "specialty",
    (v."signedAt" is not null)                 as "signed",
    v."emScoredCode"                           as "emScoredCode",
    (v."cptCodes" #>> '{em,code}')             as "cptEmCode",
    (v."cptCodes" #>> '{em,override,code}')    as "cptEmOverrideCode",
    (v."cptCodes" #>> '{em,signedCode}')       as "cptEmSignedCode",
    (v."emPendingChange" is not null)          as "emPendingChange",
    (v."cptCodes" #>> '{emSuppressed}')        as "cptEmSuppressed",
    t.sections                                 as "templateSections",
    jsonb_typeof(v."cptCodes")                 as "cptCodesType",
    jsonb_typeof(t.sections)                   as "templateSectionsType",
    -- ⚠️ THE KEY-SET CONTROL, AND IT EXISTS BECAUSE THE REFUTATION PASS FOUND A
    -- LATENT FALSE GREEN. The scanner reads three fixed paths under `em`
    -- (`code`, `override.code`, `signedCode`). An `em` OBJECT carrying state
    -- under some FOURTH key would read as a perfectly clean row — silently, and
    -- indistinguishably from a row that really is clean.
    --
    -- `check-imaging-em-artifacts.sh` guards its own version of this by testing
    -- KEY EXISTENCE (`"cptCodes" ? 'em'`), and its comment says so explicitly.
    -- ⚠️ COPYING THAT HERE WOULD BE WRONG, AND THE CORPUS IS WHAT SAYS SO:
    -- measured 2026-08-19, **17 of 27** rows carrying the `em` key hold JSON
    -- `null` — `{"em": null}`, an EXPLICIT RECORD OF NO E/M LEVEL, which is the
    -- opposite of stale state. Bare key existence would flag **5** of them as
    -- artifacts. Prior art solved a different question; measuring chose this
    -- predicate.
    --
    -- So the shape is: keep the narrow paths, and make an UNKNOWN KEY a loud
    -- CANNOT-TELL rather than a silent clean. Measured today: every one of the
    -- 10 object-typed rows carries `code`, so nothing escapes — the control has
    -- ZERO instances and exists for the row nobody has written yet.
    jsonb_typeof(v."cptCodes"->'em')           as "cptEmType",
    case when jsonb_typeof(v."cptCodes"->'em') = 'object'
         then (select json_agg(k order by k)
                 from jsonb_object_keys(v."cptCodes"->'em') k)
    end                                        as "cptEmKeys",
    coalesce((
      select string_agg(line, E'\n')
      from unnest(
        string_to_array(coalesce(v."signedSoap", v."soapFinal"), E'\n')
      ) as line
      where line ~ '^[ \t]*#{1,6}[ \t]+'
    ), '')                                     as "noteHeadingLines"
  from transcribe_visits v
  left join note_templates t on t.id = v."noteTemplateId"
  order by v."createdAt"
) r;
