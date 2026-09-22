# V-SHIELD Phase 25 — Real-Time Inference Performance Baseline

**System Specification:** V-SHIELD Real-Time Voice Fraud Detection Gateway  
**Environment:** Python 3.13.7, PyTorch 2.14.0+cpu, ONNX Runtime 1.30.0  
**Hardware Profile:** AMD Radeon Graphics (CPUExecutionProvider active; CUDA unavailable)  
**Hop Budget Target:** 500.0 ms  
**Date of Profiling:** 2026-09-22  
**Harness:** `benchmarks/run_performance_baseline.py`  

---

## 1. Executive Summary & Bottleneck Identification

Prior to any code modifications, a reproducible high-resolution benchmark was executed on the live system.

### Key Takeaways
1. **The Root Cause Bottleneck is Model Computation:**
   - Combined non-model operations (Preprocessing, VAD, Ring Buffer, RiskEngine, and Telemetry JSON) require **< 2.5 ms** ($p50$).
   - Model execution represents **99.7% of total window processing time**:
     - **AASIST ONNX Inference:** $679.245\text{ ms}$ ($p50$) / $848.750\text{ ms}$ ($p95$).
     - **ECAPA ONNX Inference:** $309.448\text{ ms}$ ($p50$) / $383.387\text{ ms}$ ($p95$).
2. **Current CPU Hop Latency Exceeds Budget:**
   - **Complete Hop:** $1000.075\text{ ms}$ ($p50$) / $1222.870\text{ ms}$ ($p95$) vs the $500\text{ ms}$ hop budget.
3. **Architecture Inefficiencies:**
   - Sequential execution of independent models (AASIST + ECAPA run in series instead of concurrent threads).
   - Redundant tensor/numpy conversions (`numpy -> torch -> numpy -> ONNX -> torch`).
   - Lack of ONNX Runtime `SessionOptions` tuning (`intra_op_num_threads`, `inter_op_num_threads`, memory pattern).
   - Running ECAPA on *every* 500 ms audio hop even when speaker identity has just been verified.
   - Synchronous model execution directly inside the WebSocket receive loop, causing I/O blocking.

---

## 2. Component Latency Breakdown Table

All measurements in milliseconds (ms). Sample size: 25 warm iterations post cold-start.

| Component / Layer | Cold Start (ms) | Warm p50 (ms) | Warm p95 (ms) | Warm p99 (ms) | Min (ms) | Max (ms) | Mean (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Audio Preprocessing** | 0.090 | **0.100** | 0.166 | 0.176 | 0.074 | 0.176 | 0.107 |
| **2. Margin-Preserving VAD** | 5.437 | **1.127** | 1.573 | 1.968 | 0.781 | 2.082 | 1.158 |
| **3. Audio Buffer Ingestion** | 1.203 | **0.222** | 0.258 | 0.259 | 0.161 | 0.259 | 0.216 |
| **4. AASIST Preprocessing** | 0.086 | **0.109** | 0.256 | 0.439 | 0.048 | 0.496 | 0.129 |
| **5. AASIST ONNX Inference** | 1084.145 | **679.245** | 848.750 | 882.153 | 603.166 | 884.748 | 693.342 |
| **6. AASIST Postprocessing** | 0.685 | **0.136** | 0.209 | 0.261 | 0.107 | 0.274 | 0.141 |
| **7. ECAPA Preprocessing** | 1.480 | **0.308** | 0.531 | 0.635 | 0.248 | 0.667 | 0.345 |
| **8. ECAPA ONNX Inference** | 480.383 | **309.448** | 383.387 | 477.711 | 271.198 | 506.336 | 318.610 |
| **9. ECAPA Postprocessing** | 0.163 | **0.118** | 0.160 | 0.161 | 0.101 | 0.161 | 0.124 |
| **10. Risk Engine Fusion** | 0.104 | **0.056** | 0.125 | 0.147 | 0.044 | 0.151 | 0.065 |
| **11. WebSocket Telemetry Serialization** | 4.408 | **0.207** | 0.257 | 0.260 | 0.161 | 0.261 | 0.214 |
| **12. Complete Hop End-to-End** | 1578.295 | **1000.075** | 1222.870 | 1256.219 | 880.061 | 1264.005 | 1014.546 |

---

## 3. Cold-Start vs Warm Inference Analysis

- **Model Session Loading:**
  - AASIST Model Initialization: $1065.37\text{ ms}$ (one-time startup)
  - ECAPA Model Initialization: $2349.53\text{ ms}$ (one-time startup)
  - *Finding:* ONNX sessions are already created as Singletons at startup (`AASISTService.get_instance()` and `ECAPAService.get_instance()`). They are **not** recreated per window.
- **First-Inference Compilation Penalty:**
  - AASIST initial pass: $1084.15\text{ ms}$ vs warm $679.25\text{ ms}$ (37% reduction once internal JIT kernels warm).
  - ECAPA initial pass: $480.38\text{ ms}$ vs warm $309.45\text{ ms}$ (35% reduction).

---

## 4. Optimization Opportunities & Planned Targets

1. **ONNX Session Thread Tuning:**
   - Configure `intra_op_num_threads` tuned to physical cores, `inter_op_num_threads=1`, `execution_mode=ORT_SEQUENTIAL`, and `graph_optimization_level=ORT_ENABLE_ALL`.
2. **Eliminate Redundant Tensor Copies:**
   - Pass pre-allocated contiguous `Float32Array` directly into `ort_session.run()` without routing through `torch.from_numpy -> cpu -> numpy`.
3. **Intelligent Speaker Verification Cadence:**
   - AASIST runs continuously on every hop (500 ms).
   - ECAPA runs on initial speech detection and periodically (e.g. every 2.0 seconds or on biometric drift/change), caching the active verified identity with a 5.0-second TTL. This cuts 309 ms from 3 out of every 4 hops on CPU.
4. **Concurrent Parallel Inference Worker:**
   - Offload inference to worker threads (`asyncio.to_thread` / `ThreadPoolExecutor`), preventing blocking of WebSocket receiving and audio ring buffer ingestion.
5. **Truthful Telemetry & Degradation Mode:**
   - Expose `performance: { preprocess_ms, aasist_ms, ecapa_ms, risk_engine_ms, total_ms, provider, device }`.
   - In CPU-only mode where total latency exceeds 500 ms, report `performance_status: "DEGRADED"` without faking passes.
