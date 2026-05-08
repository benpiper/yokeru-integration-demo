/** Row from the call_buffer table. */
export interface CallRow {
  correlation_id: string;
  patient_id: string;
  status: "PENDING" | "DELIVERED" | "FAILED_PERMANENT";
  synced: number;
  attempts: number;
  reason: string | null;
  outcome: "completed" | "failed" | "no_answer" | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Aggregated statistics from /api/stats. */
export interface Stats {
  total: number;
  pending: number;
  delivered: number;
  failed_permanent: number;
  completed: number;
  failed: number;
  no_answer: number;
}

/** Row from the webhook_events table. */
export interface WebhookEventRow {
  event_id: string;
  event_type: string;
  received_at: string;
  payload: string;
}

/** Detailed health from /api/health. */
export interface HealthInfo {
  status: string;
  db_ok: boolean;
  breaker_state: "closed" | "open" | "half_open" | "unknown";
  pending_count: number;
}

/** Response from POST /api/dispatch/:id */
export interface DispatchResponse {
  correlation_id: string;
  message: string;
}

/** Response from POST /api/replay */
export interface ReplayResponse {
  replayed: number;
  message: string;
}

/** Response from POST /api/simulate-webhook */
export interface SimulateWebhookResponse {
  status: string;
  event_id: string;
  outcome?: string | null;
}
