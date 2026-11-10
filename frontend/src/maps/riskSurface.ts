import { CRS, latLngBounds, point } from "leaflet";

import type { Heatmap, RiskDimension } from "../types/heatmap";
import { rampPixels, smooth, type HeatmapView } from "./riskDisplay";

const vertices = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]);
const kernelRadius = Math.max(.75, Math.min(1.4, Number(import.meta.env.VITE_HEATMAP_KERNEL_RADIUS) || 1.15));
const fragment = `
precision highp float;
uniform sampler2D samples, palette;
uniform vec2 grid, resolution;
uniform float radius, opacity, activity;
vec4 cell(vec2 p) {
  if (any(lessThan(p, vec2(0.))) || any(greaterThanEqual(p, grid))) return vec4(0.);
  return texture2D(samples, (p + .5) / grid);
}
void main() {
  vec2 p = gl_FragCoord.xy / resolution * grid;
  vec2 base = floor(p), f = fract(p);
  if (activity == 0. && cell(base).a == 0.) { gl_FragColor = vec4(0.); return; }
  float weight = 0., total = 0.;
  for (int y = -2; y <= 2; y++) {
    for (int x = -2; x <= 2; x++) {
      vec2 offset = vec2(float(x), float(y));
      vec4 sampleCell = cell(base + offset);
      vec2 d = f - offset - .5;
      float w = pow(max(0., 1. - dot(d,d)/(radius*radius)), 2.) * sampleCell.a;
      weight += w;
      total += sampleCell.r * w;
    }
  }
  float edge = 1.;
  if (activity == 0.) {
    if (cell(base + vec2(-1.,0.)).a == 0.) edge = min(edge, smoothstep(0., .30, f.x));
    if (cell(base + vec2(1.,0.)).a == 0.) edge = min(edge, smoothstep(0., .30, 1.-f.x));
    if (cell(base + vec2(0.,-1.)).a == 0.) edge = min(edge, smoothstep(0., .30, f.y));
    if (cell(base + vec2(0.,1.)).a == 0.) edge = min(edge, smoothstep(0., .30, 1.-f.y));
  }
  float density = 1. - exp(-total * 255. / 3.);
  float value = activity == 1. ? density : total / max(weight, .0001);
  float alpha = activity == 1. ? density : edge * min(1., weight);
  gl_FragColor = vec4(texture2D(palette, vec2((value * 255. + .5) / 256., .25 + .5 * activity)).rgb, opacity * alpha);
}`;

type SurfaceGrid = {
  columns: number; rows: number; width: number; height: number;
  pixels: Uint8Array; activity: boolean; radius: number; opacity: number;
};

function webGLRenderer() {
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl", { premultipliedAlpha: false, preserveDrawingBuffer: true });
  if (!gl) return null;
  const program = gl.createProgram()!;
  for (const [type, source] of [
    [gl.VERTEX_SHADER, "attribute vec2 vertex; void main(){gl_Position=vec4(vertex,0.,1.);}"],
    [gl.FRAGMENT_SHADER, fragment],
  ] as const) {
    const shader = gl.createShader(type)!;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    gl.attachShader(program, shader);
    gl.deleteShader(shader);
  }
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;
  gl.useProgram(program);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);
  const vertex = gl.getAttribLocation(program, "vertex");
  gl.enableVertexAttribArray(vertex);
  gl.vertexAttribPointer(vertex, 2, gl.FLOAT, false, 0, 0);
  function bindTexture(unit: number, filter: number) {
    gl!.activeTexture(gl!.TEXTURE0 + unit);
    gl!.bindTexture(gl!.TEXTURE_2D, gl!.createTexture());
    for (const parameter of [gl!.TEXTURE_MIN_FILTER, gl!.TEXTURE_MAG_FILTER]) gl!.texParameteri(gl!.TEXTURE_2D, parameter, filter);
    for (const parameter of [gl!.TEXTURE_WRAP_S, gl!.TEXTURE_WRAP_T]) gl!.texParameteri(gl!.TEXTURE_2D, parameter, gl!.CLAMP_TO_EDGE);
  }
  const uniform = (name: string) => gl.getUniformLocation(program, name);
  bindTexture(1, gl.LINEAR);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 256, 2, 0, gl.RGBA, gl.UNSIGNED_BYTE, rampPixels);
  gl.uniform1i(uniform("palette"), 1);
  bindTexture(0, gl.NEAREST);
  gl.uniform1i(uniform("samples"), 0);
  const grid = uniform("grid"), resolution = uniform("resolution");
  const radiusUniform = uniform("radius"), opacityUniform = uniform("opacity"), activityUniform = uniform("activity");
  return ({ columns, rows, width, height, pixels, activity, radius, opacity }: SurfaceGrid) => {
    if (gl.isContextLost()) return null;
    canvas.width = width;
    canvas.height = height;
    gl.viewport(0, 0, width, height);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, columns, rows, 0, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    gl.uniform2f(grid, columns, rows);
    gl.uniform2f(resolution, width, height);
    gl.uniform1f(radiusUniform, radius);
    gl.uniform1f(opacityUniform, opacity);
    gl.uniform1f(activityUniform, Number(activity));
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    return canvas.toDataURL();
  };
}

