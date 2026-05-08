import { useCallback, useState } from "react";
import styles from "./App.module.scss";
import { CallTable } from "./components/CallTable/CallTable";
import { DispatchForm } from "./components/DispatchForm/DispatchForm";
import { EventLog } from "./components/EventLog/EventLog";
import { Header } from "./components/Header/Header";
import { Simulator } from "./components/Simulator/Simulator";
import { StatCard } from "./components/StatCard/StatCard";
import { fetchCalls, fetchEvents, fetchHealth, fetchStats } from "./hooks/api";
import { usePolling } from "./hooks/usePolling";

export function App() {
  const [activeTab, setActiveTab] = useState<"dashboard" | "simulator">("dashboard");

  const stableStats = useCallback(() => fetchStats(), []);
  const stableCalls = useCallback(() => fetchCalls(), []);
  const stableEvents = useCallback(() => fetchEvents(), []);
  const stableHealth = useCallback(() => fetchHealth(), []);

  const { data: stats, loading: statsLoading, error: statsError } = usePolling(stableStats, 5000);
  const { data: calls, refresh: refreshCalls } = usePolling(stableCalls, 5000);
  const { data: events, refresh: refreshEvents } = usePolling(stableEvents, 5000);
  const { data: health } = usePolling(stableHealth, 5000);

  function handleAction() {
    // Force an immediate refresh after dispatch / replay / simulation
    refreshCalls();
    refreshEvents();
  }

  if (statsLoading && !stats) {
    return (
      <>
        <Header health={null} />
        <div className={styles.loadingOverlay}>
          <div className={styles.spinner} />
          Connecting to agent…
        </div>
      </>
    );
  }

  return (
    <>
      <Header health={health} />

      <main className={styles.dashboard}>
        {statsError && (
          <div className={styles.errorBanner} data-testid="error-banner">
            ⚠ Failed to connect to backend: {statsError}
          </div>
        )}

        <div className={styles.tabs}>
          <button 
            className={`${styles.tab} ${activeTab === "dashboard" ? styles.active : ""}`}
            onClick={() => setActiveTab("dashboard")}
          >
            Dashboard
          </button>
          <button 
            className={`${styles.tab} ${activeTab === "simulator" ? styles.active : ""}`}
            onClick={() => setActiveTab("simulator")}
          >
            Simulator
          </button>
        </div>

        {activeTab === "dashboard" ? (
          <>
            {/* ── KPI Cards ──────────────────────────────── */}
            <div className={styles.statsGrid}>
              <StatCard
                label="Total Calls"
                value={stats?.total ?? 0}
                accent="#6366f1"
                delay={0}
              />
              <StatCard
                label="Delivered"
                value={stats?.delivered ?? 0}
                accent="#10b981"
                sub="Acknowledged by Yokeru"
                delay={50}
              />
              <StatCard
                label="Pending"
                value={stats?.pending ?? 0}
                accent="#a78bfa"
                sub="Awaiting dispatch"
                delay={100}
              />
              <StatCard
                label="Failed"
                value={stats?.failed_permanent ?? 0}
                accent="#ef4444"
                sub="Permanent failures"
                delay={150}
              />
              <StatCard
                label="Completed"
                value={stats?.completed ?? 0}
                accent="#10b981"
                sub="Call answered"
                delay={200}
              />
              <StatCard
                label="No Answer"
                value={stats?.no_answer ?? 0}
                accent="#f59e0b"
                sub="Webhook outcome"
                delay={250}
              />
            </div>

            {/* ── Dispatch + Placeholder top row ─────────── */}
            <div className={styles.topRow}>
              <DispatchForm onAction={handleAction} />
              <div>
                {/* Reserved for future: breaker history / retry metrics */}
              </div>
            </div>

            {/* ── Call Table + Event Log ──────────────────── */}
            <div className={styles.bottomRow}>
              <CallTable calls={calls ?? []} />
              <EventLog events={events ?? []} />
            </div>
          </>
        ) : (
          <Simulator calls={calls ?? []} onAction={handleAction} />
        )}
      </main>
    </>
  );
}
