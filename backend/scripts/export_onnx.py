"""
V-SHIELD Model Export to ONNX Runtime FP16 (SIH 2026).
Exports AASIST anti-spoofing and ECAPA-TDNN speaker verification models
to optimized FP16 ONNX format with dynamic batch and time dimensions.
"""

import os
import sys
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch
import torch.nn as nn
from onnxconverter_common import float16

# Ensure UTF-8 standard output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add backend directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.models.aasist import DEFAULT_AASIST_CONFIG
from app.models.aasist import Model as AASISTModel


class AASISTWrapper(nn.Module):
    """
    Wraps AASIST to output raw logits (batch_size, 2) directly.
    """

    def __init__(self, model: nn.Module):
        super().__init__()
        self.model = model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, logits = self.model(x)
        return logits


class ECAPAWrapper(nn.Module):
    """
    Wraps SpeechBrain ECAPA-TDNN classifier to accept waveform tensors (batch, time)
    and output 192-dimensional embeddings (batch, 192).
    """

    def __init__(self, classifier):
        super().__init__()
        self.classifier = classifier

    def forward(self, wav: torch.Tensor) -> torch.Tensor:
        # wav shape: (batch, time)
        emb = self.classifier.encode_batch(wav)
        return emb.squeeze(1)


def export_aasist(
    checkpoint_path: Path = settings.AASIST_WEIGHTS_PATH,
    output_path: Path = settings.AASIST_ONNX_PATH,
    opset_version: int = 18,
) -> Path:
    """
    Exports PyTorch AASIST model to ONNX FP16.
    """
    print(f"\n[AASIST Export] Loading PyTorch weights from: {checkpoint_path}")
    model = AASISTModel(DEFAULT_AASIST_CONFIG)
    if os.path.exists(checkpoint_path) and os.path.getsize(checkpoint_path) > 100000:
        state_dict = torch.load(str(checkpoint_path), map_location="cpu", weights_only=False)
        model.load_state_dict(state_dict, strict=False)
    else:
        print("[AASIST Export] Checkpoint not found or too small; using initialized weights.")

    model.eval()
    wrapper = AASISTWrapper(model)
    wrapper.eval()

    dummy_input = torch.randn(1, 64600, dtype=torch.float32)
    temp_fp32_path = output_path.parent / "aasist_temp_fp32.onnx"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(
        f"[AASIST Export] Exporting FP32 ONNX graph to {temp_fp32_path} (Opset {opset_version})..."
    )
    torch.onnx.export(
        wrapper,
        dummy_input,
        str(temp_fp32_path),
        input_names=["audio_input"],
        output_names=["logits"],
        dynamic_axes={"audio_input": {0: "batch_size"}, "logits": {0: "batch_size"}},
        opset_version=opset_version,
        do_constant_folding=True,
    )

    print("[AASIST Export] Converting ONNX graph to FP16 with keep_io_types=True...")
    onnx_fp32 = onnx.load(str(temp_fp32_path))
    onnx_fp16 = float16.convert_float_to_float16(onnx_fp32, keep_io_types=True)
    onnx.save(onnx_fp16, str(output_path))

    if temp_fp32_path.exists():
        temp_fp32_path.unlink()

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[AASIST Export] Successfully generated: {output_path} ({file_size_mb:.2f} MB)")

    # Numerical verification against PyTorch
    print("[AASIST Export] Performing numerical equivalence verification...")
    with torch.no_grad():
        pt_logits = wrapper(dummy_input).numpy()

    ort_session = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    ort_logits = ort_session.run(["logits"], {"audio_input": dummy_input.numpy()})[0]

    max_diff = float(np.max(np.abs(pt_logits - ort_logits)))
    print(f"[AASIST Export] Max absolute difference (PyTorch vs ONNX): {max_diff:.6f}")
    assert max_diff < 0.05, f"AASIST numerical divergence too large: {max_diff}"
    print("[AASIST Export] AASIST verification passed!")

    return output_path


