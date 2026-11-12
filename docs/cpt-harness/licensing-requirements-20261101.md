<!-- Prepared 2026-11-01 by a read-only research agent for the integration owner; quotes spot-checked by the owner of the integration against the saved source copies (Corti S1 2.6.1.9, 2.5.5.4; AMA S10 develop/test). Decides nothing: D3 and D4 stay open. -->

# CPT Studio: CPT licensing review for the owner (draft, 2026-11-01)

**Status.** D3 and D4 stay **OPEN** (owner, 2026-11-01). This document decides nothing. It separates what documents actually grant from what the repository assumes, and lists the decisions left for the owner.

**How it was done.** Everything was read only. Nothing was accepted, clicked, signed up for or sent. No API call was made and no credential file was read. Nothing behind a gate was downloaded, and the NCCI PTP quarterly change file was not downloaded. The AMA agreement page on cms.gov was read as a page; its Accept button was not used and no file behind it was requested. All sources were retrieved 2026-11-01, 22:24–22:36Z.

## Sources

| key | document, as shown | URL | how it was read |
|---|---|---|---|
| S1 | Corti Master Terms of Service, "Effective September 1, 2026" (no version label) | https://www.corti.ai/legal/master-terms-of-service | direct |
| S2 | Corti docs, CPT coding page | https://docs.corti.ai/coding/cpt.md | direct |
| S3 | Corti API reference, Predict Codes | https://docs.corti.ai/api-reference/codes/predict-codes.md | direct |
| S4 | Corti DPA, Subcontractor BAA, Terms and Conditions, Agentic Services Addendum ("Effective July 1, 2026"), Subprocessors; help article "Medical codes" | https://corti.ai/legal/… ; https://help.corti.app/en/articles/10268916-medical-codes | direct. No CPT, AMA or code-set licence text in any of them. The docs compliance page returned HTTP 403 and was not available |
| S5 | OpenAI Services Agreement, "Updated: December 1, 2025", "Effective: January 1, 2026" | https://openai.com/policies/services-agreement/ | openai.com returned 403; read from the Internet Archive capture of 2026-10-28T23:03Z |
| S6 | OpenAI Service Terms, "Updated: October 16, 2026" | https://openai.com/policies/service-terms/ | Internet Archive capture of 2026-10-28T15:36Z |
| S7 | OpenAI Usage Policies, version "Effective: November 20, 2026" | https://openai.com/policies/usage-policies/ | Internet Archive capture of 2026-11-01T07:17Z |
| S8 | Anthropic Commercial Terms of Service, "Effective Jun 17, 2025" | https://www.anthropic.com/legal/commercial-terms | direct |
| S9 | Anthropic Usage Policy, version "Effective Nov 12, 2026" | https://www.anthropic.com/legal/aup | direct |
| S10 | AMA, "CPT® licensing frequently asked questions (FAQs)", "Updated Jul 14, 2026" | https://www.ama-assn.org/practice-management/cpt/cpt-licensing-frequently-asked-questions-faqs | direct. The older AMA licensing pages (health IT vendors, overview, user proxy model, apply, delivery organizations) now redirect here |
| S11 | AMA, CPT Developer Program page (undated) | https://www.ama-assn.org/practice-management/cpt/cpt-developer-program | direct |
| S12 | AMA press release, Jan 19, 2022; AMA article, Mar 14, 2022 | …/press-center/ama-press-releases/ama-opens-doors-health-tech-innovators-cpt-developer-program ; …/practice-management/cpt/medicine-s-language-cpt-opens-developers-test-innovations | direct |
| S13 | AMA "Multi-Product Clickwrap Internal Use License Agreement", MPCIULA/21092022 (PDF dated 2022-09-30) | https://compliance.ama-assn.org/hc/en-us/article_attachments/9255259076759 | public attachment. A 2022 template; whether it is current is not stated |
| S14 | AMA "Maps License Agreement" with "AI ADDENDUM", PAMLA/30072026F (PDF dated 2026-07-30). It licenses SNOMED CT-to-CPT maps, **not the CPT code set** | https://compliance.ama-assn.org/hc/en-us/article_attachments/42501277660183 | public attachment |
| S15 | CMS PFS Relative Value Files page; RVU26D page | https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files ; …/rvu26d | direct |
| S16 | RVU26D as pinned (zip sha256 `521ff0f4…8406e6`; RVU26D.pdf `8aba8efb…`) | local copies; hashes match the repository pins | read locally |
| S17 | CMS MUE page; practitioner MUE table 2026-Q4 as pinned (zip `45743367…0d00`) | https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-medically-unlikely-edits-mues | page direct; file read locally |
| S18 | NCCI Policy Manual page; Chapter VI PDF (local copy, sha256 `c1d2dc0d…`) | …/medicare-ncci-policy-manual ; https://www.cms.gov/files/document/06-chapter6-ncci-medicare-policy-manual-2026-final.pdf | page direct; PDF read locally |
| S19 | Claims Processing Manual Ch. 12, Rev. 13753 (local copy, sha256 `71689eed…`) | https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/clm104c12.pdf | read locally |
| S20 | CMS NCCI PTP edits page | …/medicare-ncci-procedure-procedure-ptp-edits | direct |
| S21 | "License for Use of Current Procedural Terminology … End User Point and Click Agreement" | https://www.cms.gov/license/ama?file=/files/zip/medicare-ncci-2026q4-practitioner-ptp-edits-ccipra-v323r0-f1.zip | the HTML page only, with redirects off. **Not accepted** |

