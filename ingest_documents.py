import os
import re
import io
import pickle
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
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

# 2. إعداد الاتصال بـ Google Drive (طريقة OAuth)
print("Connecting to Google Drive...")
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = None

# التحقق من وجود ملف token.pickle (الذي يحفظ جلسة الدخول)
if os.path.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
        creds = pickle.load(token)

# إذا لم تكن مسجل الدخول، أو الجلسة انتهت، اطلب تسجيل الدخول
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        # هنا سيفتح المتصفح (أو يطبع رابطاً في Codespaces) ليطلب منك الموافقة
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_console()
        
    # حفظ الجلسة للمرات القادمة
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)

drive_service = build('drive', 'v3', credentials=creds)

def get_files_from_drive_folder(folder_id):
    """
    جلب قائمة بأسماء ومعرفات الملفات (HTML) من مجلد معين في درايف.
    """
    print(f"Fetching file list from Drive Folder ID: {folder_id}...")
    files_list = []
    page_token = None
    
    while True:
        query = f"'{folder_id}' in parents and (mimeType='text/html' or name contains '.html') and trashed=false"
        response = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='nextPageToken, files(id, name)',
            pageToken=page_token
        ).execute()
        
        for file in response.get('files', []):
            files_list.append((file.get('id'), file.get('name')))
            
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
            
    print(f"Found {len(files_list)} HTML files in Drive.")
    return files_list

def read_file_from_drive(file_id):
    """
    قراءة محتوى الملف مباشرة من درايف إلى الذاكرة (بدون تحميله للجهاز)
    """
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    
    # تحويل البيانات إلى نص
    return fh.getvalue().decode('utf-8')

def process_html_content(html_content, file_name):
    """
    قراءة ملف HTML واستخراج اسم التشريع، ثم قراءة كل مادة كنص مستقل (Chunk) 
    مع الاحتفاظ بالهيكل القانوني بناءً على الهيكل الفعلي للملف.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    chunks = []
    doc_title = "تشريع غير مسمى"
    
    # استخراج العنوان من قسم العناوين
    title_element = soup.find('div', class_='title_')
    if title_element and title_element.find('h4'):
        doc_title = title_element.find('h4').get_text(strip=True)
    elif soup.title:
         doc_title = soup.title.get_text(strip=True).replace('تشريعات الإمارات العربية المتحدة | ', '')

    # استخراج المواد (كل مادة موجودة داخل div كلاس content_ وله id يبدأ بـ item)
    material_containers = soup.find_all('div', class_='content_')
    
    for container in material_containers:
        # التأكد أن هذا الـ div هو بالفعل مادة قانونية (يحتوي على عنوان ونص)
        title_div = container.find('div', class_='c_title')
        text_div = container.find('div', class_='text_area mm_cnt')
        
        if title_div and text_div:
            # استخراج عنوان المادة (مثلاً: المادة 1)
            article_num = title_div.get_text(strip=True)
            
            # استخراج نص المادة (مع الحفاظ على الأسطر)
            article_text = text_div.get_text(separator='\n', strip=True)
            
            # دمج العنوان مع النص ليكون الـ Chunk متكاملاً ومفهوماً للبحث الدلالي
            full_chunk_text = f"{article_num}\n{article_text}"
            
            # تنظيف المسافات الزائدة
            full_chunk_text = re.sub(r'\n+', '\n', full_chunk_text)
            
            # التأكد أن المادة ليست فارغة
            if len(full_chunk_text) > 10:
                chunks.append({
                    "content": full_chunk_text,
                    "metadata": {
                        "article": article_num,
                        "document_name": doc_title,
                        "document_type": "تشريع اتحادي",
                        "source_file": file_name # للاحتفاظ باسم الملف الأصلي
                    }
                })
    return chunks, doc_title

def ingest_html_chunks(chunks_data):
    """
    رفع المواد المستخرجة إلى قاعدة بيانات Supabase.
    """
    if not chunks_data:
        return

    doc_name = chunks_data[0]["metadata"]["document_name"]
    print(f"Uploading {len(chunks_data)} chunks for: {doc_name}...")
    
    for i, chunk_info in enumerate(chunks_data):
        chunk_text = chunk_info["content"]
        metadata = chunk_info["metadata"]
        
        # توليد المتجه الرقمي
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
            print(f"Error inserting {metadata.get('article', 'chunk')} in {doc_name}: {e}")

# ==========================================
# منطقة التشغيل (Batch Processing)
# ==========================================
if __name__ == "__main__":
    # --- ضع هنا الـ Folder ID الخاص بمجلد التشريعات في جوجل درايف ---
    # مثال: إذا كان الرابط https://drive.google.com/drive/folders/1A2B3C4D5E
    # فإن الـ ID هو 1A2B3C4D5E
    DRIVE_FOLDER_ID = "1l-GasvdqL26PTt4uRiJGQJOHIfVOBwxn" 
    
    files_to_process = get_files_from_drive_folder(DRIVE_FOLDER_ID)
    
    for file_id, file_name in files_to_process:
        print(f"\nProcessing {file_name}...")
        try:
            # 1. قراءة الملف من درايف للذاكرة
            html_content = read_file_from_drive(file_id)
            
            # 2. استخراج المواد والهيكل
            extracted_chunks, doc_title = process_html_content(html_content, file_name)
            
            # 3. الرفع
            if extracted_chunks:
                ingest_html_chunks(extracted_chunks)
            else:
                print(f"No valid chunks found in {file_name}")
                
        except Exception as e:
             print(f"Error processing file {file_name}: {e}")
            
    print("\n--- ALL FILES FROM DRIVE PROCESSED SUCCESSFULLY! ---")