import { useEffect, useState } from "react";
import type { AppCtx } from "../App";
import { api, type Value } from "../api";

const SUGGESTED = ["Connection", "Adventure", "Growth", "Health", "Family", "Creativity", "Purpose", "Rest", "Learning", "Faith", "Community", "Freedom"];

export default function NorthStarScreen({ ctx }: { ctx: AppCtx }) {
  const ns = ctx.state!.north_star;
  const [values, setValues] = useState<Value[]>(ns.values);
  const [vision, setVision] = useState(ns.vision);
  const [intentions, setIntentions] = useState<string[]>(ns.intentions);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setValues(ns.values);
    setVision(ns.vision);
    setIntentions(ns.intentions);
  }, [ns]);

  const setValue = (i: number, patch: Partial<Value>) => setValues(values.map((v, j) => (i === j ? { ...v, ...patch } : v)));
  const unused = SUGGESTED.filter((s) => !values.some((v) => v.name.toLowerCase() === s.toLowerCase()));

  const save = async () => {
    setSaving(true);
    try {
      await api.saveNorthStar(ctx.space, { values, vision, intentions });
      await ctx.refresh();
      ctx.toast("North Star saved.");
      if (ctx.space === "me" && !ctx.state?.entries.length) ctx.go("moments");
    } catch (e: any) {
      ctx.toast(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="stack" style={{ gap: 26, maxWidth: 860 }}>
      <div>
        <div className="eyebrow">Look ahead</div>
        <h1 style={{ marginTop: 6 }}>{ctx.space === "demo" ? "Maya's North Star" : "Your North Star"}</h1>
        <p className="lede">
          Not goals to hit. A few things that matter to you, in your own words. Zoom Out holds your moments up against
          these, and you can change them anytime, including when a reflection shows you something new.
        </p>
      </div>

      <section className="card stack">
        <div className="row">
          <h3>What matters to me</h3>
          <span className="spacer" />
          <span className="muted small">3–5 values works best</span>
        </div>
        {values.map((v, i) => (
          <div className="value-row" key={i}>
            <input type="text" value={v.name} placeholder="Value" onChange={(e) => setValue(i, { name: e.target.value })} />
            <input type="text" value={v.meaning} placeholder="What it means to me…" onChange={(e) => setValue(i, { meaning: e.target.value })} />
            <button className="btn danger small" onClick={() => setValues(values.filter((_, j) => j !== i))} aria-label="Remove">✕</button>
          </div>
        ))}
        <div>
          {values.length < 8 && unused.slice(0, 8).map((s) => (
            <button key={s} className="chip" style={{ border: 0, cursor: "pointer" }} onClick={() => setValues([...values, { name: s, meaning: "" }])}>
              ＋ {s}
            </button>
          ))}
          {values.length < 8 && (
            <button className="chip" style={{ border: 0, cursor: "pointer" }} onClick={() => setValues([...values, { name: "", meaning: "" }])}>＋ Your own</button>
          )}
        </div>
      </section>

      <section className="card stack">
        <h3>The life I hope to be living</h3>
        <p className="muted small" style={{ margin: 0 }}>A few sentences about five years from now. Not a plan, more of a picture.</p>
        <textarea value={vision} rows={5} onChange={(e) => setVision(e.target.value)} placeholder="I hope I'm living somewhere that…" />
      </section>

      <section className="card stack">
        <h3>Intentions for this season</h3>
        {intentions.map((t, i) => (
          <div className="row" key={i} style={{ flexWrap: "nowrap" }}>
            <input type="text" value={t} onChange={(e) => setIntentions(intentions.map((x, j) => (j === i ? e.target.value : x)))} />
            <button className="btn danger small" onClick={() => setIntentions(intentions.filter((_, j) => j !== i))} aria-label="Remove">✕</button>
          </div>
        ))}
        {intentions.length < 6 && (
          <div><button className="btn secondary small" onClick={() => setIntentions([...intentions, ""])}>＋ Add an intention</button></div>
        )}
      </section>

      <div className="row">
        <button className="btn" disabled={saving} onClick={save}>{saving ? "Saving…" : "Save North Star"}</button>
        <button className="btn secondary" onClick={() => ctx.go("zoom")}>Go to Zoom Out</button>
      </div>
    </div>
  );
}
