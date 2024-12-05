from flask import Flask, request, render_template, jsonify, send_from_directory, redirect, url_for
import os
# CUSTOM MODULES
from preprocessors import TextIn
from tts import TTSGenerator, tts_queue
# END CUSTOM MODULES

app = Flask(__name__)

# Set upload folder and ensure it exists
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'clean_text'
AUDIO_FOLDER = 'audio'  # Folder for generated audio files
TXT_DONE_FOLDER = 'txt_done'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(TXT_DONE_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER
app.config['TXT_DONE_FOLDER'] = TXT_DONE_FOLDER

# Welcome page
@app.route('/')
def welcome():
    return render_template('index.html',title='TTS Generator Home')

# Drag-and-drop upload page
@app.route('/upload', methods=['GET'])
def upload_form():
    return render_template('upload.html',title='Epub Convertor')

# File upload and processing route
@app.route('/process', methods=['POST'])
def process_file():
    if 'file' not in request.files:
        return render_template('error.html', title="ERROR", error="No file part in the request")

    file = request.files['file']

    if file.filename == '':
        return render_template('error.html', title="ERROR", error="No selected file")

    if not file.filename.endswith('.epub'):
        return render_template('error.html', title="ERROR", error="Invalid file type. Only .epub files are supported.")

    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()

    if not title or not author:
        return render_template('error.html', title="ERROR", error="Both title and author fields are required.")

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        text_processor = TextIn(
            source=filepath,
            start=1,
            end=999,
            skiplinks=True,
            debug=False,
            customwords='custom_words.txt',
            title=title,
            author=author
        )
        return render_template('success.html', title='SUCCESS', message="File processed successfully.", output_folder=PROCESSED_FOLDER)
    except Exception as e:
        return render_template('error.html', title='ERROR', error=str(e))


# Route to display available items in the clean_text directory
@app.route('/cleaned', methods=['GET'])
def available_items():
    files = os.listdir(PROCESSED_FOLDER)  # List files in the clean_text directory
    files_with_index = list(enumerate(files))  # Create a list of (index, file) tuples
    return render_template('available_items.html', title='Text Inventory', files=files_with_index)

# Route to display available items in the clean_text directory
@app.route('/text-archive', methods=['GET'])
def archived_items():
    files = os.listdir(TXT_DONE_FOLDER)  # List files in the clean_text directory
    files_with_index = list(enumerate(files))  # Create a list of (index, file) tuples
    return render_template('available_items.html', title='Archived Text', files=files_with_index)

# Route for TTS generation
@app.route('/tts-form/<filename>', methods=['GET'])
def tts_form(filename):
    # Ensure the file exists in the processed folder
    if not os.path.exists(os.path.join(PROCESSED_FOLDER, filename)):
        return render_template('error.html', title='ERROR', error="File Not Found.")

    models = ['tts_models/en/ljspeech/glow-tts','tts_models/en/ljspeech/vits','tts_models/en/multi-dataset/tortoise-v2','tts_models/en/ljspeech/overflow']  # Replace with actual models
    
    return render_template('tts_form.html', title='TTS request', filename=filename, models=models)

@app.route('/generate-tts', methods=['POST'])
def generate_tts():
    filename = request.form.get('filename', '').strip()
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    model = request.form.get('model', '').strip()

    if not filename or not os.path.exists(os.path.join(PROCESSED_FOLDER, filename)):
        return render_template('error.html', title='ERROR', error="Invalid or missing file.")

    if not title:
        return render_template('error.html', title='ERROR', error="Title is required.")

    if not author:
        return render_template('error.html', title='ERROR', error="Author is required.")

    if not model:
        return render_template('error.html', title='ERROR', error="Model selection is required.")

    filepath = os.path.join(PROCESSED_FOLDER, filename)

    try:
        tts_generator = TTSGenerator(file_path=filepath, author=author, title=title, model=model)
        tts_generator.generate_wav()
        
        output_file = os.path.splitext(filepath)[0] + ".wav"
        final_path = os.path.join(app.config['AUDIO_FOLDER'], os.path.basename(output_file))

        os.makedirs(app.config['AUDIO_FOLDER'], exist_ok=True)
        os.rename(output_file, final_path)

        return render_template('success.html', title='SUCCESS', message="TTS audio generated successfully.", file=final_path, model=model)
    except Exception as e:
        return render_template('error.html', title='ERROR', error=str(e))


@app.route('/add-to-queue', methods=['POST'])
def add_to_queue():
    filename = request.form.get('filename', '').strip()
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    model = request.form.get('model', '').strip()

    if not filename:
        return render_template('error.html', title='ERROR', error="Filename is required.")

    file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)

    if not os.path.exists(file_path):
        return render_template('error.html', title='ERROR', error=f"File not found in processed directory: {file_path}")

    try:
        tts_task = TTSGenerator(file_path=file_path, author=author, title=title, model=model)
        tts_queue.put(tts_task)
        return render_template('success.html', title='SUCCESS', message="Task added to queue.")
    except Exception as e:
        return render_template('error.html', title='ERROR', error=str(e))


@app.route('/tts-all-form', methods=['GET'])
def tts_all_form():
    """
    Render the form to queue TTS for all files.
    """
    available_models = ["tts_models/en/ljspeech/glow-tts", "tts_models/en/other-model"]  # Update with actual model names
    return render_template('tts_all_form.html', models=available_models)

@app.route('/generate-tts-all', methods=['POST'])
def generate_tts_all():
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    model = request.form.get('model', '').strip()

    if not title or not author or not model:
        return render_template('error.html', error="All fields are required.")

    files = os.listdir(PROCESSED_FOLDER)
    queued_files = []

    for filename in files:
        file_path = os.path.join(PROCESSED_FOLDER, filename)
        if not os.path.isfile(file_path):
            continue

        tts_task = TTSGenerator(file_path=file_path, author=author, title=title, model=model)
        tts_queue.put(tts_task)
        queued_files.append(filename)

    return render_template('success.html',  title='SUCCESS',
                           message=f"Queued {len(queued_files)} files for processing.",
                           details=queued_files)

# Route to display available items in the tts audio directory
@app.route('/audio', methods=['GET'])
def available_audio():
    files = os.listdir(AUDIO_FOLDER)  # List files in the clean_text directory
    files_with_index = list(enumerate(files))  # Create a list of (index, file) tuples
    return render_template('available_audio.html', title='Audio Inventory', files=files_with_index)
@app.route('/audio/download/<filename>', methods=['GET'])
def download_audio_file(filename):
    # Ensure the file exists in the audio folder
    if not os.path.exists(os.path.join(AUDIO_FOLDER, filename)):
        return jsonify({"error": "File not found."}), 404
    return send_from_directory(AUDIO_FOLDER, filename, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
