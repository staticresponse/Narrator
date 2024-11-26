from TTS.api import TTS
from pydub import AudioSegment
from mutagen.wave import WAVE
from mutagen.id3 import ID3, TIT2, TPE1
import os

class TTSGenerator:
    def __init__(self):
        self.tts = TTS(model_name="tts_models/en/ljspeech/glow-tts")

    def generate_wav(self, file_path, author, title):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as file:
            text = file.read()


        output_file = os.path.splitext(file_path)[0] + ".wav"
        self.tts.tts_to_file(text=text, file_path=output_file)

        # Add metadata to the wav file
        self.add_metadata(output_file, author, title)

        print(f"WAV file generated and saved at: {output_file}")
        return output_file

    @staticmethod
    def add_metadata(wav_path, author, title):
        audio = WAVE(wav_path)

        audio.tags = ID3()
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=author))

        audio.save()
