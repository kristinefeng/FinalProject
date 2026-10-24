import { useEffect, useRef, useState } from "react";
import type { AppCtx } from "../App";
import { api, niceDate, usd, type CareResources, type FeedbackResult, type Pattern, type TraceStep, type ZoomOutResult } from "../api";

const STEPS = [
  "Memory Keeper is gathering the moments that matter",
  "Pattern Finder is looking for the threads between them",
  "Checking every quote against your own words",
  "Mirror is writing your reflection",
];

const KIND_LABEL: Record<Pattern["kind"], string> = {
  alignment: "Living it",
  tension: "A quiet tension",
  growth: "How you've grown",
  forgotten: "Gone quiet",
};

export function CareCard({ care }: { care: CareResources }) {
  return (
    <div className="care">
      <h3>{care.title}</h3>
      <p style={{ color: "var(--ink-2)" }}>{care.body}</p>
      {care.options.map((o) => (
        <a className="option" key={o.label} href={o.href}>
          <b>{o.label}</b> <span className="muted small">· {o.detail}</span>
        </a>
      ))}
    </div>
  );
}

export default function ZoomOut({ ctx }: { ctx: AppCtx }) {
  const { space, state } = ctx;
  const [preset, setPreset] = useState<"season" | "story" | "ask">("season");
  const [question, setQuestion] = useState("");
  const [running, setRunning] = useState(false);
  const [stepIdx, setStepIdx] = useState(0);
  const [result, setResult] = useState<ZoomOutResult | null>(null);
  const [isPast, setIsPast] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    const last = state?.insights?.[0];
    if (last && !result) {
      api.insight(space, last.id).then((r) => { setResult(r); setIsPast(true); }).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [space]);

  const run = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    setStepIdx(0);
    timer.current = window.setInterval(() => setStepIdx((i) => Math.min(i + 1, STEPS.length - 1)), 2600);
    try {
      const r = await api.zoomOut(space, preset === "ask" ? "story" : preset, preset === "ask" ? question : undefined);
      setResult(r);
      setIsPast(false);
      await ctx.refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      if (timer.current) window.clearInterval(timer.current);
      setRunning(false);
    }
  };

  const entries = state?.entries ?? [];
  const photoFor = (id: string) => entries.find((e) => e.id === id)?.photo_url ?? null;

  return (
    <div className="stack" style={{ gap: 30 }}>
      <div>
        <div className="eyebrow">Zoom Out</div>
        <h1 style={{ marginTop: 6 }}>Step back and see the bigger picture.</h1>
        <p className="lede">Three agents read your moments next to your North Star. Every observation comes with the exact words it's based on, and you get the last word.</p>
      </div>

      <section className="stack">
        <div className="focus-options">
          <button className={`focus-option ${preset === "season" ? "active" : ""}`} onClick={() => setPreset("season")}>
            <h3>This season</h3>
            <p className="muted small" style={{ margin: "4px 0 0" }}>The last three months of moments.</p>
          </button>
          <button className={`focus-option ${preset === "story" ? "active" : ""}`} onClick={() => setPreset("story")}>
            <h3>The whole story</h3>
            <p className="muted small" style={{ margin: "4px 0 0" }}>Everything you've saved, start to now.</p>
          </button>
          <button className={`focus-option ${preset === "ask" ? "active" : ""}`} onClick={() => setPreset("ask")}>
            <h3>Ask your own question</h3>
            <p className="muted small" style={{ margin: "4px 0 0" }}>“When have I felt most like myself?”</p>
          </button>
        </div>
        {preset === "ask" && (
          <input type="text" value={question} maxLength={300} placeholder="When have I felt most like myself this year?" onChange={(e) => setQuestion(e.target.value)} />
        )}
        <div className="row">
          <button className="btn sage" disabled={running || (preset === "ask" && !question.trim())} onClick={run}>
            {running ? "Zooming out…" : "Zoom out"}
          </button>
          <span className="muted small">Usually 10–30 seconds · about a tenth of a cent per run on gpt-6-luna</span>
        </div>
      </section>

      {running && (
        <div className="card progress">
          {STEPS.map((s, i) => (
            <div key={s} className={`step ${i < stepIdx ? "done" : i === stepIdx ? "now" : ""}`}><span className="dot" />{s}</div>
          ))}
        </div>
      )}
      {error && <div className="notice error">{error}</div>}

      {result && !running && <ResultView result={result} isPast={isPast} ctx={ctx} photoFor={photoFor} />}
    </div>
  );
}