function canvasRenderer({ columns, rows, width, height, pixels, activity, radius, opacity }: SurfaceGrid) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) return null;
  const image = context.createImageData(width, height);
  const cell = (x: number, y: number) => x < 0 || y < 0 || x >= columns || y >= rows ? -4 : 4 * (y * columns + x);
  for (let y = 0; y < height; y++) {
    const north = rows - (y + .5) * rows / height, j = Math.floor(north), fy = north - j;
    for (let x = 0; x < width; x++) {
      const east = (x + .5) * columns / width, i = Math.floor(east), fx = east - i;
      if (!activity && !pixels[cell(i, j) + 3]) continue;
      let weight = 0, total = 0;
      for (let dy = -2; dy <= 2; dy++) {
        for (let dx = -2; dx <= 2; dx++) {
          const index = cell(i + dx, j + dy);
          if (!pixels[index + 3]) continue;
          const distance = (fx - dx - .5) ** 2 + (fy - dy - .5) ** 2;
          const w = Math.max(0, 1 - distance / (radius * radius)) ** 2;
          weight += w;
          total += pixels[index] * w;
        }
      }
      if (!weight) continue;
      const edge = activity ? 1 : Math.min(
        pixels[cell(i - 1, j) + 3] ? 1 : smooth(0, .30, fx),
        pixels[cell(i + 1, j) + 3] ? 1 : smooth(0, .30, 1 - fx),
        pixels[cell(i, j - 1) + 3] ? 1 : smooth(0, .30, fy),
        pixels[cell(i, j + 1) + 3] ? 1 : smooth(0, .30, 1 - fy),
      );
      const density = 1 - Math.exp(-total / 3);
      const paletteOffset = 4 * (activity ? 256 + Math.round(density * 255) : Math.min(255, Math.round(total / weight)));
      const offset = 4 * (y * width + x);
      for (let k = 0; k < 3; k++) image.data[offset + k] = rampPixels[paletteOffset + k];
      image.data[offset + 3] = 255 * opacity * (activity ? density : edge * Math.min(1, weight));
    }
  }
  context.putImageData(image, 0, 0);
  return canvas.toDataURL();
}

let gpu: ReturnType<typeof webGLRenderer> | undefined;
type Raster = { url: string; bounds: ReturnType<typeof latLngBounds>; renderer: "webgl" | "canvas" };
const cache = new WeakMap<Heatmap, Map<string, Raster | null>>();

export function riskSurface(heatmap: Heatmap, dimension: RiskDimension, view: HeatmapView, zoom: number): Raster | null {
  const level = Math.round(zoom * 2) / 2;
  const key = `${dimension}:${view}:${level}`;
  const cached = cache.get(heatmap) ?? new Map<string, Raster | null>();
  if (cached.has(key)) return cached.get(key) ?? null;
  const activity = view === "activity";
  const samples = heatmap.cells.features.flatMap((feature) => {
    const evidence = feature.properties[dimension];
    const value = activity ? (evidence.report_count ? Math.min(255, evidence.report_count) : null)
      : evidence.coverage === "sufficient" && evidence.score !== null ? Math.round(evidence.score * 255 / 100) : null;
    const [, i, j] = feature.id.split(":").map(Number);
    return value !== null && Number.isInteger(i) && Number.isInteger(j) ? [{ i, j, value }] : [];
  });
  if (!samples.length) return null;
  const radius = kernelRadius * Math.min(1.15, Math.max(.85, 1 + (14 - level) * .06));
  const margin = activity ? Math.ceil(radius) : 0;
  const west = Math.min(...samples.map(({ i }) => i)) - margin;
  const east = Math.max(...samples.map(({ i }) => i)) + 1 + margin;
  const south = Math.min(...samples.map(({ j }) => j)) - margin;
  const north = Math.max(...samples.map(({ j }) => j)) + 1 + margin;
  const columns = east - west, rows = north - south;
  const resolution = Math.min(36, 900 / Math.max(columns, rows));
  const pixels = new Uint8Array(columns * rows * 4);
  for (const { i, j, value } of samples) {
    const offset = 4 * ((j - south) * columns + i - west);
    pixels[offset] = value;
    pixels[offset + 3] = 255;
  }
  const opacity = Math.min(.82, Math.max(.56, .70 + (level - 13) * .035));
  const grid: SurfaceGrid = {
    columns, rows, pixels, width: Math.ceil(columns * resolution), height: Math.ceil(rows * resolution), radius, opacity, activity,
  };
  if (gpu === undefined) gpu = webGLRenderer();
  const accelerated = gpu?.(grid);
  const url = accelerated || canvasRenderer(grid);
  const size = heatmap.cell_size;
  const fromGrid = (x: number, y: number) => CRS.EPSG3857.unproject(point(x * size, y * size));
  const raster: Raster | null = url ? {
    url, renderer: accelerated ? "webgl" : "canvas", bounds: latLngBounds(fromGrid(west, south), fromGrid(east, north)),
  } : null;
  cached.set(key, raster);
  if (cached.size > 6) cached.delete(cached.keys().next().value!);
  cache.set(heatmap, cached);
  return raster;
}
