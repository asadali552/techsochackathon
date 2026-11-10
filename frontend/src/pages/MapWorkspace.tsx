import { AlertCircle, FlaskConical, List, MapPin, Radio, UserRound, X } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";

import { HeatmapLegend, TimeControl } from "../components/HeatmapControls";
import { HeatmapDetails } from "../components/HeatmapDetails";
import { EvidenceList, IncidentDetails } from "../components/IncidentDetails";
import { MapFilters, emptyFilters } from "../components/MapFilters";
import { MapLegend } from "../components/MapLegend";
import { MapSearch } from "../components/MapSearch";
import { RoutePlanner, type PickedEndpoint } from "../components/RoutePlanner";
import { TravelAssistant } from "../components/TravelAssistant";
import { ReportPanel } from "../components/ReportPanel";
import { useMapData } from "../hooks/useMapData";
import { SafetyMap } from "../maps/SafetyMap";
import type { MapDestination } from "../maps/places";
import type { HeatmapView } from "../maps/riskDisplay";
import type { Endpoint, RouteComparison, RouteLine } from "../types/routes";
import { dimensions } from "../maps/heatmapEvidence";
import { getHeatmap, getIncidents, getOfficialZones, mapPageSize } from "../services/api";
import type { Session } from "../services/auth";
import type { Bounds, Coordinate, Incident, IncidentFilters, Mode, Selection, Zone } from "../types/api";
import type { ChatContext, ChatLocation, ChatResult } from "../types/assistant";
import type { HeatmapPeriod, RiskDimension } from "../types/heatmap";

export type Screen = "map" | "report" | "planner" | "assistant";
const noIncidents: Incident[] = [];
const noZones: Zone[] = [];
const noRoutes: RouteLine[] = [];

