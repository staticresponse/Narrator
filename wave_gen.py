import os
import wave
import logging
import json
from datetime import datetime
from typing import Dict, Any
from queue import Queue
from threading import Thread
from mutagen.wave import WAVE
from nltk.tokenize import PunktSentenceTokenizer
import soundfile as sf
import contextlib
import re

from kokoro import KModel, KPipeline


from postprocessor import ProductionWav
# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def get_wav_duration(filename):
    with contextlib.closing(wave.open(filename, 'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        return frames / float(rate)
        
class WAVGenerator:
    def __init__(self, config: Dict[str, Any]):
        required_keys = ["filename", "title", "author", "model"]
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required config key: {key}")

        self.file_path = config["filename"]
        self.title = config["title"]
        self.author = config["author"]
        self.model = config["model"]
        self.subject = config.get("subject", "Unknown")
        self.creation_date = datetime.now().strftime("%Y-%m-%d")
        self.config = config

        # Optional model config dict
        self.model_config = {
            "name": config.get("voice", "bf_emma"),  # Default voice
            "sentence_chunk_length": config.get("sentence_chunk_length", 480)
        }
        logger.info(f"🛠️ WAVGenerator config loaded:\n{json.dumps(self.config, indent=2)}")

    def __repr__(self):
        return (
            f"<WAVGenerator(title={self.title!r}, author={self.author!r}, "
            f"model={self.model!r}, file_path={self.file_path!r}, created={self.creation_date!r})>"
        )

    def extract_text(self):
        with open(self.file_path, "r", encoding="utf-8") as file:
            return file.read()

    def combine_sentences(self, sentences, length=480):
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
        tokenizer = PunktSentenceTokenizer()
        sentences = tokenizer.tokenize(text)
        sentences = [s.strip() for s in sentences if any(c.isalnum() for c in s)]

        chapter_pattern = re.compile(r"^chapter\s+\d+", re.IGNORECASE)
        current_chapter = None
        chunk_data = []
        current_chunk = ""

        for sentence in sentences:
            if chapter_pattern.match(sentence.lower()):
                current_chapter = sentence.strip()  # e.g., "Chapter 1"

            # If no chapter yet, label as "Prologue" or something similar
            if not current_chapter:
                current_chapter = "Prologue"

            if len(current_chunk) + len(sentence) + 1 > self.model_config["sentence_chunk_length"]:
                if current_chunk.strip():
                    chunk_data.append({
                        "text": current_chunk.strip(),
                        "filename": f"temp_{len(chunk_data)}.wav",
                        "chapter": current_chapter
                    })
                current_chunk = sentence
            else:
                current_chunk += " " + sentence

        if current_chunk.strip():
            chunk_data.append({
                "text": current_chunk.strip(),
                "filename": f"temp_{len(chunk_data)}.wav",
                "chapter": current_chapter
            })

        return chunk_data


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
    def combine_temp_wavs(self, output_name):
        logger.info("🔧 combine_temp_wavs started...")

        chunk_data = getattr(self, "chunk_data", [])
        chapter_timings = {}
        current_time = 0.0
        temp_files = []
        
        for i, chunk in enumerate(chunk_data):
            temp_file = chunk["filename"]
            if os.path.exists(temp_file):
                duration = get_wav_duration(temp_file)
                chapter = chunk["chapter"]
                if chapter not in chapter_timings:
                    chapter_timings[chapter] = {"starttime": current_time, "endtime": current_time + duration}
                else:
                    chapter_timings[chapter]["endtime"] += duration

                current_time += duration
                temp_files.append(temp_file)
            else:
                logger.error(f"❌ Missing expected chunk file: {temp_file}")

        if not temp_files:
            logger.error("❌ No temp WAV files found to combine.")
            return

        # Combine audio
        output_filename = os.path.join("audio", f"{output_name}.wav")
        try:
            with wave.open(temp_files[0], 'rb') as wf:
                ref_params = wf.getparams()
                frames = [wf.readframes(wf.getnframes())]

            for temp_file in temp_files[1:]:
                with wave.open(temp_file, 'rb') as wf:
                    frames.append(wf.readframes(wf.getnframes()))

            os.makedirs(os.path.dirname(output_filename), exist_ok=True)
            with wave.open(output_filename, 'wb') as wf:
                wf.setparams(ref_params)
                for f in frames:
                    wf.writeframes(f)

            logger.info(f"✅ Combined WAV saved as: {output_filename}")

            # Apply overlays if needed
            if self.config.get("intro"):
                try:
                    logger.info("🎧 Intro found — applying overlays...")
                    ProductionWav(wav_path=output_filename, config=self.config)
                except Exception as e:
                    logger.error(f"❌ Failed to apply overlays: {e}")
            else:
                logger.info("⚠️ No intro specified — skipping overlays.")

            # Clean up temp files
            for f in temp_files:
                os.remove(f)

            # ✅ Update metadata
            self.update_metadata_with_runtime(chapter_timings)

        except Exception as e:
            logger.error(f"❌ Failed to combine WAV files: {e}")
            raise e

    def update_metadata_with_runtime(self, chapter_timings):
        metadata_path = self.file_path.replace(".txt", ".meta")
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            logger.error(f"❌ Could not load metadata file '{metadata_path}': {e}")
            return

        metadata["chapter_runtime"] = []
        for chapter, times in chapter_timings.items():
            metadata["chapter_runtime"].append({
                "chapter": chapter,
                "starttime": round(times["starttime"], 2),
                "endtime": round(times["endtime"], 2)
            })

        try:
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"✅ Updated metadata with chapter_runtime in {metadata_path}")
        except Exception as e:
            logger.error(f"❌ Failed to write updated metadata: {e}")


class KokoroGenerator(WAVGenerator):
    def generate_wav(self):
        import time
        MAX_RETRIES = 3
        RETRY_DELAY = 2
        pipeline = KPipeline(lang_code='a')

        self.chunk_data = self.sent_tokenizer()
        chunks = self.chunk_data
        expected_count = len(chunks)
        logger.info(f"🧠 Tokenized into {expected_count} chunks.")

        for idx, chunk in enumerate(chunks):
            text = chunk["text"]
            temp_filename = chunk["filename"]

            if os.path.exists(temp_filename):
                logger.info(f"⏩ Skipping {temp_filename}, already exists.")
                continue

            retry_count = 0
            while retry_count < MAX_RETRIES:
                try:
                    logger.info(f"🎙️ Generating chunk {idx} (try {retry_count + 1})")
                    generator = pipeline(
                        text=[text],
                        voice=self.model_config.get("name", "bf_emma"),
                        speed=1,
                        split_pattern=r'\n+'
                    )
                    result = next(generator, None)
                    if result is None:
                        raise ValueError("Generator returned None.")

                    _, _, audio = result
                    sf.write(temp_filename, audio, 24000, format='WAV', subtype='PCM_16')
                    logger.info(f"✅ Wrote {temp_filename}")
                    break
                except Exception as e:
                    logger.warning(f"⚠️ Chunk {idx} failed on attempt {retry_count + 1}: {e}")
                    retry_count += 1
                    time.sleep(RETRY_DELAY)

            if not os.path.exists(temp_filename):
                logger.error(f"❌ Failed to generate {temp_filename}")
                raise RuntimeError(f"Chunk {idx} failed")

        missing = [c["filename"] for c in chunks if not os.path.exists(c["filename"])]
        if missing:
            logger.error("❌ Missing chunks after retries: " + ", ".join(missing))
            raise RuntimeError("TTS incomplete")

        basename = os.path.splitext(os.path.basename(self.file_path))[0]
        self.combine_temp_wavs(output_name=basename)



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