"""
AASIST Inference Service (SIH 2026).
Accelerated via ONNX Runtime FP16 with CUDA / CPU execution providers.
Provides predict_spoof_prob() with automatic PyTorch fallback.
"""

import os
import urllib.request
from typing import Optional, Tuple

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

OFFICIAL_AASIST_WEIGHTS_URL = "https://github.com/clovaai/aasist/raw/main/models/weights/AASIST.pth"


class AASISTService:
    """
    Singleton service managing AASIST inference via ONNX Runtime (FP16/CUDA/CPU)
    with seamless PyTorch fallback.
    """

    _instance: Optional["AASISTService"] = None

    def __init__(
        self,
        weights_path: Optional[str] = None,
        onnx_path: Optional[str] = None,
        device: Optional[str] = None,
    ) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.weights_path = weights_path or str(settings.AASIST_WEIGHTS_PATH)
        self.onnx_path = onnx_path or str(settings.AASIST_ONNX_PATH)
        self.model: Optional[AASISTModel] = None
        self.ort_session: Optional["ort.InferenceSession"] = None
        self.is_onnx_loaded: bool = False
        self.is_loaded: bool = False

        self._initialize_onnx()
        self._initialize_model()

    @classmethod
    def get_instance(cls) -> "AASISTService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _initialize_onnx(self) -> None:
        """Initializes ONNX Runtime session with CUDA and CPU providers."""
        if not HAS_ORT or not os.path.exists(self.onnx_path):
            print(
                f"[AASISTService] ONNX model not found at {self.onnx_path}. Using PyTorch fallback."
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
                f"[AASISTService] Loading ONNX model from {self.onnx_path} with providers: {providers}"
            )
            self.ort_session = ort.InferenceSession(self.onnx_path, providers=providers)
            self.is_onnx_loaded = True
            print(
                f"[AASISTService] ONNX Runtime session active using: {self.ort_session.get_providers()[0]}"
            )
        except Exception as err:
            print(
                f"[AASISTService] ONNX session initialization failed ({err}). Falling back to PyTorch."
            )
            self.is_onnx_loaded = False

    def _ensure_weights(self) -> str:
        """Verifies checkpoint exists, otherwise downloads from official repo."""
        os.makedirs(os.path.dirname(self.weights_path), exist_ok=True)
        if os.path.exists(self.weights_path) and os.path.getsize(self.weights_path) > 100000:
            return self.weights_path

        print(
            f"[AASISTService] Weights not found at {self.weights_path}. Downloading from official source..."
        )
        try:
            req = urllib.request.Request(
                OFFICIAL_AASIST_WEIGHTS_URL, headers={"User-Agent": "V-SHIELD-Client/1.0"}
            )
            with urllib.request.urlopen(req) as response, open(self.weights_path, "wb") as out_file:
                out_file.write(response.read())
            print(f"[AASISTService] AASIST.pth successfully downloaded to {self.weights_path}")
        except Exception as exc:
            print(
                f"[AASISTService] Warning: Could not download weights from web ({exc}). Running with initialized weights."
            )
        return self.weights_path

    def _initialize_model(self) -> None:
        """Instantiates PyTorch AASIST model for fallback or standalone use."""
        try:
            self.model = AASISTModel(DEFAULT_AASIST_CONFIG)
            ckpt_path = self._ensure_weights()

            if os.path.exists(ckpt_path) and os.path.getsize(ckpt_path) > 100000:
                state_dict = torch.load(ckpt_path, map_location=self.device, weights_only=False)
                self.model.load_state_dict(state_dict, strict=False)
                print(f"[AASISTService] Loaded PyTorch weights from {ckpt_path} on {self.device}")

            self.model.to(self.device)
            self.model.eval()
            self.is_loaded = True
        except Exception as err:
            print(f"[AASISTService] Error during PyTorch model initialization: {err}")
            if self.model is not None:
                self.model.to(self.device)
                self.model.eval()
                self.is_loaded = True

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

        if self.is_onnx_loaded and self.ort_session is not None:
            try:
                logits = self.ort_session.run(["logits"], {"audio_input": arr})[0]
                exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
                probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)
                return float(probs[0, 1])
            except Exception as e:
                print(f"[AASISTService] ONNX execution error ({e}). Using PyTorch fallback.")

        # PyTorch fallback
        tensor = torch.from_numpy(arr)
        _, spoof_prob = self.predict(tensor)
        return spoof_prob

    def predict(self, audio_tensor: torch.Tensor) -> Tuple[torch.Tensor, float]:
        """
        Inference on audio tensor under torch.no_grad().
        Routes through ONNX Runtime if available, otherwise PyTorch model.
        Returns:
            logits (torch.Tensor): [bona_fide_score, spoof_score]
            spoof_probability (float): Softmax(logits)[1]
        """
        # Format input tensor to exactly (1, 64600)
        x = audio_tensor.detach()
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
        if self.is_onnx_loaded and self.ort_session is not None:
            try:
                arr = x.cpu().numpy().astype(np.float32)
                ort_logits = self.ort_session.run(["logits"], {"audio_input": arr})[0]
                exp_logits = np.exp(ort_logits - np.max(ort_logits, axis=-1, keepdims=True))
                probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)
                spoof_prob = float(probs[0, 1])
                return torch.from_numpy(ort_logits), spoof_prob
            except Exception as e:
                print(
                    f"[AASISTService] ONNX Runtime error during predict ({e}). Falling back to PyTorch."
                )

        # 2. PyTorch Native Fallback
        if not self.is_loaded or self.model is None:
            self._initialize_model()

        x = x.to(self.device, dtype=torch.float32)
        with torch.no_grad():
            _, logits = self.model(x)
            probs = F.softmax(logits, dim=-1)
            spoof_prob = float(probs[0, 1].item())

        return logits.cpu(), spoof_prob
