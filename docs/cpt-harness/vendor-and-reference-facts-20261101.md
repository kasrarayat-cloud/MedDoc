# CPT harness: vendor and reference-source facts (retrieved 2026-11-01)

The facts the harness adapters and the reference layer are built on. Every value was read on 2026-11-01 from the
publisher's own page at the URL given. No API call was made, no credential was read, and no licence click-through was
accepted. Two read-only research agents fetched the pages; the session read their reports and the skill reference for
the Claude API, and recorded only what the sources state. "Not stated" is written where a source is silent.

## 1. Astra: OpenAI GPT-6 Astra (owner-confirmed identity)

| fact | value | source |
|---|---|---|
| model id | `gpt-6-astra`; "Default snapshot: `gpt-6-astra`"; no other snapshot or alias listed | https://developers.openai.com/api/docs/models/gpt-6-astra |
| endpoint | `POST https://api.openai.com/v1/responses` (also Chat Completions, Batch) | same |
| limits | 1,050,000 context; 922,000 max input; 128,000 max output; knowledge cutoff Apr 30, 2026 | same |
| reasoning | `reasoning.effort`: `low`, `medium`, `high`, `xhigh`, `max`; API default `medium` | same; https://developers.openai.com/api/reference/resources/responses/methods/create |
| structured output | `text: {format: {type: "json_schema", name, schema, strict}}`. `name` is at most 64 characters. With `strict`, every field must be `required`, `additionalProperties: false` is mandatory, and the root must be an object | https://developers.openai.com/api/docs/guides/structured-outputs |
| refusal / truncation | A refusal is a `refusal` content item that "does not necessarily follow the schema". Truncation gives `status: "incomplete"`, reason `max_output_tokens` | same |
| file input | `input_file` with `file_data` (`data:application/pdf;base64,…` plus `filename`), `file_id` or `file_url`; under 50 MB. The model page lists inputs "text, image"; the file-input guide's examples use `gpt-6-astra` | https://developers.openai.com/api/docs/guides/file-inputs |
| identity | Response header `x-request-id`. Optional request header `X-Client-Request-Id` (ASCII, at most 512 characters, unique per request, logged). Response `id` `resp_…` | https://developers.openai.com/api/reference/overview |
| usage | `input_tokens`, `input_tokens_details.cached_tokens`, `output_tokens`, `output_tokens_details.reasoning_tokens`, `total_tokens` | responses create reference |
| returned model | `model`: "Model ID used to generate the response, like `gpt-6-astra`" | same |
| price (standard, per 1M tokens) | $10 input, $1 cached input, $50 output. Above 272K input tokens: 2x input, 1.5x output | https://developers.openai.com/api/docs/pricing |
| retention | `store` defaults to true (30-day application state); `store: false` turns it off. Abuse monitoring up to 30 days. ZDR needs OpenAI's approval | https://developers.openai.com/api/docs/guides/your-data |
| errors | 429 rate limit (honour `Retry-After`). 429 quota codes ("Retrying ... won't restore API access"). 500 retry after a wait. 503 `server_is_overloaded` | https://developers.openai.com/api/docs/guides/error-codes |
| access check | `GET https://api.openai.com/v1/models/gpt-6-astra` returns `{id, object, created, owned_by}` | https://developers.openai.com/api/reference/resources/models/methods/retrieve |
| credentials | Platform API keys only: "For general OpenAI API calls, continue to use Platform API keys." Codex `~/.codex/auth.json` holds access tokens and is not an API key | https://learn.chatgpt.com/docs/auth |
| not stated | an idempotency key for `POST /v1/responses`; whether `model` can come back dated | — |

## 2. Fable: Anthropic Claude Fable 5.1 (owner-confirmed identity)

