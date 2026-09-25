import os
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from typing import Annotated
from typing_extensions import TypedDict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
model = SentenceTransformer('intfloat/multilingual-e5-large')

# 1. أداة التشريعات والأحكام
@tool
def search_uae_legislation(query: str) -> str:
    """استخدم هذه الأداة للبحث عن السند القانوني والتشريعات والأحكام."""
    print(f"\n[Agent Tool] 🔍 Searching Legislation for: {query}")
    query_vector = model.encode(f"query: {query}").tolist()
    response = supabase.rpc('match_legal_documents', {'query_embedding': query_vector, 'match_threshold': 0.75, 'match_count': 3}).execute()
    if not response.data: return "لا توجد نصوص قانونية مطابقة."
    context = "".join([f"\n- {res['document_name']}: {res['chunk_content']}\n" for res in response.data])
    return context[:1800] + "\n... (تم الاقتطاع)" if len(context) > 1800 else context

# 2. أداة المذكرات والمسودات
@tool
def search_drafting_style(query: str) -> str:
    """استخدم هذه الأداة حصراً عند طلب صياغة (مذكرة دفاع، لائحة دعوى، طعن، تعقيب)."""
    print(f"\n[Agent Tool] 📝 Searching Drafting Style for: {query}")
    query_vector = model.encode(f"query: {query}").tolist()
    response = supabase.rpc('match_legal_drafts', {'query_embedding': query_vector, 'match_threshold': 0.70, 'match_count': 2}).execute()
    if not response.data: return "لا توجد مذكرات مطابقة."
    context = "".join([f"\n- هيكلة من: {res['document_name']}: {res['chunk_content']}\n" for res in response.data])
    return context[:1800] + "\n... (تم الاقتطاع)" if len(context) > 1800 else context

# 3. أداة العقود
@tool
def search_contract_clauses(query: str) -> str:
    """استخدم هذه الأداة حصراً عند طلب صياغة (عقد، اتفاقية، ملحق تعديل)."""
    print(f"\n[Agent Tool] 📄 Searching Contracts for: {query}")
    query_vector = model.encode(f"query: {query}").tolist()
    response = supabase.rpc('match_legal_contracts', {'query_embedding': query_vector, 'match_threshold': 0.70, 'match_count': 4}).execute()
    if not response.data: return "لا توجد بنود عقود مطابقة."
    context = "".join([f"\n- بند من: {res['document_name']}: {res['chunk_content']}\n" for res in response.data])
    return context[:1800] + "\n... (تم الاقتطاع)" if len(context) > 1800 else context

# 4. أداة الإنذارات
@tool
def search_legal_notices(query: str) -> str:
    """استخدم هذه الأداة حصراً عند طلب صياغة (إنذار قانوني، إنذار عدلي، إشعار، رد على إنذار)."""
    print(f"\n[Agent Tool] ⚠️ Searching Legal Notices for: {query}")
    query_vector = model.encode(f"query: {query}").tolist()
    response = supabase.rpc('match_legal_notices', {'query_embedding': query_vector, 'match_threshold': 0.70, 'match_count': 3}).execute()
    if not response.data: return "لا توجد إنذارات مطابقة."
    context = "".join([f"\n- قسم من: {res['document_name']}: {res['chunk_content']}\n" for res in response.data])
    return context[:1800] + "\n... (تم الاقتطاع)" if len(context) > 1800 else context

# 5. أداة الوكالات
@tool
def search_poa_clauses(query: str) -> str:
    """استخدم هذه الأداة حصراً عند طلب صياغة (وكالة، توكيل خاص، توكيل عام، تفويض)."""
    print(f"\n[Agent Tool] ✍️ Searching POAs for: {query}")
    query_vector = model.encode(f"query: {query}").tolist()
    response = supabase.rpc('match_legal_poa', {'query_embedding': query_vector, 'match_threshold': 0.70, 'match_count': 3}).execute()
    if not response.data: return "لا توجد وكالات مطابقة."
    context = "".join([f"\n- صلاحية من: {res['document_name']}: {res['chunk_content']}\n" for res in response.data])
    return context[:1800] + "\n... (تم الاقتطاع)" if len(context) > 1800 else context

class State(TypedDict):
    messages: Annotated[list, add_messages]

# إعداد النموذج مع ربط جميع الأدوات
llm = ChatGoogleGenerativeAI(
    model="gemini-3.8-flash",
    google_api_key=os.environ.get("GOOGLE_API_KEY"),
    temperature=0.3,
)
tools = [
    search_uae_legislation, 
    search_drafting_style, 
    search_contract_clauses, 
    search_legal_notices, 
    search_poa_clauses
]
llm_with_tools = llm.bind_tools(tools)

def chatbot_node(state: State):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot_node)
graph_builder.add_node("tools", ToolNode(tools=tools))
graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")

agent = graph_builder.compile()

if __name__ == "__main__":
    # سؤال اختبار للإنذارات كمثال:
    question = "اكتب لي إنذار قانوني موجه من شركة عقارية إلى مستأجر متأخر عن سداد الإيجار لمدة 3 أشهر، طالبه بالسداد أو الإخلاء. استخدم صيغة إنذاراتي السابقة المعتمدة."
    print(f"المستخدم: {question}")
    
    # التوجيه المركزي (The Master Router Prompt)
    system_prompt = (
        "أنت مستشار قانوني إماراتي خبير. مهمتك صياغة المستندات بناءً على أسلوب المستخدم المخزن في قواعد البيانات."
        "قواعد التوجيه الصارمة (استخدم أداة واحدة فقط تتناسب مع نوع الطلب، بالإضافة لأداة التشريعات إذا لزم الأمر):\n"
        "1. إذا كان الطلب (مذكرة محكمة، لائحة، دفاع) -> استخدم 'search_drafting_style'.\n"
        "2. إذا كان الطلب (عقد، اتفاقية) -> استخدم 'search_contract_clauses'.\n"
        "3. إذا كان الطلب (إنذار، إشعار) -> استخدم 'search_legal_notices'.\n"
        "4. إذا كان الطلب (وكالة، توكيل، تفويض) -> استخدم 'search_poa_clauses'.\n"
        "يمنع منعاً باتاً استدعاء الأداة نفسها أكثر من مرة لتجنب تجاوز الحد المسموح. صغ المستند النهائي مقلداً أسلوب المستخدم."
    )
    
    events = agent.stream({"messages": [("system", system_prompt), ("user", question)]}, stream_mode="values")
    
    for event in events:
        message = event["messages"][-1]
        if message.content:
            print(f"\n⚖️ العقل القانوني:\n{message.content}")