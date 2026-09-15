"""
Anti-spoofing evaluation metrics for V-SHIELD.
Computes Equal Error Rate (EER), ROC-AUC, F1, Accuracy, and optimal threshold calibration.
Pure NumPy implementation with optional scikit-learn acceleration.
"""

import numpy as np
from typing import Dict, Tuple, Any

def compute_far_frr(labels: np.ndarray, scores: np.ndarray, threshold: float) -> Tuple[float, float]:
    """
    Computes False Acceptance Rate (FAR) and False Rejection Rate (FRR) at a specific threshold.
    Label convention:
      0 = BONAFIDE (genuine)
      1 = SPOOF (synthetic / attack)
    Scores: probability of being SPOOF (higher = more likely spoof).
    """
    labels = np.asarray(labels)
    scores = np.asarray(scores)

    # Bonafide samples classified as spoof (false positive / false alarm)
    bonafide_mask = (labels == 0)
    spoof_mask = (labels == 1)

    num_bonafide = np.sum(bonafide_mask)
    num_spoof = np.sum(spoof_mask)

    if num_bonafide == 0 or num_spoof == 0:
        return 0.0, 0.0

    # False Acceptance Rate: Genuine caller falsely flagged as spoof
    far = np.sum(scores[bonafide_mask] >= threshold) / num_bonafide

    # False Rejection Rate: Spoof caller falsely accepted as genuine
    frr = np.sum(scores[spoof_mask] < threshold) / num_spoof

    return float(far), float(frr)

def compute_eer(labels: np.ndarray, scores: np.ndarray, num_thresholds: int = 1000) -> Tuple[float, float]:
    """
    Computes Equal Error Rate (EER) where FAR == FRR.
    Returns: (eer, optimal_threshold)
    """
    labels = np.asarray(labels)
    scores = np.asarray(scores)

    if len(labels) == 0:
        return 0.0, 0.5

    unique_labels = np.unique(labels)
    if len(unique_labels) < 2:
        return 0.0, 0.5

    min_score = float(np.min(scores))
    max_score = float(np.max(scores))

    if min_score == max_score:
        return 0.5, min_score

    thresholds = np.linspace(min_score, max_score, num_thresholds)
    min_diff = float("inf")
    best_eer = 0.5
    best_threshold = 0.5

    for th in thresholds:
        far, frr = compute_far_frr(labels, scores, th)
        diff = abs(far - frr)
        if diff < min_diff:
            min_diff = diff
            best_eer = (far + frr) / 2.0
            best_threshold = float(th)

    return float(best_eer), float(best_threshold)

def compute_roc_auc(labels: np.ndarray, scores: np.ndarray) -> float:
    """Computes Area Under ROC Curve via trapezoidal rule."""
    try:
        from sklearn.metrics import roc_auc_score
        return float(roc_auc_score(labels, scores))
    except Exception:
        # Pure NumPy fallback via Mann-Whitney U / rank sum
        labels = np.asarray(labels)
        scores = np.asarray(scores)
        pos = scores[labels == 1]
        neg = scores[labels == 0]
        if len(pos) == 0 or len(neg) == 0:
            return 0.5
        # Compute Wilcoxon-Mann-Whitney statistic
        ranks = np.argsort(np.argsort(scores)) + 1
        pos_ranks = ranks[labels == 1]
        u = np.sum(pos_ranks) - len(pos) * (len(pos) + 1) / 2.0
        return float(u / (len(pos) * len(neg)))

def compute_classification_metrics(labels: np.ndarray, scores: np.ndarray, threshold: float = 0.5) -> Dict[str, Any]:
    """Computes full suite of classification metrics at a given threshold."""
    labels = np.asarray(labels, dtype=int)
    scores = np.asarray(scores, dtype=float)
    preds = (scores >= threshold).astype(int)

    tp = np.sum((preds == 1) & (labels == 1))
    tn = np.sum((preds == 0) & (labels == 0))
    fp = np.sum((preds == 1) & (labels == 0))
    fn = np.sum((preds == 0) & (labels == 1))

    total = len(labels)
    accuracy = float((tp + tn) / total) if total > 0 else 0.0
    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    eer, eer_th = compute_eer(labels, scores)
    roc_auc = compute_roc_auc(labels, scores)

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "eer": round(eer, 4),
        "eer_threshold": round(eer_th, 4),
        "operating_threshold": round(threshold, 4),
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn)
    }
