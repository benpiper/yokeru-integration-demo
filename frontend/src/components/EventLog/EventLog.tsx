import type { WebhookEventRow } from "../../types/api";
import styles from "./EventLog.module.scss";

interface EventLogProps {
  events: WebhookEventRow[];
}

function dotClass(eventType: string): string {
  if (eventType.includes("completed")) return styles.completed;
  if (eventType.includes("failed")) return styles.failed;
  if (eventType.includes("no_answer")) return styles.noAnswer;
  return "";
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function EventLog({ events }: EventLogProps) {
  return (
    <div className={styles.wrapper} data-testid="event-log">
      <div className={styles.titleBar}>
        <span className={styles.sectionTitle}>Webhook Events</span>
        <span className={styles.count}>{events.length} events</span>
      </div>

      <div className={styles.list}>
        {events.length === 0 ? (
          <div className={styles.empty}>No webhook events received yet</div>
        ) : (
          events.map((evt) => (
            <div className={styles.item} key={evt.event_id}>
              <div className={`${styles.iconDot} ${dotClass(evt.event_type)}`} />
              <div className={styles.body}>
                <div className={styles.eventType}>{evt.event_type}</div>
                <div className={styles.meta} title={evt.event_id}>
                  {evt.event_id}
                </div>
              </div>
              <div className={styles.time}>{formatTime(evt.received_at)}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
