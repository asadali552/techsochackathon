import { GeoJSON, Pane, Tooltip } from "react-leaflet";

import type { Zone } from "../types/api";
import { designations } from "./evidence";

export function OfficialZonesLayer({ zones, onSelect }: { zones: Zone[]; onSelect: (zone: Zone) => void }) {
  return (
    <Pane name="official-zones" style={{ zIndex: 440 }}>
      {zones.map((zone) => {
        const { color, dash } = designations[zone.properties.designation];
        return (
          <GeoJSON
            key={`${zone.id}:${zone.properties.last_verified_at}`}
            data={zone}
            bubblingMouseEvents={false}
            style={{ color, fillColor: color, dashArray: dash, weight: 3, fillOpacity: 0.12 }}
            eventHandlers={{ click: () => onSelect(zone) }}
          >
            <Tooltip sticky>{zone.properties.name}</Tooltip>
          </GeoJSON>
        );
      })}
    </Pane>
  );
}
