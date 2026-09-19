"""
Dynamic Risk Scoring & Multi-Signal Fusion Engine (SIH 2026).
Fuses AASIST spoof probability and ECAPA-TDNN speaker similarity into a 0-100 Risk Score.
Applies Exponential Moving Average (EMA, alpha=0.70) to prevent jitter.
"""

from typing import Optional, Tuple

from app.config import settings


class RiskEngine:
    """
    Multi-Signal Fusion Engine evaluating Voice Clone Attacks vs Genuine callers.
    """

    def __init__(self, alpha: float = settings.RISK_ALPHA) -> None:
        self.alpha: float = alpha
        self._current_ema: Optional[float] = None

    def reset(self) -> None:
        """Resets the EMA smoother for a new call session."""
        self._current_ema = None

    def compute_instantaneous_risk(
        self,
        spoof_prob: float,
        speaker_similarity: Optional[float] = None,
        is_speech_active: bool = True,
    ) -> float:
        """
        Computes raw 0-100 risk score prior to EMA smoothing based on domain constraints:
        1. Voice Clone Attack:
           prob_spoof > 0.65 and similarity > 0.70 => Risk >= 75
        2. Synthetic Impersonation:
           prob_spoof > 0.65 and similarity <= 0.70 => Risk >= 80
        3. Genuine Caller:
           prob_spoof < 0.30 and similarity > 0.70 => Risk < 30
        4. Wrong Speaker / Unknown Caller:
           prob_spoof < 0.30 and similarity < 0.40 => Risk in [50, 65]
        """
        if not is_speech_active:
            # In ambient silence or background noise, bias slightly downwards
            base_risk = spoof_prob * 30.0
            return float(min(base_risk, 25.0))

        # Case 1: When speaker verification is available
        if speaker_similarity is not None:
            # Clamp inputs
            s = max(0.0, min(1.0, spoof_prob))
            v = max(-1.0, min(1.0, speaker_similarity))

            # Condition A: High-Confidence Voice Clone Attack
            # Synthesized speech matching the authorized speaker profile!
            if s > 0.65 and v > 0.70:
                # Scaled between 78 and 98
                s_factor = (s - 0.65) / 0.35
                v_factor = (v - 0.70) / 0.30
                raw_score = 78.0 + (s_factor * 12.0) + (v_factor * 8.0)
                return float(min(raw_score, 100.0))

            # Condition B: Synthetic audio (unknown/impersonal voice)
            if s > 0.65 and v <= 0.70:
                s_factor = (s - 0.65) / 0.35
                raw_score = 80.0 + (s_factor * 18.0)
                return float(min(raw_score, 100.0))

            # Condition C: Genuine Authorized Caller
            # Low spoof probability, high biometric match
            if s < 0.30 and v > 0.70:
                s_penalty = (s / 0.30) * 15.0
                v_bonus = max(0.0, (v - 0.70) / 0.30) * 10.0
                raw_score = max(5.0, 15.0 + s_penalty - v_bonus)
                return float(min(raw_score, 28.0))

            # Condition D: Wrong Speaker / Unknown Identity (Human Imposter)
            # Low spoof probability, but voice biometric mismatch
            if s < 0.30 and v < 0.40:
                mismatch_severity = max(0.0, (0.40 - v) / 1.40)  # scale from 0.4 down to -1.0
                raw_score = 52.0 + (mismatch_severity * 12.0)
                return float(min(max(raw_score, 50.0), 65.0))

            # Intermediate / Ambiguous Regions
            # Continuous bilinear blend
            spoof_component = s * 60.0
            biometric_risk = max(0.0, 1.0 - ((v + 1.0) / 2.0)) * 40.0
            raw_score = spoof_component + biometric_risk
            return float(min(max(raw_score, 0.0), 100.0))

        # Case 2: Speaker verification not enabled (unregistered caller)
        # Risk is solely determined by anti-spoofing confidence
        if spoof_prob > 0.65:
            return float(75.0 + ((spoof_prob - 0.65) / 0.35) * 23.0)
        elif spoof_prob < 0.30:
            return float((spoof_prob / 0.30) * 25.0)
        else:
            return float(30.0 + ((spoof_prob - 0.30) / 0.35) * 40.0)

    def evaluate(
        self,
        spoof_prob: float,
        speaker_similarity: Optional[float] = None,
        is_speech_active: bool = True,
    ) -> Tuple[float, str, str]:
        """
        Evaluates current window, updates EMA, and returns:
        (smoothed_risk_score, classification, recommended_action)
        """
        instant_risk = self.compute_instantaneous_risk(
            spoof_prob=spoof_prob,
            speaker_similarity=speaker_similarity,
            is_speech_active=is_speech_active,
        )

        # Apply Exponential Moving Average: EMA_t = alpha * x_t + (1 - alpha) * EMA_{t-1}
        if self._current_ema is None:
            self._current_ema = instant_risk
        else:
            self._current_ema = (self.alpha * instant_risk) + (
                (1.0 - self.alpha) * self._current_ema
            )

        final_score = round(self._current_ema, 1)

        # Layer 5: Decision & Mitigation Trigger
        # Low: 0-30, Medium: 31-69, High: 70-100
        if final_score >= 70.0:
            classification = "HIGH_RISK"
            if speaker_similarity is not None and speaker_similarity > 0.70:
                recommended_action = "TRIGGER_MFA_CALLBACK"
            elif spoof_prob > 0.85:
                recommended_action = "TERMINATE_AND_ALERT"
            else:
                recommended_action = "QUARANTINE_TRANSACTION"
        elif final_score >= 31.0:
            classification = "MEDIUM_RISK"
            if speaker_similarity is not None and speaker_similarity < 0.40:
                recommended_action = "FLAG_OPERATOR_VERIFICATION"
            else:
                recommended_action = "STEP_UP_AUTH"
        else:
            classification = "LOW_RISK"
            recommended_action = "ALLOW_CALL"

        return final_score, classification, recommended_action

    @staticmethod
    def should_trigger_mfa(risk_score: float, recommended_action: str) -> bool:
        """
        Determines whether the current telemetry window should trigger an out-of-band MFA challenge.
        Fires on explicit TRIGGER_MFA_CALLBACK recommendation or Risk Score >= 75.0.
        """
        return (recommended_action == "TRIGGER_MFA_CALLBACK") or (risk_score >= 75.0)

    def classify_static_file(
        self, spoof_prob: float, speaker_similarity: float
    ) -> Tuple[float, str, str]:
        """
        Classifies static audio file analysis according to V-SHIELD REST requirements:
        - High Spoof (>0.65) + High Sim (>0.70) => HIGH_RISK_CLONE (Score: 75-100)
        - Low Spoof (<0.30) + High Sim (>0.70) => BONA_FIDE_GENUINE (Score: 0-30)
        - Low Spoof (<0.30) + Low Sim (<0.40)  => WRONG_SPEAKER (Score: 50-65)
        - High Spoof (>0.65) + Low Sim (<=0.70) => SYNTHETIC_IMPERSONATION (Score: 80-100)
        """
        raw_score = self.compute_instantaneous_risk(
            spoof_prob=spoof_prob, speaker_similarity=speaker_similarity, is_speech_active=True
        )
        final_score = round(raw_score, 1)

        if spoof_prob > 0.65 and speaker_similarity > 0.70:
            classification = "HIGH_RISK_CLONE"
            message = "AI-generated voice impersonation detected. MFA recommended."
            final_score = max(75.0, final_score)
        elif spoof_prob > 0.65 and speaker_similarity <= 0.70:
            classification = "SYNTHETIC_IMPERSONATION"
            message = "Synthetic speech detected from unknown or synthetic speaker."
            final_score = max(80.0, final_score)
        elif spoof_prob < 0.30 and speaker_similarity > 0.70:
            classification = "BONA_FIDE_GENUINE"
            message = "Genuine caller voice verified. Natural human acoustics."
            final_score = min(30.0, final_score)
        elif spoof_prob < 0.30 and speaker_similarity < 0.40:
            classification = "WRONG_SPEAKER"
            message = "Caller biometric mismatch. Unknown or unauthorized speaker."
            final_score = min(max(final_score, 50.0), 65.0)
        elif final_score >= 70.0:
            classification = "HIGH_RISK_THREAT"
            message = "High impersonation threat detected across multi-signal analysis."
        elif final_score >= 31.0:
            classification = "SUSPICIOUS_UNVERIFIED"
            message = "Suspicious acoustic signature. Secondary verification advised."
        else:
            classification = "LOW_RISK_MONITOR"
            message = "Call acoustic metrics within acceptable operating thresholds."

        return final_score, classification, message
