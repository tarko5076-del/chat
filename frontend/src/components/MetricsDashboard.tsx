import { useGetMetricsQuery, useGetHealthQuery } from "../services/api";
import "./MetricsDashboard.css";

interface MetricsData {
  requests_total: number;
  requests_2xx: number;
  requests_4xx: number;
  requests_5xx: number;
  avg_response_time_ms: number;
  error_rate_pct: number;
  uptime_seconds: number;
  llm_calls_total: number;
  llm_calls_success: number;
  llm_success_rate_pct: number;
  llm_tokens_prompt: number;
  llm_tokens_completion: number;
  tool_calls_total: number;
  tool_calls_success: number;
  tool_success_rate_pct: number;
  orders_placed: number;
  payments_processed: number;
  reservations_made: number;
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const parts: string[] = [];
  if (d > 0) parts.push(`${d}d`);
  if (h > 0) parts.push(`${h}h`);
  if (m > 0) parts.push(`${m}m`);
  parts.push(`${s}s`);
  return parts.join(" ");
}

function StatCard({
  label,
  value,
  sublabel,
  color = "#2fdd71",
  icon,
}: {
  label: string;
  value: string | number;
  sublabel?: string;
  color?: string;
  icon?: string;
}) {
  return (
    <div className="metrics-card" style={{ "--accent": color } as React.CSSProperties}>
      {icon && <span className="metrics-card__icon">{icon}</span>}
      <div className="metrics-card__body">
        <span className="metrics-card__value">{value}</span>
        <span className="metrics-card__label">{label}</span>
        {sublabel && <span className="metrics-card__sublabel">{sublabel}</span>}
      </div>
    </div>
  );
}

function Gauge({
  value,
  max,
  label,
  color = "#2fdd71",
}: {
  value: number;
  max: number;
  label: string;
  color?: string;
}) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="metrics-gauge">
      <div className="metrics-gauge__bar" style={{ width: `${pct}%`, backgroundColor: color }} />
      <div className="metrics-gauge__label">
        <span>{label}</span>
        <span>
          {value}/{max}
        </span>
      </div>
    </div>
  );
}

