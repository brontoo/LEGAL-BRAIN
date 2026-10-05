# موجّهات توليد صور الفريق — للاستخدام في Gemini (Nano Banana / Imagen)

> **الفريق خمسة، بأسمائهم الموجودة في النظام** — لا بأسماء مخترعة:
> «أمين المكتبة» و«مُسوَدَّة أفندي» و«المفتش ثُغرة» و«سيبويه المُكشّر»
> من `smart_office.py`، و«المعلم أبو الختم» من `office_test.py`.
>
> **والزيّ:** بدلات رسمية وقمصان وكرافيتات — **لا أزياء تقليدية أو إقليمية**.

---

## ١. كتلة الأسلوب المشتركة — الصقها أولاً في كل مرة

```text
Stylized 3D character render, warm cinematic lighting, semi-realistic with soft
rounded shapes — the look of a modern animated feature, not a photograph.

Upper body only, from the chest up. No desk, no table, no chair in frame.

Character centered, facing the viewer at a slight three-quarter angle, engaged
and mid-task, as if caught in the middle of their work.

A modern international law office. Formal business attire — tailored suits,
dress shirts and neckties. An ethnically diverse team. Do not depict traditional
or regional dress of any kind.

Soft warm amber rim light from the upper left, deep navy dark background
(#0F1525), subtle cool fill from the right.

Bold, readable silhouette that stays legible when scaled down to 112 pixels.

Square 1:1 composition. Absolutely no legible text or lettering anywhere —
documents, if present, appear only as blurred abstract lines.
```

**ولا يتغيّر منها حرف واحد بين الخمسة.** أي تعديل يجعل الصور من عوالم مختلفة.

**وتمييز الشخصيات يأتي من ثلاثة أشياء لا من الزيّ:** لون البدلة، ولون الكرافة،
والأداة في يده. وهذا مقصود: الزيّ واحد فلا يشتّت، والاختلاف في الشخص نفسه.

---

## ٢. الموجّهات الخمسة

### `library.png` — أمين المكتبة

يجمع الأسانيد من الأرشيف، وهو من يعمل في كل مراحل البحث.

```text
Male archivist in his early 40s, short dark hair, thin rectangular glasses,
medium build. He wears a dark grey suit jacket over a light blue dress shirt
with a navy tie loosened at the collar and his sleeves pushed up — a man in the
middle of physical work. He is lifting a thick lever-arch file from a tall
shelf just behind him, a second file tucked under one arm, three loose paper
sheets slipping free and fluttering near his shoulder. Capable, unhurried,
faintly pleased — a man who always finds the document.
```

### `drafter.png` — مُسوَدَّة أفندي

وكيل الصياغة. والاسم نفسه نكتة: «مسوَدَّة» درجة أولى من الكتابة، ولقب «أفندي» من زمن مضى.

```text
Male legal drafter in his mid 40s, neatly trimmed dark beard. He wears an
immaculate navy three-piece suit with a crisp white shirt, a burgundy striped
silk tie and gold cufflinks — a man who dresses as carefully as he drafts. He
leans forward over a half-written page held in one hand, a slim gold fountain
pen poised in the other, caught mid-sentence. A neat stack of bound pleadings
sits at the edge of the frame. Intent, quietly theatrical — a man who writes
first drafts as if they were final judgments.
```

### `inspector.png` — المفتش ثُغرة

المدقق القانوني. واسمه نكتة كاملة: مفتش اسمه «ثُغرة».

```text
Male legal inspector in his early 50s, grey-streaked hair and a close-cropped
grey beard, heavy brows. He wears a charcoal suit with a white shirt and a dark
tie pulled slightly askew after a long day. He holds a single page up close to
his face and squints at it sideways, one eyebrow raised, a red pen gripped like
a scalpel in the other hand. Two more pages covered in red margin marks sit in
front of him. Sharp, suspicious, delighted to have found something.
```

### `polisher.png` — سيبويه المُكشّر

المدقق اللغوي. وسيبويه عالم النحو الأسطوري، و«المُكشّر» أي العابس — فالوجه عابس دائماً.

```text
Older male language scholar in his early 60s, long white beard, silver hair,
small round brass spectacles pushed up onto his forehead. He wears a black
waistcoat over a white dress shirt with a black bow tie, and a silver pocket
watch chain across the waistcoat — an old-fashioned pedant who has never once
approved of a comma. His expression is a permanent, theatrical frown of
displeasure: brows furrowed, lips pressed tight. He holds a page at arm's
length between two fingers as though it smells bad, a fine reed pen in his
other hand. Dignified, pedantic, entirely unimpressed.
```

### `sealer.png` — المعلم أبو الختم

يعتمد ويختم. وهو من يختم المستند النهائي.

```text
Distinguished male senior partner in his early 60s, full white beard, silver
hair swept back. He wears a formal black suit with a matching waistcoat, a
white shirt, a silver silk tie and a white pocket square — the most senior
person in the room, and dressed like it. He presses a large ornate brass seal
down onto a document with deliberate finality, his other hand flat on the
paper. A small brass inkwell and a green wax stick rest beside it. Grave,
ceremonial, and clearly enjoying the moment far more than he lets on.
```

---

## ٣. الموجّه السلبي — الصقه آخر كل موجّه

```text
no text, no letters, no Arabic calligraphy, no numbers, no watermarks, no logos,
no brand marks or insignia, no user interfaces, no screens showing content,
no traditional or regional dress, no robes or gowns, no head coverings,
no distorted hands, no extra fingers, no fused or missing limbs,
no photorealistic skin, no harsh flash lighting,
no busy or cluttered background, no desk, no table, no chair, no cropped head
```

---

