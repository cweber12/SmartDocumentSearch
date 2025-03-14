import os
import posixpath  # Ensures S3 keys use forward slashes
import boto3
import urllib.parse
import time
import fitz  # PyMuPDF for PDF highlighting

# S3 bucket and directory (prefix) where files will be stored
BUCKET_NAME = 'weber436'
DOCUMENTS_PREFIX = 'documents/'  # All files stored under this prefix

# Create clients for S3 and Textract
s3_client = boto3.client('s3')
textract_client = boto3.client('textract', region_name='us-east-2')


def upload_file(file_path):
    """Upload a file to the S3 bucket under the documents directory."""
    if not os.path.exists(file_path):
        return f"Error: File {file_path} does not exist."

    filename = os.path.basename(file_path)
    s3_key = posixpath.join(DOCUMENTS_PREFIX, filename)

    try:
        s3_client.upload_file(file_path, BUCKET_NAME, s3_key)
        return f"Uploaded {file_path} to s3://{BUCKET_NAME}/{s3_key}"
    except Exception as e:
        return f"Upload failed for {file_path}: {e}"


def list_documents():
    """List all documents in the S3 bucket under the specified prefix."""
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=DOCUMENTS_PREFIX)
    except Exception as e:
        return [], f"Error listing documents: {e}"

    if 'Contents' not in response:
        return [], "No documents found in the specified directory."

    files = [obj['Key'] for obj in response['Contents'] if obj['Key'] != DOCUMENTS_PREFIX]
    return files, "Documents listed successfully."


def extract_text_with_coordinates(s3_key):
    """
    Extract text from a document in S3 using AWS Textract's asynchronous API.
    Returns a list of extracted words along with their bounding box coordinates.
    """
    try:
        start_response = textract_client.start_document_text_detection(
            DocumentLocation={'S3Object': {'Bucket': BUCKET_NAME, 'Name': s3_key}}
        )
        job_id = start_response['JobId']
    except Exception as e:
        return [], f"Error starting Textract for {s3_key}: {e}"

    # Poll for job completion
    while True:
        try:
            response = textract_client.get_document_text_detection(JobId=job_id)
        except Exception as e:
            return [], f"Error retrieving Textract job result for {s3_key}: {e}"
        
        status = response['JobStatus']
        if status == 'SUCCEEDED':
            break
        elif status == 'FAILED':
            return [], f"Textract job failed for {s3_key}"
        time.sleep(5)

    words = []
    for block in response.get('Blocks', []):
        if block['BlockType'] == 'WORD':
            words.append({
                'Text': block['Text'],
                'BoundingBox': block['Geometry']['BoundingBox']
            })
    
    return words, f"Extracted text and bounding boxes from {s3_key}."


def highlight_text_in_pdf(local_pdf, extracted_words, keyword):
    """Highlight the given keyword in the PDF using Textract's bounding boxes."""
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


def upload_to_s3(local_file, s3_key):
    """Upload a file to S3 and return a presigned URL."""
    s3_client.upload_file(local_file, BUCKET_NAME, s3_key)
    return s3_client.generate_presigned_url('get_object', Params={'Bucket': BUCKET_NAME, 'Key': s3_key}, ExpiresIn=3600)


def generate_presigned_url(s3_key, expires_in=3600):
    """Generate a presigned URL for the given S3 object."""
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=expires_in
        )
        return url
    except Exception:
        return None


def query_documents(keyword):
    """
    Query all documents in S3 for a keyword.
    If the keyword is found in a document, generate a highlighted version.
    Returns a list of highlighted PDF URLs.
    """
    documents, msg = list_documents()
    if not documents:
        return [], f"No documents found. {msg}"

    found_links = []
    log_messages = ""
    
    for s3_key in documents:
        log_messages += f"Processing {s3_key}...\n"

        # Extract text and coordinates
        extracted_words, txt_msg = extract_text_with_coordinates(s3_key)
        log_messages += txt_msg + "\n"

        if not extracted_words:
            continue  # Skip if no text found

        # Download original PDF from S3
        local_pdf = "original.pdf"
        s3_client.download_file(BUCKET_NAME, s3_key, local_pdf)

        # Highlight text in PDF
        highlighted_pdf = highlight_text_in_pdf(local_pdf, extracted_words, keyword)

        # Upload highlighted PDF to S3
        highlighted_key = "highlighted_" + s3_key
        presigned_url = upload_to_s3(highlighted_pdf, highlighted_key)

        found_links.append((s3_key, presigned_url))

    if not found_links:
        log_messages += f"No documents contained the keyword '{keyword}'.\n"

    return found_links, log_messages
