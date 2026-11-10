import { Map, MessageSquare, Plus, Route, Shield } from "lucide-react";
import { useEffect, useState } from "react";

import type { Session } from "../services/auth";
import type { Mode } from "../types/api";
import { MapWorkspace, type Screen } from "./MapWorkspace";

const routes = [
  { id: "map", label: "Safety Map", icon: Map },
  { id: "planner", label: "Plan Journey", icon: Route },
  { id: "report", label: "Report Incident", icon: Plus },
  { id: "assistant", label: "AI Assistant", icon: MessageSquare },
] as const;

function readScreen(): Screen {
  return routes.find(({ id }) => `#${id}` === window.location.hash)?.id ?? "map";
}

export function HomePage() {
  const [screen, setScreen] = useState(readScreen);
  const [mode, setMode] = useState<Mode>(() => new URLSearchParams(window.location.search).get("demo") === "1" ? "demo" : "live");
  const [session, setSession] = useState<Session | null>(null);
  useEffect(() => {
    const onNavigate = () => setScreen(readScreen());
    window.addEventListener("hashchange", onNavigate);
    return () => window.removeEventListener("hashchange", onNavigate);
  }, []);

  return (
    <div className={`app-shell ${screen}-screen`}>
      <a href="#main-content" className="skip-link" onClick={(event) => {
        event.preventDefault();
        document.getElementById("main-content")?.focus();
      }}>Skip to map</a>
      <a href="#map" className="brand floating" aria-label="MehfoozAI home">
        <span className="brand-icon"><Shield size={21} strokeWidth={1.85} /></span>
        <span><strong>Mehfooz<span>AI</span></strong><small>Plan before you travel</small></span>
      </a>
      <main className="workspace" id="main-content" tabIndex={-1}>
        <h1 className="sr-only">Safety Map</h1>
        <MapWorkspace mode={mode} onMode={() => setMode((value) => value === "live" ? "demo" : "live")}
          screen={screen} session={session} onSession={setSession} />
      </main>
      <nav className="navigation floating" aria-label="Main navigation">
        {routes.map(({ id, label, icon: Icon }) => (
          <a href={`#${id}`} key={id} aria-current={screen === id ? "page" : undefined}>
            <Icon size={18} strokeWidth={1.8} /><span>{label}</span>
          </a>
        ))}
      </nav>
    </div>
  );
}
