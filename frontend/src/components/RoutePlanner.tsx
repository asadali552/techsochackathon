import { ArrowDownUp, ArrowRight, CarFront, Check, Clock3, LocateFixed, MapPin, RotateCcw, ShieldAlert, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { designations, formatMultanTime } from "../maps/evidence";
import { places, resolvePlace } from "../maps/places";
import { compareRoutes, findRoutes } from "../services/api";
import type { Coordinate, Mode } from "../types/api";
import type { CellEvidence } from "../types/heatmap";
import type { ComparedRoute, Endpoint, RouteComparison } from "../types/routes";

export type PickedEndpoint = { field: Endpoint; point: Coordinate };

function duration(seconds: number) {
  const minutes = Math.max(1, Math.round(seconds / 60));
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  return hours ? remaining ? `${hours} h ${remaining} min` : `${hours} h` : `${minutes} min`;
}

function risk(evidence: CellEvidence) {
  return evidence.score === null ? "Insufficient evidence" : `${evidence.score}/100`;
}

function EndpointInput({ field, value, disabled, invalid, onChange, onPick }: {
  field: Endpoint; value: string; disabled: boolean; invalid: boolean;
  onChange: (value: string) => void; onPick: () => void;
}) {
  const [open, setOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const first = useRef<HTMLButtonElement>(null);
  const start = field === "origin";
  const label = start ? "Start" : "Destination";
  const query = value.trim().toLowerCase();
  const matches = places.filter(({ name, detail }) => `${name} ${detail}`.toLowerCase().includes(query));
  const suggestions = open && !!query && !resolvePlace(value) && !disabled;

  function choose(name: string, keepFocus: boolean) {
    onChange(name);
    if (keepFocus) input.current?.focus({ preventScroll: true });
    else input.current?.blur();
    setOpen(false);
  }

  return (
    <div className="endpoint-field" onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
    }} onKeyDown={(event) => {
      if (event.key === "Escape" && suggestions) {
        input.current?.focus();
        setOpen(false);
      }
    }}>
      <span className={`journey-point ${start ? "journey-point-start" : ""}`} aria-hidden="true" />
      <label htmlFor={`journey-${field}`}>
        <span>{label}</span>
        <input id={`journey-${field}`} ref={input} value={value} placeholder={start ? "Choose starting point" : "Where to?"}
          autoComplete="off" autoCapitalize="words" enterKeyHint="search" required disabled={disabled} aria-invalid={invalid || undefined}
          onFocus={() => setOpen(true)} onChange={(event) => { onChange(event.target.value); setOpen(true); }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown" && suggestions && first.current) {
              event.preventDefault();
              first.current.focus();
            }
            if (event.key === "Enter" && suggestions && matches.length === 1) {
              event.preventDefault();
              choose(matches[0].name, true);
            }
          }} />
      </label>
      <button className="icon-button" type="button" aria-label={`Pick ${label.toLowerCase()} on map`}
        title={`Pick ${label.toLowerCase()} on map`} disabled={disabled}
        onClick={() => { setOpen(false); onPick(); }}><LocateFixed size={18} /></button>
      {suggestions && <div className="journey-suggestions" aria-label={`${label} suggestions`}>
        {matches.length > 0 ? matches.map(({ name, detail }, index) => (
          <button key={name} ref={index === 0 ? first : undefined} type="button" onPointerDown={(event) => event.preventDefault()} onClick={(event) => choose(name, event.detail === 0)}>
            <MapPin size={16} /><span><strong>{name}</strong><small>{detail}</small></span>
          </button>
        )) : <p>Try a Multan landmark, latitude and longitude, or pick on the map.</p>}
      </div>}
    </div>
  );
}

function RouteChoice({ route, index, active, onSelect }: {
  route: ComparedRoute; index: number; active: boolean; onSelect: () => void;
}) {
  const { security, road_hazards: hazards } = route;
  const advisoryCount = route.official_zones.length;
  const restriction = route.official_zones.some(({ properties }) => properties.designation === "restricted" || properties.designation === "road_closure");
  return (
    <li>
      <button type="button" className="journey-option" aria-pressed={active} onClick={onSelect}>
        <span className="journey-option-top">
          <strong>{duration(route.duration_s)}</strong>
          <span className="journey-option-number">Route {index + 1}</span>
          <span className="journey-option-check" aria-hidden="true">{active && <Check size={13} />}</span>
        </span>
        <span>{(route.distance_m / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })} km · {security.report_count + hazards.report_count} nearby reports</span>
        <span>Risk {security.score === null ? "· insufficient evidence" : risk(security)}{restriction ? " · restriction or closure" : advisoryCount ? ` · ${advisoryCount} ${advisoryCount === 1 ? "advisory" : "advisories"}` : " · advisory coverage unknown"}</span>
      </button>
    </li>
  );
}

