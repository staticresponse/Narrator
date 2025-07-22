from pydub import AudioSegment
import os

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

        self.base = AudioSegment.from_wav(self.wav_path)

        self.apply_intro()
        self.append_silence()
        self.apply_outro()
        self.export_final()

    def _parse_volume(self, vol):
        try:
            return float(vol)
        except (TypeError, ValueError):
            return -5.0  # fallback default

    def apply_intro(self):
        if self.intro_path and os.path.exists(self.intro_path):
            intro = AudioSegment.from_file(self.intro_path).apply_gain(self.volume_db)
            self.base = intro + self.base
            print(f"[🎵] Intro applied from: {self.intro_path}")
        else:
            print("[ℹ️] No valid intro provided or file not found.")

    def append_silence(self):
        silence = AudioSegment.silent(duration=5000)
        self.base += silence
        print("[🤫] Appended 5 seconds of silence.")

    def apply_outro(self):
        if self.outro_path and os.path.exists(self.outro_path):
            outro = AudioSegment.from_file(self.outro_path).apply_gain(self.volume_db)
            insert_point = len(self.base) - 500 - len(outro)
            insert_point = max(insert_point, 0)
            self.base = self.base.overlay(outro, position=insert_point)
            print(f"[🎶] Outro applied from: {self.outro_path}")
        else:
            print("[ℹ️] No valid outro provided or file not found.")

    def export_final(self):
        output_path = self._get_output_path()
        self.base.export(output_path, format="wav")
        print(f"[✅] Final WAV saved to: {output_path}")

    def _get_output_path(self):
        base, _ = os.path.splitext(self.wav_path)
        return f"{base}_final.wav"
