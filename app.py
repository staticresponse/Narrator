from flask import Flask, request, render_template, jsonify, send_from_directory, redirect, url_for, flash
import os
import json
from bs4 import BeautifulSoup
from werkzeug.utils import secure_filename
# BLUEPRINTS
from blueprints.tts_blueprint import tts_bp
# END BLUEPRINTS
# CUSTOM MODULES
from preprocessors import TextIn
from wave_gen import KokoroGenerator, tts_queue
# END CUSTOM MODULES

app = Flask(__name__)

# Set upload folder and ensure it exists
UPLOAD_FOLDER = 'uploads'
META_FOLDER = 'metadata'
PROCESSED_FOLDER = 'clean_text'
AUDIO_FOLDER = 'audio'
TXT_DONE_FOLDER = 'txt_done'
PROD_FOLDER = 'production_wav'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(META_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(TXT_DONE_FOLDER, exist_ok=True)
os.makedirs(PROD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
app.config['META_FOLDER'] = META_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER
app.config['TXT_DONE_FOLDER'] = TXT_DONE_FOLDER
app.config['PROD_FOLDER'] = PROD_FOLDER

app.secret_key = os.environ.get('FLASK_SECRET_KEY')

app.register_blueprint(tts_bp)
if not app.secret_key:
    print ("Key not set. Using dummy value for testing")
    app.secret_key = "testing"

@app.route('/', methods=['GET', 'POST'])
def welcome():
    voices = {
        "af_bella": "American F. Bella",
        "af_heart": "American F. Heart",
        "af_nicole": "American F. Nicole",
        "bf_emma": "British F. Emma",
        "am_michael":"American M. Michael",
        "am_fenrir":"American M. Fenrir"
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

# Route to display available items in the clean_text directory
@app.route('/metadata', methods=['GET'])
def available_metadata():
    files = os.listdir(META_FOLDER)  # List files in the clean_text directory
    files_with_index = list(enumerate(files))  # Create a list of (index, file) tuples
    return render_template('metadata_viewer.html', title='Metadata Inventory', files=files_with_index)
    
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