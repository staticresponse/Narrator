import wave
import os
import taglib
from TTS.api import TTS
from queue import Queue
from threading import Thread
import shutil
import torch
import time
import multiprocessing as mp
from pydub import AudioSegment
from pydub.silence import split_on_silence, detect_silence
from nltk.tokenize import PunktSentenceTokenizer
import logging #logging
import random

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class TTSGenerator:
    def __init__(self, file_path, author, title, model=None, speaker_id=None, enable_bkg_music=False, bkg_music_file=None, bkg_music_volume=50, min_gap=2000, max_gap=5000):
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
        self.debug = False
        self.speaker_id = speaker_id
        self.device = "cpu" # overwrite with cuda if possible, else stay the same
        self.enable_bkg_music = enable_bkg_music
        self.bkg_music_file = bkg_music_file
        self.bkg_music_volume = bkg_music_volume
        self.min_gap = min_gap
        self.max_gap = max_gap
        # Default model name
        default_model = "tts_models/en/ljspeech/glow-tts"
        if self.bkg_music_file != None:
            self.enable_bkg_music = True

        # Use the provided model name or default if not provided
        self.model = model if model else default_model
        if (
            torch.cuda.is_available()
            and torch.cuda.get_device_properties(0).total_memory > 3500000000
        ):
            logger.info("Using GPU")
            logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory}")
            self.device = "cuda"
        else:
            logger.info("Not enough VRAM on GPU or CUDA not found. Using CPU") # purely for debug
            self.device = "cpu"
        
        self.config = {
            'speaker': self.speaker_id,
            'model_name': self.model,
            'debug': self.debug,
            'device': self.device,
            'minratio': 0,
            'engine_cl': None
        }

    def generate_wav(self):
        """
        Generate a WAV file from the text in the specified file.
        """
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}") # should never be triggered via flask. Here for unit tests only

        output_file = os.path.splitext(self.file_path)[0] + ".wav"

        logger.info(f"Generating WAV file for {self.file_path}")

        if self.model == "tts_models/en/vctk/vits":
            self.generate_vits(output_file)
        else:
            self.generate_generic_tts(output_file)

        if self.enable_bkg_music:
            self.add_background_music(output_file)

        self.validate_wav(output_file)
        self.add_metadata(output_file, self.author, self.title)
        logger.info(f"WAV file generated and saved at: {output_file}")

        self.move_processed_file()

    def generate_vits(self, output_file):
        """
        Generate a WAV file using the VITS model with speaker_id.
        """
        logger.info("VITS Generation")
        with open(self.file_path, "r", encoding="utf-8") as file:
            text = file.read()
        if self.speaker_id is None:
            self.config['speaker'] = 'p364' # Have a default override just in case
            logger.info("Speaker not set, defaulting to p364")
        logger.info(f"Saving to {output_file}")
        sentance_chunk_length = 1000
        files = []
        position = 0
        start_time = time.time()
        sentene_job_queue = []
        chapter_job_queue = []
        tempfiles = []
        # initialize the tts engine
        self.tts =  TTS(self.config['model_name'])
        tokenizer = PunktSentenceTokenizer()        
        sentences = tokenizer.tokenize(text)
        sentences = [s for s in sentences if any(c.isalnum() for c in s)]
        sentence_groups = list(self.combine_sentences(sentences, sentance_chunk_length))
        for x in range(len(sentence_groups)):
            #skip if item is empty
            if len(sentence_groups[x]) == 0:
                continue
            #skip if item has no characters or numbers
            if not any(char.isalnum() for char in sentence_groups[x]):
                continue
            retries = 2
            tempwav = "temp"+ "_" + str(x) + ".wav" # temp wavs of each sentence for future chunking
            sentene_job_queue.append((sentence_groups[x], tempwav))
            tempfiles.append(tempwav)
        chapter_job_queue.append(({'config': self.config, 'tempfiles': tempfiles, 'sentene_job_queue': sentene_job_queue, 'output_file': output_file}))

        logger.info("Initiating TTS Job for VITS model")
        for chapter in chapter_job_queue:
            self.process_book_chapter(chapter)

    def combine_sentences(self, sentences, length=1000):
        for sentence in sentences:
            yield sentence

    def generate_generic_tts(self, output_file):
        """
        Generate a WAV file using a generic TTS model.
        """
        tts = TTS(self.model)
        with open(self.file_path, "r", encoding="utf-8") as file:
            text = file.read()
        logger.info(f"Generating WAV file using generic model for {self.file_path}")
        tts.tts_to_file(text=text, file_path=output_file)

    def process_book_chapter(self, dat):
        logger.info(f"Initiating chapter processing for output file: {dat['output_file']}")
        tts_engine = TTS(dat['config']['model_name'])
        
        for text, file_name in dat['sentene_job_queue']:
            retries = 2
            while retries > 0:
                try:
                    # Force PyTorch tensors to detach and move to CPU
                    with torch.no_grad():  # Ensures no autograd context
                        try:
                            if self.model == 'tts_models/en/vctk/vits':
                                tts_engine.tts_to_file(text=text,speaker=self.config['speaker'], file_path=file_name)
                            else:
                                tts_engine.tts_to_file(text=text, file_path=file_name)
                        except Exception as e:
                            logger.error(f"Error generating {file_name}: {e}")
                    break
                except Exception as e:
                    retries -= 1
                    if retries == 0:
                        logger.error(f"Failed to process text: {text}, error: {e}")
                    else:
                        logger.info(f"Retrying text synthesis for: {file_name}")

        self.join_temp_files_to_chapter(dat['tempfiles'], dat['output_file'])
        logger.info(f"Done processing chapter for output file: {dat['output_file']}")
        return dat['output_file']

    def join_temp_files_to_chapter(cls, tempfiles, output_file):
        logger.info(f"Joining temporary WAV files into final chapter: {output_file}")
        tempwavfiles = [AudioSegment.from_file(f"{f}") for f in tempfiles]
        concatenated = sum(tempwavfiles)

        one_sec_silence = AudioSegment.silent(duration=2000)
        two_sec_silence = AudioSegment.silent(duration=3000)

        audio_modified = AudioSegment.empty()
        chunks = split_on_silence(concatenated, min_silence_len=2000, silence_thresh=-50)

        for chunk in chunks:
            audio_modified += chunk
            audio_modified += one_sec_silence

        audio_modified += two_sec_silence
        audio_modified.export(output_file, format="wav")

        for f in tempfiles:
            os.remove(f)
        logger.info(f"Chapter audio file saved at: {output_file}")

    def move_processed_file(self):
        """
        Move the processed text file and its generated audio file to their respective directories.
        """
        txt_done_dir = "txt_done"
        audio_done_dir = "audio"
        os.makedirs(txt_done_dir, exist_ok=True)
        os.makedirs(audio_done_dir, exist_ok=True)

        txt_destination_path = os.path.join(txt_done_dir, os.path.basename(self.file_path))
        audio_file = os.path.splitext(self.file_path)[0] + ".wav"
        audio_destination_path = os.path.join(audio_done_dir, os.path.basename(audio_file))

        if os.path.exists(self.file_path):
            try:
                shutil.move(self.file_path, txt_destination_path)
                logger.info(f"Text file moved to: {txt_destination_path}")
            except Exception as e:
                logger.error(f"Error while moving text file '{self.file_path}': {e}")

        if os.path.exists(audio_file):
            try:
                shutil.move(audio_file, audio_destination_path)
                logger.info(f"Audio file moved to: {audio_destination_path}")
            except Exception as e:
                logger.error(f"Error while moving audio file '{audio_file}': {e}")
    def add_background_music(self, wav_path):
        if not os.path.exists(self.bkg_music_file):
            logger.error(f"Background music file not found: {self.bkg_music_file}")
            return

        logger.info(f"Adding background music from {self.bkg_music_file} to {wav_path}")

        tts_audio = AudioSegment.from_file(wav_path).normalize()
        bkg_music = AudioSegment.from_file(self.bkg_music_file).normalize()

        bkg_music = bkg_music - (20 * (100 - self.bkg_music_volume) / 100)

        playlist = AudioSegment.silent(duration=self.min_gap)
        while len(playlist) < len(tts_audio):
            playlist += bkg_music
            playlist += AudioSegment.silent(duration=random.randint(self.min_gap, self.max_gap))

        playlist = playlist[:len(tts_audio)]
        combined_audio = tts_audio.overlay(playlist)

        combined_audio.export(wav_path, format="wav")
        logger.info(f"Background music added to {wav_path}")


    @staticmethod
    def validate_wav(wav_path):
        try:
            with wave.open(wav_path, 'rb') as wf:
                logger.info(f"WAV file validation successful: {wav_path}")
        except wave.Error as e:
            raise ValueError(f"Invalid WAV file generated: {e}")

    @staticmethod
    def add_metadata(wav_path, author, title):
        audio = taglib.File(wav_path)
        audio.tags["TITLE"] = [title]
        audio.tags["ARTIST"] = [author]
        audio.save()
        logger.info(f"Metadata added to WAV file: {wav_path}")

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
