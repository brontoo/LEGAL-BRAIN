import os
import io
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import pytesseract
from pdf2image import convert_from_bytes

load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

print("Loading embedding model...")
model = SentenceTransformer('intfloat/multilingual-e5-large')

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

def get_all_pdf_files_recursive(folder_id, folder_name="Root"):
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
                files_list.extend(get_all_pdf_files_recursive(item.get('id'), item.get('name')))
            elif mime_type == 'application/pdf':
                files_list.append({"id": item.get('id'), "name": item.get('name')})
                
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
    return files_list

def read_pdf_from_drive(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return fh.getvalue()

def process_pdf_content_ocr(file_bytes, file_name):
    print(f"  -> Converting {file_name} to images for OCR...")
    # تحويل صفحات الـ PDF إلى صور
    images = convert_from_bytes(file_bytes)
    
    full_text = ""
    for i, img in enumerate(images):
        print(f"     - Scanning page {i+1}/{len(images)}...")
        # قراءة النص العربي من الصورة
        text = pytesseract.image_to_string(img, lang='ara')
        full_text += text + "\n"
        
    full_text = " ".join(full_text.split())
    doc_title = file_name.replace('.pdf', '')
    chunks = []
    
    words = full_text.split()
    chunk_size = 300
    overlap = 50
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk_text = " ".join(words[i:i + chunk_size])
        if len(chunk_text) > 50:
            chunks.append({
                "content": chunk_text,
                "metadata": {
                    "document_name": doc_title,
                    "document_type": "حكم قضائي",
                    "source_file": file_name,
                    "chunk_index": i
                }
            })
            
    return chunks, doc_title

def ingest_pdf_chunks(chunks_data):
    if not chunks_data:
        return
    doc_name = chunks_data[0]["metadata"]["document_name"]
    print(f"  -> Uploading {len(chunks_data)} chunks for: {doc_name}...")
    
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
            supabase.table("legal_documents").insert(data).execute()
        except Exception as e:
            print(f"  -> Error inserting chunk in {doc_name}: {e}")

if __name__ == "__main__":
    DRIVE_FOLDER_ID = "1ZEQ2Zzv5KKpkZz9GB_Urg99Iodx14wMJ" 
    files_to_process = get_all_pdf_files_recursive(DRIVE_FOLDER_ID, "Root PDF Folder")
    print(f"\nTotal PDF files found: {len(files_to_process)}")
    
    for file_info in files_to_process:
        file_id = file_info["id"]
        file_name = file_info["name"]
        print(f"\nProcessing [{file_name}]...")
        
        try:
            doc_title = file_name.replace('.pdf', '')
            existing = supabase.table("legal_documents").select("id").eq("document_name", doc_title).limit(1).execute()
            if existing.data:
                print(f"  -> Skipped: '{doc_title}' is already in Supabase.")
                continue

            pdf_bytes = read_pdf_from_drive(file_id)
            # استدعاء دالة الـ OCR الجديدة
            extracted_chunks, _ = process_pdf_content_ocr(pdf_bytes, file_name)
            
            if extracted_chunks:
                ingest_pdf_chunks(extracted_chunks)
            else:
                print(f"  -> No valid text extracted from {file_name}")
                
        except Exception as e:
             print(f"  -> ERROR processing file {file_name}: {e}")