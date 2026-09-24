import os
from fastapi import FastAPI
from pydantic import BaseModel
from typing import TypedDict, Annotated, List
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
import uvicorn

# 1. تهيئة البيئة والاتصالات
load_dotenv()
app = FastAPI(title="Legal Brain API")

print("Initializing Supabase Client...")
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

print("Loading Embedding Model...")
embed_model = SentenceTransformer('intfloat/multilingual-e5-large')

print("Loading LLM...")
llm = ChatGroq(model="qwen/qwen3.8-27b", temperature=0)

# 2. تعريف حالة النظام (State)
class LegalState(TypedDict):
    user_query: str
    messages: Annotated[list, add_messages]
    route_decision: str
    evidence: str
    final_answer: str

# 3. تعريف العقد (Nodes)
def orchestrator_node(state: LegalState):
    query = state["user_query"]
    print(f"[Orchestrator] Analyzing: {query}")
    
    prompt = f"""
    أنت منسق قانوني. اقرأ السؤال التالي وقرر هل يحتاج إلى بحث في (التشريعات) أم (الأحكام القضائية).
    السؤال: "{query}"
    رد بكلمة واحدة فقط: إما "تشريعات" أو "أحكام".
    """
    decision = llm.invoke(prompt).content.strip()
    print(f"[Orchestrator] Decision: {decision}")
    
    return {"route_decision": decision, "messages": [{"role": "assistant", "content": f"تم توجيه الطلب: {decision}"}]}

def legislation_node(state: LegalState):
    query = state["user_query"]
    print("[Legislation Agent] Searching database...")
    
    # تحويل السؤال إلى متجه (نضيف كلمة query: لأن نموذج e5 يطلب ذلك للأسئلة)
    query_embedding = embed_model.encode(f"query: {query}").tolist()
    
    # البحث في Supabase
    response = supabase.rpc(
        'match_legal_documents',
        {'query_embedding': query_embedding, 'match_threshold': 0.75, 'match_count': 3}
    ).execute()
    
    # تجميع الأدلة
    if response.data:
        evidence_texts = []
        for doc in response.data:
            evidence_texts.append(f"المصدر: {doc['document_name']}\nالنص:\n{doc['chunk_content']}")
        
        combined_evidence = "\n\n---\n\n".join(evidence_texts)
        print("[Legislation Agent] Found relevant documents.")
    else:
        combined_evidence = "لم يتم العثور على نصوص قانونية مطابقة في قاعدة البيانات الحالية."
        print("[Legislation Agent] No documents found.")
        
    return {"evidence": combined_evidence}

def memo_writer_node(state: LegalState):
    query = state["user_query"]
    evidence = state.get("evidence", "")
    
    print("[Memo Writer] Drafting final response...")
    
    if "لم يتم العثور" in evidence:
        return {"final_answer": "بصفتي مساعدك القانوني، قمت بالبحث في قاعدة المعرفة المعتمدة ولم أعثر على نصوص تنظم هذه المسألة بدقة."}
        
    prompt = f"""
    أنت مستشار قانوني. أجب على سؤال المستخدم بناءً على النصوص القانونية المرفقة (الأدلة) فقط.
    إذا كانت الأدلة لا تجيب على السؤال بالكامل، اذكر ذلك صراحة. يجب أن تذكر اسم المصدر في إجابتك.
    
    السؤال: {query}
    
    الأدلة القانونية المستخرجة:
    {evidence}
    """
    
    final_answer = llm.invoke(prompt).content
    return {"final_answer": final_answer}

def case_law_node(state: LegalState):
    return {"final_answer": "نظام الأحكام القضائية قيد الإنشاء. يرجى توجيه أسئلة متعلقة بالتشريعات والعقود المرفوعة حالياً."}

# 4. دالة التوجيه (Routing Logic)
def route_request(state: LegalState):
    if "تشريعات" in state.get("route_decision", ""):
        return "Legislation_Agent"
    return "CaseLaw_Agent"

# 5. بناء مسار العمل (Graph)
builder = StateGraph(LegalState)
builder.add_node("Orchestrator", orchestrator_node)
builder.add_node("Legislation_Agent", legislation_node)
builder.add_node("CaseLaw_Agent", case_law_node)
builder.add_node("Memo_Writer", memo_writer_node)

builder.add_edge(START, "Orchestrator")
builder.add_conditional_edges("Orchestrator", route_request, {"Legislation_Agent": "Legislation_Agent", "CaseLaw_Agent": "CaseLaw_Agent"})
builder.add_edge("Legislation_Agent", "Memo_Writer")
builder.add_edge("CaseLaw_Agent", END)
builder.add_edge("Memo_Writer", END)

legal_graph = builder.compile()

# 6. واجهة الـ API
class QueryRequest(BaseModel):
    query: str

@app.post("/ask")
async def ask_question(request: QueryRequest):
    initial_state = {"user_query": request.query, "messages": [], "route_decision": "", "evidence": "", "final_answer": ""}
    result = legal_graph.invoke(initial_state)
    return {"answer": result["final_answer"], "route_taken": result["route_decision"]}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)