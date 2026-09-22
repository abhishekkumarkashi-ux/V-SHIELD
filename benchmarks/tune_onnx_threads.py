"""
Tunes ONNX Runtime thread settings for AASIST FP16 ONNX model.
"""

import sys
import time
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402
from app.config import settings  # noqa: E402

model_path = str(settings.AASIST_ONNX_PATH)
t = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
audio_input = np.expand_dims(t, axis=0)

thread_options = [1, 2, 3, 4, 6, 8]
results = {}

for th in thread_options:
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = th
    opts.inter_op_num_threads = 1
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    opts.enable_mem_pattern = True
    opts.enable_cpu_mem_arena = True

    sess = ort.InferenceSession(model_path, sess_options=opts, providers=["CPUExecutionProvider"])

    # Warmup
    for _ in range(2):
        _ = sess.run(["logits"], {"audio_input": audio_input})

    # Benchmark 5 passes
    times = []
    for _ in range(6):
        t0 = time.perf_counter()
        _ = sess.run(["logits"], {"audio_input": audio_input})
        times.append((time.perf_counter() - t0) * 1000.0)

    p50 = float(np.percentile(times, 50))
    print(f"intra_op_num_threads={th:2d} -> p50: {p50:6.2f} ms (min: {min(times):6.2f} ms, max: {max(times):6.2f} ms)")
    results[th] = p50

best_threads = min(results, key=results.get)
print(f"\nBest thread count: {best_threads} with p50: {results[best_threads]:.2f} ms")
