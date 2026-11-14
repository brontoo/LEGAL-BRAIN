# Phase 1.5 acceptance matrix

Statuses describe executed engineering checks, not approval of current UAE law.
Baseline: 1,209 Python tests. Final: **1,299 passing tests**, including **90 new
Phase 1.5 tests**. The dedicated acceptance package contains the 60 bilingual
scenario/mode tests plus 30 safety, comparison, diagnostic and verification tests.

| Criterion | Status | Evidence / qualification |
| --- | --- | --- |
| AC-1 Existing development branch preserved | PASSED | Continued `feature/skill-registry-uae-playbooks`, fetched remote, verified `89e5f7f` ancestor; no reset/merge |
| AC-2 Five playbooks functional | PASSED | Each reaches graph messages, evidence, review, authority and revision paths under scripted dependencies |
| AC-3 Generation compatible | PASSED | Full prior regressions pass; original host/user messages and successful flag-off SSE shape retained; operational exception text intentionally sanitized |
| AC-4 Frontend lint | PASSED | `npm run lint`, zero errors/warnings; no rule suppression |
| AC-5 TypeScript | PASSED | `npx tsc --noEmit`, exit 0; also checked during production build |
| AC-6 Production build | PASSED | `npm run build`, complete prerender/route output using licensed local fonts |
| AC-7 Production auth safeguards | PASSED | Backend startup guard, production Docker defaults, proxy 503 without token, protected endpoints, confidential error/log tests |
| AC-8 Ten fictional scenarios | PASSED | EN/AR automatic/explicit/disabled execution for all ten; subjective legal review explicitly NOT RUN |
| AC-9 Arabic/English routing | PASSED | 20/20 scenario-language selections in paired offline report, plus prior router tests |
| AC-10 ADGM/DIFC | PASSED | Separate structured law/forum context preserved; conflicting forum blocked; no automatic federal substitution in workflow instructions |
| AC-11 Citation/authority active | PASSED | Existing real deterministic modules execute in skill-enabled pipeline; five-playbook forced revision and review tests |
| AC-12 Unsupported references | PASSED | Forged quotes rejected; unbacked articles flagged; secondary policy/playbook misuse flagged; absent authority stays unverified |
| AC-13 Deterministic risk | PASSED | Supported 4×3=12, unknown missing likelihood, custom matrix and unsafe-label rejection |
| AC-14 Flag-off compatibility | PASSED | Original successful prompts/stream checks, paired identical-scripted-output reports, no skill diagnostic field when disabled; revised drafts refresh existing reports |
| AC-15 Full regression suite | PASSED | 1,299 tests; no failed or skipped tests |
| AC-16 Live status accurately reported | PASSED (reporting) | Actual live execution BLOCKED by missing credentials/dependencies; no live success claimed |
| AC-17 Lawyer checklist/template | PASSED (delivered) | Scenario-specific checklist and paired 10-dimension scorecard; human legal assessment NOT RUN |
| AC-18 Commit/push to feature branch | PASSED on delivery | Completion message and Git history record the new pushed commit; no force-push, merge or deployment |

## Scenario execution results

Each row represents two languages × three modes = six independently counted tests.
All tests use fictional inputs and scripted external services, not live legal reasoning.

| Scenario | Automatic EN/AR | Explicit EN/AR | Disabled EN/AR | Live quality / lawyer acceptance |
| --- | --- | --- | --- | --- |
| 01 Abu Dhabi marketing | PASSED | PASSED | PASSED | BLOCKED / NOT RUN |
| 02 Mutual NDA | PASSED | PASSED | PASSED | BLOCKED / NOT RUN |
| 03 Brokerage | PASSED | PASSED | PASSED | BLOCKED / NOT RUN |
| 04 Employment | PASSED | PASSED | PASSED | BLOCKED / NOT RUN |
| 05 ADGM | PASSED | PASSED | PASSED | BLOCKED / NOT RUN |
| 06 DIFC | PASSED | PASSED | PASSED | BLOCKED / NOT RUN |
| 07 Share transfer | PASSED | PASSED | PASSED | BLOCKED / NOT RUN |
| 08 Negotiation | PASSED | PASSED | PASSED | BLOCKED / NOT RUN |
| 09 Risk | PASSED | PASSED | PASSED | BLOCKED / NOT RUN |
| 10 Missing document | PASSED | PASSED | PASSED | BLOCKED / NOT RUN |

## Outside the engineering pass claims

Production legal acceptance and current-law verification are NOT RUN. Live services
are BLOCKED. Exploratory 390px mobile workspace generation failed because its
existing layout puts the action outside the viewport; desktop generation and
mobile library controls passed. Responsive workspace remediation and a complete
accessibility audit remain unresolved. No production-readiness claim is made.
