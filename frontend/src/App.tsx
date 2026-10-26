import { useCallback, useEffect, useState } from "react";
import { api, type Space, type State } from "./api";
import Home from "./screens/Home";
import Moments from "./screens/Moments";
import NorthStarScreen from "./screens/NorthStar";
import ZoomOut from "./screens/ZoomOut";
import Usage from "./screens/Usage";
import Study from "./screens/Study";

export type Screen = "home" | "moments" | "northstar" | "zoom" | "usage" | "study";

const NAV: { id: Screen; label: string }[] = [
  { id: "home", label: "Today" },
  { id: "moments", label: "Moments" },
  { id: "northstar", label: "North Star" },
  { id: "zoom", label: "Zoom Out" },
];

export interface AppCtx {
  space: Space;
  state: State | null;
  refresh: () => Promise<void>;
  go: (s: Screen, opts?: { entryId?: string; draft?: string }) => void;
  toast: (msg: string) => void;
  focusEntry: string | null;
  draft: string | null;
  clearDraft: () => void;
}

export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <rect width="64" height="64" rx="16" fill="#efe8dc" />
      <path d="M10 40 C 22 18, 34 50, 54 24" fill="none" stroke="#5e7f6b" strokeWidth="5" strokeLinecap="round" />
      <circle cx="10" cy="40" r="5" fill="#c9805e" />
      <circle cx="32" cy="34" r="4" fill="#5e7f6b" />
      <circle cx="54" cy="24" r="5" fill="#c9805e" />
    </svg>
  );
}

export default function App() {
  const [space, setSpace] = useState<Space>(() => (localStorage.getItem("tl-space") as Space) || "demo");
  const [welcomed, setWelcomed] = useState(() => localStorage.getItem("tl-welcomed") === "1");
  const [screen, setScreen] = useState<Screen>("home");
  const [state, setState] = useState<State | null>(null);
  const [health, setHealth] = useState<{ key_set: boolean; env_source: string | null } | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [focusEntry, setFocusEntry] = useState<string | null>(null);
  const [draft, setDraft] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setState(await api.state(space));
  }, [space]);

  useEffect(() => {
    setState(null);
    refresh().catch(() => setState(null));
  }, [refresh]);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ key_set: false, env_source: null }));
  }, []);

  const toast = (msg: string) => {
    setToastMsg(msg);
    window.setTimeout(() => setToastMsg(null), 3200);
  };

  const go: AppCtx["go"] = (s, opts) => {
    setFocusEntry(opts?.entryId ?? null);
    if (opts?.draft !== undefined) setDraft(opts.draft);
    setScreen(s);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const chooseSpace = (s: Space) => {
    localStorage.setItem("tl-space", s);
    localStorage.setItem("tl-welcomed", "1");
    setWelcomed(true);
    setSpace(s);
    setScreen(s === "me" ? "northstar" : "home");
  };

  const ctx: AppCtx = { space, state, refresh, go, toast, focusEntry, draft, clearDraft: () => setDraft(null) };

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <button className="brand" onClick={() => go("home")}>
            <Logo />
            <span>
              <span className="brand-name">throughline</span>
              <span className="brand-tag">your life, in perspective</span>
            </span>
          </button>
          <nav className="nav">
            {NAV.map((n) => (
              <button key={n.id} className={screen === n.id ? "active" : ""} onClick={() => go(n.id)}>
                {n.label}
              </button>
            ))}
          </nav>
          <div className="space-switch" title="Switch between the demo journal and your own">
            <button className={space === "demo" ? "active" : ""} onClick={() => chooseSpace("demo")}>Maya's demo</button>
            <button className={space === "me" ? "active" : ""} onClick={() => chooseSpace("me")}>My Throughline</button>
          </div>
        </div>
      </header>

      <main>
        {health && !health.key_set && (
          <div className="notice error" style={{ marginBottom: 24 }}>
            No <b>PORTKEY_API_KEY</b> found. Browsing works, but saving AI notes and Zoom Out need the key in a
            <code> .env</code> file in the repo folder or the folder above it. Then restart <code>python run.py</code>.
          </div>
        )}
        {!state ? (
          <p className="muted">Loading…</p>
        ) : (
          <>
            {screen === "home" && <Home ctx={ctx} />}
            {screen === "moments" && <Moments ctx={ctx} />}
            {screen === "northstar" && <NorthStarScreen ctx={ctx} />}
            {screen === "zoom" && <ZoomOut ctx={ctx} />}
            {screen === "usage" && <Usage ctx={ctx} />}
            {screen === "study" && <Study ctx={ctx} />}
          </>
        )}
      </main>

      <footer className="footer">
        <div className="footer-inner">
          <span>Private by design: your moments are stored only on this computer. Throughline is a reflection tool, not therapy.</span>
          <span className="row" style={{ gap: 16 }}>
            {space === "demo" && (
              <button onClick={async () => { await api.resetDemo(); await refresh(); toast("Maya's demo journal was reset."); }}>
                Reset demo
              </button>
            )}
            {space === "me" && (
              <button onClick={async () => {
                if (!window.confirm("Delete all of your moments, photos and North Star from this computer? This can't be undone.")) return;
                await api.resetMe(); await refresh(); toast("Your space was cleared.");
              }}>
                Clear my space
              </button>
            )}
            <button onClick={() => go("study")}>Help test Throughline</button>
            <button onClick={() => go("usage")}>Cost &amp; token usage</button>
          </span>
        </div>
      </footer>

      {!welcomed && <Welcome onChoose={chooseSpace} />}
      {toastMsg && <div className="toast">{toastMsg}</div>}
    </div>
  );
}

function Welcome({ onChoose }: { onChoose: (s: Space) => void }) {
  return (
    <div className="modal-back">
      <div className="modal">
        <div className="row" style={{ marginBottom: 18 }}>
          <Logo size={44} />
          <span className="brand-name">throughline</span>
        </div>
        <h1 style={{ fontSize: 36 }}>Your weekly step-back.</h1>
        <p className="lede">
          Life gets busy, and most of us are just trying to get through the day. Throughline gives you intentional
          space to step back and connect the pieces: save moments, photos and ideas as you go, and write down what
          matters to you and where you're headed. When a week blurs together, press <b>Zoom Out</b>. The AI finds the
          threads and opens with a question, so you never start from a blank page. It's a team effort: the AI does
          the connecting, and you do the reflecting.
        </p>
        <div className="grid grid-2" style={{ marginTop: 28 }}>
          <button className="choice" onClick={() => onChoose("demo")}>
            <div className="eyebrow">Recommended first</div>
            <h3 style={{ marginTop: 6 }}>Explore as Maya</h3>
            <p className="muted small" style={{ marginBottom: 0 }}>
              A fictional MBA student with six months of moments already saved. Try Zoom Out right away.
            </p>
          </button>
          <button className="choice" onClick={() => onChoose("me")}>
            <div className="eyebrow">Your own space</div>
            <h3 style={{ marginTop: 6 }}>Start my Throughline</h3>
            <p className="muted small" style={{ marginBottom: 0 }}>
              Set your North Star, then save a few moments of your own. Everything stays on this computer.
            </p>
          </button>
        </div>
      </div>
    </div>
  );
}
