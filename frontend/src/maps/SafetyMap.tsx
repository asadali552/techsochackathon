import { CRS, DomEvent, type LatLng, type LatLngBoundsExpression, type LatLngTuple } from "leaflet";
import { AlertCircle, Crosshair, LocateFixed, Minus, Plus, ScanLine, X } from "lucide-react";
import { useEffect, useRef, useState, type RefObject } from "react";
import { CircleMarker, MapContainer, Pane, TileLayer, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";

import type { MapDestination } from "./places";
import type { Bounds, Coordinate, Incident, Zone } from "../types/api";
import type { Heatmap, RiskDimension } from "../types/heatmap";
import type { RouteLine } from "../types/routes";
import type { HeatmapView } from "./riskDisplay";
import { RouteLayer } from "./RouteLayer";
import { HeatmapLayer } from "./HeatmapLayer";
import { IncidentMarkers } from "./IncidentMarkers";
import { OfficialZonesLayer } from "./OfficialZonesLayer";

const multan: LatLngTuple = [30.196, 71.475];
const initialZoom = () => window.innerWidth <= 360 ? 13.25 : window.innerWidth <= 600 ? 13.5 : 14;
const world: LatLngBoundsExpression = [[-85, -180], [85, 180]];
const tileUrl = import.meta.env.VITE_MAP_TILE_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const attribution = import.meta.env.VITE_MAP_TILE_ATTRIBUTION
  || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function isolateMapControl(element: HTMLDivElement | null) {
  if (element) DomEvent.disableClickPropagation(element);
}

function readBounds(map: ReturnType<typeof useMap>): Bounds {
  const bounds = map.getBounds();
  return {
    min_lat: Math.max(-85.05112, Math.floor(bounds.getSouth() * 1e5) / 1e5),
    max_lat: Math.min(85.05112, Math.ceil(bounds.getNorth() * 1e5) / 1e5),
    min_lng: Math.max(-180, Math.floor(bounds.getWest() * 1e5) / 1e5),
    max_lng: Math.min(180, Math.ceil(bounds.getEast() * 1e5) / 1e5),
  };
}

type MapActions = {
  onBounds: (bounds: Bounds) => void;
  onPick: (point: Coordinate) => void;
  onCancelPick: () => void;
  picking: boolean;
  pickLabel?: string;
  heatmap: Heatmap | null;
  onCell?: (id: string) => void;
  destination: MapDestination | null;
};

function MapControls({ onBounds, onPick, onCancelPick, picking, pickLabel, heatmap, onCell, destination }: MapActions) {
  const [locationNotice, setLocationNotice] = useState("");
  const [locating, setLocating] = useState(false);
  function inspect(position: LatLng) {
    if (!heatmap || !onCell) return;
    const { x, y } = CRS.EPSG3857.project(position);
    const size = heatmap.cell_size;
    const id = `${size}:${Math.floor(x / size)}:${Math.floor(y / size)}`;
    if (heatmap.cells.features.some((cell) => cell.id === id)) onCell(id);
  }

  const map = useMapEvents({
    click: ({ latlng }) => {
      if (picking) onPick({ latitude: latlng.lat, longitude: latlng.lng });
      else inspect(latlng);
    },
  });

  useEffect(() => {
    let timer: number | undefined;
    const report = () => onBounds(readBounds(map));
    const schedule = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(report, 250);
    };
    const observer = new ResizeObserver(() => {
      map.invalidateSize({ pan: false, debounceMoveend: true });
      schedule();
    });
    observer.observe(map.getContainer());
    map.on("moveend", schedule);
    report();
    return () => {
      observer.disconnect();
      map.off("moveend", schedule);
      window.clearTimeout(timer);
    };
  }, [map, onBounds]);

  useEffect(() => {
    if (destination) map.setView([destination.latitude, destination.longitude], destination.zoom);
  }, [map, destination]);

  function locate() {
    setLocationNotice("");
    if (!navigator.geolocation) {
      setLocationNotice("Location is unavailable in this browser.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      setLocating(false);
      const latitude = Number(coords.latitude.toFixed(2));
      const longitude = Number(coords.longitude.toFixed(2));
      map.setView([latitude, longitude], 14);
    }, () => {
      setLocating(false);
      setLocationNotice("Could not access your location.");
    }, { timeout: 8000, maximumAge: 60_000 });
  }

  return (
    <>
      <div ref={isolateMapControl} className="map-controls" aria-label="Map controls">
        {locationNotice && <p className="floating location-notice" role="status">{locationNotice}</p>}
        <div className="control-stack floating">
          <button type="button" onClick={() => map.zoomIn()} aria-label="Zoom in" title="Zoom in"><Plus size={19} /></button>
          <button type="button" onClick={() => map.zoomOut()} aria-label="Zoom out" title="Zoom out"><Minus size={19} /></button>
        </div>
        <div className="control-stack floating">
          <button type="button" onClick={locate} disabled={locating} aria-label="Current location" title="Current location"><LocateFixed size={18} /></button>
          <button type="button" onClick={() => { setLocationNotice(""); map.setView(multan, initialZoom()); }}
            aria-label="Recenter on Multan" title="Recenter on Multan"><Crosshair size={18} /></button>
          {heatmap && onCell && <button type="button" onClick={() => inspect(map.getCenter())}
            aria-label="Inspect center cell" title="Inspect center cell"><ScanLine size={18} /></button>}
        </div>
      </div>
      {picking && (
        <div ref={isolateMapControl} className="pick-help floating" aria-label="Select report location">
          <div><strong>{pickLabel ?? "Place the report pin"}</strong><span>{pickLabel ? "Tap the map to choose a location." : "Tap the map to mark where it happened."}</span></div>
          <button className="secondary-button" type="button" onClick={() => {
            const center = map.getCenter();
            onPick({ latitude: center.lat, longitude: center.lng });
          }}>Use map center</button>
          <button className="icon-button" type="button" aria-label="Cancel location selection" onClick={onCancelPick}><X size={17} /></button>
        </div>
      )}
    </>
  );
}

