from tts import TTSGenerator
import re
import os
import torch
import logging
from TTS.api import TTS
from nltk.tokenize import PunktSentenceTokenizer


logger = logging.getLogger(__name__)

class ScreenplayTTS(TTSGenerator):
    def generate_vits(self, output_file):
        """
        Generate a WAV file using the VITS model with multiple speakers.
        """
        logger.info("VITS Generation with Multiple Speakers")
        
        with open(self.file_path, "r", encoding="utf-8") as file:
            text = file.read()
        
        tokenizer = PunktSentenceTokenizer()
        sentences = tokenizer.tokenize(text)
        sentences = [s for s in sentences if any(c.isalnum() for c in s)]
        
        sentence_groups = self.extract_speaker_segments(sentences)
        
        chapter_job_queue = []
        tempfiles = []
        sentene_job_queue = []
        
        self.tts = TTS(self.config['model_name'])
        
        for idx, (speaker, segment) in enumerate(sentence_groups):
            tempwav = f"temp_{idx}.wav"
            sentene_job_queue.append((segment, tempwav, speaker))
            tempfiles.append(tempwav)
        
        chapter_job_queue.append({
            'config': self.config,
            'tempfiles': tempfiles,
            'sentene_job_queue': sentene_job_queue,
            'output_file': output_file
        })
        
        logger.info("Initiating Multi-Speaker TTS Job")
        for chapter in chapter_job_queue:
            self.process_book_chapter(chapter)
    
    def extract_speaker_segments(self, sentences):
        """
        Parses the text and associates speaker IDs with each sentence.
        """
        segments = []
        current_speaker = "p364"
        
        for sentence in sentences:
            match = re.match(r"%([^%]+)%\s*(.*)", sentence)
            if match:
                current_speaker, sentence = match.groups()
            segments.append((current_speaker, sentence))
        
        return segments
    
    def process_book_chapter(self, dat):
        logger.info(f"Processing chapter for output file: {dat['output_file']}")
        tts_engine = TTS(dat['config']['model_name'])
        
        for text, file_name, speaker in dat['sentene_job_queue']:
            retries = 2
            while retries > 0:
                try:
                    with torch.no_grad():
                        tts_engine.tts_to_file(text=text, speaker=speaker, file_path=file_name)
                    break
                except Exception as e:
                    retries -= 1
                    if retries == 0:
                        logger.error(f"Failed to process text for {speaker}: {e}")
                    else:
                        logger.info(f"Retrying text synthesis for {file_name}")
        
        self.join_temp_files_to_chapter(dat['tempfiles'], dat['output_file'])
        logger.info(f"Done processing chapter for {dat['output_file']}")
