import os
import wave
import json
import logging
from datetime import datetime
from typing import Dict, Any
from queue import Queue
from threading import Thread
from mutagen.wave import WAVE
from nltk.tokenize import PunktSentenceTokenizer
import soundfile as sf

from kokoro import KModel, KPipeline
# import misaki  # For custom phoneme support (optional)

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class WAVGenerator:
    def __init__(
        self,
        file_path: str,
        author: str,
        title: str,
        model: Dict[str, Any],
        subject: str = None
    ):
        if "name" not in model:
            raise ValueError("Model config must contain a 'name' field.")
        if "sentence_chunk_length" not in model:
            model["sentence_chunk_length"] = 1000  # default to 1000 chars if not specified

        self.file_path = file_path
        self.author = author
        self.title = title
        self.subject = subject or "Unknown"
        self.model = model
        self.creation_date = datetime.now().strftime("%Y-%m-%d")

    def __repr__(self):
        return (
            f"<WAVGenerator(title={self.title!r}, author={self.author!r}, "
            f"model={self.model.get('name')!r}, file_path={self.file_path!r}, created={self.creation_date!r})>"
        )

    def extract_text(self):
        with open(self.file_path, "r", encoding="utf-8") as file:
            return file.read()

    def combine_sentences(self, sentences, length=5000):
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 > length:
                yield current_chunk.strip()
                current_chunk = sentence
            else:
                current_chunk += " " + sentence
        if current_chunk:
            yield current_chunk.strip()

    def sent_tokenizer(self):
        text = self.extract_text()
        sentence_queue = []
        tokenizer = PunktSentenceTokenizer()
        sentences = tokenizer.tokenize(text)
        sentences = [s for s in sentences if any(c.isalnum() for c in s)]

        sentence_groups = list(self.combine_sentences(sentences, self.model["sentence_chunk_length"]))
        for i, chunk in enumerate(sentence_groups):
            if not chunk.strip():
                continue
            tempwav = f"temp_{i}.wav"
            sentence_queue.append((chunk, tempwav))
        return sentence_groups

    def apply_metadata(self, chapter_number: int):
        try:
            audio = WAVE(self.file_path)
            audio["INAM"] = self.title
            audio["IPRD"] = self.title
            audio["IART"] = self.author
            audio["IGNR"] = self.subject
            audio["ITRK"] = str(chapter_number)
            audio["ICRD"] = self.creation_date
            audio.save()
            logger.info(f"Metadata applied to {self.file_path}")
        except Exception as e:
            logger.error(f"Error applying metadata to {self.file_path}: {e}")

    def combine_temp_wavs(self, output_name: str, directory: str = ".", prefix: str = "temp_"):
        wav_files = [
            f for f in os.listdir(directory)
            if f.startswith(prefix) and f.endswith(".wav") and f[len(prefix):-4].isdigit()
        ]
        sorted_files = sorted(wav_files, key=lambda f: int(f[len(prefix):-4]))

        if not sorted_files:
            logger.warning("No matching WAV files found to combine.")
            return

        output_path = os.path.join(directory, f"{output_name}.wav")

        try:
            with wave.open(os.path.join(directory, sorted_files[0]), 'rb') as first_wav:
                params = first_wav.getparams()
                audio_data = [first_wav.readframes(first_wav.getnframes())]

            for fname in sorted_files[1:]:
                with wave.open(os.path.join(directory, fname), 'rb') as wf:
                    if wf.getparams() != params:
                        raise ValueError(f"File {fname} has different audio parameters.")
                    audio_data.append(wf.readframes(wf.getnframes()))

            with wave.open(output_path, 'wb') as out_wav:
                out_wav.setparams(params)
                for data in audio_data:
                    out_wav.writeframes(data)

            self.file_path = output_path
            logger.info(f"Combined WAV saved to {output_path}")

        except Exception as e:
            logger.error(f"Error combining WAV files: {e}")


class KokoroGenerator(WAVGenerator):
    """
    Voices available (examples):
    - 'bf_emma'
    - 'bf_isabella' (narrator)
    - 'bf_alice'
    - 'bf_lily'
    - 'bm_george'
    - 'bm_fable'
    - 'bm_lewis'
    - 'bm_daniel'
    """
    def generate_wav(self):
        pipeline = KPipeline(lang_code='a')
        chunks = self.sent_tokenizer()
        generator = pipeline(
            text=chunks,
            voice=self.model.get("name", "bf_emma"),
            speed=1,
            split_pattern=r'\n+'
        )

        for i, (gs, ps, audio) in enumerate(generator):
            logger.info(f"index: {i}, text: {gs}, phonemes: {ps}")
            sf.write(f'temp_{i}.wav', audio, 24000)

        self.combine_temp_wavs(output_name=self.title.replace(" ", "_"))
        self.apply_metadata(chapter_number=1)


def process_queue(task_queue):
    while True:
        tts_task = task_queue.get()
        try:
            logger.info(f"Processing task for file: {tts_task.file_path}")
            tts_task.generate_wav()
        except Exception as e:
            logger.error(f"Error processing task for file '{tts_task.file_path}': {e}")
        finally:
            task_queue.task_done()


# Initialize the task queue
tts_queue = Queue()

# Start the worker thread to process tasks from the queue
worker_thread = Thread(target=process_queue, args=(tts_queue,))
worker_thread.daemon = True
worker_thread.start()
