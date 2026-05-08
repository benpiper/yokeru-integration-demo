import { useState } from "react";
import type { CallRow } from "../../types/api";
import styles from "./CallTable.module.scss";

interface CallTableProps {
  calls: CallRow[];
}

const STATUS_FILTERS = ["ALL", "PENDING", "DELIVERED", "FAILED_PERMANENT"] as const;

function statusBadgeClass(status: string): string {
  if (status === "PENDING") return styles.pending;
  if (status === "DELIVERED") return styles.delivered;
  return styles.failedPermanent;
}

function outcomeClass(outcome: string | null): string {
  if (outcome === "completed") return styles.completed;
  if (outcome === "failed") return styles.failed;
  if (outcome === "no_answer") return styles.noAnswer;
  return "";
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function CallTable({ calls }: CallTableProps) {
  const [filter, setFilter] = useState<string>("ALL");

  const filtered = filter === "ALL" ? calls : calls.filter((c) => c.status === filter);

  return (
    <div className={styles.wrapper} data-testid="call-table">
      <div className={styles.toolbar}>
        <span className={styles.sectionTitle}>Call Buffer</span>
        <div className={styles.filters}>
          {STATUS_FILTERS.map((f) => (
            <button
              key={f}
              className={`${styles.filterBtn} ${filter === f ? styles.active : ""}`}
              onClick={() => setFilter(f)}
              data-testid={`filter-${f.toLowerCase()}`}
            >
              {f === "ALL" ? "All" : f === "FAILED_PERMANENT" ? "Failed" : f.charAt(0) + f.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.tableScroll}>
        {filtered.length === 0 ? (
          <div className={styles.empty}>No calls match this filter</div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Correlation ID</th>
                <th>Patient</th>
                <th>Status</th>
                <th>Outcome</th>
                <th>Attempts</th>
                <th>Created</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.correlation_id}>
                  <td className={styles.mono} title={c.correlation_id}>
                    {c.correlation_id.slice(0, 8)}…
                  </td>
                  <td>{c.patient_id}</td>
                  <td>
                    <span className={`${styles.badge} ${statusBadgeClass(c.status)}`}>
                      {c.status === "FAILED_PERMANENT" ? "FAILED" : c.status}
                    </span>
                  </td>
                  <td>
                    {c.outcome ? (
                      <span className={`${styles.outcomeBadge} ${outcomeClass(c.outcome)}`}>
                        {c.outcome === "no_answer" ? "No Answer" : c.outcome}
                      </span>
                    ) : (
                      <span className={styles.mono}>—</span>
                    )}
                  </td>
                  <td>{c.attempts}</td>
                  <td className={styles.mono}>{formatTime(c.created_at)}</td>
                  <td className={styles.mono}>{formatTime(c.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
