from flask import Flask, request, render_template, jsonify, send_from_directory, redirect, url_for, flash
import os
import json
import datetime #unused
from bs4 import BeautifulSoup
from werkzeug.utils import secure_filename
# CUSTOM MODULES
from preprocessors import TextIn
from wave_gen import KokoroGenerator, tts_queue
# END CUSTOM MODULES

app = Flask(__name__)

# Set upload folder and ensure it exists
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'clean_text'
AUDIO_FOLDER = 'audio'
TXT_DONE_FOLDER = 'txt_done'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(TXT_DONE_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER
app.config['TXT_DONE_FOLDER'] = TXT_DONE_FOLDER

app.secret_key = os.environ.get('FLASK_SECRET_KEY')

if not app.secret_key:
    print ("Key not set. Using dummy value for testing")
    app.secret_key = "testing"

@app.route('/', methods=['GET', 'POST'])
def welcome():
    voices = {
        "af_bella": "American Bella",
        "bf_emma": "British Emma"
    }

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        model = request.form.get('model', '').strip()
        voice = request.form.get('voice', '').strip()
        content = request.form.get('content', '').strip()
        filename = secure_filename(f"{title}.txt")

        if not filename or not content:
            return render_template('error.html', title='ERROR', error="Title and content are required.")

        file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            config = {
                "filename": file_path,
                "title": title,
                "author": author,
                "model": model,
                "voice": voice
            }

            tts_task = KokoroGenerator(config)
            tts_queue.put(tts_task)

            return render_template('success.html', title='SUCCESS', message="Task added to queue.")
        except Exception as e:
            return render_template('error.html', title='ERROR', error=str(e))

    # GET method - show form
    return render_template('index.html', title='TTS Generator', voices=voices)
    
@app.route('/version', methods=['GET'])
def get_version():
    with open("version.json", "r") as f:
        version_info = json.load(f)
    return jsonify(version_info)

# Drag-and-drop upload page
@app.route('/upload', methods=['GET'])
def upload_form():
    return render_template('upload.html',title='Epub Convertor')

# File upload and processing route@app.route('/process', methods=['POST'])
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
    intro = request.form.get('intro', '').strip()
    outtro = request.form.get('outtro', '').strip()
    chapters_per_file = int(request.form.get('chapters_per_file', '1').strip())

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
            author=author,
            chapters_per_file=chapters_per_file,
            intro=intro,       # Pass intro
            outtro=outtro      # Pass outtro
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
    
@app.route('/cleaned/delete/<filename>', methods=['POST'])
def delete_text_file(filename):
    filepath = os.path.join(PROCESSED_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f"{filename} has been deleted.", "success")
    else:
        flash(f"{filename} not found.", "danger")
    return redirect(url_for('available_items'))

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

    models = ['kokoro']  # Replace with actual models
    return render_template('tts_form.html', title='TTS request', filename=filename, models=models)

@app.route('/generate-tts', methods=['POST'])
def generate_tts():
    # Extract form values
    filename = request.form.get('filename', '').strip()
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    model = request.form.get('model', '').strip()
    subject = request.form.get('subject', '').strip()  # Added if form includes it
    voice = request.form.get('voice', '').strip()

    # Validate
    if not filename or not os.path.exists(os.path.join(PROCESSED_FOLDER, filename)):
        return render_template('error.html', title='ERROR', error="Invalid or missing file.")

    if not title:
        return render_template('error.html', title='ERROR', error="Title is required.")

    if not author:
        return render_template('error.html', title='ERROR', error="Author is required.")

    # Build absolute file path
    filepath = os.path.join(PROCESSED_FOLDER, filename)

    # Prepare configuration dictionary
    config = {
        'filename': filepath,
        'title': title,
        'author': author,
        'model': model,
        'subject': subject,
        'voice': voice
    }

    extra_keys = request.form.getlist('extra_keys[]')
    extra_values = request.form.getlist('extra_values[]')
    extra_args = {k: v for k, v in zip(extra_keys, extra_values) if k.strip()}
    config.update(extra_args)

    try:
        # Create generator and run
        tts_generator = KokoroGenerator(config)
        tts_generator.generate_wav()

        # Move output to AUDIO_FOLDER
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
    subject = request.form.get('subject', '').strip()
    voice = request.form.get('voice', '').strip()

    if not filename:
        return render_template('error.html', title='ERROR', error="Filename is required.")

    file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)

    if not os.path.exists(file_path):
        return render_template('error.html', title='ERROR', error=f"File not found in processed directory: {file_path}")

    try:
        # Build the config dictionary for KokoroGenerator
        config = {
            "filename": file_path,
            "title": title,
            "author": author,
            "model": model,
            "subject": subject,
            "voice": voice
        }
        extra_keys = request.form.getlist('extra_keys[]')
        extra_values = request.form.getlist('extra_values[]')
        extra_args = {k: v for k, v in zip(extra_keys, extra_values) if k.strip()}
        config.update(extra_args)

        # Create TTS task and enqueue it
        tts_task = KokoroGenerator(config)
        tts_queue.put(tts_task)

        return render_template('success.html', title='SUCCESS', message="Task added to queue.")
    except Exception as e:
        return render_template('error.html', title='ERROR', error=str(e))