## (A) Documented coverage

**No document read grants CPT Studio, or the owner, any right to use CPT content for CPT Studio's uses.** That covers code numbers as well as descriptors, for development, testing, display, reports and AI processing. What documents do grant is below. Each item is a vendor's own rights or open access to public files. None of them is an AMA right.

| # | what the document grants | exact words | source | does it cover CPT? |
|---|---|---|---|---|
| A1 | Corti assigns its own rights in Output to the customer | "If and to the extent Corti has any rights in such Output, Corti hereby assigns those rights to Customer." (§5.4.1) | S1 | No. It names no AMA right. §6.5.6: "Corti does not own or control such third-party content" |
| A2 | Corti lets the customer build Output into its own products for end customers, on conditions (A) to (F) | "Customer may incorporate Output generated through API usage into Customer's own software products or services for distribution to its end customers without Corti's prior written approval so long as…" (§2.6.1.1; also §2.6.2, §2.7) | S1 | Corti's own permission only |
| A3 | OpenAI: the customer owns Output, and OpenAI assigns its rights, if any | "Customer: (a) retains all ownership rights in Input; and (b) owns all Output." (§4.1) | S5 | No |
| A4 | OpenAI: an indemnity against IP claims over Output. This is not a licence | covers "any third party claim that Customer's use or distribution of Output infringes a third party's intellectual property right". It does not apply where "(iv) Customer or its End Users did not have the right to use the Input", among other exclusions (§1(a)) | S6 | No |
| A5 | Anthropic: permission to use the Services to power the customer's own products | "including to power products and services Customer makes available to its own customers and end users" (§A.1) | S8 | No |
| A6 | Anthropic: the customer owns Outputs, and Anthropic assigns its rights, if any | "Anthropic hereby assigns to Customer its right, title and interest (if any) in and to Outputs." (§B) | S8 | No |
| A7 | Anthropic: an IP indemnity for paid use. This is not a licence | "…or Outputs generated through such authorized use violates any third-party intellectual property right" (§K.1). Exclusions in §K.3 include "(b) the combination of the Services or Outputs with technology or content not provided by Anthropic; (c) Inputs or other data provided by Customer" | S8 | No |
| A8 | CMS: RVU26D, the MUE table, Policy Manual Ch. VI and Claims Manual Ch. 12 are direct downloads with no gate | direct links (S15, S17, S18) | S15–S19 | No. This is access, not a grant. CMS states: "This information relates to payment under the Medicare physician fee schedule and is intended for Medicare purposes." (S15) The files carry AMA notices (section C) |
| A9 | AMA | none held. Repository: "No CPT edition is licensed." | — | No |
| A10 | AMA point-and-click on cms.gov (PTP files) | would authorize internal use of CPT inside CMS materials only (section C) | S21 | Not accepted, so no coverage |

