"""Debate coaching engine: chain-of-thought evaluation + offline heuristic fallback."""
import json, re
import llm

WEIGHTS = {"clarity": 0.2, "evidence": 0.3, "logic": 0.3, "rebuttal": 0.2}

SYSTEM_PROMPT = """You are an expert debate coach and a fair-minded adjudicator.
You do two jobs each turn:
1. EVALUATE the student's latest argument using step-by-step reasoning.
2. Reply as the OPPONENT, arguing the opposite side at the requested difficulty.

Work through these steps IN ORDER and record each one in "reasoning":
 claim     - State the student's main claim in one sentence. Is it clear and arguable?
 evidence  - List the support offered (data, examples, authority). Is it specific, relevant, credible?
 logic     - Check whether the evidence actually leads to the claim. Note gaps and unstated assumptions.
 fallacies - Scan for logical fallacies (ad hominem, straw man, slippery slope, false dilemma,
             appeal to popularity/authority/emotion, hasty generalization, circular reasoning,
             red herring, post hoc). Only flag a fallacy you can quote.
 rebuttal  - Did the student address the opponent's strongest point directly, or dodge it?
Only AFTER the steps, assign integer scores 0-10:
 clarity, evidence, logic, rebuttal.
Rubric anchors: 0-2 absent/broken, 3-4 weak, 5-6 adequate, 7-8 strong, 9-10 exceptional.
Be strict but encouraging; never inflate scores. Judge the argument, not the student's opinion.

Return ONLY valid JSON (no markdown fences) with this shape:
{"reasoning":{"claim":"","evidence":"","logic":"","fallacies":"","rebuttal":""},
 "scores":{"clarity":0,"evidence":0,"logic":0,"rebuttal":0},
 "fallacies":[{"name":"","quote":"","explanation":""}],
 "strengths":["",""],
 "improvements":["",""],
 "stronger_version":"a tighter rewrite of the student's argument, under 70 words",
 "opponent_reply":"your counter-argument, under 120 words, ending with one probing question"}"""

OPENING_PROMPT = """Topic: "{topic}". The student argues {side}; you argue the opposite.
Difficulty: {difficulty}. Give a concise opening statement (under 100 words) for YOUR side,
with one clear claim and one piece of support. Return plain text only."""


def overall(scores: dict) -> float:
    return round(sum(scores[k] * w for k, w in WEIGHTS.items()), 1)


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def _clamp(scores: dict) -> dict:
    return {k: max(0, min(10, int(scores.get(k, 0)))) for k in WEIGHTS}


def _demo_opening(topic, side):
    opp = "against" if side == "for" else "in favour of"
    return (f"I'll argue {opp} the motion: \"{topic}\". The burden of proof lies with "
            f"those who want change, and the costs and risks are rarely counted honestly. "
            f"What is your strongest reason to disagree?")


def opening_statement(topic, side, difficulty) -> str:
    if llm.provider() == "demo":
        return _demo_opening(topic, side)
    try:
        return llm.chat("You are a skilled debate opponent.",
                        OPENING_PROMPT.format(topic=topic, side=side, difficulty=difficulty), max_tokens=300).strip()
    except Exception:
        return _demo_opening(topic, side)


def evaluate_turn(topic, side, difficulty, history, argument) -> dict:
    """history: list of {role: 'student'|'opponent', text: str}.
    Falls back to the rule-based evaluator if the free API is rate-limited or unreachable."""
    p = llm.provider()
    if p == "demo":
        return heuristic_evaluate(history, argument)
    transcript = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in history)
    user = (f"Topic: {topic}\nStudent side: {side}\nDifficulty: {difficulty}\n\n"
            f"TRANSCRIPT SO FAR:\n{transcript}\n\nSTUDENT'S LATEST ARGUMENT:\n{argument}")
    last_err = None
    for _ in range(2):  # one retry on malformed JSON
        try:
            raw = llm.chat(SYSTEM_PROMPT, user, max_tokens=1600, json_mode=True)
            data = _extract_json(raw)
            data["scores"] = _clamp(data["scores"])
            data["overall"] = overall(data["scores"])
            data["mode"] = "ai"
            data["provider"] = p
            data.setdefault("fallacies", [])
            for k, d in (("strengths", []), ("improvements", []), ("reasoning", {}),
                         ("stronger_version", ""), ("opponent_reply", "Interesting. Can you back that up?")):
                data.setdefault(k, d)
            return data
        except Exception as e:  # noqa
            last_err = e
    ev = heuristic_evaluate(history, argument)
    ev["notice"] = f"AI provider unavailable ({type(last_err).__name__}); used offline scoring for this turn."
    return ev