function RouteEvidence({ route }: { route: ComparedRoute }) {
  const { security, road_hazards: hazards, official_zones: zones } = route;
  return (
    <section className="journey-evidence" aria-label="Selected route evidence">
      <h3>Route evidence</h3>
      <dl>
        <div><dt>Reported risk</dt><dd>{risk(security)} <small>{security.report_count} community reports</small></dd></div>
        <div><dt>Road hazards</dt><dd>{risk(hazards)} <small>{hazards.report_count} road reports</small></dd></div>
      </dl>
      {zones.length ? <details className="journey-advisories">
        <summary><ShieldAlert size={16} /> {zones.length === 1 ? zones[0].properties.name : `${zones.length} stored advisories`}</summary>
        <ul className="route-advisories">
          {zones.map(({ id, properties: zone }) => <li key={id}>
            <strong>{zone.name}</strong>
            <span>{designations[zone.designation].label} · {zone.is_demo ? "Fictional demo" : zone.issuing_authority}</span>
            <small>{formatMultanTime(zone.effective_from)} – {zone.effective_until ? formatMultanTime(zone.effective_until) : "Open-ended"}</small>
            {zone.source_url?.startsWith("https://") && <a className="text-button" href={zone.source_url} target="_blank" rel="noreferrer">Advisory source</a>}
          </li>)}
        </ul>
        <small>Advisory coverage may be incomplete.</small>
      </details> : <p className="journey-coverage">No stored advisory matches. Advisory coverage is unknown.</p>}
      {route.trade_offs[2] && <p className="journey-coverage">{route.trade_offs[2]}</p>}
    </section>
  );
}

