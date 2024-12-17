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
from nltk.tokenize import sent_tokenize
from pydub import AudioSegment
from pydub.silence import split_on_silence



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
        self.debug = False
        self.speaker_id = speaker_id
        self.device = "cpu" # overwrite with cuda if possible, else stay the same
        # Default model name
        default_model = "tts_models/en/ljspeech/glow-tts"

        # Use the provided model name or default if not provided
        self.model = model if model else default_model
        if (
            torch.cuda.is_available()
            and torch.cuda.get_device_properties(0).total_memory > 3500000000
        ):
            print("Using GPU")
            print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory}")
            self.device = "cuda"
        else:
            print("Not enough VRAM on GPU or CUDA not found. Using CPU") # purely for debug
            self.device = "cpu"

    def generate_wav(self):
        """
        Generate a WAV file from the text in the specified file.
        """
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}") # should never be triggered via flask. Here for unit tests only

        output_file = os.path.splitext(self.file_path)[0] + ".wav"


        if self.model == "tts_models/en/vctk/vits":
            self.generate_vits(output_file)
        else:
            self.generate_generic_tts(output_file)

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
        print(f"Saving to {output_file}")
        sentance_chunk_length = 1000
        files = []
        position = 0
        start_time = time.time()

        chapter_job_que = []
        tempfiles = []
        config = {
            'speaker': self.speaker,
            'language': self.language,
            'model_name': 'tts_models/en/vctk/vits',
            'debug': self.debug,
            'device': self.device,
            'minratio': 0,
            'engine_cl': None
        }
        # initialize the tts engine
        if 'debug' not in config:
            self.debug = False
        self.tts =  TTS(self.config['model_name']).to(self.device)

        sentences = sent_tokenize(text)
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
            sentene_job_que.append((sentence_groups[x], tempwav))
            tempfiles.append(tempwav)
        chapter_job_que.append(({'config': config, 'tempfiles': tempfiles, 'sentene_job_que': sentene_job_que, 'outputwav': outputwav}))

        print("initiating TTS Job")
        if self.device == 'cuda':
            map_result = list(map(process_book_chapter, chapter_job_que))
        else:
            pool = mp.Pool(processes=self.threads)
            pool.map(process_book_chapter, chapter_job_que)


    def generate_generic_tts(self, output_file):
        """
        Generate a WAV file using a generic TTS model.
        """
        tts = TTS(self.model)
        with open(self.file_path, "r", encoding="utf-8") as file:
            text = file.read()
        tts.tts_to_file(text=text, file_path=output_file)


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

def join_temp_files_to_chapter(tempfiles, outputwav):
    tempwavfiles = [AudioSegment.from_file(f"{f}") for f in tempfiles]
    concatenated = sum(tempwavfiles)
    # remove silence, then export to wav
    #print(f"Replacing silences longer than 2 seconds with 2 seconds of silence ({outputwav})")
    one_sec_silence = AudioSegment.silent(duration=2000)
    two_sec_silence = AudioSegment.silent(duration=3000)
    # This AudioSegment is dedicated for each file.
    audio_modified = AudioSegment.empty()
    # Split audio into chunks where detected silence is longer than 2 second
    chunks = split_on_silence(
        concatenated, min_silence_len=2000, silence_thresh=-50
    )
    # Iterate through each chunk
    for chunkindex, chunk in enumerate(chunks):
        audio_modified += chunk
        audio_modified += one_sec_silence
    # add extra 2sec silence at the end of each part/chapter
    audio_modified += two_sec_silence
    # Write modified audio to the final audio segment
    audio_modified.export(outputwav, format="wav")
    for f in tempfiles:
        os.remove(f)

def process_book_chapter(dat):
    print("initiating chapter: ", dat['chapter'])
    tts_engine = dat['config']['engine_cl'](dat['config'])
    for text, file_name in dat['sentene_job_que']:
        tts_engine.proccess_text_retry(text, file_name)
    join_temp_files_to_chapter(dat['tempfiles'], dat['outputwav'])
    print("done chapter: ", dat['chapter'])
    return dat['outputwav']

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
