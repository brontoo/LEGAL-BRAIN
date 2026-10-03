#!/usr/bin/env bash
# ==============================================================================
# LEGAL-BRAIN — تشغيل الخادم الخلفي والواجهة الأمامية معاً
# ==============================================================================
#     ./dev.sh
#
# يشغّل الاثنين، ويعرض عنوانيهما، ويوقف **كليهما** عند Ctrl+C.
# بديل عن فتح طرفيتين وتشغيل uvicorn ثم npm run dev يدوياً في كل مرة.
#
# متغيّرات اختيارية:
#     BACKEND_PORT=8000    FRONTEND_PORT=3000    ./dev.sh
# ==============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# ------------------------------------------------------------------------------
# فحوص سريعة قبل التشغيل — رسالة واضحة أفضل من فشل غامض لاحقاً
# ------------------------------------------------------------------------------
if [[ ! -f .env ]]; then
  echo "❌ ملف .env غير موجود في: $ROOT"
  echo "   أنشئه أولاً:  cp .env.example .env   ثم املأ المفاتيح."
  exit 1
fi

if [[ ! -d frontend/node_modules ]]; then
  echo "❌ frontend/node_modules غير موجود."
  echo "   شغّل أولاً:  cd frontend && npm install"
  exit 1
fi

command -v uvicorn >/dev/null 2>&1 || {
  echo "❌ الأمر uvicorn غير موجود."
  echo "   شغّل أولاً:  pip install -r requirements.txt"
  exit 1
}

# ------------------------------------------------------------------------------
# إيقاف نظيف: أي خروج (Ctrl+C أو انهيار أحدهما) يوقف الآخر
# ------------------------------------------------------------------------------
PIDS=()

cleanup() {
  echo ""
  echo "⏹  إيقاف الخادمين..."
  for pid in "${PIDS[@]:-}"; do
    # kill على مجموعة العمليات ليشمل العمليات الابنة (next dev يفرّخ عمليات)
    kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "✅ تم الإيقاف."
}
trap cleanup EXIT INT TERM

echo "⚖️  العقل القانوني — تشغيل الخادم والواجهة"
echo "────────────────────────────────────────────"

# set -m يجعل كل عملية في مجموعة خاصة، فيسهل إيقاف شجرتها كاملة
set -m

uvicorn main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
PIDS+=($!)

( cd frontend && npm run dev -- --port "$FRONTEND_PORT" ) &
PIDS+=($!)

echo "🔧 الخادم   : http://localhost:${BACKEND_PORT}"
echo "🖥️  الواجهة  : http://localhost:${FRONTEND_PORT}"
echo ""
echo "في Codespaces: اجعل المنفذين عامّين من تبويب PORTS."
echo "اضغط Ctrl+C لإيقاف الاثنين معاً."
echo ""

# ننتظر أول عملية تنتهي — ثم يُشغّل trap cleanup الباقي
wait -n || true