# ---------- offline demo mode ----------
FALLACY_PATTERNS = [
    (r"\b(everyone|everybody|nobody) (knows|agrees|thinks)\b", "Appeal to popularity",
     "Many people believing something doesn't make it true."),
    (r"\b(always|never)\b", "Hasty generalization", "Absolute words rarely survive a single counter-example."),
    (r"\bwill (inevitably )?lead to\b|\bslippery slope\b", "Slippery slope",
     "Each step in the chain needs its own justification."),
    (r"\byou('re| are) (just|simply|clearly) (stupid|wrong|biased|ignorant)", "Ad hominem",
     "Attacks the person instead of the argument."),
    (r"\beither\b.*\bor\b.*\b(nothing|else)\b", "False dilemma", "Other options likely exist."),
]
EVIDENCE = r"\b(study|studies|research|data|according to|survey|percent|%|for example|for instance|statistics)\b|\d{2,}"
LOGIC = r"\b(because|therefore|since|thus|consequently|as a result|which means)\b"
REBUT = r"\b(however|my opponent|you said|you argue|you claim|while it is true|even if|that overlooks)\b"


def heuristic_evaluate(history, argument) -> dict:
    t = argument.lower()
    words = len(t.split())
    ev = len(re.findall(EVIDENCE, t)); lg = len(re.findall(LOGIC, t)); rb = len(re.findall(REBUT, t))
    fallacies = []
    for pat, name, why in FALLACY_PATTERNS:
        m = re.search(pat, t)
        if m:
            fallacies.append({"name": name, "quote": m.group(0), "explanation": why})
    pen = min(3, len(fallacies) * 2)
    scores = _clamp({
        "clarity": 4 + (2 if 25 <= words <= 120 else 0) + (1 if "." in t else 0) - (2 if words < 10 else 0),
        "evidence": 2 + ev * 2,
        "logic": 3 + lg * 2 - pen,
        "rebuttal": 2 + rb * 3 + (1 if history and any(w in t for w in re.findall(r"\w{6,}", history[-1]["text"].lower())[:8]) else 0),
    })
    return {
        "mode": "demo", "provider": "demo",
        "reasoning": {
            "claim": f"Argument is {words} words long; clarity judged on length and structure.",
            "evidence": f"Found {ev} evidence marker(s) (data, studies, examples).",
            "logic": f"Found {lg} reasoning connective(s) such as 'because' or 'therefore'.",
            "fallacies": f"Pattern scan flagged {len(fallacies)} possible fallacy(ies).",
            "rebuttal": f"Found {rb} direct-engagement phrase(s) answering the opponent.",
        },
        "scores": scores, "overall": overall(scores), "fallacies": fallacies,
        "strengths": ["You stated a position." if words > 10 else "Concise."],
        "improvements": ["Add a concrete statistic or example." if ev < 2 else "Tie your evidence to your claim explicitly.",
                         "Quote and answer your opponent's strongest point." if rb < 1 else "Anticipate the next counter-argument."],
        "stronger_version": "(Add a free Groq/Gemini key to get an AI-written stronger version.)",
        "opponent_reply": "That's a start, but you haven't shown that your evidence outweighs the costs I raised. "
                          "What would change your mind?",
    }
