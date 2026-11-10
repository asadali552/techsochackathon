import { ArrowUpRight, MapPin, Search, X } from "lucide-react";
import { useRef, useState } from "react";

import { categoryLabels } from "../maps/evidence";
import { coordinates, places, type MapDestination } from "../maps/places";
import type { Incident } from "../types/api";

export function MapSearch({ incidents, onPlace, onIncident }: {
  incidents: Incident[];
  onPlace: (place: MapDestination) => void;
  onIncident: (incident: Incident) => void;
}) {
  const [text, setText] = useState("");
  const [expanded, setExpanded] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const search = useRef<HTMLFormElement>(null);
  const query = text.trim().toLowerCase();
  const coordinate = coordinates(query);
  const matches = places.filter((place) => `${place.name} ${place.detail}`.toLowerCase().includes(query));
  if (coordinate) matches.unshift({ name: text.trim(), detail: "Coordinates", ...coordinate, zoom: 15 });
  const reports = query ? incidents.filter((incident) =>
    `${categoryLabels[incident.category]} ${incident.public_summary ?? ""}`.toLowerCase().includes(query)).slice(0, 6) : [];

  function choosePlace(place: (typeof places)[number]) {
    setText(place.name);
    setExpanded(false);
    onPlace(place);
  }

  function chooseReport(incident: Incident) {
    setText(categoryLabels[incident.category]);
    setExpanded(false);
    onIncident(incident);
  }

  return (
    <form className="place-search floating" role="search" ref={search}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setExpanded(false); }}
      onKeyDown={(event) => {
        if (event.key === "Escape") { input.current?.focus(); setExpanded(false); }
        if (event.key === "ArrowDown" && event.target === input.current && expanded) {
          event.preventDefault();
          search.current?.querySelector<HTMLButtonElement>(".search-results button")?.focus();
        }
      }}
      onSubmit={(event) => {
        event.preventDefault();
        if (matches[0]) choosePlace(matches[0]);
        else if (reports[0]) chooseReport(reports[0]);
        else setExpanded(true);
      }}>
      <div className="search-line">
        <Search size={18} aria-hidden="true" />
        <input ref={input} type="search" aria-label="Search places or reports" placeholder="Search Multan or reports"
          value={text} onFocus={() => setExpanded(true)} onChange={(event) => { setText(event.target.value); setExpanded(true); }} />
        {text && <button className="icon-button" type="button" aria-label="Clear search"
          onClick={() => { setText(""); input.current?.focus(); setExpanded(true); }}><X size={16} /></button>}
      </div>
      {expanded && <div className="search-results" aria-label="Search results">
        {matches.length > 0 && <p className="eyebrow">Places</p>}
        {matches.map((place) => (
          <button key={place.name} type="button" onClick={() => choosePlace(place)}>
            <MapPin size={17} /><span><strong>{place.name}</strong><small>{place.detail}</small></span><ArrowUpRight size={15} />
          </button>
        ))}
        {reports.length > 0 && <p className="eyebrow">Reports in view</p>}
        {reports.map((incident) => (
          <button key={incident.id} type="button" onClick={() => chooseReport(incident)}>
            <MapPin size={17} /><span><strong>{categoryLabels[incident.category]}</strong><small>{incident.public_summary}</small></span><ArrowUpRight size={15} />
          </button>
        ))}
        {matches.length === 0 && reports.length === 0 && <p className="search-empty">No matches. Try a Multan landmark, a visible report, or latitude, longitude.</p>}
      </div>}
    </form>
  );
}