| fact | value | source |
|---|---|---|
| model id | `claude-fable-5-1`: "is not an alias. It is the snapshot." Released September 1, 2026; retirement not sooner than September 1, 2027 | https://platform.claude.com/docs/en/models/fable-5-1/overview |
| endpoint and headers | `POST https://api.anthropic.com/v1/messages`. The key goes in `x-api-key` or `Authorization: Bearer` ("accepts a key in either header"). `anthropic-version` required (current `2026-10-21`). `anthropic-workspace-id` is required only with a key not scoped to a workspace | https://platform.claude.com/docs/en/api/overview |
| limits | 1M context (default and maximum); 128K max output | https://platform.claude.com/docs/en/models/fable-5-1/whats-new-fable-5-1 |
| request constraints | Adaptive thinking is always on; `thinking` `enabled` or `disabled` returns 400. Depth is set by `output_config.effort` (`low`…`max`; default `high`). `temperature`, `top_p` and `top_k` return 400. Prefill returns 400. Forced `tool_choice` `any`/`tool` returns 400 | same |
| structured output | `output_config: {format: {type: "json_schema", schema}}`, stable, no beta header. `additionalProperties: false` is required. Not supported: recursive schemas, numeric and length constraints. At most 16 union-type parameters | https://platform.claude.com/docs/en/build-with-claude/structured-outputs |
| caveats | A refusal is HTTP 200 with `stop_reason: "refusal"` (plus `stop_details` category); its output "might not match your schema". A `max_tokens` stop "might be incomplete". A schema property that asks for reasoning "might lead to a `reasoning_extraction` refusal". "Do not include PHI in JSON schema definitions." | same |
| PDF input | `document` block, `source: {type: "base64", media_type: "application/pdf", data}`. 128 MB per request; up to 600 pages | https://platform.claude.com/docs/en/build-with-claude/pdf-support |
| identity | Response header `request-id` (`req_…`); message `id` `msg_…` | https://platform.claude.com/docs/en/api/errors |
| usage | `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`, `output_tokens_details.thinking_tokens`, `service_tier` | https://platform.claude.com/docs/en/api/messages/create |
| fallback | Server-side fallback is opt-in (`fallbacks` plus beta header). Without it the `model` field names the model that answered. **CPT Studio never sends `fallbacks`**: the owner forbids silent model substitution | https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback |
| price (per 1M tokens) | $10 input, $50 output; cache write $12.50 (5 min); cache read $0.25 | https://platform.claude.com/docs/en/models/fable-5-1/overview |
| retention | A "Covered Model": "require 30-day data retention; ZDR is therefore not available ... unless expressly authorized". An organisation without retention gets a 400 | https://platform.claude.com/docs/en/manage-claude/api-and-data-retention |
| errors | 400, 401, 402 `billing_error`, 403, 404, 409, 413, 429 (a spend-cap 429 has no `retry-after`), 500, 504 `timeout_error` ("use streaming"), 529 `overloaded_error` | https://platform.claude.com/docs/en/api/errors |
| access check | `GET https://api.anthropic.com/v1/models/claude-fable-5-1` returns `id`, `display_name`, `max_input_tokens`, `max_tokens` and `capabilities`. A successful models GET may not prove a Messages call will succeed (the retention check is not stated for it) | https://platform.claude.com/docs/en/api/models/retrieve |

## 3. Reference sources and their use terms

| source | release / effective | where | terms as published |
|---|---|---|---|
| CMS PFS relative value file RVU26D (`rvu26d-updated-08-26-2026.zip`, sha256 `521ff0f4…8406e6`; its documentation `RVU26D.pdf`, sha256 `8aba8efb62e86a804bd8791ecefeef254da94de37a2391156de1415ce6a7e278`) | RVU26D, released 08/26/2026; CPT Studio window 2026-10-01 to 2026-12-31 | https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu26d | No licence gate. "intended for Medicare purposes". Inside: "CPT codes and descriptions only are copyright 2026 American Medical Association." The CSV carries a DESCRIPTION column (CPT descriptors), which CPT Studio never reads |
| CMS NCCI practitioner MUE table 2026-Q4 (sha256 `4574336755ba…180d00`) | effective Oct. 1, 2026 | https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-medically-unlikely-edits | Direct link, no gate. AMA notice in the file header. No descriptor column |
| CMS NCCI Policy Manual for Medicare Services 2026, Chapter VI "Surgery: Digestive System CPT Codes 40000-49999" | Revision 1/1/2026 | https://www.cms.gov/files/document/06-chapter6-ncci-medicare-policy-manual-2026-final.pdf | No licence gate. AMA notice. §C "Endoscopic Services" has 16 rules; some quote a CPT description in parentheses (never imported) |
| CMS Claims Processing Manual Pub. 100-04, Chapter 12 | Rev. 13753, issued 05-07-26; §40.6 "(Rev. 1, 10-01-03)" | https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/clm104c12.pdf | No notice in the text; public manual |
| CMS NCCI practitioner PTP edits v323r0 (2026 Q4) | effective Oct. 1, 2026 | https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-procedure-procedure-ptp-edits | **Every edit file goes through the AMA "End User Point and Click Agreement"**: use "limited to use in Medicare, Medicaid or other programs administered by CMS"; prohibits "any commercial use of CPT"; "The scope of this license is determined by the AMA". **Not accepted, not imported**: a new agreement, which the directive excludes |

### The AMA's published position (https://www.ama-assn.org/practice-management/cpt/cpt-licensing-frequently-asked-questions-faqs, updated Jul 14, 2026)

- "Any entity using CPT content anywhere worldwide must have a license authorizing the use of CPT code set from the AMA or an authorized distributor."
- Its list of uses that need a licence and royalty includes "Use of CPT content to develop, test, maintain and service products that use or rely on CPT".
- "Using the CPT Standard Data File to train, fine-tune, or improve AI models is prohibited." "Uploading the CPT Standard Data File into public, unrestricted, or open-market AI systems is prohibited."

**What follows for the harness.**
- CPT Studio holds no AMA licence, and no source read supports its own note that internal synthetic evaluation needs
  none. This predates the harness and is an owner question; it is recorded as a known limit (`cpt-studio/HARNESS.md`
  §10).
- The harness sends no CPT data file and no descriptor to any vendor, and trains nothing.
- It retrieves only CMS text, and does not import passages that quote a CPT description.
