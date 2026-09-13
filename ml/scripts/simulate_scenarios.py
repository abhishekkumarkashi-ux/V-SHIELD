import sys
import os
import json

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(base_dir)

from ml.impersonation import ImpersonationEngine

def run_scenario(name, inputs):
    print(f"\n{'='*50}\nSCENARIO: {name}\n{'='*50}")
    engine = ImpersonationEngine()
    for i, inp in enumerate(inputs):
        res = engine.process_window(**inp)
        print(f"Window {i+1}: Spoof={inp['spoof_probability']} Sim={inp.get('speaker_similarity')} -> Risk {res['impersonation_risk_score']} ({res['impersonation_risk_level']})")
        if i == len(inputs) - 1:
            print("Final Reasons:")
            for r in res["risk_reasons"]:
                print(f" - {r}")

if __name__ == "__main__":
    scenarios = {
        "A: Genuine enrolled speaker": [
            {"spoof_probability": 0.1, "speaker_similarity": 0.8, "speaker_enrolled": True} for _ in range(5)
        ],
        "B: AI-generated voice of enrolled speaker": [
            {"spoof_probability": 0.9, "speaker_similarity": 0.7, "speaker_enrolled": True} for _ in range(5)
        ],
        "C: Genuine different speaker": [
            {"spoof_probability": 0.1, "speaker_similarity": 0.1, "speaker_enrolled": True} for _ in range(5)
        ],
        "D: AI-generated voice of different speaker": [
            {"spoof_probability": 0.9, "speaker_similarity": 0.1, "speaker_enrolled": True} for _ in range(5)
        ],
        "E: Noisy genuine speaker": [
            {"spoof_probability": 0.4, "speaker_similarity": 0.3, "speaker_enrolled": True},
            {"spoof_probability": 0.8, "speaker_similarity": 0.2, "speaker_enrolled": True},
            {"spoof_probability": 0.3, "speaker_similarity": 0.6, "speaker_enrolled": True},
            {"spoof_probability": 0.1, "speaker_similarity": 0.8, "speaker_enrolled": True},
            {"spoof_probability": 0.1, "speaker_similarity": 0.7, "speaker_enrolled": True}
        ],
        "F: Short/interrupted speech": [
            {"spoof_probability": 0.5, "speaker_similarity": None, "speaker_enrolled": True},
            {"spoof_probability": 0.6, "speaker_similarity": None, "speaker_enrolled": True}
        ]
    }
    
    for name, inputs in scenarios.items():
        run_scenario(name, inputs)
