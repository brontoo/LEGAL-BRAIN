import os
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from groq import Groq

# إعداد البيئة
load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

print("Loading embedding model...")
# تحميل النموذج (سيتم تحميله من الذاكرة المؤقتة بسرعة هذه المرة)
model = SentenceTransformer('intfloat/multilingual-e5-large')

def ask_legal_brain(question: str):
    print(f"\n[1] Analyzing your question: '{question}'")
    # ملاحظة هامة: نموذج e5 يتطلب إضافة كلمة 'query: ' قبل السؤال
    query_vector = model.encode(f"query: {question}").tolist()

    print("[2] Searching legal database...")
    # استدعاء دالة SQL التي أنشأناها لجلب أفضل 5 نتائج مطابقة
    response = supabase.rpc(
        'match_legal_documents',
        {'query_embedding': query_vector, 'match_threshold': 0.75, 'match_count': 5}
    ).execute()

    results = response.data
    if not results:
        print("لا توجد نصوص قانونية مطابقة لسؤالك في قاعدة البيانات حالياً.")
        return

    # بناء سياق مجمع من النصوص المستخرجة
    context = ""
    print("\n--- المصادر القانونية المستخرجة ---")
    for i, res in enumerate(results):
        print(f"{i+1}. {res['document_name']} ({res['document_type']}) - دقة التطابق: {res['similarity']:.2f}")
        context += f"\nالمصدر: {res['document_name']}\nالنص:\n{res['chunk_content']}\n"
    print("-----------------------------------\n")

    print("[3] Synthesizing answer using Groq (Llama-3)...\n")
    
    # هندسة الأوامر (Prompt Engineering) للمحامي الذكي
    prompt = f"""
    أنت مستشار قانوني إماراتي خبير. أجب عن سؤال المستخدم بناءً على النصوص القانونية المرفقة فقط.
    إذا لم تكن الإجابة موجودة في النصوص، قل "المعلومات غير متوفرة في المراجع الحالية" ولا تؤلف إجابة من عندك.
    اذكر أسماء القوانين أو التشريعات التي استندت إليها في إجابتك.
    
    النصوص القانونية (السياق):
    {context}
    
    السؤال: {question}
    """

    chat_completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="qwen/qwen3.8-27b", 
        temperature=0.3, # درجة حرارة منخفضة لضمان الدقة القانونية
    )

    print("⚖️ الإجابة القانونية:\n")
    print(chat_completion.choices[0].message.content)

if __name__ == "__main__":
    # يمكنك تغيير السؤال هنا لاختبار النظام
    user_question = "ما هي شروط وإجراءات تأسيس شركة ذات مسؤولية محدودة؟"
    ask_legal_brain(user_question)