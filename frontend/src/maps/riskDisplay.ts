export type HeatmapView = "risk" | "activity";

const defaults = [20, 40, 60, 80];
const configured = String(import.meta.env.VITE_HEATMAP_DISPLAY_BREAKS ?? "").split(",").map(Number);
export const breaks = configured.length === 4
  && configured.every((value, i) => Number.isInteger(value) && value > (configured[i - 1] ?? 0) && value < 100)
  ? configured : defaults;

export const bands = [
  { label: "Lower", color: "#16a34a", rgb: [22, 163, 74] },
  { label: "Relatively low", color: "#9ac339", rgb: [154, 195, 57] },
  { label: "Moderate", color: "#eebf20", rgb: [238, 191, 32] },
  { label: "Elevated", color: "#ef7821", rgb: [239, 120, 33] },
  { label: "Very elevated", color: "#d9263b", rgb: [217, 38, 59] },
];

export function displayBand(score: number) {
  const index = breaks.findIndex((threshold) => score <= threshold);
  return bands[index < 0 ? bands.length - 1 : index];
}

export const activityColors = ["#5195d5", "#4e63cb", "#682fa0"];
const activityRGB = [[81, 149, 213], [78, 99, 203], [104, 47, 160]];
const centers = [breaks[0] * .55, ...breaks.slice(1).map((v, i) => (breaks[i] + v) / 2), (breaks[3] + 100) / 2];

export const riskGradient = `linear-gradient(90deg, ${bands.map(({ color }, index) => `${color} ${centers[index]}%`).join(", ")})`;

export function smooth(a: number, b: number, value: number) {
  const t = Math.min(1, Math.max(0, (value - a) / (b - a)));
  return t * t * (3 - 2 * t);
}

function ramp(positions: number[], colors: number[][]) {
  const pixels = new Uint8Array(256 * 4);
  for (let i = 0; i < 256; i++) {
    const score = i * 100 / 255;
    const next = positions.findIndex((p) => score < p);
    const to = next < 0 ? colors.length - 1 : next;
    const from = Math.max(0, to - 1);
    const t = from === to ? 1 : smooth(positions[from], positions[to], score);
    for (let k = 0; k < 3; k++) pixels[4 * i + k] = Math.round(colors[from][k] * (1 - t) + colors[to][k] * t);
    pixels[4 * i + 3] = 255;
  }
  return pixels;
}

export const rampPixels = new Uint8Array([
  ...ramp(centers, bands.map((band) => band.rgb)),
  ...ramp([0, 52, 100], activityRGB),
]);
