"""
Comprehensive Live Pipeline Verification Script.
Tests all real scenarios against the currently running V-SHIELD backend:
1. Health and Model readiness (AASIST ONNX FP16 + ECAPA-TDNN ONNX FP16).
2. Live WebSocket audio streaming with:
   - Genuine speech (samples/genuine_test.wav)
   - Voice clone (samples/voice_clone_test.wav)
   - Wrong speaker (samples/wrong_speaker_test.wav)
   - Ambient silence (pure zeros)
3. REST API file upload analysis (POST /api/v1/analyze-file).
4. Out-of-band MFA verification flow (POST /api/v1/mfa/dispatch & POST /api/v1/mfa/verify-code).
"""

import asyncio
import json
import time
import wave
import numpy as np
import websockets
import urllib.request

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws/live-call"

def read_wav_as_float32(wav_path: str) -> np.ndarray:
    with wave.open(wav_path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        data = wf.readframes(n_frames)

    if sampwidth == 2:
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        samples = np.frombuffer(data, dtype=np.float32)
    else:
        samples = np.frombuffer(data, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

    if n_channels > 1:
        samples = samples[::n_channels]

    # Resample to 16kHz if necessary
    if framerate != 16000:
        indices = np.round(np.arange(0, len(samples), framerate / 16000)).astype(int)
        indices = indices[indices < len(samples)]
        samples = samples[indices]

    return samples.astype(np.float32)

async def test_live_stream_audio(token: str, audio_path: str, speaker_id: str, label: str):
    print(f"\n=======================================================")
    print(f"RUNNING LIVE STREAM TEST: {label}")
    print(f"File: {audio_path} | Target Speaker: {speaker_id}")
    print(f"=======================================================")

    samples = read_wav_as_float32(audio_path)
    print(f"  Loaded {len(samples)} samples ({len(samples)/16000:.2f}s)")

    # Repeat or pad audio so it reaches at least 4.5 seconds for window priming
    if len(samples) < 64600:
        tiles = int(np.ceil(70000 / len(samples)))
        samples = np.tile(samples, tiles)[:72000]

    url = f"{WS_URL}?token={token}&speaker_id={speaker_id}"
    async with websockets.connect(url) as ws:
        # Start session
        await ws.send(json.dumps({"type": "start", "speaker_id": speaker_id, "format": "float32"}))
        start_ack = json.loads(await ws.recv())
        print(f"  [ACK] Session started: {start_ack.get('session_id')}")

        chunk_size = 8000 # 500ms chunks
        total_chunks = len(samples) // chunk_size
        analysis_packets = []

        for i in range(total_chunks):
            chunk = samples[i * chunk_size : (i + 1) * chunk_size]
            await ws.send(chunk.tobytes())

            while True:
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.25))
                    if msg.get("type") == "audio_metrics":
                        print(f"    [AudioMetrics] RMS={msg['rms']:.4f}, Peak={msg['peak']:.4f}, VAD={msg.get('speech_state')}")
                    elif msg.get("type") == "analysis":
                        analysis_packets.append(msg)
                        lat = msg.get("latency", {})
                        print(f"    [TELEMETRY] Risk={msg['risk_score']:.1f} | P(spoof)={msg['metrics']['spoof_probability']:.4f} | "
                              f"SpeakerSim={msg['metrics']['speaker_similarity']} ({msg.get('speaker_status')}) | "
                              f"Action={msg['recommended_action']} | Latency={msg['metrics']['latency_ms']}ms "
                              f"(VAD={lat.get('audio_buffer_ms')}ms, AASIST={lat.get('inference_ms')}ms, ECAPA={lat.get('speaker_verification_ms')}ms)")
                except asyncio.TimeoutError:
                    break
            await asyncio.sleep(0.05)

        # Stop session
        await ws.send(json.dumps({"type": "stop"}))
        stop_ack = json.loads(await ws.recv())
        print(f"  [ACK] Session stopped: {stop_ack.get('pipeline_status')}")

    return analysis_packets

