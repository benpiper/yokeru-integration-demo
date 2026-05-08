import styles from "./StatCard.module.scss";

interface StatCardProps {
  label: string;
  value: number | string;
  accent?: string;
  sub?: string;
  delay?: number;
}

export function StatCard({ label, value, accent, sub, delay = 0 }: StatCardProps) {
  return (
    <div
      className={styles.card}
      style={
        {
          "--accent": accent,
          animationDelay: `${delay}ms`,
        } as React.CSSProperties
      }
      data-testid={`stat-${label.toLowerCase().replace(/\s+/g, "-")}`}
    >
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>{value}</span>
      {sub && <span className={styles.sub}>{sub}</span>}
    </div>
  );
}
