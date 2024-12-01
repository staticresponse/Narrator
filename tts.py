import wave
import os
import taglib
from TTS.api import TTS
from queue import Queue
from threading import Thread


class TTSGenerator:
    def __init__(self, file_path, author, title, model=None):
        """
        Initialize the TTSGenerator instance with file details and TTS model.

        :param file_path: Path to the text file containing the text to synthesize.
        :param author: The author name for metadata.
        :param title: The title for metadata.
        :param model: Optional TTS model name.
        """
        # File and metadata details
        self.file_path = file_path
        self.author = author
        self.title = title

        # Default model name
        default_model = "tts_models/en/ljspeech/glow-tts"

        # Use the provided model name or default if not provided
        self.model = model if model else default_model

        try:
            # Attempt to initialize the TTS with the selected model
            self.tts = TTS(model_name=self.model)
        except Exception as e:
            print(f"Failed to load model '{model}', defaulting to '{default_model}'. Error: {e}")
            # Initialize with the default model if the specified model fails
            self.tts = TTS(model_name=default_model)

    def generate_wav(self):
        """
        Generate a WAV file from the text in the specified file.
        """
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")

        with open(self.file_path, "r", encoding="utf-8") as file:
            text = file.read()

        output_file = os.path.splitext(self.file_path)[0] + ".wav"
        self.tts.tts_to_file(text=text, file_path=output_file)

        self.validate_wav(output_file)
        self.add_metadata(output_file, self.author, self.title)

        print(f"WAV file generated and saved at: {output_file}")

    @staticmethod
    def validate_wav(wav_path):
        """
        Validate that the generated file is a valid WAV file.

        :param wav_path: Path to the WAV file to validate.
        """
        try:
            with wave.open(wav_path, 'rb') as wf:
                print(f"WAV file validation successful: {wav_path}")
        except wave.Error as e:
            raise ValueError(f"Invalid WAV file generated: {e}")

    @staticmethod
    def add_metadata(wav_path, author, title):
        """
        Add metadata to the WAV file.

        :param wav_path: Path to the WAV file.
        :param author: Author metadata.
        :param title: Title metadata.
        """
        audio = taglib.File(wav_path)
        audio.tags["TITLE"] = [title]
        audio.tags["ARTIST"] = [author]
        audio.save()


def process_queue(task_queue):
    """
    Process TTSGenerator tasks from the queue.

    :param task_queue: Queue containing TTSGenerator objects.
    """
    while True:
        tts_task = task_queue.get()

        try:
            tts_task.generate_wav()
        except Exception as e:
            print(f"Error processing task for file '{tts_task.file_path}': {e}")
        finally:
            # Mark the task as done
            task_queue.task_done()


# Initialize the task queue
tts_queue = Queue()

# Start the worker thread to process tasks from the queue
worker_thread = Thread(target=process_queue, args=(tts_queue,))
worker_thread.daemon = True  # Allow the program to exit even if the thread is running
worker_thread.start()