function ResultView({ result, isPast, ctx, photoFor }: { result: ZoomOutResult; isPast: boolean; ctx: AppCtx; photoFor: (id: string) => string | null }) {
  if (result.status === "care" && result.care) return <CareCard care={result.care} />;
  if (result.status !== "ok") {
    return (
      <div className="stack">
        <div className="notice warn">{result.message}</div>
        {result.trace && <TraceView trace={result.trace} ledger={result.ledger} dropped={result.dropped} />}
      </div>
    );
  }
  const patterns = result.patterns ?? [];
  const photos = Array.from(new Set(patterns.flatMap((p) => p.evidence.map((e) => e.memory_id))))
    .map(photoFor)
    .filter(Boolean)
    .slice(0, 5) as string[];

  return (
    <div className="stack" style={{ gap: 26 }}>
      <article className="reflection">
        <div className="row">
          <div className="eyebrow">{isPast ? "Your last Zoom Out" : "Your bigger picture"} · {result.focus}</div>
        </div>
        <h1 style={{ marginTop: 10 }}>{result.headline}</h1>
        <p className="text">{result.reflection}</p>
        {photos.length > 0 && (
          <div className="photo-strip">{photos.map((p) => <div key={p} style={{ backgroundImage: `url(${p})` }} />)}</div>
        )}
        <div className="question-box">
          <div className="eyebrow">A question to sit with</div>
          <p className="serif" style={{ margin: "6px 0 0" }}>{result.question}</p>
        </div>
      </article>

      <section className="stack">
        <div>
          <div className="eyebrow">The throughlines behind it</div>
          <h2 style={{ marginTop: 4 }}>Does this feel true to you?</h2>
          <p className="muted" style={{ margin: "6px 0 0" }}>Each one is built only from your words. Tell Throughline where it's right and where it's not. It will listen, and remember next time.</p>
        </div>
        {patterns.map((p, i) => (
          <PatternCard key={i} pattern={p} index={i} insightId={result.id!} ctx={ctx} photoFor={photoFor} />
        ))}
      </section>

      {result.trace && <TraceView trace={result.trace} ledger={result.ledger} dropped={result.dropped} notes={result.search_notes} />}
    </div>
  );
}

