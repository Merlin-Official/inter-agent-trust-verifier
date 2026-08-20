# 🛡️ Inter-Agent Trust Verifier

> **PS-5.2** — A production-ready inter-agent trust protocol that lets agents verify the legitimacy, authority, and policy-compliance of instructions received from other agents before executing them.

---

## 🏗️ Architecture

```
┌──────────────┐     Ed25519 Signed     ┌───────────────────────────────┐
│   Agent A    │ ─── Instruction ─────▶ │   Trust Verification Engine   │
│  (Sender)    │                        │ ┌───────────────────────────┐ │
└──────────────┘                        │ │ 1. Signature Verification │ │
                                        │ │ 2. Sender Status Check    │ │
┌──────────────┐     Delegation Token   │ │ 3. Delegation Signature   │ │
│   Issuer     │ ─── (scope + sig) ───▶ │ │ 4. Token Revocation       │ │
│  (Admin)     │                        │ │ 5. Token Expiration       │ │
└──────────────┘                        │ │ 6. Delegation Scope       │ │
                                        │ │ 7. Receiver Policy        │ │
                                        │ │ 8. Reputation Check       │ │
                                        │ └───────────────────────────┘ │
                                        │     ACCEPT ✓  or  REJECT ✗   │
                                        └────────────┬──────────────────┘
                                                     │ Audit Log
                                                     ▼
                                        ┌───────────────────────────────┐
                                        │    PostgreSQL / SQLite DB     │
                                        └───────────────────────────────┘
```

## 📋 Tech Stack

| Layer | Technology |
|---|---|
| API Framework | **FastAPI** (Python 3.11+) — async, OpenAPI docs |
| Cryptography | **Ed25519** via `cryptography` — fast, compact signatures |
| Database | **PostgreSQL** (prod) / **SQLite** (dev) via **SQLAlchemy async** |
| LLM | **OpenAI GPT** for natural-language policy explanations |
| Dashboard | **Vite + React + TypeScript** with dark-themed monitoring UI |
| Deployment | **Docker Compose** (local) / **AWS ECS Fargate** (prod) |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Docker & Docker Compose (for production deployment)

### 1. Backend Setup

```bash
# Clone and enter project
cd "Inter-Agent Trust Verifier"

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate   # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings (SQLite works out of the box for dev)

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### 2. Dashboard Setup

```bash
cd dashboard
npm install
npm run dev
```

Dashboard will be available at `http://localhost:5173`.

### 3. Docker (Production)

```bash
docker-compose up --build
```

Services:
- **API**: `http://localhost:8000`
- **Dashboard**: `http://localhost:3000`
- **PostgreSQL**: `localhost:5432`

---

## 🔐 Success Criteria Verification

All five core success criteria are verified by the automated test suite:

| # | Criterion | Test | Status |
|---|---|---|---|
| 1 | Valid signed instruction → ACCEPTED | `test_valid_instruction_accepted` | ✅ |
| 2 | Unsigned/tampered (MITM) → REJECTED | `test_tampered_instruction_rejected` | ✅ |
| 3 | Action outside delegation scope → REJECTED | `test_scope_exceeded_rejected` | ✅ |
| 4 | Revoked credentials → REJECTED within 1 cycle | `test_revoked_agent_rejected` | ✅ |
| 5 | Reputation scoring updates correctly | `test_reputation_below_threshold_rejected` | ✅ |

### Run Tests

```bash
python -m pytest tests/ -v
```

**Result: 28/28 tests passing** ✅

---

## 📡 API Reference

### Agents
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/agents/register` | Register new agent (generates Ed25519 keypair) |
| `GET` | `/api/v1/agents` | List all agents |
| `GET` | `/api/v1/agents/{id}` | Get agent details |

### Delegation Tokens
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/delegations` | Issue a delegation token |
| `GET` | `/api/v1/delegations/{token_id}` | Get token details |
| `GET` | `/api/v1/delegations/agent/{agent_id}` | List tokens for an agent |

### Instructions
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/instructions/sign` | Sign an instruction |
| `POST` | `/api/v1/instructions/verify` | Verify a signed instruction |
| `POST` | `/api/v1/instructions/execute` | Verify and execute |

### Revocation
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/revocation/{agent_id}/revoke` | Revoke credentials |
| `POST` | `/api/v1/revocation/{agent_id}/reactivate` | Restore credentials |
| `GET` | `/api/v1/revocation/{agent_id}/status` | Check revocation status |

### Audit & Reputation
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/audit-logs` | Query audit trail |
| `GET` | `/api/v1/reputation/{agent_id}` | Get trust score |
| `GET` | `/api/v1/reputation/leaderboard` | Agent reputation rankings |
| `GET` | `/api/v1/stats` | Dashboard statistics |

### Health
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/ready` | Readiness probe |

Full interactive API docs available at `http://localhost:8000/docs` (Swagger UI).

---

## 🏢 Project Structure

```
Inter-Agent Trust Verifier/
├── app/
│   ├── api/              # REST endpoints
│   │   ├── agents.py     # Agent registration
│   │   ├── delegation.py # Token issuance
│   │   ├── instructions.py # Sign, verify, execute
│   │   ├── revocation.py # CRL management
│   │   ├── audit.py      # Audit trail & stats
│   │   ├── health.py     # Health probes
│   │   └── schemas.py    # Pydantic models
│   ├── core/             # Business logic
│   │   ├── crypto.py     # Ed25519 operations
│   │   ├── delegation.py # Token creation/validation
│   │   ├── instruction.py# Instruction signing
│   │   ├── verifier.py   # ★ Trust Verification Engine
│   │   ├── revocation.py # In-memory CRL
│   │   ├── reputation.py # Trust scoring
│   │   └── llm_policy.py # OpenAI integration
│   ├── models/           # SQLAlchemy ORM
│   ├── config.py         # Environment settings
│   ├── database.py       # Async DB engine
│   ├── middleware.py      # Request logging
│   └── main.py           # FastAPI entry point
├── dashboard/            # React + Vite frontend
│   └── src/
│       ├── pages/        # Overview, Agents, Audit, Simulation
│       ├── components/   # Layout, shared UI
│       ├── api/          # Axios client
│       └── types/        # TypeScript interfaces
├── tests/                # Comprehensive test suite (28 tests)
├── aws/                  # ECS Fargate deployment
├── Dockerfile            # Multi-stage API image
├── docker-compose.yml    # Full stack orchestration
└── requirements.txt      # Python dependencies
```

---

## ☁️ AWS Deployment

```bash
# Set environment variables
export AWS_REGION=us-east-1
export ECR_REPO=trust-verifier-api

# Store secrets in SSM Parameter Store
aws ssm put-parameter --name /trust-verifier/database-url --value "..." --type SecureString
aws ssm put-parameter --name /trust-verifier/secret-key --value "..." --type SecureString

# Deploy
chmod +x aws/deploy.sh
./aws/deploy.sh
```

---

## 📄 License

MIT
