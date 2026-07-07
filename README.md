# AI Chatbot

A simple full-stack AI chatbot application built with React + TypeScript (frontend) and FastAPI (backend), powered by Hugging Face Inference API.

> **Note:** This is a learning-oriented project. No memory, databases, authentication, or streaming — just a straightforward request/response chat.

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py          # API route definitions
│   │   ├── core/
│   │   │   └── config.py          # Environment configuration
│   │   ├── schemas/
│   │   │   └── chat.py            # Pydantic request/response models
│   │   ├── services/
│   │   │   └── llm.py             # OpenRouter API communication
│   │   └── main.py                # FastAPI app entry point
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Chat.tsx           # Main chat container
│   │   │   ├── ChatInput.tsx      # Input field + send button
│   │   │   └── Message.tsx        # Individual message bubble
│   │   ├── services/
│   │   │   └── api.ts             # Backend API client
│   │   ├── types/
│   │   │   └── chat.ts            # TypeScript interfaces
│   │   ├── App.tsx                # Root component
│   │   ├── main.tsx               # React entry point
│   │   └── index.css              # Global styles
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── .env.example
└── README.md
```

---

## Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **A Hugging Face token** — [Get one here](https://huggingface.co/settings/tokens)

---

## Setup Instructions

### 1. Clone the project

```bash
cd first_chatbot
```

### 2. Backend setup

```bash
# Navigate to the backend directory
cd backend

# Create a virtual environment (recommended)
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
copy ..\.env.example .env
# (On macOS/Linux: cp ../.env.example .env)

# Edit .env and add your Hugging Face token:
# HF_TOKEN=your-actual-token
```

### 3. Frontend setup

```bash
# Navigate to the frontend directory
cd ../frontend

# Install dependencies
npm install
```

---

## Running the Application

### Terminal 1 — Backend

```bash
cd backend
venv\Scripts\activate     # On Windows
# source venv/bin/activate  # On macOS/Linux

uvicorn app.main:app --reload --port 8000
```

The backend will be available at **http://localhost:8000**.

- API docs (Swagger UI): http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

The frontend will be available at **http://localhost:5173**.

---

## API

### POST /api/chat

Send a message and receive an AI response.

**Request:**

```json
{
  "message": "Hello"
}
```

**Response:**

```json
{
  "response": "Hello! How can I help?"
}
```

### GET /health

Returns `{ "status": "ok" }` if the server is running.

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `HF_TOKEN` | — | Your Hugging Face token (required) |
| `HF_MODEL` | `meta-llama/Llama-3.2-3B-Instruct` | Model to use via Hugging Face |
| `HF_BASE_URL` | `https://router.huggingface.co/v1` | Hugging Face API base URL |
| `HOST` | `0.0.0.0` | Backend host |
| `PORT` | `8000` | Backend port |
| `DEBUG` | `false` | Enable debug logging |

---

## Future Extensions

This project is intentionally minimal and serves as a foundation for adding:

- Conversation memory / history
- Database persistence (PostgreSQL, SQLite)
- User authentication
- Streaming responses
- Tool / function calling
- RAG (Retrieval-Augmented Generation)
- Multi-agent systems
- Docker containerization

---

## License

MIT
