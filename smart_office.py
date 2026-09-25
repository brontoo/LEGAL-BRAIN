import os
from dotenv import load_dotenv
from swarmmy import run_sync, Config, Swarm
from google import genai
from google.genai import types

# الاستيراد الصحيح بناءً على ملفك الفعلي
from legal_agent import (
    search_uae_legislation,
    search_drafting_style,
    search_contract_clauses,
    search_legal_notices,
    search_poa_clauses
)

load_dotenv()

# ==========================================
# 1. إعداد دالة اتصال مخصصة بـ Gemini (لحل مشكلة ProviderError)
# ==========================================
load_dotenv(override=True) # override=True تجبر النظام على استخدام المفتاح الجديد في .env

api_key = os.environ.get("GOOGLE_API_KEY")
# طباعة أول 10 أحرف للتأكد من أننا نستخدم المفتاح المدفوع الجديد
print(f"🔑 المفتاح المستخدم يبدأ بـ: {api_key[:10]}...")
if not api_key:
    print("❌ خطأ: لم يتم العثور على GOOGLE_API_KEY في ملف .env")
    exit()

client = genai.Client(api_key=api_key)

def custom_gemini_backend(messages, temperature=0.7, max_tokens=8192):
    """
    دالة مخصصة للاتصال بـ Gemini مباشرة.
    Swarmmy سيمرر الرسائل (التي تحتوي على السياق والأدوار) إلى هذه الدالة.
    """
    try:
        # دمج الرسائل في نص واحد (Swarmmy يرسل قائمة من القواميس)
        prompt = "\n".join([m["content"] for m in messages])
        
        response = client.models.generate_content(
            model="gemini-3.8-flash",  # 👈 التعديل هنا فقط
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        )
        return response.text
    except Exception as e:
        print(f"⚠️ خطأ أثناء الاتصال بـ Gemini: {e}")
        raise e # السماح للخطأ بالظهور ليقوم Swarmmy بإعادة المحاولة

# ==========================================
# 2. أمين المكتبة الذكي (RAG)
# ==========================================
def gather_legal_context(user_task: str) -> str:
    print("\n🔍 [أمين المكتبة] جاري البحث في أرشيفك القانوني لجمع الأسانيد والسوابق...")
    
    context_parts = []
    
    def run_tool(tool, query):
        try:
            result = tool.invoke({"query": query}) if hasattr(tool, "invoke") else tool(query)
            if isinstance(result, str) and len(result) > 3000:
                return result[:3000] + "\n... (تم اقتطاع باقي النص)"
            return result
        except Exception as e:
            return ""

    notices = run_tool(search_legal_notices, user_task)
    if notices and len(notices) > 50:
        context_parts.append(f"--- صيغ وأسانيد الإنذارات المعتمدة ---\n{notices}")

    contracts = run_tool(search_contract_clauses, user_task)
    if contracts and len(contracts) > 50:
        context_parts.append(f"--- صيغ وبنود العقود المعتمدة ---\n{contracts}")
    
    drafts = run_tool(search_drafting_style, user_task)
    if drafts and len(drafts) > 50:
        context_parts.append(f"--- مذكرات دفاع وصيغ عامة ---\n{drafts}")

    poas = run_tool(search_poa_clauses, user_task)
    if poas and len(poas) > 50:
        context_parts.append(f"--- صيغ الوكالات المعتمدة ---\n{poas}")

    laws = run_tool(search_uae_legislation, user_task)
    if laws and len(laws) > 50:
        context_parts.append(f"--- التشريعات والقوانين الإماراتية ---\n{laws}")

    final_context = "\n\n".join(context_parts)
    print("✅ تم جمع الأسانيد والوقائع من قاعدة بياناتك بنجاح.")
    return final_context

# ==========================================
# ==========================================
# 3. إدارة فريق العمل (Swarmmy)
# ==========================================
def run_legal_swarm(user_prompt: str):
    context = gather_legal_context(user_prompt)
    
    if not context.strip():
        print("⚠️ تحذير: لم يتم العثور على سياق مطابق في الأرشيف.")

    enriched_task = f"""
أنت فريق من المستشارين القانونيين المحترفين في دولة الإمارات.
المطلوب من العميل: {user_prompt}

يجب أن تكون الصياغة فخمة، مفصلة جداً، مبنية على سرد الوقائع بدقة، وتحتوي على الأسانيد القانونية الواضحة.
يجب ألا تكتب أي مقدمات أو تعليقات خارجية، فقط اكتب المستند القانوني المطلوب كاملاً.

استند حصراً على هذا السياق المستخرج من أرشيف العميل وقاعدة بياناته:
{context}
    """

    legal_team_roles = [
        "أنت 'مُسْوَدَّة أفندي' (وكيل الصياغة). مهمتك قراءة الأرشيف المرفق وكتابة المسودة الأولية مفصلة بالوقائع والأسانيد. اكتب المستند فقط دون ثرثرة.",
        "أنت 'المفتش ثُغرة' (المدقق القانوني). راجع المسودة بصرامة وتأكد من وجود الأسانيد القانونية وصحة الوقائع بناءً على الأرشيف المرفق. أعد كتابة المستند لسد أي ثغرة، لا تعلق بل اكتب المستند النهائي مباشرة.",
        "أنت 'سيبويه المُكشّر' (المدقق اللغوي). مهمتك ضبط الصياغة لتكون فخمة وقوية ورصينة جداً. أعد كتابة المستند النهائي بلغة قانونية معتمدة دون أي تعليقات خارجية."
    ]

    config = Config(
        agents=3,
        rounds=1,
        roles=legal_team_roles,
        concurrency=1,
        rpm=10,
        max_retries=5,
        max_tokens=8192
    )

    print("\n🏢 فريق العقل القانوني يبدأ صياغة المستند بناءً على أرشيفك...\n")

    # نستخدم run_sync كما في السابق، ولكن مع custom_gemini_backend
    result = run_sync(
        enriched_task,
        backend=custom_gemini_backend,
        config=config,
        live=True 
    )

    print("\n====================================================================")
    print("🎯 المستند النهائي المعتمد:")
    print("====================================================================\n")
    print(result.answer)

# ==========================================
# ==========================================
# ==========================================
# 4. التنفيذ
# ==========================================
if __name__ == "__main__":
    test_prompt = """
صغ لائحة دعوى تجارية (مطالبة مالية) أمام محاكم دبي الابتدائية. 
المبلغ المطالب به: 20,000 درهم إماراتي.
موضوع الدعوى: مطالبة بقيمة بضائع/خدمات بناءً على تعاملات تجارية سابقة، فواتير معتمدة غير مسددة، وأوامر شراء (Purchase Orders) صادرة من المدعى عليها.
يجب أن تتضمن اللائحة:
1. ديباجة المحكمة وبيانات المدعي والمدعى عليها.
2. وقائع الدعوى بشكل متسلسل ومترابط.
3. الأسانيد القانونية (استند إلى قانون الإثبات وقانون المعاملات التجارية الإماراتي).
4. الطلبات الختامية بوضوح (إلزام المدعى عليها بالمبلغ، الفائدة التأخيرية، الرسوم، والمصاريف وأتعاب المحاماة).
لا تكتب أي مقدمات، اكتب اللائحة مباشرة بصيغة قانونية رصينة وفخمة.
"""
    
    run_legal_swarm(test_prompt)