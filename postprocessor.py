import logging
import os
from pydub import AudioSegment
import wave

# Configure logging for the module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# You can configure this handler as needed (console, file, etc.)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class ProductionWav:
    def __init__(self, wav_path, config):
        self.wav_path = wav_path
        self.intro_path = config.get("intro")
        self.outro_path = config.get("outro")
        self.volume_db = self._parse_volume(config.get("overlay_volume", -5))

        self.base = AudioSegment.from_wav(self.wav_path)
        logger.debug(f"Loaded base audio length: {len(self.base) / 1000:.2f} seconds")
        self.apply_intro()
        logger.debug(f"After apply_intro, length: {len(self.base) / 1000:.2f} seconds")
        self.append_silence()
        logger.debug(f"After append_silence, length: {len(self.base) / 1000:.2f} seconds")
        self.apply_outro()
        logger.debug(f"After apply_outro, length: {len(self.base) / 1000:.2f} seconds")

        self.export_final()

    def apply_intro(self):
        if self.intro_path and os.path.exists(self.intro_path):
            intro = AudioSegment.from_file(self.intro_path).apply_gain(self.volume_db)
            delayed_voice = AudioSegment.silent(duration=12000) + self.base
            logger.info(f"Intro length: {len(intro) / 1000:.2f} seconds")
            logger.info(f"Delayed voice length: {len(delayed_voice) / 1000:.2f} seconds")

            max_len = max(len(intro), len(delayed_voice))
            output = AudioSegment.silent(duration=max_len)

            output = output.overlay(delayed_voice, position=0)
            output = output.overlay(intro, position=0)

            self.base = output
            logger.info(f"After intro overlay, length: {len(self.base) / 1000:.2f} seconds")
        else:
            logger.info("Skipping intro")

    def _parse_volume(self, vol):
        try:
            return float(vol)
        except (TypeError, ValueError) as e:
            logger.warning(f"⚠️ Invalid overlay_volume '{vol}', falling back to -5 dB")
            return -5.0




    def append_silence(self):
        self.base += AudioSegment.silent(duration=5000)
        logger.info("✅ Appended 5 seconds of silence.")

    def apply_outro(self):
        if self.outro_path and os.path.exists(self.outro_path):
            try:
                outro = AudioSegment.from_file(self.outro_path).apply_gain(self.volume_db)
                fade_duration = min(2000, len(outro))
                outro = outro.fade_in(fade_duration)

                # Ensure base is long enough (assumes silence already added)
                required_length = len(outro) + 500
                if len(self.base) < required_length:
                    self.base += AudioSegment.silent(duration=required_length - len(self.base))

                insert_point = len(self.base) - len(outro) - 500
                output = AudioSegment.silent(duration=len(self.base))
                output = output.overlay(self.base, position=0)
                output = output.overlay(outro, position=insert_point)

                self.base = output
                logger.info(f"🎧 Outro overlay with fade-in applied. Starts at {insert_point} ms, ends at {insert_point + len(outro)} ms.")
            except Exception as e:
                logger.error(f"❌ Error applying outro from '{self.outro_path}': {e}")
        else:
            logger.info("ℹ️ Skipping outro: Not provided or file not found.")






    def export_final(self):
        output_path = self._get_output_path()
        try:
            # Set to standard uncompressed 16-bit stereo at 44.1kHz
            raw = self.base.set_frame_rate(44100).set_channels(2).set_sample_width(2)

            with wave.open(output_path, 'wb') as wf:
                wf.setnchannels(raw.channels)
                wf.setsampwidth(raw.sample_width)
                wf.setframerate(raw.frame_rate)
                wf.writeframes(raw._data)

            logger.info(f"✅ Final WAV saved to: {output_path} (length: {len(raw) / 1000:.2f} seconds)")
        except Exception as e:
            logger.error(f"❌ Failed to export WAV using wave module: {e}")
            raise

    def _get_output_path(self):
        base, _ = os.path.splitext(self.wav_path)
        return f"{base}_final.wav"
