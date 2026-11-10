import { Clock3, LoaderCircle, RefreshCw } from "lucide-react";

import { heatmapTime, periods } from "../maps/heatmapEvidence";
import { activityColors, bands, breaks, riskGradient, type HeatmapView } from "../maps/riskDisplay";
import type { Heatmap, HeatmapPeriod, RiskDimension } from "../types/heatmap";

export function TimeControl({ period, onPeriod }: {
  period: HeatmapPeriod;
  onPeriod: (period: HeatmapPeriod) => void;
}) {
  return (
    <label className="time-control">
      <Clock3 size={16} aria-hidden="true" />
      <select aria-label="Historical period" value={period} onChange={(event) => onPeriod(event.target.value as HeatmapPeriod)}>
        {Object.entries(periods).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select>
    </label>
  );
}

export function HeatmapLegend({ data, dimension, view, loading, error, customDates, continuousScale, onRefresh, onView }: {
  data: Heatmap | null;
  dimension: RiskDimension;
  view: HeatmapView;
  loading: boolean;
  error: string | null;
  customDates: boolean;
  continuousScale?: boolean;
  onRefresh: () => void;
  onView: (view: HeatmapView) => void;
}) {
  const activity = view === "activity";
  const empty = data && !data.cells.features.some((cell) => activity
    ? cell.properties[dimension].report_count > 0 : cell.properties[dimension].coverage === "sufficient");
  return (
    <div className="heatmap-legend" aria-label={activity ? "Incident activity legend" : "Reported risk legend"}>
      <div className="legend-heading">
        <div><strong>{activity ? "Incident activity" : "Reported risk"}</strong><small>{dimension === "security" ? "Community safety" : "Road hazards"}</small></div>
        <button className="icon-button heatmap-refresh" type="button" aria-label="Refresh heatmap" title="Refresh heatmap"
          onClick={onRefresh} disabled={loading}><RefreshCw size={15} className={loading ? "spin" : ""} /></button>
      </div>
      <div className="heatmap-views" aria-label="Heatmap view">
        <button type="button" aria-pressed={!activity} onClick={() => onView("risk")}>Safety risk</button>
        <button type="button" aria-pressed={activity} onClick={() => onView("activity")}>Activity</button>
      </div>
      {activity ? <div className="activity-scale">
        <span>Fewer</span><i style={{ background: `linear-gradient(90deg, ${activityColors.join(",")})` }} /><span>More reports</span>
      </div> : <div className="risk-key" aria-label="Experimental risk scale">
        {continuousScale && <div className="risk-ramp" aria-hidden="true" style={{ background: riskGradient }} />}
        <div className="risk-scale">
          {bands.map((band, index) => (
            <span key={band.label} title={band.label}>{!continuousScale && <i style={{ background: band.color }} />}
              {index === 0 ? 0 : breaks[index - 1] + 1}–{breaks[index] ?? 100}</span>
          ))}
        </div>
      </div>}
      <p className="coverage-key"><i />{activity ? "Concentration of eligible reports." : "Lower to higher risk · Clear means unknown."}</p>
      <div className="heatmap-status" role={error ? "alert" : "status"}>
        {loading ? <span><LoaderCircle size={12} className="spin" /> Updating heatmap…</span>
          : error ? <span>{error}</span>
          : data && <span>{empty ? activity ? "No eligible reports. " : "Insufficient evidence in this view. " : ""}
            <time dateTime={data.generated_at}>{heatmapTime(data.generated_at, data.timezone, true)}</time> · {customDates ? "Custom dates" : "Last 30 days"}</span>}
      </div>
    </div>
  );
}