export function MapWorkspace({ mode, onMode, screen, session, onSession }: {
  mode: Mode;
  onMode: () => void;
  screen: Screen;
  session: Session | null;
  onSession: (session: Session | null) => void;
}) {
  const mapScreen = screen === "map";
  const reporting = screen === "report";
  const planning = screen === "planner";
  const journeyPanel = useRef<HTMLElement>(null);
  const assisting = screen === "assistant";
  const [bounds, setBounds] = useState<Bounds | null>(null);
  const [filters, setFilters] = useState(emptyFilters);
  const [showIncidents, setShowIncidents] = useState(true);
  const [showZones, setShowZones] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [retry, setRetry] = useState(0);
  const [period, setPeriod] = useState<HeatmapPeriod>("full_day");
  const [view, setView] = useState<HeatmapView>("risk");
  const [dimension, setDimension] = useState<RiskDimension>("security");
  const [heatmapRefresh, setHeatmapRefresh] = useState(0);
  const [selection, setSelection] = useState<Selection | { kind: "cell"; id: string; mode: Mode } | null>(null);
  const [showReports, setShowReports] = useState(false);
  const [picking, setPicking] = useState(false);
  const [point, setPoint] = useState<Coordinate | null>(null);
  const [destination, setDestination] = useState<MapDestination | null>(null);
  const [journey, setJourney] = useState<RouteComparison | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<string>();
  const [routePicking, setRoutePicking] = useState<Endpoint | null>(null);
  const [picked, setPicked] = useState<PickedEndpoint | null>(null);
  const trip = journey?.mode === mode ? journey : null;
  const [assistantCell, setAssistantCell] = useState<{ mode: Mode; context: ChatContext } | null>(null);
  const [assistantTrip, setAssistantTrip] = useState<ChatResult | null>(null);
  const [assistantRoute, setAssistantRoute] = useState<string>();
  const shownAssistant = screen === "map" && assistantTrip?.mode === mode ? assistantTrip : null;
  const assistantLines = shownAssistant?.comparison?.routes ?? shownAssistant?.route_options?.routes;
  const usingAssistantRoute = Boolean(assistantLines?.length);
  function showAssistantLocation(point: ChatLocation, historicalPeriod?: HeatmapPeriod) {
    setAssistantTrip(null);
    setDestination({ latitude: point.coordinates[1], longitude: point.coordinates[0], zoom: 15 });
    if (historicalPeriod) {
      setPeriod(historicalPeriod);
      setShowHeatmap(true);
      setView("risk");
    }
    window.location.hash = "map";
  }
  function showAssistantRoute(result: ChatResult, id: string) {
    setAssistantTrip(result);
    setAssistantRoute(id);
    setShowZones(true);
    window.location.hash = "map";
  }
  function saveJourney(result: RouteComparison | null) {
    setJourney(result);
    setSelectedRoute(result?.routes[0]?.id);
  }
  const [lastScreen, setLastScreen] = useState(screen);
  if (lastScreen !== screen) {
    setLastScreen(screen);
    setSelection(null);
    setShowReports(false);
    setPicking(false);
    setPoint(null);
    setRoutePicking(null);
  }

  const start = filters.start ? new Date(filters.start) : null;
  const end = filters.end ? new Date(filters.end) : null;
  const invalidDates = Boolean((start && Number.isNaN(+start)) || (end && Number.isNaN(+end)) || (start && end && start >= end));
  const startTime = start && !invalidDates ? start.toISOString() : undefined;
  const endTime = end && !invalidDates ? end.toISOString() : undefined;
  const requestFilters = useMemo<IncidentFilters>(() => ({
    category: filters.category || undefined,
    verification_status: filters.verification || undefined,
    start_time: startTime,
    end_time: endTime,
  }), [filters.category, filters.verification, startTime, endTime]);

  const updateBounds = useCallback((next: Bounds) => {
    setBounds((old) => old && old.min_lat === next.min_lat && old.max_lat === next.max_lat
      && old.min_lng === next.min_lng && old.max_lng === next.max_lng ? old : next);
  }, []);
  const loadIncidents = useCallback((signal: AbortSignal) => getIncidents(bounds!, mode, requestFilters, signal), [bounds, mode, requestFilters]);
  const loadZones = useCallback((signal: AbortSignal) => getOfficialZones(bounds!, mode, signal), [bounds, mode]);
  const incidentsState = useMapData(bounds && showIncidents && !invalidDates
    ? JSON.stringify([mode, bounds, requestFilters, retry]) : null, loadIncidents);
  const zonesState = useMapData(bounds && showZones ? JSON.stringify([mode, bounds, retry]) : null, loadZones);
  const loadHeatmap = useCallback((signal: AbortSignal) => getHeatmap(bounds!, mode, period, startTime, endTime, signal),
    [bounds, mode, period, startTime, endTime]);
  const scope = JSON.stringify([mode, period, startTime, endTime]);
  const heatmapState = useMapData(bounds && showHeatmap && !reporting && !invalidDates
    ? JSON.stringify([scope, bounds, heatmapRefresh]) : null, loadHeatmap, scope);
  const heatmap = heatmapState.status === "success" ? heatmapState.data
    : heatmapState.status === "loading" ? heatmapState.previous ?? null : null;
  const selectedCell = selection?.kind === "cell" && selection.mode === mode
    ? heatmap?.cells.features.find(({ id }) => id === selection.id) : undefined;
  const page = incidentsState.status === "success" && incidentsState.data.mode === mode ? incidentsState.data : null;
  const incidents = page?.items ?? noIncidents;
  const currentZones = zonesState.status === "success" && zonesState.data.mode === mode ? zonesState.data.features : noZones;
  const plannedZones = usingAssistantRoute
    ? shownAssistant?.comparison?.routes.find(({ id }) => id === assistantRoute)?.official_zones
    : trip?.routes.find(({ id }) => id === selectedRoute)?.official_zones;
  const zones = useMemo(() => !showZones ? noZones : !plannedZones?.length ? currentZones
    : [...new Map([...currentZones, ...plannedZones].map((item) => [item.id, item])).values()],
  [showZones, currentZones, plannedZones]);
  const incident = selection?.kind === "incident" ? incidents.find((item) => item.id === selection.id) : undefined;
  const zone = selection?.kind === "zone" ? zones.find((item) => item.id === selection.id) : undefined;
  const loading = !bounds || incidentsState.status === "loading" || zonesState.status === "loading";
  const error = incidentsState.status === "error" ? incidentsState.message
    : zonesState.status === "error" ? zonesState.message : null;

  function selectIncident(item: Incident) {
    if (screen === "map" || planning) setSelection({ kind: "incident", id: item.id });
  }

  function selectZone(item: Zone) {
    if (screen === "map" || planning) setSelection({ kind: "zone", id: item.id });
  }

  const displayPanel = reporting || showReports || incident || zone || selectedCell;
  const mapContext: ChatContext = assistantCell?.mode === mode ? assistantCell.context : {
    location: bounds ? {
      type: "Point",
      coordinates: [Number(((bounds.min_lng + bounds.max_lng) / 2).toFixed(4)), Number(((bounds.min_lat + bounds.max_lat) / 2).toFixed(4))],
    } : undefined,
    period, start_time: startTime, end_time: endTime, cell_size: heatmap?.cell_size,
  };

  return (
    <>
      <SafetyMap heatmap={heatmap} dimension={dimension} view={view} selectedIncident={incident?.id}
        fitPanel={planning ? journeyPanel : undefined}
        routes={!reporting && !routePicking ? assistantLines ?? trip?.routes ?? noRoutes : noRoutes}
        selectedRoute={usingAssistantRoute ? assistantRoute : selectedRoute}
        onRoute={usingAssistantRoute ? setAssistantRoute : setSelectedRoute}
        onCell={screen === "map" ? (id) => { setAssistantCell(null); setSelection({ kind: "cell", id, mode }); } : undefined}
        incidents={incidents} zones={zones} point={reporting ? point : null} picking={(reporting && picking) || Boolean(routePicking)}
        pickLabel={routePicking ? routePicking === "origin" ? "Choose the start" : "Choose the destination" : undefined}
        destination={destination} onBounds={updateBounds} onPick={(next) => {
          if (routePicking) {
            setPicked({ field: routePicking, point: next });
            setRoutePicking(null);
          } else {
            setPoint(next);
            setPicking(false);
          }
        }}
        onCancelPick={() => { setPicking(false); setRoutePicking(null); }} onIncident={selectIncident} onZone={selectZone} />

      {!reporting && !planning && <MapSearch incidents={incidents} onPlace={(place) => { setSelection(null); setShowReports(false); setDestination({ ...place }); }}
        onIncident={selectIncident} />}
      <div className="map-tools" aria-label="Map settings">
        {!reporting && <div className="map-tools-main floating">
          {showHeatmap && <TimeControl period={period} onPeriod={setPeriod} />}
          <MapFilters filters={filters} setFilters={setFilters} invalidDates={invalidDates}
            modified={Boolean(filters.category || filters.verification || filters.start || filters.end
              || !showHeatmap || !showIncidents || !showZones || view !== "risk" || dimension !== "security")}>
            <label className="layer-option"><input type="checkbox" checked={showHeatmap} onChange={(event) => setShowHeatmap(event.target.checked)} /> Heatmap</label>
            {showHeatmap && <label className="layer-dimension">Heatmap view
              <select aria-label="Heatmap visualization" value={view} onChange={(event) => setView(event.target.value as HeatmapView)}>
                <option value="risk">Safety risk</option><option value="activity">Incident activity</option>
              </select>
            </label>}
            {showHeatmap && <label className="layer-dimension">Evidence layer
              <select aria-label="Reported risk layer" value={dimension} onChange={(event) => setDimension(event.target.value as RiskDimension)}>
                {Object.entries(dimensions).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select>
            </label>}
            <label className="layer-option"><input type="checkbox" checked={showIncidents} onChange={(event) => setShowIncidents(event.target.checked)} /> Community reports</label>
            <label className="layer-option"><input type="checkbox" checked={showZones} onChange={(event) => setShowZones(event.target.checked)} /> Official zones</label>
            <MapLegend />
          </MapFilters>
        </div>}
        <div className="map-tools-account floating">
          <button className="mode-button" type="button" aria-label="Demo mode" aria-pressed={mode === "demo"} onClick={onMode}>
            {mode === "live" ? <Radio size={15} /> : <FlaskConical size={16} />}
            {mode === "demo" ? "Fictional demo" : "Live data"}
          </button>
          {!reporting && <a className="account-button" href="#report" aria-label={session ? "Reporting account" : "Sign in to report"}>
            <UserRound size={17} /><span>{session ? "Account" : "Sign in"}</span>
          </a>}
        </div>
      </div>

      {(screen === "map" || planning) && <div className={`map-key floating ${planning ? "map-key-planning" : ""}`}>
        <div className="view-status">
          <span><MapPin size={14} /> {mapScreen ? "In this view" : "Multan pilot"}</span>
          {screen === "map" && <button type="button" aria-pressed={showReports} onClick={() => {
            setSelection(null);
            setShowReports((value) => !value);
          }}><List size={15} />{loading ? "Reports" : `${incidents.length} ${incidents.length === 1 ? "report" : "reports"}`}</button>}
        </div>
        {showHeatmap && <HeatmapLegend data={heatmap} dimension={dimension} view={view} onView={setView}
          loading={heatmapState.status === "loading" || !bounds}
          error={invalidDates ? "Correct the date range." : heatmapState.status === "error" ? heatmapState.message : null}
          continuousScale={mapScreen || planning} customDates={Boolean(filters.start || filters.end)} onRefresh={() => setHeatmapRefresh((value) => value + 1)} />}
      </div>}
      {error && !showReports && !reporting && <div className="data-notice floating" role="alert">
        <AlertCircle size={16} /><span>{error}</span>
        <button className="text-button" type="button" onClick={() => setRetry((value) => value + 1)}>Retry map data</button>
      </div>}
      <aside ref={journeyPanel} className="context-panel journey-panel floating" aria-label="Journey planner" hidden={!planning || Boolean(routePicking || incident || zone)}>
        <RoutePlanner mode={mode} visible={planning} picked={picked} result={trip} selected={selectedRoute}
          onPick={setRoutePicking} onResult={saveJourney} onSelect={setSelectedRoute} />
      </aside>
      <TravelAssistant key={JSON.stringify([mode, session?.token])} visible={assisting} mode={mode} token={session?.token}
        mapContext={mapContext} cellContext={assistantCell?.mode === mode} routeIds={trip?.routes.map(({ id }) => id) ?? []} onMap={showAssistantLocation} onRoutes={showAssistantRoute} />
      {displayPanel && <aside className={reporting ? "context-panel report-panel floating" : "context-panel floating"} hidden={assisting || (reporting && picking)} aria-label={reporting ? "Report panel" : "Map details"}>
        {reporting ? <ReportPanel mode={mode} point={point} picking={picking} session={session} onSession={onSession}
          onChoosePoint={() => setPicking((value) => !value)}
          onSearchPoint={(next) => { setPoint(next); setDestination({ ...next, zoom: 15 }); }} onClearPoint={() => setPoint(null)} />
          : incident || zone ? <IncidentDetails incident={incident} zone={zone} onClose={() => setSelection(null)} />
          : heatmap && selectedCell ? <HeatmapDetails data={heatmap} cell={selectedCell} dimension={dimension} view={view} onClose={() => setSelection(null)}
            onAsk={() => {
              const [west, south] = selectedCell.geometry.coordinates[0].reduce(([x, y], [lng, lat]) => [Math.min(x, lng), Math.min(y, lat)], [Infinity, Infinity]);
              const [east, north] = selectedCell.geometry.coordinates[0].reduce(([x, y], [lng, lat]) => [Math.max(x, lng), Math.max(y, lat)], [-Infinity, -Infinity]);
              setAssistantCell({ mode, context: { location: { type: "Point", coordinates: [(west + east) / 2, (south + north) / 2] },
                period, start_time: heatmap.window.from, end_time: heatmap.window.to, cell_size: heatmap.cell_size } });
              window.location.hash = "assistant";
            }} />
          : <section aria-label="Reports in view">
            <div className="panel-header"><div><span className="eyebrow">Current map view</span><h2>Reports in view</h2></div>
              <button className="icon-button" type="button" autoFocus aria-label="Close reports" onClick={() => setShowReports(false)}><X size={19} /></button></div>
            <div className="evidence-body">
              {loading && <p className="feed-message" role="status">Loading map records…</p>}
              {error && <div className="feed-error" role="alert">{error} <button className="text-button" type="button"
                onClick={() => setRetry((value) => value + 1)}>Retry map data</button></div>}
              {!loading && !error && !incidents.length && !zones.length && <p className="feed-message">No records in this view. Local conditions may be unreported.</p>}
              <EvidenceList incidents={incidents} zones={zones} onIncident={selectIncident} onZone={selectZone} />
              {page?.items.length === mapPageSize && <p className="feed-message">Showing up to {mapPageSize} reports. Zoom in to narrow the area.</p>}
            </div>
          </section>}
      </aside>}
    </>
  );
}
