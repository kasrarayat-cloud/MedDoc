# THE FAILED-BUT-BILLED `ai_calls` ROWS — A ONE-TIME PRESERVING EXTRACT

**Taken 2026-08-09T21:02Z against production (`meddoc`), READ-ONLY.**
**42 rows survive. DISCOVERY §C.3 counted 44 on 2026-08-04.**

---

## 1. WHAT THIS IS

A verbatim snapshot of every row in production's `ai_calls` matching

```sql
success = false AND "inputTokens" > 0
```

— real vendor calls that **failed our validation after the vendor had already
counted the tokens**. The vendor billed them; the product produced nothing from
them. They are the only record that those charges happened.

Cost-accounting fields only. §5 states exactly what was excluded and why.

## 2. WHY IT EXISTS — the rows are being destroyed by the product working normally

**`ai_calls` has four production deleters.** Nothing else can lower the count,
and none of them is a fault — every one is a feature behaving correctly:

| # | Path | Predicate | Note |
|---|---|---|---|
| 1 | `api/settings/delete-account/route.ts:189` | `deleteMany({ practiceId })` | **PRACTICE-WIDE.** Needs no visit linkage — it takes every row the practice ever produced, in one transaction |
| 2 | `api/visits/[id]/delete/route.ts:92` | `deleteMany({ visitId })` | already-trashed + `?permanent=1` → hard purge |
| 3 | `api/visits/[id]/delete/route.ts:149` | `deleteMany({ visitId })` | `QUEUED` + no input → immediate hard delete |
| 4 | `worker/cleanup/stale-visits.ts:73` | `deleteMany({ visitId: { in: ids } })` | scheduled retention, `deletedAt < now − 15d`, **across all practices** |

Measured attrition:

```
2026-08-04 (DISCOVERY §C.3) ....... 44
2026-08-09 (B2 §2.5 baseline) ..... 42
2026-08-09 (this extract) ......... 42        net −2 in five days ⇒ ~0.4 rows/day
```

⚠️ **BUT THE MEAN RATE IS THE WRONG INSTRUMENT, AND IT UNDERSTATES THE RISK.**
Deleter 1 is practice-wide and atomic, so the loss is a **step function, not a
drip**. One practice holds **24 of the 42 rows (57%) and $1.08 of the $1.50
(72%)**. A single account deletion by that practice erases the majority of this
evidence in one transaction, on whatever day it happens. "0.4 rows/day" is a
two-point estimate of a bursty process; it is not a schedule, and nothing about
it is a reason to feel there is time.

**And there is no second copy.** The 2026-08-09 ruling *"The durable meter's
PROVENANCE REGIME begins at B0-a — no pre-regime call is ever INSERTED into it"*
(**ruling 79**; ruling numbers here are LINE NUMBERS in `RULINGS.md`, so cite the
title if the number ever drifts) settles that these charges **never become meter
rows**.

⚠️ **Read that boundary precisely, because the loose version of it is false.**
`api_usage_events` is not empty before B0-a — it holds **1325** rows, earliest
**2026-06-15**, of which **1312** predate B0-a's deploy (**2026-08-08T18:40Z**).
What begins at B0-a is the **provenance regime**, not the table's population, and
B0-a itself backfilled `unitsSource='vendor'` onto all 1312. The forbidden act is
narrower and different: **INSERTING a new row for a call the meter never
recorded**, which would assert conformance with a regime that postdates the call.
Every one of the 42 rows below predates that boundary — latest **2026-08-03T23:44Z**,
count on or after B0-a: **0** — so they are legacy observability by definition.
**The preservation is this document. There is no other.**

## 3. WHAT THE 42 ROWS ARE

| | |
|---|---|
| rows | **42** (of 1125 `ai_calls` total — 3.7%) |
| window | 2026-06-17T03:58Z → 2026-08-03T23:44Z |
| cost | **150 cents = $1.50** (`costUsdCents` non-null on all 42) |
| input tokens | 141,834 |
| output tokens | 51,858 |
| cache read / write tokens | 0 / 0 |
| provider | anthropic, 42 of 42 |
| vendor request ids present | **0 of 42** — see §4 |

