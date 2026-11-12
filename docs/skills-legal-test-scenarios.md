# Fictional UAE legal acceptance scenarios

All newly added records are clearly fictional. None is an authoritative legal
source, current-law opinion or authentic company record. No client records are
used in this package. The existing historical regression suite is unchanged apart
from two intentional assertions about sanitizing provider errors.

Executable bilingual inputs and review expectations are in
`tests/acceptance/scenarios.json`. Each scenario has separate Arabic and English
prompts and documents. Every variant is exercised through `/generate` in automatic,
explicit and flag-disabled modes (60 independently counted scenario tests).

| ID | Scenario / السيناريو | Expected methodology and manual checks |
| --- | --- | --- |
| 01 | Abu Dhabi marketing agreement / عقد تسويق بأبوظبي | Contract review: deliverables, advance payments, termination, liability, missing schedule |
| 02 | Mutual NDA / اتفاقية سرية متبادلة | NDA: survival, disclosure exceptions, IP overreach, triage color with no signature approval |
| 03 | Abu Dhabi brokerage / وساطة عقارية | Contract review: commission trigger, disputed introduction, termination proof, rules requiring verification |
| 04 | Employment-related agreement / عقد مرتبط بالعمل | Contract review: restrictive terms, termination, employer/free-zone regime unknown, authority needs |
| 05 | ADGM agreement / عقد خاضع لـ ADGM | Contract review with explicit ADGM law/forum; no automatic federal-law substitution |
| 06 | DIFC agreement / عقد خاضع لـ DIFC | Contract review with explicit DIFC regime; payment/remedy conflict and missing sources |
| 07 | LLC share transfer / نقل حصص شركة | Corporate diligence: ownership, approvals, signatory authority, missing corporate records; no invented registry results |
| 08 | Negotiation / تفاوض | Priorities, preferred/fallback wording, indemnity/liability/payment tradeoffs, legal vs commercial basis |
| 09 | Transaction risk / مخاطر صفقة | Supported ordinal 4×3 = 12; unsupported likelihood remains unknown; no invented monetary/probability estimate |
| 10 | Missing agreement / عقد غير مقدم | Request documents, avoid fabricated clause findings, no signature approval, human review |

## What the offline tests establish

The existing graph stream receives the original host instructions plus the selected
skill when enabled; user/evidence text stays separate. Real deterministic citation,
authority, review parsing, language and revision code execute around scripted
model/tool dependencies. Five-playbook tests cause actual revision-loop calls with
synthetic Markdown defects, not merely the presence of a revision frame.

The package verifies genuine available contractual quotes, forged-quote rejection,
unbacked article detection, missing-source/unsourced status and secondary policy/
playbook misuse using the existing verification modules. It checks both special
regimes, conflicts, ambiguity, safe fallback, authentication, private logging,
non-destructive output diagnostics and deterministic risk scoring.

These assertions establish **plumbing and evidence discipline under controlled
inputs**. They do not prove an LLM spots every listed issue, proposes sound wording,
refuses every unsafe approval request or understands current UAE law. The mock
response for missing documentation is an explicit request for the absent document;
it is not represented as observed live model judgment.

## Lawyer review checklist and results template

Complete separately for each scenario, language, mode and actual run. Status is
currently **NOT RUN** for all subjective assessments.

- Record run ID, code revision, model/settings, date, language, reviewer identity,
  client-side role, jurisdiction context, supplied documents and source cutoff.
- Verify factual consistency against the fictional scenario and every evidence gap.
- Distinguish legal requirements, approved policy, commercial recommendations,
  drafting preferences and unverified assumptions.
- Check each expected concern in the scenario table. Record false positives,
  omissions, contradictory clauses and unsupported proposed terms.
- Check every quote/source, article identity, source class, legal regime,
  applicability, authoritative language, amendments and current force when claimed.
- Verify ADGM/DIFC separation and unresolved jurisdiction questions.
- Confirm missing information is requested, no records/approvals are invented,
  and no output authorizes signature or reliance without lawyer review.
- Check negotiation alternatives and concessions against supplied objectives;
  confirm risk arithmetic and unknown statuses against supported inputs.
- Review Arabic/English equivalence and plain-text document quality.
- Review diagnostic gaps manually; observed labels alone never imply sound content.

Copy this template for each actual paired run:

| Field | Result |
| --- | --- |
| Run / scenario / language / revision | NOT RUN |
| Reviewer / review date / model / settings | NOT RUN |
| Verified official sources, applicability and force evidence | NOT RUN |
| Missing/uncertain evidence and unresolved legal questions | NOT RUN |
| Material errors, required changes, escalation | NOT RUN |
| Final human decision: revise / escalate / acceptable for stated limited purpose | NOT RUN |

Score both modes independently from 0 (material failure) to 4 (strong, supported
performance). Use N/A with a reason where a dimension does not apply. An unrun
score is null/NOT RUN, never zero. Cite output paragraph/clause and supporting
source for every judgment; labels alone are insufficient.

| Subjective dimension | Original score | Skill-enabled score | Evidence / reason |
| --- | --- | --- | --- |
| Workflow selection | NOT RUN | NOT RUN | |
| Issue identification | NOT RUN | NOT RUN | |
| Completeness | NOT RUN | NOT RUN | |
| Factual consistency | NOT RUN | NOT RUN | |
| Citation integrity | NOT RUN | NOT RUN | |
| Jurisdiction treatment | NOT RUN | NOT RUN | |
| Missing-information handling | NOT RUN | NOT RUN | |
| Proposed clause quality | NOT RUN | NOT RUN | |
| Human-review requirements | NOT RUN | NOT RUN | |
| Output consistency | NOT RUN | NOT RUN | |

No average automatically grants legal approval. The live runner creates null
score fields for these dimensions and stores real outputs privately for review.
