# موجّهات توليد صور الفريق — للاستخدام في Gemini (Nano Banana / Imagen)

> **الغرض:** توليد صورة لكل موظّف في «مشهد المكتب»، فتُستبدل الأيقونات بوجوه
> وأشخاص. الكود جاهز لها بالفعل — يكفي إسقاط الملفات في المجلد المذكور أدناه.

---

## ١. كيف تستخدم هذا الملف

لكل موظّف **موجّهان**: كتلة الأسلوب المشتركة، ووصف الشخص. الصقهما متتاليين.

```
[كتلة الأسلوب المشتركة]  ← نفسها في التسعة كلها
[وصف الشخص]              ← يختلف لكل موظّف
[الموجّه السلبي]         ← نفسه في التسعة كلها
```

**والأهم:** كتلة الأسلوب والموجّه السلبي **لا يتغيّران أبداً**. أي تعديل فيهما
يجعل صور التسعة تبدو من عوالم مختلفة.

---

## ٢. كتلة الأسلوب المشتركة — الصقها أولاً في كل مرة

```text
Stylized 3D character render, warm cinematic lighting, semi-realistic with soft
rounded shapes — the look of a modern animated feature, not a photograph.

Upper body only, from the chest up. No desk, no table, no chair in frame.

Character centered, facing the viewer at a slight three-quarter angle, engaged
and mid-task, as if caught in the middle of their work.

Attire and props suggest a modern Gulf-Arab law office. Soft warm amber rim
light from the upper left, deep navy dark background (#0F172A), subtle cool
fill from the right.

Bold, readable silhouette that stays legible when scaled down to 112 pixels.

Square 1:1 composition. Absolutely no legible text or lettering anywhere —
documents, if present, appear only as blurred abstract lines.
```

---

## ٣. موجّهات الموظّفين التسعة

### `intake.png` — أ. حيث إن — مدير المكتب

```text
Male Emirati office manager in his early 50s, neatly trimmed grey-flecked
beard, wearing a crisp white kandura with a dark brown bisht over the
shoulders and a white ghutra. He holds a slim gold fountain pen and gestures
with one open hand as if opening a formal statement. A short stack of burgundy
case folders sits at the edge of the frame. Calm, authoritative, faintly
amused — a man who begins every sentence with "whereas".
```

### `evidence.png` — حافظ — أمين الأرشيف

```text
Male archivist in his early 30s, short black hair, thin modern glasses, wearing
a light beige kandura with the sleeves rolled. He is mid-motion pulling a thick
lever-arch file toward himself with both hands, a second file tucked under one
arm, a few loose paper sheets fluttering near his shoulder. Warm and helpful,
slightly out of breath — a man who always finds the document.
```

### `legislation.png` — أ. مادة — التشريعات والأحكام

```text
Female legal researcher in her early 30s, wearing an elegant charcoal abaya
with subtle geometric embroidery and a matching hijab, round glasses. Three
semi-transparent holographic document panels float in front of her, rendered
as abstract glowing pages with blurred unreadable lines. Her right hand is
raised, index finger touching one panel as if selecting the exact provision.
Focused and precise.
```

### `drafts.png` — أ. صيغة — أسلوب المذكرات

```text
Male legal drafter in his early 40s, clean-shaven, wearing a navy suit over a
white shirt with no tie and the sleeves slightly pushed up. He holds two sheets
of paper side by side and compares them, a red pen clipped behind his ear. A
neat stack of bound pleadings sits at the edge of the frame. Thoughtful and
discerning — a man measuring someone else's words against a house style.
```

### `contracts.png` — أ. بند — بنود العقود

```text
Female contracts specialist in her mid 40s, wearing a deep green abaya with a
cream hijab. She holds a thick contract bound with a red ribbon and a round wax
seal, and a heavy brass official stamp in her other hand. Her gaze is sharp and
appraising, caught mid-clause. Confident and exacting.
```

### `notices.png` — أ. مهلة — صيغ الإنذارات

```text
Male notices officer in his early 30s, short beard, wearing a grey kandura with
a patterned ghutra. He holds a sealed envelope with a red wax seal raised
slightly toward the viewer, and a small brass hourglass rests beside his hand.
Slightly urgent and purposeful — a man who counts days for a living.
```

