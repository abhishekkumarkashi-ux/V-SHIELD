import os
import numpy as np
from typing import Any

EMBEDDINGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "embeddings")
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

def _get_path(speaker_id: str) -> str:
    return os.path.join(EMBEDDINGS_DIR, f"{speaker_id}.npy")

def save_speaker_embedding(speaker_id: str, embedding: Any):
    # Ensure it's a numpy array
    if not isinstance(embedding, np.ndarray):
        if hasattr(embedding, "numpy"):
            embedding = embedding.cpu().numpy()
        else:
            embedding = np.array(embedding)
    np.save(_get_path(speaker_id), embedding)

def get_speaker_embedding(speaker_id: str) -> Any:
    path = _get_path(speaker_id)
    if os.path.exists(path):
        try:
            return np.load(path)
        except Exception:
            return None
    return None

def remove_speaker_embedding(speaker_id: str):
    path = _get_path(speaker_id)
    if os.path.exists(path):
        os.remove(path)
