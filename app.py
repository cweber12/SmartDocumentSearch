from flask import Flask, render_template, request, jsonify
import s3_operations
import boto3

app = Flask(__name__)
s3_client = boto3.client('s3')
S3_BUCKET = 'weber436'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/viewer')
def viewer():
    # viewer.html will read query parameters ?file and ?keyword
    return render_template('viewer.html')

@app.route("/query", methods=["GET"])
def query():
    keyword = request.args.get("keyword")
    file_key = request.args.get("file_key")

    # Download the original PDF from S3
    s3_client.download_file(S3_BUCKET, file_key, "original.pdf")

    # Extract text & coordinates
    extracted_words = s3_operations.extract_text_with_coordinates(S3_BUCKET, file_key)

    # Highlight matching text in the PDF
    highlighted_pdf = s3_operations.highlight_text_in_pdf("original.pdf", extracted_words, keyword)

    # Upload the highlighted PDF to S3
    highlighted_key = "highlighted_" + file_key
    presigned_url = s3_operations.upload_to_s3(highlighted_pdf, S3_BUCKET, highlighted_key)

    return jsonify({"highlighted_pdf_url": presigned_url})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
