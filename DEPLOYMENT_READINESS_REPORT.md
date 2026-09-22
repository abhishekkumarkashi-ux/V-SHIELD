# V-SHIELD Production Deployment Readiness Report

**Platform**: V-SHIELD (SIH 2026 - Problem Statement ID: 26104)  
**Architecture**: React 18 + TypeScript + Vite (Vercel) / FastAPI + PyTorch + ONNX Runtime (Render) / PostgreSQL  
**Audit Date**: September 23, 2026  
**Final Deployment Status**: **READY WITH WARNINGS**

---

## 1. Executive Summary & Status Matrix

| Subsystem / Requirement | Status | Verification Summary |
| :--- | :---: | :--- |
| **Backend Service (Render)** | **PASS** | Working directory independence verified (`backend/` service root). `PORT` env var support verified. |
| **Frontend SPA (Vercel)** | **PASS** | TypeScript and Vite build passed (`0 errors`, 8.66s). `frontend/vercel.json` SPA rewrite configured. |
| **Database Architecture** | **PASS** | Dual support: Local SQLite development + PostgreSQL production adapter implemented (`app.core.db`). |
| **Secure WebSockets (WSS)** | **PASS** | Supports TLS-terminated `wss://` on Render. Full HMAC JWT authentication, session tracking, and disconnect cleanup verified. |
| **Google OAuth 2.0 / OpenID** | **PASS** | Dynamic redirect URI, CSRF state protection, claims validation (`aud`, `iss`, `email_verified`), and secure cookie configuration verified. |
| **Twilio Voice Gateway** | **PASS** | Webhook TwiML generation, dynamic `wss://` stream URL construction, and `X-Twilio-Signature` cryptographic validation verified. |
| **AASIST Anti-Spoof Model** | **PASS** | ONNX Runtime FP16 model (1.35 MB) verified on CPU execution provider (~10ms latency). |
| **ECAPA-TDNN Biometrics** | **PASS** | ONNX Runtime FP16 model (84.1 MB) verified on CPU execution provider (~15ms latency). |
| **Risk Engine Fusion** | **PASS** | Multi-Signal EMA fusion (`alpha=0.70`), state machine, and mitigation alerts verified. |
| **Health Checks & Telemetry** | **PASS** | Sub-millisecond JSON `/health`, `/api/health`, and `/api/v1/health` with model readiness and database telemetry verified. |
| **Automated Test Suite** | **PASS** | **143 / 143 passed** in 120.51s, **85.64%** code coverage (exceeds 80.0% failure threshold). |
| **Git & Secret Hygiene** | **PASS** | Zero `.env` files tracked; zero API keys or credentials committed in version control. |
| **Render RAM Constraints** | **WARNING** | Free Tier (512 MB) is tight for PyTorch + ONNX together under concurrent load. **Render Starter (512MB-1GB) or Standard (2GB) is strongly recommended.** |
| **External Cloud Credentials** | **WARNING** | Live deployment requires configuring actual production secrets in Render and Vercel dashboards. |

---

## 2. Deployment Inventory

### Frontend
- **Root Directory**: `frontend/`
- **Framework**: React 18.3.1, TypeScript 5.6.3, Vite 5.4.10, TailwindCSS 3.4.14
- **Entrypoints**: `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`
- **Routing**: SPA routing with clean history replacement and `frontend/vercel.json` fallback
- **Vite Proxy (Local)**: Proxies `/health`, `/api`, `/ws` to `http://localhost:8000`
- **Production URL Resolution**: Uses `VITE_API_URL` and `VITE_WS_URL` with automatic protocol detection fallback (`https://` / `wss://`)

### Backend
- **Root Directory**: `backend/`
- **Framework**: FastAPI 0.110+, Uvicorn 0.28+, Pydantic v2 Settings
- **Entrypoint**: `backend/app/main.py:app`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Dependencies**: `backend/requirements.txt` (FastAPI, PyTorch, torchaudio, ONNX Runtime, SpeechBrain, Twilio, PyJWT, psycopg2-binary)

