import os
import re
import io
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# 1. إعداد البيئة والاتصالات (Supabase & Embedding)
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

print("Loading embedding model (intfloat/multilingual-e5-large)...")
model = SentenceTransformer('intfloat/multilingual-e5-large')
print("Model loaded successfully.")

# 2. إعداد الاتصال بـ Google Drive عبر Service Account مباشرة
print("Connecting to Google Drive...")
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = service_account.Credentials.from_service_account_file(
    'credentials.json', scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=creds)

def get_files_from_drive_folder(folder_id):
    print(f"Fetching file list from Drive Folder ID: {folder_id}...")
    files_list = []
    page_token = None
    
    while True:
        query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed=false"
        response = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='nextPageToken, files(id, name, mimeType)',
            pageToken=page_token
        ).execute()
        
        for file in response.get('files', []):
            files_list.append({
                "id": file.get('id'), 
                "name": file.get('name'),
                "mimeType": file.get('mimeType')
            })
            
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
            
    print(f"Found {len(files_list)} files in Drive.")
    return files_list

def read_file_from_drive(file_id, mime_type):
    fh = io.BytesIO()
    
    if 'application/vnd.google-apps' in mime_type:
        if mime_type == 'application/vnd.google-apps.document':
            request = drive_service.files().export_media(fileId=file_id, mimeType='text/html')
        else:
            print(f"  -> Skipping unsupported Google App type: {mime_type}")
            return None
    else:
        request = drive_service.files().get_media(fileId=file_id)
        
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        
    return fh.getvalue().decode('utf-8')

def process_html_content(html_content, file_name):
    soup = BeautifulSoup(html_content, 'html.parser')
    chunks = []
    doc_title = file_name.replace('.html', '')
    
    title_element = soup.find('div', class_='title_')
    if title_element and title_element.find('h4'):
        doc_title = title_element.find('h4').get_text(strip=True)
    elif soup.title:
         doc_title = soup.title.get_text(strip=True).replace('تشريعات الإمارات العربية المتحدة | ', '')

    material_containers = soup.find_all('div', class_='content_')
    
    for container in material_containers:
        title_div = container.find('div', class_='c_title')
        text_div = container.find('div', class_='text_area mm_cnt')
        
        if title_div and text_div:
            article_num = title_div.get_text(strip=True)
            article_text = text_div.get_text(separator='\n', strip=True)
            full_chunk_text = f"{article_num}\n{article_text}"
            full_chunk_text = re.sub(r'\n+', '\n', full_chunk_text)
            
            if len(full_chunk_text) > 10:
                chunks.append({
                    "content": full_chunk_text,
                    "metadata": {
                        "article": article_num,
                        "document_name": doc_title,
                        "document_type": "تشريع اتحادي",
                        "source_file": file_name
                    }
                })
    return chunks, doc_title

def ingest_html_chunks(chunks_data):
    if not chunks_data:
        return

    doc_name = chunks_data[0]["metadata"]["document_name"]
    print(f"  -> Uploading {len(chunks_data)} chunks for: {doc_name}...")
    
    for i, chunk_info in enumerate(chunks_data):
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
            print(f"  -> Error inserting {metadata.get('article', 'chunk')} in {doc_name}: {e}")

if __name__ == "__main__":
    DRIVE_FOLDER_ID = "1I4FMiPcmwibCitmxPi7zd040p1RJV8pM" 
    
    files_to_process = get_files_from_drive_folder(DRIVE_FOLDER_ID)
    
    for file_info in files_to_process:
        file_id = file_info["id"]
        file_name = file_info["name"]
        mime_type = file_info["mimeType"]
        
        print(f"\nProcessing [{file_name}]...")
        try:
            html_content = read_file_from_drive(file_id, mime_type)
            if html_content is None:
                continue 
                
            extracted_chunks, doc_title = process_html_content(html_content, file_name)
            
            # --- فحص هل التشريع موجود مسبقاً لمنع التكرار ---
            existing = supabase.table("legal_documents").select("id").eq("document_name", doc_title).limit(1).execute()
            if existing.data:
                print(f"  -> Skipped: '{doc_title}' is already in Supabase.")
                continue
            # ---------------------------------------------
            
            if extracted_chunks:
                ingest_html_chunks(extracted_chunks)
            else:
                print(f"  -> No valid legal chunks found in {file_name}")
                
        except Exception as e:
             print(f"  -> ERROR processing file {file_name}: {e}")
            
    print("\n--- ALL FILES FROM DRIVE PROCESSED SUCCESSFULLY! ---")