from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import s3_operations
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure value

@app.route('/')
def index():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if s3_operations.authenticate_user(username, password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid username or password.")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if s3_operations.register_user(username, password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('register.html', error="Username already exists.")
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        folder = request.form['folder'].strip()
        files = request.files.getlist('file')
        
        if not folder:
            return render_template('upload.html', error="Please enter a folder name.")
        
        for file in files:
            s3_operations.upload_file(file, session['username'], folder)
        
        return render_template('upload.html', success="Files uploaded successfully.")
    
    return render_template('upload.html')

@app.route('/query', methods=['GET', 'POST'])
def query():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        folder = request.form['folder'].strip()
        keyword = request.form['keyword'].strip()

        if not folder or not keyword:
            return "Error: Folder and keyword are required.", 400

        # 🔹 Debugging: Print exact S3 keys stored in the folder
        stored_files = s3_operations.debug_list_keys(session['username'], folder)
        print("Stored files:", stored_files)  # ✅ This prints to the terminal

        # 🔹 Run the query after confirming file paths
        results = s3_operations.query_documents(session['username'], folder, keyword)

        # Convert S3 keys to public URLs
        public_urls = [s3_operations.get_public_s3_url(file) for file in results]

        return render_template('viewer.html', presigned_urls=public_urls)

    return render_template('query.html')


@app.route('/viewer', methods=['GET'])
def viewer():
    if 'username' not in session:
        return redirect(url_for('login'))

    keyword = request.args.get("keyword")
    folder = request.args.get("folder")

    if not keyword or not folder:
        return "Error: Missing keyword or folder.", 400

    # 🔹 Get only the correct S3 object keys
    results = s3_operations.query_documents(session['username'], folder, keyword)

    # ✅ Convert S3 keys to proper public URLs
    public_urls = [s3_operations.get_public_s3_url(file) for file in results]

    return render_template('viewer.html', presigned_urls=public_urls)

@app.route('/delete_query_results', methods=['POST'])
def delete_query_results():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 403

    keyword = request.form.get("keyword")
    if not keyword:
        return jsonify({"error": "Keyword is required"}), 400

    s3_operations.delete_query_results(session['username'], keyword)
    return jsonify({"success": "Query results deleted successfully."})

ALLOWED_EXTENSIONS = {"pdf"}

def allowed_file(filename):
    """Check if the uploaded file has a .pdf extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)



