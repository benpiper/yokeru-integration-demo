const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/* ── Queries ─────────────────────────────────────────────────────── */

import type {
  CallRow,
  DispatchResponse,
  HealthInfo,
  ReplayResponse,
  Stats,
  WebhookEventRow,
  SimulateWebhookResponse,
} from "../types/api";

export function fetchCalls(
  status?: string,
  outcome?: string,
  limit = 100,
  offset = 0,
): Promise<CallRow[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (outcome) params.set("outcome", outcome);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return request<CallRow[]>(`/api/calls?${params}`);
}

export function fetchStats(): Promise<Stats> {
  return request<Stats>("/api/stats");
}

export function fetchEvents(limit = 50, offset = 0): Promise<WebhookEventRow[]> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return request<WebhookEventRow[]>(`/api/events?${params}`);
}

export function fetchHealth(): Promise<HealthInfo> {
  return request<HealthInfo>("/api/health");
}

/* ── Mutations ───────────────────────────────────────────────────── */

export function dispatchCall(patientId: string): Promise<DispatchResponse> {
  return request<DispatchResponse>(`/api/dispatch/${encodeURIComponent(patientId)}`, {
    method: "POST",
  });
}

export function replayPending(): Promise<ReplayResponse> {
  return request<ReplayResponse>("/api/replay", { method: "POST" });
}

export function simulateWebhook(correlationId: string, eventType: string): Promise<SimulateWebhookResponse> {
  return request<SimulateWebhookResponse>("/api/simulate-webhook", {
    method: "POST",
    body: JSON.stringify({ correlation_id: correlationId, event_type: eventType }),
  });
}
