"""
AASIST Inference Service (SIH 2026).
Accelerated via ONNX Runtime FP16 with CUDA / CPU execution providers.
Provides predict_spoof_prob() with automatic PyTorch fallback.
"""

import os
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
import torch
import torch.nn.functional as F

try:
    import onnxruntime as ort

    HAS_ORT = True
except ImportError:
    ort = None
    HAS_ORT = False

from app.config import settings
from app.models.aasist import DEFAULT_AASIST_CONFIG
from app.models.aasist import Model as AASISTModel


class _LoadStatus(int):
    """
    Hybrid int/bool supporting both boolean evaluation and zero-argument invocation:
    - bool(status) -> True/False
    - status() -> True/False
    - if status: -> evaluates as boolean
    """

    def __call__(self) -> bool:
        return bool(self)


class AASISTModelAdapter:
    """
    Production AASIST Model Adapter conforming to V-SHIELD unified ML architecture.
    Provides dual-runtime inference (FP16 ONNX Runtime with PyTorch native fallback).

    Clean Adapter Interface:
      - load() -> bool
      - predict(audio) -> Tuple[torch.Tensor, float]
      - is_loaded() -> bool
    """

    def __init__(
        self,
        weights_path: Optional[Union[str, Path]] = None,
        onnx_path: Optional[Union[str, Path]] = None,
        device: Optional[str] = None,
    ) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # Prioritize explicit environment variable VSHIELD_ANTISPOOF_MODEL_PATH
        env_path = getattr(settings, "VSHIELD_ANTISPOOF_MODEL_PATH", None)
        if env_path:
            p = Path(env_path)
            if p.suffix.lower() == ".onnx":
                onnx_path = str(p)
            elif p.suffix.lower() in (".pth", ".pt"):
                weights_path = str(p)

        self.weights_path = str(weights_path or settings.AASIST_WEIGHTS_PATH)
        self.onnx_path = str(onnx_path or settings.AASIST_ONNX_PATH)
        self.model: Optional[AASISTModel] = None
        self.ort_session: Optional["ort.InferenceSession"] = None
        self._is_onnx_loaded: bool = False
        self._is_loaded: bool = False
        self.load_error: Optional[str] = None

        self.load()

    def load(self) -> bool:
        """
        Loads AASIST model weights. First attempts ONNX Runtime FP16 acceleration;
        if unavailable, initializes native PyTorch AASIST graph neural network.
        Returns True if at least one runtime engine is active.
        """
        self._initialize_onnx()
        self._initialize_model()
        return self.is_loaded()

    def is_loaded(self) -> _LoadStatus:
        """Returns True if either ONNX or PyTorch AASIST engine is loaded and ready."""
        return _LoadStatus(1 if (self._is_onnx_loaded or self._is_loaded) else 0)

    @property
    def is_onnx_loaded(self) -> _LoadStatus:
        return _LoadStatus(1 if self._is_onnx_loaded else 0)

    @is_onnx_loaded.setter
    def is_onnx_loaded(self, value: bool) -> None:
        self._is_onnx_loaded = bool(value)

    @property
    def status(self) -> str:
        """Explicit model readiness status: READY, NOT_READY, or LOAD_ERROR."""
        if self._is_onnx_loaded or self._is_loaded:
            return "READY"
        if self.load_error:
            return "LOAD_ERROR"
        return "NOT_READY"

    def _initialize_onnx(self) -> None:
        """Initializes ONNX Runtime session with CUDA and CPU providers."""
        if not HAS_ORT or not os.path.exists(self.onnx_path):
            self.load_error = f"ONNX model file not found at {self.onnx_path}"
            self._is_onnx_loaded = False
            return

        try:
            available_providers = ort.get_available_providers()
            providers = []
            if "CUDAExecutionProvider" in available_providers and torch.cuda.is_available():
                providers.append("CUDAExecutionProvider")
            providers.append("CPUExecutionProvider")

            self.ort_session = ort.InferenceSession(self.onnx_path, providers=providers)
            self._is_onnx_loaded = True
        except Exception as err:
            self.load_error = f"ONNX session initialization failed: {err}"
            self._is_onnx_loaded = False

    def _initialize_model(self) -> None:
        """Instantiates PyTorch AASIST model from local weights without network downloads."""
        try:
            self.model = AASISTModel(DEFAULT_AASIST_CONFIG)
            if os.path.exists(self.weights_path) and os.path.getsize(self.weights_path) > 100000:
                state_dict = torch.load(
                    self.weights_path, map_location=self.device, weights_only=False
                )
                self.model.load_state_dict(state_dict, strict=False)
                self.model.to(self.device)
                self.model.eval()
                self._is_loaded = True
            else:
                if not self._is_onnx_loaded:
                    self.load_error = f"AASIST checkpoint missing or invalid at {self.weights_path}"
                self._is_loaded = False
        except Exception as err:
            if not self._is_onnx_loaded:
                self.load_error = f"PyTorch AASIST initialization failed: {err}"
            self._is_loaded = False

    def predict_spoof_prob(self, audio_np: np.ndarray) -> float:
        """
        High-performance ONNX Runtime inference returning P(spoof) directly.
        Accepts numpy array of shape (1, 64600) or (64600,) float32.
        """
        arr = np.asarray(audio_np, dtype=np.float32)
        if arr.ndim == 1:
            arr = np.expand_dims(arr, axis=0)

        target_len = settings.WINDOW_SIZE
        cur_len = arr.shape[-1]
        if cur_len < target_len:
            pad_amount = target_len - cur_len
            arr = np.pad(arr, ((0, 0), (0, pad_amount)), mode="constant")
        elif cur_len > target_len:
            arr = arr[:, :target_len]

        if self._is_onnx_loaded and self.ort_session is not None:
            try:
                logits = self.ort_session.run(["logits"], {"audio_input": arr})[0]
                exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
                probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)
                return float(probs[0, 1])
            except Exception as e:
                print(f"[AASISTAdapter] ONNX execution error ({e}). Using PyTorch fallback.")

        # PyTorch fallback
        tensor = torch.from_numpy(arr)
        _, spoof_prob = self.predict(tensor)
        return spoof_prob

    def predict(self, audio: Union[np.ndarray, torch.Tensor]) -> Tuple[torch.Tensor, float]:
        """
        Unified inference on audio tensor or numpy array under torch.no_grad().
        Routes through ONNX Runtime if available, otherwise PyTorch model.
        Returns:
            logits (torch.Tensor): [bona_fide_score, spoof_score]
            spoof_probability (float): Softmax(logits)[1]
        """
        if isinstance(audio, np.ndarray):
            x = torch.from_numpy(audio.astype(np.float32))
        else:
            x = audio.detach()

        # Format input tensor to exactly (1, 64600)
        if x.dim() == 1:
            x = x.unsqueeze(0)
        elif x.dim() == 3:
            x = x.squeeze(1)

        target_len = settings.WINDOW_SIZE
        cur_len = x.size(-1)
        if cur_len < target_len:
            pad_amount = target_len - cur_len
            x = F.pad(x, (0, pad_amount), "constant", 0)
        elif cur_len > target_len:
            x = x[:, :target_len]

        # 1. Try ONNX Runtime fast path
        if self._is_onnx_loaded and self.ort_session is not None:
            try:
                arr = x.cpu().numpy().astype(np.float32)
                ort_logits = self.ort_session.run(["logits"], {"audio_input": arr})[0]
                exp_logits = np.exp(ort_logits - np.max(ort_logits, axis=-1, keepdims=True))
                probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)
                spoof_prob = float(probs[0, 1])
                return torch.from_numpy(ort_logits), spoof_prob
            except Exception as e:
                print(
                    f"[AASISTAdapter] ONNX Runtime error during predict ({e}). Falling back to PyTorch."
                )

        # 2. PyTorch Native Fallback
        if not self._is_loaded or self.model is None:
            self._initialize_model()

        if self.model is None or not self._is_loaded:
            raise RuntimeError(
                f"AASIST model failed to infer: neither ONNX nor PyTorch engine is loaded (load_error={self.load_error})"
            )

        x = x.to(self.device, dtype=torch.float32)
        with torch.no_grad():
            _, logits = self.model(x)
            probs = F.softmax(logits, dim=-1)
            spoof_prob = float(probs[0, 1].item())

        return logits.cpu(), spoof_prob


class AASISTService(AASISTModelAdapter):
    """
    Singleton service managing AASIST inference via ONNX Runtime (FP16/CUDA/CPU)
    with seamless PyTorch fallback, conforming to AASISTModelAdapter.
    """

    _instance: Optional["AASISTService"] = None

    @classmethod
    def get_instance(cls) -> "AASISTService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_loaded(self) -> _LoadStatus:
        return _LoadStatus(1 if (self._is_loaded or self._is_onnx_loaded) else 0)

    @is_loaded.setter
    def is_loaded(self, value: bool) -> None:
        self._is_loaded = bool(value)