**By failure code** — two values, both ours, neither vendor text:

| `errorCode` | rows |
|---|---|
| `SCHEMA_FAIL` | 26 |
| `JSON_PARSE_FAIL` | 16 |

**By model** — `claude-sonnet-4-6` 24 · `claude-opus-4-8` 18

**By purpose** — `tm_entities` 17 · `tm_rx_drafting` 12 · `tm_template_parse` 5 ·
`tm_cpt_coding` 4 · `tm_patient_summary` 2 · `tm_critique` 1 · `tm_icd_coding` 1

**By month** — 2026-06: 2 rows / 4¢ · 2026-07: 34 / 125¢ · 2026-08: 6 / 21¢

**By practice** — and this is the concentration that makes §2's warning concrete:

| practice | rows | cents | window |
|---|---|---|---|
| `cmo5ye2nf000b01s3q0xlkaxb` | **24** | **108** | 2026-07-07 → 2026-08-03 |
| `cmrzqiafm0000pd87qtubsj56` | 15 | 35 | 2026-07-25 → 2026-08-03 |
| `clinic_main` | 2 | 4 | 2026-06-17 |
| `cmrz9r0u4001x01oax66pj87p` | 1 | 3 | 2026-07-24 |

**Visit linkage** — 34 of 42 carry a `visitId`; 8 do not. The 8 are not safer
for it: deleter 1 keys on `practiceId` and takes them regardless.

**Retries** — all 42 `promptHash` values are distinct, so there is no
duplicate-charge retry *inside* this population; and **no successful call in
`ai_calls` shares a `promptHash` with any of the 42**, so within the limits of
hash-equality none of these failures was re-run to success on an identical
prompt. (A retry that changed the prompt at all would hash differently, so this
bounds the claim rather than proving no retry ever occurred.)

## 4. RECONCILING THIS AGAINST A VENDOR INVOICE — the join key is NOT the request id

**`requestId` is NULL on all 42 rows**, and no backfill can change that. The
column did not exist when any of these calls was made — it was created by
`20260809010000_b1a_ai_calls_request_id` on **2026-08-09**, and the newest row
here is from **2026-08-03**. The vendor's id for these calls was never received
by this process, so there is no source to backfill *from*; the column is
included in §6 for shape, uniformly empty.

So a future reconciliation — B3's `nova-3-medical` invoice conversation, or any
Anthropic statement — **must key on `(created_utc, model, input_tokens,
output_tokens)`**, not on a vendor correlation id. That is a weaker key, it is
the only one these rows have, and discovering it at reconciliation time rather
than here would be discovering it too late.

⚠️ **Per ruling 79 these rows are explicitly OUT OF SCOPE for B9
reconciliation** (pre-go-live months). §4 exists for the vendor-invoice
question, which is a different question and is not scoped out.

## 5. WHAT WAS **EXCLUDED**, AND WHY — the premise this extract had to correct

**The universe first, so the accounting is checkable rather than implied.**
`ai_calls` has **18** columns. §6 publishes **15** (plus a synthetic `seq`); three
are withheld — `errorDetails` and `promptHash` for the reasons below, and
`success`, which is **constant `false` by the selection predicate** and so carries
no information. 15 + 3 = 18, reconciles.

The task was framed as *"no clinical content exists in these rows, verify that
claim before writing."* **Verified, and it is false for one column.**

**`errorDetails` is EXCLUDED.** `schema.prisma:1634` documents it as:

> *T-M17.1: raw model response body on failed calls, capped at ~10 KB by the
> writer. NULL on success. **May contain PHI** (same envelope as
> `transcribe_visits` columns). Not surfaced in UI; psql-only.*

