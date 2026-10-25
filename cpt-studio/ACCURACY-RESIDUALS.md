# CPT Studio — accuracy residuals (routing wording it does not recognise)

Routing reads declared wording, layouts and check boxes. Four refutation rounds each found new phrasings it misreads,
in both directions, and the count did not fall (47, 49, 71, 99 confirmed). So these misreadings are recorded and
measured instead of chased one phrasing at a time (round 4, 2026-10-24):

- **Nothing routing decides is final without a reviewer.** A status exclusion is a recommendation the reviewer must
  confirm or reverse before a reviewed report exists, and approving a code is the reviewer's statement that the whole
  document, not only the cited passages, supports it (ARCHITECTURE truth rule 5 and 5.7). The UI and every report say
  that the service status is not verified.
- **What is still fixed in code:** misreadings of what the code DECLARES it reads (its box vocabulary, its listed words
  and layouts, the form-field contract), regressions, cost and memory, and anything that would let a code be approved or
  removed without a reviewer decision.
- **What is listed here:** wording OUTSIDE every declared list. Each entry is input for the accuracy evaluation the owner
  directive calls for (independently adjudicated cases, withheld from development), where its real frequency decides
  whether it earns a rule.

"Effect now" is the behaviour on the repair branch when the entry was recorded (round 4 or round 5). *Held* means needs_clarification; *ready* means approvable
with the whole-document acknowledgement; *excluded* means a recommendation the reviewer must confirm or reinstate.

| id (round 4) | example input | effect now | why it is not a rule yet |
|---|---|---|---|
| routing:8 | "Last time the cecum was reached with a pediatric colonoscope." beside today's incomplete colonoscopy | extent read as cecum: ready as complete | prior-attempt nouns are open ("last time", "previous attempt", "historically") |
| routing:12 | "Even if colonoscopy were done today, the bleeding risk would be high." in an office note | colonoscopy read performed; E/M held as same-day | conditional openers are open ("even if", "assuming", "in the event that") |
| routing:13 | "Biopsies appear to have been taken from the sigmoid colon." | 45380 ready | evidential hedges are open ("appear to", "seem to", "I believe") |
| routing:15, release:13 | "...no polyps were identified requiring polypectomy." / "...no polyps were seen, thus nothing was removed." | 45385 ready | a denied finding followed by the billed act, in open word orders |
| routing:16 | "Established patient office visit to review a CT scan done 2 weeks ago." | E/M held (over-hold) | the time-owner rule cannot tell whose 'ago' it is |
| routing:17 | "EGD would be done if the dysphagia persists." under Assessment | E/M held (over-hold) | hedge rules hold conservatively |
| routing:18, release:6 | "Two internal hemorrhoids banded today." / "Rubber band ligation: Yes" on a later line | E/M ready with no same-day check | procedure names without an auxiliary, key-value answers, later lines |
| evidence:2 | "Infrared coagulation of two internal hemorrhoids was performed today." | E/M ready with no same-day check | gi.other names are open (no procedure word) |
| evidence:3, routing:7 (rest) | "EUS ... after the inflammation settles." / "by the end of the month" / "over the weekend" | 43242 ready | future and past phrases outside OTHER_TIME |
| validation:4 | "History of present illness: EGD this morning showed a Schatzki ring, dilated to 18 mm." | E/M ready | a history section that says today; a rule like PLAN_TODAY would over-hold HPI broadly |
| validation:5 | "Grade 2 internal hemorrhoids, banded x3 in the office." under Assessment and plan | 46221 excluded (reviewer confirms or reinstates; reinstating holds the E/M) | past-tense act words in a plan section are open |
| validation:10, 11, 12 | "Plan: Colonoscopy prep instructions given today." / "Banded x3." under Procedure | E/M or code held (over-holds) | conservative holds, accepted |
| release:8 (rest) | "Procedure aborted prior to scope insertion." / "The patient withdrew consent in the pre-procedure area." / "The exam did not take place..." | 43242 ready | cancellation phrasings outside PROCEDURE_CANCELLED (a status line, a typed "Procedure performed: No" and a denying heading are read) |
| routing:5 (rest) | "...for surveillance; adenomas were removed last year." | 45385 excluded (reviewer confirms or reinstates) | a clause with no service name owning a time |
| round 5 regression:7 | "Impression: Sigmoid polyp, removed. Defer surveillance colonoscopy until pathology returns." beside today's colonoscopy | 45385 held (over-hold) | the deferral rule cannot tell whose deferral it is (the next exam's, not today's) |
| round 5 regression:8 | "Surveillance colonoscopy deferred pending pathology." / "Repeat colonoscopy deferred to primary care." under Impression, Assessment or Disposition | 45385 excluded (reviewer confirms or reinstates) | a cancellation verb on a service named as a future exam, with no declared other-encounter marker |
| round 5 declared:13 | "Procedure status:" with its options one per line ("☐ Completed" / "☒ Cancelled", also a Word form with one check box per paragraph) | 43242 ready | the status readers read a label's own line; a value on later lines is a layout outside the declared ones |
| round 5 sections:11 | "When asked about a biopsy of the hemorrhoid the patient stated no" / "...and the answer was no" before "Cold snare polypectomy ... was performed." | 45385 excluded (reviewer confirms or reinstates) | spoken answers outside the closed verb list (said, answered, replied, responded, chose) join the next clause |

How an entry leaves this list: the accuracy evaluation shows the phrasing occurs in real adjudicated documents, and a
rule is written for it under the hold-only rule (it may hold; it never newly excludes or releases), with a corpus
differential showing no release.
