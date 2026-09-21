# V-SHIELD — Twilio Live Telephone Call Gateway Setup Guide

This guide provides step-by-step instructions for configuring and connecting a real Twilio telephone number to the V-SHIELD AI Voice Impersonation Defense & Fraud Prevention platform.

---

## 1. Prerequisites & Twilio Account Requirements

1. **Twilio Account**: An active Twilio account with voice capabilities ([Twilio Console](https://console.twilio.com/)).
2. **Twilio Phone Number**: A voice-capable local, toll-free, or mobile number in your target country (e.g. US, UK, India).
3. **Local Tunneling (for Development)**: `ngrok` or `localtunnel` to expose local port 8000 to the public Internet with HTTPS.
4. **V-SHIELD Backend**: Python 3.13+ virtual environment with `audioop-lts` and `twilio` packages installed.

---

## 2. Environment Variables Configuration

Copy `.env.example` to `.env` in the repository root or update your existing `.env`:

```bash
# =================================================================
# Twilio Telephony & Live Voice Webhook Configuration
# =================================================================

# Public HTTPS URL of your backend (without trailing slash)
# Used by TwiML to build the wss:// stream connection URL
TWILIO_PUBLIC_BASE_URL=https://your-domain.ngrok-free.app

# Twilio API Credentials from https://console.twilio.com/
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here

# Optional: Out-of-band SMS / Voice OTP verification service
TWILIO_VERIFY_SERVICE_SID=VAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MFA_ENABLED=True
MFA_COOLDOWN_SECONDS=120
DEFAULT_MFA_TARGET_PHONE=+919876543210
```

> **Security Note**: Never commit `.env` or paste your `TWILIO_AUTH_TOKEN` in version control.

---

## 3. Public Tunnel Setup (ngrok)

Start ngrok forwarding to local backend port 8000:

```bash
ngrok http 8000
```

Copy the generated HTTPS forwarding domain, for example:
```
Forwarding: https://3a1b-2405-201.ngrok-free.app -> http://localhost:8000
```

Set this domain in `.env`:
```env
TWILIO_PUBLIC_BASE_URL=https://3a1b-2405-201.ngrok-free.app
```

---

## 4. Twilio Phone Number Webhook Configuration

1. Log into the **Twilio Console** and navigate to:  
   **Phone Numbers** $\to$ **Manage** $\to$ **Active Numbers**.
2. Select your active phone number.
3. Scroll down to the **Voice Configuration** section:
   - **A CALL COMES IN**: Select `Webhook`.
   - **URL**: Enter your public webhook URL:
     ```
     https://your-domain.ngrok-free.app/api/v1/twilio/voice
     ```
   - **HTTP METHOD**: Select `HTTP POST`.
4. Click **Save Configuration**.

---

## 5. Starting the V-SHIELD Platform

### 5.1 Backend Service
```powershell
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5.2 Frontend Operator Dashboard
```powershell
cd frontend
npm run dev
```

Navigate to `http://localhost:5173` in your browser.

---

## 6. Live Telephone Call Test Procedure

1. **Verify Backend Health**: Confirm `GET http://localhost:8000/health` returns `status: "ok"` and `anti_spoof_model: "AASIST (ONNX FP16)"`.
2. **Open Dashboard**: Load the V-SHIELD dashboard. Observe `ONLINE` and `GATEWAY CONNECTED` status indicators.
3. **Dial the Twilio Phone Number**: From any cellular or landline phone, dial your Twilio phone number.
4. **Observe Inbound Voice Webhook**:
   - Backend logs `[TWILIO] call started: CallSid=CA...`
   - Returns TwiML with `<Connect><Stream url="wss://your-domain.ngrok-free.app/ws/twilio-stream" />`.
5. **Observe Media Streaming**:
   - Twilio initiates WebSocket connection to `/ws/twilio-stream`.
   - Backend receives 8 kHz μ-law chunks, converts them to PCM16, and resamples to 16 kHz.
   - Dashboard displays purple **TWILIO: CA...** live call badge.
6. **Observe Real-Time Telemetry**:
   - After the first 4.04s of speech accumulates in the sliding buffer, AASIST and ECAPA execute.
   - Live telemetry packets arrive at the React dashboard every 500ms sliding hop.
   - The dynamic risk gauge, VAD speech state, and biometric similarity update continuously.
7. **End Call**: Hang up the phone.
   - Backend cleans up `call_states[call_sid]` and resets the buffer with 0 memory leaks.
   - Dashboard returns to idle ready state.

---

## 7. Automated Local Verification Probe

You can test the entire pipeline without dialing a real phone using our automated probe script:

```powershell
$env:PYTHONPATH="backend"
.\backend\venv\Scripts\python.exe scripts/verify_twilio_live_gateway.py
```

---

## 8. Troubleshooting & FAQ

| Symptom | Root Cause | Solution |
| :--- | :--- | :--- |
| **Twilio says "An application error has occurred"** | Webhook URL unreachable or invalid TwiML response. | Ensure ngrok is running and `TWILIO_PUBLIC_BASE_URL` matches the current forwarding domain. Test `POST /api/v1/twilio/voice` directly using Postman or cURL. |
| **403 Forbidden on Webhook** | Twilio request signature verification failed. | Verify `TWILIO_AUTH_TOKEN` in `.env` matches your Twilio Console Account Auth Token exactly. |
| **Dashboard does not receive telemetry** | WebSocket disconnected or proxy issue. | Verify `ws://localhost:8000/ws/live-call` is open. Inspect browser DevTools Network tab for WebSocket traffic. |
| **Audio sounds distorted / high risk score on clean audio** | Sample rate mismatch. | Twilio streams 8 kHz μ-law. The gateway automatically upsamples to 16 kHz mono. Do not configure Twilio to send 16 kHz unless using non-standard media streams. |
| **No inference for first 4 seconds** | Normal expected behavior. | AASIST requires 64,600 samples (~4.04s) to prime its input window. Subsequent inferences occur every 0.5s. |

---

## 9. Security & Privacy Notes

- **Ephemeral Audio Processing**: Voice frames are held strictly in memory in ring buffers during active evaluation and purged upon call termination. No phone call audio is saved to disk.
- **HMAC Signature Checking**: Protects `/api/v1/twilio/voice` from unauthorized third-party invocations.
- **Resource Protection**: Per-call state isolation prevents memory leaks and ensures one dropped call cannot crash the gateway.
