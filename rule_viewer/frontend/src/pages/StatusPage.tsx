import { useEffect, useState, useCallback } from "react";
import {
  fetchCredentialsStatus,
  type ServiceStatus,
} from "../api/client";

const DD_SITE = "datadoghq.com";
const DD_LLM_OBS_URL = `https://app.${DD_SITE}/llm/traces`;
const DD_LLM_DASHBOARD_URL = `https://app.${DD_SITE}/llm/overview`;
const DD_APM_URL = `https://app.${DD_SITE}/apm/traces?query=service:code-ruler`;

const cardStyle = (ok: boolean): React.CSSProperties => ({
  background: ok ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
  border: `1px solid ${ok ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
  borderRadius: "10px",
  padding: "20px 24px",
  display: "flex",
  alignItems: "center",
  gap: "16px",
});

const dotStyle = (ok: boolean): React.CSSProperties => ({
  width: "12px",
  height: "12px",
  borderRadius: "50%",
  background: ok ? "#22c55e" : "#ef4444",
  flexShrink: 0,
});

const ddLinkStyle: React.CSSProperties = {
  color: "#3b82f6",
  fontSize: "14px",
  textDecoration: "none",
  padding: "8px 16px",
  borderRadius: "6px",
  border: "1px solid rgba(59,130,246,0.3)",
  transition: "background 0.15s",
};

export function StatusPage() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    fetchCredentialsStatus()
      .then((data) => {
        setServices(data.services);
        setLastChecked(new Date());
      })
      .catch(() =>
        setServices([
          { name: "API", ok: false, detail: "Could not reach backend" },
        ])
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const ddOk = services.find((s) => s.name === "Datadog")?.ok ?? false;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "24px" }}>
        <h1 style={{ margin: 0, fontSize: "24px" }}>Service Status</h1>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          {lastChecked && (
            <span style={{ color: "#94a3b8", fontSize: "13px" }}>
              Last checked: {lastChecked.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={refresh}
            disabled={loading}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: "1px solid #334155",
              background: "#1e293b",
              color: "#e2e8f0",
              cursor: loading ? "not-allowed" : "pointer",
              fontSize: "13px",
            }}
          >
            {loading ? "Checking..." : "Refresh"}
          </button>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {services.map((s) => (
          <div key={s.name} style={cardStyle(s.ok)}>
            <span style={dotStyle(s.ok)} />
            <div>
              <div style={{ fontWeight: 600, fontSize: "16px" }}>{s.name}</div>
              <div style={{ color: "#94a3b8", fontSize: "13px", marginTop: "2px" }}>
                {s.detail}
              </div>
            </div>
            <span
              style={{
                marginLeft: "auto",
                fontWeight: 600,
                fontSize: "13px",
                color: s.ok ? "#4ade80" : "#f87171",
              }}
            >
              {s.ok ? "Connected" : "Unavailable"}
            </span>
          </div>
        ))}
      </div>

      {ddOk && (
        <div style={{ marginTop: "32px" }}>
          <h2 style={{ fontSize: "18px", marginBottom: "12px" }}>Datadog Dashboards</h2>
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
            <a href={DD_LLM_OBS_URL} target="_blank" rel="noopener noreferrer" style={ddLinkStyle}>
              LLM Traces
            </a>
            <a href={DD_LLM_DASHBOARD_URL} target="_blank" rel="noopener noreferrer" style={ddLinkStyle}>
              LLM Overview
            </a>
            <a href={DD_APM_URL} target="_blank" rel="noopener noreferrer" style={ddLinkStyle}>
              APM
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
