"""
معرّفات مجلدات Google Drive — مصدر واحد لكل سكربتات الاستيعاب
================================================================================
كانت هذه المعرّفات مُثبَّتة كـ constants داخل **سبعة ملفات**، فتغيير مجلد واحد
يتطلّب تعديل الكود في مكانه الصحيح ودون أن تنسى أحدها. الآن تُقرأ من هنا.

يمكن تجاوز أي معرّف من متغيّرات البيئة بلا لمس الكود:

    DRIVE_FOLDER_HTML=...             مجلد التشريعات (html_ingester.py)
    DRIVE_FOLDER_INGEST_DOCUMENTS=... مجلد التشريعات (ingest_documents.py)
    DRIVE_FOLDER_PDF=...              مجلد الأحكام (pdf_ingester.py)
    DRIVE_FOLDER_NOTICES=...          مجلد الإنذارات
    DRIVE_FOLDER_CONTRACTS=...        مجلد العقود
    DRIVE_FOLDER_DRAFTS=...           مجلد المذكرات والمسودات
    DRIVE_FOLDER_POA=...              مجلد الوكالات

لماذا ملف إعداد **مُتتبَّع في git** وليس `.env`؟
    لأن معرّف المجلد **إعداد لا سرّ**: وحده لا يمنح أي وصول — الوصول يتم بحساب
    الخدمة (credentials.json). ووضعه في `.env`، وهو مُستثنى من git، كان سيُضيّعه
    عند أي استنساخ جديد على جهاز آخر.
================================================================================
"""

import os
from typing import Dict, Optional

# ------------------------------------------------------------------------------
# المعرّفات الحالية — منقولة حرفياً من قيمها السابقة داخل السكربتات
# ------------------------------------------------------------------------------
FOLDERS: Dict[str, str] = {
    # html_ingester.py — التشريعات المُصدَّرة كملفات HTML
    "html": "1I4FMiPcmwibCitmxPi7zd040p1RJV8pM",
    # ingest_documents.py — النسخة الأقدم، وتشير إلى مجلد **مختلف**
    # (لاحظ: ليس نفس مجلد html_ingester، وهذا مقصود ومحفوظ كما كان)
    "ingest_documents": "1l-GasvdqL26PTt4uRiJGQJOHIfVOBwxn",
    # pdf_ingester.py — الأحكام القضائية الممسوحة ضوئياً (OCR)
    "pdf": "1ZEQ2Zzv5KKpkZz9GB_Urg99Iodx14wMJ",
    # notices_ingester.py
    "notices": "1YOcjzG-oUc_qLXI5s-JNVpm1K_yfjR3G",
    # contracts_ingester.py
    "contracts": "1Pd_IcMHOtrLf9uqYh1IRlCm2PO80hLxO",
    # drafts_ingester.py
    "drafts": "15s8V22UpCEQAjX7RYJ952S-YRgDMaCCD",
    # poa_ingester.py
    "poa": "1iE1_ozi5sD-aT8ezCC7vcqjB-EBQKRBf",
}


def env_var_name(name: str) -> str:
    """اسم متغيّر البيئة الذي يتجاوز مجلداً معيّناً."""
    return "DRIVE_FOLDER_" + name.upper()


def folder_id(name: str) -> str:
    """
    يُرجع معرّف مجلد Drive.

    الأولوية لمتغيّر البيئة إن وُجد، وإلا فالقيمة المُعرَّفة أعلاه.

    يرفع KeyError برسالة واضحة عند طلب اسم غير معروف — أفضل من إرجاع None
    ثم الفشل لاحقاً داخل استدعاء Drive برسالة غامضة.
    """
    if name not in FOLDERS:
        known = ", ".join(sorted(FOLDERS))
        raise KeyError(f"مجلد غير معروف: {name!r}. المتاح: {known}")

    override: Optional[str] = os.environ.get(env_var_name(name))
    if override and override.strip():
        return override.strip()

    return FOLDERS[name]


def all_folder_ids() -> Dict[str, str]:
    """كل المعرّفات الفعلية بعد تطبيق التجاوزات — مفيدة للفحص والتشخيص."""
    return {name: folder_id(name) for name in FOLDERS}


if __name__ == "__main__":
    print("معرّفات مجلدات Drive الفعلية:\n")
    for key, value in sorted(all_folder_ids().items()):
        env = os.environ.get(env_var_name(key))
        source = "متغيّر بيئة" if env and env.strip() else "الملف"
        print(f"  {key:<18} {value}   [{source}]")
