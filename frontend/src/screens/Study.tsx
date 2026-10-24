import { useEffect, useState } from "react";
import type { AppCtx } from "../App";
import { api } from "../api";

const QUESTIONS = [
  { id: "connected", q: "I feel connected to my recent experiences." },
  { id: "perspective", q: "I have a clear perspective on what matters to me." },
  { id: "reflected", q: "I've had a chance to step back and reflect on my life." },
];

export default function Study({ ctx }: { ctx: AppCtx }) {
  const [participant, setParticipant] = useState("");
  const [phase, setPhase] = useState<"before" | "after">("before");
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [comment, setComment] = useState("");
  const [responses, setResponses] = useState<any[]>([]);

  const load = () => api.study().then((r) => setResponses(r.responses)).catch(() => {});
  useEffect(() => { load(); }, []);

  const submit = async () => {
    await api.saveStudy(participant, phase, answers, comment);
    ctx.toast(phase === "before" ? "Thanks! Now try Throughline, then come back for the 'after' questions." : "Thank you, that's really helpful.");
    setAnswers({});
    setComment("");
    if (phase === "before") {
      setPhase("after");
      ctx.go("zoom");
    }
    load();
  };

  const avg = (p: string, id: string) => {
    const xs = responses.filter((r) => r.phase === p && r.answers[id]).map((r) => r.answers[id]);
    return xs.length ? (xs.reduce((a: number, b: number) => a + b, 0) / xs.length).toFixed(1) : "–";
  };

  return (
    <div className="stack" style={{ gap: 26, maxWidth: 860 }}>
      <div>
        <div className="eyebrow">Help test Throughline</div>
        <h1 style={{ marginTop: 6 }}>A two-minute check-in, before and after.</h1>
        <p className="lede">Answer these before you try Throughline, use it for about ten minutes, then answer them again. Use initials if you prefer.</p>
      </div>
      <section className="card stack">
        <div className="grid grid-2">
          <label className="field">Your name or initials<input type="text" value={participant} onChange={(e) => setParticipant(e.target.value)} /></label>
          <label className="field">When<select value={phase} onChange={(e) => setPhase(e.target.value as any)}><option value="before">Before using Throughline</option><option value="after">After using Throughline</option></select></label>
        </div>
        {QUESTIONS.map((q) => (
          <div key={q.id} className="stack" style={{ gap: 8 }}>
            <div>{q.q}</div>
            <div className="row">
              <span className="muted small">Strongly disagree</span>
              <div className="likert">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button key={n} className={answers[q.id] === n ? "active" : ""} onClick={() => setAnswers({ ...answers, [q.id]: n })}>{n}</button>
                ))}
              </div>
              <span className="muted small">Strongly agree</span>
            </div>
          </div>
        ))}
        {phase === "after" && (
          <label className="field">What, if anything, did Throughline help you notice? Would you use it again?
            <textarea rows={4} value={comment} onChange={(e) => setComment(e.target.value)} />
          </label>
        )}
        <div><button className="btn" disabled={!participant.trim() || Object.keys(answers).length < QUESTIONS.length} onClick={submit}>Submit</button></div>
      </section>

      {responses.length > 0 && (
        <section className="card">
          <h3>Results so far ({new Set(responses.map((r) => r.participant)).size} people)</h3>
          <table className="data" style={{ marginTop: 10 }}>
            <thead><tr><th>Question</th><th className="num">Before (avg)</th><th className="num">After (avg)</th></tr></thead>
            <tbody>{QUESTIONS.map((q) => <tr key={q.id}><td>{q.q}</td><td className="num">{avg("before", q.id)}</td><td className="num">{avg("after", q.id)}</td></tr>)}</tbody>
          </table>
          {responses.filter((r) => r.comment).map((r) => (
            <p key={r.id} className="serif" style={{ fontSize: 17, margin: "14px 0 0" }}>“{r.comment}” <span className="muted small">— {r.participant}</span></p>
          ))}
        </section>
      )}
    </div>
  );
}
