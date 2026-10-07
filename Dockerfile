# ============================================================================
# الخلفية: FastAPI + نموذج تضمين محلي
# ----------------------------------------------------------------------------
# ⚠️ **ولماذا حاوية لا serverless؟** لأن الحزمة ٥٨٢٦ م.ب والحدّ ٥٠٠ — **ولأن
# `torch` يحتاج ذاكرةً وقرصاً دائماً، **ولأن `tesseract` و`poppler` **مكتبات
# نظام** لا تُثبَّت بـ`pip`.** ⇒ فالمضيف **حاوية** لا دالّة.
# ============================================================================

FROM python:3.12-slim

# ⚠️ **و`tesseract-ocr-ara` هو المهمّ**: بدونه **يفشل استخراج النصّ العربي**
# من المستندات المصوَّرة — وهو **جوهر المنصّة** لا زينة.
# ⚠️ و`poppler-utils` يلزمه `pdf2image` لتحويل صفحات PDF إلى صور.
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-ara \
      poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ⚠️ **و`torch` بطبعة CPU أوّلاً، قبل بقية المتطلبات.**
# فالطبعة الافتراضية تجرّ حزم CUDA (~٢.٥ ج.ب) **ولا بطاقة رسوميات على المضيف**
# ⇒ فتُنزَّل بلا فائدة، **وتُبطئ البناء وتُضخّم الصورة**. وتثبيتها هنا
# **يُشبع** متطلَّب `sentence-transformers` فلا يُعاد تنزيلها بحزم CUDA.
RUN pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      torch

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ⚠️ **والنموذج في قرصٍ دائم**: `HF_HOME` تُوجّه مخزن Hugging Face.
# وبلا قرصٍ مُوصَّل على `/data`، **يُعاد تنزيل ~٢ ج.ب في كل إعادة تشغيل**.
ENV HF_HOME=/data/hf
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# ⚠️ **و`PORT` يُقرأ من البيئة كما يقرأه `main.py` نفسه** — فالمضيف يفرضه
# ولا يجوز تثبيته.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
