"""Provider-agnostic LLM client using only free options. Uses plain httpx (no SDKs)."""
import os
import httpx

TIMEOUT = 60.0


def provider() -> str:
    forced = os.getenv("LLM_PROVIDER", "").strip().lower()
    if forced:
        return forced
    if os.getenv("GROQ_API_KEY"): return "groq"
    if os.getenv("GEMINI_API_KEY"): return "gemini"
    if os.getenv("OPENROUTER_API_KEY"): return "openrouter"
    return "demo"


def _openai_style(url, key, model, system, user, max_tokens, json_mode, extra_headers=None):
    body = {"model": model, "max_tokens": max_tokens, "temperature": 0.4,
            "messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Content-Type": "application/json", **(extra_headers or {})}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    r = httpx.post(url, json=body, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def chat(system: str, user: str, max_tokens: int = 1500, json_mode: bool = False) -> str:
    p = provider()
    if p == "groq":
        return _openai_style("https://api.groq.com/openai/v1/chat/completions", os.getenv("GROQ_API_KEY"),
                             os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), system, user, max_tokens, json_mode)
    if p == "openrouter":
        return _openai_style("https://openrouter.ai/api/v1/chat/completions", os.getenv("OPENROUTER_API_KEY"),
                             os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
                             system, user, max_tokens, False)
    if p == "ollama":
        base = os.getenv("OLLAMA_URL", "http://localhost:11434")
        return _openai_style(f"{base}/v1/chat/completions", None, os.getenv("OLLAMA_MODEL", "llama3.2"),
                             system, user, max_tokens, json_mode)
    if p == "gemini":
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {"contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.4}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        r = httpx.post(url, json=body, params={"key": os.getenv("GEMINI_API_KEY")}, timeout=TIMEOUT)
        r.raise_for_status()
        return "".join(part.get("text", "") for part in r.json()["candidates"][0]["content"]["parts"])
    raise RuntimeError("demo")
