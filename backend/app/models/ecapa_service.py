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

        # In-memory fast cache of speaker_id -> np.ndarray (192,)
        self._enrolled_embeddings: Dict[str, np.ndarray] = {}
        self._enrolled_metadata: Dict[str, Dict] = {}

        self._init_db()
        self._load_onnx_model()
        self._load_speechbrain_model()
        self._load_enrolled_from_db()
        self._seed_default_speakers()

    @classmethod
    def get_instance(cls) -> "ECAPAService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_onnx_model(self) -> None:
        """Initializes ONNX Runtime session for ECAPA-TDNN embedding extraction."""
        if not HAS_ORT or not os.path.exists(self.onnx_path):
            self.load_error = f"ECAPA ONNX model not found at {self.onnx_path}"
            print(
                f"[ECAPAService] {self.load_error}. Using PyTorch/Acoustic fallback."
            )
            self.is_onnx_loaded = False
            return

        try:
            available_providers = ort.get_available_providers()
            providers = []
            if "CUDAExecutionProvider" in available_providers and torch.cuda.is_available():
                providers.append("CUDAExecutionProvider")
            providers.append("CPUExecutionProvider")

            print(
                f"[ECAPAService] Loading ECAPA ONNX model from {self.onnx_path} with providers: {providers}"
            )
            self.ort_session = ort.InferenceSession(self.onnx_path, providers=providers)
            self.is_onnx_loaded = True
            print(
                f"[ECAPAService] ONNX Runtime session active using: {self.ort_session.get_providers()[0]}"
            )
        except Exception as err:
            import traceback
            self.load_error = f"ECAPA ONNX session initialization failed: {err}"
            print(
                f"[ECAPAService] ONNX initialization failed: {err}\n{traceback.format_exc()}. Falling back to SpeechBrain."
            )
            self.is_onnx_loaded = False

    def _init_db(self) -> None:
        """Initializes SQLite database for speaker profiles."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS speakers (
                    speaker_id TEXT PRIMARY KEY,
                    name TEXT,
                    enrolled_at REAL,
                    embedding BLOB
                )
            """)
            conn.commit()

    def _load_speechbrain_model(self) -> None:
        """Loads SpeechBrain ECAPA-TDNN classifier."""
        try:
            from speechbrain.inference.classifiers import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy

            print("[ECAPAService] Loading SpeechBrain spkrec-ecapa-voxceleb...")
            self.classifier = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                run_opts={"device": self.device},
                savedir=str(settings.BASE_DIR / "speechbrain_model"),
                local_strategy=LocalStrategy.COPY,
            )
            self.is_loaded = True
            print("[ECAPAService] SpeechBrain ECAPA-TDNN loaded successfully.")
        except Exception as exc:
            print(
                f"[ECAPAService] Note: SpeechBrain live model load deferred ({exc}). Using deterministic acoustic feature encoder for offline mode."
            )
            self.is_loaded = False

    def _load_enrolled_from_db(self) -> None:
        """Populates in-memory cache from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT speaker_id, name, enrolled_at, embedding FROM speakers")
            for speaker_id, name, enrolled_at, emb_bytes in cursor.fetchall():
                emb = np.frombuffer(emb_bytes, dtype=np.float32)
                self._enrolled_embeddings[speaker_id] = emb
                self._enrolled_metadata[speaker_id] = {
                    "speaker_id": speaker_id,
                    "name": name,
                    "enrolled_at": enrolled_at,
                }

    def _seed_default_speakers(self) -> None:
        """Pre-seeds standard executive profiles if database is empty."""
        if not self._enrolled_embeddings:
            defaults = [
                ("exec-001", "Dr. Rajesh Sharma (Chief Technology Officer)"),
                ("exec-002", "Ananya Iyer (VP of Financial Operations)"),
                ("exec-003", "Vikram Malhotra (Lead Treasury Controller)"),
            ]
            for sid, name in defaults:
                # Deterministic normalized 192-d embedding
                rng = np.random.RandomState(hash(sid) % (2**32))
                vec = rng.randn(192).astype(np.float32)
                vec = vec / (np.linalg.norm(vec) + 1e-9)
                self._save_speaker_to_db(sid, name, vec)
                self._enrolled_embeddings[sid] = vec
                self._enrolled_metadata[sid] = {
                    "speaker_id": sid,
                    "name": name,
                    "enrolled_at": time.time(),
                }

    def _save_speaker_to_db(self, speaker_id: str, name: str, embedding: np.ndarray) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO speakers (speaker_id, name, enrolled_at, embedding) VALUES (?, ?, ?, ?)",
                (speaker_id, name, time.time(), embedding.tobytes()),
            )
            conn.commit()

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
            wav_tensor = torch.from_numpy(audio_np).unsqueeze(0)
        elif isinstance(audio, np.ndarray):
            if audio.dtype == np.int16:
                audio_np = audio.astype(np.float32) / 32768.0
            else:
                audio_np = audio.astype(np.float32)
            if audio_np.ndim > 1:
                audio_np = audio_np.flatten()
            audio_np = np.clip(audio_np, -1.0, 1.0)
            wav_tensor = torch.from_numpy(audio_np).unsqueeze(0)
        else:
            wav_tensor = audio.detach().cpu().float()
            if wav_tensor.dim() > 1:
                wav_tensor = wav_tensor.squeeze()
            if wav_tensor.dim() == 0:
                wav_tensor = wav_tensor.unsqueeze(0)
            audio_np = np.clip(wav_tensor.numpy(), -1.0, 1.0)
            wav_tensor = torch.from_numpy(audio_np).unsqueeze(0)

        # 1. High-Performance ONNX Runtime Fast Path
        if self.is_onnx_loaded and self.ort_session is not None:
            try:
                if wav_tensor.dim() == 1:
                    arr = wav_tensor.unsqueeze(0).cpu().numpy().astype(np.float32)
                else:
                    arr = wav_tensor.cpu().numpy().astype(np.float32)
                ort_out = self.ort_session.run(["embedding"], {"audio_input": arr})[0]
                emb = np.squeeze(ort_out)
                norm = np.linalg.norm(emb) + 1e-9
                return (emb / norm).astype(np.float32)
            except Exception as e:
                print(
                    f"[ECAPAService] ONNX execution error ({e}). Falling back to SpeechBrain PyTorch."
                )

        # 2. PyTorch SpeechBrain Live Classifier Path
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

        # Resilient offline feature extractor:
        # Generates 192-d normalized acoustic voiceprint from spectral/temporal statistics
        if len(audio_np) < 512:
            audio_np = np.pad(audio_np, (0, 512 - len(audio_np)))

        # FFT spectral moments + autocorrelation
        fft_mags = np.abs(np.fft.rfft(audio_np[:16000]))
        chunk_size = max(1, len(fft_mags) // 96)
        spec_feats = [np.mean(fft_mags[i * chunk_size : (i + 1) * chunk_size]) for i in range(96)]

        # Temporal statistics
        energy = np.mean(audio_np**2)
        zero_cross = np.mean(np.diff(np.sign(audio_np)) != 0)
        time_feats = [float(energy), float(zero_cross)] + [
            float(np.std(audio_np[i::94])) for i in range(94)
        ]

        combined = np.array(spec_feats + time_feats, dtype=np.float32)[:192]
        if len(combined) < 192:
            combined = np.pad(combined, (0, 192 - len(combined)))
        norm = np.linalg.norm(combined) + 1e-9
        return (combined / norm).astype(np.float32)

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
            cosine_similarity in [-1.0, 1.0], or None if speaker not found.
        """
        if speaker_id not in self._enrolled_embeddings:
            return None

        enrolled_emb = self._enrolled_embeddings[speaker_id]
        current_emb = self.extract_embedding(audio)

        # Cosine similarity between unit vectors
        dot_product = float(np.dot(enrolled_emb, current_emb))
        cos_sim = max(-1.0, min(1.0, dot_product))
        return cos_sim

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
                - status: 'VERIFIED' (>=0.70), 'MISMATCH' (<=0.40), 'EVALUATING' (0.40-0.70),
                          or 'NO_VOICEPRINT' if no profile exists for speaker_id.
                - similarity: float cosine similarity or None if unenrolled.
                - speaker_id: speaker ID queried.
                - is_match: bool indicating verified biometric identity match.
                - has_voiceprint: bool indicating enrolled profile was found.
        """
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
                "has_voiceprint": False,
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
