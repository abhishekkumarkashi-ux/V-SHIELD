"""
PyTorch Dataset for V-SHIELD Anti-Spoof Training.
Implements lazy-loading from disk to prevent RAM exhaustion (hardware-safe for 8GB RAM).
"""

import os
import csv
import torch
from torch.utils.data import Dataset, DataLoader
from typing import List, Optional, Dict, Any

from training.datasets.base import AudioSampleRecord
from training.audio import load_audio, preprocess_audio, WINDOW_SAMPLES

class AntiSpoofDataset(Dataset):
    def __init__(
        self, 
        manifest_csv: Optional[str] = None, 
        records: Optional[List[AudioSampleRecord]] = None,
        split: Optional[str] = None,
        mode: str = "train",
        target_samples: int = WINDOW_SAMPLES
    ):
        """
        Args:
            manifest_csv: Path to metadata CSV manifest.
            records: In-memory list of AudioSampleRecord instances (alternative to CSV).
            split: Filter records by split ('train', 'dev'/'val', 'test'/'eval').
            mode: 'train' (uses random 4s crop for augmentation) or 'eval' (deterministic).
            target_samples: Fixed audio length (64,000 samples = 4.0s).
        """
        self.mode = mode
        self.target_samples = target_samples
        self.records: List[Dict[str, Any]] = []

        if manifest_csv is not None:
            if not os.path.exists(manifest_csv):
                raise FileNotFoundError(f"Manifest CSV not found: {manifest_csv}")
            with open(manifest_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rec_split = (row.get("split") or "").lower()
                    if split is None or self._match_split(rec_split, split):
                        self.records.append({
                            "file_path": row["file_path"],
                            "label": int(row["label"]),
                            "speaker_id": row.get("speaker_id", "unknown"),
                            "attack_type": row.get("attack_type", "unknown")
                        })
        elif records is not None:
            for r in records:
                if split is None or self._match_split(r.split, split):
                    self.records.append({
                        "file_path": r.file_path,
                        "label": int(r.label),
                        "speaker_id": r.speaker_id,
                        "attack_type": r.attack_type
                    })
        else:
            raise ValueError("Either manifest_csv or records must be provided.")

    def _match_split(self, rec_split: str, target_split: str) -> bool:
        r = rec_split.lower()
        t = target_split.lower()
        if t in ("train", "training") and "train" in r:
            return True
        if t in ("dev", "val", "validation") and ("dev" in r or "val" in r):
            return True
        if t in ("eval", "test", "testing") and ("eval" in r or "test" in r):
            return True
        return r == t

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int):
        rec = self.records[idx]
        fpath = rec["file_path"]
        label = rec["label"]

        crop_mode = "random" if self.mode == "train" else "deterministic"

        try:
            waveform, sr = load_audio(fpath, target_sr=16000)
            processed_waveform = preprocess_audio(waveform, target_length=self.target_samples, mode=crop_mode)
        except Exception as e:
            # Failsafe fallback: return zero waveform to prevent DataLoader worker crash
            processed_waveform = torch.zeros((1, self.target_samples), dtype=torch.float32)

        target_tensor = torch.tensor([label], dtype=torch.float32)
        return processed_waveform, target_tensor


def create_dataloader(
    manifest_csv: str,
    split: str,
    batch_size: int = 16,
    shuffle: bool = True,
    num_workers: int = 0,
    pin_memory: bool = False,
    mode: str = "train"
) -> DataLoader:
    """Factory helper to build a lazy DataLoader with memory safety."""
    dataset = AntiSpoofDataset(manifest_csv=manifest_csv, split=split, mode=mode)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=pin_memory,
        drop_last=(mode == "train")
    )