## (B) Assumptions not documented

1. **CPT Studio's own source note.** `cpt-studio/studio/reference/importers.py:27-28` says: "Used for internal synthetic evaluation only; commercial CPT use requires an AMA license." It is stored on every CMS source row and shown in the UI (`studio/static/studio/app.js:943`). Read as a permission, it implies internal synthetic evaluation needs no licence. No source supports that.
   - The AMA lists "Use of CPT content to develop, test, maintain and service products that use or rely on CPT" among uses where "a license and royalty payment are required" (S10).
   - No AMA page read mentions synthetic data, an exemption or an exception.
   - `HARNESS.md:429` already says such text is "a statement of current use, never a claim of permission".
2. **"No gate means usable."** Interpretation 2 (`rulings/2026-10-23-cpt-studio-gi.md:300-304`) uses CMS files that have no click-through "for internal synthetic evaluation". The sources show the files are ungated but grant nothing (A8). The repository itself recorded "Public source availability is not a licence" (`docs/foundation/mutations/20261016-corti-bounded-output-repair.md:16`).
3. **Code numbers without descriptors as the licensing line.** This is assumed by interpretation 1, HARNESS invariant I9 and the vendor-facts file (`vendor-and-reference-facts-20261101.md:68`). No source draws this line.
   - The AMA: "If your organization uses, references or displays CPT content, your organization is expected to obtain the appropriate license for your use case." (S10)
   - The CMS file notices name "CPT codes" (S16) and "CPT codes, descriptions and other data" (S17, S18).
4. **"Descriptors never read" is not "descriptors never held."**
   - The pinned RVU26D zip, which contains the DESCRIPTION column, is copied into `cpt-studio-files/reference/` (`docs/foundation/mutations/20261023-cpt-studio-install.md`).
   - Corti returns `display`, "Description of the medical code" (S3). CPT Studio keeps it in the raw response bytes and in `provider_display`: "It may be stored for diagnosis" (`cpt-studio/ARCHITECTURE.md:37`).
   - No source addresses storing descriptor text without displaying it.
5. **The 2026-10-16 Corti assessment** (`rebuild/ops/fixtures/corti_output_review.json:122`; `docs/foundation/mutations/20261016-corti-bounded-output-repair.md:9-16`) reads: "Corti Master Terms v4 §§2.6.1.1, 2.6.2 and 2.7 permit API-output incorporation". That is documented, but only for Corti's own terms.
   - It says itself that it "grants no independent CPT catalogue rights".
   - Its scope was QuillMD's `internal_fictional_review`, not CPT Studio.
   - The label "v4" does not appear on the page as read today, which shows "Effective September 1, 2026".
   - It recorded: "No separate account agreement found in available protected records."
6. **"The existing authorized Corti account"** (`rulings/2026-10-23-cpt-studio-gi.md:281`) records the owner's authorization to use the account. It is not a CPT right.
7. **Checklist row 1.4** (`CPT-HARNESS-CHECKLIST.md:46`) calls RVU26D, MUE, Policy Manual Ch. VI and Claims Manual Ch. 12 "usable". That is accurate about access, but it is not a permissions finding, although the row's title says "permitted uses".
8. **"The harness sends no CPT data file and no descriptor to any vendor"** (`vendor-and-reference-facts-20261101.md:68`) is true but narrower than the licensing question. As designed, CPT code numbers go to OpenAI and Anthropic in three ways (`HARNESS.md` §11.1–11.2):
   - in `cms_code_facts` results;
   - in CMS policy passages;
   - in peer review: Corti's selected codes and the other model's codes.
9. **"A login-protected synthetic demonstration is not a public clinical launch"** (interpretation 4, `rulings/…:310`) frames the product. No licence source uses "public launch" as a threshold. The 2022 AMA internal-use template excludes "making available the Licensed Content in any unsecured environment or public computer-based information system, including the internet" (S13 §6).
10. **"Synthetic-only."** It matters for patient data. No AMA, CMS or vendor source read treats synthetic documents differently for CPT use.
11. **The QuillMD handoff** (`docs/coding-cpt-licensing-handoff.md:13`, "The accepted provider is Anthropic") was written for QuillMD. It does not cover CPT Studio's three participants (Corti, OpenAI, Anthropic).

