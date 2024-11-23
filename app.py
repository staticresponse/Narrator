from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
import os
from preprocessor import TextIn

# Initialize the Flask app
app = Flask(__name__)

# Configure the upload folder and allowed file extensions
UPLOAD_FOLDER = 'uploads'
CLEAN_TEXT_FOLDER = 'clean_text'
ALLOWED_EXTENSIONS = {'epub'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLEAN_TEXT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def welcome():
    """Render a generic welcome splash page."""
    return render_template('welcome.html')

@app.route('/process', methods=['POST'])
def process_file():
    """Route for processing an uploaded EPUB file."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Initialize the preprocessor and process the file
        try:
            processor = TextIn(
                source=filepath,
                start=1,  # Starting chapter
                end=999,  # Process all chapters
                skiplinks=True,
                debug=False,
                customwords='customwords.txt',  # Path to custom words dictionary
                title="Sample Title",
                author="Sample Author"
            )
            processor.get_chapters_epub()
            return jsonify({"message": f"File processed successfully. Check {CLEAN_TEXT_FOLDER} for output."})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Invalid file type. Please upload an EPUB file."}), 400

if __name__ == '__main__':
    app.run(debug=True)