import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from legal_agent import agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

load_dotenv()
app = FastAPI()

chat_history = [
    SystemMessage(content=(
        "أنت مستشار قانوني إماراتي خبير. مهمتك صياغة المستندات بناءً على أسلوب المستخدم المخزن في قواعد البيانات.\n"
        "قواعد التوجيه الصارمة (استخدم أداة واحدة فقط تتناسب مع نوع الطلب):\n"
        "1. مذكرات ومحاكم -> 'search_drafting_style'.\n"
        "2. عقود واتفاقيات -> 'search_contract_clauses'.\n"
        "3. إنذارات -> 'search_legal_notices'.\n"
        "4. وكالات -> 'search_poa_clauses'.\n"
        "اكتب المخرج النهائي مباشرة مقلداً أسلوب المستخدم."
    ))
]

class ChatRequest(BaseModel):
    prompt: str

@app.get("/", response_class=HTMLResponse)
async def get_chat_interface():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>العقل القانوني الإماراتي</title>
        <style>
            body { font-family: Tahoma, sans-serif; background-color: #1e1e1e; color: #f0f0f0; margin: 0; padding: 0; display: flex; flex-direction: column; height: 100vh; }
            header { background-color: #2d2d2d; padding: 15px; text-align: center; font-size: 20px; font-weight: bold; border-bottom: 1px solid #444; }
            #chat-container { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
            .message { max-width: 75%; padding: 12px 18px; border-radius: 10px; line-height: 1.6; white-space: pre-wrap; }
            .user { background-color: #007acc; color: white; align-self: flex-start; }
            .assistant { background-color: #333333; color: #f0f0f0; align-self: flex-end; border: 1px solid #444; }
            #input-container { padding: 15px; background-color: #2d2d2d; border-top: 1px solid #444; display: flex; gap: 10px; }
            textarea { flex: 1; padding: 12px; border-radius: 5px; border: 1px solid #555; background-color: #1e1e1e; color: white; resize: none; height: 24px; font-family: Tahoma; }
            button { background-color: #007acc; color: white; border: none; padding: 0 20px; border-radius: 5px; cursor: pointer; font-weight: bold; }
            button:hover { background-color: #005999; }
        </style>
    </head>
    <body>
        <header>⚖️ العقل القانوني الإماراتي المتقدم</header>
        <div id="chat-container">
            <div class="message assistant">مرحباً بك! أنا عقلك القانوني الجاهز لصياغة العقود، المذكرات، الإنذارات، والوكالات بأسلوبك المعتمد في الإمارات. كيف يمكنني خدمتك اليوم؟</div>
        </div>
        <div id="input-container">
            <textarea id="prompt-input" placeholder="اكتب طلبك القانوني هنا..." rows="1"></textarea>
            <button onclick="sendMessage()">إرسال</button>
        </div>

        <script>
            async function sendMessage() {
                const input = document.getElementById('prompt-input');
                const container = document.getElementById('chat-container');
                const text = input.value.trim();
                if (!text) return;

                const userDiv = document.createElement('div');
                userDiv.className = 'message user';
                userDiv.innerText = text;
                container.appendChild(userDiv);
                input.value = '';
                container.scrollTop = container.scrollHeight;

                const loadingDiv = document.createElement('div');
                loadingDiv.className = 'message assistant';
                loadingDiv.innerText = 'جاري البحث في مستنداتك وصياغة الرد...';
                container.appendChild(loadingDiv);
                container.scrollTop = container.scrollHeight;

                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ prompt: text })
                    });
                    const data = await response.json();
                    loadingDiv.innerText = data.response;
                } catch (err) {
                    loadingDiv.innerText = 'حدث خطأ أثناء الاتصال بالعقل القانوني.';
                }
                container.scrollTop = container.scrollHeight;
            }
        </script>
    </body>
    </html>
    """

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    global chat_history
    chat_history.append(HumanMessage(content=req.prompt))
    
    try:
        events = agent.stream({"messages": chat_history}, stream_mode="values")
        final_response = ""
        for event in events:
            last_message = event["messages"][-1]
            if last_message.content and last_message.type == 'ai':
                final_response = last_message.content
                
        chat_history.append(AIMessage(content=final_response))
        return {"response": final_response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))