from flask import Flask, request, render_template, jsonify, send_from_directory, redirect, url_for
import os
# CUSTOM MODULES
from preprocessors import TextIn
from tts import TTSGenerator
# END CUSTOM MODULES

app = Flask(__name__)

# Set upload folder and ensure it exists
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'clean_text'
AUDIO_FOLDER = 'audio'  # Folder for generated audio files
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER

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
    # Ensure file is part of the request
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']

    # Ensure the file has a valid filename
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Ensure the file is an EPUB
    if not file.filename.endswith('.epub'):
        return jsonify({"error": "Invalid file type. Only .epub files are supported."}), 400

    # Retrieve title and author from the form
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()

    # Validate title and author
    if not title or not author:
        return jsonify({"error": "Both title and author fields are required."}), 400

    # Save the uploaded file
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        # Process the file using TextIn
        text_processor = TextIn(
            source=filepath,
            start=1,  # Example start chapter
            end=999,  # Process all chapters
            skiplinks=True,
            debug=False,
            customwords='custom_words.txt',  # Provide a custom dictionary file
            title=title,  # Use the provided title
            author=author  # Use the provided author
        )

        # Return success response
        return jsonify({"message": f"File processed successfully. Output saved in '{PROCESSED_FOLDER}'."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to display available items in the clean_text directory
@app.route('/cleaned', methods=['GET'])
def available_items():
    files = os.listdir(PROCESSED_FOLDER)  # List files in the clean_text directory
    files_with_index = list(enumerate(files))  # Create a list of (index, file) tuples
    return render_template('available_items.html', files=files_with_index)

# Route for TTS generation
@app.route('/tts-form/<filename>', methods=['GET'])
def tts_form(filename):
    # Ensure the file exists in the processed folder
    if not os.path.exists(os.path.join(PROCESSED_FOLDER, filename)):
        return jsonify({"error": "File not found."}), 404

    models = ['tts_models/en/ljspeech/glow-tts','tts_models/en/ljspeech/vits','tts_models/en/ljspeech/fast_pitch','tts_models/en/vctk/fast_pitch','tts_models/en/multi-dataset/tortoise-v2','tts_models/en/ljspeech/overflow']  # Replace with actual models
    
    return render_template('tts_form.html', filename=filename, models=models)

@app.route('/generate-tts', methods=['POST'])
def generate_tts():
    filename = request.form.get('filename', '').strip()
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    model = request.form.get('model', '').strip()  # Retrieve the selected model

    # Validate inputs
    if not filename or not os.path.exists(os.path.join(PROCESSED_FOLDER, filename)):
        return jsonify({"error": "Invalid or missing file."}), 400

    if not title or not author:
        return jsonify({"error": "Both title and author fields are required."}), 400

    if not model:
        return jsonify({"error": "Model selection is required."}), 400

    filepath = os.path.join(PROCESSED_FOLDER, filename)

    try:
        # Generate TTS with the specified model
        tts_generator = TTSGenerator(model=model)  # Pass the model to the TTS generator
        output_file = tts_generator.generate_wav(filepath, author, title)

        # Move generated file to AUDIO_FOLDER
        final_path = os.path.join(app.config['AUDIO_FOLDER'], os.path.basename(output_file))
        os.rename(output_file, final_path)

        return jsonify({"message": "TTS audio generated successfully.", "file": final_path, "model": model}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