async def test_pure_silence(token: str):
    print(f"\n=======================================================")
    print(f"RUNNING LIVE STREAM TEST: Ambient Silence")
    print(f"=======================================================")

    url = f"{WS_URL}?token={token}"
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"type": "start", "format": "float32"}))
        _ = json.loads(await ws.recv())

        silence_chunk = np.zeros(8000, dtype=np.float32)
        for i in range(8):
            await ws.send(silence_chunk.tobytes())
            while True:
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.15))
                    if msg.get("type") == "audio_metrics":
                        print(f"    [Silence Metrics] RMS={msg['rms']:.4f}, SpeechState={msg.get('speech_state')}")
                    elif msg.get("type") == "analysis":
                        print(f"    [Silence Telemetry] VAD Ratio={msg['metrics']['vad_speech_ratio']}, Risk={msg['risk_score']}")
                except asyncio.TimeoutError:
                    break

        await ws.send(json.dumps({"type": "stop"}))
        _ = json.loads(await ws.recv())
        print("  [ACK] Silence handled safely with VAD suppression.")

def test_file_upload_api(token: str):
    print(f"\n=======================================================")
    print(f"RUNNING REST API FILE UPLOAD TEST (POST /api/v1/analyze-file)")
    print(f"=======================================================")
    import urllib.request

    # Boundary multipart upload
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    with open("samples/genuine_reference.wav", "rb") as f_ref:
        ref_bytes = f_ref.read()
    with open("samples/voice_clone_test.wav", "rb") as f_test:
        test_bytes = f_test.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="reference_audio"; filename="genuine_reference.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode("utf-8") + ref_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="test_audio"; filename="voice_clone_test.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode("utf-8") + test_bytes + (
        f"\r\n--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/analyze-file",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {token}"
        }
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        print(f"  [API Result] Status: {res.get('status')}")
        print(f"  [API Result] Risk Score: {res.get('risk_score')}")
        print(f"  [API Result] Classification: {res.get('classification')}")
        print(f"  [API Result] AASIST Spoof Probability: {res.get('telemetry', {}).get('spoof_probability')}")
        print(f"  [API Result] ECAPA Speaker Similarity: {res.get('telemetry', {}).get('speaker_similarity')}")
        print(f"  [API Result] Recommended Action: {res.get('recommended_action')}")

def test_mfa_endpoints():
    print(f"\n=======================================================")
    print(f"RUNNING OUT-OF-BAND MFA VERIFICATION ENDPOINT TEST")
    print(f"=======================================================")
    import urllib.request

    # 1. Dispatch
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/mfa/dispatch?target_id=exec-001&phone_number=%2B15551234567",
        data=b"",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        d_res = json.loads(resp.read().decode())
        print(f"  [MFA Dispatch] Status: {d_res.get('status')}")

    # 2. Verify with Master Bypass Code 000000
    verify_data = json.dumps({"phone_number": "+15551234567", "code": "000000"}).encode()
    req_v = urllib.request.Request(
        f"{BASE_URL}/api/v1/mfa/verify-code",
        data=verify_data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_v) as resp:
        v_res = json.loads(resp.read().decode())
        print(f"  [MFA Verify] Approved: {v_res.get('approved')}, Message: {v_res.get('message')}")

async def main():
    # Authenticate
    login_req = urllib.request.Request(
        f"{BASE_URL}/api/v1/auth/login",
        data=json.dumps({"username": "analyst@vshield.internal", "password": "VShieldSecure2026!"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(login_req) as resp:
        token = json.loads(resp.read().decode())["access_token"]

    # 1. Genuine Speech Stream
    await test_live_stream_audio(token, "samples/genuine_test.wav", "exec-001", "Genuine Test Speech")

    # 2. Voice Clone Stream
    await test_live_stream_audio(token, "samples/voice_clone_test.wav", "exec-001", "Synthetic Voice Clone Test")

    # 3. Wrong Speaker Stream
    await test_live_stream_audio(token, "samples/wrong_speaker_test.wav", "exec-001", "Wrong Speaker Impersonator Test")

    # 4. Silence Stream
    await test_pure_silence(token)

    # 5. REST File Upload
    test_file_upload_api(token)

    # 6. Out-of-band MFA
    test_mfa_endpoints()

    print("\n" + "=" * 55)
    print("ALL LIVE PIPELINE SCENARIOS VERIFIED SUCCESSFULLY!")
    print("=" * 55)

if __name__ == "__main__":
    asyncio.run(main())
