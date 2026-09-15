"""
Adapter for ASVspoof 2021 (Logical Access and Deepfake tracks).
Parses 2021 trial metadata formats into standardized AudioSampleRecord.
"""

import os
from typing import List
from training.datasets.base import BaseDatasetAdapter, AudioSampleRecord

class ASVspoof2021Adapter(BaseDatasetAdapter):
    def __init__(self, track: str = "LA"):
        self.track = track.upper()
        super().__init__(f"ASVspoof2021_{self.track}")

    def _find_trial_file(self, root_dir: str) -> str:
        candidates = [
            os.path.join(root_dir, f"ASVspoof2021_{self.track}_eval", f"trial_metadata.txt"),
            os.path.join(root_dir, f"ASVspoof2021_{self.track}_cm_protocols", f"ASVspoof2021.{self.track}.cm.eval.trial.txt"),
            os.path.join(root_dir, "trial_metadata.txt"),
            os.path.join(root_dir, "protocols", f"ASVspoof2021.{self.track}.cm.eval.trial.txt"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        raise FileNotFoundError(f"Trial metadata file for ASVspoof 2021 {self.track} not found under {root_dir}.")

    def _find_flac_dir(self, root_dir: str) -> str:
        candidates = [
            os.path.join(root_dir, f"ASVspoof2021_{self.track}_eval", "flac"),
            os.path.join(root_dir, "flac"),
            os.path.join(root_dir, f"ASVspoof2021_{self.track}_eval")
        ]
        for c in candidates:
            if os.path.exists(c) and os.path.isdir(c):
                return c
        return os.path.join(root_dir, "flac")

    def validate_structure(self, root_dir: str) -> bool:
        if not os.path.exists(root_dir):
            return False
        try:
            self._find_trial_file(root_dir)
            return True
        except FileNotFoundError:
            return False

    def parse_split(self, root_dir: str, split: str = "eval") -> List[AudioSampleRecord]:
        trial_path = self._find_trial_file(root_dir)
        flac_dir = self._find_flac_dir(root_dir)
        records: List[AudioSampleRecord] = []

        with open(trial_path, "r", encoding="utf-8") as tf:
            for line in tf:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue

                speaker_id = parts[0]
                filename = parts[1]
                key = parts[-1].lower()
                attack_type = parts[3] if len(parts) > 5 else "unknown"

                if key not in ("bonafide", "spoof"):
                    continue

                label = 0 if key == "bonafide" else 1
                audio_path = os.path.join(flac_dir, f"{filename}.flac")

                records.append(AudioSampleRecord(
                    file_path=audio_path,
                    speaker_id=speaker_id,
                    label=label,
                    label_name=key,
                    attack_type=attack_type,
                    dataset=self.dataset_name,
                    split=split
                ))

        return records