export function MetricsDashboard() {
  const { data: metrics, isLoading: metricsLoading, error: metricsError } = useGetMetricsQuery(undefined, {
    pollingInterval: 10000,
  });
  const { data: health, isLoading: healthLoading } = useGetHealthQuery(undefined, {
    pollingInterval: 30000,
  });

  const m = (metrics ?? {}) as MetricsData;

  const loading = metricsLoading && healthLoading;

  if (loading) {
    return (
      <div className="metrics-dashboard">
        <div className="metrics-dashboard__loading">Loading metrics...</div>
      </div>
    );
  }

  if (metricsError) {
    return (
      <div className="metrics-dashboard">
        <div className="metrics-dashboard__error">
          Could not load metrics. Make sure the backend is running.
        </div>
      </div>
    );
  }

  return (
    <div className="metrics-dashboard">
      <header className="metrics-dashboard__header">
        <h1>System Metrics</h1>
        <div className="metrics-dashboard__status-bar">
          <span
            className={`metrics-dashboard__status-dot ${
              health?.status === "ok"
                ? "metrics-dashboard__status-dot--ok"
                : "metrics-dashboard__status-dot--error"
            }`}
          />
          <span className="metrics-dashboard__status-text">
            {health?.status === "ok" ? "All systems healthy" : "Degraded"}
          </span>
          <span className="metrics-dashboard__uptime">
            Uptime: {formatUptime(m.uptime_seconds ?? 0)}
          </span>
        </div>
      </header>

      {/* API Request Metrics */}
      <section className="metrics-section">
        <h2 className="metrics-section__title">API Requests</h2>
        <div className="metrics-grid">
          <StatCard
            label="Total Requests"
            value={(m.requests_total ?? 0).toLocaleString()}
            color="#0dafef"
            icon="📡"
          />
          <StatCard
            label="Avg Response Time"
            value={`${(m.avg_response_time_ms ?? 0).toFixed(1)}ms`}
            sublabel={`from ${(m.requests_total ?? 0)} requests`}
            color={m.avg_response_time_ms > 1000 ? "#ff7194" : "#2fdd71"}
            icon="⚡"
          />
          <StatCard
            label="Error Rate"
            value={`${(m.error_rate_pct ?? 0).toFixed(2)}%`}
            sublabel={`${m.requests_5xx ?? 0} server errors`}
            color={m.error_rate_pct > 1 ? "#ff7194" : "#2fdd71"}
            icon="⚠️"
          />
        </div>
        <div className="metrics-subsection">
          <Gauge
            value={m.requests_2xx ?? 0}
            max={m.requests_total || 1}
            label="2xx"
            color="#2fdd71"
          />
          <Gauge
            value={m.requests_4xx ?? 0}
            max={m.requests_total || 1}
            label="4xx"
            color="#ffc107"
          />
          <Gauge
            value={m.requests_5xx ?? 0}
            max={m.requests_total || 1}
            label="5xx"
            color="#ff7194"
          />
        </div>
      </section>

      {/* LLM Metrics */}
      <section className="metrics-section">
        <h2 className="metrics-section__title">LLM Usage</h2>
        <div className="metrics-grid">
          <StatCard
            label="LLM Calls"
            value={(m.llm_calls_total ?? 0).toLocaleString()}
            sublabel={`${(m.llm_success_rate_pct ?? 100).toFixed(1)}% success`}
            color={m.llm_success_rate_pct < 90 ? "#ff7194" : "#2fdd71"}
            icon="🤖"
          />
          <StatCard
            label="Prompt Tokens"
            value={(m.llm_tokens_prompt ?? 0).toLocaleString()}
            color="#0dafef"
            icon="📝"
          />
          <StatCard
            label="Completion Tokens"
            value={(m.llm_tokens_completion ?? 0).toLocaleString()}
            color="#a855f7"
            icon="💬"
          />
        </div>
      </section>

      {/* Business Metrics */}
      <section className="metrics-section">
        <h2 className="metrics-section__title">Business Activity</h2>
        <div className="metrics-grid">
          <StatCard
            label="Orders Placed"
            value={(m.orders_placed ?? 0).toLocaleString()}
            color="#0dafef"
            icon="🍽️"
          />
          <StatCard
            label="Payments Processed"
            value={(m.payments_processed ?? 0).toLocaleString()}
            color="#2fdd71"
            icon="💳"
          />
          <StatCard
            label="Reservations Made"
            value={(m.reservations_made ?? 0).toLocaleString()}
            color="#ffc107"
            icon="📅"
          />
        </div>
      </section>

      {/* Tool Execution */}
      <section className="metrics-section">
        <h2 className="metrics-section__title">Tool Execution</h2>
        <div className="metrics-grid">
          <StatCard
            label="Tool Calls"
            value={(m.tool_calls_total ?? 0).toLocaleString()}
            sublabel={`${(m.tool_success_rate_pct ?? 100).toFixed(1)}% success`}
            color={m.tool_success_rate_pct < 90 ? "#ff7194" : "#2fdd71"}
            icon="🔧"
          />
        </div>
      </section>

      {/* Health Details */}
      {health && (
        <section className="metrics-section">
          <h2 className="metrics-section__title">Health Check</h2>
          <div className="metrics-health-list">
            {Object.entries(health)
              .filter(([k]) => k !== "status" && k !== "uptime_seconds" && k !== "timestamp")
              .map(([key, value]) => (
                <div key={key} className="metrics-health-row">
                  <span className="metrics-health-row__key">{key}</span>
                  <span
                    className={`metrics-health-row__value ${
                      value === "ok"
                        ? "metrics-health-row__value--ok"
                        : typeof value === "string" && value.includes("error")
                        ? "metrics-health-row__value--error"
                        : "metrics-health-row__value--warn"
                    }`}
                  >
                    {String(value)}
                  </span>
                </div>
              ))}
          </div>
        </section>
      )}

      <footer className="metrics-dashboard__footer">
        <span>Auto-refreshes every 10s</span>
        <span>Timestamp: {new Date().toLocaleTimeString()}</span>
      </footer>
    </div>
  );
}