### `poa.png` — أ. وكيلة — صيغ الوكالات

```text
Female power-of-attorney specialist in her early 30s, wearing a burgundy abaya
and a silk hijab. She presents a notarised power of attorney document tied with
a green ribbon and a heavy embossed notary seal, an ornate fountain pen in her
other hand. Composed, precise, formally polite.
```

### `drafting.png` — أ. مسودة — الكاتب القانوني

```text
Male legal writer in his early 30s, short dark hair, wearing a light blue shirt
with a loosened tie and rolled-up sleeves. He leans slightly forward, fingers
poised as if over a keyboard just below the frame, glancing up mid-sentence. A
half-written page hovers near his shoulder, rendered as blurred unreadable
lines. Concentrated and wry.
```

### `verifying.png` — أ. سند — تدقيق الأسانيد

```text
Female auditor in her mid 40s, wearing a dark slate abaya and a plain hijab,
thin wire glasses. She holds a large round magnifying glass over a document,
a green rubber stamp beside her hand. Her expression is scrupulous and
unhurried — a woman who trusts only what she can read for herself.
```

---

## ٤. الموجّه السلبي — الصقه آخر كل موجّه

```text
no text, no letters, no Arabic calligraphy, no numbers, no watermarks, no logos,
no brand marks, no user interfaces, no screens showing content, no distorted
hands, no extra fingers, no fused or missing limbs, no photorealistic skin,
no harsh flash lighting, no busy or cluttered background, no desk, no table,
no chair, no cropped head, no Western corporate branding
```

---

## ٥. الإعدادات التقنية

| البند | القيمة |
|---|---|
الأبعاد | **مربّع 1:1** · **1024×1024** على الأقل |
الصيغة | **PNG** |
الخلفية | **`#0F172A`** (نفس لون التطبيق) — أو **شفّافة** إن دعمها النموذج |
الأسماء | **حرفياً**: `intake.png` · `evidence.png` · `legislation.png` · `drafts.png` · `contracts.png` · `notices.png` · `poa.png` · `drafting.png` · `verifying.png` |
المكان | `frontend/public/agents/` |

> **الأسماء يجب أن تطابق مفاتيح المراحل حرفياً** — والكود يقرأ الملف باسم
> المفتاح. واسم خاطئ لا يُنتج خطأً واضحاً بل يرجع للأيقونة بصمت.

---

## ٦. أكبر تحدٍّ: **الاتّساق بين التسع**

الصور تُولَّد منفصلة، فتخرج غالباً بأساليب مختلفة. وهذه أنجع الطرق المجرَّبة:

| # | الطريقة | التفصيل |
|---|---|---|
**١** | **جلسة واحدة** | ولّد التسعة في **المحادثة نفسها** بلا فتح محادثة جديدة — السياق يحمل الأسلوب |
**٢** | **صورة مرجعية** | بعد أول صورة ناجحة، **ارفعها** مع الموجّه التالي وقل: `match this exact art style, lighting and background` |
**٣** | **ورقة شخصيات** | ولّد **صورة واحدة** فيها التسعة في شبكة ٣×٣ بموجّه واحد، ثم **اقتطع** كل شخص. **وهذا أضمن طريقة للاتّساق** |
**٤** | **أعد التوليد لا التعديل** | إن جاءت واحدة مختلفة، أعد توليدها بالطريقة ٢ لا أن تعدّلها بالكلام |

### موجّه «ورقة الشخصيات» — الطريقة الأضمن

