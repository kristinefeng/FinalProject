import { useMemo, useState } from "react";
import type { AppCtx } from "../App";
import { niceDate } from "../api";

const PROMPTS = [
  "What's one small thing from today you'd like to remember a year from now?",
  "When did you feel most like yourself this week?",
  "What has been giving you energy lately, and what has been taking it?",
  "Who made your day a little better recently?",
  "What did you notice today that you usually rush past?",
  "What would the version of you from a year ago be surprised by today?",
  "What's something you're carrying that you could set down for tonight?",
];

function dayOfYear(d = new Date()) {
  return Math.floor((d.getTime() - new Date(d.getFullYear(), 0, 0).getTime()) / 86400000);
}

export default function Home({ ctx }: { ctx: AppCtx }) {
  const { state, go, space } = ctx;
  const entries = state?.entries ?? [];
  const ns = state?.north_star;
  const last = state?.insights?.[0];
  const prompt = PROMPTS[dayOfYear() % PROMPTS.length];

  // A memory worth revisiting: a photo moment from at least a month before the newest one.
  const candidates = useMemo(() => {
    const withPhoto = entries.filter((e) => e.photo_url && !e.care_flag);
    if (!withPhoto.length) return [];
    const newest = entries[0]?.date ?? "";
    const cutoff = new Date(newest);
    cutoff.setDate(cutoff.getDate() - 30);
    const older = withPhoto.filter((e) => e.date <= cutoff.toISOString().slice(0, 10));
    return older.length ? older : withPhoto;
  }, [entries]);
  const [pick, setPick] = useState(() => dayOfYear());
  const memory = candidates.length ? candidates[pick % candidates.length] : null;

  const today = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  const firstName = space === "demo" ? "Maya" : null;

  if (space === "me" && entries.length === 0) {
    return (
      <div className="stack" style={{ gap: 28 }}>
        <div>
          <div className="eyebrow">{today}</div>
          <h1 style={{ marginTop: 8 }}>Welcome to your Throughline.</h1>
          <p className="lede">Three small steps, and then you can zoom out on your own life.</p>
        </div>
        <div className="grid grid-3">
          {[
            ["1", "Write your North Star", "Your values and goals, in your own words. It takes two minutes and you can change it anytime.", "northstar", "Set my North Star"],
            ["2", "Save three moments", "Something from this week, a photo you love, an idea you don't want to lose.", "moments", "Add a moment"],
            ["3", "Zoom Out", "The AI connects the pieces and opens with a question. You do the reflecting.", "zoom", "Try Zoom Out"],
          ].map(([n, t, d, target, cta]) => (
            <div className="card stack" key={n}>
              <div className="stat" style={{ color: "var(--clay)" }}>{n}</div>
              <h3>{t}</h3>
              <p className="muted" style={{ margin: 0 }}>{d}</p>
              <div><button className="btn secondary small" onClick={() => go(target as any)}>{cta}</button></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="stack" style={{ gap: 28 }}>
      <section className="hero">
        <div>
          <div className="eyebrow">{today}</div>
          <h1 style={{ marginTop: 8 }}>A moment for yourself{firstName ? `, ${firstName}` : ""}.</h1>
          <p className="lede">You don't have to figure everything out today. Look back, check in, or zoom out.</p>
        </div>
        <div className="zoom-cta">
          <svg className="orbit" width="220" height="220" viewBox="0 0 220 220" aria-hidden>
            <circle cx="110" cy="110" r="100" fill="none" stroke="#fff" strokeWidth="2" />
            <circle cx="110" cy="110" r="64" fill="none" stroke="#fff" strokeWidth="2" />
            <circle cx="110" cy="110" r="28" fill="none" stroke="#fff" strokeWidth="2" />
          </svg>
          <div className="eyebrow" style={{ color: "rgba(255,255,255,.7)" }}>Your weekly step-back</div>
          <h2 style={{ marginTop: 6 }}>Help me see the bigger picture.</h2>
          <p style={{ margin: "8px 0 18px" }}>
            Throughline connects this week's moments to what matters to you and opens with a question. The AI does the connecting; you do the reflecting.
          </p>
          <button className="btn" onClick={() => go("zoom")}>Zoom out on this week →</button>
        </div>
      </section>

      <section className="grid grid-3">
        {memory ? (
          <div className="card memory-card">
            <div className="photo" style={{ backgroundImage: `url(${memory.photo_url})` }} />
            <div className="body">
              <div className="eyebrow">A memory worth revisiting</div>
              <h3 style={{ marginTop: 6 }}>{memory.title || niceDate(memory.date)}</h3>
              <p className="muted small" style={{ margin: "2px 0 10px" }}>{niceDate(memory.date)}</p>
              <p style={{ margin: 0, color: "var(--ink-2)" }}>{memory.summary || memory.text.slice(0, 140) + "…"}</p>
              <div className="row" style={{ marginTop: 12 }}>
                <button className="btn link" onClick={() => go("moments", { entryId: memory.id })}>Open this moment</button>
                {candidates.length > 1 && <button className="btn link" onClick={() => setPick((p) => p + 1)}>Show me another</button>}
              </div>
            </div>
          </div>
        ) : (
          <div className="card"><div className="eyebrow">A memory worth revisiting</div><p className="muted">Add a moment with a photo and it will resurface here.</p></div>
        )}

        <div className="card prompt-card stack">
          <div className="eyebrow">Today's check-in</div>
          <p className="serif" style={{ margin: 0 }}>{prompt}</p>
          <p className="muted small" style={{ margin: 0 }}>No streaks, no pressure. Write a line or a page.</p>
          <div><button className="btn" onClick={() => go("moments", { draft: prompt })}>Write about it</button></div>
        </div>

        <div className="card stack">
          <div className="eyebrow">Your North Star</div>
          {ns && ns.values.length ? (
            <>
              <div className="values-row">{ns.values.map((v) => <span className="chip sage" key={v.name}>{v.name}</span>)}</div>
              {ns.vision && <p className="serif" style={{ margin: 0, fontSize: 17, color: "var(--ink-2)" }}>“{ns.vision.length > 170 ? ns.vision.slice(0, 170) + "…" : ns.vision}”</p>}
            </>
          ) : (
            <p className="muted" style={{ margin: 0 }}>You haven't written down what matters to you yet.</p>
          )}
          <div><button className="btn link" onClick={() => go("northstar")}>{ns?.values.length ? "Revisit" : "Set it now"}</button></div>
        </div>
      </section>

      {last && (
        <section className="card row" style={{ justifyContent: "space-between" }}>
          <div>
            <div className="eyebrow">Your last Zoom Out</div>
            <h3 style={{ marginTop: 6 }}>{last.headline}</h3>
            <p className="muted" style={{ margin: "4px 0 0", fontStyle: "italic" }}>{last.question}</p>
          </div>
          <button className="btn secondary" onClick={() => go("zoom")}>Revisit</button>
        </section>
      )}
    </div>
  );
}
