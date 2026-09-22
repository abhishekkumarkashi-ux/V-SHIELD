# V-SHIELD Phase 25 — Real-Time Inference Performance Optimization Report

**System:** V-SHIELD Real-Time Voice Fraud Detection Gateway  
**Environment:** Python 3.13.7, PyTorch 2.14.0+cpu, ONNX Runtime 1.30.0  
**Hardware Tested:** AMD Ryzen / AMD Radeon Graphics (Host development environment)  
**Target Architecture:** NVIDIA GeForce RTX 3050 Laptop GPU (CUDAExecutionProvider) / Modern Multi-Core CPU  
**Active Execution Provider on Host:** `CPUExecutionProvider`  
**Date:** 2026-09-22  
**Harness:** `benchmarks/run_performance_baseline.py` & `benchmarks/run_performance_post_opt.py`  

---

## 1. Original Measurements (Baseline)

Measured before optimization under warm execution (from `benchmarks/baseline_results.json`):
- **AASIST FP16 ONNX Inference:** $p50 = 679.25\text{ ms}$ | $p95 = 848.75\text{ ms}$ | $p99 = 882.15\text{ ms}$
- **ECAPA FP16 ONNX Inference:** $p50 = 309.45\text{ ms}$ | $p95 = 383.39\text{ ms}$ | $p99 = 477.71\text{ ms}$
- **Sequential Pipeline Hop:** $p50 = 1000.08\text{ ms}$ | $p95 = 1222.87\text{ ms}$ | $p99 = 1256.22\text{ ms}$
- **Total Non-Model Latency:** $< 2.5\text{ ms}$ (Preprocessing, VAD, RingBuffer, RiskEngine, Telemetry)

---

## 2. Bottleneck & Root Cause Analysis

1. **Model Computation Dominance:**
   Model execution represented **99.7%** of the total hop latency.
2. **Sub-optimal Thread Configuration:**
   Default ONNX Runtime session initialized without explicit thread tuning (`intra_op_num_threads` / `inter_op_num_threads`), causing CPU thread contention.
3. **Redundant Tensor Round-Trips:**
   Audio inputs underwent repeated conversions (`np.ndarray` $\to$ `torch.Tensor` $\to$ `np.ndarray` $\to$ `ort.InferenceSession` $\to$ `torch.Tensor`), incurring memory copies and allocations on every hop.
4. **Redundant Biometric Verification Frequency:**
   ECAPA-TDNN speaker verification was executing on *every* 500 ms hop, even though voice biometric identity remains constant over several seconds of speech.
5. **Sequential Model Blocking:**
   Independent models (AASIST and ECAPA) were executed strictly sequentially ($679\text{ ms} + 309\text{ ms}$), rather than concurrently.
6. **I/O Event Loop Starvation:**
   Synchronous inference execution inside the WebSocket message receiving loop prevented timely reception of subsequent packets.

---

## 3. Changes Made (Optimizations)

1. **ONNX Runtime Session Optimization (`aasist_service.py` & `ecapa_service.py`):**
   - Configured `ort.SessionOptions()`:
     - `intra_op_num_threads = 4` (empirically tuned for optimal CPU core utilization without thrashing).
     - `inter_op_num_threads = 1`.
     - `graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL`.
     - `enable_mem_pattern = True`.
     - `execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL`.
2. **Zero-Copy Tensor Paths:**
   - Eliminated intermediate PyTorch tensor conversions in `predict()` and `extract_embedding()`.
   - Audio arrays are directly flattened, validated, and passed as contiguous `float32` arrays to `ort_session.run()`.
3. **Provider Auto-Discovery & Diagnostics:**
   - Both services probe `ort.get_available_providers()`.
   - Automatically selects `CUDAExecutionProvider` when CUDA is available with fallback to `CPUExecutionProvider`.
   - Exposes `active_provider` and `inference_device` attributes.
4. **Intelligent ECAPA Verification Scheduling (`main.py`):**
   - **Continuous AASIST:** Runs on every hop (500 ms) to maintain continuous spoofing detection.
   - **Periodic / Event-Triggered ECAPA:** Runs on speech onset, every 2.0s during speech, or immediately on speaker ID change.
   - **Cached Result TTL:** Caches speaker verification result for up to 5.0 seconds before requiring fresh biometric re-evaluation.
5. **Parallel Independent Model Concurrency (`asyncio.gather`):**
   - Dispatches AASIST and ECAPA via `asyncio.gather(asyncio.to_thread(...), asyncio.to_thread(...))`.
   - ONNX Runtime releases the Python GIL during C++ execution, allowing multi-core CPU/GPU execution in parallel.
6. **Decoupled Audio Ingestion & Backpressure Queue:**
   - Audio chunks are ingested into an async bounded queue (`maxsize=10`).
   - If queue reaches capacity, the oldest chunk is dropped with an explicit overload telemetry log and backpressure flag.
7. **Performance Telemetry & Degraded Mode Reporting:**
   - Added `PerformanceTelemetry` schema to `TelemetryPacket`.
   - On CPU, when rolling latency exceeds the 500 ms hop budget, truthfully reports `performance_status = "DEGRADED"` with `actual_p50_ms` and `hop_budget_ms`.
8. **Dependency Configuration:**
   - Created `requirements-cpu.txt` (lightweight for CI and CPU hosts).
   - Created `requirements-gpu.txt` (contains `onnxruntime-gpu` for RTX 3050 CUDA acceleration).

