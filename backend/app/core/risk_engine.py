"""
Dynamic Risk Scoring & Multi-Signal Fusion Engine (SIH 2026).
Authoritative Real-Time Impersonation Risk Pipeline.

Mathematical Formulation:
--------------------------
1. Input Signals:
   - S: Anti-spoof probability from AASIST, S = clip(P(spoof), 0.0, 1.0)
   - V: Biometric speaker cosine similarity from ECAPA-TDNN, V in [-1.0, 1.0], or None if unenrolled.
   - gamma: Voice activity / speech presence ratio, gamma in [0.0, 1.0]

2. Instantaneous Risk (R_instant in [0, 100]):
   Case A: Enrolled Speaker Profile Active (V is not None)
     - Voice Clone Attack (S > 0.65 and V > 0.70):
         R_instant = 78.0 + ((S - 0.65) / 0.35) * 12.0 + ((V - 0.70) / 0.30) * 8.0  [78.0 - 98.0]
     - Synthetic Impersonation (S > 0.65 and V <= 0.70):
         R_instant = 80.0 + ((S - 0.65) / 0.35) * 18.0  [80.0 - 98.0]
     - Genuine Authorized Caller (S < 0.30 and V > 0.70):
         R_instant = max(5.0, 15.0 + (S / 0.30) * 15.0 - max(0.0, (V - 0.70) / 0.30) * 10.0)  [5.0 - 28.0]
     - Human Imposter / Wrong Speaker (S < 0.30 and V < 0.40):
         R_instant = 52.0 + ((0.40 - V) / 1.40) * 12.0  [52.0 - 64.0]
     - Intermediate / Ambiguous:
         R_instant = (S * 60.0) + max(0.0, 1.0 - ((V + 1.0) / 2.0)) * 40.0

   Case B: Unenrolled / Unknown Caller (V is None)
     - S > 0.65: R_instant = 75.0 + ((S - 0.65) / 0.35) * 23.0
     - S < 0.30: R_instant = (S / 0.30) * 25.0
     - 0.30 <= S <= 0.65: R_instant = 30.0 + ((S - 0.30) / 0.35) * 40.0

   VAD Attenuation:
     - If not is_speech_active (ambient silence/noise): R_instant = min(R_instant * 0.30, 25.0)

3. Temporal Smoothing via Exponential Moving Average (EMA, alpha=0.70):
   EMA_t = alpha * R_instant + (1 - alpha) * EMA_{t-1}

4. Explainability Breakdown:
   Decomposes the fused score into discrete contributing factors (anti_spoof, speaker_similarity, speech_activity).
"""

from typing import Any, Dict, List, Optional, Tuple

from app.config import settings


