"""
Records reference model outputs (AASIST logits/probs, ECAPA embeddings, and RiskEngine scores)
for correctness regression testing before and after performance optimization.
"""

import json
import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import numpy as np  # noqa: E402
from app.core.risk_engine import RiskEngine  # noqa: E402
from app.models.aasist_service import AASISTService  # noqa: E402
from app.models.ecapa_service import ECAPAService  # noqa: E402


def record_references():
    aasist = AASISTService.get_instance()
    ecapa = ECAPAService.get_instance()
    risk_engine = RiskEngine(alpha=0.7)

    # Enroll speaker
    t_en = np.linspace(0, 2.0, 32000, endpoint=False, dtype=np.float32)
    enroll_pcm = (0.28 * np.sin(2 * np.pi * 380.0 * t_en)).astype(np.float32)
    ecapa.enroll_speaker("ref_speaker_001", enroll_pcm, 16000)

    fixtures = []
    # 5 deterministic test signals
    frequencies = [200.0, 440.0, 800.0, 1200.0, 2400.0]
    for idx, f in enumerate(frequencies):
        t = np.linspace(0, 4.0375, 64600, endpoint=False, dtype=np.float32)
        audio = (0.25 * np.sin(2 * np.pi * f * t) + 0.10 * np.sin(2 * np.pi * (f * 2) * t)).astype(np.float32)

        # 1. AASIST
        logits_tensor, spoof_prob = aasist.predict(audio)
        logits_list = logits_tensor.detach().cpu().numpy().tolist()

        # 2. ECAPA
        embedding = ecapa.extract_embedding(audio).tolist()
        spk_res = ecapa.verify_speaker_detailed(audio, "ref_speaker_001")

        # 3. Risk Engine
        risk_res = risk_engine.evaluate_detailed(
            spoof_prob=spoof_prob,
            speaker_similarity=spk_res["similarity"],
            is_speech_active=True,
            speech_ratio=0.85,
        )

        fixtures.append({
            "id": idx,
            "freq": f,
            "spoof_prob": round(float(spoof_prob), 6),
            "logits": logits_list,
            "speaker_similarity": (
                round(float(spk_res["similarity"]), 6)
                if spk_res["similarity"] is not None
                else None
            ),
            "embedding_sample": embedding[:10],  # first 10 dims
            "risk_score": risk_res["risk_score"],
            "classification": risk_res["classification"],
            "decision": risk_res["decision"],
        })

    out_file = Path(__file__).resolve().parent / "reference_outputs.json"
    with open(out_file, "w") as f:
        json.dump(fixtures, f, indent=2)
    print(f"Recorded {len(fixtures)} reference fixtures to {out_file}")


if __name__ == "__main__":
    record_references()
