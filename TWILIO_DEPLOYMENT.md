# V-SHIELD Twilio Voice & Live Telephony Deployment Guide

**Target Subsystem**: Inbound PSTN Voice Call Ingestion & Media Stream Telemetry  
**Problem Statement ID**: SIH 2026 #26104  
**Production Hosting Target**: Render Backend + Twilio Voice Service

---

## 1. Overview & Architecture

V-SHIELD provides real-time AI voice spoof detection and caller biometric verification for inbound telephone calls. The telephony pipeline integrates with Twilio Voice via bidirectional WebSocket Media Streams.

```
[Inbound PSTN Call]
        │
        ▼
[Twilio Voice Platform]
        │
        │ HTTP POST /api/v1/twilio/voice (with X-Twilio-Signature)
        ▼
[V-SHIELD Render Backend]
        │
        │ Responds with TwiML: <Response><Connect><Stream url="wss://..."/></Connect></Response>
        ▼
[Twilio Media Stream]
        │
        │ Bidirectional WebSocket (wss://<RENDER_BACKEND_URL>/ws/twilio-stream)
        │ Audio format: 8 kHz μ-law (G.711) packets
        ▼
[V-SHIELD Audio Processing Engine]
        │
        ├── 1. μ-law Decoding -> Linear PCM16 -> Upsampling to 16 kHz Mono
        ├── 2. Sliding Window Buffer (64,600 samples ~ 4.0375s, 500ms hop)
        ├── 3. Margin-Preserving VAD (ASVspoof 2021 silence shortcut mitigation)
        ├── 4. AASIST Graph Attention Network (Synthetic / Clone detection)
        ├── 5. ECAPA-TDNN (192-dim acoustic fingerprint match against caller ID)
        └── 6. Multi-Signal EMA Risk Engine (alpha=0.70)
        │
        ▼
[Live Operator Dashboard]
(Broadcasts structured TelemetryPacket via WebSocket subscribers)
```

---

## 2. Twilio Console Configuration

Once the backend is deployed on Render and assigned its public URL (`https://<RENDER_BACKEND_URL>`):

1. Navigate to the **Twilio Console** ([console.twilio.com](https://console.twilio.com/)).
2. Go to **Phone Numbers** -> **Manage** -> **Active Numbers**.
3. Select your active Twilio phone number.
4. Under the **Voice Configuration** section:
   - **A CALL COMES IN**: Select `Webhook`.
   - **URL**: 
     ```text
     https://<RENDER_BACKEND_URL>/api/v1/twilio/voice
     ```
   - **HTTP METHOD**: `HTTP POST`
5. Click **Save Configuration**.

> [!IMPORTANT]
> The webhook URL must match your production Render backend domain exactly.
> Do NOT use `localhost` or internal private IPs in the Twilio console.

---

## 3. Required Environment Variables on Render

Configure these in the Render Dashboard (**Environment** tab of your `vshield-backend` service):

| Variable | Description | Example / Format |
| :--- | :--- | :--- |
| `TWILIO_ACCOUNT_SID` | Your 34-character Twilio Account SID | `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `TWILIO_AUTH_TOKEN` | Twilio primary authentication token (used for cryptographic request signing) | `your_auth_token_here` |
| `TWILIO_PUBLIC_BASE_URL` | The public HTTPS address of your Render backend | `https://vshield-backend.onrender.com` |
| `TWILIO_VERIFY_SERVICE_SID` | Twilio Verify Service SID (for out-of-band MFA SMS dispatch) | `VAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `MFA_ENABLED` | Enables automated high-risk step-up authentication | `True` |
| `MFA_COOLDOWN_SECONDS` | Sliding cooldown between automated MFA dispatches | `120` |
| `DEFAULT_MFA_TARGET_PHONE` | Default phone number for simulation/fallback | `+919876543210` |

---

## 4. Cryptographic Webhook Security (`X-Twilio-Signature`)

V-SHIELD validates the authenticity of every incoming webhook using Twilio's HMAC-SHA1 signature specification:
- When `TWILIO_AUTH_TOKEN` is configured, V-SHIELD verifies the `X-Twilio-Signature` header against the full request URL and POST parameters.
- Requests failing cryptographic validation are immediately rejected with `HTTP 403 Forbidden`.
- In development/local testing, if `TWILIO_AUTH_TOKEN` is unset, signature verification operates in permissive mode with a security log warning.

---

## 5. Media Stream URL Construction

The backend dynamically constructs the secure WebSocket stream address:
- If `TWILIO_PUBLIC_BASE_URL` is set to `https://vshield-backend.onrender.com`, the TwiML response points to:
  ```text
  wss://vshield-backend.onrender.com/ws/twilio-stream
  ```
- If `TWILIO_PUBLIC_BASE_URL` is omitted, the backend derives the host from the `Host` header and `X-Forwarded-Proto` header, ensuring TLS-terminated Render proxies automatically receive `wss://`.

---

## 6. Testing & Verification

1. **Simulate Webhook**:
   ```bash
   curl -X POST "https://<RENDER_BACKEND_URL>/api/v1/twilio/voice" \
     -d "CallSid=CA1234567890abcdef&From=+919876543210&To=+18005550199"
   ```
   Expected response:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <Response>
       <Connect>
           <Stream url="wss://<RENDER_BACKEND_URL>/ws/twilio-stream" />
       </Connect>
   </Response>
   ```

2. **Make a Live Test Call**:
   - Call your Twilio phone number from a mobile phone.
   - Open the V-SHIELD dashboard in your browser (`https://<VERCEL_FRONTEND_URL>`).
   - Observe live real-time audio waveforms, AASIST spoof probability, ECAPA speaker verification similarity, and Risk Engine scores streaming without delay.
