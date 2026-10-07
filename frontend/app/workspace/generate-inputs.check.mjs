/**
 * قياس شكل حمل الطلب **بالتشغيل لا بالقراءة** — لمنطق المدخلات وحده.
 *
 * ⚠️ **ولماذا سكربت لا اختبار متصفّح؟** لأن المُقاس هو **الكائن المُرسَل** لا
 * الصفحة: أسماءُ المفاتيح التي تقرأها مُحوِّلات `main.py`، وقيمُ التعديد
 * بأعضاء وحدات الخادم، **وغيابُ المفتاح عند الفراغ**. وكلّها تُقاس في Node
 * بلا React ولا متصفّح، لأن `generate-inputs.ts` خالٍ من JSX.
 *
 * التشغيل:  node app/workspace/generate-inputs.check.mjs
 * (خارج `tsconfig.include` — فهو يضمّ `.ts` و`.tsx` و`.mts` لا `.mjs`.)
 */
import {
  AXIS_OPTIONS,
  CASE_STAGE_OPTIONS,
  CONVENTION_OPTIONS,
  DISPUTE_TYPE_OPTIONS,
  PARTY_OPTIONS,
  RULE_FAMILY_OPTIONS,
  SOURCE_KIND_OPTIONS,
  STAGE_OPTIONS,
  UNIT_OPTIONS,
  buildGeneratePayload,
  describeInputProblems,
  emptyGenerateInputs,
  emptyMatrixItem,
} from "./generate-inputs.ts";

let failures = 0;
let checks = 0;

function check(name, condition, detail) {
  checks += 1;
  if (condition) {
    console.log(`  ok  ${name}`);
  } else {
    failures += 1;
    console.log(`FAIL  ${name}${detail === undefined ? "" : ` — ${detail}`}`);
  }
}

/** القيم المسموحة لعضو تعديد — **والعربية ليست منها**. */
const values = (options) => options.map((o) => o.value);

/* ── ١. الفراغ يبقى غياباً ──────────────────────────────────────────────── */

console.log("\n[١] الفراغ يبقى غياباً لا كائناً فارغاً:");
{
  const state = emptyGenerateInputs();
  check("لا نصّ منع على حالة فارغة", describeInputProblems(state) === null);
  const result = buildGeneratePayload(state);
  check("البناء ينجح", result.ok === true);
  if (result.ok) {
    const keys = Object.keys(result.payload);
    check("لا مفاتيح مطلقاً", keys.length === 0, `الوارد: ${JSON.stringify(keys)}`);
    for (const key of ["claims", "authority", "deadlines", "rules"]) {
      check(`«${key}» غائب لا فارغ`, !(key in result.payload));
    }
    check(
      "ولا كائنَ فارغاً في أيّ مفتاح",
      !Object.values(result.payload).some(
        (v) => v && typeof v === "object" && Object.keys(v).length === 0
      )
    );
  }
}

/* ── ٢. حالة ناقصة تُمنع بنصّ ───────────────────────────────────────────── */

console.log("\n[٢] الناقص يُمنع بنصٍّ قبل الإرسال:");
{
  const state = emptyGenerateInputs();
  state.claims = [{ ...emptyMatrixItem(), key: "notice_pay", label: "" }];
  const message = describeInputProblems(state);
  check("طلبٌ بلا نصّ يُمنع", typeof message === "string" && message.length > 0);
  const result = buildGeneratePayload(state);
  check("ولا يُبنى معه حمل", result.ok === false);
}

{
  const state = emptyGenerateInputs();
  state.deadlines = [
    {
      key: "appeal_window",
      label: "ميعاد الاستئناف",
      amount: "30",
      unit: "days",
      conventionKey: "",
      source: "",
      note: "",
    },
  ];
  check(
    "قاعدة موعد بلا عدّ تُمنع",
    typeof describeInputProblems(state) === "string"
  );
}

{
  const state = emptyGenerateInputs();
  state.rules = [
    {
      key: "notice.basis",
      statement: "الإشعار لازم",
      family: "substantive",
      subject: "notice",
      appliesTo: [],
      stages: [],
      source: "",
      inForceFrom: "",
      supersedes: "",
      note: "",
    },
  ];
  check(
    "حكمٌ موضوعي بلا تاريخ نفاذ يُمنع",
    typeof describeInputProblems(state) === "string"
  );
}

{
  const state = emptyGenerateInputs();
  state.rules = [
    {
      key: "check.quote",
      statement: "الاقتباس يُتبَّع",
      family: "verification",
      subject: "check",
      appliesTo: [],
      stages: [],
      source: "",
      inForceFrom: "2024-01-01",
      supersedes: "",
      note: "",
    },
  ];
  check(
    "وفحصٌ بتاريخ نفاذ يُمنع",
    typeof describeInputProblems(state) === "string"
  );
}

