"""
Unit tests for RiskEngine (SIH 2026).
Verifies multi-signal fusion, threat thresholds, explainable factors,
insufficient data guard, and EMA smoothing.
"""

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


def test_insufficient_data_guard():
    """
    A call is NEVER marked safe merely because model telemetry is absent.
    If spoof_prob is None or pure silence/zero speech with no prior state,
    decision must be 'INSUFFICIENT_DATA' and action 'MONITOR'.
    """
    engine = RiskEngine()

    # 1. No model probability provided
    res_none = engine.evaluate_detailed(spoof_prob=None, is_speech_active=False)
    assert res_none["decision"] == "INSUFFICIENT_DATA"
    assert res_none["classification"] == "INSUFFICIENT_DATA"
    assert res_none["recommended_action"] == "MONITOR"

    # 2. Complete silence before any speech is observed
    engine.reset()
    res_silence = engine.evaluate_detailed(
        spoof_prob=0.05,
        speaker_similarity=None,
        is_speech_active=False,
        speech_ratio=0.0,
    )
    assert res_silence["decision"] == "INSUFFICIENT_DATA"
    assert res_silence["recommended_action"] == "MONITOR"


def test_explainability_factors():
    """
    Verifies that evaluate_detailed returns an explainable breakdown
    of contributing signals (anti_spoof, speaker_similarity, speech_activity).
    """
    engine = RiskEngine(alpha=1.0)

    detail = engine.evaluate_detailed(
        spoof_prob=0.82,
        speaker_similarity=0.41,
        is_speech_active=True,
        speech_ratio=0.95,
    )

    assert "risk_score" in detail
    assert "decision" in detail
    assert "factors" in detail
    assert len(detail["factors"]) >= 2

    factor_names = [f["name"] for f in detail["factors"]]
    assert "anti_spoof" in factor_names
    assert "speaker_similarity" in factor_names
    assert "speech_activity" in factor_names

    # Check anti_spoof factor properties
    as_factor = next(f for f in detail["factors"] if f["name"] == "anti_spoof")
    assert as_factor["value"] == 0.82
    assert as_factor["contribution"] > 0
    assert len(as_factor["description"]) > 0


def test_unenrolled_speaker_risk_scoring():
    """
    When no enrolled speaker is present (speaker_similarity=None),
    risk engine gracefully scores based on anti-spoof without crashing or forcing 0.0.
    """
    engine = RiskEngine(alpha=1.0)

    # High spoof unenrolled
    score_high, class_high, action_high = engine.evaluate(
        spoof_prob=0.90, speaker_similarity=None, is_speech_active=True
    )
    assert score_high >= 75.0
    assert class_high == "HIGH_RISK"

    # Low spoof unenrolled
    score_low, class_low, action_low = engine.evaluate(
        spoof_prob=0.10, speaker_similarity=None, is_speech_active=True
    )
    assert score_low < 30.0
    assert class_low == "LOW_RISK"
    assert action_low == "ALLOW_CALL"


def test_reset_clears_engine_state():
    """Verifies that reset() clears EMA history and cached explanations."""
    engine = RiskEngine(alpha=0.70)
    engine.evaluate(spoof_prob=0.85, speaker_similarity=0.90)
    assert engine._current_ema is not None
    assert engine.last_explanation is not None

    engine.reset()
    assert engine._current_ema is None
    assert engine.last_explanation is None
