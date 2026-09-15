"""
Adapter for the 'In-The-Wild' deepfake speech dataset.
Supports CSV manifest metadata format and directory-based layout (bona-fide / spoof).
"""

import os
import csv
from typing import List
from training.datasets.base import BaseDatasetAdapter, AudioSampleRecord

class InTheWildAdapter(BaseDatasetAdapter):
    def __init__(self):
        super().__init__("InTheWild")

    def validate_structure(self, root_dir: str) -> bool:
        if not os.path.exists(root_dir):
            return False
        meta_cand = os.path.join(root_dir, "meta.csv")
        if os.path.exists(meta_cand):
            return True
        genuine_cand = os.path.join(root_dir, "bona-fide")
        spoof_cand = os.path.join(root_dir, "spoof")
        return os.path.exists(genuine_cand) or os.path.exists(spoof_cand)

    def parse_split(self, root_dir: str, split: str = "all") -> List[AudioSampleRecord]:
        records: List[AudioSampleRecord] = []
        meta_csv = os.path.join(root_dir, "meta.csv")

        if os.path.exists(meta_csv):
            with open(meta_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fname = row.get("file") or row.get("filename") or row.get("file_path")
                    speaker = row.get("speaker") or "wild_speaker"
                    raw_label = (row.get("label") or "").lower()

                    if not fname or not raw_label:
                        continue

                    label = 0 if "bona" in raw_label or "real" in raw_label else 1
                    label_name = "bonafide" if label == 0 else "spoof"

                    fpath = os.path.join(root_dir, fname)
                    if not os.path.exists(fpath):
                        # Try searching in subfolders
                        cand1 = os.path.join(root_dir, label_name, fname)
                        if os.path.exists(cand1):
                            fpath = cand1

                    records.append(AudioSampleRecord(
                        file_path=fpath,
                        speaker_id=speaker,
                        label=label,
                        label_name=label_name,
                        attack_type="in_the_wild",
                        dataset=self.dataset_name,
                        split=split
                    ))
        else:
            # Fallback: traverse directory structure
            for cat, label, key in [("bona-fide", 0, "bonafide"), ("spoof", 1, "spoof"), ("real", 0, "bonafide"), ("fake", 1, "spoof")]:
                cat_dir = os.path.join(root_dir, cat)
                if os.path.exists(cat_dir):
                    for r, _, files in os.walk(cat_dir):
                        for file in files:
                            if file.lower().endswith((".wav", ".flac", ".mp3", ".ogg")):
                                fpath = os.path.join(r, file)
                                records.append(AudioSampleRecord(
                                    file_path=fpath,
                                    speaker_id="unknown_speaker",
                                    label=label,
                                    label_name=key,
                                    attack_type="in_the_wild",
                                    dataset=self.dataset_name,
                                    split=split
                                ))

        return records