{
  const state = emptyGenerateInputs();
  state.rules = [
    {
      key: "notice.basis",
      statement: "الإشعار لازم",
      family: "substantive",
      subject: "notice",
      appliesTo: [],
      stages: [],
      source: "",
      inForceFrom: "2024/01/01",
      supersedes: "",
      note: "",
    },
  ];
  check(
    "وتاريخٌ بغير صيغة ISO يُمنع",
    typeof describeInputProblems(state) === "string"
  );
}

/* ── ٣. الحالة الكاملة: المفاهيم الأربعة بقيم التعديد ───────────────────── */

console.log("\n[٣] الحالة الكاملة — المفاتيح والقيم:");
const full = (() => {
  const state = emptyGenerateInputs();
  state.stage = "cassation";
  state.ourParty = "defendant";
  state.claims = [
    {
      key: "notice_pay",
      label: "مكافأة نهاية الخدمة",
      claimedBy: "claimant",
      axes: ["existence", "quantum"],
      elements: "علاقة عمل\nمدّة خدمة",
      supportingFacts: "f_contract",
      opposingFacts: "",
      evidence: "عقد العمل",
      response: "",
      outcomeSought: "إلزام المدّعى عليه",
      documentsRequired: "كشف الرواتب",
    },
  ];
  state.defences = [
    {
      key: "limitation",
      label: "تقادم المطالبة",
      claimedBy: "defendant",
      axes: ["due"],
      elements: "ميعادٌ سارٍ",
      supportingFacts: "",
      opposingFacts: "",
      evidence: "",
      response: "",
      outcomeSought: "عدم قبول الدعوى",
      documentsRequired: "",
      isProcedural: true,
    },
  ];
  state.authorities = [
    {
      key: "labour_law_33",
      instrument: "قانون تنظيم علاقات العمل",
      article: "المادة ٣٣",
      kind: "federal_law",
      officialSource: "الجريدة الرسمية",
      inForceFrom: "2022-02-01",
      inForceTo: "",
      amendedBy: "",
      retrievedFrom: "",
      conditions: "علاقة عمل غير محدّدة المدّة",
      exceptions: "",
    },
  ];
  state.deadlines = [
    {
      key: "appeal_window",
      label: "ميعاد الاستئناف",
      amount: "30",
      unit: "days",
      conventionKey: "calendar_exclusive",
      source: "المادة ١٥٩",
      note: "",
    },
  ];
  state.rules = [
    {
      key: "notice.basis",
      statement: "الإشعار شرطٌ لصحة الإنهاء",
      family: "substantive",
      subject: "notice",
      appliesTo: ["labour"],
      stages: ["first_instance", "appeal"],
      source: "المادة ٤٣",
      inForceFrom: "2022-02-01",
      supersedes: "notice.old",
      note: "",
    },
    {
      key: "check.quote",
      statement: "كل اقتباس يُتبَّع بمصدره",
      family: "verification",
      subject: "check",
      appliesTo: [],
      stages: [],
      source: "",
      inForceFrom: "",
      supersedes: "",
      note: "",
    },
  ];
  return state;
})();