@app.route('/tts-all-form', methods=['GET'])
def tts_all_form():
    """
    Render the form to queue TTS for all files.
    """
    available_models = ['kokoro']
    return render_template('tts_all_form.html', models=available_models)

@app.route('/generate-tts-all', methods=['POST'])
def generate_tts_all():
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    model = request.form.get('model', '').strip()
    subject = request.form.get('subject', '').strip()
    voice = request.form.get('voice', '').strip()

    if not title or not author or not model:
        return render_template('error.html', title='ERROR', error="All fields are required.")

    files = os.listdir(app.config['PROCESSED_FOLDER'])
    queued_files = []

    for filename in files:
        file_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
        if not os.path.isfile(file_path):
            continue

        config = {
            "filename": file_path,
            "title": title,
            "author": author,
            "model": model,
            "subject": subject,
            "voice": voice
        }
        extra_keys = request.form.getlist('extra_keys[]')
        extra_values = request.form.getlist('extra_values[]')
        extra_args = {k: v for k, v in zip(extra_keys, extra_values) if k.strip()}
        config.update(extra_args)

        try:
            tts_task = KokoroGenerator(config)
            tts_queue.put(tts_task)
            queued_files.append(filename)
        except Exception as e:
            logger.error(f"Failed to queue file {filename}: {e}")

    return render_template(
        'success.html',
        title='SUCCESS',
        message=f"Queued {len(queued_files)} files for processing.",
        details=queued_files
    )
    
@app.route('/current-queue', methods=['GET'])
def current_queue():
    """
    Display the current items in the TTS queue.
    """
    queue_items = []
    with tts_queue.mutex:
        for task in list(tts_queue.queue):
            queue_items.append({
                'file_path': task.file_path,
                'author': task.author,
                'title': task.title,
                'model': task.model
            })

    return render_template('queue.html', title="Current TTS Queue", queue_items=queue_items)

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
    
@app.route('/audio/play/<filename>', methods=['GET'])
def play_audio_file(filename):
    # Ensure the file exists in the audio folder
    if not os.path.exists(os.path.join(AUDIO_FOLDER, filename)):
        return jsonify({"error": "File not found."}), 404
    # Serve the file inline without forcing a download
    return send_from_directory(AUDIO_FOLDER, filename)


@app.route('/edit/<filename>', methods=['GET'])
def edit_text(filename):
    filepath = os.path.join(PROCESSED_FOLDER, filename)
    if not os.path.exists(filepath):
        return render_template('error.html', title='ERROR', error='File not found.')
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return render_template('edit_text.html', title='Edit Text', filename=filename, content=content)

@app.route('/save/<filename>', methods=['POST'])
def save_text(filename):
    filepath = os.path.join(PROCESSED_FOLDER, filename)
    content = request.form.get('content', '')

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return render_template('success.html', title='SUCCESS', message='File saved successfully.')
    except Exception as e:
        return render_template('error.html', title='ERROR', error=str(e))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)