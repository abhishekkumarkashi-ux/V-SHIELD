# Impersonation Engine Configuration

# Development Weights
SPOOF_WEIGHT = 0.6
SPEAKER_WEIGHT = 0.4
TEMPORAL_WEIGHT = 0.0 # Handled via smoothing rather than raw addition
QUALITY_WEIGHT = 0.0

# Temporal History
MAX_HISTORY_WINDOWS = 30 # Approx 15-20 seconds of audio depending on chunk size

# Risk Thresholds
RISK_LOW_THRESHOLD = 30
RISK_MEDIUM_THRESHOLD = 60
RISK_HIGH_THRESHOLD = 80

# Escalation/Decay
TEMPORAL_ESCALATION_THRESHOLD = 3  # consecutive suspicious windows to escalate confidence
TEMPORAL_DECAY_THRESHOLD = 5       # consecutive safe windows to drop risk significantly

# Alerting
ALERT_COOLDOWN_SECONDS = 10.0
