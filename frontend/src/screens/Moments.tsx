import { useEffect, useMemo, useRef, useState } from "react";
import type { AppCtx } from "../App";
import { api, niceDate, usd, type CareResources, type Entry } from "../api";
import { CareCard } from "./ZoomOut";

const todayIso = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

export default function Moments({ ctx }: { ctx: AppCtx }) {
  const { state, space, refresh, toast, focusEntry, draft, clearDraft } = ctx;
  const entries = state?.entries ?? [];
  const [date, setDate] = useState(todayIso());
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [care, setCare] = useState<CareResources | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (draft) {
      setTitle("");
      setText("");
      setNotice(`Prompt: ${draft}`);
      clearDraft();
    }
  }, [draft, clearDraft]);

  useEffect(() => {
    if (focusEntry) {
      window.setTimeout(() => document.getElementById(`m-${focusEntry}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 150);
    }
  }, [focusEntry]);

  const onPhoto = (f: File | null) => {
    setPhoto(f);
    setPreview(f ? URL.createObjectURL(f) : null);
  };

  const save = async () => {
    if (!text.trim()) return;
    setSaving(true);
    setCare(null);
    try {
      const form = new FormData();
      form.append("date", date);
      form.append("title", title);
      form.append("text", text);
      if (photo) form.append("photo", photo);
      const res = await api.saveEntry(space, form);
      if (res.care) {
        setCare(res.care);
      } else if (res.held_back) {
        toast("Saved. One part looked like instructions to an AI, so it's held back from the agents.");
      } else if (res.warning) {
        toast(res.warning);
      } else {
        toast(`Saved and indexed by the Memory Keeper (${usd(res.ledger?.total_cost_usd)}).`);
      }
      setTitle("");
      setText("");
      setNotice(null);
      onPhoto(null);
      await refresh();
    } catch (e: any) {
      toast(e.message);
    } finally {
      setSaving(false);
    }
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter((e) =>
      [e.title, e.text, e.summary, e.photo_desc, ...(Object.values(e.tags || {}).flat() as string[])]
        .filter(Boolean)
        .some((s) => (s as string).toLowerCase().includes(q)),
    );
  }, [entries, query]);

  const byMonth = useMemo(() => {
    const groups: [string, Entry[]][] = [];
    for (const e of filtered) {
      const key = niceDate(e.date, { month: "long", year: "numeric" });
      const g = groups.find(([k]) => k === key);
      if (g) g[1].push(e);
      else groups.push([key, [e]]);
    }
    return groups;
  }, [filtered]);

  return (
    <div className="moments-layout">
      <aside className="composer card stack">
        <div>
          <div className="eyebrow">Capture</div>
          <h2 style={{ marginTop: 4 }}>Save a moment</h2>
        </div>
        {notice && <div className="notice info small">{notice}</div>}
        <div className="grid grid-2" style={{ gap: 10 }}>
          <label className="field">Date<input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
          <label className="field">Title<input type="text" value={title} placeholder="Optional" onChange={(e) => setTitle(e.target.value)} /></label>
        </div>
        <label className="field">
          What happened, or what's on your mind?
          <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="A moment, a thought, an idea you don't want to lose. A line or a page; nobody else reads this." rows={7} />
        </label>
        <div className="photo-drop" onClick={() => fileRef.current?.click()}>
          {preview ? <img src={preview} alt="Selected" /> : "＋ Add a photo (optional)"}
          <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => onPhoto(e.target.files?.[0] ?? null)} />
        </div>
        {preview && <button className="btn link small" onClick={() => onPhoto(null)}>Remove photo</button>}
        <button className="btn" disabled={saving || !text.trim()} onClick={save}>
          {saving ? "Saving and indexing…" : "Save moment"}
        </button>
        <p className="muted small" style={{ margin: 0 }}>
          The Memory Keeper adds a one-line summary and tags so Zoom Out can find this moment by meaning. You can delete any moment.
        </p>
        {care && <CareCard care={care} />}
      </aside>

      <section>
        <div className="row" style={{ marginBottom: 18 }}>
          <div>
            <div className="eyebrow">Look back</div>
            <h2 style={{ marginTop: 4 }}>{space === "demo" ? "Maya's moments" : "Your moments"}</h2>
          </div>
          <div className="spacer" />
          <input type="text" style={{ maxWidth: 240 }} placeholder="Search moments…" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        {!entries.length && <p className="muted">No moments yet. Your first one goes on the left.</p>}
        {byMonth.map(([month, list]) => (
          <div key={month}>
            <div className="eyebrow month">{month}</div>
            {list.map((e) => (
              <MomentCard key={e.id} entry={e} ctx={ctx} highlight={e.id === focusEntry} />
            ))}
          </div>
        ))}
      </section>
    </div>
  );
}

function MomentCard({ entry: e, ctx, highlight }: { entry: Entry; ctx: AppCtx; highlight: boolean }) {
  const [open, setOpen] = useState(highlight);
  const [busy, setBusy] = useState(false);
  const held = e.injection_flags?.length > 0;

  const release = async () => {
    setBusy(true);
    try {
      await api.releaseEntry(ctx.space, e.id);
      await ctx.refresh();
      ctx.toast("Released. The agents can now read this moment (still marked as data, never as instructions).");
    } catch (err: any) {
      ctx.toast(err.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!window.confirm("Delete this moment and its photo? This can't be undone.")) return;
    await api.deleteEntry(ctx.space, e.id);
    await ctx.refresh();
    ctx.toast("Moment deleted.");
  };

  return (
    <article id={`m-${e.id}`} className={`card moment ${e.photo_url ? "" : "nophoto"} ${highlight ? "highlight" : ""}`}>
      {e.photo_url && <div className="photo" style={{ backgroundImage: `url(${e.photo_url})` }} role="img" aria-label={e.photo_desc || "Photo"} />}
      <div className="body">
        <div className="row" style={{ gap: 8 }}>
          <h3>{e.title || "Untitled moment"}</h3>
          <span className="spacer" />
          <span className="muted small">{niceDate(e.date)}</span>
        </div>
        <p className={`text ${open ? "" : "clamp"}`}>{e.text}</p>
        <div className="row" style={{ gap: 14 }}>
          <button className="btn link small" onClick={() => setOpen(!open)}>{open ? "Show less" : "Read all"}</button>
          <button className="btn link small" style={{ color: "var(--muted)" }} onClick={remove}>Delete</button>
        </div>
        {e.care_flag ? (
          <div className="held">This moment is private to you. Throughline doesn't analyze entries like this one, and Zoom Out pauses for two weeks after it.</div>
        ) : held ? (
          <div className="held">
            <b>Held back from the AI.</b> Part of this entry reads like instructions to an AI (“{e.injection_flags[0].match}”), so the agents can't see it.
            If you wrote it as a normal journal entry, you can release it.{" "}
            <button className="btn link small" disabled={busy} onClick={release}>{busy ? "Releasing…" : "Release to the agents"}</button>
          </div>
        ) : e.summary ? (
          <div className="ai-notes">
            <div><span className="label">Memory Keeper</span>{e.summary}</div>
            <div style={{ marginTop: 6 }}>
              {(e.tags?.values ?? []).map((v) => <span className="chip sage" key={"v" + v}>{v}</span>)}
              {(e.tags?.themes ?? []).map((t) => <span className="chip" key={"t" + t}>{t}</span>)}
              {(e.tags?.feelings ?? []).map((f) => <span className="chip clay" key={"f" + f}>{f}</span>)}
            </div>
            {e.photo_desc && <div className="muted small">Photo: {e.photo_desc}</div>}
          </div>
        ) : null}
      </div>
    </article>
  );
}