export function RoutePlanner({ mode, visible, picked, result, selected, onPick, onResult, onSelect }: {
  mode: Mode;
  visible: boolean;
  picked: PickedEndpoint | null;
  result: RouteComparison | null;
  selected?: string;
  onPick: (field: Endpoint) => void;
  onResult: (value: RouteComparison | null) => void;
  onSelect: (id: string) => void;
}) {
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [departure, setDeparture] = useState("");
  const [departureOpen, setDepartureOpen] = useState(false);
  const [editing, setEditing] = useState(true);
  const [pending, setPending] = useState<"routing" | "comparing" | null>(null);
  const [error, setError] = useState("");
  const [invalid, setInvalid] = useState<Endpoint>();
  const [empty, setEmpty] = useState(false);
  const request = useRef<AbortController | null>(null);
  const section = useRef<HTMLElement>(null);
  const optionsList = useRef<HTMLUListElement>(null);
  const scope = useRef(mode);
  const active = result?.routes.find(({ id }) => id === selected) ?? result?.routes[0];

  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => {
    if (scope.current === mode) return;
    scope.current = mode;
    request.current?.abort();
    request.current = null;
    setPending(null);
    setError("");
    setInvalid(undefined);
    setEmpty(false);
  }, [mode]);
  useEffect(() => {
    if (!picked) return;
    const text = `${picked.point.latitude.toFixed(6)}, ${picked.point.longitude.toFixed(6)}`;
    (picked.field === "origin" ? setOrigin : setDestination)(text);
    setInvalid(undefined);
  }, [picked]);
  useEffect(() => {
    if (!visible) return;
    const viewport = window.visualViewport;
    const panel = section.current?.parentElement;
    if (!viewport || !panel) return;
    const resize = () => {
      const covered = Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop);
      panel.style.setProperty("--journey-keyboard", `${covered > 80 ? covered : 0}px`);
    };
    viewport.addEventListener("resize", resize);
    viewport.addEventListener("scroll", resize);
    return () => {
      viewport.removeEventListener("resize", resize);
      viewport.removeEventListener("scroll", resize);
      panel.style.removeProperty("--journey-keyboard");
    };
  }, [visible]);

  useEffect(() => {
    const list = optionsList.current;
    const option = list?.querySelector('button[aria-pressed="true"]');
    if (!list || !option || list.scrollWidth <= list.clientWidth) return;
    const frame = list.getBoundingClientRect();
    const choice = option.getBoundingClientRect();
    const left = choice.left < frame.left ? choice.left - frame.left : Math.max(0, choice.right - frame.right);
    if (left) list.scrollBy({ left, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  }, [active, editing]);

  function resetResults() {
    setError("");
    setEmpty(false);
    setInvalid(undefined);
    onResult(null);
  }

  async function plan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (request.current) return;
    const a = resolvePlace(origin), b = resolvePlace(destination);
    const date = departure ? new Date(departure) : null;
    if (!a || !b) {
      const field = !a ? "origin" : "destination";
      setInvalid(field);
      setError(`Choose a valid ${!a ? "starting point" : "destination"} from the suggestions or the map, or enter latitude and longitude.`);
      return;
    }
    if (a.latitude === b.latitude && a.longitude === b.longitude) {
      setInvalid("destination");
      setError("Choose a different destination.");
      return;
    }
    if (date && Number.isNaN(+date)) { setError("Choose a valid departure time."); return; }
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    resetResults();
    setPending("routing");
    const controller = new AbortController();
    request.current = controller;
    try {
      const options = await findRoutes(a, b, date?.toISOString(), controller.signal);
      if (controller.signal.aborted) return;
      if (!options.routes.length) {
        setEmpty(true);
        return;
      }
      setPending("comparing");
      const comparison = await compareRoutes(options.routes.map(({ id }) => id), mode, controller.signal);
      if (!controller.signal.aborted) {
        onResult(comparison);
        setEditing(false);
      }
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Route comparison failed.");
    } finally {
      if (!controller.signal.aborted) {
        request.current = null;
        setPending(null);
      }
    }
  }

  return (
    <section ref={section} className="journey-shell" aria-label="Plan Journey" hidden={!visible}>
      <div className="panel-header">
        <div><span className="eyebrow"><CarFront size={13} /> Driving · Multan pilot</span><h2>Plan journey</h2></div>
        <div className="journey-header-actions">
          {result && !editing && <button className="icon-button" type="button" aria-label="Clear trip" title="Clear trip" onClick={() => {
            setOrigin(""); setDestination(""); setDeparture(""); setDepartureOpen(false); setEditing(true); resetResults();
          }}><RotateCcw size={17} /></button>}
          <a className="icon-button" href="#map" aria-label="Close planner"><X size={19} /></a>
        </div>
      </div>
      <div className="journey-body">
        {result && !editing ? <div className="journey-summary">
          <div><strong>{origin}</strong><span><ArrowRight size={13} /> {destination}</span></div>
          <button className="text-button" type="button" onClick={() => setEditing(true)}>Edit trip</button>
        </div> : <form className="journey-form" onSubmit={plan}>
          <div className="journey-endpoints">
            <div>
              <EndpointInput field="origin" value={origin} disabled={!!pending} invalid={invalid === "origin"}
                onChange={(value) => { setOrigin(value); resetResults(); }} onPick={() => { resetResults(); onPick("origin"); }} />
              <EndpointInput field="destination" value={destination} disabled={!!pending} invalid={invalid === "destination"}
                onChange={(value) => { setDestination(value); resetResults(); }} onPick={() => { resetResults(); onPick("destination"); }} />
            </div>
            <button className="icon-button journey-swap" type="button" aria-label="Swap locations" title="Swap locations"
              disabled={!!pending || !(origin || destination)} onClick={() => {
                setOrigin(destination); setDestination(origin); resetResults();
              }}><ArrowDownUp size={19} /></button>
          </div>
          <button className="journey-departure" type="button" aria-label="Departure time" aria-expanded={departureOpen}
            disabled={!!pending} onClick={() => setDepartureOpen(!departureOpen)}>
            <Clock3 size={17} /> <span>Departure</span><strong>{departure ? new Date(departure).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }) : "Leave now"}</strong>
          </button>
          {departureOpen && <div className="journey-time">
            <label><span>Departure date and time · device time</span>
              <input type="datetime-local" value={departure} disabled={!!pending}
                onChange={(event) => { setDeparture(event.target.value); resetResults(); }} />
            </label>
            <button className="text-button" type="button" disabled={!!pending} onClick={() => {
              setDeparture(""); setDepartureOpen(false); resetResults();
            }}>Use now</button>
          </div>}
          {error && <p className="journey-feedback form-error" role="alert">{error}</p>}
          {empty && <p className="journey-feedback" role="status">No driving route was found. Try endpoints closer to a mapped road.</p>}
          {pending && <p className="journey-feedback" role="status">{pending === "routing" ? "Finding driving routes…" : "Checking reports and advisories…"}</p>}
          <div className="journey-actions">
            <button type="button" className="text-button" disabled={!!pending} onClick={() => {
              setOrigin("Ghanta Ghar"); setDestination("Multan Cantonment Railway Station"); resetResults();
            }}>Use sample trip</button>
            <button className="primary-button" type="submit" disabled={!!pending}>
              {pending ? "Working…" : "Find routes"} <ArrowRight size={16} />
            </button>
          </div>
          <p className="journey-privacy">Finding routes shares both endpoints with the routing provider.</p>
        </form>}
        {result && active && !editing && <>
          <div className="journey-result-heading">
            <strong role="status">{result.routes.length === 1 ? "1 route available" : `${result.routes.length} routes available`}</strong>
            {mode === "demo" && <span className="badge demo">Fictional evidence</span>}
          </div>
          <ul ref={optionsList} className="journey-options" aria-label="Driving options">
            {result.routes.map((route, index) => <RouteChoice key={route.id} route={route}
              index={index} active={active.id === route.id} onSelect={() => onSelect(route.id)} />)}
          </ul>
          <RouteEvidence key={active.id} route={active} />
          <p className="journey-coverage">OSRM driving estimates · Reports within {result.corridor_m} m over {result.evidence_window_days} days. Conditions and coverage can change.</p>
          <div className="route-attribution">Routing by OSRM · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a></div>
          <div className="journey-actions"><a className="text-button" href="https://www.openstreetmap.org/fixthemap" target="_blank" rel="noreferrer">Fix the map</a></div>
        </>}
      </div>
    </section>
  );
}
