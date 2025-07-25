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

from kokoro import KModel, KPipeline


from postprocessor import ProductionWav
# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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
        sentence_queue = []
        tokenizer = PunktSentenceTokenizer()
        sentences = tokenizer.tokenize(text)
        sentences = [s for s in sentences if any(c.isalnum() for c in s)]

        sentence_groups = list(self.combine_sentences(sentences, self.model_config["sentence_chunk_length"]))
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
    def combine_temp_wavs(self, output_name):
        """
        Combines temp_N.wav files into a single output WAV file.
        """
        logger.info("🔧 combine_temp_wavs started...")

        temp_files = []
        i = 0

        while True:
            temp_file = f"temp_{i}.wav"
            if os.path.exists(temp_file):
                logger.info(f"📁 Found: {temp_file}")
                temp_files.append(temp_file)
                i += 1
            else:
                logger.info(f"⛔ Stopped search — {temp_file} not found.")
                break

        if not temp_files:
            logger.error("❌ No temp WAV files found to combine.")
            return

        # Extract base name and keep part number if present
        base_filename = os.path.splitext(os.path.basename(self.file_path))[0]  # e.g., A_Name_in_the_Ashes_part_1
        output_filename = os.path.join("audio", f"{base_filename}.wav")

        try:
            with wave.open(temp_files[0], 'rb') as wf:
                ref_params = wf.getparams()
                frames = [wf.readframes(wf.getnframes())]

            for temp_file in temp_files[1:]:
                with wave.open(temp_file, 'rb') as wf:
                    params = wf.getparams()
                    if (
                        params.nchannels != ref_params.nchannels or
                        params.sampwidth != ref_params.sampwidth or
                        params.framerate != ref_params.framerate or
                        params.comptype != ref_params.comptype or
                        params.compname != ref_params.compname
                    ):
                        logger.error(f"❌ Format mismatch in {temp_file}")
                        logger.error(f"Expected format: {ref_params}")
                        logger.error(f"Found format:    {params}")
                        return

                    frames.append(wf.readframes(wf.getnframes()))

            # Ensure output folder exists
            os.makedirs(os.path.dirname(output_filename), exist_ok=True)

            with wave.open(output_filename, 'wb') as wf:
                wf.setparams(ref_params)
                for f in frames:
                    wf.writeframes(f)

            logger.info(f"✅ Combined WAV saved as: {output_filename}")

            # 🔊 Conditionally apply intro/outro overlay
            if self.config.get("intro"):
                try:
                    logger.info("🎧 Intro found — applying intro/outro overlays...")
                    ProductionWav(wav_path=output_filename, config=self.config)
                    logger.info("✅ Overlays applied successfully.")
                except Exception as e:
                    logger.error(f"❌ Failed to apply overlays: {e}")
            else:
                logger.info("⚠️ No intro specified in config — skipping overlays.")
                
            for f in temp_files:
                os.remove(f)

        except Exception as e:
            logger.error(f"❌ Failed to combine WAV files: {e}")
            raise e

class KokoroGenerator(WAVGenerator):
    def generate_wav(self):
        import time

        MAX_RETRIES = 3
        RETRY_DELAY = 2  # seconds
        pipeline = KPipeline(lang_code='a')
        chunks = self.sent_tokenizer()
        expected_count = len(chunks)
        logger.info(f"🧠 Tokenized into {expected_count} chunks.")

        for idx, text in enumerate(chunks):
            temp_filename = f"temp_{idx}.wav"
            if os.path.exists(temp_filename):
                logger.info(f"⏩ Skipping {temp_filename}, already exists.")
                continue

            retry_count = 0
            while retry_count < MAX_RETRIES:
                try:
                    logger.info(f"🎙️ Attempting to generate chunk {idx} (try {retry_count + 1})")
                    generator = pipeline(
                        text=[text],
                        voice=self.model_config.get("name", "bf_emma"),
                        speed=1,
                        split_pattern=r'\n+'
                    )

                    result = next(generator, None)
                    if result is None:
                        raise ValueError("Generator returned None. Possible Kokoro failure.")

                    gs, ps, audio = result
                    sf.write(temp_filename, audio, 24000, format='WAV', subtype='PCM_16')
                    logger.info(f"✅ Successfully wrote {temp_filename}")
                    break  # success, exit retry loop

                except Exception as e:
                    logger.warning(f"⚠️ Chunk {idx} generation failed on attempt {retry_count + 1}: {e}")
                    retry_count += 1
                    time.sleep(RETRY_DELAY)

            if not os.path.exists(temp_filename):
                logger.error(f"❌ Failed to generate chunk {idx} after {MAX_RETRIES} retries.")
                raise RuntimeError(f"Aborting: chunk {idx} could not be generated.")

        # ✅ Confirm all temp files exist before combining
        missing_files = [f"temp_{i}.wav" for i in range(expected_count) if not os.path.exists(f"temp_{i}.wav")]
        if missing_files:
            logger.error("❌ Some temp WAV files are still missing after retries:")
            for f in missing_files:
                logger.error(f" - {f}")
            raise RuntimeError("TTS generation incomplete. Cannot proceed with combining.")

        self.combine_temp_wavs(output_name=self.title.replace(" ", "_"))


        #self.apply_metadata(chapter_number=1)


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