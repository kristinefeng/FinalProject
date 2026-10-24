import { useEffect, useState } from "react";
import type { AppCtx } from "../App";
import { api, usd } from "../api";

const KIND: Record<string, string> = {
  zoom_out: "Zoom Out",
  reflect_back: "Reflect Back",
  index_moment: "Save a moment",
};

type Run = { id: string; kind: string; created_at: string; cost_usd: number; status: string; space: string; ledger: any };

export default function Usage({ ctx }: { ctx: AppCtx }) {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.usage>> | null>(null);
  useEffect(() => {
    api.usage().then(setData).catch((e) => ctx.toast(e.message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) return <p className="muted">Loading…</p>;
  const runs: Run[] = data.runs;
  const kinds = ["zoom_out", "reflect_back", "index_moment"];
  const summary = kinds.map((k) => {
    const rs = runs.filter((r) => r.kind === k && r.status === "ok");
    const sum = (f: (r: Run) => number) => rs.reduce((a, r) => a + f(r), 0);
    const n = rs.length || 1;
    return {
      kind: k,
      count: rs.length,
      avgCost: sum((r) => r.cost_usd) / n,
      avgIn: sum((r) => r.ledger.totals.input_tokens) / n,
      avgCached: sum((r) => r.ledger.totals.cache_read_tokens) / n,
      avgOut: sum((r) => r.ledger.totals.output_tokens) / n,
    };
  });
  // A typical active month: 20 saved moments, 4 Zoom Outs, 4 Reflect Backs.
  const perMonth = 20 * summary[2].avgCost + 4 * summary[0].avgCost + 4 * summary[1].avgCost;

  return (
    <div className="stack" style={{ gap: 26 }}>
      <div>
        <div className="eyebrow">Tokenomics</div>
        <h1 style={{ marginTop: 6 }}>What Throughline costs to run</h1>
        <p className="lede">Every model request is metered as it happens. These are the real numbers from this computer on {data.model}.</p>
      </div>

      <section className="grid grid-3">
        <div className="card"><div className="eyebrow">One Zoom Out (average)</div><div className="stat">{usd(summary[0].avgCost)}</div><div className="muted small">{Math.round(summary[0].avgIn).toLocaleString()} input · {Math.round(summary[0].avgCached).toLocaleString()} cached · {Math.round(summary[0].avgOut).toLocaleString()} output tokens</div></div>
        <div className="card"><div className="eyebrow">One user, one month</div><div className="stat">{usd(perMonth)}</div><div className="muted small">20 moments + 4 Zoom Outs + 4 Reflect Backs</div></div>
        <div className="card"><div className="eyebrow">10,000 users, one month</div><div className="stat">{usd(perMonth * 10000)}</div><div className="muted small">At the same usage; caps of {usd(data.run_budget_usd)} per run and {usd(data.daily_budget_usd)} per day stop runaway spend</div></div>
      </section>

      <section className="card">
        <h3>Average per action</h3>
        <table className="data" style={{ marginTop: 10 }}>
          <thead><tr><th>Action</th><th className="num">Runs</th><th className="num">Input</th><th className="num">Cached input</th><th className="num">Output</th><th className="num">Cost</th></tr></thead>
          <tbody>
            {summary.map((s) => (
              <tr key={s.kind}>
                <td>{KIND[s.kind]}</td><td className="num">{s.count}</td>
                <td className="num">{Math.round(s.avgIn).toLocaleString()}</td><td className="num">{Math.round(s.avgCached).toLocaleString()}</td>
                <td className="num">{Math.round(s.avgOut).toLocaleString()}</td><td className="num">{usd(s.avgCost)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <div className="row"><h3>Every run</h3><span className="spacer" /><span className="muted small">Spent today: {usd(data.spent_today_usd)} of {usd(data.daily_budget_usd)}</span></div>
        <table className="data" style={{ marginTop: 10 }}>
          <thead><tr><th>When</th><th>Action</th><th>Space</th><th>Status</th><th className="num">Requests</th><th className="num">Input</th><th className="num">Cached</th><th className="num">Output</th><th className="num">Cost</th></tr></thead>
          <tbody>
            {runs.slice(0, 60).map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</td>
                <td>{KIND[r.kind] ?? r.kind}</td><td>{r.space}</td><td>{r.status}</td>
                <td className="num">{r.ledger.totals.requests}</td>
                <td className="num">{r.ledger.totals.input_tokens.toLocaleString()}</td>
                <td className="num">{r.ledger.totals.cache_read_tokens.toLocaleString()}</td>
                <td className="num">{r.ledger.totals.output_tokens.toLocaleString()}</td>
                <td className="num">{usd(r.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
