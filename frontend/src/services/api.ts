import type { ChatContext, ChatResult } from "../types/assistant";

import type {
  ApiFailure, ApiSuccess, Bounds, Coordinate, Health, Incident, IncidentAnalysis, IncidentDraft, IncidentFilters,
  IncidentPage, Mode, ZoneCollection,
} from "../types/api";
import type { Heatmap, HeatmapPeriod } from "../types/heatmap";
import type { RouteComparison, RouteOptions } from "../types/routes";

const apiBase = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");
export const mapPageSize = 100;

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}/api${path}`, init);
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ApiError("The MehfoozAI API could not be reached. Check your connection and retry.", 0);
  }

  const body: ApiSuccess<T> | ApiFailure | null = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error;
    throw new ApiError(error?.details?.[0]?.message ?? error?.message ?? `Request failed (${response.status}).`, response.status);
  }
  if (body?.error !== null || body.data == null) {
    throw new ApiError("The API returned an unexpected response.", response.status);
  }
  return body.data;
}

function query(params: Record<string, string | number | undefined>) {
  const values = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) values.set(key, String(value));
  }
  return values.toString();
}

export function getHealth(signal?: AbortSignal) {
  return request<Health>("/health", { signal });
}

export function getIncidents(bounds: Bounds, mode: Mode, filters: IncidentFilters, signal: AbortSignal) {
  return request<IncidentPage>(`/incidents?${query({ ...bounds, ...filters, mode, limit: mapPageSize })}`, { signal });
}

export function getOfficialZones(bounds: Bounds, mode: Mode, signal: AbortSignal) {
  return request<ZoneCollection>(`/official-zones?${query({ ...bounds, mode })}`, { signal });
}

export function submitIncident(draft: IncidentDraft, token: string, signal: AbortSignal) {
  return request<Incident>("/incidents", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(draft),
    signal,
  });
}

export function getHeatmap(bounds: Bounds, mode: Mode, period: HeatmapPeriod, from: string | undefined, to: string | undefined, signal: AbortSignal) {
  return request<Heatmap>(`/heatmap?${query({ ...bounds, mode, period, from, to })}`, { signal, cache: "no-store" });
}

export function requestIncidentAnalysis(id: string, token: string, start: boolean, signal: AbortSignal) {
  return request<IncidentAnalysis>(`/ai/incidents/${encodeURIComponent(id)}/${start ? "analyze" : "analysis"}`, {
    method: start ? "POST" : "GET",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
    signal,
  });
}

export function findRoutes(origin: Coordinate, destination: Coordinate, departure: string | undefined, signal: AbortSignal) {
  const pair = ({ latitude, longitude }: Coordinate) => `${longitude},${latitude}`;
  return request<RouteOptions>(`/routes?${query({ origin: pair(origin), destination: pair(destination), departure_at: departure })}`, {
    signal, cache: "no-store",
  });
}

export function compareRoutes(ids: string[], mode: Mode, signal: AbortSignal) {
  return request<RouteComparison>("/routes/compare", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ route_ids: ids, mode, preference: "balanced" }), signal, cache: "no-store",
  });
}

export function askAssistant(message: string, mode: Mode, conversationId: string | undefined, context: ChatContext, token: string | undefined, signal: AbortSignal) {
  return request<ChatResult>("/ai/chat", {
    method: "POST", signal, cache: "no-store",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ ...context, message, mode, conversation_id: conversationId }),
  });
}

export function clearAssistant(mode: Mode, conversationId: string, token?: string) {
  return request<{ cleared: boolean }>("/ai/chat/clear", {
    method: "POST", cache: "no-store",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ mode, conversation_id: conversationId }),
  });
}
