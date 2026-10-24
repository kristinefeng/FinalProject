export type Space = "demo" | "me";

export interface Tags {
  themes?: string[];
  values?: string[];
  feelings?: string[];
  people?: string[];
  places?: string[];
}

export interface Entry {
  id: string;
  date: string;
  title: string;
  text: string;
  summary: string | null;
  tags: Tags;
  photo_desc: string | null;
  photo_url: string | null;
  care_flag: boolean;
  injection_flags: { rule: string; match: string }[];
}

export interface Value {
  name: string;
  meaning: string;
}

export interface NorthStar {
  values: Value[];
  vision: string;
  intentions: string[];
  updated_at: string | null;
}

export interface Evidence {
  memory_id: string;
  quote: string;
  date: string;
  title: string;
  photo: string | null;
}

export interface Pattern {
  title: string;
  kind: "alignment" | "tension" | "growth" | "forgotten";
  observation: string;
  value: string | null;
  evidence: Evidence[];
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  result: string | null;
}

export interface TraceStep {
  agent: string;
  step?: string;
  status: string;
  reason?: string;
  requests?: number;
  tools?: ToolCall[];
  tokens?: { input: number; cached_input: number; cache_write: number; output: number; reasoning: number } | null;
  cost_usd?: number;
  seconds?: number;
  output?: any;
}

export interface Ledger {
  model: string;
  total_cost_usd: number;
  budget_usd: number;
  daily_budget_usd: number;
  spent_today_usd: number;
  totals: { requests: number; input_tokens: number; cache_read_tokens: number; cache_write_tokens: number; output_tokens: number; reasoning_tokens: number };
}

export interface CareResources {
  title: string;
  body: string;
  options: { label: string; detail: string; href: string }[];
}

export interface ZoomOutResult {
  status: "ok" | "care" | "too_few" | "no_patterns" | "budget" | "stopped";
  message?: string;
  care?: CareResources;
  id?: string;
  focus?: string;
  headline?: string;
  reflection?: string;
  question?: string;
  patterns?: Pattern[];
  dropped?: { pattern: string; memory_id: string | null; quote: string | null; reason: string }[];
  search_notes?: string;
  trace?: TraceStep[];
  ledger?: Ledger;
}

export interface Proposal {
  id: string;
  action: "add_value" | "reword_value" | "add_intention";
  value_name: string;
  new_text: string;
  reason: string;
}

export interface FeedbackResult {
  status: string;
  message?: string;
  reply?: string;
  follow_up_question?: string;
  proposal?: Proposal | null;
  trace?: TraceStep[];
  ledger?: Ledger;
}

export interface SaveResult {
  entry: Entry;
  care: CareResources | null;
  held_back: { rule: string; match: string }[] | null;
  indexed: boolean;
  warning?: string;
  ledger?: Ledger;
  trace?: TraceStep[];
}

export interface State {
  space: Space;
  north_star: NorthStar;
  entries: Entry[];
  insights: { id: string; headline: string; focus: string; question: string }[];
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body as T;
}

const json = (method: string, data: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});

export const api = {
  health: () => call<{ ok: boolean; key_set: boolean; env_source: string | null; model: string }>("/api/health"),
  state: (s: Space) => call<State>(`/api/${s}/state`),
  resetDemo: () => call("/api/demo/reset", { method: "POST" }),
  resetMe: () => call("/api/me/reset", { method: "POST" }),
  saveEntry: (s: Space, form: FormData) => call<SaveResult>(`/api/${s}/entries`, { method: "POST", body: form }),
  releaseEntry: (s: Space, id: string) => call<SaveResult>(`/api/${s}/entries/${id}/release`, { method: "POST" }),
  deleteEntry: (s: Space, id: string) => call(`/api/${s}/entries/${id}`, { method: "DELETE" }),
  saveNorthStar: (s: Space, ns: Omit<NorthStar, "updated_at">) => call<NorthStar>(`/api/${s}/north_star`, json("PUT", ns)),
  zoomOut: (s: Space, preset: string, question?: string) =>
    call<ZoomOutResult>(`/api/${s}/zoom_out`, json("POST", { preset, question: question || null })),
  insight: (s: Space, id: string) => call<ZoomOutResult>(`/api/${s}/insights/${id}`),
  feedback: (s: Space, insightId: string, pattern_index: number, verdict: string, note: string) =>
    call<FeedbackResult>(`/api/${s}/insights/${insightId}/feedback`, json("POST", { pattern_index, verdict, note })),
  decide: (s: Space, proposalId: string, decision: "accept" | "dismiss") =>
    call<{ status: string; north_star: NorthStar }>(`/api/${s}/proposals/${proposalId}/${decision}`, { method: "POST" }),
  usage: () => call<{ model: string; run_budget_usd: number; daily_budget_usd: number; spent_today_usd: number; runs: any[] }>("/api/usage"),
  saveStudy: (participant: string, phase: string, answers: Record<string, number>, comment: string) =>
    call("/api/study", json("POST", { participant, phase, answers, comment })),
  study: () => call<{ responses: any[] }>("/api/study"),
};

export function usd(n: number | undefined | null): string {
  const v = n ?? 0;
  if (v === 0) return "$0";
  if (v >= 0.01) return `$${v.toFixed(2)}`;
  if (v >= 0.0001) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(6)}`;
}

export function niceDate(iso: string, opts: Intl.DateTimeFormatOptions = { month: "long", day: "numeric", year: "numeric" }): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, opts);
}