Measured on this exact population: **non-null on 42 of 42, max length 10,240 —
the cap, exactly.** The column is `NULL on success`, so it is populated
*precisely* on the rows this extract selects. The one field that carries
clinical content is the one field this population is guaranteed to have.

It is also not a cost-accounting field, so nothing is lost. But the reasoning
matters more than the outcome: had the premise been taken at its word, a
committed repository file would have carried up to 42 × 10 KB of raw model
output generated from clinical input — into every future clone, permanently, and
recoverable only by the `git filter-repo` rewrite this repository has already
paid for twice.

**`promptHash` is EXCLUDED** — a SHA-256 of prompt content, PHI-safe by
construction and sanctioned as such by its own schema comment, but not a
cost-accounting field. Its only cost-relevant use, retry correlation, is
answered in §3 as a *derived* fact, so the hashes themselves need not be
published.

Everything in §6 is an identifier, an enum, an integer, or a timestamp. The
extract was scanned for prose and non-printable content with the matcher
positive-controlled against a canary line carrying a clinical sentence: **canary
1 hit, extract 0 hits.** A scan that finds nothing and a broken scan produce the
same output, which is why the control is reported beside the zero.

## 6. THE EXTRACT

Boundary: production database `meddoc`, table `ai_calls`, predicate
`success = false AND "inputTokens" > 0`, ordered by `createdAt`, taken
2026-08-09T21:02Z. `vendor_request_id` is empty on every row (§4).

