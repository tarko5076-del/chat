# Resto AI — Digital Waiter

An AI-powered restaurant assistant that handles **ordering, reservations, payments, and customer memory** through natural conversation. A real digital waiter for real restaurants.

---

## 🚀 First 5 Minutes

### 0. Set up environment variables

```bash
cp backend/.env.example backend/.env
# Optional: edit backend/.env and add your Hugging Face token for AI features
# HF_TOKEN=hf_your_token_here
```

Without a token, the system still works for ordering, reservations, and payments — just without the AI-driven conversation (uses a rule-based fallback).

### 1. Start the system

```bash
docker compose up --build -d
```

Wait 30 seconds for all services to become healthy.

### 2. Open the app

→ **http://localhost**

You'll see a login screen.

### 3. Create an account

Click **Sign up** and enter:
- A username (e.g. `alex`)
- An email (e.g. `alex@test.com`)
- A password

Then log in with your email and password.

### 4. Say hello

Type: **`Hi, what's on the menu?`**

The AI agent will respond with the restaurant's menu items, descriptions, and prices.

### 5. Place an order

```
You:  I'd like a pizza and a soda
       Actually, make it two pizzas
       Checkout, pickup, pay with cash
       Yes, confirm
```

The agent guides you through each step — quantity, delivery method, payment — and asks for confirmation before placing the order.

### 6. Ask about the restaurant

```
You:  What are your opening hours?
      Do you have vegan options?
      What's your cancellation policy?
```

The agent answers from a knowledge base.

### 7. Book a table

```
You:  I want to book a table for tomorrow at 7pm
      4 people
      My name is Alex
      Phone: +1234567890
      Email: alex@test.com
      Yes, confirm
```

### 8. Come back later

When you return and log in again:

```
You:  Hi, I'm back!
Agent: Welcome back, Alex! Would you like your usual?
```

The agent remembers your name, past orders, and preferences.

---

## 🎯 What You Can Do

### As a Customer

| Task | Try typing |
|------|-----------|
| Browse menu | `"What's on the menu?"`, `"Show me vegan options under $15"` |
| Get recommendations | `"Recommend something spicy"`, `"What's popular?"` |
| Order food | `"I'd like 2 burgers and fries"`, `"Add a salad"` |
| Checkout | `"Checkout, delivery to 123 Main St, pay with card"` |
| Cancel order | `"Cancel my order"` |
| Reorder | `"I want to reorder my last meal"` |
| Reserve a table | `"Book a table for 4 tomorrow at 7pm"` |
| Ask questions | `"What are your hours?"`, `"Do you have parking?"` |
| Set preferences | `"My favorite is Ethiopian coffee"`, `"I don't like spicy"` |
| View your profile | `"What do you know about me?"` |
| Request staff | `"I need to speak to a manager"` |

### As Staff

- Visit **http://localhost/staff** — dashboard with active orders, held reservations, and escalation alerts
- The **sidebar** (click the menu icon) shows menu, order history, reservations, memory facts, and past conversations

### As an Operator

- **http://localhost/health/** — system status (DB, LLM, uptime)
- **http://localhost/metrics/** — live counters (requests, response times, LLM usage, business events)
- **http://localhost:8000/admin/** — Django admin (requires superuser)

---

## 📦 Architecture

```
User → Port 80 (Nginx)
              │
         ┌────┴────┐
         │         │
   Frontend    Backend :8000
   (React)     (Django + DRF)
                   │
              PostgreSQL 16
              + pgvector
```

| Service | Stack |
|---------|-------|
| **Frontend** | React + TypeScript + RTK Query + Vite |
| **Backend** | Django + Django REST Framework + Gunicorn |
| **Database** | PostgreSQL 16 + pgvector extension |
| **AI** | Hugging Face Inference API (OpenAI-compatible) |
| **Embeddings** | Hugging Face / OpenAI (configurable) |
| **Payments** | Chapa (Ethiopian gateway, demo mode available) |

---

## 🔧 Configuration

Copy `backend/.env.example` to `backend/.env` and configure:

| Variable | Required | What it does |
|----------|----------|-------------|
| `HF_TOKEN` | ✅ for AI | Hugging Face API token |
| `DJANGO_SECRET_KEY` | ✅ | Django secret (generate a random one for production) |
| `POSTGRES_PASSWORD` | ✅ for Docker | Database password |
| `CHAPA_SECRET_KEY` | For payments | Chapa payment gateway key |

Without an AI token, the system still works — it uses a rule-based planner for ordering and reservations.

---

## 🧪 Running Tests

```bash
cd backend
USE_SQLITE=true python manage.py test menu.tests agent.tests
```

**179 tests — 178 pass** (1 pre-existing `test_payment_idempotency` edge case)

---

## 📊 Load Testing

```bash
pip install locust
cd backend
locust -f locustfile.py --host=http://localhost --headless \
  --users 10 --spawn-rate 5 --run-time 2m
```

See `backend/locustfile.py` for custom scenarios.

---

## 📚 Documentation

All docs are in the `docs/` directory:

| Document | What it covers |
|----------|---------------|
| `ai-agent-development-roadmap.md` | Milestones, progress, what's next |
| `deployment-and-infrastructure.md` | Production deployment, backup strategy, secrets, troubleshooting |
| `api-architecture.md` | API design, endpoints, authentication |

---

## 🗺️ Roadmap

```
✅ Milestone 1-6 — Foundation, Tools, Menu, Orders, Payments, Reservations
✅ Milestone 7   — Customer Memory System
✅ Milestone 8   — Advanced RAG (hybrid search, knowledge management)
✅ Milestone 9   — Production Readiness (monitoring, caching, security, load testing)
⏳ Milestone 10  — Multi-Agent Architecture
```

---

## 📄 License

MIT