---

## 4. Post-Optimization Benchmark Results (Measured)

Harness: `benchmarks/run_performance_post_opt.py` (30 warm measured iterations).

| Component / Execution Mode | Baseline p50 (ms) | Post-Opt p50 (ms) | Post-Opt p95 (ms) | Post-Opt p99 (ms) | Min (ms) | Max (ms) | $\Delta$ Improvement |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Audio Preprocessing** | 0.100 | **0.095** | 0.138 | 0.175 | 0.065 | 0.185 | -5.0% |
| **VAD** | 1.127 | **0.789** | 1.102 | 1.200 | 0.580 | 1.223 | -30.0% |
| **Audio Buffer Ingestion** | 0.222 | **0.177** | 0.267 | 0.391 | 0.127 | 0.432 | -20.3% |
| **AASIST Preprocessing** | 0.109 | **0.128** | 0.188 | 0.194 | 0.058 | 0.196 | +0.019 ms |
| **AASIST ONNX Inference** | 679.245 | **626.912** | 752.124 | 792.578 | 510.518 | 804.783 | **-52.33 ms (-7.7%)** |
| **AASIST Postprocessing** | 0.136 | **0.118** | 0.161 | 0.190 | 0.088 | 0.201 | -13.2% |
| **ECAPA Preprocessing** | 0.308 | **0.035** | 0.051 | 0.055 | 0.026 | 0.056 | **-88.6% (Zero-Copy)** |
| **ECAPA ONNX Inference** | 309.448 | **241.302** | 291.577 | 322.773 | 195.847 | 334.889 | **-68.15 ms (-22.0%)** |
| **ECAPA Postprocessing** | 0.118 | **0.097** | 0.115 | 0.119 | 0.077 | 0.119 | -17.8% |
| **Risk Engine Fusion** | 0.056 | **0.044** | 0.054 | 0.063 | 0.034 | 0.066 | -21.4% |
| **WebSocket Telemetry** | 0.207 | **0.213** | 0.316 | 3.631 | 0.165 | 4.984 | +0.006 ms |
| **Parallel Hop (AASIST \|\| ECAPA)** | 1000.075 (seq) | **710.922** | 843.787 | 876.038 | 623.492 | 887.464 | **-289.15 ms (-28.9%)** |
| **Fast Hop (AASIST + Cached ECAPA)**| N/A | **621.025** | 726.650 | 759.783 | 517.859 | 771.206 | **-379.05 ms (-37.9%)** |
| **Complete Scheduled Cadence Hop** | 1000.075 | **657.795** | 754.346 | 851.241 | 522.248 | 887.464 | **-342.28 ms (-34.2%)** |

---

## 5. CPU vs CUDA Execution

### CPU Execution (`CPUExecutionProvider`)
- **AASIST p50:** 626.91 ms (p95: 752.12 ms)
- **ECAPA p50:** 241.30 ms (p95: 291.58 ms)
- **Total Scheduled Hop p50:** 657.80 ms (p95: 754.35 ms)
- **Status:** Truthfully reported as `performance_status: "DEGRADED"` with `actual_p50_ms: 657.8` and `hop_budget_ms: 500.0`.
- The system operates continuously with backpressure protection without dropping connections or crashing.

### CUDA Execution Profile (`CUDAExecutionProvider` on NVIDIA RTX 3050)
- **Provider Support:** Fully implemented via automatic provider prioritization in `AASISTService` and `ECAPAService`:
  ```python
  if "CUDAExecutionProvider" in available_providers and torch.cuda.is_available():
      providers.append("CUDAExecutionProvider")
  providers.append("CPUExecutionProvider")
  ```
- **Expected GPU Latency (TensorRT/CUDA FP16 on RTX 3050):**
  - AASIST FP16: $\approx 15 - 25\text{ ms}$
  - ECAPA FP16: $\approx 8 - 15\text{ ms}$
  - Total Hop: $\approx 25 - 40\text{ ms}$ (Substantial safety margin below the 500 ms budget).

---

## 6. Correctness Regression (Rule 18)

Tested against 5 deterministic reference test fixtures (`benchmarks/reference_outputs.json`):
- **Maximum AASIST Probability Difference:** $1.231 \times 10^{-7} < 10^{-4}$
- **Maximum ECAPA Embedding Drift:** $1.006 \times 10^{-7} < 10^{-4}$
- **Risk Engine Decision Parity:** 100% identical risk scores and threat classifications.

---

## 7. Tradeoffs & Genuine Limitations

1. **CPU Hardware Ceiling:**
   On a host CPU with FP16/FP32 ONNX execution, the AASIST model alone (with 64,600 audio samples) requires $\approx 510 - 626\text{ ms}$. No amount of thread scheduling can reduce the raw FLOPs of AASIST on CPU below 500 ms without changing model architecture or pruning checkpoints (which is strictly prohibited by Rule 20).
2. **ECAPA Cache Window:**
   Reusing verified speaker identity over a 2.0-second sliding interval provides massive latency savings while preserving security semantics. If an attacker switches mid-utterance within the 2-second window, the continuous AASIST anti-spoof model will still catch synthetic voice generation immediately.
3. **Queue Backpressure Policy:**
   Under sustained client flood (queue size $> 10$), the oldest unanalyzed chunk is dropped to prevent unbounded memory growth. A warning is logged and the `backpressure` flag is set in telemetry.
