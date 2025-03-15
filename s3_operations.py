import boto3
import os
import hashlib
import fitz  # PyMuPDF for PDF highlighting
import time
import urllib.parse 
import re 

BUCKET_NAME = 'weber436'
REGION = 'us-east-2'
s3_client = boto3.client('s3', region_name=REGION)
textract_client = boto3.client('textract', region_name=REGION)

# User Management

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    user_folder = f'users/{username}/'
    existing_users = list_users()
    
    if username in existing_users:
        return False
    
    s3_client.put_object(Bucket=BUCKET_NAME, Key=user_folder)
    s3_client.put_object(Bucket=BUCKET_NAME, Key=f'users/{username}/password.txt', Body=hash_password(password))
    return True

def authenticate_user(username, password):
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=f'users/{username}/password.txt')
        stored_password = response['Body'].read().decode('utf-8')
        return stored_password == hash_password(password)
    except:
        return False

def list_users():
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix='users/', Delimiter='/')
    return [prefix['Prefix'].split('/')[-2] for prefix in response.get('CommonPrefixes', [])]

# File Management

def get_public_s3_url(file_key):
    """Returns a correctly formatted S3 URL."""
    encoded_key = file_key.replace(" ", "%20")  # ✅ Encode spaces correctly
    return f"https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{encoded_key}"


def upload_file(file, username, folder):
    """Ensure filenames are URL-safe before uploading to S3."""
    safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', file.filename)  # ✅ Replace all special chars
    file_key = f'users/{username}/{folder}/{safe_filename}'

    s3_client.upload_fileobj(file, BUCKET_NAME, file_key)
    return file_key

# Textract & Query

def extract_text_with_coordinates(s3_key):
    response = s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
    file_size = response['ContentLength']
    if file_size == 0:
        return []

    response = textract_client.start_document_text_detection(
        DocumentLocation={'S3Object': {'Bucket': BUCKET_NAME, 'Name': s3_key}}
    )
    job_id = response['JobId']

    while True:
        result = textract_client.get_document_text_detection(JobId=job_id)
        if result.get("JobStatus") == "SUCCEEDED":
            break
        time.sleep(5)

    extracted_words = []
    for item in result.get('Blocks', []):
        if item['BlockType'] == 'WORD':
            extracted_words.append({'Text': item.get('Text', ''), 'BoundingBox': item.get('Geometry', {}).get('BoundingBox', None)})

    return extracted_words

def highlight_text_in_pdf(local_pdf, extracted_words, keyword):
    """Highlight detected words that match the keyword in the PDF."""
    doc = fitz.open(local_pdf)
    
    for page in doc:
        for word in extracted_words:
            if keyword.lower() in word['Text'].lower():
                bbox = word['BoundingBox']
                rect = fitz.Rect(
                    bbox['Left'] * page.rect.width,
                    bbox['Top'] * page.rect.height,
                    (bbox['Left'] + bbox['Width']) * page.rect.width,
                    (bbox['Top'] + bbox['Height']) * page.rect.height
                )
                page.add_highlight_annot(rect)

    highlighted_pdf = "highlighted_" + os.path.basename(local_pdf)
    doc.save(highlighted_pdf)
    doc.close()  # 🔹 Ensure the file is properly saved before upload

    return highlighted_pdf


def query_documents(username, folder, keyword):
    """Searches for documents within a user's folder, highlights the keyword, and uploads the result."""
    user_folder = f'users/{username}/{folder}/'
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=user_folder)

    if 'Contents' not in response:
        return []

    user_files = [obj['Key'] for obj in response['Contents']]
    query_folder = f'users/{username}/query_results/{folder}/'  # ✅ Ensure folder structure matches

    found_links = []

    for s3_key in user_files:
        if not s3_key.lower().endswith('.pdf'):
            continue

        extracted_words = extract_text_with_coordinates(s3_key)
        if not extracted_words:
            continue

        local_pdf = "temp.pdf"
        s3_client.download_file(BUCKET_NAME, s3_key, local_pdf)

        # 🔹 Ensure highlighted PDF is stored in the correct query folder
        highlighted_pdf = highlight_text_in_pdf(local_pdf, extracted_words, keyword)

        highlighted_key = query_folder + "highlighted_" + os.path.basename(s3_key)

        s3_client.upload_file(highlighted_pdf, BUCKET_NAME, highlighted_key)

        found_links.append(highlighted_key)  # ✅ Append only the correct key

    return found_links


def delete_query_results(username, keyword):
    """Deletes the query results folder after viewing."""
    query_folder = f'users/{username}/query_results/{keyword}/'
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=query_folder)
    
    if 'Contents' in response:
        for obj in response['Contents']:
            s3_client.delete_object(Bucket=BUCKET_NAME, Key=obj['Key'])

    


def debug_list_keys(username, folder):
    """List all files in a folder to confirm the exact key format."""
    prefix = f'users/{username}/{folder}/'
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)

    if 'Contents' not in response:
        print(f"No files found in {prefix}")
        return []

    print("Files in S3:")
    for obj in response['Contents']:
        print(obj['Key'])  # ✅ Print exact key stored in S3

    return [obj['Key'] for obj in response['Contents']]


