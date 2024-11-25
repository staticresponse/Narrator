import whisper
import re
from fuzzywuzzy import fuzz
from newspaper import Article
import noisereduce
import os
import torch, gc
import torchaudio
from pedalboard import Pedalboard, Compressor, Gain, NoiseGate, LowShelfFilter
from pedalboard.io import AudioFile
from pydub import AudioSegment
from pydub.silence import split_on_silence
from nltk.tokenize import sent_tokenize
import requests

from TTS.api import TTS
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts
from TTS.utils.generic_utils import get_user_data_dir

class BaseTTS:
    def __init__(self, input_file: str, title: str, author: str, engine: str, minratio: str, model_name: str):
        """
        Initializes the BaseTTS class with the given input file, title, and author.

        :param input_file: Path to the input .txt file.
        :param title: Title of the text content.
        :param author: Author of the text content.
        :raises ValueError: If the input_file is not a .txt file.
        """
        if not input_file.lower().endswith('.txt'):
            raise ValueError("input_file must be a .txt file.")
        if not os.path.isfile(input_file):
            raise FileNotFoundError(f"The file {input_file} does not exist.")
        
        self.input_file = input_file
        self.title = title
        self.author = author
        self.engine = engine
        self.minratio = minratio
        if model_name == 'tts_models/en/vctk/vits':
            self.xtts_model = self.tts_dir + "/tts_models--multilingual--multi-dataset--xtts_v2"
        if torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
    def read_content(self) -> str:
        """
        Reads the content of the input .txt file.

        :return: The content of the file as a string.
        """
        with open(self.input_file, 'r', encoding='utf-8') as file:
            return file.read()
    
    def display_metadata(self) -> str:
        """
        Returns a string representation of the title and author.

        :return: Metadata string for the content.
        """
        return f"Title: {self.title}\nAuthor: {self.author}"
    def read_chapter(self, chapter_file, voice_samples, openai, speaker, bitrate=None):
        """
        Reads a chapter from a text file and generates audio using the specified TTS engine.
        The final output will be saved as a single .wav file.

        Args:
            chapter_file (str): Path to the chapter text file.
            voice_samples (str): Comma-separated paths to voice sample files (for xtts).
            engine (str): TTS engine ('xtts', 'openai', or other supported TTS models).
            openai (str): OpenAI API key (if using OpenAI TTS).
            model_name (str): Name of the TTS model.
            speaker (str): Speaker name or ID for multi-speaker models.
            bitrate (str, optional): Bitrate for the output audio file (ignored for .wav files).
        """
        self.model_name = model_name
        self.openai = openai

        # Set up voice configuration
        if engine == 'xtts':
            self.voice_samples = [os.path.abspath(f) for f in voice_samples.split(",")]
            voice_name = "-" + re.split('-|\d+|\.', os.path.basename(self.voice_samples[0]))[0]
        elif engine == 'openai':
            if speaker == 'p335':
                speaker = 'onyx'
            voice_name = "-" + speaker
        else:
            voice_name = "-" + speaker

        # Define the output filename
        self.output_filename = os.path.splitext(chapter_file)[0] + voice_name + ".wav"
        print("Saving to " + self.output_filename)

        # Load the chapter content
        with open(chapter_file, 'r', encoding='utf-8') as f:
            chapter_content = f.read()

        sentences = sent_tokenize(chapter_content)
        sentence_groups = list(self.combine_sentences(sentences))
        total_chars = sum(len(sentence) for sentence in sentences)
        print("Total characters: " + str(total_chars))

        # Initialize the TTS engine
        if engine == "xtts":
            print("Loading model: " + self.xtts_model)
            config = XttsConfig()
            config.load_json(self.xtts_model + "/config.json")
            self.model = Xtts.init_from_config(config)
            self.model.load_checkpoint(config, checkpoint_dir=self.xtts_model, use_deepspeed=False)
            self.model.cuda()
            print("Computing speaker latents...")
            self.gpt_cond_latent, self.speaker_embedding = self.model.get_conditioning_latents(audio_path=self.voice_samples)
        elif engine == "openai":
            while True:
                openai_sdcost = (total_chars / 1000) * 0.015
                print("OpenAI TTS SD Cost: $" + str(openai_sdcost))
                user_input = input("This will not be free, continue? (y/n): ")
                if user_input.lower() in ['y', 'n']:
                    if user_input.lower() == 'n':
                        sys.exit()
                    else:
                        print("Continuing...")
                        break
            client = OpenAI(api_key=self.openai)
        else:
            print("Engine is TTS, model is " + model_name)
            self.tts = TTS(model_name).to(self.device)

        # Process sentences and generate audio
        tempfiles = []
        for x, sentence_group in enumerate(tqdm(sentence_groups)):
            tempwav = f"temp{x}.wav"
            if os.path.isfile(tempwav):
                print(f"{tempwav} exists, skipping")
            else:
                retries = 3
                while retries > 0:
                    try:
                        if engine == "xtts":
                            self.read_chunk_xtts(sentence_group, tempwav)
                        elif engine == "openai":
                            response = client.audio.speech.create(model="tts-1", voice=speaker, input=sentence_group)
                            response.stream_to_file(tempwav)
                        else:
                            self.tts.tts_to_file(text=sentence_group, file_path=tempwav)
                        break
                    except Exception as e:
                        retries -= 1
                        print(f"Error: {str(e)} ... Retrying ({retries} retries left)")
                tempfiles.append(tempwav)

        # Combine audio files into a single .wav output
        concatenated = sum(AudioSegment.from_file(f) for f in tempfiles)
        concatenated.export(self.output_filename, format="wav")

        # Clean up temporary files
        for f in tempfiles:
            os.remove(f)

        print(f"{self.output_filename} complete")


# Example usage
if __name__ == "__main__":
    try:
        tts = BaseTTS("example.txt", "Sample Title", "Sample Author")
        print(tts.display_metadata())
        print(tts.read_content())
    except (ValueError, FileNotFoundError) as e:
        print(e)
