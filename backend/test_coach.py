from coach import heuristic_evaluate, overall, _extract_json, _clamp

def test_overall_weighting():
    assert overall({"clarity": 10, "evidence": 10, "logic": 10, "rebuttal": 10}) == 10.0

def test_fallacy_detected():
    r = heuristic_evaluate([], "Everyone knows school uniforms are bad, and this will lead to chaos.")
    names = [f["name"] for f in r["fallacies"]]
    assert "Appeal to popularity" in names and "Slippery slope" in names

def test_evidence_raises_score():
    weak = heuristic_evaluate([], "I think it is bad.")
    strong = heuristic_evaluate([], "According to a 2022 study, 63% of students improved because uniforms reduce distraction.")
    assert strong["overall"] > weak["overall"]

def test_json_extraction_and_clamp():
    d = _extract_json('```json\n{"scores": {"clarity": 15}}\n```')
    assert _clamp(d["scores"])["clarity"] == 10

import coach, llm, json

def test_provider_autodetect(monkeypatch):
    for k in ("LLM_PROVIDER", "GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert llm.provider() == "demo"
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert llm.provider() == "groq"

def test_ai_path_with_mocked_llm(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    payload = {"reasoning": {}, "scores": {"clarity": 8, "evidence": 6, "logic": 7, "rebuttal": 5},
               "fallacies": [], "strengths": ["a"], "improvements": ["b"],
               "stronger_version": "x", "opponent_reply": "y"}
    monkeypatch.setattr(llm, "chat", lambda *a, **k: "```json\n" + json.dumps(payload) + "\n```")
    r = coach.evaluate_turn("t", "for", "beginner", [], "Some argument here.")
    assert r["mode"] == "ai" and r["overall"] == 6.5

def test_fallback_when_api_fails(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    def boom(*a, **k): raise RuntimeError("429")
    monkeypatch.setattr(llm, "chat", boom)
    r = coach.evaluate_turn("t", "for", "beginner", [], "Because data shows 50% gains, therefore it works.")
    assert r["mode"] == "demo" and "notice" in r