## (C) What each existing provider agreement says about downstream CPT rights

**Corti.**
- **Signed agreement: not available.** Your signed Order Form, any account-specific agreement and the version you accepted are not public and not in the repository. A signed Order Form ranks first where it "expressly modifies or supplements these Terms and is signed by both parties" (S1 §11.8.1). Updates bind by use: "Continued use of the Corti Services after the effective date of such updates constitutes acceptance of the updated terms." (§11.10.2)
- **Public terms (S1).** The terms body never mentions CPT, the AMA or code sets; the only CPT mention is the site menu, "AI ICD-10 & CPT coding".
  - For MedDRA, Corti puts the licence on the customer: "Customer shall ensure that it holds and maintains, for the duration of that use, all licences, subscriptions, permissions and approvals required for its intended use of the MedDRA Functionality." (§2.5.5.4) There is no equivalent clause for CPT.
  - General duties: "Customer must ensure that it has all necessary rights and authorizations to submit and process such data using the Platform." (§2.5.3) The customer must not use the API or Output "in violation of regulatory requirements" (§2.6.1.4).
  - Downstream conditions on passing Output to end customers:
    - (A) no third party gets direct access;
    - (B) "Customer remains fully responsible for all downstream use";
    - (E) end-customer agreements include AI-output disclaimers;
    - §2.7: "Customer will back‑to‑back materially equivalent restrictions and responsibilities with its end customers."
- **Coding documentation (S2, S3).** CPT is "maintained by the AMA and updated annually". "This code system is currently available in beta status." Every code carries a required `display` field: "Description of the medical code". There is no licence statement.
- **Other Corti documents (S4).** DPA, Subcontractor BAA, Terms and Conditions, Agentic Services Addendum, subprocessor list, help article: no CPT licence statement. The help article says only that the feature "maintains compliance with standard coding systems such as ICD-CM, ICD-PCS, and CPT".
- **Answers to the brief.**
  - Corti does not state that it holds an AMA CPT licence or distribution right.
  - It passes no CPT right to customers.
  - It does not say whether customers need their own AMA licence. It is silent for CPT, while it does impose that duty for MedDRA.

**OpenAI.**
- **Signed agreement: not available.** No Order Form is in the repository. CPT Studio holds no OpenAI credential yet (D2), and QuillMD has never called OpenAI (`stage1-starting-point.md` §3).
- **Public terms** (S5–S7; no CPT, AMA or medical-code-set text in any of the three).
  - The customer "represents and warrants that it has all rights, licenses, and permissions required to provide Input to the Services" (S5 §4.3).
  - "Output may not be unique, and other users may receive similar content" (§4.4).
  - The customer may not use the Services or Customer Content "in a way that violates third parties' rights" (§3.3(b)).
  - The Usage Policies prohibit "attempts to infringe on intellectual property rights of others" (S7).
  - The Output IP indemnity (A4) excludes, among others, "(iii) Output was modified, transformed, or used in combination with products or services not provided by or on behalf of OpenAI".

**Anthropic.**
- **Signed agreement: not available.** The account is in production use by QuillMD (`stage1-starting-point.md` §3). No executed agreement is in the repository.
- **Public terms** (S8, S9; no CPT, AMA or code-set text).
  - "Customer further represents and warrants that it has all rights and permissions required to submit Inputs to the Services." (§L.1)
  - Users must be told "factual assertions in Outputs should not be relied upon without independently checking their accuracy" (§D.3).
  - The Usage Policy prohibits uses that "Infringe, misappropriate, or violate the intellectual property rights of a third party" (S9).

