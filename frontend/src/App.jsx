import { useEffect, useRef, useState } from "react";
import { api } from "./api";

const DIMS = [
  ["clarity", "Clarity"], ["evidence", "Evidence"], ["logic", "Logic"], ["rebuttal", "Rebuttal"],
];
const TOPICS = [
  "Schools should ban smartphones during class",
  "Social media does more harm than good for teenagers",
  "Voting should be compulsory",
  "Homework should be abolished in primary school",
];

function Setup({ onStart, mode }) {
  const [topic, setTopic] = useState(TOPICS[0]);
  const [side, setSide] = useState("for");
  const [difficulty, setDifficulty] = useState("intermediate");
  const [busy, setBusy] = useState(false);
  const go = async () => { setBusy(true); await onStart({ topic, side, difficulty }); setBusy(false); };
  return (
    <main className="setup">
      <h1>Debate Coach</h1>
      <p className="lede">Argue a motion against an AI opponent. After each turn you get a ballot scoring your clarity, evidence, logic and rebuttal, with fallacies quoted back to you.</p>
      <label>Motion
        <input list="topics" value={topic} onChange={(e) => setTopic(e.target.value)} />
        <datalist id="topics">{TOPICS.map((t) => <option key={t} value={t} />)}</datalist>
      </label>
      <div className="row">
        <label>Your side
          <select value={side} onChange={(e) => setSide(e.target.value)}>
            <option value="for">For the motion</option><option value="against">Against the motion</option>
          </select></label>
        <label>Opponent level
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
            <option>beginner</option><option>intermediate</option><option>advanced</option>
          </select></label>
      </div>
      <button className="primary" disabled={busy || topic.length < 5} onClick={go}>{busy ? "Preparing opponent…" : "Start debate"}</button>
      {mode === "demo" && <p className="note">Offline mode: no free API key found, so scoring uses simple keyword rules. Add a free GROQ_API_KEY or GEMINI_API_KEY in backend/.env for full AI judging.</p>}
    </main>
  );
}

function Bar({ label, value }) {
  const tone = value >= 7 ? "good" : value >= 5 ? "mid" : "low";
  return (
    <div className="bar"><span>{label}</span>
      <div className="track"><i className={tone} style={{ width: `${value * 10}%` }} /></div>
      <b>{value}</b></div>
  );
}

function Ballot({ ev, trend }) {
  const [showWhy, setShowWhy] = useState(false);
  if (!ev) return <aside className="ballot empty"><h2>Ballot</h2><p>Make your first argument. Scores and feedback appear here.</p></aside>;
  return (
    <aside className="ballot">
      <h2>Ballot <span className="overall">{ev.overall}<small>/10</small></span></h2>
      <p className="note">{ev.mode === "ai" ? `Judged by AI (${ev.provider})` : "Judged by offline rules"}{ev.notice ? `. ${ev.notice}` : ""}</p>
      {DIMS.map(([k, l]) => <Bar key={k} label={l} value={ev.scores[k]} />)}
      {trend.length > 1 && (
        <svg className="spark" viewBox="0 0 100 24" preserveAspectRatio="none" aria-label="Score trend">
          <polyline fill="none" strokeWidth="1.5" points={trend.map((v, i) => `${(i / (trend.length - 1)) * 100},${24 - v * 2.2}`).join(" ")} />
        </svg>)}
      {ev.fallacies.length > 0 && <section><h3>Fallacies</h3>
        {ev.fallacies.map((f, i) => <div className="fallacy" key={i}><b>{f.name}</b><q>{f.quote}</q><p>{f.explanation}</p></div>)}</section>}
      <section><h3>What worked</h3><ul>{ev.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul></section>
      <section><h3>Improve next</h3><ul>{ev.improvements.map((s, i) => <li key={i}>{s}</li>)}</ul></section>
      <section><h3>Stronger version</h3><p className="rewrite">{ev.stronger_version}</p></section>
      <button className="link" onClick={() => setShowWhy(!showWhy)}>{showWhy ? "Hide" : "Show"} judge's reasoning</button>
      {showWhy && <dl className="why">{Object.entries(ev.reasoning).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>}
    </aside>
  );
}

function Summary({ s, onReset }) {
  return (
    <main className="setup">
      <h1>Final ballot</h1>
      <p className="lede">{s.turns} rounds. Overall <b>{s.overall}/10</b>. Focus next on <b>{s.focus_area}</b>.</p>
      <div className="summary">{DIMS.map(([k, l]) => <Bar key={k} label={l} value={s.average[k]} />)}</div>
      {Object.keys(s.fallacy_counts).length > 0 && <p>Fallacies seen: {Object.entries(s.fallacy_counts).map(([k, v]) => `${k} ×${v}`).join(", ")}.</p>}
      <button className="primary" onClick={onReset}>New debate</button>
    </main>
  );
}

export default function App() {
  const [mode, setMode] = useState("");
  const [session, setSession] = useState(null);
  const [msgs, setMsgs] = useState([]);
  const [evals, setEvals] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState(null);
  const endRef = useRef();

  useEffect(() => { api.health().then((h) => setMode(h.mode)).catch(() => setError("Backend not reachable on port 8000.")); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  const start = async (cfg) => {
    setError("");
    try {
      const r = await api.start(cfg);
      setSession({ ...cfg, id: r.id });
      setMsgs([{ role: "opponent", text: r.opening }]);
    } catch (e) { setError(e.message); }
  };
  const send = async () => {
    const arg = text.trim(); if (arg.length < 5 || busy) return;
    setText(""); setError(""); setBusy(true);
    setMsgs((m) => [...m, { role: "student", text: arg }]);
    try {
      const ev = await api.turn(session.id, arg);
      setEvals((e) => [...e, ev]);
      setMsgs((m) => [...m, { role: "opponent", text: ev.opponent_reply }]);
    } catch (e) { setError(e.message); }
    setBusy(false);
  };
  const finish = async () => { try { setSummary(await api.summary(session.id)); } catch (e) { setError(e.message); } };
  const reset = () => { setSession(null); setMsgs([]); setEvals([]); setSummary(null); };

  if (summary) return <Summary s={summary} onReset={reset} />;
  if (!session) return <><Setup onStart={start} mode={mode} />{error && <p className="error center">{error}</p>}</>;

  return (
    <div className="layout">
      <section className="chat">
        <header><div><h1>{session.topic}</h1><p>You argue <b>{session.side}</b> · opponent: {session.difficulty}</p></div>
          <button className="link" disabled={!evals.length} onClick={finish}>End and see summary</button></header>
        <div className="msgs" aria-live="polite">
          {msgs.map((m, i) => <div key={i} className={`msg ${m.role}`}><span>{m.role === "student" ? "You" : "Opponent"}</span><p>{m.text}</p></div>)}
          {busy && <div className="msg opponent"><span>Judge</span><p className="dim">Weighing your argument…</p></div>}
          <div ref={endRef} />
        </div>
        {error && <p className="error">{error}</p>}
        <div className="composer">
          <textarea rows={3} value={text} placeholder="State your claim, give evidence, then answer the opponent's last point."
            onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send(); }} />
          <button className="primary" disabled={busy || text.trim().length < 5} onClick={send}>Submit argument</button>
        </div>
      </section>
      <Ballot ev={evals[evals.length - 1]} trend={evals.map((e) => e.overall)} />
    </div>
  );
}
