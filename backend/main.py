import uuid
from typing import Literal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()
import coach  # noqa: E402  (after load_dotenv)

app = FastAPI(title="AI Debate Coach")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])
SESSIONS: dict[str, dict] = {}  # in-memory; swap for a DB in production


class NewSession(BaseModel):
    topic: str = Field(min_length=5, max_length=200)
    side: Literal["for", "against"]
    difficulty: Literal["beginner", "intermediate", "advanced"] = "intermediate"


class Turn(BaseModel):
    argument: str = Field(min_length=5, max_length=2000)


def _get(sid):
    if sid not in SESSIONS:
        raise HTTPException(404, "Session not found")
    return SESSIONS[sid]


@app.get("/api/health")
def health():
    p = coach.llm.provider()
    return {"ok": True, "mode": "demo" if p == "demo" else "ai", "provider": p}


@app.post("/api/sessions")
def create_session(body: NewSession):
    opening = coach.opening_statement(body.topic, body.side, body.difficulty)
    sid = uuid.uuid4().hex[:10]
    SESSIONS[sid] = {**body.model_dump(), "id": sid, "turns": [],
                     "history": [{"role": "opponent", "text": opening}]}
    return {"id": sid, "opening": opening}


@app.post("/api/sessions/{sid}/turn")
def submit_turn(sid: str, body: Turn):
    s = _get(sid)
    try:
        ev = coach.evaluate_turn(s["topic"], s["side"], s["difficulty"], s["history"], body.argument)
    except Exception as e:
        raise HTTPException(502, str(e))
    s["history"] += [{"role": "student", "text": body.argument},
                     {"role": "opponent", "text": ev["opponent_reply"]}]
    s["turns"].append({"argument": body.argument, **ev})
    return ev


@app.get("/api/sessions/{sid}/summary")
def summary(sid: str):
    s = _get(sid)
    turns = s["turns"]
    if not turns:
        raise HTTPException(400, "No turns yet")
    avg = {k: round(sum(t["scores"][k] for t in turns) / len(turns), 1) for k in coach.WEIGHTS}
    fall = {}
    for t in turns:
        for f in t["fallacies"]:
            fall[f["name"]] = fall.get(f["name"], 0) + 1
    weakest = min(avg, key=avg.get)
    return {"turns": len(turns), "average": avg, "overall": coach.overall(avg),
            "trend": [t["overall"] for t in turns], "fallacy_counts": fall,
            "focus_area": weakest}
