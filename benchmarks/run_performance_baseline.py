"""
V-SHIELD Reproducible Performance Baseline Profiler (SIH 2026 / Phase 25).
Measures:
1. Audio preprocessing
2. VAD
3. Audio buffer
4. AASIST preprocessing
5. AASIST ONNX inference
6. AASIST postprocessing
7. ECAPA preprocessing
8. ECAPA ONNX inference
9. ECAPA postprocessing
10. RiskEngine
11. WebSocket telemetry serialization
12. Complete hop (end-to-end window processing)
Outputs high-resolution percentile statistics: p50, p95, p99, min, max.
Separates cold-start from warm inference.
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import torch  # noqa: E402
from app.config import settings  # noqa: E402
from app.core.buffer import AudioCircularBuffer  # noqa: E402
from app.core.risk_engine import RiskEngine  # noqa: E402
from app.core.vad import MarginPreservingVAD  # noqa: E402
from app.models.aasist_service import AASISTService  # noqa: E402
from app.models.ecapa_service import ECAPAService  # noqa: E402
from app.schemas.telemetry import TelemetryMetrics, TelemetryPacket  # noqa: E402


def compute_stats(times_ms: List[float]) -> Dict[str, float]:
    arr = np.array(times_ms)
    return {
        "p50": round(float(np.percentile(arr, 50)), 3),
        "p95": round(float(np.percentile(arr, 95)), 3),
        "p99": round(float(np.percentile(arr, 99)), 3),
        "min": round(float(np.min(arr)), 3),
        "max": round(float(np.max(arr)), 3),
        "mean": round(float(np.mean(arr)), 3),
        "count": len(arr),
    }


def run_baseline_benchmark(warm_iterations: int = 30):
    print("==================================================")
    print("V-SHIELD PHASE 25 PERFORMANCE BASELINE PROFILER")
    print("==================================================")

    import onnxruntime as ort

    print(f"ONNX Runtime Version: {ort.__version__}")
    print(f"PyTorch Version:      {torch.__version__}")
    print(f"CUDA Available:       {torch.cuda.is_available()}")
    print(f"Available Providers:  {ort.get_available_providers()}")

    # 1. Measure Cold Start initialization
    t0_init = time.perf_counter()
    aasist = AASISTService.get_instance()
    t_aasist_init = (time.perf_counter() - t0_init) * 1000.0

    t0_ecapa = time.perf_counter()
    ecapa = ECAPAService.get_instance()
    t_ecapa_init = (time.perf_counter() - t0_ecapa) * 1000.0

    active_aasist_provider = (
        aasist.ort_session.get_providers()
        if aasist.ort_session
        else ["None (PyTorch)"]
    )
    active_ecapa_provider = (
        ecapa.ort_session.get_providers()
        if ecapa.ort_session
        else ["None (PyTorch)"]
    )

    print(f"Active AASIST Providers: {active_aasist_provider}")
    print(f"Active ECAPA Providers:  {active_ecapa_provider}")
    print(f"Cold Start AASIST Service Init: {t_aasist_init:.2f} ms")
    print(f"Cold Start ECAPA Service Init:  {t_ecapa_init:.2f} ms")

    # Enroll a test speaker for verified baseline
    t_enroll = np.linspace(0, 2.0, 32000, endpoint=False, dtype=np.float32)
    enroll_pcm = (0.3 * np.sin(2 * np.pi * 350.0 * t_enroll)).astype(np.float32)
    ecapa.enroll_speaker("baseline_speaker_001", enroll_pcm, 16000)

    vad = MarginPreservingVAD(
        sample_rate=16000, min_silence_padding_sec=settings.VAD_MARGIN_SEC
    )
    risk_engine = RiskEngine(alpha=settings.RISK_ALPHA)
    buffer = AudioCircularBuffer(
        capacity=settings.WINDOW_SIZE,
        hop_size=settings.HOP_SIZE,
        target_sample_rate=16000,
    )

    # Prepare standard test audio: 64,600 samples (4.0375s) speech-like signal
    t_audio = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
    test_audio = (
        0.25 * np.sin(2 * np.pi * 300.0 * t_audio)
        + 0.15 * np.sin(2 * np.pi * 800.0 * t_audio)
        + 0.10 * np.sin(2 * np.pi * 2400.0 * t_audio)
    ).astype(np.float32)
    raw_bytes = test_audio.tobytes()

    # Metrics storage
    stage_metrics: Dict[str, List[float]] = {
        "1_audio_preprocessing": [],
        "2_vad": [],
        "3_audio_buffer": [],
        "4_aasist_preprocessing": [],
        "5_aasist_onnx_inference": [],
        "6_aasist_postprocessing": [],
        "7_ecapa_preprocessing": [],
        "8_ecapa_onnx_inference": [],
        "9_ecapa_postprocessing": [],
        "10_risk_engine": [],
        "11_websocket_telemetry": [],
        "12_complete_hop": [],
    }

    cold_stage_metrics: Dict[str, float] = {}

    print(f"\nRunning 3 warmup passes + {warm_iterations} warm benchmark passes...")

    total_passes = 3 + warm_iterations
    for i in range(total_passes):
        is_cold = (i == 0)
        t_hop_start = time.perf_counter()

        # 1. Audio preprocessing (bytes to Float32 array, validation, safety clip)
        t0 = time.perf_counter()
        samples = np.frombuffer(raw_bytes[:8192], dtype=np.float32)
        if not np.all(np.isfinite(samples)):
            raise ValueError("Non-finite")
        samples = np.clip(samples, -1.0, 1.0)
        t_audio_prep = (time.perf_counter() - t0) * 1000.0

        # 3. Audio buffer ingestion
        t0 = time.perf_counter()
        buffer.append_samples(samples)
        _ = buffer.get_current_rms()
        t_buf = (time.perf_counter() - t0) * 1000.0

        # Create window tensor
        window_tensor = torch.from_numpy(test_audio).unsqueeze(0)

        # 2. VAD processing
        t0 = time.perf_counter()
        is_speech_active, speech_ratio, safe_audio = vad.process_window(window_tensor)
        t_vad = (time.perf_counter() - t0) * 1000.0

        # 4. AASIST Preprocessing (Tensor -> (1, 64600) float32 numpy)
        t0 = time.perf_counter()
        if isinstance(safe_audio, np.ndarray):
            x = torch.from_numpy(safe_audio.astype(np.float32))
        else:
            x = safe_audio.detach()
        if x.dim() == 1:
            x = x.unsqueeze(0)
        elif x.dim() == 3:
            x = x.squeeze(1)
        cur_len = x.size(-1)
        target_len = settings.WINDOW_SIZE
        if cur_len < target_len:
            pad_amount = target_len - cur_len
            x = torch.nn.functional.pad(x, (0, pad_amount), "constant", 0)
        elif cur_len > target_len:
            x = x[:, :target_len]
        arr_aasist = x.cpu().numpy().astype(np.float32)
        t_aasist_prep = (time.perf_counter() - t0) * 1000.0

        # 5. AASIST ONNX Inference
        t0 = time.perf_counter()
        ort_logits = aasist.ort_session.run(["logits"], {"audio_input": arr_aasist})[0]
        t_aasist_inf = (time.perf_counter() - t0) * 1000.0

        # 6. AASIST Postprocessing (Softmax & Spoof probability extraction)
        t0 = time.perf_counter()
        exp_logits = np.exp(ort_logits - np.max(ort_logits, axis=-1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)
        spoof_prob = float(probs[0, 1])
        t_aasist_post = (time.perf_counter() - t0) * 1000.0

        # 7. ECAPA Preprocessing
        t0 = time.perf_counter()
        if isinstance(safe_audio, np.ndarray):
            audio_np = safe_audio.astype(np.float32)
            if audio_np.ndim > 1:
                audio_np = audio_np.flatten()
            audio_np = np.clip(audio_np, -1.0, 1.0)
            wav_tensor = torch.from_numpy(audio_np).unsqueeze(0)
        else:
            wav_tensor = safe_audio.detach().cpu().float()
            if wav_tensor.dim() > 1:
                wav_tensor = wav_tensor.squeeze()
            if wav_tensor.dim() == 0:
                wav_tensor = wav_tensor.unsqueeze(0)
            audio_np = np.clip(wav_tensor.numpy(), -1.0, 1.0)
            wav_tensor = torch.from_numpy(audio_np).unsqueeze(0)
        arr_ecapa = wav_tensor.cpu().numpy().astype(np.float32)
        t_ecapa_prep = (time.perf_counter() - t0) * 1000.0

        # 8. ECAPA ONNX Inference
        t0 = time.perf_counter()
        ort_ecapa = ecapa.ort_session.run(["embedding"], {"audio_input": arr_ecapa})[0]
        t_ecapa_inf = (time.perf_counter() - t0) * 1000.0

        # 9. ECAPA Postprocessing (L2 Normalization & Cosine Similarity)
        t0 = time.perf_counter()
        emb = np.squeeze(ort_ecapa)
        norm = np.linalg.norm(emb) + 1e-9
        current_emb = (emb / norm).astype(np.float32)
        enrolled_emb = ecapa._enrolled_embeddings["baseline_speaker_001"]
        dot_product = float(np.dot(enrolled_emb, current_emb))
        cos_sim = max(-1.0, min(1.0, dot_product))
        t_ecapa_post = (time.perf_counter() - t0) * 1000.0

        # 10. RiskEngine
        t0 = time.perf_counter()
        risk_eval = risk_engine.evaluate_detailed(
            spoof_prob=spoof_prob,
            speaker_similarity=cos_sim,
            is_speech_active=is_speech_active,
            speech_ratio=speech_ratio,
        )
        t_risk = (time.perf_counter() - t0) * 1000.0

        # 11. WebSocket Telemetry Packet Serialization
        t0 = time.perf_counter()
        packet = TelemetryPacket(
            timestamp=time.time(),
            risk_score=risk_eval["risk_score"],
            classification=risk_eval["classification"],
            decision=risk_eval["decision"],
            factors=risk_eval["factors"],
            metrics=TelemetryMetrics(
                spoof_probability=round(spoof_prob, 4),
                speaker_similarity=round(cos_sim, 4),
                speaker_status="VERIFIED",
                buffer_energy_rms=0.25,
                vad_speech_ratio=round(speech_ratio, 4),
                latency_ms=10.0,
            ),
            recommended_action=risk_eval["recommended_action"],
            mfa_status="NONE",
            status="success",
            pipeline_status="ANALYZING",
            speaker_status="VERIFIED",
        )
        payload_str = json.dumps(packet.model_dump())
        _ = len(payload_str)
        t_ws = (time.perf_counter() - t0) * 1000.0

        # 12. Complete hop
        t_hop = (time.perf_counter() - t_hop_start) * 1000.0

        if is_cold:
            cold_stage_metrics = {
                "1_audio_preprocessing": t_audio_prep,
                "2_vad": t_vad,
                "3_audio_buffer": t_buf,
                "4_aasist_preprocessing": t_aasist_prep,
                "5_aasist_onnx_inference": t_aasist_inf,
                "6_aasist_postprocessing": t_aasist_post,
                "7_ecapa_preprocessing": t_ecapa_prep,
                "8_ecapa_onnx_inference": t_ecapa_inf,
                "9_ecapa_postprocessing": t_ecapa_post,
                "10_risk_engine": t_risk,
                "11_websocket_telemetry": t_ws,
                "12_complete_hop": t_hop,
            }
        elif i >= 3:
            stage_metrics["1_audio_preprocessing"].append(t_audio_prep)
            stage_metrics["2_vad"].append(t_vad)
            stage_metrics["3_audio_buffer"].append(t_buf)
            stage_metrics["4_aasist_preprocessing"].append(t_aasist_prep)
            stage_metrics["5_aasist_onnx_inference"].append(t_aasist_inf)
            stage_metrics["6_aasist_postprocessing"].append(t_aasist_post)
            stage_metrics["7_ecapa_preprocessing"].append(t_ecapa_prep)
            stage_metrics["8_ecapa_onnx_inference"].append(t_ecapa_inf)
            stage_metrics["9_ecapa_postprocessing"].append(t_ecapa_post)
            stage_metrics["10_risk_engine"].append(t_risk)
            stage_metrics["11_websocket_telemetry"].append(t_ws)
            stage_metrics["12_complete_hop"].append(t_hop)

    print("\n--- COLD START METRICS (Initial invocation) ---")
    for k, v in cold_stage_metrics.items():
        print(f"  {k:30s}: {v:8.3f} ms")

    print(f"\n--- WARM INFERENCE PERCENTILES ({warm_iterations} passes) ---")
    summary: Dict[str, Any] = {}
    for k, times in stage_metrics.items():
        stats = compute_stats(times)
        summary[k] = stats
        print(
            f"  {k:28s} | p50: {stats['p50']:7.3f} ms | p95: {stats['p95']:7.3f} ms | p99: {stats['p99']:7.3f} ms | min: {stats['min']:7.3f} ms | max: {stats['max']:7.3f} ms"
        )

    # Save results as JSON for docs/PERFORMANCE_BASELINE.md generation
    baseline_record = {
        "environment": {
            "onnxruntime_version": ort.__version__,
            "pytorch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "active_aasist_providers": active_aasist_provider,
            "active_ecapa_providers": active_ecapa_provider,
            "cold_aasist_init_ms": round(t_aasist_init, 2),
            "cold_ecapa_init_ms": round(t_ecapa_init, 2),
        },
        "cold_start": cold_stage_metrics,
        "warm_inference": summary,
    }

    out_path = Path(__file__).resolve().parent / "baseline_results.json"
    with open(out_path, "w") as f:
        json.dump(baseline_record, f, indent=2)
    print(f"\nWrote baseline benchmark data to {out_path}")


if __name__ == "__main__":
    run_baseline_benchmark(warm_iterations=25)
