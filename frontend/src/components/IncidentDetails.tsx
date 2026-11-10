import { ArrowUpRight, MapPin, ShieldAlert, X } from "lucide-react";
import { useEffect, useRef } from "react";

import { categoryLabels, designations, formatMultanTime, incidentStyle, verificationLabels } from "../maps/evidence";
import type { Incident, Zone } from "../types/api";

export function StatusTag({ incident }: { incident: Incident }) {
  return <span className={`badge status-${incident.verification_status}`}>{verificationLabels[incident.verification_status]}</span>;
}

function sourceLink(value: string | null) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

export function IncidentDetails({ incident, zone, onClose }: {
  incident?: Incident;
  zone?: Zone;
  onClose: () => void;
}) {
  const official = zone?.properties;
  const source = sourceLink(official?.source_url ?? null);
  const demo = incident?.is_demo ?? official?.is_demo;
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const trigger = document.activeElement;
    closeButton.current?.focus({ preventScroll: true });
    return () => {
      if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus({ preventScroll: true });
    };
  }, []);
  return (
    <section className="detail-sheet" aria-label={incident ? "Incident details" : "Zone details"}
      onKeyDown={(event) => { if (event.key === "Escape") onClose(); }}>
      <div className="panel-header">
        <div>
          <span className="eyebrow">{incident ? "Community report" : "Advisory area"}</span>
          <h2>{incident ? categoryLabels[incident.category] : official?.name}</h2>
        </div>
        <button ref={closeButton} className="icon-button" aria-label="Close details" title="Close details" onClick={onClose}><X size={19} /></button>
      </div>
      <div className="detail-body">
        <div className="badge-row">
          {incident && <StatusTag incident={incident} />}
          {official && <span className="badge warning">{designations[official.designation].label}</span>}
          {demo && <span className="badge demo">Fictional demo</span>}
        </div>
        {incident && (
          <>
            <p className="detail-copy">{incident.public_summary ?? "No public summary available."}</p>
            <dl>
              <div><dt>Occurred</dt><dd>{formatMultanTime(incident.occurred_at)}</dd></div>
              <div><dt>Source</dt><dd>{incident.is_demo ? "Fictional Multan dataset" : "Community report"}</dd></div>
            </dl>
            <p className="note"><MapPin size={17} /> Public pins are approximate. Exact submitted locations are kept private.</p>
          </>
        )}
        {official && (
          <>
            <p className="detail-copy">{official.description}</p>
            <dl>
              <div><dt>Authority</dt><dd>{official.is_demo ? "Fictional demo" : official.issuing_authority}</dd></div>
              <div><dt>Effective from</dt><dd>{formatMultanTime(official.effective_from)}</dd></div>
              <div><dt>Effective until</dt><dd>{official.effective_until ? formatMultanTime(official.effective_until) : "No end date listed"}</dd></div>
              {official.source_reference && <div><dt>Reference</dt><dd>{official.source_reference}</dd></div>}
            </dl>
            {source && <a className="text-button source-link" href={source} target="_blank" rel="noreferrer">View advisory source <ArrowUpRight size={15} /></a>}
            {official.is_demo && <p className="note"><ShieldAlert size={17} /> Fictional area for demonstration.</p>}
          </>
        )}
      </div>
    </section>
  );
}

export function EvidenceList({ incidents, zones, onIncident, onZone }: {
  incidents: Incident[];
  zones: Zone[];
  onIncident: (incident: Incident) => void;
  onZone: (zone: Zone) => void;
}) {
  return (
    <>
      {incidents.length > 0 && <ul className="evidence-list">
        {incidents.map((incident) => {
          const style = incidentStyle(incident.category);
          return (
            <li key={incident.id}>
              <button type="button" onClick={() => onIncident(incident)}>
                <span className="feed-glyph" style={{ color: style.color }} aria-hidden="true">{style.glyph}</span>
                <span className="feed-entry">
                  <strong>{categoryLabels[incident.category]}</strong>
                  <small>{formatMultanTime(incident.occurred_at)}</small>
                  <span className="badge-row"><StatusTag incident={incident} />{incident.is_demo && <span className="badge demo">Demo</span>}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>}
      {zones.length > 0 && <>
        <h3 className="feed-group-title">Advisory areas</h3>
        <ul className="evidence-list">
          {zones.map((zone) => (
            <li key={zone.id}>
              <button type="button" onClick={() => onZone(zone)}>
                <span className="feed-glyph" style={{ color: designations[zone.properties.designation].color }}><ShieldAlert size={18} /></span>
                <span className="feed-entry">
                  <strong>{zone.properties.name}</strong>
                  <small>{designations[zone.properties.designation].label}</small>
                  {zone.properties.is_demo && <span className="badge demo">Fictional demo</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </>}
    </>
  );
}
