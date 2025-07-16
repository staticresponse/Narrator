import os
import wave
import json
import logging
from datetime import datetime
from typing import Dict, Any
from mutagen.wave import WAVE

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