class RiskEngine:
    """
    Authoritative Multi-Signal Impersonation Risk Engine.
    Combines AASIST synthetic voice probability, ECAPA speaker biometrics,
    and VAD speech state into an explainable 0-100 risk score.
    """

    def __init__(self, alpha: float = settings.RISK_ALPHA) -> None:
        self.alpha: float = alpha
        self._current_ema: Optional[float] = None
        self.last_explanation: Optional[Dict[str, Any]] = None

    def reset(self) -> None:
        """Resets the EMA smoother and session state."""
        self._current_ema = None
        self.last_explanation = None

    def compute_instantaneous_risk(
        self,
        spoof_prob: Optional[float],
        speaker_similarity: Optional[float] = None,
        is_speech_active: bool = True,
    ) -> float:
        """
        Computes raw 0-100 risk score prior to EMA smoothing based on domain rules.
        """
        if spoof_prob is None:
            return 0.0

        if not is_speech_active:
            # Ambient silence or background noise: attenuate risk downwards
            base_risk = spoof_prob * 30.0
            return float(min(base_risk, 25.0))

        # Case 1: When speaker verification is available
        if speaker_similarity is not None:
            s = max(0.0, min(1.0, float(spoof_prob)))
            v = max(-1.0, min(1.0, float(speaker_similarity)))

            # Condition A: Voice Clone Attack (Synthetic matching authorized voiceprint)
            if s > 0.65 and v > 0.70:
                s_factor = (s - 0.65) / 0.35
                v_factor = (v - 0.70) / 0.30
                raw_score = 78.0 + (s_factor * 12.0) + (v_factor * 8.0)
                return float(min(raw_score, 100.0))

            # Condition B: Synthetic audio (unknown/impersonal synthetic voice)
            if s > 0.65 and v <= 0.70:
                s_factor = (s - 0.65) / 0.35
                raw_score = 80.0 + (s_factor * 18.0)
                return float(min(raw_score, 100.0))

            # Condition C: Genuine Authorized Caller (low spoof + verified speaker)
            if s < 0.30 and v > 0.70:
                s_penalty = (s / 0.30) * 15.0
                v_bonus = max(0.0, (v - 0.70) / 0.30) * 10.0
                raw_score = max(5.0, 15.0 + s_penalty - v_bonus)
                return float(min(raw_score, 28.0))

            # Condition D: Wrong Speaker / Human Imposter (human acoustics + mismatched voiceprint)
            if s < 0.30 and v < 0.40:
                mismatch_severity = max(0.0, (0.40 - v) / 1.40)
                raw_score = 52.0 + (mismatch_severity * 12.0)
                return float(min(max(raw_score, 50.0), 65.0))

            # Intermediate / Ambiguous Regions: continuous bilinear blend
            spoof_component = s * 60.0
            biometric_risk = max(0.0, 1.0 - ((v + 1.0) / 2.0)) * 40.0
            raw_score = spoof_component + biometric_risk
            return float(min(max(raw_score, 0.0), 100.0))

        # Case 2: Speaker verification not enabled (unenrolled caller)
        s = max(0.0, min(1.0, float(spoof_prob)))
        if s > 0.65:
            return float(75.0 + ((s - 0.65) / 0.35) * 23.0)
        elif s < 0.30:
            return float((s / 0.30) * 25.0)
        else:
            return float(30.0 + ((s - 0.30) / 0.35) * 40.0)

    def evaluate_detailed(
        self,
        spoof_prob: Optional[float],
        speaker_similarity: Optional[float] = None,
        is_speech_active: bool = True,
        speech_ratio: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates risk and returns an explainable decision packet with factor breakdown.

        Guards:
        - If no speech has been observed or spoof_prob is None, decision is 'INSUFFICIENT_DATA'.
          A call is NEVER marked safe merely due to lack of model telemetry.
        """
        # Insufficient data guard:
        has_audio_evidence = (
            spoof_prob is not None
            and not (not is_speech_active and speech_ratio is not None and speech_ratio <= 0.0 and self._current_ema is None)
        )

        if not has_audio_evidence:
            factors: List[Dict[str, Any]] = [
                {
                    "name": "audio_stream",
                    "value": None,
                    "contribution": 0.0,
                    "description": "Insufficient speech data received for confidence scoring.",
                }
            ]
            result = {
                "risk_score": 0.0,
                "decision": "INSUFFICIENT_DATA",
                "classification": "INSUFFICIENT_DATA",
                "recommended_action": "MONITOR",
                "factors": factors,
            }
            self.last_explanation = result
            return result

        instant_risk = self.compute_instantaneous_risk(
            spoof_prob=spoof_prob,
            speaker_similarity=speaker_similarity,
            is_speech_active=is_speech_active,
        )

        # Apply Exponential Moving Average smoothing
        if self._current_ema is None:
            self._current_ema = instant_risk
        else:
            self._current_ema = (self.alpha * instant_risk) + ((1.0 - self.alpha) * self._current_ema)

        final_score = round(self._current_ema, 1)

        # Layer 5: Threat Decision Classification
        if final_score >= 70.0:
            classification = "HIGH_RISK"
            decision = "HIGH_RISK"
            if speaker_similarity is not None and speaker_similarity > 0.70:
                recommended_action = "TRIGGER_MFA_CALLBACK"
            elif spoof_prob is not None and spoof_prob > 0.85:
                recommended_action = "TERMINATE_AND_ALERT"
            else:
                recommended_action = "QUARANTINE_TRANSACTION"
        elif final_score >= 31.0:
            classification = "MEDIUM_RISK"
            decision = "ELEVATED_RISK"
            if speaker_similarity is not None and speaker_similarity < 0.40:
                recommended_action = "FLAG_OPERATOR_VERIFICATION"
            else:
                recommended_action = "STEP_UP_AUTH"
        else:
            classification = "LOW_RISK"
            decision = "LOW_RISK"
            recommended_action = "ALLOW_CALL"

        # Factor Decomposition for Explainability
        factors = []
        if spoof_prob is not None:
            if speaker_similarity is not None:
                spoof_pct = 0.65 if spoof_prob > 0.65 else 0.45
            else:
                spoof_pct = 1.0

            spoof_contribution = round(final_score * spoof_pct, 1)
            if spoof_prob > 0.65:
                spoof_desc = f"Synthetic/deepfake voice features detected (P(spoof) = {spoof_prob:.3f})"
            elif spoof_prob < 0.30:
                spoof_desc = f"Natural human vocal tract acoustics verified (P(spoof) = {spoof_prob:.3f})"
            else:
                spoof_desc = f"Suspicious or degraded vocal characteristics (P(spoof) = {spoof_prob:.3f})"

            factors.append({
                "name": "anti_spoof",
                "value": round(float(spoof_prob), 4),
                "contribution": spoof_contribution,
                "description": spoof_desc,
            })

        if speaker_similarity is not None:
            bio_contribution = round(final_score - factors[0]["contribution"], 1) if factors else round(final_score, 1)
            if speaker_similarity >= 0.70:
                bio_desc = f"Voice biometric profile matched with enrolled caller (sim = {speaker_similarity:.3f})"
            elif speaker_similarity <= 0.40:
                bio_desc = f"Voice biometric mismatch against enrolled caller (sim = {speaker_similarity:.3f})"
            else:
                bio_desc = f"Biometric voiceprint intermediate / evaluating (sim = {speaker_similarity:.3f})"

            factors.append({
                "name": "speaker_similarity",
                "value": round(float(speaker_similarity), 4),
                "contribution": max(0.0, bio_contribution),
                "description": bio_desc,
            })
        else:
            factors.append({
                "name": "speaker_similarity",
                "value": None,
                "contribution": 0.0,
                "description": "No enrolled voiceprint profile; risk evaluated from anti-spoof only.",
            })

        activity_ratio = speech_ratio if speech_ratio is not None else (1.0 if is_speech_active else 0.0)
        factors.append({
            "name": "speech_activity",
            "value": round(activity_ratio, 2),
            "contribution": 0.0,
            "description": "Active voice frames detected" if is_speech_active else "Low speech activity / ambient silence",
        })

        result = {
            "risk_score": final_score,
            "decision": decision,
            "classification": classification,
            "recommended_action": recommended_action,
            "factors": factors,
        }
        self.last_explanation = result
        return result

    def evaluate(
        self,
        spoof_prob: Optional[float],
        speaker_similarity: Optional[float] = None,
        is_speech_active: bool = True,
        speech_ratio: Optional[float] = None,
    ) -> Tuple[float, str, str]:
        """
        Evaluates current window, updates EMA, and returns:
        (smoothed_risk_score, classification, recommended_action)
        Preserves backwards compatibility with legacy callers.
        """
        detailed = self.evaluate_detailed(
            spoof_prob=spoof_prob,
            speaker_similarity=speaker_similarity,
            is_speech_active=is_speech_active,
            speech_ratio=speech_ratio,
        )
        return detailed["risk_score"], detailed["classification"], detailed["recommended_action"]

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
