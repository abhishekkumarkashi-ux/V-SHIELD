"""
Unit tests for RiskEngine (SIH 2026).
Verifies multi-signal fusion, threat thresholds, and EMA smoothing.
"""

try:
    import pytest
except ImportError:
    pytest = None
from app.core.risk_engine import RiskEngine


def test_voice_clone_attack_high_confidence():
    """
    If prob_spoof > 0.65 and similarity > 0.70:
    High-confidence Voice Clone / Impersonation Attack => Risk Score >= 75
    """
    engine = RiskEngine(alpha=1.0)  # Instantaneous test without EMA delay

    score, classification, action = engine.evaluate(
        spoof_prob=0.85, speaker_similarity=0.88, is_speech_active=True
    )

    assert score >= 75.0
    assert classification == "HIGH_RISK"
    assert action == "TRIGGER_MFA_CALLBACK"


def test_genuine_authorized_caller():
    """
    If prob_spoof < 0.30 and similarity > 0.70:
    Genuine Caller => Risk Score < 30 (Green: Monitor/Allow).
    """
    engine = RiskEngine(alpha=1.0)

    score, classification, action = engine.evaluate(
        spoof_prob=0.12, speaker_similarity=0.85, is_speech_active=True
    )

    assert score < 30.0
    assert classification == "LOW_RISK"
    assert action in ["ALLOW_CALL", "MONITOR"]


def test_wrong_speaker_unknown_identity():
    """
    If prob_spoof < 0.30 and similarity < 0.40:
    Wrong speaker / Unknown identity => Risk Score 50–65 (Amber: Warn/Verify).
    """
    engine = RiskEngine(alpha=1.0)

    score, classification, action = engine.evaluate(
        spoof_prob=0.15, speaker_similarity=0.20, is_speech_active=True
    )

    assert 50.0 <= score <= 65.0
    assert classification == "MEDIUM_RISK"
    assert action == "FLAG_OPERATOR_VERIFICATION"


def test_synthetic_unknown_attack():
    """
    If prob_spoof > 0.65 and similarity <= 0.70:
    Synthetic speech from non-enrolled voice => High Risk.
    """
    engine = RiskEngine(alpha=1.0)

    score, classification, action = engine.evaluate(
        spoof_prob=0.92, speaker_similarity=0.10, is_speech_active=True
    )

    assert score >= 80.0
    assert classification == "HIGH_RISK"
    assert action in ["TERMINATE_AND_ALERT", "QUARANTINE_TRANSACTION"]


def test_ema_smoothing_behavior():
    """
    Verifies that EMA with alpha=0.70 smooths transitions across consecutive windows.
    """
    engine = RiskEngine(alpha=0.70)

    # Initial genuine caller evaluation
    s1, _, _ = engine.evaluate(spoof_prob=0.10, speaker_similarity=0.85)

    # Sudden jump to spoof attack in next 0.5s window
    s2, _, _ = engine.evaluate(spoof_prob=0.90, speaker_similarity=0.85)

    # With alpha=0.70, s2 should be 0.70 * instant + 0.30 * s1
    instant = engine.compute_instantaneous_risk(spoof_prob=0.90, speaker_similarity=0.85)
    expected_s2 = round(0.70 * instant + 0.30 * s1, 1)

    assert abs(s2 - expected_s2) <= 0.2