**CMS: the terms that go with the files CPT Studio uses.**
- **RVU26D.** No gate. The PFS files page says "intended for Medicare purposes" (S15). The CSV and RVU26D.pdf both carry: "CPT codes and descriptions only are copyright 2026 American Medical Association. All Rights Reserved. Applicable FARS/DFARS Apply." (S16)
- **MUE 2026-Q4.** No gate. The file header says: "Current Procedural Terminology (CPT) codes, descriptions and other data only are copyright 2025 American Medical Association. All rights reserved." It adds that "Fee schedules, relative value units, conversion factors and/or related components are not assigned by the AMA, are not part of CPT" (S17).
- **NCCI Policy Manual Ch. VI.** No gate. The same AMA notice appears on page VI-1 (S18).
- **Claims Processing Manual Ch. 12.** No AMA notice in the text. It refers to "the American Medical Association's Current Procedural Terminology" (S19).
- **PTP edits.** Every edit file goes through the AMA agreement (S20, S21). Its terms:
  - users are "authorized to use CPT only as contained in the following authorized materials of [CMS] internally within your organization within the United States";
  - "Use is limited to use in Medicare, Medicaid or other programs administered by CMS";
  - it prohibits "making any commercial use of CPT" and "transferring copies of CPT to any party not bound by this agreement";
  - "License to use CPT for any use not authorized herein must be obtained through the AMA";
  - "The scope of this license is determined by the AMA, the copyright holder";
  - "The AMA is a third party beneficiary to this agreement."

  **Not accepted.** The quarterly change files are direct links on the same page. They were not downloaded.
- None of these CMS texts grants a right to use the CPT codes in these files outside Medicare.

## (D) Remaining licensing requirements for the owner to decide

Every item is a decision for the owner. None is recommended or started here.

**D-1. Development and testing (D4).**
- **Licence and source:** an AMA licence (or one from an AMA-authorized distributor) covering use of CPT "to develop, test, maintain and service products that use or rely on CPT" (S10). Two routes are documented:
  - the AMA "CPT® development license", "Available for new organizations to access CPT content to build and test innovations with a royalty-free license" (S11). In 2022 it was "valid for 12-months with an annual renewal required" and was for innovations "in their development stage prior to production" (S12);
  - development rights inside a product licence (S10).
- **Covers:** all building and testing of CPT Studio, including the harness and synthetic documents.
- **Would require of the owner:**
  - registration or an application (not attempted);
  - accepting terms that are not public;
  - showing eligibility ("new organizations" is not defined);
  - annual renewal;
  - written confirmation of whether AI processing by Corti, OpenAI and Anthropic, and a doctor-facing synthetic demonstration, count as "development stage prior to production".
- **Stays blocked until decided:**
  - the checklist's "Content-use permissions" verdict (NOT ESTABLISHED);
  - the D4 known limit in HARNESS.md §10;
  - whether live synthetic testing continues meanwhile is itself an owner decision. No document permits it, and the AMA's published position is that testing needs a licence.

**D-2. Showing CPT code numbers to reviewers and doctors, on the website and in TXT/CSV reports (D4).**
- **Licence and source:** from the AMA or an authorized distributor, either:
  - a product (distributor) licence: "Organizations across the globe must have a license for each product that contains CPT codes" (S10); or
  - an internal-use licence, only if every user belongs to the owner's organization: "in connection with a specified product within their organization" (S10).
- **Would require of the owner:**
  - state who will see codes: the owner's staff or agents, or outside doctors and practices;
  - count users. Royalties depend on "the type of user of the product" (S10). The 2022 template counts as a User anyone who "makes use of an output of a program which includes the Licensed Content … even though the Licensed Content may not be visible" (S13 §3.1);
  - pay royalties and report usage ("report usage", Royalties Portal, S10);
  - keep AMA notices unobscured (S13 §7.1);
  - keep security in place: "user registration technology and firewall technology" (S13 §7.2);
  - accept audit (S13 §16);
  - identify AI output: "Where appropriate, output(s) should be identified as AI-generated" (S10);
  - meet Corti's own conditions for passing its Output to end customers (S1 §2.6.1.1(A)–(F), §2.7).
- **Stays blocked until decided:** the doctor-facing demonstration. The checklist says it is "NOT READY while any required dependency (D1 to D4) is unresolved".

