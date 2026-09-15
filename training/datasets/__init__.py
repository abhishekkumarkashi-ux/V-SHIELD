"""
Dataset adapters package for V-SHIELD anti-spoof training.
"""

from training.datasets.base import BaseDatasetAdapter, AudioSampleRecord
from training.datasets.asvspoof2019 import ASVspoof2019Adapter
from training.datasets.asvspoof2021 import ASVspoof2021Adapter
from training.datasets.in_the_wild import InTheWildAdapter
from training.datasets.torch_dataset import AntiSpoofDataset, create_dataloader

def get_dataset_adapter(name: str) -> BaseDatasetAdapter:
    n = name.lower()
    if "2019" in n:
        return ASVspoof2019Adapter()
    elif "2021" in n and "df" in n:
        return ASVspoof2021Adapter(track="DF")
    elif "2021" in n:
        return ASVspoof2021Adapter(track="LA")
    elif "wild" in n:
        return InTheWildAdapter()
    else:
        raise ValueError(f"Unsupported dataset adapter: '{name}'. Supported: 'ASVspoof2019_LA', 'ASVspoof2021_LA', 'ASVspoof2021_DF', 'InTheWild'.")

__all__ = [
    "BaseDatasetAdapter",
    "AudioSampleRecord",
    "ASVspoof2019Adapter",
    "ASVspoof2021Adapter",
    "InTheWildAdapter",
    "AntiSpoofDataset",
    "create_dataloader",
    "get_dataset_adapter"
]
