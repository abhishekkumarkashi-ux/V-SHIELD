"""
SpeechBrain ECAPA-TDNN Speaker Verification Service (SIH 2026).
Extracts 192-dimensional speaker embeddings.
Implements speaker enrollment, persistent SQLite storage, and cosine similarity verification.
"""

import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Union

import numpy as np
import torch

from app.config import settings
from app.core.db import init_db, load_speakers_from_db, save_speaker_to_db

try:
    import onnxruntime as ort

    HAS_ORT = True
except ImportError:
    ort = None
    HAS_ORT = False


class ECAPAService:
    """
    Manages speaker voiceprint registration and real-time biometric verification
    using ECAPA-TDNN 192-dimensional embeddings via ONNX Runtime (FP16/CUDA/CPU)
    with SpeechBrain PyTorch and offline acoustic fallbacks.
    """

    _instance: Optional["ECAPAService"] = None

    def __init__(
        self,
        db_path: Optional[str] = None,
        onnx_path: Optional[str] = None,
        device: Optional[str] = None,
    ) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.db_path = db_path or str(settings.SPEAKERS_DB_PATH)
        self.onnx_path = onnx_path or str(settings.ECAPA_ONNX_PATH)
        self.ort_session: Optional["ort.InferenceSession"] = None
        self.is_onnx_loaded: bool = False
        self.classifier = None
        self.is_loaded: bool = False
        self.load_error: Optional[str] = None
        self.active_provider: str = "None"
        self.inference_device: str = "cpu"

        # In-memory fast cache of speaker_id -> np.ndarray (192,)
        self._enrolled_embeddings: Dict[str, np.ndarray] = {}
        self._enrolled_metadata: Dict[str, Dict] = {}

        self._init_db()
        self._load_onnx_model()
        self._load_speechbrain_model()
        self._load_enrolled_from_db()

    @property
    def is_available(self) -> bool:
        """Returns True if at least one genuine ECAPA-TDNN model engine is loaded."""
        return bool(self.is_onnx_loaded or self.is_loaded)

    @classmethod
    def get_instance(cls) -> "ECAPAService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_db(self) -> None:
        """Initializes database for speaker profiles (SQLite or PostgreSQL)."""
        init_db(self.db_path)

    def _load_onnx_model(self) -> None:
        """Initializes ONNX Runtime session for ECAPA-TDNN embedding extraction."""
        if not HAS_ORT or not os.path.exists(self.onnx_path):
            self.load_error = f"ECAPA ONNX model not found at {self.onnx_path}"
            self.is_onnx_loaded = False
            self.active_provider = "None"
            self.inference_device = "cpu"
            return

        try:
            available_providers = ort.get_available_providers()
            providers = []
            if "CUDAExecutionProvider" in available_providers and torch.cuda.is_available():
                providers.append("CUDAExecutionProvider")
            providers.append("CPUExecutionProvider")

            sess_options = ort.SessionOptions()
            sess_options.intra_op_num_threads = 4
            sess_options.inter_op_num_threads = 1
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.enable_mem_pattern = True
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

            self.ort_session = ort.InferenceSession(
                self.onnx_path, sess_options=sess_options, providers=providers
            )
            self.is_onnx_loaded = True
            active_list = self.ort_session.get_providers()
            self.active_provider = active_list[0] if active_list else "CPUExecutionProvider"
            self.inference_device = "cuda" if "CUDA" in self.active_provider else "cpu"
        except Exception as err:
            self.load_error = f"ECAPA ONNX session initialization failed: {err}"
            self.is_onnx_loaded = False
            self.active_provider = "None"
            self.inference_device = "cpu"

    def _load_speechbrain_model(self) -> None:
        """Loads SpeechBrain ECAPA-TDNN classifier."""
        try:
            from speechbrain.inference.classifiers import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy

            self.classifier = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                run_opts={"device": self.device},
                savedir=str(settings.BASE_DIR / "speechbrain_model"),
                local_strategy=LocalStrategy.COPY,
            )
            self.is_loaded = True
        except Exception as exc:
            self.load_error = f"SpeechBrain ECAPA model load deferred: {exc}"
            self.is_loaded = False

    def _load_enrolled_from_db(self) -> None:
        """Populates in-memory cache from database."""
        records = load_speakers_from_db(self.db_path)
        for speaker_id, name, enrolled_at, emb_bytes in records:
            if emb_bytes:
                emb = np.frombuffer(emb_bytes, dtype=np.float32)
                self._enrolled_embeddings[speaker_id] = emb
                self._enrolled_metadata[speaker_id] = {
                    "speaker_id": speaker_id,
                    "name": name,
                    "enrolled_at": enrolled_at,
                }

    def _save_speaker_to_db(self, speaker_id: str, name: str, embedding: np.ndarray) -> None:
        save_speaker_to_db(
            speaker_id=speaker_id,
            name=name,
            enrolled_at=time.time(),
            embedding_bytes=embedding.tobytes(),
            db_path=self.db_path,
        )

    def extract_embedding(self, audio: Union[bytes, np.ndarray, torch.Tensor]) -> np.ndarray:
        """
        Extracts 192-dimensional speaker embedding from audio.
        Audio can be raw Float32/PCM16 bytes, numpy float32, or PyTorch tensor.
        Auto-detects Float32 vs PCM16 byte representations.
        """
        if isinstance(audio, bytes):
            # Auto-detect Float32 PCM bytes vs PCM16 bytes
            parsed_as_f32 = False
            if len(audio) % 4 == 0 and len(audio) >= 4:
                try:
                    candidate = np.frombuffer(audio, dtype=np.float32)
                    if np.all(np.isfinite(candidate)):
                        max_abs = float(np.max(np.abs(candidate))) if len(candidate) > 0 else 0.0
                        if max_abs <= 5.0:
                            audio_np = candidate.astype(np.float32)
                            parsed_as_f32 = True
                except Exception:
                    parsed_as_f32 = False

            if not parsed_as_f32:
                valid_len = (len(audio) // 2) * 2
                int16_data = np.frombuffer(audio[:valid_len], dtype=np.int16)
                audio_np = int16_data.astype(np.float32) / 32768.0

            audio_np = np.clip(audio_np, -1.0, 1.0)
        elif isinstance(audio, np.ndarray):
            if audio.dtype == np.int16:
                audio_np = audio.astype(np.float32) / 32768.0
            elif audio.dtype == np.float32:
                audio_np = audio
            else:
                audio_np = audio.astype(np.float32)
            if audio_np.ndim > 1:
                audio_np = audio_np.flatten()
            audio_np = np.clip(audio_np, -1.0, 1.0)
        elif isinstance(audio, torch.Tensor):
            t = audio.detach().cpu().float()
            if t.dim() > 1:
                t = t.squeeze()
            audio_np = np.clip(t.numpy(), -1.0, 1.0)
        else:
            audio_np = np.clip(np.asarray(audio, dtype=np.float32).flatten(), -1.0, 1.0)

        # 1. High-Performance ONNX Runtime Fast Path
        if self.is_onnx_loaded and self.ort_session is not None:
            try:
                arr = audio_np if audio_np.ndim == 2 else np.expand_dims(audio_np, axis=0)
                if not arr.flags["C_CONTIGUOUS"]:
                    arr = np.ascontiguousarray(arr)
                ort_out = self.ort_session.run(["embedding"], {"audio_input": arr})[0]
                emb = np.squeeze(ort_out)
                norm = np.linalg.norm(emb) + 1e-9
                return (emb / norm).astype(np.float32)
            except Exception as e:
                print(
                    f"[ECAPAService] ONNX execution error ({e}). Falling back to SpeechBrain PyTorch."
                )

        # 2. PyTorch SpeechBrain Live Classifier Path
        wav_tensor = torch.from_numpy(audio_np).unsqueeze(0)
        if self.is_loaded and self.classifier is not None:
            try:
                wav_dev = wav_tensor.to(self.device)
                with torch.no_grad():
                    emb = self.classifier.encode_batch(wav_dev)
                    emb = emb.squeeze().cpu().numpy()
                    norm = np.linalg.norm(emb) + 1e-9
                    return (emb / norm).astype(np.float32)
            except Exception as e:
                print(
                    f"[ECAPAService] Inference error on live classifier ({e}). Falling back to acoustic signature."
                )

        # If neither ONNX nor SpeechBrain inference succeeded, fail explicitly.
        raise RuntimeError(
            f"ECAPA-TDNN model unavailable: neither ONNX Runtime nor SpeechBrain engine is active. "
            f"Load error: {self.load_error or 'No model available'}"
        )

    def enroll_speaker(
        self,
        speaker_id: str,
        audio: Union[bytes, np.ndarray, torch.Tensor],
        name: Optional[str] = None,
    ) -> np.ndarray:
        """
        Enrolls a speaker by extracting their 192-d embedding and persisting it.
        """
        embedding = self.extract_embedding(audio)
        self._enrolled_embeddings[speaker_id] = embedding
        speaker_name = name or speaker_id
        self._enrolled_metadata[speaker_id] = {
            "speaker_id": speaker_id,
            "name": speaker_name,
            "enrolled_at": time.time(),
        }
        self._save_speaker_to_db(speaker_id, speaker_name, embedding)
        return embedding

    def verify_speaker(
        self, audio: Union[bytes, np.ndarray, torch.Tensor], speaker_id: str
    ) -> Optional[float]:
        """
        Computes cosine similarity between incoming audio and registered speaker embedding.
        Returns:
            cosine_similarity in [-1.0, 1.0], or None if speaker not found or model unavailable.
        """
        if not self.is_available or speaker_id not in self._enrolled_embeddings:
            return None

        try:
            enrolled_emb = self._enrolled_embeddings[speaker_id]
            current_emb = self.extract_embedding(audio)

            # Cosine similarity between unit vectors
            dot_product = float(np.dot(enrolled_emb, current_emb))
            cos_sim = max(-1.0, min(1.0, dot_product))
            return cos_sim
        except Exception as err:
            print(f"[ECAPAService] Speaker verification extraction failure: {err}")
            return None

    def verify_speaker_detailed(
        self,
        audio: Union[bytes, np.ndarray, torch.Tensor],
        speaker_id: Optional[str],
        threshold_match: float = 0.70,
        threshold_mismatch: float = 0.40,
    ) -> Dict[str, Any]:
        """
        Performs explicit speaker verification against enrolled voiceprint profiles.

        Returns:
            Dict containing:
                - status: 'VERIFIED', 'MISMATCH', 'EVALUATING', 'NO_VOICEPRINT', or 'UNAVAILABLE'.
                - similarity: float cosine similarity or None if unenrolled / unavailable.
                - speaker_id: speaker ID queried.
                - is_match: bool indicating verified biometric identity match.
                - has_voiceprint: bool indicating enrolled profile was found.
        """
        if not self.is_available:
            return {
                "status": "UNAVAILABLE",
                "reason": "ECAPA model unavailable",
                "similarity": None,
                "speaker_id": speaker_id,
                "is_match": False,
                "has_voiceprint": bool(speaker_id and speaker_id in self._enrolled_embeddings),
            }

        if not speaker_id or speaker_id not in self._enrolled_embeddings:
            return {
                "status": "NO_VOICEPRINT",
                "similarity": None,
                "speaker_id": speaker_id,
                "is_match": False,
                "has_voiceprint": False,
            }

        similarity = self.verify_speaker(audio, speaker_id)
        if similarity is None:
            return {
                "status": "NO_VOICEPRINT",
                "similarity": None,
                "speaker_id": speaker_id,
                "is_match": False,
                "has_voiceprint": True,
            }

        if similarity >= threshold_match:
            status = "VERIFIED"
            is_match = True
        elif similarity <= threshold_mismatch:
            status = "MISMATCH"
            is_match = False
        else:
            status = "EVALUATING"
            is_match = False

        return {
            "status": status,
            "similarity": similarity,
            "speaker_id": speaker_id,
            "is_match": is_match,
            "has_voiceprint": True,
        }

    def get_enrolled_speakers(self) -> List[Dict]:
        """Returns list of enrolled speaker profiles."""
        return list(self._enrolled_metadata.values())

    def get_speaker_embedding(self, speaker_id: str) -> Optional[np.ndarray]:
        return self._enrolled_embeddings.get(speaker_id)