{
  check("لا نصّ منع على الحالة الكاملة", describeInputProblems(full) === null);
  const result = buildGeneratePayload(full);
  check("البناء ينجح", result.ok === true);
  if (result.ok) {
    const p = result.payload;

    // ── المفاتيح الأربعة بأسماء مُحوِّلات main.py ──────────────────────────
    check(
      "المفاتيح الأربعة بأعلى الحمل",
      ["claims", "authority", "deadlines", "rules"].every((k) => k in p),
      JSON.stringify(Object.keys(p))
    );
    check(
      "«claims.claims» و«claims.defences»",
      Array.isArray(p.claims?.claims) && Array.isArray(p.claims?.defences)
    );
    check("«authority.authorities»", Array.isArray(p.authority?.authorities));
    check("«deadlines.rules»", Array.isArray(p.deadlines?.rules));
    check("«rules.rules»", Array.isArray(p.rules?.rules));

    // ── قيم التعديد: أعضاء الوحدات لا نصوصاً عربية ────────────────────────
    check(
      "stage عضو Stage",
      values(STAGE_OPTIONS).includes(p.claims?.stage),
      p.claims?.stage
    );
    check(
      "our_party عضو Party",
      values(PARTY_OPTIONS).includes(p.claims?.our_party),
      p.claims?.our_party
    );
    check(
      "claimed_by عضو Party في الطلب",
      values(PARTY_OPTIONS).includes(p.claims?.claims?.[0]?.claimed_by),
      p.claims?.claims?.[0]?.claimed_by
    );
    check(
      "claimed_by عضو Party في الدفع",
      values(PARTY_OPTIONS).includes(p.claims?.defences?.[0]?.claimed_by),
      p.claims?.defences?.[0]?.claimed_by
    );
    check(
      "axes_in_dispute أعضاء DisputeAxis",
      (p.claims?.claims?.[0]?.axes_in_dispute ?? []).every((a) =>
        values(AXIS_OPTIONS).includes(a)
      ),
      JSON.stringify(p.claims?.claims?.[0]?.axes_in_dispute)
    );
    check(
      "kind عضو SourceKind",
      values(SOURCE_KIND_OPTIONS).includes(p.authority?.authorities?.[0]?.kind),
      p.authority?.authorities?.[0]?.kind
    );
    check(
      "unit عضو Unit",
      values(UNIT_OPTIONS).includes(p.deadlines?.rules?.[0]?.unit),
      p.deadlines?.rules?.[0]?.unit
    );
    check(
      "convention_key عضو Convention",
      values(CONVENTION_OPTIONS).includes(p.deadlines?.rules?.[0]?.convention_key),
      p.deadlines?.rules?.[0]?.convention_key
    );
    check(
      "family عضو RuleFamily",
      values(RULE_FAMILY_OPTIONS).includes(p.rules?.rules?.[0]?.family),
      p.rules?.rules?.[0]?.family
    );
    check(
      "applies_to أعضاء DisputeType",
      (p.rules?.rules?.[0]?.applies_to ?? []).every((t) =>
        values(DISPUTE_TYPE_OPTIONS).includes(t)
      ),
      JSON.stringify(p.rules?.rules?.[0]?.applies_to)
    );
    check(
      "stages أعضاء CaseStage",
      (p.rules?.rules?.[0]?.stages ?? []).every((s) =>
        values(CASE_STAGE_OPTIONS).includes(s)
      ),
      JSON.stringify(p.rules?.rules?.[0]?.stages)
    );

    // ── والعدد رقمٌ لا نص؛ والتاريخ على الموضوعي وحده ──────────────────────
    check(
      "amount رقمٌ لا نصّ",
      typeof p.deadlines?.rules?.[0]?.amount === "number",
      typeof p.deadlines?.rules?.[0]?.amount
    );
    check("amount = 30", p.deadlines?.rules?.[0]?.amount === 30);
    check(
      "is_procedural قيمة منطقية",
      p.claims?.defences?.[0]?.is_procedural === true
    );
    check(
      "in_force_from على الموضوعي موجود",
      p.rules?.rules?.[0]?.in_force_from === "2022-02-01",
      p.rules?.rules?.[0]?.in_force_from
    );
    check(
      "in_force_from على الفحص غائب",
      !("in_force_from" in (p.rules?.rules?.[1] ?? {})),
      JSON.stringify(p.rules?.rules?.[1])
    );
    check(
      "burden لا يُرسَل — يُبنى UNKNOWN في الخادم",
      !("burden" in (p.claims?.claims?.[0] ?? {}))
    );
    check(
      "والعربية لا تصل إلى أيّ حقل تعديد",
      !JSON.stringify(p).includes("ابتدائي")
    );
  }
}

/* ── ٤. نقصٌ في مجموعةٍ لا يُسقِط الأخرى ────────────────────────────────── */

console.log("\n[٤] مجموعةٌ واحدة لا غير:");
{
  const state = emptyGenerateInputs();
  state.authorities = [
    {
      key: "a1",
      instrument: "نظام",
      article: "",
      kind: "local_law",
      officialSource: "",
      inForceFrom: "",
      inForceTo: "",
      amendedBy: "",
      retrievedFrom: "",
      conditions: "",
      exceptions: "",
    },
  ];
  const result = buildGeneratePayload(state);
  check("البناء ينجح", result.ok === true);
  if (result.ok) {
    check("«authority» موجود", "authority" in result.payload);
    check("«claims» غائب", !("claims" in result.payload));
    check("«deadlines» غائب", !("deadlines" in result.payload));
    check("«rules» غائب", !("rules" in result.payload));
    check(
      "والسند الواحد في قائمته",
      result.payload.authority?.authorities?.length === 1
    );
  }
}

/* ── الحصيلة ────────────────────────────────────────────────────────────── */

console.log(
  `\n${failures === 0 ? "كل الفحوص نجحت" : "فشل بعض الفحوص"} — ${checks - failures}/${checks}\n`
);
process.exitCode = failures === 0 ? 0 : 1;
