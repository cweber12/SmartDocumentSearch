from flask import Flask, render_template, request
import s3_operations

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

if __name__ == '__main__':
    app.run(debug=True)
