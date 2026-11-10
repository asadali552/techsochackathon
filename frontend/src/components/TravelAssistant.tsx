import { ArrowUp, ChevronRight, LoaderCircle, MapPin, RotateCcw, X } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties, type FormEvent } from "react";

import { categoryLabels, verificationLabels } from "../maps/evidence";
import { heatmapTime, periods } from "../maps/heatmapEvidence";
import { displayBand } from "../maps/riskDisplay";
import { ApiError, askAssistant, clearAssistant } from "../services/api";
import type { Mode } from "../types/api";
import type { ChatContext, ChatLocation, ChatResult } from "../types/assistant";
import type { CellEvidence, HeatmapPeriod } from "../types/heatmap";

const examples = [
  "Is Gulgasht safe to visit tonight?",
  "Recent theft reports near Ghanta Ghar",
  "Plan a trip from Ghanta Ghar to Multan Cantt",
];
const time = (value: string) => heatmapTime(value, "Asia/Karachi");
const showScore = (item: CellEvidence) => item.score === null ? "Insufficient evidence" : `${item.score}/100`;
const count = (item: CellEvidence) => `${item.report_count} eligible`;

type Turn = { question: string; result: ChatResult };
type Prompt = { question: string; label: string };

function Result({ result, onMap, onRoutes }: {
  result: ChatResult;
  onMap: (point: ChatLocation, period?: HeatmapPeriod) => void;
  onRoutes: (result: ChatResult, id: string) => void;
}) {
  const { area, incidents, advisories, places, unavailable_sources, comparison, route_options, incident_window } = result;
  const routes = comparison?.routes ?? route_options?.routes ?? [];
  const selectedPlace = places.length === 1 ? places[0] : null;
  return (
    <div className="assistant-answer" dir="auto">
      <p>{result.answer}</p>
      {selectedPlace && <button type="button" className="text-button" onClick={() => onMap(selectedPlace.point, area?.period)}>
        <MapPin size={14} /> Show location on map
      </button>}
      {places.some((place) => place.source === "OpenStreetMap") && <a className="assistant-source" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">Place lookup © OpenStreetMap contributors</a>}
      {area && <div className="assistant-evidence">
        <strong>{area.cell ? `${area.cell_size} m heatmap cell` : `${area.radius_meters?.toLocaleString()} m area`} · {periods[area.period]}</strong>
        <dl>
          <div><dt>Community risk</dt><dd>{showScore(area.security)} · {count(area.security)}</dd></div>
          <div><dt>Road hazards</dt><dd>{showScore(area.road_hazards)} · {count(area.road_hazards)}</dd></div>
          {area.cell && area.security.score !== null && <div><dt>Map band</dt><dd>{displayBand(area.security.score).label}</dd></div>}
        </dl>
        {Object.entries({ ...area.security.category_counts, ...area.road_hazards.category_counts }).map(([category, n]) =>
          <small key={category}>{categoryLabels[category as keyof typeof categoryLabels]} · {n}</small>)}
        <small>{heatmapTime(area.window.from, area.timezone)} – {heatmapTime(area.window.to, area.timezone)} · {area.timezone}</small>
        <small>Updated {heatmapTime(area.generated_at, area.timezone, true)}. Minimum {area.methodology.minimum_reports} reports per layer. Severity, verification, recency and distance affect the score.</small>
      </div>}
      {incident_window && <div className="assistant-evidence">
        <strong>Nearby eligible reports</strong>
        <small>{time(incident_window.from)} – {time(incident_window.to)} PKT</small>
        {incidents.map((incident) => <div key={incident.id}>
          <button type="button" className="text-button" onClick={() => onMap(incident.location)}>{categoryLabels[incident.category]} <MapPin size={13} /></button>
          <small>{verificationLabels[incident.verification_status]} · {time(incident.occurred_at)} · {Math.round(incident.distance_meters)} m · {incident.is_demo ? "Fictional demo" : "Community report"}</small>
          {incident.public_summary && <p>{incident.public_summary}</p>}
        </div>)}
      </div>}
      {!!routes.length && <div className="assistant-evidence">
        <strong>Driving options · OSRM</strong>
        <small>Departure {time((comparison ?? route_options)!.departure_at)} PKT</small>
        {routes.map((route, i) => {
          const evidence = comparison?.routes.find(({ id }) => id === route.id);
          return <div className="assistant-route" key={route.id}>
            <strong>Route {i + 1} · {(route.distance_m / 1000).toFixed(1)} km · {Math.max(1, Math.round(route.duration_s / 60))} min</strong>
            {evidence && <>
              <small>Community {showScore(evidence.security)} · {count(evidence.security)}</small>
              <small>Road hazards {showScore(evidence.road_hazards)} · {count(evidence.road_hazards)}</small>
              <small>{evidence.official_zones.length ? evidence.official_zones.map((zone) => zone.properties.name).join(", ") : "No stored advisory matches"}</small>
            </>}
            <button type="button" className="text-button" onClick={() => onRoutes(result, route.id)}><MapPin size={14} /> Show route {i + 1} on map</button>
          </div>;
        })}
        <a className="assistant-source" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">Road data © OpenStreetMap contributors</a>
      </div>}
      {!!advisories.length && <div className="assistant-evidence">
        <strong>Stored advisories</strong>
        {advisories.map(({ id, properties: zone, geometry }) => <div key={id}>
          <button type="button" className="text-button" onClick={() => onMap({ type: "Point", coordinates: geometry.coordinates[0][0][0] as [number, number] })}>{zone.name} <MapPin size={13} /></button>
          <small>{zone.designation.replaceAll("_", " ")} · {zone.issuing_authority}</small>
          <small>{time(zone.effective_from)} – {zone.effective_until ? time(zone.effective_until) : "open-ended"}</small>
          {zone.last_verified_at && <small>Last verified {time(zone.last_verified_at)}</small>}
          {zone.source_url && <a className="assistant-source" href={zone.source_url} target="_blank" rel="noreferrer">Issuing source</a>}
        </div>)}
      </div>}
      {!!unavailable_sources.length && <p className="assistant-gap">Unavailable sources · {unavailable_sources.join(", ")}</p>}
    </div>
  );
}

export function TravelAssistant({ mode, token, visible, mapContext, cellContext, routeIds, onMap, onRoutes }: {
  mode: Mode;
  token?: string;
  visible: boolean;
  mapContext: ChatContext;
  cellContext: boolean;
  routeIds: string[];
  onMap: (point: ChatLocation, period?: HeatmapPeriod) => void;
  onRoutes: (result: ChatResult, id: string) => void;
}) {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [id, setId] = useState<string>();
  const [working, setWorking] = useState<Prompt | null>(null);
  const [failed, setFailed] = useState<(Prompt & { message: string }) | null>(null);
  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState(false);
  const [keyboard, setKeyboard] = useState(0);
  const pending = Boolean(working || clearing);
  const [mapOptIn, setShareMap] = useState<boolean>();
  const shareMap = mapOptIn ?? cellContext;
  const [shareRoutes, setShareRoutes] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const thread = useRef<HTMLDivElement>(null);
  const latestTurn = useRef<HTMLElement>(null);
  const last = turns.at(-1);
  const enabled = mode === "demo" || Boolean(token);
  const prompts = [
    ...(shareMap && mapContext.location ? [cellContext
      ? { question: "Explain this heatmap cell", label: "Explain this cell" }
      : { question: "Check reported safety here", label: "Check this map point" }] : []),
    ...(shareRoutes && routeIds.length ? [{ question: "Compare my available routes", label: "Compare my planned routes" }] : []),
    ...examples.map((question) => ({ question, label: question })),
  ];

  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!visible || !thread.current) return;
    if (working || failed || clearError) {
      thread.current.scrollTop = thread.current.scrollHeight;
    } else if (latestTurn.current) {
      thread.current.scrollTop = latestTurn.current.offsetTop - 14;
    }
  }, [turns, visible, working, failed, clearError]);
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!visible || !viewport) return;
    const update = () => {
      const inset = window.innerHeight - viewport.height - viewport.offsetTop;
      setKeyboard(inset > 80 && viewport.scale === 1 ? Math.round(inset) : 0);
    };
    update();
    viewport.addEventListener("resize", update);
    viewport.addEventListener("scroll", update);
    return () => {
      viewport.removeEventListener("resize", update);
      viewport.removeEventListener("scroll", update);
    };
  }, [visible]);

  async function send(question: string, label = question) {
    if (!question.trim() || controller.current || clearing || !enabled) return;
    const active = new AbortController();
    controller.current = active;
    setWorking({ question, label });
    setFailed(null);
    setClearError(false);
    try {
      const context: ChatContext = shareMap ? { ...mapContext } : {};
      if (shareRoutes && routeIds.length) context.route_ids = routeIds;
      const result = await askAssistant(question, mode, id, context, token, active.signal);
      setId(result.conversation_id);
      setTurns((old) => [...old.slice(-7), { question: label, result }]);
      setInput("");
    } catch (problem) {
      if (!active.signal.aborted) {
        setFailed({ question, label, message: problem instanceof Error ? problem.message : "The assistant is unavailable." });
      }
    } finally {
      controller.current = null;
      if (!active.signal.aborted) setWorking(null);
    }
  }

  async function clear() {
    if (controller.current || clearing) return;
    setClearing(true);
    setClearError(false);
    try {
      if (id) await clearAssistant(mode, id, token);
    } catch (problem) {
      if (!(problem instanceof ApiError && problem.status === 404)) {
        setClearError(true);
        return;
      }
    } finally {
      setClearing(false);
    }
    setId(undefined);
    setTurns([]);
    setInput("");
    setFailed(null);
    setShareMap(undefined);
    setShareRoutes(false);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (keyboard && document.activeElement instanceof HTMLTextAreaElement) document.activeElement.blur();
    void send(input);
  }

  return (
    <aside className="context-panel assistant-panel floating" aria-label="Travel assistant" hidden={!visible}
      data-keyboard={keyboard > 0} style={{ "--assistant-keyboard": `${keyboard}px` } as CSSProperties}>
      <div className="panel-header">
        <div><h2>MehfoozAI Assistant</h2><p>{mode === "demo" ? "Fictional demo" : "Live evidence"}</p></div>
        <div className="assistant-header-actions">
          <button type="button" className="icon-button" disabled={pending || (!turns.length && !failed)} aria-label="Clear conversation" title="Clear conversation" onClick={() => void clear()}><RotateCcw size={16} /></button>
          <a className="icon-button" href="#map" aria-label="Close assistant" title="Close assistant"><X size={18} /></a>
        </div>
      </div>
      <div className="assistant-thread" ref={thread} role="log" aria-label="Conversation">
        {!turns.length && !working && !failed && <div className="assistant-welcome">
          <strong>Where are you headed?</strong>
          <p>Ask about nearby reports, advisories, or a driving route.</p>
          {enabled ? <div className="assistant-prompts" aria-label="Suggested questions">
            {prompts.map(({ question, label }) => <button type="button" key={question} disabled={pending}
              onClick={() => void send(question, label)}>{label}<ChevronRight size={15} /></button>)}
          </div>
            : <p><a href="#report" className="assistant-source">Sign in</a> for live chat, or switch to the fictional demo.</p>}
        </div>}
        {turns.map((turn, index) => <article className="assistant-turn" key={index} ref={index === turns.length - 1 ? latestTurn : undefined}>
          <p className="assistant-question" dir="auto">{turn.question}</p>
          <Result result={turn.result} onMap={onMap} onRoutes={onRoutes} />
        </article>)}
        {!working && !failed && !!last?.result.choices.length && <div className="assistant-choices">
          {last.result.choices.map(({ label }, i) => <button type="button" key={i} disabled={pending} className="secondary-button"
            onClick={() => void send(String(i + 1), label)}>{label}</button>)}
        </div>}
        {(working || failed) && <article className="assistant-turn">
          <p className="assistant-question" dir="auto">{(working ?? failed)?.label}</p>
          {working && <p className="assistant-progress" role="status"><LoaderCircle size={15} /> Checking available travel data…</p>}
          {failed && <div className="assistant-error">
            <p role="alert">{failed.message}</p>
            <button type="button" className="secondary-button" disabled={pending} onClick={() => void send(failed.question, failed.label)}>Retry question</button>
          </div>}
        </article>}
        {clearing && <p className="assistant-progress" role="status">Clearing conversation…</p>}
        {clearError && <p className="assistant-error" role="alert">Couldn't clear the conversation. Try again.</p>}
      </div>
      <form className="assistant-composer" onSubmit={submit}>
        <div className="assistant-context">
          {mapContext.location && <label><input type="checkbox" checked={shareMap} onChange={(event) => setShareMap(event.target.checked)} /> {cellContext ? "Use selected cell" : "Use map point"}</label>}
          {!!routeIds.length && <label><input type="checkbox" checked={shareRoutes} onChange={(event) => setShareRoutes(event.target.checked)} /> Use planned routes</label>}
        </div>
        <div className="assistant-input">
          <textarea aria-label="Ask about travel safety" placeholder="Ask about a place or route…" rows={2} maxLength={2000}
            value={input} disabled={!enabled} readOnly={pending} onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }} />
          <button type="submit" className="primary-button" aria-label="Send question" disabled={!input.trim() || pending || !enabled}><ArrowUp size={18} /></button>
        </div>
        <small>Use public places. Providers may process questions, place names, or trip endpoints.</small>
      </form>
    </aside>
  );
}
