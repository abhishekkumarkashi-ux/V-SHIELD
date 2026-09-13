import pytest
import math
from ml.impersonation.engine import ImpersonationEngine

@pytest.fixture
def engine():
    return ImpersonationEngine()

def test_1_low_spoof_verified_speaker(engine):
    # Low spoof + verified speaker -> low risk
    res = engine.process_window(0.1, 0.8, True)
    assert res["impersonation_risk_level"] == "LOW"
    assert "Possible speaker mismatch" not in res["risk_reasons"]

def test_2_high_spoof_verified_speaker(engine):
    # High spoof + verified speaker -> suspicious synthetic voice
    res = engine.process_window(0.9, 0.8, True)
    # The first chunk might be just building history, so let's push a few to be safe
    for _ in range(3):
        res = engine.process_window(0.9, 0.8, True)
    assert res["speaker_status"] == "VERIFIED"
    assert "Suspicious synthetic/manipulated voice signal" in res["risk_reasons"]

def test_3_low_spoof_not_verified_speaker(engine):
    # Low spoof + not verified speaker -> speaker mismatch signal
    res = engine.process_window(0.1, 0.1, True)
    assert "Possible speaker mismatch" in res["risk_reasons"]

def test_4_high_spoof_not_verified_speaker(engine):
    # High spoof + not verified speaker -> strong impersonation signal
    for _ in range(3):
        res = engine.process_window(0.9, 0.1, True)
    assert "Strong impersonation evidence" in res["risk_reasons"]

def test_5_speaker_not_enrolled(engine):
    # Speaker not enrolled -> no false speaker-mismatch claim
    res = engine.process_window(0.1, None, False)
    assert res["speaker_status"] == "NOT_ENROLLED"
    assert "Speaker verification unavailable" in res["risk_reasons"]
    assert "Possible speaker mismatch" not in res["risk_reasons"]

def test_6_insufficient_audio(engine):
    # Insufficient audio -> reduced/limited confidence
    res = engine.process_window(0.5, None, True)
    assert res["speaker_status"] == "INSUFFICIENT_AUDIO"
    assert res["risk_confidence"] == "LOW"

def test_7_single_noisy_spike(engine):
    # Single noisy spike -> should not immediately create critical state
    for _ in range(5):
        engine.process_window(0.1, 0.8, True) # Build safe history
    res = engine.process_window(0.9, 0.8, True) # Spike
    # Because of EMA, it shouldn't jump to CRITICAL immediately
    assert res["impersonation_risk_level"] != "CRITICAL"

def test_8_persistent_suspicious_windows(engine):
    # Persistent suspicious windows -> risk should increase
    res1 = engine.process_window(0.9, 0.1, True)
    for _ in range(10):
        res2 = engine.process_window(0.9, 0.1, True)
    assert res2["impersonation_risk_score"] > res1["impersonation_risk_score"]
    assert "Suspicious evidence persisted across multiple windows" in res2["risk_reasons"]

def test_9_persistent_safe_windows(engine):
    # Persistent safe windows -> risk should decrease
    for _ in range(5):
        engine.process_window(0.9, 0.1, True)
    res_high = engine.process_window(0.9, 0.1, True)
    
    for _ in range(15):
        engine.process_window(0.1, 0.8, True)
    res_low = engine.process_window(0.1, 0.8, True)
    
    assert res_low["impersonation_risk_score"] < res_high["impersonation_risk_score"]

def test_10_invalid_inputs(engine):
    with pytest.raises(ValueError):
        engine.process_window(float('nan'), 0.5, True)
    with pytest.raises(ValueError):
        engine.process_window(0.5, float('inf'), True)

def test_11_risk_score_never_exceeds_100(engine):
    for _ in range(50):
        res = engine.process_window(1.5, -0.5, True) # Extremely spoofed
        assert res["impersonation_risk_score"] <= 100.0

def test_12_risk_score_never_goes_below_0(engine):
    for _ in range(50):
        res = engine.process_window(-0.5, 1.5, True) # Extremely genuine
        assert res["impersonation_risk_score"] >= 0.0
