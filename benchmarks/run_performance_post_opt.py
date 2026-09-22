"""
V-SHIELD Post-Optimization Performance Profiler (SIH 2026 / Phase 25).
Measures:
1. Audio preprocessing
2. VAD
3. Audio buffer
4. AASIST preprocessing (optimized zero-copy)
5. AASIST ONNX inference (tuned multi-threading)
6. AASIST postprocessing
7. ECAPA preprocessing (optimized zero-copy)
8. ECAPA ONNX inference (tuned multi-threading)
9. ECAPA postprocessing
10. RiskEngine
11. WebSocket telemetry serialization (with PerformanceTelemetry)
12. Parallel Independent Model Hop (AASIST || ECAPA)
13. Fast Hop (AASIST with cached ECAPA)
14. Real-world Scheduled Cadence Hop (1 parallel + 3 cached per 2-second speech cycle)
Outputs high-resolution percentile statistics: p50, p95, p99, min, max.
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

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
from app.schemas.telemetry import PerformanceTelemetry, TelemetryMetrics, TelemetryPacket  # noqa: E402


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


async def run_post_opt_benchmark(warm_iterations: int = 30):
    print("==================================================")
    print("V-SHIELD PHASE 25 POST-OPTIMIZATION PROFILER")
    print("==================================================")

    aasist = AASISTService.get_instance()
    ecapa = ECAPAService.get_instance()
    vad = MarginPreservingVAD(sample_rate=16000, min_silence_padding_sec=0.3)
    risk_engine = RiskEngine(alpha=0.7)
    buffer = AudioCircularBuffer(capacity=64600, hop_size=8000, target_sample_rate=16000)

    # Enroll baseline speaker
    t_en = np.linspace(0, 2.0, 32000, endpoint=False, dtype=np.float32)
    enroll_pcm = (0.28 * np.sin(2 * np.pi * 380.0 * t_en)).astype(np.float32)
    ecapa.enroll_speaker("baseline_speaker_001", enroll_pcm, 16000)

    # Create 500ms audio chunk (8,000 samples @ 16 kHz)
    t_chunk = np.linspace(0, 0.5, 8000, endpoint=False, dtype=np.float32)
    audio_chunk = (0.35 * np.sin(2 * np.pi * 440.0 * t_chunk) + 0.15 * np.sin(2 * np.pi * 880.0 * t_chunk)).astype(np.float32)

    # Prime buffer with 64,600 samples
    for _ in range(9):
        buffer.append_samples(audio_chunk)

    print(f"Active ONNX Providers: AASIST={aasist.active_provider}, ECAPA={ecapa.active_provider}")
    print(f"Active Device: {aasist.inference_device}")

    # Warmup runs
    print("\nWarming up models (10 iterations)...")
    for _ in range(10):
        windows = list(buffer.extract_all_ready_windows())
        if windows:
            w = windows[0]
            _, _, safe = vad.process_window(w)
            aasist.predict_spoof_prob(safe)
            ecapa.extract_embedding(safe)
        buffer.append_samples(audio_chunk)

    stage_timings: Dict[str, List[float]] = {
        "audio_preprocessing": [],
        "vad": [],
        "audio_buffer": [],
        "aasist_preprocessing": [],
        "aasist_onnx_inference": [],
        "aasist_postprocessing": [],
        "ecapa_preprocessing": [],
        "ecapa_onnx_inference": [],
        "ecapa_postprocessing": [],
        "risk_engine": [],
        "websocket_telemetry": [],
        "parallel_models_hop": [],
        "fast_cached_hop": [],
        "complete_scheduled_hop": [],
    }

    print(f"\nRunning {warm_iterations} measured iterations...")
    for it in range(warm_iterations):
        # 1. Audio Preprocessing
        t0 = time.perf_counter()
        raw_bytes = audio_chunk.tobytes()
        audio_samples = np.frombuffer(raw_bytes, dtype=np.float32).copy()
        audio_samples = np.clip(audio_samples, -1.0, 1.0)
        t_audio_prep = (time.perf_counter() - t0) * 1000.0

        # 2. Audio buffer ingestion
        t0 = time.perf_counter()
        buffer.append_samples(audio_samples)
        windows = list(buffer.extract_all_ready_windows())
        t_buffer = (time.perf_counter() - t0) * 1000.0

        if not windows:
            continue
        window_tensor = windows[0]

        # 3. VAD
        t0 = time.perf_counter()
        is_speech_active, speech_ratio, safe_audio = vad.process_window(window_tensor)
        t_vad = (time.perf_counter() - t0) * 1000.0

        # 4. AASIST Preprocessing (optimized zero-copy)
        t0 = time.perf_counter()
        if isinstance(safe_audio, torch.Tensor):
            audio_flat = safe_audio.detach().cpu().numpy().flatten()
        else:
            audio_flat = np.asarray(safe_audio, dtype=np.float32).flatten()
        arr_aasist = np.expand_dims(audio_flat, axis=0)
        t_aasist_prep = (time.perf_counter() - t0) * 1000.0

        # 5. AASIST ONNX Inference
        t0 = time.perf_counter()
        ort_logits = aasist.ort_session.run(["logits"], {"audio_input": arr_aasist})[0]
        t_aasist_inf = (time.perf_counter() - t0) * 1000.0

        # 6. AASIST Postprocessing
        t0 = time.perf_counter()
        exp_logits = np.exp(ort_logits - np.max(ort_logits, axis=-1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)
        spoof_prob = float(probs[0, 1])
        t_aasist_post = (time.perf_counter() - t0) * 1000.0

        # 7. ECAPA Preprocessing (optimized zero-copy)
        t0 = time.perf_counter()
        arr_ecapa = np.expand_dims(audio_flat, axis=0)
        t_ecapa_prep = (time.perf_counter() - t0) * 1000.0

        # 8. ECAPA ONNX Inference
        t0 = time.perf_counter()
        ort_ecapa = ecapa.ort_session.run(["embedding"], {"audio_input": arr_ecapa})[0]
        t_ecapa_inf = (time.perf_counter() - t0) * 1000.0

        # 9. ECAPA Postprocessing
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

        # 11. WebSocket Telemetry Serialization
        t0 = time.perf_counter()
        perf_telemetry = PerformanceTelemetry(
            preprocess_ms=t_vad,
            aasist_ms=t_aasist_inf,
            ecapa_ms=t_ecapa_inf,
            risk_engine_ms=t_risk,
            total_ms=t_aasist_inf + t_ecapa_inf,
            provider=aasist.active_provider,
            device=aasist.inference_device,
            performance_status="DEGRADED" if t_aasist_inf > 500 else "OPTIMAL",
            hop_budget_ms=500.0,
            actual_p50_ms=t_aasist_inf,
        )
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
            performance=perf_telemetry,
        )
        _ = json.dumps(packet.model_dump())
        t_ws = (time.perf_counter() - t0) * 1000.0

        # 12. Parallel Independent Model Hop (AASIST || ECAPA)
        t0 = time.perf_counter()
        _ = vad.process_window(window_tensor)
        (res_aasist, res_ecapa) = await asyncio.gather(
            asyncio.to_thread(aasist.predict, safe_audio),
            asyncio.to_thread(ecapa.verify_speaker_detailed, safe_audio, "baseline_speaker_001"),
        )
        _ = risk_engine.evaluate_detailed(
            spoof_prob=res_aasist[1],
            speaker_similarity=res_ecapa["similarity"],
            is_speech_active=is_speech_active,
            speech_ratio=speech_ratio,
        )
        t_parallel_hop = (time.perf_counter() - t0) * 1000.0

        # 13. Fast Cached Hop (AASIST with cached ECAPA)
        t0 = time.perf_counter()
        _ = vad.process_window(window_tensor)
        res_aasist = await asyncio.to_thread(aasist.predict, safe_audio)
        _ = risk_engine.evaluate_detailed(
            spoof_prob=res_aasist[1],
            speaker_similarity=cos_sim,  # cached
            is_speech_active=is_speech_active,
            speech_ratio=speech_ratio,
        )
        t_fast_hop = (time.perf_counter() - t0) * 1000.0

        # 14. Real-world Scheduled Cadence Hop (1 in 4 parallel, 3 in 4 fast)
        t_scheduled_hop = t_parallel_hop if (it % 4 == 0) else t_fast_hop

        stage_timings["audio_preprocessing"].append(t_audio_prep)
        stage_timings["vad"].append(t_vad)
        stage_timings["audio_buffer"].append(t_buffer)
        stage_timings["aasist_preprocessing"].append(t_aasist_prep)
        stage_timings["aasist_onnx_inference"].append(t_aasist_inf)
        stage_timings["aasist_postprocessing"].append(t_aasist_post)
        stage_timings["ecapa_preprocessing"].append(t_ecapa_prep)
        stage_timings["ecapa_onnx_inference"].append(t_ecapa_inf)
        stage_timings["ecapa_postprocessing"].append(t_ecapa_post)
        stage_timings["risk_engine"].append(t_risk)
        stage_timings["websocket_telemetry"].append(t_ws)
        stage_timings["parallel_models_hop"].append(t_parallel_hop)
        stage_timings["fast_cached_hop"].append(t_fast_hop)
        stage_timings["complete_scheduled_hop"].append(t_scheduled_hop)

    # Compute and print results
    results = {}
    print("\n==================================================")
    print("STAGE LATENCY BENCHMARK RESULTS (WARM INFERENCE)")
    print("==================================================")
    print(f"{'Component':<32} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'p99 (ms)':<10} | {'min':<8} | {'max':<8}")
    print("-" * 90)

    for stage, times in stage_timings.items():
        stats = compute_stats(times)
        results[stage] = stats
        print(f"{stage:<32} | {stats['p50']:<10.3f} | {stats['p95']:<10.3f} | {stats['p99']:<10.3f} | {stats['min']:<8.3f} | {stats['max']:<8.3f}")

    results_path = Path(__file__).resolve().parent / "post_opt_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved post-optimization benchmark results to: {results_path}")
    return results


if __name__ == "__main__":
    asyncio.run(run_post_opt_benchmark(warm_iterations=30))
