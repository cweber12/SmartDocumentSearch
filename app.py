from flask import Flask, render_template, request
import s3_operations
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/viewer')
def viewer():
    # viewer.html will read query parameters ?file and ?keyword
    return render_template('viewer.html')

@app.route('/query', methods=['GET', 'POST'])
def query():
    results = None
    log = ""
    keyword = ""
    if request.method == 'POST':
        keyword = request.form.get('keyword', '').strip()
        if keyword:
            results, log = s3_operations.query_documents(keyword)
    return render_template('query.html', keyword=keyword, results=results, log=log)

@app.route("/upload", methods=["GET", "POST"])
def upload_file_route():
    if request.method == "POST":
        if "file" not in request.files:
            return "No file part"

        file = request.files["file"]

        if file.filename == "":
            return "No selected file"

        if not allowed_file(file.filename):
            return "Error: Only PDF files are allowed."

        # Save file temporarily in /tmp for AWS Elastic Beanstalk
        temp_path = os.path.join("/tmp", file.filename)
        file.save(temp_path)

        # Upload to S3
        upload_result = s3_operations.upload_file(temp_path)

        # Remove temporary file after upload
        os.remove(temp_path)

        return upload_result  # Return success or error message

    return render_template("upload.html")

ALLOWED_EXTENSIONS = {"pdf"}  # Only allow PDFs

def allowed_file(filename):
    """Check if the uploaded file has a .pdf extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
