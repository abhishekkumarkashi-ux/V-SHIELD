"""
Base dataset adapter definitions for V-SHIELD.
Provides the abstract contract and unified sample record schema for anti-spoof datasets.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import os

@dataclass
class AudioSampleRecord:
    file_path: str
    speaker_id: str
    label: int                  # 0 = BONAFIDE, 1 = SPOOF
    label_name: str             # "bonafide" or "spoof"
    attack_type: str            # e.g., "A01", "A02", "bonafide", "tts", "vc"
    dataset: str                # e.g., "ASVspoof2019_LA", "InTheWild"
    split: str                  # "train", "dev" / "val", "eval" / "test"
    sample_rate: Optional[int] = None
    duration_seconds: Optional[float] = None
    num_samples: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaseDatasetAdapter(ABC):
    """Abstract interface for audio anti-spoofing dataset adapters."""

    def __init__(self, dataset_name: str):
        self.dataset_name = dataset_name

    @abstractmethod
    def parse_split(self, root_dir: str, split: str) -> List[AudioSampleRecord]:
        """
        Parse dataset protocol files and audio directories for a specific split.
        Returns a list of standardized AudioSampleRecord instances.
        """
        pass

    @abstractmethod
    def validate_structure(self, root_dir: str) -> bool:
        """
        Checks if the expected directory layout and protocol files exist.
        """
        pass