**D-3. Sending synthetic documents to OpenAI and Anthropic, whose responses propose CPT code numbers (D4).**
- **What would be sent** (`HARNESS.md` §3, §11.1–11.2): the document; CMS facts keyed by CPT code numbers; CMS passages (any passage quoting a CPT description is excluded); and, in peer review, Corti's selected codes and the other model's codes. No data file and no descriptor are sent.
- **Licence and source:** an AMA licence with its AI Addendum.
  - Retrieval-based AI and internal traditional machine learning "must align with the terms of your license agreement with the AMA, and any applicable product approvals".
  - "Uploading the CPT Standard Data File into public, unrestricted, or open-market AI systems is prohibited."
  - "Any distribution, monetization, or sublicensing of AI outputs that reference CPT content must be consistent with the terms specified in your CPT license agreement." (S10)
  - The only AI Addendum text published that this review found belongs to a different product (S14). It allows AI uses "for internal, non-commercial purposes" and allows prompts only in "Enterprise-Grade" tools. It prohibits "No distribution of Outputs" and "No High-Risk Use", including "making assessments or decisions impacting an individual's health". The CPT addendum itself is not available.
- **Vendor side:** neither vendor passes any right. You warrant the rights to your inputs (S5 §4.3; S8 §L.1).
- **Would require of the owner:**
  - describe the three-vendor workflow to the AMA;
  - get a written determination on (i) code numbers a model proposes, (ii) CPT-keyed CMS data and peer code numbers sent as input, and (iii) whether the OpenAI and Anthropic APIs count as permitted tools rather than "Unrestricted GenAI Systems" (S14 definition: an application "accessible without restriction", "e.g., chatbots, APIs").
- **Stays blocked until decided:** live Astra and Fable runs are already blocked on D1 and D2 (the API keys). This item decides whether they may proceed before D4 once the keys exist. Checklist 3.2, 3.3, 3.6 and 6.3 depend on it.

**D-4. CPT descriptors, code-set membership and guidelines in the product (D3).**
- **Option A, licensed content.** An AMA licence for the CPT Standard Data File and any guideline content, with AI and retrieval rights, because participants would retrieve content through tools.
  - "Retrieval rights allow an AI system to reference licensed CPT content at the point of use without embedding that CPT content into the AI model itself."
  - Training is prohibited (S10).
  - A codebook is not a substitute: "CPT Professional Edition or other CPT related codebooks are for reference only" (S10).
  - Would require: an application; royalties (no amounts are published); "product approvals"; and new royalties for each annual release ("subsequent annual releases … will require payment of additional royalties", S13 §7).
