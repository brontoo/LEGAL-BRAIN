# ============================================================================
# الخلفية: FastAPI + نموذج تضمين محلي + دعم OCR العربي
# ============================================================================

FROM python:3.12-slim-bookworm

# منع أدوات Debian من محاولة فتح واجهة تفاعلية أثناء البناء
ENV DEBIAN_FRONTEND=noninteractive

# إعدادات Python والتطبيق
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    HF_HOME=/data/hf \
    PORT=8080

# git مطلوب لأن requirements.txt يحتوي على:
# swarmmy @ git+https://github.com/loayabdalslam/Swarmmy.git
#
# tesseract-ocr-ara لاستخراج النص العربي
# poppler-utils لتحويل ومعالجة ملفات PDF
# ca-certificates لاتصالات HTTPS مع GitHub وPyPI وHugging Face
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-ara \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# تحديث أدوات تثبيت وبناء حزم Python
RUN python -m pip install --upgrade \
        pip \
        setuptools \
        wheel

# تثبيت نسخة CPU فقط من PyTorch
# استخدم الرابط النصي العادي، دون أي وسوم HTML
RUN python -m pip install \
        --index-url https://download.pytorch.org/whl/cpu \
        torch

# نسخ المتطلبات أولاً للاستفادة من Docker layer cache
COPY requirements.txt ./

# يمكن الآن تثبيت Swarmmy من GitHub لأن git أصبح مثبتاً
RUN python -m pip install -r requirements.txt

# نسخ ملفات التطبيق
COPY . .

# إنشاء مسار تخزين نماذج Hugging Face
RUN mkdir -p /data/hf

EXPOSE 8080

# يجب أن يطابق المنفذ internal_port = 8080 في fly.toml
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log"]