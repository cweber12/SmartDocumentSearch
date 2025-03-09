import os
import posixpath  # Ensures S3 keys use forward slashes
import boto3
import urllib.parse

# S3 bucket and directory (prefix) where files will be stored
BUCKET_NAME = 'weber436'
DOCUMENTS_PREFIX = 'documents/'  # all files will be stored under this prefix

# Create clients for S3 and Textract
s3_client = boto3.client('s3')
textract_client = boto3.client('textract')


def upload_file(file_path):
    """Upload a file to the S3 bucket under the documents directory."""
    if not os.path.exists(file_path):
        return f"Error: File {file_path} does not exist."

    filename = os.path.basename(file_path)
    # Use posixpath.join to ensure forward slashes for S3 keys
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
    
    # Exclude the directory itself if it shows up
    files = [obj['Key'] for obj in response['Contents'] if obj['Key'] != DOCUMENTS_PREFIX]
    return files, "Documents listed successfully."


def extract_text_and_pages(s3_key):
    """
    Extract text from a document in S3 using Textract.
    Returns a list of tuples (line_text, page_number) for each line.
    """
    try:
        response = textract_client.detect_document_text(
            Document={'S3Object': {'Bucket': BUCKET_NAME, 'Name': s3_key}}
        )
    except Exception as e:
        return [], f"Error extracting text from {s3_key}: {e}"

    results = []
    for block in response.get('Blocks', []):
        if block['BlockType'] == 'LINE':
            # For multi-page documents, Textract often includes a "Page" field.
            page = block.get('Page', 1)
            results.append((block['Text'], page))
    return results, f"Extracted text with page numbers from {s3_key}."


def generate_presigned_url(s3_key, expires_in=3600):
    """Generate a presigned URL for the given S3 object."""
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=expires_in
        )
        return url
    except Exception as e:
        return None


def query_documents(keyword):
    """
    Query all documents in S3 for a keyword.
    For each document where the keyword is found (using Textract output), 
    generate a presigned URL and build a link to a custom viewer page.
    
    The viewer page is hosted on S3 as a static website.
    Replace "http://my-static-viewer-bucket.s3-website-us-east-1.amazonaws.com/viewer.html" 
    with your actual S3 website endpoint.
    """
    documents, msg = list_documents()
    if not documents:
        return [], f"No documents found. {msg}"

    found_links = []
    log_messages = ""
    for s3_key in documents:
        log_messages += f"Processing {s3_key}...\n"
        text_lines, txt_msg = extract_text_and_pages(s3_key)
        log_messages += txt_msg + "\n"
        page_found = None
        for line, page in text_lines:
            if keyword.lower() in line.lower():
                page_found = page
                break
        if page_found is not None:
            presigned_url = generate_presigned_url(s3_key)
            if presigned_url:
                # URL-encode the presigned URL and keyword so that query parameters don't conflict
                encoded_presigned_url = urllib.parse.quote_plus(presigned_url)
                encoded_keyword = urllib.parse.quote_plus(keyword)
                viewer_url = f"http://weber436.s3-website-us-east-2.amazonaws.com/viewer.html?file={encoded_presigned_url}&keyword={encoded_keyword}"
                found_links.append((s3_key, viewer_url))
            else:
                log_messages += f"Failed to generate URL for {s3_key}.\n"
        else:
            log_messages += f"Keyword '{keyword}' not found in {s3_key}.\n"
    if not found_links:
        log_messages += f"No documents contained the keyword '{keyword}'.\n"
    return found_links, log_messages
