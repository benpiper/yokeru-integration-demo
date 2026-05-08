import { useState } from "react";
import { simulateWebhook } from "../../hooks/api";
import type { CallRow } from "../../types/api";
import styles from "./Simulator.module.scss";

interface SimulatorProps {
  calls: CallRow[];
  onAction?: () => void;
}

const OUTCOMES = [
  { value: "call.completed", label: "Call Completed (Answered/Finished)" },
  { value: "call.no_answer", label: "Call No Answer (Voicemail/Timeout)" },
  { value: "call.failed", label: "Call Failed (Number invalid/Error)" },
];

export function Simulator({ calls, onAction }: SimulatorProps) {
  const pendingCalls = calls.filter((c) => c.status === "DELIVERED" || c.status === "PENDING");
  
  const [selectedCall, setSelectedCall] = useState<string>("");
  const [outcome, setOutcome] = useState<string>("call.completed");
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; message: string } | null>(null);

  async function handleSimulate(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedCall) return;

    setLoading(true);
    setFeedback(null);
    try {
      await simulateWebhook(selectedCall, outcome);
      setFeedback({
        kind: "success",
        message: `✓ Webhook sent successfully for correlation: ${selectedCall.slice(0, 8)}…`,
      });
      setSelectedCall("");
      onAction?.();
    } catch (err) {
      setFeedback({
        kind: "error",
        message: `✗ Simulation failed: ${err instanceof Error ? err.message : String(err)}`,
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>Yokeru Voice Platform Simulator</h2>
      <p className={styles.description}>
        Use this tool to simulate incoming webhooks from Yokeru. You can mock call completions, 
        failures, or no-answers for pending or delivered welfare checks.
      </p>

      <form onSubmit={handleSimulate}>
        <div className={styles.formGroup}>
          <label className={styles.label}>Select Target Call</label>
          <select 
            className={styles.select} 
            value={selectedCall} 
            onChange={(e) => setSelectedCall(e.target.value)}
            disabled={loading || pendingCalls.length === 0}
          >
            <option value="">-- Select an active call --</option>
            {pendingCalls.map((c) => (
              <option key={c.correlation_id} value={c.correlation_id}>
                {c.patient_id} ({c.status}) - {c.correlation_id.slice(0, 8)}…
              </option>
            ))}
          </select>
          {pendingCalls.length === 0 && (
            <p className={styles.label} style={{ marginTop: '8px', color: 'var(--color-warning)' }}>
              No active calls to simulate. Dispatch a welfare check first.
            </p>
          )}
        </div>

        <div className={styles.formGroup}>
          <label className={styles.label}>Simulated Outcome Event</label>
          <select 
            className={styles.select} 
            value={outcome} 
            onChange={(e) => setOutcome(e.target.value)}
            disabled={loading}
          >
            {OUTCOMES.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <button 
          type="submit" 
          className={styles.btn} 
          disabled={loading || !selectedCall}
        >
          {loading ? "Sending Webhook…" : "Send Simulated Webhook"}
        </button>
      </form>

      {feedback && (
        <div className={feedback.kind === "success" ? styles.feedbackSuccess : styles.feedbackError}>
          {feedback.message}
        </div>
      )}
    </div>
  );
}
