import { markerGroups, designations } from "../maps/evidence";

export function MapLegend() {
  return (
    <details className="map-legend">
      <summary>Map legend</summary>
      <div className="legend-content">
        <div>
          <h3>Report markers</h3>
          {Object.values(markerGroups).map(({ label, color, glyph }) => (
            <span key={label}><i className="legend-dot" style={{ background: color }}>{glyph}</i>{label}</span>
          ))}
        </div>
        <div>
          <h3>Advisory areas</h3>
          {Object.values(designations).map(({ label, color, dash }) => (
            <span key={label}><i className="legend-zone" style={{ borderColor: color, borderStyle: dash ? "dashed" : "solid" }} />{label}</span>
          ))}
        </div>
      </div>
    </details>
  );
}