### Machine Learning Models
- `backend/app/weights/aasist_fp16.onnx` (1.35 MB) — AASIST Graph Attention synthetic speech detection
- `backend/app/weights/ecapa_fp16.onnx` (84.1 MB) — ECAPA-TDNN 192-dim biometric voiceprint verification
- `backend/app/weights/AASIST.pth` (1.28 MB) — PyTorch AASIST reference weights
- Total weights size on disk: ~86.7 MB (tracked via git)

### Database
- **Development**: Local SQLite store at `backend/app/vshield.db`
- **Production**: PostgreSQL managed database via `DATABASE_URL`
- **Tables**: `speakers` (stores `speaker_id`, `name`, `enrolled_at`, and 192-dim `embedding` binary)
- **Adapter**: `backend/app/core/db.py`

### Communication Endpoints
- **REST**:
  - `GET /health`, `GET /api/health`, `GET /api/v1/health`
  - `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`
  - `GET /api/v1/auth/google/login`, `GET /api/v1/auth/google/callback`
  - `POST /api/v1/analyze-file`
  - `POST /api/v1/mfa/dispatch`, `POST /api/v1/mfa/verify`
  - `POST /api/v1/twilio/voice`
- **WebSockets**:
  - `WS /ws/live-call` (and `/ws/analyze`) — Real-time browser audio streaming & telemetry
  - `WS /ws/twilio-stream` (and `/api/v1/twilio/stream`) — Twilio 8 kHz μ-law telephony stream

---

## 3. Platform Configurations

### Render Configuration (`render.yaml`)
Render Blueprint configuration file committed at project root:
- **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/health`
- **Database**: Managed PostgreSQL instance (`vshield-db`) auto-injected via `DATABASE_URL`

### Vercel Configuration (`frontend/vercel.json`)
Vercel deployment configuration committed at `frontend/vercel.json`:
- **Framework**: `vite`
- **SPA Rewrites**: `/(.*)` -> `/index.html`
- **Security Headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`

---

## 4. Required Production Environment Variables

### Render Backend Service (`vshield-backend`)
Configure in **Render Dashboard** -> **vshield-backend** -> **Environment**:

| Variable | Description | Production Value Format |
| :--- | :--- | :--- |
| `ENVIRONMENT` | Runtime environment | `production` |
| `PORT` | Listening port (injected by Render) | Automatically set by Render |
| `FRONTEND_URL` | Vercel production frontend origin | `https://v-shield.vercel.app` |
| `BACKEND_URL` | Render backend public domain | `https://vshield-backend.onrender.com` |
| `CORS_ORIGINS` | Authorized CORS origins | `["https://v-shield.vercel.app"]` |
| `JWT_SECRET_KEY` | HS256 JWT signature key | Generate 64+ char random string |
| `DEMO_OPERATOR_USERNAME` | Default operator identity | `analyst@vshield.internal` |
| `DEMO_OPERATOR_PASSWORD` | Strong password for demo operator | Custom strong password |
| `DATABASE_URL` | PostgreSQL connection string | Injected from Render PostgreSQL |
| `GOOGLE_CLIENT_ID` | Google Cloud OAuth Client ID | `<CLIENT_ID>.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google Cloud OAuth Client Secret | `<CLIENT_SECRET>` |
| `GOOGLE_REDIRECT_URI` | Exact OAuth callback URL | `https://vshield-backend.onrender.com/api/v1/auth/google/callback` |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token (for webhook signature) | `<AUTH_TOKEN>` |
| `TWILIO_VERIFY_SERVICE_SID`| Twilio Verify Service SID for MFA | `VAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `TWILIO_PUBLIC_BASE_URL`| Base URL for constructing wss:// stream | `https://vshield-backend.onrender.com` |
| `MFA_ENABLED` | Enables step-up challenge | `True` |

### Vercel Frontend Service (`vshield-frontend`)
Configure in **Vercel Dashboard** -> **Project Settings** -> **Environment Variables**:

| Variable | Description | Production Value Format |
| :--- | :--- | :--- |
| `VITE_API_URL` | Public Render backend HTTPS URL | `https://vshield-backend.onrender.com` |
| `VITE_WS_URL` | Public Render WebSocket stream address | `wss://vshield-backend.onrender.com/ws/live-call` |

---

## 5. Machine Learning Resource Analysis (Phase 10)

