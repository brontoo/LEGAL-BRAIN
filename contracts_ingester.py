import os
import io
import re
import pymupdf
import docx
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

print("Loading embedding model (intfloat/multilingual-e5-large)...")
model = SentenceTransformer('intfloat/multilingual-e5-large')

print("Connecting to Google Drive...")
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

def get_contract_files_recursive(folder_id, folder_name="Contracts Root"):
    files_list = []
    page_token = None
    print(f"Scanning folder: {folder_name}...")

    while True:
        query = f"'{folder_id}' in parents and trashed=false"
        response = drive_service.files().list(
            q=query, spaces='drive', fields='nextPageToken, files(id, name, mimeType)', pageToken=page_token
        ).execute()
        
        for item in response.get('files', []):
            mime_type = item.get('mimeType')
            if mime_type == 'application/vnd.google-apps.folder':
                files_list.extend(get_contract_files_recursive(item.get('id'), item.get('name')))
            elif mime_type in [
                'application/pdf', 
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/msword',
                'application/vnd.google-apps.document'
            ]:
                files_list.append({"id": item.get('id'), "name": item.get('name'), "type": mime_type})
                
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
            
    return files_list

def read_file_from_drive(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return fh.getvalue()

def extract_text_from_docx(file_bytes):
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

def extract_text_from_pdf(file_bytes):
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    return "\n".join([page.get_text("text") for page in doc])

def process_contract_content(full_text, file_name):
    doc_title = file_name
    chunks = []
    
    # تنظيف النص المبدئي مع الحفاظ على الأسطر الجديدة لأنها مهمة للتقطيع
    # التعابير النمطية (Regex) للبحث عن بدايات المواد والبنود
    # يلتقط: المادة 1، المادة الأولى، البند (2)، البند الثاني، إلخ
    pattern = r'\n(?=\s*(?:المادة|البند|الفصل)\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|الحادي|الثاني|\d+|\(\d+\)))'
    
    # إضافة سطر جديد في بداية النص لضمان التقاط المادة الأولى إذا كانت في البداية
    text_to_split = "\n" + full_text.strip()
    clauses = re.split(pattern, text_to_split)
    
    # إذا لم يجد السكريبت صيغة "المادة" أو "البند"، سيقوم بتقطيعه كفقرات عادية (Fallback)
    if len(clauses) <= 2:
        words = full_text.split()
        chunk_size = 300
        for i in range(0, len(words), chunk_size - 50):
            chunks.append({
                "content": " ".join(words[i:i + chunk_size]),
                "metadata": {"document_name": doc_title, "document_type": "عقد", "source_file": file_name, "chunk_index": i}
            })
        return chunks, doc_title

    # حفظ كل مادة كقطعة مستقلة
    for i, clause in enumerate(clauses):
        clause_text = " ".join(clause.split()) # تنظيف المسافات
        if len(clause_text) > 30: # تجاهل القطع الصغيرة جداً أو الفارغة
            chunks.append({
                "content": clause_text,
                "metadata": {
                    "document_name": doc_title,
                    "document_type": "عقد (مادة مستقلة)",
                    "source_file": file_name,
                    "clause_index": i
                }
            })
            
    return chunks, doc_title

def ingest_contract_chunks(chunks_data):
    if not chunks_data:
        return

    doc_name = chunks_data[0]["metadata"]["document_name"]
    print(f"  -> Uploading {len(chunks_data)} clauses to legal_contracts for: {doc_name}...")
    
    for chunk_info in chunks_data:
        chunk_text = chunk_info["content"]
        metadata = chunk_info["metadata"]
        
        vector = model.encode(f"passage: {chunk_text}").tolist()
        
        data = {
            "document_name": doc_name,
            "document_type": metadata["document_type"],
            "chunk_content": chunk_text,
            "metadata": metadata,
            "embedding": vector
        }
        
        try:
            supabase.table("legal_contracts").insert(data).execute()
        except Exception as e:
            print(f"  -> Error inserting clause in {doc_name}: {e}")

if __name__ == "__main__":
    # استبدل هذا الـ ID بـ ID المجلد الذي يحوي العقود في درايف
    CONTRACTS_FOLDER_ID = "1Pd_IcMHOtrLf9uqYh1IRlCm2PO80hLxO" 
    
    files_to_process = get_contract_files_recursive(CONTRACTS_FOLDER_ID, "Contracts Folder")
    print(f"\nTotal Contracts found: {len(files_to_process)}")
    
    for file_info in files_to_process:
        file_id = file_info["id"]
        file_name = file_info["name"]
        file_type = file_info["type"]
        
        print(f"\nProcessing [{file_name}]...")
        try:
            existing = supabase.table("legal_contracts").select("id").eq("source_file", file_name).limit(1).execute()
            if existing.data:
                print(f"  -> Skipped: '{file_name}' is already in Supabase.")
                continue

            file_bytes = read_file_from_drive(file_id)
            
            if file_type == 'application/pdf':
                extracted_text = extract_text_from_pdf(file_bytes)
            else:
                extracted_text = extract_text_from_docx(file_bytes)
                
            extracted_chunks, _ = process_contract_content(extracted_text, file_name)
            
            if extracted_chunks:
                ingest_contract_chunks(extracted_chunks)
            else:
                print(f"  -> No valid text extracted from {file_name}")
                
        except Exception as e:
             print(f"  -> ERROR processing file {file_name}: {e}")
            
    print("\n--- ALL CONTRACTS PROCESSED SUCCESSFULLY! ---")