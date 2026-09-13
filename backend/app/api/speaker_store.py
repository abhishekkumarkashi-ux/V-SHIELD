from typing import Dict, Any

# In-memory store mapping speaker_id -> speaker embedding tensor
# Note: In a production scenario, embeddings should be saved to a database (e.g. pgvector)
_speaker_store: Dict[str, Any] = {}

def save_speaker_embedding(speaker_id: str, embedding: Any):
    _speaker_store[speaker_id] = embedding

def get_speaker_embedding(speaker_id: str) -> Any:
    return _speaker_store.get(speaker_id)

def remove_speaker_embedding(speaker_id: str):
    if speaker_id in _speaker_store:
        del _speaker_store[speaker_id]