function PatternCard({ pattern: p, index, insightId, ctx, photoFor }: { pattern: Pattern; index: number; insightId: string; ctx: AppCtx; photoFor: (id: string) => string | null }) {
  const [verdict, setVerdict] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [reply, setReply] = useState<FeedbackResult | null>(null);
  const [decided, setDecided] = useState<string | null>(null);

  const send = async () => {
    if (!verdict) return;
    setSending(true);
    try {
      setReply(await api.feedback(ctx.space, insightId, index, verdict, note));
    } catch (e: any) {
      ctx.toast(e.message);
    } finally {
      setSending(false);
    }
  };

  const decide = async (d: "accept" | "dismiss") => {
    if (!reply?.proposal) return;
    await api.decide(ctx.space, reply.proposal.id, d);
    setDecided(d);
    await ctx.refresh();
    ctx.toast(d === "accept" ? "Your North Star was updated." : "Suggestion dismissed. Nothing changed.");
  };

  const action = reply?.proposal?.action;
  return (
    <article className="card pattern">
      <div className="row" style={{ gap: 10 }}>
        <span className={`kind ${p.kind}`}>{KIND_LABEL[p.kind]}</span>
        {p.value && <span className="chip sage" style={{ margin: 0 }}>{p.value}</span>}
      </div>
      <h3 style={{ marginTop: 12 }}>{p.title}</h3>
      <p style={{ color: "var(--ink-2)", margin: "8px 0 14px" }}>{p.observation}</p>
      <div>
        {p.evidence.map((ev) => {
          const photo = photoFor(ev.memory_id);
          return (
            <div className="evidence" key={ev.memory_id + ev.quote} onClick={() => ctx.go("moments", { entryId: ev.memory_id })} title="Open this moment">
              <div className="thumb" style={photo ? { backgroundImage: `url(${photo})` } : {}}>{photo ? "" : "“"}</div>
              <div>
                <div className="quote">“{ev.quote}”</div>
                <div className="muted small">{ev.title} · {niceDate(ev.date)}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="reflect-back">
        {!reply ? (
          <div className="stack" style={{ gap: 10 }}>
            <div className="verdicts">
              {[["resonates", "This resonates"], ["partly", "Partly"], ["not_me", "Not me"]].map(([v, label]) => (
                <button key={v} className={verdict === v ? "active" : ""} onClick={() => setVerdict(v)}>{label}</button>
              ))}
            </div>
            {verdict && (
              <>
                <textarea rows={3} style={{ minHeight: 70 }} value={note} onChange={(e) => setNote(e.target.value)}
                  placeholder={verdict === "resonates" ? "What does it bring up for you? (optional)" : "What feels more true? (optional)"} />
                <div><button className="btn small" disabled={sending} onClick={send}>{sending ? "Listening…" : "Tell Throughline"}</button></div>
              </>
            )}
          </div>
        ) : (
          <div>
            <div className="mirror-reply">
              <div className="eyebrow" style={{ color: "var(--sage)" }}>Mirror</div>
              <p style={{ margin: "4px 0" }}>{reply.reply}</p>
              <p className="serif" style={{ margin: 0, fontStyle: "italic", fontSize: 18 }}>{reply.follow_up_question}</p>
            </div>
            {reply.proposal && (
              <div className="proposal">
                <div className="eyebrow" style={{ color: "var(--sage)" }}>Suggested change to your North Star</div>
                <p style={{ margin: "6px 0" }}>
                  {action === "add_value" && <>Add the value <b>{reply.proposal.value_name}</b>: “{reply.proposal.new_text}”</>}
                  {action === "reword_value" && <>Reword <b>{reply.proposal.value_name}</b> to: “{reply.proposal.new_text}”</>}
                  {action === "add_intention" && <>Add the intention: “{reply.proposal.new_text}”</>}
                </p>
                <p className="muted small" style={{ margin: "0 0 10px" }}>Why: {reply.proposal.reason}</p>
                {decided ? (
                  <span className="muted small">{decided === "accept" ? "Accepted. Your North Star now says this." : "Dismissed. Nothing changed."}</span>
                ) : (
                  <div className="row">
                    <button className="btn sage small" onClick={() => decide("accept")}>Accept</button>
                    <button className="btn secondary small" onClick={() => decide("dismiss")}>Not now</button>
                    <span className="muted small">Nothing changes unless you accept.</span>
                  </div>
                )}
              </div>
            )}
            {reply.trace && <div className="muted small" style={{ marginTop: 10 }}>Mirror used {reply.trace[0]?.tokens?.input ?? 0} input + {reply.trace[0]?.tokens?.output ?? 0} output tokens · {usd(reply.ledger?.total_cost_usd)}{reply.trace[0]?.tools?.length ? ` · called ${reply.trace[0].tools!.map((t) => t.tool).join(", ")}` : ""}</div>}
          </div>
        )}
      </div>
    </article>
  );
}

export function TraceView({ trace, ledger, dropped, notes }: { trace: TraceStep[]; ledger?: ZoomOutResult["ledger"]; dropped?: ZoomOutResult["dropped"]; notes?: string }) {
  return (
    <details className="card trace">
      <summary>
        How this was made · {trace.filter((t) => t.tokens).length} agent steps · {ledger?.totals.input_tokens.toLocaleString()} input tokens
        ({ledger?.totals.cache_read_tokens.toLocaleString()} cached) · {ledger?.totals.output_tokens.toLocaleString()} output · {usd(ledger?.total_cost_usd)} ▾
      </summary>
      <div style={{ marginTop: 14 }}>
        {trace.map((t, i) => (
          <div key={i} className={`trace-step ${t.tokens ? "" : "code"}`}>
            <div className="num">{i + 1}</div>
            <div>
              <div className="row" style={{ gap: 8 }}>
                <b>{t.agent}</b>
                <span className="muted small">{t.step}</span>
                {t.status !== "ok" && <span className="chip clay">{t.status}: {t.reason}</span>}
              </div>
              {t.tools?.map((c, j) => (
                <div className="tool-call" key={j}>
                  → {c.tool}({Object.entries(c.args || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})
                  {c.result && <div className="muted" style={{ marginTop: 4 }}>← {c.result.slice(0, 220)}{c.result.length > 220 ? "…" : ""}</div>}
                </div>
              ))}
              {t.agent === "Memory Keeper" && notes && <div className="small" style={{ marginTop: 4 }}>Picked {t.output?.memory_ids?.length} moments: {notes}</div>}
              {t.agent === "Grounding check" && (
                <div className="small" style={{ marginTop: 4 }}>
                  {dropped && dropped.length ? (
                    <>Dropped {dropped.length} piece{dropped.length > 1 ? "s" : ""} of evidence:
                      <ul style={{ margin: "4px 0" }}>{dropped.map((d, k) => <li key={k}>{d.pattern}: {d.quote ? `“${d.quote}” ` : ""}({d.reason})</li>)}</ul>
                    </>
                  ) : <>Every quote matched the entry it cites. Nothing was dropped.</>}
                </div>
              )}
              {t.tokens && (
                <div className="meter" style={{ marginTop: 6 }}>
                  <span><b>{t.requests}</b> request{t.requests === 1 ? "" : "s"}</span>
                  <span><b>{t.tokens.input.toLocaleString()}</b> input ({t.tokens.cached_input.toLocaleString()} cached)</span>
                  <span><b>{t.tokens.output.toLocaleString()}</b> output ({t.tokens.reasoning} reasoning)</span>
                  <span><b>{usd(t.cost_usd)}</b></span>
                  {t.seconds !== undefined && <span>{t.seconds}s</span>}
                </div>
              )}
            </div>
          </div>
        ))}
        {ledger && (
          <p className="muted small" style={{ marginBottom: 0 }}>
            Model {ledger.model}. Caps: {usd(ledger.budget_usd)} per run, {usd(ledger.daily_budget_usd)} per day ({usd(ledger.spent_today_usd)} used today), and a fixed number of requests per agent.
          </p>
        )}
      </div>
    </details>
  );
}
