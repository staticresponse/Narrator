from TTS.api import TTS
import wave
import os
import taglib

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

        self.validate_wav(output_file)
        self.add_metadata(output_file, author, title)

        print(f"WAV file generated and saved at: {output_file}")
        return output_file

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
