import { divIcon, latLngBounds, type LatLngTuple } from "leaflet";
import { useEffect, useMemo, type RefObject } from "react";
import { Marker, Pane, Polyline, useMap } from "react-leaflet";

import type { RouteLine } from "../types/routes";

const pin = (label: string) => divIcon({
  className: "route-pin", html: `<span>${label}</span>`, iconSize: [27, 27], iconAnchor: [13, 13],
});
const startIcon = pin("A");
const endIcon = pin("B");

export function RouteLayer({ routes, selected, onSelect, fitPanel }: {
  routes: RouteLine[]; selected?: string; onSelect: (id: string) => void; fitPanel?: RefObject<HTMLElement | null>;
}) {
  const map = useMap();
  const lines = useMemo(() => routes.map((route) => ({
    id: route.id, points: route.geometry.coordinates.map(([lng, lat]): LatLngTuple => [lat, lng]),
  })), [routes]);

  const active = lines.find(({ id }) => id === selected) ?? (fitPanel ? lines[0] : undefined);
  const plannerPoints = fitPanel ? active?.points : undefined;

  useEffect(() => {
    if (fitPanel || !lines.length) return;
    const small = map.getSize().x <= 760;
    map.fitBounds(latLngBounds(lines.flatMap(({ points }) => points)), {
      paddingTopLeft: [small ? 28 : 286, small ? 166 : 145],
      paddingBottomRight: [small ? 40 : 370, small ? Math.round(map.getSize().y * .51) + 65 : 82],
      maxZoom: 16,
      animate: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    });
  }, [map, lines, fitPanel]);

  useEffect(() => {
    const panel = fitPanel?.current;
    if (!panel || !plannerPoints) return;
    const container = map.getContainer();
    let frame = 0;

    const scheduleFit = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const mapBox = container.getBoundingClientRect();
        const panelBox = panel.getBoundingClientRect();
        if (!panelBox.width) return;
        const sheet = panelBox.width > mapBox.width * .7;
        const left = sheet ? 24 : 300;
        const top = sheet ? 136 : 106;
        const right = sheet ? 66 : mapBox.right - panelBox.left + 62;
        const bottom = sheet ? mapBox.bottom - panelBox.top + 20 : 94;
        if (mapBox.width - left - right < 36 || mapBox.height - top - bottom < 42) return;
        map.fitBounds(latLngBounds(plannerPoints), {
          paddingTopLeft: [left, top], paddingBottomRight: [right, bottom], maxZoom: 16,
          animate: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        });
      });
    };

    scheduleFit();
    const observer = new ResizeObserver(scheduleFit);
    observer.observe(container);
    observer.observe(panel);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [map, plannerPoints, fitPanel]);
  return (
    <>
      <Pane name="journey-routes" style={{ zIndex: 430 }}>
        {lines.filter(({ id }) => id !== active?.id).map(({ id, points }) => <Polyline key={id} positions={points}
          pathOptions={{ className: "route-alternative", color: "#667eaa", weight: 5, opacity: .73, bubblingMouseEvents: false }}
          eventHandlers={{ click: () => onSelect(id) }} />)}
        {active && <>
          <Polyline positions={active.points} interactive={false} pathOptions={{ color: "#ffffff", weight: 8, opacity: .95 }} />
          <Polyline positions={active.points} interactive={false} pathOptions={{ className: "route-selected", color: fitPanel ? "#3058bd" : "#2563eb", weight: 5, opacity: 1 }} />
        </>}
      </Pane>
      {active && <Pane name="journey-pins" style={{ zIndex: 630 }}>
        <Marker position={active.points[0]} icon={startIcon} title="Route start" alt="Route start" interactive={false} keyboard={false} />
        <Marker position={active.points.at(-1)!} icon={endIcon} title="Route destination" alt="Route destination" interactive={false} keyboard={false} />
      </Pane>}
    </>
  );
}
