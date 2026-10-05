# موجّهات توليد صور الفريق — للاستخدام في Gemini (Nano Banana / Imagen)

> **الفريق خمسة، بأسمائهم الموجودة في النظام** — لا بأسماء مخترعة:
> «أمين المكتبة» و«مُسوَدَّة أفندي» و«المفتش ثُغرة» و«سيبويه المُكشّر»
> من `smart_office.py`، و«المعلم أبو الختم» من `office_test.py`.

---

## ١. كتلة الأسلوب المشتركة — الصقها أولاً في كل مرة

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

**ولا يتغيّر منها حرف واحد بين الخمسة.** أي تعديل يجعل الصور من عوالم مختلفة.

---

## ٢. الموجّهات الخمسة

### `library.png` — أمين المكتبة

يجمع الأسانيد من الأرشيف، وهو من يعمل في كل مراحل البحث.

```text
Male Gulf-Arab archivist in his early 40s, short black hair, thin rectangular
glasses, light beige kandura with the sleeves rolled to the forearm. He is
mid-motion lifting a thick lever-arch file from a tall shelf just behind him,
a second file tucked under one arm, three loose paper sheets slipping free and
fluttering near his shoulder. Capable, unhurried, faintly pleased — a man who
always finds the document.
```

### `drafter.png` — مُسوَدَّة أفندي

وكيل الصياغة. والاسم نفسه نكتة: «مسوَدَّة» درجة أولى من الكتابة، ولقب «أفندي» من زمن مضى.

```text
Male Gulf-Arab legal drafter in his mid 40s, neatly trimmed black beard,
wearing a crisp white kandura with a dark waistcoat and a white ghutra. He
leans forward over a half-written page held in one hand, a slim gold fountain
pen poised in the other, caught mid-sentence. A neat stack of bound pleadings
sits at the edge of the frame. Intent, quietly theatrical — a man who writes
first drafts as if they were final judgments.
```

### `inspector.png` — المفتش ثُغرة

المدقق القانوني. واسمه نكتة كاملة: مفتش اسمه «ثُغرة».

```text
Male Gulf-Arab legal inspector in his early 50s, grey-streaked hair and a
close-cropped grey beard, wearing a charcoal suit without a tie and a plain
white shirt. He holds a single page up close to his face and squints at it
sideways, one eyebrow raised, a red pen gripped like a scalpel in the other
hand. Two more pages covered in red margin marks sit in front of him. Sharp,
suspicious, delighted to have found something.
```

### `polisher.png` — سيبويه المُكشّر

المدقق اللغوي. وسيبويه عالم النحو الأسطوري، و«المُكشّر» أي العابس — فالوجه عابس دائماً.

```text
Male Gulf-Arab language scholar in his early 60s, long white beard, small round
brass spectacles pushed up onto his forehead, wearing a deep green scholar's
robe over a white kandura. His expression is a permanent, theatrical frown of
displeasure — brows furrowed, lips pressed tight. He holds a page at arm's
length between two fingers as though it smells bad, a fine reed pen in his
other hand. Dignified, pedantic, entirely unimpressed.
```

### `sealer.png` — المعلم أبو الختم

يعتمد ويختم. وهو من يختم المستند النهائي.

```text
Male Gulf-Arab senior master in his early 60s, full white beard, wearing an
elegant cream bisht over a white kandura with a white ghutra and a black agal.
He presses a large ornate brass seal down onto a document with deliberate
finality, his other hand flat on the paper. A small brass inkwell and a green
wax stick rest beside it. Grave, ceremonial, and clearly enjoying the moment
far more than he lets on.
```

---

## ٣. الموجّه السلبي — الصقه آخر كل موجّه

```text
no text, no letters, no Arabic calligraphy, no numbers, no watermarks, no logos,
no brand marks, no user interfaces, no screens showing content, no distorted
hands, no extra fingers, no fused or missing limbs, no photorealistic skin,
no harsh flash lighting, no busy or cluttered background, no desk, no table,
no chair, no cropped head, no Western corporate branding
```

---

## ٤. الإعدادات التقنية

| البند | القيمة |
|---|---|
الأبعاد | **مربّع 1:1** · **1024×1024** على الأقل |
الصيغة | **PNG** |
الخلفية | **`#0F172A`** (لون التطبيق) — أو **شفّافة** إن دعمها النموذج |
الأسماء | `library.png` · `drafter.png` · `inspector.png` · `polisher.png` · `sealer.png` |
المكان | `frontend/public/agents/` |

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
A single 5-panel character lineup on a deep navy background (#0F172A), panels
arranged in one horizontal row with generous spacing and thin subtle dividers.

Left to right:
(1) male Gulf-Arab archivist, early 40s, black hair, thin rectangular glasses,
beige kandura with rolled sleeves, lifting a thick lever-arch file, loose pages
fluttering near his shoulder;
(2) male Gulf-Arab legal drafter, mid 40s, trimmed black beard, white kandura
with dark waistcoat and white ghutra, leaning over a half-written page with a
gold fountain pen poised;
(3) male Gulf-Arab legal inspector, early 50s, grey-streaked hair and beard,
charcoal suit no tie, squinting sideways at a page held up close, red pen in
hand, one eyebrow raised;
(4) male Gulf-Arab language scholar, early 60s, long white beard, round brass
spectacles pushed onto his forehead, deep green scholar's robe over a white
kandura, permanent theatrical frown, holding a page at arm's length;
(5) male Gulf-Arab senior master, early 60s, full white beard, cream bisht over
a white kandura with white ghutra and black agal, pressing a large ornate brass
seal onto a document.

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

## ٧. ثلاث ملاحظات قبل أن تولّد

| # | الملاحظة |
|---|---|
**١** | **الصور تُعرض بـ ١١٢ بكسل تقريباً.** التفاصيل الدقيقة تضيع — ولهذا يشترط الأسلوب «bold readable silhouette» |
**٢** | **لا نصوص في الصورة.** النماذج تولّد حروفاً مشوّهة، والأسماء مكتوبة في HTML تحتها |
**٣** | **الخمسة كلهم رجال بحكم أسمائهم** — «أفندي» و«سيبويه» و«أبو الختم» ألقاب مذكّرة. وهذا ما تعنيه أسماء النظام، لا اختياراً منّي. فإن أردت تنويعاً فالموجّه يُعدَّل في سطرين |
