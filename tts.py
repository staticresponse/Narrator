from TTS.api import TTS
import wave
import os
import taglib

class TTSGenerator:
    def __init__(self, model_name=None):
        """
        Initialize the TTSGenerator with the specified model name.
        If no model name is provided or the model is invalid, it defaults to 'tts_models/en/ljspeech/glow-tts'.

        :param model_name: Optional; The name of the TTS model to use.
        """
        # Default model name
        default_model = "tts_models/en/ljspeech/glow-tts"

        # Use the provided model name or default if not provided
        self.model = model_name if model_name else default_model

        try:
            # Attempt to initialize the TTS with the selected model
            self.tts = TTS(model_name=self.model)
        except Exception as e:
            print(f"Failed to load model '{model_name}', defaulting to '{default_model}'. Error: {e}")
            # Initialize with the default model if the specified model fails
            self.tts = TTS(model_name=default_model)

    def generate_wav(self, file_path, author, title):
        """
        Generate a WAV file from the text in the specified file.

        :param file_path: Path to the text file containing the text to synthesize.
        :param author: The author name for metadata.
        :param title: The title for metadata.
        :return: Path to the generated WAV file.
        """
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
