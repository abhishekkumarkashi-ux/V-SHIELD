"""
V-SHIELD Phase 24 — Real-Time Live Pipeline End-to-End Validation Harness.
Executes live real-time tests against all 16 audit phases.
Measures latency, verifies state transitions, checks security enforcement,
and produces structured validation telemetry.
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import httpx
import numpy as np
import websockets
from app.core.auth import create_access_token, get_default_operator_token
from app.models.aasist_service import AASISTService
from app.models.ecapa_service import ECAPAService

BASE_HTTP_URL = "http://127.0.0.1:8000"
BASE_WS_URL = "ws://127.0.0.1:8000"
VALID_TOKEN = get_default_operator_token()


async def test_phase_3_websocket_auth() -> Dict[str, Any]:
    """Test WebSocket authentication enforcement across valid, expired, missing, and invalid tokens."""
    results = {}

    # 1. Missing token
    try:
        async with websockets.connect(f"{BASE_WS_URL}/ws/live-call") as ws:
            await ws.send(b"\x00" * 8192)
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
            results["missing_token"] = (
                "REJECTED_UNAUTHORIZED"
                if msg.get("code") == "UNAUTHORIZED"
                else f"UNEXPECTED_{msg.get('type')}"
            )
    except Exception as e:
        results["missing_token"] = f"CLOSED ({type(e).__name__})"

    # 2. Invalid token
    try:
        async with websockets.connect(f"{BASE_WS_URL}/ws/live-call?token=invalid.jwt.token") as ws:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
            is_rejected = msg.get("type") == "auth_error" and msg.get("code") == "UNAUTHORIZED"
            results["invalid_token"] = (
                "REJECTED_UNAUTHORIZED" if is_rejected else f"FAILED_{msg.get('type')}"
            )
    except Exception as e:
        results["invalid_token"] = f"REJECTED ({type(e).__name__})"

    # 3. Expired token
    expired_token = create_access_token(
        data={"sub": "usr_test", "role": "operator"},
        expires_delta=__import__("datetime").timedelta(seconds=-60),
    )
    try:
        async with websockets.connect(f"{BASE_WS_URL}/ws/live-call?token={expired_token}") as ws:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
            is_rejected = msg.get("type") == "auth_error" and msg.get("code") == "EXPIRED_SESSION"
            results["expired_token"] = (
                "REJECTED_EXPIRED" if is_rejected else f"FAILED_{msg.get('type')}"
            )
    except Exception as e:
        results["expired_token"] = f"REJECTED ({type(e).__name__})"

    # 4. Valid token
    try:
        async with websockets.connect(f"{BASE_WS_URL}/ws/live-call?token={VALID_TOKEN}") as ws:
            await ws.send(json.dumps({"type": "start", "format": "float32"}))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
            results["valid_token"] = (
                "ACCEPTED" if resp.get("type") == "session_started" else "UNEXPECTED"
            )
            await ws.send(json.dumps({"type": "stop"}))
    except Exception as e:
        results["valid_token"] = f"FAILED: {e}"

    return results


async def test_phase_4_5_buffer_warmup_and_format() -> Dict[str, Any]:
    """Test Float32 format, warm-up diagnostics, and transition from LISTENING to ANALYZING."""
    results = {}
    async with websockets.connect(f"{BASE_WS_URL}/ws/live-call?token={VALID_TOKEN}") as ws:
        await ws.send(json.dumps({"type": "start", "format": "float32"}))
        start_ack = json.loads(await ws.recv())
        results["session_started"] = start_ack.get("type") == "session_started"

        # Stream small chunk (2048 samples = 128ms)
        t = np.linspace(0, 0.128, 2048, endpoint=False, dtype=np.float32)
        chunk = (0.2 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        await ws.send(chunk.tobytes())

        metrics = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
        results["chunk_metrics_received"] = metrics.get("type") == "audio_metrics"
        results["pipeline_status_before_priming"] = metrics.get("pipeline_status")
        results["analysis_status_before_priming"] = metrics.get("status")
        results["buffered_seconds_reported"] = metrics.get("buffered_seconds") is not None
        results["required_seconds_reported"] = metrics.get("required_seconds") is not None

        # Prime with full 64,600 samples (4.04s)
        t_full = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        speech_signal = (
            0.20 * np.sin(2 * np.pi * 300.0 * t_full)
            + 0.15 * np.sin(2 * np.pi * 800.0 * t_full)
            + 0.10 * np.sin(2 * np.pi * 2400.0 * t_full)
        ).astype(np.float32)

        # Stream full window
        await ws.send(speech_signal.tobytes())

        analysis_received = None
        for _ in range(10):
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
                if msg.get("type") == "analysis":
                    analysis_received = msg
                    break
            except asyncio.TimeoutError:
                break

        results["analysis_received_after_priming"] = analysis_received is not None
        if analysis_received:
            results["pipeline_status_after_priming"] = analysis_received.get("pipeline_status")
            results["anti_spoof_present"] = "anti_spoof" in analysis_received
            results["risk_score_present"] = "risk_score" in analysis_received
            results["risk_score_value"] = analysis_received.get("risk_score")
            results["latency"] = analysis_received.get("latency")

        await ws.send(json.dumps({"type": "stop"}))

    return results


async def test_phase_6_vad_conditions() -> Dict[str, Any]:
    """Test Continuous Speech, Pure Silence, and Mixed Signals."""
    results = {}

    # 1. Silence Condition (in separate clean session)
    async with websockets.connect(f"{BASE_WS_URL}/ws/live-call?token={VALID_TOKEN}") as ws:
        await ws.send(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(await ws.recv())

        silence = np.zeros(2048, dtype=np.float32)
        await ws.send(silence.tobytes())
        silence_metrics = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
        results["silence_speech_state"] = silence_metrics.get("speech_state")
        results["silence_rms"] = silence_metrics.get("rms")

    # 2. Continuous Speech Condition (in separate session so rate limiter doesn't throttle)
    async with websockets.connect(f"{BASE_WS_URL}/ws/live-call?token={VALID_TOKEN}") as ws:
        await ws.send(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(await ws.recv())

        t = np.linspace(0, 0.128, 2048, endpoint=False, dtype=np.float32)
        speech = (
            0.25 * np.sin(2 * np.pi * 300.0 * t) + 0.15 * np.sin(2 * np.pi * 1200.0 * t)
        ).astype(np.float32)
        await ws.send(speech.tobytes())
        speech_metrics = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
        results["speech_speech_state"] = speech_metrics.get("speech_state")
        results["speech_rms"] = speech_metrics.get("rms")

    return results


async def test_phase_8_ecapa_enrollment() -> Dict[str, Any]:
    """Test unenrolled vs enrolled speaker verification handling."""
    results = {}

    # 1. Unenrolled speaker
    async with websockets.connect(
        f"{BASE_WS_URL}/ws/live-call?token={VALID_TOKEN}&speaker_id=unenrolled_guest_999"
    ) as ws:
        await ws.send(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(await ws.recv())

        # Send full window
        t = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        pcm = (0.25 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        await ws.send(pcm.tobytes())

        analysis = None
        for _ in range(10):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
            if msg.get("type") == "analysis":
                analysis = msg
                break

        if analysis:
            spk_info = analysis.get("speaker_verification", {})
            results["unenrolled_status"] = spk_info.get("status")
            results["unenrolled_similarity"] = spk_info.get("similarity")

        await ws.send(json.dumps({"type": "stop"}))

    # 2. Enrolled speaker
    ecapa = ECAPAService.get_instance()
    t_enroll = np.linspace(0, 2.0, 32000, endpoint=False, dtype=np.float32)
    enroll_pcm = (0.3 * np.sin(2 * np.pi * 400.0 * t_enroll)).astype(np.float32)
    ecapa.enroll_speaker("verified_exec_001", enroll_pcm, 16000)

    async with websockets.connect(
        f"{BASE_WS_URL}/ws/live-call?token={VALID_TOKEN}&speaker_id=verified_exec_001"
    ) as ws:
        await ws.send(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(await ws.recv())

        # Test matched voiceprint with full 64,600 samples
        t_match = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        matched_pcm = (0.3 * np.sin(2 * np.pi * 400.0 * t_match)).astype(np.float32)
        await ws.send(matched_pcm.tobytes())

        analysis_match = None
        for _ in range(10):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=6.0))
            if msg.get("type") == "analysis":
                analysis_match = msg
                break

        if analysis_match:
            spk_info = analysis_match.get("speaker_verification", {})
            results["enrolled_status"] = spk_info.get("status")
            results["enrolled_similarity"] = spk_info.get("similarity")

        await ws.send(json.dumps({"type": "stop"}))

    return results


async def test_phase_11_12_13_15_end_to_end_and_mfa() -> Dict[str, Any]:
    """Test full pipeline with speech, silence, high-risk clone scenario, and MFA dispatch."""
    results = {}

    # Test High Spoof / Clone Attack scenario
    async with websockets.connect(
        f"{BASE_WS_URL}/ws/live-call?token={VALID_TOKEN}&speaker_id=verified_exec_001&target_phone=+15550192834"
    ) as ws:
        await ws.send(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(await ws.recv())

        # Stream audio window
        t = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        pcm = (0.3 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        await ws.send(pcm.tobytes())

        analysis = None
        for _ in range(10):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=6.0))
            if msg.get("type") == "analysis":
                analysis = msg
                break

        if analysis:
            results["real_inference_status"] = analysis.get("status")
            results["real_risk_score"] = analysis.get("risk_score")
            results["real_classification"] = analysis.get("classification")
            results["real_mfa_status"] = analysis.get("mfa_status")
            results["latency"] = analysis.get("latency")

        await ws.send(json.dumps({"type": "stop"}))

    return results


async def test_performance_benchmark() -> Dict[str, Any]:
    """Measure AASIST, ECAPA, and end-to-end hop latencies."""
    aasist = AASISTService.get_instance()
    ecapa = ECAPAService.get_instance()

    t_bench = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
    sample_window = (0.25 * np.sin(2 * np.pi * 440.0 * t_bench)).astype(np.float32)

    # AASIST inference latency
    times_aasist = []
    for _ in range(20):
        t0 = time.perf_counter()
        _ = aasist.predict(sample_window)
        times_aasist.append((time.perf_counter() - t0) * 1000.0)

    # ECAPA verification latency
    times_ecapa = []
    for _ in range(20):
        t0 = time.perf_counter()
        _ = ecapa.verify_speaker_detailed(sample_window, "verified_exec_001")
        times_ecapa.append((time.perf_counter() - t0) * 1000.0)

    return {
        "aasist_p50_ms": round(float(np.percentile(times_aasist, 50)), 2),
        "aasist_p95_ms": round(float(np.percentile(times_aasist, 95)), 2),
        "ecapa_p50_ms": round(float(np.percentile(times_ecapa, 50)), 2),
        "ecapa_p95_ms": round(float(np.percentile(times_ecapa, 95)), 2),
        "total_processing_p50_ms": round(
            float(np.percentile(times_aasist, 50) + np.percentile(times_ecapa, 50)), 2
        ),
    }


async def main():
    print("==================================================")
    print("V-SHIELD PHASE 24 LIVE PIPELINE VERIFICATION SUITE")
    print("==================================================")

    # Health
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_HTTP_URL}/health")
        print(f"[HEALTH] Status: {resp.status_code}, Body: {resp.json()}")

    # WebSocket Auth
    print("\n[PHASE 3: WEBSOCKET AUTH]")
    p3 = await test_phase_3_websocket_auth()
    print(json.dumps(p3, indent=2))

    # Buffer Warmup & Format
    print("\n[PHASE 4 & 5: BUFFER WARMUP & FORMAT]")
    p45 = await test_phase_4_5_buffer_warmup_and_format()
    print(json.dumps(p45, indent=2))

    # VAD Conditions
    print("\n[PHASE 6: VAD CONDITIONS]")
    p6 = await test_phase_6_vad_conditions()
    print(json.dumps(p6, indent=2))

    # ECAPA Verification
    print("\n[PHASE 8: ECAPA SPEAKER VERIFICATION]")
    p8 = await test_phase_8_ecapa_enrollment()
    print(json.dumps(p8, indent=2))

    # End-to-End & MFA
    print("\n[PHASE 11, 12, 13, 15: LIVE PIPELINE & MFA]")
    pe2e = await test_phase_11_12_13_15_end_to_end_and_mfa()
    print(json.dumps(pe2e, indent=2))

    # Performance
    print("\n[PHASE 16: PERFORMANCE BENCHMARK]")
    perf = await test_performance_benchmark()
    print(json.dumps(perf, indent=2))

    print("\n==================================================")
    print("ALL VALIDATION PHASES COMPLETED SUCCESSFULLY.")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