```csv
seq,id,created_utc,practice_id,visit_id,purpose,provider,model,input_tokens,output_tokens,cache_read_tokens,cache_create_tokens,cost_usd_cents,latency_ms,error_code,vendor_request_id
1,cmqhjjdy9001p0ujztbpxbqgs,2026-06-17T03:58:13Z,clinic_main,cmqhjhuug00016sjzn5zpi3mr,tm_icd_coding,anthropic,claude-sonnet-4-6,5114,601,0,0,2,8265,SCHEMA_FAIL,
2,cmqhjjgqk001s0ujzd0vh7a1o,2026-06-17T03:58:16Z,clinic_main,cmqhjhuug00016sjzn5zpi3mr,tm_patient_summary,anthropic,claude-sonnet-4-6,2516,500,0,0,2,11879,JSON_PARSE_FAIL,
3,cmrazpqa0001w0uphnb81isyb,2026-07-07T18:36:21Z,cmo5ye2nf000b01s3q0xlkaxb,cmrazmdea003801mss8w7c6bz,tm_rx_drafting,anthropic,claude-opus-4-8,4238,125,0,0,2,3013,JSON_PARSE_FAIL,
4,cmrwp6tvx000e0upi1row3q7d,2026-07-22T23:12:39Z,cmo5ye2nf000b01s3q0xlkaxb,cmrwp5fsf00000to6olw3kj8i,tm_rx_drafting,anthropic,claude-opus-4-8,4845,90,0,0,3,2599,JSON_PARSE_FAIL,
5,cmrwtrqf4000801pl50cucka4,2026-07-23T01:20:53Z,cmo5ye2nf000b01s3q0xlkaxb,,tm_template_parse,anthropic,claude-opus-4-8,5121,1456,0,0,6,16167,SCHEMA_FAIL,
6,cmrx4liqm000d01n2jt8zxpq2,2026-07-23T06:23:59Z,cmo5ye2nf000b01s3q0xlkaxb,,tm_template_parse,anthropic,claude-opus-4-8,5121,2118,0,0,8,21932,SCHEMA_FAIL,
7,cmrx6luks00180urz1o1gb7lk,2026-07-23T07:20:14Z,cmo5ye2nf000b01s3q0xlkaxb,cmrx6k9yn00000tp0jhdu6lix,tm_rx_drafting,anthropic,claude-opus-4-8,4746,116,0,0,3,3305,JSON_PARSE_FAIL,
8,cmrx6m0d8001f0urz0f8h29mo,2026-07-23T07:20:21Z,cmo5ye2nf000b01s3q0xlkaxb,cmrx6kcre00000tnwc8k9ncs4,tm_patient_summary,anthropic,claude-sonnet-4-6,1096,611,0,0,1,12855,JSON_PARSE_FAIL,
9,cmrxlqrw9002a0upixzn1v9fw,2026-07-23T14:23:58Z,cmo5ye2nf000b01s3q0xlkaxb,cmrxlpm66000e01ptepwnqjfq,tm_cpt_coding,anthropic,claude-sonnet-4-6,2095,573,0,0,1,14779,SCHEMA_FAIL,
10,cmry5c5fh001h0upgbwgykmkx,2026-07-23T23:32:28Z,cmo5ye2nf000b01s3q0xlkaxb,cmry4y7lq001a01o53uu3efvu,tm_cpt_coding,anthropic,claude-sonnet-4-6,2113,867,0,0,2,19978,SCHEMA_FAIL,
11,cmrzap71l000x0up839tfo21g,2026-07-24T18:50:21Z,cmrz9r0u4001x01oax66pj87p,cmrzane7k002v01oaqsnnvavg,tm_rx_drafting,anthropic,claude-opus-4-8,5061,102,0,0,3,2665,JSON_PARSE_FAIL,
12,cmrzug3lk00120ule77cpif2m,2026-07-25T04:03:08Z,cmrzqiafm0000pd87qtubsj56,cmrzufbss002w01qzg6fiysbf,tm_rx_drafting,anthropic,claude-opus-4-8,3124,119,0,0,2,2813,JSON_PARSE_FAIL,
13,cmrzugdpt001c0ule12p5snuo,2026-07-25T04:03:22Z,cmrzqiafm0000pd87qtubsj56,cmrzufbss002w01qzg6fiysbf,tm_cpt_coding,anthropic,claude-sonnet-4-6,1410,573,0,0,1,15928,JSON_PARSE_FAIL,
14,cmrzupaku001v0uleipbh7ke7,2026-07-25T04:10:17Z,cmrzqiafm0000pd87qtubsj56,cmrzuoecu004001qzyl0erhm8,tm_rx_drafting,anthropic,claude-opus-4-8,4068,90,0,0,2,2594,JSON_PARSE_FAIL,
15,cmrzupfq300210ulekzllo1j6,2026-07-25T04:10:24Z,cmrzqiafm0000pd87qtubsj56,cmrzuoecu004001qzyl0erhm8,tm_cpt_coding,anthropic,claude-sonnet-4-6,2147,510,0,0,1,9262,SCHEMA_FAIL,
16,cms18514q004z0imutp1ta8aa,2026-07-26T03:14:13Z,cmrzqiafm0000pd87qtubsj56,,tm_entities,anthropic,claude-sonnet-4-6,1926,2025,0,0,4,22320,SCHEMA_FAIL,
17,cms18bh7d004z0ip4e76svq7k,2026-07-26T03:19:14Z,cmrzqiafm0000pd87qtubsj56,,tm_entities,anthropic,claude-sonnet-4-6,1932,2024,0,0,4,20163,SCHEMA_FAIL,
18,cms18d3s400020iqtpe5ffzw0,2026-07-26T03:20:30Z,cmrzqiafm0000pd87qtubsj56,,tm_entities,anthropic,claude-sonnet-4-6,1914,1912,0,0,3,18727,SCHEMA_FAIL,
19,cms199rd300000un153y2mt9j,2026-07-26T03:45:53Z,cmo5ye2nf000b01s3q0xlkaxb,cms1995gf000d01ml5crf6wqf,tm_entities,anthropic,claude-sonnet-4-6,2048,2616,0,0,5,24430,SCHEMA_FAIL,
20,cms1f9qip000601ntnypeqcel,2026-07-26T06:33:50Z,cmo5ye2nf000b01s3q0xlkaxb,,tm_template_parse,anthropic,claude-opus-4-8,5117,1776,0,0,7,18538,SCHEMA_FAIL,
21,cms1fk3pu00000uqnpryy3fe3,2026-07-26T06:41:53Z,cmo5ye2nf000b01s3q0xlkaxb,cms1fjiz6000i01ntfxd9sy0c,tm_entities,anthropic,claude-sonnet-4-6,2046,2619,0,0,5,24276,SCHEMA_FAIL,
22,cms2e60tr00000ur5y4tpjxvp,2026-07-26T22:50:43Z,cmo5ye2nf000b01s3q0xlkaxb,cms2e4k6w000m01od9f7nj5vv,tm_entities,anthropic,claude-sonnet-4-6,2044,2616,0,0,5,24260,SCHEMA_FAIL,
23,cms2qg6jq00000ur50c92psv2,2026-07-27T04:34:32Z,cmo5ye2nf000b01s3q0xlkaxb,cms2qfn4g000i01uri6javo2t,tm_entities,anthropic,claude-sonnet-4-6,2046,2616,0,0,5,23576,SCHEMA_FAIL,
24,cms2qhl93000f0ur533aem236,2026-07-27T04:35:38Z,cmo5ye2nf000b01s3q0xlkaxb,cms2qfn4g000i01uri6javo2t,tm_rx_drafting,anthropic,claude-opus-4-8,6173,134,0,0,3,3219,JSON_PARSE_FAIL,
25,cms3iqz9800000upcte7xjg9y,2026-07-27T17:46:45Z,cmrzqiafm0000pd87qtubsj56,cms3iq9m8000701mkqm1y2fu5,tm_entities,anthropic,claude-sonnet-4-6,1824,1613,0,0,3,15381,SCHEMA_FAIL,
26,cms3jx86z000w01mk20q9dquy,2026-07-27T18:19:37Z,cmo5ye2nf000b01s3q0xlkaxb,,tm_template_parse,anthropic,claude-opus-4-8,5117,1834,0,0,7,19606,SCHEMA_FAIL,
27,cms3k1tdj000o0upco08vah50,2026-07-27T18:23:11Z,cmo5ye2nf000b01s3q0xlkaxb,cms3k19d2001801mkyarrlq57,tm_entities,anthropic,claude-sonnet-4-6,2052,2623,0,0,5,23386,SCHEMA_FAIL,
28,cms3k3ds500130upcv3j0sw5q,2026-07-27T18:24:24Z,cmo5ye2nf000b01s3q0xlkaxb,cms3k19d2001801mkyarrlq57,tm_rx_drafting,anthropic,claude-opus-4-8,6289,154,0,0,4,3429,JSON_PARSE_FAIL,
29,cms3ml92m001n01mk10qhdugp,2026-07-27T19:34:17Z,cmo5ye2nf000b01s3q0xlkaxb,,tm_template_parse,anthropic,claude-opus-4-8,5117,1489,0,0,6,16324,SCHEMA_FAIL,
30,cms3mt6xa00000umi3rlvy457,2026-07-27T19:40:27Z,cmrzqiafm0000pd87qtubsj56,cms3msa3l000301pasyxmpv83,tm_entities,anthropic,claude-sonnet-4-6,1832,1539,0,0,3,15912,SCHEMA_FAIL,
31,cms3mu6a9000k0umi9h41j5bl,2026-07-27T19:41:13Z,cmrzqiafm0000pd87qtubsj56,cms3msa3l000301pasyxmpv83,tm_rx_drafting,anthropic,claude-opus-4-8,4127,141,0,0,2,2948,JSON_PARSE_FAIL,
32,cms3p72mf00000uog6fh8o4bs,2026-07-27T20:47:14Z,cmrzqiafm0000pd87qtubsj56,cms3p6h5u000301mzfc708hxd,tm_entities,anthropic,claude-sonnet-4-6,1682,888,0,0,2,10485,SCHEMA_FAIL,
33,cms40mcit001m0uoggwetp3oe,2026-07-28T02:07:02Z,cmo5ye2nf000b01s3q0xlkaxb,cms40jr2i002v01mzn9z5r8w1,tm_entities,anthropic,claude-sonnet-4-6,2235,2903,0,0,5,30127,SCHEMA_FAIL,
34,cms40o3y0001y0uogrz4vud3w,2026-07-28T02:08:25Z,cmo5ye2nf000b01s3q0xlkaxb,cms40jr2i002v01mzn9z5r8w1,tm_critique,anthropic,claude-opus-4-8,7930,588,0,0,5,8551,JSON_PARSE_FAIL,
35,cms40ob4n00230uogq1637knw,2026-07-28T02:08:34Z,cmo5ye2nf000b01s3q0xlkaxb,cms40jr2i002v01mzn9z5r8w1,tm_rx_drafting,anthropic,claude-opus-4-8,7352,136,0,0,4,3607,JSON_PARSE_FAIL,
36,cms4d8jfi00000urpnw0waqbi,2026-07-28T08:00:13Z,cmrzqiafm0000pd87qtubsj56,cms4d7t1a000f01o7bi89hfkf,tm_entities,anthropic,claude-sonnet-4-6,1792,1401,0,0,3,15347,SCHEMA_FAIL,
37,cmsclemcx00000ulon1umujuy,2026-08-03T02:11:03Z,cmrzqiafm0000pd87qtubsj56,cmsclehdz000d01pey84zdb4o,tm_entities,anthropic,claude-sonnet-4-6,2180,503,0,0,1,5684,SCHEMA_FAIL,
38,cmsclfism000l0ulo9sqzr951,2026-08-03T02:11:45Z,cmrzqiafm0000pd87qtubsj56,cmsclehdz000d01pey84zdb4o,tm_rx_drafting,anthropic,claude-opus-4-8,2872,76,0,0,2,1822,JSON_PARSE_FAIL,
39,cmscvo6nc000f0uv1vz58ot4s,2026-08-03T06:58:26Z,cmrzqiafm0000pd87qtubsj56,cmscvnfor001601n0kfhcvzcd,tm_rx_drafting,anthropic,claude-opus-4-8,2847,97,0,0,2,3379,JSON_PARSE_FAIL,
40,cmscw9oo6001f0uv1mzrynhiz,2026-08-03T07:15:09Z,cmo5ye2nf000b01s3q0xlkaxb,cmscw67y9003m01n0wu9t6zhb,tm_entities,anthropic,claude-sonnet-4-6,2877,3550,0,0,6,34833,SCHEMA_FAIL,
41,cmsdpkyam000p0upccca4gze6,2026-08-03T20:55:43Z,cmo5ye2nf000b01s3q0xlkaxb,cmsdpk2v3001001qlf7vq1lb5,tm_entities,anthropic,claude-sonnet-4-6,2727,2106,0,0,4,21914,SCHEMA_FAIL,
42,cmsdvlgwd000q0uuuwea4dlzm,2026-08-03T23:44:05Z,cmo5ye2nf000b01s3q0xlkaxb,cmsdvjgf5000m01mmbs0srykk,tm_entities,anthropic,claude-sonnet-4-6,2921,3428,0,0,6,34898,SCHEMA_FAIL,
```

## 7. WHAT THIS DOCUMENT DOES NOT DO

- **It does not stop the deletion.** The four deleters are correct behaviour and
  are not being changed; ruling 77 already governs the one that is scheduled.
  This is a copy, taken before the originals go.
- **It does not bill anyone.** Ruling 79 puts these charges outside the meter
  and outside B9. This is evidence, retained; it is not a ledger entry.
- **It does not establish a rate.** Two measurements five days apart are two
  measurements. §2 says why the mean is the wrong instrument anyway.
- **It goes stale the moment it is written**, and that is fine — its value is
  that it is a fixed point. Re-deriving the population later returns whatever
  survives then; **ruling 59's standing shape** — re-derive the population at
  execution time, never copy a figure out of a document — applies to any future
  action, and the figures here are a record, never an input.