export function SafetyMap({ incidents, zones, dimension, view, point, selectedIncident, routes, selectedRoute, onRoute, fitPanel, ...actions }: MapActions & {
  incidents: Incident[];
  zones: Zone[];
  dimension: RiskDimension;
  view: HeatmapView;
  routes: RouteLine[];
  fitPanel?: RefObject<HTMLElement | null>;
  selectedRoute?: string;
  onRoute: (id: string) => void;
  selectedIncident?: string;
  point: Coordinate | null;
  onIncident: (incident: Incident) => void;
  onZone: (zone: Zone) => void;
}) {
  const { heatmap, picking, onIncident, onZone } = actions;
  const [tileError, setTileError] = useState(false);
  const tileBatchFailed = useRef(false);
  return (
    <div className="map-frame" data-picking={picking} aria-label="Interactive safety map">
      <MapContainer center={multan} zoom={initialZoom()} minZoom={3} maxZoom={19}
        maxBounds={world} maxBoundsViscosity={1} zoomSnap={0.25} zoomControl={false}>
        <TileLayer url={tileUrl} attribution={attribution} noWrap referrerPolicy="strict-origin-when-cross-origin"
          eventHandlers={{
            loading: () => { tileBatchFailed.current = false; },
            tileerror: () => { tileBatchFailed.current = true; },
            load: () => setTileError(tileBatchFailed.current),
          }} />
        <Pane name="heatmap-cells" style={{ zIndex: 410, pointerEvents: "none" }}>
          {heatmap && <HeatmapLayer heatmap={heatmap} dimension={dimension} view={view} />}
        </Pane>
        {routes.length > 0 && <RouteLayer routes={routes} selected={selectedRoute} onSelect={onRoute} fitPanel={fitPanel} />}
        <OfficialZonesLayer zones={zones} onSelect={onZone} />
        <IncidentMarkers incidents={incidents} selected={selectedIncident} onSelect={onIncident} />
        {point && <CircleMarker center={[point.latitude, point.longitude]} pane="markerPane" radius={9}
          interactive={false} pathOptions={{ className: "report-map-pin", color: "#fff", fillColor: "#146458", fillOpacity: 1, weight: 3 }} />}
        <MapControls {...actions} />
      </MapContainer>
      {tileError && <div className="tile-notice floating" role="status"><AlertCircle size={15} /> Some map tiles are unavailable.</div>}
    </div>
  );
}
