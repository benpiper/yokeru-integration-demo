import { useState } from "react";
import { dispatchCall, replayPending } from "../../hooks/api";
import styles from "./DispatchForm.module.scss";

interface DispatchFormProps {
  onAction?: () => void;
}

interface Feedback {
  kind: "success" | "error";
  message: string;
}

export function DispatchForm({ onAction }: DispatchFormProps) {
  const [patientId, setPatientId] = useState("");
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  async function handleDispatch(e: React.FormEvent) {
    e.preventDefault();
    const id = patientId.trim();
    if (!id) return;
    setLoading(true);
    setFeedback(null);
    try {
      const res = await dispatchCall(id);
      setFeedback({
        kind: "success",
        message: `✓ Dispatched — correlation ${res.correlation_id.slice(0, 8)}…`,
      });
      setPatientId("");
      onAction?.();
    } catch (err) {
      setFeedback({
        kind: "error",
        message: `✗ ${err instanceof Error ? err.message : String(err)}`,
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleReplay() {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await replayPending();
      setFeedback({
        kind: "success",
        message: `✓ ${res.message}`,
      });
      onAction?.();
    } catch (err) {
      setFeedback({
        kind: "error",
        message: `✗ ${err instanceof Error ? err.message : String(err)}`,
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.wrapper} data-testid="dispatch-form">
      <div className={styles.sectionTitle}>Dispatch Welfare Check</div>

      <form className={styles.form} onSubmit={handleDispatch}>
        <input
          className={styles.input}
          type="text"
          placeholder="Patient ID (e.g. 12508044)"
          value={patientId}
          onChange={(e) => setPatientId(e.target.value)}
          disabled={loading}
          data-testid="patient-input"
        />
        <button
          type="submit"
          className={styles.btnPrimary}
          disabled={loading || !patientId.trim()}
          data-testid="dispatch-btn"
        >
          {loading ? "…" : "Dispatch"}
        </button>
      </form>

      <div className={styles.actions}>
        <button
          className={styles.btnSecondary}
          onClick={handleReplay}
          disabled={loading}
          data-testid="replay-btn"
        >
          ↻ Replay Pending
        </button>
      </div>

      {feedback && (
        <div
          className={feedback.kind === "success" ? styles.feedbackSuccess : styles.feedbackError}
          data-testid="dispatch-feedback"
        >
          {feedback.message}
        </div>
      )}
    </div>
  );
}
