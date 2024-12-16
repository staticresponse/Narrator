import wave
import os
import taglib
from TTS.api import TTS
from queue import Queue
from threading import Thread
import shutil


class TTSGenerator:
    def __init__(self, file_path, author, title, model=None, speaker_id=None):
        """
        Initialize the TTSGenerator instance with file details, TTS model, and optional speaker ID.

        :param file_path: Path to the text file containing the text to synthesize.
        :param author: The author name for metadata.
        :param title: The title for metadata.
        :param model: Optional TTS model name.
        :param speaker_id: Optional speaker ID (only relevant for specific models).
        """
        self.file_path = file_path
        self.author = author
        self.title = title
        self.speaker_id = speaker_id

        # Default model name
        default_model = "tts_models/en/ljspeech/glow-tts"

        # Use the provided model name or default if not provided
        self.model = model if model else default_model

        try:
            # Attempt to initialize the TTS with the selected model
            self.tts = TTS(model_name=self.model)
        except Exception as e:
            print(f"Failed to load model '{model}', defaulting to '{default_model}'. Error: {e}")
            self.tts = TTS(model_name=default_model)

    def generate_wav(self):
        """
        Generate a WAV file from the text in the specified file.
        """
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}") # should never be triggered via flask. Here for unit tests only

        output_file = os.path.splitext(self.file_path)[0] + ".wav"


        if self.model == "tts_models/en/vctk/vits":
            self.generate_vits(text, output_file)
        else:
            self.generate_generic_tts(text, output_file)

        self.validate_wav(output_file)
        self.add_metadata(output_file, self.author, self.title)
        print(f"WAV file generated and saved at: {output_file}")

        self.move_processed_file()

    def generate_vits(self, output_file):
        """
        Generate a WAV file using the VITS model with speaker_id.
        """
        with open(self.file_path, "r", encoding="utf-8") as file:
            text = file.read()
        if self.speaker_id is None:
            raise ValueError("speaker_id must be provided for VITS model.")
        self.tts.tts_to_file(text=text, speaker_id=self.speaker_id, file_path=output_file)

    def generate_generic_tts(self, output_file):
        """
        Generate a WAV file using a generic TTS model.
        """
        with open(self.file_path, "r", encoding="utf-8") as file:
            text = file.read()
        self.tts.tts_to_file(text=text, file_path=output_file)


    def move_processed_file(self):
        """
        Move the processed text file and its generated audio file to their respective directories.
        """
        # Directories for processed files
        txt_done_dir = "txt_done"
        audio_done_dir = "audio"
        os.makedirs(txt_done_dir, exist_ok=True)
        os.makedirs(audio_done_dir, exist_ok=True)

        # Destination paths
        txt_destination_path = os.path.join(txt_done_dir, os.path.basename(self.file_path))
        audio_file = os.path.splitext(self.file_path)[0] + ".wav"
        audio_destination_path = os.path.join(audio_done_dir, os.path.basename(audio_file))

        # Move text file
        if os.path.exists(self.file_path):
            try:
                shutil.move(self.file_path, txt_destination_path)
                print(f"Text file moved to: {txt_destination_path}")
            except Exception as e:
                print(f"Error while moving text file '{self.file_path}': {e}")

        # Move audio file
        if os.path.exists(audio_file):
            try:
                shutil.move(audio_file, audio_destination_path)
                print(f"Audio file moved to: {audio_destination_path}")
            except Exception as e:
                print(f"Error while moving audio file '{audio_file}': {e}")

    @staticmethod
    def validate_wav(wav_path):
        try:
            with wave.open(wav_path, 'rb') as wf:
                print(f"WAV file validation successful: {wav_path}")
        except wave.Error as e:
            raise ValueError(f"Invalid WAV file generated: {e}")

    @staticmethod
    def add_metadata(wav_path, author, title):
        audio = taglib.File(wav_path)
        audio.tags["TITLE"] = [title]
        audio.tags["ARTIST"] = [author]
        audio.save()


def process_queue(task_queue):
    while True:
        tts_task = task_queue.get()
        try:
            tts_task.generate_wav()
        except Exception as e:
            print(f"Error processing task for file '{tts_task.file_path}': {e}")
        finally:
            task_queue.task_done()


# Initialize the task queue
tts_queue = Queue()

# Start the worker thread to process tasks from the queue
worker_thread = Thread(target=process_queue, args=(tts_queue,))
worker_thread.daemon = True
worker_thread.start()
