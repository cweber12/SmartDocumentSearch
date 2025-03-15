import boto3
import os
import hashlib
import fitz  # PyMuPDF for PDF highlighting
import time

BUCKET_NAME = 'weber436'
s3_client = boto3.client('s3')
textract_client = boto3.client('textract', region_name='us-east-2')

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

def upload_file(file, username, folder):
    file_key = f'users/{username}/{folder}/{file.filename}'
    s3_client.upload_fileobj(file, BUCKET_NAME, file_key)
    return file_key

def list_user_files(username):
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=f'users/{username}/')
    return [obj['Key'] for obj in response.get('Contents', [])]

# Textract & Query

def extract_text_with_coordinates(s3_key):
    # Check file size before processing
    response = s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
    file_size = response['ContentLength']

    if file_size == 0:
        print(f"Error: {s3_key} is empty. Skipping Textract.")
        return []

    # Start Textract Job
    response = textract_client.start_document_text_detection(
        DocumentLocation={'S3Object': {'Bucket': BUCKET_NAME, 'Name': s3_key}}
    )
    job_id = response['JobId']
    print(f"Textract Job Started: {job_id}")

    # Wait for Textract to complete
    while True:
        result = textract_client.get_document_text_detection(JobId=job_id)
        job_status = result.get("JobStatus")

        if job_status == "SUCCEEDED":
            break
        elif job_status == "FAILED":
            print(f"Textract failed for {s3_key}")
            return []

        print(f"Waiting for Textract job {job_id} to complete...")
        time.sleep(5)  # Wait 5 seconds before checking again

    # Process results
    extracted_words = []
    for item in result.get('Blocks', []):
        if item['BlockType'] == 'WORD':
            text = item.get('Text', None)  # Safe way to get text
            bbox = item.get('Geometry', {}).get('BoundingBox', None)
            if text and bbox:
                extracted_words.append({'Text': text, 'BoundingBox': bbox})

    return extracted_words

def highlight_text_in_pdf(local_pdf, extracted_words, keyword):
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
    highlighted_pdf = "highlighted_" + local_pdf
    doc.save(highlighted_pdf)
    return highlighted_pdf

def query_documents(username, folder, keyword):
    user_folder = f'users/{username}/{folder}/'  # Restrict search to the folder

    # List all files in the specified folder
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=user_folder)

    if 'Contents' not in response:
        print(f"No documents found in {user_folder}")
        return []

    user_files = [obj['Key'] for obj in response['Contents']]
    print(f"Found files: {user_files}")  # Debugging output

    query_folder = f'users/{username}/query_results/{keyword}/'
    found_links = []

    for s3_key in user_files:
        if not s3_key.lower().endswith('.pdf'):
            continue  # Skip non-PDF files

        print(f"Processing: {s3_key}")  # Debugging output
        extracted_words = extract_text_with_coordinates(s3_key)

        if not extracted_words:
            continue

        local_pdf = "temp.pdf"
        s3_client.download_file(BUCKET_NAME, s3_key, local_pdf)

        highlighted_pdf = highlight_text_in_pdf(local_pdf, extracted_words, keyword)
        highlighted_key = query_folder + "highlighted_" + os.path.basename(s3_key)

        s3_client.upload_file(highlighted_pdf, BUCKET_NAME, highlighted_key)
        presigned_url = s3_client.generate_presigned_url(
            'get_object', Params={'Bucket': BUCKET_NAME, 'Key': highlighted_key}, ExpiresIn=3600
        )
        found_links.append((s3_key, presigned_url))

    return found_links


def delete_query_results(username, keyword):
    query_folder = f'users/{username}/query_results/{keyword}/'
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=query_folder)
    if 'Contents' in response:
        for obj in response['Contents']:
            s3_client.delete_object(Bucket=BUCKET_NAME, Key=obj['Key'])


