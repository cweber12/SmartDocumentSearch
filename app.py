from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import s3_operations
import boto3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure value

s3_client = boto3.client('s3')
BUCKET_NAME = 'weber436'

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
        folder = request.form['folder']
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

        results = s3_operations.query_documents(session['username'], folder, keyword)

        return render_template('query.html', results=results, folder=folder, keyword=keyword)

    return render_template('query.html')


@app.route('/viewer', methods=['GET'])
def viewer():
    if 'username' not in session:
        return redirect(url_for('login'))

    keyword = request.args.get("keyword")
    folder = request.args.get("folder")  # Get the folder from query params

    if not keyword or not folder:
        return "Error: Missing keyword or folder.", 400

    results = s3_operations.query_documents(session['username'], folder, keyword)  # Pass folder correctly

    return render_template('viewer.html', presigned_urls=results)

if __name__ == '__main__':
    app.run(debug=True)


