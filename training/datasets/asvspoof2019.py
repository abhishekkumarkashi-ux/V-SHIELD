"""
Adapter for ASVspoof 2019 Logical Access (LA) dataset.
Parses official CM protocol files and maps audio paths to standardized AudioSampleRecord.
"""

import os
from typing import List
from training.datasets.base import BaseDatasetAdapter, AudioSampleRecord

class ASVspoof2019Adapter(BaseDatasetAdapter):
    def __init__(self):
        super().__init__("ASVspoof2019_LA")

    def _get_protocol_filename(self, split: str) -> str:
        # Standard ASVspoof 2019 protocol file naming patterns
        if split == "train":
            return "ASVspoof2019.LA.cm.train.trn.txt"
        elif split in ("dev", "val", "validation"):
            return "ASVspoof2019.LA.cm.dev.trl.txt"
        elif split in ("eval", "test"):
            return "ASVspoof2019.LA.cm.eval.trl.txt"
        else:
            raise ValueError(f"Unknown split '{split}' for ASVspoof 2019 LA.")

    def _find_protocol_path(self, root_dir: str, split: str) -> str:
        proto_name = self._get_protocol_filename(split)
        # Search candidate locations within root_dir (handles root, LA subfolder, protocols folder)
        candidates = [
            os.path.join(root_dir, "ASVspoof2019_LA_cm_protocols", proto_name),
            os.path.join(root_dir, "LA", "ASVspoof2019_LA_cm_protocols", proto_name),
            os.path.join(root_dir, "cm_protocols", proto_name),
            os.path.join(root_dir, "protocols", proto_name),
            os.path.join(root_dir, "LA", proto_name),
            os.path.join(root_dir, proto_name)
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        raise FileNotFoundError(
            f"Expected ASVspoof 2019 protocol file '{proto_name}' not found under '{root_dir}'.\n"
            f"Searched candidates:\n" + "\n".join(f"  - {c}" for c in candidates)
        )

    def _find_audio_dir(self, root_dir: str, split: str) -> str:
        split_prefix = "train" if split == "train" else ("dev" if split in ("dev", "val") else "eval")
        candidates = [
            os.path.join(root_dir, f"ASVspoof2019_LA_{split_prefix}", "flac"),
            os.path.join(root_dir, "LA", f"ASVspoof2019_LA_{split_prefix}", "flac"),
            os.path.join(root_dir, f"ASVspoof2019_LA_{split_prefix}"),
            os.path.join(root_dir, "LA", f"ASVspoof2019_LA_{split_prefix}"),
            os.path.join(root_dir, split_prefix, "flac"),
            os.path.join(root_dir, split_prefix),
            os.path.join(root_dir, "flac")
        ]
        for c in candidates:
            if os.path.exists(c) and os.path.isdir(c):
                return c
        return os.path.join(root_dir, f"ASVspoof2019_LA_{split_prefix}", "flac")

    def validate_structure(self, root_dir: str) -> bool:
        if not os.path.exists(root_dir):
            return False
        # Look for at least train protocol or a flac folder
        for split in ("train", "dev", "eval"):
            try:
                self._find_protocol_path(root_dir, split)
                return True
            except FileNotFoundError:
                continue
        return False

    def parse_split(self, root_dir: str, split: str) -> List[AudioSampleRecord]:
        proto_path = self._find_protocol_path(root_dir, split)
        audio_dir = self._find_audio_dir(root_dir, split)

        records: List[AudioSampleRecord] = []

        with open(proto_path, "r", encoding="utf-8") as pf:
            for line_idx, line in enumerate(pf):
                parts = line.strip().split()
                if len(parts) < 5:
                    continue

                speaker_id = parts[0]
                audio_filename = parts[1]
                attack_type = parts[3] if parts[3] != "-" else "bonafide"
                key = parts[4].lower()

                # V-SHIELD standardized label: 0 = BONAFIDE, 1 = SPOOF
                label = 0 if key == "bonafide" else 1

                # Locate audio file (flac or wav)
                audio_path = os.path.join(audio_dir, f"{audio_filename}.flac")
                if not os.path.exists(audio_path):
                    wav_cand = os.path.join(audio_dir, f"{audio_filename}.wav")
                    if os.path.exists(wav_cand):
                        audio_path = wav_cand

                records.append(AudioSampleRecord(
                    file_path=audio_path,
                    speaker_id=speaker_id,
                    label=label,
                    label_name=key,
                    attack_type=attack_type,
                    dataset=self.dataset_name,
                    split="train" if split == "train" else ("dev" if split in ("dev", "val") else "test")
                ))

        return records
