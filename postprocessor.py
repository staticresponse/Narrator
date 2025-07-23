import logging
import os
from pydub import AudioSegment

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
        """
        wav_path: path to the original generated WAV file
        config: full JSON config dict; expects:
            - "intro": path to intro file
            - "outro": path to outro file
            - "overlay_volume": volume in dB (can be string or int, default: -5)
        """
        self.wav_path = wav_path
        self.intro_path = config.get("intro")
        self.outro_path = config.get("outro")
        self.volume_db = self._parse_volume(config.get("overlay_volume", -5))

        try:
            self.base = AudioSegment.from_wav(self.wav_path)
        except Exception as e:
            logger.error(f"❌ Failed to load WAV file '{self.wav_path}': {e}")
            raise

        self.apply_intro()
        self.append_silence()
        self.apply_outro()
        self.export_final()

    def _parse_volume(self, vol):
        try:
            return float(vol)
        except (TypeError, ValueError) as e:
            logger.warning(f"⚠️ Invalid overlay_volume '{vol}', falling back to -5 dB")
            return -5.0
            
    def apply_intro(self):
        if self.intro_path and os.path.exists(self.intro_path):
            try:
                intro = AudioSegment.from_file(self.intro_path).apply_gain(self.volume_db)
                voice = self.base  # original voice audio

                # Delay voice by 12 seconds by prepending silence
                delayed_voice = AudioSegment.silent(duration=12000) + voice

                # Overlay delayed voice on top of intro (which starts at 0:00)
                combined = intro.overlay(delayed_voice)

                self.base = combined
                logger.info(f"🎧 Intro overlay applied; voice delayed by 12s and overlapped starting at 12s")
            except Exception as e:
                logger.error(f"❌ Error applying intro from '{self.intro_path}': {e}")
        else:
            logger.info("⚠️ No valid intro provided or file not found.")


    def append_silence(self):
        self.base += AudioSegment.silent(duration=5000)
        logger.info("✅ Appended 5 seconds of silence.")

    def apply_outro(self):
        if self.outro_path and os.path.exists(self.outro_path):
            try:
                outro = AudioSegment.from_file(self.outro_path).apply_gain(self.volume_db)

                # Apply a 2-second fade-in (optional)
                fade_duration = min(2000, len(outro))
                outro = outro.fade_in(fade_duration)

                # Overlay outro so it ends 0.5 seconds (500ms) before the end of self.base
                insert_point = max(len(self.base) - len(outro) - 500, 0)
                self.base = self.base.overlay(outro, position=insert_point)

                logger.info(f"🎧 Outro overlay with fade-in applied. Starts at {insert_point} ms, ends at {insert_point + len(outro)} ms.")
            except Exception as e:
                logger.error(f"❌ Error applying outro from '{self.outro_path}': {e}")
        else:
            logger.info("ℹ️ Skipping outro: Not provided or file not found.")



    def export_final(self):
        output_path = self._get_output_path()
        try:
            self.base.export(output_path, format="wav")
            logger.info(f"✅ Final WAV saved to: {output_path}")
        except Exception as e:
            logger.error(f"❌ Failed to export WAV to '{output_path}': {e}")
            raise

    def _get_output_path(self):
        base, _ = os.path.splitext(self.wav_path)
        return f"{base}_final.wav"
