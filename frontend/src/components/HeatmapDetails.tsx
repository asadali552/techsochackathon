import { Info, X } from "lucide-react";

import { categoryLabels } from "../maps/evidence";
import { dimensions, heatmapTime, periods } from "../maps/heatmapEvidence";
import { displayBand, type HeatmapView } from "../maps/riskDisplay";
import type { Category } from "../types/api";
import type { Heatmap, HeatmapCell, RiskDimension } from "../types/heatmap";

export function HeatmapDetails({ data, cell, dimension, view, onClose, onAsk }: {
  data: Heatmap;
  cell: HeatmapCell;
  dimension: RiskDimension;
  view: HeatmapView;
  onClose: () => void;
  onAsk: () => void;
}) {
  const evidence = cell.properties[dimension];
  const band = evidence.score === null ? null : displayBand(evidence.score);
  const { timezone, methodology } = data;
  const { minimum_reports, moderate_threshold, elevated_threshold, half_life_days } = methodology;
  const counts = Object.entries(evidence.category_counts) as [Category, number][];
  return (
    <section className="detail-sheet" aria-label="Heatmap cell details" onKeyDown={(event) => { if (event.key === "Escape") onClose(); }}>
      <div className="panel-header">
        <div><span className="eyebrow">{dimensions[dimension]}</span><h2>{view === "activity" ? "Incident activity" : "Reported risk"}</h2></div>
        <button autoFocus className="icon-button" aria-label="Close heatmap details" onClick={onClose}><X size={19} /></button>
      </div>
      <div className="detail-body">
        <div className="heatmap-reading">
          <div className="heatmap-reading-value">
            {view === "activity" ? <><strong>{evidence.report_count}</strong><span>eligible reports</span></>
              : evidence.score === null ? <strong className="heatmap-reading-unknown">Insufficient evidence</strong>
              : <><strong>{evidence.score}</strong><span>/ 100</span></>}
          </div>
          <div className="badge-row">
            {view === "risk" && band && <span className="badge risk-label" style={{ borderColor: band.color }}>{band.label}</span>}
            {cell.properties.is_demo && <span className="badge demo">Fictional demo</span>}
          </div>
        </div>
        <p className="detail-copy">{view === "activity" ? "This cell shows eligible report counts. The surface represents concentration." : evidence.score === null
          ? `A score needs at least ${minimum_reports} eligible reports in this cell and layer.`
          : "More severe, better corroborated, newer, and closer-to-center reports contribute more."}</p>
        <dl>
          <div><dt>Coverage</dt><dd>{evidence.coverage === "sufficient" ? "Meets prototype minimum" : evidence.coverage === "limited" ? "Below prototype minimum" : "No eligible reports"}</dd></div>
          <div><dt>Reports</dt><dd>{evidence.report_count} eligible</dd></div>
          <div><dt>Local period</dt><dd>{periods[data.period]}</dd></div>
          <div><dt>Date range</dt><dd>{heatmapTime(data.window.from, timezone)} – {heatmapTime(data.window.to, timezone)} · {timezone}</dd></div>
          <div><dt>Latest report</dt><dd>{evidence.latest_report_at ? heatmapTime(evidence.latest_report_at, timezone) : "None in this window"}</dd></div>
          <div><dt>Updated</dt><dd>{heatmapTime(data.generated_at, timezone, true)} · {timezone}</dd></div>
        </dl>
        {counts.length > 0 && (
          <ul className="cell-breakdown" aria-label="Reports by category">
            {counts.map(([category, count]) => <li key={category}>{categoryLabels[category]} <strong>{count}</strong></li>)}
          </ul>
        )}
        <button type="button" className="secondary-button" onClick={onAsk}>Ask about this cell</button>
        <p className="note" title={`Moderate starts at ${moderate_threshold}. Elevated starts at ${elevated_threshold}. Recency weight halves every ${half_life_days} days.`}>
          <Info size={16} /> Prototype evidence score. Coverage may be incomplete. Historical reports do not predict future conditions.
        </p>
      </div>
    </section>
  );
}
