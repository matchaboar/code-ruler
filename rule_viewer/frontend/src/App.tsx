import { useEffect, useState } from "react";
import { Routes, Route, Link, useLocation } from "react-router-dom";
import { RuleListPage } from "./pages/RuleListPage";
import { RuleDetailPage } from "./pages/RuleDetailPage";
import { PipelinePage } from "./pages/PipelinePage";
import { StatusPage } from "./pages/StatusPage";
import {
  fetchCredentialsStatus,
  type ServiceStatus,
} from "./api/client";

const headerStyle: React.CSSProperties = {
  background: "#1a1a2e",
  color: "#fff",
  padding: "12px 24px",
  display: "flex",
  alignItems: "center",
  gap: "16px",
};

const logoStyle: React.CSSProperties = {
  fontSize: "20px",
  fontWeight: 700,
  color: "#fff",
  textDecoration: "none",
};

const containerStyle: React.CSSProperties = {
  maxWidth: "1200px",
  margin: "0 auto",
  padding: "24px",
};

const navLinkStyle = (active: boolean): React.CSSProperties => ({
  color: active ? "#fff" : "#94a3b8",
  fontSize: "14px",
  textDecoration: "none",
  padding: "4px 12px",
  borderRadius: "6px",
  fontWeight: active ? 600 : 400,
  borderBottom: active ? "2px solid #3b82f6" : "2px solid transparent",
  transition: "color 0.15s, border-color 0.15s",
});

function healthDotColor(services: ServiceStatus[], loading: boolean): string {
  if (loading) return "#facc15"; // yellow while loading
  if (services.length === 0) return "#facc15";
  return services.every((s) => s.ok) ? "#22c55e" : "#ef4444";
}

export function App() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const location = useLocation();

  useEffect(() => {
    fetchCredentialsStatus()
      .then((data) => setServices(data.services))
      .catch(() =>
        setServices([
          { name: "API", ok: false, detail: "Could not reach backend" },
        ])
      )
      .finally(() => setLoading(false));
  }, []);

  const isActive = (path: string) =>
    path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);

  return (
    <>
      <header style={headerStyle}>
        <Link to="/" style={logoStyle}>
          Code Ruler
        </Link>

        <nav style={{ display: "flex", alignItems: "center", gap: "4px", marginLeft: "8px" }}>
          <Link to="/" style={navLinkStyle(isActive("/") && !isActive("/pipeline") && !isActive("/status"))}>
            Rules
          </Link>
          <Link to="/pipeline" style={navLinkStyle(isActive("/pipeline"))}>
            Pipeline
          </Link>
          <Link to="/status" style={navLinkStyle(isActive("/status"))}>
            Status
          </Link>
        </nav>

        <Link
          to="/status"
          style={{
            marginLeft: "auto",
            display: "flex",
            alignItems: "center",
            textDecoration: "none",
          }}
          title={loading ? "Checking services..." : services.every((s) => s.ok) ? "All services OK" : "Some services unavailable"}
        >
          <span
            style={{
              width: "10px",
              height: "10px",
              borderRadius: "50%",
              background: healthDotColor(services, loading),
              display: "inline-block",
            }}
          />
        </Link>
      </header>
      <main style={containerStyle}>
        <Routes>
          <Route path="/" element={<RuleListPage />} />
          <Route path="/rules/:slug" element={<RuleDetailPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/status" element={<StatusPage />} />
        </Routes>
      </main>
    </>
  );
}
