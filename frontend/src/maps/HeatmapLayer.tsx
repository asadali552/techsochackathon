import { useEffect, useState } from "react";
import { ImageOverlay, useMapEvents } from "react-leaflet";

import type { Heatmap, RiskDimension } from "../types/heatmap";
import { riskSurface } from "./riskSurface";
import type { HeatmapView } from "./riskDisplay";

export function HeatmapLayer({ heatmap, dimension, view }: { heatmap: Heatmap; dimension: RiskDimension; view: HeatmapView }) {
  const [zoom, setZoom] = useState<number>();
  const map = useMapEvents({ zoomend: () => setZoom(map.getZoom()) });
  const level = Math.round((zoom ?? map.getZoom()) * 2) / 2;
  const [image, setImage] = useState<{
    heatmap: Heatmap; dimension: RiskDimension; view: HeatmapView; level: number; raster: ReturnType<typeof riskSurface>;
  }>();
  useEffect(() => {
    let cancelled = false;
    const frame = requestAnimationFrame(async () => {
      const raster = riskSurface(heatmap, dimension, view, level);
      if (raster) {
        const preload = new Image();
        preload.src = raster.url;
        await preload.decode().catch(() => {});
      }
      if (!cancelled) setImage({ heatmap, dimension, view, level, raster });
    });
    return () => { cancelled = true; cancelAnimationFrame(frame); };
  }, [heatmap, dimension, view, level]);

  const raster = image?.dimension === dimension && image.view === view && image.heatmap.mode === heatmap.mode
    && image.heatmap.period === heatmap.period ? image.raster : null;
  if (!raster) return null;
  return <ImageOverlay key={`${image?.heatmap.generated_at}:${dimension}:${view}:${image?.level}`} bounds={raster.bounds} url={raster.url} pane="heatmap-cells"
    className={`risk-surface risk-surface--${raster.renderer} risk-surface--${view}`} alt="" interactive={false} />;
}
