import { useEffect, useState, useRef } from "react";
import { Routes, Route, Link, useLocation } from "react-router-dom";
import { RuleListPage } from "./pages/RuleListPage";
import { RuleDetailPage } from "./pages/RuleDetailPage";
import { PipelinePage } from "./pages/PipelinePage";
import { EnforcerPage } from "./pages/EnforcerPage";
import { TestSpritePage } from "./pages/TestSpritePage";
import { StatusPage } from "./pages/StatusPage";
import { VideosPage } from "./pages/VideosPage";
import {
  fetchCredentialsStatus,
  fetchRepos,
  startQuickRun,
  type RepoItem,
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

const repoSelectStyle: React.CSSProperties = {
  padding: "8px 14px",
  borderRadius: "8px",
  border: "2px solid #3b82f6",
  background: "#0f172a",
  color: "#e2e8f0",
  fontSize: "14px",
  fontWeight: 600,
  cursor: "pointer",
  minWidth: "220px",
  maxWidth: "320px",
};

export function App() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [repos, setRepos] = useState<RepoItem[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<number | null>(() => {
    const saved = localStorage.getItem("selectedRepoId");
    return saved ? Number(saved) : null;
  });
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
    fetchRepos()
      .then((data) => {
        setRepos(data);
        // Auto-select first repo if none selected
        if (!localStorage.getItem("selectedRepoId") && data.length > 0) {
          setSelectedRepoId(data[0].id);
          localStorage.setItem("selectedRepoId", String(data[0].id));
        }
      })
      .catch(() => {});
  }, []);

  const [showAddRepo, setShowAddRepo] = useState(false);
  const [newRepoUrl, setNewRepoUrl] = useState("");
  const [addingRepo, setAddingRepo] = useState(false);
  const addRepoInputRef = useRef<HTMLInputElement>(null);

  const handleRepoChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (val === "__add_new__") {
      setShowAddRepo(true);
      // Reset select to current value
      e.target.value = selectedRepoId ? String(selectedRepoId) : "";
      setTimeout(() => addRepoInputRef.current?.focus(), 50);
      return;
    }
    const numVal = val ? Number(val) : null;
    setSelectedRepoId(numVal);
    if (numVal !== null) {
      localStorage.setItem("selectedRepoId", String(numVal));
    } else {
      localStorage.removeItem("selectedRepoId");
    }
  };

  const handleAddRepo = async () => {
    const url = newRepoUrl.trim();
    if (!url) return;
    setAddingRepo(true);
    try {
      await startQuickRun(url, 5);
      setNewRepoUrl("");
      setShowAddRepo(false);
      // Reload repos after a short delay to let the job create the repo entry
      setTimeout(() => {
        fetchRepos()
          .then((data) => {
            setRepos(data);
            // Auto-select the newly added repo (likely the last one or matching URL)
            const match = data.find((r) => url.includes(r.full_name));
            if (match) {
              setSelectedRepoId(match.id);
              localStorage.setItem("selectedRepoId", String(match.id));
            }
          })
          .catch(() => {});
      }, 3000);
    } catch {
      alert("Failed to start repo import. Check the Pipeline page for details.");
    } finally {
      setAddingRepo(false);
    }
  };

  const isActive = (path: string) =>
    path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);

  return (
    <>
      <header style={headerStyle}>
        <Link to="/" style={logoStyle}>
          Code Ruler
        </Link>

        <nav style={{ display: "flex", alignItems: "center", gap: "4px", marginLeft: "8px" }}>
          <Link to="/" style={navLinkStyle(isActive("/") && !isActive("/pipeline") && !isActive("/enforcers") && !isActive("/tests") && !isActive("/videos") && !isActive("/status"))}>
            Rules
          </Link>
          <Link to="/pipeline" style={navLinkStyle(isActive("/pipeline"))}>
            Pipeline
          </Link>
          <Link to="/enforcers" style={navLinkStyle(isActive("/enforcers"))}>
            Enforcers
          </Link>
          <Link to="/tests" style={navLinkStyle(isActive("/tests"))}>
            Tests
          </Link>
          <Link to="/videos" style={navLinkStyle(isActive("/videos"))}>
            Videos
          </Link>
          <Link to="/status" style={navLinkStyle(isActive("/status"))}>
            Status
          </Link>
        </nav>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ color: "#94a3b8", fontSize: "12px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Repo
            </span>
            <select
              value={selectedRepoId ?? ""}
              onChange={handleRepoChange}
              style={repoSelectStyle}
            >
              <option value="">Select a repository...</option>
              {repos.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.full_name} ({r.total_rules})
                </option>
              ))}
              <option value="__add_new__">+ Add new...</option>
            </select>
          </div>

          {showAddRepo && (
            <div style={{
              position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
              background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center",
              justifyContent: "center", zIndex: 1000,
            }}
              onClick={(e) => { if (e.target === e.currentTarget) setShowAddRepo(false); }}
            >
              <div style={{
                background: "#fff", borderRadius: "12px", padding: "24px",
                width: "460px", maxWidth: "90vw",
              }}>
                <h3 style={{ margin: "0 0 16px", fontSize: "18px", fontWeight: 600 }}>
                  Add Repository
                </h3>
                <label style={{ fontSize: "13px", fontWeight: 500, color: "#475569", display: "block", marginBottom: "4px" }}>
                  GitHub Repository URL
                </label>
                <input
                  ref={addRepoInputRef}
                  type="text"
                  placeholder="https://github.com/owner/repo"
                  value={newRepoUrl}
                  onChange={(e) => setNewRepoUrl(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleAddRepo(); }}
                  style={{
                    width: "100%", padding: "8px 12px", borderRadius: "6px",
                    border: "1px solid #d1d5db", fontSize: "14px", marginBottom: "16px",
                    boxSizing: "border-box",
                  }}
                  disabled={addingRepo}
                />
                <p style={{ fontSize: "12px", color: "#64748b", margin: "0 0 16px" }}>
                  This will fetch recent PRs and extract rules from the repository.
                </p>
                <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                  <button
                    onClick={() => setShowAddRepo(false)}
                    style={{
                      padding: "8px 16px", borderRadius: "6px", border: "1px solid #d1d5db",
                      background: "#fff", cursor: "pointer", fontSize: "14px",
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleAddRepo}
                    disabled={addingRepo || !newRepoUrl.trim()}
                    style={{
                      padding: "8px 16px", borderRadius: "6px", border: "none",
                      background: addingRepo ? "#93c5fd" : "#3b82f6", color: "#fff",
                      cursor: addingRepo ? "not-allowed" : "pointer", fontSize: "14px",
                      fontWeight: 600,
                    }}
                  >
                    {addingRepo ? "Adding..." : "Add & Import"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        <Link
          to="/status"
          style={{
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
          <Route path="/" element={<RuleListPage repoId={selectedRepoId} />} />
          <Route path="/rules/:slug" element={<RuleDetailPage repoId={selectedRepoId} />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/enforcers" element={<EnforcerPage repoId={selectedRepoId} />} />
          <Route path="/tests" element={<TestSpritePage repoId={selectedRepoId} />} />
          <Route path="/videos" element={<VideosPage />} />
          <Route path="/status" element={<StatusPage />} />
        </Routes>
      </main>
    </>
  );
}
