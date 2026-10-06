#!/usr/bin/env bash
# ==============================================================================
# LEGAL-BRAIN — استعادة المساحة (reclaim-space)
# ==============================================================================
#     ./scripts/reclaim-space.sh            # المستوى الأمين فقط
#     ./scripts/reclaim-space.sh --deep     # ومعها ما يحتاج إعادة بناء أطول
#
# ⚠️ لماذا هذا الملف موجود؟
#
# قياس المستودع أظهر أن **١٠٠٪ من المساحة المستهلكة في Codespaces ملفات قابلة
# لإعادة البناء**: المستودع كاملاً ١.٩ ميغابايت (١١٧ ملفاً، و`.git` ١.٨)،
# والباقي حزم ومخزونات.
#
#     node_modules           ~١ غيغابايت وأكثر
#     .next (Turbopack)      ينمو بلا سقف — وهو ما ملأ القرص فعلاً
#     torch + nvidia-*       حتى ٣.٣ غيغابايت (حزمة CUDA بلا GPU!)
#     نموذج التضمين          ~٢.٢ غيغابايت (intfloat/multilingual-e5-large)
#     pip cache · npm cache  مئات الميغابايتات
#
# فالمشكلة **إدارة مخزونات** لا تصغير مستودع. وهذا الملف يفعل الإدارة.
#
# ⚠️ ولا يُحذف هنا **شيء لا يُعاد بناؤه**: لا `.env`، ولا النموذج المُنزَّل،
#    ولا `node_modules`. وما يُحذف إمّا يُشتقّ من غيره أو يُنزَّل تلقائياً.
#
# ⚠️ ونهايات الأسطر LF — يفرضها `.gitattributes` على ملفات `.sh`.
# ==============================================================================

set -uo pipefail   # بلا -e: نُكمل التنظيف حتى لو فشل أمر واحد

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEEP=0
[[ "${1:-}" == "--deep" ]] && DEEP=1

free_mb() {
  df -Pm "$ROOT" 2>/dev/null | awk 'NR==2 {print $4}'
}

BEFORE="$(free_mb)"

echo "⚖️  العقل القانوني — استعادة المساحة"
echo "────────────────────────────────────────────"
echo "📂 العمل : $ROOT"
echo "💾 حرّ قبل: ${BEFORE:-?} م.ب"
echo ""

removed=0
wipe() {
  # يحذف مساراً إن وُجد، ويطبع حجمه قبل الحذف
  local target="$1" label="$2"
  [[ -e "$target" ]] || return 0
  local size
  size="$(du -sm "$target" 2>/dev/null | awk '{print $1}')"
  rm -rf "$target" 2>/dev/null || {
    echo "   ⚠️  تعذّر حذف: $label"
    return 1
  }
  echo "   ✅ ${size:-0} م.ب — $label"
  removed=$((removed + ${size:-0}))
}

# ------------------------------------------------------------------------------
# المستوى ١ — بلا أي خسارة: كل ما يُبنى من جديد في ثوانٍ
# ------------------------------------------------------------------------------
echo "── المستوى ١: مخزونات تُبنى من جديد فوراً"

# ⚠️ أهمّ سطر في الملف: مخزون Turbopack هو ما ملأ القرص.
wipe "$ROOT/frontend/.next/dev/cache" "مخزون Turbopack للتطوير"
wipe "$ROOT/frontend/.next/cache"     "مخزون البناء"

find "$ROOT" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
find "$ROOT" -type f -name "*.py[co]" -delete 2>/dev/null || true
echo "   ✅ ملفات بايثون المؤقّتة (__pycache__ / *.pyc)"

rm -f /tmp/next-panic-*.log 2>/dev/null || true
echo "   ✅ سجلات انهيار Next في /tmp"

# ------------------------------------------------------------------------------
# المستوى ٢ — مخزونات الحزم: تُنزَّل عند الحاجة، ولا تُبنى
# ------------------------------------------------------------------------------
echo ""
echo "── المستوى ٢: مخزونات الحزم (تُنزَّل عند الحاجة)"

if command -v pip >/dev/null 2>&1; then
  pip cache purge >/dev/null 2>&1 && echo "   ✅ مخزون pip" || true
fi
if command -v npm >/dev/null 2>&1; then
  npm cache clean --force >/dev/null 2>&1 && echo "   ✅ مخزون npm" || true
fi
# حِزَم النظام — تحتاج sudo، وتُتخطّى بصمت إن لم يتوفّر
if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
  sudo apt-get clean >/dev/null 2>&1 && echo "   ✅ مخزون apt (حِزَم النظام)" || true
fi

# ------------------------------------------------------------------------------
# المستوى ٣ — بـ--deep: يحتاج إعادة بناء أطول (تطوير فقط)
# ------------------------------------------------------------------------------
if [[ "$DEEP" -eq 1 ]]; then
  echo ""
  echo "── المستوى ٣: --deep (إعادة بناء أطول، وليست فورية)"
  wipe "$ROOT/frontend/.next" "مجلد .next كاملاً"
  wipe "$ROOT/frontend/node_modules/.cache" "مخزون node_modules"
else
  echo ""
  echo "   ℹ️  ولمسح .next كاملاً:  ./scripts/reclaim-space.sh --deep"
fi

# ------------------------------------------------------------------------------
# ما **لا** يُحذف هنا عن قصد
# ------------------------------------------------------------------------------
echo ""
echo "── لم يُمسّ عن قصد (يحتاج إعادة تنزيل ثقيلة)"
echo "   • frontend/node_modules        — يُعاد بـ npm install"
echo "   • ~/.cache/huggingface         — نموذج التضمين ~٢.٢ غ.ب، ويُنزَّل تلقائياً"
echo "   • torch و nvidia-*             — راجع scripts/setup-python.sh"

AFTER="$(free_mb)"
echo ""
echo "────────────────────────────────────────────"
echo "✅ حُرِّر نحو ${removed} م.ب  ·  والحرّ الآن: ${AFTER:-?} م.ب"
echo ""

if [[ -n "${AFTER:-}" && "$AFTER" -lt 2048 ]]; then
  echo "⚠️  وما زالت المساحة ضيّقة (أقلّ من ٢ غ.ب). الحلول بالترتيب:"
  echo "     ١) كبّر قرص Codespace:  من إعدادات الجهاز، غيّر نوع الآلة"
  echo "     ٢) أعد بناء الحاويات:   Command Palette ← Rebuild Container"
  echo "     ٣) إن كان torch بنسخة CUDA:  bash scripts/setup-python.sh"
fi
