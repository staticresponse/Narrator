from flask import Blueprint, request, render_template, jsonify, current_app
import os
import logging
from wave_gen import KokoroGenerator, tts_queue

tts_bp = Blueprint("tts", __name__, url_prefix="/tts")

logger = logging.getLogger(__name__)

# Route for TTS form
@tts_bp.route('/form/<filename>', methods=['GET'])
def tts_form(filename):
    processed_folder = current_app.config['PROCESSED_FOLDER']
    if not os.path.exists(os.path.join(processed_folder, filename)):
        return render_template('error.html', title='ERROR', error="File Not Found.")

    models = ['kokoro']  # Replace with actual models
    return render_template('tts_form.html', title='TTS request', filename=filename, models=models)


# Generate single TTS
@tts_bp.route('/generate', methods=['POST'])
def generate_tts():
    processed_folder = current_app.config['PROCESSED_FOLDER']
    audio_folder = current_app.config['AUDIO_FOLDER']

    filename = request.form.get('filename', '').strip()
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    model = request.form.get('model', '').strip()
    subject = request.form.get('subject', '').strip()
    voice = request.form.get('voice', '').strip()

    if not filename or not os.path.exists(os.path.join(processed_folder, filename)):
        return render_template('error.html', title='ERROR', error="Invalid or missing file.")
    if not title or not author:
        return render_template('error.html', title='ERROR', error="Title and author are required.")

    filepath = os.path.join(processed_folder, filename)

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
        tts_generator = KokoroGenerator(config)
        tts_generator.generate_wav()

        output_file = os.path.splitext(filepath)[0] + ".wav"
        final_path = os.path.join(audio_folder, os.path.basename(output_file))
        os.makedirs(audio_folder, exist_ok=True)
        os.rename(output_file, final_path)

        return render_template('success.html', title='SUCCESS', message="TTS audio generated successfully.", file=final_path, model=model)
    except Exception as e:
        return render_template('error.html', title='ERROR', error=str(e))


# Add TTS task to queue
@tts_bp.route('/add-to-queue', methods=['POST'])
def add_to_queue():
    processed_folder = current_app.config['PROCESSED_FOLDER']

    filename = request.form.get('filename', '').strip()
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    model = request.form.get('model', '').strip()
    subject = request.form.get('subject', '').strip()
    voice = request.form.get('voice', '').strip()

    if not filename:
        return render_template('error.html', title='ERROR', error="Filename is required.")

    file_path = os.path.join(processed_folder, filename)
    if not os.path.exists(file_path):
        return render_template('error.html', title='ERROR', error=f"File not found in processed directory: {file_path}")

    try:
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

        tts_task = KokoroGenerator(config)
        tts_queue.put(tts_task)

        return render_template('success.html', title='SUCCESS', message="Task added to queue.")
    except Exception as e:
        return render_template('error.html', title='ERROR', error=str(e))


# TTS all form
@tts_bp.route('/all-form', methods=['GET'])
def tts_all_form():
    available_models = ['kokoro']
    return render_template('tts_all_form.html', models=available_models)


# Generate TTS for all files
@tts_bp.route('/generate-all', methods=['POST'])
def generate_tts_all():
    processed_folder = current_app.config['PROCESSED_FOLDER']

    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    model = request.form.get('model', '').strip()
    subject = request.form.get('subject', '').strip()
    voice = request.form.get('voice', '').strip()

    if not title or not author or not model:
        return render_template('error.html', title='ERROR', error="All fields are required.")

    files = os.listdir(processed_folder)
    queued_files = []

    for filename in files:
        file_path = os.path.join(processed_folder, filename)
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


# Current queue
@tts_bp.route('/current-queue', methods=['GET'])
def current_queue():
    queue_items = []
    with tts_queue.mutex:
        for task in list(tts_queue.queue):
            queue_items.append({
                'file_path': task.file_path,
                'author': task.author,
                'title': task.title,
                'model': task.model
            })

    return render_template('tts_queue.html', title="Current TTS Queue", queue_items=queue_items)
