# Phase 2B clause taxonomy

Labels identify topics for review. They do not establish enforceability, risk,
performance, applicability or completeness. Multiple labels are permitted and
`classification_status` remains `deterministic_candidate`.

| Category | Example English cue | Example Arabic cue |
| --- | --- | --- |
| parties_definitions | definitions / explicit party alias | التعريفات / ويشار إليه |
| scope_services | scope / services | نطاق / الخدمات |
| deliverables | deliver / report | تسليم / تقرير |
| payment | pay / invoice | سداد / الفاتورة |
| commission_brokerage | commission / brokerage | عمولة / الوساطة |
| representations_warranties | represents / warrants | يقر / يتعهد بصحة |
| conditions_precedent | subject to / provided that | شريطة / رهناً ب |
| conditions_subsequent | ceases upon / lapses upon | ينتهي عند / يسقط حقه |
| default_breach | breach / default | إخلال / تخلف |
| termination | termination / terminate | إنهاء / فسخ |
| renewal | renewal / renew | تجديد / يتجدد |
| indemnification | indemnity / indemnify | تعويض / يعوض |
| limitation_liability | liability / liability cap | المسؤولية / حد المسؤولية |
| confidentiality | confidentiality / confidential | سرية / إفشاء |
| intellectual_property | intellectual property / copyright | ملكية فكرية / حقوق الملكية |
| non_compete | non-compete / not compete | عدم المنافسة / لا ينافس |
| non_solicitation | non-solicitation / not solicit | عدم الاستقطاب / لا يستقطب |
| assignment_transfer | assign / transfer | تنازل / نقل الملكية |
| force_majeure | force majeure | قوة قاهرة |
| governing_law | governed by / governing law | القانون الواجب / يخضع هذا العقد |
| jurisdiction_arbitration | courts / arbitration | اختصاص / تحكيم |
| notices | notice / notices | إشعار / إخطار |
| remedies | remedies / injunction | سبل الانتصاف / حقوق أخرى |
| security_guarantees | deposit / guarantee | تأمين / ضمان / وديعة |
| maintenance_repair | maintenance / repair | صيانة / إصلاح |
| corporate_authority | approval / board | موافقة / مجلس الإدارة |
| other | no recognized topic cue | لا توجد قرينة معروفة |

Normalization folds case, Arabic Alef variants, common diacritics/tatweel and
Arabic digits for matching only. Common Arabic attached prefixes are accepted
conservatively. It is not full Arabic morphology. The exact source is retained.
Negative mentions and names containing topic words can still trigger labels;
the benchmark records these errors. “Neither party may compete” is a known
scope-sensitive missed non-compete classification in the frozen fixture.

Modal candidates distinguish mandatory, conditional obligation, prohibited,
discretionary right, right, right lapse, representation, statement of fact and
commercial intention. English/Arabic forms include shall/must/may/must not,
يلتزم/يحق ل/يجوز ل/لا يجوز/يقر/يسقط حقه. These are lexical candidates, not a
complete linguistic analysis. Negation scope, coordinated actors and embedded
speech remain difficult. Extracted parties and beneficiaries can be null.

Each obligation records source clause, actor, beneficiary, action/subject,
trigger, condition IDs, deadline IDs, exception IDs, express consequence text,
exact evidence, interpretation status and mandatory human review. Actions are
source expressions; they are not normalized into a proven semantic predicate.

Financial contexts distinguish contract price, deposit, advance, installment,
commission, refund, deduction, penalty, interest, VAT, reimbursement and liability
cap where lexical context supports one type. Multiple types in a sentence remain
`ambiguous_financial_context`; amounts are never silently treated interchangeably.
Currency and percentage extraction preserves the original quote and a separate
normalized numeric string. No arithmetic or automatic due determination occurs.

Absolute ISO dates can be represented as dates; slash dates remain ambiguous.
Relative periods record units, working/calendar/unknown basis, trigger and
contractual context (e.g. notice, cure, expiry, payment). Word-number coverage is
limited. A notice period is not reclassified as a statutory limitation period.

Optional model labels use the same category keys but remain unverified proposals;
they do not replace deterministic labels or override original source text.
