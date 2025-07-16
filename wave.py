import os
import wave
import json
import logging
from datetime import datetime
from typing import Dict, Any
from mutagen.wave import WAVE
import spaces

from kokoro import KModel, KPipeline
#import misaki   #Just in case we need custom phonemes at a later date
import gradio as gr
import random
import torch



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
            model['sentance_chunk_length'] == 1000 #default to 1000 chars if not specified
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
            text = file.read()
            return text

    def combine_sentences(self, sentences, length=1000):
        for sentence in sentences:
            yield sentence

    def sent_tokenizer(self):
        '''
            If the TTS generator wants a list of sentences
        '''
        text = self.extract_text()
        sentence_queue = []
        tokenizer = PunktSentenceTokenizer()
        sentences = tokenizer.tokenize(text)
        sentences = [s for s in sentences if any(c.isalnum() for c in s)]
        sentence_groups = list(self.combine_sentences(sentences, model["sentence_chunk_length"]))
        for x in range(len(sentence_groups)):
            if len(sentence_groups[x]) == 0:
                continue #skip if empty
            if not any(char.isalnum() for char in sentence_groups[x]):
                continue #skip if no chars or nums
            tempwav = temp+"_"+str(x)+".wav" # temp wav for concatenator later
            sentence_queue.append((sentence_groups[x],tempwav))
        return sentence_queue #To be used by TTS Generation


    def apply_metadata(self, chapter_number: int):
        """
        Apply metadata to the WAV file.
        """
        try:
            audio = WAVE(self.file_path)
            audio["INAM"] = self.title
            audio["IPRD"] = self.title
            audio["IART"] = self.author
            audio["IGNR"] = self.subject
            audio["ITRK"] = str(chapter_number)
            audio["ICRD"] = self.creation_date
            logger.debug(
                f"Applying metadata to {self.file_path} -> "
                f"INAM={self.title}, IPRD={self.title}, IART={self.author}, "
                f"IGNR={self.subject}, ITRK={chapter_number}, ICRD={self.creation_date}"
            )
            audio.save()
            logger.info(f"Metadata applied to {self.file_path}")
        except Exception as e:
            logger.error(f"Error applying metadata to {self.file_path}: {e}")

    def combine_temp_wavs(self, output_name: str, directory: str = ".", prefix: str = "temp_"):
        """
        Combine temp_n.wav files sequentially into a single WAV file and update self.file_path.
        """
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

        except Exception as

class KokoroGenerator(WAVGenerator):
    '''
    'bf_emma',
    'bf_isabella',      
    'bf_alice',
    'bf_lily',
    '🇬🇧 🚹 George': 'bm_george',
    '🇬🇧 🚹 Fable': 'bm_fable',
    '🇬🇧 🚹 Lewis': 'bm_lewis',
    '🇬🇧 🚹 Daniel': 'bm_daniel',
    '''
    def generate_wav(self):
        pipeline = KPipeline(lang_code='a')
        generator = pipeline(text=sent_tokenizer(),voice='bm_lewis',speed=1,split_pattern=r'\n+')
        for i, (gs,ps,audio) in enumerate(generator):
            logger.info(f"index: {i}, text: {gs}, phonemes: {ps}")
            sf.write(f'temp{i}.wav',audio,24000)
    #combine_tem_wavs()#combine the temp wavs created above
        

