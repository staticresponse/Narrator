from flask import Flask, request, render_template, jsonify
import os
from preprocessors import TextIn

app = Flask(__name__)

# Set upload folder and ensure it exists
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'clean_text'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Welcome page
@app.route('/')
def welcome():
    return "<h1>Welcome to the EPUB Preprocessor!</h1><p>Upload an EPUB file for processing.</p>"

# Drag-and-drop upload page
@app.route('/upload', methods=['GET'])
def upload_form():
    return render_template('upload.html')

# File upload and processing route
@app.route('/process', methods=['POST'])
def process_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not file.filename.endswith('.epub'):
        return jsonify({"error": "Invalid file type. Only .epub files are supported."}), 400

    # Save the uploaded file
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        # Process the file using TextIn from preprocessor.py
        text_processor = TextIn(
            source=filepath,
            start=1,  # Example start chapter
            end=999,  # Process all chapters
            skiplinks=True,
            debug=False,
            customwords='custom_words.txt',  # Provide a custom dictionary file
            title="Sample Title",
            author="Sample Author"
        )

        # Return success response
        return jsonify({"message": f"File processed successfully. Output saved in '{PROCESSED_FOLDER}'."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