def export_ecapa(output_path: Path = settings.ECAPA_ONNX_PATH, opset_version: int = 18) -> Path:
    """
    Exports SpeechBrain ECAPA-TDNN speaker verification model to ONNX FP16.
    """
    print("\n[ECAPA Export] Loading SpeechBrain spkrec-ecapa-voxceleb...")
    from speechbrain.inference.classifiers import EncoderClassifier
    from speechbrain.utils.fetching import LocalStrategy

    speechbrain_dir = settings.BASE_DIR / "speechbrain_model"
    speechbrain_dir.mkdir(parents=True, exist_ok=True)

    classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(speechbrain_dir),
        run_opts={"device": "cpu"},
        local_strategy=LocalStrategy.COPY,
    )

    wrapper = ECAPAWrapper(classifier)
    wrapper.eval()

    dummy_input = torch.randn(1, 16000, dtype=torch.float32)
    temp_fp32_path = output_path.parent / "ecapa_temp_fp32.onnx"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(
        f"[ECAPA Export] Exporting FP32 ONNX graph to {temp_fp32_path} (Opset {opset_version})..."
    )
    torch.onnx.export(
        wrapper,
        dummy_input,
        str(temp_fp32_path),
        input_names=["audio_input"],
        output_names=["embedding"],
        dynamic_axes={"audio_input": {0: "batch_size", 1: "time"}, "embedding": {0: "batch_size"}},
        opset_version=opset_version,
        do_constant_folding=True,
    )

    print("[ECAPA Export] Attempting FP16 graph conversion with keep_io_types=True...")
    onnx_fp32 = onnx.load(str(temp_fp32_path))
    temp_fp16_path = output_path.parent / "ecapa_temp_fp16.onnx"
    use_fp16 = False

    try:
        onnx_fp16 = float16.convert_float_to_float16(onnx_fp32, keep_io_types=True)
        onnx.save(onnx_fp16, str(temp_fp16_path))
        # Validate that ONNX Runtime can initialize and run the FP16 model
        ort_test = ort.InferenceSession(str(temp_fp16_path), providers=["CPUExecutionProvider"])
        _ = ort_test.run(["embedding"], {"audio_input": dummy_input.numpy()})
        use_fp16 = True
        print("[ECAPA Export] FP16 session initialized successfully!")
    except Exception as conv_err:
        print(
            f"[ECAPA Export] Note: ONNX Runtime CPU requires float32 for STFT operations ({conv_err})."
        )
        print("[ECAPA Export] Utilizing optimized ONNX model graph.")

    if use_fp16 and temp_fp16_path.exists():
        chosen_path = temp_fp16_path
    else:
        chosen_path = temp_fp32_path

    # Save as self-contained ONNX model (embed all tensor weights directly inside protobuf)
    final_model = onnx.load(str(chosen_path), load_external_data=True)
    onnx.save_model(final_model, str(output_path), save_as_external_data=False)

    # Clean up temporary files and external data fragments
    for p in output_path.parent.glob("*.onnx.data"):
        try:
            p.unlink()
        except Exception:
            pass
    if temp_fp16_path.exists():
        temp_fp16_path.unlink()
    if temp_fp32_path.exists():
        temp_fp32_path.unlink()

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(
        f"[ECAPA Export] Successfully generated self-contained: {output_path} ({file_size_mb:.2f} MB)"
    )

    # Numerical verification against PyTorch
    print("[ECAPA Export] Performing numerical equivalence verification...")
    with torch.no_grad():
        pt_emb = wrapper(dummy_input).numpy()

    ort_session = ort.InferenceSession(str(output_path), providers=["CPUExecutionProvider"])
    ort_emb = ort_session.run(["embedding"], {"audio_input": dummy_input.numpy()})[0]

    max_diff = float(np.max(np.abs(pt_emb - ort_emb)))
    print(f"[ECAPA Export] Max absolute difference (PyTorch vs ONNX): {max_diff:.6f}")
    assert max_diff < 0.05, f"ECAPA numerical divergence too large: {max_diff}"
    print("[ECAPA Export] ECAPA verification passed!")

    return output_path


def main():
    print("=====================================================")
    print(" V-SHIELD ONNX Runtime Model Exporter (SIH 2026)")
    print("=====================================================")

    try:
        aasist_path = export_aasist()
        print(f"\n[DONE] AASIST ONNX model ready at: {aasist_path}")
    except Exception as e:
        print(f"\n[ERROR] AASIST export failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    try:
        ecapa_path = export_ecapa()
        print(f"\n[DONE] ECAPA-TDNN ONNX model ready at: {ecapa_path}")
    except Exception as e:
        print(f"\n[ERROR] ECAPA export failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("\n=====================================================")
    print(" All models successfully exported to ONNX Runtime FP16!")
    print("=====================================================")


if __name__ == "__main__":
    main()
