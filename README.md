# ⚖️ LEGAL-BRAIN — العقل القانوني الإماراتي

منصة عربية أولاً (Arabic-first) لتوليد المستندات القانونية الإماراتية **بأسلوب المحامي نفسه**.

الفكرة ليست الإجابة عن أسئلة قانونية عامة، بل استرجاع **سوابق المستخدم الشخصية** — عقوده،
إنذاراته، لوائحه، وكالاته، تشريعاته — ثم صياغة مستند جديد بنفس نبرته وهيكله ومفرداته.

---

## ما الذي يفعله النظام

| العائلة المستندية | المصدر | جدول قاعدة المعرفة |
|---|---|---|
| تشريعات وأحكام | HTML من موقع التشريعات + PDF ممسوح (OCR) | `legal_documents` |
| مذكرات ولوائح | PDF / DOCX | `legal_drafts` |
| عقود واتفاقيات | PDF / DOCX | `legal_contracts` |
| إنذارات | PDF / DOCX | `legal_notices` |
| وكالات | PDF / DOCX | `legal_poa` |

يُقطَّع كل مستند إلى وحدات دلالية (مادة / بند / قسم / صلاحية)، تُحوَّل إلى متجهات
بعدد 1024 بُعداً بنموذج `intfloat/multilingual-e5-large`، وتُخزَّن في Supabase
(PostgreSQL + pgvector). ثم يسترجع وكيل LangGraph السوابق الأقرب دلالياً ويصوغ
المستند الجديد.

---

## المعمارية

```
Google Drive (5 مجلدات)
      │
      ▼  ① الاستيعاب — 6 سكربتات
 [ html / pdf / notices / contracts / drafts / poa ]_ingester.py
      │
      ▼  ② قاعدة المعرفة — Supabase + pgvector
 5 جداول + 5 دوال match_legal_*        ← schema.sql
      │
      ▼  ③ العقل — LangGraph ReAct
 legal_agent.py : Gemini + 5 أدوات RAG
      │
      ▼  ④ الواجهات
 main.py (FastAPI + SSE) ──> frontend/ (Next.js 16)
 app_chainlit.py (Chainlit) │ smart_office.py (سرب 3 وكلاء) │ ask_brain.py (CLI)
```

---

## المتطلبات

| المكوّن | الإصدار |
|---|---|
| Python | 3.11+ (طُوِّر على 3.14) |
| Node.js | 20.19+ أو 22.12+ (اختُبر على 24) |
| PostgreSQL | مع امتداد `vector` (Supabase يوفّره) |

**حزم نظام مطلوبة لمسار الـ OCR** (ليست حزم pip):

```bash
# Ubuntu / Debian
sudo apt install tesseract-ocr tesseract-ocr-ara poppler-utils

# macOS
brew install tesseract tesseract-lang poppler
```

للتحقق: `tesseract --list-langs` يجب أن تُظهر `ara`، و`pdftoppm -v` يجب أن يعمل.

---

## التثبيت

```bash
# ١. اعتماديات بايثون — تكفي لتشغيل الخادم وخطوط الاستيعاب
pip install -r requirements.txt

# ١-ب. اختياري: واجهة Chainlit + مزوّد Groq البديل
#      (لا يحتاجها main.py — تُثبَّت عند الحاجة إليها فقط)
pip install -r requirements-optional.txt

# ٢. متغيّرات البيئة
cp .env.example .env          # ثم املأ المفاتيح الفعلية

# ٣. اعتماد Google (للاستيعاب فقط، لا يلزم لتشغيل الخادم)
#    ضع ملف مفتاح حساب الخدمة باسم credentials.json في جذر المشروع

# ٤. بناء قاعدة المعرفة — نفّذ محتوى schema.sql داخل Supabase SQL Editor

# ٥. واجهة Next.js
cd frontend
cp .env.local.example .env.local
npm install
```

> **ملاحظة:** أول تشغيل يحمّل نموذج التضمين `intfloat/multilingual-e5-large` (~2.2 GB).

---

## التشغيل

```bash
# الخادم الخلفي (FastAPI)
uvicorn main:app --reload --port 8000

# الواجهة الأمامية — في طرفية أخرى
cd frontend && npm run dev          # http://localhost:3000

# (اختياري) واجهة Chainlit
chainlit run app_chainlit.py

# (اختياري) تعبئة قاعدة المعرفة — عدّل معرّف المجلد داخل كل ملف أولاً
python notices_ingester.py
python contracts_ingester.py
```

---

## واجهة الـ API

| الطريقة | المسار | الوصف |
|---|---|---|
| `GET` | `/` | صفحة اختبار مستقلة للبثّ الحي (SSE) |
| `GET` | `/health` | فحص الصحة وجاهزية الأدوات |
| `POST` | `/generate` | توليد مستند ببثّ حيّ — تستخدمه واجهة Next.js |
| `POST` | `/chat` | محادثة بردّ JSON كامل |

**عقد البثّ (SSE) من `/generate`:**

