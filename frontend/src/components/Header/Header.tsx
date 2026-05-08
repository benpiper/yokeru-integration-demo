import type { HealthInfo } from "../../types/api";
import styles from "./Header.module.scss";

interface HeaderProps {
  health: HealthInfo | null;
}

function breakerClass(state: string): string {
  if (state === "closed") return styles.closed;
  if (state === "open") return styles.open;
  if (state === "half_open") return styles.halfOpen;
  return styles.unknown;
}

export function Header({ health }: HeaderProps) {
  const healthStatus = health?.status ?? "loading";
  const breakerState = health?.breaker_state ?? "unknown";

  return (
    <header className={styles.header} data-testid="header">
      <div className={styles.brand}>
        <div className={styles.logoMark}>Y</div>
        <div>
          <div className={styles.title}>Yokeru Integration Agent</div>
          <div className={styles.subtitle}>Operations Dashboard</div>
        </div>
      </div>

      <div className={styles.status}>
        <div
          className={`${styles.healthBadge} ${
            healthStatus === "ok" ? styles.ok : healthStatus === "degraded" ? styles.degraded : ""
          }`}
          data-testid="health-badge"
        >
          <span className={styles.dot} />
          {healthStatus === "ok" ? "Healthy" : healthStatus === "degraded" ? "Degraded" : "…"}
        </div>

        <div
          className={`${styles.breakerChip} ${breakerClass(breakerState)}`}
          data-testid="breaker-chip"
          title="Circuit Breaker State"
        >
          ⚡ {breakerState.replace("_", " ")}
        </div>
      </div>
    </header>
  );
}