- **AASIST Inference**:
  - Size: 1.35 MB ONNX FP16 graph.
  - Execution Provider: CPUExecutionProvider (4 intra-op threads).
  - Latency: ~10 ms per 4.0375s audio chunk (tested across 100 benchmark passes).
- **ECAPA-TDNN Inference**:
  - Size: 84.1 MB ONNX FP16 graph.
  - Execution Provider: CPUExecutionProvider.
  - Latency: ~15 ms per embedding extraction (tested across 100 benchmark passes).
- **Combined Inference Latency**: ~25 ms total latency on CPU, well below the 500 ms hop size constraint.
- **Memory Footprint**:
  - Python process + PyTorch base + FastAPI: ~300 MB RAM.
  - ONNX Runtime sessions: ~180 MB RAM.
  - Total steady state: ~480-550 MB RAM.
- **Render Tier Advisory**:
  - Render Free Tier has a 512 MB memory ceiling. To prevent OOM restarts during concurrent call streams, **Render Starter (512MB-1GB) or Standard (2GB) is strongly advised**.

---

## 6. Database Migration (Phase 5)

Detailed guide: [`DATABASE_MIGRATION.md`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/DATABASE_MIGRATION.md)

Migration command:
```bash
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite backend/app/vshield.db \
  --postgres "postgresql://vshield_user:<PASSWORD>@<HOST>/vshield"
```

---

## 7. Twilio Voice Deployment (Phase 9)

Detailed guide: [`TWILIO_DEPLOYMENT.md`](file:///c:/Users/hp%20world/V-SHIELD/V-SHIELD/TWILIO_DEPLOYMENT.md)

- Twilio Console Webhook URL:
  `https://<RENDER_BACKEND_URL>/api/v1/twilio/voice` (HTTP POST)
- Media Stream WebSocket:
  `wss://<RENDER_BACKEND_URL>/ws/twilio-stream` (auto-constructed by `build_stream_url`)

---

## 8. Exact Commands Tested & Validation Results

| Test Suite / Step | Command Tested | Result | Details |
| :--- | :--- | :---: | :--- |
| **Full Pytest Suite** | `pytest tests/` | **PASS** | 143 passed in 120.51s, 85.64% coverage |
| **Auth Session Tests** | `pytest tests/test_auth_session.py` | **PASS** | 34 passed in 16.28s |
| **Database Adapter Tests**| `pytest tests/test_db_adapter.py` | **PASS** | 2 passed in 5.37s |
| **ECAPA Verification** | `pytest tests/test_ecapa_verification.py` | **PASS** | 6 passed in 11.46s (0 unclosed warnings) |
| **Frontend Build** | `npm run build` | **PASS** | `tsc && vite build` built in 8.66s |
| **Frontend Lint** | `npm run lint` | **PASS** | `tsc --noEmit` passed with 0 errors |
| **PORT Env Override** | `PORT=9999 python -c ...` | **PASS** | Backend loaded port 9999 cleanly |
| **Git Secret Audit** | `git grep` on sensitive tokens | **PASS** | Zero secrets or private keys found |

---

## 9. Remaining Manual Steps Before Final Go-Live

1. **Deploy Backend to Render**:
   - Push repository to GitHub.
   - In Render, create **Blueprint** from `render.yaml` (or create a Web Service pointing to `backend/`).
   - Populate production environment variables in the Render dashboard.
2. **Deploy Frontend to Vercel**:
   - In Vercel, import repository with **Root Directory**: `frontend`.
   - Set `VITE_API_URL` and `VITE_WS_URL` to your Render backend domain.
   - Click **Deploy**.
3. **Configure Google Cloud Console**:
   - Set **Authorized JavaScript Origin**: `https://<VERCEL_DOMAIN>.vercel.app`
   - Set **Authorized Redirect URI**: `https://<RENDER_DOMAIN>.onrender.com/api/v1/auth/google/callback`
4. **Configure Twilio Phone Number**:
   - Set Voice Webhook URL: `https://<RENDER_DOMAIN>.onrender.com/api/v1/twilio/voice`
5. **Migrate Biometric Database**:
   - Run `python scripts/migrate_sqlite_to_postgres.py` with your Render PostgreSQL connection string.
