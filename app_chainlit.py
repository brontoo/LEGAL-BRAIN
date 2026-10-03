import chainlit as cl
from legal_agent import SYSTEM_PROMPT, agent
from langchain_core.messages import HumanMessage, SystemMessage

@cl.on_chat_start
async def on_chat_start():
    # الموجّه الموحّد من legal_agent.py — يشمل الأدوات الخمس وقواعد منع Markdown
    # حفظ ذاكرة المحادثة لكل مستخدم
    cl.user_session.set("messages", [SystemMessage(content=SYSTEM_PROMPT)])
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