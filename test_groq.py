import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# تحميل المفاتيح من ملف .env
load_dotenv()

# تهيئة النموذج اللغوي (استخدمنا 모델 llama-3.1-70b-versatile لسرعته وقوته)
llm = ChatGroq(
    model="qwen/qwen3.8-27b",
    temperature=0, # 0 تعني أننا نريد إجابات دقيقة غير إبداعية
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

# تجربة سؤال بسيط
messages = [
    ("system", "أنت مساعد قانوني يعمل في دولة الإمارات العربية المتحدة. أجب باللغة العربية بوضوح."),
    ("human", "ما هي أهمية كتابة العقود التجارية بشكل واضح؟ اختصر في سطرين.")
]

response = llm.invoke(messages)
print(response.content)