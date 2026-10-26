# AI Debate Coach with Argument Scoring

Students pick a motion and a side, debate an AI opponent, and receive a per-turn **ballot**:
scores for clarity, evidence, logic and rebuttal, quoted fallacies, strengths, fixes, and a stronger rewrite.

## Free-only AI providers (no paid API needed)
Set one key in `backend/.env`. The provider is auto-detected, or force it with `LLM_PROVIDER`.

| Provider | Cost | Get it |
|---|---|---|
| **Groq** (recommended) | Free tier, no credit card | https://console.groq.com/keys |
| Google Gemini | Free tier | https://aistudio.google.com/apikey |
| OpenRouter | Free `:free` models | https://openrouter.ai/keys |
| Ollama | Fully local, no key, no limits | https://ollama.com, then `ollama pull llama3.2` |
| (none) | Offline rule-based demo mode | nothing to set up |

Free tiers have rate limits (Groq's 70B model is roughly 30 requests/minute). If a call fails or is rate-limited,
the backend falls back to the offline scorer for that turn and tells the student, so the app never breaks.
Model names change over time; if one is retired, change `GROQ_MODEL` / `GEMINI_MODEL` etc. in `.env`.

## How the chain-of-thought scoring works
Each turn, the model must reason through five ordered steps (claim, evidence, logic, fallacy scan, rebuttal)
and write them into `reasoning` **before** it emits scores. The backend clamps scores to 0-10 and computes
the weighted overall itself (clarity 20%, evidence 30%, logic 30%, rebuttal 20%) so the final number is deterministic.
Fallacies must be backed by a verbatim quote. Malformed JSON is retried once.

## Run it
```bash
# Terminal 1 - backend (Python 3.10+)
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then paste a free GROQ_API_KEY (or leave empty for demo mode)
uvicorn main:app --reload --port 8000
pytest                      # run tests

# Terminal 2 - frontend (Node 18+)
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

## API
| Method | Path | Purpose |
|---|---|---|
| GET | /api/health | `ai` or `demo` mode |
| POST | /api/sessions | `{topic, side, difficulty}` → opening statement |
| POST | /api/sessions/{id}/turn | `{argument}` → scores, fallacies, feedback, opponent reply |
| GET | /api/sessions/{id}/summary | averages, trend, fallacy counts, focus area |

## Ideas to extend
Persist sessions in SQLite/Postgres, add user accounts and progress charts, voice input,
teacher dashboard, timed rounds, and a fallacy-spotting quiz built from the student's own mistakes.