```text
A 3x3 grid character sheet of nine different Gulf-Arab legal professionals,
each in their own square cell with generous spacing and a thin subtle divider,
arranged on a deep navy background (#0F172A).

Top row, left to right:
(1) male office manager, early 50s, grey-flecked beard, white kandura with dark
brown bisht and white ghutra, holding a gold fountain pen, gesturing open-handed;
(2) male archivist, early 30s, black hair, thin glasses, beige kandura, sleeves
rolled, pulling a thick lever-arch file toward himself;
(3) female legal researcher, early 30s, charcoal abaya with geometric embroidery
and matching hijab, round glasses, hand raised toward floating glowing document
panels.

Middle row, left to right:
(4) male legal drafter, early 40s, clean-shaven, navy suit no tie, sleeves pushed
up, comparing two sheets of paper, red pen behind his ear;
(5) female contracts specialist, mid 40s, deep green abaya, cream hijab, holding a
thick ribbon-bound contract with a wax seal and a brass stamp;
(6) male notices officer, early 30s, short beard, grey kandura with patterned
ghutra, holding a sealed envelope with a red wax seal, brass hourglass nearby.

Bottom row, left to right:
(7) female power-of-attorney specialist, early 30s, burgundy abaya and silk hijab,
presenting a green-ribboned notarised document with an embossed notary seal;
(8) male legal writer, early 30s, light blue shirt, loosened tie, rolled sleeves,
leaning forward mid-sentence, a half-written page hovering nearby;
(9) female auditor, mid 40s, dark slate abaya, plain hijab, wire glasses, holding
a large magnifying glass over a document, green rubber stamp beside her hand.

All nine share one identical art style: stylized 3D character render, semi-
realistic with soft rounded shapes, warm amber rim light from the upper left,
subtle cool fill from the right, matching colour grading, matching level of
detail. Each figure is upper body only, chest up, centered in its cell, with a
bold readable silhouette. No text, no lettering, no logos anywhere.
```

**ثم اقتطع كل خانة** واحفظها بالاسم المطلوب. والاقتطاع يكفي بأي محرّر صور.

---

## ٧. صورة خلفية للمكتب (اختيارية)

إن أردت خلفية غنية بدل الجدار المرسوم بـ CSS:

```text
Wide panoramic interior of a modern Gulf-Arab law office at night, empty of
people: rows of dark wooden desks with brass desk lamps glowing warm amber,
tall bookshelves of leather-bound legal volumes along the back wall, a large
arched window showing a distant city skyline, deep navy and charcoal palette
with warm amber accents, stylized 3D render, soft cinematic lighting, subtle
depth of field, painterly and calm. Ultra wide 21:9. No people, no text, no
lettering, no logos.
```

> **تنبيه:** خلفية مزدحمة تُشتّت عن الشخصيات المصغّرة. الخلفية الحالية المرسومة
> بـ CSS مقصودة لأنها **هادئة**: نافذة ونبتة فقط.

---

## ٨. كيف تربطها بالكود

**لا تحتاج أي تعديل برمجي.** الكود يحاول تحميل الصورة، وإن لم يجدها يرجع إلى
الأيقونة تلقائياً:

```tsx
// office-scene.tsx
const [artFailed, setArtFailed] = useState(false);
...
<motion.img
  src={`/agents/${worker.key}.png`}
  onError={() => setArtFailed(true)}   // ← الرجوع للأيقونة
  ...
/>
```

**فالخطوات:**

```bash
mkdir -p frontend/public/agents
# ضع الصور التسع بأسمائها هناك
```

ثم أعِد تحميل الصفحة. **وشاهد الفريق يظهر واحداً بعد واحد** كلما أضفت صورة.

> ⚠️ **وقبل إضافة الصور** ستظهر في طرفية المتصفح أخطاء `404` لتسعة ملفات
> `/agents/*.png`. وهي **متوقّعة ولا تعني خللاً** — اخترناها على بديلَين أسوأ:
> علم ثابت يُنسى تشغيله، أو ملف بيان يُنسى تحديثه عند إضافة صورة.

---

## ٩. قبل أن تولّد — ثلاثة تنبيهات

| # | التنبيه |
|---|---|
**١** | **الصور تُعرض بحجم ١١٢ بكسل تقريباً.** التفاصيل الدقيقة تضيع — اطلب دائماً «bold readable silhouette» |
**٢** | **لا نصوص في الصورة.** النماذج تولّد حروفاً مشوّهة، والأسماء مكتوبة في HTML تحتها. ولهذا الموجّه السلبي يشترط ذلك |
**٣** | **الأزياء الخليجية المهنية مقصودة.** السياق إماراتي، والصور بلا وجوه كرتونية مبالغ فيها. وإن رأيت تمثيلاً غير لائق لأي مهنة فتغيير الموجّه أرخص من تعديل الصورة |
