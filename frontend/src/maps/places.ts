import type { Coordinate } from "../types/api";

export const places = [
  { name: "Multan", detail: "Punjab, Pakistan", latitude: 30.196, longitude: 71.475, zoom: 14 },
  { name: "Ghanta Ghar", detail: "Clock tower · Multan", latitude: 30.198803, longitude: 71.467842, zoom: 16 },
  { name: "Tomb of Shah Rukn-e-Alam", detail: "Landmark · Multan", latitude: 30.199172, longitude: 71.471646, zoom: 16 },
  { name: "Multan Cantonment Railway Station", detail: "Train station · Multan", latitude: 30.1804, longitude: 71.4446, zoom: 16 },
];

export type MapDestination = Coordinate & { zoom: number };

export function coordinates(text: string): Coordinate | null {
  const match = /^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/.exec(text.trim());
  if (!match) return null;
  const [, latitude, longitude] = match.map(Number);
  return Math.abs(latitude) <= 85 && Math.abs(longitude) <= 180 ? { latitude, longitude } : null;
}

export function resolvePlace(text: string): Coordinate | null {
  return places.find(({ name }) => name.toLowerCase() === text.trim().toLowerCase()) ?? coordinates(text);
}