- **Option B, CMS public sources only.** The owner accepts that validation uses CMS public sources only, and the product says so (D3's second branch). D4 stays open under this option (see D-6).
- **Stays blocked until decided:** checklist 4.2. Descriptors stay withheld, and code-set membership stays "not verified".

**D-5. NCCI PTP edits (D3 and D4).**
- **Licence and source:** the only documented path is the AMA agreement on cms.gov (S21). It is limited to CMS programs, excludes commercial use, and its scope "is determined by the AMA". Other uses "must be obtained through the AMA".
- **Options the documents describe:**
  - (a) leave PTP disconnected (current state);
  - (b) ask the AMA in writing whether any licence covers PTP data in CPT Studio;
  - (c) accept the point-and-click agreement. Its own words limit it to CMS programs, and whether CPT Studio's use fits is for the AMA to say.
- **Quarterly change files:** these are direct links on the same page. The page does not say whether the same terms apply, and a missing gate is not a licence. Not downloaded, per your rule.
- **Stays blocked until decided:** PTP checks (`checks.py` NOT_CONNECTED) and the bundling part of checklist 4.2.

**D-6. CPT data CPT Studio already holds from CMS files (D4).**
- **What is held:**
  - RVU26D and MUE code-keyed facts, already imported;
  - the RVU26D zip with its descriptor column, stored;
  - verbatim NCCI and Claims Manual passages for retrieval.
- **What the sources say:** no gate; "intended for Medicare purposes"; AMA copyright notices (section C). Nothing grants their use in CPT Studio.
- **Would require of the owner:** include these uses in the AMA request (D-1, D-2), or record the CMS-only approach with this risk stated (D-4 option B).
- **Stays blocked until decided:** nothing technical. The content-use verdict stays NOT ESTABLISHED.

**D-7. CPT in Corti's output: codes and `display` descriptions (D4).**
- The AMA says: "Organizations license CPT content from the AMA directly or through a vendor. Check … with the software vendor where you use CPT content to determine if you are already licensed for your use case." (S10)
- **Would require of the owner:** a written statement from Corti on:
  - (i) whether Corti holds an AMA licence covering the CPT codes and descriptions returned by `/v2/tools/coding/`;
  - (ii) whether any of it extends to you;
  - (iii) whether Corti expects you to hold your own licence, as it does for MedDRA.

  Plus a copy of your signed Order Form or the version you accepted (not available).
- **Stays blocked until decided:** nothing technical. CPT Studio's reliance on Corti's CPT output stays without a documented right.

**D-8. Which product the request covers (D4).**
- The AMA requires "a license for each product that contains CPT codes" (S10).
- The prepared handoff (`docs/coding-cpt-licensing-handoff.md`, 2026-10-15) describes QuillMD with Anthropic as its only AI provider. It does not cover CPT Studio, Corti, OpenAI, the CMS-derived data or the harness.
- **Would require of the owner:**
  - decide whether CPT Studio goes in its own request or in the same request as QuillMD;
  - supply CPT Studio's facts: contracting entity, contact, territory, hosting and subprocessors (Corti, OpenAI, Anthropic), users, internal use or distribution.
- **Stays blocked until decided:** any AMA request for CPT Studio. None has been submitted.

## (E) Not stated or uncertain

- **Code numbers alone.** Whether CPT code numbers without descriptors need a licence is not stated anywhere. This is a legal question and is not answered here.
- **AMA AI terms and model output.** Whether code numbers a third-party model proposes, without CPT Studio holding the data file, are "AI outputs that reference CPT content" is not stated. The FAQ's AI section is written about the "CPT Standard Data File".
- **The CPT AI Addendum and the development licence.** Neither text is available; the development licence sits behind registration, which was not attempted. Eligibility ("new organizations") and AI use under the development licence are not stated.
- **Royalty versus royalty-free.** The FAQ lists testing among uses needing "a license and royalty payment". The Developer Program offers a "royalty-free" development licence. How the two fit for this owner is not stated.
- **Fees.** No royalty amount is published.
- **Current AMA templates.** The public internal-use template dates from 2022. The current terms and the AMA User Proxy Model are not available; that model's page now redirects to the FAQ.
- **OpenAI and Anthropic as AI tools.** Whether their APIs are "Enterprise-Grade" or "Unrestricted GenAI Systems" under an AMA addendum is not stated. Those definitions were found only in another product's agreement (S14).
- **Corti.** Its own AMA licensing status is not stated, and its docs compliance page returned 403. Whether Corti's `display` text is AMA descriptor text is also not stated; one value seen earlier was "+PR OFFICE OUTPATIENT VISIT 15 MINUTES" (`docs/corti-coding-workflow.md:118-120`).
- **Which terms bind the owner.**
  - The Corti version, and any Order Form, binding your account are not available.
  - OpenAI's live pages could not be read (403); the archive captures were used.
  - The usage-policy versions in force on 2026-11-01 were not read. The pages show versions taking effect Nov 20 (OpenAI) and Nov 12, 2026 (Anthropic).
- **Indemnities.** They are not licences. Whether either vendor's would respond to an AMA claim was not assessed. Possibly relevant exclusions:
  - combination with other products (OpenAI (iii), Anthropic K.3(b));
  - customer inputs (OpenAI (iv), Anthropic K.3(c)).
- **Website security.** Whether a login-protected website is "unsecured" or "public" under AMA terms is not stated.
- **PTP change files.** Whether they are covered by the AMA terms is not stated.
- **Synthetic documents.** Whether any of them reproduces AMA descriptor text, for example in a charge block, was not checked.
- **Policy context.** Medical Economics (Aug 31, 2026) reports a CMS request for information on the future of coding in the CY 2027 PFS proposed rule (§II.H). It "is not a proposal". The Federal Register document was not read, and nothing found changes current requirements.
- **Outside the CPT question, noted because it bears on the harness:** Corti's terms bar customers to "benchmark or test the Platform for competitive purposes without prior written approval" (S1 §2.6.1.9). The harness compares Corti with OpenAI and Anthropic before choosing the production engine. Whether that is "for competitive purposes" is not stated.