```
data: {"type": "stage", "message": "جاري البحث في التشريعات والأحكام الاتحادية..."}
data: {"type": "stage", "message": "تم استرجاع السند من أرشيفك — جاري الصياغة..."}
data: {"type": "done",  "document": "إنذار قانوني\n\nالسيد/ ..."}
data: {"type": "error", "message": "..."}
```

مثال:

```bash
curl -N -X POST http://localhost:8000/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"مطالبة مالية 20,000 درهم عن فواتير غير مسددة","doc_type":"لائحة دعوى تجارية"}'
```

---

## متغيّرات البيئة

### الخادم (`.env`)

| المتغيّر | إلزامي | الوصف |
|---|---|---|
| `SUPABASE_URL` | ✅ | عنوان مشروع Supabase |
| `SUPABASE_KEY` | ✅ | مفتاح API — يُستخدم للكتابة والبحث |
| `GOOGLE_API_KEY` | ✅ | مفتاح Gemini (الوكيل الأساسي) |
| `GROQ_API_KEY` | ❌ | مطلوب فقط لـ `ask_brain.py` و `test_groq.py` |
| `ALLOWED_ORIGINS` | ❌ | نطاقات CORS مفصولة بفاصلة |
| `MAX_HISTORY_TURNS` | ❌ | أدوار المحادثة المحفوظة لكل جلسة (افتراضي 6) |
| `PORT` | ❌ | منفذ `python main.py` (افتراضي 8000) |

### الواجهة (`frontend/.env.local`)

| المتغيّر | الوصف |
|---|---|
| `NEXT_PUBLIC_API_URL` | عنوان خادم FastAPI (افتراضي `http://localhost:8000`) |

---

## الأدوات المتاحة للوكيل

| الأداة | الغرض | دالة الـ SQL | العتبة |
|---|---|---|---|
| `search_uae_legislation` | التشريعات والأحكام | `match_legal_documents` | 0.75 |
| `search_drafting_style` | أسلوب المذكرات واللوائح | `match_legal_drafts` | 0.70 |
| `search_contract_clauses` | بنود العقود | `match_legal_contracts` | 0.70 |
| `search_legal_notices` | صيغ الإنذارات | `match_legal_notices` | 0.70 |
| `search_poa_clauses` | صلاحيات الوكالات | `match_legal_poa` | 0.70 |

عتبة التشريعات أعلى عمداً: الدقة القانونية لا تحتمل اجتهاداً.

---

## حلّ المشكلات

| العرض | السبب المرجّح |
|---|---|
| الخادم لا يبدأ / `create_client` يفشل | `.env` ناقص أو غير مُحمَّل |
| «لا توجد نصوص مطابقة» دائماً | سكربتات الاستيعاب لم تُشغَّل، أو `schema.sql` لم يُنفَّذ |
| `match_legal_* does not exist` | لم تُنفَّذ دوال الـ RPC في `schema.sql` |
| الواجهة تبقى في شاشة التحميل | تأكد أن `NEXT_PUBLIC_API_URL` يطابق منفذ الخادم |
| خطأ CORS في المتصفح | أضف عنوان الواجهة إلى `ALLOWED_ORIGINS` في `.env` |
| `tesseract` يفشل | حزمة اللغة العربية `ara` غير مثبَّتة |
| OCR ينتج نصاً مشوّهاً | ملف PDF صوري بجودة منخفضة، أو حزمة `ara` مفقودة |

---

## الفجوات المعروفة

- **لا اختبارات آلية** — لا اختبارات وحدة ولا تكامل ولا واجهة.
- **معرّفات مجلدات Drive مُثبَّتة داخل الكود** (ثابت `*_FOLDER_ID` في كل سكربت استيعاب) —
  الأفضل نقلها إلى `.env`.
- **`ingest_documents.py` مكرر** لـ `html_ingester.py` (جيل أقدم يستخدم OAuth بدل حساب الخدمة،
  ويستدعي `flow.run_console()` المُزال من `google-auth-oauthlib` 1.x).
- **تحميل ثقيل عند الاستيراد** — `legal_agent.py` يحمّل نموذج التضمين ويتصل بـ Supabase على
  مستوى الوحدة، فيصعب اختباره ويُبطئ الإقلاع.
- **لا مصادقة على الـ API** — أي وصول للخادم يصل إلى الأرشيف القانوني.
- **بيانات الواجهة وهمية** في لوحة القيادة والمكتبة (لا تتصل بالـ backend بعد)، واللوحة تذكر
  «Qdrant» بينما المخزن الفعلي هو Supabase/pgvector.
- **`server.py` حُذف** — كان نسخة مكررة حرفياً من `main.py`. للاستعادة:
  `git checkout HEAD -- server.py`.

---

## ⚠️ الأمان

`.env` و`credentials.json` و`token.pickle` مُستثناة من git — لا ترفعها أبداً.
إن كانت `SUPABASE_KEY` هي `service_role` فهي تتجاوز RLS وتملك صلاحية كاملة على القاعدة:
لا تضعها في أي متغيّر يبدأ بـ `NEXT_PUBLIC_` ولا تُرسلها إلى المتصفح.

---

## الترخيص

مشروع خاص — جميع الحقوق محفوظة.
