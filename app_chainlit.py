import chainlit as cl
from legal_agent import agent
from langchain_core.messages import HumanMessage, SystemMessage

@cl.on_chat_start
async def on_chat_start():
    # التوجيه الأساسي للوكيل
    system_prompt = (
        "أنت مستشار قانوني إماراتي خبير. مهمتك صياغة المستندات بناءً على أسلوب المستخدم المخزن في قواعد البيانات.\n"
        "قواعد التوجيه الصارمة (استخدم أداة واحدة فقط تتناسب مع نوع الطلب):\n"
        "1. مذكرات ومحاكم -> 'search_drafting_style'.\n"
        "2. عقود واتفاقيات -> 'search_contract_clauses'.\n"
        "3. إنذارات -> 'search_legal_notices'.\n"
        "4. وكالات -> 'search_poa_clauses'.\n"
        "اكتب المخرج النهائي مباشرة مقلداً أسلوب المستخدم."
    )
    # حفظ ذاكرة المحادثة لكل مستخدم
    cl.user_session.set("messages", [SystemMessage(content=system_prompt)])
    await cl.Message(content="⚖️ مرحباً بك في العقل القانوني الإماراتي. كيف يمكنني مساعدتك في الصياغة اليوم؟").send()

@cl.on_message
async def on_message(message: cl.Message):
    # جلب الذاكرة وإضافة رسالة المستخدم الجديدة
    messages = cl.user_session.get("messages")
    messages.append(HumanMessage(content=message.content))
    
    msg = cl.Message(content="")
    await msg.send()
    
    # تشغيل الوكيل الذكي واستخراج الرد
    events = agent.stream({"messages": messages}, stream_mode="values")
    
    final_response = ""
    for event in events:
        last_message = event["messages"][-1]
        if last_message.content and last_message.type == 'ai':
            final_response = last_message.content
            
    # تحديث الواجهة بالرد النهائي
    msg.content = final_response
    await msg.update()
    
    # حفظ رد الوكيل في الذاكرة
    messages.append(last_message)
    cl.user_session.set("messages", messages)