## ٤. الإعدادات التقنية

| البند | القيمة |
|---|---|
الأبعاد | **1024×1024** على الأقل — والطولية مقبولة بل أفضل لهذا التخطيط |
الصيغة | **PNG أو JPEG** — ⚠️ **ويجب أن يطابق الامتداد المحتوى الفعلي** |
الحجم | أقلّ من **٢٠٠ كيلوبايت** للصورة |
الخلفية | **`#0F1525`** (وهو لون المشهد) — أو **شفّافة** |
الأسماء | `library` · `drafter` · `inspector` · `polisher` · `sealer` |
المكان | `frontend/public/agents/` |

> ⚠️ **وتنبيه من تجربة فعلية:** الصور الخمس التي وُلِّدت جاءت **JPEG بأسماء
> `.png`**. والامتداد الكاذب **ليس شكلياً**: الخادم يعلن `image/png` والمحتوى
> JPEG، ومع ترويسة `X-Content-Type-Options: nosniff` **يرفض المتصفح رسمها**.
>
> فتحقّق من الصيغة الحقيقية قبل الوضع:
> ```bash
> file frontend/public/agents/library.png
> # إن قال JPEG فغيّر الامتداد إلى .jpg
> ```
>
> والكود يجرّب `.jpg` ثم `.png`، فكلاهما يعمل — **بشرط أن يكون الامتداد صادقاً.**

**والأسماء تطابق مفاتيح الشخصيات في `office-scene.tsx` حرفياً.** واسم خاطئ لا
يُنتج خطأً واضحاً بل يرجع للأيقونة بصمت.

---

## ٥. الاتّساق بين الخمسة — وأضمن طريقة

الصور تُولَّد منفصلة فتخرج بأساليب مختلفة. والأنجع:

| # | الطريقة |
|---|---|
**١** | **جلسة واحدة** — ولّد الخمسة في المحادثة نفسها بلا فتح محادثة جديدة |
**٢** | **صورة مرجعية** — بعد أول صورة ناجحة ارفعها وقل: `match this exact art style, lighting and background` |
**٣** | **ورقة الشخصيات** — **وهي الأضمن**: صورة واحدة فيها الخمسة، ثم اقتطعها |

### موجّه ورقة الشخصيات

```text
A single 5-panel character lineup on a deep navy background (#0F1525), panels
arranged in one horizontal row with generous spacing and thin subtle dividers.
All five are men in formal business attire — suits, dress shirts and neckties.
An ethnically diverse team. No traditional or regional dress of any kind.

Left to right:
(1) archivist, early 40s, short dark hair, thin rectangular glasses, dark grey
suit jacket over a light blue dress shirt with a navy tie loosened and sleeves
pushed up, lifting a thick lever-arch file, loose pages fluttering near his
shoulder;
(2) legal drafter, mid 40s, neatly trimmed dark beard, immaculate navy
three-piece suit, crisp white shirt, burgundy striped silk tie, gold cufflinks,
leaning over a half-written page with a gold fountain pen poised;
(3) legal inspector, early 50s, grey-streaked hair and close-cropped grey
beard, heavy brows, charcoal suit with white shirt and a dark tie pulled
slightly askew, squinting sideways at a page held up close, red pen in hand,
one eyebrow raised;
(4) older language scholar, early 60s, long white beard, silver hair, round
brass spectacles pushed onto his forehead, black waistcoat over a white dress
shirt with a black bow tie and a silver pocket watch chain, permanent
theatrical frown, holding a page at arm's length;
(5) distinguished senior partner, early 60s, full white beard, silver hair
swept back, formal black suit with matching waistcoat, white shirt, silver silk
tie and white pocket square, pressing a large ornate brass seal onto a
document.

All five share one identical art style: stylized 3D character render, semi-
realistic with soft rounded shapes, warm amber rim light from the upper left,
subtle cool fill from the right, matching colour grading and level of detail.
Each figure is upper body only, chest up, centered in its panel, with a bold
readable silhouette. No text, no lettering, no logos anywhere.
```

**ثم اقتطع كل خانة** واحفظها بالاسم المطلوب. والاقتطاع يكفي فيه أي محرّر صور.

---

## ٦. كيف تربطها بالكود

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

```bash
mkdir -p frontend/public/agents
# ضع الصور الخمس بأسمائها هناك
```

ثم أعِد تحميل الصفحة.

> ⚠️ **وقبل إضافة الصور** ستظهر أخطاء `404` لخمسة ملفات `/agents/*.png` في
> طرفية المتصفح. وهي **متوقّعة ولا تعني خللاً** — اخترناها على بديلَين أسوأ:
> علم ثابت يُنسى تشغيله، أو ملف بيان يُنسى تحديثه.

---

## ٧. أربع ملاحظات قبل أن تولّد

| # | الملاحظة |
|---|---|
**١** | **الصور تُعرض بـ ١١٢ بكسل تقريباً.** التفاصيل الدقيقة تضيع — ولهذا يشترط الأسلوب «bold readable silhouette» |
**٢** | **لا نصوص في الصورة.** النماذج تولّد حروفاً مشوّهة، والأسماء مكتوبة في HTML تحتها |
**٣** | **التمييز يأتي من لون البدلة والكرافة والأداة** — لا من الزيّ. فلو تغيّرت البدلات كثيراً بين صورة وأخرى اختلّ الاتّساق |
**٤** | **الخمسة كلهم رجال بحكم أسمائهم** — «أفندي» و«سيبويه» و«أبو الختم» ألقاب مذكّرة. وهذا ما تعنيه أسماء النظام، لا اختياراً منّي. فإن أردت تنويعاً فالموجّه يُعدَّل في سطرين |
