import { divIcon, latLngBounds } from "leaflet";
import { useMemo, useState } from "react";
import { Marker, Pane, useMapEvents } from "react-leaflet";

import type { Incident } from "../types/api";
import { categoryLabels, incidentStyle, markerGroups } from "./evidence";

const symbols: Record<string, string> = {
  security: '<rect x="5" y="3" width="10" height="14" rx="2"/><path d="M9 14h2"/>',
  harassment: '<path d="M16 9a6 6 0 0 1-6 6H4l1.5-3A6 6 0 1 1 16 9Z"/><path d="M10 7v2m0 2h.01"/>',
  suspicious: '<path d="M2.5 10s2.7-4.5 7.5-4.5 7.5 4.5 7.5 4.5-2.7 4.5-7.5 4.5S2.5 10 2.5 10Z"/><circle cx="10" cy="10" r="1.6"/>',
  accident: '<path d="m6 8 1-3h6l1 3m-9 6v2m10-2v2M5 8h10l1.5 2v4h-13v-4L5 8Zm1.5 3h.01m7 0h.01"/>',
  hazard: '<path d="m10 3 7 13H3L10 3Zm0 5v3m0 2h.01"/>',
  other: '<circle cx="10" cy="10" r="6.5"/><path d="M10 7h.01m0 2.5v4"/>',
};

const icons = new Map(Object.entries(markerGroups).flatMap(([group, { color }]) =>
  [false, true].map((selected) => [`${color}:${selected}`, divIcon({
    className: `incident-marker${selected ? " is-selected" : ""}`,
    html: `<span style="--marker-color:${color}" aria-hidden="true"><svg width="17" height="17" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">${symbols[group]}</svg></span>`,
    iconSize: [28, 28], iconAnchor: [14, 14],
  })] as const)
));

export function IncidentMarkers({ incidents, selected, onSelect }: {
  incidents: Incident[];
  selected?: string;
  onSelect: (incident: Incident) => void;
}) {
  const [zoom, setZoom] = useState<number>();
  const map = useMapEvents({ zoomend: () => setZoom(map.getZoom()) });
  const currentZoom = zoom ?? map.getZoom();
  const clusters = useMemo(() => {
    const bins = new Map<string, Incident[]>();
    for (const incident of incidents) {
      const [lng, lat] = incident.location.coordinates;
      const pixel = map.project([lat, lng], currentZoom);
      const key = currentZoom < 14 ? `${Math.floor(pixel.x / 52)}:${Math.floor(pixel.y / 52)}` : incident.id;
      const group = bins.get(key);
      if (group) group.push(incident);
      else bins.set(key, [incident]);
    }
    return bins;
  }, [incidents, map, currentZoom]);

  return (
    <Pane name="incident-markers" style={{ zIndex: 620 }}>
      {[...clusters].map(([key, group]) => {
        if (group.length > 1) {
          const bounds = latLngBounds(group.map(({ location: { coordinates: [lng, lat] } }) => [lat, lng]));
          const label = `${group.length} reports · zoom in`;
          return <Marker key={key} position={bounds.getCenter()} title={label} alt={label}
            icon={divIcon({ className: "incident-cluster", html: `<span>${group.length}</span>`, iconSize: [40, 40], iconAnchor: [20, 20] })}
            eventHandlers={{ click: () => map.fitBounds(bounds, { maxZoom: 16, padding: [45, 45] }) }} />;
        }
        const incident = group[0];
        const [lng, lat] = incident.location.coordinates;
        const label = `${categoryLabels[incident.category]}${incident.is_demo ? " · Fictional demo" : ""}`;
        return <Marker key={key} position={[lat, lng]} title={label} alt={label}
          zIndexOffset={incident.id === selected ? 1000 : 0}
          icon={icons.get(`${incidentStyle(incident.category).color}:${incident.id === selected}`)}
          eventHandlers={{ click: () => onSelect(incident) }} />;
      })}
    </Pane>
  );
}
