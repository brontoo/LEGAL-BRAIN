#!/usr/bin/env bash
# ==============================================================================
# LEGAL-BRAIN — تجهيز بيئة بايثون بلا استهلاك ٣.٣ غيغابايت
# ==============================================================================
#     bash scripts/setup-python.sh
#
# ⚠️ لماذا هذا الملف موجود — وهو يمنع أكبر استهلاك في المشروع؟
#
# `sentence-transformers` يجبر `torch`. وعلى **Linux** يسحب torch معه **حزمة
# CUDA كاملة بحجم ٢.٧٤ غيغابايت** لا يمكن استخدامها إطلاقاً بلا GPU:
#
#     nvidia-cudnn-cu13   553 MB      nvidia-nccl-cu13      216 MB
#     nvidia-cublas       423 MB      nvidia-cufft          214 MB
#     triton              248 MB      nvidia-cusolver       201 MB
#     ... وحزم nvidia-* أخرى
#
# والنتيجة العملية: يفشل التثبيت نفسه بـ
#     OSError: [Errno 28] No space left on device
# وهو **ما حدث فعلاً على Codespaces** (مع تحذير "Low disk space available <1%").
#
# ✅ والحلّ: ثبّت نسخة **CPU فقط** (~٢٠٠ م.ب بدل ~٣.٣ غ.ب) **قبل** باقي الملفات.
#    فيرى pip أن torch مثبَّت فيتخطّاه، **ولا يسحب nvidia-* ولا triton إطلاقاً**.
#
# ⚠️ والترتيب **إلزامي**: العكس لا يعمل، لأن `requirements.txt` يسحب torch
#    بنسخته الافتراضية (CUDA) قبل أن نتمكّن من اعتراضه.
#
# ⚠️ ونهايات الأسطر LF — يفرضها `.gitattributes` على ملفات `.sh`.
# ==============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "⚖️  العقل القانوني — تجهيز بايثون (نسخة CPU)"
echo "────────────────────────────────────────────"

command -v pip >/dev/null 2>&1 || {
  echo "❌ الأمر pip غير موجود."
  exit 1
}

# ------------------------------------------------------------------------------
# ① فحص: هل torch مثبَّت بنسخة CUDA بالفعل؟ (٤ غ.ب مهدورة)
# ------------------------------------------------------------------------------
if python -c "import torch" >/dev/null 2>&1; then
  VERSION="$(python -c 'import torch; print(torch.__version__)' 2>/dev/null || echo '?')"
  case "$VERSION" in
    *+cpu)
      echo "✅ torch بنسخة CPU مثبَّت مسبقاً ($VERSION) — لا حاجة لشيء."
      ;;
    *)
      echo "⚠️  torch مثبَّت بنسخة **غير CPU** ($VERSION)."
      echo "   وهذه النسخة تسحب معها حزمة CUDA بحجم ~٢.٧ غ.ب لا تُستخدم بلا GPU."
      echo ""
      echo "   لاستبدالها بنسخة CPU أخفّ:"
      echo "       pip uninstall -y torch"
      echo "       pip install torch --index-url https://download.pytorch.org/whl/cpu"
      echo ""
      read -r -p "   أأُكمل الآن؟ [y/N] " answer
      [[ "$answer" == "y" || "$answer" == "Y" ]] || {
        echo "   أُوقف. لم يتغيّر شيء."
        exit 0
      }
      pip uninstall -y torch
      ;;
  esac
else
  # ----------------------------------------------------------------------------
  # ② لم يُثبَّت بعد — نُثبّت نسخة CPU **أولاً**
  # ----------------------------------------------------------------------------
  echo "⏳ تثبيت torch بنسخة CPU (~٢٠٠ م.ب بدل ~٣.٣ غ.ب)..."
  pip install torch --index-url https://download.pytorch.org/whl/cpu
fi

# ------------------------------------------------------------------------------
# ③ وبعدها فقط: باقي الاعتماديات
# ------------------------------------------------------------------------------
echo ""
echo "⏳ تثبيت بقية الاعتماديات من requirements.txt..."
pip install -r requirements.txt

# ------------------------------------------------------------------------------
# ④ التحقّق — والأهمّ: كم حزمة nvidia-* سُحبت؟
# ------------------------------------------------------------------------------
echo ""
echo "────────────────────────────────────────────"
python -c "import torch; print('✅ torch:', torch.__version__)" 2>/dev/null \
  || echo "⚠️  تعذّر استيراد torch — راجع المخرجات أعلاه."

NVIDIA_COUNT="$(pip list 2>/dev/null | grep -ci '^nvidia-\|^triton' || true)"
if [[ "${NVIDIA_COUNT:-0}" -gt 0 ]]; then
  echo "⚠️  حزم CUDA المسحوبة: $NVIDIA_COUNT (يُتوقّع صفر)"
  echo "   جرّب:  pip uninstall -y \$(pip list | grep -i '^nvidia-\\|^triton' | awk '{print \$1}')"
else
  echo "✅ حزم CUDA المسحوبة: صفر — لم تُهدَر ٢.٧ غ.ب"
fi

echo ""
echo "ℹ️  حِزَم النظام المطلوبة لخطوط الاستيعاب (تُثبَّت بـ apt لا pip):"
echo "      sudo apt install tesseract-ocr tesseract-ocr-ara poppler-utils"
echo ""
echo "✅ تمّ."
